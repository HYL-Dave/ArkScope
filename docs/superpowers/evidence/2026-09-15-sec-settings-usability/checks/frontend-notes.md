# SEC Settings Frontend Evidence

Worktree: /tmp/arkscope-research-output-boundary
Branch: codex/sec-research-integration
Starting HEAD: f36a7b336aad35d49c043547815e0f28dee463ff
Starting tracked status: clean (git --no-optional-locks status).

Approved scope: frontend SEC settings only. No backend, Python, docs, runtime,
Desktop, git index, commits, data directories, credentials, live application,
provider network, or production DB access. No dev-server build/relaunch.

Workflow: use existing worktree and approval; RED-first frontend tests; bounded
product changes; targeted vitest then typecheck, sequential commands only.

Regression targets:
- 300 ms settled filters, latest-only records/status/errors, cursor reset.
- Local GET-only filtering; refresh/resume still explicit POST commands.
- Pending debounce cancellation on navigation, CIK changes, unmount, manual read.
- Generation guards reject late responses after filtering/navigation/unmount/CIK.
- Official SEC link remains; embedded reader action is removed in both locales.
- Independent document, fact, filing citation GET reopening still works.

Consumer audit before removal (apps/arkscope-web/src only):
- getSecResearchDocument / acquireSecResearchDocument: settings reader and its
  dedicated API tests only. Server route from these adapters is GET/POST
  /sec-research/filings/{filingId}/document. Backend routes remain untouched.
- SecDocumentQuery, Entry, Section, Page, Attempt: reader-specific.
- SecDocumentCitation and SecDocumentMetadata: retained for SecCitationRead.
- SecCitationView and getSecResearchCitation: independent research consumers.

Only tests and this external evidence note were edited before the first RED run.

## Results

Commands run from /tmp/arkscope-research-output-boundary/apps/arkscope-web with
/home/hyl/.nvm/versions/node/v22.14.0/bin prepended to PATH. Each invocation used
`bash -o pipefail` and piped stdout/stderr to the named external evidence log.
No test/typecheck commands overlapped; Vitest file parallelism was also disabled.

1. Initial command `node node_modules/vitest/vitest.mjs run ...` did not collect
   tests: dependencies are hoisted at repo root. Exit 1 (red-ui.log). Neither
   node_modules symlink nor dependencies were changed.
2. RED UI (red-ui-tests.log), exit 1: 13 failed, 58 passed, 71 total.
   Expected failures: no settled filter GET, stale cursor chain, tab switching
   after filter edit did not reload, and reader buttons remained in both locales.
   All 11 independent citation tests passed before the product change.
3. RED locales (red-locales.log), exit 1: 1 failed, 13 skipped.
   Expected failure: obsolete reader's 31 keys still present (1037 vs 1006
   settings keys; 2968 vs 2937 total leaves per locale).
4. GREEN UI (green-ui-tests.log), exit 0: 71 passed, 2 files.
5. GREEN targeted regressions (green-targeted.log), exit 0: 185 passed, 8 files.
   No warnings or errors in the GREEN test output.
6. Typecheck (typecheck.log), exit 0, no diagnostics.
7. `git --no-optional-locks diff --check -- apps/arkscope-web/src`, exit 0.

Exact test/typecheck commands (append `2>&1 | tee <log>` under bash -o pipefail):

```sh
# RED and GREEN UI
node ../../node_modules/vitest/vitest.mjs run src/settings/SecResearchPanel.test.tsx src/SecCitationView.test.tsx --no-file-parallelism --maxWorkers=1

# RED locale inventory
node ../../node_modules/vitest/vitest.mjs run src/i18n/resources.test.ts -t "remaining-surface namespace inventory" --no-file-parallelism --maxWorkers=1

# GREEN targeted regressions
node ../../node_modules/vitest/vitest.mjs run src/settings/SecResearchPanel.test.tsx src/SecCitationView.test.tsx src/secResearchApi.test.ts src/secCitationApi.test.ts src/i18n/resources.test.ts src/ResearchEvidenceDrawer.test.tsx src/settings/DataStorageSection.test.tsx src/settings/dataScheduleControls.test.tsx --no-file-parallelism --maxWorkers=1

# Typecheck (only after Vitest completed)
node ../../node_modules/typescript/bin/tsc --noEmit
```

## Changed Paths

All paths below are relative to apps/arkscope-web/src:

- Modified: settings/SecResearchPanel.tsx
- Modified: settings/SecResearchPanel.test.tsx
- Modified: settings/secResearch.css
- Modified: api.ts (reader-only deletions, no changes to shared transport)
- Modified: SecCitationView.test.tsx
- Modified: i18n/resources.test.ts
- Modified: i18n/resources/en/settings.ts
- Modified: i18n/resources/zh-Hant/settings.ts
- Deleted: settings/SecDocumentReader.tsx
- Deleted: settings/SecDocumentReader.test.tsx
- Deleted: secDocumentApi.test.ts

## Review and Handoff

- Explicit Load local still selects/loads a valid normalized CIK; merely typing
  a CIK does not query. After loading, a 300 ms trailing debounce queries local
  records and status. Dates, forms, amendments, concepts, as-of and revisions
  retain their existing serialization. Clearing a filter uses the same path.
- Edits immediately discard pages/cursors, stale reads and errors. The loaded
  issuer remains selected so tab changes can immediately query the chosen view.
- Pending debounces clear on CIK changes, view changes, unmount and explicit
  local reads (including the reread after a refresh receipt).
- In-flight responses are logically cancelled by existing generation/mounted
  guards, not transport-aborted. Existing shared API transport is unchanged.
- Official catalog source links retain href, target=_blank and noopener
  noreferrer. Browser navigation was prevented in tests; no SEC site was opened.
- The full reader implementation, dedicated tests/styles/translations, and
  frontend-only document adapters/types are deleted, not hidden or parked.
- Removed helpers: getSecResearchDocument and acquireSecResearchDocument.
  Removed types: SecDocumentQuery, SecDocumentEntry, SecDocumentSection,
  SecDocumentPage and SecDocumentAttempt.
- Retained: SecDocumentCitation, SecDocumentMetadata, SecCitationRead and
  getSecResearchCitation. SecCitationView product implementation is unchanged.
- GET/POST /sec-research/filings/{filing_id}/document lose their frontend owner.
  Parent independently confirmed sole frontend ownership and owns server route
  deletion and relocation of retained citation HTTP tests. No backend edits
  were made here; tools' direct DocumentService/Queries use stays parent's scope.
- All 11 modified/deleted paths are frontend-owned. Parent's Python changes
  appeared during final status inspection and were neither read nor altered.
- HEAD remained f36a7b336aad35d49c043547815e0f28dee463ff. No index writes,
  staging, commits, dependency changes, or server process changes were performed.
- Residual verification boundary: no browser layout/hand test or build was run;
  parent owns later build/relaunch. Verification was targeted Vitest + typecheck.
- No independent reviewer tool is available in this session; the scoped diff,
  consumer references, lifecycle guards and test coverage were reviewed inline.

## Reviewed Source-Link Label Finish

Parent requested that the primary-document browser route read "SEC original" in
English and "SEC 原文" in Traditional Chinese, with no rendering/control changes.

Changed paths for this follow-up (relative to apps/arkscope-web/src):
- i18n/resources/en/settings.ts: secResearch.catalogUrl value only.
- i18n/resources/zh-Hant/settings.ts: secResearch.catalogUrl value only.
- settings/SecResearchPanel.test.tsx: updated column/link expectations and added
  tooltip plus both-locale header assertions.

The translation key is unchanged; the existing header, title tooltip and
aria-label all resolve through it. No helper or component architecture changes.

Tests were updated before the locale values. Same focused command for RED/GREEN,
from apps/arkscope-web with the same Node PATH and pipefail logging as above:

```sh
node ../../node_modules/vitest/vitest.mjs run src/settings/SecResearchPanel.test.tsx src/i18n/resources.test.ts --no-file-parallelism --maxWorkers=1
```

- red-source-label.log: exit 1, 3 expected label failures, 71 passed (74 total).
- green-source-label.log: exit 0, 74 passed across 2 files, no diagnostics.
- Scoped `git --no-optional-locks diff --check`: exit 0.
- No full frontend suite, typecheck rerun, build, live app, backend, staging or
  commit activity in this follow-up. Parent owns full frontend integration run.

## Source-Link Visibility Polish at 90c8e04c

Started clean on codex/sec-research-integration at
90c8e04c16403d5424bc5d3afc800a8c5630163b. Prior work was already committed by
parent. This follow-up changes only these three frontend files:

- apps/arkscope-web/src/settings/SecResearchPanel.tsx
- apps/arkscope-web/src/settings/SecResearchPanel.test.tsx
- apps/arkscope-web/src/settings/secResearch.css

Filing column order is now form, filed_date, primary_url, report_date,
accepted_at, primary_document, accession, filing_id. Fact columns, labels,
filtering, pagination and acquisition controls are unchanged.

Source anchors now use var(--fg), with the existing var(--panel2) hover
background and 2px var(--accent) keyboard focus outline at a 2px offset.
The 28px minimum hit area is unchanged; the hover area has a 4px radius.

RED-first tests updated both-locale source header positions, the complete
filing header/cell ordering, and cached page expectations. A new regression
checks parsed stylesheet color/hover/focus declarations and real anchor focus.
jsdom cannot reliably resolve custom-property colors or :focus-visible, so
the styling test uses CSSOM declarations, consistent with repo CSS contracts;
it is not a screenshot or measured Electron pixel-contrast test.

Commands (same Node PATH, apps/arkscope-web cwd, pipefail + external tee logs):

```sh
# RED then GREEN; each process finished before the next started.
node ../../node_modules/vitest/vitest.mjs run src/settings/SecResearchPanel.test.tsx --no-file-parallelism --maxWorkers=1

# Only after GREEN completed:
node ../../node_modules/typescript/bin/tsc --noEmit
```

- red-source-visibility.log: exit 1, 5 expected failed tests / 56 passed.
  Failures identify the old sixth-column source link and missing theme,
  hover and focus styling. No product files were edited before RED.
- green-source-visibility.log: exit 0, all 61 panel tests passed.
- typecheck-source-visibility.log: exit 0, no diagnostics.
- Scoped git diff --check: exit 0.
- Final git status shows only the three approved files modified, unstaged.
- No full suite, Python, backend/docs changes, index writes, commits, build,
  live-app access, or process changes. Parent owns the isolated app rebuild;
  this work does not change its running 90c8e04c version.
