"""Route-level tests for the §2 card endpoints.

Calls the route functions directly (the profile-tests pattern — TestClient hangs
against the lazy-startup app). gather/synthesize/save_report are stubbed so no LLM
or network runs; the CardRunStore is real (tmp SQLite) to exercise the lifecycle.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.routes import analysis_cards as routes
from src.api.routes.analysis_cards import (
    ArchiveBody,
    GenerateBody,
    TranslateBody,
    archive_card,
    delete_card,
    generate_card,
    get_card,
    list_cards,
    save_card,
    translate_card_route,
)
from src.card_runs import CardRunStore
from src.evidence_packet import EvidenceItem, EvidencePacket
from src.result_card import ResultCard, Traceability


def _card() -> ResultCard:
    return ResultCard(
        ticker="AAPL",
        analysis_time="2026-06-05T00:00:00Z",
        conclusion="constructive",
        counter_thesis=["soft demand"],
        confidence_level="medium",
        traceability=Traceability(),
    )


def _packet() -> EvidencePacket:
    return EvidencePacket(
        ticker="AAPL",
        generated_at="2026-06-05T00:00:00Z",
        items=[EvidenceItem(evidence_id="C", source="coverage", source_type="coverage",
                            data={"present": ["price"], "missing": []})],
    )


@pytest.fixture()
def store(tmp_path):
    return CardRunStore(tmp_path / "profile_state.db")


@pytest.fixture()
def stub_generation(monkeypatch):
    monkeypatch.setattr(routes, "gather_evidence",
                        lambda dal, ticker, **kw: _packet())
    monkeypatch.setattr(routes, "synthesize_card",
                        lambda packet, **kw: (_card(), {"provider": "anthropic", "model": "claude-opus-4-7"}))


def test_generate_clamps_and_forwards_news_window(store, monkeypatch):
    captured: dict = {}

    def capture_gather(dal, ticker, **kw):
        captured.update(kw)
        return _packet()

    monkeypatch.setattr(routes, "gather_evidence", capture_gather)
    monkeypatch.setattr(routes, "synthesize_card",
                        lambda packet, **kw: (_card(), {"provider": "anthropic", "model": "m"}))
    # out-of-range values get clamped (days→90, news→1); defaults pass nothing
    generate_card("AAPL", GenerateBody(include_sa=False, news_days=999, max_news=0), dal=object(), store=store)
    assert captured["news_days"] == 90 and captured["max_news"] == 1
    captured.clear()
    generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)
    assert "news_days" not in captured and "max_news" not in captured  # gather defaults apply


def test_translate_caches_and_returns(store, stub_generation, monkeypatch):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    calls = {"n": 0}

    def fake_translate(card, *, lang="zh-Hant", model=None):
        calls["n"] += 1
        return {**card, "conclusion": "繁中結論"}

    monkeypatch.setattr(routes, "translate_card", fake_translate)
    r1 = translate_card_route(rid, TranslateBody(lang="zh-Hant"), store=store)
    assert r1["card"]["conclusion"] == "繁中結論"
    assert r1["cached"] is False
    # second call hits the cache — no re-translation
    r2 = translate_card_route(rid, TranslateBody(lang="zh-Hant"), store=store)
    assert r2["cached"] is True
    assert calls["n"] == 1


def test_generate_caches_run(store, stub_generation):
    res = generate_card("aapl", GenerateBody(question="q?", include_sa=False), dal=object(), store=store)
    assert res["status"] == "generated"
    assert res["card"]["conclusion"] == "constructive"
    assert res["provider"] == "anthropic"
    # round-trips through the store
    det = get_card(res["run_id"], store=store)
    assert det["card"]["conclusion"] == "constructive"
    assert det["evidence_packet"]["ticker"] == "AAPL"


def test_list_hides_archived_by_default(store, stub_generation):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    assert any(c["run_id"] == rid for c in list_cards(store=store)["cards"])

    archive_card(rid, ArchiveBody(archived=True), store=store)
    assert not any(c["run_id"] == rid for c in list_cards(store=store)["cards"])
    assert any(c["run_id"] == rid for c in list_cards(include_archived=True, store=store)["cards"])

    # restore
    archive_card(rid, ArchiveBody(archived=False), store=store)
    assert any(c["run_id"] == rid for c in list_cards(store=store)["cards"])


def test_save_promotes_to_report(store, stub_generation, monkeypatch):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    monkeypatch.setattr(routes, "save_report",
                        lambda dal, **kw: {"id": 7, "file_path": "data/reports/x.md", "title": kw["title"]})
    res = save_card(rid, dal=object(), store=store)
    assert res["status"] == "saved"
    assert res["saved_report_id"] == 7
    # status persisted
    assert get_card(rid, store=store)["status"] == "saved"


def test_save_is_idempotent_after_report_promotion(store, stub_generation, monkeypatch):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    calls = {"n": 0}

    def fake_save_report(dal, **kw):
        calls["n"] += 1
        return {"id": 7, "file_path": "data/reports/x.md", "title": kw["title"]}

    monkeypatch.setattr(routes, "save_report", fake_save_report)
    first = save_card(rid, dal=object(), store=store)
    second = save_card(rid, dal=object(), store=store)

    assert first["status"] == "saved"
    assert second["status"] == "saved"
    assert second["saved_report_id"] == 7
    assert second["already_saved"] is True
    assert calls["n"] == 1


def test_restore_keeps_saved_card_saved(store, stub_generation, monkeypatch):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    monkeypatch.setattr(routes, "save_report", lambda dal, **kw: {"id": 9, "title": kw["title"]})
    save_card(rid, dal=object(), store=store)
    # archive then restore must NOT demote a promoted card back to 'generated'
    archive_card(rid, ArchiveBody(archived=True), store=store)
    res = archive_card(rid, ArchiveBody(archived=False), store=store)
    assert res["status"] == "saved"
    assert get_card(rid, store=store)["saved_report_id"] == 9


def test_delete_then_404(store, stub_generation):
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    assert delete_card(rid, store=store)["deleted"] is True
    with pytest.raises(HTTPException) as ei:
        get_card(rid, store=store)
    assert ei.value.status_code == 404


def test_unknown_run_is_404(store):
    with pytest.raises(HTTPException) as ei:
        get_card(99999, store=store)
    assert ei.value.status_code == 404


def test_bad_provider_is_400(store, stub_generation):
    with pytest.raises(HTTPException) as ei:
        generate_card("AAPL", GenerateBody(provider="grok", include_sa=False), dal=object(), store=store)
    assert ei.value.status_code == 400
