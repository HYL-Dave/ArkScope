import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { FileText } from "lucide-react";

import { getResearchRun, getResearchRunEvents, type ResearchRunDTO, type SecCitation, type SecCitationTrace } from "./api";
import { SecCitationGap, SecCitationView } from "./SecCitationView";
import {
  presentResearchRoute,
  presentResearchSelection,
  researchEvidenceStatusLabel,
  researchEvidenceTimingLabel,
  researchEvidenceTokenRows,
} from "./i18n/researchPresentation";
import { stanceLabel } from "./personalizationDisplay";
import { ResearchPersonalizationContext } from "./ResearchPersonalizationContext";
import { sanitizeResearchDiagnostic } from "./researchErrors";
import type { Message, ToolTraceRow, TraceRow } from "./researchReducer";
import { quotaKindForAuthMode } from "./researchSelection";
import { formatSystemTimestamp } from "./timeDisplay";
import { Button, Drawer, InlineAlert, StatusBadge } from "./ui";

interface EvidenceRow extends SecCitationTrace {
  name: string;
  input?: unknown;
  resultPreview?: string;
  completion: "complete" | "running" | "recorded";
}

interface FetchedRunAuthority {
  runId: string;
  run: ResearchRunDTO;
}

interface DiagnosticRunState {
  runId: string;
  diagnostic: string | null;
  failed: boolean;
  loading: boolean;
}

function freshestRunDetail(
  fetchedRun: ResearchRunDTO | null,
  activeRun: ResearchRunDTO | null,
): ResearchRunDTO | null {
  if (!fetchedRun) return activeRun;
  if (!activeRun) return fetchedRun;
  return Date.parse(activeRun.updated_at) >= Date.parse(fetchedRun.updated_at)
    ? activeRun
    : fetchedRun;
}

export function researchEvidenceRows(
  message: Message | null,
  activeTrace: readonly TraceRow[],
): EvidenceRow[] {
  if (!message && activeTrace.length > 0) {
    return activeTrace
      .filter((row): row is ToolTraceRow => row.kind === "tool")
      .map(({ kind: _kind, done, chars: _chars, result_preview, ...row }) => ({
        ...row,
        resultPreview: result_preview,
        completion: done ? "complete" : "running",
      }));
  }
  return (message?.tool_calls ?? []).map(({ result_preview, ...call }) => ({
    ...call,
    resultPreview: result_preview,
    completion: "recorded",
  }));
}

function boundedPreview(value: string | undefined): string | null {
  if (!value) return null;
  return value.length > 500 ? `${value.slice(0, 500)}…` : value;
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "[unserializable]";
  }
}

export function ResearchEvidenceDrawer({
  open,
  pinned,
  onClose,
  onPinnedChange,
  returnFocusRef,
  message,
  activeTrace,
  activeRun,
  developerMode,
}: {
  open: boolean;
  pinned: boolean;
  onClose: () => void;
  onPinnedChange: (pinned: boolean) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  message: Message | null;
  activeTrace: readonly TraceRow[];
  activeRun: ResearchRunDTO | null;
  developerMode: boolean;
}) {
  const { t: researchT, i18n: researchI18n } = useTranslation("research");
  const { t: commonT } = useTranslation("common");
  const researchLocale = researchI18n.resolvedLanguage;
  const sourceListDelimiter = researchLocale === "en" ? ", " : "、";
  const evidence = useMemo(
    () => researchEvidenceRows(message, activeTrace),
    [activeTrace, message],
  );
  const hasEvidence = evidence.length > 0;
  const evidenceOwner = message ?? activeRun?.id ?? activeTrace;
  const [sourceSelection, setSourceSelection] = useState<{
    owner: typeof evidenceOwner; key: string; citation: SecCitation;
  } | null>(null);
  const sourceTriggers = useRef(new Map<string, HTMLButtonElement>());
  const selectedSource = open && sourceSelection?.owner === evidenceOwner ? sourceSelection : null;
  useEffect(() => { setSourceSelection(null); }, [open, evidenceOwner]);
  const closeSource = () => {
    const trigger = selectedSource ? sourceTriggers.current.get(selectedSource.key) : null;
    setSourceSelection(null);
    if (trigger?.isConnected) trigger.focus();
  };
  // A selected transcript turn owns its exact linkage. Never borrow a newer
  // active/latest run for a legacy message that has no persisted run_id.
  const runId = message ? (message.runId ?? null) : (activeRun?.id ?? null);
  const [fetchedAuthority, setFetchedAuthority] = useState<FetchedRunAuthority | null>(null);
  const [detailState, setDetailState] = useState<"idle" | "loading" | "ready" | "partial">("idle");
  const [diagnosticState, setDiagnosticState] = useState<DiagnosticRunState | null>(null);
  const diagnosticAuthorityRef = useRef({ generation: 0, runId: null as string | null });
  const visibleDiagnosticState = diagnosticState?.runId === runId ? diagnosticState : null;

  useEffect(() => {
    const authority = {
      generation: diagnosticAuthorityRef.current.generation + 1,
      runId: open ? runId : null,
    };
    diagnosticAuthorityRef.current = authority;
    const revokeAuthority = () => {
      if (
        diagnosticAuthorityRef.current.generation === authority.generation
        && diagnosticAuthorityRef.current.runId === authority.runId
      ) {
        diagnosticAuthorityRef.current = {
          generation: authority.generation + 1,
          runId: null,
        };
      }
    };
    setDiagnosticState(runId && open ? {
      runId,
      diagnostic: null,
      failed: false,
      loading: false,
    } : null);
    if (!open || !runId) {
      setFetchedAuthority(null);
      setDetailState("idle");
      return revokeAuthority;
    }
    let alive = true;
    setFetchedAuthority(null);
    setDetailState("loading");
    void getResearchRun(runId)
      .then(({ run }) => {
        if (!alive) return;
        setFetchedAuthority({ runId, run });
        setDetailState("ready");
      })
      .catch(() => {
        if (!alive) return;
        setDetailState("partial");
      });
    return () => {
      alive = false;
      revokeAuthority();
    };
  }, [open, runId]);

  const loadDiagnostics = () => {
    const authority = diagnosticAuthorityRef.current;
    const diagnosticRunId = authority.runId;
    const stateForAuthority = diagnosticState?.runId === diagnosticRunId ? diagnosticState : null;
    if (
      !developerMode
      || !diagnosticRunId
      || stateForAuthority?.diagnostic != null
      || stateForAuthority?.failed
      || stateForAuthority?.loading
    ) return;
    const authorityIsCurrent = () => (
      diagnosticAuthorityRef.current.generation === authority.generation
      && diagnosticAuthorityRef.current.runId === diagnosticRunId
    );
    setDiagnosticState({
      runId: diagnosticRunId,
      diagnostic: null,
      failed: false,
      loading: true,
    });
    void getResearchRunEvents(diagnosticRunId, 0)
      .then((response) => {
        if (!authorityIsCurrent()) return;
        const safe = response.events.map((event) => ({
          seq: event.seq,
          type: event.type,
          created_at: event.created_at,
          data: event.data,
        }));
        const nextDiagnostic = sanitizeResearchDiagnostic(safeJson(safe), 8_000);
        setDiagnosticState((current) => (
          authorityIsCurrent() && current?.runId === diagnosticRunId
            ? { ...current, diagnostic: nextDiagnostic }
            : current
        ));
      })
      .catch(() => {
        setDiagnosticState((current) => (
          authorityIsCurrent() && current?.runId === diagnosticRunId
            ? { ...current, failed: true }
            : current
        ));
      })
      .finally(() => {
        setDiagnosticState((current) => (
          authorityIsCurrent() && current?.runId === diagnosticRunId
            ? { ...current, loading: false }
            : current
        ));
      });
  };

  const fetchedRun = fetchedAuthority?.runId === runId && fetchedAuthority.run.id === runId
    ? fetchedAuthority.run
    : null;
  const activeRunCandidate = activeRun?.id === runId ? activeRun : null;
  const details = freshestRunDetail(fetchedRun, activeRunCandidate);
  const usage = details?.token_usage ?? message?.token_usage ?? null;
  const personalization = message?.personalization ?? null;
  const messagePersonalizationKnown = message != null && message.personalization !== undefined;
  const detailPersonalizationKnown = details != null && details.personalization !== undefined;
  const personalizationContext = messagePersonalizationKnown
    ? (message.personalization ?? null)
    : (details?.personalization ?? null);
  const personalizationContextKnown = messagePersonalizationKnown || detailPersonalizationKnown;
  const hasTranscriptDetails = Boolean(details || message);
  const route = useMemo(() => {
    if (details) {
      return presentResearchRoute({
        provider: details.provider,
        model: details.model,
        effort: details.effort,
        runId: details.id,
        errorCode: details.error_code,
      }, researchT);
    }
    if (message?.provider || message?.model || message?.effort) {
      return presentResearchRoute({
        provider: message.provider,
        model: message.model,
        effort: message.effort,
        runId: message.runId,
        errorCode: message.errorCode,
      }, researchT);
    }
    return null;
  }, [details, message, researchLocale, researchT]);
  const auth = useMemo(() => {
    if (!details?.auth_mode) return null;
    return presentResearchSelection({
      provenance: null,
      authMode: details.auth_mode,
      quotaKind: quotaKindForAuthMode(details.auth_mode),
      reasonCode: null,
    }, researchT, commonT);
  }, [commonT, details?.auth_mode, researchLocale, researchT]);
  const tokenRows = useMemo(
    () => researchEvidenceTokenRows(usage, researchT),
    [researchLocale, researchT, usage],
  );
  let factOrdinal = 0;

  return (
    <Drawer
      open={open}
      title={researchT(($) => $.evidence.drawerTitle)}
      onClose={onClose}
      returnFocusRef={returnFocusRef}
      pinnable={hasEvidence}
      pinned={pinned && hasEvidence}
      onPinnedChange={onPinnedChange}
    >
      <div className="research-evidence" data-has-evidence={String(hasEvidence)}>
        <section>
          <h3 className="surface-title tiny">{researchT(($) => $.evidence.toolEvidence)}</h3>
          {hasEvidence ? (
            <ul className="research-evidence-list">
              {evidence.map((row, index) => (
                <li key={row.call_id ?? `${row.name}-${index}`} className="research-evidence-tool" data-call-id={row.call_id}>
                  <div className="research-evidence-tool-head">
                    <span className="mono">{row.name}</span>
                    <StatusBadge
                      state={row.completion === "running" ? "running" : "ready"}
                      label={researchEvidenceStatusLabel(row.completion, researchT)}
                    />
                  </div>
                  {row.input !== undefined ? (
                    <pre className="research-evidence-input mono tiny muted">{safeJson(row.input)}</pre>
                  ) : null}
                  {boundedPreview(row.resultPreview) ? (
                    <div className="research-evidence-preview tiny muted">{boundedPreview(row.resultPreview)}</div>
                  ) : null}
                  {row.sec_citations?.map((citation, citationIndex) => {
                    const key = `${index}:${citationIndex}`;
                    const label = citation.kind === "document" ? citation.document_id
                      : citation.kind === "filing" ? citation.filing_id : citation.cik;
                    const kind = citation.kind === "document" ? researchT(($) => $.citations.document)
                      : citation.kind === "filing" ? researchT(($) => $.citations.filing)
                        : researchT(($) => $.citations.fact, { position: ++factOrdinal });
                    return <Button key={key} tone="ghost" size="compact" className="sec-citation-open"
                      data-sec-citation-open={key} aria-expanded={selectedSource?.key === key}
                      aria-label={researchT(($) => $.citations.open, { kind, label })}
                      ref={(element) => { if (element) sourceTriggers.current.set(key, element); else sourceTriggers.current.delete(key); }}
                      icon={<FileText size={16} />} onClick={() => setSourceSelection({ owner: evidenceOwner, key, citation })}>
                      <span>{kind}: {label}</span>
                    </Button>;
                  })}
                  {row.sec_citation_gaps?.map((code, gapIndex) => <SecCitationGap key={gapIndex} code={code} />)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted tiny">{researchT(($) => $.evidence.noToolEvidence)}</p>
          )}
        </section>

        {selectedSource ? <SecCitationView key={selectedSource.key} citation={selectedSource.citation} onClose={closeSource} /> : null}

        <section className="research-run-details">
          <h3 className="surface-title tiny">{researchT(($) => $.evidence.runDetails)}</h3>
          {!runId ? <p className="muted tiny">{researchT(($) => $.evidence.legacyNoRunLink)}</p> : null}
          {detailState === "loading" && !details ? (
            <p className="muted tiny">{researchT(($) => $.evidence.loadingRunDetails)}</p>
          ) : null}
          {detailState === "partial" ? (
            <InlineAlert state="partial" title={researchT(($) => $.evidence.partialTitle)}>
              {researchT(($) => $.evidence.partialDetail)}
            </InlineAlert>
          ) : null}
          {hasTranscriptDetails ? (
            <dl className="research-run-detail-list">
              {route ? (
                <div>
                  <dt>{researchT(($) => $.evidence.route)}</dt>
                  <dd>{route.providerLabel} · {route.modelLabel} · {route.effortLabel}</dd>
                </div>
              ) : null}
              {auth?.authLabel ? (
                <div>
                  <dt>{researchT(($) => $.evidence.authAndQuota)}</dt>
                  <dd>{auth.billingCopy
                    ? researchT(($) => $.evidence.authQuotaSummary, {
                      label: auth.authLabel,
                      billing: auth.billingCopy,
                    })
                    : auth.authLabel}</dd>
                </div>
              ) : null}
              {details ? (
                <div><dt>{researchEvidenceTimingLabel("created", researchT)}</dt><dd>{formatSystemTimestamp(details.created_at)}</dd></div>
              ) : null}
              {details ? (
                <div><dt>{researchEvidenceTimingLabel("started", researchT)}</dt><dd>{formatSystemTimestamp(details.started_at)}</dd></div>
              ) : null}
              {details ? (
                <div><dt>{researchEvidenceTimingLabel("completed", researchT)}</dt><dd>{formatSystemTimestamp(details.completed_at)}</dd></div>
              ) : null}
              {!details && message?.created_at ? (
                <div><dt>{researchEvidenceTimingLabel("turn_saved", researchT)}</dt><dd>{formatSystemTimestamp(message.created_at)}</dd></div>
              ) : null}
              {message?.elapsed_seconds != null ? (
                <div>
                  <dt>{researchEvidenceTimingLabel("model_elapsed", researchT)}</dt>
                  <dd>{message.elapsed_seconds.toFixed(1)}{researchT(($) => $.evidence.secondsSuffix)}</dd>
                </div>
              ) : null}
              {personalization?.profile_active && personalization.assistant_stance !== "off" ? (
                <div><dt>{researchT(($) => $.evidence.stance)}</dt><dd>{stanceLabel(personalization.assistant_stance, commonT)}</dd></div>
              ) : null}
              {personalization?.applied_skills?.length ? (
                <div><dt>{researchT(($) => $.evidence.appliedSkills)}</dt><dd>{personalization.applied_skills.join(sourceListDelimiter)}</dd></div>
              ) : null}
              {(message?.tools_used?.length ?? 0) > 0 ? (
                <div><dt>{researchT(($) => $.evidence.tools)}</dt><dd>{message!.tools_used.join(sourceListDelimiter)}</dd></div>
              ) : null}
              {tokenRows.map((row) => (
                <div key={row.key}><dt>{row.label}</dt><dd>{row.value.toLocaleString()}</dd></div>
              ))}
            </dl>
          ) : null}
          {personalizationContextKnown ? (
            <ResearchPersonalizationContext trace={personalizationContext} />
          ) : null}
          {developerMode && runId ? (
            <details
              key={runId}
              className="research-diagnostic"
              onToggle={(event) => { if (event.currentTarget.open) loadDiagnostics(); }}
            >
              <summary>{researchT(($) => $.evidence.diagnosticEvents)}</summary>
              {visibleDiagnosticState?.loading ? <p className="muted tiny">{researchT(($) => $.evidence.loading)}</p> : null}
              {visibleDiagnosticState?.diagnostic ? <pre>{visibleDiagnosticState.diagnostic}</pre> : null}
              {visibleDiagnosticState?.failed ? <p className="error-text tiny">{researchT(($) => $.evidence.diagnosticsFailed)}</p> : null}
            </details>
          ) : null}
        </section>
      </div>
    </Drawer>
  );
}
