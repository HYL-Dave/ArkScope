# Task4 Settings Filing Reader

Status: implementation and frontend gates complete; parent independent review pending.
Base: 64a25c34. Only scoped frontend/API/resources/tests are owned here. Parent
owns browser helpers, actual HTTP/service/store Playwright, backend and census.

## Browser Selectors And Workflows

- Reader root: `.sec-document-reader`, named region `secDocument.title`.
- Catalog row open: icon button `secDocument.open` (English `Read filing`), inside
  the primary-document cell. Existing table columns/order and variants retained.
- Reader close: `secDocument.close` (`Close reader`). Original row metadata is
  `.sec-document-identity`; `.sec-document-text` contains exact plaintext per passage.
  Opening focuses `.sec-document-heading h4[tabindex="-1"]` and scrolls it into
  view. Closing restores the exact clicked row button only while it is connected.
- All new keys are under `settings.secDocument` in both en and zh-Hant resources.
- Document select: `document` (`Document`), options `primary` plus actual observed
  `file:<name>` values. Section select: `section` (`Section`), whole-document value
  empty string, actual opaque section IDs otherwise. Section selection performs GET.
- Literal input: `search` (`Literal search (case-sensitive)`); submit icon button
  `searchAction` (`Search passages`), uses unchanged input, not regex/trimmed text.
- Whole-document command: `whole` (`Whole document`), explicit fallback drops both
  section/query and follows stored `text_start_cursor` with unchanged max_chars.
- Passage pager: `previous` / `next` (`Previous passage page` / `Next passage page`).
  Index pager: `indexPrevious` / `indexNext` (`Previous index page` / `Next index page`).
  Index pages remain separately accessible while reading passages/searching.
- Current command: `currentAction` (`Read current capture`), always GET without pin.
  Current observation label `current` (`Current at read`); pinned label `pinned`
  (`Pinned capture`). Capture input `captureId` (`Capture ID`) and command
  `pinAction` (`Open pinned capture`) permit exact pinned reopening.
- Closing/reopening a row remembers its last successfully read capture within this
  mounted Settings panel, visibly pinned. Switching current is always explicit.
- Acquisition: `acquire` (`Acquire primary document`), POST primary only on click.
  Unknown outcome: `unknownOutcome` (`Acquisition outcome unknown. The server may
  still be running.`); `reread` (`Reread stored document`) is GET-only. No auto POST.
  Unknown state survives close/reopen within this Settings panel. While unknown,
  reread checks current `primary` without capture_id; the pin command remains
  independently available. Unknown is not erased by an ordinary stored GET.
- Citation anchor: `source` (`Source citation`); details: `citation` (`Citation metadata`).
- Secondary unavailable capture keeps the observed directory choices and its
  observation context `directoryCapture` (`Directory observed with capture`).
  Passage/section state for the previous document is not shown as secondary text.
- Long-directory fixture: open fixture1, acquire explicitly if missing, use index
  Next to reach later choices; passage navigation must not consume index cursors.
- Unknown section response: parent mutates actual outgoing section request operands
  to reach the real unknown-section envelope; no fallback GET until Whole document.
  Section remains the published select, not an editable input. It offers actual
  index entries, not invented form templates.

## Verification

All commands run from `/tmp/arkscope-listing-sec-macro-convergence` with:

`/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-document-reading/run_checks.py NAME frontend ARGS`

The helper records exact expanded commands/environment/time/output in each unique
NAME directory (`command.json`, `output.log`). Installed Node22 and linked modules,
offline Node guard, isolated HOME, TZ=Asia/Taipei; no installation/network/provider.

| NAME | ARGS | Result |
| --- | --- | --- |
| task4-red-reader-api-01 | `test -- src/secDocumentApi.test.ts src/settings/SecDocumentReader.test.tsx` | 21 failed: missing API functions and missing per-row Read filing command |
| task4-green-reader-api-01 | `test -- src/secDocumentApi.test.ts src/settings/SecDocumentReader.test.tsx src/settings/SecResearchPanel.test.tsx src/secResearchApi.test.ts` | 66 passed / 4 files |
| task4-red-boundaries-02 | `test -- src/settings/SecDocumentReader.test.tsx` | 19 passed / 3 failed: lost-POST state disappeared across reopening and superseding GET; one proposed editable-section test did not match the retained select |
| task4-green-boundaries-02 | `test -- src/secDocumentApi.test.ts src/settings/SecDocumentReader.test.tsx src/settings/SecResearchPanel.test.tsx src/secResearchApi.test.ts` | 70 passed / 4 files |
| task4-precommit-frontend-01 | `test` | 1759 passed / 4 failed / 123 files: two CSS-class coverage tests, two exact resource inventory tests |
| task4-precommit-typecheck-01 | `run typecheck` | exit 0 |
| task4-precommit-i18n-01 | `run check:i18n-literals` | exit 0; 37 candidates, 20 signatures, 0 debt signatures, 20 allowlist |
| task4-green-inventory-css-03 | `test -- src/SettingsCss.test.ts src/ui/classCoverage.test.ts src/i18n/resources.test.ts` | 27 passed / 3 files |
| task4-red-focus-04 | `test -- src/settings/SecDocumentReader.test.tsx` | 23 passed / 1 failed: activeElement remained body instead of reader heading |
| task4-green-focus-04 | `test -- src/secDocumentApi.test.ts src/settings/SecDocumentReader.test.tsx src/settings/SecResearchPanel.test.tsx src/secResearchApi.test.ts src/SettingsCss.test.ts src/ui/classCoverage.test.ts src/i18n/resources.test.ts` | 99 passed / 7 files |
| task4-precommit-frontend-02 | `test` | 1765 passed / 123 files; 0 failed, 0 skipped |
| task4-precommit-typecheck-02 | `run typecheck` | exit 0 |
| task4-precommit-i18n-02 | `run check:i18n-literals` | exit 0; 37 candidates, 20 signatures, 0 debt signatures, 20 allowlist |

The editable-section proposal was dropped after parent confirmed its real-request
operand fault can exercise unknown sections without adding another UI feature.
That test now checks forwarding opaque observed section IDs and explicit fallback;
it is not claimed as RED evidence for new editable-section behavior. Existing 45
catalog/facts/API tests are unchanged. Normal i18next languageChanged stdout remains;
focused GREEN logs contain no stderr/Warning/Error/FAIL. Full final frontend output
contains 930 React act-environment warnings in unchanged tests (including DataTable
and overlays), not claimed pristine. Baseline1738 + new reader24 + API3 =1765;
no test removals/skips. The 31 new keys are exhaustively asserted per locale;
Settings988->1019 and total2931->2962. Historical pre-Slice counts645/35/680 remain
unchanged by enumerating the new post-Slice keys, not relaxing those assertions.

## Self-Review

- Independent generation ownership: initial index/text chain, index next, literal
  filters, document selection, current/pinned lookup, close/unmount, POST completion.
- POST uncertainty is tracked per filing across reader mounts; known completion
  never replaces a newer reading generation. Lost POST never automatically retries.
- Current failed refresh clears displayed text; prior successful capture remains
  explicitly reopenable by Capture ID and remembered row pin.
- Index context is separate from passage responses, bound to its own locator;
  uncaptured secondary keeps navigation but no old text or section claim.
- Full caller-visible acquisition errors use unknown for transport/5xx, definite
  request rejection for typed <500. Acquisition is primary-only by contract.
- No backend contract defects identified. No backend, provider, parent helper,
  production config/DB, environment, install, restart, merge, push changes.
- Fixed missing `.sec-document-attempt` selector caught by full class-coverage tests.
- Fixed unknown POST state loss after reopen/newer GET with focused RED evidence;
  existing captured/pinned reread explicitly asserts no capture_id on its index GET.
- Parent actual geometry established below-fold opening (desktop1235..1255 vs960,
  mobile929..948 vs844). Added focus/scroll and connected-opener return without
  introducing a modal/focus trap; focused RED/GREEN evidence above.

## Browser Evidence

Parent owns and ran the actual HTTP/service/store/CaptureStore/PublicSourceReader
checks with generated transport bodies at fixture-only Vite8457. No browser helper
was edited by this worker; no canned product response path exists.

- Parent reported `parent-reader-browser-03` passed en/zh-Hant desktop/mobile,
  70 HTTP observations per viewport, including existing-pin lostPOST->current GET.
- `parent-reader-browser-04` retained all document workflows and 13 passage citation
  checks per viewport, but proved the opening geometry defect subsequently fixed.
- Worker visually inspected parent04 `en-1280-reader-passages.png` and
  `zh-Hant-390-reader-index.png`: compact unframed Settings reader, contained
  controls, wrapping full IDs, independently bounded catalog/text scrolling; no
  incoherent overlaps. Those screenshots alone did not verify initial focus/scroll.
- Parent is verifying final heading-visible/focus assertions against the stable
  focus implementation. Final backend/census/archive/whole-change review remain
  parent responsibilities, not completion claims of this report.

## Files And Scope

1. `apps/arkscope-web/src/api.ts`: exact typed document GET/POST helpers.
2. `apps/arkscope-web/src/settings/SecResearchPanel.tsx`: row open/close, original
   selection, in-panel remembered pins and per-filing acquisition uncertainty.
3. `apps/arkscope-web/src/settings/SecDocumentReader.tsx`: bounded reader state/UI.
4. `apps/arkscope-web/src/settings/secResearch.css`: scoped bounded layout/focus.
5. `apps/arkscope-web/src/i18n/resources/en/settings.ts`: 31 reader keys.
6. `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`: matching31 keys.
7. `apps/arkscope-web/src/settings/SecDocumentReader.test.tsx`: 24 cases.
8. `apps/arkscope-web/src/secDocumentApi.test.ts`: 3 API cases.
9. `apps/arkscope-web/src/i18n/resources.test.ts`: exact new-key inventory and
   post-Slice enumeration; historical constraints preserved.

The report/check artifacts remain in ignored `.superpowers` for parent archive;
only the nine source/test paths above are staged under sole-index permission.
No product source edits occurred during the final full frontend/typecheck/i18n run.
`git diff --check` and `git diff --cached --check` passed.

Commit: `f53a87a4 feat(settings): add capture-pinned SEC filing reader`.
Nine files; 695 insertions, 8 deletions. No unrelated or parent helper changes.

## Limits

Remembered pins and unknown-acquisition indicators last for this mounted Settings
panel, not across App restarts; explicit capture-ID GET supports durable reopening.
Unknown outcome remains conservative after ordinary GET because a stored capture
alone does not identify the lost POST attempt. No automatic POST retry or new
history endpoint. Independent Task4 review and final integration gates belong to
parent. No unresolved implementation/HTTP contract defects identified.

## Fix Round1: I1 / I2 / I3

Read the complete `task-4-review.md` and unchanged reviewer probe
`task4-review-probe/pending-reopen.test.tsx`; all three Important findings reproduced
before production edits. No reviewer probe or parent helper was changed.

- I1: per-filing uncertainty is now controlled React state in SecResearchPanel,
  not a ref plus mount-time reader copy. A definite complete/failed HTTP200 or
  HTTP403 rejection clears uncertainty in a pending-close-reopened reader without
  replacing its newer search/passage generation. Tests also keep genuinely lost
  POSTs unknown/GET-only, leave ordinary pending rereads unknown, and prevent
  another filing's completion from clearing the active filing's uncertainty.
- I2: primary alias selection reuses the observed pin only if capture+filing match
  the directory context and the capture's resolved document matches its recorded
  `file:<primary_document>` binding. A/B and A/failed-latest each have direct and
  missing-secondary variants; all preserve A. Explicit current GET still returns
  B/unavailable as appropriate. Captured nonprimary control never lends its pin
  to primary. The selected filing row is not used as alias authority.
- I3: section options retain all loaded capture-bound index pages independently
  of Index Back. Test asserts actual select.value and selectedOptions label,
  preserved text, outgoing section/literal/cursor/pin, cached index navigation,
  and explicit whole-document clearing of both section and query.

Same runner prefix/cwd/environment as above, unique run directories with exact
`command.json` and `output.log`. Commands and actual results:

- `task4-fix1-red-all-01`: `test -- src/settings/SecDocumentReader.test.tsx`:
  8 failed / 27 passed. I1's three outcomes retained unknown; four I2 variants
  omitted capture_id; I3 displayed empty section instead of item_1a. No import errors.
- `task4-fix1-green-i1-01`: `test -- src/settings/SecDocumentReader.test.tsx -t 'I1|POST|acquisition|late GET'`:
  15 passed / 20 name-filtered skips; no added skip markers.
- `task4-fix1-green-i2-01`: `test -- src/settings/SecDocumentReader.test.tsx -t 'I2|uncaptured secondary|current versus pinned'`:
  7 passed / 28 name-filtered skips.
- `task4-fix1-green-all-01`: `test -- src/settings/SecDocumentReader.test.tsx src/secDocumentApi.test.ts src/settings/SecResearchPanel.test.tsx src/secResearchApi.test.ts`:
  83 passed / 4 files, no failures/skips/stderr warnings.
- `task4-fix1-precommit-frontend-01`: `test`: 1776 passed / 123 files;
  1765 + 11 new cases, no removals/failures/skips. Existing React act warnings remain.
- `task4-fix1-precommit-typecheck-01`: `run typecheck`: exit0.
- `task4-fix1-precommit-i18n-01`: `run check:i18n-literals`: exit0,
  candidates37/signatures20/debt0/allowlist20, unchanged.

Self-review: uncertainty is keyed by filing, separate from reading generation;
known completion never initiates GET in another/reopened reader. Alias matching
checks capture metadata rather than current catalog or a nonprimary basename.
Sections reset only on actual directory/capture rebinding, not index position.
No UI selectors/resources/CSS/API/backend contracts changed. Only
SecDocumentReader.tsx, SecResearchPanel.tsx and SecDocumentReader.test.tsx changed
in this fix; source held stable for the final frontend/typecheck/i18n runs.
Parent's disjoint plan edit remains untouched/unstaged. Parent owns extended
actual-store browser alias/index workflows, repeat final gates and independent
rereview. No unresolved contract concern; this delta does not claim those gates.
Commit: `02a0fff4 fix(settings): preserve SEC reader state across navigation`;
3 files, 155 insertions / 10 deletions. Scoped cached diff check passed; post-commit
status contains only the parent's pre-existing plan modification.
