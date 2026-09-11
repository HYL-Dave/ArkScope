# Scoped Final Re-review

## Assessment

**Spec compliance: PASS. Code quality: APPROVED. I1 is closed.**
**Ready for this batch's completion: Yes.** The sole whole-batch finding is
resolved and the inspected, source-bound parent gates satisfy the prior review's
verification conditions. This is not approval of the unfinished broader SEC
first release, production activation, or authorization to merge/push.

## Complete Residual Findings

- Critical: None.
- Important: None. Previous I1/P2 is resolved, not deferred.
- Minor: None.

No additional findings or required corrections remain within this re-review.

## I1 Closure

- `apps/arkscope-web/src/settings/SecResearchPanel.tsx:102` now assigns unique
  page-local positions to catalog rows. Conflicting variants no longer collide
  on filing identity. The adjacent comment documents the reason. These rows
  contain read-only, stateless rendered cells, so positional reconciliation is
  appropriate here; no per-record component state needs preservation. The fact
  key expression, observations, cursor/cache behavior and backend are unchanged.
- `apps/arkscope-web/src/settings/SecResearchPanel.test.tsx:280` adds the actual
  panel regression. It preserves both conflicting variants and the conflict gap,
  checks exact cell values/order/counts through 20 -> 1 -> 20 -> 1, verifies the
  unchanged opaque cursor and limit, and checks cached back/forward navigation
  despite a changed latest fixture response. Console errors are checked and the
  spy is restored in finally. No deduplication conceals the supported conflict.
- RED and the old-key inverse each show the new regression failing while 39
  controls pass. The raw RED assertion at `final-fix-red/output.log:412` is
  expected 1 row versus actual 2, with duplicate-key/stale-content failures also
  present. Restored GREEN records 45 passing panel/API cases. Command records
  confirm the focused scopes and expected exit codes; these are inspected
  executions, not tests rerun by this reviewer.
- Parent `browser-conflict-red/output.log` independently reproduces 1 versus 2
  through real FastAPI/Store/React. In `browser-post-fix/browser/results.json`,
  all four locale/viewport cases retain 20 first-page rows, exactly one next-page
  row and no duplicate-key warnings. The relevant browser assertions at
  `browser_check.py:154` verify retained variants and both return transitions.
  Inspected the English 390px conflict-next screenshot: one row, Page 2, and the
  conflict gap remain visible. The conflict fixture intentionally differs from
  the earlier non-conflict browser-final fixture; this does not invalidate the
  corresponding conflict RED/GREEN comparison.

## Scope And Source Identity

- Reviewed only the complete prior finding list (I1), its two-file fix and
  relevant verification evidence. No whole-batch review restart or agents.
- Range: `97a1aba680c5654d0f723bcf53a7e6e8c4665dff` through
  `5d03c57e403386edca93529322f7c62a39571cc7`; 53 insertions, 1 deletion.
- `final-fix-diff.txt` was initially absent, so the immutable commit delta was
  inspected directly. The artifact subsequently appeared and was read completely
  once, confirming the same changes. Artifact SHA-256:
  `d5cebff5f6c2206ae35b4e8fcd78e161ef8c3f12bf2a019069a18b9d778597a2`.
- Independently hashed all 1088 current paths against `source-final.json`: zero
  mismatches. Compared before/final manifests: exactly the component and its
  frontend test changed; all 798 backend paths are unchanged. Both changed blobs
  also match commit 5d03c57e and the worker's restored source/test hashes.
- Independently checked all five final-gates command/log hash pairs and exit
  codes, and the backend checkpoint hash in `post-fix-verification.json`.

## Completed Parent Gates

- Backend: raw completed log records **8811 passed / 12 skipped**.
  `verification-summary.json` reconciles **8823 exact nodes, +377/-0**, the same
  twelve skips and all 1088 paths at the **pre-frontend-fix** checkpoint. This
  is not represented as a backend execution after the fix. The verified absence
  of backend changes supports reusing that completed result without another run.
- Post-fix frontend: raw log records **121 files / 1738 passed**; typecheck and
  i18n exit 0. I18n remains 37 candidates/20 signatures/zero debt/20 existing
  allowlist entries. All four post-fix browser cases pass, each with 33 local HTTP
  requests and 10 generated fixture dispatches. No real provider call is implied.
- Census remains **review_required / exit 2**, with 4360 candidates, 3444
  uncertainties, 53 new candidates and 248 new uncertainty IDs; no reported
  coverage/dependency/untracked-path drift. This scoped frontend fix does not
  clear the existing inventory queues or grant deletion permission.

## Limits And Preservation

Only this report was written. No product/test/index/branch writes, new probe,
suite/browser rerun, provider/production access, install, merge or push occurred.
The parent's tests/browser are inspected evidence, not reviewer executions;
backend node reconciliation is the parent artifact, not independently rerun here.
No additional adjacent product reads were needed beyond the narrow diff context.

The original RED script was not run or modified. Its retained result remained
byte-identical throughout this re-review, SHA-256:
`42143d1468e35a7d24547c4bf12e8957b88eb88f9415f36d0671719ef9e86869`.
The original whole-batch report and RED history remain intact. Future editable
row state would require revisiting positional keys; that is not a current defect.
All broader unfinished SEC/schema/SQLite and native-packaging boundaries from
the original review remain unchanged and are not reopened as findings.
