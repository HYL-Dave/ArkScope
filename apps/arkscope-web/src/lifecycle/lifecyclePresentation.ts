import type {
  SecurityLifecycleActionProposal,
  SecurityLifecycleAcceptanceAuthority,
  SecurityLifecycleActionReadiness,
  SecurityLifecycleAssessment,
  SecurityLifecycleAssessmentAuthor,
  SecurityLifecycleAutomationBlockerCode,
  SecurityLifecycleAutomationMethod,
  SecurityLifecycleAutomationOperatorDetail,
  SecurityLifecycleConfidence,
  SecurityLifecycleEventType,
  SecurityLifecycleEvidenceSourceFamily,
  SecurityLifecycleFactType,
  SecurityLifecycleInvestigationRun,
  SecurityLifecycleListingAuthority,
  SecurityLifecycleListingStatus,
  SecurityLifecycleOutcome,
  SecurityLifecycleProposalBlockReason,
  SecurityLifecycleProposalType,
  SecurityLifecycleRelevance,
  SecurityLifecycleSourcePresence,
  SecurityLifecycleTrackingSource,
  SecurityLifecycleWorkflowState,
  SecurityLifecycleDecisionTier,
  SecurityLifecycleDisposition,
  SecurityLifecycleDispositionReason,
  SecurityLifecycleSourceFamilyState,
} from "../api";
import enExplore from "../i18n/resources/en/explore";
import zhHantExplore from "../i18n/resources/zh-Hant/explore";

export type LifecycleLocale = "en" | "zh-Hant";

function lifecycleCopy(locale: LifecycleLocale) {
  return locale === "en" ? enExplore.lifecycle : zhHantExplore.lifecycle;
}

function closedLifecycleLabel<Value extends string>(
  value: string,
  labels: Record<Value, string>,
  locale: LifecycleLocale,
): string {
  return Object.prototype.hasOwnProperty.call(labels, value)
    ? labels[value as Value]
    : lifecycleCopy(locale).states.unknownValue;
}

export function lifecycleDecisionTierLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).decisionTiers;
  return closedLifecycleLabel<SecurityLifecycleDecisionTier>(value, {
    verified_automatic: copy.verifiedAutomatic,
    review_suggested: copy.reviewSuggested,
  }, locale);
}

export function lifecycleActionReadinessLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).actionReadiness;
  return closedLifecycleLabel<SecurityLifecycleActionReadiness>(value, {
    not_applicable: copy.notApplicable,
    waiting_effective_date: copy.waitingEffectiveDate,
    waiting_market_confirmation: copy.waitingMarketConfirmation,
    waiting_transition_revalidation: copy.waitingTransitionRevalidation,
    transition_eligible: copy.transitionEligible,
    action_blocked: copy.actionBlocked,
  }, locale);
}

export function lifecycleDispositionLabel(
  value: SecurityLifecycleDisposition,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).dispositions;
  const labels: Record<SecurityLifecycleDisposition, string> = {
    confirmed_monitoring: copy.confirmedMonitoring,
    confirmed_effective: copy.confirmedEffective,
    not_confirmed_yet: copy.notConfirmedYet,
    exception_required: copy.exceptionRequired,
  };
  return labels[value] ?? lifecycleCopy(locale).states.unknownValue;
}

export function lifecycleDispositionReasonLabel(
  value: SecurityLifecycleDispositionReason,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).dispositionReasons;
  return closedLifecycleLabel<SecurityLifecycleDispositionReason>(value, {
    awaiting_initial_automation: copy.awaitingInitialAutomation,
    automation_running: copy.automationRunning,
    waiting_effective_date: copy.waitingEffectiveDate,
    waiting_market_confirmation: copy.waitingMarketConfirmation,
    waiting_transition_revalidation: copy.waitingTransitionRevalidation,
    retryable_source_unavailable: copy.retryableSourceUnavailable,
    event_completion_not_confirmed: copy.eventCompletionNotConfirmed,
    not_confirmed_as_of: copy.notConfirmedAsOf,
    source_missing: copy.sourceMissing,
    source_conflict: copy.sourceConflict,
    ambiguous_event: copy.ambiguousEvent,
    nonretryable_provider_failure: copy.nonretryableProviderFailure,
    automation_failure: copy.automationFailure,
    automation_finalization_failure: copy.automationFinalizationFailure,
    resolved_no_change: copy.resolvedNoChange,
    resolved_assessment: copy.resolvedAssessment,
    transition_applied: copy.transitionApplied,
    transition_reversed: copy.transitionReversed,
    transition_cancelled: copy.transitionCancelled,
    transition_needs_review: copy.transitionNeedsReview,
    reviewed_inconclusive: copy.reviewedInconclusive,
  }, locale);
}

export function lifecycleSourceFamilyStateLabel(
  value: SecurityLifecycleSourceFamilyState,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).sourceFamilyStates;
  return closedLifecycleLabel<SecurityLifecycleSourceFamilyState>(value, {
    confirmed: copy.confirmed,
    present: copy.present,
    missing: copy.missing,
    unavailable: copy.unavailable,
    conflict: copy.conflict,
  }, locale);
}

type KnownAutomationRuleId =
  | "lifecycle.terminal_delisting"
  | "lifecycle.no_identity_change"
  | "lifecycle.simple_symbol_continuation"
  | "lifecycle.venue_transfer"
  | "lifecycle.ma_review"
  | "lifecycle.source_conflict"
  | "lifecycle.insufficient_identity_facts";

type AutomationNarrativeKey =
  | "terminalDelisting"
  | "noIdentityChange"
  | "simpleSymbolContinuation"
  | "venueTransfer"
  | "maReview"
  | "sourceConflict"
  | "insufficientIdentityFacts";

const AUTOMATION_NARRATIVE_KEYS: Record<KnownAutomationRuleId, AutomationNarrativeKey> = {
  "lifecycle.terminal_delisting": "terminalDelisting",
  "lifecycle.no_identity_change": "noIdentityChange",
  "lifecycle.simple_symbol_continuation": "simpleSymbolContinuation",
  "lifecycle.venue_transfer": "venueTransfer",
  "lifecycle.ma_review": "maReview",
  "lifecycle.source_conflict": "sourceConflict",
  "lifecycle.insufficient_identity_facts": "insufficientIdentityFacts",
};

function narrativeTemplate(
  template: string,
  values: Record<string, string>,
): string {
  return template.replace(/\{\{([a-zA-Z]+)\}\}/g, (_, key: string) => (
    values[key] ?? ""
  ));
}

export function lifecycleAutomationNarrative(
  assessment: SecurityLifecycleAssessment,
  ticker: string,
  locale: LifecycleLocale,
): { conclusion: string; impact: string } {
  if (assessment.author !== "automation") {
    return {
      conclusion: assessment.conclusion,
      impact: assessment.impact_summary,
    };
  }
  const copy = lifecycleCopy(locale);
  const ruleId = assessment.rule_id ?? copy.states.unknownValue;
  const key = Object.prototype.hasOwnProperty.call(AUTOMATION_NARRATIVE_KEYS, ruleId)
    ? AUTOMATION_NARRATIVE_KEYS[ruleId as KnownAutomationRuleId]
    : null;
  const template = key
    ? copy.automationNarratives[key]
    : copy.automationNarratives.unknownRule;
  const values = {
    ticker,
    successor: assessment.successor_ticker ?? copy.states.unknownValue,
    venue: assessment.destination_venue ?? copy.states.unknownValue,
    rule: ruleId,
  };
  const structured = [
    [copy.fields.counterpartyName, assessment.counterparty_name],
    [copy.fields.counterpartyTicker, assessment.counterparty_ticker],
    [copy.fields.successorTicker, assessment.successor_ticker],
    [copy.fields.destinationVenue, assessment.destination_venue],
    [copy.fields.effectiveDate, assessment.effective_date],
    [copy.fields.considerationCurrency, assessment.consideration_currency],
    [
      copy.fields.cashPerSecurity,
      assessment.cash_per_security_decimal
        ? formatAssessmentDecimal(
          assessment.cash_per_security_decimal,
          assessment.consideration_currency,
          locale,
        )
        : null,
    ],
    [copy.fields.exchangeRatio, assessment.exchange_ratio_decimal],
  ]
    .filter((entry): entry is [string, string] => Boolean(entry[1]))
    .map(([label, value]) => `${label}: ${value}`);
  const impact = narrativeTemplate(template.impact, values);
  return {
    conclusion: narrativeTemplate(template.conclusion, values),
    impact: structured.length > 0
      ? `${impact} ${copy.automationNarratives.structuredPrefix} ${structured.join(
        copy.automationNarratives.structuredSeparator,
      )}`
      : impact,
  };
}

export function lifecycleAssessmentAuthorLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).assessmentAuthors;
  return closedLifecycleLabel<SecurityLifecycleAssessmentAuthor>(value, {
    human: copy.human,
    legacy_review: copy.legacyReview,
    automation: copy.automation,
  }, locale);
}

export function lifecycleAutomationMethodLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).automationMethods;
  return closedLifecycleLabel<SecurityLifecycleAutomationMethod>(value, {
    deterministic_rule: copy.deterministicRule,
    model_assisted: copy.modelAssisted,
  }, locale);
}

export function lifecycleAcceptanceAuthorityLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).acceptanceAuthorities;
  return closedLifecycleLabel<SecurityLifecycleAcceptanceAuthority>(value, {
    human: copy.human,
    automation_policy: copy.automationPolicy,
    legacy_migration: copy.legacyMigration,
  }, locale);
}

export function lifecycleEvidenceSourceFamilyLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).evidenceFamilies;
  return closedLifecycleLabel<SecurityLifecycleEvidenceSourceFamily>(value, {
    regulator: copy.regulator,
    listing_authority: copy.listingAuthority,
    market_infrastructure: copy.marketInfrastructure,
    publisher: copy.publisher,
    general_web: copy.generalWeb,
    manual: copy.manual,
  }, locale);
}

export function lifecycleListingAuthorityLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).listingEvidence.authorities;
  return closedLifecycleLabel<SecurityLifecycleListingAuthority>(value, {
    nasdaq_trader: copy.nasdaqTrader,
    massive: copy.massive,
  }, locale);
}

export function lifecycleListingStatusLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).listingEvidence.statuses;
  return closedLifecycleLabel<SecurityLifecycleListingStatus>(value, {
    active: copy.active,
    inactive: copy.inactive,
    not_found: copy.notFound,
    unverified: copy.unverified,
  }, locale);
}

export function lifecycleFactTypeLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).factTypes;
  return closedLifecycleLabel<SecurityLifecycleFactType>(value, {
    source_ticker: copy.sourceTicker,
    successor_ticker: copy.successorTicker,
    source_venue: copy.sourceVenue,
    destination_venue: copy.destinationVenue,
    effective_date: copy.effectiveDate,
    security_class: copy.securityClass,
    issuer_cik: copy.issuerCik,
    transaction_structure: copy.transactionStructure,
    tracked_security_effect: copy.trackedSecurityEffect,
  }, locale);
}

type SecurityClassFactValue = "common_stock";
type TransactionStructureFactValue =
  | "asset_acquisition"
  | "cash"
  | "corporate_unification"
  | "mixed"
  | "security_class_change"
  | "spin_off"
  | "stock"
  | "unknown";
type TransactionTermsStatus = "not_extracted" | "partial" | "complete";
type TrackedSecurityEffectFactValue =
  | "terminal_delisting"
  | "symbol_change"
  | "venue_change_only"
  | "symbol_and_venue_change"
  | "no_identity_change"
  | "asset_acquisition_no_registrant_change";

export function lifecycleFactValueLabel(
  factType: string,
  value: unknown,
  locale: LifecycleLocale,
): string | null {
  const copy = lifecycleCopy(locale).factValues;
  if (factType === "transaction_structure") {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return lifecycleCopy(locale).states.unknownValue;
    }
    const transaction = value as Record<string, unknown>;
    if (typeof transaction.kind !== "string"
      || typeof transaction.terms_status !== "string") {
      return lifecycleCopy(locale).states.unknownValue;
    }
    const kind = closedLifecycleLabel<TransactionStructureFactValue>(
      transaction.kind,
      {
        asset_acquisition: copy.assetAcquisition,
        cash: copy.cashConsideration,
        corporate_unification: copy.corporateUnification,
        mixed: copy.mixedConsideration,
        security_class_change: copy.securityClassChange,
        spin_off: copy.spinOff,
        stock: copy.stockConsideration,
        unknown: copy.unknownTransaction,
      },
      locale,
    );
    const terms = closedLifecycleLabel<TransactionTermsStatus>(
      transaction.terms_status,
      {
        not_extracted: copy.termsNotExtracted,
        partial: copy.termsPartial,
        complete: copy.termsComplete,
      },
      locale,
    );
    return [kind, terms].join(copy.transactionSummarySeparator);
  }
  if (typeof value !== "string") return null;
  if (factType === "security_class") {
    return closedLifecycleLabel<SecurityClassFactValue>(value, {
      common_stock: copy.commonStock,
    }, locale);
  }
  if (factType === "tracked_security_effect") {
    return closedLifecycleLabel<TrackedSecurityEffectFactValue>(value, {
      terminal_delisting: copy.terminalDelisting,
      symbol_change: copy.symbolChange,
      venue_change_only: copy.venueChangeOnly,
      symbol_and_venue_change: copy.symbolAndVenueChange,
      no_identity_change: copy.noIdentityChange,
      asset_acquisition_no_registrant_change: copy.assetAcquisitionNoRegistrantChange,
    }, locale);
  }
  return null;
}

export function lifecycleAutomationBlockerLabel(
  value: string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).automationBlockers;
  return closedLifecycleLabel<SecurityLifecycleAutomationBlockerCode>(value, {
    sec_identity_unconfigured: copy.secIdentityUnconfigured,
    sec_governor_unavailable: copy.secGovernorUnavailable,
    sec_request_budget_exhausted: copy.secRequestBudgetExhausted,
    sec_rate_limited: copy.secRateLimited,
    sec_access_denied: copy.secAccessDenied,
    sec_transport_unavailable: copy.secTransportUnavailable,
    sec_document_unavailable: copy.secDocumentUnavailable,
    sec_evidence_insufficient: copy.secEvidenceInsufficient,
    internal_news_unavailable: copy.internalNewsUnavailable,
    internal_news_schema_mismatch: copy.internalNewsSchemaMismatch,
    ibkr_gateway_unavailable: copy.ibkrGatewayUnavailable,
    ibkr_contract_missing: copy.ibkrContractMissing,
    ibkr_contract_ambiguous: copy.ibkrContractAmbiguous,
    ibkr_entitlement_denied: copy.ibkrEntitlementDenied,
    market_confirmation_missing: copy.marketConfirmationMissing,
    listing_directory_unavailable: copy.listingDirectoryUnavailable,
    listing_directory_schema_mismatch: copy.listingDirectorySchemaMismatch,
    listing_directory_stale: copy.listingDirectoryStale,
    listing_status_unresolved: copy.listingStatusUnresolved,
    listing_authority_conflict: copy.listingAuthorityConflict,
    massive_credential_missing: copy.massiveCredentialMissing,
    massive_access_denied: copy.massiveAccessDenied,
    massive_rate_limited: copy.massiveRateLimited,
    massive_reference_unavailable: copy.massiveReferenceUnavailable,
    source_conflict: copy.sourceConflict,
    impact_context_requested: copy.impactContextRequested,
    transition_approval_changed: copy.transitionApprovalChanged,
    transition_approval_unavailable: copy.transitionApprovalUnavailable,
  }, locale);
}

export function lifecycleAutomationOperatorDetailLabel(
  value: unknown,
  locale: LifecycleLocale,
): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const detail = value as Partial<SecurityLifecycleAutomationOperatorDetail>;
  if (
    detail.code !== "candidate_budget_exceeded"
    || !Number.isInteger(detail.candidate_count)
    || !Number.isInteger(detail.query_limit)
    || Number(detail.query_limit) < 1
    || Number(detail.query_limit) > 16
    || Number(detail.candidate_count) <= Number(detail.query_limit)
    || detail.provider_contacted !== false
  ) {
    return null;
  }
  return narrativeTemplate(
    lifecycleCopy(locale).automationOperatorDetails.candidateBudgetExceeded,
    {
      candidateCount: String(detail.candidate_count),
      queryLimit: String(detail.query_limit),
    },
  );
}

export function lifecycleWorkflowLabel(
  value: SecurityLifecycleWorkflowState,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).workflow;
  const labels: Record<SecurityLifecycleWorkflowState, string> = {
    unresolved: copy.unresolved,
    investigating: copy.investigating,
    evidence_ready: copy.evidenceReady,
    reviewed_inconclusive: copy.reviewedInconclusive,
    resolved: copy.resolved,
  };
  return labels[value] ?? lifecycleCopy(locale).states.unknownValue;
}

export function lifecycleSourcePresenceLabel(
  value: SecurityLifecycleSourcePresence,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).states;
  const labels: Record<SecurityLifecycleSourcePresence, string> = {
    present: copy.sourcePresent,
    source_missing: copy.sourceMissing,
  };
  return labels[value] ?? copy.unknownValue;
}

export function lifecycleTrackingSourceLabel(
  value: SecurityLifecycleTrackingSource | string,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleTrackingSource, string> = {
    manual_lists: copy.trackingSources.manualLists,
    portfolio_open: copy.trackingSources.portfolioOpen,
    sa_alpha_picks_current: copy.trackingSources.saAlphaPicksCurrent,
    legacy_config_seed: copy.trackingSources.legacyConfigSeed,
  };
  return labels[value as SecurityLifecycleTrackingSource] ?? copy.states.unknownValue;
}

export function lifecycleRelevanceLabel(
  value: SecurityLifecycleRelevance,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleRelevance, string> = {
    undetermined: copy.relevance.undetermined,
    direct_tracked_security: copy.relevance.direct,
    issuer_related: copy.relevance.issuer,
    unrelated: copy.relevance.unrelated,
  };
  return labels[value] ?? copy.states.unknownValue;
}

export function lifecycleConfidenceLabel(
  value: SecurityLifecycleConfidence,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleConfidence, string> = {
    unknown: copy.confidence.unknown,
    low: copy.confidence.low,
    medium: copy.confidence.medium,
    high: copy.confidence.high,
  };
  return labels[value] ?? copy.states.unknownValue;
}

export function lifecycleEventLabel(
  value: SecurityLifecycleEventType,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleEventType, string> = {
    merger_agreement: copy.eventKinds.mergerAgreement,
    merger_proxy: copy.eventKinds.mergerProxy,
    acquisition_completed: copy.eventKinds.acquisitionCompleted,
    listing_status_review: copy.eventKinds.listingStatusReview,
    listing_removal_notice: copy.eventKinds.listingRemovalNotice,
  };
  return labels[value] ?? copy.states.unknownValue;
}

export function lifecycleOutcomeLabel(
  value: SecurityLifecycleOutcome,
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleOutcome, string> = {
    undetermined: copy.outcomes.undetermined,
    listing_ended: copy.outcomes.listingEnded,
    venue_transfer: copy.outcomes.venueTransfer,
    symbol_changed: copy.outcomes.symbolChanged,
    symbol_or_venue_changed: copy.outcomes.symbolOrVenueChanged,
    acquisition_cash: copy.outcomes.acquisitionCash,
    acquisition_stock: copy.outcomes.acquisitionStock,
    acquisition_mixed: copy.outcomes.acquisitionMixed,
    acquisition_terms_unknown: copy.outcomes.acquisitionUnknown,
    issuer_security_change: copy.outcomes.issuerSecurityChange,
    no_tracked_security_change: copy.outcomes.noTrackedChange,
    other: copy.outcomes.other,
    not_applicable: copy.outcomes.notApplicable,
  };
  return labels[value] ?? copy.states.unknownValue;
}

export function lifecycleAssessmentStatusLabel(
  value: SecurityLifecycleAssessment["status"],
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleAssessment["status"], string> = {
    draft: copy.assessmentStatuses.draft,
    accepted: copy.assessmentStatuses.accepted,
    superseded: copy.assessmentStatuses.superseded,
  };
  return labels[value] ?? copy.states.unknownValue;
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
  const labels: Record<SecurityLifecycleProposalType, string> = {
    archive_manual_memberships: copy.archiveManualMemberships,
    hide_from_active_universe: copy.hideFromActiveUniverse,
    keep_tracking: copy.keepTracking,
    no_action: copy.noAction,
    notify: copy.notify,
    remap_symbol: copy.remapSymbol,
    review_portfolio_position: copy.reviewPortfolioPosition,
  };
  return labels[actionType] ?? lifecycleCopy(locale).states.unknownValue;
}

export function lifecycleProposalBlockReasonLabel(
  reason: SecurityLifecycleProposalBlockReason | null | undefined,
  locale: LifecycleLocale,
): string | null {
  if (!reason) return null;
  const copy = lifecycleCopy(locale);
  const labels: Record<SecurityLifecycleProposalBlockReason, string> = {
    portfolio_position_open: copy.states.portfolioBlock,
    successor_evidence_missing: copy.proposalBlocks.successorEvidenceMissing,
    source_context_unavailable: copy.proposalBlocks.sourceContextUnavailable,
    stale_assessment: copy.proposalBlocks.staleAssessment,
    action_executor_not_available: copy.proposalBlocks.actionExecutorUnavailable,
  };
  return labels[reason] ?? copy.states.unknownValue;
}

export function actionProposalPresentation(
  proposal: Pick<
    SecurityLifecycleActionProposal,
    "action_type" | "status" | "block_reason" | "projected_block_reason"
  >,
  locale: LifecycleLocale,
): { label: string; state: string; canApply: false; blockReason: string | null } {
  const states: Record<SecurityLifecycleActionProposal["status"], string> = {
    proposed: lifecycleCopy(locale).states.recommendationOnly,
    dismissed: lifecycleCopy(locale).states.recommendationDismissed,
  };
  return {
    label: lifecycleProposalLabel(proposal.action_type, locale),
    state: states[proposal.status] ?? lifecycleCopy(locale).states.unknownValue,
    canApply: false,
    blockReason: lifecycleProposalBlockReasonLabel(
      proposal.projected_block_reason ?? proposal.block_reason,
      locale,
    ),
  };
}

export function lifecycleRunStatusLabel(
  status: SecurityLifecycleInvestigationRun["status"],
  locale: LifecycleLocale,
): string {
  const copy = lifecycleCopy(locale).runStatuses;
  const labels: Record<SecurityLifecycleInvestigationRun["status"], string> = {
    queued: copy.queued,
    running: copy.running,
    succeeded: copy.succeeded,
    failed: copy.failed,
    cancelled: copy.cancelled,
  };
  return labels[status] ?? lifecycleCopy(locale).states.unknownValue;
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
  else if (code === "credential_missing") message = copy.credentialMissing;
  else if (code === "permission_denied") message = copy.permissionDenied;
  else if (code === "network_error") message = copy.networkError;
  else if (code === "extract_failed") message = copy.extractFailed;
  else if (code === "unsupported_content") message = copy.unsupportedContent;
  else if (
    code === "security_lifecycle_market_store_unavailable"
    || code === "security_lifecycle_profile_store_unavailable"
  ) message = copy.dataUnavailable;
  return {
    code,
    message,
  };
}
