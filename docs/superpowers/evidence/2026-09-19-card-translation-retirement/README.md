# Card Translation Scope Correction

Date: 2026-09-20. Branch: `codex/spark-retirement`.
Preservation baseline: `544d8dfd`, based on master `52037620`.

## Binding Scope

The user explicitly clarified: keep card translation; remove Spark execution
and its generated results. Clearing all translation records is also permitted.
That permission does not include original cards, execution receipts, saved
reports, Research conversations, translation settings or the feature's schema.

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
DELETE FROM main.ai_card_translation_versions;
UPDATE main.ai_card_runs SET translations_json=NULL
WHERE translations_json IS NOT NULL;
```

It preserves the table, index, embedded column, sequence state, all model-route
and runtime rows, original card contents, receipts and Research. Old embedded
translations can lack model provenance, so the approved all-translation-results
scope avoids guessing which model produced them. It does not erase original
Spark provenance on unrelated historical records.

Preflight rejects changed translation schema, unexpected owned objects,
triggers on written tables and external references that could cascade. One
transaction checks integrity/FKs before and after, unchanged schema/settings/
originals/sequences, and rollback on failure. Counts are reported; content and
credentials are not dumped. Repeating an already empty cleanup is a no-op.

The entry point requires `--clear-all-translations --writers-stopped` and
opens only the named main profile with `mode=rw`. The old `--apply` command
is no longer accepted. The stop flag is an operator assertion, not a replacement
for checking App/native-host/collector writers and DB handles. No production
apply has run. Private translation YAML/environment keys are retained.

## Verification

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
- Full backend, frontend, typecheck/build and desktop acceptance of this
  corrected revision are pending. Prior all-feature-removal results are not
  acceptance of the clarified scope.

The first focused run had 118 passes and one test-harness failure: SQLite's
authorizer reported virtual PRAGMA schema preparation as apparent metadata
writes. The guard now checks executed SQL, exact changed-row count and
unchanged full schema; it does not ignore writes to product tables.

## Historical Runs And Operational Gate

The earlier unmerged full-feature-removal revision `033c4515` passed
11,266 backend / 12 skipped and 1,830 frontend / 124 files. Those tests proved
the mistaken removal was internally consistent, not that it met user intent.
The correct preservation baseline `544d8dfd` had passed 11,400 backend /
12 skipped and 1,854 frontend / 124 files. The corrected branch must be rerun.

Master remains `52037620`; the App was running at the last check. No merge,
App restart, production translation deletion, backup deletion or push occurred.
The user alone pushes. The stopped-writer gate remains for cleanup/activation.

The existing old root-level June/July backup inventory is 29 files including
sidecars, 13,324,488,704 logical bytes. That previously approved, named inventory
does not include recent `data/backups/`, archives, current databases or their
WAL/SHM files. It is separate from translation-record cleanup.

The unaccepted fundamentals/source-workflow branch is not merged or deleted.
Its source/tool/research audit is committed at `5c123120`. Main's pre-existing
untracked documentation and dirty/unknown worktrees remain untouched. Only the
previously verified merged, unattached `codex/research-output-boundary` branch
was deleted in the preceding work; this correction removes no further branch.
