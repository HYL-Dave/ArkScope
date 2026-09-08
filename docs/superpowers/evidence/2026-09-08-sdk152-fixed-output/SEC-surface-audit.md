# SEC Surface Audit

Status: read-only product assessment, not an approved implementation or migration.
No SEC/provider requests, production database queries, collector configuration
changes, or deletion were performed for this assessment.

## Current responsibilities

| Surface | Actual behavior | Recommendation |
| --- | --- | --- |
| Settings `SEC company events` | `src/service/data_scheduler.py` still advertises `sec_corporate_actions`. Its collector checks the new lifecycle journal and returns `retired` before constructing the SEC client when cutover is installed. | Retire the obsolete scheduling controls, preserving history; do not relabel the old job as a new financials collector. |
| Target investigation | `src/lifecycle_investigation/agent.py` prioritizes relevant local news and original issuer/exchange notices, with SEC optional low-priority supplementation. | Retain on-demand SEC access when it helps a particular question, without recreating a general SEC event queue. |
| Structured financial statements | `data_sources/sec_edgar_source.py` provides submissions and company-facts access; `sec_edgar_financials.py` converts facts to income, balance-sheet, and cash-flow statements. | Reuse this acquisition/parser core. Do not create another SEC client/parser just to replace a scheduler label. |
| Research fundamentals | `src/tools/analysis_tools.py::get_detailed_financials` consumes SEC static metrics and a separate qualified local price, with a 90-day static cache. | Preserve existing consumers. A new filing-arrival refresh policy must account for amendments and accessions, not assume the TTL proves current reporting. |
| Local filing-list API/tool | `get_sec_filings` queries DAL metadata. The local backend delegates to `FileBackend.query_sec_filings`, which currently returns an empty schema-correct frame. The standalone SEC financials client does have a live `get_filings_list`. | A useful filing library needs an explicit catalog/store bridge. It is not already a complete archived-report feature. |

## Proposed direction

Prefer a bounded **Tracked-company financial reports** function, separate from
listing/ticker investigation. Default scope would be the selected/currently
tracked issuers, annual and quarterly reports (10-K/10-Q and amendments), with
20-F/40-F and selected 6-K support evaluated for foreign issuers rather than
silently treating their absence of 10-Q as missing data. Fetch metadata first;
download/reuse facts or full reports only when the workflow needs them.

Distinguish a structured-number cache from a readable filing. Company Facts
does not preserve every narrative passage, note, table, or issuer-extension
concept. A future report view should retain filing accession, source URL,
filing date, report period, currency/unit, and revision provenance. It should
not push every original document into an LLM or the target-event queue.

Do not reuse the old `sec_corporate_actions` schedule ID, enable flag, or job
history for financial-report collection: that would silently authorize a new
job and change the meaning of historical executions. Reuse transport/parsers,
but define the new scope and scheduling intent explicitly. Preserve the
retained 36 legacy observation/case records as history; they are not inputs or
bootstrap requirements for a financial-report feature.

## External contract checked

The [SEC EDGAR API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
describes unauthenticated JSON submissions histories and company-facts XBRL
aggregates. Company-facts aggregation covers standard-taxonomy, entity-wide
facts, not every filing disclosure. This supports reusing the existing facts
pipeline while retaining links to the actual filing when full context matters.

The September 3 SEC Filing Intelligence follow-on remains recorded in the
Priority Map. Narrow financial-report retrieval can be its first slice;
general filing interpretation/search remains a separate, later scope. Product
approval is still needed before replacing the obsolete visible scheduling
surface or adding the new report-catalog/storage path.
