from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import json
from pathlib import Path

import pytest

from src.security_lifecycle_provider_census import (
    CENSUS_OUTCOMES,
    CensusCaseResult,
    CensusObservation,
    classify_known_case,
    render_census_summary,
)


_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "lifecycle_provider_census"
    / "known_cases.json"
)
_OUTCOMES = (
    "confirmed",
    "contradicted",
    "coverage_limited",
    "not_entitled",
    "credential_unavailable",
    "provider_unavailable",
    "ambiguous",
)
_STABLE_IDS = {
    "LC": "FIGI-LC",
    "HAPN": "FIGI-LC",
    "ARCH": "FIGI-ARCH",
    "CNR": "FIGI-CNR",
    "LTHM": "FIGI-LTHM",
    "ALTM": "FIGI-ALTM",
    "TA": "FIGI-TA",
    "AAPL": "FIGI-AAPL",
    "SMCI": "FIGI-SMCI",
    "SMCI*": "FIGI-SMCI",
}
_DEFAULT = object()


def observation(
    provider: str,
    axis: str,
    source: str,
    *,
    successor: str | None = None,
    active: bool | None = None,
    stable_id: str | None | object = _DEFAULT,
    effective_date: str | None = None,
    complete: bool = True,
) -> CensusObservation:
    resolved_stable_id = _STABLE_IDS.get(source) if stable_id is _DEFAULT else stable_id
    assert resolved_stable_id is None or isinstance(resolved_stable_id, str)
    return CensusObservation(
        provider=provider,
        axis=axis,
        source_ticker=source,
        successor_ticker=successor,
        active=active,
        stable_id=resolved_stable_id,
        effective_date=effective_date,
        complete=complete,
    )


def test_known_case_fixture_is_frozen_before_provider_adapters():
    assert json.loads(_FIXTURE.read_text(encoding="utf-8")) == {
        "version": 1,
        "cases": [
            {"case_id": "LC", "source": "LC", "successor": "HAPN", "terminal": False},
            {"case_id": "ARCH", "source": "ARCH", "successor": None, "terminal": True},
            {"case_id": "LTHM", "source": "LTHM", "successor": None, "terminal": True},
            {"case_id": "TA", "source": "TA", "successor": None, "terminal": True},
            {"case_id": "AAPL", "source": "AAPL", "successor": None, "terminal": False},
            {"case_id": "SMCI", "source": "SMCI", "successor": None, "terminal": False},
        ],
    }


def test_census_observation_has_only_normalized_transport_fields():
    assert tuple(field.name for field in fields(CensusObservation)) == (
        "provider",
        "axis",
        "source_ticker",
        "successor_ticker",
        "active",
        "stable_id",
        "effective_date",
        "complete",
    )
    with pytest.raises(TypeError, match="issuer_name"):
        CensusObservation(
            provider="massive",
            axis="listing_state",
            source_ticker="AAPL",
            successor_ticker=None,
            active=True,
            stable_id="FIGI-AAPL",
            effective_date=None,
            complete=True,
            issuer_name="Apple Inc.",  # type: ignore[call-arg]
        )


def test_census_observation_is_frozen():
    row = observation("massive", "listing_state", "AAPL", active=True)
    with pytest.raises(FrozenInstanceError):
        row.active = False  # type: ignore[misc]


@pytest.mark.parametrize("axis", ("listing", "rename", "merger", ""))
def test_census_observation_rejects_unknown_axes(axis: str):
    with pytest.raises(ValueError, match="census_axis"):
        observation("massive", axis, "AAPL", active=True)


@pytest.mark.parametrize(
    "ticker",
    ("aapl", " AAPL", "AAPL ", "AAPL/US", "AAPL**", ""),
)
def test_census_observation_rejects_lowercase_or_noncanonical_tickers(ticker: str):
    with pytest.raises(ValueError, match="source_ticker"):
        observation("massive", "listing_state", ticker, active=True)


def test_census_observation_preserves_provider_marker_punctuation():
    row = observation("massive", "listing_state", "SMCI*", active=True)
    assert row.source_ticker == "SMCI*"


def test_successor_requires_an_explicit_relation_axis():
    with pytest.raises(ValueError, match="successor_relation"):
        observation(
            "massive",
            "listing_state",
            "LC",
            successor="HAPN",
            active=False,
        )


@pytest.mark.parametrize("axis", ("ticker_change", "economic_successor"))
def test_complete_relation_requires_an_exact_successor(axis: str):
    with pytest.raises(ValueError, match="successor_relation"):
        observation("massive", axis, "LC")


def test_complete_listing_state_requires_a_boolean():
    with pytest.raises(ValueError, match="listing_state_active"):
        observation("massive", "listing_state", "AAPL", active=None)
    with pytest.raises(ValueError, match="listing_state_active"):
        observation("massive", "listing_state", "AAPL", active=1)  # type: ignore[arg-type]


def test_incomplete_observation_can_omit_the_unresolved_value():
    row = observation(
        "massive",
        "listing_state",
        "AAPL",
        active=None,
        stable_id=None,
        complete=False,
    )
    assert row.active is None
    assert row.complete is False


def test_census_case_result_has_only_closed_fields():
    assert tuple(field.name for field in fields(CensusCaseResult)) == (
        "case_id",
        "outcome",
        "listing_state",
        "successor",
        "reasons",
    )
    with pytest.raises(TypeError, match="raw_payload"):
        CensusCaseResult(
            case_id="AAPL",
            outcome="confirmed",
            listing_state="active",
            successor=None,
            reasons=("expected_listing_state",),
            raw_payload={},  # type: ignore[call-arg]
        )


@pytest.mark.parametrize("outcome", _OUTCOMES)
def test_census_case_result_accepts_every_closed_outcome(outcome: str):
    result = CensusCaseResult(
        case_id="AAPL",
        outcome=outcome,
        listing_state="unresolved",
        successor=None,
        reasons=("fixture_result",),
    )
    assert result.outcome == outcome


def test_census_case_result_rejects_values_outside_closed_vocabularies():
    assert CENSUS_OUTCOMES == frozenset(_OUTCOMES)
    with pytest.raises(ValueError, match="census_outcome"):
        CensusCaseResult("AAPL", "not_found", "unresolved", None, ())
    with pytest.raises(ValueError, match="census_listing_state"):
        CensusCaseResult("AAPL", "ambiguous", "delisted", None, ())


def test_nonconfirmed_result_cannot_publish_a_successor():
    with pytest.raises(ValueError, match="successor_authority"):
        CensusCaseResult(
            "LC",
            "ambiguous",
            "inactive",
            "HAPN",
            ("relation_missing",),
        )


def test_lc_requires_exact_same_security_change_to_hapn():
    rows = (
        observation("massive", "listing_state", "LC", active=False),
        observation("massive", "ticker_change", "LC", successor="HAPN"),
        observation("massive", "listing_state", "HAPN", active=True),
    )
    confirmed = classify_known_case("LC", rows)
    assert confirmed.outcome == "confirmed"
    assert confirmed.listing_state == "inactive"
    assert confirmed.successor == "HAPN"

    without_relation = (rows[0], rows[2])
    unresolved = classify_known_case("LC", without_relation)
    assert unresolved.outcome == "ambiguous"
    assert unresolved.successor is None


def test_lc_requires_stable_identity_agreement():
    rows = (
        observation("massive", "listing_state", "LC", active=False),
        observation("massive", "ticker_change", "LC", successor="HAPN"),
        observation(
            "massive",
            "listing_state",
            "HAPN",
            active=True,
            stable_id="FIGI-DIFFERENT",
        ),
    )
    result = classify_known_case("LC", rows)
    assert result.outcome == "ambiguous"
    assert result.successor is None


def test_same_security_ticker_change_is_not_a_merger_conversion():
    listing_rows = (
        observation("massive", "listing_state", "LC", active=False),
        observation("massive", "listing_state", "HAPN", active=True),
    )
    rename = classify_known_case(
        "LC",
        listing_rows
        + (observation("massive", "ticker_change", "LC", successor="HAPN"),),
    )
    conversion = classify_known_case(
        "LC",
        listing_rows
        + (
            observation(
                "massive",
                "economic_successor",
                "LC",
                successor="HAPN",
            ),
        ),
    )
    assert (rename.outcome, rename.successor) == ("confirmed", "HAPN")
    assert (conversion.outcome, conversion.successor) == ("contradicted", None)


def test_independently_confirmed_terminal_acquisition_never_becomes_identity_alias():
    rows = (
        observation("massive", "listing_state", "ARCH", active=False),
        observation("massive", "economic_successor", "ARCH", successor="CNR"),
        observation("massive", "listing_state", "CNR", active=True),
    )
    result = classify_known_case("ARCH", rows)
    assert result.outcome == "confirmed"
    assert result.listing_state == "inactive"
    assert result.successor is None


def test_acquisition_relation_without_terminal_state_is_not_terminal_authority():
    rows = (
        observation("massive", "economic_successor", "ARCH", successor="CNR"),
        observation("massive", "listing_state", "CNR", active=True),
    )
    result = classify_known_case("ARCH", rows)
    assert result.outcome == "ambiguous"
    assert result.successor is None


def test_lthm_requires_terminal_state_without_an_altm_alias():
    rows = (
        observation("massive", "listing_state", "LTHM", active=False),
        observation("massive", "economic_successor", "LTHM", successor="ALTM"),
        observation("massive", "listing_state", "ALTM", active=True),
    )
    result = classify_known_case("LTHM", rows)
    assert result.outcome == "confirmed"
    assert result.successor is None


def test_ta_requires_terminal_state_without_a_successor():
    rows = (observation("massive", "listing_state", "TA", active=False),)
    result = classify_known_case("TA", rows)
    assert result.outcome == "confirmed"
    assert result.successor is None


@pytest.mark.parametrize("case_id", ("AAPL", "SMCI"))
def test_active_controls_require_exact_active_listing_state(case_id: str):
    rows = (observation("massive", "listing_state", case_id, active=True),)
    result = classify_known_case(case_id, rows)
    assert result.outcome == "confirmed"
    assert result.listing_state == "active"
    assert result.successor is None


def test_active_control_rejects_an_unexpected_ticker_change():
    rows = (
        observation("massive", "listing_state", "AAPL", active=True),
        observation("massive", "ticker_change", "AAPL", successor="MSFT"),
    )
    result = classify_known_case("AAPL", rows)
    assert result.outcome == "contradicted"
    assert result.successor is None


def test_smci_provider_marker_cannot_match_exact_control():
    rows = (observation("massive", "listing_state", "SMCI*", active=True),)
    assert classify_known_case("SMCI", rows).outcome == "ambiguous"


def test_complete_incompatible_listing_state_is_contradicted():
    result = classify_known_case(
        "AAPL",
        (observation("massive", "listing_state", "AAPL", active=False),),
    )
    assert result.outcome == "contradicted"
    assert result.listing_state == "inactive"


def test_provider_disagreement_is_ambiguous():
    rows = (
        observation("massive", "listing_state", "AAPL", active=True),
        observation(
            "eodhd",
            "listing_state",
            "AAPL",
            active=False,
            stable_id=None,
        ),
    )
    result = classify_known_case("AAPL", rows)
    assert result.outcome == "ambiguous"
    assert result.listing_state == "conflicting"


def test_incomplete_exact_response_is_ambiguous():
    rows = (
        observation(
            "massive",
            "listing_state",
            "AAPL",
            active=None,
            stable_id=None,
            complete=False,
        ),
    )
    assert classify_known_case("AAPL", rows).outcome == "ambiguous"


def test_missing_stable_identity_is_ambiguous():
    rows = (
        observation(
            "massive",
            "listing_state",
            "AAPL",
            active=True,
            stable_id=None,
        ),
    )
    assert classify_known_case("AAPL", rows).outcome == "ambiguous"


def test_duplicate_contradictory_provider_rows_are_rejected():
    rows = (
        observation("massive", "listing_state", "AAPL", active=True),
        observation("massive", "listing_state", "AAPL", active=False),
    )
    with pytest.raises(ValueError, match="contradictory_observations"):
        classify_known_case("AAPL", rows)


def test_unknown_known_case_is_rejected():
    with pytest.raises(ValueError, match="known_case"):
        classify_known_case("MSFT", ())


def test_render_census_summary_is_closed_and_input_order_independent():
    results = tuple(
        CensusCaseResult(
            case_id=f"CASE{index}",
            outcome=outcome,
            listing_state="unresolved",
            successor=None,
            reasons=("fixture_result",),
        )
        for index, outcome in enumerate(_OUTCOMES)
    )
    forward = render_census_summary(results)
    reverse = render_census_summary(reversed(results))

    assert forward == reverse
    assert forward.endswith("\n")
    assert json.loads(forward) == {
        "version": 1,
        "outcome_counts": {
            "ambiguous": 1,
            "confirmed": 1,
            "contradicted": 1,
            "coverage_limited": 1,
            "credential_unavailable": 1,
            "not_entitled": 1,
            "provider_unavailable": 1,
        },
        "results": [
            {
                "case_id": f"CASE{index}",
                "listing_state": "unresolved",
                "outcome": outcome,
                "reasons": ["fixture_result"],
                "successor": None,
            }
            for index, outcome in enumerate(_OUTCOMES)
        ],
    }
