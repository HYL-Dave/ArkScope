import type {
  SecurityLifecycleActionProposal,
  SecurityLifecycleInvestigationRun,
  SecurityLifecycleSourcePresence,
  SecurityLifecycleWorkflowState,
} from "../api";
import enExplore from "../i18n/resources/en/explore";
import zhHantExplore from "../i18n/resources/zh-Hant/explore";

export type LifecycleLocale = "en" | "zh-Hant";

function lifecycleCopy(locale: LifecycleLocale) {
  return locale === "en" ? enExplore.lifecycle : zhHantExplore.lifecycle;
}

export function lifecycleWorkflowLabel(
  value: SecurityLifecycleWorkflowState,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).workflow;
  if (value === "investigating") return copy.investigating;
  if (value === "evidence_ready") return copy.evidenceReady;
  if (value === "reviewed_inconclusive") return copy.reviewedInconclusive;
  if (value === "resolved") return copy.resolved;
  return copy.unresolved;
}

export function lifecycleSourcePresenceLabel(
  value: SecurityLifecycleSourcePresence,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).states;
  const sourcePresent = value === "present";
  if (sourcePresent) return copy.sourcePresent;
  return copy.sourceMissing;
}

export function formatAssessmentDecimal(
  value: string | null | undefined,
  unit?: string | null,
  locale: LifecycleLocale = "en",
): string {
  if (!value) return lifecycleCopy(locale).confidence.unknown;
  return unit ? `${unit} ${value}` : value;
}

export function safeEvidenceUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function lifecycleProposalLabel(
  actionType: SecurityLifecycleActionProposal["action_type"],
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).proposalTypes;
  if (actionType === "archive_manual_memberships") return copy.archiveManualMemberships;
  if (actionType === "keep_tracking") return copy.keepTracking;
  if (actionType === "no_action") return copy.noAction;
  if (actionType === "notify") return copy.notify;
  if (actionType === "remap_symbol") return copy.remapSymbol;
  return copy.reviewPortfolioPosition;
}

export function actionProposalPresentation(
  proposal: Pick<SecurityLifecycleActionProposal, "action_type" | "status" | "block_reason">,
  locale: LifecycleLocale,
): { label: string; state: string; canApply: false; blockReason: string | null } {
  return {
    label: lifecycleProposalLabel(proposal.action_type, locale),
    state: lifecycleCopy(locale).states.recommendationOnly,
    canApply: false,
    blockReason: proposal.block_reason,
  };
}

export function lifecycleRunStatusLabel(
  status: SecurityLifecycleInvestigationRun["status"],
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).runStatuses;
  if (status === "queued") return copy.queued;
  if (status === "running") return copy.running;
  if (status === "succeeded") return copy.succeeded;
  return copy.failed;
}

export function lifecycleErrorPresentation(
  error: unknown,
  locale: LifecycleLocale,
): { code: string; message: string } {
  const code = error && typeof error === "object" && "code" in error
    && typeof error.code === "string" && error.code.trim()
    ? error.code.trim()
    : "security_lifecycle_unavailable";
  const copy = lifecycleCopy(locale).errors;
  let message: string = copy.requestFailed;
  if (code === "usage_limit_reached") message = copy.usageLimitReached;
  else if (code === "rate_limited") message = copy.rateLimited;
  else if (code === "adapter_unavailable") message = copy.adapterUnavailable;
  else if (
    code === "security_lifecycle_market_store_unavailable"
    || code === "security_lifecycle_profile_store_unavailable"
  ) message = copy.dataUnavailable;
  return {
    code,
    message,
  };
}
