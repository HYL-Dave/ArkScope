"""Tests for the §2 result-card schema and the local card-runs store."""

from __future__ import annotations

import sqlite3

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


def test_translation_roundtrip(store):
    run = store.record(ticker="AAPL", result_card=_minimal_card().model_dump())
    assert store.get_translation(run.id, "zh-Hant") is None
    store.set_translation(run.id, "zh-Hant", {"conclusion": "看多"})
    assert store.get_translation(run.id, "zh-Hant") == {"conclusion": "看多"}
    # persisted on the run row
    assert store.get(run.id).translations["zh-Hant"]["conclusion"] == "看多"
    # unknown id is a no-op (no crash)
    store.set_translation(999999, "zh-Hant", {"x": 1})


# ─── Track A: personalization metadata on card runs ─────────────────────────

_OFF_TRACE = {
    "profile_active": False,
    "assistant_stance": "off",
    "skill_mode": "off",
    "suggested_skills": [],
    "applied_skills": [],
}


def test_card_run_personalization_defaults_off(tmp_path):
    from src.card_runs import CardRunStore

    store = CardRunStore(tmp_path / "cards.db")
    run = store.record(ticker="NVDA", result_card={"conclusion": "x"})
    expected = {**_OFF_TRACE, "context_snapshot": None}
    assert run.personalization == expected
    assert store.get(run.id).personalization == expected


def test_card_run_personalization_round_trip(tmp_path):
    from src.card_runs import CardRunStore

    store = CardRunStore(tmp_path / "cards.db")
    trace = {
        "profile_active": True,
        "assistant_stance": "strict_risk_control",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
    }
    run = store.record(ticker="NVDA", result_card={"conclusion": "x"}, personalization=trace)
    assert store.get(run.id).personalization == {**trace, "context_snapshot": None}
    assert store.record(ticker="AMD", result_card={}).personalization == {
        **_OFF_TRACE,
        "context_snapshot": None,
    }


def test_card_run_context_snapshot_distinguishes_legacy_null_from_new_disabled_empty(
    tmp_path,
):
    db = tmp_path / "legacy_cards.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE ai_card_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                question TEXT,
                horizon TEXT,
                card_type TEXT NOT NULL DEFAULT 'analysis',
                result_card_json TEXT NOT NULL,
                evidence_packet_json TEXT,
                provider TEXT,
                model TEXT,
                generated_at TEXT NOT NULL,
                as_of TEXT,
                status TEXT NOT NULL DEFAULT 'generated',
                saved_report_id INTEGER,
                expires_at TEXT,
                translations_json TEXT,
                profile_active INTEGER NOT NULL DEFAULT 0,
                assistant_stance TEXT NOT NULL DEFAULT 'off',
                skill_mode TEXT NOT NULL DEFAULT 'off',
                suggested_skills_json TEXT NOT NULL DEFAULT '[]',
                applied_skills_json TEXT NOT NULL DEFAULT '[]'
            );
            INSERT INTO ai_card_runs
                (id, ticker, result_card_json, generated_at)
            VALUES
                (7, 'LEGACY', '{}', '2026-07-01T00:00:00+00:00');
            """
        )

    store = CardRunStore(db)
    legacy = store.get(7)
    assert legacy is not None
    assert legacy.personalization == {**_OFF_TRACE, "context_snapshot": None}

    disabled_trace = {**_OFF_TRACE, "context_snapshot": ""}
    disabled = store.record(
        ticker="DISABLED",
        result_card={"conclusion": "off"},
        personalization=disabled_trace,
    )
    assert store.get(disabled.id).personalization == disabled_trace

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT id, personalization_context_snapshot FROM ai_card_runs ORDER BY id"
        ).fetchall()
    assert rows == [(7, None), (disabled.id, "")]


def test_card_run_context_snapshot_round_trips_exact_active_prompt_block(tmp_path):
    from dataclasses import replace

    from src.api.routes.analysis_cards import _summary, get_card
    from src.investor_profile import build_personalization_context, default_profile

    context = build_personalization_context(
        replace(
            default_profile(),
            enabled=True,
            risk_appetite=9,
            risk_capacity=3,
            risk_mismatch="appetite_above_capacity",
            default_stance="strict_risk_control",
        )
    )
    trace = {
        "profile_active": True,
        "assistant_stance": "strict_risk_control",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
        "context_snapshot": context,
    }
    store = CardRunStore(tmp_path / "active_cards.db")

    run = store.record(
        ticker="NVDA",
        result_card={"conclusion": "bounded"},
        personalization=trace,
    )

    persisted = store.get(run.id)
    assert persisted is not None
    assert persisted.personalization == trace
    assert _summary(persisted)["personalization"] == trace
    assert get_card(run.id, store=store)["personalization"] == trace
