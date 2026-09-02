# Lifecycle Proposal Contract Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the BLBD/CCL drawer crash by projecting proposals through a closed API DTO and removing the unused historical source snapshot from the UI.

**Architecture:** Keep the durable proposal table unchanged. Add a single projection boundary in `SecurityLifecycleInvestigationStore.project_proposals`, narrow the TypeScript interface to that projection, and validate the proposal shape as part of the case-detail response before React receives it.

**Tech Stack:** Python 3, SQLite, pytest, TypeScript, React, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-01-lifecycle-sec-admission-and-detail-clarity-design.md`

## Global Constraints

- Do not modify profile or market schema.
- Do not read or write production databases from tests.
- Do not expose proposal storage identifiers, hashes, dedupe keys, or raw JSON.
- Preserve proposal dismissal by `proposal_id`.
- Use RED-first tests against real projection and render paths.

---

### Task 1: Closed Backend Proposal Projection

**Files:**
- Modify: `src/security_lifecycle_investigation.py`
- Test: `tests/test_security_lifecycle_investigation.py`

**Interfaces:**
- Consumes: durable proposal rows from `list_proposals(case_id)`.
- Produces: `project_proposals(...) -> list[dict]` with exactly `proposal_id`, `action_type`, `status`, `projected_block_reason`, and `replacement_ticker`.

- [ ] **Step 1: Write a failing real-store test**

Create a proposal through `generate_action_proposals`, call
`project_proposals`, and assert the exact literal key set and values. The test
must fail against the current `{**proposal, ...}` implementation because it
leaks storage fields.

- [ ] **Step 2: Run the named test and confirm RED**

Run: `pytest -q tests/test_security_lifecycle_investigation.py -k proposal_projection_is_a_closed_public_dto`

Expected: FAIL because the returned key set includes `source_snapshot_json`,
`proposal_dedupe_key`, `assessment_fingerprint_sha256`, and other storage
fields.

- [ ] **Step 3: Implement the minimal closed projection**

Build each public dictionary field by field after the existing stale-state
calculation. Do not change `list_proposals`, `get_proposal`, or the table.

- [ ] **Step 4: Run focused backend tests and confirm GREEN**

Run: `pytest -q tests/test_security_lifecycle_investigation.py`

Expected: all tests pass.

### Task 2: Runtime-Validated Case Detail and Crash-Free Proposal UI

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Test: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Test: `apps/arkscope-web/src/api.test.ts`

**Interfaces:**
- Consumes: unknown JSON from `GET /security-lifecycle/cases/{case_id}`.
- Produces: a validated `SecurityLifecycleCaseDetail`; proposal entries match the five-field backend DTO.

- [ ] **Step 1: Write a failing BLBD-shaped render test**

Supply a complete case-detail fixture whose proposal contains the five public
fields and no `source_snapshot`. Open the drawer and assert that the proposal
label/state/replacement ticker render without a React error. The current
`.map()` call must fail the test.

- [ ] **Step 2: Write failing parser contract tests**

Exercise the exported case-detail parser with a complete valid fixture and
with malformed `proposals`, `active_sources`, and `evidence` fields. The valid
fixture must pass; each malformed array must fail with the existing typed API
response error shape.

- [ ] **Step 3: Run the named frontend tests and confirm RED**

Run: `npm test -- --run src/api.test.ts src/lifecycle/LifecycleView.test.tsx`

Expected: the BLBD-shaped render fails at `source_snapshot.map`; parser tests
fail because `getSecurityLifecycleCase` currently performs only a TypeScript
cast.

- [ ] **Step 4: Implement the minimal client contract**

Remove the source-snapshot paragraph, narrow
`SecurityLifecycleActionProposal`, add the case-detail parser following the
existing closed parser helpers in `api.ts`, and route
`getSecurityLifecycleCase` through it.

- [ ] **Step 5: Run frontend tests, typecheck, and build**

Run: `npm test -- --run src/api.test.ts src/lifecycle/LifecycleView.test.tsx`

Run: `npm run typecheck`

Run: `npm run build`

Expected: all commands pass.

### Task 3: Slice Verification

**Files:**
- No new production files.

**Interfaces:**
- Verifies the complete first slice without SEC admission changes.

- [ ] **Step 1: Run backend lifecycle contracts**

Run: `pytest -q tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_routes.py`

- [ ] **Step 2: Run frontend lifecycle suite**

Run: `npm test -- --run src/lifecycle/LifecycleView.test.tsx src/lifecycle/lifecyclePresentation.test.ts`

- [ ] **Step 3: Verify diff scope and whitespace**

Run: `git diff --check`

Confirm no schema, collector, SEC policy, or production-data file changed in
this slice.
