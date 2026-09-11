# Spec Compliance

- **PASS. Task quality: Approved.** I1, M1, M2, and the same-wave no-fee accounting-copy correction are addressed. No new Critical, Important, or Minor findings in this scoped revision.
- Reviewed only the seven frontend paths in frozen `task-4-r1-diff.txt`, base `05edf925293c1b096503526782f1350b1beefe83`, head `c6e2e435970c47252970767c9e40300f79ddba23`. Compared against the prior findings and `task-4-report.md:248` / `task-4-report.md:350`; implementer claims were treated as unverified until checked below.
- No broader SEC release, backend, scheduler, model-tool, or shared Button redesign is introduced. The diff preserves the existing exact budget arithmetic, query parameters, request behavior, and ten-minute refresh allowance; this is not a new whole-branch review.

# Strengths And Finding Closure

- **I1 closed (previously Important):** `apps/arkscope-web/src/settings/secResearch.css:40` now targets `.sec-pagination > span`. The page counter retains its 64px minimum; nested Button icon wrappers no longer match. The regression at `apps/arkscope-web/src/settings/SecResearchPanel.test.tsx:99` applies the real stylesheet to the rendered controls, asserts two icon wrappers, and checks that neither receives 64px. Parent browser results independently record both arrows contained in each locale/viewport at `browser-r1/browser/results.json:157`, `:355`, `:553`, and `:751`. The supplied desktop catalog screenshot visibly confirms arrows centered inside their button rectangles.
- **M1 closed (previously Minor):** `apps/arkscope-web/src/api.ts:1209` and `:1212` admit null query data; `apps/arkscope-web/src/settings/SecResearchPanel.tsx:19` propagates it to Page. The existing null fallback at `SecResearchPanel.tsx:83` remains intact. Typed real-shaped fixtures at `apps/arkscope-web/src/secResearchApi.test.ts:8` cover both helpers; `SecResearchPanel.test.tsx:159` covers both tabs as unavailable, gap-bearing, rowless, and non-pageable, without relabeling absence as observed-empty.
- **M2 closed (previously Minor):** `apps/arkscope-web/src/settings/SecResearchPanel.tsx:85` places form/dates first in the catalog; `:90` places concept/value/unit/end first in facts, with opaque IDs last. Column presence, exact string rendering, full IDs, and safe catalog links are preserved. Tests at `SecResearchPanel.test.tsx:109` and `:125` assert complete header/cell ordering with full-length identifiers and an exact long decimal. `apps/arkscope-web/src/settings/secResearch.css:34` bounds the viewport with `max-height: clamp(360px, 60vh, 480px)` and auto scrolling on both axes. The test at `SecResearchPanel.test.tsx:141` retains all 20/40 rows and verifies pagination remains outside and after the table. The supplied 390px facts screenshot visibly starts with useful concept/value/unit fields and a bounded table, not a column of hashes.
- **Accounting copy closed:** `apps/arkscope-web/src/i18n/resources/en/settings.ts:16` uses "Accounted usage"; `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts:16` uses "已計入容量". Neither implies a fee. The locale keys and byte accounting are unchanged; `SecResearchPanel.test.tsx:179` checks the English label with actual usage, and `:436` checks the Chinese label while rejecting the old fee wording.

# Issues

- Critical: none.
- Important: none. The original I1 acceptance blocker is resolved for this revision.
- Minor: none remaining within R1; M1/M2 are resolved rather than deferred.

# Evidence Checked

- **Behavior RED:** `task-4/r1-red-behavior/command.json:11` records exit 1. `output.log:467` demonstrates the erroneous 64px icon width; `:479` / `:508` show ID-first ordering; `:539` shows absent height limits; `:556` / `:568` show the accounting-copy failures. `output.log:586` records 7 failed / 37 passed. These are relevant assertion failures, not reliance on the initial fixture-path error described in the handoff.
- **Type RED:** `task-4/r1-types-red/command.json:9` records exit 2. `output.log:5` and `:6` contain the two expected TS2322 null-to-array errors for the filings/facts typed fixtures. This substantiates the original type-contract finding without inventing a runtime failure.
- **Hashed GREEN:** `task-4/r1-commit-full/output.log:48309` / `:48310` records 121 files / **1737 tests passed**; `r1-commit-full/command.json:8` records exit 0. The focused owners within that full run passed with 39 panel tests (`output.log:30293`) and 5 API tests (`:45463`). Relative to the prior 1729 total, the diff adds seven panel cases and one API case, with no assertion deletions unrelated to the corrected copy.
- **Typecheck/i18n GREEN:** `task-4/r1-commit-typecheck/command.json:9` and `r1-commit-i18n/command.json:9` record exit 0; their raw logs show the expected commands. I18n remains 37 candidates, 20 signatures, zero debt, and 20 existing allowlist entries (`r1-commit-i18n/output.log:5`). Command metadata retains isolated HOME, Asia/Taipei timezone, and the TCP/DNS-denying preload.
- **Source/evidence identity:** ran read-only SHA-256 checks on exactly the seven scoped frontend files and six final command/log artifacts. All 13 digests match the full values archived at `task-4-report.md:336` and `:385`. This verifies current source/evidence identity against the handoff; no independent git-tree reconstruction or suite rerun is claimed.
- **Parent browser evidence:** inspected `browser-r1/browser/results.json`, which records all four locale/viewport runs with empty error lists, eight contained arrow rectangles, and concept/value-first headers. Inspected `browser-r1/browser/zh-Hant-1280-catalog.png` and `browser-r1/browser/en-390-facts-first.png` for the previously demonstrated visual defects. The parent reports its table-height <=600 assertion also passed; the results JSON does not serialize a numeric height, so that measurement remains parent-owned evidence, supported here by the bounded CSS, DOM regression, and screenshot inspection.

# Review Boundaries

- Read the frozen R1 diff once. Tool output clipped only the panel-test segment corresponding to new lines 75..130; recovered that segment from the frozen diff, not the changed source file. No other changed-file content was reopened.
- Named outside checks were limited to evidence risks: whether RED failed for the intended reasons, whether GREEN artifacts match the reported source hashes, and whether parent browser evidence closes the visual findings. No new outside product-code reads were required.
- No tests, browser automation, agents, live/provider calls, production data/config/token access, git commands, installs, or servers were run. Source hashing was read-only; no new noise is attributed to R1 without evidence against the retained baseline.
- The sole write is `task-4-r1-review.md`. Product files, index, branch state, and the implementer's report were not modified.

# Assessment

**Approved for the scoped Task 4 R1 gate.** The fixes address the demonstrated causes with narrow code changes and meaningful regressions, and the archived test/hash and parent browser evidence are consistent with the reviewed revision. This closes the prior Task 4 findings without claiming complete SEC release acceptance.
