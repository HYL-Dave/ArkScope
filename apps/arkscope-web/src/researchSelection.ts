import type {
  CredentialAuthType,
  ExplicitResearchEffort,
  ModelCatalog,
  ModelProvider,
} from "./api";
import { modelProviderReason, optionReason } from "./modelPicker";
import { effortOptionsForModel, isTaskRouteEffort, taskRouteBlocker } from "./researchModels";

export interface ResearchTuple {
  provider: ModelProvider;
  model: string;
  effort: string | null;
}

export interface ExplicitResearchTuple extends ResearchTuple {
  effort: ExplicitResearchEffort;
}

export type ResearchSelectionProvenance = "thread" | "explicit" | "settings" | "user";

interface StorageReader {
  getItem(key: string): string | null;
}

interface StorageWriter extends StorageReader {
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface SelectionSemantics {
  authMode: CredentialAuthType | null;
  quotaKind: "subscription" | "api" | null;
}

export type ResearchSelectionResult = SelectionSemantics & (
  | {
      state: "ready";
      tuple: ExplicitResearchTuple;
      provenance: ResearchSelectionProvenance;
      reasonCode: null;
    }
  | {
      state: "blocked";
      tuple: ResearchTuple;
      provenance: ResearchSelectionProvenance;
      reasonCode: string;
    }
  | {
      state: "needs_selection";
      tuple: null;
      provenance: null;
      reasonCode: null;
    }
);

export const RESEARCH_SELECTION_STORAGE_KEY = "arkscope.aiResearch.explicitSelection.v1";

export function quotaKindForAuthMode(
  authMode: string | null,
): "subscription" | "api" | null {
  switch (authMode) {
    case "chatgpt_oauth":
    case "claude_code_oauth":
      return "subscription";
    case "api_key":
    case "api_key_pool":
      return "api";
    default:
      return null;
  }
}

const isProvider = (value: unknown): value is ModelProvider =>
  value === "openai" || value === "anthropic";

function normalizeTuple(value: unknown): ResearchTuple | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Partial<ResearchTuple>;
  if (!isProvider(row.provider)) return null;
  const model = typeof row.model === "string" ? row.model.trim() : "";
  const effort = typeof row.effort === "string" ? row.effort.trim() || null : null;
  if (!model) return null;
  return { provider: row.provider, model, effort };
}

function normalizeExplicitTuple(value: unknown): ExplicitResearchTuple | null {
  const tuple = normalizeTuple(value);
  if (!tuple || !tuple.effort || !isTaskRouteEffort(tuple.effort)) return null;
  return { ...tuple, effort: tuple.effort };
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
): ExplicitResearchTuple | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(RESEARCH_SELECTION_STORAGE_KEY);
    if (!raw) return null;
    const envelope = JSON.parse(raw) as { version?: unknown; tuple?: unknown };
    if (envelope.version !== 1) return null;
    return normalizeExplicitTuple(envelope.tuple);
  } catch {
    return null;
  }
}

export function writeExplicitResearchSelection(
  tuple: ExplicitResearchTuple,
  storage: StorageWriter | null = defaultStorage(),
): void {
  const normalized = normalizeExplicitTuple(tuple);
  if (!storage || !normalized) return;
  try {
    storage.setItem(RESEARCH_SELECTION_STORAGE_KEY, JSON.stringify({ version: 1, tuple: normalized }));
  } catch {
    // Storage is an ergonomic preference only; a denied write must not break research.
  }
}

function selectionSemantics(authMode: CredentialAuthType | null): SelectionSemantics {
  return {
    authMode,
    quotaKind: quotaKindForAuthMode(authMode),
  };
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
    ...selectionSemantics(authMode),
  };
}

function defaultResearchSelection(): ExplicitResearchTuple {
  return { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" };
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
  userSelection?: ExplicitResearchTuple | null;
  preferenceStorage?: StorageReader | null;
  sdkAvailability?: Partial<Record<ModelProvider, boolean>>;
}): ResearchSelectionResult {
  let tuple: ResearchTuple | null = normalizeExplicitTuple(userSelection);
  let provenance: ResearchSelectionProvenance | null = tuple ? "user" : null;

  if (!tuple && hasActiveThread && threadSelection === undefined) {
    return {
      state: "needs_selection",
      tuple: null,
      provenance: null,
      reasonCode: null,
      authMode: null,
      quotaKind: null,
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
    tuple = defaultResearchSelection();
    provenance = "explicit";
  }
  if (!tuple || !provenance) {
    return {
      state: "needs_selection",
      tuple: null,
      provenance: null,
      reasonCode: null,
      authMode: null,
      quotaKind: null,
    };
  }

  const context = catalog.effective?.providers?.[tuple.provider] ?? null;
  const providerBlock = catalog.effective?.tasks.ai_research?.providers?.[tuple.provider];
  const providerReason = modelProviderReason(context, providerBlock);
  const authMode = context?.auth_mode ?? null;
  if (providerReason) return blocked(tuple, provenance, providerReason, authMode);
  if (!providerBlock) return blocked(tuple, provenance, "discovery_unavailable", authMode);

  const routeBlocker = taskRouteBlocker(catalog, {
    provider: tuple.provider,
    model: tuple.model,
    effort: tuple.effort ?? "",
  });
  if (routeBlocker === "model_retired") {
    return blocked(tuple, provenance, routeBlocker, authMode);
  }

  const selected = providerBlock.models.find((entry) => entry.id === tuple!.model);
  if (!selected) return blocked(tuple, provenance, "model_not_visible", authMode);
  const selectedReason = optionReason(selected, null);
  if (selectedReason) return blocked(tuple, provenance, selectedReason, authMode);

  if (!tuple.effort || tuple.effort === "default" || tuple.effort === "none") {
    return blocked(tuple, provenance, "effort_required", authMode);
  }
  const supported = effortOptionsForModel(
    catalog,
    tuple.provider,
    tuple.model,
    selected.effort_options,
  ).some((option) => option.id === tuple!.effort);
  if (!supported || routeBlocker === "effort_required") {
    return blocked(tuple, provenance, "effort_not_supported", authMode);
  }

  if (sdkAvailability && sdkAvailability[tuple.provider] !== true) {
    return blocked(tuple, provenance, "runtime_unavailable", authMode);
  }

  return {
    state: "ready",
    tuple: tuple as ExplicitResearchTuple,
    provenance,
    reasonCode: null,
    ...selectionSemantics(authMode),
  };
}

export async function loadResearchThreadSelection(
  threadId: string,
  loader: (id: string) => Promise<unknown>,
): Promise<ResearchTuple | null> {
  const body = await loader(threadId);
  if (body === null) return null;
  const tuple = normalizeTuple(body);
  if (!tuple) throw new Error("research selection response is invalid");
  return tuple;
}
