import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRight, ArrowRightLeft, Check, ChevronLeft, ChevronRight, ExternalLink, RefreshCw, RotateCcw, X } from "lucide-react";
import {
  listCurrentLifecycleReviews, getCurrentLifecycleReview, getLifecycleReviewPacket, confirmLifecycleReview,
  cancelTickerIdentityTransition, retryTickerIdentityTransition, reverseTickerIdentityTransition,
  listTickerIdentityTransitionActivity, acknowledgeTickerIdentityTransitionActivity,
  type CurrentLifecycleReview, type CurrentLifecycleReviewList, type LifecycleReviewPacket,
  type RuntimeConfig, type TickerIdentityTransitionPreviewOptions,
} from "../api";
import type { NavigationTarget } from "../shell/navigation";
import { Button, IconButton } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { LifecycleCaseDrawer, LifecycleCaseSection } from "./LifecycleCaseDrawer";
import { CurrentLifecycleAudit } from "./CurrentLifecycleAudit";
import { LifecycleWebPanel } from "./LifecycleWebPanel";
import { currentReviewCopy, currentSourceCheckLabel } from "./currentReviewPresentation";
import { lifecycleAutomationOperatorDetailLabel, lifecycleTrackingSourceLabel, safeEvidenceUrl } from "./lifecyclePresentation";
import { tickerTransitionBlockReasonLabel, tickerTransitionCaveatLabel } from "./tickerIdentityPresentation";
import { LifecycleActivityBand, transitionBlockLabels, type LifecycleActivityItem } from "./LifecycleActivityBand";
import { useLifecycleSourceCheck } from "./useLifecycleSourceCheck";

type Command = "confirm" | "check" | "resume" | "cancel" | "reverse";

export function LifecycleView({ initialCaseId = null, onNavigate, runtime = null }: {
  initialCaseId?: string | null; onNavigate?: (target: NavigationTarget) => void; runtime?: RuntimeConfig | null;
}) {
  const { t, i18n } = useTranslation("explore");
  const locale = i18n.resolvedLanguage === "en" ? "en" : "zh-Hant";
  const copy = currentReviewCopy(locale);
  const blockLabels = transitionBlockLabels(t);
  const stageLabels = {
    preparing: t(($) => $.lifecycle.automationControl.stages.preparing), sec: t(($) => $.lifecycle.automationControl.stages.sec),
    listing: t(($) => $.lifecycle.automationControl.stages.listing), ibkr: t(($) => $.lifecycle.automationControl.stages.ibkr),
    evaluate: t(($) => $.lifecycle.automationControl.stages.evaluate), persist: t(($) => $.lifecycle.automationControl.stages.persist),
    approve: t(($) => $.lifecycle.automationControl.stages.approve), finalize: t(($) => $.lifecycle.automationControl.stages.finalize),
  };
  const effectLabels = { add: t(($) => $.lifecycle.transition.effects.add), archive: t(($) => $.lifecycle.transition.effects.archive),
    reactivate: t(($) => $.lifecycle.transition.effects.reactivate), unchanged: t(($) => $.lifecycle.transition.effects.unchanged) };
  const providerLabels = { massive: t(($) => $.lifecycle.listingEvidence.authorities.massive),
    eodhd: t(($) => $.lifecycle.listingEvidence.authorities.eodhd), nasdaq: t(($) => $.lifecycle.listingEvidence.authorities.nasdaqTrader) };
  const [view, setView] = useState<"attention" | "history">("attention");
  const [ticker, setTicker] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CurrentLifecycleReviewList | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [listBusy, setListBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CurrentLifecycleReview | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [detailFailed, setDetailFailed] = useState(false);
  const [packet, setPacket] = useState<LifecycleReviewPacket | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [options, setOptions] = useState<TickerIdentityTransitionPreviewOptions>({});
  const [dirty, setDirty] = useState(false);
  const [command, setCommand] = useState<Command | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setErrorCode] = useState<"preview" | "changed" | "unknown" | null>(null);
  const [errorReasons, setErrorReasons] = useState<string[]>([]);
  const [auditRevision, setAuditRevision] = useState(0);
  const [activityOpen, setActivityOpen] = useState(false);
  const [activities, setActivities] = useState<LifecycleActivityItem[]>([]);
  const [activityFailed, setActivityFailed] = useState(false);
  const [activityReverse, setActivityReverse] = useState<string | null>(null);
  const [linkFailed, setLinkFailed] = useState(false);
  const [linkRevision, setLinkRevision] = useState(0);
  const query = useRef({ view, ticker, offset }); query.current = { view, ticker, offset };
  const selected = useRef(selectedId); selected.current = selectedId;
  const listSequence = useRef(0), detailSequence = useRef(0), previewSequence = useRef(0);
  const activitySequence = useRef(0);
  const opener = useRef<HTMLButtonElement | null>(null);
  const mounted = useRef(true);
  const initialOpened = useRef<string | null>(null);
  const commandLock = useRef(false);

  const loadList = useCallback(async () => {
    const token = ++listSequence.current;
    setListBusy(true); setListFailed(false);
    try {
      const result = await listCurrentLifecycleReviews({ ...query.current, limit: 50 });
      if (mounted.current && token === listSequence.current) setPage(result);
    } catch { if (mounted.current && token === listSequence.current) setListFailed(true); }
    finally { if (mounted.current && token === listSequence.current) setListBusy(false); }
  }, []);
  const loadDetail = useCallback(async (id: string) => {
    const token = ++detailSequence.current;
    setDetailBusy(true); setDetailFailed(false);
    try {
      const result = await getCurrentLifecycleReview(id);
      if (mounted.current && token === detailSequence.current && selected.current === id) setDetail(result.item);
    } catch { if (mounted.current && token === detailSequence.current && selected.current === id) setDetailFailed(true); }
    finally { if (mounted.current && token === detailSequence.current && selected.current === id) setDetailBusy(false); }
  }, []);
  const loadActivity = useCallback(async () => {
    const token = ++activitySequence.current;
    try { const value = await listTickerIdentityTransitionActivity({ limit: 50 }); if (mounted.current && token === activitySequence.current) { setActivities(value.items); setActivityFailed(false); } }
    catch { if (mounted.current && token === activitySequence.current) setActivityFailed(true); }
  }, []);
  const refresh = useCallback(() => {
    setPacket(null); setPreviewBusy(false); setErrorCode(null); setErrorReasons([]); setDirty(false); previewSequence.current += 1;
    void loadList(); if (selected.current) void loadDetail(selected.current);
    setAuditRevision((value) => value + 1);
  }, [loadList, loadDetail]);
  const check = useLifecycleSourceCheck(refresh);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; listSequence.current++; detailSequence.current++; previewSequence.current++; activitySequence.current++; }; }, []);
  useEffect(() => { void loadList(); }, [loadList, view, ticker, offset]);
  useEffect(() => {
    setPacket(null); setPreviewBusy(false); setCommand(null); setErrorCode(null); setErrorReasons([]); setDetail(null); setOptions({}); setDirty(false); previewSequence.current += 1;
    if (selectedId) void loadDetail(selectedId);
  }, [selectedId, loadDetail]);
  useEffect(() => {
    if (!initialCaseId || initialOpened.current === initialCaseId) return;
    let cancelled = false;
    const generation = detailSequence.current;
    setLinkFailed(false);
    void listCurrentLifecycleReviews({ case_id: initialCaseId }).then((result) => {
      if (cancelled || generation !== detailSequence.current) return;
      const matches = result.items.filter((row) => row.case_ids.includes(initialCaseId));
      if (matches.length !== 1) { setLinkFailed(true); return; }
      initialOpened.current = initialCaseId;
      selected.current = matches[0].review_id; setSelectedId(matches[0].review_id);
    }).catch(() => { if (!cancelled) setLinkFailed(true); });
    return () => { cancelled = true; };
  }, [initialCaseId, linkRevision]);

  async function preview(nextOptions: TickerIdentityTransitionPreviewOptions = {}) {
    if (!detail?.next_action.assessment_id || busy) return;
    const id = detail.review_id, token = ++previewSequence.current;
    setPreviewBusy(true); setErrorCode(null); setErrorReasons([]);
    try {
      const value = await getLifecycleReviewPacket(detail.next_action.case_id, detail.next_action.assessment_id, nextOptions);
      if (!mounted.current || token !== previewSequence.current || selected.current !== id) return;
      setPacket(value); setDirty(false); setOptions({
        ...(value.options.execute_on ? { execute_on: value.options.execute_on } : {}),
        ...(value.options.priority_resolution ? { priority_resolution: value.options.priority_resolution } : {}),
        unhide_successor: value.options.unhide_successor,
      });
    } catch { if (mounted.current && token === previewSequence.current && selected.current === id) { setPacket(null); setErrorCode("preview"); } }
    finally { if (mounted.current && token === previewSequence.current) setPreviewBusy(false); }
  }
  async function acknowledgeActivity(id: string) {
    if (commandLock.current) return;
    commandLock.current = true; activitySequence.current += 1;
    setBusy(true); setActivityFailed(false);
    try { await acknowledgeTickerIdentityTransitionActivity(id); if (mounted.current) await loadActivity(); }
    catch { if (mounted.current) setActivityFailed(true); }
    finally { commandLock.current = false; if (mounted.current) setBusy(false); }
  }
  async function execute() {
    if ((!detail && !activityReverse) || commandLock.current || !command) return;
    const action = command, transitionId = activityReverse ?? detail?.next_action.transition_id;
    const caseId = detail?.next_action.case_id;
    const reviewed = packet;
    commandLock.current = true;
    setBusy(true); setErrorCode(null); setErrorReasons([]);
    try {
      if (action === "check" && caseId) await check.start(caseId);
      else if (action === "confirm" && reviewed && !dirty) {
        const result = await confirmLifecycleReview(reviewed);
        if (result.status === "blocked" || result.status === "applied_state_changed") { setErrorCode("changed"); setErrorReasons(result.block_reasons); }
      } else if (action === "cancel" && transitionId) await cancelTickerIdentityTransition(transitionId);
      else if (action === "reverse" && transitionId) {
        const result = await reverseTickerIdentityTransition(transitionId);
        if (result.status !== "reversed") { setErrorCode("changed"); setErrorReasons(result.block_reasons); }
      } else if (action === "resume" && transitionId && detail?.next_action.preview_sha256) {
        const result = await retryTickerIdentityTransition(transitionId, { preview_sha256: detail.next_action.preview_sha256 });
        if (!["applied", "already_applied"].includes(result.status)) { setErrorCode("changed"); setErrorReasons(result.block_reasons ?? []); }
      } else throw new Error("review_changed");
      if (action !== "check") { setPacket(null); setDirty(false); void loadList(); if (selected.current) void loadDetail(selected.current); setAuditRevision((value) => value + 1); }
      if (activityOpen) void loadActivity();
    } catch (failure) {
      const code = failure && typeof failure === "object" && "code" in failure ? String(failure.code) : "";
      setErrorCode(["review_changed", "transition_preview_changed", "stale_assessment", "reverse_state_changed"].includes(code) ? "changed" : "unknown");
    } finally { commandLock.current = false; if (mounted.current) { setBusy(false); setCommand(null); setActivityReverse(null); } }
  }
  const disabled = busy || detailBusy || detailFailed || previewBusy || check.busy;
  const title = command === "check" ? t(($) => $.lifecycle.current.checkPrompt, { ticker: detail?.ticker ?? "" })
    : command === "confirm" ? (packet?.action === "terminal_delisting" ? t(($) => $.lifecycle.current.removePrompt, { ticker: detail?.ticker ?? "" }) : copy.renamePrompt)
    : command === "reverse" ? copy.reversePrompt : command === "cancel" ? copy.cancelPrompt : copy.resume;
  const consequence = command === "check" ? copy.checkCost : command === "reverse" ? copy.reverseEffect : command === "cancel" ? copy.preserved
    : (packet?.action ?? detail?.next_action.transition_kind) === "symbol_continuation" ? copy.renameEffect : copy.removeEffect;
  const actionable = detail?.next_action;
  const errorDetails = errorReasons.map((reason) => <p key={reason}>{tickerTransitionBlockReasonLabel(reason, blockLabels, copy.changed)}</p>);

  return <section className="lifecycle-current" aria-label={t(($) => $.lifecycle.aria)}>
    <header className="lifecycle-current-head"><h2>{t(($) => $.lifecycle.title)}</h2>
      <IconButton label={copy.reload} icon={<RefreshCw size={16} />} disabled={busy} onClick={() => { refresh(); check.refresh(); setLinkRevision((value) => value + 1); }} />
    </header>
    {page && <dl className="lifecycle-coverage-summary">
      <div><dt>{copy.tracked}</dt><dd>{page.coverage.tracked ?? copy.unconfirmed}</dd></div>
      <div><dt>{copy.active}</dt><dd>{page.coverage.confirmed_active ?? copy.unconfirmed}</dd></div>
      <div><dt>{copy.unconfirmed}</dt><dd>{page.coverage.unconfirmed ?? copy.unconfirmed}</dd></div>
    </dl>}
    {(check.readFailed || check.status?.active_incident || check.status?.last_status === "failed") && <p role="alert" className="errorbox">{check.readFailed ? copy.checkUnknown : copy.checkFailed}</p>}
    {(check.busy || check.status?.last_status === "running") && <p role="status">{copy.checkRunning}</p>}
    {check.status?.current_progress.map((progress) => <ol className="lifecycle-automation-progress" data-testid="lifecycle-automation-progress" key={progress.request_id}>
      {[...progress.completed_stages, progress.current_stage].filter((stage): stage is NonNullable<typeof stage> => stage !== null)
        .filter((stage, index, all) => !progress.skipped_stages.includes(stage) && all.indexOf(stage) === index)
        .map((stage) => <li key={stage} aria-current={stage === progress.current_stage ? "step" : undefined}>{stageLabels[stage]}</li>)}
    </ol>)}
    {check.error && <p role="alert" className="errorbox">{check.outcomeUnknown ? copy.commandUnknown : copy.checkUnavailable}</p>}
    {linkFailed && <p role="alert" className="errorbox">{copy.linkUnavailable}</p>}
    {error && !detail && <div role="alert" className="errorbox">{error === "unknown" ? copy.commandUnknown : copy.changed}{errorDetails}</div>}
    <div className="lifecycle-current-toolbar">
      <div role="group" aria-label={t(($) => $.lifecycle.queues.aria)} className="lifecycle-view-switch">
        <Button aria-pressed={view === "attention"} onClick={() => { setView("attention"); setOffset(0); }}>{copy.attention}</Button>
        <Button aria-pressed={view === "history"} onClick={() => { setView("history"); setOffset(0); }}>{copy.history}</Button>
      </div>
      <input type="search" aria-label={copy.search} placeholder={copy.search} value={ticker} onChange={(event) => { setTicker(event.target.value); setOffset(0); }} />
      {page && <span className="tiny">{page.counts[view]}</span>}
    </div>
    {listFailed && <div role="alert" className="errorbox">{copy.unavailable}</div>}
    {listBusy && <p role="status">{copy.loading}</p>}
    {page && !listFailed && <>
      <div className="lifecycle-current-table-wrap"><table className="lifecycle-current-table" aria-busy={listBusy}>
        <thead><tr><th>{t(($) => $.lifecycle.filters.ticker)}</th><th>{copy.collection}</th><th>{copy.finding}</th><th>{copy.missing}</th><th>{copy.observed}</th><th aria-label={copy.preview} /></tr></thead>
        <tbody>{page.items.map((row) => <tr key={row.review_id}>
          <td><strong>{row.ticker}</strong>{row.issuer_name && <span className="tiny">{row.issuer_name}</span>}</td>
          <td data-label={copy.collection}>{copy.collections[row.collection.state]}</td>
          <td data-label={copy.finding}><strong>{copy.findings[row.finding]}</strong><span className="tiny">{copy.reasons[row.reason]}</span></td>
          <td data-label={copy.missing}>{lifecycleAutomationOperatorDetailLabel(row.diagnostics, locale) || copy.notObserved}<span className="tiny">{copy.nextCheck}: {row.next_check_at ?? copy.notScheduled}</span></td>
          <td data-label={copy.observed}>{row.observed_at ? <time dateTime={row.observed_at}>{row.observed_at.replace("T", " ").replace("Z", " UTC")}</time> : copy.notObserved}</td>
          <td><IconButton label={t(($) => $.lifecycle.current.inspect, { ticker: row.ticker })} icon={<ArrowRight size={16} />} disabled={busy}
            onClick={(event) => { opener.current = event.currentTarget; selected.current = row.review_id; setSelectedId(row.review_id); }} /></td>
        </tr>)}</tbody>
      </table></div>
      {!page.items.length && !listBusy && <p>{copy.empty}</p>}
      <div className="lifecycle-current-pages">
        <IconButton label={copy.previous} icon={<ChevronLeft size={16} />} disabled={offset === 0 || listBusy} onClick={() => setOffset(Math.max(0, offset - 50))} />
        <span>{page.page.total ? Math.min(offset + 1, page.page.total) : 0}-{Math.min(offset + page.items.length, page.page.total)} / {page.page.total}</span>
        <IconButton label={copy.next} icon={<ChevronRight size={16} />} disabled={offset + page.items.length >= page.page.total || listBusy} onClick={() => setOffset(offset + 50)} />
      </div>
    </>}
    <details onToggle={(event) => { if (event.currentTarget.open) { setActivityOpen(true); void loadActivity(); } }}>
      <summary>{t(($) => $.lifecycle.activity.title)}</summary>
      {activityFailed && <p role="alert">{copy.auditUnavailable}</p>}
      {activityOpen && <LifecycleActivityBand items={activities} busyAction={busy ? "pending" : null}
        onAcknowledge={(id) => void acknowledgeActivity(id)}
        onReverse={(id) => { if (!busy) { setActivityReverse(id); setCommand("reverse"); } }} />}
    </details>
    <LifecycleCaseDrawer open={selectedId !== null} title={detail?.ticker ?? copy.preview} returnFocusRef={opener} onClose={() => { if (!busy) { selected.current = null; setSelectedId(null); } }}>
      {detailBusy && <p role="status">{copy.loading}</p>}
      {detailFailed && <div role="alert" className="errorbox">{copy.unavailable}<Button icon={<RefreshCw size={14} />} onClick={refresh}>{copy.reload}</Button></div>}
      {detail && <>
        <LifecycleCaseSection title={copy.findings[detail.finding]}>
          <p>{detail.issuer_name ?? detail.ticker}</p><p>{copy.reasons[detail.reason]}</p>
          <dl className="lifecycle-current-facts">
            <div><dt>{copy.collection}</dt><dd>{copy.collections[detail.collection.state]}</dd></div>
            <div><dt>{copy.observed}</dt><dd>{detail.observed_at ?? copy.notObserved}</dd></div>
            {detail.listing.ended_on && <div><dt>{t(($) => $.lifecycle.fields.effectiveDate)}</dt><dd>{detail.listing.ended_on}</dd></div>}
            {detail.continuation.successor_ticker && <div><dt>{t(($) => $.lifecycle.fields.successorTicker)}</dt><dd>{detail.continuation.successor_ticker}</dd></div>}
            <div><dt>{copy.nextCheck}</dt><dd>{detail.next_check_at ?? copy.notScheduled}</dd></div>
          </dl>
          {detail.collection.sources.length > 0 && <p className="tiny">{detail.collection.sources.map((source) => lifecycleTrackingSourceLabel(source, locale)).join(" / ")}</p>}
          <p>{lifecycleAutomationOperatorDetailLabel(detail.diagnostics, locale)}</p>
          {actionable && actionable.state !== "not_prepared" && <p className="lifecycle-state" data-action-state={actionable.state}>{copy.states[actionable.state]}{actionable.execute_on ? " / " + actionable.execute_on : ""}</p>}
          {actionable?.block_reasons.map((reason) => <p key={reason}>{tickerTransitionBlockReasonLabel(reason, blockLabels, copy.changed)}</p>)}
          <div className="lifecycle-current-actions">
            {actionable?.kind === "review_removal" && <Button icon={<Check size={15} />} disabled={disabled} onClick={() => void preview()}>{copy.reviewRemoval}</Button>}
            {actionable?.kind === "review_symbol_change" && <Button icon={<ArrowRightLeft size={15} />} disabled={disabled} onClick={() => void preview()}>{copy.reviewRename}</Button>}
            {actionable?.kind === "recheck" && <Button icon={<RefreshCw size={15} />} disabled={disabled || check.status?.last_status === "running"} onClick={() => setCommand("check")}>{copy.checkSources}</Button>}
            {actionable?.kind === "resume" && <Button icon={<Check size={15} />} disabled={disabled} onClick={() => setCommand("resume")}>{copy.resume}</Button>}
            {actionable && ["approved", "scheduled", "blocked"].includes(actionable.state) && <Button icon={<X size={15} />} disabled={disabled} onClick={() => setCommand("cancel")}>{copy.cancel}</Button>}
            {actionable?.state === "applied" && <Button icon={<RotateCcw size={15} />} disabled={disabled || !actionable.can_reverse} onClick={() => setCommand("reverse")}>{copy.reverse}</Button>}
          </div>
        </LifecycleCaseSection>
        {error && <div role="alert" className="errorbox">{error === "preview" ? copy.previewUnavailable : error === "changed" ? copy.changed : copy.commandUnknown}
          {errorDetails}
          <Button icon={<RefreshCw size={14} />} disabled={busy} onClick={refresh}>{copy.reload}</Button></div>}
        {packet && <LifecycleCaseSection title={copy.preview}>
          <p>{packet.finding.conclusion}</p><p>{packet.finding.impact_summary}</p>
          <label className="field lifecycle-current-date"><span>{copy.executionDate}</span><input type="date" value={options.execute_on ?? packet.execute_on ?? ""} disabled={busy}
            onChange={(event) => { setOptions((old) => ({ ...old, execute_on: event.target.value })); setDirty(true); }} /></label>
          {packet.effects.priority.source_value !== packet.effects.priority.successor_value && packet.effects.priority.source_value && packet.effects.priority.successor_value && <fieldset>
            <legend>{copy.priority}</legend>{(["source", "successor"] as const).map((choice) => <label key={choice}><input type="radio" name="review-priority" disabled={busy}
              checked={options.priority_resolution === choice} onChange={() => { setOptions((old) => ({ ...old, priority_resolution: choice })); setDirty(true); }} />{choice === "source" ? packet.source_ticker : packet.finding.successor_ticker}: {choice === "source" ? packet.effects.priority.source_value : packet.effects.priority.successor_value}</label>)}
          </fieldset>}
          {packet.effects.suppression.successor_hidden && <label><input type="checkbox" disabled={busy} checked={options.unhide_successor === true}
            onChange={(event) => { setOptions((old) => ({ ...old, unhide_successor: event.target.checked })); setDirty(true); }} />{copy.unhide}</label>}
          {dirty && <Button icon={<RefreshCw size={14} />} disabled={disabled || options.execute_on === ""} onClick={() => void preview(options)}>{copy.refreshPreview}</Button>}
          <dl className="lifecycle-current-facts">
            {Object.entries(packet.effects.watchlists).filter(([, rows]) => rows.length > 0).map(([action, rows]) => <div key={action}><dt>{copy.affectedLists} / {effectLabels[action as keyof typeof effectLabels]}</dt><dd>{rows.map((r) => `${r.list_name}: ${r.ticker}`).join(" / ")}</dd></div>)}
            {Object.entries(packet.effects.legacy_config_seed).filter(([, rows]) => rows.length > 0).map(([action, rows]) => <div key={`legacy-${action}`}><dt>{lifecycleTrackingSourceLabel("legacy_config_seed", locale)} / {effectLabels[action as keyof typeof effectLabels]}</dt><dd>{rows.map((r) => r.ticker).join(" / ")}</dd></div>)}
            {!!packet.effects.sa_tracking_memberships?.length && <div><dt>{copy.affectedMemberships}</dt><dd>{packet.effects.sa_tracking_memberships.map((r) => `${r.ticker} (${r.picked_date})`).join(" / ")}</dd></div>}
            {!!packet.effects.editable_tags_to_copy.length && <div><dt>{copy.copiedTags}</dt><dd>{packet.effects.editable_tags_to_copy.map((r) => `${r.facet}: ${r.value}`).join(" / ")}</dd></div>}
            {packet.effects.priority.write_successor && <div><dt>{copy.priority}</dt><dd>{packet.effects.priority.result_value}</dd></div>}
          </dl>
          {packet.effects.suppression.hide_source && <p>{copy.hideSource}</p>}
          {packet.effects.suppression.unhide_successor && <p>{copy.unhide}</p>}
          <p className="tiny">{copy.preserved}</p>
          {packet.caveats.map((reason) => <p key={reason}>{tickerTransitionCaveatLabel(reason, {
            provider_owned_sources_retained: t(($) => $.lifecycle.transition.caveats.providerOwnedSourcesRetained),
            portfolio_position_retained: t(($) => $.lifecycle.transition.caveats.portfolioPositionRetained, { ticker: packet.source_ticker }),
            successor_already_tracked: t(($) => $.lifecycle.transition.caveats.successorAlreadyTracked),
          }, copy.unconfirmed)}</p>)}
          {packet.block_reasons.map((reason) => <p role="note" key={reason}>{tickerTransitionBlockReasonLabel(reason, blockLabels, copy.changed)}</p>)}
          <Button tone="primary" icon={<Check size={15} />} disabled={disabled || dirty || !packet.ready || error !== null} onClick={() => setCommand("confirm")}>{copy.confirm}</Button>
        </LifecycleCaseSection>}
        {detail.source_checks.length > 0 && <LifecycleCaseSection title={copy.sourceChecks}>
          <div className="lifecycle-current-checks">{detail.source_checks.map((source, index) => <div key={index}>
            <strong>{providerLabels[source.provider]}</strong>
            <span>{currentSourceCheckLabel(source.directory ?? source.check, locale)} / {source.ticker}</span><span>{copy.sourceStates[source.status]}</span>
            <time className="tiny" dateTime={source.observed_at}>{source.observed_at}</time>
            {safeEvidenceUrl(source.url) && <a aria-label={t(($) => $.lifecycle.actions.openEvidence)} href={source.url!} target="_blank" rel="noreferrer"><ExternalLink size={14} /></a>}
          </div>)}</div>
        </LifecycleCaseSection>}
        <LifecycleWebPanel key={detail.next_action.case_id} caseId={detail.next_action.case_id} ticker={detail.ticker} onChanged={refresh} />
        <CurrentLifecycleAudit key={`${detail.review_id}:${auditRevision}`} caseIds={detail.case_ids} ticker={detail.ticker} notices={detail.source_notices} runtime={runtime} onNavigate={onNavigate} />
      </>}
    </LifecycleCaseDrawer>
    <ConfirmDialog open={command !== null} title={title} consequence={consequence} confirmLabel={command === "check" ? copy.checkSources : command === "reverse" ? copy.reverse : command === "cancel" ? copy.cancel : copy.confirm}
      busy={busy} onConfirm={() => void execute()} onCancel={() => { setCommand(null); setActivityReverse(null); }} />
  </section>;
}
