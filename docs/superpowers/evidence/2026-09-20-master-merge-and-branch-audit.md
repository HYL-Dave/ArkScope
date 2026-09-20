# Master Merge And Branch Audit

## Scope

The user closed the desktop App and authorized integration and local branch
cleanup. Push remains a manual user action. This operation does not authorize
Spark translation deletion, backup deletion, provider purchases, a SQLite
runtime switch, or adopting the unaccepted fundamentals implementation.

Master advanced from `52037620` to `214b8ae8` by fast-forward, preserving generic
card translation and subscription usage while retiring Spark. The independent
schedule layout fix `bcbe9aeb` was then merged at `097a7cc1`. Its only conflict
was the locale inventory test: both changes produce 1,056 Settings leaves and
2,987 total leaves per language. No backend conflict or implementation change
was introduced by the schedule merge.

## Local Branch Disposition

| Former branch suffix under `codex/` | Original tip | Disposition |
| --- | --- | --- |
| `chatgpt-oauth-auth-repair` | `30bb31c7` | Already an ancestor; branch deleted. |
| `sec-research-integration` | `52037620` | Already an ancestor; branch deleted. |
| `spark-retirement` | `214b8ae8` | Fast-forwarded into master; branch deleted. |
| `schedule-status-layout` | `bcbe9aeb` | Merged at `097a7cc1`; branch deleted. |
| `c15-current-installation-cleanup` | `3132d56e` | Exact patch equivalent of `34a112ba`; archived, then branch deleted. |
| `listing-sec-macro-convergence` | `ba4f2619` | Original WIP already replayed at `3fef138d`; archived, then branch deleted. |
| `research-source-workflow` | `5c123120` | Retained pending the user's archive-or-retain decision; 31 unique commits remain after the schedule merge. |
| `research-session-continuity` | `650130cb` | Retained pending the same decision; design documents only, not a delivered feature. |

Two annotated local tags retain the non-ancestral source commits:

- `archive/2026-09-20/c15-current-installation-cleanup`
- `archive/2026-09-20/listing-sec-macro-convergence`

`git cherry master codex/c15-current-installation-cleanup` reported the C15
commit as patch-equivalent before deletion. The SEC replay and its follow-up
commits are documented in
`docs/superpowers/plans/2026-09-12-sec-research-release-integration.md` and are
ancestors of master. These two source commits were not merged a second time.

Each retired branch worktree was checked clean, detached at its unchanged tip,
and retained on disk. This removes obsolete branch refs without deleting ignored
databases, caches, preview files, or local configuration. No force-removal of a
worktree was used. Existing detached worktrees were also retained, including the
dirty `arkscope-lifecycle-final-audit` tree and historical trees whose git-crypt
filter cannot inspect their status without keys. They are not additional
unmerged branches and have not been certified disposable.

## Verification On The Main Worktree

- Full frontend: **1,859 passed / 124 files**.
- TypeScript check and production Vite build: passed. The existing large-chunk
  warning remains; build limits were not changed.
- i18n literal scan: **zero debt signatures**.
- Related backend tests: **171 passed**, run as one pytest process. Coverage:
  Spark rejection, narrowed translation cleanup, mandatory backup, generic card
  translation, model selection, subscription usage, report-path attacks, and
  SQLite backup behavior.
- Electron navigation/native-host configuration unit tests: **8 passed**.
- Schedule browser checks: **18 combinations** across English/Traditional
  Chinese, widths 390/1,067/1,440, and live/long/macro scenarios. No clipping,
  duplicate running badges, page overflow, browser errors, or external requests.
  Interval application and run-button state also passed. The previous revision
  reproduced 11 geometry issues in the same harness.
- Generic translation browser checks: **4 combinations** across two languages
  and desktop/mobile widths. Translate, cache reuse, refresh, original content,
  save controls, and the model receipt passed with synthetic responses. No paid
  model call was made.
- Actual Electron launch used the main tree's built renderer and real Python
  sidecar, with a fresh private profile, separate database paths, separate native
  host configuration, and all schedulers disabled. Health returned 200; Home,
  Research, Settings, and all 10 schedule rows loaded. No renderer errors or
  external renderer requests occurred. Production database/WAL file identities,
  sizes, and modification times were unchanged. The test App was closed.
- The first Electron script run used an incorrect Traditional Chinese Home
  label and timed out. Correcting the script to the actual label passed without
  a product-code change.

This is not a new full-backend claim. The previously recorded full run at
`b7e1886b` was **11,437 passed / 12 skipped**. Its product backend, dependencies,
and desktop implementation are unchanged in this merge; the narrower cleanup
operator and affected tests were rerun above. No live provider acquisition or
production translation cleanup was performed.

Local browser artifacts:

- `/tmp/arkscope-schedule-status-preview/merged-main-evidence/`
- `/tmp/arkscope-card-translation-preserved-browser/`
- `/tmp/arkscope-master-merge-smoke-jN6xJb/evidence/`

## Push Readiness

The live remote `refs/heads/master` still points at `30bb31c7`; it is an ancestor
of the integrated master. No push was performed. No newly added Git blob over
50 MB was found in the outgoing range, and its changed paths include no `.env`,
`.mcp.json`, production `data/` file, database, backup, private key, or PEM file.
This path check is not a claim that a full historical secret audit was run.

The new merge passes `git diff --check`. A check of the entire outgoing history
still reports pre-existing trailing whitespace in archived evidence/logs and
one historical test EOF; those historical artifacts were not reformatted.

The main tree's two pre-existing untracked documentation items remain untouched
and outside every commit. Local archive tags are not included in
`git push origin master`; publishing them is a separate explicit operation.
