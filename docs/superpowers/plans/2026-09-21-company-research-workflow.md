# Company Research Source Workflow

## Delivery Unit

Deliver one usable path: select a company, choose eligible sources, reuse or
acquire appropriate observations, conduct research, then inspect the cited
source. A catalog, a CIK input repair or another isolated cache change is not
the product acceptance unit. Small internal commits remain useful for review
and rollback; they do not require a separate user acceptance cycle each time.

This is the execution baseline following the September 21 scope feedback,
not a claim that the workflow below is already implemented. No subscription,
production setting change, data purge or removal of retained evidence is
authorized by this plan.

## Reconciled Baseline Facts

- The current SEC Settings panel requires a numeric CIK. The existing issuer
  resolver supports exact ticker lookup, not company-name search; absent maps
  and ambiguous matches must be handled rather than asking users to know IDs.
- FD is already explicitly selectable through financial routing, including as
  the sole source. Describing it as permanently SEC-only fallback is outdated.
- SA has Chrome alarm-driven Alpha Picks and market-news acquisition. It is
  browser-dependent, not inherently manual/passive and not a headless service.
- SA structured financial/rating capture is not implemented. Listing it in the
  catalog does not make it a replacement for an existing financial adapter.
- Registry presence does not prove channel exposure. Both current subscription
  allowlists omit direct SA article detail, comment focus and holdings tools.
- Earnings-impact analysis is a retained user requirement, not replaced by SEC
  financial statements. Its event/window semantics still need repair.

Owners: [issuer parsing](../../../src/sec_research/issuers.py),
[issuer resolution](../../../src/sec_research/issuer_store.py),
[SEC Settings](../../../apps/arkscope-web/src/settings/SecResearchPanel.tsx),
[source routing](../../../src/data_source_routing.py),
[SA extension](../../../extensions/sa_alpha_picks/background.js),
[Claude subscription](../../../src/auth_drivers/claude_code_sdk_driver.py),
[ChatGPT subscription](../../../src/auth_drivers/chatgpt_oauth_driver.py),
[historical usage limits](../../data/2026-09-20-research-usage.md).

## Cohesive Work Packages

1. **Usable company-data input.** Prioritize a bounded SA company-data capture
   through the already-authorized signed-in browser/extension approach.
   Financial statements and valuation/ratings are separate acceptance tracks;
   success of either does not certify the other. Verify against observed pages
   rather than advertising all company tabs as implemented.
   Retain ticker, provider, page URL, capture time, period, units/currency, table
   headers and completeness. Missing/locked/not-loaded sections remain typed
   gaps. No anti-bot bypass or unsupported assumptions about Premium access.
   FD's existing selected-source path is an independent financial alternative,
   not an automatic paid fallback on SA failure. Replacement decisions use the
   coverage of the selected, admitted providers; they do not wait indefinitely
   for SA, and they do not imply that FD supplies ratings or every old metric.
2. **Capture to actual research.** Connect successful observations to local
   persistence, query tools and per-dataset source selection in the same batch.
   Propagate selected-source provenance through applicable native and OAuth
   channels. Keep providers separate; unavailable selected sources must not
   silently cause paid acquisition or a switch to SEC parsing. Audit the SA
   body/comment/holdings reads needed by this workflow instead of trusting the
   tool count. Do not expose all registry entries as supposedly read-only.
3. **SEC as optional verification.** Remove the raw CIK requirement and technical
   SEC browsing/administration from the normal company-research path. Any
   retained original-filing entry uses a familiar ticker/company choice, with
   explicit handling of missing mapping and ambiguity. Keep original-source
   links and reopening of already retained citations. Provider fundamentals,
   filing downloads, capture maintenance and security-identity uses are distinct
   layers; do not disable them all merely because they use SEC.
4. **Retained analytical behavior.** Do not publish old ratios or event reactions
   under unjustified labels. Repair or explicitly withhold the affected outputs
   as their consumers are connected: debt versus total liabilities, comparable
   fiscal periods, actual release dates versus fiscal period end, and complete
   trading-session windows. Preserve earnings-reaction capability; do not adopt
   the archived SEC-report implementation as an automatic replacement.
5. **Retire superseded paths together.** After replacement coverage is demonstrated,
   remove redundant normal-mode SEC surfaces and superseded legacy calculation
   paths with their callers, schemas, channel declarations, copy and tests.
   Keeping citations readable is independent of new acquisition. Data deletion
   requires a separate reference/retention decision; green absence tests alone
   do not prove that removing a capability is safe.

These packages form one user-facing workflow. Cross-platform, Python sandbox,
SQLite replacement, external MCP hosting, a new notes product and a separate
usage-monitoring product are not prerequisites and do not join this batch.
Existing card translation and account-usage display are not retirement targets.

## SA Quality And Operating Boundary

The extension owns page extraction, the native host validates the input before
the capture store accepts it, and the research tool owns bounded local reads.
Both sides use a versioned semantic layout contract: company identity, selected
view, currency/unit context, column roles and row-to-column alignment. Record a
structural fingerprint with observations, but do not treat a hash as proof of
numerical truth or hash cosmetic classes/advertisements. An unknown semantic
shape fails closed; do not silently accept it as a new baseline. Existing valid
captures survive a rejected update. Fixtures must mutate plausible-but-wrong
layouts, not only remove the entire table.

Retain displayed values alongside deterministic decimal cleaning. Missing,
not-meaningful, not-applicable and zero are different. Do not infer an exact
period-end day from a month label, mix TTM with annual values, relabel liabilities
as debt, or invent normalized currency amounts from an ambiguous unit context.
Layout recognition and financial coverage are distinct acceptance results.

SA is an optional browser-assisted input, not the mandatory primary source for
all company data. The initial company-page capture is explicit; reading it does
not launch Chrome, subscribe, synchronize or spend. Existing SA alarms still
need Chrome/login/page availability. A headless unattended workflow must use
eligible API sources or report the browser dependency, not claim equivalent
availability. Unattended service lifetime remains an open workstream.

No duplicate full-page archives, automatic company-page schedule or unlimited
retry history is introduced merely to test extraction. New observation storage
must deduplicate unchanged content and report storage limits before ingestion
expands. Existing data/backup retention needs its own inventory and approval;
neither quoted directory sizes nor old timestamps authorize deletion. A blocked
integration remains explicitly unavailable in the catalog until a deliberate
retirement decision, rather than being hidden as though the data were unwanted.

## Freshness By Use

- Financial observations: keep period/version and provider processing separate
  from capture time. Reuse suitable retained observations; explicit refresh is
  available. Event-aware checks need trustworthy coverage, not an arbitrary
  future calendar entry or a new quarter-long timer on every request.
- News: opt-in periodic collection and explicit catch-up; scope and partial
  body/comment results matter. Reading freshness is not a 90-day deletion rule.
- SA material: reads use captured observations; browser-triggered acquisition
  reports its actual prerequisites and separate body/comment outcomes.
- Quotes and current account value: use an appropriate live request when that
  is the task, with feed/time qualification. A stored holdings read is not sync.

The existing category map remains an inventory, not eleven mandatory user
questions or one fixed freshness setting for every use of each category.

## Acceptance And External Gates

- [x] Reconcile the reported CIK issue, existing routing and SA alarm ownership.
- [x] Signed-in page observations and extraction fixtures for the bounded SA scope.
- [x] Semantic-layout mutations fail without replacing accepted observations.
- [x] Financial and valuation acceptance are recorded independently; selected FD
      remains usable without SA and without an implicit paid retry.
- [x] Capture, persistence, source selection and research reads work together for
      the new SA financial-table reader. Other legacy analytic consumers remain.
- [ ] Normal research requires no CIK and no compulsory original-filing workflow.
- [ ] Required reads work across their admitted channels, including honest gaps.
- [ ] Redundant paths are removed only after replacement and reference checks.
- [ ] Final frozen revision passes full backend/frontend regression and build.
- [ ] Real-source workflow acceptance, including restart and retained provenance.

### Financial Table Implementation Status

The first integrated implementation adds the extension command, semantic
validation, bounded/deduplicated SA-store persistence, independent Settings
selection and a local-only reader on the two API-key and two OAuth channels.
It does not depend on a new subscription, an external MCP server, a headless
browser or replacing SEC first. The three statement types are supported in
Annual/Quarterly Absolute views. Standalone TTM views are not accepted; the
distinct TTM column in an annual income/cash-flow table is preserved as trailing,
not relabeled as annual. At that revision, growth and valuation/rating pages
were not implemented; the research-table expansion is recorded below.

Live page acceptance covered AMD's three annual statements and quarterly
income/balance views, AAPL's annual balance sheet and INTC's annual cash flow.
A site verification challenge interrupted broader navigation; requests stopped,
the operator completed verification, and remaining checks resumed individually.
Its cause is not established. Four captured real tables also passed Native
Messaging framing/process persistence and 16 local tool calls across the four
channels, without opening a market DB or calling a model/provider API.

The input implementation at `e99e417f` passes a single complete backend run:
12,086 passed / 12 unchanged skips. Complete frontend is 1,909 passed / 126 files;
typecheck/build, i18n, eight desktop checks and thirteen isolated browser layouts
pass. Product/test/config files remain unchanged through full acceptance.
Evidence: [SA company input](../evidence/2026-09-21-sa-company-data/README.md).

This is input-path acceptance, not completion of all five workflow packages.
Installing/reloading the new extension for an operator session, broader source
coverage, company selection/CIK removal, legacy calculation retirement and
required article/comment/holdings channel review still need their own evidence.
Existing backups/news retention is not changed by this slice. The maintained
root policy documents the capture trigger, clocks, storage cap and failure path.

### Source Coverage Evaluation

The user's follow-up separates acquisition feasibility from high-value research
sufficiency. The [September21 comparison](../../data/2026-09-21-company-data-coverage.md)
supports prioritizing SA valuation/peers and estimates/revisions alongside the
existing financial input, not requiring a copy of every original filing field.
It is experiment evidence, not shipped adapters or unrestricted SA capture.

FD's explicit selected-source financial path remains useful, but the newly
tested KPI/derived-signal defects prevent treating all of its enriched endpoints
as an admitted replacement. AV's existing unpaid access returned useful forward
estimates, worth evaluating without buying a subscription; no AV App connector
was added. Keep acquisition, cleaning, source-separated storage, readable
outputs and installed Chrome/Firefox acceptance in the same workflow package.
Do not silently spend on FD or switch sources after an SA loading failure.

### Research Table Expansion Status

The September 22 expansion connects valuation measures, all 18 recognized peer
tables, annual EPS/revenue estimates and annual revisions through the shared
Chrome/Firefox capture command, existing SA observation store, independent source
switches and the same four-channel local reader. It is company-data workflow
coverage, not a claim that every SA tab/chart or the five packages are complete.

- [x] Recognized current-page sections are scrolled and checked before admission;
      labels-only loading, unknown pagination, navigation and operator input stop
      the attempt. No auto-retry, navigation or paid fallback is introduced.
- [x] Source selection is checked before potential browser acquisition and again
      at persistence; financials, valuation/peers and forecasts have separate routes.
- [x] Values retain display scale, missingness and forecast/grade/peer-selection
      semantics. Native validation, immutable storage and four-channel section
      pagination have focused regression coverage.
- [x] Real Chrome captures: AMD valuation, peers, estimates and revisions; AAPL
      peers. An observed `Semiannual` spelling was added with a regression case.
- [x] Firefox dependency build includes the same extractor. Installed, logged-in
      Firefox is still an external acceptance gate, not inferred from build parity.
- [ ] Frozen revision complete regression and saved evidence.
- [ ] Operator extension reload and actual popup-to-host capture in each browser.

These inputs do not yet replace the legacy ratio/event calculators. Remaining
workflow work is the normal company/SEC entrypoint, article/comment/holdings
channel review, period/debt/event semantics, and retirement of superseded callers
after replacement evidence. Those items are not silently closed by this input
expansion. No production data, subscriptions or schedules are changed.

Use focused tests during implementation, then one complete regression on the
final integrated revision. A changed product revision invalidates affected
results; do not waive security, citation or cancellation checks to increase pace.
Do not run overlapping pytest sessions or edit a tree during its full suite.

Ask the user when a real external prerequisite is reached: authenticated Chrome,
human verification, an unapproved paid endpoint/subscription, or destructive
production work. A single endpoint success establishes only its tested scope,
not the account's entire plan or durable entitlement. Lack of an integration is
not evidence that the requested capability should be retired.

Durable policy: [Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md).
