import type {
  CredentialAuthType,
  ModelCatalog,
  ModelProvider,
} from "./api";
import { modelProviderReason, optionReason } from "./modelPicker";
import { MODEL_UX_LABELS } from "./modelRoutingUx";
import { effortOptionsForModel } from "./researchModels";

export interface ResearchTuple {
  provider: ModelProvider;
  model: string;
  effort: string;
}

export type ResearchSelectionProvenance = "thread" | "explicit" | "settings" | "user";

interface StorageReader {
  getItem(key: string): string | null;
}

interface StorageWriter extends StorageReader {
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface SelectionPresentation {
  authMode: CredentialAuthType | null;
  authLabel: string | null;
  billingCopy: string | null;
}

export type ResearchSelectionResult = SelectionPresentation & (
  | {
      state: "ready";
      tuple: ResearchTuple;
      provenance: ResearchSelectionProvenance;
      reasonCode: null;
      reasonLabel: null;
    }
  | {
      state: "blocked";
      tuple: ResearchTuple;
      provenance: ResearchSelectionProvenance;
      reasonCode: string;
      reasonLabel: string;
    }
  | {
      state: "needs_selection";
      tuple: null;
      provenance: null;
      reasonCode: null;
      reasonLabel: null;
    }
);

export const RESEARCH_SELECTION_STORAGE_KEY = "arkscope.aiResearch.explicitSelection.v1";

const isProvider = (value: unknown): value is ModelProvider =>
  value === "openai" || value === "anthropic";

function normalizeTuple(value: unknown): ResearchTuple | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Partial<ResearchTuple>;
  if (!isProvider(row.provider)) return null;
  const model = typeof row.model === "string" ? row.model.trim() : "";
  const effort = typeof row.effort === "string" ? row.effort.trim() : "";
  if (!model || !effort) return null;
  return { provider: row.provider, model, effort };
}

function defaultStorage(): StorageWriter | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readExplicitResearchSelection(
  storage: StorageReader | null = defaultStorage(),
): ResearchTuple | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(RESEARCH_SELECTION_STORAGE_KEY);
    if (!raw) return null;
    const envelope = JSON.parse(raw) as { version?: unknown; tuple?: unknown };
    if (envelope.version !== 1) return null;
    return normalizeTuple(envelope.tuple);
  } catch {
    return null;
  }
}

export function writeExplicitResearchSelection(
  tuple: ResearchTuple,
  storage: StorageWriter | null = defaultStorage(),
): void {
  const normalized = normalizeTuple(tuple);
  if (!storage || !normalized) return;
  try {
    storage.setItem(RESEARCH_SELECTION_STORAGE_KEY, JSON.stringify({ version: 1, tuple: normalized }));
  } catch {
    // Storage is an ergonomic preference only; a denied write must not break research.
  }
}

function presentation(authMode: CredentialAuthType | null): SelectionPresentation {
  if (!authMode) return { authMode: null, authLabel: null, billingCopy: null };
  const subscription = authMode === "chatgpt_oauth" || authMode === "claude_code_oauth";
  return {
    authMode,
    authLabel: MODEL_UX_LABELS.authModes[authMode] ?? authMode,
    billingCopy: subscription
      ? "使用訂閱額度，非 API 帳單"
      : "使用 API 額度，會計入 API 帳單",
  };
}

function reasonLabel(reasonCode: string): string {
  if (reasonCode === "effort_not_supported") return "此模型不支援已選 effort";
  if (reasonCode === "runtime_unavailable") return "此 provider 的執行環境目前不可用";
  return MODEL_UX_LABELS.reasons[reasonCode] ?? reasonCode;
}

function blocked(
  tuple: ResearchTuple,
  provenance: ResearchSelectionProvenance,
  reasonCode: string,
  authMode: CredentialAuthType | null,
): ResearchSelectionResult {
  return {
    state: "blocked",
    tuple,
    provenance,
    reasonCode,
    reasonLabel: reasonLabel(reasonCode),
    ...presentation(authMode),
  };
}

export function resolveResearchSelection({
  catalog,
  hasActiveThread,
  threadSelection,
  userSelection = null,
  preferenceStorage = defaultStorage(),
  sdkAvailability,
}: {
  catalog: ModelCatalog;
  hasActiveThread: boolean;
  threadSelection: ResearchTuple | null | undefined;
  userSelection?: ResearchTuple | null;
  preferenceStorage?: StorageReader | null;
  sdkAvailability?: Partial<Record<ModelProvider, boolean>>;
}): ResearchSelectionResult {
  let tuple: ResearchTuple | null = normalizeTuple(userSelection);
  let provenance: ResearchSelectionProvenance | null = tuple ? "user" : null;

  if (!tuple && hasActiveThread && threadSelection === undefined) {
    return {
      state: "needs_selection",
      tuple: null,
      provenance: null,
      reasonCode: null,
      reasonLabel: null,
      authMode: null,
      authLabel: null,
      billingCopy: null,
    };
  }
  if (!tuple && hasActiveThread && threadSelection) {
    tuple = normalizeTuple(threadSelection);
    provenance = "thread";
  }
  if (!tuple && !hasActiveThread) {
    tuple = readExplicitResearchSelection(preferenceStorage);
    if (tuple) provenance = "explicit";
  }
  if (!tuple) {
    const route = catalog.routes.ai_research;
    tuple = normalizeTuple({
      provider: route?.provider,
      model: route?.model,
      effort: route?.effort || "default",
    });
    provenance = "settings";
  }
  if (!tuple || !provenance) {
    return {
      state: "needs_selection",
      tuple: null,
      provenance: null,
      reasonCode: null,
      reasonLabel: null,
      authMode: null,
      authLabel: null,
      billingCopy: null,
    };
  }

  const context = catalog.effective?.providers?.[tuple.provider] ?? null;
  const providerBlock = catalog.effective?.tasks.ai_research?.providers?.[tuple.provider];
  const providerReason = modelProviderReason(context, providerBlock);
  const authMode = context?.auth_mode ?? null;
  if (providerReason) return blocked(tuple, provenance, providerReason, authMode);
  if (!providerBlock) return blocked(tuple, provenance, "discovery_unavailable", authMode);

  const selected = providerBlock.models.find((entry) => entry.id === tuple!.model);
  if (!selected) return blocked(tuple, provenance, "model_not_visible", authMode);
  const selectedReason = optionReason(selected, null);
  if (selectedReason) return blocked(tuple, provenance, selectedReason, authMode);

  if (tuple.effort !== "default") {
    const supported = effortOptionsForModel(
      catalog,
      tuple.provider,
      tuple.model,
      selected.effort_options,
    ).some((option) => option.id === tuple!.effort);
    if (!supported) return blocked(tuple, provenance, "effort_not_supported", authMode);
  }

  if (sdkAvailability && sdkAvailability[tuple.provider] !== true) {
    return blocked(tuple, provenance, "runtime_unavailable", authMode);
  }

  return {
    state: "ready",
    tuple,
    provenance,
    reasonCode: null,
    reasonLabel: null,
    ...presentation(authMode),
  };
}

export async function loadResearchThreadSelection(
  threadId: string,
  fetcher: typeof fetch = fetch,
): Promise<ResearchTuple | null> {
  const base = typeof window !== "undefined"
    ? (window.arkscope?.apiBase ?? (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8420")
    : "http://127.0.0.1:8420";
  const response = await fetcher(`${base}/research/threads/${encodeURIComponent(threadId)}/selection`);
  if (!response.ok) throw new Error(`research selection request failed (${response.status})`);
  const body = await response.json() as unknown;
  if (body === null) return null;
  const tuple = normalizeTuple(body);
  if (!tuple) throw new Error("research selection response is invalid");
  return tuple;
}
