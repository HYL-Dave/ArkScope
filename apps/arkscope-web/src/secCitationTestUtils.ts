import type { SecCitation, SecCitationRead } from "./api";

export const factCitation: SecCitation = {
  kind: "fact", cik: "0000000123", fact_id: `secfact_${"a".repeat(64)}`,
  snapshot_id: `secsnapshot_${"b".repeat(64)}`, source_sha256: "c".repeat(64),
  source_pointer: "/facts/us-gaap/Assets/units/USD/0",
  source_url: "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json",
  observed_at: "2026-09-12T00:00:00Z",
};
export const filingCitation: SecCitation = {
  kind: "filing", filing_id: "0000000123:0000000123-26-000001",
  snapshot_id: `secsnapshot_${"d".repeat(64)}`, source_sha256: "e".repeat(64),
  source_pointer: "/filings/recent/0",
  source_url: "https://data.sec.gov/submissions/CIK0000000123.json",
  observed_at: "2026-09-12T00:00:00Z",
};
export const documentCitation: SecCitation = {
  kind: "document", filing_id: "0000000123:0000000123-26-000001",
  document_id: "file:annual.htm", capture_id: `secdoc_${"f".repeat(64)}`,
  accession: "0000000123-26-000001",
  source_url: "https://www.sec.gov/Archives/edgar/data/123/000000012326000001/annual.htm",
  original_sha256: "1".repeat(64), text_sha256: "2".repeat(64),
  extraction_version: "sec-document-text-v1", start_byte: 0, end_byte: 12,
  match_start_byte: null, match_end_byte: null,
};

export function citationRead(citation: SecCitation, text = "Retained passage"): SecCitationRead {
  const source = citation.kind === "document" ? null : {
    source: { sha256: citation.source_sha256, pointer: citation.source_pointer },
    snapshot_id: citation.snapshot_id, observed_at: citation.observed_at,
    source_url: citation.source_url, object_sha256: citation.source_sha256,
  };
  return {
    status: "ok", gaps: [], observed_at: "2026-09-12T00:00:00Z",
    coverage: { complete: true }, next_cursor: null,
    data: citation.kind === "document" ? {
      citation, text, document: {
        capture_id: citation.capture_id, accession: citation.accession,
        filing_id: citation.filing_id, document_id: citation.document_id,
        form: "10-K", source_url: citation.source_url,
        original_sha256: citation.original_sha256, text_sha256: citation.text_sha256,
        extraction_version: citation.extraction_version, mime_type: "text/html",
      },
    } : citation.kind === "fact" ? {
      citation, observation: {
        ...source, cik: citation.cik, fact_id: citation.fact_id,
        namespace: "us-gaap", concept: "Assets", value: "12345678901234567890.00100",
        unit: "USD", start: null, end: "2025-12-31", fiscal_year: 2025,
        fiscal_period: "FY", frame: null, accession: "0000000123-26-000001",
        form: "10-K", filed_date: "2026-02-01",
      },
    } : {
      citation, observation: {
        ...source, cik: "0000000123", filing_id: citation.filing_id,
        accession: "0000000123-26-000001", form: "10-K", filed_date: "2026-02-01",
        report_date: "2025-12-31", accepted_at: "2026-02-01T12:00:00Z",
        primary_document: "annual.htm", primary_url: documentCitation.source_url,
      },
    },
  };
}
