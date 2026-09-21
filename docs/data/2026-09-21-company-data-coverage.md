# Company Research Data Coverage

Observed September 19 and 21, 2026. This is a source decision aid, not an
investment recommendation, all-company accuracy rating, subscription purchase,
or declaration that the complete company workflow has shipped.

The two questions are deliberately separate:

1. Can ArkScope acquire and use the information reliably?
2. Does that information cover the high-value research questions?

## Decision In Brief

**SA Premium is a strong primary research-information candidate under the
existing subscription.** Its useful coverage extends well beyond financial
statements: forward estimates, revisions, valuation context, peers, profitability,
ratings, dividends and qualitative research. Normal research need not begin by
reconstructing original SEC filings.

**That is not a claim of complete acquisition or product integration.** The
implemented extension/native/tool path covers selected statement-table views.
The additional pages below were read in the user's signed-in Chrome and retained
as private experiment inputs; their production adapters are still missing.
Chrome/Firefox build parity is not installed-browser acceptance. Site challenges,
login, lazy loading, view selection and pagination prevent promising unrestricted
or continuously unattended capture.

**FD is complementary, not categorically more complete or more accurate.**
The bounded paid test returned standardized statements, business segments,
earnings releases, guidance and non-GAAP items. Some enriched fields have
material period/mapping defects. Keep useful fields and source labels; do not
admit defective derivatives merely because an API is paid or responds with 200.

**A free API alternative is worth retaining in the evaluation:** Alpha Vantage
returned actual/estimated earnings and forward estimates/revisions under the
user's existing access. It overlaps part of SA without browser dependence.
No upgrade is justified by this sample alone.

## What Counts As Sufficient?

Evaluate whether the chosen inputs let a user examine business performance,
cash generation, financing risk, expectations, relative valuation and the
investment thesis. Counting every SEC tag, table cell or available year does
not measure that. Duplicate ratios are not additional independent evidence.

For a retained value, preserve provider, company, source URL, observed time,
financial/forecast period, currency/unit, original label and accounting basis.
Reported facts, provider-adjusted values, consensus forecasts, company guidance
and opinions remain different. A small rounding difference may be acceptable;
a change of sign, period, business segment or meaning is not mere rounding.

Missing information must distinguish: not applicable; not disclosed; not offered
by this source; not accessible to this account; not loaded; and not integrated
into ArkScope. Finding no adapter is not evidence that nobody can obtain it.

## High-Value Coverage

"Observed" describes the tested companies/pages/endpoints, not all securities.
SA's financial/estimate/Wall Street data uses S&P Global Market Intelligence;
its Quant grades are a separate judgment layer.
[SA source description](https://help.seekingalpha.com/basic/where-do-you-source-your-market-data-from)

| Research input | SA observations | FD observations | Other existing, unpaid access |
| --- | --- | --- | --- |
| Historical income, balance sheet and cash flow | Three annual statements for AMD/AAPL/INTC; additional Annual/Quarterly table capture verified separately | Same three issuers and FY2023-2025 retained from September 19; new AMD two-quarter response | Alpha Vantage returned all three statements for all three issuers on September 19 |
| Forward EPS/revenue and estimate revisions | AMD annual consensus, high/low, analyst counts, forward multiples; 1/3/6-month revision trends | Earnings endpoint returned historical actual/estimate comparisons, not the multi-year forward curve. No equivalent forward-consensus endpoint established | New Alpha Vantage response has annual/quarterly estimates, counts, ranges and revision history |
| Valuation and context | 19 valuation rows distinguish GAAP/non-GAAP and TTM/FWD, with sector medians and five-year averages | Existing AMD historical metric snapshot has trailing valuation/profitability/growth fields; sector-relative grades not established | Finnhub basic metrics and Alpha Vantage overview offer partial overlap, not the whole SA context |
| Peer comparison and business classification | Six named companies, 18 sections and 141 aligned comparison rows after loading | Raw inputs can support a separate comparison; equivalent vendor peer/context page not demonstrated | Finnhub peer list and recommendation trends were accessible; peer selection is still vendor judgment |
| Cash generation, leverage and profitability | Financial tables and peer sections expose cash flow, margins, debt/cash and returns | Core statements useful; earlier debt/D&A/liability discrepancies remain field-specific review items | AV/Finnhub provide overlapping inputs/ratios, with definition differences |
| Business/product/geographic drivers | Not established as a comparable structured table in the inspected SA financial views; articles/releases may discuss them | Segment endpoint returned data for all three companies. Hierarchies overlap and cannot simply be summed. AMD KPI endpoint failed period/label checks | No additional free structured segment endpoint tested |
| Management outlook and non-GAAP explanation | Research/release content may supply these; no dedicated adapter established | AMD guidance returned three items. Non-GAAP capture required two pages for 12 rows, one of which is outlook rather than a historical actual | AV earnings data offers actual/estimate comparison, not a demonstrated management-guidance replacement |
| Dividend research | AAPL scorecard exposes grades, payout/growth summary and announced-dividend dates; AMD nonpayment is not missing data | Base statement fields do not establish equivalent safety/growth grading | Basic AV/Finnhub dividend metrics overlap only part of this |
| Alpha Picks thesis, articles and comments | Existing SA content capability; the specific authors and discussion are valuable and not replaceable by financial tables | No equivalent Alpha Picks/community content established | News APIs do not provide the same article discussion |
| Intraday prices, execution inputs and personal holdings | Company research pages are not the source contract for these tasks | No new intraday/account acceptance in this comparison | Retain the separate IBKR/API workstream and actual live/delayed/account-time checks |

Thus SA appears sufficient for a broad **ordinary company-research input pack**
for the sampled large US companies. It does not establish sufficient coverage
for every bank, insurer, REIT, small cap, foreign issuer, detailed operating KPI,
intraday decision or historical point-in-time backtest. Those need their own
scope checks, not a blanket declaration that SA is complete or unusable.

## Acquisition Findings

### SA: Loaded Is Not The Same As Present

The AMD peer page initially exposed 141 row labels but only **24 rows** had six
company-value cells. Scrolling the sections into view produced **141 aligned
rows**, 846 cell positions, with the same six company headers throughout. Some
positions contain explicit missing/not-meaningful markers; 846 is not a count
of valid numerical observations.

The new bounded session also read AMD annual estimates, revisions, valuation and
AAPL dividends. No human challenge occurred during these five navigations and
one same-page loading pass. An earlier financial-capture session did encounter
a challenge that the user cleared. Neither observation identifies its cause or
proves a safe polling rate. Deliberate waits are not a page-latency benchmark.

The production extensions must therefore validate each requested section/view,
headers, company columns, units and actual cell loading. A missing value must
not be substituted for an unloaded section. Preserve per-section outcomes and
old valid observations on failure; stop on verification/login requirements.

The installed application does not gain valuation/peer/forecast tools from this
experiment. Current financial input implementation and its separate limitations
are recorded in the [input acceptance](../superpowers/evidence/2026-09-21-sa-company-data/README.md).
The existing article/detail and comment-focus reads also need channel review;
their absence from the current OAuth allowlists cannot be fixed by buying more
SA access. This audit did not recapture entire articles or comment histories.

### SA Versus Free Estimates

For AMD FY2026 and FY2027, compare EPS and revenue mean/low/high/analyst-count
fields: **16 of 16 agree within SA's displayed precision**, with exact analyst
counts. Period matching is the displayed fiscal year/end month, not a claim that
SA exposes an exact fiscal-end day. This establishes numerical agreement on a
small current sample, not independent validation, common methodology or a
guaranteed shared upstream.

SA exposes a longer forward curve in this view. Five distant years have only
one analyst; that extra horizon is not automatically more useful than near-term
consensus. Alpha Vantage returned 41 annual/quarterly estimate records, including
history, not 41 future periods. Its public free allocation is 25 requests/day.
That is useful for targeted research, not a claim that an unrestricted scheduled
universe fits the free tier.
[Estimate API](https://www.alphavantage.co/documentation/#earnings-estimates),
[free request allowance](https://www.alphavantage.co/support/)

### FD: Valuable Additions With Specific Defects

The most important new counterexamples are not harmless display rounding:

- AMD KPI results carry `period_type=quarterly` and a publication-date period,
  but all four revenue values match the release's six-month column. Data Center
  is 12,493 million instead of the quarter's 6,718 million. Another row uses
  `metric_name=gaming_revenue` for `segment=Client`. Do not admit this response
  as quarterly operating-driver data.
- AMD earnings contains two non-GAAP divergence signals comparing a 2025
  non-GAAP period with a 2026 parent period; INTC has one analogous signal.
  These derived conclusions fail period comparability. Do not use the API's
  textual signals as verified analytical conclusions.
- FD's separate AMD guidance endpoint correctly preserves the tested revenue
  range and forward period. Its non-GAAP endpoint yields useful current metrics
  after pagination, but an outlook row must remain separate from actuals.
  A successful endpoint does not validate every derivative from another one.

The source release distinguishes the periods and accounting bases directly.
This was a targeted discrepancy check, not a return to mandatory SEC parsing
for ordinary research.
[AMD release and tables](https://www.sec.gov/Archives/edgar/data/2488/000000248826000121/q22026991.htm)

FD segment responses add real explanatory inputs, but include parent/child
totals together: AMD has Client and Gaming plus Gaming, AAPL has Products plus
individual product lines, and INTC has Total Intel Products plus components.
The captured schema does not provide a clean non-overlapping hierarchy.
Missing cash-flow segment data in these responses does not mean the issuer has
no cash flow. Retain scope and avoid blind aggregation.
[Segment endpoint](https://docs.financialdatasets.ai/api/financials/all-segments)

Earlier FY2025 sampling found many useful matching core statement values and
specific debt/D&A/liability questions. This session reused that evidence rather
than rebuying it. Neither those matches nor these defects justify an all-fields
accuracy score or silently substituting another supplier's number.

## Access, Cost And Scope

- New calls: **11 FD GETs and 2 Alpha Vantage GETs**, all returned data. FD cost
  envelope was 12 requests/40 standard units; actual reserved units were 39,
  including the weighted KPI endpoints and second non-GAAP page. At advertised
  Credits pricing this is **USD0.78 estimated**, not a verified account charge.
  No auto-reload setting, subscription or production paid policy was changed.
  [FD pricing](https://www.financial-datasets.ai/pricing)
- The prior September 19 comparison already establishes accessible free
  Finnhub metrics/peers/recommendations/earnings and AV statements. Finnhub full
  financials/annual EPS estimates and Massive financials/ratios were denied.
  These results were not re-probed after no reported entitlement change. An
  inaccessible endpoint is not proof that the vendor lacks the information.
- The prior IBKR statement request failed with 430; price access was a separate
  successful test. No Gateway/account access was needed this session. Alpaca
  remains untested because the user has no account/key.
- Raw provider responses and signed-in-page content remain private, outside Git.
  Only metadata, hashes, coverage and narrowly explained findings are retained
  here. No production DB/cache writes, settings changes, automatic retries,
  purchases, SEC ingestion, extension installation, merges or pushes occurred.

The [evidence receipt](../superpowers/evidence/2026-09-21-company-coverage/README.md)
separates new observations from reused captures. Scope is AMD/AAPL/INTC, with
five additional named companies only as columns on the AMD peer page, not a
full independent company audit.

## Next Delivery Priorities

1. Finish the high-value SA research pack: existing statement capture plus
   valuation/peer context and estimates/revisions, with scope loading,
   source-separated local storage, bounded reading and both extension builds.
   Verify installed Chrome and Firefox paths, not just DOM experiments/builds.
2. Connect existing article and comment evidence to the required research
   channels. Financial API access does not replace that content or its identity.
3. Keep FD explicitly selectable for useful admitted fields and API availability;
   withhold the affected KPI/signals. Evaluate AV estimates as a targeted free
   alternative without advertising an unimplemented App connector as working.
4. Complete company selection and source inspection, then retire superseded SEC
   normal-mode surfaces/calculations after workflow acceptance. Keep existing
   citations readable. No new subscription or perfect all-SEC-field coverage is
   a prerequisite for this workflow.

This is a proposed delivery order informed by the authorized comparison, not
permission to switch the user's sources or delete data. The maintained
[acquisition policy](../../DATA_ACQUISITION_AND_UPDATES.md) and
[workflow plan](../superpowers/plans/2026-09-21-company-research-workflow.md)
remain the implementation owners.
