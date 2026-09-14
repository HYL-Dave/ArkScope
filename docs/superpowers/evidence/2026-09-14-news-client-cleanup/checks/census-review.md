# C12 Census Comparison Review

Current source: `c30c5bb8`; comparison baseline:
`docs/superpowers/evidence/2026-09-14-news-bootstrap-policy/checks/news-census.json.gz`.
The same scanner ran after focused acceptance and before the final full suite,
without another pytest or agent session. `census-command.json` preserves its
command, exit code and output. Main-worktree untracked names were enumerated;
their contents were not read.

## Summary

| Measure | Baseline | Current |
| --- | ---: | ---: |
| Read source files | 1175 | 1177 |
| Candidates | 4306 | 4306 |
| Uncertainties | 3283 | 3284 |
| New candidate IDs | | 0 |
| New uncertainty IDs | | 17 |
| Coverage reductions | | 4 |
| Dependency metadata changes | | 0 |
| Untracked path changes | | 0 |

Exit **2**, `review_required: true`, is retained. Candidate totals are a review
queue, not confirmed dead code and not deletion authority. There are sixteen
line-location replacements and one new, deliberate test loader. This review
does not close the broader scanner uncertainty queue or change the scanner.

## Every New Uncertainty

IDs below refer to `census.json.gz`. Before/after lines belong to the same path.
The base-to-tip scheduler diff changes imports, obsolete news adapter tuples,
comments and test injection targets; the setting and SQL bodies listed here
are unchanged. `relocation.json` independently proves the current CLI `main()`
body is exact-source identical to the base.

| New ID | Path | Before -> after line | Interpretation |
| --- | --- | --- | --- |
| `python:1a4320fd5f82f4ac` | `src/service/data_scheduler.py` | 1437 -> 1431 | Existing lazy generic adapter import; still needed by SEC research. |
| `python:850adb4efc8ba7b0` | `tests/test_data_scheduler.py` | 1323 -> 1317 | Existing parametrized import, now targeting the two extracted client modules. |
| `python:b0f347716fcbf0ca` | `tests/test_news_clients.py` | new: 39 | Deliberate `spec_from_file_location` fresh-import test for both clients, under filesystem/logging/provider guards. |
| `settings:641b5adef6bdef16` | `src/service/data_scheduler.py` | 570 -> 564 | Existing dynamic per-source interval key read. |
| `settings:8b00eaf8d8967c28` | `src/service/data_scheduler.py` | 638 -> 632 | Existing dynamic per-source interval key write. |
| `settings:a3604a85a1377c89` | `src/service/data_scheduler.py` | 635 -> 629 | Existing dynamic per-source enable key write. |
| `settings:b1203ae3fb49c457` | `src/service/data_scheduler.py` | 381 -> 375 | Existing settings snapshot accessor. |
| `settings:bd06e6ed5fc9ce84` | `src/service/data_scheduler.py` | 568 -> 562 | Existing dynamic per-source enable key read. |
| `sql:02a521c35855c352` | `src/service/data_scheduler.py` | 608 -> 602 | Existing parameter-placeholder SQL in macro schedule reader. |
| `sql:3682a61546d82d10` | `src/service/data_scheduler.py` | 599 -> 593 | Existing `PRAGMA query_only = ON`, outside the scanner's modeled statement classes. |
| `sql:b8dfb7e1c3f40841` | `src/service/data_scheduler.py` | 609 -> 603 | Same existing macro reader query, formatted string location. |
| `sql:1f92347ae3f30742` | `src/daily_update.py` | 371 -> 233 | Existing `--ibkr-news` help string starts with "Update"; not SQL. |
| `sql:845ebe9b7ef811f0` | `src/daily_update.py` | 361 -> 223 | Existing `--all` help string starts with "Update"; not SQL. |
| `sql:8ce1527bfe5e3665` | `src/daily_update.py` | 365 -> 227 | Existing `--massive` help string starts with "Update"; not SQL. |
| `sql:a2f82be63b220d9a` | `src/daily_update.py` | 373 -> 235 | Existing `--ibkr-prices` help string starts with "Update"; not SQL. |
| `sql:c50b1fbc1e1f64bd` | `src/daily_update.py` | 369 -> 231 | Existing `--finnhub` help string starts with "Update"; not SQL. |
| `sql:ef3161593d5a15cd` | `src/daily_update.py` | 363 -> 225 | Existing `--news` help string starts with "Update"; not SQL. |

## Every Coverage Reduction

- `src/collectors/__init__.py`: deleted empty package owner.
- `src/collectors/polygon_news.py`: live transport/parser/credential definitions
  moved to `src/news_clients/polygon.py`; retired CLI/storage owners removed.
- `src/collectors/finnhub_news.py`: equivalent move to
  `src/news_clients/finnhub.py`; retired CLI/storage owners removed.
- `tests/test_collector_adapters.py`: thirteen deleted-CLI tests removed or
  superseded by actual current callers. `deleted-test-ownership.md` maps each
  owner and distinguishes the two additional renamed scheduler parameter IDs.

The three client package files and two new test modules plus scope-test helper
replace these four files: net two more read paths. AST/exact-source comparisons,
427-case focused acceptance and full-suite node reconciliation are separate
evidence; census alone cannot prove the preserved runtime behavior.
