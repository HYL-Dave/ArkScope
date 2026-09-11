import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, BookOpen, Database, ExternalLink, Pin, RefreshCw, Search, X } from "lucide-react";
import {
  ApiError, acquireSecResearchDocument, getSecResearchDocument,
  type SecDocumentAttempt, type SecDocumentPage, type SecDocumentQuery,
  type SecResearchFiling, type SecResearchGap,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { Button, IconButton } from "../ui/Button";

export interface SecDocumentLocator { document_id: string; capture_id?: string }
type ReadingPage = { result: SecDocumentPage; query: SecDocumentQuery };
type Directory = { locator: SecDocumentLocator; pages: SecDocumentPage[]; position: number };
const MAX_CHARS = 6000;

function safeCitationUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function SecDocumentReader({ filing, initial, uncertain, onUncertain, onClose, onCapture }: {
  filing: SecResearchFiling;
  initial?: SecDocumentLocator;
  uncertain: boolean;
  onUncertain: (value: boolean) => void;
  onClose: () => void;
  onCapture: (locator: SecDocumentLocator) => void;
}) {
  const { t } = useTranslation("settings");
  const heading = useRef<HTMLHeadingElement>(null);
  const generation = useRef(0);
  const active = useRef(false);
  const postActive = useRef(false);
  const [locator, setLocator] = useState<SecDocumentLocator>(initial ?? { document_id: "primary" });
  const [pinned, setPinned] = useState(Boolean(initial?.capture_id));
  const [captureInput, setCaptureInput] = useState(initial?.capture_id ?? "");
  const [directory, setDirectory] = useState<Directory | null>(null);
  const [observation, setObservation] = useState<SecDocumentPage | null>(null);
  const [pages, setPages] = useState<ReadingPage[]>([]);
  const [position, setPosition] = useState(0);
  const [section, setSection] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [acquiring, setAcquiring] = useState(false);
  const unknownOutcome = uncertain;
  const [attempt, setAttempt] = useState<SecDocumentAttempt | null>(null);
  const [error, setError] = useState<unknown>(null);
  const page = pages[position];
  const shown = page?.result ?? observation;
  const current = (request: number) => active.current && generation.current === request;
  const operands = (target: SecDocumentLocator): SecDocumentQuery => ({ ...target, max_chars: MAX_CHARS });

  function invalidate() {
    generation.current++; setBusy(false); setError(null); setPages([]); setPosition(0);
  }

  async function readIndex(target: SecDocumentLocator, pin: boolean, keepDirectory = false) {
    const request = ++generation.current;
    setLocator(target); setPinned(pin); setCaptureInput(target.capture_id ?? "");
    setSection(""); setSearch(""); setPages([]); setPosition(0); setObservation(null);
    setBusy(true); setError(null);
    if (!keepDirectory) setDirectory(null);
    try {
      const result = await getSecResearchDocument(filing.filing_id, operands(target));
      if (!current(request)) return;
      setObservation(result);
      const captureId = result.data?.document?.capture_id;
      const bound = captureId ? { ...target, capture_id: captureId } : target;
      setLocator(bound); setCaptureInput(bound.capture_id ?? "");
      if (result.coverage.mode === "index" && captureId) {
        setDirectory({ locator: bound, pages: [result], position: 0 });
        onCapture(bound);
      }
      const cursor = result.data?.text_start_cursor;
      if (cursor && captureId) {
        const query = { ...operands(bound), cursor };
        const text = await getSecResearchDocument(filing.filing_id, query);
        if (current(request)) setPages([{ result: text, query }]);
      }
    } catch (err) { if (current(request)) setError(err); }
    finally { if (current(request)) setBusy(false); }
  }

  useEffect(() => {
    active.current = true;
    heading.current?.focus();
    heading.current?.scrollIntoView?.({ block: "start" });
    void readIndex(initial ?? { document_id: "primary" }, Boolean(initial?.capture_id));
    return () => { active.current = false; generation.current++; };
  }, []);

  async function readPassages(query: SecDocumentQuery, append = false) {
    const request = ++generation.current;
    setBusy(true); setError(null);
    if (!append) { setPages([]); setPosition(0); }
    try {
      const result = await getSecResearchDocument(filing.filing_id, query);
      if (!current(request)) return;
      setPages(append ? [...pages.slice(0, position + 1), { result, query }] : [{ result, query }]);
      setPosition(append ? position + 1 : 0);
    } catch (err) { if (current(request)) setError(err); }
    finally { if (current(request)) setBusy(false); }
  }

  function filter(nextSection = section) {
    void readPassages({ ...operands(locator), section_id: nextSection || undefined, query: search || undefined,
      ...(!nextSection && !search ? { cursor: observation?.data?.text_start_cursor ?? undefined } : {}) });
  }

  function wholeDocument() {
    setSection(""); setSearch("");
    const cursor = shown?.data?.text_start_cursor ?? observation?.data?.text_start_cursor;
    if (cursor) void readPassages({ ...operands(locator), cursor });
  }

  async function nextIndex() {
    if (!directory || busy) return;
    const nextPosition = directory.position + 1;
    if (directory.pages[nextPosition]) { setDirectory({ ...directory, position: nextPosition }); return; }
    const cursor = directory.pages[directory.position]?.next_cursor;
    if (!cursor) return;
    const request = ++generation.current;
    setBusy(true); setError(null);
    try {
      const result = await getSecResearchDocument(filing.filing_id, { ...operands(directory.locator), cursor });
      if (current(request)) setDirectory({ ...directory, pages: [...directory.pages, result], position: nextPosition });
    } catch (err) { if (current(request)) setError(err); }
    finally { if (current(request)) setBusy(false); }
  }

  async function acquire() {
    if (postActive.current || unknownOutcome) return;
    postActive.current = true;
    onUncertain(true);
    const request = ++generation.current;
    setBusy(false); setAcquiring(true); setError(null); setAttempt(null);
    if (locator.capture_id) setPinned(true);
    try {
      const result = await acquireSecResearchDocument(filing.filing_id);
      onUncertain(false);
      if (!current(request)) return;
      setAttempt(result);
      await readIndex({ document_id: "primary" }, false);
    } catch (err) {
      if (err instanceof ApiError && err.status < 500) {
        onUncertain(false);
        if (current(request)) setError(err);
      }
    } finally {
      postActive.current = false;
      if (active.current) setAcquiring(false);
    }
  }

  function gapLabel(gap: SecResearchGap) {
    switch (gap.code) {
      case "stored_document_unavailable": return t(($) => $.secDocument.noCapture);
      case "section_unavailable": return t(($) => $.secDocument.sectionUnavailable);
      case "section_ambiguous": return t(($) => $.secDocument.sectionAmbiguous);
      case "document_index_entry_too_large": return t(($) => $.secDocument.indexEntryTooLarge);
      case "document_page_size_insufficient": return t(($) => $.secDocument.pageInsufficient);
      default: return gap.code;
    }
  }

  const choices = directory?.pages.slice(0, directory.position + 1).flatMap((value) => value.data?.documents ?? []) ?? [];
  const boundDirectory = locator.capture_id && locator.capture_id === directory?.locator.capture_id;
  const sections = boundDirectory ? directory.pages.flatMap((value) => value.data?.sections ?? []) : [];
  const statusLabel = shown?.status === "ok" ? t(($) => $.secResearch.ok)
    : shown?.status === "empty" ? t(($) => $.secResearch.empty)
    : shown?.status === "partial" ? t(($) => $.secResearch.partial)
    : shown?.status === "unavailable" ? t(($) => $.secResearch.unavailable) : t(($) => $.secResearch.unknown);
  const gaps = shown?.gaps ?? [];
  const errorCode = error instanceof ApiError ? error.code ?? String(error.status) : error instanceof Error ? error.message : String(error);

  return <section className="sec-document-reader" aria-label={t(($) => $.secDocument.title)}>
    <div className="sec-document-heading"><h4 ref={heading} tabIndex={-1}>{t(($) => $.secDocument.title)}</h4>
      <IconButton size="compact" label={t(($) => $.secDocument.close)} icon={<X size={16} />} onClick={() => { generation.current++; onClose(); }} />
    </div>
    <dl className="sec-document-identity">
      <dt>{t(($) => $.secResearch.form)}</dt><dd>{filing.form}</dd>
      <dt>{t(($) => $.secResearch.document)}</dt><dd>{filing.primary_document}</dd>
      <dt>{t(($) => $.secResearch.accession)}</dt><dd>{filing.accession}</dd>
      <dt>{t(($) => $.secResearch.filingId)}</dt><dd>{filing.filing_id}</dd>
    </dl>
    <div className="sec-fields">
      <Button size="compact" icon={<RefreshCw size={16} />} busy={acquiring} disabled={unknownOutcome} onClick={() => void acquire()}>{t(($) => $.secDocument.acquire)}</Button>
      <Button size="compact" icon={<Database size={16} />} onClick={() => void readIndex({ document_id: locator.document_id }, false, true)}>{t(($) => $.secDocument.currentAction)}</Button>
      <Button size="compact" icon={<Database size={16} />} onClick={() => void readIndex(unknownOutcome ? { document_id: "primary" } : locator, unknownOutcome ? false : pinned, true)}>{t(($) => $.secDocument.reread)}</Button>
    </div>
    {unknownOutcome && <p role="alert">{t(($) => $.secDocument.unknownOutcome)}</p>}
    {attempt && <div className="sec-document-attempt" role="status">
      <span>{t(($) => $.secDocument.attempt)}: {attempt.status} / {attempt.outcome}</span>
      {attempt.gaps.map((gap, i) => <p key={i}>{gapLabel(gap)}</p>)}
    </div>}
    <div className="sec-fields">
      <label><span>{t(($) => $.secDocument.document)}</span><select aria-label={t(($) => $.secDocument.document)} value={locator.document_id} onChange={(event) => {
        const id = event.target.value;
        const observed = directory?.pages[0]?.data?.document;
        const sameDocument = observed?.document_id === id || (id === "primary"
          && observed?.primary_document != null && observed.document_id === `file:${observed.primary_document}`);
        const captureId = sameDocument && observed?.filing_id === filing.filing_id
          && observed.capture_id === directory?.locator.capture_id ? observed.capture_id : undefined;
        void readIndex({ document_id: id, ...(captureId ? { capture_id: captureId } : {}) }, Boolean(captureId), true);
      }}><option value="primary">{t(($) => $.secResearch.document)}</option>
        {choices.map((entry) => <option key={entry.document_id} value={entry.document_id}>{entry.name}</option>)}
        {locator.document_id !== "primary" && !choices.some((entry) => entry.document_id === locator.document_id) && <option value={locator.document_id}>{locator.document_id}</option>}
      </select></label>
      <label><span>{t(($) => $.secDocument.captureId)}</span><input aria-label={t(($) => $.secDocument.captureId)} value={captureInput} onChange={(event) => { setCaptureInput(event.target.value); invalidate(); }} /></label>
      <IconButton size="compact" label={t(($) => $.secDocument.pinAction)} icon={<Pin size={16} />} disabled={!captureInput} onClick={() => void readIndex({ document_id: locator.document_id, capture_id: captureInput }, true)} />
    </div>
    <div className="sec-document-capture">
      <span>{pinned ? t(($) => $.secDocument.pinned) : t(($) => $.secDocument.current)}</span>
      <code>{locator.capture_id ?? t(($) => $.secDocument.noCapture)}</code>
      <span>{t(($) => $.secDocument.observed)}: {observation?.observed_at ? formatSystemTimestamp(observation.observed_at) : t(($) => $.secResearch.unknown)}</span>
    </div>
    {directory && <div className="sec-document-index">
      <p>{t(($) => $.secDocument.directoryCapture)}: <code>{directory.locator.capture_id}</code></p>
      <div className="sec-pagination">
        <IconButton size="compact" label={t(($) => $.secDocument.indexPrevious)} icon={<ArrowLeft size={16} />} disabled={busy || directory.position === 0} onClick={() => setDirectory({ ...directory, position: directory.position - 1 })} />
        <span>{t(($) => $.secDocument.indexPage, { page: directory.position + 1 })}</span>
        <IconButton size="compact" label={t(($) => $.secDocument.indexNext)} icon={<ArrowRight size={16} />} disabled={busy || !directory.pages[directory.position]?.next_cursor} onClick={() => void nextIndex()} />
      </div>
      {directory.pages[directory.position]?.gaps.map((gap, i) => <p key={i}>{gapLabel(gap)}</p>)}
    </div>}
    <form className="sec-fields" onSubmit={(event) => { event.preventDefault(); filter(); }}>
      <label><span>{t(($) => $.secDocument.section)}</span><select aria-label={t(($) => $.secDocument.section)} value={section} disabled={!boundDirectory} onChange={(event) => { setSection(event.target.value); filter(event.target.value); }}>
        <option value="">{t(($) => $.secDocument.whole)}</option>
        {sections.map((entry) => <option key={entry.section_id} value={entry.section_id}>{entry.label}</option>)}
      </select></label>
      <label><span>{t(($) => $.secDocument.search)}</span><input aria-label={t(($) => $.secDocument.search)} value={search} disabled={!locator.capture_id} onChange={(event) => { setSearch(event.target.value); invalidate(); }} /></label>
      <IconButton size="compact" type="submit" label={t(($) => $.secDocument.searchAction)} icon={<Search size={16} />} disabled={!locator.capture_id} />
      <Button size="compact" icon={<BookOpen size={16} />} disabled={!shown?.data?.text_start_cursor && !observation?.data?.text_start_cursor} onClick={wholeDocument}>{t(($) => $.secDocument.whole)}</Button>
    </form>
    <div className="sec-observation"><span role="status" data-state={shown?.status ?? "unknown"}>{busy ? t(($) => $.secResearch.loading) : statusLabel}</span></div>
    {error != null && <p role="alert">{t(($) => $.secResearch.errorDetail, { message: t(($) => $.secResearch.readError), detail: errorCode })}</p>}
    {gaps.length > 0 && <div aria-label={t(($) => $.secResearch.gaps)}>{gaps.map((gap, i) => <p key={i}>{gapLabel(gap)}</p>)}</div>}
    <div className="sec-document-passages">
      {page?.result.data?.passages.map((passage, i) => {
        const url = safeCitationUrl(passage.citation.source_url);
        return <div className="sec-document-passage" key={i}>
          <pre className="sec-document-text">{passage.text}</pre>
          <div className="sec-document-citation">
            {url && <a href={url} target="_blank" rel="noopener noreferrer" aria-label={t(($) => $.secDocument.source)} title={t(($) => $.secDocument.source)}><ExternalLink size={16} aria-hidden="true" />{t(($) => $.secDocument.source)}</a>}
            <details><summary>{t(($) => $.secDocument.citation)}</summary><pre>{JSON.stringify(passage.citation, null, 2)}</pre></details>
          </div>
        </div>;
      })}
    </div>
    <div className="sec-pagination">
      <IconButton size="compact" label={t(($) => $.secDocument.previous)} icon={<ArrowLeft size={16} />} disabled={busy || position === 0} onClick={() => { generation.current++; setPosition(position - 1); setError(null); }} />
      <span>{t(($) => $.secResearch.page, { page: position + 1 })}</span>
      <IconButton size="compact" label={t(($) => $.secDocument.next)} icon={<ArrowRight size={16} />} disabled={busy || !page?.result.next_cursor} onClick={() => {
        if (pages[position + 1]) { generation.current++; setPosition(position + 1); setError(null); }
        else if (page?.result.next_cursor) void readPassages({ ...page.query, cursor: page.result.next_cursor }, true);
      }} />
    </div>
  </section>;
}
