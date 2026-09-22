# Data Acquisition And Updates

Maintained policy and implementation map. Last reconciled with source: 2026-09-22.

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
| Company financial statements and facts | SEC EDGAR and Financial Datasets through existing financial tools; explicit SA statement-table capture and local reads | SA displayed tables are source observations, not a replacement for every old calculated metric. Massive financials remain a candidate. Detailed financials has narrower coverage than fundamental analysis. |
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
existing Chrome extension capture/auto-sync. The catalog links to its status;
capture controls remain in the extension, not a new sidecar API job. SA structured
financial tables, valuation/peers and estimates/revisions have separate
eligibility switches and share the explicit company-capture command. Finnhub entries describe required
endpoint access without presuming a paid subscription or certifying free access.

Owners: [catalog](src/data_source_catalog.py),
[metadata endpoint](src/api/routes/providers_config.py),
[Settings catalog](apps/arkscope-web/src/settings/DataSourceCatalogSection.tsx).

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
| Legacy financial analysis and detailed financials | On-demand `auto` reuses eligible local observations from selected sources; otherwise acquire in the configured order within paid admission limits. | Age-based reuse, not a latest-period check. No explicit fiscal-period/version selector on these tools. |
| Earnings supplements in detailed financials | Independently selected Finnhub history/upcoming responses, with a shorter reuse window | Not the earnings-calendar scheduler interval, and not an earnings-reaction monitor |
| SEC research: `list_sec_filings`, `get_sec_financial_facts`, `read_sec_filing` | Default `stored`; explicit `auto` / `refresh` can download and persist through identity, path and transport guards | Separate from legacy financial tools; the general permission hook is audit-only, not an interactive authorization engine |
| General news | Opt-in source schedules, Run now, or the scoped `daily_update` wrapper; source-specific incremental collection | No universal query-triggered catch-up or interval-completeness guarantee |
| SA articles / comments | Signed-in browser extension captures into local storage; research reads retained captures | Body and comment outcomes are separate. A successful body does not prove comments loaded. |
| SA company financial tables | Explicit current-tab capture, or opt-in extension financial refresh; `get_sa_company_data` reads saved observations | Per-ticker/statement/view checks, initially every 7 days; no paid fallback or claim that displayed periods are the latest publication. Requires the browser and installed extension. |
| SA valuation, peers, annual estimates/revisions | Explicit current-tab capture with bounded section scrolling; local reads of a pinned observation | DOM readiness polling is not a recurring provider refresh. No hidden pagination, automatic paid fallback or live-quote claim. |
| `compare_financial_sources` | Compare already retained SA/SEC/FD statement observations from selected sources | No acquisition or spending; compatible display-period comparisons are not exact accounting equivalence or a materiality judgment. |
| FRED and Finnhub calendars | Local reads plus explicit jobs or opt-in source schedules | A release calendar is not evidence that a financial provider has processed the release. |
| `get_current_quote` | `source=auto` tries an IBKR snapshot; `ibkr` requires that path; `local` reads stored bars | Snapshot, not streaming. Auto's local fallback is labeled historical, not live. |
| `get_portfolio_holdings` | Pages an existing local profile snapshot in one read transaction | Does not install schema, create accounts, sync IBKR or establish current account value; missing storage is unavailable, not an empty portfolio |

### Selected Financial Sources

Settings -> Data and Sync -> Data Sources and Schedules -> Financial Data Sources
controls these implemented paths, using one policy catalog:

| Dataset | Selectable sources | Runtime consumers |
| --- | --- | --- |
| `fundamentals_analysis` | SEC EDGAR, Financial Datasets | `get_fundamentals_analysis` and stored-only `compare_financial_sources` on all four existing research channels |
| `detailed_financials` | SEC EDGAR | SEC calculation component of `get_detailed_financials` and existing callers |
| `earnings_supplements` | Finnhub | History/upcoming component of `get_detailed_financials` |
| `sa_company_financials` | Seeking Alpha | `get_sa_company_data` and stored-only `compare_financial_sources` on all four research channels; explicit extension ingestion |
| `sa_company_valuation` | Seeking Alpha | Same local reader with `dataset=valuation` or `peers`; explicit ingestion |
| `sa_company_estimates` | Seeking Alpha | Same local reader with `dataset=estimates` or `revisions`; explicit ingestion |

The ordered selection is an eligible set, not a command to fetch all sources.
Automatic fundamental analysis first tries acceptable local observations in that
order, then permitted acquisitions. Thus an eligible second source's complete
local result may avoid a first source's network request. A missing or partial
result remains visible as acquisition gaps; values from different providers are
not silently combined to fill a financial statement.

If no complete local result is available but selected FD statements are partly
retained, `stored` returns that partial result. `auto` keeps that provider and
attempts only its missing statements within the budget. It does not restart the
statement set at another provider or repurchase the already eligible statements.

`get_fundamentals_analysis(source="sec_edgar"|"financial_datasets")` selects one
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
- Source values, labels, currency, unit note/scale, observation/content identity
  and acquisition metadata remain separate. New SEC/FD statement projections
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
old SEC/FD caches may overwrite previous responses. Budget reducers preserve the
whole comparison or return a smaller-page request, never clipped numeric JSON.

Owners: [comparison reader](src/tools/financial_comparison_tools.py),
[comparison rules](src/fundamentals/source_comparison.py),
[regression cases](tests/test_financial_source_comparison.py).

### Retained Articles, Comments And Holdings

These are local research reads, admitted to both native API adapters and both
internal OAuth research adapters. They are not a new external MCP service or
permission to acquire data. The registry remains 58 tools; each OAuth research
allowlist now admits 22. `get_sa_feed` supplies article IDs; the relevant
research/summarizer subagents can follow them to `get_sa_article_detail` and
`get_sa_comment_focus`. Holdings are the user's local account positions, not the
Alpha Picks recommendation membership.

**Acquisition and time.** Reading does not start an extension, reload a page,
extract comment signals, poll a provider, call IBKR, update configuration or
spend. Article body/comment capture times are distinct, and holdings retain
their stored per-position synchronization times. Neither a read time nor a
summary-generation time is a fresh market observation. Update remains an
explicit extension/sync operation with its existing requirements. A missing or
incompatible store is unavailable; it is not silently created or migrated.

**Article pages.** Defaults are 4,000 Markdown characters and two comments,
with 500 characters per comment. These are page defaults, not retention or
total-content caps. `body_limit=0` or `comment_limit=0` omits that section. Follow
`next_body_offset` / `next_comment_offset`; a long comment uses `comment_id` plus
its `next_text_offset`. Text offsets count Unicode code points. Comments are a
flat list with original parent IDs, not a claimed complete nested tree. Parents
outside the page can be read by ID; missing retained parents are flagged.

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
introduced here. Existing complete UI/native-host readers remain unchanged.

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

### SA Financial Refresh Scheduling

**State:** the shared Chrome/Firefox implementation is opt-in and off by default.
Signed-in installed-extension acceptance is a separate gate; building the Firefox
artifact does not establish live SA loading reliability. No production schedule
is enabled by a code upgrade.

In the extension's **Financial statement updates**, choose selected tickers or
**App watchlist**, statements
(income, balance sheet, cash flow), Annual/Quarterly views and an interval of
1-365 days (initially 7). Scheduled scopes use **USD / Absolute** tables.
The interval is a repeat-check policy, not a claim that financial publications
expire after seven days. **Update now** explicitly requests a new capture even
inside the interval, but cannot override a rate-limit cooldown. Valuation,
estimates, news and Alpha Picks do not inherit
this schedule or interval. App watchlist targets come from the same complete,
read-only active-universe authority as the App, not a manually copied list.
The preview includes membership sources, stale-source warnings and unsupported
symbols. Unmapped provider symbols are not guessed or counted as captured.
Retained former Alpha Picks remain targets when still members of the App list.
Each acquisition rechecks membership; unavailable source databases stop work
instead of falling back to a partial list. There is no 183-ticker hard limit.

**One collector, both browser builds.** Click **Use this browser** explicitly
in the chosen browser installation. Initial operator rollout uses Firefox;
Chrome already contains the same implementation. Opening either browser,
reading status or saving a schedule does not select it. The selection applies
to an installation UUID, not every profile bearing the same browser name.
Both native hosts must point at the same SA database to share this authority.
Another installation can read saved data and status but cannot navigate financial
acquisition pages. Switching requires an explicit selection while no capture is
active. The previous browser's local schedule is not copied or automatically
enabled in the new browser.

`sa_company_refresh.db`, beside the selected `sa_capture.db`, owns selection,
active reservation, shared financial cooldown, challenge pause and admission
failures. Native-host processes serialize mutations with SQLite transactions.
An active reservation cannot be stolen or expire into competing work. If a
browser crashes or an acknowledgement/cleanup is uncertain, stop that collector
and its acquisition tabs, then explicitly **Recover stopped capture**. Recovery
is logged and revokes the old reservation; it does not select another browser
or forgive cooldown/challenge state. Do not confirm recovery while the old
collector is still running. Missing/corrupt control state never grants admission.
Status/watchlist reads do not install a database or construct a writable DAL.

Each ticker/statement/view has its own last-success time, observation ID, attempt,
failure and next eligibility time. Reading data or saving unchanged settings does
not move the deadline. Only an accepted capture does; unchanged content advances
the successful check without duplicating observations. Matching manual current-page
captures can satisfy a scheduled USD scope. Failure preserves old data and the last
success. Retry starts at six hours and backs off to seven days, not a new freshness
window. Verification, login/access and recognized structural/identity failures
pause the batch until explicit manual retry after correction.

The existing extension queue serializes work. Repeated refresh requests join the
pending batch. A queued automatic scope is checked again before navigation and
capture; a newly successful matching capture or removed/disabled scope prevents
unnecessary acquisition. Each alarm handles at most one overdue scope, with at
least one minute between overdue alarm runs. All financial page starts also have
a shared one-minute minimum gap. Small manual batches remain sequential; when
admission asks them to wait, remaining scopes persist for a later alarm. A manual
App-watchlist update immediately queues all selected scopes and processes one per
alarm, even if the periodic **Scheduled** toggle is off. **Cancel queued update**
clears that one-time queue; uncheck **Scheduled** separately to stop periodic work.
The popup reports the remaining scope count. Closing the popup does not discard
the queue; restarting the background restores it. A browser crash during an active
reservation requires the explicit recovery above. Source/host admission failures
are visible and delayed instead of becoming silent one-minute retry loops.

Admission reads the saved SA observation's capture timestamp before scheduled
navigation. Switching browsers does not turn a recent successful capture into
"never captured", and reusing it does not advance its deadline. A success receipt
must match a persisted observation captured during that reservation; a fabricated
or older receipt cannot certify success. Manual saves from an already open page
remain distinct from navigated acquisition and do not reset acquisition cooldown.

A recognized visible rate-limit error (a page title or visible heading containing
`Too many requests` or `Rate limit exceeded`) stops the financial batch. A shared
financial-refresh cooldown survives reloads, settings changes and ticker changes;
neither an alarm nor **Update now** can bypass it. Consecutive rate-limit responses
back off from six hours, doubling to a maximum seven days. A successful new
acquisition resets that counter; saving an already loaded page does not clear the
acquisition cooldown. Old observations and successful timestamps are retained.
The popup shows the cooldown deadline, and automatic alarms respect it.
Restrictions are persisted before tab cleanup or pacing, not only when the batch
returns. Verification challenges take priority over simultaneous rate-limit
messages: a timer expiring must not resume an unresolved human-verification gate.

These are local safety policies, not published SA request allowances. Visible-page
detection is not a complete HTTP 429 / `Retry-After` monitor. Financial cooldowns
are now shared across Chrome/Firefox installations using the same local SA store;
they do not govern Alpha Picks/news, manually opened pages, other hosts or the
entire site's subrequests. One page can make several provider requests, so this
is not a guaranteed account/IP request rate. Before bulk rollout, verify bounded
real-site behavior. No production/all-watchlist schedule is enabled by this change.

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
financial refresh deadline. Detailed financials cannot use FD as a replacement
until its own adapter is implemented. SA company tables do not silently feed the
legacy ratio calculators; those remain separate consumers. Massive financials
remain unavailable rather than presented as working merely because a key or
subscription exists. No external MCP server or subscription upgrade is implied.

Owners: [source policy](src/data_source_routing.py),
[Settings API](src/api/routes/providers_config.py),
[Settings controls](apps/arkscope-web/src/settings/DataSourceRoutingSection.tsx).
GET `/providers/data-routes` and PUT `/providers/data-routes/{dataset}` inspect
or save policy only; neither contacts a data provider.

### Financial Read Controls

`get_fundamentals_analysis` and `get_detailed_financials` accept `freshness` and
optional `max_age_seconds`:

| Mode | Behavior |
| --- | --- |
| `auto` (default) | Reuse a valid matching observation inside the selected window. Acquire only when needed and permitted. |
| `stored` | No provider acquisition or cache write. With no age bound, an older valid observation may be returned; a missing eligible observation is reported as a gap. |
| `refresh` | Bypass observations predating this request. An identical successful acquisition already in flight may satisfy it. Failure is not silently replaced by an older success. |

`max_age_seconds` must be a nonnegative integer, not a boolean or string. It
overrides the automatic defaults and can constrain `stored`; combining it with
`refresh` is rejected rather than silently ignored. These are tool controls,
not a claim that every Settings screen exposes them.

Current default authority is
[`config/user_profile.yaml`](config/user_profile.yaml), under
`data_preferences.fundamentals_sources`:

- `refresh_days`: **7 days** for financial observations.
- `earnings_refresh_seconds`: **3600 seconds** for detailed-financials earnings
  history/upcoming observations, unless an explicit age overrides it.

These are configurable fallbacks, not the final event-aware policy. A local read
does not restart the acquisition-age clock; a fresh provider response currently
does. Legacy `ttl_days` / `cache_days_*` storage metadata does not decide read
eligibility in this path. Merely choosing annual or quarterly data does not make
the response permanently valid: restatements and provider corrections can change
a period. Reopening an exact retained version and asking for the latest version
are different requests.

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
