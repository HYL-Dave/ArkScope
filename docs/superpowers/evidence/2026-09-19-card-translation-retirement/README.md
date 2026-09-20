# Card Translation Scope Correction

Date: 2026-09-20. Branch: `codex/spark-retirement`.
Preservation baseline: `544d8dfd`, based on master `52037620`.

## Binding Scope

The latest September 20 instruction supersedes the earlier permission to clear
all translation records: keep card translation and subscription usage display;
prepare **Spark-only** cleanup with a backup. Do not close the App or execute
cleanup in this review. Original cards, execution receipts, saved reports,
Research conversations, other translations, settings and schema are protected.

The entire-feature removal at `4125026b` was our interpretation error, not a
user product decision. It was never merged or activated and no production
cleanup ran. This packet retains its path to make the correction discoverable;
it no longer instructs anyone to retire card translation.

## Restored And Retained

- Restore the generic translation task, route, provider/model/effort settings,
  runtime controls, dispatch, errors, cache/version storage, language controls,
  refresh, execution receipts, locales and original feature tests.
- Preserve Spark retirement: no current/eligible option, no direct execution,
  no dedicated translation adapter and no quota hint that re-enables it.
  A historical rejection identity still blocks stale or custom Spark routes.
- Do not silently change a selected model or billing authority. An existing
  Spark route remains visibly invalid until the user selects a supported model.
- Restore the generic fixed-output translation canary and harness tests.
  No live canary or paid call is made by this correction.
- Keep the independent report-file confinement fix at `751b2051` and its
  24 adversarial tests. Earnings observations remain a separate repair and
  scheduling capability, not replaced by SEC fundamentals.
- Preserve the all-task default-route guard from `033c4515`, now including
  the fourth task, `card_translation`. API inventory returns to 223 with the
  explicit translation route, not just a larger count.

## Record-Only Cleanup

`checks/dispose.py` is an explicit offline operator program, never imported
by App startup or a scheduler. The old destructive implementation has been
replaced. The only data writes are:

```sql
DELETE FROM main.ai_card_translation_versions
WHERE model = 'gpt-5.3-codex-spark';
UPDATE main.ai_card_runs SET translations_json=:remaining_languages
WHERE id=13;
```

The UPDATE runs only when run 13's `zh-Hant` content has the same full canonical
SHA-256 as a Spark version for **that run and language**. It removes that key,
not the whole map; NULL is used only when no other language remains. Other
cards' embedded caches are unchanged even if their content matches. Unknown
provenance, a nonmatching value, or identical content also attributed to a
non-Spark model is preserved. Malformed/duplicate-key JSON and numbers that
would silently round while parsing block cleanup before backup or deletion.

It preserves the table, index, embedded column, sequence state, all model-route
and runtime rows, original card contents, receipts and Research. Non-Spark
version rows, including NULL-model rows, remain byte-for-byte unchanged.
It does not erase original Spark provenance on unrelated historical records.

Preflight rejects changed translation schema, unexpected owned objects,
triggers on written tables and external references that could cascade. One
write transaction checks integrity/FKs and exact expected rows, including
unchanged schema/settings/originals/sequences, and rolls back on failure.
Counts are reported; content and credentials are not dumped. Repeating cleanup
changes no source rows, but still requires a new backup destination.

Backup is mandatory, using the existing `src.sqlite_backup.backup_connection`
owner: SQLite's WAL-inclusive backup API, a new non-overwritable destination,
0600 file permissions, and integrity/schema/retained-row verification. The
source read snapshot stays pinned during backup. After acquiring the write
lock, both `data_version` and the inventory must still match; an intervening
writer aborts cleanup. Failure retains the backup and rolls back source writes.
The receipt records the backup path and full file hash, not `archive_created:
False`. Backups contain private profile data and must not be committed.

The entry point requires `--clear-spark-translations --writers-stopped
--backup-path <new-private-file>` and opens only the named main profile with
`mode=rw`. The old `--clear-all-translations` and `--apply` commands are rejected.
The stop flag is an operator assertion, not a substitute for checking App/
native-host/collector writers and DB handles. **No production apply or backup
has run in this review.** Private translation YAML/environment keys remain.

## Independent Read-Only Check

With the App left running, `mode=ro`, `PRAGMA query_only=ON` and a read
transaction observed one version row: run 13 / `zh-Hant` / Spark. No non-Spark
version rows were present at that observation. Both retained representations
are semantically identical. Using sorted keys, UTF-8, `ensure_ascii=False`
and default JSON separators, their full canonical SHA-256 is:

`e9dfed4f5c0490c21359d6982877d58fe201511f8785b49f2923680d36c9a6f9`

That confirms the reviewer's prefix. Compact JSON uses a different hash, so
the script fixes one serialization instead of comparing undocumented prefixes.
No original card/translation text was printed. This observation is not cleanup
authorization; the operator rechecks the actual rows when eventually invoked.

## Usage Display Preserved

The removed `EffectiveProviderSummary.entitlement_hints` field had a generic
name but a Spark-only producer (`_subscription_entitlement_hints`) and a
Spark-only consumer (`hasSparkUsageHint`). Its sole purpose was a model-picker
hint. It was not the account-usage payload and is intentionally not restored.

`codex_account_usage.py`, `oauth_status.py`, `ProviderSection.tsx` and
`oauthAccountUsage.ts` are byte-identical to master `52037620`. The credential
account-usage GET and sync POST routes remain. Bucket IDs/names, seven-day
windows, percentages, reset times, source and observation time are still
displayed. `gpt-reserve` and `codex` are treated as observed usage groups, not
as model IDs or entitlement to execute a model.

## Current Verification

- Focused backend: **147 passed**, including cleanup, translation round trip,
  backup failures, WAL/concurrent-write refusal, Spark admission rejection,
  account usage parsing/persistence and model-catalog isolation.
- The cleanup suite has **24** synthetic cases. Two preservation tests were
  also run against the previous all-record implementation at `1c732eb6`
  (adapting only its old function signature); they produce three expected
  assertion failures, not import/interface failures.
- The API test removes only the Spark result, retains unknown-provenance
  output, and then translates and caches again using a supported-model stub.
- Complete frontend: **1,856 passed / 124 files**. New screenshot-shaped
  cases cover both named groups and ID-only groups, manual sync, and no model
  options added from quota evidence. Only fixtures are used; no live sync or
  paid provider request is made.
- TypeScript and production build pass; the existing large-bundle warning
  remains. The first typecheck rejected the new ID-only test fixture because
  its helper inferred a non-null name; the fixture now uses the real nullable
  `OAuthRateLimitSnapshot.limit_name` contract. No App code was changed.
- No App implementation file changes in this follow-up; only the offline
  operator, tests and documentation change. The previous complete backend run
  below belongs to `b7e1886b`, not to the newly narrowed operator.

## Previous Full Acceptance At b7e1886b

- Focused backend: **119 passed**, including Spark rejection, the preserved
  translation API, original-store behavior, all-task routes, record cleanup
  and the report security boundary.
- Twelve synthetic cleanup tests are now part of the regular backend suite
  through `tests/test_translation_record_cleanup.py`, not only a separate
  operator rehearsal. They check schema/settings/original preservation,
  trigger/FK refusal, rollback, exact data-write scope and writing new
  translations without recreating schema.
- An API integration test seeds a Spark translation and unknown-provenance
  output, clears them, translates again with a supported-model stub, reuses
  the cache, checks the new receipt and proves the original card is unchanged.
- Browser runner `browser_check.py` now checks controls are present, explicit
  translate/cache/refresh work, locale changes make no request, both runtime
  settings survive, and original text stays readable. It uses synthetic
  responses only. All four 1440px/390px and en/zh-Hant cases passed, with no
  horizontal overflow or external request; screenshots were visually checked
  under `/tmp/arkscope-card-translation-preserved-browser/`.
- Three preservation tests fail when run against the previous `0fbea0b5`
  schema-dropping operator, using only in-memory fixtures. They prevent this
  scope error from returning as a supposedly valid cleanup.
- Frozen revision: `b7e1886b7586ec78fe8ac08eae45adc59f0e80a7`.
  Complete backend: **11,437 passed / 12 skipped**, exit 0, **1,799.58s**.
  Command: `/home/hyl/.virtualenvs/llm_app/bin/python -m pytest tests/ -q
  --tb=short --disable-warnings`, with one pytest process and no concurrent
  source edits or other pytest session in this tree.
- Complete frontend: **1,854 passed / 124 files**, **13.84s**. TypeScript and
  production build pass; the pre-existing large-bundle warning remains.
  i18n: 37 candidates, 20 signatures, **zero debt**. Desktop shell: **8 passed**.
- All **1,169** tracked files under `src`, `data_sources`, `tests`, `apps`,
  this packet's `checks/` and `browser_check.py`, and the restored generic
  `2026-09-08-sdk152-fixed-output/live_api_canary.py` have the same pre/post
  fingerprint: `fb00fcabb093ede32a61843afeb18f19ded6e8c42964ffb1edd5ea38bc7854e7`.
  Method: `git ls-files -z <those paths> | sort -z | xargs -0 sha256sum |
  sha256sum`. The worktree was clean after every complete gate.
- Compared with the preserved `544d8dfd` baseline, `src` and `apps` differ
  only in the independent report-file security fix. The 37 additional backend
  cases are its 24 adversarial tests and 13 record-cleanup/API cases.
  Full-run logs: `/tmp/arkscope-translation-preserved-backend.log`,
  `/tmp/arkscope-translation-preserved-frontend.log`, and
  `/tmp/arkscope-translation-preserved-build.log`.

The first focused run had 118 passes and one test-harness failure: SQLite's
authorizer reported virtual PRAGMA schema preparation as apparent metadata
writes. The guard now checks executed SQL, exact changed-row count and
unchanged full schema; it does not ignore writes to product tables.

## Historical Runs And Operational Gate

The earlier unmerged full-feature-removal revision `033c4515` passed
11,266 backend / 12 skipped and 1,830 frontend / 124 files. Those tests proved
the mistaken removal was internally consistent, not that it met user intent.
The correct preservation baseline `544d8dfd` had passed 11,400 backend /
12 skipped and 1,854 frontend / 124 files. The corrected branch has now been
independently rerun as recorded above; the mistaken-removal numbers are not
reused as its acceptance.

Master remains `52037620`; the App was running at the last check. No merge,
App restart, production translation deletion, production backup creation,
backup deletion or push occurred. The user alone pushes. The latest review
explicitly leaves the App running and withholds cleanup authorization.

The existing old root-level June/July backup inventory is 29 files including
sidecars, 13,324,488,704 logical bytes. That previously approved, named inventory
does not include recent `data/backups/`, archives, current databases or their
WAL/SHM files. It is separate from translation-record cleanup and remains
untouched while cleanup is on hold.

The unaccepted fundamentals/source-workflow branch is not merged or deleted.
Its source/tool/research audit is committed at `5c123120`. Main's pre-existing
untracked documentation and dirty/unknown worktrees remain untouched. Only the
previously verified merged, unattached `codex/research-output-boundary` branch
was deleted in the preceding work; this correction removes no further branch.
