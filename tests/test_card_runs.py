"""Tests for the §2 result-card schema and the local card-runs store."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.card_runs import CardRunStore
from src.result_card import ResultCard, Traceability


def _minimal_card(ticker: str = "AAPL") -> ResultCard:
    return ResultCard(
        ticker=ticker,
        analysis_time="2026-06-05T00:00:00Z",
        conclusion="Constructive into the print.",
        primary_reasons=["services margin", "buyback"],
        counter_thesis=["China demand soft"],
        confidence_level="medium",
        traceability=Traceability(),
    )


# --- schema -------------------------------------------------------------


def test_result_card_requires_core_fields():
    with pytest.raises(ValidationError):
        ResultCard(ticker="AAPL")  # missing conclusion/confidence/analysis_time/traceability


def test_result_card_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        ResultCard(
            ticker="AAPL",
            analysis_time="t",
            conclusion="c",
            confidence_level="sky-high",  # not in enum
            traceability=Traceability(),
        )


def test_result_card_defaults_and_reserved_fields():
    card = _minimal_card()
    assert card.card_type == "analysis"
    assert card.key_levels is None  # reserved trading extension
    assert card.changes_vs_last is None  # reserved versioning
    assert card.traceability.is_single_model_inference is True
    assert card.risks == []  # list defaults are independent
    other = _minimal_card("MSFT")
    card.risks.append("x")
    assert other.risks == []


# --- store --------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    return CardRunStore(tmp_path / "profile_state.db")


def test_record_and_get_roundtrip(store):
    card = _minimal_card()
    run = store.record(
        ticker="aapl",
        result_card=card.model_dump(),
        evidence_packet={"fundamentals": {"as_of": "2026-06-01"}},
        question="thesis?",
        horizon="swing",
        provider="anthropic",
        model="claude-opus-4-6",
        as_of="2026-06-05",
    )
    assert run.ticker == "AAPL"  # normalized
    assert run.status == "generated"
    fetched = store.get(run.id)
    assert fetched is not None
    assert fetched.result_card["conclusion"] == card.conclusion
    assert fetched.evidence_packet["fundamentals"]["as_of"] == "2026-06-01"


def test_status_lifecycle_and_recent_filter(store):
    a = store.record(ticker="AAPL", result_card=_minimal_card().model_dump())
    b = store.record(ticker="AAPL", result_card=_minimal_card().model_dump())

    # default recent() shows generated + saved
    assert {r.id for r in store.recent(ticker="AAPL")} == {a.id, b.id}

    # archive one -> drops out of default recent()
    assert store.set_status(a.id, "archived").status == "archived"
    assert {r.id for r in store.recent(ticker="AAPL")} == {b.id}
    # but visible when asked for
    assert {r.id for r in store.recent(ticker="AAPL", statuses=("archived",))} == {a.id}

    # promote b to saved
    saved = store.mark_saved(b.id, saved_report_id=42)
    assert saved.status == "saved" and saved.saved_report_id == 42

    assert store.set_status(999, "deleted") is None  # unknown id


def test_set_status_validates(store):
    run = store.record(ticker="AAPL", result_card=_minimal_card().model_dump())
    with pytest.raises(ValueError):
        store.set_status(run.id, "bogus")


def test_archive_generated_before(store):
    old = store.record(
        ticker="AAPL", result_card=_minimal_card().model_dump(), generated_at="2026-01-01T00:00:00Z"
    )
    new = store.record(
        ticker="AAPL", result_card=_minimal_card().model_dump(), generated_at="2026-06-05T00:00:00Z"
    )
    n = store.archive_generated_before("2026-03-01T00:00:00Z")
    assert n == 1
    assert store.get(old.id).status == "archived"
    assert store.get(new.id).status == "generated"
