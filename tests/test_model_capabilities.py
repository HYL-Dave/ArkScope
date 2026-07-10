"""Capability registry tests (P2.7 Task 1).

The old-vs-new equivalence test imports the LIVE pre-consolidation helpers —
they are untouched in Task 1, so divergence beyond the five ruled fixes fails
loudly here instead of surfacing later as a silent behavior change.
"""

from src.model_capabilities import (
    all_models,
    capability_for,
    default_picker_models,
)

_PRE_CONSOLIDATION_IDS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
    "claude-sonnet-4-5", "claude-opus-4-5",
    "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.2", "gpt-5.2-codex",
}

# Ruled divergences (user-acked 2026-07-10): everything else must match the
# live helpers exactly.
_RULED_FIXES = {
    ("claude-opus-4-8", "context_limit"),        # Fix B
    ("claude-opus-4-8", "context_mode"),         # Fix B
    ("claude-opus-4-8", "effort_options"),       # Fix A
    ("claude-opus-4-8", "supports_compaction"),  # Fix C
    ("claude-sonnet-4-6", "max_output"),         # Fix D
    ("claude-sonnet-4-6", "effort_options"),     # Fix E
}


def test_registry_covers_every_pre_consolidation_id():
    assert {m for m in _PRE_CONSOLIDATION_IDS if capability_for(m) is None} == set()


def test_registry_matches_live_legacy_helpers_except_ruled_fixes():
    from src.agents.anthropic_agent.agent import (
        _MODEL_MAX_OUTPUT as OLD_ANTH_OUT,
        _ADAPTIVE_THINKING_MODELS as OLD_ADAPTIVE,
        _COMPACTION_MODELS as OLD_COMPACT,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit
    from src.agents.shared.subagent import _1M_GA_MODELS, _1M_BETA_MODELS
    from src.agents.shared.model_catalog import get_effort_options

    for mid in sorted(_PRE_CONSOLIDATION_IDS):
        cap = capability_for(mid)
        old_ctx = get_model_context_limit(mid)
        if (mid, "context_limit") in _RULED_FIXES:
            assert cap.context_limit == 1_000_000 and old_ctx == 200_000, mid
        else:
            assert cap.context_limit == old_ctx, mid
        if cap.provider == "anthropic":
            old_out = next((v for k, v in OLD_ANTH_OUT.items() if mid.startswith(k)), 64_000)
        else:
            old_out = _get_openai_max_output(mid)
        if (mid, "max_output") in _RULED_FIXES:               # Fix D
            assert cap.max_output == 128_000 and old_out == 64_000, mid
        else:
            assert cap.max_output == old_out, mid
        if cap.provider == "anthropic":
            expected_mode = (
                "adaptive_opt_in"
                if any(mid.startswith(m) for m in OLD_ADAPTIVE)
                else "manual_budget"
            )
        else:
            expected_mode = "none"
        assert cap.thinking_mode == expected_mode, mid
        old_tuple = get_effort_options(mid)
        if (mid, "effort_options") in _RULED_FIXES:
            if mid == "claude-opus-4-8":                      # Fix A
                assert old_tuple is None
                assert cap.effort_options == ("max", "xhigh", "high", "medium", "low"), mid
            else:                                             # Fix E (sonnet-4-6)
                assert tuple(old_tuple) == ("high", "medium", "low")
                assert cap.effort_options == ("max", "high", "medium", "low"), mid
        elif cap.provider == "anthropic":
            assert cap.effort_options == (tuple(old_tuple) if old_tuple else ()), mid
        old_compact = any(mid.startswith(m) for m in OLD_COMPACT)
        if (mid, "supports_compaction") in _RULED_FIXES:      # Fix C
            assert cap.supports_compaction is True and old_compact is False, mid
        else:
            assert cap.supports_compaction == old_compact, mid
        old_mode = (
            "ga_1m" if mid in _1M_GA_MODELS
            else "beta_1m" if mid in _1M_BETA_MODELS
            else "standard"
        )
        if (mid, "context_mode") in _RULED_FIXES:
            assert cap.context_mode == "ga_1m" and old_mode == "standard", mid
        else:
            assert cap.context_mode == old_mode, mid


def test_openai_models_record_provider_wide_effort_set():
    for mid in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano",
                "gpt-5.2", "gpt-5.2-codex"):
        assert capability_for(mid).effort_options == (
            "none", "minimal", "low", "medium", "high", "xhigh",
        ), mid


def test_view_flags_pin_exact_current_memberships():
    routing = {c.id for c in all_models() if c.in_routing_seed}
    cli = {c.id for c in all_models() if c.in_cli_catalog}
    assert routing == {
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    }
    assert cli == {
        "claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.4-mini",
        "gpt-5.4-nano", "gpt-5.4", "gpt-5.2", "gpt-5.2-codex",
    }


def test_picker_visibility_matches_the_ruling():
    vis = {c.id: c.picker_visibility for c in all_models()}
    assert vis["claude-opus-4-8"] == "default"
    assert vis["claude-haiku-4-5"] == "default"
    assert vis["gpt-5.4-mini"] == "default"
    assert vis["claude-opus-4-7"] == "advanced"
    assert vis["claude-sonnet-4-6"] == "advanced"
    for pinned in ("gpt-5.5", "gpt-5.4", "gpt-5.4-nano", "gpt-5.2",
                   "gpt-5.2-codex", "claude-sonnet-4-5", "claude-opus-4-5"):
        assert vis[pinned] == "pinned_only", pinned


def test_default_picker_models_helper():
    assert {c.id for c in default_picker_models("openai")} == {"gpt-5.4-mini"}
    assert {c.id for c in default_picker_models("anthropic")} == {
        "claude-opus-4-8", "claude-haiku-4-5",
    }


def test_prefix_precedence_is_structural_not_list_order():
    assert capability_for("gpt-5.4-mini-2026-x").id == "gpt-5.4-mini"
    assert capability_for("gpt-5.4-2026-x").id == "gpt-5.4"
    assert capability_for("gpt-5.2-codex-x").id == "gpt-5.2-codex"
    assert capability_for("claude-haiku-4-5-20251001").id == "claude-haiku-4-5"


def test_unknown_model_returns_none():
    assert capability_for("mystery-model") is None


def test_every_entry_carries_provenance_visibility_and_mode():
    for cap in all_models():
        assert cap.source_url and cap.verified_at, cap.id
        assert cap.picker_visibility in ("default", "advanced", "pinned_only"), cap.id
        assert cap.thinking_mode in (
            "none", "manual_budget", "adaptive_opt_in",
            "adaptive_default_on", "adaptive_always_on",
        ), cap.id
