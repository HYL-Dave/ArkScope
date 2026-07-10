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


def test_registry_and_helpers_agree_for_every_pre_consolidation_id():
    """Post-convergence consistency: every helper output equals the registry.

    MIGRATION EVIDENCE: the pre-convergence version of this test (commit
    02fe47d, Task 1) ran against the genuinely-old hardcoded tables and proved
    the registry reproduced them exactly, with the five user-ruled fixes (A-E)
    as the only divergences. Post-Task-2 the old tables are registry-derived,
    so this test pins the CONVERGED state plus the fixes' absolute values.
    """
    from src.agents.anthropic_agent.agent import (
        _get_model_max_output,
        _supports_adaptive_thinking,
        _supports_compaction,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit
    from src.agents.shared.subagent import _1M_GA_MODELS, _1M_BETA_MODELS
    from src.agents.shared.model_catalog import get_effort_options

    for mid in sorted(_PRE_CONSOLIDATION_IDS):
        cap = capability_for(mid)
        assert get_model_context_limit(mid) == cap.context_limit, mid
        if cap.provider == "anthropic":
            assert _get_model_max_output(mid) == cap.max_output, mid
            assert _supports_adaptive_thinking(mid) == cap.thinking_mode.startswith("adaptive"), mid
            assert _supports_compaction(mid) == cap.supports_compaction, mid
            expected_tuple = tuple(cap.effort_options) if cap.effort_options else None
            assert get_effort_options(mid) == expected_tuple, mid
            assert (mid in _1M_GA_MODELS) == (cap.context_mode == "ga_1m"), mid
            assert (mid in _1M_BETA_MODELS) == (cap.context_mode == "beta_1m"), mid
        else:
            assert _get_openai_max_output(mid) == cap.max_output, mid
            assert get_effort_options(mid) is None, mid


def test_ruled_fixes_absolute_values():
    """The five user-acked fixes (2026-07-10), pinned as absolute values."""
    opus48 = capability_for("claude-opus-4-8")
    assert opus48.effort_options == ("max", "xhigh", "high", "medium", "low")  # Fix A
    assert opus48.context_limit == 1_000_000                                   # Fix B
    assert opus48.context_mode == "ga_1m"                                      # Fix B
    assert opus48.supports_compaction is True                                  # Fix C
    sonnet46 = capability_for("claude-sonnet-4-6")
    assert sonnet46.max_output == 128_000                                      # Fix D
    assert sonnet46.effort_options == ("max", "high", "medium", "low")         # Fix E


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


# ── Task 2: convergence tests ────────────────────────────────────


def test_agent_helpers_now_read_the_registry():
    from src.agents.anthropic_agent.agent import (
        _get_model_max_output, _supports_adaptive_thinking, _supports_effort,
        _supports_compaction,
    )
    from src.agents.openai_agent.agent import _get_openai_max_output
    from src.agents.shared.context_manager import get_model_context_limit
    from src.agents.shared.subagent import _use_extended_context_beta

    assert _get_model_max_output("claude-opus-4-8") == 128_000
    assert _get_model_max_output("claude-sonnet-4-6") == 128_000   # ruled Fix D
    assert _get_model_max_output("unknown-claude") == 64_000
    assert _supports_adaptive_thinking("claude-sonnet-4-6-future") is True
    assert _supports_effort("claude-haiku-4-5") is False
    assert _supports_compaction("claude-sonnet-4-6") is True
    assert _supports_compaction("claude-opus-4-8") is True    # ruled Fix C
    assert _get_openai_max_output("gpt-5.4-nano") == 128_000
    assert _get_openai_max_output("totally-unknown") == 128_000
    assert get_model_context_limit("gpt-5.4-mini") == 400_000
    assert get_model_context_limit("claude-opus-4-8") == 1_000_000   # ruled Fix B
    assert get_model_context_limit("unknown") == 200_000
    # wire behavior of the beta-header helper is UNCHANGED incl. opus-4.8 (=False)
    assert _use_extended_context_beta("claude-opus-4-8", True) is False
    assert _use_extended_context_beta("claude-opus-4-7", True) is False
    assert _use_extended_context_beta("claude-sonnet-4-5", True) is True


def test_build_thinking_param_wire_shapes_pinned():
    # Exact values from live runs (plan grounding §2) — GREEN before the swap,
    # pins the baseline so the registry-driven rewrite cannot drift it.
    from src.agents.anthropic_agent.agent import _build_thinking_param

    class _Cfg:
        max_tokens = 8192
        anthropic_thinking = True

    assert _build_thinking_param("claude-opus-4-8", True, _Cfg()) == (
        {"type": "adaptive"}, 128000,
    )
    assert _build_thinking_param("claude-haiku-4-5", True, _Cfg()) == (
        {"type": "enabled", "budget_tokens": 55808}, 64000,
    )
    assert _build_thinking_param("claude-haiku-4-5", False, _Cfg()) == (None, 8192)


def test_cli_effort_helper_contract_preserved_plus_fix_a():
    from src.agents.shared.model_catalog import get_effort_options
    assert get_effort_options("claude-opus-4-8") == ("max", "xhigh", "high", "medium", "low")  # Fix A
    assert get_effort_options("claude-opus-4-7") == ("max", "xhigh", "high", "medium", "low")
    assert get_effort_options("claude-sonnet-4-6") == ("max", "high", "medium", "low")  # ruled Fix E
    for openai_id in ("gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.2"):
        assert get_effort_options(openai_id) is None     # anthropic-only contract kept


def test_route_wire_effort_values_untouched():
    from src.model_routing import EFFORT_OPTIONS
    assert [o.id for o in EFFORT_OPTIONS["openai"]] == [
        "default", "none", "minimal", "low", "medium", "high", "xhigh",
    ]
    assert [o.id for o in EFFORT_OPTIONS["anthropic"]] == [
        "default", "low", "medium", "high", "xhigh", "max",
    ]


def test_derived_views_keep_exact_membership_and_aliases():
    from src.model_routing import MODEL_CATALOG as ROUTING_VIEW, is_seed_model
    from src.agents.shared.model_catalog import MODEL_CATALOG as CLI_VIEW, find_model

    assert {m.id for m in ROUTING_VIEW} == {
        "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-4-6",
        "claude-haiku-4-5", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
    }
    assert {m.id for m in CLI_VIEW} == {
        "claude-opus-4-7", "claude-sonnet-4-6", "gpt-5.5", "gpt-5.4-mini",
        "gpt-5.4-nano", "gpt-5.4", "gpt-5.2", "gpt-5.2-codex",
    }
    assert find_model("opus").id == "claude-opus-4-7"    # exact, not startswith
    assert find_model("mini").id == "gpt-5.4-mini"
    assert find_model("codex").id == "gpt-5.2-codex"
    assert is_seed_model("openai", "gpt-5.5")

    for option in ROUTING_VIEW:
        cap = capability_for(option.id)
        assert option.supports_structured_output == cap.supports_structured_output
        assert option.supports_tool_calling == cap.supports_tool_calling


def test_single_source_no_local_fact_tables():
    """Review Gate 3: after convergence the four agent modules hold no model-id
    fact tables (registry reads only). Checked structurally: the OLD table
    globals must be derived (registry-built), which we assert by identity of
    values with the registry rather than greping source here — the grep gate
    runs in CI/steps."""
    from src.agents.anthropic_agent import agent as anth
    from src.model_capabilities import all_models

    reg_compact = {c.id for c in all_models("anthropic") if c.supports_compaction}
    assert set(anth._COMPACTION_MODELS) == reg_compact
    reg_adaptive = {c.id for c in all_models("anthropic")
                    if c.thinking_mode.startswith("adaptive")}
    assert set(anth._ADAPTIVE_THINKING_MODELS) == reg_adaptive
