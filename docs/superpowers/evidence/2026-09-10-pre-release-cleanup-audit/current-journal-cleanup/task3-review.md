# Task 3 Independent Spec And Quality Review

## Findings

**PASS for Task 3 foundation. No blocking spec or quality defects found.**
No concrete nonblocking bug was identified in the frozen five-file snapshot.
This verdict does not establish SEC workflow readiness or authorize integration,
production cleanup, or any change to the user's stored data.

## Scope And Identity

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Reviewed `task3-review-package.md` and `task3-report.md` in this directory.
- All five current SHA-256 values match both frozen artifacts. The scoped diff
  against the base is exactly five new files and 601 insertions.
- No applicable `AGENTS.md` was found in the worktree or its ancestor directories.
- Requirements: Task 3 and the global config/path constraints in
  `docs/superpowers/plans/2026-09-11-current-journal-and-sec-foundation.md`, plus
  storage/configuration and capacity requirements in
  `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.

The reviewed change scope is exactly:

| File | SHA-256 |
| --- | --- |
| `src/sec_research/__init__.py` | `283db4d3a4f27a14b29fb8e6b1c60bac262252a801ceea21c7f6375ef574d07f` |
| `src/sec_research/config.py` | `67818a242046a94b97c61a6fc80e24627dc4eed9a4c13da77efc0b918a30646c` |
| `src/sec_research/paths.py` | `93fc1abd8addc3d7b924d1b6b67ab0a94a7203d061da4e7c8a4b7a57e3005eaa` |
| `tests/test_sec_research_config.py` | `8bcbbaf8c54b88f26e0165fcbb52b802c1f5e0645e3115e72ad9d8f5833cfea9` |
| `tests/test_sec_research_paths.py` | `0bdad74318b5849d89fe9f2810a295401299fc46bf13a266b8fa460f01afc408` |

Existing store/resolver definitions and the two existing profile-setting controls
were read only as contract context; no concurrent task was reviewed.

## Contract Checks

- **Real settings API:** `config.py:27` uses `get_settings_snapshot`, whose actual
  implementation at `src/profile_state.py:919` retains present NULL values and
  omits missing keys. Membership testing therefore preserves the required
  distinction. `config.py:46` uses the existing single-key `set_setting` upsert
  (`src/profile_state.py:909`). Both APIs also exist at the supplied base.
- **Budget representation:** `config.py:11` defines exactly 107374182400 bytes
  and the independent technical maximum 9007199254740991. `config.py:16` rejects
  bools, floats, nonpositive values and overflow before writing; no rounding or
  clamping occurs. `config.py:31` bounds and validates canonical ASCII decimal
  text before integer conversion. NULL, blobs and malformed values fail without
  fallback or repair. There is no new schema, schedule, acquisition or path write.
- **Data preservation tests:** `tests/test_sec_research_config.py:39` and `:103`
  check read-only default/error behavior using real temporary profile stores.
  The test at `:150` verifies exact increases/decreases, large odd integers,
  unrelated setting values/timestamps, unchanged schema and persistence after
  reopening. Invalid writes and absent-key preservation are covered at `:134`
  and `:143`; market/capture noncreation is covered at `:189`.
- **Path authority and relocation:** `paths.py:13` freezes the resolved database
  binding. `paths.py:17` delegates to `src/market_data_admin.py:254`, the same
  resolver imported by the market DAL at `src/market_data_direct.py:51`, rather
  than introducing another environment variable or default. The resolver also
  exists at the base. `paths.py:27` retains the full DB filename in the specified
  sibling root. Tests at `tests/test_sec_research_paths.py:22`, `:32`, `:42`,
  `:66`, `:78`, `:95`, `:107` and `:120` cover noncreation, distinct stores,
  stable binding, env/default/delegated authority, DB symlinks and moved captures.
- **Portable keys and escape guard:** `paths.py:37` validates canonical relative
  POSIX keys and rejects traversal, foreign absolute/drive/UNC/device forms,
  alternate streams, malformed components and Windows-unsafe names. Literal
  percent text is not decoded. `paths.py:62` resolves symlinks and checks actual
  component containment against the DB-derived anchor, not an already-redirected
  capture root or a string prefix. Tests at `tests/test_sec_research_paths.py:158`,
  `:218`, `:248`, `:262`, `:272` and `:281` exercise malformed keys, escaping and
  contained links, preexisting root redirection, root aliases and loops.

## Verification Evidence

Parsed the existing focused JUnit XML, including expanded node IDs and mutation
failure details, rather than relying solely on the worker's summary:

- `task3-green-frozen-12.xml`: 128 cases, zero failures/errors/skips; 54 config,
  72 path and two existing profile controls. The earlier GREEN/restored XML each
  records 127 cases before the additional preexisting-root test.
- RED owners: three assertion failures plus two passing controls. RED behavior:
  125 assertion failures at missing-module gates, not independent runtime-branch
  failures. This limitation is correctly disclosed in the implementation report.
- NULL, bool, range, combined traversal, symlink and preexisting-root mutation
  XML record respectively 1, 2, 2, 1, 7 and 1 expected failures. The single-guard
  traversal mutation records one pass because another guard still rejects `..`;
  it is correctly reported as surviving, not as evidence of a killed mutant.
- Fresh scoped `git diff --check` against the supplied base returned exit 0.

No additional runtime test was needed after static inspection, hash matching and
XML review. No focused suite or full suite was rerun; the passing results above
are existing evidence, not a newly executed test claim.

## Residual Risk And Boundaries

- Windows syntax is tested through the standard path parsers on Linux. Native
  Windows filesystem behavior has not been exercised; this is a coverage limit,
  not a demonstrated Task 3 defect or a demand for generic compatibility work.
- Containment is a resolution-time check, as `paths.py:34` explicitly states.
  Concurrent filesystem replacement after validation is not prevented. Atomic
  file I/O/publication belongs to later capture work, not this foundation review.
- Relocation coverage uses tiny path/object fixtures, not an actual SQLite export
  or restoration. Quota accounting/reservations, export/restore, acquisition and
  tool/UI registration remain outside Task 3. Their absence is not a blocker here.
- This review inspected no production DB, configuration file, `.env` or token
  store, and performed no provider/network access, install, restart or commit.
  No database was opened by this reviewer, no source/test was edited, and no
  cleanup/disposal was performed. The only created file is this review report.
