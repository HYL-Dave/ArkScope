# Trusted Lifecycle Automation Stage 5 Admission Repair Plan

> **Execution:** Use test-driven development in the existing isolated worktree.
> Do not merge or push. Provider calls and every production database operation
> remain hard stops.

**Goal:** Repair four independently reproduced paths that made the first Stage 5
shadow compatible with an always-rejecting system, then rebuild offline admission
before requesting real SEC/IBKR validation.

**Authority:**
`docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`
section 16.

## Constraints

- Base is exact clean tip `e1f7a394ca95926ebf93caa58d455f8a2c65174d`.
- The packet under
  `docs/superpowers/evidence/2026-08-25-trusted-lifecycle-automation-stage-5/`
  is retained but rejected as migration authority.
- No provider/network call, production DB read/write/preflight/backup/migration,
  app cutover, merge, or push.
- No inferred legal date. Explicit source dates only.
- No candidate ticker is persisted as an alias before transition application.
- No policy-side scalar-to-mapping compatibility shim.
- No synthetic M&A regex may claim counterparty or consideration extraction.
- Every changed non-governance path must appear in the owned ledger.

## Mechanical Authorities

- Owned paths:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-repair-owned-paths.tsv`
- Focused paths:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-repair-focused-paths.tsv`
- Additions:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-repair-additions.nodes`
- Evolved owners:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-repair-evolved-owners.tsv`

## Task 0: Freeze The Rejected Authority

- [ ] Record the four reproduced defects and reject the original Stage 5 packet
  for migration/cutover authority without deleting its evidence.
- [ ] Verify every ownership pin against the exact base.

## Task 1: Exact RED

- [ ] Prove an explicit `LC -> HAPN` declaration emits HAPN when the alias set
  contains only LC.
- [ ] Prove only a completely fetched explicit-dated Form 25 chain emits a
  policy-usable terminal delisting.
- [ ] Prove a regulator-declared successor is queried through IBKR without first
  appearing in persistent aliases.
- [ ] Prove scalar `transaction_structure` and mapping-valued scalar facts are
  rejected at the fact boundary; evolve BLBD/M&A owners to the reviewed mapping.
- [ ] Evolve approval-drift ownership to require accepted assessment retention,
  `waiting_transition_revalidation`, a visible typed blocker, and one-day retry.

## Task 2: Fact And Source Repair

- [ ] Add one closed fact-shape normalizer used by emitters and persistence.
- [ ] Emit structured transaction kind plus honest `terms_status`; preserve every
  injected complete M&A term in assessment prefill.
- [ ] Admit one-known-side explicit symbol declarations while keeping the new
  side candidate-only.
- [ ] Fetch the selected SEC chain before excerpt construction so every locator
  gets a truthful chain-completeness witness.
- [ ] Emit terminal facts only from explicit Form 25/25-NSE text with tracked
  alias, security class, and date support.
- [ ] Include cited successor candidates in bounded IBKR lookup only.

## Task 3: Approval Revalidation And UI Truth

- [ ] Add the closed readiness and blocker values to schema/API/presentation.
- [ ] Add one atomic kernel operation that replaces `transition_eligible` with
  waiting revalidation and writes the typed blocker.
- [ ] Recheck at most once per day, preserve the accepted assessment/proposals,
  and clear the blocker only when the run is reserved again.
- [ ] Render the reason in English and Traditional Chinese through exhaustive
  mappings; no fallback may map it to another known state.

## Task 4: Offline Readmission

- [ ] Run exact additions and focused suites, then collection twice and full
  backend twice with isolated basetemp roots.
- [ ] Run frontend full, typecheck, literal scanner, production build, and the
  bilingual browser matrix with all network/write requests denied.
- [ ] Rebuild the Stage 5 packet at the repaired product/test authority and mark
  real SEC source bytes plus read-only IBKR shape as separately unauthorized.
- [ ] Stop for independent review before any hard stop.

## Post-Repair Authorization Boundary

After offline GREEN, request one explicit authorization covering only four SEC
documents and one read-only IBKR shape canary. Do not combine it with production
migration or cutover authority.
