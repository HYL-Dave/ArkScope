"""Typed SEC research adapters; registration is replaced atomically in Task 2."""

from src.sec_research.runtime import build_tool_service


def list_sec_filings(issuer: str, forms: list[str] | None = None,
                     filed_from: str | None = None, filed_to: str | None = None,
                     include_amendments: bool = True, cursor: str | None = None,
                     limit: int = 20, freshness: str = "auto") -> dict:
    """List receipt-bound SEC filings for an exact ticker or explicit CIK.

    Filter by forms and filing dates; cursors reopen their original observation.
    Freshness is auto, stored, or refresh. Return data, gaps and source coverage.
    """
    return build_tool_service().invoke("list_sec_filings", dict(
        issuer=issuer, forms=forms, filed_from=filed_from, filed_to=filed_to,
        include_amendments=include_amendments, cursor=cursor, limit=limit, freshness=freshness))


def get_sec_financial_facts(issuer: str, metrics: list[str] | None = None,
                          concepts: list[str] | None = None, fact_ids: list[str] | None = None,
                          accession: str | None = None, as_of: str | None = None,
                          period: str = "all", start: str | None = None, end: str | None = None,
                          revisions: str = "latest", cursor: str | None = None,
                          limit: int = 40, freshness: str = "auto") -> dict:
    """Select exact decimal SEC facts with immutable source citations.

    Metrics/concepts select observations; accession, dates, period and revisions
    constrain them. Fact IDs and cursors reopen stored data without acquisition.
    Freshness is auto, stored, or refresh; pins cannot request refresh.
    """
    return build_tool_service().invoke("get_sec_financial_facts", locals())


def read_sec_filing(filing_id: str, document_id: str = "primary",
                    section_id: str | None = None, query: str | None = None,
                    capture_id: str | None = None, cursor: str | None = None,
                    max_chars: int = 6000, freshness: str = "auto") -> dict:
    """Read a filing's document index or exact cited UTF-8 passages.

    Use primary or an observed file ID, never a URL. Section/query select text;
    capture IDs and cursors are stored-only pins. Auto reuses admitted captures;
    refresh records a new observation. max_chars bounds each passage page.
    """
    return build_tool_service().invoke("read_sec_filing", locals())
