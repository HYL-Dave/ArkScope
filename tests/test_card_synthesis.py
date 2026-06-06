"""Tests for card synthesis: packet → validated ResultCard merge + rendering.

The live provider call is mocked — these lock the merge contract (metadata
stamped from the packet, per-claim citations carried into traceability,
single-model flag) and the markdown promotion path.
"""

from __future__ import annotations

import pytest

from src.card_synthesis import (
    CardSynthesis,
    _SynthClaim,
    render_card_markdown,
    synthesize_card,
)
from src.evidence_packet import EvidenceItem, EvidencePacket
from src.result_card import ResultCard, Traceability


def _packet() -> EvidencePacket:
    return EvidencePacket(
        ticker="AAPL",
        generated_at="2026-06-05T00:00:00Z",
        question="thesis into the print?",
        items=[
            EvidenceItem(evidence_id="E1", source="price_summary", source_type="observed_market",
                         as_of="2026-06-04", data={"latest_close": 124.0}),
            EvidenceItem(evidence_id="E2", source="technical_metrics", source_type="deterministic_metric",
                         data={"return_20d_pct": 19.2}),
            EvidenceItem(evidence_id="E3", source="news_rows", source_type="observed_news",
                         data={"count": 2}),
            EvidenceItem(evidence_id="C", source="coverage", source_type="coverage",
                         data={"present": ["price", "technicals", "news"], "missing": ["iv", "fundamentals"]}),
        ],
    )


def _synth() -> CardSynthesis:
    return CardSynthesis(
        conclusion="Constructive but data is thin.",
        primary_reasons=["20d momentum positive"],
        counter_thesis=["No fundamentals in packet — low conviction"],
        risks=["IV unavailable"],
        confidence_level="low",
        confidence_rationale="fundamentals + iv missing",
        claims=[
            _SynthClaim(claim="20d momentum positive", evidence_ids=["E2"]),
            _SynthClaim(claim="thin data", evidence_ids=["C"]),
        ],
    )


def test_synthesize_merges_metadata_and_citations(monkeypatch):
    monkeypatch.setattr(
        "src.card_synthesis._synthesize_anthropic",
        lambda packet, model, effort="default": (_synth(), {"effort": effort}),
    )
    card, meta = synthesize_card(
        _packet(), now_iso="2026-06-05T00:00:00Z", provider="anthropic",
        question="thesis into the print?", horizon="swing",
    )
    assert isinstance(card, ResultCard)
    assert card.ticker == "AAPL"
    assert card.horizon == "swing"
    assert card.analysis_time == "2026-06-05T00:00:00Z"
    assert card.card_type == "analysis"
    assert card.confidence_level == "low"
    # traceability: one DataSourceRef per non-coverage evidence item
    assert len(card.traceability.data_sources) == 3
    assert {d.name for d in card.traceability.data_sources} == {
        "price_summary", "technical_metrics", "news_rows"
    }
    assert card.traceability.is_single_model_inference is True
    # per-claim citations carried through
    assert len(card.traceability.claims) == 2
    assert card.traceability.claims[0].evidence_ids == ["E2"]
    # completeness derived from source types present
    assert card.traceability.completeness.news is True
    assert card.traceability.completeness.technicals is True
    assert card.traceability.completeness.fundamentals is False
    assert "iv" in (card.traceability.completeness.note or "")
    assert meta == {"provider": "anthropic", "model": meta["model"], "effort": "default"}


def test_synthesize_rejects_unknown_provider():
    with pytest.raises(ValueError):
        synthesize_card(_packet(), now_iso="t", provider="grok")  # type: ignore[arg-type]


def test_translation_validation_rejects_list_count_change():
    from src.card_synthesis import _validate_translation

    card = ResultCard(
        ticker="AAPL", analysis_time="t", conclusion="c",
        primary_reasons=["a", "b"], counter_thesis=["x"],
        confidence_level="low", traceability=Traceability(),
    ).model_dump()
    # same structure → ok
    _validate_translation(card, {**card, "conclusion": "結論", "primary_reasons": ["甲", "乙"]})
    # dropped a list item → reject (would silently lose a reason)
    with pytest.raises(ValueError):
        _validate_translation(card, {**card, "primary_reasons": ["只剩一條"]})


def test_task_model_routing(monkeypatch):
    from src.agents.config import get_agent_config, task_model, task_route

    get_agent_config.cache_clear()
    # translation defaults to the fast model (not the Opus synthesis model)
    assert task_model("card_translation") == "claude-sonnet-4-6"
    # env override wins for either task
    monkeypatch.setenv("ARKSCOPE_CARD_TRANSLATION_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", "test-model-x")
    assert task_model("card_translation") == "claude-haiku-4-5"
    assert task_model("card_synthesis") == "test-model-x"
    # provider can be set independently; model-only OpenAI ids infer provider.
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_MODEL")
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", "gpt-5.4-mini")
    assert task_route("card_synthesis").provider == "openai"
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_PROVIDER", "anthropic")
    assert task_route("card_synthesis").provider == "anthropic"


def test_render_card_markdown_has_core_sections(monkeypatch):
    monkeypatch.setattr(
        "src.card_synthesis._synthesize_anthropic",
        lambda packet, model, effort="default": (_synth(), {"effort": effort}),
    )
    card, _ = synthesize_card(_packet(), now_iso="2026-06-05T00:00:00Z", provider="anthropic")
    md = render_card_markdown(card)
    assert "## Conclusion" in md
    assert "Counter-thesis" in md
    assert "## Confidence" in md
    assert "LOW" in md
    assert "## Data sources" in md
