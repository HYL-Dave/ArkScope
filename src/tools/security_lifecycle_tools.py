"""Provider-neutral local reads for security-lifecycle cases."""

from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterable, Mapping

from src.market_data_admin import resolve_market_db_path
from src.security_lifecycle_disposition import (
    LIFECYCLE_QUEUE_BUCKETS,
    project_lifecycle_disposition,
)
from src.security_lifecycle_investigation import (
    LifecycleStoreUnavailable,
    compose_security_lifecycle,
    observation_fingerprint,
)
from src.security_lifecycle_schema import (
    ASSESSMENT_RELEVANCE,
    CASE_WORKFLOW_STATES,
    OBSERVATION_KINDS,
    PROPOSAL_ACTIONS,
    SOURCE_PRESENCE_STATES,
)


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DETAIL_HISTORY_LIMIT = 20
_DETAIL_EXCERPT_LIMIT = 2000
_ACTIVE_SOURCE_FAMILIES = (
    "regulator",
    "listing_authority",
    "market_infrastructure",
    "manual",
)
_LISTING_LOCATOR_KEYS = frozenset(
    {
        "locator_kind",
        "adapter",
        "authority",
        "directory",
        "candidate_ticker",
        "expected_active_state",
        "listing_status",
        "market",
        "primary_exchange",
        "security_type",
        "issuer_cik",
        "composite_figi",
        "delisted_utc",
        "source_as_of",
        "provider_last_updated_utc",
        "snapshot_complete",
        "source_document_sha256",
        "adapter_version",
    }
)
_LISTING_ADAPTER_AUTHORITIES = {
    "nasdaq_symbol_directory": "nasdaq_trader",
    "massive_reference": "massive",
}
_LISTING_DIRECTORIES = frozenset({"nasdaq_listed", "other_listed"})
_LISTING_STATUSES = frozenset({"active", "inactive", "not_found", "unverified"})
_LISTING_MARKETS = frozenset({"stocks", "otc"})
_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")
_EXCHANGE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_SECURITY_TYPE = re.compile(r"^[A-Z][A-Z0-9_-]{0,19}$")
_CIK = re.compile(r"^\d{10}$")
_FIGI = re.compile(r"^BBG[A-Z0-9]{9}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ADAPTER_VERSION = re.compile(r"^[a-z][a-z0-9.-]{0,63}$")
_HISTORY_ORDER_FIELDS = {
    "investigation_runs": ("created_at", "run_id"),
    "automation_runs": ("created_at", "run_id"),
    "automation_facts": ("created_at", "fact_id"),
    "evidence": ("created_at", "evidence_id"),
    "assessment_history": ("created_at", "assessment_id"),
    "acknowledgement_history": ("acknowledged_at", "acknowledgement_id"),
    "proposals": ("created_at", "proposal_id"),
}


def _nullable_listing_text(value: object, pattern: re.Pattern[str]) -> bool:
    return value is None or (
        isinstance(value, str) and pattern.fullmatch(value) is not None
    )


def _valid_listing_temporal(value: object, *, nullable: bool) -> bool:
    if value is None:
        return nullable
    if not isinstance(value, str) or not value or len(value) > 64:
        return False
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat() == value
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _compact_listing(source_locator_json: object) -> dict:
    if not isinstance(source_locator_json, str):
        raise ValueError("listing_locator")
    try:
        locator = json.loads(source_locator_json)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("listing_locator") from None
    if not isinstance(locator, dict) or frozenset(locator) != _LISTING_LOCATOR_KEYS:
        raise ValueError("listing_locator")

    adapter = locator["adapter"]
    authority = locator["authority"]
    directory = locator["directory"]
    candidate_ticker = locator["candidate_ticker"]
    if (
        locator["locator_kind"] != "listing_directory_snapshot"
        or not isinstance(adapter, str)
        or adapter not in _LISTING_ADAPTER_AUTHORITIES
        or authority != _LISTING_ADAPTER_AUTHORITIES[adapter]
        or not isinstance(candidate_ticker, str)
        or _TICKER.fullmatch(candidate_ticker) is None
        or type(locator["expected_active_state"]) is not bool
        or not isinstance(locator["listing_status"], str)
        or locator["listing_status"] not in _LISTING_STATUSES
        or not isinstance(locator["market"], str)
        or locator["market"] not in _LISTING_MARKETS
        or not _nullable_listing_text(locator["primary_exchange"], _EXCHANGE)
        or not _nullable_listing_text(locator["security_type"], _SECURITY_TYPE)
        or not _nullable_listing_text(locator["issuer_cik"], _CIK)
        or not _nullable_listing_text(locator["composite_figi"], _FIGI)
        or not _valid_listing_temporal(
            locator["delisted_utc"], nullable=True
        )
        or not _valid_listing_temporal(locator["source_as_of"], nullable=False)
        or not _valid_listing_temporal(
            locator["provider_last_updated_utc"], nullable=True
        )
        or type(locator["snapshot_complete"]) is not bool
        or not isinstance(locator["source_document_sha256"], str)
        or _SHA256.fullmatch(locator["source_document_sha256"]) is None
        or not isinstance(locator["adapter_version"], str)
        or _ADAPTER_VERSION.fullmatch(locator["adapter_version"]) is None
    ):
        raise ValueError("listing_locator")
    if adapter == "nasdaq_symbol_directory":
        if (
            not isinstance(directory, str)
            or directory not in _LISTING_DIRECTORIES
            or locator["market"] != "stocks"
        ):
            raise ValueError("listing_locator")
    elif directory is not None:
        raise ValueError("listing_locator")

    return {
        "authority": authority,
        "directory": directory,
        "candidate_ticker": candidate_ticker,
        "listing_status": locator["listing_status"],
        "market": locator["market"],
        "primary_exchange": locator["primary_exchange"],
        "source_as_of": locator["source_as_of"],
    }


def project_active_security_lifecycle_case(case: Mapping[str, object]) -> dict:
    item = dict(case)
    evidence = []
    for raw in item.get("evidence", []):
        if not isinstance(raw, Mapping):
            raise ValueError("evidence")
        source_family = raw.get("source_family")
        if source_family not in _ACTIVE_SOURCE_FAMILIES:
            continue
        if source_family == "listing_authority":
            if raw.get("kind") != "listing_directory_snapshot":
                continue
            try:
                listing = _compact_listing(raw.get("source_locator_json"))
            except ValueError:
                continue
            evidence.append(
                {
                    "evidence_id": raw.get("evidence_id"),
                    "source_family": "listing_authority",
                    "kind": "listing_directory_snapshot",
                    "source_url": raw.get("source_url"),
                    "created_at": raw.get("created_at"),
                    "listing": listing,
                }
            )
            continue
        row = dict(raw)
        row.pop("source_locator_json", None)
        row.pop("adapter", None)
        evidence.append(row)
    item["evidence"] = evidence

    statuses = item.get("source_family_status", {})
    if not isinstance(statuses, Mapping):
        raise ValueError("source_family_status")
    item["source_family_status"] = {
        family: statuses[family]
        for family in _ACTIVE_SOURCE_FAMILIES
        if family in statuses
    }
    if "evidence_count" in item:
        item["evidence_count"] = len(evidence)
    return item


def _profile_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        _PROJECT_ROOT / "data" / "profile_state.db"
    )


def _load_sources_by_ticker() -> Mapping[str, Iterable[str]] | None:
    from src.active_universe import ActiveUniverseUnavailable, build_active_universe_snapshot

    try:
        return build_active_universe_snapshot().sources_by_ticker
    except ActiveUniverseUnavailable:
        return None


def _store_exists(path: str, store: str) -> None:
    try:
        exists = Path(path).is_file()
    except OSError:
        exists = False
    if not exists:
        raise LifecycleStoreUnavailable(store)


def _ticker_transitions_by_case(profile_db_path: str) -> dict[str, dict]:
    from src.ticker_identity_schema import (
        TickerIdentitySchemaMismatch,
        identity_schema_present,
        verify_ticker_identity_connection,
    )

    conn: sqlite3.Connection | None = None
    try:
        path = Path(profile_db_path)
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        if not identity_schema_present(conn):
            return {}
        verify_ticker_identity_connection(conn)
        from src.ticker_identity_transition import (
            TickerIdentityTransitionStore,
            profile_snapshot_sha256,
        )

        store = TickerIdentityTransitionStore(conn)
        transitions: dict[str, dict] = {}
        rows = conn.execute(
            "SELECT transition_id,case_id,kind,status,source_ticker,"
            "successor_ticker,execute_on,approved_preview_sha256,"
            "approved_preview_json,approval_authority,automation_policy_version,"
            "rule_id,rule_version,decision_provenance_sha256,updated_at "
            "FROM ticker_identity_transitions "
            "ORDER BY case_id,updated_at DESC,transition_id DESC"
        ).fetchall()
        for row in rows:
            case_id = str(row[1])
            if case_id in transitions:
                continue
            transition_id = str(row[0])
            attempt = conn.execute(
                "SELECT status,block_reasons_json,attempted_at "
                "FROM ticker_identity_transition_attempts "
                "WHERE transition_id=? "
                "ORDER BY attempted_at DESC,attempt_id DESC LIMIT 1",
                (transition_id,),
            ).fetchone()
            latest_attempt = None
            if attempt is not None:
                block_reasons = json.loads(str(attempt[1]))
                if not isinstance(block_reasons, list) or not all(
                    isinstance(value, str) for value in block_reasons
                ):
                    raise ValueError("transition_attempt_block_reasons")
                latest_attempt = {
                    "status": str(attempt[0]),
                    "block_reasons": block_reasons,
                    "attempted_at": str(attempt[2]),
                }
            approved_preview = json.loads(str(row[8]))
            if not isinstance(approved_preview, dict):
                raise ValueError("transition_approved_preview")
            if (
                approved_preview.get("preview_sha256") != str(row[7])
                or profile_snapshot_sha256(approved_preview) != str(row[7])
            ):
                raise ValueError("transition_approved_preview")
            activity = store.list_transition_activity(transition_id, limit=20)
            reverse_readiness = (
                store.reverse_readiness(transition_id)
                if str(row[3]) == "applied"
                else None
            )
            transitions[case_id] = {
                "transition_id": transition_id,
                "kind": str(row[2]),
                "status": str(row[3]),
                "source_ticker": str(row[4]),
                "successor_ticker": str(row[5]) if row[5] is not None else None,
                "execute_on": str(row[6]),
                "approved_preview_sha256": str(row[7]),
                "approved_preview": approved_preview,
                "approval_authority": str(row[9]),
                "automation_policy_version": (
                    str(row[10]) if row[10] is not None else None
                ),
                "rule_id": str(row[11]) if row[11] is not None else None,
                "rule_version": str(row[12]) if row[12] is not None else None,
                "decision_provenance_sha256": str(row[13]),
                "updated_at": str(row[14]),
                "latest_attempt": latest_attempt,
                "reverse_readiness": reverse_readiness,
                "activity_history": activity["items"],
                "activity_count": activity["count"],
                "unacknowledged_activity_count": activity[
                    "unacknowledged_count"
                ],
            }
        return transitions
    except (OSError, sqlite3.Error, TickerIdentitySchemaMismatch, ValueError):
        raise LifecycleStoreUnavailable("profile") from None
    finally:
        if conn is not None:
            conn.close()


def _provider_neutral_case(case: Mapping[str, object]) -> dict:
    item = project_active_security_lifecycle_case(case)
    histories = {
        "investigation_runs": [],
        "automation_runs": [],
        "automation_facts": [],
        "evidence": [],
        "assessment_history": [],
        "acknowledgement_history": [],
        "proposals": [],
    }
    truncation = {}
    for name in histories:
        rows = list(item.get(name, []))
        timestamp_field, id_field = _HISTORY_ORDER_FIELDS[name]
        ordered = sorted(
            rows,
            key=lambda row: (
                str(row.get(timestamp_field) or ""),
                str(row.get(id_field) or ""),
            ),
        )
        selected = ordered[-_DETAIL_HISTORY_LIMIT:]
        rendered = []
        for row in selected:
            value = dict(row)
            if name == "investigation_runs":
                value = {
                    key: field
                    for key, field in value.items()
                    if key not in {"adapter", "query_plan_json", "usage_json"}
                }
            elif name == "automation_runs":
                for key in (
                    "run_key",
                    "query_context",
                    "query_context_json",
                    "diagnostics",
                    "diagnostics_json",
                ):
                    value.pop(key, None)
                value["blockers"] = [
                    {
                        "blocker_code": blocker.get("blocker_code"),
                        "retryable": bool(blocker.get("retryable")),
                    }
                    for blocker in value.get("blockers", [])
                ]
            elif name == "automation_facts":
                value = {
                    key: value.get(key)
                    for key in (
                        "fact_id",
                        "automation_run_id",
                        "evidence_id",
                        "source_family",
                        "fact_type",
                        "normalized_value",
                        "source_span_start",
                        "source_span_end",
                        "cited_text_sha256",
                        "extractor_rule_id",
                        "extractor_rule_version",
                        "created_at",
                    )
                }
            elif name == "evidence":
                value.pop("adapter", None)
                value.pop("source_locator_json", None)
                if value.get("source_family") == "listing_authority":
                    rendered.append(value)
                    continue
                value["translations"] = [
                    {
                        key: field
                        for key, field in translation.items()
                        if key != "translated_text"
                    }
                    for translation in value.get("translations", [])
                ]
                value["excerpt"] = str(value.get("excerpt") or "")[
                    :_DETAIL_EXCERPT_LIMIT
                ]
            rendered.append(value)
        item[name] = rendered
        truncation[name] = {"total": len(rows), "returned": len(rendered)}
    item["truncation"] = truncation
    return item


def _case_summary(case: Mapping[str, object]) -> dict:
    observation = case.get("observation") or {}
    automation_runs = list(case.get("automation_runs", []))
    current_automation = automation_runs[0] if automation_runs else {}
    return {
        "case_id": case["case_id"],
        "source": case["source"],
        "source_ref": case["source_ref"],
        "ticker": case["ticker"],
        "source_presence": case["source_presence"],
        "workflow_state": case["workflow_state"],
        "issuer_name": observation.get("issuer_name"),
        "filing_date": observation.get("filing_date"),
        "kinds": list(observation.get("kinds", [])),
        "current_assessment": case.get("current_assessment"),
        "current_acknowledgement": case.get("current_acknowledgement"),
        "active_sources": list(case.get("active_sources", [])),
        "source_context": case.get("source_context"),
        "components": dict(case.get("components", {})),
        "investigation_run_count": len(case.get("investigation_runs", [])),
        "automation_run_count": int(
            case.get("automation_run_count", len(automation_runs))
        ),
        "automation_fact_count": int(
            case.get("automation_fact_count", len(case.get("automation_facts", [])))
        ),
        "automation_tier": current_automation.get("decision_tier"),
        "action_readiness": current_automation.get("action_readiness"),
        "disposition": case["disposition"],
        "queue_bucket": case["queue_bucket"],
        "disposition_reason": case["disposition_reason"],
        "disposition_as_of": case["disposition_as_of"],
        "last_checked_at": case["last_checked_at"],
        "next_check_at": case["next_check_at"],
        "source_family_status": dict(case["source_family_status"]),
        "evidence_count": len(case.get("evidence", [])),
        "assessment_count": len(case.get("assessment_history", [])),
        "acknowledgement_count": len(case.get("acknowledgement_history", [])),
        "proposal_count": len(case.get("proposals", [])),
    }


class SecurityLifecycleReadService:
    """Compose both lifecycle stores without creating or mutating either one."""

    def __init__(
        self,
        *,
        market_db_path: str,
        profile_db_path: str,
        source_loader: Callable[[], Mapping[str, Iterable[str]] | None] = (
            _load_sources_by_ticker
        ),
    ):
        self.market_db_path = market_db_path
        self.profile_db_path = profile_db_path
        self._source_loader = source_loader

    def sources_by_ticker(self) -> Mapping[str, Iterable[str]] | None:
        return self._source_loader()

    def _cases(self) -> list[dict]:
        _store_exists(self.market_db_path, "market")
        _store_exists(self.profile_db_path, "profile")
        sources = self.sources_by_ticker()
        cases = compose_security_lifecycle(
            self.market_db_path,
            self.profile_db_path,
        )["cases"]
        ticker_transitions = _ticker_transitions_by_case(self.profile_db_path)
        rendered = []
        for case in cases:
            item = dict(case)
            item.setdefault("investigation_runs", [])
            item.setdefault("evidence", [])
            item.setdefault("assessment_history", [])
            item.setdefault("acknowledgement_history", [])
            item.setdefault("proposals", [])
            item.setdefault("current_acknowledgement", None)
            item["ticker_transition"] = ticker_transitions.get(
                str(item["case_id"])
            )
            item["active_sources"] = (
                []
                if sources is None
                else sorted(set(sources.get(str(item["ticker"]), ())))
            )
            item["source_context"] = (
                "unavailable" if sources is None else "available"
            )
            item["components"] = {
                "market": {
                    "status": "available",
                    "source_presence": item["source_presence"],
                },
                "profile": {"status": "available"},
            }
            observation = item.get("observation")
            item["observation_fingerprint_sha256"] = (
                observation_fingerprint(dict(observation))
                if isinstance(observation, Mapping)
                else None
            )
            projection = project_lifecycle_disposition(item)
            item.update(
                {
                    "disposition": projection.disposition,
                    "queue_bucket": projection.queue_bucket,
                    "disposition_reason": projection.reason_code,
                    "disposition_as_of": projection.disposition_as_of,
                    "last_checked_at": projection.last_checked_at,
                    "next_check_at": projection.next_check_at,
                    "source_family_status": dict(projection.source_family_status),
                }
            )
            rendered.append(item)
        return rendered

    def list_cases(
        self,
        *,
        ticker: str | None = None,
        workflow_state: str | None = None,
        relevance: str | None = None,
        event_type: str | None = None,
        proposal_type: str | None = None,
        queue_bucket: str | None = None,
        source_presence: str = "present",
        limit: int = 50,
    ) -> dict:
        if workflow_state is not None and workflow_state not in CASE_WORKFLOW_STATES:
            raise ValueError("workflow_state")
        if relevance is not None and relevance not in ASSESSMENT_RELEVANCE:
            raise ValueError("relevance")
        if event_type is not None and event_type not in OBSERVATION_KINDS:
            raise ValueError("event_type")
        if proposal_type is not None and proposal_type not in PROPOSAL_ACTIONS:
            raise ValueError("proposal_type")
        if (
            queue_bucket is not None
            and queue_bucket not in LIFECYCLE_QUEUE_BUCKETS
        ):
            raise ValueError("queue_bucket")
        if source_presence not in SOURCE_PRESENCE_STATES:
            raise ValueError("source_presence")
        bounded_limit = min(max(int(limit), 1), 200)
        normalized_ticker = str(ticker or "").strip().upper()
        all_cases = self._cases()
        source_missing_count = sum(
            case["source_presence"] == "source_missing" for case in all_cases
        )
        selected = []
        for case in all_cases:
            if case["source_presence"] != source_presence:
                continue
            if normalized_ticker and not case["ticker"].startswith(
                normalized_ticker
            ):
                continue
            if workflow_state and case["workflow_state"] != workflow_state:
                continue
            assessment = case.get("current_assessment") or {}
            if relevance and assessment.get("relevance") != relevance:
                continue
            kinds = {
                str(row.get("event_type"))
                for row in (case.get("observation") or {}).get("kinds", [])
            }
            if event_type and event_type not in kinds:
                continue
            if proposal_type and proposal_type not in {
                row.get("action_type") for row in case.get("proposals", [])
            }:
                continue
            selected.append(case)
        queue_counts = {bucket: 0 for bucket in sorted(LIFECYCLE_QUEUE_BUCKETS)}
        for case in selected:
            queue_counts[str(case["queue_bucket"])] += 1
        if queue_bucket is not None:
            selected = [
                case for case in selected if case["queue_bucket"] == queue_bucket
            ]
        count = len(selected)
        cases = [
            _case_summary(project_active_security_lifecycle_case(case))
            for case in selected[:bounded_limit]
        ]
        return {
            "cases": cases,
            "count": count,
            "queue_counts": queue_counts,
            "data_integrity": {"source_missing_count": source_missing_count},
        }

    def get_case(self, case_id: str) -> dict:
        for case in self._cases():
            if case["case_id"] == case_id:
                return {**case, **_case_summary(case)}
        raise KeyError("case_not_found")


def _typed_unavailable(exc: LifecycleStoreUnavailable) -> dict:
    return {
        "status": "unavailable",
        "error": {
            "code": f"security_lifecycle_{exc.store}_store_unavailable",
            "store": exc.store,
        },
    }


def list_security_lifecycle_cases(
    ticker: str | None = None,
    workflow_state: str | None = None,
    source_presence: str = "present",
    limit: int = 50,
) -> dict:
    """List local lifecycle cases without provider access or writes."""
    service = SecurityLifecycleReadService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=_profile_db_path(),
    )
    try:
        payload = service.list_cases(
            ticker=ticker,
            workflow_state=workflow_state,
            source_presence=source_presence,
            limit=limit,
        )
    except LifecycleStoreUnavailable as exc:
        return _typed_unavailable(exc)
    return {
        "status": "ok",
        "cases": payload["cases"],
        "count": payload["count"],
        "queue_counts": payload["queue_counts"],
        "data_integrity": payload["data_integrity"],
    }


def get_security_lifecycle_case(case_id: str) -> dict:
    """Read one local lifecycle case without provider access or writes."""
    service = SecurityLifecycleReadService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=_profile_db_path(),
    )
    try:
        case = service.get_case(case_id)
    except LifecycleStoreUnavailable as exc:
        return _typed_unavailable(exc)
    except KeyError:
        return {
            "status": "unavailable",
            "error": {
                "code": "security_lifecycle_case_not_found",
                "case_id": case_id,
            },
        }
    return {"status": "ok", "case": _provider_neutral_case(case)}


__all__ = [
    "SecurityLifecycleReadService",
    "get_security_lifecycle_case",
    "list_security_lifecycle_cases",
    "project_active_security_lifecycle_case",
]
