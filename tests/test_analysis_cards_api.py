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
from src.fixed_task_runtime_config import FixedTaskRuntimeSettings
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


@pytest.fixture(autouse=True)
def fixed_task_runtime(monkeypatch):
    monkeypatch.setattr(
        routes,
        "resolve_fixed_task_runtime",
        lambda task: FixedTaskRuntimeSettings(
            task=task,
            model_timeout_s=900.0,
            source="default",
        ),
        raising=False,
    )


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

    def fake_translate(card, *, lang="zh-Hant", model=None, model_timeout_s):
        calls["n"] += 1
        assert model_timeout_s == 900.0
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


def test_generate_resolves_synthesis_timeout_before_gather_and_forwards_it(
    store, monkeypatch
):
    events = []
    captured = {}

    def resolve(task):
        events.append(("resolve", task))
        return FixedTaskRuntimeSettings(task=task, model_timeout_s=1234, source="db")

    def gather(dal, ticker, **kwargs):
        events.append(("gather", ticker))
        return _packet()

    def synthesize(packet, **kwargs):
        captured.update(kwargs)
        return _card(), {"provider": "anthropic", "model": "m"}

    monkeypatch.setattr(routes, "resolve_fixed_task_runtime", resolve)
    monkeypatch.setattr(routes, "gather_evidence", gather)
    monkeypatch.setattr(routes, "synthesize_card", synthesize)

    generate_card(
        "AAPL", GenerateBody(include_sa=False), dal=object(), store=store
    )

    assert events[:2] == [("resolve", "card_synthesis"), ("gather", "AAPL")]
    assert captured["model_timeout_s"] == 1234.0


def test_translate_resolves_translation_timeout_and_forwards_it(
    store, stub_generation, monkeypatch
):
    rid = generate_card(
        "AAPL", GenerateBody(include_sa=False), dal=object(), store=store
    )["run_id"]
    captured = {}
    monkeypatch.setattr(
        routes,
        "resolve_fixed_task_runtime",
        lambda task: FixedTaskRuntimeSettings(
            task=task, model_timeout_s=432, source="db"
        ),
    )

    def translate(card, **kwargs):
        captured.update(kwargs)
        return {**card, "conclusion": "繁中結論"}

    monkeypatch.setattr(routes, "translate_card", translate)

    translate_card_route(rid, TranslateBody(lang="zh-Hant"), store=store)

    assert captured["lang"] == "zh-Hant"
    assert captured["model_timeout_s"] == 432.0


def test_generate_timeout_returns_structured_502_and_stores_no_run(
    store, monkeypatch
):
    from src import card_synthesis as cs

    writes = []
    monkeypatch.setattr(routes, "gather_evidence", lambda *args, **kwargs: _packet())
    monkeypatch.setattr(
        routes,
        "require_db_write",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    def timeout(packet, **kwargs):
        raise cs.ModelExecutionTimeout(
            provider="anthropic",
            model="claude-sonnet-5",
            effort="max",
            effective_seconds=900,
        )

    monkeypatch.setattr(routes, "synthesize_card", timeout)

    with pytest.raises(HTTPException) as exc:
        generate_card(
            "AAPL", GenerateBody(include_sa=False), dal=object(), store=store
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == {
        "code": "model_timeout",
        "task": "card_synthesis",
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "effort": "max",
        "effective_seconds": 900.0,
    }
    assert writes == []
    assert store.recent() == []


def test_translate_timeout_returns_structured_502_and_stores_no_translation(
    store, stub_generation, monkeypatch
):
    from src import card_synthesis as cs

    rid = generate_card(
        "AAPL", GenerateBody(include_sa=False), dal=object(), store=store
    )["run_id"]

    def timeout(card, **kwargs):
        raise cs.ModelExecutionTimeout(
            provider="openai",
            model="gpt-5.4-mini",
            effort="high",
            effective_seconds=600,
        )

    monkeypatch.setattr(routes, "translate_card", timeout)

    with pytest.raises(HTTPException) as exc:
        translate_card_route(rid, TranslateBody(lang="zh-Hant"), store=store)

    assert exc.value.status_code == 502
    assert exc.value.detail == {
        "code": "model_timeout",
        "task": "card_translation",
        "provider": "openai",
        "model": "gpt-5.4-mini",
        "effort": "high",
        "effective_seconds": 600.0,
    }
    assert store.get(rid).translations is None


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


# ─── Track A: investor profile personalization on card generation ───────────


def _profile(tmp_path, monkeypatch, *, enabled):
    from src.investor_profile import InvestorProfileStore

    pstore = InvestorProfileStore(tmp_path / "investor_profile.db")
    if enabled:
        pstore.save({"enabled": True, "risk_appetite": 8, "risk_capacity": 4,
                     "default_stance": "complementary"})
    monkeypatch.setattr("src.api.dependencies.get_investor_profile_store", lambda: pstore)
    return pstore


def test_generate_card_profile_off_does_not_change_gather_or_synthesis_context(
    store, tmp_path, monkeypatch
):
    _profile(tmp_path, monkeypatch, enabled=False)
    gather_kw, synth_kw = {}, {}

    def capture_gather(dal, ticker, **kw):
        gather_kw.update(kw)
        return _packet()

    def capture_synth(packet, **kw):
        synth_kw.update(kw)
        return _card(), {"provider": "anthropic", "model": "m"}

    monkeypatch.setattr(routes, "gather_evidence", capture_gather)
    monkeypatch.setattr(routes, "synthesize_card", capture_synth)
    resp = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)
    assert "personalization_context" not in synth_kw  # off → kwarg omitted
    assert "personalization_context" not in gather_kw
    assert resp["personalization"]["profile_active"] is False
    assert store.get(resp["run_id"]).personalization["profile_active"] is False


def test_generate_card_enabled_profile_passes_synthesis_context_only(
    store, tmp_path, monkeypatch
):
    _profile(tmp_path, monkeypatch, enabled=True)
    gather_kw, synth_kw = {}, {}

    def capture_gather(dal, ticker, **kw):
        gather_kw.update(kw)
        return _packet()

    def capture_synth(packet, **kw):
        synth_kw.update(kw)
        return _card(), {"provider": "anthropic", "model": "m"}

    monkeypatch.setattr(routes, "gather_evidence", capture_gather)
    monkeypatch.setattr(routes, "synthesize_card", capture_synth)
    resp = generate_card(
        "AAPL",
        GenerateBody(include_sa=False, assistant_stance="strict_risk_control"),
        dal=object(),
        store=store,
    )
    ctx = synth_kw["personalization_context"]
    assert "[Assistant Stance]" in ctx and "strict_risk_control" in ctx
    # evidence boundary: gather_evidence never sees profile/stance values
    assert "personalization_context" not in gather_kw
    assert "assistant_stance" not in gather_kw
    assert resp["personalization"]["assistant_stance"] == "strict_risk_control"
    assert resp["personalization"]["profile_active"] is True
    assert store.get(resp["run_id"]).personalization == resp["personalization"]


def test_get_card_returns_personalization_metadata(store, tmp_path, monkeypatch):
    _profile(tmp_path, monkeypatch, enabled=True)
    monkeypatch.setattr(routes, "gather_evidence", lambda dal, ticker, **kw: _packet())
    monkeypatch.setattr(
        routes, "synthesize_card",
        lambda packet, **kw: (_card(), {"provider": "anthropic", "model": "m"}),
    )
    rid = generate_card("AAPL", GenerateBody(include_sa=False), dal=object(), store=store)["run_id"]
    detail = routes.get_card(rid, store=store)
    assert detail["personalization"]["assistant_stance"] == "complementary"
    summaries = routes.list_cards(store=store)
    assert summaries["cards"][0]["personalization"]["assistant_stance"] == "complementary"


def test_generate_card_invalid_assistant_stance_returns_400(store, tmp_path, monkeypatch):
    _profile(tmp_path, monkeypatch, enabled=True)
    called = {"gather": False}
    monkeypatch.setattr(
        routes, "gather_evidence",
        lambda *a, **k: called.__setitem__("gather", True) or _packet(),
    )
    with pytest.raises(HTTPException) as exc:
        generate_card(
            "AAPL",
            GenerateBody(include_sa=False, assistant_stance="yolo"),
            dal=object(),
            store=store,
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": "invalid_assistant_stance", "field": "assistant_stance"}
    assert called["gather"] is False  # validation precedes evidence gathering
