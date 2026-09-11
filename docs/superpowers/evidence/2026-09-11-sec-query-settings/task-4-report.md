# Task 4 Frontend Handoff

Initial handoff: **ready-to-commit**, reported before any git index mutation.
Commit at that checkpoint: **none**. See Authorized Commit below for the subsequent
parent-authorized commit. Parent retains independent review and browser integration.

Worktree: `/tmp/arkscope-listing-sec-macro-convergence`
Branch: `codex/listing-sec-macro-convergence`

Implemented only the independent frontend task from `task-4-brief.md`, the approved
`docs/superpowers/plans/2026-09-11-sec-query-settings.md`, and the SEC substrate spec.
No subagents, dependency installs, providers, live sidecar, production store/config
access, app server, restart, staging, commit, merge, or push. All manual edits used
apply_patch. Backend workers' Python files/tests and parent ledgers/scripts were
left alone. The index was empty at the final read-only check.

## Implementation

- Typed helpers for config GET, budget-only PUT, stored status, filings/facts GET,
  and explicit refresh/resume POST using existing getJSON/sendJSON handling.
  Query lists repeat, CIK/path/query values are URL-encoded, and opaque cursors are
  unchanged. Only refresh receives a 600000ms client wait allowance; ordinary GETs
  retain 15000ms. Lost commands are not automatically retried.
- Real compact, unframed Settings subsection `sec_structured_storage`, registered
  under Market Data with directory/search ownership. No retired SEC event intake,
  future-feature placeholder, ticker guessing, tool activation, or schedule.
- Mount reads config only. Explicit CIK and Load local control issuer reads.
  Catalog/facts tabs show whole records and present source fields. Fact decimals
  remain strings. Catalog links accept only HTTP(S) without URL credentials and
  do not claim retained filing captures. Tables scroll within their container.
- Unknown, unavailable, partial, and observed-empty remain distinct. Coverage,
  gap codes, snapshots, and separate refresh receipts are available. Timestamp
  copy is **Receipt checkpoint**, never a last-success/all-sources-fetched claim.
- Exact decimal/BigInt budget conversion rejects fractional bytes and unsafe
  integers without rounding, accepts budgets beyond 100 GiB, and reopens unaligned
  persisted budgets as exact bytes. Unit switches preserve exact values through
  Number.MAX_SAFE_INTEGER. Reads remain available below usage or on config errors.
- Confirmed budget plus actual persisted/reserved/orphan/charged/remaining bytes;
  null capacity means unknown, not zero. PUT is followed by config readback. Save
  errors and differing confirmed values cannot claim saved; drafts remain intact.
- Cached previous pages stay receipt-pinned. Issuer/filter changes invalidate
  query history and pending reads. Issuer identity separately owns acquisition
  responses, so intervening rereads cannot suppress the current issuer receipt.
  Refresh completion resets pagination using the current filters. A panel-wide
  acquisition lock prevents duplicate POSTs even while the selected issuer changes;
  old responses cannot paint the new issuer. Unmount invalidates pending results.
- Budget confirmation has separate ownership, preventing refresh-driven config
  reads from superseding a save. Dirty budgets survive refresh. All new UI copy
  uses selector-based English/Traditional Chinese resources.

## Verification

All frontend commands ran via the supplied offline runner, with isolated HOME,
`TZ=Asia/Taipei`, and `offline_node.cjs` denying real TCP/DNS. No live browser or
HTTP server was launched. Tests mock fetch or explicitly fixture the new config
GET in existing importOriginal API mocks.

Runner prefix (from the named worktree):

```text
/home/hyl/.virtualenvs/llm_app/bin/python .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py
```

Each artifact below has exact argv/environment/cwd/exit code in `command.json`
and unabridged stdout/stderr in `output.log`, under
`.superpowers/sdd/2026-09-11-sec-query-settings/task-4/<artifact>/`.

| Artifact | Result |
| --- | --- |
| red | API helpers absent: 4 failed; panel module absent caused suite-load failure |
| red-behavior | Render-only panel shell: 27 failed, 2 files |
| green-1 | 26 passed, 1 failed; fixture reused a consumed Response, corrected to fresh responses |
| typecheck-1 | Exit 0 |
| integration-red | 80 passed, 2 expected missing mount/registry failures |
| focused-green | 92 passed, 3 copy/directory inventory failures |
| i18n-1 | Numeric decimal template flagged; changed numeric expression, no allowlist exception |
| focused-green-2 | 95 passed, 5 files |
| i18n-green | Exit 0 |
| full-1 | 1715 passed, 5 failed across 4 files; CSS/resource/directory inventory reconciliation |
| race-red | 23 passed, 3 new race regressions failed |
| race-green | 30 passed, 2 files |
| collateral-green | 60 passed, 4 files |
| confirmation-red | 31 passed, 1 new differing-readback regression failed |
| focused-final | **164 passed, 9 files** |
| full-final | **1729 passed, 121 files**, exit 0 |
| typecheck-final | **Exit 0** |
| i18n-final | **Exit 0**, 37 candidates / 20 signatures / 0 debt / 20 existing allowlist entries |

Final commands appended to the runner prefix:

```text
task-4/focused-final frontend test -- src/secResearchApi.test.ts src/settings/SecResearchPanel.test.tsx src/settings/DataStorageSection.test.tsx src/settings/settingsRegistry.test.ts src/SettingsLocalStorage.test.ts src/SettingsWorkspace.test.tsx src/SettingsCss.test.ts src/ui/classCoverage.test.ts src/i18n/resources.test.ts
task-4/full-final frontend test
task-4/typecheck-final frontend run typecheck
task-4/i18n-final frontend run check:i18n-literals
```

`git diff --check` also passed. Full-suite logs retain existing React act warnings;
no assertions, timezone behavior, or unrelated timestamp display code were weakened.

Baseline reconciliation: 119 files / 1692 passed -> **121 files / 1729 passed**.
Added 32 panel tests, 4 API tests, and 1 DataStorage mount test: **+37 tests**.
Both locales gained **71 SEC keys**: Settings 917 -> 988, total 2860 -> 2931.
The historical pre-Slice-5 count remains 645; the 71 new paths are enumerated as
post-Slice keys instead of changing the historical count. Class inventory tests
now include the actual dedicated stylesheet; none of their coverage is excluded.

## Named Owners

- `secResearchApi.test.ts`: actual URL/repeated-query encoding, budget-only exact
  PUT, HTTP codes, scoped ten-minute allowance, no retry after lost POST.
- `SecResearchPanel.test.tsx`: config-only mount; explicit CIK reads; exact facts;
  state distinctions; exact byte boundaries and units; real accounting; dirty
  drafts; save errors, confirmation errors and differing server values; refresh
  versus resume; stable previous pages and opaque next cursors; issuer/filter
  races; current-issuer refresh after reread; current-filter reset; overlapping
  save/refresh; unconfirmed outcome GET reread; unmount and unsafe links; zh-Hant.
- `DataStorageSection.test.tsx`: real SEC subsection mount alongside the existing
  lifecycle controls, with a fixture-covered config GET.
- Registry, Settings workspace/local-storage, i18n resources, and CSS inventory
  tests: navigation/search, unchanged existing behaviors, exact added inventories.
- Parent: independent task review, fixture-only Playwright desktop/mobile
  screenshots, real-API fixture integration after Tasks 2/3, whole-change checks,
  serialized commit, and canonical evidence/ledger updates.

## Explicit Commit Scope

All paths below are relative to the worktree; stage only these frontend files:

```text
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/secResearchApi.test.ts
apps/arkscope-web/src/settings/SecResearchPanel.tsx
apps/arkscope-web/src/settings/SecResearchPanel.test.tsx
apps/arkscope-web/src/settings/secResearch.css
apps/arkscope-web/src/settings/DataStorageSection.tsx
apps/arkscope-web/src/settings/DataStorageSection.test.tsx
apps/arkscope-web/src/settings/SettingsDirectory.tsx
apps/arkscope-web/src/settings/settingsRegistry.ts
apps/arkscope-web/src/settings/settingsRegistry.test.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/i18n/resources.test.ts
apps/arkscope-web/src/SettingsLocalStorage.test.ts
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/SettingsCss.test.ts
apps/arkscope-web/src/ui/classCoverage.test.ts
```

## Remaining Boundaries

Frontend fixture verification is complete; visual/mobile geometry and real-API
browser verification were explicitly delegated to the parent and are not claimed.
The Task 3 report available at handoff still records pending real-facts wiring
dependent on Task 2. This frontend does not claim full HTTP integration or complete
SEC Research first release. No original-document capture, citations, issuer
resolution, export, model-facing replacement tools, or schedule is introduced.

The panel shows a minimal useful query surface (forms/date/amendments and
concepts/as-of/revisions); typed API helpers support the full approved filter set.
Page history is local to the mounted panel and resets on explicit new selections
or acquisition completion. The ten-minute wait is not server cancellation or a
server wall-clock bound. Acquisition remains blocked panel-wide until the pending
client request settles, even if the input CIK changes; local reads remain usable.

## Authorized Commit

After reviewing this report and the scoped diff, the parent explicitly granted
this worker sole index/commit authorization for the 17 frontend paths listed above.
No source edits were needed during this commit turn.

Commit: **`baecc18c33d3b23ff1f477ae83a2cedf52e7bb0a`**

Subject: `feat(sec-research): add structured-storage settings`

Fresh offline verification used the same runner prefix and environment:

```text
task-4/commit-full frontend test
task-4/commit-typecheck frontend run typecheck
task-4/commit-i18n frontend run check:i18n-literals
```

- Full frontend: **1729 passed, 121 files**, exit 0.
- Typecheck and i18n: **exit 0**. I18n remains 37 candidates, 20 signatures,
  zero debt, and 20 existing allowlist entries.
- Raw command metadata and logs: `task-4/commit-full/`,
  `task-4/commit-typecheck/`, and `task-4/commit-i18n/`, each containing
  `command.json` and `output.log`.
- SHA-256 comparisons confirmed all 17 files stayed unchanged through verification.
- Before staging, the index was empty. Explicit-path staging contained exactly
  the authorized 17 paths; staged whitespace checks passed and staged contents
  matched the tested worktree (`git diff --exit-code -- <17 paths>`).
- Commit readback confirms **17 files, 1015 insertions, 10 deletions**. No backend,
  plan, report, or evidence file entered the commit. The report remains ignored
  handoff evidence, not an eighteenth committed path.
- Post-commit index is empty; no frontend files remain dirty. The parent plan and
  Tasks 2/3 Python changes remain outside the commit. No push or merge occurred.

The parent is independently verifying browser behavior; this commit does not
claim that verification or complete SEC Research release integration.

## Final Hash Handoff

Confirmed after the interrupted report turn: the Authorized Commit section was
already persisted. Only this ignored report was edited on resumption; no product
or index changes were made. All 17 scoped worktree files still match commit
`baecc18c33d3b23ff1f477ae83a2cedf52e7bb0a`; the index remains empty.

Commit tree: `2ca92bf7d798cfae890f2b62718bb7c6c8d47b5a`.

SHA-256 of the 17 committed frontend files (worktree-relative paths):

```text
9c6bcfa9d83acdd843fcd7ffa18014e4ef5def79c87c2519bad64e7b12606196  apps/arkscope-web/src/api.ts
4578de66031938e04d3276d719f28f700aeb6beb4ea2e02e3c8fc899ebfd085d  apps/arkscope-web/src/secResearchApi.test.ts
59580ed4be2cf1245e1e3c0460114bd7cba5ffec4befc19bd4952da33fa51b98  apps/arkscope-web/src/settings/SecResearchPanel.tsx
e3dea43abf9ee8ab91d6e1c0e4b98abb96fbec11d5197a22c9bacc47f59b8397  apps/arkscope-web/src/settings/SecResearchPanel.test.tsx
337dfa4513cb8dbd6f4c213665420d2338c3aef5dcb7ab4fb95c0b4318b79540  apps/arkscope-web/src/settings/secResearch.css
d6ba1d0353670e0a2fb05405f19283f1c73db4ceea094784d8ddfcb374871a82  apps/arkscope-web/src/settings/DataStorageSection.tsx
46998ad73b4526f630fcc1215ad19a613d9905c6f34fccf4c5af392de035bf77  apps/arkscope-web/src/settings/DataStorageSection.test.tsx
346b0274976d8ce13cf59375ad62a9b8a94609ea2ca6c5a41427a0c4c2e3a7d4  apps/arkscope-web/src/settings/SettingsDirectory.tsx
a40b5438b409dfcd109cb761b5ce87112dc7d3916a02c4ff2f8a0e66a15a1fc2  apps/arkscope-web/src/settings/settingsRegistry.ts
48aebb8e6e2e420269326100c53749c0dbd3407066267eacfa4c5a3f9a1764e4  apps/arkscope-web/src/settings/settingsRegistry.test.ts
294d7f03801120c6cd5a70328ffd41e2fd3ae3cd2df0760d15d0c7ff5b25e4d0  apps/arkscope-web/src/i18n/resources/en/settings.ts
c0be2d2d2fad089fedccbf64dd5a763c399670afdf733e8db08257cf08739037  apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
2403e75c40b9bbe4eecc519b0e502892cc87eb5eb0a73da930480a7e4f7a8b1d  apps/arkscope-web/src/i18n/resources.test.ts
e16bea61be6c12f4a7c13b6b5ea3dff59f5084a85540e4863db77e06224f07ef  apps/arkscope-web/src/SettingsLocalStorage.test.ts
7ea678787dc7a91ffc2f09bb4e4380939434ed5109d271e83273fade1f78e948  apps/arkscope-web/src/SettingsWorkspace.test.tsx
e4fe5de37208c6e42397ca15fc514ef7c54b5d6666da568df24e2eaef455399f  apps/arkscope-web/src/SettingsCss.test.ts
fe32d655e67e045ed624b51adbf81acf98fc5e7c4ebad57d39e663fb59374321  apps/arkscope-web/src/ui/classCoverage.test.ts
```

SHA-256 of fresh pre-commit verification artifacts:

```text
88b7721aeb62750cc7c21dd97dda57a01352949fbda1e01b29c6688116a114b4  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-full/command.json
f4c0de99ef4eb7d57746b28eae09fe055d50cfa65b9e3d546042e12e55946383  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-full/output.log
2130f03d2cee0dcdb40d7080a657f78b9163b3de799243a138a9fbed32ce4e24  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-typecheck/command.json
f11cc6b081b601fbfb3d906dd86e989fdf90f9d1b527808504811363f1303fad  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-typecheck/output.log
b35155ad60b46af036320c65f6e0f62f7bc1dee9be2156fff12556b5446dc38e  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-i18n/command.json
f3ff49dfdae1cbb61ff75d18c2a37b6dcf17abe70a175f97b5d46febdc06d0a2  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/commit-i18n/output.log
```

Final handoff is complete. Frozen task review and browser verification remain
parent-owned; this worker has made no further commit or index mutation.

## R1 Accepted Review Fix Wave

Status: **ready-fix**, uncommitted. This is one scoped wave for accepted
`task-4-review.md` I1, M1, M2 and the parent's same-wave accounting-copy correction.
The earlier commit and hashes above describe the original frozen snapshot;
the seven-file working-tree revision below supersedes them for R1 review.
No agents, provider/live-sidecar calls, shared Button edits, new cards, new design,
backend edits, git index mutations, or commits were performed in this wave.

### Corrections

- **I1:** `.sec-pagination > span` restricts the 64px counter minimum to the direct
  page-counter span. Nested `.ui-button-icon` spans no longer match this rule.
- **M1:** both query helper return types and the panel Page alias admit null data.
  Typed fixtures use the actual unavailable shape with `data: null`,
  `observed_at: null`, empty coverage, and `sec_research_not_installed` gap code.
  Existing runtime null handling is preserved and explicitly tested in both tabs.
- **M2:** catalog order is form, filed date, report date, accepted time, primary
  document, catalog URL, accession, filing ID. Facts order is concept, exact value,
  unit, end, start, namespace, filed date, accession, fact ID. No displayed field,
  exact value, full opaque identifier, or catalog link was removed or truncated.
- Both record containers now use `max-height: clamp(360px, 60vh, 480px)` with
  explicit horizontal and vertical auto scrolling. Pagination remains outside
  the scroll container after it in document order; the full 20/40-row page stays
  rendered. The existing table presentation and horizontal scrolling remain.
- Existing `secResearch.charged` copy is now **Accounted usage** / **已計入容量**.
  The underlying `charged_bytes` accounting and locale key inventory are unchanged.

### RED Owners And Evidence

Named owners in `SecResearchPanel.test.tsx`:

- `limits pagination counter sizing to the counter, excluding button icon wrappers`
  applies the real adjacent stylesheet to the real rendered Button hierarchy and
  checks computed styles. RED found 64px on both nested icon wrappers.
- `puts readable catalog fields before complete opaque filing IDs` and
  `leads facts with concept value unit and end while retaining every field and full ID`
  assert exact header and full cell order using realistic 64-character identifiers
  and the exact `1234567890123456789.123` value. Both were RED for hash-first order.
- `bounds the Catalog/Facts table viewport with both scroll axes and pagination outside`
  checks the computed max-height/overflow properties, full page row counts, and
  pagination's location outside and after the table. RED found no height cap.
- `shows an actual unavailable-null Catalog/Facts response without observed-empty rows`
  verifies both live-shaped null fixtures remain unavailable, gap-bearing, rowless,
  and non-pageable rather than observed-empty. Existing runtime behavior passed.
- Existing mount/accounting and Traditional Chinese owners were extended for the
  corrected copy; both failed before the resource change.

Named type owner in `secResearchApi.test.ts`:
`admits and preserves unavailable null-data envelopes for both stored queries`.
RED typecheck produced exactly two TS2322 errors assigning null to the original
array-only helper return types. Runtime GET preservation already passed; this
finding was a type-contract correction, not an invented runtime failure.

All runs use the supplied offline runner prefix documented above, isolated HOME,
`TZ=Asia/Taipei`, and TCP/DNS denial. Raw files are under `task-4/<run>/`, each with
`command.json` and `output.log`:

| Run | Result |
| --- | --- |
| r1-red | 39 passed / 5 failed; initial CSS fixture path was transformed by Vite into a non-file URL, corrected before product edits |
| r1-types-red | Exit 2; two expected null-to-array TS2322 errors |
| r1-red-behavior | 37 passed / 7 expected assertion failures, 2 files |
| r1-focused-green | **172 passed, 9 files**, exit 0 |
| r1-typecheck-green | **Exit 0** |
| r1-i18n-green | **Exit 0**; 37 candidates, 20 signatures, zero debt, 20 unchanged allowlist entries |
| r1-full-green | **1737 passed, 121 files**, exit 0 |

Final commands appended to the same runner prefix:

```text
task-4/r1-focused-green frontend test -- src/secResearchApi.test.ts src/settings/SecResearchPanel.test.tsx src/settings/DataStorageSection.test.tsx src/settings/settingsRegistry.test.ts src/SettingsLocalStorage.test.ts src/SettingsWorkspace.test.tsx src/SettingsCss.test.ts src/ui/classCoverage.test.ts src/i18n/resources.test.ts
task-4/r1-typecheck-green frontend run typecheck
task-4/r1-i18n-green frontend run check:i18n-literals
task-4/r1-full-green frontend test
```

Scoped `git diff --check` passes. Relative to the prior 1729-test frontend result,
this wave adds 7 panel cases and 1 API case: **+8 = 1737**, with no new test files
and no weakened/deleted assertions. Locale key counts remain unchanged.

### R1 Scope And Hashes

Only these seven existing Task 4 frontend files changed; this report is ignored
handoff evidence. No index or commit authorization is assumed for the revision.
SHA-256 of the ready-fix files:

```text
9109aa7c965e52fceff58a50a2ac168aab4e40723e180a70ea01fe88ff085c5e  apps/arkscope-web/src/api.ts
1e4c36e8b8f346f75addacafde9a7cba6b46e6cf835e8796f577e45d3a24382d  apps/arkscope-web/src/secResearchApi.test.ts
411341e410cb0ecc2f2a2dd11892072c117aab1b4921181c68eab7626b5a22dd  apps/arkscope-web/src/settings/SecResearchPanel.tsx
e03d373d5a3035083a935207a98768612471bd9f46fe6d7772e55b6a48881b47  apps/arkscope-web/src/settings/SecResearchPanel.test.tsx
3b9c4ea39cf8179658ef6b0a56aeb1f12df46c2d004559f130c2e195f67846bc  apps/arkscope-web/src/settings/secResearch.css
28189479400e98581688d84e06f7b819b8bacb8f6daa5202fa7e5b5ccdd0f769  apps/arkscope-web/src/i18n/resources/en/settings.ts
96b796530d4123ba0ac0bb53c270bd8a96d0b8c8a62fde0db8aff1e18f0afdc3  apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
```

The parent owns the real browser rerun and bounding-rectangle assertions for arrow
containment, meaningful first facts columns, and bounded table client height.
These computed-style/DOM tests do not claim pixel-geometry verification. No live
browser, sidecar, or App was started by this worker. R1 is ready for parent review.

## R1 Authorized Commit And Final Handoff

After the parent verified the R1 report and granted sole index/commit permission
for these seven files, this worker committed only that reviewed scope.

Commit: **`c6e2e435970c47252970767c9e40300f79ddba23`**

Tree: `f2ebe7b3ee2aaaefc165caba80b1266991a144d0`

Subject: `fix(sec-research): correct storage settings layout and query types`

No product edits were made during this commit turn. The seven SHA-256 values in
R1 Scope And Hashes above were rechecked before verification, after verification,
and against the committed worktree. They are unchanged and identify this R1
commit's frontend contents. The staged and committed path sets were both checked
against the exact seven-file allowlist. The full staged diff was read;
whitespace checks passed; staged contents matched the tested files.

Fresh verification (same supplied offline runner, isolated HOME,
`TZ=Asia/Taipei`, and TCP/DNS-denying preload):

```text
task-4/r1-commit-full frontend test
task-4/r1-commit-typecheck frontend run typecheck
task-4/r1-commit-i18n frontend run check:i18n-literals
```

Results: **1737 tests passed in 121 files**, typecheck exit 0, i18n exit 0.
I18n retains 37 candidates, 20 signatures, zero debt, and 20 existing allowlist
entries. These run directories each contain exact command/environment metadata
and full raw output.

SHA-256 of the pre-commit verification artifacts:

```text
cc7785ee743633ba79e6a52178fd92746bbaa7461d996f836bc5208b4abc2584  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-full/command.json
7844e569529978ffd04ef0cf8e025a8db5ad66c38350bc1c1070bbdb4cefb8f6  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-full/output.log
1f0e1ddd287b5b017c6a41a0f0492cb58416631609c42f34134d922664537a44  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-typecheck/command.json
f11cc6b081b601fbfb3d906dd86e989fdf90f9d1b527808504811363f1303fad  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-typecheck/output.log
52dd7244c80cac6491546dfc0277afc0bbb965f94aec3cc2063627591800a1d8  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-i18n/command.json
f3ff49dfdae1cbb61ff75d18c2a37b6dcf17abe70a175f97b5d46febdc06d0a2  .superpowers/sdd/2026-09-11-sec-query-settings/task-4/r1-commit-i18n/output.log
```

Commit readback: **7 files changed, 112 insertions, 13 deletions**. No Task 3
backend/fix files, shared Button code, plan, or evidence files were committed.
The index is empty and the scoped frontend files are clean. The parent-owned
plan remains dirty and was left untouched. No push or merge occurred.

This ignored report append is the final worker handoff. The parent owns the
post-commit browser geometry assertions and all-workflow rerun; those results
are not claimed here.
