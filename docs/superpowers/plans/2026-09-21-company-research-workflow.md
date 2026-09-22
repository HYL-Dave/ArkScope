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

Current state: [Progress At Each Handoff](#progress-at-each-handoff).
Latest accepted slice: [retained article, comment and holdings reads](../evidence/2026-09-22-retained-research-reads/README.md).

## Reconciled Pre-Implementation Baseline (September 21)

- The then-current SEC Settings panel required a numeric CIK. The existing issuer
  resolver supports exact ticker lookup, not company-name search; absent maps
  and ambiguous matches must be handled rather than asking users to know IDs.
- FD is already explicitly selectable through financial routing, including as
  the sole source. Describing it as permanently SEC-only fallback is outdated.
- SA has Chrome alarm-driven Alpha Picks and market-news acquisition. It is
  browser-dependent, not inherently manual/passive and not a headless service.
- SA structured financial/rating capture was not implemented. Listing it in the
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
   Cross-source acceptance must compare retained observations for a common
   ticker/period with labels, scale, currency and date precision side by side.
   Explain only evidenced differences; an unknown accounting/revision cause
   remains unknown, not an invented reconciliation. The archived SEC
   `compare_reports()` is a same-basis report comparator, not a current reusable
   SA/SEC/FD component. Do not restore its archived report engine for this task.
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
   Exercise populated legacy caches as well as cold requests. A repaired formula
   must be recomputed from retained inputs or explicitly withheld, never bypassed
   by a cached legacy derived result. This must not implicitly trigger paid
   acquisition merely to replace an old calculation.
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

## Progress At Each Handoff

Report newly testable results, partial implementations and their limits, pending
work, and operator-only gates at every handoff. Do not replace this with only a
test count or an assertion that the whole company workflow is complete.

| Package | Current implementation | Remaining work |
| --- | --- | --- |
| 1. Company inputs | Shared Chrome/Firefox code for three statement types and the bounded valuation/peers/annual-estimates/revisions scope; real Chrome captures retained | Installed, signed-in extension-to-host acceptance on both browsers; other pages/views are not advertised as captured |
| 2. Research access | SA source switches, stored/pinned company reader and qualified SA/SEC/FD comparisons; article/comment/holdings read-only paging and four-channel admission verified at `e0bce862`, including full regression and real retained-data replay | Full end-to-end operator research acceptance and explicit production comment-signal backlog processing |
| 3. Optional SEC | Stock-symbol resolution, explicit directory update, collapsed technical administration; existing citations preserved | Remaining normal-mode surface/consumer review, not wholesale SEC retirement |
| 4. Analytics | Comparison excludes the legacy ratios and does not endorse them | D/E, comparable financial periods, earnings-event dates and complete trading-session windows |
| 5. Retirement | No premature deletion of replacement-dependent capabilities or retained evidence | Remove superseded paths and consumers only after replacement acceptance; retention/inventory decisions remain separate |

The September 22 comparison/entry implementation at `e4d58842` passed its
integrated acceptance: **12,225 backend / 12 unchanged skips**, **1,920 frontend /
126 files**, typecheck/build, i18n, eight desktop checks and twelve isolated
browser layouts. Retained AAPL balance/INTC cash-flow responses also pass the
four-channel comparison replay, without new acquisition or spending. See the
[scope and limits](../evidence/2026-09-22-source-workflow/README.md). This does not
close the remaining workflow gates. The two archived research branches remain
archived, and master/production settings are not changed by this work.

The September 22 retained-reader batch at `e0bce862` passed integrated acceptance:
**12,306 backend / 12 unchanged skips**, **934 related backend**, **1,920 frontend /
126 files**, typecheck/build, i18n and eight desktop checks. The first full run
caught an old OAuth count assertion; expanding its exact roster also required
classifying that test reference in the existing consumer census. Both guards
remain enforced, and the final frozen full run has no failure. See the
[verification record](../evidence/2026-09-22-retained-research-reads/README.md).

Retained article/body/comment/holdings reads are bounded, source-aware and
admitted to all four transports. The article reader is now separate from the
unpaged UI/native host read, and holdings use a single read-only transaction
without constructing the schema-initializing store. Long comments can be fully continued; parents and
capture gaps stay visible. Both readers reject changed content between pages,
without claiming immutable historical archives. Holdings totals also qualify
valuation gaps and withhold mixed/unknown broker-base currencies. These changes
are documented in the root acquisition policy, not only this execution log.

The next product package is legacy ratio/event repair, followed by
replacement-dependent retirement. Cross-provider comparisons are
not blockers merely because numbers differ: field/unit/period correctness is a
separate obligation from the research significance of a qualified difference.
Installed Chrome/Firefox operator acceptance remains open; this read-only batch
does not silently certify the extension's live capture workflow.

Retained-copy acceptance covered three real article bodies, first/last comment
pages, a fully reassembled 51,727-character comment and ten real holdings across
all four transports, plus fresh-process reopening. This replay opened production
databases only as read-only SQLite backup sources; tool calls used private copies
and socket connections were blocked. No model/provider request was made.
The disposable copy also verified the existing explicit extraction job: 7,523
pending comment signals were processed and all four focus readers returned 979
qualifying comments in the latest replay's moving 90-day window (01:40 UTC).
Production backlog processing is still pending; a read never starts that job
itself. Copies were removed.

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
- [x] Required reads work across their admitted internal channels, including
      honest gaps; real model/operator acceptance remains separate below.
- [ ] Redundant paths are removed only after replacement and reference checks.
- [ ] Workflow-final revision, after all packages, passes full backend/frontend
      regression and build. The retained-reader slice has passed at `e0bce862`.
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
- [x] Frozen `692b4311` regression: 12,178 backend passes / 12 unchanged skips;
      1,911 frontend passes / 126 files; typecheck/build, 34 browser layouts and
      8 desktop checks pass. Real snapshots also reopen all 41 tables / 2,026
      cells through 160 paged reads. See the
      [acceptance record](../evidence/2026-09-22-sa-company-research/README.md).
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
