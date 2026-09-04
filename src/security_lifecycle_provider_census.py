"""Pure known-case oracle for the lifecycle provider authority census."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import re
from typing import Iterable


CENSUS_OUTCOMES = frozenset(
    {
        "confirmed",
        "contradicted",
        "coverage_limited",
        "not_entitled",
        "credential_unavailable",
        "provider_unavailable",
        "ambiguous",
    }
)
CENSUS_AXES = frozenset(
    {
        "listing_state",
        "ticker_change",
        "economic_successor",
    }
)
CENSUS_LISTING_STATES = frozenset(
    {
        "active",
        "inactive",
        "conflicting",
        "unresolved",
    }
)

_PROVIDER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_TICKER = re.compile(r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*(?:\*)?$")
_REASON = re.compile(r"^[a-z][a-z0-9_]*$")
_TERMINAL_CASES = frozenset({"ARCH", "LTHM", "TA"})
_ACTIVE_CASES = frozenset({"AAPL", "SMCI"})
_KNOWN_CASES = frozenset({"LC", *_TERMINAL_CASES, *_ACTIVE_CASES})
_LC_SUCCESSOR = "HAPN"


def _validate_ticker(name: str, value: object, *, provider_marker: bool) -> None:
    if not isinstance(value, str) or _TICKER.fullmatch(value) is None:
        raise ValueError(name)
    canonical_length = len(value[:-1] if value.endswith("*") else value)
    if canonical_length > 16 or (not provider_marker and value.endswith("*")):
        raise ValueError(name)


def _validate_optional_text(name: str, value: object) -> None:
    if value is None:
        return
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 128
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(name)


@dataclass(frozen=True)
class CensusObservation:
    provider: str
    axis: str
    source_ticker: str
    successor_ticker: str | None
    active: bool | None
    stable_id: str | None
    effective_date: str | None
    complete: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.provider, str)
            or _PROVIDER.fullmatch(self.provider) is None
        ):
            raise ValueError("census_provider")
        if self.axis not in CENSUS_AXES:
            raise ValueError("census_axis")
        _validate_ticker("source_ticker", self.source_ticker, provider_marker=True)
        if self.successor_ticker is not None:
            _validate_ticker(
                "successor_ticker",
                self.successor_ticker,
                provider_marker=True,
            )
        _validate_optional_text("stable_id", self.stable_id)
        if type(self.complete) is not bool:
            raise ValueError("observation_complete")
        if self.effective_date is not None:
            if not isinstance(self.effective_date, str):
                raise ValueError("effective_date")
            try:
                parsed_date = date.fromisoformat(self.effective_date)
            except ValueError:
                raise ValueError("effective_date") from None
            if parsed_date.isoformat() != self.effective_date:
                raise ValueError("effective_date")

        if self.axis == "listing_state":
            if self.successor_ticker is not None:
                raise ValueError("successor_relation")
            if self.active is not None and type(self.active) is not bool:
                raise ValueError("listing_state_active")
            if self.complete and self.active is None:
                raise ValueError("listing_state_active")
            return

        if self.active is not None:
            raise ValueError("relation_active")
        if self.complete and self.successor_ticker is None:
            raise ValueError("successor_relation")


@dataclass(frozen=True)
class CensusCaseResult:
    case_id: str
    outcome: str
    listing_state: str
    successor: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_ticker("case_id", self.case_id, provider_marker=False)
        if self.outcome not in CENSUS_OUTCOMES:
            raise ValueError("census_outcome")
        if self.listing_state not in CENSUS_LISTING_STATES:
            raise ValueError("census_listing_state")
        if self.successor is not None:
            _validate_ticker("successor", self.successor, provider_marker=False)
            if self.outcome != "confirmed":
                raise ValueError("successor_authority")
        if not isinstance(self.reasons, tuple):
            raise ValueError("census_reasons")
        if any(
            not isinstance(reason, str) or _REASON.fullmatch(reason) is None
            for reason in self.reasons
        ):
            raise ValueError("census_reasons")
        if self.reasons != tuple(sorted(set(self.reasons))):
            raise ValueError("census_reasons")


@dataclass(frozen=True)
class _ListingSnapshot:
    state: str
    stable_id: str | None
    blocker: str | None


def _exact_ticker(observed: str, expected: str) -> bool:
    return observed == expected


def _listing_snapshot(
    observations: tuple[CensusObservation, ...],
    ticker: str,
) -> _ListingSnapshot:
    rows = tuple(
        row
        for row in observations
        if row.axis == "listing_state" and _exact_ticker(row.source_ticker, ticker)
    )
    if not rows:
        return _ListingSnapshot("unresolved", None, "exact_source_missing")
    if any(not row.complete for row in rows):
        return _ListingSnapshot("unresolved", None, "incomplete_observation")

    states = {row.active for row in rows}
    if len(states) != 1:
        return _ListingSnapshot("conflicting", None, "provider_disagreement")
    state = "active" if states == {True} else "inactive"

    if any(row.stable_id is None for row in rows):
        return _ListingSnapshot(state, None, "missing_stable_identity")
    stable_ids = {row.stable_id for row in rows}
    if len(stable_ids) != 1:
        return _ListingSnapshot(state, None, "stable_identity_conflict")
    return _ListingSnapshot(state, next(iter(stable_ids)), None)


def _deduplicate_observations(
    observations: Iterable[CensusObservation],
) -> tuple[CensusObservation, ...]:
    rows: list[CensusObservation] = []
    seen: dict[tuple[str, str, str], CensusObservation] = {}
    for row in observations:
        if not isinstance(row, CensusObservation):
            raise TypeError("census_observation")
        key = (row.provider, row.axis, row.source_ticker)
        previous = seen.get(key)
        if previous is not None:
            if previous != row:
                raise ValueError("contradictory_observations")
            continue
        seen[key] = row
        rows.append(row)
    return tuple(rows)


def _result(
    case_id: str,
    outcome: str,
    listing_state: str,
    *reasons: str,
    successor: str | None = None,
) -> CensusCaseResult:
    return CensusCaseResult(
        case_id=case_id,
        outcome=outcome,
        listing_state=listing_state,
        successor=successor,
        reasons=tuple(sorted(set(reasons))),
    )


def _classify_lc(
    observations: tuple[CensusObservation, ...],
) -> CensusCaseResult:
    source = _listing_snapshot(observations, "LC")
    if source.blocker is not None:
        return _result("LC", "ambiguous", source.state, source.blocker)
    if source.state != "inactive":
        return _result("LC", "contradicted", source.state, "listing_state_contradicted")

    rename_rows = tuple(
        row
        for row in observations
        if row.axis == "ticker_change" and _exact_ticker(row.source_ticker, "LC")
    )
    conversion_rows = tuple(
        row
        for row in observations
        if row.axis == "economic_successor" and _exact_ticker(row.source_ticker, "LC")
    )
    if any(not row.complete for row in rename_rows):
        return _result("LC", "ambiguous", source.state, "incomplete_observation")
    if any(not row.complete for row in conversion_rows):
        return _result("LC", "ambiguous", source.state, "incomplete_observation")
    complete_conversion_rows = tuple(row for row in conversion_rows if row.complete)
    if not rename_rows:
        outcome = "contradicted" if complete_conversion_rows else "ambiguous"
        reason = (
            "relation_axis_contradicted"
            if complete_conversion_rows
            else "relation_missing"
        )
        return _result("LC", outcome, source.state, reason)
    if complete_conversion_rows:
        return _result("LC", "ambiguous", source.state, "relation_axis_conflict")

    successors = {row.successor_ticker for row in rename_rows}
    if len(successors) != 1:
        return _result("LC", "ambiguous", source.state, "provider_disagreement")
    if successors != {_LC_SUCCESSOR}:
        return _result("LC", "contradicted", source.state, "relation_contradicted")

    if any(row.stable_id is None for row in rename_rows):
        return _result("LC", "ambiguous", source.state, "missing_stable_identity")
    relation_ids = {row.stable_id for row in rename_rows}
    if len(relation_ids) != 1 or relation_ids != {source.stable_id}:
        return _result("LC", "ambiguous", source.state, "stable_identity_conflict")

    successor = _listing_snapshot(observations, _LC_SUCCESSOR)
    if successor.blocker is not None:
        return _result("LC", "ambiguous", source.state, successor.blocker)
    if successor.state != "active":
        return _result(
            "LC",
            "contradicted",
            source.state,
            "successor_listing_contradicted",
        )
    if successor.stable_id != source.stable_id:
        return _result("LC", "ambiguous", source.state, "stable_identity_conflict")
    return _result(
        "LC",
        "confirmed",
        source.state,
        "exact_ticker_change",
        "stable_identity_agreement",
        "successor_active",
        successor=_LC_SUCCESSOR,
    )


def _classify_listing_case(
    case_id: str,
    observations: tuple[CensusObservation, ...],
    *,
    expected_state: str,
) -> CensusCaseResult:
    listing = _listing_snapshot(observations, case_id)
    if listing.blocker is not None:
        return _result(case_id, "ambiguous", listing.state, listing.blocker)

    rename_rows = tuple(
        row
        for row in observations
        if row.axis == "ticker_change" and _exact_ticker(row.source_ticker, case_id)
    )
    if any(not row.complete for row in rename_rows):
        return _result(case_id, "ambiguous", listing.state, "incomplete_observation")
    if rename_rows:
        return _result(
            case_id, "contradicted", listing.state, "unexpected_ticker_change"
        )
    if listing.state != expected_state:
        return _result(
            case_id,
            "contradicted",
            listing.state,
            "listing_state_contradicted",
        )

    economic_relation_present = any(
        row.axis == "economic_successor"
        and _exact_ticker(row.source_ticker, case_id)
        and row.complete
        for row in observations
    )
    reasons = ["expected_listing_state"]
    if economic_relation_present:
        reasons.append("economic_successor_not_identity_alias")
    return _result(case_id, "confirmed", listing.state, *reasons)


def classify_known_case(
    case_id: str,
    observations: Iterable[CensusObservation],
) -> CensusCaseResult:
    """Classify one frozen canary without inferring identity relationships."""

    if case_id not in _KNOWN_CASES:
        raise ValueError("known_case")
    rows = _deduplicate_observations(observations)
    if case_id == "LC":
        return _classify_lc(rows)
    if case_id in _TERMINAL_CASES:
        return _classify_listing_case(case_id, rows, expected_state="inactive")
    return _classify_listing_case(case_id, rows, expected_state="active")


def render_census_summary(results: Iterable[CensusCaseResult]) -> str:
    """Return canonical JSON for a deterministic, closed census summary."""

    materialized: list[CensusCaseResult] = []
    for result in results:
        if not isinstance(result, CensusCaseResult):
            raise TypeError("census_case_result")
        materialized.append(result)
    ordered = sorted(
        materialized,
        key=lambda result: (
            result.case_id,
            result.outcome,
            result.listing_state,
            result.successor or "",
            result.reasons,
        ),
    )
    counts = {outcome: 0 for outcome in sorted(CENSUS_OUTCOMES)}
    for result in ordered:
        counts[result.outcome] += 1
    payload = {
        "version": 1,
        "outcome_counts": counts,
        "results": [asdict(result) for result in ordered],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
