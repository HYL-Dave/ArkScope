"""Structured listing authority; absence, identity continuity and trading differ."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Literal

from data_sources.lifecycle_provider_census_transport import MassiveTickerEventsResult
from src.security_lifecycle_listing_evidence import ListingEvidence


PROVIDER_OBSERVATION_SOURCE = "listing_authority"
_AUTHORITIES = {"massive_reference": "massive", "nasdaq_symbol_directory": "nasdaq_trader", "eodhd_symbol_directory": "eodhd"}
_TICKER = re.compile(r"[A-Z][A-Z0-9.-]{0,15}")
_CONTINUATION_ERROR_PREFIXES = ("massive_timeline_", "massive_successor_")


@dataclass(frozen=True)
class ProviderListingDecision:
    listing_state: Literal["active", "inactive", "unresolved"]
    continuation_state: Literal["confirmed", "candidate", "unavailable", "ambiguous", "not_observed"] = "not_observed"
    listing_reasons: tuple[str, ...] = ()
    continuation_reasons: tuple[str, ...] = ()
    listing_end_date: str | None = None
    continuation_effective_date: str | None = None
    successor_ticker: str | None = None
    candidate_tickers: tuple[str, ...] = ()

    @property
    def state(self) -> str:
        """Existing storage vocabulary; it is not a claim of issuer extinction."""
        if self.listing_state == "active":
            return "active"
        if self.continuation_state == "confirmed":
            return "continuation"
        return "terminal" if self.listing_state == "inactive" else "unresolved"

    @property
    def effective_date(self) -> str | None:
        return self.continuation_effective_date if self.state == "continuation" else self.listing_end_date

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.listing_reasons + (self.continuation_reasons if self.state == "unresolved" else ()))))


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


def _unresolved(*reasons: str) -> ProviderListingDecision:
    return ProviderListingDecision("unresolved", "unavailable", listing_reasons=tuple(sorted(set(reasons))))


def _date(value: object, *, timestamp: bool = False) -> date:
    if not isinstance(value, str):
        raise ValueError("provider_date")
    if timestamp and len(value) > 10:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("provider_date")
        return parsed.astimezone(timezone.utc).date()
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("provider_date")
    return parsed


def _continuation(base, *, ticker, figi, rows, events, issues, today):
    candidates = set()
    for timeline in events:
        latest = timeline.get("latest_ticker")
        if isinstance(latest, str) and _TICKER.fullmatch(latest) and latest != ticker:
            candidates.add(latest)
        relations = timeline.get("events")
        if isinstance(relations, (tuple, list)):
            for relation in relations:
                if (isinstance(relation, (tuple, list)) and len(relation) == 3 and relation[0] == ticker
                        and isinstance(relation[1], str) and _TICKER.fullmatch(relation[1]) and relation[1] != ticker):
                    candidates.add(relation[1])

    def result(state, *reasons):
        return replace(base, continuation_state=state, continuation_reasons=tuple(sorted(set(reasons))),
                       candidate_tickers=tuple(sorted(candidates)))

    if issues:
        return result("ambiguous" if any("invalid" in issue for issue in issues) else "unavailable", *issues)
    if not events:
        return result("unavailable", "successor_check_unavailable")
    timelines = [row for row in events if row.get("composite_figi") == figi]
    if len(timelines) != len(events):
        return replace(result("ambiguous", "successor_identity_conflict"), listing_state="unresolved",
                       listing_reasons=tuple(sorted({*base.listing_reasons, "listing_identity_conflict"})))
    if len(timelines) != 1:
        return result("ambiguous", "successor_ambiguous")
    timeline = timelines[0]
    relations = timeline.get("events")
    if (not isinstance(relations, (tuple, list)) or any(
            not isinstance(row, (tuple, list)) or len(row) != 3
            or any(not isinstance(value, str) or not _TICKER.fullmatch(value) for value in row[:2])
            or row[0] == row[1] for row in relations)):
        return result("ambiguous", "successor_check_invalid")
    successors = [row for row in relations if row[0] == ticker]
    if len(successors) > 1:
        return result("ambiguous", "successor_ambiguous")
    if not successors:
        if candidates:
            return result("candidate", "successor_relation_missing")
        if timeline.get("latest_ticker") == ticker:
            return result("not_observed")
        return result("unavailable", "successor_check_unavailable")
    _, successor, changed_on = successors[0]
    try:
        change_date = _date(changed_on)
    except ValueError:
        return result("ambiguous", "successor_date_invalid")
    if change_date > today:
        return result("ambiguous", "successor_date_future")
    if timeline.get("latest_ticker") != successor:
        return result("ambiguous", "successor_ambiguous")
    active = [row for row in rows if row.get("candidate_ticker") == successor and row.get("adapter") == "massive_reference"
              and row.get("market") == "stocks" and row.get("expected_active_state") is True and row.get("listing_status") == "active"]
    if any(row.get("composite_figi") != figi for row in active):
        return result("ambiguous", "successor_identity_conflict")
    if len(active) != 1:
        return result("candidate", "successor_market_confirmation_missing")
    return replace(base, continuation_state="confirmed", continuation_effective_date=changed_on, successor_ticker=successor)


def classify_provider_listing(*, ticker: str, evidence: Iterable[object], today: date,
                              provider_codes: Iterable[str] = ()) -> ProviderListingDecision:
    rows, events = [], []
    listing_issues, continuation_issues = [], []
    for raw in evidence:
        if _field(raw, "source_family") != "listing_authority":
            continue
        optional = _field(raw, "adapter") == "massive_ticker_events"
        try:
            row = evidence_dict(raw)
            locator = row["source_locator"]
            optional = optional or (isinstance(locator.get("candidate_ticker"), str) and locator["candidate_ticker"] != ticker)
            validate_provider_material(row)
            retrieved = datetime.fromisoformat(str(row["retrieved_at"]).replace("Z", "+00:00"))
            if retrieved.tzinfo is None or not today - timedelta(days=3) <= retrieved.astimezone(timezone.utc).date() <= today:
                (continuation_issues if optional else listing_issues).append("successor_check_stale" if optional else "listing_directory_stale")
                continue
            if locator.get("snapshot_complete") is not True:
                (continuation_issues if optional else listing_issues).append("successor_check_incomplete" if optional else "listing_observation_incomplete")
                continue
            if row["adapter"] == "massive_ticker_events":
                if locator.get("candidate_ticker") == ticker:
                    events.append(locator)
                continue
            adapter = row["adapter"]
            if adapter not in _AUTHORITIES or locator.get("adapter") != adapter or locator.get("authority") != _AUTHORITIES[adapter]:
                raise ValueError("listing_observation_invalid")
            if locator.get("listing_status") not in {"active", "inactive", "not_found", "unverified"}:
                raise ValueError("listing_observation_invalid")
            rows.append(locator)
        except (ValueError, TypeError, KeyError):
            (continuation_issues if optional else listing_issues).append("successor_check_invalid" if optional else "listing_observation_invalid")
    if listing_issues:
        return _unresolved(*listing_issues)

    codes = tuple(provider_codes)
    unscoped_codes = tuple(code for code in codes if not code.startswith(_CONTINUATION_ERROR_PREFIXES))
    if any(code.startswith(_CONTINUATION_ERROR_PREFIXES) for code in codes):
        continuation_issues.append("successor_check_unavailable")
    source = [row for row in rows if row.get("candidate_ticker") == ticker]
    active = [row for row in source if row["listing_status"] == "active"]
    inactive = [row for row in source if row["listing_status"] == "inactive"]
    if active:
        if inactive:
            return _unresolved("active_listing_present")
        if unscoped_codes:
            return _unresolved("listing_provider_error")
        return ProviderListingDecision("active")

    massive = [row for row in inactive if row["adapter"] == "massive_reference" and row.get("market") == "stocks" and row.get("expected_active_state") is False]
    if len(massive) != 1:
        return _unresolved("massive_explicit_inactive_missing")
    old = massive[0]
    figi = old.get("composite_figi")
    if not isinstance(figi, str) or re.fullmatch(r"BBG[A-Z0-9]{9}", figi) is None:
        return _unresolved("stable_identity_missing")
    ciks = [row["issuer_cik"] for row in source if row.get("issuer_cik") is not None]
    if (any(row.get("composite_figi") not in (None, figi) for row in source)
            or any(not isinstance(cik, str) or re.fullmatch(r"\d{10}", cik) is None for cik in ciks)
            or len(set(ciks)) > 1):
        return _unresolved("listing_identity_conflict")
    try:
        effective = _date(old.get("delisted_utc"), timestamp=True)
    except ValueError:
        return _unresolved("delisting_date_missing")
    if effective > today:
        return _unresolved("delisting_date_future")

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

    # The old scanner stopped at its first error. With all six required checks
    # present and no timeline, this one legacy code can only belong to the latter.
    legacy_timeline_failure = not missing and not events and not continuation_issues and set(unscoped_codes) == {"massive_not_found"}
    if unscoped_codes and not legacy_timeline_failure:
        return replace(_unresolved(*missing, "listing_provider_error"), listing_end_date=effective.isoformat())
    base = ProviderListingDecision("unresolved" if missing else "inactive", listing_reasons=tuple(sorted(missing)),
                                   listing_end_date=effective.isoformat())
    return _continuation(base, ticker=ticker, figi=figi, rows=rows, events=events, issues=continuation_issues, today=today)


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
    decision = classify_provider_listing(ticker=ticker, evidence=row["evidence"], today=now.date(), provider_codes=row["blockers"])
    if transition_kind == "terminal_delisting":
        if decision.listing_state != "inactive" or successor_ticker is not None:
            return ("provider_terminal_not_confirmed",)
        if decision.listing_end_date != effective_date:
            return ("provider_listing_check_changed",)
        if effective_date < "2025-01-01" and human_accepted is not True:
            return ("provider_legacy_event_review",)
    elif transition_kind == "symbol_continuation":
        if (decision.continuation_state != "confirmed" or decision.successor_ticker != successor_ticker
                or decision.continuation_effective_date != effective_date or human_accepted is not True):
            return ("provider_continuation_review",)
    else:
        return ("provider_transition_kind_invalid",)
    return ()


def evaluate_provider_decision(*, case, evidence, current_date, active_sources, transition_preview):
    from src.security_lifecycle_decision_policy import _decision, _preview

    active_sources = tuple(active_sources)
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
                         conclusion="Current listing evidence does not establish that the old listing is inactive.",
                         impact_summary="Tracking remains unchanged; inspect the missing or conflicting source.")
    if not active_sources:
        return _decision(**common, decision_tier="verified_automatic", action_readiness="not_applicable", confidence="high",
                         outcomes=("listing_ended",), decision_issues=result.continuation_reasons,
                         conclusion="Listing checks confirm the old listing is inactive; it has no active tracking sources.",
                         impact_summary="No further tracking change is requested. Retain any unresolved continuation for follow-up.")
    if result.effective_date < "2025-01-01":
        return _decision(**common, decision_tier="review_suggested", action_readiness="not_applicable", confidence="high",
                         outcomes=("listing_ended",), decision_issues=result.continuation_reasons,
                         conclusion="Listing checks confirm delisting before the automation coverage window.",
                         impact_summary="An attended decision is required to retire this historical tracking membership.")
    if "portfolio_open" in active_sources:
        eligible, issues = False, ("portfolio_position_open",)
    else:
        eligible, issues = _preview(transition_preview, {"transition_kind": "terminal_delisting", "source_ticker": case["ticker"],
                                                       "successor_ticker": None, "effective_date": result.effective_date, "outcomes": ("listing_ended",)})
    return _decision(**common, decision_tier="verified_automatic", action_readiness="transition_eligible" if eligible else "action_blocked",
                     confidence="high", outcomes=("listing_ended",), decision_issues=(*issues, *result.continuation_reasons), transition_requested=eligible,
                     conclusion="Explicit delisting and current listing checks establish that the old listing stopped trading.",
                     impact_summary="Stop active collection for the old security; preserve history and do not track the acquirer automatically.")
