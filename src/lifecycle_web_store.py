"""Durable Web execution, separate from deterministic automation and acceptance."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from src.auth_drivers.lifecycle_web_models import WebModelError
from src.auth_drivers.lifecycle_web_usage import project_usage_report, token_totals, validate_usage_report
from src.lifecycle_journal_codec import canonical_json, digest_json
from src.lifecycle_public_sources import PublicSourcePage, SourceReadLimits, _capture_digest, _page_material_digest, canonical_source_url, validate_source_read_report
from src.lifecycle_web_schema import RUNNING, TERMINAL, WebJournalError, install_web_journal, verify_web_journal
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_schema import assert_lifecycle_writes_available
from src.security_lifecycle_web_contract import ExecutionSelection, PublicInvestigationInput, RunControl, validate_selection
from src.security_lifecycle_web_finding import validate_finding
from src.lifecycle_source_context import parse_source_context


LEASE_SECONDS = 60
JOURNAL_BUSY_SECONDS = 45
_MISSING_SOURCE_URLS = object()


@dataclass(frozen=True)
class WebInvestigationOptions:
    """Decode the existing journal header without importing an orchestrator."""

    max_sources: int
    max_source_requests: int
    max_redirects: int
    max_source_bytes: int
    source_timeout_seconds: float
    model_timeout_seconds: float
    max_search_uses: int
    output_token_limit: int | None
    effort: str | None
    max_decoded_source_bytes: int | None = None

    def __post_init__(self):
        if (type(self.max_sources) is not int or self.max_sources <= 0
                or type(self.max_search_uses) is not int or self.max_search_uses <= 0
                or type(self.model_timeout_seconds) not in (int, float)
                or not math.isfinite(self.model_timeout_seconds) or self.model_timeout_seconds <= 0):
            raise ValueError("web_investigation_limits")
        SourceReadLimits(self.max_source_requests, self.max_redirects, self.max_source_bytes, self.source_timeout_seconds,
                         self.max_decoded_source_bytes)


def _identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", value):
        raise WebJournalError("web_identity_invalid")
    return value


def _source_gaps(failures, pages, *, max_sources, urls=_MISSING_SOURCE_URLS):
    """Join host-observed failures to admitted URLs; legacy URLs stay unknown."""
    if (type(failures) is not dict
            or any(not isinstance(key, str) or not re.fullmatch(r"source-[1-9][0-9]*", key)
                   or not isinstance(reason, str) or not re.fullmatch(r"[a-z_]{1,100}", reason)
                   for key, reason in failures.items())
            or set(failures) & set(pages) or len(failures) + len(pages) > max_sources):
        raise WebJournalError("web_source_gaps_invalid")
    if urls is not _MISSING_SOURCE_URLS:
        if type(urls) is not dict or set(urls) != set(failures):
            raise WebJournalError("web_source_gaps_invalid")
        try:
            if any(canonical_source_url(url) != url for url in urls.values()):
                raise ValueError("url")
        except (TypeError, ValueError):
            raise WebJournalError("web_source_gaps_invalid") from None
    return [{"url": None if urls is _MISSING_SOURCE_URLS else urls[key], "reason": failures[key]}
            for key in sorted(failures, key=lambda identity: int(identity.split("-")[1]))]


@dataclass(frozen=True)
class ValidatedWebRead:
    """Request-local source validation; mutable profile decisions are not cached."""

    path: Path
    run_id: str
    binding: tuple
    material: dict

    def on_connection(self, conn, run_id):
        database = next((row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main"), None)
        if (not conn.in_transaction or self.run_id != run_id or not database
                or Path(database).resolve() != self.path):
            raise WebJournalError("web_journal_integrity")
        if LifecycleWebStore._review_binding(conn, run_id) != self.binding:
            raise WebJournalError("web_journal_integrity")
        return self.material


class LifecycleWebStore:
    def __init__(self, path, *, clock=None):
        self.path = Path(path).resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def _now(self):
        return instant(self.clock()).isoformat()

    @contextmanager
    def connection(self, *, write=False):
        conn = None
        try:
            conn = sqlite3.connect(self.path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=JOURNAL_BUSY_SECONDS)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            verify_web_journal(conn)
            if write:
                assert_lifecycle_writes_available(conn)
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            if write:
                conn.commit()
        except sqlite3.Error:
            raise WebJournalError("web_recording_unavailable") from None
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _row(conn, run_id):
        row = conn.execute("SELECT * FROM lifecycle_web_runs WHERE run_id=?", (_identity(run_id),)).fetchone()
        if row is None:
            raise KeyError(run_id)
        try:
            header = json.loads(row["header_json"])
            if digest_json(header) != row["header_sha256"] or header["case_id"] != row["case_id"] or header["version"] != 1:
                raise ValueError("binding")
        except (ValueError, KeyError, TypeError):
            raise WebJournalError("web_journal_integrity") from None
        return dict(row), header

    def _owned(self, conn, run_id, owner):
        row, header = self._row(conn, run_id)
        if row["owner"] != owner:
            raise WebJournalError("web_owner_changed")
        if row["status"] not in RUNNING or instant(row["lease_until"]) <= instant(self._now()):
            raise WebJournalError("web_run_not_running")
        return row, header

    def start(self, *, case_id, observation_sha256, request, selection, options, owner, request_key, credential_generation=None):
        _identity(owner)
        _identity(request_key)
        _identity(case_id)
        if not isinstance(observation_sha256, str) or not re.fullmatch("[0-9a-f]{64}", observation_sha256):
            raise WebJournalError("web_identity_invalid")
        request = PublicInvestigationInput.model_validate(request.model_dump())
        selection = validate_selection(**asdict(selection))
        options.__post_init__()
        if credential_generation is not None and not re.fullmatch("[0-9a-f]{64}", credential_generation):
            raise WebJournalError("web_identity_invalid")
        header = {"version": 1, "case_id": case_id, "observation_sha256": observation_sha256,
                  "request": request.model_dump(), "selection": asdict(selection), "options": asdict(options),
                  "credential_generation": credential_generation}
        at = self._now()
        with self.connection(write=True) as conn:
            existing = conn.execute("SELECT run_id,header_sha256 FROM lifecycle_web_runs WHERE request_key=?", (request_key,)).fetchone()
            if existing is not None:
                if existing["header_sha256"] != digest_json(header):
                    raise WebJournalError("web_request_identity_changed")
                return {"run_id": existing["run_id"], "created": False}
            case = conn.execute("SELECT ticker FROM security_lifecycle_cases WHERE case_id=?", (case_id,)).fetchone()
            if case is None or case["ticker"] != request.ticker:
                raise WebJournalError("web_case_identity_changed")
            if conn.execute("SELECT 1 FROM lifecycle_web_runs WHERE case_id=? AND status IN ('queued','searching','reading_sources','analyzing')", (case_id,)).fetchone():
                raise WebJournalError("web_investigation_running")
            run_id = "lwr_" + uuid4().hex
            conn.execute("INSERT INTO lifecycle_web_runs (run_id,case_id,request_key,header_json,header_sha256,owner,created_at,lease_until,status) VALUES (?,?,?,?,?,?,?,?,'queued')",
                         (run_id, case_id, request_key, canonical_json(header), digest_json(header), owner, at, (instant(at) + timedelta(seconds=LEASE_SECONDS)).isoformat()))
        return {"run_id": run_id, "created": True}

    def heartbeat(self, run_id, *, owner):
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            conn.execute("UPDATE lifecycle_web_runs SET lease_until=? WHERE run_id=?", ((instant(self._now()) + timedelta(seconds=LEASE_SECONDS)).isoformat(), run_id))
            return row["cancel_requested_at"] is not None

    def set_phase(self, run_id, *, owner, phase):
        if phase not in RUNNING:
            raise WebJournalError("web_phase_invalid")
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            if row["cancel_requested_at"] is not None:
                raise WebJournalError("stop_requested")
            if RUNNING.index(phase) < RUNNING.index(row["status"]):
                raise WebJournalError("web_phase_invalid")
            conn.execute("UPDATE lifecycle_web_runs SET status=? WHERE run_id=?", (phase, run_id))

    def request_cancel(self, run_id):
        with self.connection(write=True) as conn:
            row, _ = self._row(conn, run_id)
            if row["status"] in RUNNING:
                conn.execute("UPDATE lifecycle_web_runs SET cancel_requested_at=COALESCE(cancel_requested_at,?) WHERE run_id=?", (self._now(), run_id))

    def reserve_call(self, run_id, call_id, *, owner):
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            if row["cancel_requested_at"] is not None:
                raise WebJournalError("stop_requested")
            pending = conn.execute("SELECT call_id,terminal FROM lifecycle_web_calls WHERE run_id=?", (run_id,)).fetchall()
            if call_id not in {"search-1", "analysis-1"} or any(value["terminal"] != "completed" for value in pending):
                raise WebJournalError("web_model_work_incomplete")
            if (call_id == "search-1" and pending) or (call_id == "analysis-1" and [value["call_id"] for value in pending] != ["search-1"]):
                raise WebJournalError("web_model_work_incomplete")
            conn.execute("INSERT INTO lifecycle_web_calls (run_id,call_id) VALUES (?,?)", (run_id, call_id))

    def bind_call(self, run_id, call_id, remote_id, *, owner, terminal=None):
        _identity(remote_id)
        if terminal not in {None, "completed", "failed", "cancelled", "interrupted"}:
            raise WebJournalError("web_terminal_invalid")
        with self.connection(write=True) as conn:
            self._owned(conn, run_id, owner)
            result = conn.execute("UPDATE lifecycle_web_calls SET remote_id=?,terminal=COALESCE(?,terminal) WHERE run_id=? AND call_id=?",
                                  (remote_id, terminal, run_id, call_id))
            if result.rowcount != 1:
                raise WebJournalError("web_call_missing")

    def add_action(self, run_id, call_id, item_id, kind, *, owner):
        _identity(item_id)
        with self.connection(write=True) as conn:
            self._owned(conn, run_id, owner)
            existing = conn.execute("SELECT kind FROM lifecycle_web_actions WHERE run_id=? AND call_id=? AND item_id=?", (run_id, call_id, item_id)).fetchone()
            if existing is not None:
                if existing[0] != kind:
                    raise WebJournalError("web_journal_integrity")
                return
            conn.execute("INSERT INTO lifecycle_web_actions VALUES (?,?,?,?)", (run_id, call_id, item_id, kind))

    def add_page(self, run_id, *, owner, source_id, page):
        if not re.fullmatch(r"source-[1-9][0-9]*", source_id) or not isinstance(page, PublicSourcePage) or _capture_digest(page) != page.capture_sha256:
            raise WebJournalError("web_source_integrity")
        material = asdict(page)
        encoded, digest = canonical_json(material, ensure_ascii=False), _page_material_digest(material)
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            if row["cancel_requested_at"] is not None:
                raise WebJournalError("stop_requested")
            conn.execute("INSERT INTO lifecycle_web_pages VALUES (?,?,?,?)",
                         (run_id, source_id, encoded, digest))

    @staticmethod
    def _decode_page(row):
        material = json.loads(row["page_json"])
        if _page_material_digest(material) != row["page_sha256"]:
            raise WebJournalError("web_journal_integrity")
        material["redirect_chain"] = tuple(material["redirect_chain"])
        page = PublicSourcePage(**material)
        if _capture_digest(page) != page.capture_sha256:
            raise WebJournalError("web_journal_integrity")
        return page

    @classmethod
    def _pages(cls, conn, run_id):
        pages = {}
        for source_id, digest in cls._source_index(conn, run_id):
            saved = conn.execute("SELECT * FROM lifecycle_web_pages WHERE run_id=? AND source_id=?", (run_id, source_id)).fetchone()
            if saved is None or saved["page_sha256"] != digest:
                raise WebJournalError("web_journal_integrity")
            pages[source_id] = cls._decode_page(saved)
            del saved
        return pages

    @staticmethod
    def _source_index(conn, run_id):
        return tuple(tuple(item) for item in conn.execute(
            "SELECT source_id,page_sha256 FROM lifecycle_web_pages WHERE run_id=? ORDER BY source_id", (run_id,)))

    def _read_pages(self, run_id, source_index):
        pages = {}
        # Immutable bodies can be decoded outside the owned read transaction.
        for source_id, digest in source_index:
            with self.connection() as conn:
                saved = conn.execute("SELECT * FROM lifecycle_web_pages WHERE run_id=? AND source_id=?", (run_id, source_id)).fetchone()
            if saved is None or saved["page_sha256"] != digest:
                raise WebJournalError("web_journal_integrity")
            pages[source_id] = self._decode_page(saved)
            del saved
        return pages

    def _completion_state(self, conn, run_id, owner):
        row, header = self._owned(conn, run_id, owner)
        calls = self._calls(conn, run_id)
        if {key: value["terminal"] for key, value in calls.items()} != {"search-1": "completed", "analysis-1": "completed"}:
            raise WebJournalError("web_model_work_incomplete")
        if row["cancel_requested_at"] is not None:
            raise WebJournalError("stop_requested")
        return row, header, self._source_index(conn, run_id), calls

    def complete(self, run_id, *, owner, payload, source_failures, usage, source_requests, source_context=None,
                 source_read_report=None, source_failure_urls=_MISSING_SOURCE_URLS, usage_report=None):
        from src.auth_drivers.lifecycle_web_models import normalized_usage
        if type(source_requests) is not int or source_requests < 0:
            raise WebJournalError("web_result_invalid")
        with self.connection() as conn:
            before, header, source_index, calls = self._completion_state(conn, run_id, owner)
        if usage_report is not None:
            usage_report, public_usage = self._usage_report(usage_report, calls, "web_result_invalid")
            if public_usage["totals"] != normalized_usage(usage):
                raise WebJournalError("web_result_invalid")
        pages = self._read_pages(run_id, source_index)
        _source_gaps(source_failures, pages, max_sources=header["options"]["max_sources"], urls=source_failure_urls)
        finding = validate_finding(PublicInvestigationInput.model_validate(header["request"]), payload, pages,
                                   unread_source_count=len(source_failures), source_context=source_context)
        material = {"finding": finding.finding.model_dump(), "source_failures": source_failures,
                    "source_requests": source_requests, "usage": normalized_usage(usage)}
        if usage_report is not None:
            material["usage_report"] = usage_report
        if source_failure_urls is not _MISSING_SOURCE_URLS:
            material["source_failure_urls"] = source_failure_urls
        if source_context is not None:
            material["source_context"] = source_context
        if source_read_report is not None:
            material["source_read_report"] = validate_source_read_report(source_read_report, max_requests=header["options"]["max_source_requests"])
            if material["source_read_report"]["requests"] != source_requests:
                raise WebJournalError("web_result_invalid")
        with self.connection(write=True) as conn:
            current, _, current_index, current_calls = self._completion_state(conn, run_id, owner)
            if current_index != source_index or current["header_sha256"] != before["header_sha256"] or current_calls != calls:
                raise WebJournalError("web_journal_integrity")
            at = self._now()
            conn.execute("INSERT INTO lifecycle_web_results VALUES (?,?,?,?)", (run_id, canonical_json(material), digest_json(material), at))
            conn.execute("UPDATE lifecycle_web_runs SET status='succeeded',finished_at=? WHERE run_id=?", (at, run_id))

    def fail(self, run_id, *, owner, code, control, source_read_report=None, usage_report=None):
        if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,100}", code):
            code = "web_execution_failed"
        with self.connection(write=True) as conn:
            row, header = self._owned(conn, run_id, owner)
            pending = conn.execute("SELECT 1 FROM lifecycle_web_calls WHERE run_id=? AND terminal IS NULL", (run_id,)).fetchone()
            status = "remote_outcome_unknown" if pending else "cancelled" if row["cancel_requested_at"] is not None else "failed"
            material = {}
            if usage_report is not None:
                material["usage_report"], _ = self._usage_report(usage_report, self._calls(conn, run_id), "web_result_invalid")
            if source_read_report is not None:
                material["failure_source_read_report"] = validate_source_read_report(source_read_report,
                             max_requests=header["options"]["max_source_requests"])
            if material:
                conn.execute("INSERT INTO lifecycle_web_results VALUES (?,?,?,?)", (run_id, canonical_json(material), digest_json(material), self._now()))
            conn.execute("UPDATE lifecycle_web_runs SET status=?,failure_code=?,finished_at=? WHERE run_id=?", (status, code, self._now(), run_id))

    def recover_expired(self, *, at):
        at = instant(at).isoformat()
        with self.connection(write=True) as conn:
            # Recovery does not parse model/source blobs or traverse predecessor chains.
            conn.execute("""UPDATE lifecycle_web_runs SET
                status=CASE WHEN EXISTS(SELECT 1 FROM lifecycle_web_calls c WHERE c.run_id=lifecycle_web_runs.run_id AND c.terminal IS NULL)
                  THEN 'remote_outcome_unknown' ELSE 'failed' END,
                failure_code='web_execution_interrupted',finished_at=?
                WHERE status IN ('queued','searching','reading_sources','analyzing') AND lease_until<=?""", (at, at))

    def control(self, run_id, *, owner):
        with self.connection() as conn:
            row, header = self._owned(conn, run_id, owner)
            if conn.execute("SELECT 1 FROM lifecycle_web_calls WHERE run_id=?", (run_id,)).fetchone():
                raise WebJournalError("web_execution_not_resumable")
        return JournalControl(self, run_id, owner, ExecutionSelection(**header["selection"]))

    def read(self, run_id, *, include_running_sources=True):
        with self.connection() as conn:
            row, header, calls, saved = self._read_record(conn, run_id)
            source_index = self._source_index(conn, run_id)
        pages = (self._read_pages(run_id, source_index)
                 if include_running_sources or row["status"] not in RUNNING else {})
        return self._read_material(row, header, calls, saved, pages)

    @classmethod
    def _review_binding(cls, conn, run_id):
        row, header, calls, saved = cls._read_record(conn, run_id)
        # Verified immutable triggers protect the bytes behind each source hash.
        # A drop/recreate of those triggers changes the schema generation too.
        return (row, header, calls, None if saved is None else dict(saved),
                cls._source_index(conn, run_id), conn.execute("PRAGMA schema_version").fetchone()[0])

    def validated_read(self, run_id):
        from src.lifecycle_investigation.adoption import is_target_run, validated_read
        if is_target_run(run_id):
            return validated_read(self.path, run_id)
        with self.connection() as conn:
            binding = self._review_binding(conn, run_id)
        row, header, calls, saved, source_index, _ = binding
        pages = self._read_pages(run_id, source_index)
        material = self._read_material(row, header, calls, saved, pages)
        read = ValidatedWebRead(self.path, run_id, binding, material)
        with self.connection() as conn:
            read.on_connection(conn, run_id)
        return read

    @classmethod
    def _read_record(cls, conn, run_id):
        verify_web_journal(conn)
        row, header = cls._row(conn, run_id)
        calls = cls._calls(conn, run_id)
        saved = conn.execute("SELECT * FROM lifecycle_web_results WHERE run_id=?", (run_id,)).fetchone()
        return row, header, calls, saved

    @staticmethod
    def _calls(conn, run_id):
        return {call[0]: {"remote_id": call[1], "terminal": call[2]} for call in conn.execute(
            "SELECT call_id,remote_id,terminal FROM lifecycle_web_calls WHERE run_id=?", (run_id,))}

    @staticmethod
    def _usage_report(value, calls, code):
        try:
            report = validate_usage_report(value, calls)
            return report, project_usage_report(report, calls)
        except WebModelError:
            raise WebJournalError(code) from None

    @classmethod
    def read_on_connection(cls, conn, run_id, *, include_running_sources=True, validated=None):
        from src.lifecycle_investigation.adoption import is_target_run, read_on_connection
        if is_target_run(run_id):
            return read_on_connection(conn, run_id, validated=validated)
        if validated is not None:
            if type(validated) is not ValidatedWebRead:
                raise WebJournalError("web_journal_integrity")
            return validated.on_connection(conn, run_id)
        row, header, calls, saved = cls._read_record(conn, run_id)
        pages = (cls._pages(conn, run_id)
                 if include_running_sources or row["status"] not in RUNNING else {})
        return cls._read_material(row, header, calls, saved, pages)

    @staticmethod
    def _read_material(row, header, calls, saved, pages):
        result = {**row, "request": PublicInvestigationInput.model_validate(header["request"]),
                  "selection": ExecutionSelection(**header["selection"]), "options": WebInvestigationOptions(**header["options"]),
                  "observation_sha256": header["observation_sha256"], "finding": None,
                  "credential_generation": header.get("credential_generation"),
                  "calls": calls, "pages": pages}
        if saved is not None:
            value = json.loads(saved["payload_json"])
            if type(value) is not dict or digest_json(value) != saved["result_sha256"]:
                raise WebJournalError("web_journal_integrity")
            if "usage_report" in value:
                _, report = LifecycleWebStore._usage_report(value["usage_report"], calls, "web_journal_integrity")
                result.update(usage_report=report, usage=report["totals"])
            if row["status"] != "succeeded":
                if (row["status"] not in TERMINAL or not value
                        or set(value) - {"failure_source_read_report", "usage_report"}):
                    raise WebJournalError("web_journal_integrity")
                if "failure_source_read_report" in value:
                    report = validate_source_read_report(value["failure_source_read_report"], max_requests=header["options"]["max_source_requests"])
                    result.update(source_read_report=report, source_requests=report["requests"])
                return result
            try:
                value["usage"] = token_totals(value.get("usage"))
            except WebModelError:
                raise WebJournalError("web_journal_integrity") from None
            if "usage_report" in value and result["usage"] != value["usage"]:
                raise WebJournalError("web_journal_integrity")
            result.update(result_sha256=saved["result_sha256"], usage=value["usage"], source_requests=value["source_requests"], source_failures=value["source_failures"])
            result["source_gaps"] = _source_gaps(value["source_failures"], pages, max_sources=header["options"]["max_sources"],
                urls=value.get("source_failure_urls", _MISSING_SOURCE_URLS))
            if "source_failure_urls" in value:
                result["source_failure_urls"] = value["source_failure_urls"]
            if "source_context" in value:
                parse_source_context(value["source_context"], result["pages"])
                result["source_context"] = value["source_context"]
            if "source_read_report" in value:
                report = validate_source_read_report(value["source_read_report"], max_requests=header["options"]["max_source_requests"])
                if report["requests"] != result["source_requests"]:
                    raise WebJournalError("web_journal_integrity")
                result["source_read_report"] = report
            result["finding"] = validate_finding(result["request"], value["finding"], result["pages"],
                                                  unread_source_count=len(value["source_failures"]), source_context=value.get("source_context"))
        elif row["status"] == "succeeded":
            raise WebJournalError("web_journal_integrity")
        return result


class JournalControl(RunControl):
    def __init__(self, store, run_id, owner, selection):
        super().__init__(selection=selection, max_model_requests=2)
        self.store, self.run_id, self.owner = store, run_id, owner

    def _record(self, operation, *args, **kwargs):
        try:
            operation(self.run_id, *args, owner=self.owner, **kwargs)
        except BaseException:
            self.request_stop()
            raise

    def reserve_model_request(self, call_id):
        super().reserve_model_request(call_id)
        self._record(self.store.reserve_call, call_id)

    def bind_remote_id(self, call_id, remote_id):
        super().bind_remote_id(call_id, remote_id)
        self._record(self.store.bind_call, call_id, remote_id)

    def observe_terminal(self, call_id, *, response_id, status, selection):
        super().observe_terminal(call_id, response_id=response_id, status=status, selection=selection)
        self._record(self.store.bind_call, call_id, response_id, terminal=status)

    def observe_web_action(self, call_id, item_id, kind):
        super().observe_web_action(call_id, item_id, kind)
        self._record(self.store.add_action, call_id, item_id, kind)
