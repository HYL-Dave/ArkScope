import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, Database, ExternalLink, Play, RefreshCw, Save } from "lucide-react";
import {
  ApiError, getSecResearchConfig, getSecResearchFacts, getSecResearchFilings,
  getSecResearchStatus, refreshSecResearch, setSecResearchBudget,
  type SecResearchConfig, type SecResearchEnvelope, type SecResearchFact,
  type SecResearchFiling, type SecResearchReceipt, type SecResearchState,
  type SecResearchStoredStatus,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { Button, IconButton } from "../ui/Button";
import { Tabs } from "../ui/Tabs";
import type { SettingsT } from "./settingsCopy";
import "./secResearch.css";

type Unit = "bytes" | "gib";
type View = "filings" | "facts";
type Page = SecResearchEnvelope<(SecResearchFiling | SecResearchFact)[] | null>;
const GIB = 1073741824n;

function wholeBytes(text: string, unit: Unit): number | null {
  const value = text.trim();
  if (value.length > 100 || !/^\d+(?:\.\d+)?$/.test(value)) return null;
  const [integer, fraction = ""] = value.split(".");
  const denominator = 10n ** BigInt(fraction.length);
  const numerator = BigInt(integer + fraction) * (unit === "gib" ? GIB : 1n);
  if (numerator % denominator !== 0n) return null;
  const bytes = numerator / denominator;
  return bytes > 0n && bytes <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(bytes) : null;
}

function budgetText(bytes: number, unit: Unit): string {
  if (unit === "bytes") return String(bytes);
  // 2^30 divides 10^30 exactly: every whole-byte GiB value has a finite decimal.
  const scaled = (BigInt(bytes) * 5n ** 30n).toString().padStart(31, "0");
  return [scaled.slice(0, -30), scaled.slice(-30)].join(".").replace(/\.?0+$/, "");
}

function normalizeCik(text: string): string | null {
  const match = /^(?:CIK:)?([0-9]{1,10})$/i.exec(text.trim());
  return match && Number(match[1]) > 0 ? match[1].padStart(10, "0") : null;
}

function stateLabel(status: SecResearchState | undefined, t: SettingsT) {
  switch (status) {
    case "ok": return t(($) => $.secResearch.ok);
    case "empty": return t(($) => $.secResearch.empty);
    case "partial": return t(($) => $.secResearch.partial);
    case "unavailable": return t(($) => $.secResearch.unavailable);
    default: return t(($) => $.secResearch.unknown);
  }
}

function errorDetail(error: unknown): string {
  if (error instanceof ApiError && error.code) return error.code;
  return error instanceof Error ? error.message : String(error);
}

function Observation({ value, t }: {
  value: Pick<Page, "status" | "observed_at" | "coverage" | "gaps"> | null;
  t: SettingsT;
}) {
  return <div className="sec-observation">
    <span role="status" data-state={value?.status ?? "unknown"}>{stateLabel(value?.status, t)}</span>
    {value && <>
      <span>{t(($) => $.secResearch.observed)}: {value.observed_at ? formatSystemTimestamp(value.observed_at) : t(($) => $.secResearch.unknown)}</span>
      <details><summary>{t(($) => $.secResearch.coverage)}</summary><pre>{JSON.stringify(value.coverage, null, 2)}</pre></details>
      {value.gaps.length > 0 && <div aria-label={t(($) => $.secResearch.gaps)}>{value.gaps.map((gap, index) => <code key={index}>{gap.code}</code>)}</div>}
    </>}
  </div>;
}

function safeCatalogUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function Records({ page, view, t }: { page: Page | null; view: View; t: SettingsT }) {
  const rows = page?.data ?? [];
  const columns: [string, string][] = view === "filings" ? [
    ["form", t(($) => $.secResearch.form)], ["filed_date", t(($) => $.secResearch.filedDate)],
    ["report_date", t(($) => $.secResearch.reportDate)], ["accepted_at", t(($) => $.secResearch.acceptedAt)],
    ["primary_document", t(($) => $.secResearch.document)], ["primary_url", t(($) => $.secResearch.catalogUrl)],
    ["accession", t(($) => $.secResearch.accession)], ["filing_id", t(($) => $.secResearch.filingId)],
  ] : [
    ["concept", t(($) => $.secResearch.concept)], ["value", t(($) => $.secResearch.value)],
    ["unit", t(($) => $.secResearch.factUnit)], ["end", t(($) => $.secResearch.end)],
    ["start", t(($) => $.secResearch.start)], ["namespace", t(($) => $.secResearch.namespace)],
    ["filed_date", t(($) => $.secResearch.filedDate)], ["accession", t(($) => $.secResearch.accession)],
    ["fact_id", t(($) => $.secResearch.factId)],
  ];
  const present = columns.filter(([key]) => rows.some((row) => row[key] != null && row[key] !== ""));
  return <>
    <Observation value={page} t={t} />
    {rows.length > 0 && <div className="sec-record-scroll" tabIndex={0} role="region" aria-label={t(($) => $.secResearch.views)}>
      <table><thead><tr>{present.map(([key, label]) => <th scope="col" key={key}>{label}</th>)}</tr></thead>
        {/* Catalog variants share filing IDs; stateless rows can use page-local positions. */}
        <tbody>{rows.map((row, index) => <tr key={view === "filings" ? index : String(row.filing_id ?? row.fact_id ?? index)}>{present.map(([key]) => {
          const url = key === "primary_url" ? safeCatalogUrl(row[key]) : null;
          return <td key={key}>{key === "primary_url"
            ? url && <a href={url} target="_blank" rel="noopener noreferrer" title={t(($) => $.secResearch.catalogUrl)} aria-label={t(($) => $.secResearch.catalogUrl)}><ExternalLink size={16} aria-hidden="true" /></a>
            : row[key] == null ? null : String(row[key])}</td>;
        })}</tr>)}</tbody>
      </table>
    </div>}
  </>;
}

export function SecResearchPanel() {
  const { t } = useTranslation("settings");
  const mounted = useRef(false);
  const generation = useRef(0);
  const issuerGeneration = useRef(0);
  const configGeneration = useRef(0);
  const dirty = useRef(false);
  const acquisition = useRef(false);
  const budgetSaving = useRef(false);
  const latestRead = useRef<() => Promise<void>>(async () => {});
  const [config, setConfig] = useState<SecResearchConfig | null>(null);
  const [configError, setConfigError] = useState<unknown>(null);
  const [configBusy, setConfigBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [unit, setUnit] = useState<Unit>("gib");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [cikInput, setCikInput] = useState("");
  const cik = normalizeCik(cikInput);
  const [view, setView] = useState<View>("filings");
  const [forms, setForms] = useState("");
  const [filedFrom, setFiledFrom] = useState("");
  const [filedTo, setFiledTo] = useState("");
  const [amendments, setAmendments] = useState(true);
  const [concepts, setConcepts] = useState("");
  const [asOf, setAsOf] = useState("");
  const [revisions, setRevisions] = useState<"latest" | "all">("latest");
  const [stored, setStored] = useState<SecResearchStoredStatus | null>(null);
  const [receipt, setReceipt] = useState<SecResearchReceipt | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [reading, setReading] = useState(false);
  const [readError, setReadError] = useState<unknown>(null);
  const [refreshBusy, setRefreshBusy] = useState(false);
  const [refreshError, setRefreshError] = useState<unknown>(null);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const bytes = wholeBytes(draft, unit);
  const page = pages[pageIndex] ?? null;

  function applyBudget(value: number) {
    const nextUnit: Unit = value % Number(GIB) === 0 ? "gib" : "bytes";
    setUnit(nextUnit); setDraft(budgetText(value, nextUnit));
  }

  async function loadConfig() {
    if (budgetSaving.current) return;
    const request = ++configGeneration.current;
    setConfigBusy(true);
    try {
      const result = await getSecResearchConfig();
      if (!Number.isSafeInteger(result.capture_budget_bytes) || result.capture_budget_bytes <= 0) throw new Error("sec_config_invalid");
      if (!mounted.current || request !== configGeneration.current) return;
      setConfig(result); setConfigError(null);
      if (!dirty.current) applyBudget(result.capture_budget_bytes);
    } catch (error) {
      if (mounted.current && request === configGeneration.current) { setConfigError(error); setConfig(null); }
    } finally {
      if (mounted.current && request === configGeneration.current) setConfigBusy(false);
    }
  }

  useEffect(() => {
    mounted.current = true;
    void loadConfig();
    return () => { mounted.current = false; generation.current++; issuerGeneration.current++; configGeneration.current++; };
  }, []);

  async function saveBudget() {
    if (bytes == null || !config || budgetSaving.current) return;
    budgetSaving.current = true;
    setSaving(true); setSaved(false); setSaveError(null);
    const request = ++configGeneration.current;
    try {
      await setSecResearchBudget(bytes);
      const confirmed = await getSecResearchConfig();
      if (!Number.isSafeInteger(confirmed.capture_budget_bytes) || confirmed.capture_budget_bytes <= 0) throw new Error("sec_config_invalid");
      if (!mounted.current || request !== configGeneration.current) return;
      setConfig(confirmed); setConfigError(null);
      if (confirmed.capture_budget_bytes !== bytes) throw new Error(t(($) => $.secResearch.confirmationMismatch));
      applyBudget(confirmed.capture_budget_bytes); dirty.current = false; setSaved(true);
    } catch (error) {
      if (mounted.current && request === configGeneration.current) setSaveError(error);
    } finally { budgetSaving.current = false; if (mounted.current) setSaving(false); }
  }

  function invalidate(issuer = false) {
    generation.current++;
    setPages([]); setPageIndex(0); setLoaded(false); setReading(false); setReadError(null);
    if (issuer) { issuerGeneration.current++; setStored(null); setReceipt(null); setRefreshError(null); setUnconfirmed(false); }
  }

  function query(issuer: string, kind: View, cursor?: string): Promise<Page> {
    return kind === "filings" ? getSecResearchFilings(issuer, {
      forms: forms.split(/[\s,]+/).filter(Boolean), filed_from: filedFrom || undefined,
      filed_to: filedTo || undefined, include_amendments: amendments, limit: 20, cursor,
    }) : getSecResearchFacts(issuer, {
      concepts: concepts.split(/[\s,]+/).filter(Boolean), as_of: asOf || undefined,
      revisions, limit: 40, cursor,
    });
  }

  async function readLocal(kind = view) {
    if (!cik) return;
    const request = ++generation.current;
    const current = () => mounted.current && request === generation.current;
    setReading(true); setReadError(null); setPages([]); setPageIndex(0); setLoaded(true);
    const statusRead = getSecResearchStatus(cik).then((result) => { if (current()) setStored(result); })
      .catch((error: unknown) => { if (current()) { setStored(null); setReadError(error); } });
    try {
      const result = await query(cik, kind);
      if (current()) setPages([result]);
    } catch (error) { if (current()) setReadError(error); }
    await statusRead;
    if (current()) setReading(false);
  }
  latestRead.current = readLocal;

  async function nextPage() {
    if (!cik || !page?.next_cursor || reading) return;
    if (pages[pageIndex + 1]) { setPageIndex(pageIndex + 1); return; }
    const request = ++generation.current;
    setReading(true); setReadError(null);
    try {
      const result = await query(cik, view, page.next_cursor);
      if (!mounted.current || request !== generation.current) return;
      setPages([...pages, result]); setPageIndex(pageIndex + 1);
    } catch (error) { if (mounted.current && request === generation.current) setReadError(error); }
    finally { if (mounted.current && request === generation.current) setReading(false); }
  }

  async function refresh(resume: boolean) {
    if (!cik || acquisition.current) return;
    acquisition.current = true;
    const request = issuerGeneration.current;
    generation.current++;
    setReading(false); setRefreshBusy(true); setRefreshError(null); setUnconfirmed(false);
    try {
      const result = await refreshSecResearch(cik, resume);
      if (!mounted.current || request !== issuerGeneration.current) return;
      setReceipt(result);
      void loadConfig();
      void latestRead.current();
    } catch (error) {
      if (!mounted.current || request !== issuerGeneration.current) return;
      if (error instanceof ApiError && error.status < 500) setRefreshError(error);
      else { setUnconfirmed(true); setRefreshError(error); }
    } finally {
      acquisition.current = false;
      if (mounted.current) setRefreshBusy(false);
    }
  }

  const message = (label: string, error: unknown) => t(($) => $.secResearch.errorDetail, { message: label, detail: errorDetail(error) });
  const field = (label: string, value: string, update: (value: string) => void, type = "text") => <label>
    <span>{label}</span><input aria-label={label} type={type} value={value} onChange={(event) => { update(event.target.value); invalidate(); }} />
  </label>;
  const filters = view === "filings" ? <>
    {field(t(($) => $.secResearch.forms), forms, setForms)}
    {field(t(($) => $.secResearch.filedFrom), filedFrom, setFiledFrom, "date")}
    {field(t(($) => $.secResearch.filedTo), filedTo, setFiledTo, "date")}
    <label className="sec-checkbox"><input type="checkbox" checked={amendments} onChange={(event) => { setAmendments(event.target.checked); invalidate(); }} />{t(($) => $.secResearch.amendments)}</label>
  </> : <>
    {field(t(($) => $.secResearch.concepts), concepts, setConcepts)}
    {field(t(($) => $.secResearch.asOf), asOf, setAsOf, "date")}
    <label><span>{t(($) => $.secResearch.revisions)}</span><select aria-label={t(($) => $.secResearch.revisions)} value={revisions} onChange={(event) => { setRevisions(event.target.value as "latest" | "all"); invalidate(); }}>
      <option value="latest">{t(($) => $.secResearch.latest)}</option><option value="all">{t(($) => $.secResearch.all)}</option>
    </select></label>
  </>;
  const table = <>
    <div className="sec-fields">{filters}</div>
    {reading && <p role="status">{t(($) => $.secResearch.loading)}</p>}
    {readError != null && <p role="alert">{message(t(($) => $.secResearch.readError), readError)}</p>}
    <Records page={page} view={view} t={t} />
    <div className="sec-pagination">
      <IconButton size="compact" label={t(($) => $.secResearch.previous)} icon={<ArrowLeft size={16} />} disabled={reading || pageIndex === 0} onClick={() => { setPageIndex(pageIndex - 1); setReadError(null); }} />
      <span>{t(($) => $.secResearch.page, { page: pageIndex + 1 })}</span>
      <IconButton size="compact" label={t(($) => $.secResearch.next)} icon={<ArrowRight size={16} />} disabled={reading || !page?.next_cursor} onClick={() => void nextPage()} />
    </div>
  </>;

  return <section className="sec-storage" aria-label={t(($) => $.secResearch.title)}>
    <h3>{t(($) => $.secResearch.title)}</h3>
    <div className="sec-fields">
      <label><span>{t(($) => $.secResearch.budget)}</span><input aria-label={t(($) => $.secResearch.budget)} inputMode="decimal" maxLength={100} value={draft} disabled={saving} onChange={(event) => { setDraft(event.target.value); dirty.current = true; setSaved(false); setSaveError(null); }} /></label>
      <label><span>{t(($) => $.secResearch.unit)}</span><select aria-label={t(($) => $.secResearch.unit)} value={unit} disabled={saving} onChange={(event) => {
        const nextUnit = event.target.value as Unit;
        if (bytes != null) setDraft(budgetText(bytes, nextUnit));
        setUnit(nextUnit); setSaved(false);
      }}><option value="gib">{t(($) => $.secResearch.gib)}</option><option value="bytes">{t(($) => $.secResearch.bytes)}</option></select></label>
      <Button size="compact" icon={<Save size={16} />} busy={saving} disabled={!config || configBusy || bytes == null} onClick={() => void saveBudget()}>{t(($) => $.secResearch.save)}</Button>
      <IconButton size="compact" label={t(($) => $.secResearch.reloadConfig)} icon={<RefreshCw size={16} />} disabled={saving} busy={configBusy} onClick={() => void loadConfig()} />
    </div>
    {draft && bytes == null && <p role="alert">{t(($) => $.secResearch.invalidBudget)}</p>}
    {configError != null && <p role="alert">{message(t(($) => $.secResearch.configError), configError)}</p>}
    {saveError != null && <p role="alert">{message(t(($) => $.secResearch.saveError), saveError)}</p>}
    {saved && <p role="status">{t(($) => $.secResearch.saved)}</p>}
    <dl className="sec-capacity">
      <dt>{t(($) => $.secResearch.confirmedBudget)}</dt><dd>{config ? t(($) => $.secResearch.byteCount, { value: String(config.capture_budget_bytes) }) : t(($) => $.secResearch.unknown)}</dd>
      {([
        ["persisted_bytes", t(($) => $.secResearch.objects)], ["reserved_bytes", t(($) => $.secResearch.reservations)],
        ["orphan_bytes", t(($) => $.secResearch.orphans)], ["charged_bytes", t(($) => $.secResearch.charged)],
        ["remaining_bytes", t(($) => $.secResearch.remaining)],
      ] as const).map(([key, label]) => <div className="sec-capacity-pair" key={key}><dt>{label}</dt><dd>{config?.capacity ? t(($) => $.secResearch.byteCount, { value: String(config.capacity[key]) }) : t(($) => $.secResearch.unknown)}</dd></div>)}
    </dl>
    {config?.capacity?.over_budget && <p role="status">{t(($) => $.secResearch.overBudget)}</p>}
    <div className="sec-fields">
      <label><span>{t(($) => $.secResearch.cik)}</span><input aria-label={t(($) => $.secResearch.cik)} value={cikInput} onChange={(event) => { setCikInput(event.target.value); invalidate(true); }} /></label>
      <Button size="compact" icon={<Database size={16} />} disabled={!cik} busy={reading} onClick={() => void readLocal()}>{t(($) => $.secResearch.load)}</Button>
      <IconButton size="compact" label={t(($) => $.secResearch.refresh)} icon={<RefreshCw size={16} />} disabled={!cik} busy={refreshBusy} onClick={() => void refresh(false)} />
      <Button size="compact" icon={<Play size={16} />} disabled={!cik || refreshBusy} onClick={() => void refresh(true)}>{t(($) => $.secResearch.resume)}</Button>
    </div>
    {unconfirmed && <p role="alert">{t(($) => $.secResearch.unconfirmed)}</p>}
    {refreshError != null && !unconfirmed && <p role="alert">{message(t(($) => $.secResearch.refreshError), refreshError)}</p>}
    {unconfirmed && <Button size="compact" icon={<Database size={16} />} disabled={!cik} busy={reading} onClick={() => void readLocal()}>{t(($) => $.secResearch.reread)}</Button>}
    <h4>{t(($) => $.secResearch.storedStatus)}</h4>
    <Observation value={stored} t={t} />
    {stored?.data && <details><summary>{t(($) => $.secResearch.snapshots)}</summary><pre>{JSON.stringify(stored.data, null, 2)}</pre></details>}
    {receipt && <><h4>{t(($) => $.secResearch.receipt)}</h4><Observation value={{ ...receipt, coverage: { completed: receipt.completed, pending: receipt.pending } }} t={t} /></>}
    <Tabs<View> ariaLabel={t(($) => $.secResearch.views)} value={view} onValueChange={(next) => {
      if (next === view) return;
      const wasLoaded = loaded;
      setView(next); invalidate();
      if (wasLoaded) void readLocal(next);
    }} items={[
      { value: "filings", label: t(($) => $.secResearch.catalog), panel: table },
      { value: "facts", label: t(($) => $.secResearch.facts), panel: table },
    ]} />
  </section>;
}
