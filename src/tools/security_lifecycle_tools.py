"""Provider-neutral local reads for security-lifecycle cases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Mapping

from src.market_data_admin import resolve_market_db_path
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
_HISTORY_ORDER_FIELDS = {
    "investigation_runs": ("created_at", "run_id"),
    "evidence": ("created_at", "evidence_id"),
    "assessment_history": ("created_at", "assessment_id"),
    "acknowledgement_history": ("acknowledged_at", "acknowledgement_id"),
    "proposals": ("created_at", "proposal_id"),
}


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
        transitions: dict[str, dict] = {}
        rows = conn.execute(
            "SELECT transition_id,case_id,kind,status,source_ticker,"
            "successor_ticker,execute_on,approved_preview_sha256,updated_at "
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
            transitions[case_id] = {
                "transition_id": transition_id,
                "kind": str(row[2]),
                "status": str(row[3]),
                "source_ticker": str(row[4]),
                "successor_ticker": str(row[5]) if row[5] is not None else None,
                "execute_on": str(row[6]),
                "approved_preview_sha256": str(row[7]),
                "updated_at": str(row[8]),
                "latest_attempt": latest_attempt,
            }
        return transitions
    except (OSError, sqlite3.Error, TickerIdentitySchemaMismatch, ValueError):
        raise LifecycleStoreUnavailable("profile") from None
    finally:
        if conn is not None:
            conn.close()


def _provider_neutral_case(case: Mapping[str, object]) -> dict:
    item = dict(case)
    histories = {
        "investigation_runs": [],
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
            elif name == "evidence":
                value.pop("adapter", None)
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
        count = len(selected)
        cases = [_case_summary(case) for case in selected[:bounded_limit]]
        return {
            "cases": cases,
            "count": count,
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
]
