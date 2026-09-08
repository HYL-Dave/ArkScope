import { useEffect, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { ExternalLink, Languages, RefreshCw, Settings2 } from "lucide-react";
import { getSecurityLifecycleCaseAudit, translateSecurityLifecycleEvidence,
  type RuntimeConfig, type SecurityLifecycleCaseAudit, type SecurityLifecycleAssessment,
  type CurrentLifecycleReview,
  type SecurityLifecycleEvidence, type SecurityLifecycleListingEvidence, type SecurityLifecycleProseEvidence,
  type TranslationFailureCode, type TranslationFailureMetadata } from "../api";
import type { NavigationTarget } from "../shell/navigation";
import { Button } from "../ui/Button";
import { formatAssessmentDecimal, lifecycleAutomationNarrative, lifecycleAssessmentStatusLabel,
  lifecycleAssessmentAuthorLabel, lifecycleAcceptanceAuthorityLabel, lifecycleAutomationMethodLabel,
  lifecycleRelevanceLabel, lifecycleConfidenceLabel, lifecycleOutcomeLabel,
  lifecycleEvidenceSourceFamilyLabel, lifecycleListingAuthorityLabel, lifecycleListingStatusLabel,
  lifecycleAutomationBlockerLabel, lifecycleAutomationOperatorDetailLabel, lifecycleRunStatusLabel, lifecycleErrorPresentation,
  lifecycleFactTypeLabel, lifecycleFactValueLabel, safeEvidenceUrl, type LifecycleLocale } from "./lifecyclePresentation";

function AssessmentHistory({
  assessment,
  ticker,
  locale,
  t,
}: {
  assessment: SecurityLifecycleAssessment;
  ticker: string;
  locale: LifecycleLocale;
  t: TFunction<"explore">;
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
    </article>
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
  "translation_context_window_exceeded",
  "translation_protocol_resource_exhausted",
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
    translation_context_window_exceeded: {
      message: t(($) => $.lifecycle.translation.contextWindowExceeded),
      action: "settings",
    },
    translation_protocol_resource_exhausted: {
      message: t(($) => $.lifecycle.translation.protocolResourceExhausted),
      action: "settings",
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

interface EvidenceItemProps {
  evidence: SecurityLifecycleEvidence;
  locale: LifecycleLocale;
  busy: boolean;
  error: TranslationErrorState | null;
  onTranslate: () => void;
  onNavigate?: (target: NavigationTarget) => void;
  t: TFunction<"explore">;
}

function ListingEvidenceItem({
  evidence,
  locale,
  t,
}: {
  evidence: SecurityLifecycleListingEvidence;
  locale: LifecycleLocale;
  t: TFunction<"explore">;
}) {
  const listing = evidence.listing;
  const authority = lifecycleListingAuthorityLabel(listing.authority, locale);
  const status = lifecycleListingStatusLabel(listing.listing_status, locale);
  const displayAsOf = listing.provider_last_updated_utc ?? listing.source_as_of;
  const sourceAsOfLabel = listing.authority === "massive"
    ? t(($) => $.lifecycle.listingEvidence.fields.retrievedAt)
    : t(($) => $.lifecycle.listingEvidence.fields.snapshotAsOf);
  const scanValues = [
    listing.candidate_ticker,
    status,
    listing.primary_exchange,
    displayAsOf,
  ].filter(Boolean).join(" · ");
  return (
    <details className="lifecycle-evidence-item">
      <summary>
        <span className="lifecycle-evidence-summary">
          <span>
            <strong>{authority}</strong>
            <span className="tiny">{scanValues}</span>
          </span>
          <span className="lifecycle-state">{
            lifecycleEvidenceSourceFamilyLabel(evidence.source_family, locale)
          }</span>
        </span>
      </summary>
      <div className="lifecycle-evidence-body">
        <dl className="lifecycle-assessment-facts">
          <div>
            <dt>{t(($) => $.lifecycle.listingEvidence.fields.authority)}</dt>
            <dd>{authority}</dd>
          </div>
          {listing.directory ? (
            <div>
              <dt>{t(($) => $.lifecycle.listingEvidence.fields.directory)}</dt>
              <dd className="mono">{listing.directory}</dd>
            </div>
          ) : null}
          <div>
            <dt>{t(($) => $.lifecycle.listingEvidence.fields.ticker)}</dt>
            <dd className="mono">{listing.candidate_ticker}</dd>
          </div>
          <div>
            <dt>{t(($) => $.lifecycle.listingEvidence.fields.status)}</dt>
            <dd>{status}</dd>
          </div>
          <div>
            <dt>{t(($) => $.lifecycle.listingEvidence.fields.market)}</dt>
            <dd>{listing.market}</dd>
          </div>
          {listing.primary_exchange ? (
            <div>
              <dt>{t(($) => $.lifecycle.listingEvidence.fields.venue)}</dt>
              <dd className="mono">{listing.primary_exchange}</dd>
            </div>
          ) : null}
          <div>
            <dt>{sourceAsOfLabel}</dt>
            <dd><time dateTime={listing.source_as_of}>{listing.source_as_of}</time></dd>
          </div>
          {listing.provider_last_updated_utc ? (
            <div>
              <dt>{t(($) => $.lifecycle.listingEvidence.fields.providerUpdatedAt)}</dt>
              <dd>
                <time dateTime={listing.provider_last_updated_utc}>
                  {listing.provider_last_updated_utc}
                </time>
              </dd>
            </div>
          ) : null}
        </dl>
        {safeEvidenceUrl(evidence.source_url) ? (
          <a href={safeEvidenceUrl(evidence.source_url)!} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}
          </a>
        ) : null}
      </div>
    </details>
  );
}

function ProseEvidenceItem({
  evidence,
  locale,
  busy,
  error,
  onTranslate,
  onNavigate,
  t,
}: Omit<EvidenceItemProps, "evidence"> & {
  evidence: SecurityLifecycleProseEvidence;
}) {
  const [mode, setMode] = useState<"original" | "translation">("original");
  const translation = evidence.translations.find(
    (item) => item.locale === locale,
  );
  const failure = error ? translationFailureForState(error, t) : null;
  const routeIdentity = error ? translationRouteIdentity(error, t) : null;
  const canRetry = error && failure?.action === "retry"
    && (error.retryable || error.code === "translation_output_invalid");
  const visibleMode = translation ? mode : "original";
  return (
    <details className="lifecycle-evidence-item">
      <summary>
        <span className="lifecycle-evidence-summary">
          <span>
            <strong>{evidence.title || t(($) => $.lifecycle.states.originalEvidence)}</strong>
            {evidence.publisher || evidence.source_published_at ? (
              <span className="tiny">{[evidence.publisher, evidence.source_published_at]
                .filter(Boolean).join(" · ")}</span>
            ) : null}
          </span>
          <span className="lifecycle-state">{
            lifecycleEvidenceSourceFamilyLabel(evidence.source_family, locale)
          }</span>
        </span>
      </summary>
      <div className="lifecycle-evidence-body">
        {translation ? (
          <div
            className="lifecycle-evidence-mode-switch"
            role="group"
            aria-label={t(($) => $.lifecycle.translation.viewMode)}
          >
            <button
              type="button"
              aria-pressed={visibleMode === "original"}
              onClick={() => setMode("original")}
            >
              {t(($) => $.lifecycle.states.originalEvidence)}
            </button>
            <button
              type="button"
              aria-pressed={visibleMode === "translation"}
              onClick={() => setMode("translation")}
            >
              {t(($) => $.lifecycle.states.machineTranslation)}
            </button>
          </div>
        ) : null}
        <div data-evidence-mode={visibleMode}>
          {visibleMode === "translation" && translation ? (
            <div className="lifecycle-derived-translation">
              <div className="lifecycle-assessment-heading">
                <strong>{t(($) => $.lifecycle.states.machineTranslation)}</strong>
                <span className="lifecycle-state">{t(($) => $.lifecycle.states.llmDerived)}</span>
              </div>
              <p>{translation.translated_text}</p>
              <p className="tiny mono">{t(($) => $.lifecycle.translation.provenance, {
                provider: translation.provider,
                model: translation.model,
                harness: translation.harness,
              })}</p>
            </div>
          ) : (
            <>
              <strong className="tiny">{t(($) => $.lifecycle.states.originalEvidence)}</strong>
              <p className="lifecycle-provider-evidence">{evidence.excerpt}</p>
              {safeEvidenceUrl(evidence.source_url) ? (
                <a href={safeEvidenceUrl(evidence.source_url)!} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}
                </a>
              ) : null}
            </>
          )}
        </div>
        {!translation ? (
          <Button
            size="compact"
            tone="ghost"
            icon={<Languages size={14} />}
            disabled={busy}
            onClick={() => { setMode("translation"); onTranslate(); }}
          >
            {t(($) => $.lifecycle.actions.translateEvidence)}
          </Button>
        ) : null}
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
                onClick={() => { setMode("translation"); onTranslate(); }}
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
      </div>
    </details>
  );
}

function EvidenceItem(props: EvidenceItemProps) {
  if (props.evidence.source_family === "listing_authority") {
    if (props.evidence.kind === "ticker_event_snapshot") {
      const evidence = props.evidence;
      return <details><summary>{props.t(($) => $.lifecycle.tickerEvents)} · {evidence.ticker_event.candidate_ticker}</summary>
        {evidence.ticker_event.events.map((row) => <p key={`${row.source_ticker}-${row.effective_date}`}>
          {row.source_ticker} → {row.successor_ticker} · {row.effective_date}
        </p>)}
        {safeEvidenceUrl(evidence.source_url) && <a href={safeEvidenceUrl(evidence.source_url)!} target="_blank" rel="noreferrer">{props.t(($) => $.lifecycle.actions.openEvidence)}</a>}
      </details>;
    }
    if (
      props.evidence.kind !== "listing_directory_snapshot"
      || !props.evidence.listing
    ) return null;
    return (
      <ListingEvidenceItem
        evidence={props.evidence}
        locale={props.locale}
        t={props.t}
      />
    );
  }
  return <ProseEvidenceItem {...props} evidence={props.evidence} />;
}


function CaseAudit({ caseId, ticker, runtime, onNavigate }: {
  caseId: string; ticker: string; runtime: RuntimeConfig | null; onNavigate?: (target: NavigationTarget) => void;
}) {
  const { t, i18n } = useTranslation("explore");
  const locale = i18n.resolvedLanguage === "en" ? "en" : "zh-Hant";
  const [audit, setAudit] = useState<SecurityLifecycleCaseAudit | null>(null);
  const [failed, setFailed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, TranslationErrorState>>({});
  const mounted = useRef(true), translating = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void getSecurityLifecycleCaseAudit(caseId).then((value) => {
      if (!cancelled) setAudit(value);
    }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [caseId, revision]);
  async function translate(evidenceId: string) {
    if (translating.current) return;
    translating.current = true;
    setBusy(evidenceId);
    try {
      const result = await translateSecurityLifecycleEvidence(evidenceId, locale, runtime);
      if (!mounted.current) return;
      const original = audit?.evidence.find((item) => item.evidence_id === evidenceId);
      if (!original || original.source_family === "listing_authority" || result.evidence_id !== evidenceId
        || result.locale !== locale || result.evidence_content_sha256 !== original.content_sha256) throw { code: "evidence_changed" };
      setAudit((value) => value ? { ...value, evidence: value.evidence.map((item) => item.evidence_id === evidenceId && item.source_family !== "listing_authority"
        ? { ...item, translations: [...item.translations.filter((old) => old.locale !== locale), result] } : item) } : value);
      setErrors((value) => { const next = { ...value }; delete next[evidenceId]; return next; });
    } catch (error) { if (mounted.current) setErrors((value) => ({ ...value, [evidenceId]: captureTranslationError(error) })); }
    finally { translating.current = false; if (mounted.current) setBusy(null); }
  }
  return <div className="lifecycle-audit-record">
    {failed && <div role="alert" className="errorbox">{t(($) => $.lifecycle.current.auditUnavailable)}
      <Button icon={<RefreshCw size={14} />} onClick={() => setRevision((value) => value + 1)}>{t(($) => $.lifecycle.current.reload)}</Button>
    </div>}
    {!audit && !failed && <p role="status">{t(($) => $.lifecycle.current.loading)}</p>}
    {audit && <>
      {audit.evidence.map((evidence) => <EvidenceItem key={evidence.evidence_id} evidence={evidence} locale={locale} t={t}
        busy={busy !== null} error={errors[evidence.evidence_id] ?? null} onTranslate={() => void translate(evidence.evidence_id)} onNavigate={onNavigate} />)}
      {audit.assessment_history.map((assessment) => <AssessmentHistory key={assessment.assessment_id} assessment={assessment} ticker={ticker} locale={locale} t={t} />)}
      {audit.automation_runs.map((run) => <details key={run.run_id}><summary>{t(($) => $.lifecycle.current.checkHistory)} · {run.updated_at ?? run.created_at}</summary>
        <p>{run.failure_code ? t(($) => $.lifecycle.current.checkFailed)
          : run.status === "blocked" ? t(($) => $.lifecycle.current.checkIncomplete) : lifecycleRunStatusLabel(run.status, locale)}</p>
        {run.blockers.map((blocker, index) => <p key={index}>{lifecycleAutomationBlockerLabel(blocker.blocker_code, locale)}
          {lifecycleAutomationOperatorDetailLabel(blocker.operator_detail, locale) ? ": " + lifecycleAutomationOperatorDetailLabel(blocker.operator_detail, locale) : ""}</p>)}
      </details>)}
      {audit.investigation_runs.map((run) => <details key={run.run_id}><summary>{lifecycleRunStatusLabel(run.status, locale)} · {run.created_at}</summary>
        {run.status === "succeeded" && run.result_count === 0 && <p>{t(($) => $.lifecycle.states.zeroResults)}</p>}
        {run.failure_code && <p>{lifecycleErrorPresentation({ code: run.failure_code }, locale).message}</p>}
      </details>)}
      {audit.automation_facts.length > 0 && <details><summary>{t(($) => $.lifecycle.sections.facts)}</summary>
        <dl className="lifecycle-current-facts">{audit.automation_facts.map((fact) => <div key={fact.fact_id}>
          <dt>{lifecycleFactTypeLabel(fact.fact_type, locale)}</dt>
          <dd>{lifecycleFactValueLabel(fact.fact_type, fact.normalized_value, locale)
            ?? (typeof fact.normalized_value === "string" || typeof fact.normalized_value === "number" ? String(fact.normalized_value) : t(($) => $.lifecycle.states.notAvailable))}
            <p className="tiny">{t(($) => $.lifecycle.fields.extractionRule)}: {fact.extractor_rule_id} / {fact.extractor_rule_version}</p></dd>
        </div>)}</dl>
      </details>}
      {audit.acknowledgement_history.map((row) => <details key={row.acknowledgement_id}><summary>{t(($) => $.lifecycle.sections.acknowledgement)} · {row.acknowledged_at}</summary>
        <p>{t(($) => $.lifecycle.acknowledgementReasons.evidenceInsufficient)}</p>{row.note && <p>{row.note}</p>}
        {row.stale && <p>{t(($) => $.lifecycle.states.revalidation)}</p>}
        {row.reopened_at && <p>{t(($) => $.lifecycle.actions.reopen)}: {row.reopened_at}</p>}
      </details>)}
      {Object.entries(audit.truncation).some(([, value]) => value.returned < value.total) && <p>{t(($) => $.lifecycle.current.auditLimited)}</p>}
      {[audit.evidence, audit.assessment_history, audit.automation_runs, audit.investigation_runs, audit.automation_facts, audit.acknowledgement_history].every((rows) => !rows.length) && <p>{t(($) => $.lifecycle.current.noAudit)}</p>}
    </>}
  </div>;
}

export function CurrentLifecycleAudit({ caseIds, ticker, notices = [], runtime, onNavigate }: {
  caseIds: string[]; ticker: string; notices?: CurrentLifecycleReview["source_notices"]; runtime: RuntimeConfig | null; onNavigate?: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [requested, setRequested] = useState(false);
  return <details className="lifecycle-audit" onToggle={(event) => { if (event.currentTarget.open) setRequested(true); }}>
    <summary>{t(($) => $.lifecycle.current.audit)}</summary>
    {requested && notices.map((notice, index) => <article key={index} className="lifecycle-audit-record">
      <strong>{notice.form} / {notice.filed_on}</strong>{notice.text && <p className="lifecycle-provider-evidence">{notice.text}</p>}
      {safeEvidenceUrl(notice.url) && <a href={notice.url!} target="_blank" rel="noreferrer"><ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}</a>}
    </article>)}
    {requested && caseIds.map((caseId) => <CaseAudit key={caseId} caseId={caseId} ticker={ticker} runtime={runtime} onNavigate={onNavigate} />)}
  </details>;
}
