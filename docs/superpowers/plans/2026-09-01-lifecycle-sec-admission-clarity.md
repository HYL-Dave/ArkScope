# Lifecycle SEC Admission Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and `superpowers:test-driven-development`.

**Goal:** Keep broad SEC observations available for audit while admitting only
direct or deterministically material tracked-security cases to the operational
queue.

**Architecture:** Admission is a pure, derived projection over an immutable
market observation and the latest matching automation run/facts. No database
column, backfill, or migration is introduced. The ordinary case list excludes
only completed `screened_out` candidates; a closed candidate-audit endpoint
retains every observation and its reason. Scheduled automation skips screened
candidates, while the attended per-case run remains an explicit override.

**Spec:**
`docs/superpowers/specs/2026-09-01-lifecycle-sec-admission-and-detail-clarity-design.md`

## Closed Contract

Admission states:

- `pending`: no complete regulator screening exists yet;
- `admitted`: a direct filing signal or cited material tracked-security fact
  exists;
- `screened_out`: complete SEC acquisition found no material tracked-security
  signal for a known conditional candidate;
- `needs_review`: provider/parser failure, missing direct-form identity binding,
  conflict, or an unknown candidate form prevents deterministic classification.

The public candidate DTO contains only `case_id`, `ticker`, `issuer_name`,
`filing_form`, `filing_items`, `filing_date`, `evidence_url`, `admission_state`,
and `admission_reason`.

Unknown means an already discovered lifecycle candidate whose SEC form is not
in the closed policy, not every unknown SEC submission for an issuer.

---

### Task 1: Pure Admission Classifier

**Files:**
- Create: `src/security_lifecycle_sec_admission.py`
- Test: `tests/test_security_lifecycle_sec_admission.py`

- [x] RED: parameterize direct 8-K Item 3.01, Form 25 with/without exact
  source-security binding, BLBD/CCL material facts, a completed conditional
  candidate without material facts, provider failure, and unknown form.
- [x] RED: prove only facts from the latest run for the current observation can
  admit a case; stale facts cannot.
- [x] Implement the pure closed classifier and candidate DTO projector.
- [x] Mutation controls: removing direct admission, material-fact admission,
  complete-screening requirement, or unknown-form fail-visible behavior kills
  a named test.

### Task 2: Candidate Audit and Active Queue Boundary

**Files:**
- Modify: `src/tools/security_lifecycle_tools.py`
- Modify: `src/api/routes/security_lifecycle.py`
- Modify: `src/security_lifecycle_automation_worker.py`
- Test: `tests/test_security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_routes.py`
- Test: `tests/test_security_lifecycle_automation_worker.py`

- [x] RED: ordinary lists exclude only `screened_out`; counts and queue badges
  use the same selected population.
- [x] RED: `GET /security-lifecycle/candidates` returns all source-present
  candidates through the exact closed DTO and supports state filtering.
- [x] RED: scheduled workers skip screened candidates, but a targeted attended
  run can re-screen one.
- [x] Implement projection, route, and worker boundary without changing durable
  case identity or deleting observations.

### Task 3: Filing Controls and Date Sanity

**Files:**
- Modify: `src/security_lifecycle_sec_evidence.py`
- Test: `tests/test_security_lifecycle_sec_evidence.py`
- Fixture: `tests/fixtures/security_lifecycle_automation_sec.json`

- [x] RED: BLBD and CCL remain positive controls that emit material
  tracked-security facts.
- [x] RED: a CDE-shaped 2026 filing sentence containing a 2010 effective date
  does not emit an `effective_date`; it records a bounded ambiguity diagnostic.
- [x] RED: an effective date without an exact tracked ticker/security binding
  does not become a fact.
- [x] RED: the filing-chain candidate policy names direct, conditional,
  support-only, and unknown-observation behavior explicitly.
- [x] Implement bounded date extraction and integer screening diagnostics. Keep
  all stored historical evidence; primary-detail filtering is Task 4.

### Task 4: Frontend Candidate Contract

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Test: `apps/arkscope-web/src/api.test.ts`

- [x] RED: malformed admission state/reason or candidate arrays fail at the API
  parser, not in React.
- [x] RED: screened candidates do not appear in the operational queue, while a
  compact audit control exposes their counted state and reason.
- [x] Implement closed runtime parsing and the compact audit surface. Do not add
  SEC excerpts or storage provenance to the default list.

### Task 5: Verification

- [ ] Run the SEC evidence, admission, tools, routes, worker, and lifecycle UI
  focused suites.
- [ ] Run the full backend suite twice and compare collected node manifests.
- [ ] Run the full frontend suite, typecheck, build, and i18n scanner.
- [ ] Run `git diff --check` and confirm no schema/migration or production data
  file changed.
- [ ] Commit this slice separately from the proposal-contract repair.
