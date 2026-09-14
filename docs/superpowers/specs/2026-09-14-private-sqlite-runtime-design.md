# Private SQLite Runtime Preparation

> **Superseded deployment direction, 2026-09-15.** This describes the historical
> self-built package, not the current deployment target. The user approved
> prebuilt-first evaluation and retreat from the custom build plan. Follow
> [the current runtime policy](../../design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md)
> and [evaluation/removal boundary](../../design/SQLITE_RUNTIME_OPERATIONS.md).
> Earlier evidence remains intact; replacement and production activation are open.

This implements the approved SQLite section of
`docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md` at `42b7ce93`.
Linux only. Preparation is separate from production admission and activation.
No installed selector, application database, Python installation, numpy package,
shell profile or system library is changed by this work.

## Package And Launch Contract

Prepare a new, exclusive directory containing a SQLite-only `lib/`, a standalone
stdlib launcher and verifier, a closed JSON manifest, and an executable `python`
selector. The destination must not exist. No updater, mutable `current` symlink,
uninstaller or automatic pruning is introduced. Immutable generations are
replaceable by a separately verified new generation, not overwritten in place.

The manifest pins the library and bootstrap bytes, unchanged interpreter and
`_sqlite3` extension identity, SQLite version/source ID and complete observed
compile options. The launcher binds the manifest digest. Digests detect drift;
they are not signatures or a sandbox against code running as the same user.
Payload names are fixed; a manifest cannot introduce arbitrary filesystem paths.
Only the prescribed relative SONAME symlink is allowed. Reject unsafe file
shape, hard links, foreign ownership and group/other-writable package objects.
The library directory must contain only the two enumerated SQLite objects.

The executable selector checks pinned manifest/bootstrap SHA-256 values with
the system `sha256sum` before executing package Python code. It bootstraps using
the pinned, existing Python with `-I -S -B`, loading only the explicit verifier
file, never adding the whole package directory to Python's import search path.
It verifies the package before starting a disposable interpreter
probe with the private loader environment. The probe checks the actual Python
SQLite engine, not a standalone CLI. It then execs the unchanged Python with
the original arguments and cwd. Native messaging stdout, stdin, exit codes,
signals, interpreter flags, module and script execution retain Python semantics.
No runpy-based imitation of the Python CLI is used.

Only that Python process and its normal descendants receive the private
`LD_LIBRARY_PATH`, package path and expected manifest digest. An inherited
`LD_PRELOAD` or `LD_AUDIT` is an explicit rejection in both launcher and actual
application-process verifier, not a silent second loading
authority. The selected lib directory replaces rather than extends inherited
search paths. Electron and closed OAuth environments are not modified.

`src` package initialization checks a selected runtime before importing any
application module. This covers direct API factory use, module CLIs, scheduler
children and the native host's application imports. The actual process rechecks
the engine, artifact mapping and manifest; a successful earlier probe alone is
not authority. No package selection means an explicitly unmanaged development
process, not an admitted runtime. Activation will require every supported writer
selector to use the launcher. Direct-library sandbox tests remain outside that
claim, as already decided. No product UI is changed in this preparation slice.

## Engine And Build Contract

The official download and release pages checked on 2026-09-14 still identify
3.53.4 as stable:
[downloads](https://www.sqlite.org/download.html),
[release history](https://www.sqlite.org/changes.html).
Pin its canonical source ZIP SHA3-256 before extraction/code generation. Generate
the amalgamation with `--enable-update-limit` so Lemon sees the grammar option;
record the generated amalgamation SHA3-256, not the different upstream default
amalgamation digest. A future
version is a new reviewed recipe, never a startup network lookup.

Compile the amalgamation as a shared library with SONAME `libsqlite3.so.0`,
without RPATH/RUNPATH or a standalone SQLite CLI. Keep the current feature
profile, particularly `MAX_VARIABLE_NUMBER=250000`, `SECURE_DELETE`, FTS5,
JSON, threading, LIKE behavior, FTS3/4, RTREE, metadata, session/preupdate and
diagnostic virtual tables. Record the actual options and explicit departures
from the old distro engine. Require disposable behavioral probes as well as
option names. Do not claim exact distro equivalence from a flag list alone.

The runtime verifier uses in-memory SQLite only. It compares version/source ID,
complete compile options, the engine function's actual loaded ELF origin and
mapped inode with the hashed package library. It also checks JSON, FTS5 and
required parameter capacity. File-backed acceptance tests use disposable data.
Library/extension/interpreter drift, missing fields, corrupt JSON, unexpected
objects or wrong engine fail before application imports/writes with a fixed
error code, not raw environment/config contents.

## Acceptance And Operational Boundary

RED-first tests own manifest/path rejection, real child/descendant loading,
same-version wrong-artifact rejection, relocation, unrelated cwd, symlink
selector use, argv/stdin/stdout/exit/signal preservation and source-startup
fail-before-import behavior. Re-run the unchanged archived UPSERT reproducer,
synthetic storage probes and native numpy/pandas imports on the final prepared
artifact. Existing backend tests run serially, without concurrent census or
another pytest session. Unmanaged full-suite results and selected-runtime tests
must be labeled separately.

Prepared artifacts and tests do not establish existing-data health, actual
Desktop/installed-SA activation, rollback safety or cross-platform support.
Production admission still requires the agreed stop-writers, selector inventory,
coherent backups, full integrity checks, activation and restart verification
window. No database repair or schema cleanup is included here.
