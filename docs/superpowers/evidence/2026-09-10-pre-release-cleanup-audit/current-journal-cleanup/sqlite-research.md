# SQLite Risk Assessment: Research And Reproduction Record

Assessment date: 2026-09-11.

Assessed repository: `/tmp/arkscope-listing-sec-macro-convergence`.

Assessed commit: `2842c497dabfdb0b13c315e22b206128eba9f57d`.

This assessment is independent of the current journal refactor. The original
assessment was read-only. The subsequent archive request authorizes this report
file only; no separate probe file was created. Commands in this report are a
record of diagnostics already executed, not an installation script or runtime
gate. The archive step did not rerun the Python probes.

## Conclusion And Confidence Boundary

The installed SQLite engine reproduces the reported UPSERT index corruption
defect. This is not a WAL-only defect. The tested SQL combines replacement
conflict handling with redundant UPSERT conflict clauses targeting the same
unique index. The reviewed repository SQL did not contain that combination.

A contained SQLite runtime upgrade is advisable, independently of cleanup and
before relying on sustained new SEC ingestion. This does not justify claiming
that ArkScope has suffered this corruption, or that an operating-system upgrade
is necessary. Cleanup and new tables do not patch the SQLite engine.

| Claim | Evidence and confidence |
| --- | --- |
| The inspected engine has the UPSERT defect | Demonstrated with synthetic `:memory:` databases in two clean interpreter probes. |
| WAL is required for that UPSERT defect | False for the tested example: `journal_mode` was `memory`. |
| Current reviewed store SQL uses the affected form | No matching form found by the scoped keyword scan and manual inspection below. Not a formal parser or whole-program proof. |
| The live application uses the inspected interpreter/library | **Not verified.** Shell selection and clean interpreter probes do not establish the running sidecar's interpreter, environment, or import customization. |
| Existing application databases are corrupt | **Not assessed.** No application database was opened, including read-only opens. |
| The WAL-reset race occurred locally | **Not demonstrated.** No filesystem-backed or concurrent WAL reproducer was run. |
| The installed vendor package contains the WAL fixes | Not established. Its inspected changelog does not document them; absence from a changelog is not proof of absence from a binary. |
| New SEC storage and PyInstaller packaging are implemented | Not at the assessed commit; the cited documents are plans, not deployed artifacts. |

## Primary SQLite Evidence

### UPSERT Index Corruption

- SQLite 3.45.2 release notes identify introduction in **3.35.0 (2021-03-12)**
  and the fix in **3.45.2 (2024-03-12)**. This concerns indexes becoming
  inconsistent with their tables, not generic UPSERT failure.
  [3.45.2 release notes](https://sqlite.org/releaselog/3_45_2.html).
- The maintainer identifies redundant UPSERT clauses on a replacement insert as
  the triggering SQL shape. The forum example has an integer primary key, a
  secondary UNIQUE column, and two UPSERT clauses targeting that same UNIQUE
  column. Ordinary one-clause UPSERTs do not satisfy that precondition.
  [Original report and maintainer explanation](https://sqlite.org/forum/forumpost/919c6579c8).
- The fix makes redundant conflict clauses inactive. The branch-3.45 check-in
  is dated 2024-03-08 and also records the trunk fix in its context. The original
  forum response and trunk check-in context identify a branch-3.44 backport;
  do not interpret the normal release interval as excluding vendor/branch
  backports.
  [Fossil branch-3.45 fix](https://sqlite.org/src/info/46245855a0be1b4e),
  [Fossil trunk fix](https://sqlite.org/src/info/d0ea6b6ba6).
- Local controls additionally demonstrated that `INSERT OR REPLACE`, or an
  ordinary `INSERT` with schema-level primary-key `ON CONFLICT REPLACE`, can
  reproduce the example when the redundant UPSERT clauses remain. Therefore
  searching only for the exact spelling `REPLACE INTO` would be insufficient.
- The maintainer says full `integrity_check` detects this index damage and
  `REINDEX` can repair damage caused by this particular defect. This is not a
  blanket repair recommendation for other corruption or lost transactions.
  [Maintainer explanation](https://sqlite.org/forum/forumpost/919c6579c8).

### Separate WAL Defects

1. **WAL-reset race:** SQLite says this is likely present from **3.7.0 through
   3.51.2**, fixed in **3.51.3 (2026-03-13)**, with backports **3.44.6** and
   **3.50.7**. It requires WAL and separate connections in separate threads or
   processes. After one checkpoint completes, another checkpoint races a commit
   that resets and starts rewriting the WAL. Later WAL growth and checkpointing
   can cause committed frames to be skipped. It is unrelated to UPSERT syntax.
   SQLite calls it rare and recommends upgrading without emergency urgency.
   Its documentation was updated on 2026-08-24 to acknowledge an uninstrumented
   reproducer, so the older statement that only special test instrumentation
   can reproduce it must not be repeated without that qualification.
   [WAL-reset documentation](https://sqlite.org/wal.html#walreset),
   [3.51.3 release](https://sqlite.org/releaselog/3_51_3.html),
   [3.44.6 Fossil backport context](https://sqlite.org/src/info/863c171b76cd36e0),
   [3.50.7 Fossil backport context](https://sqlite.org/src/info/c7facf7ac58d2cda).

2. **WAL checksum/savepoint defect:** rolling back a savepoint after dirty pages
   have spilled and WAL frames have been rewritten can leave invalid checksums,
   with committed data missing after recovery. The maintainer traces it to the
   optimization first released in **3.11.0**; the release fix is **3.50.2
   (2025-06-28)**. The reported example uses a tiny cache and auto-vacuum, not
   redundant UPSERTs. No production `SAVEPOINT` statement was found in the
   scoped source scan; a test-only `SAVEPOINT` was found.
   [Original report and introduction history](https://sqlite.org/forum/forumpost/b490f726db),
   [3.50.2 release notes](https://sqlite.org/releaselog/3_50_2.html).

3. **Older savepoint/temp-store defect:** the distinct corruption issue involving
   savepoint rollback, `temp_store=MEMORY`, subsequent changes, and outer commit
   was introduced in **3.35.0** and **already fixed in 3.37.2 (2022-01-06)**.
   It must not be described as introduced in 3.37.2 or confused with the 2024
   UPSERT fix.
   [3.37.2 release notes](https://sqlite.org/releaselog/3_37_2.html).

Version 3.45.2 fixes the stated UPSERT defect, not these later WAL defects.
The release history inspected on the assessment date lists **3.53.4
(2026-07-24)** as the current release and labels **3.52.0 withdrawn**. A bare
numeric minimum alone should not be mistaken for a complete release selection.
[SQLite release history](https://sqlite.org/changes.html).

## Observed Runtime

The shell's existing PATH selected
`/home/hyl/.virtualenvs/llm_app/bin/python` and its `python3` sibling. A separate
system interpreter was available at `/usr/bin/python3`. The assessed worktree
had no `.venv` or `venv` directory at the checked locations.

Both interpreter paths, explicitly invoked under `env -i` with `-I -S -B`,
reported the following:

| Observation | Value |
| --- | --- |
| Python | `3.10.12 (main, Aug 31 2026, 10:18:17) [GCC 11.4.0]` |
| SQLite | `3.37.2` |
| Python sqlite3 module | `/usr/lib/python3.10/sqlite3/__init__.py` |
| Native extension | `/usr/lib/python3.10/lib-dynload/_sqlite3.cpython-310-x86_64-linux-gnu.so` |
| Actual loader initialization | `/lib/x86_64-linux-gnu/libsqlite3.so.0` |
| Resolved library file | `/usr/lib/x86_64-linux-gnu/libsqlite3.so.0.8.6` |
| Library and development packages | `libsqlite3-0:amd64` and `libsqlite3-dev:amd64`, both `3.37.2-2ubuntu0.7` |
| Python package | `python3.10`, `3.10.12-1~22.04.18` |
| Standalone SQLite CLI | Not found on the inspected PATH; `dpkg-query` found no package named `sqlite3`. |

Exact SQLite source ID observed:

```text
2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1
```

Selected compile options observed in the system probe were `THREADSAFE=1`,
`TEMP_STORE=1`, `DEFAULT_WAL_AUTOCHECKPOINT=1000`, `DEFAULT_SYNCHRONOUS=2`,
`DEFAULT_WAL_SYNCHRONOUS=2`, `ENABLE_FTS5`, and `ENABLE_JSON1`. These are build
observations, not measurements of application connection settings or proof
that a particular bug is fixed.

The `alt1` source ID and vendor package revision mean version-number comparison
alone cannot establish all backport status. The UPSERT reproducer supplies
direct evidence for that defect in this binary. No comparable local evidence
was obtained for the WAL defects.

The clean probes bypassed application imports, environment-derived library
overrides, and Python site initialization. They establish those explicit clean
processes' behavior, **not** the live application's interpreter or complete
runtime environment. In Python 3.10, `-S` also affects virtual-environment
prefix initialization; prefix output from this probe is not a venv activation
test. Python documents `sqlite3.sqlite_version` as the runtime library version.
[Python SQLite reference](https://docs.python.org/3/library/sqlite3.html#sqlite3.sqlite_version).

## Exact In-Memory Commands Actually Executed

These shell commands ran with working directory `/tmp` and `login=false` in the
execution tool. They only created synthetic `:memory:` databases. SQL strings
inside them are diagnostic data, not application SQL loaded from the repo.

### Shell-Selected Interpreter: Upstream Reproducer

```bash
env -i PATH=/usr/bin:/bin /home/hyl/.virtualenvs/llm_app/bin/python -I -S -B -c 'import sys, sqlite3, _sqlite3; print("executable:", sys.executable); print("python:", sys.version); print("stdlib_sqlite:", sqlite3.__file__); print("extension:", _sqlite3.__file__); c = sqlite3.connect(":memory:"); print("engine:", c.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()); c.executescript("CREATE TABLE v0(c1 INTEGER PRIMARY KEY ON CONFLICT REPLACE,c2 UNIQUE); INSERT INTO v0 VALUES(0,33),(11,22); REPLACE INTO v0 VALUES(0,11) ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2 ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1;"); print("journal:", c.execute("PRAGMA journal_mode").fetchone()); print("counts:", c.execute("SELECT count(*) FROM v0").fetchone(), c.execute("SELECT count(*) FROM v0 WHERE c2>8").fetchone()); print("integrity:", c.execute("PRAGMA integrity_check").fetchall()); c.close()'
```

Observed relevant output, exit code 0:

```text
executable: /home/hyl/.virtualenvs/llm_app/bin/python
python: 3.10.12 (main, Aug 31 2026, 10:18:17) [GCC 11.4.0]
stdlib_sqlite: /usr/lib/python3.10/sqlite3/__init__.py
extension: /usr/lib/python3.10/lib-dynload/_sqlite3.cpython-310-x86_64-linux-gnu.so
engine: ('3.37.2', '2022-01-06 13:25:41 872ba256cbf61d9290b571c0e6d82a20c224ca3ad82971edc46b29818d5dalt1')
journal: ('memory',)
counts: (2,) (3,)
integrity: [('wrong # of entries in index sqlite_autoindex_v0_1',)]
```

Exit code 0 means the diagnostic command ran successfully; it does **not** mean
the database passed its integrity check.

### System Interpreter: Independent Reproducer

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B -c 'import sqlite3; c = sqlite3.connect(":memory:"); c.executescript("CREATE TABLE v0 (c1 INTEGER PRIMARY KEY ON CONFLICT REPLACE, c2 UNIQUE); INSERT INTO v0 VALUES (0,33),(11,22); REPLACE INTO v0 VALUES (0,11) ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2 ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1;"); print("SQLite:", sqlite3.sqlite_version); print("journal:", c.execute("PRAGMA journal_mode").fetchone()); print("table_count:", c.execute("SELECT count(*) FROM v0").fetchone()); print("indexed_count:", c.execute("SELECT count(*) FROM v0 WHERE c2 > 8").fetchone()); print("integrity:", c.execute("PRAGMA integrity_check").fetchall()); c.close()'
```

```text
SQLite: 3.37.2
journal: ('memory',)
table_count: (2,)
indexed_count: (3,)
integrity: [('wrong # of entries in index sqlite_autoindex_v0_1',)]
```

### Replacement Variants And Single-Clause Controls

```bash
env -i PATH=/usr/bin:/bin /home/hyl/.virtualenvs/llm_app/bin/python -I -S -B -c 'import sqlite3
cases = [("upstream_replace_duplicate", "REPLACE", " ON CONFLICT REPLACE", True), ("insert_schema_replace_duplicate", "INSERT", " ON CONFLICT REPLACE", True), ("insert_or_replace_duplicate", "INSERT OR REPLACE", "", True), ("replace_single_clause", "REPLACE", " ON CONFLICT REPLACE", False), ("insert_single_clause", "INSERT", " ON CONFLICT REPLACE", False)]
for label, verb, schema_policy, duplicate in cases:
    c = sqlite3.connect(":memory:")
    c.executescript("CREATE TABLE v0(c1 INTEGER PRIMARY KEY" + schema_policy + ",c2 UNIQUE); INSERT INTO v0 VALUES(0,33),(11,22);")
    sql = verb + " INTO v0 VALUES(0,11) ON CONFLICT(c2) DO UPDATE SET c1=c2,c2=c2" + (" ON CONFLICT(c2) DO UPDATE SET c1=c1,c2=c1" if duplicate else "")
    c.execute(sql)
    print(label, "counts", c.execute("SELECT count(*) FROM v0").fetchone()[0], c.execute("SELECT count(*) FROM v0 WHERE c2>8").fetchone()[0], "integrity", c.execute("PRAGMA integrity_check").fetchall(), "quick", c.execute("PRAGMA quick_check").fetchall())
    c.close()'
```

```text
upstream_replace_duplicate counts 2 3 integrity [('wrong # of entries in index sqlite_autoindex_v0_1',)] quick [('ok',)]
insert_schema_replace_duplicate counts 2 3 integrity [('wrong # of entries in index sqlite_autoindex_v0_1',)] quick [('ok',)]
insert_or_replace_duplicate counts 2 3 integrity [('wrong # of entries in index sqlite_autoindex_v0_1',)] quick [('ok',)]
replace_single_clause counts 2 2 integrity [('ok',)] quick [('ok',)]
insert_single_clause counts 2 2 integrity [('ok',)] quick [('ok',)]
```

These controls isolate the redundant-clause difference for this example. They
do not prove all other single-clause UPSERTs, schemas, or SQLite features free
of defects. The successful `quick_check` on the failing cases matches SQLite's
documentation: it does not compare index contents against table contents.
[PRAGMA quick_check](https://sqlite.org/pragma.html#pragma_quick_check).

## Runtime Inspection Command Record

The following relevant commands were actually executed. `type -a` used the
existing shell PATH only to identify executables; no application environment
or configuration file was sourced. Python invocations used clean environments.

```bash
type -a python3 python sqlite3
```

This returned the virtualenv paths and system `python3` paths above, and a
not-found result for `sqlite3` (exit code 1).

```bash
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B -c 'import sys, sqlite3, _sqlite3; print("executable:", sys.executable); print("python:", sys.version); print("prefix:", sys.prefix); print("base_prefix:", sys.base_prefix); print("sqlite3_module:", sqlite3.__file__); print("_sqlite3_extension:", _sqlite3.__file__); c = sqlite3.connect(":memory:"); print("engine:", c.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()); print("journal_mode:", c.execute("PRAGMA journal_mode").fetchone()); print("compile_options:", c.execute("PRAGMA compile_options").fetchall()); c.close()'
```

```bash
env -i PATH=/usr/bin:/bin ldd /usr/lib/python3.10/lib-dynload/_sqlite3.cpython-310-x86_64-linux-gnu.so
```

```bash
env -i PATH=/usr/bin:/bin LD_DEBUG=libs /usr/bin/python3 -I -S -B -c 'import sqlite3; print(sqlite3.sqlite_version)' 2>&1 | rg 'libsqlite3|3\.37\.2'
```

```bash
env -i PATH=/usr/bin:/bin LD_DEBUG=libs /home/hyl/.virtualenvs/llm_app/bin/python -I -S -B -c 'import sqlite3; print(sqlite3.sqlite_version)' 2>&1 | rg 'libsqlite3|3\.37\.2'
```

Both loader traces included `calling init: /lib/x86_64-linux-gnu/libsqlite3.so.0`.

```bash
env -i PATH=/usr/bin:/bin readlink -f /lib/x86_64-linux-gnu/libsqlite3.so.0
```

```bash
env -i PATH=/usr/bin:/bin dpkg-query -W '-f=${binary:Package}\t${Version}\n' libsqlite3-0 libsqlite3-dev sqlite3 python3 python3.10 libpython3.10-stdlib
```

The package query returned installed versions and exited 1 because the `sqlite3`
CLI package was absent. Library-package presence is distinct from CLI presence.

```bash
env -i PATH=/usr/bin:/bin gzip -dc /usr/share/doc/libsqlite3-0/changelog.Debian.gz | sed -n '1,160p'
```

This read installed package documentation only. The latest listed revision was
`3.37.2-2ubuntu0.7`, dated 2026-07-16, documenting Session Extension security
fixes, not these UPSERT/WAL fixes. No package update command was run.

## SQL Scope: What Was And Was Not Parsed

**There was no AST traversal, SQL parser inventory, ORM expansion, statement
capture, or whole-program analysis.** "SQL review" here means case-insensitive
keyword inventory of tracked source at HEAD, followed by manual reading of
selected statements, DDL, string concatenation, and branches. Only the synthetic
probe SQL above was parsed/executed by SQLite during runtime testing.

### Exact Broad Source Scan

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence grep -n -i -E 'on[[:space:]]+conflict|replace[[:space:]]+into|insert[[:space:]]+or[[:space:]]+replace|savepoint|wal_checkpoint|temp_store|sqlalchemy|pysqlite|apsw' HEAD -- '*.py' '*.sql' '*.js' '*.ts' '*.tsx' requirements.txt ':!docs/**' ':!config/**' ':!**/fixtures/**' ':!**/auth_drivers/**' ':!**/*token*' ':!**/*credential*' ':!**/replay_fixtures/**'
```

This searched committed code, including matching test files, not untracked
artifacts or installed third-party package source. Explicit exclusions were
documentation, the root configuration directory, fixture/replay-fixture paths,
authentication-driver paths, and paths containing `token` or `credential`.
Source modules with configuration-related names were not all excluded by this
broad scan; no production configuration contents were read.

### WAL And Store-Focused Scan

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence grep -n -i -E 'on[[:space:]]+conflict|insert[[:space:]]+or[[:space:]]+replace|journal_mode|wal_checkpoint|savepoint|temp_store' HEAD -- 'src/**/*.py' 'src/*.py' 'data_sources/**/*.py' ':!**/*config*' ':!**/*token*' ':!**/*credential*' ':!**/auth_drivers/**'
```

This narrower scan also excluded paths containing `config`; it is not a claim
to include every top-level `data_sources` file. The broad extension scan above
was used to expand coverage beyond those narrower pathspecs.

### Targeted Negative/Runtime-Dependency Scan

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence grep -n -i -E 'sec_research|sqlite_version|sqlite_source_id|wal_autocheckpoint|wal_checkpoint|savepoint|temp_store|on[[:space:]]+conflict[[:space:]]+replace' HEAD -- src data_sources ':!**/*token*' ':!**/*credential*' ':!src/auth_drivers/**'
```

This returned a documentation reference to the planned `src/sec_research/`, not
an implemented service. It found no production `SAVEPOINT`, explicit
`wal_checkpoint`, `wal_autocheckpoint`, or schema `ON CONFLICT REPLACE` in this
scope. The broad scan separately found a test-only savepoint in
`tests/test_security_lifecycle_automation_schema.py:620`.

Absence of explicit checkpoint SQL does not exclude automatic checkpoints.
WAL mode persists in database files, so lack of a WAL-setting statement in one
store does not establish an existing database's mode. The application was not
started to observe either behavior.
[WAL configuration and automatic checkpoints](https://sqlite.org/wal.html#activating_and_configuring_wal_mode).

### Manually Resolved Statement Shapes

Line references below refer to the assessed commit, not a later refactor.

| Source | Manually inspected shape | Relevance |
| --- | --- | --- |
| [Macro store](/tmp/arkscope-listing-sec-macro-convergence/src/macro_calendar/local_store.py:480) | `INSERT ... ON CONFLICT(series_id) DO UPDATE`; analogous single clauses at lines 512 and 544 for observation and release keys. | No replacement policy or redundant clauses in the inspected statements. |
| [Provider metadata](/tmp/arkscope-listing-sec-macro-convergence/src/market_data_direct.py:394) | One conflict target `(provider, ticker, interval)` with an UPDATE expression. | Updating multiple columns does not mean multiple UPSERT clauses. |
| [Lifecycle observation storage](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle.py:191) | One conflict target `(source, source_ref, ticker)`. | No redundant target in the inspected insert. |
| [News search documents](/tmp/arkscope-listing-sec-macro-convergence/src/news_normalized/store.py:897) | One conflict target `(article_id)`. | No matching compound replacement/UPSERT form. |
| [Investor profile](/tmp/arkscope-listing-sec-macro-convergence/src/investor_profile.py:339) | `INSERT OR REPLACE ... VALUES ...` without appended UPSERT clauses. | Replacement alone is not the demonstrated defect. |
| [Alpha Picks dynamic SQL](/tmp/arkscope-listing-sec-macro-convergence/src/tools/backends/sa_capture_backend.py:419) | `if/else` chooses either the closed-scope target at line 421 or the current-scope target at line 426; line 434 appends the chosen clause once. | Two clauses in the source file are not two clauses in one executed statement. |
| [Profile connection setup](/tmp/arkscope-listing-sec-macro-convergence/src/profile_state.py:245) | A fresh connection per operation; schema setup requests WAL at line 257. | Multiple connections and WAL are plausible architectural conditions, not proof of the WAL-reset race. |
| [Market writer setup](/tmp/arkscope-listing-sec-macro-convergence/src/market_data_direct.py:650) | Separate connection creation and best-effort WAL requests at lines 654 and 697. | Actual mode and concurrent checkpoint timing remain unobserved. |
| [Macro connection setup](/tmp/arkscope-listing-sec-macro-convergence/src/macro_calendar/local_store.py:305) | Sets busy timeout and foreign keys, not journal mode. | Does not establish the mode of an existing macro database. |

Representative exact manual-inspection commands actually run:

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:src/tools/backends/sa_capture_backend.py | nl -ba | sed -n '390,446p'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:src/macro_calendar/local_store.py | nl -ba | sed -n '1,90p;300,335p;461,558p'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:src/security_lifecycle.py | nl -ba | sed -n '1,45p;145,213p'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:src/investor_profile.py | nl -ba | sed -n '325,395p'
```

### Static Review Limitations

- The scans are line-oriented. They can miss keywords split between Python
  strings, generated character-by-character, loaded from excluded/non-code
  resources, or constructed by dependencies. Manual expansion was performed
  for the cited Alpha Picks branch, not for every possible runtime SQL string.
- Matches include comments, documentation strings, and tests; a keyword hit is
  not evidence of an executed production statement.
- No persisted schema, trigger, index, journal mode, or database provenance was
  inspected. Runtime schema can differ from tracked creation SQL.
- Third-party SQL, excluded paths, historical statements that populated retained
  data, and future SEC implementation are outside the negative finding.
- There was no application test run, migration run, provider run, live sidecar
  inspection, or filesystem-backed SQLite stress test. The synthetic control
  matrix is not an ArkScope regression suite.

## Packaging And New SEC Scope

- [requirements.txt](/tmp/arkscope-listing-sec-macro-convergence/requirements.txt:1)
  has no SQLite replacement package/version pin or PyInstaller dependency.
  Reviewed stores import the standard-library `sqlite3` module.
- [Desktop launcher](/tmp/arkscope-listing-sec-macro-convergence/apps/arkscope-desktop/main.js:25)
  selects `process.env.ARKSCOPE_PYTHON || "python"`; line 108 spawns that
  interpreter with `-m src.api`. Its live environment was not inspected.
- [Desktop package metadata](/tmp/arkscope-listing-sec-macro-convergence/apps/arkscope-desktop/package.json:8)
  has an Electron start script, not an implemented native sidecar build.
- The [distribution plan](/tmp/arkscope-listing-sec-macro-convergence/docs/superpowers/plans/2026-09-03-desktop-distribution-foundation.md:7)
  proposes native PyInstaller onedir builds. Its line 63 says to create
  `requirements-desktop-build.txt` with `pyinstaller==6.22.2`; that is a planned
  file, not an observed build dependency. Tracked-file enumeration did not find
  an implemented PyInstaller spec or this build requirements file.
- The [SEC research design](/tmp/arkscope-listing-sec-macro-convergence/docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md:3)
  explicitly says the new service is not yet implemented. Line 91 proposes
  `sec_research_*` tables in `market_data.db`. Neither proposed SQL nor future
  ingestion behavior can be certified from the present source.

Exact packaging/document inspection commands actually run included:

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:requirements.txt | nl -ba
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:apps/arkscope-desktop/main.js | nl -ba | sed -n '1,45p;100,121p'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:apps/arkscope-desktop/package.json | nl -ba
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence ls-tree -r --name-only HEAD | rg '(^|/)(AGENTS\.md|[^/]*requirements[^/]*|pyproject\.toml|[^/]*\.spec|[^/]*[Dd]ockerfile[^/]*|[^/]*[Pp]y[Ii]nstaller[^/]*|[^/]*sidecar[^/]*|[^/]*build[^/]*)$|\.github/|^docs/[^/]+$'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:docs/superpowers/plans/2026-09-03-desktop-distribution-foundation.md | nl -ba | sed -n '1,25p;40,67p;88,126p'
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence show HEAD:docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md | nl -ba | sed -n '1,30p;89,101p'
```

## Contained Options, Not Actions Performed

1. Use an application-local CPython distribution with its actual SQLite build
   verified separately for Linux, Windows, and macOS. The existing desktop
   launcher can select an explicit interpreter. For example, uv-managed CPython
   uses portable `python-build-standalone` distributions; do not assume a Python
   version number guarantees a particular SQLite patch level.
   [Managed Python distributions](https://docs.astral.sh/uv/concepts/python-versions/#managed-python-distributions).
2. Alternatively, build an application-private CPython/SQLite runtime with
   controlled library linkage, then package natively for each supported OS.
   PyInstaller collects the build interpreter and dependencies; it does not
   independently upgrade SQLite. Updating the CLI, creating another venv on the
   same base interpreter, or changing PyInstaller alone is not a reliable engine
   upgrade. No global library replacement is proposed here.
   [CPython SQLite linkage](https://docs.python.org/3/using/configure.html#envvar-LIBSQLITE3_LIBS),
   [PyInstaller behavior](https://pyinstaller.org/en/stable/operating-mode.html),
   [Python virtual environments](https://docs.python.org/3/library/venv.html).

Any future upgrade needs to account for both the UPSERT and WAL fixes, not stop
at 3.45.2. Existing damage would need a separately authorized investigation;
upgrading the engine does not retroactively repair data. Full integrity checks
and recoverable backups belong to that separate operation, not this assessment.

No installation, dependency change, runtime admission gate, application restart,
or application/database test was implemented or run as part of archiving this
report. The parent can archive the report and independently rerun the isolated
reproducer.

## Evidence Collection And Write Boundary

SQLite release notes, changes, forum posts, and Fossil references were checked
using the web tool. Some Fossil URLs were intermittently unavailable through
that tool. The branch-3.45 fix and WAL-backport pages above were successfully
retrieved with it. The trunk fix overview was additionally retrieved directly
to stdout with this exact command; no source archive was downloaded or applied:

```bash
env -i PATH=/usr/bin:/bin curl -q -fsSL --max-time 20 https://sqlite.org/src/info/d0ea6b6ba6 | sed -n '1,170p'
```

The returned overview identified trunk commit
`d0ea6b6ba64dba9d68c2b391ccf1171ea96fcdd7409dafdb2b697accb00246b8`, dated
2024-03-08, and the redundant-clause fix. Failed attempts to fetch alternate
Fossil/diff URLs were not treated as successful patch inspection. The command
record here covers the substantive probes and scope-defining reads; it is not
a verbatim dump of every tool call, repeated URL attempt, or filename listing.

Repository identity and read-only status were checked with:

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence rev-parse --show-toplevel HEAD
```

```bash
env -i PATH=/usr/bin:/bin GIT_OPTIONAL_LOCKS=0 git -C /tmp/arkscope-listing-sec-macro-convergence status --short --untracked-files=no
```

The original tracked status was empty. HEAD was rechecked before writing this
archive and remained the assessed commit. The intended report path did not
exist; only its parent directory was listed during the archive preflight.
`apply_patch` was used to add this file, not to change application code.

No production database, production configuration, `.env`, credential/token data,
or main-worktree untracked artifact contents were read. No application modules
were imported. Network access was limited to public technical documentation
and source-reference pages. All SQLite runtime work was confined to disposable
in-memory databases; no filesystem-backed SQLite connection was opened.
