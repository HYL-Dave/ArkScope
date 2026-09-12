# Standalone SQLite 3.53.4 Candidate

Date: 2026-09-12. Build/probe window: 15:32-15:47 UTC (23:32-23:47 Asia/Taipei).

## Outcome and Boundary

**The pinned SQLite library and CLI were built privately and passed the bounded
Linux probes. No application runtime is upgraded or production-admitted.**

- Python remains `/home/hyl/.virtualenvs/llm_app/bin/python`, version 3.10.12.
  No Python download, rebuild, dependency install, venv change, or version decision.
- `LD_LIBRARY_PATH` was set only in explicitly isolated probe subprocesses and
  their synthetic children. This is not an activation or deployment recommendation.
- No App/sidecar, collector provider, SA browser host, or production DB was run.
  No global install, `ldconfig`, user-config change, product edit, index operation,
  commit, data migration, repair, or production backup occurred.
- All source/build/probe artifacts, logs, temporary HOME/TMPDIR, synthetic DBs,
  WALs and lock files are inside the authorized scratch directory below.
  This new Markdown report is the only write outside that directory.
- Total scratch footprint was approximately 25 MiB. No binaries are added to
  product source. All command sessions finished; the final scoped process check
  returned no matching probe/build/CLI processes (pgrep exit 1).

Initial tracked-source anchor: `3fef138daae0a5c357b385156738d34107a04956`.
The controller continued SEC integration independently. The archived reproducer
remained byte-identical: Git blob `cd2a0e50f7c23a9a89e750b8b4780415f7259a64`.

## Source and Build Identity

Only this artifact was fetched:
[official SQLite autoconf archive](https://www.sqlite.org/2026/sqlite-autoconf-3530400.tar.gz).
HTTP 200, effective URL unchanged, 3,283,177 bytes. No redirect, retry to another
version, or alternate artifact was used. The expected hashes were supplied by
the controller from the [official download page](https://www.sqlite.org/download.html)
and [release history](https://www.sqlite.org/changes.html).

| Verification | Expected and observed SHA3-256 |
|---|---|
| `sqlite-autoconf-3530400.tar.gz` | `454e45f61c6bd75b7420e7190732dea03ce6639c63ada47bbc592f67fc340338` |
| Unmodified `sqlite3.c` | `67f423e9ebbbdc473cbc4772c872ee6b89f31fde4ed0279a5c25d5f65c043a16` |

Archive verification preceded extraction. All 54 archive members had confined
paths and were regular files/directories. Both `sqlite3.h` and `sqlite3.c`, the
Python-loaded library, and the private CLI reported version 3.53.4 and exactly:

```text
2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc
```

Source hash and source-ID verification passed again after the build/probes.

Build host: Linux x86_64, kernel `6.8.0-134-generic`.
Compiler: `cc (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0`.
Make: GNU Make 4.3. Maximum Make parallelism: `-j4`.
Build exit 0, elapsed 24.072091 seconds, empty stderr.

Configuration enabled FTS5 and `SQLITE_THREADSAFE=1`, retained default JSON,
and disabled optional CLI readline and the standalone static library target.
The CLI embeds the amalgamation by the upstream default; Python tests use the
separate shared library, not the CLI's engine. Upstream defaults also enabled
math/percentile functions. No build dependency was missing.

Private library: `prefix/lib/libsqlite3.so.3.53.4`, 1,396,552 bytes.
Private CLI: `prefix/bin/sqlite3`, 2,062,216 bytes.
SONAME: `libsqlite3.so.0`; both `.so` and `.so.0` symlink to `.so.3.53.4`.
ELF RUNPATH points only to the scratch prefix's lib directory; NEEDED entries
are `libm.so.6` and `libc.so.6`. This is not a relocatable application package.

## Runtime Comparison

Both probes used the existing Python 3.10.12 executable and the unchanged
extension `/usr/lib/python3.10/lib-dynload/_sqlite3.cpython-310-x86_64-linux-gnu.so`.
Its SHA-256 was `634cbbb96ae1302313d77de76a465ec552ffb51007a37d02697b1747482a83af`.

| Runtime | SQL version | Actual mapped library |
|---|---|---|
| Baseline, no loader override | 3.37.2 | `/usr/lib/x86_64-linux-gnu/libsqlite3.so.0.8.6` |
| Candidate subprocess only | 3.53.4 | `$R/prefix/lib/libsqlite3.so.3.53.4` |
| Fresh baseline after candidate tests | 3.37.2 | Same system library and SHA-256 as before |

Baseline source ID:
`2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1`.
Its library SHA-256 remained
`26917e4509991ee5c180c3dcfc39630f1bf81bc7812a5711be0cbaaef1650148`.

Candidate identity is verified by SQL version/source ID, `/proc/self/maps`,
library hashing, and `ldd` on the actual `_sqlite3` extension. The synthetic
runner fails before file-backed DB tests if the expected engine is not loaded.
Each subprocess worker reports its engine/source ID and must match its parent.

### Archived UPSERT Matrix

The [unchanged archived script](../2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py)
was invoked by absolute path with `-I -S -B`, without any application imports.

| Case | Baseline 3.37.2 | Verified candidate 3.53.4 |
|---|---|---|
| `upstream_replace_duplicate` | defect signature | pass |
| `insert_schema_replace_duplicate` | defect signature | pass |
| `insert_or_replace_duplicate` | defect signature | pass |
| `replace_single_clause` | pass | pass |
| `insert_single_clause` | pass | pass |
| Overall classification / process exit | `defect_reproduced` / 1 | `all_pass` / 0 |

All cases retained two table rows. The baseline's three defect cases returned
indexed count 3 and `wrong # of entries in index sqlite_autoindex_v0_1` from
full `integrity_check`; `quick_check` nevertheless returned `ok`. The candidate
returned indexed count 2 and full `integrity_check=ok` in all five cases.

### Synthetic Matrix

The scratch-only `synthetic_probe.py` imports no application modules. A SQLite
audit hook confines file-backed connections to scratch; temporary SQLite
storage is memory-backed, with TMPDIR also confined to scratch.

| Test | Observable assertions | Baseline | Candidate / repeat |
|---|---|---|---|
| JSON and exact decimal TEXT | Exact `12345678901234567890.12345678901234567890` string and SQL `text` types, trailing zeros, JSON arrays/null, invalid JSON rejection | pass | pass / pass |
| FTS5 external-content triggers | `porter unicode61`, stemming, accented-word normalization, insert/update/delete index synchronization, FTS external-content integrity command | pass | pass / pass |
| Foreign keys | Orphan rejected, delete cascade, empty `foreign_key_check` | pass | pass / pass |
| Transactions | Commit, savepoint rollback, Python context rollback after PK violation, exact retained row | pass | pass / pass |
| WAL writer/reader locking | Real child holds `BEGIN IMMEDIATE`; contender times out near 150 ms; reader retains snapshot; killed uncommitted writer rolls back and releases lock | pass | pass / pass |
| WAL concurrency/checkpoints | Three child writers, 100 commits each; fourth process performs 50 PASSIVE, 50 RESTART and 50 TRUNCATE checkpoints; 300 exact TEXT rows, per-writer count/sum `(100,4950)`, final checkpoint `(0,0,0)`, full integrity | pass | pass / pass |
| Backup with uncheckpointed WAL | WAL 8,272 bytes; deliberately incomplete main-file copy contains 1 row; `Connection.backup()` contains all 3 rows, including exact decimal TEXT; backup progress finishes with status 101 and zero remaining pages | pass | pass / pass |
| POSIX process lock | Independent process excluded by `flock`; lock reacquired after SIGKILL | pass | pass / pass |
| Suite total / process exit | | 8 passed, 0 failed / 0 | 8 passed, 0 failed / 0, twice |

Candidate WAL checkpoint workers observed partially completed write sets 110
and 118 times, respectively, establishing actual overlap. All 150 checkpoint
calls completed in each run; contention is independently forced by the writer
lock test. Candidate busy waits were 0.150879 and 0.150736 seconds.

**Limits:** These are bounded synthetic tests, not a deterministic reproducer
of the upstream WAL-reset race. The baseline also passes this WAL stress test;
that does not establish the absence of its known race. The pinned source
contains the upstream fix according to [SQLite's WAL-reset documentation](https://www.sqlite.org/wal.html#walreset).
Decimal guarantees tested here concern strings/TEXT, not arbitrary-precision
JSON numbers or SQL REAL arithmetic. The main-file copy is solely a negative
control on synthetic data, never a recommended backup method.

## Corrected Attempt Failures

No integrity/source-ID gate failed and no alternate version was used. These
operator/harness failures are retained rather than removed from the receipts:

| Receipt label | Actual exit | Explanation and correction |
|---|---|---|
| `private-stage` | 2 | Requested nonexistent target `install-shell`; upstream target is `install-shell-0`. The library build had already succeeded. This was not a missing dependency. Corrected staging exited 0. |
| `candidate-upsert` | 1 | Invoked prematurely after failed staging. Empty private lib directory meant the subprocess still loaded 3.37.2 and reproduced the baseline defect. Not counted as a candidate result. |
| `candidate-identity` | 1 | Scratch audit hook initially treated a bytes path as a Path-compatible string. TypeError occurred before opening the memory connection. Fixed with `os.fsdecode`; corrected identity, baseline suite and both candidate suites passed. |

Consequently there are three archived-script invocations in the raw receipts:
the intended baseline, one rejected misconfigured attempt, and the verified
candidate. Candidate source identity and actual mapped library were checked
before accepting the successful rerun.

## Exact Commands and Receipts

Definitions used below:

```bash
REPO=/tmp/arkscope-research-output-boundary
R="$REPO/.superpowers/sdd/2026-09-12-sec-research-release-integration/sqlite-candidate"
P=/home/hyl/.virtualenvs/llm_app/bin/python
S="$R/sqlite-autoconf-3530400"
REPRO="$REPO/docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py"
run() {
  env -i PATH=/usr/bin:/bin "$P" -I -S -B "$R/run_step.py" "$@"
}
```

`run_step.py` runs each child with exactly this allowlisted environment:
`PATH=/usr/bin:/bin`, `HOME=$R/home`, `TMPDIR=$R/tmp`, `LC_ALL=C`,
`PYTHONDONTWRITEBYTECODE=1`. Only `--library-path "$R/prefix/lib"` adds
`LD_LIBRARY_PATH`, to that child only. No shell profile, inherited provider
environment, user Python site, curl config, or existing user HOME is used.
Default cwd is `$R`; `--cwd "$S"` is explicit for configure/build/staging.

The [complete evidence audit](../../../../.superpowers/sdd/2026-09-12-sec-research-release-integration/sqlite-candidate/logs/evidence-audit.stdout)
contains the 28 preceding command receipts: exact argv, shell-quoted command,
cwd, full allowlisted environment, UTC start, elapsed time, timeout setting,
expected and actual exit, and SHA-256 of full stdout/stderr. Audit exited 0.
Every receipt stream hash was read back and verified. The per-step raw files
are `$R/logs/<label>.json`, `.stdout`, `.stderr`; console truncation does not
truncate those files.

Core sequence actually executed, including retained failed commands:

```bash
run --label baseline-upsert --expect 1 -- "$P" -I -S -B "$REPRO"
run --label archive-download --timeout 150 -- /usr/bin/curl --disable --fail --show-error --silent --proto =https --connect-timeout 20 --max-time 120 --output "$R/sqlite-autoconf-3530400.tar.gz" --write-out '%{http_code}\n%{url_effective}\n%{size_download}\n' https://www.sqlite.org/2026/sqlite-autoconf-3530400.tar.gz
run --label archive-verify -- "$P" -I -S -B "$R/verify_source.py" archive
run --label archive-extract -- /usr/bin/tar --extract --gzip --file sqlite-autoconf-3530400.tar.gz --no-same-owner --no-same-permissions
run --label source-verify -- "$P" -I -S -B "$R/verify_source.py" source
run --label configure-help --cwd "$S" -- /bin/sh ./configure --help
run --label configure --cwd "$S" -- /bin/sh ./configure --prefix="$R/prefix" --disable-static --disable-readline --fts5 --soname=legacy 'CFLAGS=-O2 -DSQLITE_THREADSAFE=1'
run --label build --timeout 240 --cwd "$S" -- /usr/bin/make -j4
run --label private-stage --cwd "$S" -- /usr/bin/make -j4 install-dll install-shell
run --label candidate-upsert --library-path "$R/prefix/lib" -- "$P" -I -S -B "$REPRO"
run --label private-stage-corrected --cwd "$S" -- /usr/bin/make -j4 install-dll install-shell-0
run --label candidate-identity --library-path "$R/prefix/lib" -- "$P" -I -S -B "$R/synthetic_probe.py" identity --expected-version 3.53.4
# The audit-hook correction was applied here; these subsequent probes use it.
run --label candidate-identity-corrected --library-path "$R/prefix/lib" -- "$P" -I -S -B "$R/synthetic_probe.py" identity --expected-version 3.53.4
run --label candidate-upsert-verified --library-path "$R/prefix/lib" -- "$P" -I -S -B "$REPRO"
run --label baseline-synthetic --timeout 180 -- "$P" -I -S -B "$R/synthetic_probe.py" suite --expected-version 3.37.2 --run-name baseline-01
run --label candidate-synthetic --timeout 180 --library-path "$R/prefix/lib" -- "$P" -I -S -B "$R/synthetic_probe.py" suite --expected-version 3.53.4 --run-name candidate-01
run --label candidate-synthetic-repeat --timeout 180 --library-path "$R/prefix/lib" -- "$P" -I -S -B "$R/synthetic_probe.py" suite --expected-version 3.53.4 --run-name candidate-02
run --label cli-identity -- "$R/prefix/bin/sqlite3" -batch -init /dev/null :memory: "SELECT sqlite_version(), sqlite_source_id(), sqlite_compileoption_used('ENABLE_FTS5'), sqlite_compileoption_used('THREADSAFE=1'), json_extract(json_object('amount','1.230000'),'$.amount');"
run --label candidate-linkage --library-path "$R/prefix/lib" -- /usr/bin/ldd /usr/lib/python3.10/lib-dynload/_sqlite3.cpython-310-x86_64-linux-gnu.so
run --label candidate-elf -- /usr/bin/readelf -d "$R/prefix/lib/libsqlite3.so.3.53.4"
run --label baseline-final-identity -- "$P" -I -S -B "$R/synthetic_probe.py" identity --expected-version 3.37.2
run --label source-final-verify -- "$P" -I -S -B "$R/verify_source.py" source
run --label artifact-checksums -- /usr/bin/sha256sum "$R/sqlite-autoconf-3530400.tar.gz" "$S/sqlite3.c" "$R/prefix/lib/libsqlite3.so.3.53.4" "$R/prefix/bin/sqlite3" "$R/run_step.py" "$R/verify_source.py" "$R/synthetic_probe.py" "$REPRO"
run --label compiler-version -- /usr/bin/cc --version
run --label make-version -- /usr/bin/make --version
run --label scratch-size -- /usr/bin/du -sh "$R"
run --label repro-blob-final -- /usr/bin/git --no-optional-locks hash-object --no-filters "$REPRO"
run --label scope-process-check --expect 1 -- /usr/bin/pgrep -af "$R/(synthetic_probe[.]py|sqlite-autoconf-3530400/|prefix/bin/sqlite3)"
run --label evidence-audit -- "$P" -I -S -B "$R/audit_evidence.py"
```

This is a historical command record, not an instruction to repeat the failed
attempts or overwrite the archive. Existing labels and test run directories
are intentionally refused. To repeat only the candidate synthetic suite without
redownloading, rebuilding, activation, or overwriting evidence, use a new label
and a new `--run-name`, for example:

```bash
run --label candidate-synthetic-repeat-03 --timeout 180 --library-path "$R/prefix/lib" -- "$P" -I -S -B "$R/synthetic_probe.py" suite --expected-version 3.53.4 --run-name candidate-03
```

### SHA-256 Receipt

| Artifact / stream | SHA-256 |
|---|---|
| Downloaded archive | `0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c` |
| `sqlite3.c` | `b1dd5d74ec7f29055a6684fa06fb3c2f6821c87dd38f9a458dfd2e8a1db28189` |
| Private shared library | `7839556f7ce531a48436cf0195d48e0415a4332ae69efa6b2e3c31aab9ad5067` |
| Private CLI | `8e8d201330def9e7e1689faca6d386bd9bcd0fd3c15e52259ecfc57ef2b4c72f` |
| Unchanged archived reproducer | `4c451c2fad8dc97efdd7139c1e420bb77565ec88f3363c401a1fbcd63f23c327` |
| `synthetic_probe.py` | `b27bfcbc91b9bf65cfc14761e211ee5494e6cd49118780660e9e59a61a710946` |
| `run_step.py` | `13080c49262ea5c3008c4a8a62f3c844ef679f19734a0be5c6c62e94a14c6d32` |
| `verify_source.py` | `9f38d6003e0edab75cbdc7a5fcc9595155cd365c6305915abbbcac877ddeeeba` |
| `audit_evidence.py` | `6dc362db0ca94fb2f4075d9b9f7f9250cb77fa94f791ffe224b548028411cbad` |
| Baseline UPSERT stdout | `8cacaabbb35decf9be41c5f557514f6e5e0181fce38995f0bcee3e65f2fffbe4` |
| Verified candidate UPSERT stdout | `d8ac56ff2db08631ef123fb036f0dc39f85a8f72fb1574a729f4a5a25fe9f754` |
| Baseline synthetic stdout | `0db40c5793be0f1d79b5543ccf5162312006fb9382a1507994d45d00fd27637f` |
| Candidate synthetic stdout | `4a4c7f269aac1c62b0fdb6bbff0a7f012770d8a284d3d4e5e312a33cfc44886d` |
| Candidate repeat stdout | `b0d1d697ddd95a2681cef0c53452f73dd0736f33d0dfce50d8acb85ea23c458a` |
| Evidence-audit stdout | `bff630e6defb321c0b86257864448612b27818a6b984baaefe9c204176454a27` |

## Not Yet Admitted

- This establishes the actual existing Python `sqlite3` engine can use the pinned
  shared library in an isolated Linux probe. It does not establish an app-local
  Python package, Python 3.13 compatibility, or the controller's Python choice.
- The candidate intentionally meets the requested FTS5/JSON/threading feature
  floor, not full distro compile-option parity. In particular,
  `MAX_VARIABLE_NUMBER` changes from 250000 to 32766; optional FTS3/4, RTREE,
  session, column-metadata and related flags differ. The complete option diff is
  retained in the evidence audit. Absence of `ENABLE_JSON1` is not absent JSON;
  behavioral JSON tests passed. Production build options require separate review.
- Actual App stores, app-specific lock wrappers, backup wrapper, launch selectors,
  schedulers, native messaging, dependency imports and provider integrations were
  not exercised. All eight tests are standalone synthetic checks.
- No Windows/macOS build, launcher, filesystem-lock, packaging or signing checks.
  No sustained production workload or deterministic upstream WAL-reset test.
- No existing-data health assessment or repair claim. Any production backup,
  full integrity assessment, data operation, coordinated writer shutdown, runtime
  activation or rollback remains separately authorized work.

## Controller Readback

At 15:57 UTC the controller independently invoked `controller-candidate-identity`
and `controller-candidate-upsert` through the same closed-environment runner.
Actual mapped library and source ID matched the pinned candidate, and the
unchanged five-case reproducer returned `all_pass`, exit 0. This confirmation
does not change the activation or production-data boundary above. The separate
Python 3.13 scope question is still pending the user's answer.

The controller then ran `sqlite-application-stores` against the candidate:
**330 passed**, exit 0. Before pytest, the launcher verified version, exact
source ID and `/proc/self/maps` against the private library. The existing
offline runner used disposable stores and blocked production paths/providers.
This adds actual SEC capture/store, profile, SA, normalized-news schema/store/
writer-locking, SQLite backup-wrapper and direct-market tests to the earlier
standalone probes. It is not the full application suite, a claim that every
test-created subprocess uses the override, or a production/platform admission.
