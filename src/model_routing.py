"""Model catalog and per-task routing for ArkScope AI operations.

The catalog is a seed, not a hard entitlement claim: providers roll models and
account access independently. The Settings UI therefore exposes both verified
seed models and a custom model-id escape hatch.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["anthropic", "openai"]
TaskId = Literal["card_synthesis", "card_translation", "ai_research"]
RouteSource = Literal["env", "db", "profile", "default"]
EffortId = Literal["default", "none", "minimal", "low", "medium", "high", "xhigh", "max"]

OPENAI_MODELS_SOURCE = "https://developers.openai.com/api/docs/models"
OPENAI_LATEST_SOURCE = "https://developers.openai.com/api/docs/guides/latest-model"
ANTHROPIC_MODELS_SOURCE = "https://docs.anthropic.com/en/docs/about-claude/models/all-models"
CATALOG_VERIFIED_AT = "2026-06-06"


class ModelOption(BaseModel):
    id: str
    provider: Provider
    label: str
    quality: Literal["frontier", "high", "balanced", "fast"]
    speed: Literal["slow", "medium", "fast"]
    cost_tier: Literal["high", "medium", "low"]
    supports_structured_output: bool = True
    supports_tool_calling: bool = True
    effort_options: list[EffortId] = Field(default_factory=list)
    recommended_for: list[TaskId] = Field(default_factory=list)
    source_url: str
    verified_at: str = CATALOG_VERIFIED_AT
    notes: str = ""


class TaskInfo(BaseModel):
    id: TaskId
    label: str
    description: str
    default_provider: Provider
    recommended_model: str


class TaskRoute(BaseModel):
    task: TaskId
    provider: Provider
    model: str
    effort: str = "default"
    source: RouteSource = "default"
    custom: bool = False
    warning: str | None = None


class EffortOption(BaseModel):
    id: EffortId
    provider: Provider
    label: str
    description: str
    applies_to_card_tasks: bool = True


class ModelCatalog(BaseModel):
    providers: list[Provider]
    tasks: list[TaskInfo]
    models: list[ModelOption]
    effort_options: dict[Provider, list[EffortOption]]


TASKS: list[TaskInfo] = [
    TaskInfo(
        id="card_synthesis",
        label="Card synthesis",
        description="Generate the structured §2 investment-research card from objective evidence.",
        default_provider="anthropic",
        recommended_model="claude-opus-4-8",
    ),
    TaskInfo(
        id="card_translation",
        label="Card translation",
        description="Translate generated cards while preserving structure, citations, and numbers.",
        default_provider="anthropic",
        recommended_model="claude-sonnet-4-6",
    ),
    TaskInfo(
        id="ai_research",
        label="AI 研究 (Research)",
        description="The interactive AI 研究 surface. Unset → the request provider's default-tier model; set a cheaper model/effort here (e.g. gpt-5.4-mini / low) for routine research.",
        default_provider="openai",
        recommended_model="gpt-5.4-mini",
    ),
]


# Derived from the capability registry (src/model_capabilities.py) — P2.7
# convergence. Membership = the registry's `in_routing_seed` flag; facts
# (structured-output/tool support, provenance) come from the same entries the
# agents execute against, so the Settings seed can no longer drift from runtime.
def _routing_view() -> list[ModelOption]:
    from src.model_capabilities import all_models

    return [
        ModelOption(
            id=cap.id,
            provider=cap.provider,  # type: ignore[arg-type]
            label=cap.label,
            quality=cap.quality,    # type: ignore[arg-type]
            speed=cap.speed,        # type: ignore[arg-type]
            cost_tier=cap.cost_tier,  # type: ignore[arg-type]
            supports_structured_output=cap.supports_structured_output,
            supports_tool_calling=cap.supports_tool_calling,
            effort_options=list(cap.effort_options),  # type: ignore[arg-type]
            recommended_for=list(cap.recommended_for),  # type: ignore[arg-type]
            source_url=cap.source_url,
            verified_at=cap.verified_at,
            notes=cap.notes,
        )
        for cap in all_models()
        if cap.in_routing_seed
    ]


MODEL_CATALOG: list[ModelOption] = _routing_view()


EFFORT_OPTIONS: dict[Provider, list[EffortOption]] = {
    "openai": [
        EffortOption(
            id="default",
            provider="openai",
            label="供應商預設",
            description="不送 effort；實際檔位由目前模型與後端決定。",
        ),
        EffortOption(
            id="none",
            provider="openai",
            label="無推理 (none)",
            description="明確送出 none；這不是未設定或供應商預設。",
        ),
        EffortOption(
            id="low",
            provider="openai",
            label="Low",
            description="Low reasoning effort.",
        ),
        EffortOption(
            id="medium",
            provider="openai",
            label="Medium",
            description="Balanced reasoning effort.",
        ),
        EffortOption(
            id="high",
            provider="openai",
            label="High",
            description="High reasoning effort for more difficult synthesis.",
        ),
        EffortOption(
            id="xhigh",
            provider="openai",
            label="Extra high",
            description="SDK-supported high-end reasoning effort; only use if the selected model/account accepts it.",
        ),
        EffortOption(
            id="max",
            provider="openai",
            label="Max",
            description="Maximum reasoning effort; currently supported by GPT-5.6 models.",
        ),
    ],
    "anthropic": [
        EffortOption(
            id="default",
            provider="anthropic",
            label="Provider default",
            description="Do not send output_config.effort; use the Claude API default.",
        ),
        EffortOption(
            id="low",
            provider="anthropic",
            label="Low",
            description="Lower effort via Anthropic output_config.effort.",
        ),
        EffortOption(
            id="medium",
            provider="anthropic",
            label="Medium",
            description="Medium effort via Anthropic output_config.effort.",
        ),
        EffortOption(
            id="high",
            provider="anthropic",
            label="High",
            description="High effort via Anthropic output_config.effort.",
        ),
        EffortOption(
            id="xhigh",
            provider="anthropic",
            label="Extra high",
            description="Extra-high effort via Anthropic output_config.effort where available.",
        ),
        EffortOption(
            id="max",
            provider="anthropic",
            label="Max",
            description="Maximum effort via Anthropic output_config.effort where available.",
        ),
    ],
}


def catalog() -> ModelCatalog:
    return ModelCatalog(
        providers=["anthropic", "openai"],
        tasks=TASKS,
        models=MODEL_CATALOG,
        effort_options=EFFORT_OPTIONS,
    )


def effort_options(provider: Provider) -> list[EffortOption]:
    return EFFORT_OPTIONS[provider]


def effort_ids_for_model(provider: Provider, model: str) -> tuple[str, ...]:
    """Return route values supported by a known model, including ``default``.

    Unknown/custom ids retain the provider union so forward-compatible model ids
    can still be tested explicitly instead of being rewritten before the call.
    """
    from src.model_capabilities import capability_for

    capability = capability_for(model)
    if capability is None or capability.provider != provider:
        return tuple(option.id for option in EFFORT_OPTIONS[provider])
    return ("default", *capability.effort_options)


def is_valid_effort(provider: Provider, effort: str, *, model: str | None = None) -> bool:
    options = effort_ids_for_model(provider, model) if model else tuple(
        option.id for option in EFFORT_OPTIONS[provider]
    )
    return effort in options


def route_capability_warnings(
    provider: Provider, model: str, effort: str, *, auth_mode: str | None
) -> list[str]:
    """Auth-mode-aware, NON-blocking capability warnings for a saved route. The model
    catalog is per (provider, auth_mode) — what serves an api_key may differ from what
    the subscription/OAuth backend serves — so a route saved against the api_key seed can
    be wrong for the ACTIVE auth mode. ``auth_mode`` = the active credential's auth_type
    for ``provider`` (None if no active credential / not resolvable). Warnings, not errors:
    the catalog allows custom ids and discovery may be stale, so we inform, never block."""
    out: list[str] = []
    if auth_mode == "chatgpt_oauth":
        # The ChatGPT backend's model set differs from the API-key catalog; seed
        # membership proves nothing here, so point the user at live discovery.
        out.append(
            f"The active OpenAI credential is a ChatGPT subscription (chatgpt_oauth); its available "
            f"models come from the ChatGPT backend, not the API-key catalog — confirm '{model}' via "
            f"discovery (列出此 key 可見模型)."
        )
    return out


def model_provider(model: str) -> Provider | None:
    lowered = model.strip().lower()
    if lowered.startswith("claude-"):
        return "anthropic"
    if lowered.startswith("gpt-") or lowered.startswith("o"):
        return "openai"
    return None


def default_model_for(provider: Provider, task: TaskId) -> str:
    for info in TASKS:
        if info.id == task and info.default_provider == provider:
            return info.recommended_model
    for model in MODEL_CATALOG:
        if model.provider == provider and task in model.recommended_for:
            return model.id
    return "claude-opus-4-8" if provider == "anthropic" else "gpt-5.5"


def is_seed_model(provider: Provider, model: str) -> bool:
    return any(m.provider == provider and m.id == model for m in MODEL_CATALOG)
