import { useEffect, useId, useRef, useState } from "react";
import { RotateCcw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ApiError, getSecResearchCitation, type SecCitation, type SecCitationRead } from "./api";
import { IconButton } from "./ui";

export function SecCitationGap({ code }: { code: string }) {
  const { t } = useTranslation("research");
  const label = code === "sec_citation_missing" ? t(($) => $.citations.missing)
    : code === "sec_citation_integrity_failed" ? t(($) => $.citations.integrityFailed)
      : code === "sec_research_not_installed" ? t(($) => $.citations.notInstalled)
        : code === "sec_citation_invalid" || code === "sec_citation_result_invalid" || code === "sec_citation_query_invalid"
          ? t(($) => $.citations.invalid) : t(($) => $.citations.unavailable);
  return <p className="sec-citation-gap tiny" role="status">{label} <code>{code}</code></p>;
}

type ReadState = { citation: SecCitation; response: SecCitationRead | null; failed: boolean; code?: string };

function validRead(response: SecCitationRead, citation: SecCitation): boolean {
  if (!response || !Array.isArray(response.gaps) || !response.gaps.every((gap) => gap && typeof gap.code === "string")) return false;
  if (response.status === "unavailable") return response.data === null;
  const data = response.data;
  const returned = data?.citation;
  if (response.status !== "ok" || !data || !returned
    || Object.keys(returned).length !== Object.keys(citation).length
    || !Object.entries(citation).every(([key, value]) => (returned as unknown as Record<string, unknown>)[key] === value)) return false;
  if (citation.kind === "document") {
    return "text" in data && typeof data.text === "string" && !!data.document
      && typeof data.document.form === "string" && typeof data.document.mime_type === "string"
      && ["capture_id", "accession", "filing_id", "document_id", "source_url", "original_sha256", "text_sha256", "extraction_version"]
        .every((key) => data.document[key] === (citation as unknown as Record<string, unknown>)[key]);
  }
  if (!("observation" in data) || !data.observation || typeof data.observation !== "object") return false;
  return citation.kind === "fact"
    ? data.observation.fact_id === citation.fact_id && typeof data.observation.value === "string"
    : data.observation.filing_id === citation.filing_id;
}

export function SecCitationView({ citation, onClose }: { citation: SecCitation; onClose: () => void }) {
  const { t } = useTranslation("research");
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<ReadState | null>(null);
  useEffect(() => { closeRef.current?.focus(); }, [citation, attempt]);
  useEffect(() => {
    let alive = true;
    setState(null);
    void getSecResearchCitation(citation).then((response) => {
      if (!alive) return;
      const valid = validRead(response, citation);
      setState({ citation, response: valid ? response : null, failed: !valid });
    }).catch((error: unknown) => {
      const code = error instanceof ApiError && ["sec_citation_invalid", "sec_citation_query_invalid", "sec_citation_missing", "sec_citation_integrity_failed"].includes(error.code ?? "")
        ? error.code! : undefined;
      if (alive) setState({ citation, response: null, failed: true, code });
    });
    return () => { alive = false; };
  }, [citation, attempt]);

  const current = state?.citation === citation ? state : null;
  const data = current?.response?.status === "ok" ? current.response.data : null;
  const observation = data && "observation" in data ? data.observation : null;
  const textValue = (value: unknown) => typeof value === "string" ? value : null;
  const form = textValue(data && "document" in data ? data.document.form : observation?.form);
  const period = [textValue(observation?.start), textValue(observation?.end ?? observation?.report_date)].filter(Boolean).join(" / ");
  const unavailable = current?.failed || current?.response?.status === "unavailable";

  return (
    <section className="sec-citation-view" data-sec-citation-view={citation.kind} role="region" aria-labelledby={titleId}
      onKeyDown={(event) => {
        if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
      }}>
      <header className="sec-citation-head">
        <h3 id={titleId} className="surface-title tiny">{t(($) => $.citations.title)}</h3>
        <IconButton ref={closeRef} tone="ghost" label={t(($) => $.citations.close)} icon={<X size={16} />} onClick={onClose} />
      </header>
      <div className="sec-citation-source tiny muted">{citation.source_url}</div>
      {!current ? <p role="status" className="tiny muted">{t(($) => $.citations.loading)}</p> : null}
      {unavailable ? <div>
        {current?.response?.gaps.length ? current.response.gaps.map((gap, index) => <SecCitationGap key={index} code={gap.code} />)
          : current?.code ? <SecCitationGap code={current.code} />
          : <p role="status" className="tiny">{t(($) => $.citations.unavailable)}</p>}
        <IconButton tone="ghost" label={t(($) => $.citations.retry)} icon={<RotateCcw size={16} />} onClick={() => setAttempt((value) => value + 1)} />
      </div> : null}
      {data ? <>
        {form || period ? <p className="tiny sec-citation-period">{[form, period].filter(Boolean).join(" / ")}</p> : null}
        {"text" in data ? <pre className="sec-citation-text">{data.text}</pre> : <dl className="sec-citation-observation tiny">
          {textValue(observation?.concept) ? <div><dt>{t(($) => $.citations.concept)}</dt><dd>{[textValue(observation?.namespace), textValue(observation?.concept)].filter(Boolean).join(":")}</dd></div> : null}
          {textValue(observation?.value) ? <div><dt>{t(($) => $.citations.value)}</dt><dd>{textValue(observation?.value)} {textValue(observation?.unit)}</dd></div> : null}
          {textValue(observation?.accession) ? <div><dt>{t(($) => $.citations.accession)}</dt><dd>{textValue(observation?.accession)}</dd></div> : null}
          {textValue(observation?.filed_date) ? <div><dt>{t(($) => $.citations.filed)}</dt><dd>{textValue(observation?.filed_date)}</dd></div> : null}
          {textValue(observation?.primary_document) ? <div><dt>{t(($) => $.citations.document)}</dt><dd>{textValue(observation?.primary_document)}</dd></div> : null}
        </dl>}
      </> : null}
    </section>
  );
}
