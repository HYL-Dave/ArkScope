"""Bounded scheduler boundary for trusted lifecycle automation."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Iterator

from src.security_lifecycle_automation_worker import (
    LifecycleAutomationEvidenceBundle,
    LifecycleAutomationWorker,
)
from src.security_lifecycle_fact_kernel import AutomationBlocker
from src.security_lifecycle_investigation import (
    LifecycleStoreUnavailable,
    compose_security_lifecycle,
    observation_fingerprint,
)
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
    verify_profile_connection,
)


logger = logging.getLogger(__name__)

_JOB_NAME = "security_lifecycle.automation"
_DEFAULT_LIMIT = 2
_MAX_CASES = 2
_AUTOMATION_TABLES = frozenset(
    {
        "security_lifecycle_automation_runs",
        "security_lifecycle_automation_facts",
    }
)
_RUN_AT: ContextVar[datetime | None] = ContextVar(
    "security_lifecycle_automation_run_at",
    default=None,
)
_STATUSES = frozenset({"succeeded", "partial", "unavailable", "not_installed"})
_REASONS = frozenset(
    {
        "automation_schema_absent",
        "case_processing_blocked",
        "case_processing_failed",
        "market_store_unavailable",
        "profile_schema_mismatch",
        "profile_store_unavailable",
        "automation_scheduler_failed",
    }
)
_RETRYABLE_BLOCKERS = frozenset(
    {
        "sec_governor_unavailable",
        "sec_rate_limited",
        "sec_transport_unavailable",
        "sec_document_unavailable",
        "sec_evidence_insufficient",
        "ibkr_gateway_unavailable",
        "ibkr_contract_missing",
    }
)


class LifecycleAutomationNotInstalled(RuntimeError):
    """The reviewed automation schema has not been installed yet."""


def _empty_summary(*, status: str = "succeeded", reason: str | None = None) -> dict:
    return {
        "status": status,
        "reason": reason,
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }


def security_lifecycle_automation_failure(reason: str) -> dict:
    """Return the closed unavailable shape used by the parent scheduler."""

    if reason not in _REASONS or reason == "automation_schema_absent":
        raise ValueError("reason")
    return _empty_summary(status="unavailable", reason=reason)


def _aware_instant(value: datetime | None) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now_must_be_timezone_aware")
    return instant.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _clock() -> str:
    return _timestamp(_RUN_AT.get() or datetime.now(timezone.utc))


def _profile_path() -> Path:
    from src.app_records_store import resolve_profile_state_db_path

    return Path(resolve_profile_state_db_path(None))


def _market_path() -> Path:
    from src.market_data_admin import resolve_market_db_path

    return Path(resolve_market_db_path())


def _automation_schema_state(conn: sqlite3.Connection) -> None:
    present = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    found = present & _AUTOMATION_TABLES
    if not found:
        raise LifecycleAutomationNotInstalled()
    if found != _AUTOMATION_TABLES:
        raise LifecycleSchemaMismatch("partial lifecycle automation schema")
    verify_profile_connection(conn)


@contextmanager
def _profile_connection() -> Iterator[sqlite3.Connection]:
    path = _profile_path()
    if not path.is_file():
        raise LifecycleStoreUnavailable("profile")
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=rw",
            uri=True,
            timeout=10.0,
            check_same_thread=False,
        )
        _automation_schema_state(conn)
        yield conn
    finally:
        if conn is not None:
            conn.close()


def _load_cases() -> tuple[dict[str, object], ...]:
    market_path = _market_path()
    profile_path = _profile_path()
    if not market_path.is_file():
        raise LifecycleStoreUnavailable("market")
    if not profile_path.is_file():
        raise LifecycleStoreUnavailable("profile")
    with sqlite3.connect(
        f"{profile_path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=10.0,
    ) as conn:
        _automation_schema_state(conn)
    cases = compose_security_lifecycle(str(market_path), str(profile_path))["cases"]
    rendered: list[dict[str, object]] = []
    for case in cases:
        item = dict(case)
        observation = item.get("observation")
        item["observation_fingerprint_sha256"] = (
            observation_fingerprint(dict(observation))
            if isinstance(observation, Mapping)
            else None
        )
        rendered.append(item)
    return tuple(rendered)


def _assert_automation_installed() -> None:
    profile_path = _profile_path()
    if not profile_path.is_file():
        raise LifecycleStoreUnavailable("profile")
    with sqlite3.connect(
        f"{profile_path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=10.0,
    ) as conn:
        _automation_schema_state(conn)


def _load_sources() -> Mapping[str, tuple[str, ...]]:
    from src.active_universe import build_active_universe_snapshot

    snapshot = build_active_universe_snapshot()
    return {
        str(ticker): tuple(sorted({str(source) for source in sources}))
        for ticker, sources in snapshot.sources_by_ticker.items()
    }


def _transition_preview(
    *,
    case: Mapping[str, object],
    request: Mapping[str, object],
    sources: tuple[str, ...],
) -> dict[str, object]:
    from src.ticker_identity_transition import (
        build_automation_transition_preflight,
    )

    with _profile_connection() as conn:
        return build_automation_transition_preflight(
            conn,
            case=case,
            request=request,
            sources=sources,
        )


def _transition_approver(
    *,
    case: Mapping[str, object],
    request: Mapping[str, object],
    sources: tuple[str, ...],
) -> dict[str, object]:
    from src.ticker_identity_service import (
        TickerIdentityConflict,
        TickerIdentityService,
    )

    del sources
    service = TickerIdentityService(
        market_db_path=str(_market_path()),
        profile_db_path=str(_profile_path()),
        source_loader=_load_sources,
        clock=_clock,
    )
    try:
        return service.approve_automation_case(
            str(case.get("case_id") or ""),
            request=request,
        )
    except TickerIdentityConflict:
        raise ValueError("transition_preview_changed") from None


def _identity_context(case: Mapping[str, object]):
    from src.security_lifecycle_sec_evidence import build_identity_context

    raw_observation = case.get("observation")
    if not isinstance(raw_observation, Mapping):
        raise ValueError("source_observation_missing")
    observation = dict(raw_observation)
    observation["event_kinds"] = tuple(
        str(row.get("event_type"))
        for row in observation.get("kinds", ())
        if isinstance(row, Mapping) and row.get("event_type")
    )
    return build_identity_context(
        case_id=str(case["case_id"]),
        observation=observation,
    )


def _normalize_sec_blocker(code: str) -> str:
    if code == "source_conflict":
        return code
    if code == "sec_response_too_large":
        return "sec_request_budget_exhausted"
    if code == "sec_http_error":
        return "sec_transport_unavailable"
    if code in {"sec_invalid_json", "sec_url_unsupported"}:
        raise ValueError("sec_source_payload_invalid")
    return code


def _blockers(codes: list[str], *, at: str) -> tuple[tuple[AutomationBlocker, ...], str | None]:
    normalized = tuple(dict.fromkeys(code for code in codes if code != "source_conflict"))
    rows = tuple(
        AutomationBlocker(code=code, retryable=code in _RETRYABLE_BLOCKERS, context={})
        for code in normalized
    )
    retry_at = None
    if rows and all(row.retryable for row in rows):
        parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
        retry_at = _timestamp(parsed + timedelta(days=1))
    return rows, retry_at


def _local_news_evidence(context, *, at: str) -> tuple[tuple[object, ...], dict[str, int]]:
    from src.sa_capture_store import resolve_sa_db_path
    from src.security_lifecycle_news_evidence import read_local_publisher_evidence

    market_path = _market_path()
    sa_path = Path(resolve_sa_db_path())
    if not market_path.is_file() or not sa_path.is_file():
        return (), {"news_evidence_count": 0, "news_unavailable": 1}
    normalized_conn: sqlite3.Connection | None = None
    sa_conn: sqlite3.Connection | None = None
    try:
        normalized_conn = sqlite3.connect(
            f"{market_path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=10.0,
        )
        sa_conn = sqlite3.connect(
            f"{sa_path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=10.0,
        )
        result = read_local_publisher_evidence(
            normalized_conn=normalized_conn,
            sa_conn=sa_conn,
            context=context,
            start_date=context.primary_start,
            end_date=context.primary_end,
            retrieved_at=at,
        )
        return result.evidence, {
            "news_evidence_count": len(result.evidence),
            "news_truncated": int(result.truncated),
            "news_unavailable": int(bool(result.blockers)),
        }
    except (OSError, sqlite3.Error):
        return (), {"news_evidence_count": 0, "news_unavailable": 1}
    finally:
        if normalized_conn is not None:
            normalized_conn.close()
        if sa_conn is not None:
            sa_conn.close()


class _LifecycleIbkrGateway:
    def __init__(self):
        from data_sources.ibkr_client_id import ibkr_client_id_for
        from data_sources.ibkr_source import IBKRDataSource

        self._source = IBKRDataSource(
            client_id=ibkr_client_id_for("lifecycle"),
            readonly=True,
            timeout=15,
        )

    def isConnected(self) -> bool:
        return bool(self._source.connect())

    def reqContractDetails(self, contract):
        gateway = getattr(self._source, "_ib", None)
        if gateway is None:
            raise ConnectionError("ibkr_gateway_unavailable")
        return gateway.reqContractDetails(contract)

    def disconnect(self) -> None:
        self._source.disconnect()


def _ibkr_evidence(context, *, at: str, regulator_successors: tuple[str, ...]):
    from src.ibkr_gateway_lock import ibkr_gateway_lock
    from src.security_lifecycle_ibkr_evidence import (
        contract_snapshot_facts,
        read_ibkr_contract_evidence,
    )

    gateway = _LifecycleIbkrGateway()

    @contextmanager
    def locked(timeout: float):
        with ibkr_gateway_lock(timeout=timeout):
            try:
                yield
            finally:
                gateway.disconnect()

    result = read_ibkr_contract_evidence(
        gateway=gateway,
        gateway_lock=locked,
        context=context,
        retrieved_at=at,
    )
    facts = tuple(
        fact
        for evidence in result.evidence
        for fact in contract_snapshot_facts(
            evidence,
            regulator_successors=regulator_successors,
        )
    )
    return result, facts


def _fact_value(fact: object) -> object:
    if isinstance(fact, Mapping):
        return fact.get("normalized_value", fact.get("value"))
    return getattr(fact, "normalized_value", getattr(fact, "value", None))


def _fact_type(fact: object) -> str:
    if isinstance(fact, Mapping):
        return str(fact.get("fact_type") or "")
    return str(getattr(fact, "fact_type", "") or "")


def _load_evidence(
    case: Mapping[str, object],
    *,
    mode: str,
    at: str,
) -> LifecycleAutomationEvidenceBundle:
    del mode
    from data_sources.sec_transport import SecRequestBudget, SecTransport
    from src.security_lifecycle_sec_evidence import collect_sec_evidence

    context = _identity_context(case)
    budget = SecRequestBudget.lifecycle()
    transport = SecTransport()
    try:
        sec = collect_sec_evidence(
            context=context,
            transport=transport,
            retrieved_at=at,
            budget=budget,
        )
        diagnostics = {
            f"sec_{key}": value
            for key, value in transport.diagnostics(budget).items()
        }
    finally:
        transport.close()

    codes = [_normalize_sec_blocker(str(code)) for code in sec.blockers]
    if not sec.facts and "sec_evidence_insufficient" not in codes:
        codes.append("sec_evidence_insufficient")
    evidence: list[object] = list(sec.evidence)
    facts: list[object] = list(sec.facts)

    news_evidence, news_diagnostics = _local_news_evidence(context, at=at)
    evidence.extend(news_evidence)
    diagnostics.update(news_diagnostics)

    successor_values = tuple(
        sorted(
            {
                str(_fact_value(fact)).upper()
                for fact in facts
                if _fact_type(fact) == "successor_ticker" and _fact_value(fact)
            }
        )
    )
    terminal = any(
        _fact_type(fact) == "tracked_security_effect"
        and _fact_value(fact) == "terminal_delisting"
        for fact in facts
    )
    if successor_values or terminal:
        ibkr, ibkr_facts = _ibkr_evidence(
            context,
            at=at,
            regulator_successors=successor_values,
        )
        evidence.extend(ibkr.evidence)
        facts.extend(ibkr_facts)
        codes.extend(str(code) for code in ibkr.blockers)
        diagnostics["ibkr_requests"] = int(ibkr.requests_made)
    else:
        diagnostics["ibkr_requests"] = 0

    blockers, retry_at = _blockers(codes, at=at)
    return LifecycleAutomationEvidenceBundle(
        evidence=tuple(evidence),
        facts=tuple(facts),
        blockers=blockers,
        diagnostics=diagnostics,
        retry_at=retry_at,
    )


def _worker() -> LifecycleAutomationWorker:
    _assert_automation_installed()
    return LifecycleAutomationWorker(
        case_loader=_load_cases,
        profile_connection=_profile_connection,
        evidence_loader=_load_evidence,
        source_loader=_load_sources,
        transition_preview=_transition_preview,
        transition_approver=_transition_approver,
        clock=_clock,
    )


def _bounded_result(result: Mapping[str, object]) -> dict:
    if not isinstance(result, Mapping):
        raise ValueError("result")
    counts: dict[str, int] = {}
    for key in (
        "selected",
        "processed",
        "accepted",
        "drafted",
        "blocked",
        "failed",
        "skipped_current",
    ):
        value = result.get(key)
        maximum = 10_000 if key == "skipped_current" else _MAX_CASES
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(key)
        counts[key] = value
    if counts["processed"] != sum(
        counts[key] for key in ("accepted", "drafted", "blocked", "failed")
    ):
        raise ValueError("processed")
    if counts["processed"] > counts["selected"]:
        raise ValueError("selected")

    raw_ids = result.get("case_ids")
    if not isinstance(raw_ids, list) or len(raw_ids) != counts["selected"]:
        raise ValueError("case_ids")
    case_ids: list[str] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            raise ValueError("case_ids")
        case_id = raw_id.strip()
        if not case_id or len(case_id) > 160 or "\0" in case_id:
            raise ValueError("case_ids")
        case_ids.append(case_id)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_ids")

    supplied_status = result.get("status")
    supplied_reason = result.get("reason")
    if supplied_status in {"unavailable", "not_installed"}:
        if any(counts.values()) or case_ids:
            raise ValueError("status")
        status = str(supplied_status)
        reason = str(supplied_reason or "")
        if status == "not_installed":
            if reason != "automation_schema_absent":
                raise ValueError("reason")
        elif reason not in _REASONS or reason == "automation_schema_absent":
            raise ValueError("reason")
    else:
        if counts["failed"]:
            status, reason = "partial", "case_processing_failed"
        elif counts["blocked"]:
            status, reason = "partial", "case_processing_blocked"
        else:
            status, reason = "succeeded", None
        if supplied_status is not None and supplied_status != status:
            raise ValueError("status")
        if supplied_reason is not None and supplied_reason != reason:
            raise ValueError("reason")
    return {
        "status": status,
        "reason": reason,
        **counts,
        "case_ids": case_ids,
    }


def run_security_lifecycle_automation(
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Run one bounded batch and return no provider payload or raw error detail."""

    if type(limit) is not int or not 1 <= limit <= _MAX_CASES:
        raise ValueError("limit")
    instant = _aware_instant(now)
    token = _RUN_AT.set(instant)
    try:
        return _bounded_result(_worker().run(limit=limit, mode="live"))
    except LifecycleAutomationNotInstalled:
        return _empty_summary(
            status="not_installed",
            reason="automation_schema_absent",
        )
    except LifecycleStoreUnavailable as exc:
        reason = (
            "market_store_unavailable"
            if exc.store == "market"
            else "profile_store_unavailable"
        )
        return security_lifecycle_automation_failure(reason)
    except (LifecycleSchemaMismatch, LifecycleWritesUnavailable):
        return security_lifecycle_automation_failure("profile_schema_mismatch")
    except (OSError, sqlite3.Error):
        return security_lifecycle_automation_failure("profile_store_unavailable")
    except Exception as exc:
        logger.warning(
            "security lifecycle automation tick failed code=%s",
            type(exc).__name__,
        )
        return security_lifecycle_automation_failure("automation_scheduler_failed")
    finally:
        _RUN_AT.reset(token)


def _job_runs_connection() -> sqlite3.Connection | None:
    path = _profile_path()
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=rw",
            uri=True,
            timeout=5.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
    except (OSError, sqlite3.Error):
        if conn is not None:
            conn.close()
        return None
    return conn


def _stored_result(raw: object) -> dict | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        return _bounded_result(parsed) if isinstance(parsed, Mapping) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _failure_incident_key(result: Mapping[str, object]) -> tuple[object, ...]:
    return (
        result["status"],
        result["reason"],
        tuple(sorted(result["case_ids"])),
    )


def _witness_at(now: datetime, not_before: object) -> str:
    instant = _aware_instant(now)
    if isinstance(not_before, str):
        try:
            boundary = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            if boundary.tzinfo is not None and boundary > instant:
                instant = boundary
        except ValueError:
            pass
    return instant.isoformat(timespec="seconds")


def _insert_witness(
    conn: sqlite3.Connection,
    *,
    result: Mapping[str, object],
    now: datetime,
    not_before: object,
) -> None:
    failed = result["status"] in {"partial", "unavailable"}
    at = _witness_at(now, not_before)
    conn.execute(
        """
        INSERT INTO job_runs (
            job_name,status,trigger_source,payload,result,message,error,
            started_at,finished_at,duration_ms,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            _JOB_NAME,
            "failed" if failed else "succeeded",
            "scheduler",
            "{}",
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            (
                "security_lifecycle_automation_failure"
                if failed
                else "security_lifecycle_automation_recovered"
            ),
            str(result["reason"]) if failed else None,
            at,
            at,
            None,
            at,
            at,
        ),
    )


def _log_witness_unavailable(result: Mapping[str, object]) -> None:
    logger.warning(
        "security lifecycle automation witness unavailable status=%s reason=%s case_ids=%s",
        result["status"],
        result["reason"],
        ",".join(result["case_ids"]),
    )


def record_security_lifecycle_automation_result(
    result: Mapping[str, object],
    *,
    now: datetime,
) -> bool:
    """Persist one deduplicated failure or recovery witness when writable."""

    try:
        bounded = _bounded_result(result)
    except Exception:
        logger.warning("security lifecycle automation returned an invalid result")
        bounded = security_lifecycle_automation_failure(
            "automation_scheduler_failed"
        )
    if bounded["status"] == "not_installed":
        return True

    conn = _job_runs_connection()
    if conn is None:
        _log_witness_unavailable(bounded)
        return False
    try:
        conn.execute("BEGIN IMMEDIATE")
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_runs'"
        ).fetchone()
        if present is None:
            conn.rollback()
            if bounded["status"] in {"partial", "unavailable"}:
                _log_witness_unavailable(bounded)
                return False
            return True
        latest = conn.execute(
            "SELECT status,result,started_at FROM job_runs WHERE job_name=? "
            "ORDER BY id DESC LIMIT 1",
            (_JOB_NAME,),
        ).fetchone()
        failed = bounded["status"] in {"partial", "unavailable"}
        if failed:
            latest_result = (
                _stored_result(latest["result"])
                if latest is not None and latest["status"] == "failed"
                else None
            )
            if (
                latest_result is not None
                and _failure_incident_key(latest_result)
                == _failure_incident_key(bounded)
            ):
                conn.commit()
                return True
            _insert_witness(
                conn,
                result=bounded,
                now=now,
                not_before=latest["started_at"] if latest is not None else None,
            )
            conn.commit()
            return True
        if latest is None or latest["status"] != "failed":
            conn.commit()
            return True
        _insert_witness(
            conn,
            result=bounded,
            now=now,
            not_before=latest["started_at"],
        )
        conn.commit()
        return True
    except (OSError, sqlite3.Error):
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        _log_witness_unavailable(bounded)
        return False
    finally:
        conn.close()


__all__ = [
    "LifecycleAutomationNotInstalled",
    "record_security_lifecycle_automation_result",
    "run_security_lifecycle_automation",
    "security_lifecycle_automation_failure",
]
