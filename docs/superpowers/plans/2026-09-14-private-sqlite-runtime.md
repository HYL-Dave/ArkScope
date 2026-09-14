# Private SQLite Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an executable, verified Linux SQLite package without activating it on production writers.

**Architecture:** A standalone stdlib manifest verifier is shared by a packaged
launcher and early application imports. An offline builder consumes a pinned
official archive and prepares a new package; existing executable selectors can
choose it without rewriting Desktop or SA routing.

**Tech Stack:** Existing Python 3.10, stdlib, SQLite amalgamation, Linux ELF loader, pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-private-sqlite-runtime-design.md`

## Global Constraints

- Linux only. No Python/numpy/dependency upgrade, global loader mutation or production activation.
- A new exclusive package directory; no overwrite, selector update or removal command.
- Selected runtime failures stop before application initialization; absent selection is unmanaged.
- No loader widening for OAuth or dormant `code_executor.py`.
- Use disposable stores and synthetic credentials only; no production paths or selectors.
- Full suites run serially, without concurrent scans, agents or source edits.

## File And Interface Map

- `src/sqlite_runtime/contract.py`: standalone stdlib package and loaded-engine verification.
  `verify_package(root: Path, expected_sha256: str) -> dict`,
  `verify_runtime(root: Path, expected_sha256: str) -> dict`,
  `require_selected_runtime() -> dict | None`; failures use `RuntimeAdmissionError`.
- `src/sqlite_runtime/launch.py`: packaged exec launcher, imports adjacent contract.
- `src/sqlite_runtime/build.py`: pinned source recipe, offline compilation and exclusive package preparation.
  `build_package(archive: Path, destination: Path, python: Path) -> Path`.
- `src/sqlite_runtime/__init__.py`: package documentation only.
- `src/__init__.py`: invoke early selected-runtime guard.
- `tests/test_sqlite_runtime_contract.py`, `tests/test_sqlite_runtime_launch.py`,
  `tests/test_sqlite_runtime_build.py`: pure policy and real process tests.

### Task 1: Closed Package And Engine Verification

- [x] Add tests importing `src.sqlite_runtime.contract` inside test bodies.
  Initial RED is `ModuleNotFoundError: src.sqlite_runtime`.
- [x] Test a synthetic manifest/package with fixed payload names; reject duplicate
  JSON keys, extra fields/objects, traversal, absolute paths, malformed digests,
  unsafe permissions, links and changed artifacts. Require explicit unmanaged
  behavior only when both selection variables are absent.
- [x] Implement package validation and in-memory engine verification. Engine
  reports compare source ID and compile options, not only version.
- [x] Run `pytest -q tests/test_sqlite_runtime_contract.py`; require zero failures.

```python
def test_half_selection_is_not_unmanaged(monkeypatch):
    from src.sqlite_runtime.contract import RuntimeAdmissionError, require_selected_runtime
    monkeypatch.setenv("ARKSCOPE_SQLITE_PACKAGE", "/missing")
    monkeypatch.delenv("ARKSCOPE_SQLITE_MANIFEST_SHA256", raising=False)
    with pytest.raises(RuntimeAdmissionError, match="sqlite_runtime_selection_invalid"):
        require_selected_runtime()
```

### Task 2: Offline Build And Executable Launcher

- [x] Add bad-archive/no-overwrite tests and real process launch tests; initial
  RED is absent `build_package`/launcher. Artifact-dependent tests require an
  explicitly supplied disposable package, never a production runtime lookup.
- [x] Implement the single pinned canonical ZIP recipe, verify archive before
  extraction, generate Lemon grammar with `--enable-update-limit`, record the
  generated amalgamation hash, no global install, no RPATH. The initial default
  amalgamation candidate is rejected: its UDL flag did not enable actual syntax.
- [x] Implement launcher package checks, isolated actual-interpreter probe,
  scoped child env and `os.execve` with untouched user argv.
- [x] Fetch only the official pinned archive into the new evidence workspace;
  build there. Test relocated copy, external symlink, cwd with spaces,
  `-c`/`-m`/stdin, nonzero exits, termination, grandchildren and corrupt payload.
- [x] Require `pytest -q tests/test_sqlite_runtime_build.py tests/test_sqlite_runtime_launch.py`
  to pass; distinguish fixture/system engine from final-artifact cases.

```python
result = subprocess.run([str(selector), "-c", "import sys; sys.exit(19)"],
                        cwd=tmp_path, env=isolated_env, capture_output=True)
assert result.returncode == 19
assert result.stdout == b""
```

### Task 3: Early Application Guard And Acceptance

- [x] Add a subprocess test with malformed runtime selection and a following
  sentinel write; initial RED is sentinel created after `import src`.
- [x] Add the early guard in `src/__init__.py`; keep normal unmanaged imports
  side-effect-free and avoid per-store monkeypatches.
- [x] Prove actual API, SA and worker import paths reject wrong engine before
  stores/provider modules start. Check OAuth closed environments and dormant
  analysis executor unchanged.
- [ ] Run final-artifact UPSERT, synthetic DB and numpy/pandas probes, focused
  launch/auth/startup collateral, then serial full backend with existing offline
  controls. Record exact failures if any, do not normalize expectations blindly.
- [ ] Seal evidence and commit source/test/docs. Keep branch unmerged and real
  activation pending its separately agreed window.

```python
child = subprocess.run([sys.executable, "-c", "import src; open('sentinel', 'w')"],
                       cwd=tmp_path, env=invalid_selection_env, capture_output=True)
assert child.returncode != 0
assert not (tmp_path / "sentinel").exists()
```

## Completion Accounting

This plan closes package preparation and selected-process startup enforcement,
not production activation, C15/C20 cleanup, cross-platform or sandbox work.
