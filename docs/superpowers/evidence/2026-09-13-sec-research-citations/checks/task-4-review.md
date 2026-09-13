# Task 4 Independent Spec And Quality Review

Decision: APPROVE. No actionable Task 4 findings in the reviewed source.

Scope: immutable `8c9ee301..bc8c86d5` in
`/tmp/arkscope-research-output-boundary`.
Read `task4-review.diff` once, focused plan Task 4, parent Task 3 UI contract,
`task-4-report.md`, Task 1 exact-read contract, and relevant product dependencies.
Confirmed HEAD `bc8c86d5122f5c01221d023a2719673dd226936e` and no frontend drift.

## Source Review

- `apps/arkscope-web/src/api.ts:1258`: optional trace metadata is typed; the
  single `ref` GET uses sorted compact ASCII JSON, including DEL/Unicode/surrogate
  escaping, unpadded base64url and bounded scalar/range checks. Backend validation
  remains authoritative; no latest lookup or reconstructed acquisition URL.
- `apps/arkscope-web/src/researchReducer.ts:165`: metadata survives tool-call
  projection, done/error/disconnect and local abort with received SEC evidence.
  Exact-ID first-completion/replay and isolated ID-less last-open pairing match
  `src/research_tool_trace.py`; end-only input is retained.
- `apps/arkscope-web/src/Research.tsx:86` and
  `apps/arkscope-web/src/ResearchEvidenceDrawer.tsx:50`: reload and both evidence
  projections preserve refs/gaps; an explicitly selected message owns its rows.
  Saved source controls do not depend on successful run-detail retrieval.
- `apps/arkscope-web/src/ResearchEvidenceDrawer.tsx:116`: owner/open guards revoke
  selection on message changes/close; pinning does not substitute another owner.
  Distinct localized fact ordinals identify same-CIK choices and open their own refs.
- `apps/arkscope-web/src/SecCitationView.tsx:18`: returned citation identity is
  checked; approved exact-read backend supplies pinned native observations/text.
  Decimal strings and passages remain text, never HTML; form/period come from data.
  Effect cleanup suppresses late reads; retry and nested Escape/close cooperate
  with the shared Drawer focus behavior. Typed unavailable gaps remain actionable.
- `apps/arkscope-web/src/styles.css:3962`: additions are evidence/citation scoped,
  with wrapping and constrained observation tracks within existing responsive drawers.
- `apps/arkscope-web/src/i18n/resources.test.ts:757`: only inventory counts change
  (+17 research keys, +17 total per locale); no guards/assertions are disabled.
  Citation fixtures have no non-test imports. Preview/artifact drivers are not product.

## Verification Boundary

This reviewer ran no tests, builds, browser, provider or app processes; read no
production stores/configuration/credentials; used no subagents; changed only this report.
Parent confirms full frontend 1824 passed and production build exit 0.
Parent additionally reports browser02 passed all four en/zh-Hant x 1280/390 runs
against a real temporary API/store: exact old 176-byte passage after refresh/root
move, Unicode/escaped fact-pointer GET, exact 21-digit value, filing period,
missing-object typed gap/retry, source/drawer Escape focus and persisted reload.
Parent visually inspected screenshots: no overflow, clipped controls or page errors.
These runtime results are supplied evidence, not independently rerun here.
Browser01's preview-only loopback-listen guard failure is not a product defect;
parent reports the corrected wrapper preserves outbound denial and base guards.
Deferred whole-SEC export/cleanup is outside Task 4, not a finding.
