"""Track A: InvestorProfileStore + stance/context/trace pure functions."""

from dataclasses import replace

import pytest

from src.investor_profile import (
    InvestorProfile,
    InvestorProfileStore,
    RISK_MISMATCHES,
    SKILL_MODES,
    STANCES,
    build_personalization_context,
    default_profile,
    derive_risk_mismatch,
    effective_stance,
    normalize_profile_payload,
    personalization_trace,
)


def test_default_profile_is_disabled_and_context_empty():
    p = default_profile()
    assert p.enabled is False
    assert p.primary_preset == "growth"
    assert p.skill_mode == "off"
    assert effective_stance(p) == "off"
    assert build_personalization_context(p) == ""
    assert personalization_trace(p) == {
        "profile_active": False,
        "assistant_stance": "off",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
    }


def test_round_trip_profile_and_json_fields(tmp_path):
    store = InvestorProfileStore(tmp_path / "profile_state.db")
    assert store.get().enabled is False  # no row yet -> default

    saved = store.save(
        {
            "enabled": True,
            "primary_preset": "value",
            "risk_appetite": 8,
            "risk_capacity": 4,
            "holding_horizon": "months",
            "drawdown_tolerance_pct": 25.0,
            "concentration_limit_pct": 20.0,
            "preferred_edge": ["valuation", "catalyst", "valuation"],
            "avoidances": ["leverage", ""],
            "behavioral_flags": ["FOMO", "anchoring"],
            "freeform_notes": "I sell winners too early.",
            "default_stance": "strict_risk_control",
            "skill_mode": "suggest_only",
        }
    )
    again = store.get()
    assert again.enabled is True
    assert again.primary_preset == "value"
    assert again.risk_appetite == 8 and again.risk_capacity == 4
    assert again.risk_mismatch == "appetite_above_capacity"  # derived, not client-supplied
    assert again.preferred_edge == ["valuation", "catalyst"]  # deduped, order kept
    assert again.avoidances == ["leverage"]  # empties dropped
    assert again.behavioral_flags == ["FOMO", "anchoring"]
    assert again.freeform_notes == "I sell winners too early."
    assert again.default_stance == "strict_risk_control"
    assert again.skill_mode == "suggest_only"
    assert again.updated_at is not None
    assert again.last_reviewed_at is not None
    assert saved == again

    # draft() normalizes but must not persist
    draft = store.draft({"enabled": False})
    assert draft.enabled is False
    assert store.get().enabled is True


@pytest.mark.parametrize(
    "appetite, capacity, expected",
    [
        (8, 4, "appetite_above_capacity"),
        (3, 7, "capacity_above_appetite"),
        (None, 5, "unclear"),
        (5, None, "unclear"),
        (None, None, "unclear"),
        (6, 5, "none"),
        (5, 5, "none"),
    ],
)
def test_risk_mismatch_derivation(appetite, capacity, expected):
    assert expected in RISK_MISMATCHES
    assert derive_risk_mismatch(appetite, capacity) == expected


def test_disabled_profile_forces_effective_stance_off():
    p = replace(default_profile(), enabled=False, default_stance="complementary")
    assert effective_stance(p) == "off"
    assert effective_stance(p, override="aligned") == "off"
    assert build_personalization_context(p, override="aligned") == ""
    trace = personalization_trace(p, override="aligned")
    assert trace["profile_active"] is False
    assert trace["assistant_stance"] == "off"


def test_enabled_profile_context_contains_stance_and_no_evidence_language():
    p = replace(
        default_profile(),
        enabled=True,
        risk_appetite=8,
        risk_capacity=4,
        risk_mismatch="appetite_above_capacity",
        behavioral_flags=["FOMO"],
        default_stance="complementary",
        skill_mode="off",
    )
    ctx = build_personalization_context(p)
    assert "[Assistant Stance]" in ctx
    assert "complementary" in ctx
    assert "appetite_above_capacity" in ctx
    assert "FOMO" in ctx
    # Evidence boundary guard is IN the block; no evidence-tampering instructions.
    assert "do not exclude, filter, or reweight evidence" in ctx
    assert "counter-thesis" in ctx
    assert "gather_evidence" not in ctx
    lowered = ctx.lower()
    assert "hide" not in lowered and "suppress" not in lowered

    trace = personalization_trace(p)
    assert trace == {
        "profile_active": True,
        "assistant_stance": "complementary",
        "skill_mode": "off",
        "suggested_skills": [],
        "applied_skills": [],
    }

    # per-run override changes the effective stance and the block
    ctx2 = build_personalization_context(p, override="strict_risk_control")
    assert "strict_risk_control" in ctx2
    assert personalization_trace(p, override="strict_risk_control")["assistant_stance"] == "strict_risk_control"


def test_rejects_invalid_stance_or_skill_mode(tmp_path):
    store = InvestorProfileStore(tmp_path / "profile_state.db")
    with pytest.raises(ValueError):
        normalize_profile_payload({"default_stance": "yolo"})
    with pytest.raises(ValueError):
        normalize_profile_payload({"skill_mode": "auto_with_trace"})  # Track C, not Track A
    assert "auto_with_trace" not in SKILL_MODES
    with pytest.raises(ValueError):
        store.save({"risk_appetite": 99})  # never silently store 99
    with pytest.raises(ValueError):
        normalize_profile_payload({"primary_preset": "yolo_preset"})
    with pytest.raises(ValueError):
        normalize_profile_payload({"holding_horizon": "forever"})
    enabled = replace(default_profile(), enabled=True)
    with pytest.raises(ValueError):
        effective_stance(enabled, override="bogus")
    assert "off" in STANCES
