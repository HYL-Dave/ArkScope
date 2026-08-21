import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import {
  Check,
  ExternalLink,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  X,
} from "lucide-react";

import {
  acceptSecurityLifecycleAssessment,
  acknowledgeSecurityLifecycleCase,
  addSecurityLifecycleEvidence,
  createSecurityLifecycleAssessment,
  dismissSecurityLifecycleProposal,
  getSecurityLifecycleCase,
  listSecurityLifecycleCases,
  reopenSecurityLifecycleAcknowledgement,
  startSecurityLifecycleInvestigation,
  type SecurityLifecycleCaseDetail,
  type SecurityLifecycleCaseFilters,
  type SecurityLifecycleCaseSummary,
  type SecurityLifecycleConfidence,
  type SecurityLifecycleEventType,
  type SecurityLifecycleOutcome,
  type SecurityLifecycleProposalType,
  type SecurityLifecycleRelevance,
  type SecurityLifecycleSourcePresence,
  type SecurityLifecycleWorkflowState,
} from "../api";
import { Button } from "../ui/Button";
import {
  actionProposalPresentation,
  lifecycleErrorPresentation,
  lifecycleProposalLabel,
  lifecycleRunStatusLabel,
  lifecycleSourcePresenceLabel,
  lifecycleWorkflowLabel,
  safeEvidenceUrl,
  type LifecycleLocale,
} from "./lifecyclePresentation";
import { LifecycleCaseDrawer, LifecycleCaseSection } from "./LifecycleCaseDrawer";

const WORKFLOW_STATES: SecurityLifecycleWorkflowState[] = [
  "unresolved",
  "investigating",
  "evidence_ready",
  "reviewed_inconclusive",
  "resolved",
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
  "keep_tracking",
  "no_action",
  "notify",
  "remap_symbol",
  "review_portfolio_position",
];

function localeValue(locale: string | undefined): LifecycleLocale {
  return locale === "en" ? "en" : "zh-Hant";
}

function relevanceLabel(value: SecurityLifecycleRelevance, t: TFunction<"explore">) {
  if (value === "direct_tracked_security") return t(($) => $.lifecycle.relevance.direct);
  if (value === "issuer_related") return t(($) => $.lifecycle.relevance.issuer);
  if (value === "unrelated") return t(($) => $.lifecycle.relevance.unrelated);
  return t(($) => $.lifecycle.relevance.undetermined);
}

function eventLabel(value: SecurityLifecycleEventType, t: TFunction<"explore">) {
  if (value === "merger_agreement") return t(($) => $.lifecycle.eventKinds.mergerAgreement);
  if (value === "merger_proxy") return t(($) => $.lifecycle.eventKinds.mergerProxy);
  if (value === "acquisition_completed") return t(($) => $.lifecycle.eventKinds.acquisitionCompleted);
  if (value === "listing_status_review") return t(($) => $.lifecycle.eventKinds.listingStatusReview);
  return t(($) => $.lifecycle.eventKinds.listingRemovalNotice);
}

function outcomeLabel(value: SecurityLifecycleOutcome, t: TFunction<"explore">) {
  if (value === "listing_ended") return t(($) => $.lifecycle.outcomes.listingEnded);
  if (value === "venue_transfer") return t(($) => $.lifecycle.outcomes.venueTransfer);
  if (value === "symbol_changed") return t(($) => $.lifecycle.outcomes.symbolChanged);
  if (value === "acquisition_cash") return t(($) => $.lifecycle.outcomes.acquisitionCash);
  if (value === "acquisition_stock") return t(($) => $.lifecycle.outcomes.acquisitionStock);
  if (value === "acquisition_mixed") return t(($) => $.lifecycle.outcomes.acquisitionMixed);
  if (value === "acquisition_terms_unknown") {
    return t(($) => $.lifecycle.outcomes.acquisitionUnknown);
  }
  if (value === "issuer_security_change") {
    return t(($) => $.lifecycle.outcomes.issuerSecurityChange);
  }
  if (value === "no_tracked_security_change") {
    return t(($) => $.lifecycle.outcomes.noTrackedChange);
  }
  if (value === "not_applicable") return t(($) => $.lifecycle.outcomes.notApplicable);
  if (value === "other") return t(($) => $.lifecycle.outcomes.other);
  return t(($) => $.lifecycle.outcomes.undetermined);
}

function confidenceLabel(
  value: SecurityLifecycleConfidence,
  t: TFunction<"explore">,
) {
  if (value === "low") return t(($) => $.lifecycle.confidence.low);
  if (value === "medium") return t(($) => $.lifecycle.confidence.medium);
  if (value === "high") return t(($) => $.lifecycle.confidence.high);
  return t(($) => $.lifecycle.confidence.unknown);
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
          <th>{t(($) => $.lifecycle.table.workflow)}</th>
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
              <td>{item.kinds.map((kind) => eventLabel(kind.event_type, t)).join(" · ") || "—"}</td>
              <td><span className={`lifecycle-state lifecycle-state-${item.workflow_state}`}>
                {lifecycleWorkflowLabel(item.workflow_state, locale)}
              </span></td>
              <td>{item.current_assessment
                ? relevanceLabel(item.current_assessment.relevance, t)
                : relevanceLabel("undetermined", t)}</td>
              <td>{item.active_sources.join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LifecycleView({
  initialCaseId = null,
}: {
  initialCaseId?: string | null;
}) {
  const { t, i18n } = useTranslation("explore");
  const locale = localeValue(i18n.resolvedLanguage);
  const [sourcePresence, setSourcePresence] = useState<SecurityLifecycleSourcePresence>("present");
  const [filters, setFilters] = useState<SecurityLifecycleCaseFilters>({ limit: 200 });
  const [cases, setCases] = useState<SecurityLifecycleCaseSummary[] | null>(null);
  const [sourceMissingCount, setSourceMissingCount] = useState(0);
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
  const [outcome, setOutcome] = useState<SecurityLifecycleOutcome>("undetermined");
  const [citeObservation, setCiteObservation] = useState(false);
  const [citedEvidence, setCitedEvidence] = useState<string[]>([]);
  const [citationError, setCitationError] = useState(false);
  const returnFocusRef = useRef<HTMLButtonElement | null>(null);

  const loadCases = useCallback(async () => {
    try {
      const response = await listSecurityLifecycleCases({
        ...filters,
        source_presence: sourcePresence,
      });
      setCases(response.cases);
      setSourceMissingCount(response.data_integrity.source_missing_count);
      setListError(null);
    } catch (error) {
      setListError(lifecycleErrorPresentation(error, locale));
    }
  }, [filters, locale, sourcePresence]);

  const loadDetail = useCallback(async (caseId: string) => {
    try {
      setDetail(await getSecurityLifecycleCase(caseId));
      setCommandError(null);
    } catch (error) {
      setCommandError(lifecycleErrorPresentation(error, locale));
    }
  }, [locale]);

  useEffect(() => { void loadCases(); }, [loadCases]);
  useEffect(() => {
    if (selectedCaseId) void loadDetail(selectedCaseId);
    else setDetail(null);
  }, [loadDetail, selectedCaseId]);
  useEffect(() => {
    setManualText("");
    setManualUrl("");
    setConclusion("");
    setImpact("");
    setRelevance("undetermined");
    setConfidence("unknown");
    setOutcome("undetermined");
    setCiteObservation(false);
    setCitedEvidence([]);
    setCitationError(false);
  }, [selectedCaseId]);
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

  const runCommand = async (name: string, command: () => Promise<unknown>) => {
    if (!selectedCaseId || busy) return;
    setBusy(name);
    setCommandError(null);
    try {
      await command();
      await Promise.all([loadCases(), loadDetail(selectedCaseId)]);
    } catch (error) {
      setCommandError(lifecycleErrorPresentation(error, locale));
    } finally {
      setBusy(null);
    }
  };

  const currentEvidence = detail?.evidence ?? [];
  const evidenceCitations = useMemo(() => currentEvidence.filter(
    (item) => Boolean(item.evidence_id),
  ), [currentEvidence]);

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
          options={RELEVANCE.map((value) => [value, relevanceLabel(value, t)])}
          allLabel={t(($) => $.lifecycle.filters.all)}
        />
        <FilterSelect
          label={t(($) => $.lifecycle.filters.eventKind)}
          value={filters.event_type ?? ""}
          onChange={(value) => updateFilter("event_type", value as SecurityLifecycleEventType | "")}
          options={EVENT_KINDS.map((value) => [value, eventLabel(value, t)])}
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
            <LifecycleCaseSection title={t(($) => $.lifecycle.sections.source)}>
              <p><strong>{lifecycleSourcePresenceLabel(detail.source_presence, locale)}</strong></p>
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
              {detail.evidence.map((item) => (
                <article className="lifecycle-history-row" key={item.evidence_id}>
                  <p className="lifecycle-provider-evidence">{item.excerpt}</p>
                  {safeEvidenceUrl(item.source_url) ? (
                    <a href={safeEvidenceUrl(item.source_url)!} target="_blank" rel="noreferrer">
                      <ExternalLink size={14} /> {t(($) => $.lifecycle.actions.openEvidence)}
                    </a>
                  ) : null}
                </article>
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
                <div className="lifecycle-commands">
                  <Button
                    size="compact"
                    icon={<Search size={15} />}
                    busy={busy === "search"}
                    onClick={() => void runCommand("search", () => (
                      startSecurityLifecycleInvestigation(detail.case_id, { adapter: "tavily" })
                    ))}
                  >
                    {busy === "search"
                      ? t(($) => $.lifecycle.actions.searching)
                      : t(($) => $.lifecycle.actions.search)}
                  </Button>
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
                <article className="lifecycle-history-row" key={assessment.assessment_id}>
                  <strong>{assessment.author === "legacy_review"
                    ? t(($) => $.lifecycle.states.legacy)
                    : assessment.conclusion}</strong>
                  {assessment.author === "legacy_review" ? (
                    <p>{t(($) => $.lifecycle.states.limitedProvenance)}</p>
                  ) : null}
                  <p>{assessment.impact_summary}</p>
                  {assessment.stale ? <p>{t(($) => $.lifecycle.states.revalidation)}</p> : null}
                  {assessment.status === "draft" && detail.source_presence === "present" ? (
                    <Button
                      size="compact"
                      icon={<Check size={15} />}
                      onClick={() => void runCommand("accept", () => (
                        acceptSecurityLifecycleAssessment(assessment.assessment_id)
                      ))}
                    >
                      {t(($) => $.lifecycle.actions.acceptAssessment)}
                    </Button>
                  ) : null}
                </article>
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
                        <option value={value} key={value}>{relevanceLabel(value, t)}</option>
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
                        <option value={value} key={value}>{confidenceLabel(value, t)}</option>
                      ))}
                    </select>
                  </label>
                  <label>{t(($) => $.lifecycle.fields.outcome)}
                    <select
                      aria-label={t(($) => $.lifecycle.fields.outcome)}
                      value={outcome}
                      onChange={(event) => setOutcome(event.target.value as SecurityLifecycleOutcome)}
                    >
                      {([
                        "undetermined", "listing_ended", "venue_transfer", "symbol_changed",
                        "acquisition_cash", "acquisition_stock", "acquisition_mixed",
                        "acquisition_terms_unknown", "issuer_security_change",
                        "no_tracked_security_change", "other", "not_applicable",
                      ] as const).map((value) => (
                        <option value={value} key={value}>{outcomeLabel(value, t)}</option>
                      ))}
                    </select>
                  </label>
                  <label>{t(($) => $.lifecycle.fields.conclusion)}
                    <textarea
                      aria-label={t(($) => $.lifecycle.fields.conclusion)}
                      value={conclusion}
                      onChange={(event) => setConclusion(event.target.value)}
                    />
                  </label>
                  <label>{t(($) => $.lifecycle.fields.impact)}
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
                          outcomes: [outcome],
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
                    {t(($) => $.lifecycle.actions.saveAssessment)}
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
                    <p className="mono tiny">{proposal.source_snapshot.join(", ")}</p>
                    {proposal.block_reason === "portfolio_position_open" ? (
                      <p>{t(($) => $.lifecycle.states.portfolioBlock)}</p>
                    ) : null}
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
          </>
        ) : null}
      </LifecycleCaseDrawer>
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
