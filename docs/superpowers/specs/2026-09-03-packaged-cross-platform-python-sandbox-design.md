# Packaged Cross-Platform Python Sandbox Design

**Status:** Approved direction; implementation remains gated. Agent-facing Python
execution stays disabled until the Phase 1 admission gates in this document pass.

## Goal

Restore bounded Python analysis to ArkScope agents without granting model-authored
code access to ArkScope credentials, profile files, arbitrary host files, the
network, child processes, or an unreviewed external runtime.

The capability must ship inside the desktop application and work without Docker,
an externally installed Python, a separately installed CLI, or operator-created
sandbox configuration. Linux is the first implementation and observation host,
but Windows and macOS are release requirements rather than optional follow-ups.

This design also records a later terminal-capability direction. A Python analysis
sandbox and a terminal are different authority levels and must never share one
ambiguous permission.

## Current Boundary

`src/tools/code_executor.py` is an internal compatibility library. Its child
environment is closed, but its CPython subprocess still has the current user's
filesystem, network, process, CPU, and memory authority. AST import checks are not
a security boundary. The module therefore remains absent from every agent
registry, bridge, prompt, subagent, and packaged skill.

The desktop shell is also still a development spike. It launches:

```text
ARKSCOPE_PYTHON || python -m src.api
```

and has no application packager. A distributable ArkScope artifact therefore
needs an embedded Python sidecar independently of this sandbox. Shipping a
WebAssembly analysis runtime while continuing to require a system Python would
not satisfy the user's zero-setup requirement.

## Product Decisions

### Capability levels

ArkScope exposes capability, not implementation, through closed levels:

| Level | Product capability | Default | Authority |
|---|---|---|---|
| L0 | Reviewed deterministic financial calculators | Available | Pure in-process functions; no arbitrary code |
| L1 | `python_analysis` | Ask | Python over explicit JSON input; no network, host filesystem, environment, process, clipboard, or shell |
| L2 | `terminal_scratch` | Off | Commands in one empty ephemeral scratch directory; no profile/workspace access or network |
| L3 | `workspace_code` | Off | Explicit attended grant to selected workspace roots; separate future design |

Phase 1 implements only L1. L2 and L3 cannot be inferred from L1 admission.

### Stable tool contract

L1 restores one tool contract only after runtime admission:

```python
execute_python_analysis(
    code: str,
    data_json: str = "",
    timeout: int = 120,
) -> {
    "success": bool,
    "output": str,
    "error_code": str | None,
    "error": str,
    "execution_time": float,
}
```

The model writes the code directly. There is no nested code-generation model,
hidden retry, background task, transport fallback, or subscription-to-API billing
fallback. The existing deterministic calculators remain preferred for their
closed domains.

`data_json` is copied into the sandbox as parsed JSON. The tool accepts no host
path. It returns text and typed failure metadata, not generated files.

### No fallback

If the packaged sandbox runtime is missing, damaged, version-incompatible, or
unsupported on the current platform, the tool is absent or returns the typed
`sandbox_unavailable` result before code starts. ArkScope must not fall back to:

- `sys.executable`;
- `python` or `python3` from `PATH`;
- Codex, Claude Code, or another harness;
- an API model asked to emulate execution;
- the existing internal subprocess executor.

## Phase 1 Architecture: Portable Analysis Containment

### Why WebAssembly inside a sandboxed renderer

Phase 1 uses a pinned Pyodide distribution inside an Electron/Chromium sandboxed
renderer. This supplies a packaged CPython-compatible scientific environment on
Linux, Windows, and macOS while avoiding native host Python execution.

Pyodide alone is not the security boundary. Python can access its JavaScript
global scope through the `js` module, and browser APIs include network-capable
primitives. The security boundary is the combined renderer process sandbox,
network/session policy, custom protocol allowlist, absent Node integration,
one-shot worker lifecycle, and closed IPC schema.

### Process topology

```text
Agent tool call
    -> FastAPI sidecar SandboxClient
    -> authenticated local sandbox broker
    -> Electron main process
    -> dedicated hidden sandbox BrowserWindow
    -> one dedicated WebWorker
    -> packaged Pyodide runtime + approved wheels
    -> closed result DTO
```

The broker uses a platform-local IPC endpoint, not a listening Internet socket:

- Unix domain socket on Linux and macOS;
- named pipe on Windows;
- a random per-launch bearer value in addition to OS endpoint permissions;
- one request ID and one result per execution;
- exact request/result JSON schemas and bounded frame lengths;
- no generic Electron IPC or Node object exposed to the Python worker.

The renderer page, preload, worker wrapper, runtime assets, and wheel manifest are
packaged read-only resources. Model-authored code is data and is never written to
or loaded as a JavaScript resource.

### Electron renderer policy

The analysis renderer is separate from the ArkScope workbench window and uses:

```text
sandbox=true
contextIsolation=true
nodeIntegration=false
nodeIntegrationInWorker=false
webSecurity=true
webviewTag=false
spellcheck=false
```

`app.enableSandbox()` is applied before readiness so later windows cannot
silently opt out. The analysis renderer has its own ephemeral session partition,
no application preload API, no ArkScope API token, no profile path, no environment
snapshot, and no DevTools in production.

A minimal reviewed preload may relay only an opaque one-shot message port between
Electron main and the trusted worker wrapper. It exposes no `ipcRenderer`, file,
shell, process, environment, clipboard, navigation, or permission primitive.
Its hash is part of runtime admission.

The renderer loads from a privileged custom `arkscope-sandbox://` protocol, never
`file://`. That protocol serves only an exact manifest of sandbox HTML, wrapper
JavaScript, WebAssembly, standard-library archives, and approved wheels. Every
other path and method is rejected.

The session applies all of the following before the page loads:

- deny every Electron permission request and permission check;
- deny navigation, new windows, downloads, external protocol dispatch, and
  clipboard integration;
- cancel every request except an exact GET for a manifest-owned
  `arkscope-sandbox://runtime/...` asset;
- reject `http`, `https`, `ws`, `wss`, `ftp`, `file`, `data`, `blob` navigation,
  and unknown schemes;
- apply a restrictive CSP whose script/worker/connect sources are limited to the
  custom runtime origin and whose object, frame, media, font, form, and base
  sources are disabled.

The custom origin remains readable because Pyodide loads its own packaged
artifacts from it. It contains no profile or application data.

### Worker boundary

Each call creates a fresh renderer and a fresh WebWorker. Pyodide is initialized
inside that worker, not the UI thread. The wrapper loads only the pinned approved
package set, parses `data_json`, captures stdout/stderr, executes once, and posts
one result.

An opaque per-call nonce remains in the trusted JavaScript lexical scope. Messages
posted directly by model-authored Python through `js.postMessage` lack that nonce
and are ignored. Electron main independently validates the request ID, result
shape, lengths, and terminal state.

The worker has only Pyodide's in-memory filesystem. No host directory, profile,
workspace, user-selected file, IndexedDB mount, persistent browser storage, or
Node filesystem bridge is mounted. A new run cannot observe files or globals from
an earlier run.

The approved initial Python packages are:

```text
Python standard library subset supplied by Pyodide
numpy
pandas
scipy
```

Package downloads, `micropip.install`, dynamic wheels, native extensions outside
the sealed manifest, and arbitrary JavaScript modules are unavailable. Adding a
package requires a dependency review, manifest update, package-capability test,
and complete containment replay.

### Resource bounds

No model-context guess is introduced. Request and output bounds are local process
protocol limits, named as bytes rather than tokens or characters, and are exposed
as runtime capability facts.

The initial runtime contract is:

- timeout: caller value clamped to 1 through 120 seconds;
- one execution at a time per worker and no background continuation;
- stdout plus stderr accepted only up to 1 MiB combined;
- request frame accepted only up to 8 MiB;
- result frame accepted only up to 2 MiB;
- renderer private-memory high-water mark: 1 GiB, sampled every 100 ms and
  terminated after two consecutive over-limit samples;
- excess output terminates the worker and returns `sandbox_output_limit`;
- timeout destroys the worker and renderer process and returns
  `sandbox_timeout`;
- memory high-water termination returns `sandbox_memory_limit`;
- renderer crash or out-of-memory termination returns `sandbox_terminated`.

Input is never truncated. The 8 MiB frame limit is a broker availability limit,
not a model or Python capability limit; callers receive `sandbox_input_limit`
before execution. Changing it is a reviewed runtime constant, not a hidden
Settings knob. A measured need may later promote it to Settings without changing
the no-truncation rule.

Electron/Chromium does not by itself give ArkScope a portable, exact hard memory
quota. Phase 1 therefore uses a fresh process, a sealed package set, bounded
frames, process-memory observation, and immediate termination on the reviewed
high-water mark. Admission must explicitly report the measured peak and residual
denial-of-service risk. It may not claim the hard memory guarantee required of
the future terminal layer.

### Result and error contract

Only these user-facing error codes are admitted:

```text
sandbox_unavailable
sandbox_protocol_invalid
sandbox_input_limit
sandbox_output_limit
sandbox_timeout
sandbox_memory_limit
sandbox_terminated
sandbox_python_error
```

Tracebacks are bounded and sanitized. They may contain submitted-code line
numbers and Python exception text, but never IPC endpoint names, runtime paths,
environment values, profile paths, Electron internals, or raw process errors.

## Desktop Distribution Requirement

Phase 1 is not distributable until the desktop artifact carries all of these:

- Electron and Chromium at an explicitly reviewed, supported version;
- the ArkScope web build;
- an embedded, versioned FastAPI sidecar runtime and all Python dependencies;
- the Pyodide runtime and exact approved wheels;
- platform IPC broker code;
- hashes and a signed runtime manifest;
- platform-specific launch and shutdown logic.

Developer mode may continue to honor `ARKSCOPE_PYTHON`, but a packaged build must
never search `PATH` or require an existing venv. It resolves the sidecar only
under `process.resourcesPath`, checks the signed manifest, and fails closed if the
runtime is absent or changed.

The sidecar should be packaged as a directory, not a self-extracting executable,
so startup, native dependencies, antivirus behavior, and resource hashes remain
observable. Builds are produced natively on each target OS/architecture; ArkScope
does not claim cross-platform support from a Linux-only artifact.

Release artifacts must install and pass first-run smoke tests on clean machines
with no system Python, Node, Codex CLI, Claude Code CLI, Docker, or developer
repository present.

## Phase 2 Architecture: Native Terminal Scratch

L2 is a separate future implementation. It may reuse the stable broker and result
envelope, but it executes a packaged native helper under an OS-specific sandbox:

- Linux: a bundled helper applies user/mount/PID/network namespaces, read-only
  runtime mounts, an empty writable scratch mount, `no_new_privs`, seccomp, and
  Landlock where available. Missing required kernel controls fails closed.
- Windows: a bundled launcher uses a low-privilege AppContainer/LPAC token plus a
  Job Object for process, time, memory, and UI limits. No network capability is
  granted. Only packaged runtime files and one scratch directory receive ACLs.
- macOS: a signed, embedded XPC service has its own App Sandbox entitlement set,
  no network entitlement, and only its container scratch directory. A normal
  inherited child process is not accepted as privilege separation.

The stable Windows AppContainer APIs are the baseline. ArkScope may evaluate the
newer `CreateProcessInSandbox` API later, but an experimental or OS-version-limited
API cannot be the sole Windows implementation.

Codex, Claude Code, Hermes, and other open-source harnesses are implementation
references only. ArkScope does not require their binaries and does not inherit
their policy vocabulary as its product contract.

L2 initially receives no profile, repository, browser, clipboard, or network
access. L3 workspace access requires a separate attended consent and file-grant
design. A shell prompt, command text, or model request alone cannot grant it.

## Admission Tests

### Offline contract tests

The test suite must prove:

1. no agent registry contains the tool before runtime admission;
2. admission requires the exact packaged runtime, manifest, Pyodide version,
   Electron security settings, protocol policy, and supported platform;
3. no PATH Python, Codex, Claude, Docker, or host package fallback exists;
4. exact JSON/math/numpy/pandas/scipy workloads succeed;
5. syntax and runtime errors return typed bounded failures;
6. every result is terminal and a timeout leaves no worker or renderer alive;
7. a second run cannot observe the first run's globals or files;
8. parent provider keys and arbitrary sentinel environment values are absent;
9. profile, repository, home, temporary, and explicitly planted trap files are
   unreadable;
10. `fetch`, XHR, WebSocket, EventSource, beacon, browser navigation, and Python
    HTTP adapters cannot reach Internet, loopback, LAN, DNS, or the sidecar;
11. `require`, Node process APIs, Electron IPC, shell, child-process, clipboard,
    dialog, download, and window creation are unavailable;
12. direct `js.postMessage` result forgery is rejected;
13. malformed, oversized, duplicate, late, or wrong-ID messages are rejected;
14. stdout/stderr, request, result, timeout, and measured-memory bounds are owned
    by positive and negative tests;
15. every packaged sandbox asset is manifest-owned and no runtime download occurs.

Each security property needs a positive calibration proving the trap itself is
reachable in an intentionally unconfined fixture. A test that only observes
`false` is not containment evidence.

### Packaged artifact matrix

Linux, Windows x64, macOS Intel, and macOS Apple Silicon artifacts each run:

- clean-machine install/start without developer runtimes;
- sidecar health and ordinary read-only UI smoke;
- sandbox positive scientific workload;
- filesystem, environment, network, process, persistence, timeout, and message
  forgery negative probes;
- app shutdown with zero surviving sidecar, broker, renderer, or worker process;
- signature/notarization verification where the platform supports it.

Windows ARM may be added after the x64 artifact is admitted. It is not silently
claimed by the first Windows release.

## Rollout

1. Keep agent Python disabled while the design and plan are reviewed.
2. Establish desktop distribution with an embedded sidecar and signed resource
   manifest.
3. Implement the broker and portable Pyodide runner behind an internal API.
4. Complete offline adversarial tests on Linux.
5. Build and run the packaged artifact matrix on Windows and macOS.
6. Re-register `execute_python_analysis` behind `code_execution=ASK` only after
   all L1 gates pass.
7. Observe real analyses before opening a separate L2 terminal design.

No phase may weaken a failed gate through fallback. A platform that has not passed
its artifact matrix shows the capability as unavailable with a reason.

## Non-Goals

- General multi-agent orchestration.
- Installing arbitrary packages during a run.
- Running repository tests, git, browser automation, or provider clients in L1.
- Reusing Codex or Claude harness sandboxes as an ArkScope runtime dependency.
- Claiming that renderer containment is equivalent to the future native terminal
  sandbox.
- Migrating provider credentials or changing profile schema.
- Enabling the tool, restarting the App, or making a provider call in this design
  slice.

## External Basis

- Electron process sandbox: https://www.electronjs.org/docs/latest/tutorial/sandbox
- Electron security checklist: https://www.electronjs.org/docs/latest/tutorial/security
- Pyodide usage and workers: https://pyodide.org/en/stable/usage/index.html
- Pyodide JavaScript bridge: https://pyodide.org/en/stable/usage/quickstart.html
- Windows AppContainer isolation: https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation
- Windows AppContainer launch: https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer
- Apple XPC services: https://developer.apple.com/documentation/xpc
- Apple App Sandbox inheritance and XPC guidance: https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html
