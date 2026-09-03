# Packaged Python Analysis Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-admit `execute_python_analysis` as an attended, one-shot agent tool running in a packaged cross-platform WebAssembly sandbox with no host filesystem, environment, network, process, shell, or external-runtime authority.

**Architecture:** The Python sidecar sends a closed request over an authenticated local pipe to Electron main. Electron creates one sandboxed hidden renderer and one WebWorker, runs pinned Pyodide 314.0.6 with only sealed numpy/pandas/scipy assets, validates one closed result, and destroys the process. The tool is registered only after runtime admission and real `code_execution` permission enforcement are both present.

**Tech Stack:** Python 3.10, Electron 43.4.0, Chromium sandbox, Pyodide 314.0.6, WebAssembly, Node test runner, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-03-packaged-cross-platform-python-sandbox-design.md`

## Global Constraints

- Complete `docs/superpowers/plans/2026-09-03-desktop-distribution-foundation.md` first.
- Do not use `src/tools/code_executor.py`, `sys.executable`, PATH Python, Docker, Codex, Claude Code, or a model fallback as the execution transport.
- Generated code is data supplied only to Pyodide. It is never evaluated as JavaScript.
- No runtime package download, host mount, profile path, workspace path, application token, provider key, proxy, or certificate environment enters the sandbox.
- Input and output are never silently truncated.
- L1 does not provide shell, terminal, git, browser, repository editing, or arbitrary package installation.
- Re-admission is blocked until Linux, Windows x64, macOS x64, and macOS arm64 packaged artifact probes pass.
- No provider call, production profile operation, database migration, App restart, merge, or push is part of this plan.

---

### Task 1: Define Closed Cross-Language Contracts

**Files:**
- Create: `src/tools/sandbox_contract.py`
- Create: `apps/arkscope-desktop/sandbox/contracts.js`
- Create: `tests/fixtures/python_sandbox_contract/v1.json`
- Create: `tests/test_python_sandbox_contract.py`
- Create: `apps/arkscope-desktop/sandbox/contracts.test.js`

**Interfaces:**
- Produces: `SandboxRequestV1`, `SandboxResultV1`, `SandboxRuntimeStatusV1`, `parse_sandbox_request`, `parse_sandbox_result`, and matching JavaScript parsers.
- Consumes: UTF-8 JSON frames from the local broker only.

- [ ] **Step 1: Write failing parity and shape tests**

```python
def test_request_contract_is_closed_and_bounded():
    request = parse_sandbox_request({
        "version": 1,
        "request_id": "a" * 32,
        "code": "print(data['x'])",
        "data_json": '{"x": 3}',
        "timeout_s": 10,
    })
    assert request.timeout_s == 10
    with pytest.raises(SandboxProtocolInvalid):
        parse_sandbox_request({**request.as_dict(), "host_path": "/tmp"})
```

Require exact field parity in Python and JavaScript, timeout 1-120, request
frame at most 8 MiB, result at most 2 MiB, stdout+stderr at most 1 MiB, a
32-hex request ID, and the eight closed error codes from the spec.

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest -q tests/test_python_sandbox_contract.py`

Run: `node --test apps/arkscope-desktop/sandbox/contracts.test.js`

Expected: FAIL because neither parser exists.

- [ ] **Step 3: Implement both parsers without coercion**

Reject booleans as integers, unknown fields, missing required fields, malformed JSON text, NaN/Infinity, wrong versions, and strings that exceed UTF-8 byte limits. Preserve Python error text only after bounded sanitization.

- [ ] **Step 4: Run parity tests**

Run: `pytest -q tests/test_python_sandbox_contract.py`

Run: `node --test apps/arkscope-desktop/sandbox/contracts.test.js`

Expected: PASS with both parsers accepting and rejecting every shared fixture identically.

- [ ] **Step 5: Commit**

```bash
git add src/tools/sandbox_contract.py apps/arkscope-desktop/sandbox/contracts.js apps/arkscope-desktop/sandbox/contracts.test.js tests/fixtures/python_sandbox_contract/v1.json tests/test_python_sandbox_contract.py
git commit -m "feat(sandbox): define closed analysis contracts"
```

### Task 2: Vendor A Sealed Pyodide Runtime

**Files:**
- Modify: `apps/arkscope-desktop/package.json`
- Modify: `package-lock.json`
- Create: `apps/arkscope-desktop/sandbox/vendorPyodide.js`
- Create: `apps/arkscope-desktop/sandbox/pyodide-capabilities.json`
- Create: `apps/arkscope-desktop/sandbox/vendorPyodide.test.js`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: upstream Pyodide 314.0.6 runtime and its published release lock metadata at build time.
- Produces: `dist/sandbox-runtime/` and a deterministic subset manifest for core, standard library, numpy, pandas, scipy, and their exact transitive wheels.

- [ ] **Step 1: Write failing dependency-closure tests**

Assert exact Pyodide version `314.0.6`, required roots `{numpy,pandas,scipy}`, no `micropip`, no package outside the computed closure, no remote URL in the runtime manifest, and SHA-256 ownership for every file.

- [ ] **Step 2: Run the test to verify RED**

Run: `node --test apps/arkscope-desktop/sandbox/vendorPyodide.test.js`

Expected: FAIL because no sealed runtime exists.

- [ ] **Step 3: Implement build-time vendoring**

The script fetches only the exact release metadata during the build, verifies upstream hashes, computes the named dependency closure, copies the matching artifacts, rewrites runtime URLs to `arkscope-sandbox://runtime/`, and writes a deterministic local manifest. Runtime code contains no fetch fallback and cannot invoke package installation.

- [ ] **Step 4: Build and inspect the closure**

Run: `node apps/arkscope-desktop/sandbox/vendorPyodide.js`

Run: `node --test apps/arkscope-desktop/sandbox/vendorPyodide.test.js`

Expected: PASS; a second build has byte-identical manifest output.

- [ ] **Step 5: Commit source and lock metadata**

Generated binary assets remain build artifacts rather than Git blobs. Commit the exact upstream/version/hash lock and closure manifest template needed to reproduce them.

```bash
git add apps/arkscope-desktop/package.json package-lock.json apps/arkscope-desktop/sandbox .gitignore
git commit -m "build(sandbox): seal the Pyodide dependency closure"
```

### Task 3: Enforce The Renderer And Protocol Policy

**Files:**
- Create: `apps/arkscope-desktop/sandbox/runtimeProtocol.js`
- Create: `apps/arkscope-desktop/sandbox/sessionPolicy.js`
- Create: `apps/arkscope-desktop/sandbox/sessionPolicy.test.js`
- Modify: `apps/arkscope-desktop/main.js`

**Interfaces:**
- Consumes: verified sandbox resource manifest and Electron `protocol`, `session`, and `BrowserWindow` APIs.
- Produces: `registerSandboxProtocol(manifest)` and `createSandboxSession(runId)` with a deny-by-default policy.

- [ ] **Step 1: Write failing policy tests**

Require exact renderer preferences, an ephemeral partition, no DevTools in production, permission request/check handlers returning false, no downloads/windows/navigation, and a request filter that admits only exact manifest-owned custom-protocol GETs.

Calibrate the filter by proving an intentionally open fixture can contact a local trap server before applying the policy.

- [ ] **Step 2: Run the tests to verify RED**

Run: `node --test apps/arkscope-desktop/sandbox/sessionPolicy.test.js`

Expected: FAIL because the policy does not exist.

- [ ] **Step 3: Implement the custom protocol and isolated session**

Call `app.enableSandbox()` before `app.whenReady()`. Canonicalize every requested resource path under the verified runtime root. Reject unknown methods, ranges, query strings, traversal, symlinks, MIME mismatches, and unmanifested bytes.

Create the hidden window with the exact security preferences from the spec. Install permission, navigation, window, download, and webRequest denials before loading its URL.

- [ ] **Step 4: Run policy tests**

Run: `node --test apps/arkscope-desktop/sandbox/sessionPolicy.test.js`

Expected: PASS for allowed runtime assets and every denied scheme/capability.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-desktop/main.js apps/arkscope-desktop/sandbox/runtimeProtocol.js apps/arkscope-desktop/sandbox/sessionPolicy.js apps/arkscope-desktop/sandbox/sessionPolicy.test.js
git commit -m "fix(sandbox): enforce renderer containment policy"
```

### Task 4: Implement The One-Shot Pyodide Worker

**Files:**
- Create: `apps/arkscope-desktop/sandbox/runner.html`
- Create: `apps/arkscope-desktop/sandbox/runner-preload.js`
- Create: `apps/arkscope-desktop/sandbox/runner.js`
- Create: `apps/arkscope-desktop/sandbox/python-worker.js`
- Create: `apps/arkscope-desktop/sandbox/python-worker.test.js`

**Interfaces:**
- Consumes: one validated `SandboxRequestV1` and sealed Pyodide assets.
- Produces: exactly one nonce-bound `SandboxResultV1`, after which the worker closes.

- [ ] **Step 1: Write positive and negative worker tests**

Positive cases cover JSON, math, numpy, pandas, scipy, Unicode, syntax errors,
runtime exceptions, and empty output. Negative cases cover second execution,
retained globals/files, direct forged `postMessage`, package installation,
oversized output, infinite loop, 1 GiB memory high-water termination after two
100 ms samples, and late result after timeout.

- [ ] **Step 2: Run the tests to verify RED**

Run: `node --test apps/arkscope-desktop/sandbox/python-worker.test.js`

Expected: FAIL because the runner does not exist.

- [ ] **Step 3: Implement trusted wrapper and worker**

The preload relays one MessagePort and nothing else. The page creates one worker. The worker keeps its nonce in lexical JavaScript scope, initializes Pyodide once, loads only manifest packages, redirects stdout/stderr to bounded collectors, parses JSON into `data`, executes `runPythonAsync`, sends one closed result, destroys PyProxy values, and closes.

It never calls `loadPackagesFromImports`; imports outside the preloaded closure fail without a download attempt.

- [ ] **Step 4: Run worker tests in Electron**

Run: `npm run test:sandbox-worker --workspace apps/arkscope-desktop`

Expected: PASS and every timeout leaves zero sandbox windows/workers.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-desktop/sandbox/runner.html apps/arkscope-desktop/sandbox/runner-preload.js apps/arkscope-desktop/sandbox/runner.js apps/arkscope-desktop/sandbox/python-worker.js apps/arkscope-desktop/sandbox/python-worker.test.js apps/arkscope-desktop/package.json package-lock.json
git commit -m "feat(sandbox): execute Python in a one-shot worker"
```

### Task 5: Add The Authenticated Local Broker

**Files:**
- Create: `apps/arkscope-desktop/sandbox/broker.js`
- Create: `apps/arkscope-desktop/sandbox/broker.test.js`
- Create: `src/tools/sandbox_client.py`
- Create: `tests/test_sandbox_client.py`
- Modify: `apps/arkscope-desktop/main.js`

**Interfaces:**
- Produces: `SandboxBroker.start()`, `SandboxBroker.close()`, and `SandboxClient.execute(request) -> SandboxResultV1`.
- Consumes: Unix socket or Windows named-pipe endpoint plus a random per-launch bearer passed only to the sidecar.

- [ ] **Step 1: Write failing cross-language broker tests**

Require UDS permissions `0600`, a current-user named pipe on Windows, bearer authentication, length-prefixed UTF-8 JSON, one in-flight request, duplicate-ID rejection, timeout cancellation, disconnect cleanup, wrong-version rejection, and no endpoint/token in returned errors.

- [ ] **Step 2: Run the tests to verify RED**

Run: `pytest -q tests/test_sandbox_client.py`

Run: `node --test apps/arkscope-desktop/sandbox/broker.test.js`

Expected: FAIL because broker and client do not exist.

- [ ] **Step 3: Implement broker lifecycle**

Electron creates endpoint and bearer before starting the sidecar, passes only `ARKSCOPE_SANDBOX_ENDPOINT` and `ARKSCOPE_SANDBOX_BEARER` to that child, validates every frame, creates one runner, and closes all resources on result/error/timeout/App quit. The sidecar client strips those values from every sandbox request and log record.

- [ ] **Step 4: Run integration tests**

Run: `pytest -q tests/test_sandbox_client.py`

Run: `node --test apps/arkscope-desktop/sandbox/broker.test.js`

Expected: PASS, including kill-during-run and app-quit cleanup.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-desktop/main.js apps/arkscope-desktop/sandbox/broker.js apps/arkscope-desktop/sandbox/broker.test.js src/tools/sandbox_client.py tests/test_sandbox_client.py
git commit -m "feat(sandbox): bridge the sidecar over local IPC"
```

### Task 6: Replace Log-Only Code Permission With Real ASK

**Files:**
- Modify: `src/api/permissions.py`
- Create: `src/permission_runtime.py`
- Create: `src/api/routes/permissions.py`
- Modify: `src/api/app.py`
- Modify: `src/api/routes/query.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Research.tsx`
- Create: `tests/test_permission_runtime.py`
- Create: `tests/test_permission_routes.py`
- Create: `apps/arkscope-web/src/ResearchCodePermission.test.tsx`

**Interfaces:**
- Produces: `permission_scope(run_id)`, `await require_async_permission(PermissionClass.code_execution, action, detail)`, `GET /permissions/pending?run_id=...`, and `POST /permissions/{request_id}/resolve` with `deny | allow_once | allow_session`.
- Consumes: the current active Research run and attended UI response.

- [ ] **Step 1: Write the failing permission-state tests**

Require default ASK, deny on timeout/disconnect/restart, one exact pending request per run/tool call, run-bound `allow_once`, process-session-bound `allow_session`, no approval persistence, and no provider or sandbox dispatch before approval.

- [ ] **Step 2: Run backend RED tests**

Run: `pytest -q tests/test_permission_runtime.py tests/test_permission_routes.py`

Expected: FAIL because `require_permission` is currently a log-only no-op.

- [ ] **Step 3: Implement the in-memory attended permission broker**

Use an `asyncio.Future` keyed by a random request ID and a `ContextVar`-backed
`permission_scope(run_id)` around each Research execution. Validate run ownership
and current pending state on resolution. Expire unresolved requests when the run,
HTTP stream consumer, or sidecar ends. `require_async_permission` awaits the
future without blocking the event loop, so the same sidecar can serve the pending
read and resolution POST. Never store submitted code in the pending DTO; expose
only tool name, capability, timeout, and input byte count.

- [ ] **Step 4: Add the Research modal and interaction test**

While a Research run is active, the UI polls the closed pending endpoint. The
modal explains that Python receives only supplied data and has no
file/network/shell access. It uses explicit Deny, Run once, and Allow for this App
session commands. Escape/close means deny. Focus is trapped and restored.

Run: `npm test --workspace apps/arkscope-web -- --run src/ResearchCodePermission.test.tsx`

Expected: PASS for approve, deny, disconnect, duplicate click, keyboard, and locale cases.

- [ ] **Step 5: Run combined permission gates**

Run: `pytest -q tests/test_permission_runtime.py tests/test_permission_routes.py tests/test_query_streaming.py`

Run: `npm test --workspace apps/arkscope-web -- --run src/ResearchCodePermission.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/api/permissions.py src/permission_runtime.py src/api/routes/permissions.py src/api/app.py src/api/routes/query.py apps/arkscope-web/src/api.ts apps/arkscope-web/src/Research.tsx tests/test_permission_runtime.py tests/test_permission_routes.py apps/arkscope-web/src/ResearchCodePermission.test.tsx
git commit -m "feat(permissions): enforce attended code execution"
```

### Task 7: Re-Admit The Single Python Analysis Tool

**Files:**
- Create: `src/tools/python_analysis_tool.py`
- Modify: `src/tools/registry.py`
- Modify: `src/agents/openai_agent/tools.py`
- Modify: `src/agents/anthropic_agent/agent.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Modify: `src/agents/shared/prompts.py`
- Modify: `src/agents/shared/subagent.py`
- Modify: `src/agents/shared/compressor/reducers.py`
- Modify: `resources/skills/dcf-model/SKILL.md`
- Modify: `resources/skills/comps-analysis/SKILL.md`
- Modify: `resources/skills/earnings-analysis/SKILL.md`
- Modify: `resources/skills/full-analysis/SKILL.md`
- Modify: `resources/skills/sector-rotation/SKILL.md`
- Modify: `tests/test_tool_calling.py`
- Modify: `tests/test_skills.py`
- Modify: `tests/test_subagent.py`

**Interfaces:**
- Consumes: admitted `SandboxClient`, current Research `run_id`, and real code-execution permission.
- Produces: the exact `execute_python_analysis(code, data_json="", timeout=120)` registry/bridge contract.

- [ ] **Step 1: Reverse the current withholding tests to RED**

Require exactly one registry entry and one schema in each model bridge; prohibit `task`, `background`, model, backend, file, command, package, URL, and retry parameters. Require nested subagents to omit the tool by default unless their parent passes an already-approved run-scoped capability.

- [ ] **Step 2: Run focused RED tests**

Run: `pytest -q tests/test_tool_calling.py tests/test_skills.py tests/test_subagent.py`

Expected: FAIL because the tool is intentionally absent.

- [ ] **Step 3: Implement the adapter and exact schemas**

The wrapper validates code/data/timeout, awaits permission, calls the broker once,
serializes the closed result, and never calls `execute_python_code`. The OpenAI
function tool is async. Anthropic's dispatcher gains an async-only branch for this
tool and the message loop awaits it; existing synchronous tools retain their
current dispatch path. Both execute inside the request's `permission_scope`, so a
pending approval suspends only that coroutine and the resolution endpoint remains
responsive. Prompts prefer deterministic calculators for supported finance math
and use Python only for unsupported calculations or tabular analysis.

- [ ] **Step 4: Add no-fallback mutation owners**

Mutate the adapter to call the internal subprocess, skip permission, retry once, accept a host path, or expose the tool to an unapproved subagent. Each mutation must kill a named test.

- [ ] **Step 5: Run tool and bridge gates**

Run: `pytest -q tests/test_tool_calling.py tests/test_skills.py tests/test_subagent.py tests/test_agents.py tests/test_tools.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tools/python_analysis_tool.py src/tools/registry.py src/agents resources/skills tests/test_tool_calling.py tests/test_skills.py tests/test_subagent.py
git commit -m "feat(tools): re-admit sandboxed Python analysis"
```

### Task 8: Prove Containment With Calibrated Adversarial Tests

**Files:**
- Create: `tests/test_packaged_python_sandbox_security.py`
- Create: `apps/arkscope-desktop/sandbox/adversarial.test.js`
- Create: `apps/arkscope-desktop/build/smoke_sandbox.js`
- Modify: `.github/workflows/desktop-artifacts.yml`

**Interfaces:**
- Consumes: packaged app artifacts and local trap servers/files/environment.
- Produces: sanitized machine-readable admission evidence for every claimed platform.

- [ ] **Step 1: Write the complete trap matrix**

Create positive calibrations and confined probes for environment values, home/profile/repository/temp files, loopback/LAN/Internet/DNS, fetch/XHR/WebSocket/EventSource/beacon, Node/Electron/process/shell APIs, navigation/windows/downloads/clipboard, JS message forgery, persistence, timeout, output flood, malformed frame, and package download.

- [ ] **Step 2: Run the unconfined calibrations**

Run: `pytest -q tests/test_packaged_python_sandbox_security.py -k calibration`

Expected: PASS by proving each planted resource is reachable from the deliberately unconfined test fixture.

- [ ] **Step 3: Run the confined current-platform matrix**

Run: `npm run test:sandbox-adversarial --workspace apps/arkscope-desktop`

Run: `pytest -q tests/test_packaged_python_sandbox_security.py -k confined`

Expected: PASS with zero trap hits and zero residual processes.

- [ ] **Step 4: Add the exact matrix to native artifact jobs**

Each Linux, Windows x64, macOS x64, and macOS arm64 job runs the positive scientific workload and the complete negative suite from the installed artifact, then uploads counts, runtime versions, peak memory, process cleanup, and trap-hit booleans. It uploads no submitted code, profile content, environment value, or IPC bearer.

- [ ] **Step 5: Commit**

```bash
git add tests/test_packaged_python_sandbox_security.py apps/arkscope-desktop/sandbox/adversarial.test.js apps/arkscope-desktop/build/smoke_sandbox.js .github/workflows/desktop-artifacts.yml
git commit -m "test(sandbox): calibrate cross-platform containment"
```

### Task 9: Current Documentation And Admission Closeout

**Files:**
- Modify: `docs/design/ARKSCOPE_TOOL_CATALOG.md`
- Modify: `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`
- Modify: `docs/design/DESKTOP_SHELL_SPIKE_PLAN.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/specs/2026-09-03-packaged-cross-platform-python-sandbox-design.md`
- Modify: `docs/superpowers/plans/2026-09-03-packaged-python-analysis-sandbox.md`

**Interfaces:**
- Consumes: exact native artifact evidence and current product surface.
- Produces: an honest L1 GREEN record while leaving L2 terminal and L3 workspace authority explicitly unavailable.

- [ ] **Step 1: Run complete repository gates**

Run: `pytest -q`

Run: `npm test --workspace apps/arkscope-web -- --run`

Run: `npm run typecheck --workspace apps/arkscope-web`

Run: `npm run build`

Run: `node --test apps/arkscope-desktop/*.test.js apps/arkscope-desktop/sandbox/*.test.js`

Run: `git diff --check`

Expected: PASS.

- [ ] **Step 2: Review artifact evidence from all four targets**

Require exact runtime versions and manifests, zero unconfined trap hits, zero surviving processes, and no unsupported platform claim. Stop if any target is absent; do not enable the tool only on the implementer's machine.

- [ ] **Step 3: Update current documentation**

Replace the withheld-tool statement only after Step 2. State that L1 is Python-over-JSON without host access, permission defaults to ASK, deterministic calculators remain preferred, and terminal/workspace execution remains unavailable.

- [ ] **Step 4: Independent security review**

Review the source-to-sink from agent arguments through permission, Python client, local broker, Electron session, worker, Pyodide `js` bridge, result parsing, termination, and packaging. Any plausible host read, network, IPC forgery, external runtime fallback, or post-timeout execution blocks completion.

- [ ] **Step 5: Commit closeout**

```bash
git add docs/design/ARKSCOPE_TOOL_CATALOG.md docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md docs/design/DESKTOP_SHELL_SPIKE_PLAN.md docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/specs/2026-09-03-packaged-cross-platform-python-sandbox-design.md docs/superpowers/plans/2026-09-03-packaged-python-analysis-sandbox.md
git commit -m "docs(sandbox): admit packaged Python analysis"
```

## Completion Gate

The plan is complete only when the installed artifacts, not a repository dev
session, pass every gate on all four target combinations. Until then the current
withheld-tool tests remain authoritative and `execute_python_analysis` stays out
of every agent surface.

The native `terminal_scratch` layer intentionally has no implementation plan in
this document. It opens only after L1 has real usage evidence and receives a
separate Windows AppContainer, macOS XPC/App Sandbox, and Linux namespace/seccomp/
Landlock design review.
