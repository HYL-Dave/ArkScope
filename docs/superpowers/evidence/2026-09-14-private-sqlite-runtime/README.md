# Private SQLite Runtime Preparation

**Status: Linux package preparation and selected-process startup enforcement
CLOSED. Production activation remains OPEN.** This is not complete project
cleanup, existing-data health verification, or Python sandbox admission.

[Plan](../../plans/2026-09-14-private-sqlite-runtime.md),
[design](../../specs/2026-09-14-private-sqlite-runtime-design.md),
[operations](../../../design/SQLITE_RUNTIME_OPERATIONS.md),
[canonical policy](../../../design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md).

## Source And Delivered Contract

- Base: `42b7ce93`, after the user separated the dormant analysis executor from
  current writer admission. Product/test checkpoint:
  `292ef27f3ef363d5bd2f586e6a7435b0785ccd16`.
- Worktree: `/tmp/arkscope-research-output-boundary`, branch
  `codex/sec-research-integration`. Master remained an ancestor, `0 / 166`
  unique commits before this receipt, with no merge or push.
- `src.sqlite_runtime.build` prepares a new, exclusive Linux x86_64 package
  from a locally supplied, hash-pinned official source archive. No downloads at
  startup, dependency installation, active-directory overwrite or automatic
  selector mutation. It returns `prepared_not_activated`.
- The package's executable `python` checks bootstrap hashes before package code,
  validates its closed manifest and interpreter, probes the actual loaded
  engine and execs the original Python CLI. It preserves argv, cwd, stdin,
  stdout, exit and signal behavior. Only selected Python children receive the
  private loader environment; Electron and closed OAuth environments do not.
- `src` initialization and the direct SA script bootstrap verify selected
  runtime identity before application initialization. Both absent selection
  variables mean unmanaged development; partial, corrupt or conflicting
  selection fails. This does not enforce a yet-uninstalled production selector.
- Existing Desktop `ARKSCOPE_PYTHON` and SA JSON `python_path` can choose the
  prepared executable. Actual launchers ran with disposable API/host fixtures;
  installed configuration and the running App were not inspected or switched.

Ordinary Python/frontend changes do not rebuild SQLite. A future engine or
interpreter change requires a new verified generation, not a permanent version
freeze. Digests detect drift; they do not authenticate against arbitrary code
already running as the installation's OS user.

## Final Artifact

[Artifact validation](checks/artifact-validation.json) and the
[package manifest](checks/package/manifest.json) identify the exact final build:

| Item | Identity |
| --- | --- |
| SQLite | 3.53.4 |
| Source ID | `2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc` |
| Source ZIP SHA3-256 | `b834d474b9b393d85a9e3ee4cc11f1329e007e9376a424ee740796f5c4bda3a8` |
| Generated amalgamation SHA3-256 | `52fde3de869fc0bff701d7bdc6589e7337f77ebf28303abcfc1e531205895193` |
| Shared library SHA256 | `b3dc933621ec32f95d827779ba2bab2e72994c9b15d205bc377c904549d47d8a` |
| Package manifest SHA256 | `6bcf7a2d170d7d8aae4c6a9ade2d844c934eb361932020f2dc0165ec4feb53b3` |

`final-package-build-03` is the final generation; earlier build labels are
superseded, not combined into its acceptance. Its shared library has SONAME
`libsqlite3.so.0`, needs only system `libm`/`libc`, and has no RPATH/RUNPATH.
The existing interpreter and `_sqlite3` extension hashes match the manifest.
No Python, numpy, SDK or system SQLite installation was changed.

The initial default-amalgamation recipe was rejected after a real syntax RED:
`ENABLE_UPDATE_DELETE_LIMIT` appeared in compile options, but the grammar was
absent. The final canonical ZIP recipe runs the upstream generator with
`--enable-update-limit`; tests execute both UPDATE and DELETE ORDER BY LIMIT.
The generated digest intentionally differs from the upstream default
amalgamation. See the official
[compile-option requirement](https://www.sqlite.org/compile.html#enable_update_delete_limit).

Compared with the observed distro engine, the final compile-option list adds
`DIRECT_OVERFLOW_READ` and no longer reports `ENABLE_JSON1` or
`ENABLE_LOAD_EXTENSION`. Actual JSON and extension-enable/disable behavior were
checked; no extension was loaded. Critical capacity/privacy settings remain,
including 250,000 bindings, secure deletion, LIKE behavior, FTS, threading,
RTREE, mmap/page limits and the existing function-argument limit. Option names
alone are not the compatibility claim.

## Verification

The one complete backend invocation used the final `package/python`, the
existing offline controls, explicit archive fixture and the whole `tests/`
directory. No other pytest, scanner, reviewer or source edit ran concurrently.
External calls, actual credentials/configuration and production stores were
excluded. The unmanaged collection run and focused parent are distinguished
from the selected-runtime full run in their receipts.

| Check | Result |
| --- | --- |
| Closed manifest RED / corrected GREEN | 30 expected failures / 30 passed |
| Build/launcher initial RED | 3 expected failures, 13 missing-builder errors |
| Startup RED / GREEN | 8 expected failures / 38 passed controls |
| Actual LIMIT grammar RED / GREEN | 1 failure plus 1 control / 15 passed |
| Executable bootstrap drift RED / GREEN | 2 failures / 61 passed |
| Adjacent-module and direct-loader review RED / GREEN | 3 failures / 67 passed |
| Bootstrap FIFO review RED | 3 bounded failures |
| Final focused runtime/startup/auth collateral | 278 passed |
| Final unchanged UPSERT reproducer | all five cases passed, exit 0 |
| Final synthetic storage probes | 8 passed |
| Final full collection | 11,250 nodes |
| Final complete selected-runtime backend | **11,238 passed / 12 unchanged skips / zero failures or errors** |

Full wrapper time: **1,493.761 seconds**; pytest reports 1,489.50 seconds.
[Exact reconciliation](checks/final-validation.json) confirms all collected
identities executed once, **70 added / zero removed**, no duplicate nodes and
the same twelve skip identities as the C12 baseline. All four new test modules,
retained safety owners and SEC maintenance/citation regressions ran and passed.
The 29 artifact-dependent cases were not skipped.

All **1,169** frozen source/test/frontend paths, SDK/runtime metadata and runner
hashes match before and after. Source collection SHA256:
`d33ad1515ccc7391d0ef16be843e7a1c6c7d7b01b6e283a0093bd18d26246dd4`.
The freeze helper's SQLite field describes its deliberately unmanaged process
(3.37.2); [the full process receipt](checks/full-admitted/runtime.json) separately
proves 3.53.4 and the actual package library. Neither is mislabeled as the other.

Real process tests cover wrong same-version artifacts, relocation/spaces,
symlink selectors, original CLI semantics, Desktop and SA launchers, current
worker help paths, descendant identity, closed OAuth environments and native
numpy/pandas operations. No frontend source changed; no new frontend suite or
actual installed-App hand-test result is claimed.

The eight synthetic probes cover exact decimal TEXT/JSON, external-content FTS,
foreign keys, transactions, WAL locking/concurrency, uncheckpointed-WAL backup
and POSIX flock. WAL stress remains **not a deterministic WAL-reset reproducer**.
The archived UPSERT program is byte-identical to the previous source and runs
in memory; this does not imply that real ArkScope data suffered that defect.

[Scoped review notes](checks/reviews.md) retain the findings and corrections.
The first contract GREEN attempt exposed group-writable fixture files under the
local umask (14 failures); setting the fixture's intended private permissions
fixed it without weakening validation. A mistyped startup test filename produced
exit 4/no tests before the corrected invocation. Two helper invocations failed
before producing receipts: an initial relative child path resolved from scratch,
and a freeze attempt with `-S` could not read installed package metadata. Their
corrected invocations are recorded; neither is counted as a successful check.

## Retained Boundaries

The post-run unmanaged interpreter still maps system SQLite **3.37.2**.
No installed selector, live database, runtime installation, App restart, merge
or push was performed. Actual writer inventory, stopped-writer backups, full
integrity checks, installation/selection and restart verification remain the
separate operational window in the runbook. Engine replacement is not data
repair or a proved rollback after resumed writes.

The dormant analysis executor and its closed child environment are unchanged,
not current-writer coverage. The future Python sandbox owns its replacement.
Windows/macOS, C15/C20 retained-data/ownership cleanup, broader census findings,
recent-source entitlement/retry reporting and SA Open-first targeting stay open.
No fresh whole-repository census result is claimed in this runtime slice.

## Evidence Inventory

[Manifest](checks/manifest.json) records **109 selected artifacts** with sizes
and SHA256; all hashes and lossless gzip round trips were checked after sealing.
Raw failed attempts, final commands/results, source freezes, exact reconciliation,
review notes and final package metadata are included. Helper paths retain the
original workspace context and are not standalone at their archival location.
Source ZIPs, libraries, fixture databases/HOME and unrelated scratch are excluded.
