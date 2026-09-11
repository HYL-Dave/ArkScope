# Final Whole-Batch Fix

Worktree: /tmp/arkscope-listing-sec-macro-convergence
Plan: docs/superpowers/plans/2026-09-11-sec-query-settings.md
HEAD: 97a1aba6. All tasks complete; this is ONE final fix dispatch, not a redesign.

Read final-review.md and final-review-probe.cjs in this scratch directory, then
the relevant Records/pagination component and existing panel tests. Apply the
receiving-code-review, systematic-debugging and RED-first TDD workflows.

Complete finding list: ONE P2 at SecResearchPanel.tsx:101. Backend intentionally
retains conflicting metadata variants with the same filing_id. React uses only
filing_id as a key, so a 20-row conflict-bearing page followed by a one-row page
can leave TWO DOM rows. Do not deduplicate/drop observations, change backend
identity semantics or stringify/round exact numeric values to repair display.

Give retained row variants a unique render identity and add a real panel test
for paging forward/back through conflicting variants, exact row counts/content,
and no duplicate-key warnings. Preserve facts behavior and cached-back semantics.
Use the narrowest correct key strategy for this stateless read-only table.
Run RED before implementation; test inverse restoring the old key must fail.

Write scope: apps/arkscope-web/src/settings/SecResearchPanel.tsx and its existing
frontend test file only, plus final-fix-* scratch reports/logs. No backend files,
other task files, package metadata, production data, credentials, provider calls,
installs, merge/push or live App. Main repo is not the implementation worktree.
No git index mutation/commit until parent gives sole permission. Use apply_patch.

Use existing run_checks.py with distinct names, or the task-4 runner's established
closed environment. Node is /home/hyl/.nvm/versions/node/v22.14.0/bin. Existing
node_modules only. Parent owns full frontend/typecheck/i18n/browser verification.
Report changed files, RED reason, GREEN count, inverse failure, restoration hashes
and limits in final-fix-report.md. Parent has already sealed full backend result
8811P/12S plus all 1088 unchanged source paths before this frontend-only fix.
