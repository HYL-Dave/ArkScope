import type { TFunction } from "i18next";

import {
  modelAuthModeLabel,
  modelReasonLabel,
  type ModelCommonT,
} from "../modelRoutingUx";
import { RESEARCH_DISCONNECT_ERROR_CODE } from "../researchReducer";

export { RESEARCH_DISCONNECT_ERROR_CODE };

export type ResearchT = TFunction<"research">;

export interface ResearchSelectionPresentation {
  provenanceLabel: string | null;
  authLabel: string | null;
  billingCopy: string | null;
  reasonLabel: string | null;
}

export interface ResearchStatusPresentation {
  state: "running" | "ready" | "failed" | "interrupted" | "empty";
  label: string;
}

export interface ResearchProgressCopy {
  stageLabel: string;
  resultLabel: string;
}

export interface ResearchSuggestedPrompt {
  id: "smci" | "cls" | "mxl" | "nvda";
  ticker: "SMCI" | "CLS" | "MXL" | "NVDA";
  text: string;
}

function selectionProvenanceLabel(value: string | null, t: ResearchT): string | null {
  switch (value) {
    case null:
      return null;
    case "thread":
      return t(($) => $.workspace.provenanceThread);
    case "settings":
      return t(($) => $.workspace.provenanceSettings);
    case "explicit":
    case "user":
      return t(($) => $.workspace.provenanceExplicit);
    default:
      return value;
  }
}

function selectionBillingCopy(value: "subscription" | "api" | null, t: ResearchT): string | null {
  switch (value) {
    case "subscription":
      return t(($) => $.selection.subscriptionBilling);
    case "api":
      return t(($) => $.selection.apiBilling);
    default:
      return null;
  }
}

function selectionReasonLabel(
  value: string | null,
  researchT: ResearchT,
  commonT: ModelCommonT,
): string | null {
  switch (value) {
    case null:
      return null;
    case "effort_not_supported":
      return researchT(($) => $.selection.effortUnsupported);
    case "runtime_unavailable":
      return researchT(($) => $.selection.runtimeUnavailable);
    default:
      return modelReasonLabel(value, commonT);
  }
}

export function presentResearchSelection(
  input: {
    provenance: string | null;
    authMode: string | null;
    quotaKind: "subscription" | "api" | null;
    reasonCode: string | null;
  },
  researchT: ResearchT,
  commonT: ModelCommonT,
): ResearchSelectionPresentation {
  return {
    provenanceLabel: selectionProvenanceLabel(input.provenance, researchT),
    authLabel: input.authMode ? modelAuthModeLabel(input.authMode, commonT) : null,
    billingCopy: selectionBillingCopy(input.quotaKind, researchT),
    reasonLabel: selectionReasonLabel(input.reasonCode, researchT, commonT),
  };
}

export function researchHistoryStatus(
  status: string | null,
  t: ResearchT,
): ResearchStatusPresentation {
  switch (status) {
    case "queued":
      return { state: "running", label: t(($) => $.history.statusQueued) };
    case "running":
      return { state: "running", label: t(($) => $.history.statusRunning) };
    case "succeeded":
      return { state: "ready", label: t(($) => $.history.statusSucceeded) };
    case "failed":
      return { state: "failed", label: t(($) => $.history.statusFailed) };
    case "cancelled":
      return { state: "interrupted", label: t(($) => $.history.statusCancelled) };
    case "interrupted":
      return { state: "interrupted", label: t(($) => $.history.statusInterrupted) };
    case null:
      return { state: "empty", label: t(($) => $.history.statusNoRun) };
    default:
      return { state: "empty", label: status };
  }
}

export function researchEvidenceStatusLabel(status: string, t: ResearchT): string {
  switch (status) {
    case "running":
      return t(($) => $.evidence.statusRunning);
    case "complete":
      return t(($) => $.evidence.statusComplete);
    case "recorded":
      return t(($) => $.evidence.statusRecorded);
    default:
      return status;
  }
}

function researchTokenLabel(key: string, t: ResearchT): string {
  const normalized = key.toLowerCase();
  if (normalized.includes("cache_creation") || normalized.includes("cache_write")) {
    return t(($) => $.evidence.cacheWriteTokens);
  }
  if (normalized.includes("cache_read") || normalized.includes("cached")) {
    return t(($) => $.evidence.cacheReadTokens);
  }
  if (normalized.includes("total_input")) return t(($) => $.evidence.totalInputTokens);
  if (normalized.includes("total_output")) return t(($) => $.evidence.totalOutputTokens);
  if (normalized.includes("last_input")) return t(($) => $.evidence.lastInputTokens);
  if (normalized === "total_tokens") return t(($) => $.evidence.totalTokens);
  if (normalized.includes("input") || normalized.includes("prompt")) {
    return t(($) => $.evidence.inputTokens);
  }
  if (normalized.includes("output") || normalized.includes("completion")) {
    return t(($) => $.evidence.outputTokens);
  }
  return key.replaceAll("_", " ");
}

export function researchEvidenceTokenRows(
  usage: Record<string, number> | null,
  t: ResearchT,
): Array<{ key: string; label: string; value: number }> {
  if (!usage) return [];
  return Object.entries(usage)
    .filter(([key, value]) => (
      Number.isFinite(value)
      && /(input|output|prompt|completion|cache|total).*token|token.*(input|output|prompt|completion|cache|total)/i.test(key)
    ))
    .map(([key, value]) => ({ key, label: researchTokenLabel(key, t), value }));
}

export function researchEvidenceTimingLabel(field: string, t: ResearchT): string {
  switch (field) {
    case "created":
      return t(($) => $.evidence.createdAt);
    case "started":
      return t(($) => $.evidence.startedAt);
    case "completed":
      return t(($) => $.evidence.completedAt);
    case "turn_saved":
      return t(($) => $.evidence.turnSaved);
    case "model_elapsed":
      return t(($) => $.evidence.modelElapsed);
    default:
      return field;
  }
}

export function researchEmptyResponseLabel(t: ResearchT): string {
  return t(($) => $.workspace.emptyResponse);
}

export function researchConnectionLabel(outcome: string, t: ResearchT): string {
  return outcome === RESEARCH_DISCONNECT_ERROR_CODE
    ? t(($) => $.connection.interrupted)
    : outcome;
}

export function researchProgressCopy(stage: string, t: ResearchT): ResearchProgressCopy {
  switch (stage) {
    case "creating":
      return {
        stageLabel: t(($) => $.progress.creating),
        resultLabel: t(($) => $.progress.resultAfterCreation),
      };
    case "queued":
      return {
        stageLabel: t(($) => $.progress.queued),
        resultLabel: t(($) => $.progress.resultAfterCompletion),
      };
    case "running":
      return {
        stageLabel: t(($) => $.progress.running),
        resultLabel: t(($) => $.progress.resultAfterCompletion),
      };
    case "succeeded":
      return {
        stageLabel: t(($) => $.progress.succeeded),
        resultLabel: t(($) => $.progress.resultSaved),
      };
    case "failed":
      return {
        stageLabel: t(($) => $.progress.failed),
        resultLabel: t(($) => $.progress.partialResultSaved),
      };
    case "interrupted":
      return {
        stageLabel: t(($) => $.progress.interrupted),
        resultLabel: t(($) => $.progress.partialResultSaved),
      };
    case "cancelled":
      return {
        stageLabel: t(($) => $.progress.cancelled),
        resultLabel: t(($) => $.progress.partialResultSaved),
      };
    default:
      return { stageLabel: stage, resultLabel: stage };
  }
}

export function researchSuggestedPrompts(t: ResearchT): ResearchSuggestedPrompt[] {
  return [
    { id: "smci", ticker: "SMCI", text: t(($) => $.workspace.suggestedSmci) },
    { id: "cls", ticker: "CLS", text: t(($) => $.workspace.suggestedCls) },
    { id: "mxl", ticker: "MXL", text: t(($) => $.workspace.suggestedMxl) },
    { id: "nvda", ticker: "NVDA", text: t(($) => $.workspace.suggestedNvda) },
  ];
}

export function presentResearchRoute(input: {
  provider?: string | null;
  model?: string | null;
  effort?: string | null;
  runId?: string | null;
  errorCode?: string | null;
}, t: ResearchT): {
  provider: string | null;
  providerLabel: string;
  model: string | null;
  modelLabel: string;
  effort: string | null;
  effortLabel: string;
  runId: string | null;
  errorCode: string | null;
} {
  const provider = input.provider ?? null;
  const model = input.model ?? null;
  const effort = input.effort ?? null;
  const unknown = t(($) => $.evidence.unknownFallback);
  return {
    provider,
    providerLabel: provider ?? unknown,
    model,
    modelLabel: model ?? unknown,
    effort,
    effortLabel: effort ?? unknown,
    runId: input.runId ?? null,
    errorCode: input.errorCode ?? null,
  };
}
