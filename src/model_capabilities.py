"""Code-reviewed model capability registry (P2.7).

The single source for model FACTS: context/output limits, thinking mode, effort
options, compaction, context mode, structured-output/tool support, picker
visibility, and compat-view membership. Discovery entitlement (which credential
can SEE a model) lives in the DB cache (src/model_discovery_cache.py) — never
here. Membership rule: an entry requires an official per-model documentation
page AND ArkScope relevance (picker policy, compat view, or an existing pin);
documented-but-irrelevant models do not enter.

Pure stdlib by design: importable from agents, routing, credentials, and the
API layer without cycles. Values are transcribed from the pre-consolidation
tables plus five user-ruled fixes (A-E, 2026-07-10) — the old-vs-new
equivalence test in tests/test_model_capabilities.py is the tripwire for any
unruled divergence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_ANTHROPIC_DOCS = "https://docs.anthropic.com/en/docs/about-claude/models/all-models"
_OPENAI_DOCS = "https://developers.openai.com/api/docs/models"
_ANTHROPIC_CTX_DOC = "https://platform.claude.com/docs/en/build-with-claude/context-windows"
_ANTHROPIC_OVERVIEW = "https://platform.claude.com/docs/en/about-claude/models/overview"

# Provider-wide OpenAI reasoning-effort wire set (model-supported options; the
# route-validation wire values incl. "default" stay in model_routing.EFFORT_OPTIONS).
_OPENAI_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
_OPUS_EFFORTS = ("max", "xhigh", "high", "medium", "low")


@dataclass(frozen=True)
class ModelCapability:
    id: str
    provider: str                     # "anthropic" | "openai"
    label: str
    picker_visibility: str            # "default" | "advanced" | "pinned_only"
    thinking_mode: str                # none | manual_budget | adaptive_opt_in |
                                      # adaptive_default_on | adaptive_always_on
    effort_options: tuple[str, ...]   # model-supported set; () = unsupported
    supports_compaction: bool
    context_mode: str                 # "standard" | "ga_1m" | "beta_1m"
    context_limit: int
    max_output: int
    supports_structured_output: bool = True
    supports_tool_calling: bool = True
    runtime_ready: bool = True
    in_routing_seed: bool = False
    in_cli_catalog: bool = False
    aliases: tuple[str, ...] = ()
    quality: str = "high"             # frontier | high | balanced | fast
    speed: str = "medium"             # slow | medium | fast
    cost_tier: str = "medium"         # high | medium | low
    recommended_for: tuple[str, ...] = ()
    source_url: str = ""
    verified_at: str = ""
    notes: str = ""


_REGISTRY: tuple[ModelCapability, ...] = (
    # ── Anthropic ────────────────────────────────────────────────
    ModelCapability(
        id="claude-opus-4-8", provider="anthropic", label="Claude Opus 4.8",
        picker_visibility="default", thinking_mode="adaptive_opt_in",
        effort_options=_OPUS_EFFORTS,          # Fix A (CLI helper previously None)
        supports_compaction=True,              # Fix C (compaction beta list)
        context_mode="ga_1m",                  # Fix B (1M GA per context-windows doc)
        context_limit=1_000_000,               # Fix B (was 200_000 fallback)
        max_output=128_000,
        in_routing_seed=True,
        quality="frontier", speed="slow", cost_tier="high",
        recommended_for=("card_synthesis",),
        source_url=_ANTHROPIC_CTX_DOC, verified_at="2026-07-10",
        notes="Fixes A/B/C applied per official docs (user-ruled 2026-07-10).",
    ),
    ModelCapability(
        id="claude-opus-4-7", provider="anthropic", label="Claude Opus 4.7",
        picker_visibility="advanced", thinking_mode="adaptive_opt_in",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        in_routing_seed=True, in_cli_catalog=True,
        aliases=("opus", "opus4.7", "opus-4.7", "o47", "claude-opus"),
        quality="high", speed="slow", cost_tier="high",
        recommended_for=("card_synthesis",),
        source_url=_ANTHROPIC_DOCS, verified_at="2026-06-06",
        notes="Previous generation kept as an Advanced path; future removal expected.",
    ),
    ModelCapability(
        id="claude-sonnet-4-6", provider="anthropic", label="Claude Sonnet 4.6",
        picker_visibility="advanced", thinking_mode="adaptive_opt_in",
        effort_options=("max", "high", "medium", "low"),   # Fix E (docs incl. max)
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000,
        max_output=128_000,                    # Fix D (was 64_000; models table)
        in_routing_seed=True, in_cli_catalog=True,
        aliases=("sonnet", "sonnet4.6", "sonnet-4.6", "s46", "claude-sonnet", "claude"),
        quality="balanced", speed="medium", cost_tier="medium",
        recommended_for=("card_translation",),
        source_url=_ANTHROPIC_OVERVIEW, verified_at="2026-07-10",
        notes="Fixes D/E applied per official docs (user-ruled 2026-07-10). "
              "Previous generation kept as an Advanced path; future removal expected.",
    ),
    ModelCapability(
        id="claude-haiku-4-5", provider="anthropic", label="Claude Haiku 4.5",
        picker_visibility="default", thinking_mode="manual_budget",
        effort_options=(), supports_compaction=False, context_mode="standard",
        context_limit=200_000, max_output=64_000,
        in_routing_seed=True,
        quality="fast", speed="fast", cost_tier="low",
        recommended_for=("card_translation",),
        source_url=_ANTHROPIC_DOCS, verified_at="2026-06-06",
        notes="Canonical dated id is claude-haiku-4-5-20251001; prefix match covers it.",
    ),
    ModelCapability(
        id="claude-sonnet-4-5", provider="anthropic", label="Claude Sonnet 4.5",
        picker_visibility="pinned_only", thinking_mode="manual_budget",
        effort_options=(), supports_compaction=False, context_mode="beta_1m",
        context_limit=200_000, max_output=64_000,
        quality="balanced", speed="medium", cost_tier="medium",
        source_url=_ANTHROPIC_DOCS, verified_at="2026-06-06",
        notes="Legacy 1M-beta-header model (subagent _1M_BETA_MODELS transcription).",
    ),
    ModelCapability(
        id="claude-opus-4-5", provider="anthropic", label="Claude Opus 4.5",
        picker_visibility="pinned_only", thinking_mode="manual_budget",
        effort_options=(), supports_compaction=False, context_mode="beta_1m",
        context_limit=200_000, max_output=64_000,
        quality="high", speed="slow", cost_tier="high",
        source_url=_ANTHROPIC_DOCS, verified_at="2026-06-06",
        notes="Legacy 1M-beta-header model (subagent _1M_BETA_MODELS transcription).",
    ),
    # ── OpenAI ───────────────────────────────────────────────────
    ModelCapability(
        id="gpt-5.5", provider="openai", label="GPT-5.5",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        in_routing_seed=True, in_cli_catalog=True,
        aliases=("gpt5", "gpt-5", "gpt5.5", "5.5"),
        quality="frontier", speed="medium", cost_tier="high",
        recommended_for=("card_synthesis",),
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
        notes="Superseded by gpt-5.6-terra at half the price (user ruling 2026-07-10).",
    ),
    ModelCapability(
        id="gpt-5.4", provider="openai", label="GPT-5.4",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        in_routing_seed=True, in_cli_catalog=True,
        aliases=("gpt5.4", "5.4"),
        quality="high", speed="medium", cost_tier="medium",
        recommended_for=("card_synthesis",),
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.4-mini", provider="openai", label="GPT-5.4 mini",
        picker_visibility="default", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        in_routing_seed=True, in_cli_catalog=True,
        aliases=("gpt5-mini", "gpt-5-mini", "5.4-mini", "mini"),
        quality="balanced", speed="fast", cost_tier="low",
        recommended_for=("card_translation",),
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
        notes="Stays default: cheapest relevant option under codex OAuth costing.",
    ),
    ModelCapability(
        id="gpt-5.4-nano", provider="openai", label="GPT-5.4 Nano",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        in_cli_catalog=True,
        aliases=("gpt5-nano", "gpt-5-nano", "5.4-nano", "nano"),
        quality="fast", speed="fast", cost_tier="low",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.2", provider="openai", label="GPT-5.2 (legacy)",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        in_cli_catalog=True,
        aliases=("gpt5.2", "5.2"),
        quality="high", speed="medium", cost_tier="medium",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.2-codex", provider="openai", label="GPT-5.2 Codex (legacy)",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        in_cli_catalog=True,
        aliases=("codex", "codex5.2", "5.2-codex"),
        quality="high", speed="medium", cost_tier="medium",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
)

# Exact alias/id lookup first; longest-prefix fallback second (structural
# precedence — never list-order luck).
_BY_EXACT: dict[str, ModelCapability] = {}
for _cap in _REGISTRY:
    _BY_EXACT[_cap.id] = _cap
    for _alias in _cap.aliases:
        if _alias in _BY_EXACT:
            raise ValueError(f"duplicate model alias/id: {_alias!r}")
        _BY_EXACT[_alias] = _cap

_BY_PREFIX: tuple[ModelCapability, ...] = tuple(
    sorted(_REGISTRY, key=lambda c: len(c.id), reverse=True)
)


def capability_for(model: str) -> ModelCapability | None:
    """Resolve a model id/alias to its capability entry (None if unknown)."""
    query = (model or "").strip()
    if not query:
        return None
    exact = _BY_EXACT.get(query) or _BY_EXACT.get(query.lower())
    if exact is not None:
        return exact
    lowered = query.lower()
    for cap in _BY_PREFIX:
        if lowered.startswith(cap.id):
            return cap
    return None


def all_models(provider: str | None = None) -> tuple[ModelCapability, ...]:
    if provider is None:
        return _REGISTRY
    return tuple(c for c in _REGISTRY if c.provider == provider)


def default_picker_models(provider: str) -> tuple[ModelCapability, ...]:
    """Default-visibility, runtime-ready models for the effective picker."""
    return tuple(
        c for c in _REGISTRY
        if c.provider == provider
        and c.picker_visibility == "default"
        and c.runtime_ready
    )
