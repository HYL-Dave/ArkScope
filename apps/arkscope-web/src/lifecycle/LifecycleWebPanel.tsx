import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRightLeft, Check, ExternalLink, RefreshCw, Search, Square } from "lucide-react";
import { getLifecycleWebPreflight, latestLifecycleWebRun, startLifecycleWebRun, getLifecycleWebRun,
  cancelLifecycleWebRun, getLifecycleWebReview, confirmLifecycleWebReview,
  type LifecycleReviewPacket, type TickerIdentityTransitionPreviewOptions } from "../api";
import { Button, IconButton } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { currentReviewCopy } from "./currentReviewPresentation";
import { webCopy, webReason } from "./webPresentation";
import { webIsRunning, type WebPreflight, type WebQuestion, type WebRun } from "./webContract";

function SourceGaps({ gaps, locale }: { gaps: WebRun["source_gaps"]; locale: "en" | "zh-Hant" }) {
  if (!gaps?.length) return null;
  const copy = webCopy(locale);
  return <aside className="lifecycle-web-gaps" aria-label={copy.sourceGapTitle}>
    <p>{copy.sourceGapSummary.replace("{count}", String(gaps.length))}</p>
    <ul>{gaps.map((gap, index) => <li key={index}>
      {gap.url ? <a href={gap.url} title={gap.url} target="_blank" rel="noreferrer noopener">
        <ExternalLink size={13} />{new URL(gap.url).hostname}</a> : <span>{copy.sourceGapUrlUnknown}</span>}
      <span>{copy.errors[gap.reason as keyof typeof copy.errors] ?? copy.sourceGapReasonUnknown}</span>
    </li>)}</ul>
  </aside>;
}

function UsageRecord({ run, locale }: { run: WebRun; locale: "en" | "zh-Hant" }) {
  const copy = webCopy(locale), report = run.usage_report;
  const format = (value: number | null) => value === null ? copy.usageUnknown : value.toLocaleString(locale);
  const totals = report?.coverage === "complete" ? report.totals : report?.known_subtotal;
  return <details className="lifecycle-web-usage">
    <summary>{copy.usageDetails}</summary>
    {!report ? <p>{copy.usageLegacy}</p> : <>
      <p>{copy.usageCoverage[report.coverage]} / {copy.usageRecorded}: {report.recorded_submissions} / {run.model_submissions}</p>
      <h4>{report.coverage === "complete" ? copy.usageTotal : copy.usageSubtotal}</h4>
      <dl><div><dt>{copy.usageInput}</dt><dd>{format(totals!.input_tokens)}</dd></div>
        <div><dt>{copy.usageOutput}</dt><dd>{format(totals!.output_tokens)}</dd></div></dl>
      {report.phases.map((phase) => <div key={phase.phase} className="lifecycle-web-usage-phase">
        <h4>{copy.usagePhases[phase.phase]}</h4><p className="tiny">{copy.usageBasis[phase.basis]}</p>
        <dl>{([
          [copy.usageInput, phase.input_tokens], [copy.usageOutput, phase.output_tokens],
          ...(phase.basis === "claude_model_usage" ? [
            [copy.usageCacheCreated, phase.cache_creation_input_tokens], [copy.usageCacheRead, phase.cache_read_input_tokens],
            [copy.usageSearch, phase.web_search_requests],
          ] : []),
        ] as [string, number | null][]).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{format(value)}</dd></div>)}</dl>
      </div>)}
    </>}
    <p className="tiny">{copy.usageScopeNote}</p>
  </details>;
}

export function LifecycleWebPanel({ caseId, ticker, onChanged }: { caseId: string; ticker: string; onChanged: () => void }) {
  const { i18n } = useTranslation("explore"), locale = i18n.resolvedLanguage === "en" ? "en" : "zh-Hant";
  const copy = webCopy(locale), current = currentReviewCopy(locale);
  const [question, setQuestion] = useState<WebQuestion>("listing_status");
  const [preflight, setPreflight] = useState<WebPreflight | null>(null);
  const [run, setRun] = useState<WebRun | null>(null);
  const [packet, setPacket] = useState<LifecycleReviewPacket | null>(null);
  const [options, setOptions] = useState<TickerIdentityTransitionPreviewOptions>({});
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"start" | "confirm" | null>(null);
  const alive = useRef(true), sequence = useRef(0), locked = useRef(false), opener = useRef<HTMLButtonElement | null>(null);
  const active = webIsRunning(run);
  const read = useCallback(async () => {
    const token = ++sequence.current;
    setLoading(true); setErrorCode(null); setPacket(null); setDirty(false); setDialog(null);
    try {
      const next = await getLifecycleWebPreflight(caseId, question);
      if (!alive.current || sequence.current !== token) return;
      if (next.case_id !== caseId) throw new Error("web_payload_changed");
      setPreflight(next);
      // A not-installed journal is already an explicit preflight state.
      const result = next.reason === "web_journal_not_installed" ? null : await latestLifecycleWebRun(caseId);
      if (!alive.current || sequence.current !== token) return;
      if (result && (result.case_id !== caseId || result.ticker !== ticker)) throw new Error("web_payload_changed");
      setRun(result);
    } catch { if (alive.current && sequence.current === token) setErrorCode("web_read_unavailable"); }
    finally { if (alive.current && sequence.current === token) setLoading(false); }
  }, [caseId, question, ticker]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; sequence.current++; }; }, []);
  useEffect(() => { void read(); }, [read]);
  useEffect(() => {
    if (!run || !active) return;
    let stopped = false, timer: ReturnType<typeof setTimeout>;
    const identity = run.run_id;
    const poll = async () => {
      try {
        const next = await getLifecycleWebRun(identity);
        if (stopped || !alive.current) return;
        if (!next || next.case_id !== caseId || next.run_id !== identity || next.ticker !== ticker) throw new Error("web_payload_changed");
        setRun(next); setErrorCode(null);
        if (webIsRunning(next)) timer = setTimeout(poll, 2000);
      } catch { if (!stopped && alive.current) setErrorCode("web_read_unavailable"); }
    };
    timer = setTimeout(poll, 2000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [run?.run_id, active, caseId, ticker]);

  async function review(nextOptions: TickerIdentityTransitionPreviewOptions = {}) {
    if (!run || locked.current) return;
    const token = ++sequence.current, id = run.run_id;
    locked.current = true; setBusy(true); setErrorCode(null);
    try {
      const next = await getLifecycleWebReview(id, nextOptions);
      if (!alive.current || token !== sequence.current) return;
      if (next.case_id !== caseId || next.source_ticker !== ticker) throw new Error("web_payload_changed");
      setPacket(next); setOptions({ execute_on: next.options.execute_on ?? undefined,
        priority_resolution: next.options.priority_resolution ?? undefined, unhide_successor: next.options.unhide_successor }); setDirty(false);
    } catch { if (alive.current && token === sequence.current) { setPacket(null); setErrorCode("web_review_unavailable"); } }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  async function stop() {
    if (!run || locked.current) return;
    locked.current = true; setBusy(true); setErrorCode(null);
    try { const next = await cancelLifecycleWebRun(run.run_id); if (alive.current) setRun(next); }
    catch { if (alive.current) setErrorCode("web_cancel_unknown"); }
    finally { locked.current = false; if (alive.current) setBusy(false); }
  }
  async function submit() {
    if (locked.current || !dialog) return;
    locked.current = true; setBusy(true); setErrorCode(null);
    try {
      if (dialog === "start" && preflight?.available && preflight.preflight_sha256) {
        const result = await startLifecycleWebRun(caseId, { question, preflight_sha256: preflight.preflight_sha256, request_key: crypto.randomUUID() });
        const next = await getLifecycleWebRun(result.run_id);
        if (alive.current) { setRun(next); setPacket(null); }
      } else if (dialog === "confirm" && run && packet && !dirty) {
        const result = await confirmLifecycleWebReview(run.run_id, packet);
        if (alive.current) {
          if (["blocked", "applied_state_changed"].includes(result.status)) setErrorCode("review_changed");
          setPacket(null); onChanged();
        }
      }
    } catch (failure) {
      const code = failure && typeof failure === "object" && "code" in failure ? String(failure.code) : "web_command_unknown";
      if (alive.current) { setErrorCode(code); setPacket(null); }
    } finally { locked.current = false; if (alive.current) { setBusy(false); setDialog(null); } }
  }
  const execution = run?.execution ?? preflight?.execution;
  const isLaunch = dialog === "start";
  const action = packet?.action ?? run?.finding?.action;
  const actionTitle = action === "symbol_continuation" ? `${current.reviewRename}: ${ticker} -> ${packet?.finding.successor_ticker ?? run?.finding?.successor_ticker ?? ""}`
    : copy.removePrompt.replace("{ticker}", ticker);
  const groups = packet ? [
    ...Object.entries(packet.effects.watchlists).flatMap(([effect, rows]) => rows.map((row) => `${copy.effects[effect as keyof typeof copy.effects]} / ${row.list_name}: ${row.ticker}`)),
    ...Object.entries(packet.effects.legacy_config_seed).flatMap(([effect, rows]) => rows.map((row) => `${copy.effects[effect as keyof typeof copy.effects]} / ${copy.legacy}: ${row.ticker}`)),
    ...(packet.effects.sa_tracking_memberships ?? []).map((row) => `${current.affectedMemberships}: ${row.ticker} (${row.picked_date})`),
    ...packet.effects.editable_tags_to_copy.map((row) => `${current.copiedTags}: ${row.facet} / ${row.value}`),
  ] : [];
  return <section className="lifecycle-web" aria-label={copy.title}>
    <header><h3>{copy.title}</h3><IconButton label={copy.reload} icon={<RefreshCw size={15} />} onClick={() => void read()} disabled={busy || loading} /></header>
    {loading && <p role="status">{current.loading}</p>}
    {execution && <p className="tiny lifecycle-web-provenance">{execution.model} / {copy.auth[execution.auth_mode]}</p>}
    {errorCode && <p role="alert" className="errorbox">{webReason(errorCode, locale)}</p>}
    {preflight && !preflight.available && <p>{webReason(preflight.reason, locale)}</p>}
    {run && <p role="status">{copy.status[run.status]}</p>}
    {run?.failure_code && <p>{webReason(run.failure_code, locale)}</p>}
    {!!run?.source_reads?.length && <details>
      <summary>{copy.sourceReadDetails}</summary>
      <ol>{run.source_reads.map((item) => <li key={item.request_index} value={item.request_index}>
        {item.status !== null && <span>{copy.sourceHttpStatus.replace("{status}", String(item.status))} / </span>}
        {item.result_code === "complete" ? copy.sourceComplete : item.result_code === "redirect" ? copy.sourceRedirect : webReason(item.result_code, locale)}
        <p className="tiny">{copy.sourceReadBytes.replace("{received}", String(item.received_body_bytes))
          .replace("{declared}", item.declared_body_bytes === null ? copy.sourceLengthUnknown : String(item.declared_body_bytes))
          .replace("{decoded}", String(item.decoded_body_bytes))}</p>
      </li>)}</ol>
    </details>}
    {run && <UsageRecord run={run} locale={locale} />}
    {active ? <Button icon={<Square size={14} />} disabled={busy || run?.status === "cancelling"} onClick={() => void stop()}>{copy.stop}</Button>
      : <div className="lifecycle-web-launch">
        <label className="field"><span>{copy.question}</span><select value={question} disabled={busy || loading} onChange={(event) => setQuestion(event.target.value as WebQuestion)}>
          <option value="listing_status">{copy.listing}</option><option value="symbol_continuation">{copy.rename}</option>
        </select></label>
        <Button icon={<Search size={15} />} disabled={busy || loading || !preflight?.available} onClick={(event) => { opener.current = event.currentTarget; setDialog("start"); }}>{copy.start}</Button>
      </div>}
    {run?.finding && <div className="lifecycle-web-result">
      <h4>{copy.events[run.finding.event_kind]}</h4><p>{run.finding.summary}</p>
      <SourceGaps gaps={run.source_gaps} locale={locale} />
      {run.source_reading && run.source_reading.selected_sources > 0 && <p className="tiny">{copy.selectedSources}</p>}
      <dl className="lifecycle-current-facts">
        <div><dt>{copy.security}</dt><dd>{run.finding.issuer_name} / {run.finding.security_class} / {run.finding.venue}</dd></div>
        {run.finding.effective_date && <div><dt>{copy.effective}</dt><dd>{run.finding.effective_date}</dd></div>}
        {run.finding.successor_ticker && <div><dt>{copy.successor}</dt><dd>{run.finding.successor_ticker}</dd></div>}
      </dl>
      {run.finding.block_reasons.map((code) => <p key={code}>{webReason(code, locale)}</p>)}
      {[...run.finding.contradictions, ...run.finding.unresolved_conditions].map((value, index) => <p key={index}>{value}</p>)}
      <ol className="lifecycle-web-citations">{run.finding.citations.map((citation, index) => <li key={`${citation.url}:${index}`}>
        <a href={citation.url} target="_blank" rel="noreferrer noopener"><ExternalLink size={13} /> {new URL(citation.url).hostname}</a>
        <blockquote>{citation.quote}</blockquote><time className="tiny" dateTime={citation.retrieved_at}>{citation.retrieved_at.replace("T", " ")}</time>
      </li>)}</ol>
      {run.finding.action && <Button icon={run.finding.action === "symbol_continuation" ? <ArrowRightLeft size={15} /> : <Check size={15} />} disabled={busy} onClick={() => void review()}>
        {run.finding.action === "symbol_continuation" ? current.reviewRename : current.reviewRemoval}</Button>}
    </div>}
    {packet && <div className="lifecycle-web-review">
      <h4>{current.preview}</h4><ul>{groups.map((group, index) => <li key={index}>{group}</li>)}</ul>
      <label className="field lifecycle-current-date"><span>{current.executionDate}</span><input type="date" disabled={busy} value={options.execute_on ?? packet.execute_on ?? ""}
        onChange={(event) => { setOptions((old) => ({ ...old, execute_on: event.target.value })); setDirty(true); }} /></label>
      {packet.effects.priority.source_value && packet.effects.priority.successor_value && packet.effects.priority.source_value !== packet.effects.priority.successor_value && <fieldset>
        <legend>{current.priority}</legend>{(["source", "successor"] as const).map((value) => <label key={value}><input type="radio" name="web-priority" disabled={busy}
          checked={options.priority_resolution === value} onChange={() => { setOptions((old) => ({ ...old, priority_resolution: value })); setDirty(true); }} />
          {value === "source" ? ticker : packet.finding.successor_ticker}: {packet.effects.priority[`${value}_value`]}</label>)}
      </fieldset>}
      {packet.effects.suppression.successor_hidden && <label><input type="checkbox" disabled={busy} checked={options.unhide_successor === true}
        onChange={(event) => { setOptions((old) => ({ ...old, unhide_successor: event.target.checked })); setDirty(true); }} />{current.unhide}</label>}
      {packet.effects.suppression.hide_source && <p>{current.hideSource}</p>}
      {packet.effects.priority.write_successor && <p>{current.priority}: {packet.effects.priority.result_value}</p>}
      <p className="tiny">{current.preserved}</p>
      {packet.block_reasons.map((code) => <p key={code}>{webReason(code, locale)}</p>)}
      {dirty && <Button icon={<RefreshCw size={14} />} disabled={busy || options.execute_on === ""} onClick={() => void review(options)}>{current.refreshPreview}</Button>}
      <Button icon={<Check size={15} />} disabled={busy || dirty || !packet.ready} onClick={(event) => { opener.current = event.currentTarget; setDialog("confirm"); }}>{current.confirm}</Button>
    </div>}
    <ConfirmDialog open={dialog !== null} title={isLaunch ? copy.start : actionTitle}
      confirmLabel={isLaunch ? copy.start : current.confirm} busy={busy} tone={isLaunch ? "primary" : "danger"}
      onCancel={() => setDialog(null)} onConfirm={() => void submit()} returnFocusRef={opener}
      consequence={isLaunch ? <>
        <p>{preflight?.credential_label} / {preflight?.execution?.model} / {preflight?.execution && copy.auth[preflight.execution.auth_mode]}</p>
        <p>{copy.cost.replace("{models}", String(preflight?.limits?.model_submissions)).replace("{sources}", String(preflight?.limits?.source_requests))}</p>
        <p>{copy.noFallback}</p>{preflight?.limits?.search_enforcement === "observed" && <p>{copy.observedBudget}</p>}
        {preflight?.limits?.background_retention && <p>{copy.retention}</p>}
        {run?.status === "remote_outcome_unknown" && <p>{copy.unknownCost}</p>}
      </> : <><p>{packet?.finding.impact_summary}</p>
        <SourceGaps gaps={packet?.source_gaps ?? null} locale={locale} />
        <p>{action === "symbol_continuation" ? current.renameEffect : current.removeEffect}</p>
        <ul>{groups.map((group, index) => <li key={index}>{group}</li>)}</ul><p>{current.preserved}</p></>} />
  </section>;
}
