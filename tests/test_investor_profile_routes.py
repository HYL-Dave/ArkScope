"""Track A: /profile/investor routes — handler-direct, no TestClient."""

import pytest
from fastapi import HTTPException

from src.investor_profile import InvestorProfileStore
from src.api.routes import investor_profile as routes


@pytest.fixture
def store(tmp_path):
    return InvestorProfileStore(tmp_path / "profile_state.db")


def test_get_default_profile_disabled(store):
    data = routes.get_investor_profile(store=store)
    assert data["profile"]["enabled"] is False
    assert data["profile"]["primary_preset"] == "growth"
    assert data["effective_stance"] == "off"
    assert data["trace"] == {
        "profile_active": False,
        "assistant_stance": "off",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
    }
    assert data["context_preview"] == ""


def test_draft_derives_mismatch_without_write_gate(store, monkeypatch):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: calls.append(a))
    body = routes.InvestorProfileBody(enabled=True, risk_appetite=9, risk_capacity=3)
    data = routes.draft_investor_profile(body, store=store)
    assert data["profile"]["risk_mismatch"] == "appetite_above_capacity"
    assert calls == []  # draft is read-only: gate NOT called
    assert store.get().enabled is False  # nothing persisted


def test_put_profile_calls_profile_state_write_and_round_trips(store, monkeypatch):
    calls = []
    monkeypatch.setattr(
        routes, "require_profile_state_write", lambda action, detail=None: calls.append(action)
    )
    body = routes.InvestorProfileBody(
        enabled=True,
        primary_preset="growth",
        risk_appetite=8,
        risk_capacity=4,
        behavioral_flags=["FOMO"],
        default_stance="complementary",
    )
    data = routes.put_investor_profile(body, store=store)
    assert calls == ["investor_profile_update"]
    assert data["profile"]["enabled"] is True
    assert data["profile"]["risk_mismatch"] == "appetite_above_capacity"
    assert data["effective_stance"] == "complementary"
    assert data["trace"]["profile_active"] is True
    assert "[Assistant Stance]" in data["context_preview"]
    assert store.get().enabled is True  # persisted


def test_put_rejects_invalid_values(store, monkeypatch):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    with pytest.raises(HTTPException) as exc:
        routes.put_investor_profile(
            routes.InvestorProfileBody(enabled=True, default_stance="yolo"), store=store
        )
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_investor_profile"
    with pytest.raises(HTTPException) as exc:
        routes.put_investor_profile(
            routes.InvestorProfileBody(enabled=True, skill_mode="auto_with_trace"), store=store
        )
    assert exc.value.status_code == 400
    assert store.get().enabled is False  # nothing persisted on rejection


def test_disabled_profile_response_context_preview_empty(store, monkeypatch):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    routes.put_investor_profile(
        routes.InvestorProfileBody(enabled=False, default_stance="strict_risk_control"),
        store=store,
    )
    data = routes.get_investor_profile(store=store)
    assert data["profile"]["default_stance"] == "strict_risk_control"  # saved but inert
    assert data["effective_stance"] == "off"
    assert data["context_preview"] == ""
    assert data["trace"]["profile_active"] is False


def test_put_explicit_null_clears_field_but_omitted_keeps(store, monkeypatch):
    monkeypatch.setattr(routes, "require_profile_state_write", lambda *a, **k: None)
    routes.put_investor_profile(
        routes.InvestorProfileBody(enabled=True, risk_appetite=8, risk_capacity=4),
        store=store,
    )
    assert store.get().risk_appetite == 8

    # explicit null = clear (the UI sends null when the user resets a field)
    body = routes.InvestorProfileBody.model_validate(
        {"risk_appetite": None, "drawdown_tolerance_pct": None}
    )
    data = routes.put_investor_profile(body, store=store)
    assert data["profile"]["risk_appetite"] is None
    assert data["profile"]["drawdown_tolerance_pct"] is None
    assert store.get().risk_appetite is None
    # omitted fields stay unchanged
    assert store.get().risk_capacity == 4
    assert store.get().enabled is True
