"""Structured listing authority; absence, identity continuity and trading differ."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import json
from types import MappingProxyType

from data_sources.lifecycle_provider_census_transport import MassiveTickerEventsResult
from src.security_lifecycle_listing_evidence import ListingEvidence


PROVIDER_OBSERVATION_SOURCE = "listing_authority"
_AUTHORITIES = {"massive_reference": "massive", "nasdaq_symbol_directory": "nasdaq_trader", "eodhd_symbol_directory": "eodhd"}


@dataclass(frozen=True)
class ProviderListingDecision:
    state: str
    reasons: tuple[str, ...] = ()
    effective_date: str | None = None
    successor_ticker: str | None = None


def _field(row: object, key: str, default=None):
    return row.get(key, default) if isinstance(row, Mapping) else getattr(row, key, default)


def evidence_dict(row: object) -> dict:
    result = {key: _field(row, key) for key in ListingEvidence.__dataclass_fields__}
    locator = result["source_locator"]
    if locator is None:
        encoded = _field(row, "source_locator_json")
        locator = json.loads(encoded) if isinstance(encoded, str) else None
    if not isinstance(locator, Mapping):
        raise ValueError("provider_evidence_locator")
    result["source_locator"] = dict(locator)
    return result


def validate_provider_material(row: Mapping) -> None:
    locator = row["source_locator"]
    excerpt = row["excerpt"]
    if not isinstance(excerpt, str) or hashlib.sha256(excerpt.encode()).hexdigest() != row["content_sha256"]:
        raise ValueError("provider_evidence_binding")
    content = json.loads(excerpt)
    if not isinstance(content, dict):
        raise ValueError("provider_evidence_binding")
    if row["adapter"] == "massive_ticker_events":
        if row["kind"] != "ticker_event_snapshot" or content != locator:
            raise ValueError("provider_evidence_binding")
    else:
        if row["kind"] != "listing_directory_snapshot" or type(locator.get("expected_active_state")) is not bool:
            raise ValueError("provider_evidence_binding")
        if content.get("ticker") != locator.get("candidate_ticker"):
            raise ValueError("provider_evidence_binding")
        if any(content.get(field) != locator.get(field) for field in (
            "authority", "directory", "listing_status", "market", "primary_exchange", "security_type", "issuer_cik",
            "composite_figi", "expected_active_state", "snapshot_complete",
            "delisted_utc", "source_as_of", "provider_last_updated_utc",
        )) or row["source_document_sha256"] != locator.get("source_document_sha256"):
            raise ValueError("provider_evidence_binding")


def ticker_event_evidence(ticker: str, result: MassiveTickerEventsResult, *, at: str) -> ListingEvidence:
    locator = {
        "locator_kind": "ticker_event_snapshot", "candidate_ticker": ticker,
        "composite_figi": result.stable_id, "events": [list(row) for row in result.events],
        "latest_ticker": result.latest_ticker, "snapshot_complete": True,
    }
    excerpt = json.dumps(locator, sort_keys=True, separators=(",", ":"))
    content = hashlib.sha256(excerpt.encode()).hexdigest()
    identity = hashlib.sha256(f"{ticker}\0{result.response_sha256}\0{content}".encode()).hexdigest()
    return ListingEvidence(
        evidence_id=f"events-{identity[:32]}", source_family="listing_authority", adapter="massive_ticker_events",
        kind="ticker_event_snapshot", source_url=result.source_locator,
        title="Same-security ticker timeline", publisher="Massive", domain="api.massive.com",
        source_published_at=None, retrieved_at=at, excerpt=excerpt, content_sha256=content,
        source_document_sha256=result.response_sha256, source_locator=MappingProxyType(locator),
        evidence_dedupe_key=f"events:{identity}",
    )


def classify_provider_listing(*, ticker: str, evidence: Iterable[object], today: date) -> ProviderListingDecision:
    def unresolved(*reasons):
        return ProviderListingDecision("unresolved", tuple(sorted(set(reasons))))

    rows = []
    events = []
    try:
        for raw in evidence:
            if _field(raw, "source_family") != "listing_authority":
                continue
            row = evidence_dict(raw)
            validate_provider_material(row)
            locator = row["source_locator"]
            retrieved = datetime.fromisoformat(str(row["retrieved_at"]).replace("Z", "+00:00"))
            if retrieved.tzinfo is None or not today - timedelta(days=3) <= retrieved.date() <= today:
                return unresolved("listing_directory_stale")
            if locator.get("snapshot_complete") is not True:
                return unresolved("listing_observation_incomplete")
            if row["adapter"] == "massive_ticker_events":
                if locator.get("candidate_ticker") == ticker:
                    events.append(locator)
                continue
            adapter = row["adapter"]
            if adapter not in _AUTHORITIES or locator.get("adapter") != adapter or locator.get("authority") != _AUTHORITIES[adapter]:
                return unresolved("listing_observation_invalid")
            if locator.get("listing_status") not in {"active", "inactive", "not_found", "unverified"}:
                return unresolved("listing_observation_invalid")
            rows.append(locator)
    except (ValueError, TypeError, KeyError):
        return unresolved("listing_observation_invalid")

    source = [row for row in rows if row.get("candidate_ticker") == ticker]
    active = [row for row in source if row["listing_status"] == "active"]
    inactive = [row for row in source if row["listing_status"] == "inactive"]
    if active:
        if inactive:
            return unresolved("active_listing_present")
        return ProviderListingDecision("active")

    massive = [row for row in inactive if row["adapter"] == "massive_reference" and row.get("market") == "stocks" and row.get("expected_active_state") is False]
    if len(massive) != 1:
        return unresolved("massive_explicit_inactive_missing")
    old = massive[0]
    figi = old.get("composite_figi")
    if not isinstance(figi, str) or not figi:
        return unresolved("stable_identity_missing")
    try:
        effective = date.fromisoformat(str(old.get("delisted_utc"))[:10])
    except ValueError:
        return unresolved("delisting_date_missing")
    if effective > today:
        return unresolved("delisting_date_future")

    missing = []
    for market in ("stocks", "otc"):
        negatives = [row for row in source if row["adapter"] == "massive_reference" and row.get("market") == market and row.get("expected_active_state") is True]
        if len(negatives) != 1 or negatives[0]["listing_status"] != "not_found":
            missing.append(f"{market}_continuation_check_missing")
    if not any(row["adapter"] == "eodhd_symbol_directory" for row in inactive):
        missing.append("eodhd_delisting_missing")
    directories = {row.get("directory") for row in source if row["adapter"] == "nasdaq_symbol_directory" and row["listing_status"] == "not_found"}
    if directories != {"nasdaq_listed", "other_listed"}:
        missing.append("nasdaq_not_found_incomplete")

    def unavailable_timeline():
        return ProviderListingDecision("unresolved", tuple(sorted([*missing, "successor_check_unavailable"])), effective.isoformat())

    timelines = [row for row in events if row.get("composite_figi") == figi]
    if len(timelines) != 1:
        return unavailable_timeline()
    timeline = timelines[0]
    relations = timeline.get("events")
    if not isinstance(relations, (tuple, list)) or any(not isinstance(row, (tuple, list)) or len(row) != 3 for row in relations):
        return unresolved("successor_check_invalid")
    successors = [row for row in relations if row[0] == ticker]
    if successors:
        if len(successors) != 1:
            return unresolved("successor_ambiguous")
        _, successor, changed_on = successors[0]
        confirmed = [row for row in rows if row.get("candidate_ticker") == successor and row.get("adapter") == "massive_reference" and row.get("listing_status") == "active" and row.get("composite_figi") == figi]
        if not confirmed:
            return unresolved("successor_market_confirmation_missing")
        try:
            change_date = date.fromisoformat(changed_on)
        except (ValueError, TypeError):
            return unresolved("successor_date_invalid")
        if change_date > today:
            return unresolved("successor_date_future")
        return ProviderListingDecision("continuation", (), changed_on, successor)
    if timeline.get("latest_ticker") != ticker:
        return unavailable_timeline()
    if missing:
        return unresolved(*missing)
    return ProviderListingDecision("terminal", (), effective.isoformat())


def terminal_requires_attestation(result: ProviderListingDecision) -> bool:
    return result.state == "unresolved" and result.reasons == ("successor_check_unavailable",)


def provider_transition_guard(conn, *, ticker, observation_fingerprint_sha256, transition_kind,
                              successor_ticker, effective_date, at, human_accepted):
    """Recheck local provider authority inside the profile write transaction."""
    from src.security_lifecycle_investigation import observation_fingerprint
    from src.security_lifecycle_provider_store import ProviderCheckStore, _instant

    row = ProviderCheckStore.latest_for_connection(conn, ticker)
    if row is None:
        return ("provider_listing_check_required",)
    now = _instant(at)
    if not now - timedelta(days=3) <= _instant(row["at"]) <= now:
        return ("provider_listing_check_stale",)
    if observation_fingerprint(row["observation"]) != observation_fingerprint_sha256:
        return ("provider_listing_check_changed",)
    decision = classify_provider_listing(ticker=ticker, evidence=row["evidence"], today=now.date())
    if decision.effective_date != effective_date:
        return ("provider_listing_check_changed",)
    if transition_kind == "terminal_delisting":
        if human_accepted and terminal_requires_attestation(decision) and set(row["blockers"]) <= {"massive_not_found"}:
            return ()
        if decision.state != "terminal" or row["blockers"]:
            return ("provider_terminal_not_confirmed",)
        if effective_date < "2025-01-01" and not human_accepted:
            return ("provider_legacy_event_review",)
    elif (decision.state != "continuation" or row["blockers"] or decision.successor_ticker != successor_ticker or not human_accepted):
        return ("provider_continuation_review",)
    return ()


def evaluate_provider_decision(*, case, evidence, current_date, active_sources, transition_preview):
    from src.security_lifecycle_decision_policy import _decision, _preview

    today = date.fromisoformat(current_date) if isinstance(current_date, str) else current_date
    result = classify_provider_listing(ticker=str(case["ticker"]), evidence=evidence, today=today)
    common = {"relevance": "direct_tracked_security", "effective_date": result.effective_date,
              "rule_id": "lifecycle.provider_listing_status"}
    if result.state == "active":
        return _decision(**common, decision_tier="verified_automatic", action_readiness="not_applicable", confidence="high",
                         outcomes=("no_tracked_security_change",), conclusion="Current listing authorities confirm active trading.",
                         impact_summary="Continue collecting prices and news.")
    if result.state == "continuation":
        return _decision(**common, decision_tier="review_suggested", action_readiness="not_applicable", confidence="high",
                         outcomes=("symbol_changed",), successor_ticker=result.successor_ticker,
                         conclusion="An exact ticker event and matching security identifier establish continuity.",
                         impact_summary="A reviewed identity transition is required before changing the tracking symbol.")
    if result.state != "terminal":
        return _decision(**common, decision_tier="review_suggested", action_readiness="action_blocked", confidence="low",
                         outcomes=("undetermined",), decision_issues=result.reasons,
                         conclusion="Current listing evidence does not establish a terminal security.",
                         impact_summary="Tracking remains unchanged; inspect the missing or conflicting source.")
    if result.effective_date < "2025-01-01":
        return _decision(**common, decision_tier="review_suggested", action_readiness="not_applicable", confidence="high",
                         outcomes=("listing_ended",), conclusion="Listing checks confirm delisting before the automation coverage window.",
                         impact_summary="An attended decision is required to retire this historical tracking membership.")
    if "portfolio_open" in active_sources:
        eligible, issues = False, ("portfolio_position_open",)
    else:
        eligible, issues = _preview(transition_preview, {"transition_kind": "terminal_delisting", "source_ticker": case["ticker"],
                                                       "successor_ticker": None, "effective_date": result.effective_date, "outcomes": ("listing_ended",)})
    return _decision(**common, decision_tier="verified_automatic", action_readiness="transition_eligible" if eligible else "action_blocked",
                     confidence="high", outcomes=("listing_ended",), decision_issues=issues, transition_requested=eligible,
                     conclusion="Explicit delisting and current listing checks establish that this security stopped trading.",
                     impact_summary="Stop active collection for the old security; preserve history and do not track the acquirer automatically.")
