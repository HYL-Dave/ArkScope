# SQLite Evidence Review Follow-Ups

Recorded 2026-09-11 in `/tmp/arkscope-listing-sec-macro-convergence`.
Scope: Task 1 evidence only. No production code, lifecycle policy, database,
configuration, token, runtime, or sealed archive was changed.

## SQLite Reproduction

Source: [sealed SQLite research](../2026-09-10-pre-release-cleanup-audit/current-journal-cleanup/sqlite-research.md),
especially "Replacement Variants And Single-Clause Controls". The new
[diagnostic](sqlite_upsert_repro.py) preserves all five archived cases, each
using a separate `sqlite3.connect(":memory:")` connection that is closed after
measurement. The schema-level replacement policy is intentionally absent in
the `INSERT OR REPLACE` variant, exactly as in the archive.

Actual command, executed with `login=false` from the worktree:

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B /tmp/arkscope-listing-sec-macro-convergence/docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py
```

The complete stdout is retained unchanged in
[sqlite-upsert-result.json](sqlite-upsert-result.json). Process exit: **1**;
classification: **defect_reproduced**. The explicit interpreter reported Python
3.10.12 and SQLite 3.37.2, source ID:

```text
2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1
```

| Case | Table count | Indexed count | Full integrity check | Quick check |
| --- | --- | --- | --- | --- |
| upstream_replace_duplicate | 2 | 3 | wrong # of entries in index sqlite_autoindex_v0_1 | ok |
| insert_schema_replace_duplicate | 2 | 3 | wrong # of entries in index sqlite_autoindex_v0_1 | ok |
| insert_or_replace_duplicate | 2 | 3 | wrong # of entries in index sqlite_autoindex_v0_1 | ok |
| replace_single_clause | 2 | 2 | ok | ok |
| insert_single_clause | 2 | 2 | ok | ok |

All five reported `journal_mode=memory`. Counts use the archived queries
`SELECT count(*) FROM v0` and `SELECT count(*) FROM v0 WHERE c2>8`.
The diagnostic also verifies actual table rows through `NOT INDEXED` and sets
`temp_store=MEMORY`; neither changes the archived DDL or UPSERT statements.
Both integrity pragmas retain every returned message, not just the first.

Classification is behavioral; engine version/source ID are provenance, never
a patch-level verdict:

- **0 / all_pass:** all five cases have the expected two table rows, counts
  2/2, full integrity `ok`, quick check `ok`, memory journal and engine metadata.
- **1 / defect_reproduced:** both single-clause controls pass, every reproducer
  is either healthy or has the exact archived signature, and at least one has
  counts 2/3 plus the archived index-entry integrity error and quick check `ok`.
- **2 / inconclusive:** any probe error, missing case/measurement, unexpected
  observation, or failed single-clause control. This takes precedence even if
  another case reproduces the defect. Unsupported SQL is not treated as success.
  Arguments are rejected before opening SQLite; the script has no database-path
  argument. Missing isolation flags also produce a structured exit-2 report.

A different runtime's negative or inconclusive output must be retained as
observed. Do not modify SQL or classification to match this recorded result.
The scratch task report preserves standard-library classification/CLI tests,
including version-independent 0/1 decisions and inconclusive-control precedence.

This proves only the behavior of the explicit clean process. It does not
identify the running App's interpreter, inspect any user's database, establish
local WAL behavior, or certify future SEC ingestion. No App import, provider or
network call, upgrade, repair, install, restart, merge, push, or commit occurred.

## Audit Directory Distinction

The parent verified the main audit directory at `30bb31c7`. A read-only
`git ls-tree -r --name-only 30bb31c7 -- src/audit` in this worktree independently
listed **four** tracked old files:

- `src/audit/__init__.py`
- `src/audit/ibkr_news_catchup_audit.py`
- `src/audit/sa_article_reconciliation.py`
- `src/audit/universe_retirement.py`

The isolated worktree's `src/audit` is absent, confirmed by directory lookup.
That absence is not evidence that the main checkout has merged cleanup and is
not authorization to delete its tracked files. No main-checkout deletion or
untracked-artifact inspection was performed. Whole-audit cleanup and actual-store
disposition remain separate open work.

## Existing Execution-Date Policy

The [September 8 completion plan](../../plans/2026-09-08-lifecycle-investigation-completion.md#verification-in-progress),
lines 91-97, already explicitly separates non-action-changing `limitations`
from blocking `unresolved_conditions`. An unknown exact event date can remain
visible in the finding and human receipt without inventing an effective date;
execution still requires the user's explicit date selection. Genuine identity,
OTC, or contrary-trading uncertainty remains blocking. This is an existing
approved policy, not a new follow-up relaxation or unresolved omission.

Current owners were read, not executed by this worker:

- `tests/test_lifecycle_investigation_findings.py::test_unknown_exact_date_is_a_visible_limitation_not_a_material_conflict`
  covers both the unknown-date limitation and the blocking OTC uncertainty.
- `tests/test_lifecycle_investigation_review.py::test_unknown_event_date_is_explicit_and_requires_an_attended_execution_date`
  rejects missing execution dates, accepts explicit attended dates, and preserves
  `effective_date=None` separately from the selected execution date.
- `tests/test_lifecycle_investigation_routes.py::test_current_confirmation_rejects_unknown_fields_dates_and_coerced_acknowledgements`
  rejects invalid dates and malformed confirmation fields.

Parent-supplied verification update (not executed or independently verified by
this worker): the Task 2 initial absence RED had 2 failures and 280 passes,
including three unchanged date/transition/review files. The final Task 2 combined
focus had **447 passes in 32.38 seconds**, with XML at `scratch/task2-green.xml`.
The parent also reported an inverse check with 2 failures and 1 pass, restoration,
and a rerun in progress. No completed inverse-rerun result is claimed here.
Independent review and staging remain parent-owned and pending.

## Archive Preservation And Review Gate

The sealed `sqlite-research.md` SHA-256 was recorded before implementation:
`170fd68b2dfe84b8fde89dd76fb763c2810c0ee465b218f50e25b058a03f109c`.
The old archive remains sealed; the executable and actual output are additive
evidence in this new directory. Independent parent review must verify exact SQL,
memory-only targets, fail-closed classification, and reproduction instructions
before staging. No independent review is claimed by this worker.
