# Desktop Distribution Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce Linux, Windows, and macOS ArkScope desktop artifacts that carry the FastAPI sidecar and require no system Python, Node, Codex CLI, Claude Code CLI, Docker, venv, or repository checkout.

**Architecture:** Freeze `src.api` as a PyInstaller onedir sidecar built natively on each target OS, include it as an Electron Builder resource, and resolve it only beneath `process.resourcesPath` in packaged mode. A signed SHA-256 manifest binds every executable and data resource; development keeps the existing explicit `ARKSCOPE_PYTHON` seam without weakening packaged resolution.

**Tech Stack:** Python 3.10, PyInstaller 6.22.2, Electron 43.4.0, Electron Builder 26.15.7, npm workspaces, Node test runner, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-03-packaged-cross-platform-python-sandbox-design.md`

## Global Constraints

- Packaged mode never searches `PATH` and never reads `ARKSCOPE_PYTHON`.
- Development mode may use an explicit interpreter, but tests must prove that branch is unreachable under `app.isPackaged`.
- Build the sidecar separately on Linux x64, Windows x64, macOS x64, and macOS arm64; PyInstaller is not a cross-compiler.
- Use onedir output, not onefile self-extraction.
- No runtime dependency or artifact is downloaded after installation.
- The packaged sidecar binds loopback on an ephemeral port and retains the existing per-run API token.
- Signing/notarization credentials are not added to the repository. Unsigned CI artifacts are test-only and cannot be labeled public releases.
- No provider call, production profile operation, database migration, App restart, merge, or push is part of this plan.

---

### Task 1: Pin The Distribution Toolchain

**Files:**
- Create: `requirements-desktop-build.txt`
- Modify: `apps/arkscope-desktop/package.json`
- Modify: `package-lock.json`
- Create: `apps/arkscope-desktop/runtimeVersions.js`
- Create: `apps/arkscope-desktop/runtimeVersions.test.js`

**Interfaces:**
- Consumes: npm workspace metadata and Python build requirements.
- Produces: `DESKTOP_RUNTIME_VERSIONS` with exact Electron, Electron Builder, PyInstaller, sidecar protocol, and manifest versions.

- [ ] **Step 1: Write the failing version-owner test**

```javascript
test("desktop distribution dependencies are exact reviewed pins", () => {
  assert.equal(pkg.devDependencies.electron, "43.4.0");
  assert.equal(pkg.devDependencies["electron-builder"], "26.15.7");
  assert.deepEqual(DESKTOP_RUNTIME_VERSIONS, {
    electron: "43.4.0",
    electronBuilder: "26.15.7",
    pyinstaller: "6.22.2",
    sidecarProtocol: 1,
    manifest: 1,
  });
});
```

- [ ] **Step 2: Run the test to verify RED**

Run: `node --test apps/arkscope-desktop/runtimeVersions.test.js`

Expected: FAIL because the exact runtime module and distribution pins do not exist.

- [ ] **Step 3: Add exact pins**

Create `requirements-desktop-build.txt` with `pyinstaller==6.22.2`; pin Electron and Electron Builder without caret ranges; export and freeze the five constants above.

- [ ] **Step 4: Install and verify**

Run: `npm install`

Run: `python -m pip install --dry-run -r requirements-desktop-build.txt`

Run: `node --test apps/arkscope-desktop/runtimeVersions.test.js`

Expected: PASS, and `package-lock.json` resolves the same exact JavaScript versions.

- [ ] **Step 5: Commit**

```bash
git add requirements-desktop-build.txt package.json package-lock.json apps/arkscope-desktop/package.json apps/arkscope-desktop/runtimeVersions.js apps/arkscope-desktop/runtimeVersions.test.js
git commit -m "build(desktop): pin distribution runtimes"
```

### Task 2: Freeze The FastAPI Sidecar As Onedir

**Files:**
- Create: `apps/arkscope-desktop/build/sidecar_entry.py`
- Create: `apps/arkscope-desktop/build/arkscope-sidecar.spec`
- Create: `apps/arkscope-desktop/build/build_sidecar.py`
- Create: `tests/test_desktop_sidecar_bundle.py`

**Interfaces:**
- Consumes: `src.api.app:create_app`, package resources, static configuration defaults, and `ARKSCOPE_API_HOST/PORT/TOKEN`.
- Produces: `dist/desktop-sidecar/arkscope-sidecar/` with one platform-native launcher and a manifest-ready resource tree.

- [ ] **Step 1: Write a failing frozen-entry smoke test**

```python
def test_sidecar_entry_uses_the_existing_api_factory():
    source = Path("apps/arkscope-desktop/build/sidecar_entry.py").read_text()
    assert "from src.api.app import create_app" in source
    assert "uvicorn.run" in source
    assert 'host=os.environ["ARKSCOPE_API_HOST"]' in source
```

Add an integration test that launches a supplied frozen executable with a random port/token, waits for `/healthz`, verifies unauthenticated denial and authenticated success, then terminates it and asserts no child remains.

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest -q tests/test_desktop_sidecar_bundle.py`

Expected: FAIL because the frozen entry and spec do not exist.

- [ ] **Step 3: Implement the entry and PyInstaller spec**

The entry calls the existing application factory and reads the existing host, port, token, and reload environment contract. The spec uses `COLLECT_ALL` only for packages proven to require data files, explicitly includes ArkScope migrations/resources, excludes test/dev modules, and emits onedir output.

The build wrapper must execute:

```python
subprocess.run(
    [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec],
    check=True,
    env=closed_build_environment(),
)
```

It then writes file size and SHA-256 for every output file in deterministic path order.

- [ ] **Step 4: Build and smoke the current platform**

Run: `python apps/arkscope-desktop/build/build_sidecar.py`

Run: `pytest -q tests/test_desktop_sidecar_bundle.py --frozen-sidecar dist/desktop-sidecar/arkscope-sidecar/arkscope-sidecar`

Expected: PASS with no system-Python child after the frozen executable starts.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-desktop/build tests/test_desktop_sidecar_bundle.py
git commit -m "build(desktop): freeze the FastAPI sidecar"
```

### Task 3: Make Packaged Sidecar Resolution Bundled-Only

**Files:**
- Create: `apps/arkscope-desktop/sidecarRuntime.js`
- Create: `apps/arkscope-desktop/sidecarRuntime.test.js`
- Modify: `apps/arkscope-desktop/main.js`

**Interfaces:**
- Consumes: Electron `app.isPackaged`, `process.resourcesPath`, current development repo root, and frozen artifact names.
- Produces: `resolveSidecarLaunch({isPackaged, resourcesPath, platform, arch, env}) -> {executable, args, cwd, mode}`.

- [ ] **Step 1: Write the bundled-only RED matrix**

```javascript
test("packaged mode ignores ARKSCOPE_PYTHON and PATH", () => {
  const launch = resolveSidecarLaunch({
    isPackaged: true,
    resourcesPath: "/app/resources",
    platform: "linux",
    arch: "x64",
    env: { ARKSCOPE_PYTHON: "/trap/python", PATH: "/trap" },
  });
  assert.equal(launch.executable, "/app/resources/sidecar/linux-x64/arkscope-sidecar");
  assert.deepEqual(launch.args, []);
});
```

Add Windows `.exe`, macOS x64/arm64, missing-file, symlink-escape, and dev-mode positive cases.

- [ ] **Step 2: Run the test to verify RED**

Run: `node --test apps/arkscope-desktop/sidecarRuntime.test.js`

Expected: FAIL because `main.js` currently uses `ARKSCOPE_PYTHON || "python"` globally.

- [ ] **Step 3: Implement closed resolution**

Resolve the platform/architecture mapping from a closed table, canonicalize both bundle root and executable, require the executable to remain under the root, and verify the runtime manifest before `spawn`. Keep the development branch explicit and separately named.

- [ ] **Step 4: Run desktop unit tests**

Run: `node --test apps/arkscope-desktop/*.test.js`

Expected: PASS, including the PATH and symlink traps.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-desktop/main.js apps/arkscope-desktop/sidecarRuntime.js apps/arkscope-desktop/sidecarRuntime.test.js
git commit -m "fix(desktop): require the packaged sidecar runtime"
```

### Task 4: Package And Verify The Resource Manifest

**Files:**
- Create: `apps/arkscope-desktop/electron-builder.yml`
- Create: `apps/arkscope-desktop/resourceManifest.js`
- Create: `apps/arkscope-desktop/resourceManifest.test.js`
- Create: `apps/arkscope-desktop/build/build_resource_manifest.py`
- Modify: `apps/arkscope-desktop/package.json`
- Modify: `package-lock.json`

**Interfaces:**
- Consumes: built web renderer, platform sidecar directory, later sandbox resources, and exact runtime versions.
- Produces: Electron artifact resources plus `arkscope-runtime-manifest-v1.json` containing relative path, byte length, SHA-256, platform, architecture, and component owner.

- [ ] **Step 1: Write manifest rejection tests**

Require success for exact bytes and rejection for a missing file, extra executable, changed byte, absolute path, `..` path, duplicate path, wrong platform, and unsupported manifest version.

- [ ] **Step 2: Run the tests to verify RED**

Run: `node --test apps/arkscope-desktop/resourceManifest.test.js`

Expected: FAIL because no verifier exists.

- [ ] **Step 3: Add Electron Builder configuration**

Configure `asar=true`; keep native sidecar and future sandbox assets under `extraResources`; define Linux AppImage, Windows NSIS x64, macOS dmg/zip x64+arm64 test artifacts; and add `dist:desktop`, `dist:sidecar`, and `verify:resources` scripts.

- [ ] **Step 4: Implement deterministic manifest generation and runtime verification**

The builder rejects symlinks and absolute paths, sorts normalized POSIX relative paths, hashes streaming bytes, and signs the final JSON in release jobs. Runtime verification occurs before either sidecar or sandbox broker starts.

- [ ] **Step 5: Build the current platform artifact**

Run: `npm run build`

Run: `npm run dist:sidecar --workspace apps/arkscope-desktop`

Run: `npm run dist:desktop --workspace apps/arkscope-desktop -- --dir`

Run: `node --test apps/arkscope-desktop/*.test.js`

Expected: PASS and the unpacked app contains no unmanifested executable resource.

- [ ] **Step 6: Commit**

```bash
git add apps/arkscope-desktop package-lock.json
git commit -m "build(desktop): package and attest runtime resources"
```

### Task 5: Add Native Build And Clean-Machine Admission Jobs

**Files:**
- Create: `.github/workflows/desktop-artifacts.yml`
- Create: `apps/arkscope-desktop/build/smoke_packaged_app.py`
- Create: `tests/test_desktop_build_contract.py`
- Modify: `docs/design/DESKTOP_SHELL_SPIKE_PLAN.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: the exact build scripts and manifest verifier from Tasks 1-4.
- Produces: native Linux x64, Windows x64, macOS x64, and macOS arm64 test artifacts with machine-readable smoke evidence.

- [ ] **Step 1: Write the workflow contract test**

```python
def test_desktop_matrix_builds_each_claimed_target_natively():
    workflow = yaml.safe_load(Path(".github/workflows/desktop-artifacts.yml").read_text())
    matrix = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
    assert {(row["os"], row["arch"]) for row in matrix} == {
        ("ubuntu-24.04", "x64"),
        ("windows-2025", "x64"),
        ("macos-15-intel", "x64"),
        ("macos-15", "arm64"),
    }
```

Also require the smoke script to clear `PATH` of Python/Node/CLI traps after launch, use a fresh profile, verify authenticated sidecar health, and assert process cleanup.

- [ ] **Step 2: Run the test to verify RED**

Run: `pytest -q tests/test_desktop_build_contract.py`

Expected: FAIL because the matrix and smoke harness do not exist.

- [ ] **Step 3: Add native jobs and evidence**

Each job installs the pinned build tools, builds the onedir sidecar and Electron artifact natively, verifies the resource manifest, installs or unpacks the artifact, starts it with a fresh profile and no developer-runtime PATH, probes health/UI, closes it, and uploads only sanitized logs plus artifact hashes.

- [ ] **Step 4: Update the old spike boundary**

Mark the 2026-06 statement that Python packaging is deferred as superseded for distribution. Record that source-tree development can still use system Python while distributable artifacts cannot.

- [ ] **Step 5: Run local gates**

Run: `pytest -q tests/test_desktop_build_contract.py tests/test_desktop_sidecar_bundle.py`

Run: `node --test apps/arkscope-desktop/*.test.js`

Run: `git diff --check`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/desktop-artifacts.yml apps/arkscope-desktop/build/smoke_packaged_app.py tests/test_desktop_build_contract.py docs/design/DESKTOP_SHELL_SPIKE_PLAN.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "ci(desktop): admit zero-setup platform artifacts"
```

## Completion Gate

This plan is complete only when all four native jobs pass from clean runners and
the resulting unsigned artifacts are clearly marked test-only. Public release
still requires separately provisioned signing/notarization credentials and a
readback of each signed artifact; those credentials never enter repository files
or ordinary test logs.
