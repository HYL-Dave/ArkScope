# Private SQLite Runtime Operations

Linux x86_64 preparation is implemented by `src.sqlite_runtime.build`.
This is not production activation, a Python distribution, or a Python sandbox.
The selected Python installation and its numpy/SDK dependencies remain separate.

The implemented preparation checkpoint is `292ef27f`. Its selected-runtime
full backend passed 11,238 cases with twelve unchanged skips; the exact artifact,
failed attempts and limitations are recorded in the
[preparation receipt](../superpowers/evidence/2026-09-14-private-sqlite-runtime/README.md).
This is not evidence that any installed App selector has switched.

## Prepare A New Generation

Requirements: existing Python 3.10+, `/usr/bin/cc`, GNU make, binutils `readelf`,
coreutils (`readlink`, `dirname`, `sha256sum`, `stat`, `timeout`) and a local copy
of the reviewed official source ZIP. No Python dependency installation is needed.
Upstream's bundled JimTCL is built only inside the disposable build directory.
No Tcl extension or SQLite CLI is installed.

The current recipe accepts only the official `sqlite-src-3530400.zip` with
SHA3-256 `b834d474b9b393d85a9e3ee4cc11f1329e007e9376a424ee740796f5c4bda3a8`.
The archive is verified before source extraction or generator execution.
The generated amalgamation includes the UPDATE/DELETE LIMIT grammar. Merely
setting a C compiler flag on the default downloaded amalgamation does not.
The upstream explanation is in
[compile options](https://www.sqlite.org/compile.html#enable_update_delete_limit).

From the reviewed source root, with deliberately supplied absolute paths:

```bash
python -m src.sqlite_runtime.build \
  --archive /absolute/staging/sqlite-src-3530400.zip \
  --destination /absolute/staging/new-generation \
  --python /absolute/existing-venv/bin/python
```

The destination must not exist, including an empty directory or dangling
symlink. It is not overwritten on retries. A failed preparation may leave an
incomplete, never-selected destination; inspect it and use a new destination.
The compiler/generator scratch is automatically removed. The tool does not
delete old generations, modify executable selectors or automatically activate
anything. Its successful output says `prepared_not_activated`.

The package contains only `manifest.json`, `python`, `contract.py`, `launch.py`
and a SQLite-only `lib/` with its relative SONAME symlink. Use the package's
`python` as an executable selector. Source files can change without rebuilding
this package unless the runtime contract/build recipe itself changes.

```bash
/absolute/staging/new-generation/python -c 'import sqlite3; print(sqlite3.sqlite_version)'
/absolute/staging/new-generation/python -m src.daily_update --help
```

The launcher verifies fixed bootstrap hashes, package inventory and interpreter
identity, probes the actual loaded engine and execs the original Python CLI.
Application imports recheck the selected engine. Fixed error codes on stderr
stop startup; the native-host stdout protocol is not used for diagnostics.
Hashing is bounded and rejects non-regular bootstrap files. Digests detect
drift, not hostile code running with the installation owner's privileges.

## Supported Selectors And Scope

- Desktop: existing `ARKSCOPE_PYTHON` points to the package's `python` executable.
  Do not put `LD_LIBRARY_PATH` on Electron/npm or in a shell profile.
- SA: existing native-host JSON `python_path` points to the same generation's
  selector. Its `project_root` and `host_script` remain unchanged. Reinstallation
  of the extension can reset this field; verify the installed selector again.
- Supported operator/test CLI: invoke the same selector explicitly. Scheduled
  Python children inherit the pinned package and loader environment and recheck
  when they import application code.
- Plain unselected Python remains an unmanaged development path, not evidence
  that the App-private runtime is active. The dormant analysis executor and
  isolated provider CLI environments are not new-runtime writer coverage.

Tests accept an explicit `ARKSCOPE_TEST_SQLITE_ARCHIVE` to compile and exercise a
disposable final artifact. If absent, the artifact tests explicitly skip rather
than downloading, inspecting an installed runtime or passing against the system
library. Release acceptance must supply it and account for those test nodes.

## Activation Window Still Required

The durable target is `~/.local/share/arkscope/runtimes/`. Preparing a package
does not authorize writing that installation or inspecting private selectors.
During the separately agreed window, inventory all supported writers/stores,
stop API, browser native-host requests and standalone/maintenance workers, take
exclusive coherent WAL-safe backups and run full integrity checks on verification
copies. Retain SEC referenced content and the old source/selector bindings.
Do not use `immutable=1` on live WAL stores, clobber backups or silently repair data.

Only then install a new generation, change both executable selectors, verify
their actual loaded engines and resume writes on the approved source revision.
After resumed writes, changing a selector alone is not a proved rollback. A
restore/repair decision remains separate. No automatic fallback, REINDEX,
VACUUM, schema reset or database deletion belongs to engine activation.

Future stable SQLite releases require a new reviewed source hash/recipe and
fresh artifact/engine tests. This is an upgradeable pre-release runtime, not a
promise to keep 3.53.4 indefinitely. Windows/macOS admission is separate.
