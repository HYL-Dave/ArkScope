"""Finite, receipt-bound body recovery intent in the shared collector database."""

from __future__ import annotations

import base64
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

from src.sa.article_acquisition_scope import read_article_scope_context
from src.sa.article_acquisition_settings import ARTICLE_SETTINGS_KEY, ArticleAcquisitionSettings, parse_article_settings
from src.sa.article_body_quality import assess_body
from src.sa.article_body_recovery import build_recovery_manifest
from src.sa.company_collector import CompanyCollector, _iso
from src.sa.company_data import CompanyDataFailure, require
from src.tools.retained_read_results import content_id


BODY_PROTOCOL = 2
REPLY_BYTES = 65_536
_TERMINAL = {"complete", "partial", "cancelled"}
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_SCHEMA = {
    "sa_body_recovery_installation": "CREATE TABLE sa_body_recovery_installation (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, ledger_id TEXT NOT NULL)",
    "sa_body_recovery_jobs": "CREATE TABLE sa_body_recovery_jobs (job_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)",
    "sa_body_recovery_items": "CREATE TABLE sa_body_recovery_items (job_id TEXT NOT NULL, ordinal INTEGER NOT NULL, article_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(job_id,article_id), UNIQUE(job_id,ordinal))",
}


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _schema(conn, ledger_id, *, install=False):
    present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    owned = present & _SCHEMA.keys()
    if not owned:
        if not install:
            return False
        for statement in _SCHEMA.values():
            conn.execute(statement)
        conn.execute("INSERT INTO sa_body_recovery_installation VALUES(1,1,?)", (ledger_id,))
    else:
        require(owned == _SCHEMA.keys(), "sa_body_journal_unavailable")
        for name, expected in _SCHEMA.items():
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
            require(sql == expected, "sa_body_journal_unavailable")
    require(conn.execute("SELECT version,ledger_id FROM sa_body_recovery_installation WHERE id=1").fetchone()
            == (1, ledger_id), "sa_body_journal_unavailable")
    return True


def _job(conn, job_id):
    row = conn.execute("SELECT payload FROM sa_body_recovery_jobs WHERE job_id=?", (job_id,)).fetchone()
    require(row is not None, "sa_body_job_not_found")
    return json.loads(row[0])


def _items(conn, job_id):
    return [json.loads(row[0]) for row in conn.execute(
        "SELECT payload FROM sa_body_recovery_items WHERE job_id=? ORDER BY ordinal", (job_id,))]


def _save_job(conn, job):
    conn.execute("UPDATE sa_body_recovery_jobs SET payload=? WHERE job_id=?", (_dump(job), job["job_id"]))


def _save_item(conn, job, item):
    conn.execute("UPDATE sa_body_recovery_items SET payload=? WHERE job_id=? AND article_id=?",
                 (_dump(item), job["job_id"], item["target"]["article_id"]))


def _target_view(target):
    view = {key: target[key] for key in ("article_id", "url", "title", "body_sha256", "priority", "published_date")}
    view["title_truncated"] = len(view["title"] or "") > 800
    view["title"] = (view["title"] or "")[:800]
    require(len(json.dumps(view).encode("utf8")) <= REPLY_BYTES - 4096, "sa_body_target_too_large")
    return view


def _summary(conn, job):
    items = _items(conn, job["job_id"])
    counts = {state: sum(i["state"] == state for i in items) for state in ("saved", "skipped", "failed")}
    counts.update(selected=len(items), pending=sum(i["state"] in {"pending", "running"} for i in items))
    current = next((item for item in items if item["state"] == "running"), None)
    if current is None and job["state"] not in _TERMINAL:
        current = next((item for item in items if item["state"] == "pending"), None)
    return {"status": "ok", "protocol_version": BODY_PROTOCOL,
            **{key: job.get(key) for key in ("job_id", "manifest_id", "revision", "state", "settings", "created_at",
                                             "reason_code", "next_eligible_at")}, "counts": counts,
            "current_item": (_target_view(current["target"]) | {"state": current["state"]}) if current else None}


def _manifest_for(job):
    settings = ArticleAcquisitionSettings.model_validate(job["settings"], strict=True)
    context = read_article_scope_context(sa_db=job["capture_path"], profile_db=job["profile_path"])
    return build_recovery_manifest(job["capture_path"], as_of=job.get("as_of"), settings=settings, scope_context=context)


def _available(job, article_id):
    with closing(sqlite3.connect(Path(job["capture_path"]).as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute("SELECT title,body_markdown FROM sa_articles WHERE article_id=?", (article_id,)).fetchone()
    return row is not None and assess_body(row[1], title=row[0])["status"] == "available"


def verify_stored_body(conn, active):
    job = _job(conn, active["body_recovery_job_id"])
    return _available(job, active["article_id"])


def bind_body_task(conn, state, message, client, task_id):
    """Called inside the collector's admission transaction, before any navigation."""
    require(_schema(conn, state["ledger_id"]), "sa_body_upgrade_required")
    job = _job(conn, message.get("body_job_id"))
    require(job["owner"] == client and job["generation"] == state["generation"], "sa_body_owner_changed")
    require(job["revision"] == message.get("body_job_revision") == message.get("intent_revision")
            and job["state"] not in _TERMINAL | {"cancelling", "paused"}, "sa_body_job_not_active")
    require(message.get("trigger") in {"manual", "continuation"}, "sa_body_intent_required")
    items = _items(conn, job["job_id"])
    require(not any(i["state"] == "running" for i in items), "sa_body_item_busy")
    item = next((i for i in items if i["target"]["article_id"] == message.get("article_id")), None)
    require(item is not None and item["state"] == "pending", "sa_body_target_invalid")
    manifest = _manifest_for(job)
    require(manifest["status"] == "ok", "sa_body_scope_unavailable")
    target = next((t for t in manifest["targets"] if t["article_id"] == message["article_id"]), None)
    require(target is not None and target["body_sha256"] == item["target"]["body_sha256"], "sa_body_target_changed")
    item.update(state="running", task_id=task_id, reason_code=None)
    job.update(state="running", next_eligible_at=None, reason_code=None)
    _save_item(conn, job, item)
    _save_job(conn, job)
    return {"body_recovery_job_id": job["job_id"], "body_job_revision": job["revision"], "article_id": target["article_id"]}


def body_navigation_allowed(conn, active):
    job = _job(conn, active["body_recovery_job_id"])
    if job["state"] in _TERMINAL | {"cancelling"} or job["revision"] != active["body_job_revision"]:
        return {"status": "deferred", "allowed": False, "reason": "operator_cancelled"}
    manifest = _manifest_for(job)
    if manifest["status"] != "ok":
        return {"status": "deferred", "allowed": False, "reason": "sa_body_scope_unavailable"}
    target = next((t for t in manifest["targets"] if t["article_id"] == active["article_id"]), None)
    item = next(i for i in _items(conn, job["job_id"]) if i["target"]["article_id"] == active["article_id"])
    if target is None or target["body_sha256"] != item["target"]["body_sha256"]:
        return {"status": "deferred", "allowed": False, "reason": "sa_body_target_changed"}
    return None


class BodyRecoveryJobs:
    def __init__(self, control_db, *, sa_db, profile_db, clock=time.time):
        self.path, self.sa_db, self.profile_db = Path(control_db), Path(sa_db), Path(profile_db)
        self.clock = clock
        self.collector = CompanyCollector(self.path, clock=clock)

    def _connect(self, write=False):
        conn = sqlite3.connect(self.path.resolve().as_uri() + ("?mode=rw" if write else "?mode=ro"),
                               uri=True, timeout=10, isolation_level=None)
        conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        return conn

    def public_status(self):
        if not self.path.exists() and not self.collector.marker.exists():
            return {"status": "ok", "protocol_version": BODY_PROTOCOL, "state": "not_started"}
        try:
            with closing(self._connect()) as conn:
                state = self.collector._read(conn)
                if not _schema(conn, state["ledger_id"]):
                    return {"status": "ok", "protocol_version": BODY_PROTOCOL, "state": "not_started"}
                row = conn.execute("SELECT payload FROM sa_body_recovery_jobs ORDER BY rowid DESC LIMIT 1").fetchone()
                if not row:
                    return {"status": "ok", "state": "not_started"}
                job = json.loads(row[0])
                result = _summary(conn, job)
                if job["state"] not in _TERMINAL and (job["owner"] != state["owner"] or job["generation"] != state["generation"]):
                    result.update(state="paused", reason_code="sa_body_owner_changed")
                return result
        except (CompanyDataFailure, sqlite3.Error, OSError, ValueError, KeyError, TypeError):
            return {"status": "error", "error_code": "sa_body_journal_unavailable"}

    def capture_target(self, message):
        """Read authorization for this page; cancellation may finish an admitted save."""
        try:
            client = self.collector._client(message.get("client"))
            with closing(self._connect()) as conn:
                state = self.collector._read(conn)
                active = self.collector._active(state, message, client)
                require(active.get("body_recovery_job_id") == message.get("body_job_id")
                        and active["task_id"] == message.get("task_id")
                        and active.get("article_id") == message.get("article_id"), "sa_body_target_invalid")
                job = _job(conn, active["body_recovery_job_id"])
                require(job["capture_path"] == str(self.sa_db.resolve()) and job["profile_path"] == str(self.profile_db.resolve()),
                        "sa_body_store_changed")
                item = next(i for i in _items(conn, job["job_id"]) if i["target"]["article_id"] == active["article_id"])
                manifest = _manifest_for(job)
                require(manifest["status"] == "ok", "sa_body_scope_unavailable")
                target = next((t for t in manifest["targets"] if t["article_id"] == active["article_id"]), None)
                if target is None:
                    return {"status": "skipped", "reason": "already_present" if _available(job, active["article_id"]) else "out_of_scope", "body_saved": False}
                if target["body_sha256"] != item["target"]["body_sha256"]:
                    return {"status": "skipped", "reason": "source_changed", "body_saved": False}
                return {"status": "ok", "target": _target_view(target)}
        except CompanyDataFailure as exc:
            return {"status": "error", "error_code": exc.code, "body_saved": False}
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError, StopIteration):
            return {"status": "error", "error_code": "sa_body_journal_unavailable", "body_saved": False}

    def handle(self, message, *, client):
        try:
            require(type(message.get("protocol_version")) is int and message["protocol_version"] == BODY_PROTOCOL, "sa_body_upgrade_required")
            client = self.collector._client(client)
            operation = message.get("operation")
            require(operation in {"start", "state", "items", "next", "checkpoint", "cancel", "resume"}, "sa_body_control_invalid")
            write = operation not in {"state", "items"}
            with closing(self._connect(write)) as conn:
                state = self.collector._read(conn)
                self.collector._owner(state, client)
                if write:
                    self.collector._generation(state, message, "expected_generation")
                installed = _schema(conn, state["ledger_id"], install=operation == "start")
                if not installed:
                    require(operation == "state", "sa_body_job_not_found")
                    return {"status": "ok", "state": "not_started", "protocol_version": BODY_PROTOCOL}
                if operation == "start":
                    job = self._start(conn, state, message, client)
                else:
                    job_id = message.get("job_id")
                    if job_id is None and operation == "state":
                        row = conn.execute("SELECT job_id FROM sa_body_recovery_jobs ORDER BY rowid DESC LIMIT 1").fetchone()
                        if row is None:
                            return {"status": "ok", "state": "not_started"}
                        job_id = row[0]
                    job = _job(conn, job_id)
                    # The selected owner may explicitly discard old intent, never
                    # inherit it. Selection itself requires confirmed native idle.
                    require(operation in {"state", "items", "cancel"} or job["owner"] == client and job["generation"] == state["generation"],
                            "sa_body_owner_changed")
                require(job["capture_path"] == str(self.sa_db.resolve()) and job["profile_path"] == str(self.profile_db.resolve()),
                        "sa_body_store_changed")
                extra = {}
                owner_changed = job["owner"] != client or job["generation"] != state["generation"]
                if not write and owner_changed:
                    extra["owner_changed"] = True
                    if job["state"] not in _TERMINAL:
                        extra.update(state="paused", reason_code="sa_body_owner_changed")
                if operation == "items":
                    return self._page(conn, job, message.get("cursor")) | extra
                if operation in {"next", "checkpoint", "cancel", "resume"}:
                    duplicate_cancel = operation == "cancel" and job["state"] in {"cancelling", "cancelled"}
                    require(duplicate_cancel or type(message.get("revision")) is int and message["revision"] == job["revision"],
                            "sa_body_revision_stale")
                    if operation == "cancel" and job["state"] not in _TERMINAL | {"cancelling"}:
                        job.update(state="cancelling", revision=job["revision"] + 1, reason_code="operator_cancelled", next_eligible_at=None)
                    if operation == "resume":
                        require(job["state"] == "paused" and message.get("confirm_handled") is True, "sa_body_resume_required")
                        require(not self.collector._blocked(state, "alpha_picks_body_repair", self.clock()), "sa_body_site_paused")
                        job.update(state="pending", reason_code=None)
                    if operation == "checkpoint":
                        item = next((i for i in _items(conn, job["job_id"]) if i["target"]["article_id"] == message.get("article_id")), None)
                        require(item is not None and item.get("task_id") == message.get("task_id") and item.get("task_id"),
                                "sa_body_receipt_unverified")
                        row = conn.execute("SELECT finished_at FROM acquisition_tasks WHERE task_id=?", (item["task_id"],)).fetchone()
                        require(row and row[0] is not None, "sa_body_receipt_unverified")
                    self._reconcile(conn, job, state)
                    if operation == "next" and job["state"] not in _TERMINAL | {"cancelling", "paused"}:
                        extra = self._next(conn, job, state)
                    _save_job(conn, job)
                response = _summary(conn, job) | extra
                if write:
                    conn.commit()
                return response
        except CompanyDataFailure as exc:
            return {"status": "error", "error_code": exc.code}
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError, AttributeError):
            return {"status": "error", "error_code": "sa_body_journal_unavailable"}

    def _start(self, conn, state, message, client):
        request_id = message.get("request_id")
        require(type(request_id) is str and _ID.fullmatch(request_id) and message.get("trigger") == "manual", "sa_body_intent_required")
        request_key = client["client_id"] + ":" + request_id
        fingerprint = content_id({k: message.get(k) for k in ("manifest_id", "trigger", "expected_generation")})
        old = conn.execute("SELECT payload FROM sa_body_recovery_jobs WHERE request_id=?", (request_key,)).fetchone()
        if old:
            job = json.loads(old[0])
            require(job["request_fingerprint"] == fingerprint, "sa_body_request_conflict")
            return job
        for row in conn.execute("SELECT payload FROM sa_body_recovery_jobs"):
            require(json.loads(row[0])["state"] in _TERMINAL, "sa_body_job_exists")
        with closing(sqlite3.connect(self.profile_db.resolve().as_uri() + "?mode=ro", uri=True)) as profile:
            raw = profile.execute("SELECT value FROM profile_settings WHERE key=?", (ARTICLE_SETTINGS_KEY,)).fetchone()
        settings = parse_article_settings(raw[0] if raw else None)
        context = read_article_scope_context(sa_db=self.sa_db, profile_db=self.profile_db)
        manifest = build_recovery_manifest(self.sa_db, settings=settings, scope_context=context)
        require(manifest["status"] == "ok", "sa_body_scope_unavailable")
        require(manifest["manifest_id"] == message.get("manifest_id"), "sa_body_preview_changed")
        limit = settings.max_articles_per_job
        targets = manifest["targets"][:limit] if limit else manifest["targets"]
        job = {"job_id": uuid4().hex, "revision": 1, "state": "pending" if targets else "complete",
               "manifest_id": manifest["manifest_id"], "settings": settings.model_dump(), "as_of": manifest["as_of"],
               "created_at": _iso(self.clock()), "owner": client, "generation": state["generation"],
               "request_fingerprint": fingerprint, "capture_path": str(self.sa_db.resolve()), "profile_path": str(self.profile_db.resolve()),
               "reason_code": None, "next_eligible_at": None}
        conn.execute("INSERT INTO sa_body_recovery_jobs VALUES(?,?,?)", (job["job_id"], request_key, _dump(job)))
        for ordinal, target in enumerate(targets):
            item = {"target": target, "state": "pending", "reason_code": None, "task_id": None}
            conn.execute("INSERT INTO sa_body_recovery_items VALUES(?,?,?,?)", (job["job_id"], ordinal, target["article_id"], _dump(item)))
        return job

    def _reconcile(self, conn, job, state):
        cancelling = job["state"] in {"cancelling", "cancelled"}
        for item in _items(conn, job["job_id"]):
            if item["state"] == "running":
                row = conn.execute("SELECT payload,finished_at,receipt FROM acquisition_tasks WHERE task_id=?", (item["task_id"],)).fetchone()
                require(row is not None, "sa_body_receipt_unverified")
                if row[1] is None:
                    continue
                task, receipt = json.loads(row[0]), json.loads(row[2])
                require(task.get("body_recovery_job_id") == receipt.get("body_recovery_job_id") == job["job_id"]
                        and task.get("article_id") == receipt.get("article_id") == item["target"]["article_id"]
                        and task["client"] == job["owner"] and task["generation"] == job["generation"], "sa_body_receipt_unverified")
                status = task["result"]["status"]
                if _available(job, item["target"]["article_id"]):
                    item.update(state="saved", reason_code=None)
                elif cancelling:
                    item.update(state="skipped", reason_code="operator_cancelled")
                elif (task.get("restriction_reason") in {"rate_limited", "login_required", "human_verification_required", "access_restricted"}
                      or task.get("rate_limit_reported") or status == "deferred"
                      or task.get("failure_reported") and self.collector._blocked(state, "alpha_picks_body_repair", self.clock())):
                    item.update(state="pending", reason_code=None)
                else:
                    item.update(state="skipped" if status == "cancelled" else "failed",
                                reason_code=task["result"].get("error_code") or "sa_body_capture_failed")
                _save_item(conn, job, item)
            elif cancelling and item["state"] == "pending":
                item.update(state="skipped", reason_code="operator_cancelled")
                _save_item(conn, job, item)
        items = _items(conn, job["job_id"])
        if not any(i["state"] in {"pending", "running"} for i in items):
            job.update(state="cancelled" if cancelling else "partial" if any(i["state"] == "failed" for i in items) else "complete",
                       next_eligible_at=None)

    def _next(self, conn, job, state):
        if any(i["state"] == "running" for i in _items(conn, job["job_id"])):
            job.update(state="running", reason_code="sa_body_cleanup_unconfirmed")
            return {}
        blocked = self.collector._blocked(state, "alpha_picks_body_repair", self.clock())
        if blocked or state["active"]:
            blocked = blocked or {"reason": "collector_busy"}
            deadline = blocked.get("retry_after")
            paused = blocked.get("reason") == "site_paused" and not deadline
            job.update(state="paused" if paused else "waiting", next_eligible_at=deadline,
                       reason_code=blocked.get("error_code") or blocked.get("reason"))
            return {}
        manifest = _manifest_for(job)
        if manifest["status"] != "ok":
            job.update(state="waiting", reason_code="sa_body_scope_unavailable", next_eligible_at=None)
            return {}
        targets = {t["article_id"]: t for t in manifest["targets"]}
        for item in _items(conn, job["job_id"]):
            if item["state"] != "pending":
                continue
            target = targets.get(item["target"]["article_id"])
            if target and target["body_sha256"] == item["target"]["body_sha256"]:
                job.update(state="pending", reason_code=None, next_eligible_at=None)
                return {"target": _target_view(item["target"])}
            item.update(state="skipped", reason_code="already_present" if _available(job, item["target"]["article_id"]) else "scope_or_source_changed")
            _save_item(conn, job, item)
        self._reconcile(conn, job, state)
        return {}

    def _page(self, conn, job, cursor):
        offset = 0
        if cursor is not None:
            try:
                decoded = json.loads(base64.urlsafe_b64decode(cursor).decode())
                require(decoded[:3] == [job["job_id"], job["manifest_id"], job["revision"]]
                        and len(decoded) == 4 and type(decoded[3]) is int and decoded[3] >= 0, "sa_body_cursor_invalid")
                offset = decoded[3]
            except (ValueError, TypeError, UnicodeError):
                raise CompanyDataFailure("sa_body_cursor_invalid") from None
        items = _items(conn, job["job_id"])
        require(offset <= len(items), "sa_body_cursor_invalid")
        response = _summary(conn, job) | {"items": [], "next_cursor": None}
        for item in items[offset:offset + 25]:
            view = _target_view(item["target"]) | {k: item.get(k) for k in ("state", "reason_code", "task_id")}
            if len(json.dumps(response | {"items": [*response["items"], view]}).encode("utf8")) > REPLY_BYTES - 1024:
                break
            response["items"].append(view)
        end = offset + len(response["items"])
        require(end > offset or end == len(items), "sa_body_target_too_large")
        if end < len(items):
            response["next_cursor"] = base64.urlsafe_b64encode(_dump([job["job_id"], job["manifest_id"], job["revision"], end]).encode()).decode()
        return response
