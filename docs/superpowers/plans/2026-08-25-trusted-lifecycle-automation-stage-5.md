# Trusted Lifecycle Automation Stage 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans`, `superpowers:test-driven-development`, and
> `superpowers:verification-before-completion`. Execute in the existing
> isolated worktree; do not merge or push.

**Goal:** Close grounded offline admission for trusted lifecycle automation:
bind four reviewed historical case identities to the real parser/IBKR/policy
interfaces, repair only cross-stage shape loss exposed by that replay, verify
the final bilingual UI with fixture-only browsers, and prepare a separately
authorized live-migration packet without opening production data.

**Architecture:** Stage 5 adds no runtime capability, route, tool, schema,
provider, or model behavior. Historical case identity is grounded by the
reviewed repository snapshot of real CIK/accession/URL rows. Filing prose and
IBKR replies remain synthetic source-shape fixtures because provider calls are
not authorized. The report must keep those two evidence strengths separate:
it proves integration against reviewed facts and parser-shaped inputs, not a
fresh source-byte replay or broad A-to-B precision. T4A closes one discovered
presentation gap by labeling known closed fact values instead of exposing
their storage codes.

**Tech Stack:** Python 3.10, stdlib `sqlite3`, existing SEC/IBKR lifecycle
adapters, pytest, React 18, TypeScript, Vite, Playwright.

**Spec:**
`docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`

## Global Constraints

- Stage 5 base is exactly `beca52e7`; product/test authority inherited from
  Stage 4 is `b8c01499bfa90d11bc34288b2748f1a678ef20b0`.
- Backend baseline collection is `4405` (`4393 passed / 12 skipped`). This
  stage adds exactly six nodes and removes none, for target collection `4411`
  and full execution `4399 passed / 12 skipped`.
- Backend focused baseline is `32`; the six additions produce target `38`.
- Frontend remains exactly `105` files and grows from `1227` to `1228` tests.
  Routes remain `187`, lifecycle routes `17`, and registry/bridge inventories
  remain `50 / 51 / 51`.
- No schema, migration, assessment-authority, transition-state, route, or tool
  byte may change. The T4A amendment owns only the reviewed closed fact-value
  labels and their presentation call site.
- The Stage 2 parser fixture remains explicitly synthetic. A report may call
  the case identities grounded only because their CIK/accession/URL tuples are
  mechanically bound to `security_lifecycle_legacy_37.json` and the reviewed
  design authority. It may not call the source text live, captured, verbatim,
  or freshly verified.
- No provider/network call, production database operation (including read-only
  preflight), app restart/cutover, merge, or push is authorized.
- Stop and amend before any new closed value, unlisted changed path,
  unexpected node/count drift, schema/UI change, or hard-stop crossing.

## Mechanical Authorities

- Owned paths:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-owned-paths.tsv`
- Focused paths:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-focused-paths.tsv`
- Additions:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-additions.nodes`
- Frontend addition:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-frontend-additions.tests`
- Evolved owners:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-evolved-owners.tsv`
- Protected paths:
  `docs/superpowers/plans/2026-08-25-trusted-lifecycle-automation-stage-5-protected.paths`

Every changed non-governance path must already appear in the owned ledger.
Evidence artifacts and this plan's ledgers are governance paths. An unexpected
product owner is a stop, not a full-suite repair.

## Task 0: Baseline And Plan Admission

- [x] Verify a clean, linear, unpublished branch at the plan-authority tip and
  prove `beca52e7` is its ancestor.
- [x] Verify every modify pin and absent add path in the owned ledger.
- [x] Collect focused baseline `32`, collection `4405` twice, frontend
  `105/1227`, route/tool inventories, and protected bytes.
- [x] Record that the local `origin/master` observation is not refreshed over
  the network; no fetch/ls-remote is permitted by this stage.

## Task 1: Add The Four-Case Shadow Authority RED

**Files:**
- Add: `tests/fixtures/security_lifecycle_grounded_shadow.json`
- Add: `tests/test_security_lifecycle_grounded_shadow.py`
- Modify: `tests/test_security_lifecycle_automation_scheduler.py`

- [x] Add one manifest node and one node for each HAPN, QBTS, CCL, and BLBD,
  plus one scheduler identity-context node: exactly six additions.
- [x] The manifest node proves each real case CIK/accession/URL tuple exists in
  the reviewed 37-row repository snapshot and declares historical A-to-B
  coverage `n=1`, source prose synthetic, IBKR reply synthetic, network calls
  zero, and transition execution coverage delegated to the Stage 4 scratch
  replay.
- [x] Each case node passes source-shaped SEC input through the real extractor,
  synthetic market snapshots through the real IBKR adapter where applicable,
  and both outputs through the real decision policy. No test may restate the
  policy result without calling those interfaces.
- [x] Expected outcomes are HAPN symbol+venue/no A-to-A transition; QBTS
  venue-only/no transition; CCL no tracked-security identity change/no
  transition; BLBD asset acquisition without registrant identity change/no
  transition.
- [x] The scheduler node proves local alias closure and known positive IBKR
  conIds are projected into the identity context before any provider call,
  with bounded reads and no transaction held for later I/O.
- [x] Commit tests before product repair and record exact RED node identity and
  reasons. Expected initial failure is cross-stage shape/context loss, never a
  provider or production-path attempt.

## Task 2: Repair Only Cross-Stage Shape Loss

**Files:**
- Modify: `src/security_lifecycle_decision_policy.py`
- Modify: `src/security_lifecycle_sec_evidence.py`
- Modify: `src/service/security_lifecycle_automation_scheduler.py`
- Modify: `tests/test_security_lifecycle_sec_evidence.py`

- [x] Let the policy consume the SEC extractor's reviewed `value` field in
  addition to persisted `normalized_value[_json]` shapes. Do not weaken fact
  identity or value normalization.
- [x] Treat explicit same-symbol continuation as both source and successor
  identity facts while retaining the invariant that no `A -> A` transition is
  emitted. Evolve only the named QBTS owner.
- [x] Recognize the extractor's explicit
  `asset_acquisition_no_registrant_change` effect as the existing no-change
  decision; do not generalize M&A forms or transaction kinds into continuity.
- [x] Enrich scheduler cases from bounded read-only local state: transitive
  alias pairs from `ticker_aliases` and matching positive IBKR conIds from
  current portfolio rows. Missing optional tables yield no hints; malformed or
  over-limit owned data is typed/fail-closed rather than guessed.
- [x] Re-run exact additions, focused `38`, and direct shape tests. No schema,
  provider, transition execution, or UI byte changes are allowed.

## Task 3: Produce The Shadow Report

- [x] Run all four cases twice from a clean tree with sockets denied and
  require byte-identical bounded JSON.
- [x] Record case identity, source pointers, extracted fact types, decision
  tier/readiness/outcomes/rule, transition request, and exact limitations. Do
  not record full source bodies, provider payloads, credentials, or production
  paths.
- [x] State explicitly that HAPN is the only historical A-to-B example and is
  already keyed by HAPN, so the report does not exercise a real production
  `A -> B` apply. Bind execution/reverse evidence to the Stage 4 scratch packet.

## Task 4: Fixture-Only Bilingual Browser Matrix

### T4A Amendment: Closed Fact Values Must Not Leak Storage Codes

The first browser replay rendered `tracked_security_effect` value
`symbol_and_venue_change` verbatim. That is a user-visible storage code, not
rule provenance. The rule ID `lifecycle.simple_symbol_continuation` remains
verbatim and is excluded from the raw-enum scan because provenance must not be
translated.

- [x] Add one frontend RED node for a closed fact-value presenter and evolve
  the existing LifecycleView owner to render a real tracked-effect fact.
- [x] Add exactly nine bilingual resource leaves: `common_stock`,
  `asset_acquisition`, `corporate_unification`, `terminal_delisting`,
  `symbol_change`, `venue_change_only`, `symbol_and_venue_change`,
  `no_identity_change`, and `asset_acquisition_no_registrant_change`.
- [x] Render those known strings through the closed presenter. Preserve raw
  ticker, venue, date, CIK, and structured transaction objects; an unknown
  closed string renders the existing explicit unknown label, never the code.
- [x] Keep the browser raw-enum check strict outside `.mono` rule/policy
  provenance. This amendment changes no decision, fact storage, transition,
  route, tool, or schema behavior.

- [x] Start only a feature-tree Vite server. Intercept every API request in
  Playwright; abort and fail on every non-loopback request. Do not start the
  production backend or App scheduler.
- [x] Exercise English and Traditional Chinese at `1440x900` and `390x844`.
  Render the activity band, an automation-accepted case, a complete suggested
  review, grouped regulator/market/publisher evidence, original source text,
  adjacent labeled translation, facts, blockers, and reversal availability.
- [x] Assert zero write requests, external requests, console errors, page
  errors, page/body horizontal overflow, incoherent overlap, raw enum leakage,
  and source/translation substitution. Rendering must not acknowledge activity.
- [x] Capture screenshots and mechanically inspect dimensions/nonblank pixels;
  visually inspect every screenshot before admission.

## Task 5: Prepare, But Do Not Execute, Live Migration Authorization

- [x] Produce a bounded runbook/manifest template bound to the final reviewed
  tree, exact migration module/schema authority, expected legacy four-row
  mapping, restore/old-code boot requirement, and rollback data-loss warning.
- [x] Leave live database path/digests, app-quiesced witness, backup identity,
  restore result, and approval digest explicitly `UNAUTHORIZED/NOT_RUN`.
- [x] Do not read production to fill any field. Fresh preflight, backup, restore
  probe, digest approval, migration, merge, and restart remain future explicit
  authorization events in the reviewed cutover order.

## Task 6: Stage 5 Offline Admission

- [ ] Run additions exact `6 passed`; focused exact `38`; collection twice
  `4411`; full backend twice with unique `--basetemp` roots at
  `4399 passed / 12 skipped / 0 failed`.
- [ ] Run frontend full `105 files / 1228 tests`, typecheck, visible-literal
  scanner, production build, and the four-entry browser matrix.
- [ ] Verify unchanged route/tool inventories, exact protected bytes, complete
  ownership, linear clean unpublished branch, and zero provider/production
  operations.
- [ ] Produce a checksummed Stage 5 packet containing node streams, shadow
  report, browser artifacts, network classification, ownership/protected
  reports, and the unexecuted migration authorization template.
- [ ] Stop before merge, push, production preflight, backup, migration,
  provider call, or app cutover and request independent review.

## Non-Goals And Hard Stops

- No fresh SEC/IBKR/news/LLM/general-search call and no claim that synthetic
  source prose is captured provider content.
- No schema/migration change, live migration, backup, restore, or production DB
  read of any kind.
- No new automation rule, source family, fact type, adapter, author, authority,
  transition status, route, tool, or UI control. Visible copy is limited to the
  nine T4A closed fact-value labels.
- No real transition execution; Stage 4 scratch evidence remains its authority.
- No app restart against the feature tree, merge, or push.
