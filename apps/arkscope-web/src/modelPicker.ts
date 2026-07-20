import type {
  EffectiveProviderModelEntry,
  EffectiveProviderModels,
  EffectiveProviderSummary,
  ModelOption,
  ModelProvider,
} from "./api";
import { MODEL_UX_LABELS, type DraftRouteValue } from "./modelRoutingUx";

export type ModelEntryGroupId = "available" | "visible_disabled" | "advanced" | "current";

export type ModelEntryWithReason = EffectiveProviderModelEntry & {
  disabledReason: string | null;
  baseLabel: string;
  compatibility: "legacy_unverified" | null;
};

export type ModelEntryGroup = {
  id: ModelEntryGroupId;
  label: string;
  entries: ModelEntryWithReason[];
};

type ModelEntryInput = EffectiveProviderModelEntry & Partial<Pick<
  ModelEntryWithReason,
  "baseLabel" | "compatibility"
>>;

export function modelProviderReason(
  context: EffectiveProviderSummary | null | undefined,
  providerBlock: EffectiveProviderModels | null | undefined,
): string | null {
  if (!context) return "missing_active_credential";
  if (providerBlock?.executable === false) {
    return providerBlock.reason_code ?? "task_auth_mode_unsupported";
  }
  return providerBlock?.reason_code ?? null;
}

export function optionReason(
  entry: EffectiveProviderModelEntry,
  providerReason: string | null,
): string | null {
  if (providerReason) return providerReason;
  if (!entry.eligible) return entry.reason_code ?? "task_capability_missing";
  if (entry.visible_to_credential === false && entry.status !== "route") {
    return "model_not_visible";
  }
  return null;
}

export function groupedModelEntries(
  entries: ModelEntryInput[],
  providerReason: string | null,
): ModelEntryGroup[] {
  const withReason = entries.map((entry) => ({
    ...entry,
    disabledReason: optionReason(entry, providerReason),
    baseLabel: entry.baseLabel ?? entry.label,
    compatibility: entry.compatibility ?? null,
  }));
  return [
    {
      id: "available",
      label: MODEL_UX_LABELS.groups[0],
      entries: withReason.filter((entry) => entry.status === "visible" && !entry.disabledReason),
    },
    {
      id: "visible_disabled",
      label: MODEL_UX_LABELS.groups[1],
      entries: withReason.filter((entry) => entry.status === "visible" && !!entry.disabledReason),
    },
    {
      id: "advanced",
      label: MODEL_UX_LABELS.groups[2],
      entries: withReason.filter((entry) => entry.status === "advanced" || entry.status === "seed"),
    },
    {
      id: "current",
      label: MODEL_UX_LABELS.groups[3],
      entries: withReason.filter((entry) => entry.status === "route"),
    },
  ];
}

export function compatEntries(
  provider: ModelProvider,
  row: Pick<DraftRouteValue, "model">,
  modelsByProvider: Record<ModelProvider, ModelOption[]>,
): ModelEntryInput[] {
  const entries: ModelEntryInput[] = (modelsByProvider[provider] ?? []).map((model) => ({
    id: model.id,
    label: `${model.label} · 未驗證（舊 sidecar 相容模式）`,
    baseLabel: model.label,
    compatibility: "legacy_unverified",
    status: "advanced",
    visible_to_credential: null,
    eligible: true,
    reason_code: null,
    thinking_mode: "none",
    effort_options: model.effort_options,
  }));
  if (row.model && !entries.some((entry) => entry.id === row.model)) {
    entries.push({
      id: row.model,
      label: `${row.model} · 未驗證（舊 sidecar 相容模式）`,
      baseLabel: row.model,
      compatibility: "legacy_unverified",
      status: "route",
      visible_to_credential: null,
      eligible: true,
      reason_code: "model_not_in_registry",
      thinking_mode: "none",
      effort_options: undefined,
    });
  }
  return entries;
}
