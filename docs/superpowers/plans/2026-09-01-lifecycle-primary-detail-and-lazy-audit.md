# Lifecycle Primary Detail and Lazy Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the lifecycle drawer answer the seven current operator questions
without loading or displaying repeated evidence, runs, facts, and provenance
until the operator explicitly opens the audit view.

**Architecture:** `GET /security-lifecycle/cases/{case_id}` becomes a closed
primary-detail projection. `GET /security-lifecycle/cases/{case_id}/audit`
returns the bounded historical arrays through a separate closed projection.
The browser validates both payloads at runtime, keeps action controls on the
primary detail, and loads the audit response only when its disclosure is opened.

**Tech Stack:** Python 3, FastAPI, SQLite-backed read services, TypeScript,
React 18, Vitest, i18next.

**Spec:**
`docs/superpowers/specs/2026-09-01-lifecycle-sec-admission-and-detail-clarity-design.md`

## Global Constraints

- Do not change profile or market schema and do not add a migration.
- Do not delete or rewrite stored observations, evidence, runs, or facts.
- Keep proposals and ticker-transition controls available on the primary view.
- CIK, accession, hashes, rule IDs, raw facts, excerpts, prior runs, and storage
  provenance must not render in the default drawer.
- The primary view must always expose what is missing and the next verification
  time, including an explicit no-next-check value.
- The audit endpoint must be a closed projection; it must not return `SELECT *`
  rows or future surplus fields.
- App restart, formal-database reads, provider canary, merge, and push remain
  outside this plan.

---

### Task 1: Closed Primary and Audit Projections

**Files:**
- Modify: `src/tools/security_lifecycle_tools.py`
- Test: `tests/test_security_lifecycle_tools.py`

**Interfaces:**
- Produces: `project_security_lifecycle_case_detail(case) -> dict`
- Produces: `project_security_lifecycle_case_audit(case) -> dict`
- Primary keys: the existing case-summary keys plus `observation`, `proposals`,
  `ticker_transition`, and `corroboration`.
- Audit keys: `case_id`, `observation_fingerprint_sha256`,
  `investigation_runs`, `automation_runs`, `automation_facts`, `evidence`,
  `assessment_history`, `acknowledgement_history`, and `truncation`.
- `corroboration` contains `regulator` and `ibkr` family states plus compact
  `nasdaq_trader` and `massive` listing snapshots or `null`.

- [x] RED: use a real composed case with regulator, Massive, IBKR, proposal,
  run, fact, and surplus sentinel fields; prove primary has no historical array
  or sentinel and audit has exactly the bounded closed keys.
- [x] RED: seed both listing authorities and prove the primary corroboration
  projection identifies each authority without exposing canonical locator JSON.
- [x] GREEN: implement the two pure projections by reusing the existing active
  evidence and automation-run projectors, then explicitly selecting every
  returned field.
- [x] GREEN: make `SecurityLifecycleReadService.get_case_detail(case_id)` and
  `get_case_audit(case_id)` call the projections while keeping `get_case()` as
  the internal full case used by write and AI-tool paths.
- [x] MUTATION: adding a future top-level, run, evidence, assessment, or
  acknowledgement field must not change either public DTO.

### Task 2: HTTP Boundary

**Files:**
- Modify: `src/api/routes/security_lifecycle.py`
- Test: `tests/test_security_lifecycle_routes.py`

**Interfaces:**
- `GET /security-lifecycle/cases/{case_id}` returns the primary DTO.
- `GET /security-lifecycle/cases/{case_id}/audit` returns the audit DTO.

- [x] RED: prove primary omits `evidence`, `automation_runs`,
  `automation_facts`, histories, `truncation`, and
  `observation_fingerprint_sha256`.
- [x] RED: prove audit returns those bounded fields and preserves the existing
  compact listing DTO and operator blocker detail.
- [x] RED: prove missing cases and unavailable stores use the same typed HTTP
  errors on both endpoints.
- [x] GREEN: add the audit route before the dynamic case route where needed and
  update the exact route inventory count.

### Task 3: Browser Runtime Contracts

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Test: `apps/arkscope-web/src/LifecycleCaseApi.test.ts`

**Interfaces:**
- `SecurityLifecycleCaseDetail` is primary-only.
- `SecurityLifecycleCaseAudit` owns all historical arrays and truncation.
- `getSecurityLifecycleCaseAudit(caseId)` parses the audit endpoint.

- [x] RED: a primary payload carrying legacy audit arrays is projected without
  them, while valid proposals and corroboration remain.
- [x] RED: malformed audit arrays, evidence translations, listing snapshots,
  assessment citations, or automation blockers fail with
  `security_lifecycle_case_contract`.
- [x] GREEN: split the current parser into explicit primary and audit parsers;
  construct returned objects from allowlisted keys rather than spreading the
  server object.
- [x] MUTATION: replacing either parser with a generic cast must kill a named
  test.

### Task 4: Seven-Question Primary Drawer

**Files:**
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/styles.css`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

**Interfaces:**
- Primary drawer fields: event, tracked-security effect, effective date,
  successor/destination, SEC filing, corroboration, and missing/next check.
- The existing proposal, acknowledgement, automation-run, and transition
  commands keep their current API behavior.

- [x] RED: render a BLBD-shaped detail and assert all seven labels and values,
  including `Not scheduled` when `next_check_at` is null.
- [x] RED: assert evidence excerpt, CIK, hash, extraction rule, and prior-run
  text are absent before opening audit.
- [x] GREEN: replace the separate status/source/evidence default sections with
  one compact definition-list summary and restrained corroboration rows.
- [x] GREEN: keep proposals and transition controls outside the audit
  disclosure because they are current commands, not provenance.
- [x] GREEN: add matching English and Traditional Chinese labels and update the
  exact resource inventory.

### Task 5: Lazy Audit Workflow

**Files:**
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`

**Interfaces:**
- Opening `details.lifecycle-audit-details` calls
  `getSecurityLifecycleCaseAudit(selectedCaseId)` exactly once per current
  version; commands refresh an already-loaded audit but do not force it open.

- [x] RED: selecting a case calls only the primary endpoint; opening audit then
  calls the audit endpoint and renders evidence, run/fact truth, assessment
  history, acknowledgement history, translation, and manual-review controls.
- [x] RED: close/reopen reuses the loaded audit; switching cases discards it;
  an out-of-order old-case audit response cannot replace the current case.
- [x] RED: audit failure is visible inside the disclosure and leaves the
  primary summary and current actions usable.
- [x] GREEN: add audit request sequencing, loading/error state, and refresh
  already-loaded audit after evidence, assessment, translation, automation, or
  acknowledgement commands.

### Task 6: Verification and Slice Commit

- [x] Run focused backend tools and route suites.
- [x] Run `LifecycleCaseApi.test.ts`, `LifecycleView.test.tsx`, and i18n resource
  tests.
- [x] Run frontend typecheck, build, and visible-literal scanner.
- [x] Run `git diff --check` and confirm schema, migrations, and data files have
  no diff.
- [x] Commit this change separately from proposal repair and SEC admission.

Verification record:

- Lifecycle/listing/ticker-identity focus: `985 passed`.
- Full backend product suite A/B: `5324 passed, 12 skipped` in each run.
- Stable backend node manifest (summary excluded):
  `77d556c16b0788887209958cc19c496adf3e45a21b22f7dc0a6a73b0ebdfe463`.
- Full frontend: `109 files, 1353 passed`; typecheck, production build, resource
  inventory, and visible-literal scanner passed.
- `git diff --check` passed; no schema, migration, or data file changed.
- The repository-root pytest command also discovers the sealed 2026-08-28
  listing packet. One packet shadow test already fails on unchanged `master`
  because the historical script predates the required `execution_owner_id`;
  this slice does not rewrite sealed evidence or weaken the current owner
  contract.
