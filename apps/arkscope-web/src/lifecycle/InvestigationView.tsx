import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowRightLeft, Check, ExternalLink, Play, RefreshCw, Search, Settings2, Square, X } from "lucide-react";
import { getInvestigationTargets, getInvestigationPreflight, latestInvestigation, startInvestigation, getInvestigation,
  cancelInvestigation, getInvestigationReview, confirmInvestigation, listTickerIdentityTransitionActivity,
  acknowledgeTickerIdentityTransitionActivity, reverseTickerIdentityTransition, getInvestigationProviders, checkInvestigationProviders,
  getInvestigationActions, cancelTickerIdentityTransition, retryTickerIdentityTransition,
  prepareInvestigationProviders, confirmLifecycleReview,
  type RuntimeConfig, type LifecycleReviewPacket, type TickerIdentityTransitionPreviewOptions } from "../api";
import type { NavigationTarget } from "../shell/navigation";
import { Button, IconButton } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { ExecutionSource } from "../ExecutionSource";
import { LifecycleActivityBand, type LifecycleActivityItem } from "./LifecycleActivityBand";
import { investigationCopy, investigationReason } from "./investigationPresentation";
import { currentReviewCopy } from "./currentReviewPresentation";
import { webCopy } from "./webPresentation";
import type { InvestigationPreflight, InvestigationRun, InvestigationProviders, InvestigationAction } from "./investigationContract";

function errorCode(value: unknown): string { return value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "investigation_unavailable"; }

export function LifecycleView({ initialTicker = null, initialCaseId = null, onNavigate }: {
  initialTicker?: string | null; initialCaseId?: string | null; onNavigate?: (target: NavigationTarget) => void; runtime?: RuntimeConfig | null;
}) {
  const { i18n } = useTranslation("explore"), locale = i18n.resolvedLanguage === "en" ? "en" : "zh-Hant";
  const copy = investigationCopy(locale);
  const [targets, setTargets] = useState<{ ticker: string }[]>([]), [ticker, setTicker] = useState(initialTicker ?? "");
  const [query, setQuery] = useState(""), [error, setError] = useState(false), [loading, setLoading] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false), [revision, setRevision] = useState(0);
  const mounted = useRef(true), request = useRef(0);
  const read = useCallback(async () => { const token = ++request.current; setLoading(true); setError(false);
    try { const rows = await getInvestigationTargets(); if (mounted.current && token === request.current) setTargets(rows); }
    catch { if (mounted.current && token === request.current) setError(true); }
    finally { if (mounted.current && token === request.current) setLoading(false); } }, []);
  useEffect(() => { mounted.current = true; void read(); return () => { mounted.current = false; request.current++; }; }, [read]);
  useEffect(() => { if (initialTicker) setTicker(initialTicker); }, [initialTicker]);
  const choices = targets.filter(row => row.ticker.toLowerCase().includes(query.toLowerCase()));
  return <section className="investigation-view" aria-label={copy.title}>
    <header className="investigation-heading"><h2>{copy.title}</h2>
      <div className="lifecycle-commands"><IconButton label={copy.refresh} icon={<RefreshCw size={16} />} disabled={loading} onClick={() => { void read(); setRevision(x => x + 1); }} />
        {onNavigate && <IconButton label={copy.settings} icon={<Settings2 size={16} />} onClick={() => onNavigate({ kind: "settings_section", section: "models" })} />}</div>
    </header>
    {error && <p role="alert">{copy.failed}</p>}
    <div className="investigation-layout">
      <aside className="investigation-targets"><label className="field"><span>{copy.target}</span>
        <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={copy.search} /></label>
        <select aria-label={copy.choose} size={8} value={ticker} onChange={e => setTicker(e.target.value)}>
          {ticker && !choices.some(row => row.ticker === ticker) && <option value={ticker}>{ticker}</option>}
          {choices.map(row => <option key={row.ticker} value={row.ticker}>{row.ticker}</option>)}
        </select>{loading ? <p role="status">{copy.loading}</p> : !choices.length && <p>{copy.empty}</p>}
      </aside>
      {ticker ? <InvestigationPanel key={`${ticker}:${locale}`} ticker={ticker} locale={locale} revision={revision}
        onChanged={() => { setRevision(x => x + 1); void read(); }} /> : <p className="investigation-empty">{copy.choose}</p>}
    </div>
    <PendingActions key={revision} locale={locale} onTarget={setTicker} onChanged={() => { setRevision(x => x + 1); void read(); }} />
    <details className="investigation-history" open={historyOpen} onToggle={e => setHistoryOpen(e.currentTarget.open)}>
      <summary>{copy.history}</summary>{historyOpen && <TrackingHistory key={revision} locale={locale}
        onChanged={() => { setRevision(x => x + 1); void read(); }} />}
    </details>
    {initialCaseId && !initialTicker && <p className="tiny">{copy.choose}</p>}
  </section>;
}

function PendingActions({ locale, onTarget, onChanged }: { locale: "en" | "zh-Hant"; onTarget: (ticker: string) => void; onChanged: () => void }) {
  const copy = investigationCopy(locale), current = currentReviewCopy(locale);
  const [rows, setRows] = useState<InvestigationAction[]>([]), [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false);
  const [command, setCommand] = useState<{ item: InvestigationAction; kind: "cancel" | "resume" } | null>(null);
  useEffect(() => { let cancelled = false; void getInvestigationActions().then(value => { if (!cancelled) setRows(value); }).catch(error => { if (!cancelled) setError(errorCode(error)); });
    return () => { cancelled = true; }; }, []);
  async function submit() { if (!command || busy) return; setBusy(true); setError(null);
    try { if (command.kind === "cancel") await cancelTickerIdentityTransition(command.item.transition_id);
      else { const r = await retryTickerIdentityTransition(command.item.transition_id, { preview_sha256: command.item.approved_preview_sha256 });
        if (r.status === "blocked") throw { code: "review_changed" }; }
      onChanged();
    } catch (e) { setError(errorCode(e)); } finally { setBusy(false); setCommand(null); } }
  const commandTitle = command?.kind === "cancel" ? current.cancelPrompt : current.resume;
  if (!rows.length && !error) return null;
  return <section className="investigation-pending"><h3>{copy.pendingActions}</h3>{error && <p role="alert">{investigationReason(error, locale)}</p>}
    {rows.map(item => <div key={item.transition_id} className="investigation-pending-row"><span>{item.source_ticker}{item.successor_ticker && <> / {item.successor_ticker}</>}</span>
      <span>{current.states[item.state]} · {item.execute_on}</span><div className="lifecycle-commands">
        {item.state === "approved" && <Button icon={<Play size={14} />} disabled={busy} onClick={() => setCommand({ item, kind: "resume" })}>{current.resume}</Button>}
        {item.state === "blocked" && <Button icon={<Search size={14} />} disabled={busy} onClick={() => onTarget(item.source_ticker)}>{copy.start}</Button>}
        <Button icon={<X size={14} />} disabled={busy} onClick={() => setCommand({ item, kind: "cancel" })}>{current.cancel}</Button>
      </div></div>)}
    <ConfirmDialog open={command !== null} title={commandTitle} confirmLabel={current.confirm}
      consequence={<p>{command?.kind === "cancel" ? current.preserved : command?.item.kind === "symbol_continuation" ? current.renameEffect : current.removeEffect}</p>}
      busy={busy} onCancel={() => setCommand(null)} onConfirm={() => void submit()} /></section>;
}

function ListingSources({ ticker, locale, revision, onChanged, onReview, disabled }: { ticker: string; locale: "en" | "zh-Hant"; revision: number;
  onChanged: () => void; onReview: (digest: string) => void; disabled: boolean }) {
  const copy = investigationCopy(locale), current = currentReviewCopy(locale);
  const checkTitle = current.checkPrompt.replace("{{ticker}}", ticker);
  const [value, setValue] = useState<InvestigationProviders | null>(null), [error, setError] = useState(false), [busy, setBusy] = useState(false), [ask, setAsk] = useState(false);
  const mounted = useRef(true);
  const gaps = [...new Set(value?.observations.gaps.map(code => copy.providerIssues[code as keyof typeof copy.providerIssues] ?? current.checkIncomplete) ?? [])];
  const decision = value?.decision;
  const finding = decision?.continuation_state === "confirmed" ? "replacement_confirmed" : decision?.listing_state === "inactive" ? "old_listing_inactive" : decision?.listing_state ?? "unresolved";
  const continuationPending = decision && ["candidate", "unavailable", "ambiguous"].includes(decision.continuation_state);
  useEffect(() => { mounted.current = true; let cancelled = false; setError(false);
    void getInvestigationProviders(ticker).then(value => { if (!cancelled) setValue(value); }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; mounted.current = false; }; }, [ticker, revision]);
  async function check() { if (busy) return; setBusy(true); setError(false);
    try { const result = await checkInvestigationProviders(ticker); if (mounted.current) { setValue(result); onChanged(); } }
    catch { if (mounted.current) setError(true); } finally { if (mounted.current) { setBusy(false); setAsk(false); } } }
  return <section className="investigation-listings"><header className="investigation-heading"><h4>{copy.providers}</h4>
    <Button icon={<RefreshCw size={14} />} disabled={busy} onClick={() => setAsk(true)}>{busy ? current.checkRunning : current.checkSources}</Button></header>
    {error && <p role="alert">{copy.providerReadFailed}</p>}
    {value?.observations.observed_at ? <p className="tiny">{current.observed}: <time dateTime={value.observations.observed_at}>{new Date(value.observations.observed_at).toLocaleString(locale)}</time></p> : <p>{copy.providersMissing}</p>}
    {gaps.map(text => <p key={text}>{text}</p>)}
    {decision && <div className="investigation-provider-finding"><p><strong>{current.findings[finding]}</strong></p>
      {decision.listing_end_date && <p className="tiny">{webCopy(locale).effective}: {decision.listing_end_date}</p>}
      {decision.successor_ticker && <p>{webCopy(locale).successor}: {decision.successor_ticker}</p>}
      {continuationPending && <p className="tiny">{copy.continuationPending}{decision.candidate_tickers.length ? ": " + decision.candidate_tickers.join(", ") : ""}</p>}
      {decision.action && <Button icon={<Check size={15} />} disabled={busy || disabled} onClick={() => onReview(decision.check_sha256)}>
        {decision.action === "symbol_continuation" ? current.reviewRename : current.reviewRemoval}</Button>}</div>}
    {!!value?.observations.listings.length && <details className="investigation-source-checks"><summary>{copy.sourceChecks}</summary>
      <ul className="investigation-listing-facts">{value.observations.listings.map((row, i) => <li key={i}><strong>{copy.providerNames[row.provider]}</strong>
        {" · "}{row.candidate_ticker}{" · "}{row.listing_status === "unverified" ? copy.providerUnverified : current.sourceStates[row.listing_status]}
        {row.market && <> · {row.market.toUpperCase()}</>}{row.delisted_utc && <> · {row.delisted_utc.slice(0, 10)}</>}
        <span className="tiny"> · {new Date(row.observed_at).toLocaleString(locale)}</span></li>)}</ul></details>}
    <ConfirmDialog open={ask} title={checkTitle} consequence={<p>{copy.providerBudget}</p>} confirmLabel={current.checkSources}
      busy={busy} onCancel={() => setAsk(false)} onConfirm={() => void check()} />
  </section>;
}

function TrackingHistory({ locale, onChanged }: { locale: "en" | "zh-Hant"; onChanged: () => void }) {
  const copy = investigationCopy(locale), current = currentReviewCopy(locale);
  const [items, setItems] = useState<LifecycleActivityItem[]>([]), [error, setError] = useState(false), [busy, setBusy] = useState(false);
  const [reverse, setReverse] = useState<string | null>(null);
  const read = useCallback(async () => { try { setItems((await listTickerIdentityTransitionActivity({ limit: 50 })).items); setError(false); } catch { setError(true); } }, []);
  useEffect(() => { void read(); }, [read]);
  async function acknowledge(id: string) { if (busy) return; setBusy(true); try { await acknowledgeTickerIdentityTransitionActivity(id); await read(); }
    catch { setError(true); } finally { setBusy(false); } }
  async function undo() { if (!reverse || busy) return; setBusy(true); try { const r = await reverseTickerIdentityTransition(reverse);
    await read(); if (r.status !== "reversed") throw new Error("review_changed"); onChanged(); } catch { setError(true); } finally { setBusy(false); setReverse(null); } }
  return <>{error && <p role="alert">{copy.failed}</p>}<LifecycleActivityBand items={items} busyAction={busy ? "history" : null}
    onAcknowledge={id => void acknowledge(id)} onReverse={setReverse} />
    <ConfirmDialog open={!!reverse} title={current.reversePrompt} consequence={<p>{current.reverseEffect}</p>} confirmLabel={current.confirm}
      busy={busy} onCancel={() => setReverse(null)} onConfirm={() => void undo()} /></>;
}

function InvestigationPanel({ ticker, locale, revision, onChanged }: { ticker: string; locale: "en" | "zh-Hant"; revision: number; onChanged: () => void }) {
  const copy = investigationCopy(locale), current = currentReviewCopy(locale), web = webCopy(locale);
  const [preflight, setPreflight] = useState<InvestigationPreflight | null>(null), [run, setRun] = useState<InvestigationRun | null>(null);
  const [error, setError] = useState<string | null>(null), [loading, setLoading] = useState(true), [busy, setBusy] = useState(false);
  const [packet, setPacket] = useState<LifecycleReviewPacket | null>(null), [dirty, setDirty] = useState(false);
  const [providerDigest, setProviderDigest] = useState<string | null>(null);
  const [options, setOptions] = useState<TickerIdentityTransitionPreviewOptions>({}), [acknowledged, setAcknowledged] = useState(false);
  const [dialog, setDialog] = useState<"start" | "confirm" | null>(null), [receipt, setReceipt] = useState(false);
  const mounted = useRef(true), sequence = useRef(0), lock = useRef(false), requestKey = useRef<string | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  const active = run?.status === "running";
  const read = useCallback(async () => {
    const token = ++sequence.current; setLoading(true); setError(null); setDialog(null); setPacket(null); setProviderDigest(null);
    try {
      const p = await getInvestigationPreflight(ticker, locale);
      if (!mounted.current || token !== sequence.current) return;
      setPreflight(p);
      if (p.reason !== "investigation_not_installed") {
        const r = await latestInvestigation(ticker);
        if (mounted.current && token === sequence.current) { setRun(r); if (r) requestKey.current = null; }
      }
    } catch (e) { if (mounted.current && token === sequence.current) setError(errorCode(e)); }
    finally { if (mounted.current && token === sequence.current) setLoading(false); }
  }, [ticker, locale]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);
  useEffect(() => { void read(); }, [read, revision]);
  useEffect(() => {
    if (!active || !run) return;
    let cancelled = false, timer: ReturnType<typeof setTimeout>;
    const id = run.run_id;
    const poll = async () => { try { const next = await getInvestigation(id); if (!cancelled && mounted.current) {
      if (next.ticker !== ticker) throw new Error("investigation_payload_invalid"); setRun(next); setError(null);
      if (next.status === "running") timer = setTimeout(poll, 2000);
    } } catch (e) { if (!cancelled && mounted.current) { setError(errorCode(e)); timer = setTimeout(poll, 5000); } } };
    timer = setTimeout(poll, 1500); return () => { cancelled = true; clearTimeout(timer); };
  }, [run?.run_id, active, ticker]);
  async function stop() { if (!run || lock.current) return; lock.current = true; setBusy(true);
    try { const next = await cancelInvestigation(run.run_id); if (mounted.current) setRun(next); }
    catch (e) { if (mounted.current) setError(errorCode(e)); } finally { lock.current = false; if (mounted.current) setBusy(false); } }
  async function preview(nextOptions: TickerIdentityTransitionPreviewOptions = {}, fromProvider: string | null = null) {
    if ((!run && !fromProvider) || lock.current) return; lock.current = true; setBusy(true); setError(null); setAcknowledged(false);
    try { const p = fromProvider ? await prepareInvestigationProviders(ticker, fromProvider, nextOptions) : await getInvestigationReview(run!.run_id, nextOptions);
      if (p.source_ticker !== ticker) throw new Error("investigation_payload_invalid");
      if (mounted.current) { setPacket(p); setProviderDigest(fromProvider); setOptions({ execute_on: p.options.execute_on ?? undefined,
        priority_resolution: p.options.priority_resolution ?? undefined, unhide_successor: p.options.unhide_successor }); setDirty(false); }
    } catch (e) { if (mounted.current) { setError(errorCode(e)); setPacket(null); } }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function submit() {
    if (lock.current || !dialog) return; lock.current = true; setBusy(true); setError(null);
    try {
      if (dialog === "start" && preflight?.available && preflight.preflight_sha256) {
        requestKey.current ??= crypto.randomUUID();
        const job = await startInvestigation(ticker, { preflight_sha256: preflight.preflight_sha256, request_key: requestKey.current, language: locale });
        const next = await getInvestigation(job.run_id);
        if (next.ticker !== ticker) throw new Error("investigation_payload_invalid");
        requestKey.current = null;
        if (mounted.current) { setRun(next); setPacket(null); setReceipt(false); }
      } else if (dialog === "confirm" && packet?.ready && (run || providerDigest) && !dirty && (!packet.source_gaps?.length || acknowledged)) {
        const confirmation = providerDigest ? await confirmLifecycleReview(packet) : await confirmInvestigation(run!.run_id, packet, acknowledged);
        if (["blocked", "applied_state_changed"].includes(confirmation.status)) throw { code: "review_changed" };
        if (mounted.current) { setReceipt(true); setPacket(null); onChanged(); }
      }
    } catch (e) { if (mounted.current) { setError(errorCode(e)); setPacket(null); } }
    finally { lock.current = false; if (mounted.current) { setBusy(false); setDialog(null); } }
  }
  const identity = run?.target ?? preflight?.target;
  const groups = packet ? Object.entries(packet.effects.watchlists).flatMap(([kind, rows]) => rows.map(row => `${web.effects[kind as keyof typeof web.effects]} / ${row.list_name}: ${row.ticker}`))
    .concat((packet.effects.sa_tracking_memberships ?? []).map(row => `${current.affectedMemberships}: ${row.ticker} (${row.picked_date})`))
    .concat(Object.entries(packet.effects.legacy_config_seed).flatMap(([kind, rows]) => rows.map(row => `${web.effects[kind as keyof typeof web.effects]} / ${row.source_key}: ${row.ticker}`)))
    .concat(packet.effects.editable_tags_to_copy.map(row => `${current.copiedTags}: ${row.facet} / ${row.value}`)) : [];
  const title = packet?.action === "symbol_continuation" ? `${current.reviewRename}: ${ticker} → ${packet.finding.successor_ticker ?? ""}` : web.removePrompt.replace("{ticker}", ticker);
  const dialogTitle = dialog === "start" ? copy.startTitle.replace("{ticker}", ticker) : title;
  return <div className="investigation-panel">
    <header className="investigation-heading"><div><h3>{ticker}</h3>{identity?.issuer_name && <p>{identity.issuer_name}</p>}</div></header>
    {loading && <p role="status">{copy.loading}</p>}
    {error && <p role="alert" className="errorbox">{investigationReason(error, locale)}</p>}
    <ListingSources ticker={ticker} locale={locale} revision={revision} onChanged={onChanged} disabled={busy || active || preflight?.reason === "target_not_tracked"}
      onReview={digest => void preview({}, digest)} />
    {preflight && !preflight.available && <p>{investigationReason(preflight.reason, locale)}</p>}
    {run && <ExecutionSource source="previous" receipt={run.execution} />}
    <div className="lifecycle-commands">{active ? <Button icon={<Square size={14} />} disabled={busy || run.cancel_requested} onClick={() => void stop()}>{copy.stop}</Button>
      : <Button tone="primary" icon={<Search size={15} />} disabled={busy || loading || !preflight?.available} onClick={e => { opener.current = e.currentTarget; setDialog("start"); }}>{run ? copy.rerun : copy.start}</Button>}
      {run && <span role="status">{copy.status[run.status]}{active && <> / {copy.phases[run.phase as keyof typeof copy.phases] ?? copy.phaseUnknown}</>}</span>}</div>
    {run?.failure_code && <p role="alert">{investigationReason(run.failure_code, locale)}</p>}
    {run?.stop_reason && <p>{investigationReason(run.stop_reason, locale)}</p>}
    {receipt && <p role="status">{copy.receipt}</p>}
    {run?.finding && <section className="investigation-result">
      <h4>{web.events[run.finding.event_kind]}</h4><p className="investigation-conclusion">{run.finding.summary}</p>
      {run.finding.limitations.map((value, i) => <p className="tiny" key={i}>{value}</p>)}
      <dl className="lifecycle-current-facts"><div><dt>{web.security}</dt><dd>{run.finding.security_class} / {run.finding.venue}</dd></div>
        {run.finding.effective_date && <div><dt>{web.effective}</dt><dd>{run.finding.effective_date}</dd></div>}
        {run.finding.successor_ticker && <div><dt>{web.successor}</dt><dd>{run.finding.successor_ticker}</dd></div>}</dl>
      {run.block_reasons.map(code => <p key={code}>{investigationReason(code, locale)}</p>)}
      {[...run.finding.contradictions, ...run.finding.unresolved_conditions].map((value, i) => <p key={i}>{value}</p>)}
      {run.action && !receipt && <Button icon={run.action === "symbol_continuation" ? <ArrowRightLeft size={15} /> : <Check size={15} />} disabled={busy} onClick={() => void preview()}>
        {run.action === "symbol_continuation" ? current.reviewRename : current.reviewRemoval}</Button>}
      <details className="investigation-evidence"><summary>{copy.evidence} ({run.passages.length})</summary>
        {run.passages.map((p, i) => <article key={`${p.passage_id}:${i}`}>
          {p.url ? <a href={p.url} target="_blank" rel="noreferrer noopener"><ExternalLink size={13} /> {p.title ?? new URL(p.url).hostname}</a> : <span>{p.title ?? copy.local}</span>}
          <blockquote>{p.text}</blockquote><p className="tiny">{p.publisher} · {copy.readAt}: <time dateTime={p.retrieved_at}>{new Date(p.retrieved_at).toLocaleString(locale)}</time></p>
        </article>)}</details>
    </section>}
    {!!run?.gaps.length && <details className="investigation-gaps"><summary>{copy.gaps} ({run.gaps.length})</summary><ul>{run.gaps.map((gap, i) => <li key={i}>
      {gap.url && <a href={gap.url} target="_blank" rel="noreferrer noopener">{new URL(gap.url).hostname}</a>} {investigationReason(gap.reason, locale)}</li>)}</ul></details>}
    {run && <details className="investigation-details" open={active}><summary>{copy.details}</summary>
      <dl className="investigation-stats">{Object.entries(copy.stats).map(([key, label]) => <div key={key}><dt>{label}</dt>
        <dd>{run.stats[key as keyof typeof run.stats]?.toLocaleString(locale) ?? copy.unknown}</dd></div>)}
        <div><dt>{copy.tokens}</dt><dd>{run.stats.input_tokens?.toLocaleString(locale) ?? copy.unknown} / {run.stats.output_tokens?.toLocaleString(locale) ?? copy.unknown}</dd></div></dl>
      <ol className="investigation-progress">{run.steps.filter(step => step.reason || step.code).map(step => <li key={step.ordinal}>
        {step.reason ?? investigationReason(step.code, locale)}</li>)}</ol>
    </details>}
    {packet && <section className="investigation-review"><h4>{current.preview}</h4>
      <p>{current.findings[packet.action === "symbol_continuation" ? "replacement_confirmed" : "old_listing_inactive"]}</p>
      <ul>{groups.map((g, i) => <li key={i}>{g}</li>)}</ul>
      {packet.effects.suppression.hide_source && <p>{current.hideSource}</p>}
      <label className="field"><span>{current.executionDate}</span><input type="date" value={options.execute_on ?? packet.execute_on ?? ""} disabled={busy}
        onChange={e => { setOptions(old => ({ ...old, execute_on: e.target.value })); setDirty(true); }} /></label>
      {packet.effects.priority.source_value && packet.effects.priority.successor_value && packet.effects.priority.source_value !== packet.effects.priority.successor_value && <fieldset>
        <legend>{current.priority}</legend>{(["source", "successor"] as const).map(value => <label key={value}><input type="radio" name="investigation-priority" disabled={busy}
          checked={options.priority_resolution === value} onChange={() => { setOptions(old => ({ ...old, priority_resolution: value })); setDirty(true); }} />
          {value === "source" ? ticker : packet.finding.successor_ticker}: {packet.effects.priority[`${value}_value`]}</label>)}
      </fieldset>}
      {packet.effects.suppression.successor_hidden && <label><input type="checkbox" disabled={busy} checked={options.unhide_successor === true}
        onChange={e => { setOptions(old => ({ ...old, unhide_successor: e.target.checked })); setDirty(true); }} />{current.unhide}</label>}
      {packet.block_reasons.map(code => <p key={code}>{investigationReason(code, locale)}</p>)}
      {!!packet.source_gaps?.length && <aside><h5>{copy.gaps}</h5><ul>{packet.source_gaps.map((gap, i) => <li key={i}>
        {gap.url && <a href={gap.url} target="_blank" rel="noreferrer noopener">{new URL(gap.url).hostname}</a>} {investigationReason(gap.reason, locale)}</li>)}</ul>
        <label><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} disabled={busy} />{copy.acknowledge}</label></aside>}
      <p className="tiny">{current.preserved}</p><div className="lifecycle-commands">
        {dirty && <Button icon={<RefreshCw size={14} />} disabled={busy || options.execute_on === ""} onClick={() => void preview(options, providerDigest)}>{current.refreshPreview}</Button>}
        <Button icon={<Check size={15} />} disabled={busy || dirty || !packet.ready || (!!packet.source_gaps?.length && !acknowledged)}
          onClick={e => { opener.current = e.currentTarget; setDialog("confirm"); }}>{current.confirm}</Button></div>
    </section>}
    <ConfirmDialog open={dialog !== null} title={dialogTitle} confirmLabel={dialog === "start" ? copy.start : current.confirm}
      busy={busy} tone={dialog === "start" ? "primary" : "danger"} onCancel={() => setDialog(null)} onConfirm={() => void submit()} returnFocusRef={opener}
      consequence={dialog === "start" ? <><ExecutionSource source="next" receipt={preflight?.execution} />
        <p>{copy.budget.replace("{models}", String(preflight?.limits?.model_submissions)).replace("{searches}", String(preflight?.limits?.web_actions)).replace("{reads}", String(preflight?.limits?.source_reads))}</p>
        <p>{copy.policy}</p><p>{copy.inBackground}</p>{preflight?.limits?.search_enforcement === "observed" && <p>{copy.nativeObserved}</p>}</>
        : <><p>{packet?.finding.impact_summary}</p><p>{packet?.action === "symbol_continuation" ? current.renameEffect : current.removeEffect}</p><ul>{groups.map((g, i) => <li key={i}>{g}</li>)}</ul><p>{current.preserved}</p></>} />
  </div>;
}
