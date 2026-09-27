# SA/FD Financial Data And SEC Retirement

Status: direction approved on September 27; this written design awaits review.
The operator separately authorized deleting retained SEC research data and all
48 legacy financial-cache rows. That cleanup does not authorize new provider
calls, subscriptions, a general news purge, or claiming the replacement UI exists.

The authorized cleanup and provider-state cutover are now completed; see the
[formal receipt](../evidence/2026-09-27-sec-retirement-cutover/README.md).
The replacement financial-flow design below still awaits written-spec review.

## Intended Outcome

Seeking Alpha captures and Financial Datasets are the primary company-financial
sources. The user should see retained financial periods, source, acquisition time,
coverage and missing inputs, not a count of arbitrary TTL-expired cache entries.
Stored financial facts do not become false because a timer expires. A newer
download also does not prove that a new reporting period or revision exists.

The separate provider-status repair and article-management/classification work
continue independently. Neither depends on retaining the retired SEC corpus.

## Authorized Cleanup

The read-only inventory of the formal installation contains:

| Owned data | Observed count |
| --- | ---: |
| `financial_cache`, all sources including old FD responses | 48 |
| SEC financial fact observations | 214,331 |
| SEC filing observations | 26,876 |
| SEC snapshots / receipts / issuer-map observations | 30 / 54 / 2 |
| SEC retained objects | 31, totaling 37,394,328 bytes |
| SEC captured filing documents / schedule batches | 0 / 0 |
| Registered SEC citations in retained research messages/events | 0 |

Recompute the inventory at the stop-write boundary; these are observations, not
hardcoded deletion predicates. Remove the exact owned SEC research schema and
its object files through the existing maintenance authority, and clear all
financial-cache rows plus legacy FD file-cache copies. Preserve the empty shared
financial-cache table while current FD code still uses it for new responses.
The operator is retiring old contents, not disabling future local reuse.

Do not delete SA captures, prices, news, FRED/calendar data, portfolio state,
research conversations/reports, credentials, model routes, or company lifecycle
observations. The small SEC-derived company-name autocomplete dictionary is a
separate identity dependency, not the financial corpus; it is not removed by
this cleanup. Existing mixed-data historical backups are not silently erased or
rewritten. This is application-data removal, not forensic secure erasure.

Before removing data, disable the SEC research schedule, remove `sec_edgar` from
the legacy fundamentals route, and disable its SEC-only detailed-financials
component. Keep the existing FD request policy unchanged. Do not automatically
populate replacements. The explicit SEC filing capability is not rewritten into
an automatic fallback, and uninstalling its store must remain visible as such.

Use a brief operator-confirmed stop-write window. The existing schema uninstall
requires a verified recovery backup and external receipt; take one temporary
rollback copy, verify unrelated data after removal, then dispose of that new
copy once the authorized cleanup is accepted. Do not label uninstall alone as
complete: its existing operation removes schema, not object files. File removal,
legacy FD cache removal and the 48-row cleanup each require a readback receipt.

## Discovered Maintenance Repair

The existing profile-root validator assumes that every `research_*` table is one
of four citation-root tables. A real App profile also has `research_reports` and
`research_runtime_config`, so the operator tool refuses the normal installation.
Admit only these known current non-root shapes, compare their columns/relations
with the owning schemas, preserve their contents, and continue rejecting unknown
tables, future reference columns, malformed citations and registered references.
Do not relax the SEC-owned DDL inventory or use a prefix-based DROP.

## Replacement Financial Flow

Use the existing SA observation readers and FD client, not a second acquisition
service. The financial route will expose SA and FD as separate selectable sources.
Local eligible observations are considered before acquisition. An SA loading or
coverage gap must not silently authorize spending on FD.

### Verified Existing Boundaries

`src/sa/company_store.py:read_capture` already supplies retained SA observations;
`FinancialDatasetsClient` already supplies governed FD reads/acquisition. Reuse
the adapters and exact mappings in `src/fundamentals/source_comparison.py` and
`src/tools/financial_comparison_tools.py`, not the comparator's result as though
it were a complete financial analysis.

The current shared mapping covers 13 named inputs: revenue, gross/operating/net
income, basic/diluted EPS, total/current assets and liabilities, and operating,
investing and financing cash flow. This is a demonstrated first normalization
scope, not a cap on the original SA table or a claim that other rows are missing
from SA. Preserve access to the original captured rows. Debt, equity, shares,
capex, FCF and EBITDA require their own reviewed mappings before deriving metrics
from them. Do not silently infer these from similar-looking labels.

SA dated columns currently establish a displayed month, not an exact fiscal-end
day or fiscal-quarter identity. FD can supply stronger period identity. A common
statement representation must retain that precision difference; it must not
create a last-day-of-month date to satisfy the old statement type. Existing FD
statement classes live in `data_sources/sec_edgar_financials.py`; move shared
types to a provider-neutral owner, retaining compatibility imports, before
attempting to remove that SEC module.

### Acquisition And Reuse Contract

- App opening, coverage, source selection and stored tool reads are local-only.
  A missing market DB must not hide SA observations in its independent database.
- An explicit provider selection reads that provider only. Automatic selection
  tries the configured local sources in order and returns one coherent source;
  it does not fill missing statement cells from another provider.
- Existing FD `auto` acquisition remains governed when FD is explicitly selected
  or the primary configured financial provider. An unavailable primary SA capture
  must not authorize an FD purchase; return the gap and available update choices.
  Local FD reuse can still follow the configured local source order.
- Forced acquisition names its provider. FD uses its existing admission and
  request coalescing. SA remains browser-owned: the App shows the existing
  collector/schedule status and an actionable browser-update requirement; this
  slice does not invent server-side SA scraping or silently queue browser pages.
- Historical period values remain readable independently of an acquisition-age
  window. For latest-selection requests, disclose stored observation age and
  reuse decision separately from statement validity. Reads never advance the
  acquisition timestamp or financial schedule.
- SA observations can reopen by retained observation ID. FD initially discloses
  current-retained-version-only behavior, rejecting changed pagination identity;
  this slice does not promise historical reopening of overwritten FD cache keys.

Do not merely add SA to the routing option list: the existing analysis dispatcher
uses SEC-versus-FD fallthrough branches that would misroute a third provider.
Provider dispatch must be explicit and unknown providers must be rejected.

The UI and tools must distinguish:

- Available source observations and displayed/reporting periods.
- Provider numeric precision, units, currency and statement identity.
- Inputs supported by the common analysis contract and derived metrics that can
  actually be computed from them.
- Last acquisition/check time and whether an explicit refresh is running or
  unavailable. A next reporting date is shown only when supported by evidence.

SA's annual page can include TTM. Do not mistake a TTM column for an annual
statement, a month label for an exact fiscal-end date, or displayed rounded
numbers for filing-exact values. Reuse the source-comparison mappings and
statement-basis checks where they apply. Missing interest-bearing debt, currency,
period identity or a compatible comparison period yields a typed gap, not zero
and not a fabricated ratio. Forecasts/ratings remain separate from reported facts.

The App's local financial read and coverage summary must use the same selected
source/read contract as tools. Retire the SEC-only `stored=true` projection and
TTL coverage counters when replacing those consumers; simply hiding them is not
the replacement. Historical reads disclose their retained observation/version;
they do not claim to answer which period is currently newest at the provider.

### Product Surfaces And Metric Eligibility

One financial read-and-coverage service supplies the tools, ticker Data tab,
Dashboard financial tile and Settings financial coverage. Replace the current
SEC-only `/fundamentals/{ticker}?stored=true` projection and the market-DB-only
coverage early return in the same delivery. Show selected source, retained
statement periods, capture time, missing statements and supported metrics.
Retire the SEC/TTL financial counters instead of moving them to another collapsed
panel. Price and news monitoring stay separate; their failures do not erase
available financial observations.

Derived metrics require compatible inputs from one source/statement basis. The
initial SA surface may expose justified same-column margins/current ratio while
leaving debt/equity, ROE/ROA and growth unavailable where required mapped inputs
or exact period identities are absent. Preserve displayed-number precision;
do not label SA rounded values as filing-exact or ordinary FD numeric precision.
Existing FD-derived metrics still use the corrected debt and period guards.
TTM, forecasts and ratings remain separate from annual/quarterly facts.

The common-reader delivery does not claim every legacy detailed valuation or
peer-comparison capability has an SA replacement. Keep unsupported operations
explicitly unavailable, list their input gaps, and port or retire those consumers
in a subsequent independently verified change. SEC filing/document functionality
is separate from the retired financial projection; keep its optional character
clear rather than presenting it as primary financial coverage.

### Alternatives

Keeping separate SA/FD tools has the smallest code impact but leaves the App and
agent with different financial views. A shared read/coverage owner is selected
because it removes that disagreement without replacing acquisition services.
A new versioned financial warehouse could provide stronger FD history but would
add storage/migration scope and is not required for this delivery.

## Delivery And Verification

1. Completed: the narrowly scoped maintenance compatibility repair and disposable
   rehearsal covered admission, reference rejection and unrelated-data
   preservation. Existing removal authority and paid limits remained intact.
2. Completed: the separately authorized cleanup ran under the brief stop-write
   boundary, followed by restoration of ordinary SA operation. The receipt records
   exact before/after counts and file hashes without article prose or credentials.
3. After approval of this written design and its implementation plan, connect
   SA/FD financial reads to the common App/tool contract in a separate branch.
   Missing mappings stay explicit; coverage is not invented to make counts green.
4. Remove obsolete SEC financial UI, projections and automatic routing when
   their consumers have moved. Keep identity/lifecycle capabilities out of this
   retirement unless separately redesigned.

Acceptance includes: zero old financial-cache rows and retained SEC objects after
cleanup; no implicit SEC repopulation; no provider calls during stored reads or
cleanup; unchanged SA/price/news/portfolio/research data; governed explicit FD
acquisition; consistent source/period/quality labels across App and tools; and
independent rollback of provider-status UI versus financial-flow changes.

Freeze and run complete regression before any product merge. A data-cleanup
receipt, focused unit tests, or an empty table alone do not certify the future
SA financial adapter or the article LLM classifier.
