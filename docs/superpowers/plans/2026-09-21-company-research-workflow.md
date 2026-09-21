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

## Reconciled Facts

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
   through the already-authorized signed-in browser/extension approach. Start
   with a supported financial statement and valuation scope, verified against
   observed pages, rather than advertising all company tabs as implemented.
   Retain ticker, provider, page URL, capture time, period, units/currency, table
   headers and completeness. Missing/locked/not-loaded sections remain typed
   gaps. No anti-bot bypass or unsupported assumptions about Premium access.
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
- [ ] Signed-in page observations and extraction fixtures for the bounded SA scope.
- [ ] Capture, persistence, source selection and research reads work together.
- [ ] Normal research requires no CIK and no compulsory original-filing workflow.
- [ ] Required reads work across their admitted channels, including honest gaps.
- [ ] Redundant paths are removed only after replacement and reference checks.
- [ ] Final frozen revision passes full backend/frontend regression and build.
- [ ] Real-source workflow acceptance, including restart and retained provenance.

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
