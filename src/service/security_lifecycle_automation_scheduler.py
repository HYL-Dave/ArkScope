"""Bounded scheduler boundary for trusted lifecycle automation."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
from typing import Iterator

from src.data_provider_config import MASSIVE_CONFIG_PROVIDER, provider_field_env_value
from src.security_lifecycle_automation_worker import (
    LifecycleAutomationEvidenceBundle,
    LifecycleAutomationWorker,
)
from src.security_lifecycle_decision_policy import (
    listing_authority_conflict_codes,
    listing_authority_required_components,
)
from src.security_lifecycle_fact_kernel import (
    AutomationBlocker,
    SecurityLifecycleFactKernel,
    normalize_terminal_finalization_failure,
)
from src.security_lifecycle_investigation import (
    LifecycleStoreUnavailable,
    SecurityLifecycleInvestigationStore,
    compose_security_lifecycle,
    observation_fingerprint,
)
from src.security_lifecycle_listing_evidence import (
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    ListingAuthoritySession,
    ListingAuthorityTransport,
    ListingRequestBudget,
)
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch,
    LifecycleWritesUnavailable,
    verify_profile_connection,
)
from src.scheduler_state import ensure_scheduler_state_schema
from src.service.security_lifecycle_automation_runtime import (
    LifecycleAutomationAlreadyRunning,
    LifecycleAutomationExecutionUnavailable,
    lifecycle_automation_execution_lock,
)


logger = logging.getLogger(__name__)

_JOB_NAME = "security_lifecycle.automation"
_AUTOMATION_STATE_VERSION = 1
_DEFAULT_LIMIT = 2
_MAX_CASES = 2
_AUTOMATION_TABLES = frozenset(
    {
        "security_lifecycle_automation_runs",
        "security_lifecycle_automation_facts",
    }
)
_STATUSES = frozenset(
    {"succeeded", "partial", "unavailable", "not_installed", "skipped"}
)
_REASONS = frozenset(
    {
        "already_running",
        "automation_schema_absent",
        "case_processing_blocked",
        "case_processing_failed",
        "market_store_unavailable",
        "profile_schema_mismatch",
        "profile_store_unavailable",
        "automation_scheduler_failed",
        "execution_lock_unavailable",
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
        "listing_directory_unavailable",
        "listing_directory_stale",
        "listing_directory_schema_mismatch",
        "massive_credential_missing",
        "massive_access_denied",
        "massive_rate_limited",
        "massive_reference_unavailable",
        "listing_status_unresolved",
    }
)
_NASDAQ_LISTING_BLOCKERS = frozenset(
    {
        "listing_directory_unavailable",
        "listing_directory_stale",
        "listing_directory_schema_mismatch",
        "listing_status_unresolved",
    }
)
_MASSIVE_LISTING_BLOCKERS = frozenset(
    {
        "massive_credential_missing",
        "massive_access_denied",
        "massive_rate_limited",
        "massive_reference_unavailable",
    }
)
_IDENTITY_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_MAX_HINT_TICKERS = 256
_MAX_ALIAS_EDGES = 512
_MAX_ALIASES_PER_TICKER = 64
_MAX_IBKR_POSITION_ROWS = 512
_MAX_IBKR_CONIDS_PER_TICKER = 32
_SQL_BATCH = 200


class LifecycleAutomationNotInstalled(RuntimeError):
    """The reviewed automation schema has not been installed yet."""


def _empty_summary(*, status: str = "succeeded", reason: str | None = None) -> dict:
    return {
        "result_version": 2,
        "case_outcomes": {},
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
    return _timestamp(datetime.now(timezone.utc))


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
def _read_only_connection(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=10.0,
    )
    try:
        yield conn
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> frozenset[str]:
    present = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if present is None:
        return frozenset()
    return frozenset(str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})"))


def _hint_ticker(value: object) -> str:
    ticker = str(value or "").strip().upper()
    if not _IDENTITY_TICKER.fullmatch(ticker):
        raise ValueError("identity_hint_ticker")
    return ticker


def _alias_closures(
    conn: sqlite3.Connection,
    requested: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    columns = _table_columns(conn, "ticker_aliases")
    if not columns:
        return {ticker: (ticker,) for ticker in requested}
    if not {"alias", "canonical"} <= columns:
        raise ValueError("ticker_aliases_schema")

    graph: dict[str, set[str]] = {ticker: {ticker} for ticker in requested}
    queried: set[str] = set()
    frontier = set(requested)
    edges: set[tuple[str, str]] = set()
    while frontier:
        batch = tuple(sorted(frontier))
        queried.update(batch)
        frontier.clear()
        for offset in range(0, len(batch), _SQL_BATCH):
            current = batch[offset : offset + _SQL_BATCH]
            placeholders = ",".join("?" for _ in current)
            rows = conn.execute(
                "SELECT alias,canonical FROM ticker_aliases "
                f"WHERE UPPER(alias) IN ({placeholders}) "
                f"OR UPPER(canonical) IN ({placeholders}) "
                "ORDER BY alias,canonical LIMIT ?",
                (*current, *current, _MAX_ALIAS_EDGES + 1),
            ).fetchall()
            if len(rows) > _MAX_ALIAS_EDGES:
                raise ValueError("ticker_aliases_exceed_limit")
            for raw_alias, raw_canonical in rows:
                alias = _hint_ticker(raw_alias)
                canonical = _hint_ticker(raw_canonical)
                edge = (alias, canonical)
                if edge in edges:
                    continue
                edges.add(edge)
                if len(edges) > _MAX_ALIAS_EDGES:
                    raise ValueError("ticker_aliases_exceed_limit")
                graph.setdefault(alias, {alias}).add(canonical)
                graph.setdefault(canonical, {canonical}).add(alias)
                for value in edge:
                    if value not in queried:
                        frontier.add(value)

    closures: dict[str, tuple[str, ...]] = {}
    for ticker in requested:
        found = {ticker}
        pending = [ticker]
        while pending:
            current = pending.pop()
            for adjacent in graph.get(current, ()):
                if adjacent not in found:
                    found.add(adjacent)
                    pending.append(adjacent)
                    if len(found) > _MAX_ALIASES_PER_TICKER:
                        raise ValueError("ticker_aliases_exceed_limit")
        closures[ticker] = tuple(sorted(found))
    return closures


def _ibkr_conids(
    conn: sqlite3.Connection,
    closures: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[int, ...]]:
    result: dict[str, set[int]] = {ticker: set() for ticker in closures}
    columns = _table_columns(conn, "portfolio_positions")
    if not columns:
        return {ticker: () for ticker in closures}
    if not {"broker", "broker_con_id", "symbol"} <= columns:
        raise ValueError("portfolio_positions_schema")

    roots_by_alias: dict[str, set[str]] = {}
    for ticker, aliases in closures.items():
        for alias in aliases:
            roots_by_alias.setdefault(alias, set()).add(ticker)
    aliases = tuple(sorted(roots_by_alias))
    seen_rows: set[tuple[str, str]] = set()
    for offset in range(0, len(aliases), _SQL_BATCH):
        current = aliases[offset : offset + _SQL_BATCH]
        placeholders = ",".join("?" for _ in current)
        rows = conn.execute(
            "SELECT broker_con_id,symbol FROM portfolio_positions "
            "WHERE LOWER(broker)='ibkr' AND broker_con_id IS NOT NULL "
            f"AND UPPER(symbol) IN ({placeholders}) "
            "ORDER BY symbol,broker_con_id LIMIT ?",
            (*current, _MAX_IBKR_POSITION_ROWS + 1),
        ).fetchall()
        if len(rows) > _MAX_IBKR_POSITION_ROWS:
            raise ValueError("ibkr_identity_candidates_exceed_limit")
        for raw_conid, raw_symbol in rows:
            symbol = _hint_ticker(raw_symbol)
            conid_text = str(raw_conid or "").strip()
            if not conid_text.isdigit() or int(conid_text) <= 0:
                raise ValueError("ibkr_conid")
            row = (conid_text, symbol)
            if row in seen_rows:
                continue
            seen_rows.add(row)
            if len(seen_rows) > _MAX_IBKR_POSITION_ROWS:
                raise ValueError("ibkr_identity_candidates_exceed_limit")
            conid = int(conid_text)
            for ticker in roots_by_alias.get(symbol, ()):
                result[ticker].add(conid)
                if len(result[ticker]) > _MAX_IBKR_CONIDS_PER_TICKER:
                    raise ValueError("ibkr_identity_candidates_exceed_limit")
    return {ticker: tuple(sorted(values)) for ticker, values in result.items()}


def _load_local_identity_hints(
    *,
    market_path: Path,
    profile_path: Path,
    tickers: tuple[str, ...],
) -> dict[str, dict[str, tuple[object, ...]]]:
    requested = tuple(sorted({_hint_ticker(value) for value in tickers}))
    if len(requested) > _MAX_HINT_TICKERS:
        raise ValueError("identity_hint_tickers_exceed_limit")
    if not requested:
        return {}
    with _read_only_connection(market_path) as market_conn:
        closures = _alias_closures(market_conn, requested)
    with _read_only_connection(profile_path) as profile_conn:
        conids = _ibkr_conids(profile_conn, closures)
    return {
        ticker: {
            "ticker_aliases": closures[ticker],
            "ibkr_conids": conids[ticker],
        }
        for ticker in requested
    }


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


def _reconcile_running_rows(
    *,
    at: str,
    execution_owner_id: str | None = None,
) -> tuple[str, ...]:
    with _profile_connection() as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        return SecurityLifecycleFactKernel(store).reconcile_running_runs(
            at=at,
            execution_owner_id=execution_owner_id,
        )


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
    hints = _load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=tuple(str(case["ticker"]) for case in cases),
    )
    rendered: list[dict[str, object]] = []
    for case in cases:
        item = dict(case)
        item.update(hints[_hint_ticker(case["ticker"])])
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
        ticker_aliases=tuple(case.get("ticker_aliases", ())),
        ibkr_conids=tuple(case.get("ibkr_conids", ())),
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


def _blockers(
    values: list[str | AutomationBlocker],
    *,
    at: str,
) -> tuple[tuple[AutomationBlocker, ...], str | None]:
    rows_by_code: dict[str, AutomationBlocker] = {}
    for value in values:
        row = (
            value
            if isinstance(value, AutomationBlocker)
            else AutomationBlocker(
                code=value,
                retryable=value in _RETRYABLE_BLOCKERS,
                context={},
            )
        )
        current = rows_by_code.get(row.code)
        if current is None or (not current.context and row.context):
            rows_by_code[row.code] = row
    rows = tuple(rows_by_code[code] for code in sorted(rows_by_code))
    if not rows or not all(row.retryable for row in rows):
        return rows, None

    parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
    retry_candidates = [_timestamp(parsed + timedelta(days=1))]
    for row in rows:
        candidate = row.context.get("next_check_at")
        if candidate is not None:
            retry_candidates.append(
                _timestamp(
                    datetime.fromisoformat(str(candidate).replace("Z", "+00:00"))
                )
            )
    return rows, max(retry_candidates)


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

    def reqMktData(
        self,
        contract,
        genericTickList,
        snapshot,
        regulatorySnapshot,
    ):
        gateway = getattr(self._source, "_ib", None)
        if gateway is None:
            raise ConnectionError("ibkr_gateway_unavailable")
        return gateway.reqMktData(
            contract,
            genericTickList,
            snapshot,
            regulatorySnapshot,
        )

    def sleep(self, seconds: float) -> None:
        gateway = getattr(self._source, "_ib", None)
        if gateway is None:
            raise ConnectionError("ibkr_gateway_unavailable")
        gateway.sleep(seconds)

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
        candidate_tickers=regulator_successors,
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


def _event_kinds(case: Mapping[str, object]) -> frozenset[str]:
    observation = case.get("observation")
    if not isinstance(observation, Mapping):
        raise ValueError("source_observation_missing")
    raw_kinds = observation.get("kinds", ())
    if not isinstance(raw_kinds, (list, tuple)):
        raise ValueError("observation_kinds")
    return frozenset(
        str(row.get("event_type") or "").strip()
        for row in raw_kinds
        if isinstance(row, Mapping) and str(row.get("event_type") or "").strip()
    )


def _exact_fact_date(facts: tuple[object, ...], fact_type: str) -> date | None:
    values = {
        str(_fact_value(fact)).strip()
        for fact in facts
        if _fact_type(fact) == fact_type and _fact_value(fact)
    }
    if len(values) != 1:
        return None
    try:
        return date.fromisoformat(next(iter(values)))
    except ValueError as exc:
        raise ValueError(fact_type) from exc


def _has_terminal_or_identity_resolution(facts: tuple[object, ...]) -> bool:
    resolved_effects = {
        "asset_acquisition_no_registrant_change",
        "no_identity_change",
        "symbol_and_venue_change",
        "symbol_change",
        "terminal_delisting",
        "venue_change_only",
    }
    return any(
        _fact_type(fact) == "tracked_security_effect"
        and _fact_value(fact) in resolved_effects
        for fact in facts
    )


def _pending_event_monitoring(
    case: Mapping[str, object],
    facts: tuple[object, ...],
    *,
    source_family_results: Mapping[str, str],
    source_deadlines: tuple[object, ...],
    at: str,
) -> AutomationBlocker | None:
    kinds = _event_kinds(case)
    if "acquisition_completed" in kinds:
        return None
    if not kinds.intersection(
        {"merger_agreement", "merger_proxy", "listing_status_review"}
    ):
        return None
    if _has_terminal_or_identity_resolution(facts):
        return None

    instant = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
    today = instant.date()
    effective = _exact_fact_date(facts, "effective_date")
    deadlines = tuple(source_deadlines)
    if len({str(getattr(row, "date", "")) for row in deadlines}) > 1:
        raise ValueError("source_deadlines")
    deadline = deadlines[0] if deadlines else None
    deadline_date = (
        date.fromisoformat(str(getattr(deadline, "date")))
        if deadline is not None
        else None
    )

    context: dict[str, object] = {
        "monitoring_reason": "event_completion_not_confirmed",
    }
    if effective is not None:
        context["effective_date"] = effective.isoformat()
    if deadline is not None:
        context.update(
            {
                "source_deadline": deadline_date.isoformat(),
                "source_deadline_evidence_id": getattr(deadline, "evidence_id"),
                "source_deadline_span_start_byte": getattr(
                    deadline, "span_start_byte"
                ),
                "source_deadline_span_end_byte": getattr(deadline, "span_end_byte"),
                "source_deadline_cited_text_sha256": getattr(
                    deadline, "cited_text_sha256"
                ),
                "source_deadline_rule_id": getattr(deadline, "rule_id"),
                "source_deadline_rule_version": getattr(deadline, "rule_version"),
            }
        )

    required_families = {
        "regulator",
        "listing_authority",
    }
    sources_complete = all(
        source_family_results.get(family) == "available"
        for family in required_families
    )
    if deadline_date is not None and today >= deadline_date and sources_complete:
        context["monitoring_reason"] = "not_confirmed_as_of"
        context["as_of"] = today.isoformat()
        return AutomationBlocker(
            code="sec_evidence_insufficient",
            retryable=False,
            context=context,
        )

    if effective is not None and today < effective:
        next_check = datetime.combine(
            effective,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
    elif effective is not None and today <= effective + timedelta(days=7):
        next_check = instant + timedelta(days=1)
    else:
        next_check = instant + timedelta(days=7)
    if deadline_date is not None and today < deadline_date:
        deadline_check = datetime.combine(
            deadline_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        next_check = min(next_check, deadline_check)
    context["next_check_at"] = _timestamp(next_check)
    return AutomationBlocker(
        code="sec_evidence_insufficient",
        retryable=True,
        context=context,
    )


def _provider_state(codes: tuple[str, ...], *, family: str) -> str:
    conflict_codes = {
        "regulator": {"source_conflict"},
        "listing_authority": {"listing_authority_conflict"},
        "market_infrastructure": {"ibkr_contract_ambiguous"},
    }[family]
    unavailable_codes = {
        "regulator": {
            "sec_access_denied",
            "sec_document_unavailable",
            "sec_governor_unavailable",
            "sec_identity_unconfigured",
            "sec_rate_limited",
            "sec_request_budget_exhausted",
            "sec_transport_unavailable",
        },
        "market_infrastructure": {
            "ibkr_entitlement_denied",
            "ibkr_gateway_unavailable",
        },
        "listing_authority": {
            "listing_directory_unavailable",
            "listing_directory_stale",
            "listing_directory_schema_mismatch",
            "massive_credential_missing",
            "massive_access_denied",
            "massive_rate_limited",
            "massive_reference_unavailable",
            "listing_status_unresolved",
        },
    }[family]
    if conflict_codes.intersection(codes):
        return "conflict"
    if unavailable_codes.intersection(codes):
        return "unavailable"
    return "available"


def _required_listing_codes(
    codes: tuple[str, ...],
    *,
    required_components: frozenset[str],
) -> tuple[str, ...]:
    return tuple(
        code
        for code in codes
        if not (
            (code in _NASDAQ_LISTING_BLOCKERS and "nasdaq" not in required_components)
            or (
                code in _MASSIVE_LISTING_BLOCKERS
                and "massive" not in required_components
            )
        )
    )


def _load_evidence(
    case: Mapping[str, object],
    *,
    mode: str,
    at: str,
    listing_session: ListingAuthoritySession,
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
            f"sec_{'payload_bytes' if key == 'body_bytes' else key}": value
            for key, value in transport.diagnostics(budget).items()
        }
    finally:
        transport.close()

    sec_codes = tuple(_normalize_sec_blocker(str(code)) for code in sec.blockers)
    codes: list[str | AutomationBlocker] = list(sec_codes)
    if not sec.facts and "sec_evidence_insufficient" not in sec_codes:
        codes.append("sec_evidence_insufficient")
    evidence: list[object] = list(sec.evidence)
    facts: list[object] = list(sec.facts)
    source_deadlines = tuple(getattr(sec, "source_deadlines", ()))
    deadline_dates = {str(getattr(row, "date", "")) for row in source_deadlines}
    if len(deadline_dates) > 1:
        raise ValueError("source_deadlines")

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
    effective = _exact_fact_date(tuple(facts), "effective_date")
    today = datetime.fromisoformat(at.replace("Z", "+00:00")).date()
    explicit_inactive_required = terminal and (
        effective is None or today >= effective
    )
    candidate_tickers = tuple(
        sorted({str(case.get("ticker") or "").upper(), *successor_values})
    )
    listing = listing_session.lookup(
        context=context,
        candidate_tickers=candidate_tickers,
        require_explicit_inactive=explicit_inactive_required,
    )
    evidence.extend(listing.evidence)
    facts.extend(listing.facts)
    required_listing_components = listing_authority_required_components(
        case=case,
        regulator_facts=sec.facts,
        listing_evidence=listing.evidence,
    )
    if terminal and not explicit_inactive_required:
        required_listing_components = required_listing_components - {"massive"}
    listing_codes = _required_listing_codes(
        tuple(str(code) for code in listing.blockers)
        + listing_authority_conflict_codes(
            case=case,
            evidence=evidence,
            facts=facts,
        ),
        required_components=required_listing_components,
    )
    codes.extend(listing_codes)
    diagnostics.update(
        {
            key.replace("_body_bytes", "_payload_bytes"): value
            for key, value in listing.diagnostics.items()
        }
    )
    pending_kinds = _event_kinds(case).intersection(
        {"merger_agreement", "merger_proxy", "listing_status_review"}
    )
    deadline_due = bool(
        deadline_dates
        and today >= date.fromisoformat(next(iter(deadline_dates)))
    )
    pending_market_check = bool(
        pending_kinds
        and "acquisition_completed" not in _event_kinds(case)
        and not _has_terminal_or_identity_resolution(tuple(facts))
        and (
            (effective is not None and today >= effective)
            or deadline_due
        )
    )
    ibkr_codes: tuple[str, ...] = ()
    market_queried = False
    if successor_values or terminal or pending_market_check:
        ibkr, ibkr_facts = _ibkr_evidence(
            context,
            at=at,
            regulator_successors=successor_values,
        )
        market_queried = True
        evidence.extend(ibkr.evidence)
        facts.extend(ibkr_facts)
        ibkr_codes = tuple(str(code) for code in ibkr.blockers)
        codes.extend(
            code
            for code in ibkr_codes
            if code not in {
                "ibkr_contract_missing",
                "ibkr_entitlement_denied",
                "ibkr_gateway_unavailable",
            }
        )
        diagnostics["ibkr_requests"] = int(ibkr.requests_made)
    else:
        diagnostics["ibkr_requests"] = 0
    diagnostics["ibkr_unavailable"] = int(
        bool(
            {"ibkr_entitlement_denied", "ibkr_gateway_unavailable"}.intersection(
                ibkr_codes
            )
        )
    )
    diagnostics["ibkr_missing"] = int("ibkr_contract_missing" in ibkr_codes)
    diagnostics["ibkr_conflict"] = int("ibkr_contract_ambiguous" in ibkr_codes)

    source_family_results = {
        "regulator": _provider_state(sec_codes, family="regulator"),
        "listing_authority": _provider_state(
            listing_codes,
            family="listing_authority",
        ),
    }
    if market_queried:
        source_family_results["market_infrastructure"] = _provider_state(
            ibkr_codes,
            family="market_infrastructure",
        )
    pending = _pending_event_monitoring(
        case,
        tuple(facts),
        source_family_results=source_family_results,
        source_deadlines=source_deadlines,
        at=at,
    )
    if pending is not None:
        codes.append(pending)

    blockers, retry_at = _blockers(codes, at=at)
    return LifecycleAutomationEvidenceBundle(
        evidence=tuple(evidence),
        facts=tuple(facts),
        blockers=blockers,
        diagnostics=diagnostics,
        retry_at=retry_at,
    )


def _worker(
    *,
    evidence_loader,
    execution_owner_id: str,
    clock=_clock,
) -> LifecycleAutomationWorker:
    _assert_automation_installed()
    return LifecycleAutomationWorker(
        case_loader=_load_cases,
        profile_connection=_profile_connection,
        evidence_loader=evidence_loader,
        source_loader=_load_sources,
        transition_preview=_transition_preview,
        transition_approver=_transition_approver,
        clock=clock,
        execution_owner_id=execution_owner_id,
    )


def _bounded_result(result: Mapping[str, object]) -> dict:
    if not isinstance(result, Mapping):
        raise ValueError("result")
    result_version = result.get("result_version", 1)
    if type(result_version) is not int or result_version not in {1, 2}:
        raise ValueError("result_version")
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
        if (
            not case_id
            or len(case_id) > 160
            or "\0" in case_id
            or (result_version == 2 and case_id != raw_id)
        ):
            raise ValueError("case_ids")
        case_ids.append(case_id)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_ids")

    case_outcomes: dict[str, str] | None = None
    if result_version == 2:
        raw_outcomes = result.get("case_outcomes")
        if not isinstance(raw_outcomes, Mapping):
            raise ValueError("case_outcomes")
        case_outcomes = {}
        allowed_outcomes = {
            "accepted",
            "drafted",
            "blocked",
            "failed",
            "skipped_current",
        }
        for raw_case_id, raw_outcome in raw_outcomes.items():
            if not isinstance(raw_case_id, str):
                raise ValueError("case_outcomes")
            normalized_case_id = raw_case_id.strip()
            if (
                normalized_case_id != raw_case_id
                or not normalized_case_id
                or len(normalized_case_id) > 160
                or "\0" in normalized_case_id
                or normalized_case_id in case_outcomes
            ):
                raise ValueError("case_outcomes")
            if raw_outcome not in allowed_outcomes:
                raise ValueError("case_outcomes")
            case_outcomes[normalized_case_id] = str(raw_outcome)
        non_skipped = {
            case_id
            for case_id, outcome in case_outcomes.items()
            if outcome != "skipped_current"
        }
        if non_skipped != set(case_ids) or len(non_skipped) != counts["selected"]:
            raise ValueError("case_outcomes")
        if counts["processed"] != counts["selected"]:
            raise ValueError("case_outcomes")
        for outcome in (
            "accepted",
            "drafted",
            "blocked",
            "failed",
            "skipped_current",
        ):
            if counts[outcome] != sum(
                value == outcome for value in case_outcomes.values()
            ):
                raise ValueError("case_outcomes")

    supplied_status = result.get("status")
    supplied_reason = result.get("reason")
    if supplied_status in {"unavailable", "not_installed", "skipped"}:
        if any(counts.values()) or case_ids:
            raise ValueError("status")
        status = str(supplied_status)
        reason = str(supplied_reason or "")
        if status == "not_installed":
            if reason != "automation_schema_absent":
                raise ValueError("reason")
        elif status == "skipped":
            if reason != "already_running":
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
    bounded = {
        "status": status,
        "reason": reason,
        **counts,
        "case_ids": case_ids,
    }
    if result_version == 2:
        bounded["result_version"] = 2
        bounded["case_outcomes"] = case_outcomes
    return bounded


@contextmanager
def _listing_authority_session(*, at: str) -> Iterator[ListingAuthoritySession]:
    transport: ListingAuthorityTransport | None = None
    session: ListingAuthoritySession | None = None
    session_closed = False
    try:
        transport = ListingAuthorityTransport()
        session = ListingAuthoritySession(
            transport=transport,
            budget=ListingRequestBudget.lifecycle(),
            retrieved_at=at,
            massive_api_key=provider_field_env_value(
                MASSIVE_CONFIG_PROVIDER,
                "api_key",
            ),
        )
        yield session
    finally:
        if session is not None:
            try:
                session.close()
                session_closed = True
            except Exception as exc:
                logger.warning(
                    "security lifecycle listing cleanup failed code=%s",
                    type(exc).__name__,
                )
        if transport is not None and not session_closed:
            try:
                transport.close()
            except Exception as exc:
                logger.warning(
                    "security lifecycle listing transport cleanup failed code=%s",
                    type(exc).__name__,
                )


def _automation_exception_result(exc: Exception) -> dict:
    if isinstance(exc, LifecycleAutomationNotInstalled):
        return _empty_summary(
            status="not_installed",
            reason="automation_schema_absent",
        )
    if isinstance(exc, LifecycleStoreUnavailable):
        reason = (
            "market_store_unavailable"
            if exc.store == "market"
            else "profile_store_unavailable"
        )
        return security_lifecycle_automation_failure(reason)
    if isinstance(exc, (LifecycleSchemaMismatch, LifecycleWritesUnavailable)):
        return security_lifecycle_automation_failure("profile_schema_mismatch")
    if isinstance(exc, (OSError, sqlite3.Error)):
        return security_lifecycle_automation_failure("profile_store_unavailable")
    logger.warning(
        "security lifecycle automation tick failed code=%s",
        type(exc).__name__,
    )
    return security_lifecycle_automation_failure("automation_scheduler_failed")


def _run_owned_automation_batch(
    *,
    limit: int,
    at: str,
    execution_owner_id: str,
) -> dict:
    try:
        with _listing_authority_session(at=at) as session:
            worker = _worker(
                evidence_loader=lambda case, *, mode, at: _load_evidence(
                    case,
                    mode=mode,
                    at=at,
                    listing_session=session,
                ),
                execution_owner_id=execution_owner_id,
                clock=lambda: at,
            )
            return _bounded_result(worker.run(limit=limit, mode="live"))
    except Exception as exc:
        return _automation_exception_result(exc)


def _record_automation_result(result: Mapping[str, object], *, now: datetime) -> None:
    try:
        record_security_lifecycle_automation_result(result, now=now)
    except Exception as exc:
        logger.warning(
            "security lifecycle automation result recording failed code=%s",
            type(exc).__name__,
        )


def _run_security_lifecycle_automation(
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
    *,
    record_result: bool,
) -> dict:
    if type(limit) is not int or not 1 <= limit <= _MAX_CASES:
        raise ValueError("limit")
    instant = _aware_instant(now)
    at = _timestamp(instant)
    try:
        with lifecycle_automation_execution_lock() as execution:
            try:
                startup_reconciled = False
                active_failure = False
                try:
                    _reconcile_running_rows(at=at)
                    startup_reconciled = True
                    result = _run_owned_automation_batch(
                        limit=limit,
                        at=at,
                        execution_owner_id=execution.execution_owner_id,
                    )
                except BaseException:
                    active_failure = True
                    raise
                finally:
                    if startup_reconciled:
                        try:
                            _reconcile_running_rows(
                                at=at,
                                execution_owner_id=execution.execution_owner_id,
                            )
                        except Exception as exc:
                            if not active_failure:
                                raise
                            logger.warning(
                                "security lifecycle owner cleanup failed code=%s",
                                type(exc).__name__,
                            )
            except Exception as exc:
                result = _automation_exception_result(exc)
            if record_result:
                _record_automation_result(result, now=instant)
            return result
    except LifecycleAutomationAlreadyRunning:
        result = _empty_summary(status="skipped", reason="already_running")
    except LifecycleAutomationExecutionUnavailable:
        result = security_lifecycle_automation_failure(
            "execution_lock_unavailable"
        )
    except Exception as exc:
        result = _automation_exception_result(exc)
    if record_result:
        _record_automation_result(result, now=instant)
    return result


def run_security_lifecycle_automation(
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Run one exclusively owned batch without recording its result."""

    return _run_security_lifecycle_automation(
        limit=limit,
        now=now,
        record_result=False,
    )


def run_and_record_security_lifecycle_automation(
    limit: int = _DEFAULT_LIMIT,
    now: datetime | None = None,
) -> dict:
    """Run and persist one batch before releasing exclusive ownership."""

    return _run_security_lifecycle_automation(
        limit=limit,
        now=now,
        record_result=True,
    )


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


def _is_operational_failure(result: Mapping[str, object]) -> bool:
    return result.get("status") == "unavailable" or (
        result.get("status") == "partial"
        and result.get("reason") == "case_processing_failed"
    )


def _failed_case_ids(
    conn: sqlite3.Connection,
    result: Mapping[str, object],
) -> tuple[str, ...]:
    if result.get("result_version") == 2:
        outcomes = result.get("case_outcomes")
        if not isinstance(outcomes, Mapping):
            raise ValueError("case_outcomes")
        return tuple(
            sorted(
                str(case_id)
                for case_id, outcome in outcomes.items()
                if outcome == "failed"
            )
        )
    failed: list[str] = []
    for case_id in sorted(str(value) for value in result.get("case_ids", ())):
        row = _latest_case_run(conn, case_id)
        if row is None:
            failed.append(case_id)
            continue
        if str(row["status"]) in {"failed", "running"}:
            failed.append(case_id)
            continue
        if _run_finalization_failure(row) is not None:
            failed.append(case_id)
    return tuple(failed)


def _latest_case_run(
    conn: sqlite3.Connection,
    case_id: str,
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT run_id,status,query_context_json FROM "
        "security_lifecycle_automation_runs WHERE case_id=? "
        "ORDER BY created_at DESC,rowid DESC LIMIT 1",
        (case_id,),
    ).fetchone()


def _run_finalization_failure(row: sqlite3.Row) -> dict[str, object] | None:
    raw_context = row["query_context_json"]
    if not isinstance(raw_context, str):
        raise ValueError("automation_query_context")
    try:
        context = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise ValueError("automation_query_context") from exc
    if not isinstance(context, Mapping):
        raise ValueError("automation_query_context")
    return normalize_terminal_finalization_failure(
        context.get("terminal_finalization_failure")
    )


def _case_failure_marker(
    conn: sqlite3.Connection,
    case_id: str,
) -> dict[str, object]:
    row = _latest_case_run(conn, case_id)
    if row is None:
        return {"run_id": None, "recovery": "new_attempt"}
    recovery = (
        "finalization"
        if str(row["status"]) == "succeeded"
        and _run_finalization_failure(row) is not None
        else "new_attempt"
    )
    return {"run_id": str(row["run_id"]), "recovery": recovery}


def _normalize_active_incident(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "case_failures",
        "scheduler_failure",
    }:
        raise ValueError("automation_active_incident")
    raw_cases = value.get("case_failures")
    if not isinstance(raw_cases, Mapping):
        raise ValueError("automation_active_incident")
    cases: dict[str, dict[str, object]] = {}
    for raw_case_id, raw_marker in raw_cases.items():
        if (
            not isinstance(raw_case_id, str)
            or not raw_case_id
            or len(raw_case_id) > 160
            or "\0" in raw_case_id
            or not isinstance(raw_marker, Mapping)
            or set(raw_marker) != {"run_id", "recovery"}
        ):
            raise ValueError("automation_active_incident")
        run_id = raw_marker.get("run_id")
        recovery = raw_marker.get("recovery")
        if (
            run_id is not None
            and (
                not isinstance(run_id, str)
                or not run_id
                or len(run_id) > 160
                or "\0" in run_id
            )
        ) or recovery not in {"new_attempt", "finalization"}:
            raise ValueError("automation_active_incident")
        cases[raw_case_id] = {"run_id": run_id, "recovery": recovery}
    scheduler_failure = value.get("scheduler_failure")
    if scheduler_failure is not None:
        if (
            not isinstance(scheduler_failure, Mapping)
            or set(scheduler_failure) != {"reason"}
            or scheduler_failure.get("reason") not in _REASONS
        ):
            raise ValueError("automation_active_incident")
        scheduler_failure = {"reason": str(scheduler_failure["reason"])}
    if not cases and scheduler_failure is None:
        return None
    return {
        "case_failures": cases,
        "scheduler_failure": scheduler_failure,
    }


def _incident_identity(
    value: Mapping[str, object] | None,
) -> tuple[tuple[str, ...], str | None]:
    normalized = _normalize_active_incident(value)
    if normalized is None:
        return (), None
    scheduler_failure = normalized["scheduler_failure"]
    reason = (
        None
        if scheduler_failure is None
        else str(scheduler_failure["reason"])
    )
    return tuple(sorted(normalized["case_failures"])), reason


def _state_envelope(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("automation_scheduler_state") from exc
    if not isinstance(value, Mapping) or set(value) != {
        "state_version",
        "latest_result",
        "active_incident",
    }:
        raise ValueError("automation_scheduler_state")
    if value.get("state_version") != _AUTOMATION_STATE_VERSION:
        raise ValueError("automation_scheduler_state")
    latest = value.get("latest_result")
    if not isinstance(latest, Mapping):
        raise ValueError("automation_scheduler_state")
    return {
        "state_version": _AUTOMATION_STATE_VERSION,
        "latest_result": _bounded_result(latest),
        "active_incident": _normalize_active_incident(
            value.get("active_incident")
        ),
    }


def _incident_from_result(
    conn: sqlite3.Connection,
    result: Mapping[str, object],
) -> dict[str, object] | None:
    if not _is_operational_failure(result):
        return None
    case_ids = _failed_case_ids(conn, result)
    if case_ids:
        return {
            "case_failures": {
                case_id: _case_failure_marker(conn, case_id)
                for case_id in case_ids
            },
            "scheduler_failure": None,
        }
    return {
        "case_failures": {},
        "scheduler_failure": {"reason": str(result["reason"])},
    }


def _case_failure_is_active(
    conn: sqlite3.Connection,
    case_id: str,
    marker: Mapping[str, object],
) -> bool:
    latest = _latest_case_run(conn, case_id)
    if latest is None:
        return True
    baseline_run_id = marker.get("run_id")
    latest_run_id = str(latest["run_id"])
    latest_status = str(latest["status"])
    finalization_failure = _run_finalization_failure(latest)
    if marker.get("recovery") == "finalization" and latest_run_id == baseline_run_id:
        return latest_status != "succeeded" or finalization_failure is not None
    if latest_run_id == baseline_run_id:
        return True
    return latest_status in {"failed", "running"} or finalization_failure is not None


def _reconcile_active_incident(
    conn: sqlite3.Connection,
    incident: Mapping[str, object] | None,
    *,
    scheduler_succeeded: bool,
) -> dict[str, object] | None:
    normalized = _normalize_active_incident(incident)
    if normalized is None:
        return None
    cases = {
        case_id: dict(marker)
        for case_id, marker in normalized["case_failures"].items()
        if _case_failure_is_active(conn, case_id, marker)
    }
    scheduler_failure = normalized["scheduler_failure"]
    if scheduler_succeeded:
        scheduler_failure = None
    return _normalize_active_incident(
        {
            "case_failures": cases,
            "scheduler_failure": scheduler_failure,
        }
    )


def _load_active_incident(
    conn: sqlite3.Connection,
    latest_witness: sqlite3.Row | None,
) -> dict[str, object] | None:
    state_row = conn.execute(
        "SELECT last_result FROM scheduler_state WHERE source=?",
        (_JOB_NAME,),
    ).fetchone()
    if state_row is not None:
        envelope = _state_envelope(state_row["last_result"])
        if envelope is not None:
            return envelope["active_incident"]
    if latest_witness is None or latest_witness["status"] != "failed":
        return None
    legacy = _stored_result(latest_witness["result"])
    if legacy is None:
        raise ValueError("automation_legacy_witness")
    return _incident_from_result(conn, legacy)


def _write_automation_state(
    conn: sqlite3.Connection,
    *,
    result: Mapping[str, object],
    active_incident: Mapping[str, object] | None,
    at: str,
) -> None:
    envelope = {
        "state_version": _AUTOMATION_STATE_VERSION,
        "latest_result": dict(result),
        "active_incident": _normalize_active_incident(active_incident),
    }
    conn.execute(
        "INSERT INTO scheduler_state "
        "(source,last_status,last_error,continuation,last_result,updated_at) "
        "VALUES (?,?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET "
        "last_status=excluded.last_status,last_error=excluded.last_error,"
        "continuation=NULL,last_result=excluded.last_result,"
        "updated_at=excluded.updated_at",
        (
            _JOB_NAME,
            "failed" if envelope["active_incident"] is not None else result["status"],
            (
                "active_incident"
                if envelope["active_incident"] is not None
                else None
            ),
            None,
            json.dumps(envelope, sort_keys=True, separators=(",", ":")),
            at,
        ),
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
    failed = _is_operational_failure(result)
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
    if bounded["status"] in {"not_installed", "skipped"}:
        return True

    conn = _job_runs_connection()
    if conn is None:
        _log_witness_unavailable(bounded)
        return False
    try:
        ensure_scheduler_state_schema(conn)
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
        prior_active = _load_active_incident(conn, latest)
        reconciled = _reconcile_active_incident(
            conn,
            prior_active,
            scheduler_succeeded=not _is_operational_failure(bounded),
        )
        current_incident = _incident_from_result(conn, bounded)
        active = reconciled
        incident_changed = False
        if current_incident is not None:
            base_cases = (
                {}
                if active is None
                else {
                    case_id: dict(marker)
                    for case_id, marker in active["case_failures"].items()
                }
            )
            base_scheduler_failure = (
                None if active is None else active["scheduler_failure"]
            )
            base_cases.update(current_incident["case_failures"])
            if current_incident["scheduler_failure"] is not None:
                base_scheduler_failure = current_incident["scheduler_failure"]
            merged = _normalize_active_incident(
                {
                    "case_failures": base_cases,
                    "scheduler_failure": base_scheduler_failure,
                }
            )
            incident_changed = _incident_identity(merged) != _incident_identity(
                reconciled
            )
            active = merged

        at = _witness_at(
            now,
            latest["started_at"] if latest is not None else None,
        )
        if current_incident is not None and incident_changed:
            _insert_witness(
                conn,
                result=bounded,
                now=now,
                not_before=latest["started_at"] if latest is not None else None,
            )
        elif prior_active is not None and active is None:
            _insert_witness(
                conn,
                result=bounded,
                now=now,
                not_before=latest["started_at"] if latest is not None else None,
            )
        _write_automation_state(
            conn,
            result=bounded,
            active_incident=active,
            at=at,
        )
        conn.commit()
        return True
    except (OSError, TypeError, ValueError, sqlite3.Error):
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
    "run_and_record_security_lifecycle_automation",
    "run_security_lifecycle_automation",
    "security_lifecycle_automation_failure",
]
