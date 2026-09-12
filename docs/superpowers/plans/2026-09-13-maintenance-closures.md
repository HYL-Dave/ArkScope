# Maintenance Closures

> Use superpowers:subagent-driven-development. Complete each independent change,
> its RED/GREEN checks and review before claiming the corresponding issue closed.

**Goal:** Close EIR-001 and C11 as working, verified removals, not new foundations.
**Architecture:** Remove only unused page-header CSS and the obsolete local-news
switch. Retain the current UI primitive, news writers and storage authorities.
**Tech Stack:** Existing Python/pytest and React/Vitest/Vite/Playwright toolchains.
**Spec:** EIR-001 in `docs/design/ENGINEERING_ISSUE_REGISTER.md`; C11's exact
contract is `docs/superpowers/plans/2026-09-13-news-routing-cleanup.md`.
**Base:** `ef5f7b48`, existing isolated `codex/sec-research-integration` worktree.

## Constraints

- No private configuration, production DB/key reads, provider calls, install,
  App restart, merge/push or stored-data deletion. SQLite source-only admission
  preflight is separate; actual maintenance needs a concrete authorized window.
- One implementation writer/test runner at a time in this worktree. Reviewers
  are read-only; never mutate source or run parallel pytest during a full suite.
- Disposable test stores and closed environments; copy the prior tracked offline
  harness into this plan's workspace. Preserve all failed run receipts.
- SEC cleanup/reset still require durable Research reference roots and operation
  leases (release Tasks3/5). Backend document citations alone do not satisfy them.
  Do not relax those prerequisites or perform an unprotected cleanup.
- Preserve exact existing news, prices, SA, cache, credentials and route choices.
  Removing the old switch does not change the live normalized-write switch.
- No unrelated CSS removal. The broader88 CSS census candidates are not identical
  to EIR-001; keep them open until independently verified.

### Task 1: Close EIR-001

Files: `apps/arkscope-web/src/styles.css`, a focused
`apps/arkscope-web/src/retiredPageHeader.test.tsx`; existing PageHeader/primitives
only as read-only controls. Controller owns issue-register/evidence updates.

- [x] Recount exact obsolete class selectors and search all actual frontend class
  consumers, including dynamic strings. `detailpage-head` is not `page-head`.
- [x] Add a named selector-absence test before CSS deletion. Assert no exact
  `.page-head`/`.page-head-actions` selector in desktop or media rules, while
  rendering the real PageHeader and retaining `.detailpage-head` and current
  `.ui-page-header*` styles as nonempty positive controls.
- [x] Record assertion RED, then delete only the obsolete desktop/mobile rules.
- [x] Run focused and full frontend tests, typecheck/build, and desktop/mobile
  responsive visual checks with the real primitive and local CSS. No live App
  or provider; screenshots use a disposable browser and isolated fixture server.
- [x] Restore an obsolete rule temporarily to prove the absence owner fails;
  restore reviewed bytes and rerun. Preserve declarations of all retained rules.
- [x] Commit and independently review; controller closes EIR-001 with exact
  commit/results. Do not claim the whole CSS census queue closed.

Task1 product commit `eec66b9e`; independent review approved. Controller focused
38P; full frontend1779P, typecheck/build and10 pixel-identical responsive pairs.
Exact closure receipt will be sealed with Task3, not a wider CSS-clean claim.

### Task 2: Close C11

Execute the complete owned-file and RED-first acceptance sections in
`2026-09-13-news-routing-cleanup.md`, not only its helper deletions. That plan's
scope, names, positive controls and expected route223->222 collateral are the
binding task brief. Mark its checkboxes as work is verified, not preemptively.

- [x] Baseline; add actual persisted false/malformed-old-setting routing and
  telemetry owners, plus obsolete-helper/PUT absence owners, then record RED.
- [x] Implement all backend/frontend removals, current documentation and exact
  caller/monkeypatch collateral. No actual persisted key deletion.
- [x] GREEN current normalized/direct writers, status/overlay/health and API
  protection, missing-store noncreation, real data controls and frontend checks.
- [x] Inverses independently restore telemetry suppression and old-value
  validation; both named owners fail. Restore and rerun.
- [ ] Independent review, commit, and final frozen full backend/frontend/census.
  Reconcile exact test additions/removals and any new scanner uncertainties.

### Task 3: Verification And Delivery

- [ ] Verify no remaining EIR-001 selectors or C11 product consumers, and retain
  current news/UI/data controls. Finish all servers/test processes owned here.
- [ ] Full suites run serially on frozen product/test source, not a union of
  partial successes. Record source/runner identity and unchanged skip IDs.
- [ ] Seal selected receipts only; verify manifest membership and hashes from
  Git, including log files ignored by default. No fixture data/binaries in Git.
- [ ] Close only completed issue scopes, list real remaining work and SQLite
  admission findings. Keep the branch/worktree; no merge or push.
