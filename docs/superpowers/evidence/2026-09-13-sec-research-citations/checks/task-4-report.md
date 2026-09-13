# Task 4 Report

Complete; frontend implementation and self-review committed, ready for parent acceptance.
Commit: `bc8c86d5122f5c01221d023a2719673dd226936e`.
Baseline: `8c9ee301e6fabcc02105be0eb2b4f2ad30ba81a7`.
Worktree: `/tmp/arkscope-research-output-boundary`; branch: `codex/sec-research-integration`.

## Scope And Behavior

13 owned frontend files; no backend or Research.tsx changes. Its DTO adapter already
retains tool_calls unchanged. The resource inventory test has only two count updates.
Report/receipts remain in this plan's ignored scratch, matching Tasks 1-3.

- api.ts exposes SecCitation, SecCitationTrace, SecCitationRead and getSecResearchCitation.
- GET uses one ref: sorted compact ASCII JSON, unpadded base64url; DEL, Unicode and
  surrogate code-unit escaping match Python. Closed scalar shape/ranges/size are
  checked locally; backend remains the semantic/storage validation authority.
- No latest query, reconstructed acquisition URL, eager fetch or runtime citation stub.
  Unit tests mock fetch; real-store browser verification remains parent-owned.
- Reducer pairs exact IDs, isolates ID-less legacy fallback, ignores replayed ends
  and late starts after completion, retains end-only input and optional refs/gaps.
- Both evidence projections and terminal/reload paths retain metadata. Local abort
  with SEC metadata retains a synthetic interrupted message; no server cancellation
  outcome is invented. Legacy-only local abort behavior remains unchanged.
- Saved source opening is independent of pending/failed getResearchRun. Selection
  is owned by the exact message/live run; switching/closing revokes pending reads.
- Pinning retains the selected owner/ref; the shared Drawer remount may reread that
  same ref. Retry keeps keyboard focus inside the source, and closing restores its
  opener. Source Escape closes the source; subsequent drawer Escape closes the drawer.
- Native fact value stays Decimal TEXT. Form/period appear only from the saved read;
  filing fields and UTF-8 passages render as plain text, including literal HTML.
- Mismatched/malformed reads and typed missing/integrity/query gaps are retryable.
  Source content and identifiers wrap; existing icons/panel styling are reused.
- Same-CIK fact choices have localized ordinals across displayed facts. Choosing
  the second fact requests exactly its reference; no concept/period is invented.

## Verification

All checks used this plan's isolated create-only runner, one process at a time.
Each NAME directory holds command.json (exact argv/environment) and output.log.
No frontend source edits followed the final typecheck/full/build/i18n sequence.

| Receipt | Actual Result |
| --- | --- |
| task4-red-01 | 33 failed / 79 passed: missing API/metadata/source controls |
| task4-boundary-red-01 | 3 failed / 23 passed: malformed read and typed query error |
| task4-abort-red-01 | 2 failed / 78 passed: local abort lost received metadata |
| task4-retry-red-01 | 1 failed / 7 passed: pending retry lost keyboard focus |
| task4-fact-label-red-01 | 2 failed / 19 passed: identical same-CIK labels, both locales |
| task4-final-focused-01 | 147 passed before the final fact-label addition |
| task4-fact-label-green-01 | 35 passed, including both exact second-fact selections |
| task4-final-full-03 | 1824 passed, 126 files, runner 14.011s |
| task4-final-typecheck-03 | exit 0 |
| task4-final-build-03 | exit 0; large-chunk advisory |
| task4-final-i18n-03 | exit 0; zero debt signatures |

Preserved intermediate failures: green-01/-02 each 111 passed/1 failed (test Response
reuse and post-unpin focus assumption corrected); full-01 had 1817 passed/2 failed
(localized interpolation and inventory counts fixed). Final-typecheck/build-02
exposed i18next's reserved boolean ordinal option; renamed interpolation to position.
Earlier successful gates are retained, superseded by the final -03 receipts.

Exact RED and final GREEN commands, run from the worktree (existing names are create-only):

```bash
P=/home/hyl/.virtualenvs/llm_app/bin/python
R=.superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py
$P -B "$R" task4-red-01 frontend test -- --run src/secCitationApi.test.ts src/researchReducer.test.ts src/ResearchEvidenceDrawer.test.tsx
$P -B "$R" task4-boundary-red-01 frontend test -- --run src/SecCitationView.test.tsx src/ResearchEvidenceDrawer.test.tsx
$P -B "$R" task4-abort-red-01 frontend test -- --run src/researchReducer.test.ts
$P -B "$R" task4-retry-red-01 frontend test -- --run src/SecCitationView.test.tsx
$P -B "$R" task4-fact-label-red-01 frontend test -- --run src/ResearchEvidenceDrawer.test.tsx
$P -B "$R" task4-final-focused-01 frontend test -- --run src/secCitationApi.test.ts src/researchReducer.test.ts src/ResearchEvidenceDrawer.test.tsx src/SecCitationView.test.tsx src/i18n/resources.test.ts src/i18n/foundationBoundaries.test.ts
$P -B "$R" task4-fact-label-green-01 frontend test -- --run src/ResearchEvidenceDrawer.test.tsx src/i18n/resources.test.ts
$P -B "$R" task4-final-typecheck-03 frontend run typecheck
$P -B "$R" task4-final-full-03 frontend test -- --run
$P -B "$R" task4-final-build-03 frontend run build
$P -B "$R" task4-final-i18n-03 frontend run check:i18n-literals
```

## Browser Selectors

- Tool row: `.research-evidence-tool[data-call-id="EXACT_CALL_ID"]`.
- Source button: `[data-sec-citation-open="ROW_INDEX:CITATION_INDEX"]` (zero-based).
- English names: `Open SEC source: Document: file:NAME`, `Open SEC source: Fact N: CIK`,
  `Open SEC source: Filing: FILING_ID`; N is the one-based displayed fact ordinal.
- zh-Hant names: `開啟 SEC 來源：文件：file:NAME`, `開啟 SEC 來源：財務事實 N：CIK`,
  `開啟 SEC 來源：申報：FILING_ID`.
- Source region: `[data-sec-citation-view]` (value document, fact or filing), named `SEC source`
  / `SEC 來源`; exact passage `.sec-citation-text`, observation `.sec-citation-observation`.
- Buttons: `Close SEC source` / `關閉 SEC 來源`; `Retry SEC source` / `重試 SEC 來源`.
- Typed gap: `.sec-citation-gap` with its closed code in `code`; no raw diagnostics.
- Existing drawer names: `Evidence and Run Details` / `證據與執行詳情`.

## Handoff

No unresolved implementation failures found in self-review. Full logs include act
warnings in unrelated test owners; build's chunk-size advisory is not addressed here.
Parent owns independent review, real-store browser acceptance and backend full suite;
none are claimed here. No subagents, browser/app/provider process, live DB/config/token
access, merge or push. Product/index/test-runner ownership is released to the parent.
