# Data Acquisition And Updates

Maintained policy and implementation map. Last reconciled with source: 2026-09-26.

This document owns the cross-source acquisition, update-trigger, freshness and retention
contract. It distinguishes current behavior from approved follow-up work; dated
plans and test receipts are evidence, not the only place to discover the policy.
The [priority map](docs/design/PROJECT_PRIORITY_MAP.md) owns work sequencing;
source-specific specifications still own their detailed protocols.

## Core Rules

- Reuse suitable local observations for efficiency, not just to avoid charges.
  Local-first does not mean that every dataset can tolerate the same age.
- Keep provider, dataset, requested scope and observation time visible. A local
  copy from one provider is not proof that another provider has equivalent data.
- Provider capability, selected source, account entitlement, permission to spend
  and data age are separate facts. A configured key does not prove a paid plan.
  The current user has no paid Finnhub subscription; neither financial reuse nor
  its future event-aware policy may require purchasing one.
- A successful request, a recent download and a new financial period are three
  different facts. None alone proves that all requested data is current.
- Users must be able to choose local-only reads, automatic acquisition when
  needed, or an explicit update where the source supports it. A browser capture
  cannot promise the latency or availability of a quote API.
- Refresh permission, paid admission and request limits remain independent.
  A freshness override does not authorize spending or bypass provider limits.
- An acquisition failure must not become a fresh empty result. Partial coverage
  must not be presented as complete. Reuse eligibility is not a deletion policy.

## Product Workflow And Delivery Scope

One active delivery unit is a complete company-research workflow: company choice,
selected-source acquisition/reuse, usable research inputs and optional source
verification. The data-category catalog is supporting inventory, not the
finished capability or a requirement for the user to redesign all preferences.
The [workflow plan](docs/superpowers/plans/2026-09-21-company-research-workflow.md)
owns implementation and acceptance; its pending items are not current behavior.

Data retention, unattended service lifetime/failure delivery and external
read/analysis MCP are also required workstreams. They do not wait for SA browser
acceptance or SEC retirement. The September 22
[cross-workstream design](docs/superpowers/specs/2026-09-22-retention-service-and-external-tools-design.md)
records proposed implementation boundaries and independent acceptance gates;
these capabilities are not yet delivered. ArkScope remains a research workbench,
not only a collection pipeline.

Original SEC analysis is an optional verification path, not a mandatory step for
ordinary company research. Retire redundant user-facing technical surfaces and
superseded calculations together with a working replacement. Do not confuse
this direction with permission to delete retained citations, disable distinct
security-identity data, or silently replace a free source with paid acquisition.
No normal research path should require the user to know a CIK.

SA's existing extension has alarm-driven acquisition. Browser availability,
login and successful page loading remain prerequisites; it is neither purely
passive nor a headless collector. The company adapters below add explicit
current-page capture and local research reads for financial statements,
valuation, peers, annual estimates and revisions. Neither company capture nor
existing SA alarms establish headless company-data availability.

Source coverage and extraction readiness are separate acceptance questions.
The [company-data comparison](docs/data/2026-09-21-company-data-coverage.md)
records observed high-value SA coverage, FD/free-API alternatives, costs and
field-specific failures. These experimental observations do not enable new
adapters or change selected sources. For additional browser tables, acceptance
must include lazy-loaded sections and complete column alignment; labels alone
are not a completed capture. API pagination and period semantics need equivalent
checks. A paid response is not automatically more complete or more reliable.

Freshness is task- and source-dependent, not a compulsory choice among four
global ages. Financial publication/provider readiness, news collection cadence,
browser capture availability and live quote/account requests keep separate
rules. Unknown access requires scoped evidence, not a subscription assumption;
one successful endpoint request cannot certify an entire provider plan.

## Data Categories Before Provider Integrations

### Settings Interpretation

The category catalog reports three independent facts: the adapter for the
selected category, integrations for other categories, and credential/access
requirements. Massive price/news support and a configured key do not implement
its financial adapter or establish financial endpoint entitlement. SA financial
tables support manual and scheduled browser capture and the common SA/FD
financial reader, including reviewed ratios from compatible retained inputs. Source switches
remain scoped to the named tool route, not every use of that provider.

Financial provider health describes retained acquisition evidence, not a live
endpoint probe. An empty readable store reports `acquisition_evidence=empty`
(no local acquisition record); failed reads report `unavailable`, not an empty
history. Rows without a usable acquisition time report `timestamp_unknown`.
An expired reuse window does not erase a recorded acquisition: `recorded` still
exposes its original fetch time without claiming a current reporting period,
usable credentials or endpoint entitlement. Missing-key and disabled states
retain precedence. Reading this status never fetches or repopulates data.

Stored prices and local financial coverage have separate sections; news
volume and per-provider collection outcomes belong to News Data. The financial
section reports the selected provider's retained periods, capture time, precision
and missing inputs, not SEC or TTL row counts. Its candidate count is a local
inventory, not a claim that every candidate has usable financials. News completion uncertainty
remains partial/unknown and is not reworded as a network-request failure.

FRED snapshots expose stored units, frequency, seasonal adjustment and revision
strategy. Monthly/quarterly observation periods are not publication dates, and
fetch time is not a live freshness guarantee. `latest_only` is the existing
initial-release strategy; `full_vintages` retains revisions. Indicator guides
link to each official FRED series and distinguish index levels, rates and
changes. The eleven-series snapshot is not a complete monitoring product;
user-defined formulas/indicators and alerts remain pending. Calendar zero counts
mean no local rows, not established empty upstream coverage. Disabled schedules
keep historical outcomes without retrying merely because an old failure exists.

The provider-health and FRED tables use local fetch time as the primary display;
each timestamp expands to show New York time. Narrow containers show labeled
records instead of clipping columns. FRED `D`, `M`, and `Q` frequency codes and
their full-name equivalents have the same observation-period interpretation.

### Financial Corpus Retirement (September 27)

The operator-authorized cleanup completed on September 27 under a confirmed
stop-write boundary. All 48 legacy `financial_cache` rows (36 SEC, 12 FD),
31 retained SEC objects, the SEC research schema, and two legacy FD file-cache
copies were removed. This retires the data, not merely its diagnostic display.
The [formal cutover receipt](docs/superpowers/evidence/2026-09-27-sec-retirement-cutover/README.md)
records the before/after checks and the later disposal of its temporary recovery
copy. Future legitimate FD acquisitions may populate the empty cache again.

The local fundamentals route now selects Financial Datasets only, the SEC-only
detailed-financials route is disabled, and the SEC research schedule is disabled.
Existing FD request limits are unchanged. Cleanup made no replacement provider
requests. SA financial, valuation and
estimate captures remain available through their existing local-read routes.
SA's common ratio-analysis adapter remains unfinished, not an implied capability
of selecting SA in the category catalog.

TTL means **time to live**: an age-based cache-reuse rule. It does not make a
reported financial fact false when it expires, prove a provider has published a
new period, or justify retaining this retired corpus. Future eligible SA/FD
observations can still be reused locally. The shared cache table was emptied
rather than dropped while the FD client still needs it.

Preserve SA captures, market prices, news, macro data, holdings, research history,
credentials and the separate company-identity dictionary/lifecycle records.
The uninstall authority required one verified temporary recovery copy. That copy
was removed after successful readback and cutover checks; no new permanent SEC
archive was kept. Existing mixed-data historical backups were not rewritten.
This is application-data removal, not forensic secure erasure.

The [SA/FD financial design](docs/superpowers/specs/2026-09-27-sa-fd-financial-data-and-sec-retirement-design.md)
separates this authorized cleanup from the subsequent common-source adapter and
replacement UI. The common reader and replacement UI are implemented on the
financial-read branch; deployment and formal provider activity are separate.

### Common Financial Reads

`GET /fundamentals/{ticker}`, the ticker Data tab, Dashboard and Settings
coverage are local-only. Opening, rereading, changing source/period and paging
cannot buy data, call SEC, launch a browser or change a schedule. The deprecated
`stored` query parameter is an alias; even `stored=false` stays local.

The selected provider is one coherent result, never an automatic blend. A
missing setting defaults to SA then FD; existing FD-only, disabled or invalid
settings are not rewritten. Select sources in Financial Data Sources explicitly.
SA partial data does not authorize paid FD fallback.

SA's 13 reviewed direct statement mappings preserve displayed month, source row,
decimal value, currency, unit conversion and display precision. Compatible SA
inputs currently support gross, operating and net margins plus current ratio.
Unreviewed debt, growth, valuation and other inputs remain named gaps, not zero.
TTM is not an annual or quarterly reporting period. Raw SA company tables retain
the additional provider rows outside these reviewed mappings.

This is a verified starting scope, not a permanent 13-field/4-ratio limit.
Extend it by checking actual retained row labels and sections, scale notes,
currency, per-share/share-count exceptions, fiscal duration and accounting basis.
Keep the raw value, normalized value, source observation and conversion formula
together; test ambiguous labels, shifted columns, unit changes and missing inputs
before adding a mapping. A source being SA is not by itself proof of a field's
meaning. Source-derived conclusions are allowed once those inputs are qualified;
unknown units/basis must remain gaps, not an operator switch to guessed numbers.

FD retains its existing qualified metrics and current response windows. Retained
data remains readable after a reuse window expires; expiry controls possible
acquisition, not whether a historical statement exists. SA observation IDs can
reopen retained captures; FD does not yet keep all overwritten response versions.
Pin `read_id` when paging; changed content is a typed refusal, not mixed history.

#### Configurable Output And FD History

Settings > Financial Data Sources > Financial History and Tool Output owns
`data_sources.financial_read.settings`. The view comes from
`GET /providers/data-routes`; `PUT /providers/financial-read-settings` only saves
validated preferences. It does not fetch, enable paid access or change sources.
Missing settings use defaults without writing a profile; malformed saved values
are disclosed and require explicit repair, not silently replaced.

- Financial result output defaults to 48,000 characters on all four research
  channels (OpenAI/Anthropic API and ChatGPT/Claude subscription bridges).
  Operators can change it or disable the additional cap (`tool_output_chars=0`).
  Model context limits and secret/result validation still apply. For oversized
  pages, redundant coverage/period metadata is projected to the returned page,
  with explicit scope and retained counts. Facts, units, metric formulas and
  their input observations are never trimmed. If that still does not fit, the
  result is a typed refusal: reduce the page size, or increase/disable the
  Settings cap if already on one period. The separate coverage API remains
  unchanged. The Anthropic insertion compressor does not impose a second
  8,000-character cap.
- FD acquisition periods are separate for each statement and annual/quarterly
  scope. Defaults remain annual income/balance/cash flow **2/1/2**, quarterly
  **4/1/4**. The positive int32 boundary is the provider's request type, not a
  chosen product ceiling. The output setting uses JavaScript-safe integers.
- FD returns up to ten periods per statement page. `limit` requests total
  periods; each cursor page is a separate metered request. Settings estimates
  pages for all three statements of one ticker, not a price or guaranteed
  response count. More periods do **not** necessarily mean one extra request
  per period. See the [FD pagination contract](https://docs.financialdatasets.ai/guides/pagination).
- Every page uses the existing paid governor. Only same-origin, same-endpoint
  HTTPS cursor links are followed; duplicate/no-progress/wrong-scope pages
  fail closed. No automatic retries or unmetered navigation. A failed walk never
  replaces the previous complete response with its partial pages.
  All four async research channels own their financial worker: timeout or
  cancellation stops subsequent page admission and waits for the in-flight
  synchronous request to finish or hit its transport timeout. Cancellation
  cannot recall a request already sent. A stopped response is not persisted as
  a complete observation; the caller cannot report finished while more pages
  continue in an abandoned worker.
- Changing the requested period counts does not hide retained statements.
  Stored reads select one newest valid response, or the newest response that
  contains the explicitly requested historical month, with `requested_periods`
  and `configured_periods` disclosed per statement. Rows from different responses
  are not spliced together. A smaller retained request
  yields `financial_datasets_history_scope_shortfall`; auto may acquire the
  larger selected FD scope only under the unchanged paid policy. A completed
  provider response with fewer available rows is not retried just to fill a
  number. Period counts control acquisition, not the reader's paginated window.

The complete-result reducer preserves tool evidence; it is not a news/archive
retention policy. FD overwrite-history preservation is also unchanged.

For an update, select Financial Datasets by name and confirm its paid action.
`POST /fundamentals/{ticker}/refresh` and explicit tool refresh require a named
source and the existing budget/admission checks. Refusal keeps a separately
labeled previous local read. SA updates remain in the extension; its status
action reads existing collector state and exposes manual source links, but does
not enqueue work. Per-ticker progress and future report dates remain unknown
unless the acquisition system supplies them.

Research tools retain explicit `stored`, `auto` and `refresh` modes. Historical
and pinned reads require `stored`. In `auto`, a selected/explicit FD primary may
update missing or stale FD inputs under admission; SA being missing or stale
never authorizes paid substitution. UI reads always choose `stored`.

Detailed legacy metrics and peer ranking have no validated replacement in this
delivery and return `financial_operation_not_ported`, without calling SEC,
FD or Finnhub. Optional SEC identity, lifecycle and original-filing tools remain
separate. The Settings request cache (60 seconds, retained at most 15 minutes)
only avoids repeated UI requests; it does not define financial fact validity.

Owners: [common reader](src/fundamentals/read_service.py),
[coverage](src/fundamentals/coverage.py),
[HTTP entrypoints](src/api/routes/fundamentals.py).

### Saved Comment Work Is Not Complete Coverage

A usable scan that successfully persisted comments but exhausted its scroll/time
budget or left unresolved controls is a v2 `deferred` comment phase, not a parser
failure and not complete. `comment_progress` records pending articles, net-new
comments saved in that run, and typed stop reasons. The extension and App display
partial work; it never advances the healthy-complete anchor. Actual parser and
storage failures retain precedence. No extra retries, longer scans, weaker
navigation admission, or bulk detail work were added to make this status green.
Quick Update retains its four-distinct-detail-article cap; historical body repair
remains a separate resumable workflow. Old receipts without this optional field
retain their canonical identity. Updated native validation must be deployed
before or with the updated extension.

The catalog starts with **what data or intelligence is needed**, then lists
providers for that category. It does not require implementing every listed
provider before the category is useful. A provider's advertised capability, a
working ArkScope adapter and access under the user's account are distinct.
Candidate sources may be recorded before integration; they must not appear as
working acquisition switches until their adapters and results are verified.

The following is an initial integration map, also exposed in the Settings
catalog below. It is not an exhaustive vendor catalog or a current subscription
recommendation; it does not make every source selectable through one policy:

| Data category | Existing ArkScope acquisition | Boundary / outstanding integration |
| --- | --- | --- |
| Company financial statements and facts | SA and Financial Datasets through the common financial reader; raw SA company tables remain available | Only reviewed mappings and metrics are supported. Massive financials remain a candidate; legacy detailed/peer operations are explicitly unavailable. |
| Provider-supplied valuation, ratings and peer comparisons | Explicit SA valuation-table and 18-section peer-page capture | Provider judgments/peer selection stay separate from financial facts. Snapshot prices are not live quotes. |
| Earnings estimates and revisions | Explicit SA annual EPS/revenue consensus and revision-table capture | Forecasts are not reported results or earnings-calendar events. Analyst counts, ranges and period labels remain available. |
| Current quotes | IBKR snapshots | Account/feed access and price time determine whether the result is live. This is not a persistent streaming service. |
| Historical price bars | IBKR / Massive price workers | The current recurring price job explicitly selects IBKR; Massive has worker support, not an independent recurring schedule. The financial-source switches do not govern either path. |
| General news | Massive, Finnhub and IBKR collectors; SA market-news extension capture | API/Gateway jobs and browser capture have different prerequisites. Sources need not cover the same publishers, bodies or comments. |
| Earnings and IPO events | Finnhub calendar jobs; separate earnings supplements in detailed financials | Implemented endpoints do not prove free-account coverage. Other providers can be evaluated without requiring a Finnhub upgrade. |
| Macro observations and release events | FRED series/release jobs and Finnhub economic-calendar jobs | Series, release dates and economic events are distinct datasets, not interchangeable responses. |
| Recommendation membership | SA Alpha Picks extension capture | Current and closed membership have separate coverage; a captured list does not prove article completeness. |
| Research articles and discussion | SA article-body and comment extension capture | Body and comment outcomes remain separate. This does not include structured company financial pages. |
| Account holdings and value | IBKR account capture, then local snapshot reads | A successful local holdings read does not initiate broker synchronization or prove current account value. |
| Original filings and filing-backed evidence | SEC research capture, local reads and opt-in updates | A separate data capability, not a required first step for every financial question. |

Current owners: [catalog metadata](src/data_source_catalog.py),
[financial routing](src/data_source_routing.py),
[quote reads](src/tools/current_quote.py), [price workers](src/prices_runtime.py),
[source jobs](src/service/data_scheduler.py),
[SA capture operations](src/sa/extension_run_protocol.py),
[SA extension](extensions/sa_alpha_picks/background.js),
[account capture](src/portfolio_capture_ibkr.py) and
[SEC research](src/sec_research/tool_service.py).
Adapter presence is not a health check or certification of analytical formulas.

### Catalog And Settings Expansion Contract

- Record content/scope, capability evidence, adapter status, account access and
  cost separately for each category/provider pair. Unverified availability is
  unknown, not proof of missing entitlement or a reason to buy a subscription.
- Select acquisition per category and provider, not one global supplier. Multiple
  sources may be selected without mixing their retained observations or fetching
  every source on every read. A listing alone authorizes no network request.
- Distinguish acquisition permission, recurring schedule enablement and eligible
  local reads. Stopping a schedule is not a deletion or a prohibition on reading
  saved data. The existing financial route controls read eligibility as well as
  acquisition through those tools; it is not a universal acquisition switch.
- Record the actual execution owner and supported triggers: API/Gateway job,
  browser extension, explicit capture or local computation. Do not advertise a
  browser-only source as available to a headless server merely by adding a row.
- Add and verify adapters incrementally. SA's existing articles, comments, picks
  and news remain independent of explicit company-table capture. No all-provider rollout, new subscription
  or external MCP is required.

The current six company/financial route IDs below identify existing tool paths, not
the final user-facing data taxonomy. Category navigation is implemented;
unified collection controls for the other categories remain follow-up work.

### Settings Catalog

Settings -> Data and Sync -> Data Sources and Schedules -> Data Types and Sources
provides a twelve-category selector. Each provider row separates integration
status, acquisition method, access/cost requirements and existing management
entrypoints. **Integrated** means an adapter exists, not that the current account
has access, the source is enabled, or its results are complete and current.

GET `/providers/data-catalog` returns static capability metadata without opening
a DAL/store, probing credentials or providers, starting jobs or saving settings.
Financial source membership derives from the existing routing catalog rather
than a second selection authority. The Settings read cache retains this metadata
for 15 minutes before revalidation, with a 60-minute hard retention limit;
these are UI metadata lifetimes, not freshness rules for financial/news data.

Management buttons navigate to existing financial-source, schedule, connection,
coverage, SEC-storage or SA-extension status sections. Navigation preserves
unsaved Settings drafts; it neither enables a source nor runs a collection.
Candidate financial/rating integrations have no acquisition buttons. A failed
catalog reload keeps the previous definitions visible with an error, not a
successful refresh indication.

SA articles, comments, recommendation membership and market news use the
existing Firefox/Chrome extension capture/auto-sync. The catalog links to its status;
capture controls remain in the extension, not a new sidecar API job. SA structured
financial tables, valuation/peers and estimates/revisions have separate
eligibility switches and share the explicit company-capture command. Finnhub entries describe required
endpoint access without presuming a paid subscription or certifying free access.

Owners: [catalog](src/data_source_catalog.py),
[metadata endpoint](src/api/routes/providers_config.py),
[Settings catalog](apps/arkscope-web/src/settings/DataSourceCatalogSection.tsx).

### Collection Outcomes and Recovery

- The SA extension's top acquisition status distinguishes a live local task,
  stopped work requiring recovery, and unavailable browser evidence. The App can
  read an unfinished native record but cannot prove that the browser is running.
  A missing capture tab interrupts that task; it must not wait for the full page
  readiness timeout or try another page on the same missing tab.
- If the extension reports **Stopped capture: recovery required**, pause its
  schedules and close remaining automatic capture tabs first. Use **Review
  recovery**, confirm the stopped state, then **Recover stopped capture**. Do not
  recover while a capture is still running. Resume the existing schedules after
  recovery; do not run a full article scan merely to test readiness.
- Financial **Missing checks** count statement/view/currency scopes, not company
  count. Select scope and inspect the preview before enabling **Scheduled
  financial updates**. Leaving that checkbox off does not start the financial
  backlog. **Article body repair** has its own preview and explicitly started
  batch; an outstanding count is not evidence that repair is running.
- IBKR news reports **subscription denied**, **request timed out**, and
  **completeness unknown** separately. A missing historical completion callback
  alone proves neither subscription denial nor successful completion. Partial
  headlines received before timeout are retained. Old unknown records cannot be
  retrospectively relabeled without evidence from a new attempt. Settings keeps
  per-ticker issues collapsed until expanded.
- Finnhub calendar status separates completed requests (including empty
  responses), requests with issues, and stored-event counts. A failed symbol does
  not invalidate successful symbols. HTTP 403 establishes endpoint access denial,
  not which subscription plan would resolve it. Empty earnings responses do not
  establish complete coverage or absence of an upcoming earnings event.

Article Entry/Exit/Related LLM classification remains a separate, unimplemented
workstream pending design confirmation. Extension manual link review is not an
LLM classifier and does not establish complete article-body availability.

## Which Clock Means What?

| Concept | Meaning | Does not establish |
| --- | --- | --- |
| Period / observation date | What fiscal period, trading instant or event the value describes | When we retrieved it, or whether a later version exists |
| Source version | Provider identity plus filing/revision/snapshot identity where available | Immutability merely because `period_end` is unchanged |
| Publication / event date | When a release is expected or observed | When each provider finishes processing each statement |
| `fetched_at` | When the retained response was acquired | The newest available financial period or a quote's trade time |
| `checked_at` / last check | When a request checked a stated scope, even if nothing changed | New content, successful persistence or complete provider coverage |
| `evaluated_at` | When the consumer judged the observation | A new acquisition |
| Reuse window | Accepted acquisition age for a particular read | A quarterly publication schedule or a retention period |
| Schedule interval | When another collection attempt becomes due | Fresh data or successful previous collection |
| `next_check_at` | Intended absolute next availability-check time in the event-aware design | An implemented field shared by all current sources |

These are semantic distinctions, not a claim that every current response exposes
all these fields. Calendar receipts currently use `checked_at`; financial reuse
currently exposes `fetched_at` and `evaluated_at`. The event-aware decision record
is still follow-up work.

## Current Acquisition Behavior

| Data / entrypoint | Trigger and reuse today | Important limit |
| --- | --- | --- |
| Common financial analysis | UI/HTTP GET is stored-only; tool `auto` may update an explicitly selected/primary FD source within admission | No paid fallback from SA; retained month/observation/read selectors do not claim latest-provider completeness |
| Legacy detailed financials and peer comparison | Explicit `financial_operation_not_ported`; no acquisition | No validated replacement for these operations in this delivery |
| `get_earnings_impact` | Reads retained release-calendar revisions and local daily prices; no acquisition or calendar schema installation | US exchange-session analysis, not a real-time monitor. Missing release timing, actuals or exact reaction-session prices are explicit gaps. |
| SEC research: `list_sec_filings`, `get_sec_financial_facts`, `read_sec_filing` | Default `stored`; explicit `auto` / `refresh` can download and persist through identity, path and transport guards | Separate from legacy financial tools; the general permission hook is audit-only, not an interactive authorization engine |
| General news | Opt-in source schedules, Run now, or the scoped `daily_update` wrapper; source-specific incremental collection | No universal query-triggered catch-up or interval-completeness guarantee |
| SA articles / comments | Signed-in browser extension captures into local storage; research reads retained captures | Body and comment outcomes are separate. A successful body does not prove comments loaded. |
| SA company financial tables | Explicit current-tab capture, or opt-in extension financial refresh; `get_sa_company_data` reads saved observations | Per-ticker/statement/view checks, initially every 7 days; no paid fallback or claim that displayed periods are the latest publication. Requires the browser and installed extension. |
| SA valuation, peers, annual estimates/revisions | Explicit current-tab capture with bounded section scrolling; local reads of a pinned observation | DOM readiness polling is not a recurring provider refresh. No hidden pagination, automatic paid fallback or live-quote claim. |
| `compare_financial_sources` | Compare already retained SA/FD statement observations from selected sources | No acquisition or spending; compatible display-period comparisons are not exact accounting equivalence or a materiality judgment. |
| FRED and Finnhub calendars | Local reads plus explicit jobs or opt-in source schedules | A release calendar is not evidence that a financial provider has processed the release. |
| `get_current_quote` | `source=auto` tries an IBKR snapshot; `ibkr` requires that path; `local` reads stored bars | Snapshot, not streaming. Auto's local fallback is labeled historical, not live. |
| `get_portfolio_holdings` | Pages an existing local profile snapshot in one read transaction | Does not install schema, create accounts, sync IBKR or establish current account value; missing storage is unavailable, not an empty portfolio |

### Analytical Basis And Research Access

Acquisition freshness does not validate a calculation. Qualified FD
financial inputs use debt/return/growth guards: debt is not total liabilities;
missing debt is not zero; annual ROE/ROA require matching statement end, period
type and currency. The denominator is disclosed as period-end equity/assets,
not an average, and quarterly income is not multiplied by four. Growth requires
an adjacent fiscal label and a plausible period-end separation (350-380 days for
annual, 70-110 days for quarterly). Quarterly growth is explicitly QoQ, not YoY.
Nonstandard/stub periods remain unavailable rather than silently comparable.

`metric_basis` and `metric_gaps` explain available and withheld outputs. Numeric
provider inputs are not promoted to exact filing evidence. The following SEC
guards describe the retained optional compatibility calculators, not an active
common financial provider or an instruction to keep a legacy corpus. SEC statement inputs
must carry the current period/debt extraction contract. It anchors the shared
report end in USD statement totals (assets/equity, revenue, net income and
operating cash flow), not later share-count disclosures or unrelated units.
It checks expected units and flow duration versus instant facts;
cumulative-only quarters and comparative-year figures cannot substitute.
Overlapping current-debt components are not added together, and operating cash
flow without known CapEx is not called free cash flow. These guards do not
certify every legacy SEC concept mapping or the optional legacy TTM algorithm.
The estimated ROIC using an assumed 21% tax rate is withheld. Basic derived
values in old caches are recomputed only from qualified retained statements;
unversioned rows remain visible but cannot publish derived ratios. An invalid
latest row does not silently select an older year. Missing average-balance
inputs are not assumed zero or replaced by an end balance. Detailed caches
without the current calculation contract and without retained inputs keep their
acquisition receipt but withhold old ratios, tech calculations and valuation
operands. This repair does not itself trigger acquisition or spending.

Peer comparison keeps each raw value, provider and basis visible. Statistics and
rankings require matching known metric bases; market-dependent ratios also need
the same price-source/interval/date/time basis. A refused comparison includes
the affected tickers and reason. Caller-supplied/configured sector membership is
a selection judgment, and numerical ordering is not investment quality.
Matching metadata is not proof of equivalent accounting concepts or revisions.

Earnings reactions use the retained calendar's release day and before/after/
during-market bucket, never the fiscal period end or nearest available bar.
Calendar actual EPS or revenue must exist; a scheduled date alone is insufficient.
After-close releases map to the next exchange session. A five-session drift
requires six valid session closes; incomplete windows return no five-session
number. Holidays and early closes use the existing exchange calendar. Results
include sample counts and gaps, not `expected_move` or `surprise_predictive`.
Exact release timestamps, underlying daily-bar completeness and adjustment basis
remain unverified and visible. No recurring event observer, notification or live
intraday signal is implied. The current retained calendar adapter is Finnhub;
no paid Finnhub plan is assumed or newly required.

The five explicit-input calculators (compound growth, DCF, peer statistics,
implied valuation and weighted scenarios) are available through both API-key and
both OAuth research adapters. They do not select providers, fetch data or open
stores. Their assumptions and input provenance remain the caller's responsibility.
This is internal tool admission, not permission for an external MCP client.

### Selected Financial Sources

Settings -> Data and Sync -> Data Sources and Schedules -> Financial Data Sources
controls these implemented paths, using one policy catalog:

| Dataset | Selectable sources | Runtime consumers |
| --- | --- | --- |
| `fundamentals_analysis` | Seeking Alpha, Financial Datasets | Common reader and stored-only comparison on all four existing research channels |
| `detailed_financials` | None | Legacy operation explicitly unavailable; existing setting is preserved, not used for acquisition |
| `earnings_supplements` | Finnhub setting retained | No longer fetched by the retired detailed-financial operation |
| `sa_company_financials` | Seeking Alpha | `get_sa_company_data` and stored-only `compare_financial_sources` on all four research channels; explicit extension ingestion |
| `sa_company_valuation` | Seeking Alpha | Same local reader with `dataset=valuation` or `peers`; explicit ingestion |
| `sa_company_estimates` | Seeking Alpha | Same local reader with `dataset=estimates` or `revisions`; explicit ingestion |

The ordered selection is an eligible set, not a command to fetch all sources.
Stored mode returns the first selected source with readable retained statements,
including partial statements. Auto first considers age-eligible retained reads;
its acquisition decision is still limited to the explicit or primary provider.
SA as the primary provider never authorizes a paid FD request, even when SA is
absent and some FD statements are retained. A missing or partial result remains
visible as gaps; values from different providers are not combined.

When FD itself is the explicit or primary source, auto can retain its fresh
statement groups and acquire only missing/stale groups under the existing
budget. It does not buy an alternate provider or repurchase fresh groups.

`get_fundamentals_analysis(source="seeking_alpha"|"financial_datasets")` selects one
provider inside that eligible set and never silently falls back to another.
`source="auto"` is the default. Comparing sources requires separate explicit
reads; existing cache records remain provider-separated. `source_routes` records
the dataset, requested source, configured order, effective source, selection
policy and whether Settings or defaults supplied the selection. Model choice
does not bypass the operator's selection or the FD governor.

Selections are saved in `profile_settings` as
`data_sources.route.<dataset>`. An empty list disables the path, including reuse
through that tool; it does not delete retained observations. No saved setting
preserves the default order in the table. Malformed or unreadable settings fail
closed with a typed gap, not a network fallback. Changes take effect on subsequent
invocations in the same App; they do not promise to cancel already-running work.

### Comparing Retained Financial Sources

`compare_financial_sources` is a **read-only**, source-separated operation. It
does not call an API, launch a browser, promote a file cache, recalculate legacy
ratios, grant paid permission or choose the authoritative provider. Its default
provider set comes from the two applicable Settings routes above; explicit
provider arguments cannot bypass disabled selections. A missing observation
stays a named gap, not a request to buy it or silently switch sources.

The reader compares recognized direct statement rows: six income measures
(revenue, gross profit, operating income, net income, basic/diluted EPS), four
balance measures (total/current assets and liabilities), and the three net cash
flow categories. This is not all financial rows, derived ratios, valuation,
forecasts or peer-selection judgments. Other SA rows remain available through
the full company-data reader. Unknown/ambiguous row labels are not fuzzy-matched.

- Default period selection is the latest common displayed month among sources
  with available statements. `end_month=YYYY-MM` explicitly selects another
  retained period; it never means a new acquisition or a claim of latest data.
  Missing requested periods remain visible. TTM/last-report columns are not
  substitutes for annual or quarterly columns.
- SEC is not a supported comparison provider in the common financial path.
  Retired or disabled source arguments fail closed without acquisition.
- Source values, labels, currency, unit note/scale, observation/content identity
  and acquisition metadata remain separate. FD statement projections
  retain declared currency; old projections with no currency remain unknown.
- SA month labels are **month alignment**, not proof of the exact fiscal end
  day or duration. Two known conflicting exact end dates prohibit a delta.
  Unknown/different currencies also prohibit it; no guessed USD or FX conversion.
- Recognized SA millions/thousands are rescaled with decimal arithmetic; EPS
  uses the per-share exception. API numbers retain their existing float
  qualification. The difference is right minus the named left source; a relative
  difference uses the absolute left value and is unavailable at zero.
- Equal displayed values do not prove accounting equivalence. Differences within
  half the displayed step are rounding-compatible, not proved rounding errors.
  Larger differences remain unexplained unless there is actual supporting
  evidence. The operation does not invent GAAP/restatement explanations, decide
  an acceptable investment tolerance, or present a normalized blend as a fact.

Misidentified fields, units, currencies or periods are correctness defects.
Ordinary provider-definition or rounding differences are not automatically
defects or blockers for using a source. A qualified descriptive difference is
input to the research question; its significance depends on the decision being
made, not a universal percentage chosen by this application.

The default page contains three measures and can be enlarged within the model's
output budget. Pin `comparison_id` on subsequent pages; changed content is a
typed refusal, not mixed-version output. This content identity is not a saved
report or an archival promise: SA can reopen immutable observations, while the
FD caches may overwrite previous responses. Budget reducers preserve the
whole comparison or return a smaller-page request, never clipped numeric JSON.

Owners: [comparison reader](src/tools/financial_comparison_tools.py),
[comparison rules](src/fundamentals/source_comparison.py),
[regression cases](tests/test_financial_source_comparison.py).

### Retained Articles, Comments And Holdings

These are local research reads, admitted to both native API adapters and both
internal OAuth research adapters. They are not a new external MCP service or
permission to acquire data. The registry remains 58 tools; each OAuth research
allowlist now admits 27, including five pure calculators. `get_sa_feed` supplies article IDs; the relevant
research/summarizer subagents can follow them to `get_sa_article_detail` and
`get_sa_comment_focus`. Holdings are the user's local account positions, not the
Alpha Picks recommendation membership.

**Alpha Picks article associations.** A stock's selection article and its
sale/removal articles are separate event links, not interchangeable company
coverage. `get_sa_pick_detail(symbol, picked_date)` returns `articles.entry`,
`articles.exit`, and `articles.related`. Entry/exit links belong to the requested
investment (symbol and pick date); separate sale dates remain visible. An empty
event group means no accepted link is stored, not that the event never happened.
Related articles have no confirmed selection/removal role and remain usable
without manual review. Manual link selection/rejection remains an optional
advanced operation; this read path does not make new reconciliation decisions.
Related articles use pages of 20; follow `articles.related_pagination.next_offset`
as the next call's `related_offset`. Accepted entry/exit links remain included
on every page. Items retain all associated symbols' evidence, while
`matching_link_ids` identifies the links for the requested investment and role.
An association-store read failure is explicitly unavailable (HTTP 503 at the
UI route), never an empty list or a suggestion that the pick was merely closed.
The existing API adapters expose per-pick detail. The internal OAuth allowlists
remain unchanged: those agents use `get_sa_feed` with an appropriate historical
window and follow the article ID through `get_sa_article_detail`, both carrying
the same event/provenance fields. This change does not silently admit the legacy
`get_sa_pick_detail` or `get_sa_articles` tools to either OAuth allowlist.

Article lists, the SA feed, digest and article reader share retained association
rules. Active accepted links can associate one article with multiple stocks;
the provider's single primary ticker does not erase those links. Non-conflicting
list/detail ticker observations provide generic association. Legacy ticker-only
projections remain explicitly `legacy`, not promoted to provider evidence.
Conflicting provider tickers alone do not establish an association. Revoked
event links do not participate. Matching uses exact symbols, never prefixes or
arbitrary mentions in the body. One article appears once per result list even
when it has multiple event links. Each returned association preserves `role`,
`link_source` (`auto`, `user`, `provider`, `legacy`), `evidence_codes`, pick date,
event date and link ID where applicable. These describe the stored basis, not a
confidence score or a new verification of the investment thesis.

In `get_sa_feed`, a complete locally known symbol in `q` (case-insensitive,
optionally prefixed with `$`) uses exact article associations/news membership
when no `ticker` filter is supplied. A quoted query forces text search; with
explicit `ticker`, `q` remains an additional text filter. Results disclose
`query_mode` and `resolved_ticker`. Other text queries retain FTS/short-text
fallback behavior. These semantics apply to the SA feed, not every provider's
search. Date windows and page limits still apply: digest is recent coverage,
whereas per-pick detail is the route to older selection/removal explanations.
Association metadata is part of the article reader's snapshot identity; a
changed link invalidates continuation just like changed article/comment text.

Owner: [association projection](src/sa/article_associations.py).
Regression: [association and role reads](tests/test_sa_article_associations.py).

**Article body quality and recovery.** A nonempty field or `detail_fetched_at`
does not prove that an article was obtained. The shared quality assessment
distinguishes missing text, recognized unusable captures (title/byline/legal
disclosures only, or a comment thread in the body field), and available article
text. Available text is **not** a certificate of completeness. Short prose and
real analysis containing disclosures remain usable; no minimum article length
is used to discard retained text. Invalid legacy captures remain stored for
inspection but are withheld as article prose by the readers, digest, feed and
reconciliation. Comments have independent coverage and remain accessible.
The raw full-text search index is not rebuilt by a read: text matching can still
find an invalid historical capture, whose result must not claim usable prose.

Failed body captures cannot replace usable text or advance its successful
capture time. A comment save can independently succeed while `body_saved` is
false. A copied per-pick report is repaired only through its existing canonical
article ID, and only if that copy is unusable; a matching ticker is insufficient.
Legacy file-cache fallback applies the same body assessment. Secondary report
files are updated only after the local store accepts a body; a rejected capture
cannot overwrite a good file or reappear through fallback.
This repair does not invent entry/exit links, accept candidate roles, overwrite
valid reports, or remove any article, comment or citation.

Body recovery is an explicit extension action, not an automatic historical
backfill triggered by the new quality detector. Its read-only preview favors
original analyses for current retained Alpha Picks cohorts (including older
articles), then recent follow-ups and recent team/portfolio commentary. All
unusable articles published within one year remain candidates even without a
ticker. Publication date, not download date, defines recency. Current membership
comes from non-stale retained Alpha Picks rows, not the user's holdings or App
watchlist; stale/unknown membership does not establish that a pick was closed.
Title, ticker and date matches provide recovery candidates, not confirmed
selection/removal roles. Long-closed companies' entire histories are not a
default recovery scope. Existing usable historical text stays untouched.

Opening an idle popup refreshes the read-only preview, but never starts capture.
The operator explicitly starts at most five bodies per batch. Each page is
background-priority work under the selected browser owner and existing shared
navigation budget/reserves, pacing and login/challenge pauses. Queue priority
does not mean an inactive tab: body recovery activates the admitted article tab,
as the existing article capture does, so visible lazy-loaded content can render.
Routine work can run between pages.

The batch waits for the shared page interval before its first page and between
pages; the popup shows a countdown, active stage and per-article outcomes.
Reopening it during a batch brings the progress section into view. Closing the
popup does not cancel the batch. An explicit native messaging port
keeps the browser background alive during this manual operation; completion or
cancellation closes it. Loss of that port interrupts the batch without automatic
reconnection. A 30-minute batch deadline requests cancellation and prevents more
pages after the active operation finishes cleanup. Browser restarts require a
new explicit start; reopening the popup reports interruption rather than silently
replaying work. A cancellation that opened no page does not restart the interval.

Only a local pacing denial with a future retry time and no attempted navigation
returns to the wait state. An opened page is not retried by this batch, and
budget, login, challenge, unknown admission or uncertain cleanup failures still
stop it. There is no new automatic schedule or website retry loop. Each target
is rechecked before opening it; the write compares the original body hash again
so a newer capture cannot be overwritten. Only the body is acquired in this
operation; no deep historical comment scan is added. A later explicit batch
omits successful repairs and shows unresolved work. Missing, disclosure-only,
metadata-only and comment-thread captures retain their specific quality failure
codes in the popup and job receipt; they are not all relabeled `parser_empty`.

Older shell deletion is on hold. Comments, event links, manual decisions,
research citations and potentially useful pick history must be reviewed before
any cleanup. Absence of a stored link is not evidence of no research value.
LLM-assisted semantic association and commentary classification remain separate
follow-up work after usable source prose is actually recovered. The proposed
[article workbench and classification design](docs/superpowers/specs/2026-09-27-sa-article-workbench-and-classification-design.md)
defines that next flow; it is not implemented or enabled by current collection.

Owners: [quality assessment](src/sa/article_body_quality.py),
[read-only recovery scope](src/sa/article_body_recovery.py),
[native recovery boundary](src/sa_native_host.py).

**Article source links and graphics.** Alpha Picks article captures retain safe
HTTP(S) hyperlink destinations, HTTPS image references, alternative text, image
titles and ordinary figure captions in their original document order. Links
inside paragraphs, lists and native HTML tables are retained as Markdown; the
original prose/table cells are not replaced by a generated interpretation. An
image reference comes from the browser-selected source or an explicit lazy-image
attribute. An unresolved image source and unsupported canvas/SVG/embedded media
remain visible gaps. The scraper neither clicks links nor downloads additional
images to fill those gaps. Unsafe schemes, embedded credentials and control
characters are rejected; relative paths resolve against the article URL rather
than a page-supplied `base` element. Excluded comments, advertising and controls
do not become article resources.

This is **remote references only, not an offline image copy**. Viewing the image
still requires a reachable original server and any applicable access permission;
the reference is not a guarantee that the image remains accessible. No image
bytes, OCR, chart values or chart interpretation are acquired. A text-only model
read has not read the image pixels. It must not claim otherwise from a caption
or URL. Quality assessment version 2 and deterministic article reconciliation
exclude reference destinations, image labels and standalone resource markers
from narrative evidence; a resource-only capture cannot establish usable prose.
Reference labels inside actual prose remain readable text.

Schema 7 adds nullable `sa_articles.body_capture_json`. The validated capture
observations (links/images observed and retained, unsupported-media count,
extractor version) are bound to the exact saved Markdown by SHA-256. Reads expose
`coverage.references` / `body_references`: `observed_references_retained` means
only the references observed in the selected article DOM were retained;
`partial` exposes missing references or unsupported media; `not_recorded` means
an older capture has no such evidence; `unavailable` means the evidence is
invalid or does not match the body. None verifies the entire source page or an
image download. The public evidence is included in the article pagination
snapshot identity. A preserved pick report can reuse it only when its body
matches the canonical article body; an older independent copy cannot borrow
newer evidence. Missing legacy evidence is not backfilled by inference or by a
read. The migration adds no network acquisition, image files or automatic recrawl.

Owners: [shared scraper](extensions/sa_alpha_picks/scrape_detail.js),
[body-bound observations](src/sa/article_body_capture.py).
Regression: [reference capture and downstream evidence](tests/test_sa_article_body_references.py).

**Acquisition and time.** Reading does not start an extension, reload a page,
extract comment signals, poll a provider, call IBKR, update configuration or
spend. Article body/comment capture times are distinct, and holdings retain
their stored per-position synchronization times. Neither a read time nor a
summary-generation time is a fresh market observation. Update remains an
explicit extension/sync operation with its existing requirements. A missing or
incompatible store is unavailable; it is not silently created or migrated.

**Article pages.** Defaults are 3,500 Markdown characters and two comments,
with 500 characters per comment. These are page defaults, not retention or
total-content caps. `body_limit=0` or `comment_limit=0` omits that section. Follow
`next_body_offset` / `next_comment_offset`; a long comment uses `comment_id` plus
its `next_text_offset`. Text offsets count Unicode code points. Comments are a
flat list with original parent IDs, not a claimed complete nested tree. Parents
outside the page can be read by ID; missing retained parents are flagged.
The default reserves room for source/reference evidence inside the existing
native model-insertion budget; neither the stored article nor its references are
shortened. All tool exporters share the same default. Larger explicitly requested
pages still face the existing output-boundary guards, with actionable continuation
or smaller-page instructions rather than malformed/truncated JSON.

Every nonzero continuation offset requires the first response's `snapshot_id`.
The article and comments are read in one SQLite read transaction. Identity
covers the served metadata and all stored body/comment content, including edits
and upvotes, so concurrent acquisition cannot silently join different versions.
The result preserves article URL/title/author/date, article/comment IDs, text
hashes and separate body/comment coverage. Observed counts or a completed scan
do not prove that the website's entire discussion was exhausted; no `complete`
claim is inferred from them. Body success cannot hide pending or failed comment
recovery. Comment focus is deterministic scoring, not verified sentiment; a
scoring backlog is exposed, not repaired by the read.
The returned next action names the existing `extract_sa_comment_signals` local
job; running it is an explicit derived-data update, not a provider acquisition.

**Holdings pages.** Defaults to ten positions, with explicit account/closed-row
filters and the same content-change guard. It does not construct the writable
`PortfolioStore`, create a manual account or alter an existing schema. Totals
cover all selected open positions, not only the current page. Values are stored,
not live; valuation counts expose missing prices/P&L. Cross-account broker-base
totals require one known base currency, otherwise they are withheld. Closed
positions remain outside totals. The raw broker-ID field is omitted and matching
legacy account labels are masked. User notes remain stored text; this is not a
claim of arbitrary free-text redaction.

**Limits and persistence.** Model/channel budgets are still enforced. Oversized
results return an actionable smaller-page result with their content identity,
not sliced JSON that loses a source, a gap or a total's scope. These snapshot IDs
detect changed mutable local data; they are **not** immutable historical archives.
Unchanged retained data can reopen across process restart, but an overwritten
old article/comment/holding version cannot be reconstructed by its hash. This
is distinct from immutable SA company-table observations and SEC citations.
No retained content is deleted by this change, and no news retention policy is
introduced here. UI/native-host article reads use the same body-quality boundary.

Owners: [article reader](src/sa/article_reader.py),
[holdings reader](src/tools/portfolio_holdings_tools.py),
[whole-page budget handling](src/tools/retained_read_results.py),
[channel and read-only regression](tests/test_retained_research_reads.py).

### SA Company Financial Tables

**Trigger and scope.** On a signed-in SA company income statement, balance sheet
or cash-flow statement page, use the extension's **Capture Company Data**
command. Supported views are Annual and Quarterly, with Absolute values; an
annual table's distinct TTM/Last Report column is retained, not relabeled as an
annual period. Standalone TTM views, growth views and hidden history are not
admitted. It captures the displayed supported period/currency view only. It does
not navigate to other companies, expand history, fetch private endpoints, solve
verification challenges, or inherit the Alpha Picks/news auto-sync alarms.
Chrome or Firefox, page loading and the account's actual entitlement remain prerequisites.
The selected tab is fixed before joining the existing extension job queue;
navigation before completion rejects the capture instead of saving another page.

**Admission and cleaning.** The extractor and native validator check a versioned
semantic contract: URL/title/company agreement, selected Absolute view,
currency/unit note, header identities and ordering, section roles, required
statement anchors and exact row/column alignment. Loading skeletons, restricted
cells, unknown shapes or values fail with typed reasons. Raw display strings and
decimal strings coexist; zero, absent and not-meaningful values are distinct.
Do not multiply every row by the table's millions/thousands scale: per-share
and other row-specific exceptions remain in the source labels. Values are
`provider_display_rounded`, not SEC-exact facts; no derived ratios are added.
Month labels yield `end_month`, never an invented exact `period_end` date.

The capture records a structural digest independent of cosmetic CSS and actual
financial values. A changed semantic structure within a previously accepted
company/statement/view/currency scope is rejected under the same extractor
revision, even when all new numbers look plausible. Existing observations stay
intact. A legitimate source redesign requires an extractor/fixture review; it
does not silently rebaseline itself. A digest is drift evidence, not proof that
SA's figures match every provider or original filing.

**Persistence and reuse.** Schema v4 of the existing `sa_capture.db` adds
`sa_company_observations`. Accepted content is addressed by a SHA-256 observation
ID. Identical content updates only its last successful capture time, while a
new value set gets a separate observation. Failed captures do not replace the
last accepted table. Company ingestion does not construct the market DAL or
write the market database. The read path opens SA/profile stores read-only and
does not create or migrate an absent/old database.

`get_sa_company_data(ticker, statement, view, currency, observation_id, ...pages)`
returns stored data, capture times, source URL, units, coverage and missing-value
reasons. Default pages contain at most 20 rows and 4 period columns; these are
page defaults, not dataset truncation. Pin the returned `observation_id` for later
pages or historical reads. Rows and columns have separate next offsets. If a
model channel cannot carry a page intact, it receives a typed smaller-page
request, never truncated numeric JSON. `last_captured_at` does not certify latest
publication or provider readiness; there is no hidden freshness timer or paid
refresh on this reader. Updates come from explicit capture or the separately
enabled financial refresh below, never from a stored-data query.

**Selection, capacity and operating boundary.** The independent
`sa_company_financials` switch controls this reader and ingestion; disabling it
does not erase captures, modify SA news/Alpha Picks, or enable FD spending. FD is
an independently selected/admitted financial alternative, not an automatic retry
when SA fails. Other supported company datasets have their own switches below.

Unchanged content is deduplicated. New company-observation JSON has a default
256 MiB logical storage budget, configurable for the native host with
`ARKSCOPE_SA_COMPANY_BUDGET_BYTES`. This budget counts this table's payloads,
not all SA data or SQLite file/index overhead. At capacity, new content is
rejected explicitly; nothing is evicted and unchanged captures still work.
It is not a retention rule for SA articles/comments or existing news. General
retention, backup removal and a headless service remain separate work.

Owners: [extractor](extensions/sa_alpha_picks/scrape_company.js),
[validation](src/sa/company_data.py), [storage](src/sa/company_store.py),
[reader](src/tools/sa_company_tools.py), [native entry](src/sa_native_host.py).

### SA Routine Acquisition Cadence

Current Chrome and Firefox sources share the same news/Alpha Picks scheduling
code. The values below are code defaults and allowed settings, not a readback
of the currently enabled browser preferences.

| Flow | Eligibility | Coverage limit |
|---|---|---|
| News | Fixed 5/15/60 minutes, default 60; optional `auto` checks a custom ET time-window table every 5 minutes | A heartbeat can skip without opening a page. `auto` is not an exchange-session calendar. |
| Alpha Picks | Quick Update every selected 15/30/60 minutes, default 30 | Recent article list plus at most four unique article pages across body, comment and reconciliation work, newest first. Never silently upgrades to Full, even with an empty local corpus. |
| Comments | Included with new article bodies; revisit scanned articles when an observed count changes or a first positive count appears | No independent comment timer; an unchanged count does not prove unchanged text. |
| Incomplete comment capture | A pending capture remains eligible even if the displayed count is unchanged; ordinary retries wait six hours after the last scan attempt | Quick adds at most one pending article per pass; Full shares its existing additional batch limit. Explicit Deep Repair can bypass this retry delay, not website admission or restrictions. |
| Additional comment recovery | In Full/Deep scans only: default seven-day age eligibility, with configured additional batches defaulting to 10/50 | The age rule does not itself schedule these scans. Old unscanned articles can remain outside Quick Update coverage. |

Comment age and scan budget are separate. Quick/Full, including first-capture
work and manual article linking, prioritize the last **30 days of comments**.
Only explicit **Deep Repair Scan** requests historical expansion. A first
capture's 120-second budget does not silently opt into historical repair.

Quick's `quick_workload` receipt exposes the selected IDs, per-run navigation
budget, eligible-candidate count and deferred-candidate count. Existing retry
gates and reconciliation proposal limits still apply: this is not a whole-corpus
backlog count. Unselected candidates retain eligibility for a later run. Historical
unusable bodies remain in the explicit body-repair flow, not the routine Quick
queue. The older native `check_detail_cache` action is not used by this flow;
its ticker matching permits exact symbols and documented scraper aliases only.

Keep existing selected intervals with shared coordination. Do
not enable frequent full/deep scans merely to compensate for missing coverage.
Future frequency changes should use actual navigation attempts, new-item yield,
retry/backlog age and restriction observations, not raw job receipt counts.
The [September 23 scheduling review](docs/superpowers/evidence/2026-09-23-sa-scheduling-review/README.md)
records the prior behavior and two reproduced defects: queued Alpha Picks could
execute after disabling auto-sync, and a known login failure did not stop its
next portfolio navigation. Both are repaired by the
[coordination delivery](docs/superpowers/evidence/2026-09-23-sa-automation-coordination/README.md).

### SA Comment Expansion And Capture Identity

**Candidate, not production-accepted.** The September 24 change remains on the
feature branch. Signed-in per-run comparison and the final frozen-revision full
regression are required before merge. See the
[comment acceptance procedure](tests/sa_comment_acceptance/README.md).
The first independent Firefox pair is **not accepted**: the candidate captured
105 comments versus 81, but omitted two baseline comments and hit the existing
45-second Manual cap. More total comments do not compensate for a lost subset.
That pair remains failed; changing its budget or combining its exports cannot
retroactively make it pass. The operator subsequently approved a separate
first-capture policy using the existing 120-second Deep budget, requiring a new
same-budget pair rather than comparing it to the earlier 45-second capture.
See the [paired evidence](docs/superpowers/evidence/2026-09-24-sa-comment-observation.md#paired-firefox-result-not-accepted).

The later 120-second large-thread pair (article `6334961`) is also **not
accepted**: legacy exported 259 comments, guarded 218; 206 shared comments
matched, 53 were missing and 12 were added. All 53 missing comments were within
30 days. Both runs exhausted their budget before reaching the bottom. The new
recency priority cannot retroactively pass that failed pair. Its geometry
motivates traversing already-loaded rows faster, without increasing the scan
budget, retries or settling frequency. Signed-in acceptance of that change
remains separate from offline browser tests.

Comment expansion is restricted to recognized comment/reply/text controls.
This includes SA's observed sibling reply-list footer, validated against its
parent row and wrapped reply rows; the whole `paywall-full-content` container
does not become an authorized control scope.
Known navigating links, new-context links, submit/reset controls and duplicate
nested controls are excluded. This does not make arbitrary page JavaScript
incapable of navigation. During capture, tab URL/loading/closure/new-context
signals and an isolated-document witness detect unexpected transitions, including
same-URL reloads. Article URL/canonical identity is checked before and after
reading body/comments. Invalid captures are not persisted under the requested
article. Once verified data has been serialized into the background, subsequent
tab navigation does not invalidate that already captured snapshot.

If a visible reply-expansion control or relevant legacy control cannot be
recognized safely, including one outside the known comment structure, the scan
reports `controls_unresolved`: existing comments and comment checkpoints are
retained, while a separately valid article body can still be saved. A diagnostic
failure is not permission to overwrite complete comments with truncated text.
The existing Quick/Full/Deep/Manual profile constants are unchanged. New
per-article selection below determines which profile an acquisition actually uses.

The isolated test package can record old/new candidates on the same DOM and run
either selector, exporting each run separately. It has no Native Messaging or
alarm permission, does not navigate to articles automatically and does not write
production databases. Browser-triggered requests from scrolling/clicking still
occur. These observations are not an exact HTTP-request count; tab events cannot
account for every XHR, redirect or page-script action. The normal SA collector
must be paused during this small manual test.

Same-DOM candidate agreement alone is not acceptance. Compare independently
captured full comment text and parent relationships, article attribution and
scan cost, never accumulated database counts. Changed source content, incomplete
traces or higher work/time are unresolved evidence, not a passing result.

### SA First Capture And Incremental Maintenance

**Candidate policy, not yet accepted on the live site.** First capture is a
per-article decision, not merely an empty-database decision. A never-scanned
article, eligible pending capture or explicit manual article repair uses the
existing Deep profile: up to 140 rounds or 120 seconds, with 1.6-second settling
and five stable-bottom observations. These are loop admission limits, not a
guarantee that an in-flight browser operation finishes at an exact deadline.
Ordinary Quick updates retain the 12-round/12-second profile; ordinary Full
updates retain 80 rounds/60 seconds. Partial work does not automatically retry
within the same pass. Website owner, allowance, pause and cooldown gates still
apply.

Valid partial captures can add comments without certifying completion. Budget
exhaustion leaves a separate pending-acquisition marker and does not advance
the provider-count checkpoint. The existing identity-overlap recovery state is
not a substitute for that marker: seeing an old comment does not prove the
unloaded tail or nested replies were visited. A qualifying stable-bottom scan
can finish pending acquisition; this still does not prove that every comment
ever published is available. Readers expose the pending state and stop reason.
Existing records without terminal evidence are not retroactively certified.

#### Recent Comment Priority

The 30-day priority uses **each comment/reply's own displayed date**, not the
article or parent date. The reference time is fixed at the start of a capture.
Dates without a timezone retain the existing browser-local interpretation;
unknown/future dates remain unknown and are not treated as old. A date quoted
inside comment prose cannot establish its publication time.

Recent/unknown comment text and their resolved parent context get priority.
Other older text-expansion controls are deferred in routine scans. Reply-list
controls are still inspected even under old parents: an unloaded reply's age
is unknown. Encountering an old row is **not** an early-stop condition, and no
unverified chronological ordering or guessed "Newest" control is assumed.
Already materialized older rows remain saveable; this is priority, not deletion
or a hard storage cutoff. Existing comments and article bodies are not purged.
Explicit Deep Repair includes older text expansion under its existing limits.

Traversal moves toward the materialized frontier in rendered, overlapping
viewport steps, not one large jump. Intermediate IntersectionObserver triggers
must still see the viewport. A round admits at most eight such steps and 500 ms
of render-wait work, within the existing capture deadline; changed row count
ends that batch. A render timeout stops acceleration and cannot support a
stable-bottom claim. The ordinary settle remains between rounds. Before any
rows exist it retains ordinary incremental scrolling. It does not increase
capture timeouts, retries, or click privileges.

Schema v6 records the last scan's scope, reference/cutoff, displayed-date basis,
observed recent/older/unknown counts, context count and deferred controls.
`coverage: unverified` remains explicit: these are observed counts, not a
provider-certified recent denominator. A terminal recent scan can finish its
pending acquisition and record the provider-count observation for detecting
changes, without advancing the full-history checkpoint or forcing historical
identity repair. Timeout/unresolved scans remain pending. Readers expose this
scope separately from overall stored-history gaps; old unscoped records remain
unknown. Identical-count Quick updates cannot prove that no text edit or
count-neutral reply replacement occurred.

Unchanged comment values do not rewrite an existing row. New comments and real
changes/enrichments still persist under the existing identity and merge rules;
truncated or unresolved captures must not overwrite fuller stored content.
Historical duplicate cleanup, which can cascade associated signals, is not run
as an acquisition side effect; destructive maintenance requires a separate action.
This saves local writes, not necessarily provider requests: the DOM collector
may need to load old parent threads to discover new nested replies. It has no
provider cursor that guarantees network-level per-comment continuation.

Routine updates skip articles with unchanged observed counts only when no
eligible pending acquisition exists. First/backfill acceptance and routine
maintenance are tested separately. The isolated harness exports the selected
profile, per-round scroll position, page height, bottom/loading state and click
count. Neither click count nor navigation count is a full HTTP request meter.
See [comment acceptance](tests/sa_comment_acceptance/README.md).
The [September 24 signed-in Firefox evidence](docs/superpowers/evidence/2026-09-24-sa-comment-recent-and-routine-acceptance.md)
records the large-thread improvement and partial routine scan separately.
It does not establish complete recent coverage, equal HTTP load, or Chrome
live acceptance; stored-row preservation is verified by isolated replay.

### SA Financial Refresh Scheduling

**State:** the shared Chrome/Firefox implementation is opt-in and off by default.
Signed-in installed-extension acceptance is a separate gate; building the Firefox
artifact does not establish live SA loading reliability. No production schedule
is enabled by a code upgrade.
The [bounded Firefox watchlist acceptance](docs/superpowers/evidence/2026-09-23-sa-watchlist-collector/README.md#signed-in-firefox-result)
verifies the operator's two-company manual queue and saved-table readback.
It is not Google Chrome acceptance or authorization to start the production list.

**Shared acquisition authority is implemented.** The formal Firefox owner was
selected on September 26. News metadata updates were observed; the first Alpha
Picks attempt exposed a page-readiness failure and an incorrect success receipt.
The [readiness repair evidence](docs/superpowers/evidence/2026-09-26-sa-alpha-readiness/README.md)
keeps that failure separate from the replacement's regression and live checks.
Either Chrome or Firefox can be explicitly selected. Firefox is the operator's
initial preference, not a fixed dependency. The
[coordination evidence](docs/superpowers/evidence/2026-09-23-sa-automation-coordination/README.md)
separates installed offline tests, private Firefox native-host checks and
remaining signed-in/rollout gates. A passing fixture is not live SA acceptance.

**Prerequisites are separate.** The local host must connect, the chosen browser
must be running, SA must be signed in when the requested content requires it,
and that content must be accessible under the relevant subscription. Premium
does not imply Alpha Picks access, and a working login does not prove either.
The App cannot infer all entitlements in advance. Detected login/challenge/access
failures have explicit states below; unobserved session liveness remains unknown.

In **Financial statement updates**, choose **App watchlist** or selected tickers,
statements (income, balance sheet, cash flow) and Annual/Quarterly views.
Both views initially check every seven days, independently adjustable from 1-365
days. The annual page also contains TTM, so it is not necessarily unchanged for a
year. All scheduled scopes use **USD / Absolute** tables. These intervals are
repeat-check policies, not data expiration or evidence that a new filing exists.

The read-only preview updates before activation: membership, missing/due/fresh
scope counts, current collector, waits and a pacing-only lower bound. Observed
capture durations, when available, are supplementary. Neither is a completion
promise: page loading, quotas, routine work, pauses and a sleeping/closed browser
can extend elapsed time. Whole-watchlist membership comes from the complete App
active universe, not a copied or hard-coded list. Source/staleness warnings and
unsupported symbols remain visible; unavailable inputs refuse partial-universe
acquisition. Membership is rechecked before each scope; removed targets do not run.

The App's `BRK B` spelling and `BRK-B` alias resolve to SA's `BRK.B` company
pages. These aliases share one capture scope, stored observation lookup and
cooldown; the original App membership is not renamed. This mapping applies to
queries and scheduling, not to validating source captures. No general replacement
of spaces or punctuation is used, and other unmapped symbols stay visible.

**Enable updates in this browser** is the explicit activation command. It first
disables local acquisition intent, validates idle authority and the operator's
policy, selects/configures the installation, then enables the selected financial
schedule and restores previously selected routine settings. A failed intermediate
step leaves local schedules disabled and identifies that step. Saving settings
alone does not activate collection. Reading status never initializes the store.
Restoration is conditional on the stored routine-setting revision: a newer stop
or interval change, before suspension or while activation awaits the host, wins.
The open popup's routine switches, intervals and summary follow storage changes;
an activation failure must not leave an apparently enabled switch on screen.

**Update missing / due** reuses fresh scopes, including while the periodic
schedule is off. A separate advanced **Force refresh** needs confirmation;
it bypasses source-age reuse only, never restrictions, budgets, ownership or a
scope's failed/interrupted-attempt backoff. Other eligible scopes continue while
that scope waits; pending intent alone does not cause one-second retry polling.
Checking force/recovery/activation consent alone is not a configuration edit and
does not save or disable the periodic schedule. Unsaved capacity-policy edits
remain a separate draft until explicit activation. Actual scope/interval edits
still use the existing disabled-save step before a manual update; re-enabling
that changed schedule requires the explicit activation command.
Changing settings cancels old manual intent. Cancelling a queued update does not
disable the separate periodic schedule; a late response cannot resurrect cancelled
work. Closing the popup does not discard the durable queue.

### SA Ownership, Pacing And Navigation Budget

The authority is `sa_company_refresh.db`, next to the chosen `sa_capture.db`.
All managed news, Alpha Picks, comments and company acquisition share it.
Both hosts must use that same local data root. Selection binds an installation
UUID, not every browser profile with the same name. Other installations can
read retained data but cannot acquire. Handoff requires explicit idle selection;
it does not copy or silently enable the other browser's local schedules.
There is no automatic failover when the selected browser closes.

The queue finishes its current work, then chooses queued routine work before one
background financial scope. It does not preempt a page operation. Continuous
routine work can delay financial work, and that waiting state is reported.
Financial pacing waits do not occupy an active reservation.

Advanced controls offer 15/30/60 seconds and a valid custom positive interval.
Existing configurations retain 60 seconds until changed. The native next-start
deadline is measured from financial task completion and confirmed cleanup, not
from popup reads. Active short timers can continue a 15-second queue while the
worker remains alive; durable browser alarms/startup restore progress after
suspension. Browser alarm granularity can make the next run later, never earlier.
This does not promise 15-second background wakeups.

Hourly and 24-hour limits are optional operator inputs. The September 26 operator
choice is no fixed page-count ceiling: a new setup leaves **Limit pages per hour /
day** unchecked. A previously accepted numeric budget stays enabled until the
operator explicitly changes it. The native policy represents uncapped operation
with both limits `null` and both reserves `0`; missing/mixed policy fields are
invalid, not an implicit unlimited grant. Turning the option off does not erase
the navigation ledger, and later re-enabling a limit counts earlier attempts.

When caps are enabled, both limits and both routine reserves must be provided.
Financial work may use only unreserved capacity; routine work can use the reserve
but cannot exceed the total. Every managed page create, URL change, reload and
current-page capture admission is checked and debited before the browser action.
A refused or repeated permission cannot become a second executable navigation.
Lowering limits, selecting another browser or restarting does not reset spent
capacity. The Quick action's small batch boundary is separate from these optional
site-wide caps; Full/Deep scans require their own explicit action.

Uncapped mode removes only the rolling count rejection. Single-owner admission,
routine-first queueing, financial/body pacing, cancellation, login/challenge pauses
and observed-rate-limit cooldowns remain enforced. It does not accelerate any
schedule or authorize bulk recovery. See the maintained
[Firefox activation guide](extensions/sa_alpha_picks/FIREFOX.md#activate-or-restore-routine-collection)
for updating the formal extension and restoring routine capture independently of
manual historical-body recovery. Chrome uses the same controls.

**These are local navigation budgets, not HTTP request quotas or SA-approved
rates.** A page may issue many subrequests, existing user tabs and other devices
remain unmeasured, and prior traffic coverage is explicitly unknown. Deduplicated
stored content does not prevent repeated network acquisition. The implementation
does not automatically turn job receipt counts into a provider allowance.

A reservation never expires into another collector. A persisted browser pending
marker is reconciled against the same native ledger, request, installation and
generation. A matching terminal record clears only that obsolete marker, without
replaying a navigation. Absence, age, unknown replies or an active native task are
not completion evidence. Uncertain browser actions or failed cleanup stop further
work until the operator stops old acquisitions/tabs and explicitly recovers.
Recovery is refused while this runtime is still executing a capture or body batch.
Recovery is logged and fences the old
reservation; it does not change owner, forgive cooldowns or remove login gates.
Missing/corrupt authority refuses acquisition instead of silently reinitializing.
Legacy financial-only state requires explicit stopped-instance confirmation,
one backup, upgrade and subsequent owner selection; old automated clients must be
stopped/updated before rollout.

### SA Successful Checks, Pauses And Receipts

Alpha Picks collection distinguishes a saved failure record from a successful
capture. A native `refresh_failure` acknowledgment is never capture success,
including when reading an older browser receipt. Failed prerequisite phases or
interrupted article extraction must not produce completed downstream phases or
advance a healthy-run anchor. Existing historical job records are not rewritten.

Routine news, Alpha Picks and financial tasks hold a native messaging port while
executing, just as manual body repair does. Closing the popup must not suspend a
task during its page/scroll waits. Ports close after cleanup and telemetry; a lost
port stops further navigation, never automatically reconnects or retries a page.
Idle schedules do not hold a port. Browser termination can still interrupt work;
the popup distinguishes a live runtime from a stopped capture requiring recovery.
New deferred job records use status `deferred`, not `succeeded`. Older receipts
retain their original identity and are interpreted using their derived outcome.

Fresh browser tabs can still contain `about:blank` before the requested document
commits. Alpha Picks readiness waits inside its existing 90-second deadline,
without reloading or widening host permissions. Known transient injection-denial
errors are retryable only while navigation is loading; a denial on a completed
provider document is an error, and login/challenge stops still take effect.
Readiness does not require every page resource to finish loading.

Each financial ticker/statement/view retains its successful capture timestamp,
observation ID, next eligibility, attempt and failure. Reads and unchanged saves
do not move deadlines. Accepted unchanged content advances the successful check
without duplicating observations. Manual matching USD captures can satisfy a
scheduled scope; native admission verifies the stored observation rather than
trusting browser freshness claims. A scope captured after a queued force request
already satisfies that same intent after recovery. A later explicit force request
is new intent.

Failures preserve old observations and successful timestamps. Scope backoff starts
at six hours and grows to seven days without blocking other eligible scopes.
Recognized structure/identity failures pause that financial batch instead of
publishing guessed values. Missing watchlist inputs retain visible pending work.

| Observation | Acquisition behavior | Operator signal and recovery |
| --- | --- | --- |
| Login required | Site-wide pause; clear acquisition alarms; stop before another page | Extension `!` badge and App home/settings warning; sign in, then explicitly resume |
| Human verification | Site-wide pause, not a timed retry | Badge/warning; operator resolves verification before explicit resume |
| Access/subscription restricted | Pause the affected financials, news or Alpha Picks capability only | Name the affected capability; login alone does not claim entitlement |
| Visible rate limit | Site-wide cooldown, initially six hours, doubling to seven days | Show deadline; force, owner switch and recovery cannot bypass it |
| Capacity exhausted | Typed deferred result with next eligibility | Retain completed work; do not label it completed or failed extraction |
| Native state/cleanup uncertain | Refuse new acquisitions | Stop old work, then explicitly recover; do not retry an uncertain navigation |

Restrictions are stored before tab cleanup. Startup/repair cannot recreate alarms
through an unresolved login/challenge gate. Challenge takes precedence over a
simultaneous rate message; timer expiry does not resolve a human gate. A successful
new acquisition resets the rate-failure counter; saving an already loaded page
does not clear cooldown. Current detection uses visible content and is not a
complete HTTP 429 / `Retry-After` monitor.

The App polls only a read-only local projection for its home/settings warning;
it does not spawn the host, contact SA or install a database. The badge uses the
same persisted restriction meaning. No system notification or remote delivery is
included here. A closed App cannot display its warning, and a closed browser
cannot run its alarms.

Protocol-v2 receipts carry installation, generation, task, policy and navigation
identity. Native terminal proof is checked at native forwarding and API admission;
delayed outbox delivery remains valid after an owner change, without granting the
old owner permission to acquire. Waits are deferred, fresh reuse/cancellation are
skipped, and real failures retain failure/degraded precedence over simultaneous
waits. Saved partial results are retained. Proof/navigation retention has not been
added: deleting those records prematurely would invalidate the seven-day outbox.

Only collector-owned tabs are opened/closed, without requesting focus. View and
currency must match. Changed selectors must produce changed, stable table values;
changed periods must also produce changed headers. A label changing before its
table finishes loading is not accepted. If a legitimate switch produces identical
values, this conservative check reports not-ready instead of guessing. Native
identity, unit, row/column and layout validation remains
mandatory. Source admission is checked before opening a page and before persistence.
No fallback API, subscription purchase, private endpoint or anti-bot bypass is added.

A closed browser cannot run alarms. Restart/reload restores the schedule and catches
up gradually, not all missed intervals. Expired login and blocked pages are failures.
Firefox temporary add-ons disappear on restart; unattended daily use needs a
persistently installed signed add-on. This is not the independent always-on service,
and Settings cannot yet observe browser liveness while the browser is closed.

Native-host launch is a separate prerequisite from a successful command-line host
probe. A connection failure stops before SA navigation and is reported as
`sa_company_native_host_unavailable`, not as a page-loading failure. The popup
shows **Local app connection unavailable** and does not advance the successful
capture time. Snap Firefox can also have a remembered desktop-portal denial for
the host; changing it requires the user's consent, not an automatic grant or a
browser-sandbox bypass. See [Firefox's native-messaging portal documentation](https://firefox-source-docs.mozilla.org/toolkit/components/extensions/webextensions/native-messaging-portal-design.html).

Firefox native-host requests are serialized by host with an extension-origin
[Web Lock](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API), including
the time spent waiting for desktop consent. A caller timeout does not release a
still-pending native request. Popup reconciliation requests are owned by the
background, with an exact popup sender and existing-action allowlist, so closing
the popup does not make it the owner of an in-progress consent request. Portal
dialog contention can record a denial without an intentional user refusal;
resetting that record still requires consent and does not itself grant access.
If the system prompt remains unavailable, the user can explicitly choose a
host-specific manual authorization. Read the exact host/browser permission back
and verify a real browser-to-host request before resuming capture; the App must
not grant permission automatically. Manual authorization does not prove that
desktop-dialog presentation is fixed. See the
[installed-browser acceptance record](docs/superpowers/evidence/2026-09-22-sa-financial-refresh/README.md#explicit-manual-consent-and-first-saved-capture).

Owners: [refresh state](extensions/sa_alpha_picks/company_refresh.js),
[browser integration](extensions/sa_alpha_picks/background.js),
[popup](extensions/sa_alpha_picks/popup_company_refresh.js),
[regression](tests/test_sa_company_refresh.py).

### SA Valuation, Peers And Forecasts

The same Chrome/Firefox source and **Capture Company Data** command support
these explicit current-page scopes, without navigating between them:

| SA path after `/symbol/<ticker>/` | Dataset | Retained scope |
| --- | --- | --- |
| `valuation/metrics` | `valuation` | Valuation measures table, including GAAP/Non-GAAP, TTM/FWD and sector/5Y comparisons; excludes sidebar cards/charts |
| `peers/comparison` | `peers` | 18 recognized tables, from profile/ratings/grades to growth, profitability, ownership, risk and financial summaries; company columns must agree across every section |
| `earnings/estimates` | `estimates` | Annual normalized EPS and revenue consensus tables, including ranges and analyst counts |
| `earnings/revisions` | `revisions` | Annual EPS/revenue revision tables, including 1M/3M/6M changes; does not infer an undeclared EPS accounting basis |

**Loading is part of acquisition.** Native-host admission checks the selected
category before script execution because scrolling can cause SA requests. Saving
rechecks selection. Capture pins the current tab before queueing, then scrolls
each recognized section and waits for two equal, aligned table reads. Each
section has a 10-second readiness deadline; the operation has a 90-second
deadline. Checks run 300ms apart against the DOM, not direct provider requests.
There are no automatic retries, clicks, new tabs or changes to financial views.
The observed horizontal arrows are scroll controls, not pagination; all their
data columns must already be in the DOM. Unknown pagination produces
`sa_company_pagination_unverified`, not an assertion that all pages were read.

Missing/empty loading cells, unknown sections/row meanings, changed company
columns, virtualized-away tables and changed values during traversal reject the
capture. A challenge stops acquisition. Mouse/keyboard/touch interaction aborts
the scroll pass; otherwise the original scroll position is restored. A normal
failure retains earlier observations and never switches to FD. These limits
bound an explicit operation; they are not a documented safe SA request rate or
permission to bypass verification.

**Semantics.** Cleaned numeric strings retain raw display text and any K/M/B/T
multiplier separately. Currency symbols do not independently establish ISO
currency; these scopes use `currency=DISPLAY` and per-cell currency remains
unknown. Percentages are not fractions. Ranks, grades, recommendations, years
and ordinary numbers are distinct cell types. Explicit missing/NM/not-covered
states are not zero, and estimates outside their displayed low/high range fail
admission. GAAP/Non-GAAP, TTM/FWD/MRQ and fiscal month labels are not collapsed.

`provider_data_at=null` means that the tables do not establish a provider update
time. `price_qualification=not_live_quote` prevents treating captured trading
rows as current executable prices. Peer selection is the displayed SA/operator
comparison set, a judgment with no verified selection rule, not an ArkScope
screen or a financial fact. Capture cannot certify upstream numerical truth.

**Reads and retention.** Use `get_sa_company_data(ticker, dataset, table, ...pages)`
with the named dataset. The result lists `available_tables`; `table` selects one
without downloading again. Omit `statement`/`currency` for these datasets; those
arguments belong to the financial-statement scope. Pin `observation_id` across
table/row/column pages and later reopening. Annual forecast rows never invent an
exact fiscal end day. No read updates a clock, creates a DB, launches a browser
or spends credits. No default TTL asserts these snapshots remain current.

The observations share the existing content-addressed store and its 256 MiB
logical payload budget; this is not a second unbounded archive. Distinct content
is retained, unchanged content deduplicates, and failed captures do not erase
history. Chrome and the generated Firefox build share the extractor; build
parity is not a claim of installed, authenticated Firefox acceptance.

Owners: [research extractor](extensions/sa_alpha_picks/scrape_company_research.js),
[research validation](src/sa/company_research.py),
[shared storage](src/sa/company_store.py), [local reader](src/tools/sa_company_tools.py).

The route surface does **not** select a provider for every dataset or globally
disable that provider. News, quotes, calendars, SA captures and other Finnhub
tools keep their existing owners. Disabling Finnhub earnings supplements does
not disable a calendar schedule, or vice versa. Calendar hints may eventually
come from another selected source; missing Finnhub coverage cannot establish a
financial refresh deadline. Detailed valuation and peer ranking return
`financial_operation_not_ported`; they do not fall through to FD or SEC. The
common SA/FD reader supports the reviewed inputs and ratios described above,
without treating raw SA tables as inputs to the legacy calculators. Massive financials
remain unavailable rather than presented as working merely because a key or
subscription exists. No external MCP server or subscription upgrade is implied.

Owners: [source policy](src/data_source_routing.py),
[Settings API](src/api/routes/providers_config.py),
[Settings controls](apps/arkscope-web/src/settings/DataSourceRoutingSection.tsx).
GET `/providers/data-routes` and PUT `/providers/data-routes/{dataset}` inspect
or save policy only; neither contacts a data provider.

### Financial Read Controls

`get_fundamentals_analysis` accepts `freshness` and optional `max_age_seconds`.
These controls belong to research tools; App/HTTP GET reads always use `stored`.
The legacy `get_detailed_financials` signature retains those arguments for
compatibility but returns `financial_operation_not_ported` without acquisition.

| Mode | Behavior |
| --- | --- |
| `auto` (tool default) | Prefer eligible local observations. Only an explicit/primary FD source may acquire missing or stale inputs under admission; an SA gap never authorizes paid FD fallback. |
| `stored` | Read retained observations without acquisition or cache writes, independently of a reuse-age window. Missing inputs and any requested age comparison remain explicit. |
| `refresh` | Require a named source. FD uses governed acquisition/coalescing; SA returns a browser-update requirement. There is no automatic source substitution. |

`max_age_seconds` must be a nonnegative integer, not a boolean or string. It
overrides the `auto` reuse age. In `stored`, it only annotates the observation's
age comparison; it does not hide retained facts or trigger acquisition. Combining
it with `refresh` is rejected rather than silently ignored. Historical period,
observation and read-identity pins require `stored`.

Current default authority is
[`config/user_profile.yaml`](config/user_profile.yaml), under
`data_preferences.fundamentals_sources`:

- `refresh_days`: **7 days** for automatic financial reuse unless explicitly
  overridden. It is not a lifetime for a retained financial statement.

This is a configurable fallback, not the final event-aware policy. A local read
does not restart the acquisition-age clock; a fresh provider response currently
does. Legacy `ttl_days` / `cache_days_*` storage metadata does not decide
stored-read eligibility. Annual and quarterly observations can be restated or
corrected; a successful read does not certify the newest provider version.
Reopening an exact retained version and asking for the latest version are
different requests. FD does not retain all overwritten response versions.

Results describe source observations with provider/dataset, retrieval mode,
`freshness_mode`, `fetched_at`, `evaluated_at`, age, selected maximum and persistence
outcome. The constant `latest_period_verified=false` field has been removed;
there is no implemented latest-period verifier behind these tools. Acquisition
reuse also does not certify the legacy financial formulas or period alignment.

Owners: [reuse policy](src/fundamentals/reuse.py),
[financial tools](src/tools/analysis_tools.py),
[FD client](data_sources/financial_datasets_client.py).

### SEC Research, Quotes And Browser Captures

The optional SEC Settings entry accepts a stock symbol such as `AAPL`; numeric
CIKs remain an advanced exact identifier, not required user knowledge. GET
`/sec-research/issuer/resolve?issuer=AAPL` uses only the existing stored official
ticker map. It does not create a market store or acquire a missing map. An absent,
failed, unmatched or ambiguous mapping has an explicit result and is never guessed.

The separate **Update company directory** command, POST
`/sec-research/issuer/refresh`, accepts a ticker and makes at most one governed
official-map request after the existing write hook, configured SEC identity and
capture-budget checks. It can install SEC storage, but does not acquire that
company's filings/facts, enable a schedule or authorize later acquisition. The
existing general permission hook is still audit-only, not a new interactive
authorization engine. Company refresh/resume remains a separate explicit action.
Storage/quota and schedule details are collapsed administration, not mandatory
company-research input. Previously retained citation endpoints are unchanged.

Owners: [SEC routes](src/api/routes/sec_research.py),
[optional Settings entry](apps/arkscope-web/src/settings/SecResearchPanel.tsx),
[issuer command/read tests](tests/test_sec_research_issuer_routes.py).

SEC research's explicit `auto` mode uses a **24-hour** recency check for issuer
mapping and full refresh receipts, and retries pending receipt coverage. This is
an application policy, not an SEC publication guarantee. Already captured filing
documents may be reused without this age test. Pinned captures/fact selections
and continuation cursors remain local; `refresh` is invalid for those pinned
reads. See the [tool service](src/sec_research/tool_service.py) and
[SEC operations](docs/design/SEC_RESEARCH_OPERATIONS.md).

Quotes default to a **60-second** requested age tolerance. `market_data_type`,
`price_basis`, provider trade time and local receipt time remain separate.
Previous close and stored bars are historical; delayed/frozen feeds are not live.
When freshness cannot be established, `stale` is null, not false. Even a newly
received bid/ask midpoint does not prove a known price timestamp. These rules
do not admit a low-latency trading service. Owners:
[quote tool](src/tools/current_quote.py),
[local holdings tool](src/tools/portfolio_holdings_tools.py).

SA capture requires a usable signed-in browser and the relevant access. Article
body success with comment failure remains incomplete for a comments request.
There is no universal synchronous "refresh SA now" contract on research reads.
The existing `refresh_sa_alpha_picks` tool returns local state and an extension
refresh hint; it does not start browser capture. The extension already owns
manual operations and opt-in Chrome alarms for Alpha Picks and market news,
using separate `alphaPicksAutoSyncEnabled` / `marketNewsAutoSyncEnabled` settings.
These are not entries in the ten-source API scheduler below. Future unified
Settings must respect that owner rather than start a second competing collector.
Browser/session and native-host availability remain prerequisites, and an alarm
does not establish successful capture or uninterrupted unattended service.
Larger scrolling budgets do not prove date coverage or list exhaustion. See the
[recent collection and Alpha Picks policy](docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md#alpha-picks-open-positions-first)
for the Open-position-first direction and its remaining implementation limits.

## Scheduled And Manual Collection

[`SOURCES`](src/service/data_scheduler.py) is the executable interval authority.
All ten data-source schedules default to **disabled**. Settings may override
`schedule.<source>.enabled` and `schedule.<source>.interval_minutes` independently;
manual execution does not require enabling the recurring schedule.

| Source ID | Default interval (minutes) |
| --- | --- |
| `sec_research_filings` | 1440 |
| `polygon_news` (Massive) | 60 |
| `finnhub_news` | 60 |
| `ibkr_news` | 120 |
| `ibkr_prices` | 60 |
| `fred_series` | 1440 |
| `fred_release_dates` | 10080 |
| `finnhub_economic_calendar` | 60 |
| `finnhub_earnings_calendar` | 240 |
| `finnhub_ipo_calendar` | 1440 |

The scheduler checks due work every 30 seconds. Due-ness uses the last attempt,
including failed terminal outcomes, so the interval also acts as retry backoff;
it is not a successful-data clock. Settings currently bounds intervals to 5
through 10080 minutes. Source locks, writer contention and Gateway availability
can defer or skip execution; the configured interval is not a completion SLA.
The source scheduler runs in the API sidecar. Independent unattended lifetime
after Desktop shutdown is not delivered by these scheduling controls.

Same-source overlap is skipped, not queued or returned as a shared task.
Financial acquisition has separate same-query coordination and rereads the saved
result after waiting. That does not implement scope-aware joining for all jobs.
Equivalent future catch-up requests must match provider, dataset, storage owner,
symbols, period/date range and completeness requirements; "the source ran" is
not enough. A failed or unsaved acquisition is not permission for every waiting
caller to retry automatically.

The shared first-news-fetch target is **14 calendar days per source/ticker**,
including newly added tickers. Existing cursors govern subsequent collection.
This target does not prove entitlement, returned coverage or completion: source
limits, pagination and interrupted work still matter. Do not invent a seven-day
free-tier ceiling from an empty result. See the
[news policy](docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md#news-a-recent-target-subject-to-real-access)
and [shared target](src/news_collection_policy.py) for implemented paths and gaps.

### Calendar Outcomes And Coverage

The default earnings-calendar request covers **today through 30 days ahead**,
using explicit symbols, otherwise the watchlist, otherwise an unfiltered request.
It cannot establish a date 70 or 90 days away. Economic recent collection uses
7 days back through 14 ahead; IPO uses 30 back through 90 ahead. These request
horizons are independent of both schedule cadence and financial reuse age.

Finnhub calendar jobs now preserve sanitized request receipts: dataset, symbol,
date range, `checked_at`, accepted/rejected row counts, response state and typed
failure. Response states distinguish `empty`, `data`, `partial`, `rejected` and
`failed`. Inserted, changed, unchanged and skipped counts describe storage work,
not the entire provider universe. Rows returned unchanged can be successful;
a valid empty window can also be successful. Malformed/error envelopes cannot
masquerade as empty data. Runs with completed storage work and errors are partial;
errors without completed storage work fail.

Corrected earnings dates are recorded as revisions. Historical reads use the date
from the selected revision, not today's canonical date. Missing historical date
evidence is unavailable, not fabricated. These repairs do not establish live
Finnhub coverage or provider statement readiness.

The old September 18 zero-row job lacks request/response evidence and was
API-triggered; its status alone cannot identify why the table remained empty.
Do not retroactively label it a failed schedule or rewrite its history. See the
[calendar repair receipt](docs/superpowers/evidence/2026-09-21-calendar-refresh-evidence/README.md).
Owners: [calendar client](data_sources/finnhub_calendar_client.py),
[job execution](src/macro_calendar/execution.py),
[revision store](src/macro_calendar/local_store.py).

## Event-Anchored Financial Updates: Approved Direction, Not Implemented

The next integration must replace the uniform-window decision where sufficient
evidence exists, without claiming that a calendar date alone proves freshness.
These are design requirements, not currently selectable states or configuration:

1. Identify the requested provider, statement set, financial periods and observed
   versions. Establish that the latest relevant released period is actually
   covered before treating a later event as a quiet-period boundary.
   Do not equate a calendar year/quarter with the company's fiscal period without
   matching evidence.
2. Keep the next expected publication/check as an **absolute time** with its
   evidence. Re-reading or fetching the same financial version updates check
   evidence, not the publication anchor. Calendar corrections can change it.
3. At an applicable release, or while a released statement is missing, check
   provider availability at bounded, authorized intervals. Income, balance and
   cash-flow statements may become available separately. An earnings calendar
   is only a hint; provider-specific readiness or actual new data is stronger
   evidence. No maximum processing delay is assumed.
4. Reuse the newly observed version when it satisfies the scope. Missing or
   ambiguous anchors use an explicit configurable fallback, currently the
   acquisition-age window. Keep unknown/pending coverage visible, respect paid
   refusal/backoff, and retain the user's ability to request a refresh.

For example, if a justified next check is at day 90, checking again on day 20
leaves **70 days**, not a new 90-day timer. A forced request returning the same
version must not move that anchor to day 110. But if the cache is already missing
the latest released quarter, a future day-90 event cannot justify waiting.
Likewise, a calendar with only 30 days of coverage cannot invent that anchor.

The future decision should record last check, data period/version, next check,
reason and evidence scope separately. Quiet-period financial reuse can avoid
repeated statement requests, but calendar/availability checks may still cost time
or money. Do not advertise 3-5 polls per event, 16-20 yearly requests or a savings
guarantee without measured usage, coverage and billing evidence.

Implementation boundary and acceptance owner:
[calendar and event-aware refresh plan](docs/superpowers/plans/2026-09-21-calendar-refresh-evidence.md).
The existing seven-day local-reuse behavior remains active until this separate
integration is implemented and verified. There is no automatic provider webhook
subscription or live latest-period probe in this policy.

## Cost, Access And Retention

Financial Datasets HTTP requires an enabled policy with positive
`daily_request_limit` and `requests_per_minute`. Settings owns the optional
`data_sources.financial_datasets.request_policy` override in `profile_settings`;
`data_preferences.paid_sources.financial_datasets` in the profile YAML is only
the default when no override exists. An invalid saved policy does not fall back
to an enabled YAML policy. Missing limits refuse new requests; disabled paid
acquisition does not prevent eligible local reads from a selected source.

PUT `/providers/request-budgets/financial_datasets` requires explicit
`confirm_paid=true` to enable paid acquisition. The UI shows the attempt limits
and their consequences before saving. Source selection alone cannot activate
spending. Saving does not fetch data, buy a subscription or discover a plan's
entitlements. Limits retain the governor's signed-int64 range; the Settings API
returns decimal strings and accepts exact decimal strings/integers to avoid
JavaScript rounding. There is no newly imposed product-tier cap.

The installation/key-scoped
[governor](data_sources/financial_datasets_governance.py) reserves attempts before
dispatch and does not refund failed/uncertain attempts. It enforces request counts,
not a verified dollar cap or the account's remaining credit balance. The legacy
`daily_budget_usd` preference is not an enforced spending limit. Separate machines
are not coordinated by this local ledger. One fundamental-analysis call can
require up to three statement requests; a tool invocation is not a billing unit.

SEC research acquisition requires the configured identity and shared
[transport governor](data_sources/sec_transport.py). Its additive-write
[permission hook](src/api/permissions.py) currently logs intent; interactive
permission enforcement is not implemented. This protection
must not be attributed to every other provider: for example, Finnhub calendar
client spacing is per client, not a shared cross-process request governor.
Future external tools need independent operation/cost authorization; internal
`auto` or detailed audit logs do not grant it. No subscription upgrade, credential
switch or repeated billable probe is implicit in a refresh request.

Acquisition lookback, read reuse and retention are separate policies. The
14-day news bootstrap and seven-day financial reuse window authorize no deletion.
The obsolete-backup cleanup is complete. The user's subsequent clarification is
that ordinary-news retention serves search usefulness and performance, not disk
capacity or permanent archival. Eligible old, unreferenced news need not retain
its body or metadata forever. A one-time export is optional, not a required
permanent archive/reopening service. This is lower-priority P2 work and must not
delay unattended service, external access or correctness repairs.

The approximately 90-day window remains a candidate-selection preference, not an
unconditional SQL delete or a default applied to every search. No general purge
or recent-only index policy is implemented. SA analysis/comments do not inherit
this ordinary-news cutoff. Manual holds, citations, investigation evidence and
active recovery dependencies retain their own protection requirements.

### Retention Delivery Status (September 22)

- **Executed:** twelve obsolete June/July market/profile rollback snapshots and
  sixteen associated empty-WAL/SHM files were removed after identity/open-handle
  checks. Removed allocation: 13,324,185,600 bytes. Newer recovery backups, current
  DBs, news rows and existing archives were not deletion targets. See the
  [exact receipt](docs/superpowers/evidence/2026-09-22-retention-delivery-reset/backup-cleanup.json).
  This is a named one-time cleanup, not an age-only backup purge policy.
- **Inventoried:** 389,545 normalized market-news articles; 294,445 precede the
  candidate cutoff `2026-06-24T00:00:00Z`. These are age-only counts before
  protection checks, not approved deletions or counts to add to the legacy view.
  Timezone-aware parsing is required: SQLite alone does not parse the legacy
  `+0000` timestamp representation. SA ordinary-news eligibility still needs its
  own inventory. [Inventory](docs/superpowers/evidence/2026-09-22-retention-delivery-reset/news-inventory.json).
- **Revised proposal, not implemented:** selective protection and eventual removal
  of old ordinary news, without a mandatory archive service or permanent title
  index. Assess actual search paths and measure relevance/latency before choosing
  index-windowing, query changes or pruning. Market search already has date
  predicates over `news_fts`; filtering results is not the same as maintaining a
  smaller index or proving faster searches. Full-text search must state its scope.
- **Still pending, lower priority:** search measurements, reference protection,
  coordinated cleanup/Settings policy across ordinary-news owners, and separate
  job-history handling. Supervised service lifetime, failure delivery and external
  admission remain higher-priority independent work. No current data/index change
  follows from this policy revision, and compaction is not its objective.

## Maintenance And Verification

### News Full-Text Index Maintenance

Archiving alone does not remove live search entries. Owner-managed deletion or
index-windowing must remove the intended search documents after protection checks.
Legacy, normalized and SA news indexes already have insert/update/delete triggers;
correctly maintained deletion does not require a full rebuild after every batch.

FTS5 `optimize` merges index segments; bounded `merge` spreads this work across
maintenance windows. FTS5 `rebuild` reconstructs the index from its content table,
useful for repair, not a mandatory cleanup timer. SQL `REINDEX` is not FTS5 rebuild.
`VACUUM` compacts database files, which is not the primary search-quality goal.
See [official FTS5 maintenance](https://www.sqlite.org/fts5.html).

No new production optimize/rebuild/purge timer is installed here. Measure actual
ticker/keyword/date/facet queries and correctness before and after controlled
cleanup; index size alone does not prove speed. Use commands supported by the
deployed SQLite version. This remains lower-priority than service and research work.

Changes to triggers, defaults, scope matching, reuse eligibility, retry rules or
reported coverage must update this document in the same change. Keep current
behavior and planned behavior visibly separate, and link source/test owners
instead of treating an old implementation diary as current policy.

Current regression owners include
[local reuse](tests/test_financial_local_reuse.py),
[same-query concurrency](tests/test_financial_reuse_concurrency.py),
[paid admission](tests/test_financial_datasets_governance.py),
[selected-source dispatch](tests/test_data_source_routing.py),
[Settings-to-runtime policy](tests/test_data_source_settings.py),
[Settings controls](apps/arkscope-web/src/settings/DataSourceRoutingSection.test.tsx),
[calendar evidence](tests/test_calendar_refresh_evidence.py),
[macro outcomes](tests/test_macro_scheduler_outcomes.py),
[scheduler behavior](tests/test_data_scheduler.py),
[news initialization](tests/test_news_bootstrap_policy.py) and
[quote freshness](tests/test_quote_freshness.py).
These offline tests do not certify live account entitlements or source coverage.
Event-aware integration additionally needs tests for missed periods, changed
event dates, staggered statement availability and the day-20/day-90 example above.
