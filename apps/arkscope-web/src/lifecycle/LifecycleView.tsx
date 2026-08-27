import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import {
  ArrowRightLeft,
  Check,
  ExternalLink,
  Plus,
  RefreshCw,
  RotateCcw,
  Settings2,
  X,
} from "lucide-react";

import {
  acceptSecurityLifecycleAssessment,
  acknowledgeTickerIdentityTransitionActivity,
  acknowledgeSecurityLifecycleCase,
  addSecurityLifecycleEvidence,
  approveTickerIdentityTransition,
  cancelTickerIdentityTransition,
  createSecurityLifecycleAssessment,
  dismissSecurityLifecycleProposal,
  getSecurityLifecycleCase,
  getTickerIdentityTransitionPreview,
  listTickerIdentityTransitionActivity,
  listSecurityLifecycleCases,
  reopenSecurityLifecycleAcknowledgement,
  retryTickerIdentityTransition,
  reverseTickerIdentityTransition,
  translateSecurityLifecycleEvidence,
  type SecurityLifecycleCaseDetail,
  type SecurityLifecycleCaseFilters,
  type SecurityLifecycleCaseSummary,
  type SecurityLifecycleDispositionReason,
  type SecurityLifecycleAssessment,
  type SecurityLifecycleAutomationFact,
  type SecurityLifecycleAssessmentOutcome,
  type SecurityLifecycleConfidence,
  type SecurityLifecycleEventType,
  type SecurityLifecycleEvidence,
  type SecurityLifecycleEvidenceSourceFamily,
  type SecurityLifecycleProposalType,
  type SecurityLifecycleQueueBucket,
  type SecurityLifecycleRelevance,
  type SecurityLifecycleSourcePresence,
  type SecurityLifecycleWorkflowState,
  type TickerIdentityPriorityResolution,
  type TickerIdentityTransitionAttemptResult,
  type TickerIdentityTransitionApprovalAuthority,
  type TickerIdentityTransitionBlockReason,
  type TickerIdentityTransitionCaveat,
  type TickerIdentityTransitionKind,
  type TickerIdentityTransitionPreview,
  type TickerIdentityTransitionStatus,
  type TickerIdentityTransitionActivity,
  type TranslationFailureCode,
  type TranslationFailureMetadata,
} from "../api";
import type { NavigationTarget } from "../shell/navigation";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import {
  actionProposalPresentation,
  formatAssessmentDecimal,
  lifecycleAssessmentStatusLabel,
  lifecycleAcceptanceAuthorityLabel,
  lifecycleActionReadinessLabel,
  lifecycleAssessmentAuthorLabel,
  lifecycleAutomationBlockerLabel,
  lifecycleAutomationNarrative,
  lifecycleAutomationMethodLabel,
  lifecycleConfidenceLabel,
  lifecycleErrorPresentation,
  lifecycleEventLabel,
  lifecycleEvidenceSourceFamilyLabel,
  lifecycleFactTypeLabel,
  lifecycleFactValueLabel,
  lifecycleOutcomeLabel,
  lifecycleDecisionTierLabel,
  lifecycleDispositionLabel,
  lifecycleDispositionReasonLabel,
  lifecycleProposalLabel,
  lifecycleRelevanceLabel,
  lifecycleRunStatusLabel,
  lifecycleSourcePresenceLabel,
  lifecycleSourceFamilyStateLabel,
  lifecycleTrackingSourceLabel,
  lifecycleWorkflowLabel,
  safeEvidenceUrl,
  type LifecycleLocale,
} from "./lifecyclePresentation";
import {
  LifecycleActivityBand,
  type LifecycleActivityItem,
} from "./LifecycleActivityBand";
import { LifecycleCaseDrawer, LifecycleCaseSection } from "./LifecycleCaseDrawer";
import {
  tickerTransitionBlockReasonLabel,
  tickerTransitionCaveatLabel,
  tickerTransitionKindLabel,
  tickerTransitionApprovalAuthorityLabel,
  tickerTransitionStatusLabel,
} from "./tickerIdentityPresentation";

const WORKFLOW_STATES: SecurityLifecycleWorkflowState[] = [
  "unresolved",
  "investigating",
  "evidence_ready",
  "reviewed_inconclusive",
  "resolved",
];
const QUEUE_VIEWS = ["attention", "monitoring", "history", "all"] as const;
type QueueView = (typeof QUEUE_VIEWS)[number];
const SOURCE_FAMILIES: SecurityLifecycleEvidenceSourceFamily[] = [
  "regulator",
  "market_infrastructure",
  "publisher",
  "general_web",
  "manual",
];
const RELEVANCE: SecurityLifecycleRelevance[] = [
  "undetermined",
  "direct_tracked_security",
  "issuer_related",
  "unrelated",
];
const EVENT_KINDS: SecurityLifecycleEventType[] = [
  "merger_agreement",
  "merger_proxy",
  "acquisition_completed",
  "listing_status_review",
  "listing_removal_notice",
];
const PROPOSAL_TYPES: SecurityLifecycleProposalType[] = [
  "archive_manual_memberships",
  "hide_from_active_universe",
  "keep_tracking",
  "no_action",
  "notify",
  "remap_symbol",
  "review_portfolio_position",
];
const ASSESSMENT_OUTCOMES: SecurityLifecycleAssessmentOutcome[] = [
  "undetermined",
  "listing_ended",
  "venue_transfer",
  "symbol_changed",
  "acquisition_cash",
  "acquisition_stock",
  "acquisition_mixed",
  "acquisition_terms_unknown",
  "issuer_security_change",
  "no_tracked_security_change",
  "other",
  "not_applicable",
];

function localeValue(locale: string | undefined): LifecycleLocale {
  return locale === "en" ? "en" : "zh-Hant";
}

function optionalText(value: string, transform?: (value: string) => string): string | null {
  const normalized = transform ? transform(value.trim()) : value.trim();
  return normalized || null;
}

function transitionStatusLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionStatus, string> {
  return {
    approved: t(($) => $.lifecycle.transition.statuses.approved),
    needs_review: t(($) => $.lifecycle.transition.statuses.needsReview),
    applied: t(($) => $.lifecycle.transition.statuses.applied),
    cancelled: t(($) => $.lifecycle.transition.statuses.cancelled),
    reversed: t(($) => $.lifecycle.transition.statuses.reversed),
  };
}

function transitionKindLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionKind, string> {
  return {
    symbol_continuation: t(($) => $.lifecycle.transition.kinds.symbolContinuation),
    terminal_delisting: t(($) => $.lifecycle.transition.kinds.terminalDelisting),
  };
}

function transitionAuthorityLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionApprovalAuthority, string> {
  return {
    attended_user: t(($) => $.lifecycle.activity.authorities.attendedUser),
    automation_policy: t(($) => $.lifecycle.activity.authorities.automationPolicy),
  };
}

function transitionBlockLabels(
  t: TFunction<"explore">,
): Record<TickerIdentityTransitionBlockReason, string> {
  return {
    successor_missing: t(($) => $.lifecycle.transition.blockers.successorMissing),
    successor_not_distinct: t(($) => $.lifecycle.transition.blockers.successorNotDistinct),
    outcome_not_executable: t(($) => $.lifecycle.transition.blockers.outcomeNotExecutable),
    assessment_case_mismatch: t(($) => $.lifecycle.transition.blockers.assessmentCaseMismatch),
    assessment_not_accepted: t(($) => $.lifecycle.transition.blockers.assessmentNotAccepted),
    assessment_not_direct: t(($) => $.lifecycle.transition.blockers.assessmentNotDirect),
    stale_assessment: t(($) => $.lifecycle.transition.blockers.staleAssessment),
    observation_citation_required: t(
      ($) => $.lifecycle.transition.blockers.observationCitationRequired,
    ),
    execution_date_required: t(($) => $.lifecycle.transition.blockers.executionDateRequired),
    execution_date_invalid: t(($) => $.lifecycle.transition.blockers.executionDateInvalid),
    source_context_unavailable: t(
      ($) => $.lifecycle.transition.blockers.sourceContextUnavailable,
    ),
    no_active_tracking_source: t(
      ($) => $.lifecycle.transition.blockers.noActiveTrackingSource,
    ),
    remap_proposal_missing: t(($) => $.lifecycle.transition.blockers.remapProposalMissing),
    proposal_missing: t(($) => $.lifecycle.transition.blockers.proposalMissing),
    priority_resolution_required: t(
      ($) => $.lifecycle.transition.blockers.priorityResolutionRequired,
    ),
    successor_hidden: t(($) => $.lifecycle.transition.blockers.successorHidden),
    portfolio_position_open: t(($) => $.lifecycle.transition.blockers.portfolioPositionOpen),
    preview_changed: t(($) => $.lifecycle.transition.blockers.previewChanged),
    reverse_state_changed: t(($) => $.lifecycle.transition.blockers.reverseStateChanged),
    successor_has_later_transition: t(
      ($) => $.lifecycle.transition.blockers.successorHasLaterTransition,
    ),
  };
}

function transitionCaveatLabels(
  t: TFunction<"explore">,
  sourceTicker: string,
): Record<TickerIdentityTransitionCaveat, string> {
  return {
    provider_owned_sources_retained: t(
      ($) => $.lifecycle.transition.caveats.providerOwnedSourcesRetained,
    ),
    portfolio_position_retained: t(
      ($) => $.lifecycle.transition.caveats.portfolioPositionRetained,
      { ticker: sourceTicker },
    ),
    successor_already_tracked: t(
      ($) => $.lifecycle.transition.caveats.successorAlreadyTracked,
    ),
  };
}

function commandErrorPresentation(
  error: unknown,
  locale: LifecycleLocale,
  t: TFunction<"explore">,
): { code: string; message: string } {
  const base = lifecycleErrorPresentation(error, locale);
  if (base.code === "transition_preview_changed") {
    return {
      code: base.code,
      message: t(($) => $.lifecycle.errors.transitionPreviewChanged),
    };
  }
  if (base.code === "successor_has_later_transition") {
    return {
      code: base.code,
      message: t(($) => $.lifecycle.errors.transitionLaterExists),
    };
  }
  if (base.code === "reverse_state_changed" || base.code === "reverse_restore_mismatch") {
    return {
      code: base.code,
      message: t(($) => $.lifecycle.errors.transitionReverseChanged),
    };
  }
  return base;
}

const EFFECT_ACTIONS = ["add", "archive", "reactivate", "unchanged"] as const;

function currentNewYorkDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "America/New_York",
    year: "numeric",
  }).formatToParts(now);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

function requireCompletedTransitionAttempt(
  result: TickerIdentityTransitionAttemptResult,
): TickerIdentityTransitionAttemptResult {
  if (result.status !== "blocked") return result;
  const code = result.block_reasons[0] || "security_lifecycle_unavailable";
  throw Object.assign(new Error(code), { code });
}

function TransitionEffectsSummary({
  preview,
}: {
  preview: TickerIdentityTransitionPreview;
}) {
  const { t } = useTranslation("explore");
  const unknown = t(($) => $.lifecycle.states.unknownValue);
  const caveatLabels = transitionCaveatLabels(t, preview.source_ticker);
  const effectLabels = {
    add: t(($) => $.lifecycle.transition.effects.add),
    archive: t(($) => $.lifecycle.transition.effects.archive),
    reactivate: t(($) => $.lifecycle.transition.effects.reactivate),
    unchanged: t(($) => $.lifecycle.transition.effects.unchanged),
  } satisfies Record<(typeof EFFECT_ACTIONS)[number], string>;

  return (
    <>
      {EFFECT_ACTIONS.flatMap((action) => preview.effects.watchlists[action].map((item) => (
        <p key={`watchlist-${action}-${item.list_id}-${item.ticker}`}>
          <strong>{t(($) => $.lifecycle.transition.fields.watchlists)}</strong>
          <span aria-hidden="true"> · </span>
          {effectLabels[action]}: {item.list_name} · <span className="mono">{item.ticker}</span>
        </p>
      )))}
      {EFFECT_ACTIONS.flatMap((action) => (
        preview.effects.legacy_config_seed[action].map((item) => (
          <p key={`legacy-${action}-${item.ticker}`}>
            <strong>{t(($) => $.lifecycle.transition.fields.legacySeed)}</strong>
            <span aria-hidden="true"> · </span>
            {effectLabels[action]}: <span className="mono">{item.ticker}</span>
          </p>
        ))
      ))}
      {preview.effects.editable_tags_to_copy.map((item) => (
        <p key={`${item.facet}-${item.source}-${item.value}`}>
          <strong>{t(($) => $.lifecycle.transition.fields.tags)}</strong>
          <span aria-hidden="true"> · </span>
          {item.facet}: {item.value} · <span className="mono">{item.ticker}</span>
        </p>
      ))}
      {preview.caveats.length > 0 ? (
        <div>
          <strong>{t(($) => $.lifecycle.transition.fields.caveats)}</strong>
          {preview.caveats.map((caveat) => (
            <p key={caveat}>{tickerTransitionCaveatLabel(
              caveat,
              caveatLabels,
              unknown,
            )}</p>
          ))}
        </div>
      ) : null}
      <p>{t(($) => $.lifecycle.transition.noHistoricalRewrite)}</p>
      <p>{t(($) => $.lifecycle.transition.approvalConsequence)}</p>
    </>
  );
}

function TransitionPreviewContent({
  preview,
  dateValue,
  priorityResolution,
  unhideSuccessor,
  onDateChange,
  onPriorityChange,
  onUnhideChange,
}: {
  preview: TickerIdentityTransitionPreview;
  dateValue: string;
  priorityResolution: TickerIdentityPriorityResolution | null;
  unhideSuccessor: boolean;
  onDateChange: (value: string) => void;
  onPriorityChange: (value: TickerIdentityPriorityResolution) => void;
  onUnhideChange: (value: boolean) => void;
}) {
  const { t } = useTranslation("explore");
  const unknown = t(($) => $.lifecycle.states.unknownValue);
  const kindLabels = transitionKindLabels(t);
  const priority = preview.effects.priority;
  const hasPriorityChoice = priority.source_value !== null
    && priority.successor_value !== null
    && priority.source_value !== priority.successor_value;

  return (
    <div className="lifecycle-history-row">
      <p className="strong">
        {preview.successor_ticker
          ? t(($) => $.lifecycle.transition.route, {
            source: preview.source_ticker,
            successor: preview.successor_ticker,
          })
          : t(($) => $.lifecycle.transition.terminalRoute, { source: preview.source_ticker })}
      </p>
      <dl className="lifecycle-assessment-facts">
        <div>
          <dt>{t(($) => $.lifecycle.transition.fields.kind)}</dt>
          <dd>{preview.transition_kind
            ? tickerTransitionKindLabel(preview.transition_kind, kindLabels, unknown)
            : unknown}</dd>
        </div>
        <div>
          <dt>{t(($) => $.lifecycle.transition.fields.executeOn)}</dt>
          <dd>{preview.execute_on ?? unknown}</dd>
        </div>
      </dl>

      <label>
        {t(($) => $.lifecycle.transition.fields.executeOn)}
        <input
          type="date"
          aria-label={t(($) => $.lifecycle.transition.fields.executeOn)}
          value={dateValue}
          onChange={(event) => onDateChange(event.target.value)}
        />
      </label>

      {hasPriorityChoice ? (
        <fieldset className="lifecycle-outcome-fieldset">
          <legend>{t(($) => $.lifecycle.transition.fields.priority)}</legend>
          <label className="lifecycle-citation">
            <input
              type="radio"
              name="ticker-transition-priority"
              checked={priorityResolution === "source"}
              onChange={() => onPriorityChange("source")}
            />
            {t(($) => $.lifecycle.transition.fields.keepSourcePriority, {
              value: priority.source_value ?? unknown,
            })}
          </label>
          <label className="lifecycle-citation">
            <input
              type="radio"
              name="ticker-transition-priority"
              checked={priorityResolution === "successor"}
              onChange={() => onPriorityChange("successor")}
            />
            {t(($) => $.lifecycle.transition.fields.keepSuccessorPriority, {
              value: priority.successor_value ?? unknown,
            })}
          </label>
        </fieldset>
      ) : null}

      {preview.effects.suppression.successor_hidden || unhideSuccessor ? (
        <label className="lifecycle-citation">
          <input
            type="checkbox"
            aria-label={t(($) => $.lifecycle.transition.fields.unhideSuccessor)}
            checked={unhideSuccessor}
            onChange={(event) => onUnhideChange(event.target.checked)}
          />
          {t(($) => $.lifecycle.transition.fields.unhideSuccessor)}
        </label>
      ) : null}

      <TransitionEffectsSummary preview={preview} />
    </div>
  );
}

function AssessmentHistory({
  assessment,
  ticker,
  locale,
  t,
  canAccept,
  onAccept,
}: {
  assessment: SecurityLifecycleAssessment;
  ticker: string;
  locale: LifecycleLocale;
  t: TFunction<"explore">;
  canAccept: boolean;
  onAccept: () => void;
}) {
  const narrative = lifecycleAutomationNarrative(assessment, ticker, locale);
  const transactionFacts = [
    [t(($) => $.lifecycle.fields.counterpartyName), assessment.counterparty_name],
    [t(($) => $.lifecycle.fields.counterpartyTicker), assessment.counterparty_ticker],
    [t(($) => $.lifecycle.fields.counterpartyCik), assessment.counterparty_cik],
    [t(($) => $.lifecycle.fields.successorTicker), assessment.successor_ticker],
    [t(($) => $.lifecycle.fields.destinationVenue), assessment.destination_venue],
    [t(($) => $.lifecycle.fields.effectiveDate), assessment.effective_date],
    [
      t(($) => $.lifecycle.fields.considerationCurrency),
      assessment.consideration_currency,
    ],
    [
      t(($) => $.lifecycle.fields.cashPerSecurity),
      assessment.cash_per_security_decimal
        ? formatAssessmentDecimal(
          assessment.cash_per_security_decimal,
          assessment.consideration_currency,
          locale,
        )
        : null,
    ],
    [t(($) => $.lifecycle.fields.exchangeRatio), assessment.exchange_ratio_decimal],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  return (
    <article className="lifecycle-history-row lifecycle-assessment-history">
      <div className="lifecycle-assessment-heading">
        <strong>{assessment.author === "legacy_review"
          ? t(($) => $.lifecycle.states.legacy)
          : assessment.author === "automation"
            ? t(($) => $.lifecycle.states.automationAssessment)
            : narrative.conclusion}</strong>
        <span className="lifecycle-state">
          {lifecycleAssessmentStatusLabel(assessment.status, locale)}
        </span>
      </div>
      {assessment.author === "legacy_review" || assessment.author === "automation" ? (
        <>
          <p>{narrative.conclusion}</p>
          {assessment.author === "legacy_review" ? (
            <p>{t(($) => $.lifecycle.states.limitedProvenance)}</p>
          ) : null}
        </>
      ) : null}
      <dl className="lifecycle-assessment-facts">
        <div>
          <dt>{t(($) => $.lifecycle.fields.assessmentAuthor)}</dt>
          <dd>{lifecycleAssessmentAuthorLabel(assessment.author, locale)}</dd>
        </div>
        {assessment.acceptance_authority ? (
          <div>
            <dt>{t(($) => $.lifecycle.fields.acceptanceAuthority)}</dt>
            <dd>{lifecycleAcceptanceAuthorityLabel(
              assessment.acceptance_authority,
              locale,
            )}</dd>
          </div>
        ) : null}
        {assessment.automation_method ? (
          <div>
            <dt>{t(($) => $.lifecycle.fields.automationMethod)}</dt>
            <dd>{lifecycleAutomationMethodLabel(assessment.automation_method, locale)}</dd>
          </div>
        ) : null}
        {assessment.rule_id && assessment.rule_version ? (
          <div>
            <dt>{t(($) => $.lifecycle.fields.rule)}</dt>
            <dd>{t(($) => $.lifecycle.activity.ruleVersion, {
              rule: assessment.rule_id,
              version: assessment.rule_version,
            })}</dd>
          </div>
        ) : null}
        <div>
          <dt>{t(($) => $.lifecycle.fields.relevance)}</dt>
          <dd>{lifecycleRelevanceLabel(assessment.relevance, locale)}</dd>
        </div>
        <div>
          <dt>{t(($) => $.lifecycle.fields.confidence)}</dt>
          <dd>{lifecycleConfidenceLabel(assessment.confidence, locale)}</dd>
        </div>
        <div>
          <dt>{t(($) => $.lifecycle.fields.outcome)}</dt>
          <dd>{assessment.outcomes
            .map((value) => lifecycleOutcomeLabel(value, locale)).join(" · ")}</dd>
        </div>
        {transactionFacts.map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
      {assessment.citations && assessment.citations.length > 0 ? (
        <div className="lifecycle-citation-summary">
          <strong>{t(($) => $.lifecycle.fields.citations)}</strong>
          {assessment.citations.map((citation, index) => (
            <p className="tiny" key={`${citation.reference_kind}-${index}`}>
              {citation.reference_kind === "observation"
                ? t(($) => $.lifecycle.citationKinds.observation)
                : t(($) => $.lifecycle.citationKinds.evidence)}
              <span aria-hidden="true"> · </span>
              <span className="mono">{citation.evidence_id ?? citation.cited_content_sha256}</span>
            </p>
          ))}
        </div>
      ) : null}
      <p>{narrative.impact}</p>
      {assessment.stale ? <p>{t(($) => $.lifecycle.states.revalidation)}</p> : null}
      {canAccept ? (
        <Button size="compact" icon={<Check size={15} />} onClick={onAccept}>
          {assessment.author === "automation"
            ? t(($) => $.lifecycle.actions.acceptSuggestion)
            : t(($) => $.lifecycle.actions.acceptAssessment)}
        </Button>
      ) : null}
    </article>
  );
}

function factValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function AutomationTruth({
  detail,
  locale,
  t,
}: {
  detail: SecurityLifecycleCaseDetail;
  locale: LifecycleLocale;
  t: TFunction<"explore">;
}) {
  const run = detail.automation_runs?.[0];
  const blockers = run?.blockers ?? [];
  const facts = detail.automation_facts ?? [];
  if (!run && facts.length === 0) return null;
  const grouped = facts.reduce<Map<string, SecurityLifecycleAutomationFact[]>>(
    (result, fact) => {
      const values = result.get(fact.source_family) ?? [];
      values.push(fact);
      result.set(fact.source_family, values);
      return result;
    },
    new Map(),
  );

  return (
    <LifecycleCaseSection title={t(($) => $.lifecycle.sections.automation)}>
      {run ? (
        <>
          <dl className="lifecycle-assessment-facts">
            {run.decision_tier ? (
              <div>
                <dt>{t(($) => $.lifecycle.fields.decisionTier)}</dt>
                <dd>{lifecycleDecisionTierLabel(run.decision_tier, locale)}</dd>
              </div>
            ) : null}
            {run.action_readiness ? (
              <div>
                <dt>{t(($) => $.lifecycle.fields.actionReadiness)}</dt>
                <dd>{lifecycleActionReadinessLabel(run.action_readiness, locale)}</dd>
              </div>
            ) : null}
            <div>
              <dt>{t(($) => $.lifecycle.fields.policy)}</dt>
              <dd className="mono">{run.policy_version}</dd>
            </div>
          </dl>
          {blockers.map((blocker) => (
            <p className="lifecycle-blocker" key={blocker.blocker_code}>
              {lifecycleAutomationBlockerLabel(blocker.blocker_code, locale)}
            </p>
          ))}
        </>
      ) : null}
      {facts.length > 0 ? (
        <div className="lifecycle-fact-groups">
          <h4>{t(($) => $.lifecycle.sections.facts)}</h4>
          {[...grouped.entries()].map(([family, familyFacts]) => (
            <section className="lifecycle-fact-group" key={family}>
              <h5>{lifecycleEvidenceSourceFamilyLabel(family, locale)}</h5>
              <dl className="lifecycle-assessment-facts">
                {familyFacts.map((fact) => (
                  <div key={fact.fact_id}>
                    <dt>{lifecycleFactTypeLabel(fact.fact_type, locale)}</dt>
                    <dd>{lifecycleFactValueLabel(
                      fact.fact_type,
                      fact.normalized_value,
                      locale,
                    ) ?? factValue(fact.normalized_value)}</dd>
                    <dd className="tiny mono">{t(($) => $.lifecycle.fields.extractionRule)}: {
                      t(($) => $.lifecycle.activity.ruleVersion, {
                        rule: fact.extractor_rule_id,
                        version: fact.extractor_rule_version,
                      })
                    }</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      ) : null}
    </LifecycleCaseSection>
  );
}

const TRANSLATION_FAILURE_CODES: readonly TranslationFailureCode[] = [
  "translation_route_unavailable",
  "translation_credential_missing",
  "translation_auth_rejected",
  "translation_rate_limited",
  "translation_quota_exhausted",
  "translation_model_unavailable",
  "translation_timeout",
  "translation_output_invalid",
  "translation_provider_error",
  "evidence_changed",
];

type TranslationErrorState = TranslationFailureMetadata & {
  code: TranslationFailureCode | "translation_unknown";
};

export interface TranslationFailurePresentation {
  message: string;
  action: "retry" | "settings" | null;
}

function isTranslationFailureCode(
  value: string | null,
): value is TranslationFailureCode {
  return value !== null
    && TRANSLATION_FAILURE_CODES.includes(value as TranslationFailureCode);
}

export function translationFailurePresentation(
  code: TranslationFailureCode,
  t: TFunction<"explore">,
): TranslationFailurePresentation {
  const presentations: Record<TranslationFailureCode, TranslationFailurePresentation> = {
    translation_route_unavailable: {
      message: t(($) => $.lifecycle.translation.routeUnavailable),
      action: "settings",
    },
    translation_credential_missing: {
      message: t(($) => $.lifecycle.translation.credentialMissing),
      action: "settings",
    },
    translation_auth_rejected: {
      message: t(($) => $.lifecycle.translation.authRejected),
      action: "settings",
    },
    translation_rate_limited: {
      message: t(($) => $.lifecycle.translation.rateLimited),
      action: "retry",
    },
    translation_quota_exhausted: {
      message: t(($) => $.lifecycle.translation.quotaExhausted),
      action: "settings",
    },
    translation_model_unavailable: {
      message: t(($) => $.lifecycle.translation.modelUnavailable),
      action: "settings",
    },
    translation_timeout: {
      message: t(($) => $.lifecycle.translation.timeout),
      action: "retry",
    },
    translation_output_invalid: {
      message: t(($) => $.lifecycle.translation.outputInvalid),
      action: "retry",
    },
    translation_provider_error: {
      message: t(($) => $.lifecycle.translation.providerError),
      action: "retry",
    },
    evidence_changed: {
      message: t(($) => $.lifecycle.translation.evidenceChanged),
      action: null,
    },
  };
  return presentations[code];
}

function captureTranslationError(error: unknown): TranslationErrorState {
  const candidate = error && typeof error === "object" ? error : null;
  const rawCode = candidate && "code" in candidate && typeof candidate.code === "string"
    ? candidate.code
    : null;
  const code = isTranslationFailureCode(rawCode) ? rawCode : "translation_unknown";
  const metadata = candidate && "metadata" in candidate
    && candidate.metadata && typeof candidate.metadata === "object"
    ? candidate.metadata as Partial<TranslationFailureMetadata>
    : null;
  return {
    code,
    provider: typeof metadata?.provider === "string" ? metadata.provider : null,
    model: typeof metadata?.model === "string" ? metadata.model : null,
    harness: typeof metadata?.harness === "string" ? metadata.harness : null,
    retryable: metadata?.retryable === true,
  };
}

function translationProviderLabel(
  provider: string,
  t: TFunction<"explore">,
): string {
  if (provider === "anthropic") {
    return t(($) => $.lifecycle.translation.providers.anthropic);
  }
  if (provider === "openai") {
    return t(($) => $.lifecycle.translation.providers.openai);
  }
  return provider;
}

function translationRouteIdentity(
  error: TranslationErrorState,
  t: TFunction<"explore">,
): string | null {
  const values = [
    error.provider ? translationProviderLabel(error.provider, t) : null,
    error.model,
    error.harness,
  ].filter((value): value is string => Boolean(value));
  return values.length > 0 ? values.join(" · ") : null;
}

function unknownTranslationFailure(
  t: TFunction<"explore">,
): TranslationFailurePresentation {
  return {
    message: t(($) => $.lifecycle.translation.unknown),
    action: null,
  };
}

function translationFailureForState(
  error: TranslationErrorState,
  t: TFunction<"explore">,
): TranslationFailurePresentation {
  if (error.code === "translation_unknown") {
    return unknownTranslationFailure(t);
  }
  return translationFailurePresentation(error.code, t);
}

function EvidenceItem({
  evidence,
  locale,
  busy,
  error,
  onTranslate,
  onNavigate,
  t,
}: {
  evidence: SecurityLifecycleEvidence;
  locale: LifecycleLocale;
  busy: boolean;
  error: TranslationErrorState | null;
  onTranslate: () => void;
  onNavigate?: (target: NavigationTarget) => void;
  t: TFunction<"explore">;
}) {
  const translation = (evidence.translations ?? []).find(
    (item) => item.locale === locale,
  );
  const failure = error ? translationFailureForState(error, t) : null;
  const routeIdentity = error ? translationRouteIdentity(error, t) : null;
  const canRetry = error && failure?.action === "retry"
    && (error.retryable || error.code === "translation_output_invalid");
  return (
    <article className="lifecycle-history-row lifecycle-evidence-item">
      <div className="lifecycle-assessment-heading">
        <strong>{evidence.title || t(($) => $.lifecycle.states.originalEvidence)}</strong>
        <span className="lifecycle-state">{
          lifecycleEvidenceSourceFamilyLabel(evidence.source_family, locale)
        }</span>
      </div>
      {evidence.publisher || evidence.source_published_at ? (
        <p className="tiny">{[evidence.publisher, evidence.source_published_at]
          .filter(Boolean).join(" · ")}</p>
      ) : null}
      <strong className="tiny">{t(($) => $.lifecycle.states.originalEvidence)}</strong>
      <p className="lifecycle-provider-evidence">{evidence.excerpt}</p>
      {safeEvidenceUrl(evidence.source_url) ? (
        <a href={safeEvidenceUrl(evidence.source_url)!} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}
        </a>
      ) : null}
      {translation ? (
        <div className="lifecycle-derived-translation">
          <strong>{t(($) => $.lifecycle.states.machineTranslation)}</strong>
          <p>{translation.translated_text}</p>
          <p className="tiny mono">{t(($) => $.lifecycle.translation.provenance, {
            provider: translation.provider,
            model: translation.model,
            harness: translation.harness,
          })}</p>
        </div>
      ) : (
        <Button
          size="compact"
          tone="ghost"
          disabled={busy}
          onClick={onTranslate}
        >
          {t(($) => $.lifecycle.actions.translateEvidence)}
        </Button>
      )}
      {error && failure ? (
        <div className="errorbox">
          <p>{failure.message}</p>
          {routeIdentity ? <p className="tiny mono">{routeIdentity}</p> : null}
          {canRetry ? (
            <Button
              size="compact"
              tone="ghost"
              icon={<RefreshCw size={14} />}
              disabled={busy}
              onClick={onTranslate}
            >
              {t(($) => $.lifecycle.translation.retry)}
            </Button>
          ) : null}
          {failure.action === "settings" ? (
            <Button
              size="compact"
              tone="ghost"
              icon={<Settings2 size={14} />}
              data-action="open-content-translation-settings"
              onClick={() => onNavigate?.({
                kind: "settings_section",
                section: "models",
              })}
            >
              {t(($) => $.lifecycle.translation.openSettings)}
            </Button>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function LifecycleDispositionReasonText({
  reason,
  dispositionAsOf,
  locale,
}: {
  reason: SecurityLifecycleDispositionReason;
  dispositionAsOf: string | null;
  locale: LifecycleLocale;
}) {
  const { t } = useTranslation("explore");
  if (reason === "not_confirmed_as_of" && dispositionAsOf) {
    return <>{t(($) => $.lifecycle.dispositionReasons.notConfirmedAsOfDated, {
      date: dispositionAsOf,
    })}</>;
  }
  return <>{lifecycleDispositionReasonLabel(reason, locale)}</>;
}

function CaseTable({
  cases,
  locale,
  onOpen,
}: {
  cases: SecurityLifecycleCaseSummary[];
  locale: LifecycleLocale;
  onOpen: (caseId: string, trigger: HTMLButtonElement) => void;
}) {
  const { t } = useTranslation("explore");
  if (cases.length === 0) return <p className="muted">{t(($) => $.lifecycle.table.empty)}</p>;
  return (
    <div className="lifecycle-table-wrap">
      <table className="wl lifecycle-table">
        <thead><tr>
          <th>{t(($) => $.lifecycle.table.ticker)}</th>
          <th>{t(($) => $.lifecycle.table.filing)}</th>
          <th>{t(($) => $.lifecycle.table.event)}</th>
          <th>{t(($) => $.lifecycle.table.disposition)}</th>
          <th>{t(($) => $.lifecycle.table.relevance)}</th>
          <th>{t(($) => $.lifecycle.table.sources)}</th>
        </tr></thead>
        <tbody>
          {cases.map((item) => (
            <tr
              data-workflow-state={item.workflow_state}
              key={item.case_id}
            >
              <td>
                <button
                  className="lifecycle-case-trigger"
                  type="button"
                  onClick={(event) => onOpen(item.case_id, event.currentTarget)}
                >
                  <span className="mono strong">{item.ticker}</span>
                  <span className="muted tiny">{item.issuer_name ?? item.source_ref}</span>
                </button>
              </td>
              <td>{item.filing_date ?? "—"}</td>
              <td>{item.kinds
                .map((kind) => lifecycleEventLabel(kind.event_type, locale)).join(" · ") || "—"}</td>
              <td>
                <div className="lifecycle-disposition-cell">
                  <span
                    className={`lifecycle-state lifecycle-disposition-${item.disposition}`}
                    data-disposition={item.disposition}
                  >
                    {lifecycleDispositionLabel(item.disposition, locale)}
                  </span>
                  <span className="tiny">
                    <LifecycleDispositionReasonText
                      reason={item.disposition_reason}
                      dispositionAsOf={item.disposition_as_of}
                      locale={locale}
                    />
                  </span>
                  {item.last_checked_at ? (
                    <span className="muted tiny">
                      {t(($) => $.lifecycle.table.lastChecked)}: {item.last_checked_at}
                    </span>
                  ) : null}
                  {item.next_check_at ? (
                    <span className="muted tiny">
                      {t(($) => $.lifecycle.table.nextCheck)}: {item.next_check_at}
                    </span>
                  ) : null}
                </div>
              </td>
              <td>{item.current_assessment
                ? lifecycleRelevanceLabel(item.current_assessment.relevance, locale)
                : lifecycleRelevanceLabel("undetermined", locale)}</td>
              <td>{item.active_sources
                .map((source) => lifecycleTrackingSourceLabel(source, locale)).join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LifecycleView({
  initialCaseId = null,
  onNavigate,
}: {
  initialCaseId?: string | null;
  onNavigate?: (target: NavigationTarget) => void;
}) {
  const { t, i18n } = useTranslation("explore");
  const locale = localeValue(i18n.resolvedLanguage);
  const [sourcePresence, setSourcePresence] = useState<SecurityLifecycleSourcePresence>("present");
  const [queueView, setQueueView] = useState<QueueView>("attention");
  const [queueCounts, setQueueCounts] = useState<Record<SecurityLifecycleQueueBucket, number>>({
    attention: 0,
    monitoring: 0,
    history: 0,
  });
  const [filters, setFilters] = useState<SecurityLifecycleCaseFilters>({ limit: 200 });
  const [cases, setCases] = useState<SecurityLifecycleCaseSummary[] | null>(null);
  const [sourceMissingCount, setSourceMissingCount] = useState(0);
  const [activityItems, setActivityItems] = useState<LifecycleActivityItem[]>([]);
  const [activityError, setActivityError] = useState<ReturnType<
    typeof lifecycleErrorPresentation
  > | null>(null);
  const [activityBusy, setActivityBusy] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(initialCaseId);
  const [detail, setDetail] = useState<SecurityLifecycleCaseDetail | null>(null);
  const [listError, setListError] = useState<ReturnType<typeof lifecycleErrorPresentation> | null>(null);
  const [commandError, setCommandError] = useState<ReturnType<typeof lifecycleErrorPresentation> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [manualText, setManualText] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [impact, setImpact] = useState("");
  const [relevance, setRelevance] = useState<SecurityLifecycleRelevance>(
    "undetermined",
  );
  const [confidence, setConfidence] = useState<SecurityLifecycleConfidence>("unknown");
  const [outcomes, setOutcomes] = useState<SecurityLifecycleAssessmentOutcome[]>([
    "undetermined",
  ]);
  const [counterpartyName, setCounterpartyName] = useState("");
  const [counterpartyTicker, setCounterpartyTicker] = useState("");
  const [counterpartyCik, setCounterpartyCik] = useState("");
  const [successorTicker, setSuccessorTicker] = useState("");
  const [destinationVenue, setDestinationVenue] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [considerationCurrency, setConsiderationCurrency] = useState("");
  const [cashPerSecurity, setCashPerSecurity] = useState("");
  const [exchangeRatio, setExchangeRatio] = useState("");
  const [citeObservation, setCiteObservation] = useState(false);
  const [citedEvidence, setCitedEvidence] = useState<string[]>([]);
  const [citationError, setCitationError] = useState(false);
  const [translationBusy, setTranslationBusy] = useState<string | null>(null);
  const [translationErrors, setTranslationErrors] = useState<
    Record<string, TranslationErrorState>
  >({});
  const [transitionPreview, setTransitionPreview] = useState<TickerIdentityTransitionPreview | null>(
    null,
  );
  const [transitionPreviewLoading, setTransitionPreviewLoading] = useState(false);
  const [transitionDate, setTransitionDate] = useState("");
  const [transitionPriority, setTransitionPriority] = useState<
    TickerIdentityPriorityResolution | null
  >(null);
  const [transitionUnhideSuccessor, setTransitionUnhideSuccessor] = useState(false);
  const [transitionDialog, setTransitionDialog] = useState<"approve" | "reverse" | null>(null);
  const caseQuery = useMemo(() => ({ filters, queueView, sourcePresence }), [
    filters,
    queueView,
    sourcePresence,
  ]);
  const transitionPreviewRequestRef = useRef(0);
  const caseRequestRef = useRef(0);
  const detailRequestRef = useRef(0);
  const caseQueryRef = useRef(caseQuery);
  const selectedCaseIdRef = useRef(selectedCaseId);
  const pendingQueueViewRef = useRef<QueueView | null>(null);
  const returnFocusRef = useRef<HTMLButtonElement | null>(null);
  caseQueryRef.current = caseQuery;
  selectedCaseIdRef.current = selectedCaseId;

  const loadCases = useCallback(async () => {
    const requestId = ++caseRequestRef.current;
    const requestQuery = caseQueryRef.current;
    try {
      const requestFilters: SecurityLifecycleCaseFilters = {
        ...requestQuery.filters,
        source_presence: requestQuery.sourcePresence,
      };
      if (requestQuery.sourcePresence === "present" && requestQuery.queueView !== "all") {
        requestFilters.queue_bucket = requestQuery.queueView;
      }
      const response = await listSecurityLifecycleCases(requestFilters);
      if (
        requestId !== caseRequestRef.current
        || requestQuery !== caseQueryRef.current
      ) return;
      setCases(response.cases);
      setQueueCounts(response.queue_counts);
      setSourceMissingCount(response.data_integrity.source_missing_count);
      if (pendingQueueViewRef.current === requestQuery.queueView) {
        setSelectedCaseId((caseId) => (
          caseId && !response.cases.some((item) => item.case_id === caseId)
            ? null
            : caseId
        ));
        pendingQueueViewRef.current = null;
      }
      setListError(null);
    } catch (error) {
      if (
        requestId !== caseRequestRef.current
        || requestQuery !== caseQueryRef.current
      ) return;
      setListError(lifecycleErrorPresentation(error, locale));
    }
  }, [locale]);

  const loadActivity = useCallback(async () => {
    try {
      const response = await listTickerIdentityTransitionActivity({ limit: 50 });
      const caseReads = new Map<string, Promise<SecurityLifecycleCaseDetail | null>>();
      for (const item of response.items) {
        if (item.activity_type !== "applied" || item.reverse_readiness) continue;
        if (!caseReads.has(item.case_id)) {
          caseReads.set(item.case_id, getSecurityLifecycleCase(item.case_id).catch(() => null));
        }
      }
      const items = await Promise.all(response.items.map(async (item) => {
        if (item.activity_type !== "applied" || item.reverse_readiness) return item;
        const activityCase = await caseReads.get(item.case_id);
        const transition = activityCase?.ticker_transition;
        return {
          ...item,
          reverse_readiness: transition?.transition_id === item.transition_id
            ? transition.reverse_readiness
            : null,
        };
      }));
      setActivityItems(items);
      setActivityError(null);
    } catch (error) {
      setActivityError(lifecycleErrorPresentation(error, locale));
    }
  }, [locale]);

  const loadDetail = useCallback(async (caseId: string) => {
    const requestId = ++detailRequestRef.current;
    try {
      const response = await getSecurityLifecycleCase(caseId);
      if (
        requestId !== detailRequestRef.current
        || selectedCaseIdRef.current !== caseId
      ) return;
      setDetail(response);
      setCommandError(null);
    } catch (error) {
      if (
        requestId !== detailRequestRef.current
        || selectedCaseIdRef.current !== caseId
      ) return;
      setCommandError(lifecycleErrorPresentation(error, locale));
    }
  }, [locale]);

  const loadTransitionPreview = useCallback(async (
    caseId: string,
    options: {
      execute_on?: string;
      priority_resolution?: TickerIdentityPriorityResolution;
      unhide_successor?: boolean;
    } = {},
    initializeControls = false,
  ) => {
    const requestId = ++transitionPreviewRequestRef.current;
    setTransitionPreviewLoading(true);
    try {
      const response = await getTickerIdentityTransitionPreview(caseId, options);
      if (requestId !== transitionPreviewRequestRef.current) return;
      setTransitionPreview(response);
      if (initializeControls) {
        setTransitionDate(response.execute_on ?? "");
        setTransitionPriority(response.effects.priority.resolution);
        setTransitionUnhideSuccessor(response.effects.suppression.unhide_successor);
      }
    } catch (error) {
      if (requestId !== transitionPreviewRequestRef.current) return;
      setTransitionPreview(null);
      setCommandError(commandErrorPresentation(error, locale, t));
    } finally {
      if (requestId === transitionPreviewRequestRef.current) {
        setTransitionPreviewLoading(false);
      }
    }
  }, [locale, t]);

  useEffect(() => { void loadCases(); }, [caseQuery, loadCases]);
  useEffect(() => { void loadActivity(); }, [loadActivity]);
  useEffect(() => {
    if (selectedCaseId) void loadDetail(selectedCaseId);
    else {
      detailRequestRef.current += 1;
      setDetail(null);
    }
  }, [loadDetail, selectedCaseId]);
  useEffect(() => {
    const transition = detail?.ticker_transition;
    const shouldPreview = detail?.source_presence === "present"
      && detail.current_assessment?.status === "accepted"
      && (!transition || transition.status === "needs_review");
    if (shouldPreview && detail) {
      void loadTransitionPreview(detail.case_id, {}, true);
    } else {
      transitionPreviewRequestRef.current += 1;
      setTransitionPreview(null);
      setTransitionPreviewLoading(false);
    }
  }, [detail, loadTransitionPreview]);
  useEffect(() => {
    setManualText("");
    setManualUrl("");
    setConclusion("");
    setImpact("");
    setRelevance("undetermined");
    setConfidence("unknown");
    setOutcomes(["undetermined"]);
    setCounterpartyName("");
    setCounterpartyTicker("");
    setCounterpartyCik("");
    setSuccessorTicker("");
    setDestinationVenue("");
    setEffectiveDate("");
    setConsiderationCurrency("");
    setCashPerSecurity("");
    setExchangeRatio("");
    setCiteObservation(false);
    setCitedEvidence([]);
    setCitationError(false);
    setTranslationBusy(null);
    setTranslationErrors({});
    setTransitionPreview(null);
    setTransitionPreviewLoading(false);
    setTransitionDate("");
    setTransitionPriority(null);
    setTransitionUnhideSuccessor(false);
    setTransitionDialog(null);
  }, [selectedCaseId]);
  const automationSuggestion = useMemo(() => detail?.assessment_history.find(
    (assessment) => assessment.author === "automation" && assessment.status === "draft",
  ) ?? null, [detail]);
  useEffect(() => {
    if (!automationSuggestion) return;
    const editableOutcomes = automationSuggestion.outcomes.filter(
      (value): value is SecurityLifecycleAssessmentOutcome => (
        ASSESSMENT_OUTCOMES.includes(value as SecurityLifecycleAssessmentOutcome)
      ),
    );
    setConclusion(automationSuggestion.conclusion);
    setImpact(automationSuggestion.impact_summary);
    setRelevance(automationSuggestion.relevance);
    setConfidence(automationSuggestion.confidence);
    setOutcomes(editableOutcomes.length > 0 ? editableOutcomes : ["undetermined"]);
    setCounterpartyName(automationSuggestion.counterparty_name ?? "");
    setCounterpartyTicker(automationSuggestion.counterparty_ticker ?? "");
    setCounterpartyCik(automationSuggestion.counterparty_cik ?? "");
    setSuccessorTicker(automationSuggestion.successor_ticker ?? "");
    setDestinationVenue(automationSuggestion.destination_venue ?? "");
    setEffectiveDate(automationSuggestion.effective_date ?? "");
    setConsiderationCurrency(automationSuggestion.consideration_currency ?? "");
    setCashPerSecurity(automationSuggestion.cash_per_security_decimal ?? "");
    setExchangeRatio(automationSuggestion.exchange_ratio_decimal ?? "");
    setCiteObservation(Boolean(automationSuggestion.citations?.some(
      (citation) => citation.reference_kind === "observation",
    )));
    setCitedEvidence((automationSuggestion.citations ?? []).flatMap((citation) => (
      citation.reference_kind === "evidence" && citation.evidence_id
        ? [citation.evidence_id]
        : []
    )));
    setCitationError(false);
  }, [automationSuggestion]);
  useEffect(() => {
    if (initialCaseId) {
      setDetail(null);
      setSourcePresence("present");
      setSelectedCaseId(initialCaseId);
    }
  }, [initialCaseId]);

  const updateFilter = <Key extends keyof SecurityLifecycleCaseFilters>(
    key: Key,
    value: SecurityLifecycleCaseFilters[Key],
  ) => setFilters((current) => ({ ...current, [key]: value }));

  const runCommand = async (name: string, command: () => Promise<unknown>): Promise<boolean> => {
    if (!selectedCaseId || busy) return false;
    setBusy(name);
    setCommandError(null);
    try {
      await command();
      const currentCaseId = selectedCaseIdRef.current;
      await Promise.all([
        loadCases(),
        currentCaseId ? loadDetail(currentCaseId) : Promise.resolve(),
      ]);
      return true;
    } catch (error) {
      setCommandError(commandErrorPresentation(error, locale, t));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const runActivityCommand = async (
    name: string,
    command: () => Promise<unknown>,
  ) => {
    if (activityBusy) return;
    setActivityBusy(name);
    setActivityError(null);
    try {
      await command();
      await Promise.all([
        loadActivity(),
        loadCases(),
        selectedCaseIdRef.current
          ? loadDetail(selectedCaseIdRef.current)
          : Promise.resolve(),
      ]);
    } catch (error) {
      setActivityError(commandErrorPresentation(error, locale, t));
    } finally {
      setActivityBusy(null);
    }
  };

  const runTranslation = async (evidenceId: string) => {
    if (!selectedCaseId || translationBusy) return;
    setTranslationBusy(evidenceId);
    setTranslationErrors((current) => {
      const next = { ...current };
      delete next[evidenceId];
      return next;
    });
    try {
      await translateSecurityLifecycleEvidence(evidenceId, locale);
      const currentCaseId = selectedCaseIdRef.current;
      if (currentCaseId) await loadDetail(currentCaseId);
    } catch (error) {
      setTranslationErrors((current) => ({
        ...current,
        [evidenceId]: captureTranslationError(error),
      }));
    } finally {
      setTranslationBusy(null);
    }
  };

  const currentEvidence = detail?.evidence ?? [];
  const evidenceGroups = useMemo(() => currentEvidence.reduce<
    Map<string, SecurityLifecycleEvidence[]>
  >((groups, evidence) => {
    const family = evidence.source_family || "manual";
    const values = groups.get(family) ?? [];
    values.push(evidence);
    groups.set(family, values);
    return groups;
  }, new Map()), [currentEvidence]);
  const evidenceCitations = useMemo(() => currentEvidence.filter(
    (item) => Boolean(item.evidence_id),
  ), [currentEvidence]);

  const updateOutcome = (
    value: SecurityLifecycleAssessmentOutcome,
    checked: boolean,
  ) => setOutcomes((current) => {
    if (value === "undetermined") {
      return checked ? ["undetermined"] : current;
    }
    const determinate = current.filter((item) => item !== "undetermined");
    if (checked) return [...determinate, value];
    const remaining = determinate.filter((item) => item !== value);
    return remaining.length > 0 ? remaining : ["undetermined"];
  });

  const statusLabels = transitionStatusLabels(t);
  const kindLabels = transitionKindLabels(t);
  const authorityLabels = transitionAuthorityLabels(t);
  const blockLabels = transitionBlockLabels(t);
  const unknownTransitionValue = t(($) => $.lifecycle.states.unknownValue);
  const queueLabels: Record<QueueView, string> = {
    attention: t(($) => $.lifecycle.queues.attention),
    monitoring: t(($) => $.lifecycle.queues.monitoring),
    history: t(($) => $.lifecycle.queues.history),
    all: t(($) => $.lifecycle.queues.all),
  };
  const queueCount = (view: QueueView): number => (
    view === "all"
      ? queueCounts.attention + queueCounts.monitoring + queueCounts.history
      : queueCounts[view]
  );
  const selectQueueView = (view: QueueView) => {
    if (view === queueView) return;
    pendingQueueViewRef.current = view;
    setQueueView(view);
  };

  const refreshTransitionOptions = (
    values: {
      executeOn?: string;
      priority?: TickerIdentityPriorityResolution | null;
      unhideSuccessor?: boolean;
    },
  ) => {
    if (!selectedCaseId) return;
    const executeOn = values.executeOn ?? transitionDate;
    const priority = values.priority === undefined ? transitionPriority : values.priority;
    const unhideSuccessor = values.unhideSuccessor ?? transitionUnhideSuccessor;
    setTransitionDate(executeOn);
    setTransitionPriority(priority);
    setTransitionUnhideSuccessor(unhideSuccessor);
    void loadTransitionPreview(selectedCaseId, {
      execute_on: executeOn || undefined,
      priority_resolution: priority ?? undefined,
      unhide_successor: unhideSuccessor,
    });
  };

  return (
    <main className="lifecycle-triage" aria-label={t(($) => $.lifecycle.aria)}>
      <div className="surface-head lifecycle-head">
        <h2 className="surface-title">{t(($) => $.lifecycle.title)}</h2>
        <span className="spacer" />
        <Button
          size="compact"
          tone="ghost"
          icon={<RefreshCw size={15} />}
          onClick={() => void loadCases()}
        >
          {t(($) => $.lifecycle.actions.refresh)}
        </Button>
      </div>

      {activityError ? (
        <p className="errorbox" data-error-code={activityError.code}>{activityError.message}</p>
      ) : null}
      <LifecycleActivityBand
        items={activityItems}
        busyAction={activityBusy}
        onAcknowledge={(activityId) => void runActivityCommand(
          `acknowledge-${activityId}`,
          () => acknowledgeTickerIdentityTransitionActivity(activityId),
        )}
        onReverse={(transitionId) => void runActivityCommand(
          `reverse-${transitionId}`,
          async () => requireCompletedTransitionAttempt(
            await reverseTickerIdentityTransition(transitionId),
          ),
        )}
      />

      <div className="lifecycle-view-switch" role="group" aria-label={t(($) => $.lifecycle.aria)}>
        <Button
          size="compact"
          tone={sourcePresence === "present" ? "primary" : "ghost"}
          onClick={() => setSourcePresence("present")}
        >
          {t(($) => $.lifecycle.views.investmentEvents)}
        </Button>
        <Button
          size="compact"
          tone={sourcePresence === "source_missing" ? "primary" : "ghost"}
          onClick={() => setSourcePresence("source_missing")}
        >
          {t(($) => $.lifecycle.views.dataIntegrity)} · {sourceMissingCount}
        </Button>
      </div>

      {sourcePresence === "present" ? (
        <div
          className="lifecycle-queue-switch"
          role="tablist"
          aria-label={t(($) => $.lifecycle.queues.aria)}
        >
          {QUEUE_VIEWS.map((view) => (
            <Button
              className="lifecycle-queue-tab"
              size="compact"
              tone={queueView === view ? "primary" : "ghost"}
              role="tab"
              aria-selected={queueView === view}
              data-queue-view={view}
              onClick={() => selectQueueView(view)}
              key={view}
            >
              <span>{queueLabels[view]}</span>
              <span className="lifecycle-queue-count">{queueCount(view)}</span>
            </Button>
          ))}
        </div>
      ) : null}

      <div className="lifecycle-filters">
        <label>{t(($) => $.lifecycle.filters.ticker)}
          <input
            aria-label={t(($) => $.lifecycle.filters.ticker)}
            value={filters.ticker ?? ""}
            onChange={(event) => updateFilter("ticker", event.target.value)}
          />
        </label>
        <FilterSelect
          label={t(($) => $.lifecycle.filters.workflow)}
          value={filters.workflow_state ?? ""}
          onChange={(value) => updateFilter("workflow_state", value as SecurityLifecycleWorkflowState | "")}
          options={WORKFLOW_STATES.map((value) => [value, lifecycleWorkflowLabel(value, locale)])}
          allLabel={t(($) => $.lifecycle.filters.all)}
        />
        <FilterSelect
          label={t(($) => $.lifecycle.filters.relevance)}
          value={filters.relevance ?? ""}
          onChange={(value) => updateFilter("relevance", value as SecurityLifecycleRelevance | "")}
          options={RELEVANCE.map((value) => [value, lifecycleRelevanceLabel(value, locale)])}
          allLabel={t(($) => $.lifecycle.filters.all)}
        />
        <FilterSelect
          label={t(($) => $.lifecycle.filters.eventKind)}
          value={filters.event_type ?? ""}
          onChange={(value) => updateFilter("event_type", value as SecurityLifecycleEventType | "")}
          options={EVENT_KINDS.map((value) => [value, lifecycleEventLabel(value, locale)])}
          allLabel={t(($) => $.lifecycle.filters.all)}
        />
        <FilterSelect
          label={t(($) => $.lifecycle.filters.proposalType)}
          value={filters.proposal_type ?? ""}
          onChange={(value) => updateFilter("proposal_type", value as SecurityLifecycleProposalType | "")}
          options={PROPOSAL_TYPES.map((value) => [value, lifecycleProposalLabel(value, locale)])}
          allLabel={t(($) => $.lifecycle.filters.all)}
        />
      </div>

      {sourcePresence === "source_missing" ? (
        <p className="lifecycle-integrity-notice">
          {lifecycleSourcePresenceLabel("source_missing", locale)} · {
            t(($) => $.lifecycle.table.sourceMissingCount, { count: sourceMissingCount })
          }
        </p>
      ) : null}
      {listError ? <p className="errorbox">{listError.message}</p> : null}
      {cases ? (
        <CaseTable
          cases={cases}
          locale={locale}
          onOpen={(caseId, trigger) => {
            returnFocusRef.current = trigger;
            setDetail(null);
            setSelectedCaseId(caseId);
          }}
        />
      ) : <p className="muted">{t(($) => $.lifecycle.states.loading)}</p>}

      <LifecycleCaseDrawer
        open={Boolean(selectedCaseId && detail)}
        title={detail ? [detail.ticker, detail.issuer_name ?? detail.source_ref].join(" · ") : ""}
        onClose={() => setSelectedCaseId(null)}
        returnFocusRef={returnFocusRef}
      >
        {detail ? (
          <>
            {commandError ? (
              <p className="errorbox" data-error-code={commandError.code}>{commandError.message}</p>
            ) : null}
            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.status)}>
              <dl className="lifecycle-assessment-facts lifecycle-disposition-summary">
                <div>
                  <dt>{t(($) => $.lifecycle.table.disposition)}</dt>
                  <dd>{lifecycleDispositionLabel(detail.disposition, locale)}</dd>
                </div>
                <div>
                  <dt>{t(($) => $.lifecycle.fields.actionReadiness)}</dt>
                  <dd><LifecycleDispositionReasonText
                    reason={detail.disposition_reason}
                    dispositionAsOf={detail.disposition_as_of}
                    locale={locale}
                  /></dd>
                </div>
                {detail.last_checked_at ? (
                  <div>
                    <dt>{t(($) => $.lifecycle.table.lastChecked)}</dt>
                    <dd><time dateTime={detail.last_checked_at}>{detail.last_checked_at}</time></dd>
                  </div>
                ) : null}
                {detail.next_check_at ? (
                  <div>
                    <dt>{t(($) => $.lifecycle.table.nextCheck)}</dt>
                    <dd><time dateTime={detail.next_check_at}>{detail.next_check_at}</time></dd>
                  </div>
                ) : null}
                {SOURCE_FAMILIES.map((family) => {
                  const state = detail.source_family_status[family];
                  return state ? (
                    <div key={family}>
                      <dt>{lifecycleEvidenceSourceFamilyLabel(family, locale)}</dt>
                      <dd>{lifecycleSourceFamilyStateLabel(state, locale)}</dd>
                    </div>
                  ) : null;
                })}
              </dl>
            </LifecycleCaseSection>
            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.source)}>
              <p><strong>{lifecycleSourcePresenceLabel(detail.source_presence, locale)}</strong></p>
              {detail.source_context === "unavailable" ? (
                <p>{t(($) => $.lifecycle.states.sourceContextUnavailable)}</p>
              ) : null}
              {detail.observation ? (
                <>
                  <p>{detail.observation.filing_form} · {detail.observation.filing_date}</p>
                  <p className="lifecycle-provider-evidence">{detail.observation.description}</p>
                  {safeEvidenceUrl(detail.observation.evidence_url) ? (
                    <a
                      className="lifecycle-evidence-link"
                      href={safeEvidenceUrl(detail.observation.evidence_url)!}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}
                    </a>
                  ) : null}
                </>
              ) : <p>{t(($) => $.lifecycle.states.revalidation)}</p>}
            </LifecycleCaseSection>

            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.evidence)}>
              {[...evidenceGroups.entries()].map(([family, items]) => (
                <section className="lifecycle-evidence-group" key={family}>
                  <h4>{lifecycleEvidenceSourceFamilyLabel(family, locale)}</h4>
                  {items.map((item) => (
                    <EvidenceItem
                      evidence={item}
                      locale={locale}
                      busy={translationBusy === item.evidence_id}
                      error={translationErrors[item.evidence_id] ?? null}
                      onTranslate={() => void runTranslation(item.evidence_id)}
                      onNavigate={onNavigate}
                      t={t}
                      key={item.evidence_id}
                    />
                  ))}
                </section>
              ))}
              {detail.investigation_runs.length > 0 ? (
                <div>
                  <h4>{t(($) => $.lifecycle.sections.runs)}</h4>
                  {detail.investigation_runs.map((run) => (
                    <p key={run.run_id}>
                      {run.status === "succeeded" && run.result_count === 0
                        ? t(($) => $.lifecycle.states.zeroResults)
                        : <>
                          {lifecycleRunStatusLabel(run.status, locale)}
                          <span aria-hidden="true"> · </span>
                          {run.result_count}
                          {run.status === "failed" && run.failure_code ? <>
                            <span aria-hidden="true"> · </span>
                            {lifecycleErrorPresentation({ code: run.failure_code }, locale).message}
                          </> : null}
                        </>}
                    </p>
                  ))}
                </div>
              ) : null}
              {detail.source_presence === "present" ? (
                <div className="lifecycle-commands lifecycle-manual-supplement">
                  <label>{t(($) => $.lifecycle.fields.manualText)}
                    <textarea
                      aria-label={t(($) => $.lifecycle.fields.manualText)}
                      value={manualText}
                      onChange={(event) => setManualText(event.target.value)}
                    />
                  </label>
                  <Button
                    size="compact"
                    icon={<Plus size={15} />}
                    disabled={!manualText.trim()}
                    onClick={() => void runCommand("manual-text", async () => {
                      await addSecurityLifecycleEvidence(detail.case_id, {
                        text: manualText.trim(),
                        url: null,
                      });
                      setManualText("");
                    })}
                  >
                    {t(($) => $.lifecycle.actions.addText)}
                  </Button>
                  <label>{t(($) => $.lifecycle.fields.manualUrl)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.manualUrl)}
                      value={manualUrl}
                      onChange={(event) => setManualUrl(event.target.value)}
                    />
                  </label>
                  <Button
                    size="compact"
                    icon={<Plus size={15} />}
                    disabled={!manualUrl.trim()}
                    onClick={() => void runCommand("manual-url", async () => {
                      await addSecurityLifecycleEvidence(detail.case_id, {
                        text: null,
                        url: manualUrl.trim(),
                      });
                      setManualUrl("");
                    })}
                  >
                    {t(($) => $.lifecycle.actions.addUrl)}
                  </Button>
                </div>
              ) : null}
            </LifecycleCaseSection>

            <AutomationTruth detail={detail} locale={locale} t={t} />

            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.acknowledgement)}>
              {detail.acknowledgement_history.map((item) => (
                <p key={item.acknowledgement_id}>
                  {t(($) => $.lifecycle.acknowledgementReasons.evidenceInsufficient)}
                  {item.stale ? <>
                    <span aria-hidden="true"> · </span>
                    {t(($) => $.lifecycle.states.revalidation)}
                  </> : null}
                </p>
              ))}
              {detail.source_presence === "present" ? (
                detail.current_acknowledgement ? (
                  <Button
                    size="compact"
                    tone="ghost"
                    icon={<RotateCcw size={15} />}
                    onClick={() => void runCommand("reopen", () => (
                      reopenSecurityLifecycleAcknowledgement(
                        detail.current_acknowledgement!.acknowledgement_id,
                      )
                    ))}
                  >
                    {t(($) => $.lifecycle.actions.reopen)}
                  </Button>
                ) : (
                  <Button
                    size="compact"
                    tone="ghost"
                    icon={<Check size={15} />}
                    onClick={() => void runCommand("acknowledge", () => (
                      acknowledgeSecurityLifecycleCase(detail.case_id, {
                        reason: "evidence_insufficient",
                        note: null,
                      })
                    ))}
                  >
                    {t(($) => $.lifecycle.actions.acknowledge)}
                  </Button>
                )
              ) : null}
            </LifecycleCaseSection>

            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.assessment)}>
              {detail.assessment_history.map((assessment) => (
                <AssessmentHistory
                  assessment={assessment}
                  ticker={detail.ticker}
                  locale={locale}
                  t={t}
                  canAccept={assessment.status === "draft" && detail.source_presence === "present"}
                  onAccept={() => void runCommand("accept", () => (
                    acceptSecurityLifecycleAssessment(assessment.assessment_id)
                  ))}
                  key={assessment.assessment_id}
                />
              ))}
              {detail.source_presence === "present" ? (
                <div className="lifecycle-assessment-form">
                  <label>{t(($) => $.lifecycle.fields.relevance)}
                    <select
                      aria-label={t(($) => $.lifecycle.fields.relevance)}
                      value={relevance}
                      onChange={(event) => setRelevance(event.target.value as SecurityLifecycleRelevance)}
                    >
                      {RELEVANCE.map((value) => (
                        <option value={value} key={value}>
                          {lifecycleRelevanceLabel(value, locale)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>{t(($) => $.lifecycle.fields.confidence)}
                    <select
                      aria-label={t(($) => $.lifecycle.fields.confidence)}
                      value={confidence}
                      onChange={(event) => setConfidence(event.target.value as SecurityLifecycleConfidence)}
                    >
                      {(["unknown", "low", "medium", "high"] as const).map((value) => (
                        <option value={value} key={value}>
                          {lifecycleConfidenceLabel(value, locale)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <fieldset className="lifecycle-outcome-fieldset">
                    <legend>{t(($) => $.lifecycle.fields.outcome)}</legend>
                    <div className="lifecycle-outcome-options">
                      {ASSESSMENT_OUTCOMES.map((value) => (
                        <label className="lifecycle-citation" key={value}>
                          <input
                            type="checkbox"
                            aria-label={lifecycleOutcomeLabel(value, locale)}
                            checked={outcomes.includes(value)}
                            onChange={(event) => updateOutcome(value, event.target.checked)}
                          />
                          {lifecycleOutcomeLabel(value, locale)}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <label>{t(($) => $.lifecycle.fields.counterpartyName)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.counterpartyName)}
                      maxLength={240}
                      value={counterpartyName}
                      onChange={(event) => setCounterpartyName(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.counterpartyTicker)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.counterpartyTicker)}
                      maxLength={20}
                      value={counterpartyTicker}
                      onChange={(event) => setCounterpartyTicker(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.counterpartyCik)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.counterpartyCik)}
                      inputMode="numeric"
                      maxLength={10}
                      value={counterpartyCik}
                      onChange={(event) => setCounterpartyCik(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.successorTicker)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.successorTicker)}
                      maxLength={20}
                      value={successorTicker}
                      onChange={(event) => setSuccessorTicker(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.destinationVenue)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.destinationVenue)}
                      maxLength={120}
                      value={destinationVenue}
                      onChange={(event) => setDestinationVenue(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.effectiveDate)}
                    <input
                      type="date"
                      aria-label={t(($) => $.lifecycle.fields.effectiveDate)}
                      value={effectiveDate}
                      onChange={(event) => setEffectiveDate(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.considerationCurrency)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.considerationCurrency)}
                      maxLength={3}
                      value={considerationCurrency}
                      onChange={(event) => setConsiderationCurrency(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.cashPerSecurity)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.cashPerSecurity)}
                      inputMode="decimal"
                      maxLength={128}
                      value={cashPerSecurity}
                      onChange={(event) => setCashPerSecurity(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.exchangeRatio)}
                    <input
                      aria-label={t(($) => $.lifecycle.fields.exchangeRatio)}
                      inputMode="decimal"
                      maxLength={128}
                      value={exchangeRatio}
                      onChange={(event) => setExchangeRatio(event.target.value)}
                    />
                  </label>
                  <label className="lifecycle-assessment-wide">
                    {t(($) => $.lifecycle.fields.conclusion)}
                    <textarea
                      aria-label={t(($) => $.lifecycle.fields.conclusion)}
                      value={conclusion}
                      onChange={(event) => setConclusion(event.target.value)}
                    />
                  </label>
                  <label className="lifecycle-assessment-wide">
                    {t(($) => $.lifecycle.fields.impact)}
                    <textarea
                      aria-label={t(($) => $.lifecycle.fields.impact)}
                      value={impact}
                      onChange={(event) => setImpact(event.target.value)}
                    />
                  </label>
                  <label className="lifecycle-citation">
                    <input
                      type="checkbox"
                      data-citation-kind="observation"
                      aria-label={t(($) => $.lifecycle.sections.source)}
                      checked={citeObservation}
                      onChange={(event) => {
                        setCitationError(false);
                        setCiteObservation(event.target.checked);
                      }}
                    />
                    {t(($) => $.lifecycle.sections.source)} · {detail.observation?.filing_form}
                  </label>
                  {evidenceCitations.map((item) => (
                    <label className="lifecycle-citation" key={item.evidence_id}>
                      <input
                        type="checkbox"
                        data-citation-kind="evidence"
                        aria-label={t(($) => $.lifecycle.fields.citeEvidence)}
                        checked={citedEvidence.includes(item.evidence_id)}
                        onChange={(event) => {
                          setCitationError(false);
                          setCitedEvidence((current) => event.target.checked
                            ? [...current, item.evidence_id]
                            : current.filter((id) => id !== item.evidence_id));
                        }}
                      />
                      {item.excerpt.slice(0, 120)}
                    </label>
                  ))}
                  {citationError ? (
                    <p className="errorbox">{t(($) => $.lifecycle.states.citationRequired)}</p>
                  ) : null}
                  <Button
                    size="compact"
                    icon={<Check size={15} />}
                    disabled={!conclusion.trim() || !impact.trim()}
                    onClick={() => {
                      const observationFingerprint = detail.observation_fingerprint_sha256;
                      if (!citeObservation || !observationFingerprint) {
                        setCitationError(true);
                        return;
                      }
                      void runCommand("assessment", () => createSecurityLifecycleAssessment(
                        detail.case_id,
                        {
                          relevance,
                          confidence,
                          conclusion: conclusion.trim(),
                          impact_summary: impact.trim(),
                          outcomes,
                          counterparty_name: optionalText(counterpartyName),
                          counterparty_ticker: optionalText(
                            counterpartyTicker,
                            (value) => value.toUpperCase(),
                          ),
                          counterparty_cik: optionalText(counterpartyCik),
                          successor_ticker: optionalText(
                            successorTicker,
                            (value) => value.toUpperCase(),
                          ),
                          destination_venue: optionalText(destinationVenue),
                          effective_date: optionalText(effectiveDate),
                          consideration_currency: optionalText(
                            considerationCurrency,
                            (value) => value.toUpperCase(),
                          ),
                          cash_per_security_decimal: optionalText(cashPerSecurity),
                          exchange_ratio_decimal: optionalText(exchangeRatio),
                          citations: [
                            {
                              reference_kind: "observation",
                              cited_content_sha256: observationFingerprint,
                            },
                            ...citedEvidence.map((evidenceId) => ({
                              reference_kind: "evidence" as const,
                              evidence_id: evidenceId,
                            })),
                          ],
                        },
                      ));
                    }}
                  >
                    {automationSuggestion
                      ? t(($) => $.lifecycle.actions.saveHumanRevision)
                      : t(($) => $.lifecycle.actions.saveAssessment)}
                  </Button>
                </div>
              ) : null}
            </LifecycleCaseSection>

            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.proposals)}>
              {detail.proposals.map((proposal) => {
                const presentation = actionProposalPresentation(proposal, locale);
                return (
                  <article className="lifecycle-proposal" key={proposal.proposal_id}>
                    <strong>{presentation.label}</strong>
                    <p>{presentation.state}</p>
                    <p className="tiny">{proposal.source_snapshot
                      .map((source) => lifecycleTrackingSourceLabel(source, locale)).join(", ")}</p>
                    {proposal.replacement_ticker ? (
                      <p>{t(($) => $.lifecycle.fields.successorTicker)}: {
                        proposal.replacement_ticker
                      }</p>
                    ) : null}
                    {presentation.blockReason ? <p>{presentation.blockReason}</p> : null}
                    {proposal.status === "proposed" ? (
                      <Button
                        size="compact"
                        tone="ghost"
                        icon={<X size={15} />}
                        onClick={() => void runCommand("dismiss", () => (
                          dismissSecurityLifecycleProposal(proposal.proposal_id)
                        ))}
                      >
                        {t(($) => $.lifecycle.actions.dismissProposal)}
                      </Button>
                    ) : null}
                  </article>
                );
              })}
            </LifecycleCaseSection>

            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.transition)}>
              {detail.ticker_transition ? (
                <div className="lifecycle-history-row">
                  <p>
                    <strong>{tickerTransitionKindLabel(
                      detail.ticker_transition.kind,
                      kindLabels,
                      unknownTransitionValue,
                    )}</strong>
                    <span aria-hidden="true"> · </span>
                    {tickerTransitionStatusLabel(
                      detail.ticker_transition.status,
                      statusLabels,
                      unknownTransitionValue,
                    )}
                  </p>
                  <p className="mono">
                    {detail.ticker_transition.successor_ticker
                      ? t(($) => $.lifecycle.transition.route, {
                        source: detail.ticker_transition.source_ticker,
                        successor: detail.ticker_transition.successor_ticker,
                      })
                      : t(($) => $.lifecycle.transition.terminalRoute, {
                        source: detail.ticker_transition.source_ticker,
                      })}
                  </p>
                  <p>
                    {t(($) => $.lifecycle.transition.fields.executeOn)}: {
                      detail.ticker_transition.execute_on
                    }
                  </p>
                  {detail.ticker_transition.approval_authority ? (
                    <p>{tickerTransitionApprovalAuthorityLabel(
                      detail.ticker_transition.approval_authority,
                      authorityLabels,
                      unknownTransitionValue,
                    )}</p>
                  ) : null}
                  {detail.ticker_transition.rule_id && detail.ticker_transition.rule_version ? (
                    <p className="tiny mono">{t(($) => $.lifecycle.activity.ruleVersion, {
                      rule: detail.ticker_transition!.rule_id,
                      version: detail.ticker_transition!.rule_version,
                    })}</p>
                  ) : null}
                  <TransitionEffectsSummary
                    preview={detail.ticker_transition.approved_preview}
                  />
                  {detail.ticker_transition.latest_attempt ? (
                    <div>
                      <strong>{t(($) => $.lifecycle.transition.fields.latestAttempt)}</strong>
                      <span aria-hidden="true"> · </span>
                      {detail.ticker_transition.latest_attempt.attempted_at}
                      {detail.ticker_transition.latest_attempt.block_reasons.map((reason) => (
                        <p key={reason}>{tickerTransitionBlockReasonLabel(
                          reason,
                          blockLabels,
                          unknownTransitionValue,
                        )}</p>
                      ))}
                    </div>
                  ) : null}
                  <div className="lifecycle-commands">
                    {detail.ticker_transition.status === "approved" ? (
                      <>
                        <Button
                          size="compact"
                          tone="ghost"
                          icon={<X size={15} />}
                          disabled={Boolean(busy)}
                          onClick={() => void runCommand("cancel-transition", () => (
                            cancelTickerIdentityTransition(
                              detail.ticker_transition!.transition_id,
                            )
                          ))}
                        >
                          {t(($) => $.lifecycle.actions.cancelTransition)}
                        </Button>
                        {detail.ticker_transition.execute_on <= currentNewYorkDate() ? (
                          <Button
                            size="compact"
                            icon={<ArrowRightLeft size={15} />}
                            disabled={Boolean(busy)}
                            onClick={() => void runCommand("retry-transition", async () => (
                              requireCompletedTransitionAttempt(await retryTickerIdentityTransition(
                                detail.ticker_transition!.transition_id,
                                {
                                  preview_sha256:
                                    detail.ticker_transition!.approved_preview_sha256,
                                },
                              ))
                            ))}
                          >
                            {t(($) => $.lifecycle.actions.retryTransition)}
                          </Button>
                        ) : null}
                      </>
                    ) : null}
                    {detail.ticker_transition.status === "needs_review" ? (
                      <Button
                        size="compact"
                        tone="ghost"
                        icon={<X size={15} />}
                        disabled={Boolean(busy)}
                        onClick={() => void runCommand("cancel-transition", () => (
                          cancelTickerIdentityTransition(
                            detail.ticker_transition!.transition_id,
                          )
                        ))}
                      >
                        {t(($) => $.lifecycle.actions.cancelTransition)}
                      </Button>
                    ) : null}
                    {detail.ticker_transition.status === "applied" ? (
                      <Button
                        size="compact"
                        tone="ghost"
                        icon={<RotateCcw size={15} />}
                        disabled={Boolean(busy)}
                        onClick={() => setTransitionDialog("reverse")}
                      >
                        {t(($) => $.lifecycle.actions.reverseTransition)}
                      </Button>
                    ) : null}
                  </div>
                  {(detail.ticker_transition.activity_history ?? []).length > 0 ? (
                    <LifecycleActivityBand
                      items={detail.ticker_transition.activity_history.map((item) => ({
                        ...item,
                        reverse_readiness: item.activity_type === "applied"
                          ? detail.ticker_transition!.reverse_readiness
                          : null,
                      }))}
                      busyAction={activityBusy}
                      onAcknowledge={(activityId) => void runActivityCommand(
                        `acknowledge-${activityId}`,
                        () => acknowledgeTickerIdentityTransitionActivity(activityId),
                      )}
                      onReverse={(transitionId) => void runActivityCommand(
                        `reverse-${transitionId}`,
                        async () => requireCompletedTransitionAttempt(
                          await reverseTickerIdentityTransition(transitionId),
                        ),
                      )}
                    />
                  ) : null}
                </div>
              ) : null}

              {transitionPreviewLoading ? (
                <p className="muted">{t(($) => $.lifecycle.transition.awaitingPreview)}</p>
              ) : null}
              {transitionPreview ? (
                <div>
                  <label>
                    {t(($) => $.lifecycle.transition.fields.executeOn)}
                    <input
                      type="date"
                      aria-label={t(($) => $.lifecycle.transition.fields.executeOn)}
                      value={transitionDate}
                      disabled={Boolean(busy) || transitionPreviewLoading}
                      onChange={(event) => refreshTransitionOptions({
                        executeOn: event.target.value,
                      })}
                    />
                  </label>
                  {transitionPreview.block_reasons.length > 0 ? (
                    <div>
                      <strong>{t(($) => $.lifecycle.transition.fields.blockers)}</strong>
                      {transitionPreview.block_reasons.map((reason) => (
                        <p key={reason}>{tickerTransitionBlockReasonLabel(
                          reason,
                          blockLabels,
                          unknownTransitionValue,
                        )}</p>
                      ))}
                    </div>
                  ) : null}
                  {transitionPreview.effects.priority.source_value !== null
                    && transitionPreview.effects.priority.successor_value !== null
                    && transitionPreview.effects.priority.source_value
                      !== transitionPreview.effects.priority.successor_value ? (
                      <fieldset className="lifecycle-outcome-fieldset">
                        <legend>{t(($) => $.lifecycle.transition.fields.priority)}</legend>
                        <label className="lifecycle-citation">
                          <input
                            type="radio"
                            name="ticker-transition-priority-summary"
                            checked={transitionPriority === "source"}
                            disabled={Boolean(busy) || transitionPreviewLoading}
                            onChange={() => refreshTransitionOptions({ priority: "source" })}
                          />
                          {t(($) => $.lifecycle.transition.fields.keepSourcePriority, {
                            value: transitionPreview.effects.priority.source_value,
                          })}
                        </label>
                        <label className="lifecycle-citation">
                          <input
                            type="radio"
                            name="ticker-transition-priority-summary"
                            checked={transitionPriority === "successor"}
                            disabled={Boolean(busy) || transitionPreviewLoading}
                            onChange={() => refreshTransitionOptions({ priority: "successor" })}
                          />
                          {t(($) => $.lifecycle.transition.fields.keepSuccessorPriority, {
                            value: transitionPreview.effects.priority.successor_value,
                          })}
                        </label>
                      </fieldset>
                    ) : null}
                  {transitionPreview.effects.suppression.successor_hidden
                    || transitionUnhideSuccessor ? (
                      <label className="lifecycle-citation">
                        <input
                          type="checkbox"
                          aria-label={t(($) => $.lifecycle.transition.fields.unhideSuccessor)}
                          checked={transitionUnhideSuccessor}
                          disabled={Boolean(busy) || transitionPreviewLoading}
                          onChange={(event) => refreshTransitionOptions({
                            unhideSuccessor: event.target.checked,
                          })}
                        />
                        {t(($) => $.lifecycle.transition.fields.unhideSuccessor)}
                      </label>
                    ) : null}
                  {!transitionPreview.transition_kind ? (
                    <p>{t(($) => $.lifecycle.transition.noExecutableTransition)}</p>
                  ) : null}
                  {transitionPreview.eligible
                    && (!detail.ticker_transition
                      || detail.ticker_transition.status === "needs_review") ? (
                      <Button
                        size="compact"
                        icon={<ArrowRightLeft size={15} />}
                        disabled={Boolean(busy) || transitionPreviewLoading}
                        onClick={() => setTransitionDialog("approve")}
                      >
                        {t(($) => $.lifecycle.actions.reviewTransition)}
                      </Button>
                    ) : null}
                </div>
              ) : null}
            </LifecycleCaseSection>
          </>
        ) : null}
      </LifecycleCaseDrawer>

      <ConfirmDialog
        open={transitionDialog === "approve" && Boolean(transitionPreview?.eligible)}
        title={t(($) => $.lifecycle.transition.modalTitle)}
        consequence={transitionPreview ? (
          <TransitionPreviewContent
            preview={transitionPreview}
            dateValue={transitionDate}
            priorityResolution={transitionPriority}
            unhideSuccessor={transitionUnhideSuccessor}
            onDateChange={(value) => refreshTransitionOptions({ executeOn: value })}
            onPriorityChange={(value) => refreshTransitionOptions({ priority: value })}
            onUnhideChange={(value) => refreshTransitionOptions({ unhideSuccessor: value })}
          />
        ) : null}
        confirmLabel={t(($) => $.lifecycle.actions.approveTransition)}
        tone="primary"
        busy={busy === "approve-transition"}
        onCancel={() => setTransitionDialog(null)}
        onConfirm={() => {
          if (!transitionPreview?.execute_on) return;
          const reviewedPreview = transitionPreview;
          void (async () => {
            const succeeded = await runCommand("approve-transition", () => (
              approveTickerIdentityTransition(detail!.case_id, {
                execute_on: reviewedPreview.execute_on!,
                preview_sha256: reviewedPreview.preview_sha256,
                priority_resolution: reviewedPreview.effects.priority.resolution,
                unhide_successor: reviewedPreview.effects.suppression.unhide_successor,
              })
            ));
            setTransitionDialog(null);
            if (!succeeded && selectedCaseId) {
              void loadTransitionPreview(selectedCaseId, {
                execute_on: transitionDate || undefined,
                priority_resolution: transitionPriority ?? undefined,
                unhide_successor: transitionUnhideSuccessor,
              });
            }
          })();
        }}
      />

      <ConfirmDialog
        open={transitionDialog === "reverse" && detail?.ticker_transition?.status === "applied"}
        title={t(($) => $.lifecycle.transition.reverseTitle)}
        consequence={<p>{t(($) => $.lifecycle.transition.reverseConsequence)}</p>}
        confirmLabel={t(($) => $.lifecycle.actions.confirmReverse)}
        busy={busy === "reverse-transition"}
        onCancel={() => setTransitionDialog(null)}
        onConfirm={() => {
          const transitionId = detail?.ticker_transition?.transition_id;
          if (!transitionId) return;
          void (async () => {
            await runCommand("reverse-transition", async () => (
              requireCompletedTransitionAttempt(
                await reverseTickerIdentityTransition(transitionId),
              )
            ));
            setTransitionDialog(null);
          })();
        }}
      />
    </main>
  );
}

function FilterSelect({
  label,
  value,
  options,
  allLabel,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  allLabel: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>{label}
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{allLabel}</option>
        {options.map(([optionValue, optionLabel]) => (
          <option value={optionValue} key={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </label>
  );
}
