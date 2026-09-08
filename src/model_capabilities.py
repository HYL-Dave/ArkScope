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

import re
from dataclasses import dataclass

from src.subscription_plan import normalize_subscription_plan

_ANTHROPIC_DOCS = "https://docs.anthropic.com/en/docs/about-claude/models/all-models"
_OPENAI_DOCS = "https://developers.openai.com/api/docs/models"
_ANTHROPIC_CTX_DOC = "https://platform.claude.com/docs/en/build-with-claude/context-windows"
_ANTHROPIC_OVERVIEW = "https://platform.claude.com/docs/en/about-claude/models/overview"

# OpenAI effort support is model-specific. ``default`` remains a route sentinel
# in model_routing; these tuples contain only values accepted by each model.
_OPENAI_56_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
_OPENAI_STANDARD_EFFORTS = ("none", "low", "medium", "high", "xhigh")
_OPENAI_CODEX_EFFORTS = ("low", "medium", "high", "xhigh")
_OPUS_EFFORTS = ("max", "xhigh", "high", "medium", "low")

MODEL_REASON_CODES = frozenset(
    {
        "adapter_unavailable",
        "context_window_exceeded",
        "discovery_unavailable",
        "missing_active_credential",
        "model_auth_unverified",
        "model_entitlement_unverified",
        "model_not_in_registry",
        "model_not_visible",
        "model_output_limit_unknown",
        "model_retired",
        "model_task_unsupported",
        "protocol_incompatible",
        "protocol_resource_exhausted",
        "provider_call_failed",
        "reauth_required",
        "subscription_plan_required",
        "subscription_plan_unverified",
        "subscription_usage_unavailable",
        "task_auth_mode_unsupported",
        "task_capability_missing",
        "task_test_unsupported",
        "timeout",
        "version_incompatible",
    }
)


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
    max_output: int | None
    supports_structured_output: bool = True
    supports_tool_calling: bool = True
    # Reviewed ArkScope transport choice, not a claim that every other API
    # combination is forbidden by the provider.
    uses_responses_for_tools: bool = False
    runtime_ready: bool = True
    # False means the registry entry exists only to preserve/display historical
    # provenance. It is stronger than task_route_status: every new execution
    # seam must reject it, while older Advanced models may remain usable by
    # non-task tools where those tools already permit custom model IDs.
    new_execution_allowed: bool = True
    supports_client_compaction: bool = True
    # Auth modes that ArkScope has not live-verified for this exact model.
    # This is an admission fact, not a provider-wide compatibility claim.
    unverified_auth_modes: tuple[str, ...] = ()
    allowed_tasks: tuple[str, ...] = ()
    allowed_auth_modes: tuple[str, ...] = ()
    required_plans: tuple[str, ...] = ()
    exact_model_id: bool = False
    execution_adapter: str = "provider_native"
    task_route_status: str = "retired"  # current | retired; independent of adapter readiness
    in_routing_seed: bool = False
    aliases: tuple[str, ...] = ()      # OFFICIAL aliases only (e.g. "gpt-5.6"→Sol)
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
        id="claude-fable-5-1", provider="anthropic", label="Claude Fable 5.1",
        picker_visibility="default", thinking_mode="adaptive_always_on",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        supports_client_compaction=False,
        unverified_auth_modes=("claude_code_oauth",),
        task_route_status="current",
        in_routing_seed=True,
        aliases=(),
        quality="frontier", speed="slow", cost_tier="high",
        recommended_for=(),
        source_url="https://platform.claude.com/docs/en/models/fable-5-1/overview",
        verified_at="2026-09-02",
        notes="Adaptive thinking is always on; default effort is high. "
              "Forced tool choice is unsupported, so direct fixed-task calls "
              "use auto plus strict tools. $10/$50 per MTok.",
    ),
    ModelCapability(
        id="claude-fable-5", provider="anthropic", label="Claude Fable 5",
        picker_visibility="pinned_only", thinking_mode="adaptive_always_on",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        new_execution_allowed=False,
        task_route_status="retired",
        in_routing_seed=False,
        aliases=(),
        quality="frontier", speed="slow", cost_tier="high",
        recommended_for=(),
        source_url="https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5",
        verified_at="2026-07-10",
        notes="Product-retired on 2026-09-02; retained for historical provenance. "
              "Thinking always-on (disable rejected); refusals return HTTP 200 "
              "stop_reason=refusal — handled via src/anthropic_refusal.py. "
              "$10/$50 per MTok.",
    ),
    ModelCapability(
        id="claude-sonnet-5", provider="anthropic", label="Claude Sonnet 5",
        picker_visibility="default", thinking_mode="adaptive_default_on",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        task_route_status="current",
        in_routing_seed=True,
        aliases=(),
        quality="balanced", speed="fast", cost_tier="medium",
        recommended_for=(),
        source_url="https://platform.claude.com/docs/en/about-claude/models/overview",
        verified_at="2026-07-10",
        notes="Thinking default-on (omit = on; explicit disabled allowed; manual "
              "budget rejected 400). $3/$15 per MTok (intro $2/$10 through "
              "2026-08-31).",
    ),
    ModelCapability(
        id="claude-opus-5", provider="anthropic", label="Claude Opus 5",
        picker_visibility="default", thinking_mode="adaptive_default_on",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        task_route_status="current", in_routing_seed=True,
        quality="frontier", speed="slow", cost_tier="high",
        source_url="https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5",
        verified_at="2026-08-28",
        notes="Thinking default-on; effort ladder verified against "
              "https://platform.claude.com/docs/en/build-with-claude/effort.",
    ),
    ModelCapability(
        id="claude-opus-4-8", provider="anthropic", label="Claude Opus 4.8",
        picker_visibility="pinned_only", thinking_mode="adaptive_opt_in",
        effort_options=_OPUS_EFFORTS,          # Fix A (CLI helper previously None)
        supports_compaction=True,              # Fix C (compaction beta list)
        context_mode="ga_1m",                  # Fix B (1M GA per context-windows doc)
        context_limit=1_000_000,               # Fix B (was 200_000 fallback)
        max_output=128_000,
        quality="frontier", speed="slow", cost_tier="high",
        source_url=_ANTHROPIC_CTX_DOC, verified_at="2026-07-10",
        notes="Fixes A/B/C applied per official docs (user-ruled 2026-07-10).",
    ),
    ModelCapability(
        id="claude-opus-4-7", provider="anthropic", label="Claude Opus 4.7",
        picker_visibility="pinned_only", thinking_mode="adaptive_opt_in",
        effort_options=_OPUS_EFFORTS,
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000, max_output=128_000,
        quality="high", speed="slow", cost_tier="high",
        source_url=_ANTHROPIC_DOCS, verified_at="2026-06-06",
        notes="Previous generation kept as an Advanced path; future removal expected.",
    ),
    ModelCapability(
        id="claude-sonnet-4-6", provider="anthropic", label="Claude Sonnet 4.6",
        picker_visibility="pinned_only", thinking_mode="adaptive_opt_in",
        effort_options=("max", "high", "medium", "low"),   # Fix E (docs incl. max)
        supports_compaction=True, context_mode="ga_1m",
        context_limit=1_000_000,
        max_output=128_000,                    # Fix D (was 64_000; models table)
        quality="balanced", speed="medium", cost_tier="medium",
        source_url=_ANTHROPIC_OVERVIEW, verified_at="2026-07-10",
        notes="Fixes D/E applied per official docs (user-ruled 2026-07-10). "
              "Previous generation kept as an Advanced path; future removal expected.",
    ),
    ModelCapability(
        id="claude-haiku-4-5", provider="anthropic", label="Claude Haiku 4.5",
        picker_visibility="pinned_only", thinking_mode="manual_budget",
        effort_options=(), supports_compaction=False, context_mode="standard",
        context_limit=200_000, max_output=64_000,
        quality="fast", speed="fast", cost_tier="low",
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
        id="gpt-5.3-codex-spark", provider="openai",
        label="GPT-5.3-Codex-Spark",
        picker_visibility="advanced", thinking_mode="none",
        effort_options=_OPENAI_CODEX_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=128_000, max_output=None,
        supports_tool_calling=False,
        allowed_tasks=("card_translation",),
        allowed_auth_modes=("chatgpt_oauth",),
        exact_model_id=True,
        execution_adapter="codex_app_server",
        task_route_status="current",
        in_routing_seed=False,
        quality="fast", speed="fast", cost_tier="low",
        recommended_for=("card_translation",),
        source_url="https://openai.com/index/introducing-gpt-5-3-codex-spark/",
        verified_at="2026-09-02",
        notes="ChatGPT Pro research preview; exact-id Content Translation route "
              "through the bundled Codex app-server only. Provider maximum "
              "output is not published.",
    ),
    ModelCapability(
        id="gpt-6-astra", provider="openai", label="GPT-6 Astra",
        picker_visibility="default", thinking_mode="none",
        effort_options=("low", "medium", "high", "xhigh", "max"),
        supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        uses_responses_for_tools=True,
        task_route_status="current", in_routing_seed=True,
        quality="frontier", speed="medium", cost_tier="high",
        source_url="https://developers.openai.com/api/docs/models/gpt-6-astra",
        verified_at="2026-09-08",
        notes="Tool calls require Responses API. No none/minimal effort or "
              "sampling parameters. Existing task defaults remain unchanged.",
    ),
    ModelCapability(
        id="gpt-5.6-sol", provider="openai", label="GPT-5.6 Sol",
        picker_visibility="default", thinking_mode="none",
        effort_options=_OPENAI_56_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        uses_responses_for_tools=True,
        task_route_status="current",
        in_routing_seed=True,
        aliases=("gpt-5.6",),   # official: the gpt-5.6 alias routes to Sol
        quality="frontier", speed="medium", cost_tier="high",
        recommended_for=(),
        source_url="https://developers.openai.com/api/docs/models/gpt-5.6-sol",
        verified_at="2026-07-10",
        notes="$5/$30 per MTok (cached in $0.50).",
    ),
    ModelCapability(
        id="gpt-5.6-terra", provider="openai", label="GPT-5.6 Terra",
        picker_visibility="default", thinking_mode="none",
        effort_options=_OPENAI_56_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        uses_responses_for_tools=True,
        task_route_status="current",
        in_routing_seed=True,
        aliases=(),
        quality="high", speed="medium", cost_tier="medium",
        recommended_for=(),
        source_url="https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        verified_at="2026-07-10",
        notes="~gpt-5.5 capability at half its price: $2.50/$15 per MTok "
              "(cached in $0.25).",
    ),
    ModelCapability(
        id="gpt-5.6-luna", provider="openai", label="GPT-5.6 Luna",
        picker_visibility="default", thinking_mode="none",
        effort_options=_OPENAI_56_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        uses_responses_for_tools=True,
        task_route_status="current",
        in_routing_seed=True,
        aliases=(),
        quality="balanced", speed="fast", cost_tier="low",
        recommended_for=(),
        source_url="https://developers.openai.com/api/docs/models/gpt-5.6-luna",
        verified_at="2026-07-10",
        notes="Cost-sensitive high-volume tier (nano successor): $1/$6 per MTok "
              "(cached in $0.10).",
    ),
    ModelCapability(
        id="gpt-5.5", provider="openai", label="GPT-5.5",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_STANDARD_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        quality="frontier", speed="medium", cost_tier="high",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
        notes="Superseded by gpt-5.6-terra at half the price (user ruling 2026-07-10).",
    ),
    ModelCapability(
        id="gpt-5.4-mini", provider="openai", label="GPT-5.4 mini",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_STANDARD_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        quality="balanced", speed="fast", cost_tier="low",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
        notes="Stays default: cheapest relevant option under codex OAuth costing.",
    ),
    ModelCapability(
        id="gpt-5.4-nano", provider="openai", label="GPT-5.4 Nano",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_STANDARD_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        quality="fast", speed="fast", cost_tier="low",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.4", provider="openai", label="GPT-5.4",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_STANDARD_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=1_050_000, max_output=128_000,
        quality="high", speed="medium", cost_tier="medium",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.2", provider="openai", label="GPT-5.2 (legacy)",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_STANDARD_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
        quality="high", speed="medium", cost_tier="medium",
        source_url=_OPENAI_DOCS, verified_at="2026-06-06",
    ),
    ModelCapability(
        id="gpt-5.2-codex", provider="openai", label="GPT-5.2 Codex (legacy)",
        picker_visibility="pinned_only", thinking_mode="none",
        effort_options=_OPENAI_CODEX_EFFORTS, supports_compaction=False,
        context_mode="standard", context_limit=400_000, max_output=128_000,
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
        if cap.exact_model_id:
            continue
        if _matches_reviewed_variant(cap.id, lowered):
            return cap
    return None


_VARIANT_CHARS = re.compile(r"-[a-z0-9][a-z0-9-]*$")
_DATED_VARIANT = re.compile(
    r"-[12][0-9]{3}(?:[0-9]{4}|(?:-[a-z0-9][a-z0-9-]*)?)$"
)


def _matches_reviewed_variant(canonical_id: str, query: str) -> bool:
    """Match a canonical model's reviewed variant forms without sibling bleed.

    Alphabetic suffixes retain the registry's legacy custom/snapshot behavior.
    Numeric suffixes are accepted only in the established dated-snapshot shape;
    this prevents an unknown Fable 5.2 or 5.10 from inheriting Fable 5/5.1 facts.
    """
    if not query.startswith(canonical_id):
        return False
    suffix = query[len(canonical_id):]
    if not suffix:
        return True
    if not suffix.startswith("-"):
        return False
    if len(suffix) == 1:
        return False
    if _VARIANT_CHARS.fullmatch(suffix) is None:
        return False
    if "0" <= suffix[1] <= "9":
        return _DATED_VARIANT.fullmatch(suffix) is not None
    return True


def model_execution_admission_detail(
    model: str,
    *,
    task: str | None = None,
    auth_mode: str | None = None,
    plan_type: str | None = None,
) -> dict[str, str] | None:
    """Return a typed block when a model cannot execute in this context."""
    capability = capability_for(model)
    if capability is None:
        return None
    if not capability.new_execution_allowed:
        return {"code": "model_retired", "field": "model"}
    normalized_task = (task or "").strip().lower()
    if capability.allowed_tasks and normalized_task not in capability.allowed_tasks:
        return {"code": "model_task_unsupported", "field": "task"}
    normalized_auth_mode = (auth_mode or "").strip().lower()
    if (
        capability.allowed_auth_modes
        and normalized_auth_mode not in capability.allowed_auth_modes
    ):
        return {"code": "task_auth_mode_unsupported", "field": "credential"}
    if capability.required_plans:
        normalized_plan = normalize_subscription_plan(plan_type)
        if normalized_plan is None:
            return {"code": "subscription_plan_unverified", "field": "credential"}
        if normalized_plan not in capability.required_plans:
            return {"code": "subscription_plan_required", "field": "credential"}
    return None


def model_entitlement_admission_detail(
    model: str,
    *,
    discovery_status: str,
    discovered_model_ids: set[str] | frozenset[str],
) -> dict[str, str] | None:
    """Require direct per-credential observation for exact-id models."""
    capability = capability_for(model)
    if capability is None or not capability.exact_model_id:
        return None
    requested_model = (model or "").strip()
    if requested_model != capability.id:
        return {"code": "model_not_visible", "field": "model"}
    if discovery_status != "ok":
        return {"code": "model_entitlement_unverified", "field": "model"}
    if requested_model not in discovered_model_ids:
        return {"code": "model_not_visible", "field": "model"}
    return None


def model_auth_admission_detail(
    model: str, auth_mode: str | None
) -> dict[str, str] | None:
    """Return a typed block for model/auth pairs ArkScope has not live-verified."""
    capability = capability_for(model)
    if (
        capability is not None
        and auth_mode is not None
        and auth_mode in capability.unverified_auth_modes
    ):
        return {"code": "model_auth_unverified", "field": "model"}
    return None


def client_compaction_admission_detail(
    model: str, enabled: bool
) -> dict[str, object] | None:
    """Block model/client-compaction pairs whose message rewriting is unverified."""
    capability = capability_for(model)
    if enabled and capability is not None and not capability.supports_client_compaction:
        return {
            "code": "model_client_compaction_incompatible",
            "field": "compaction.enabled",
            "message": (
                "Claude Fable 5.1 has not been validated with ArkScope client-side "
                "compaction. Disable client-side compaction or choose another model."
            ),
            "actions": ["disable_client_compaction", "choose_another_model"],
        }
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
