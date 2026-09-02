# Code Execution Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop agent-authored Python from directly inheriting ArkScope credentials, retire the hidden code-generation/CLI fallback path, and make the remaining Claude OAuth probe use only the reviewed bundled runtime.

**Architecture:** Keep one direct Python executor library: the calling model, if the product tool is admitted after the open safety decision, authors code and the existing tool loop owns correction. Launch it with a closed child environment, but describe it honestly as a restricted subprocess rather than an OS sandbox. Remove the nested model generator and its external-CLI/API fallback surface; replace the obsolete Claude P3 subprocess probes with the existing fail-closed structured-output SDK path, and remove default Codex account-usage fallback to an external `PATH` binary.

**Tech Stack:** Python 3, `subprocess`, pytest, OpenAI Agents SDK tool wrappers, Anthropic tool schemas.

**Spec:** User-approved convergence in the 2026-09-03 thread; current product boundary in `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` and runtime admission in `docs/design/CLAUDE_AGENT_SDK_RUNTIME_ADMISSION.md`.

## Global Constraints

- No provider call, production profile read/write, database migration, App restart, merge, or push.
- Never pass a parent environment wholesale to agent-authored code.
- The immediate environment fix is not an OS sandbox: filesystem, process, network, CPU, memory, and output containment remain a separate design and implementation slice.
- The Claude credential probe must use the reviewed `claude-agent-sdk` bundled binary; no `PATH` lookup or external CLI fallback.
- Remove hidden model retries and all automatic subscription-to-API billing fallback by deleting the nested code generator.
- Open decision before Task 3: default-disable the agent-facing Python tool until real OS containment exists (recommended), or knowingly retain its narrowed direct-code surface.

---

### Task 1: Close The Python Child Environment

**Files:**
- Modify: `tests/test_code_executor.py`
- Modify: `src/tools/code_executor.py`

**Interfaces:**
- Consumes: `execute_python_code(code: str, data_json: str = "", timeout: int = 120)`.
- Produces: `_python_child_environment(source: Mapping[str, str] | None = None) -> dict[str, str]`, containing only fixed Python I/O settings plus approved locale/timezone values.

- [x] **Step 1: Write the failing regression test**

Add real subprocess tests that place inert sentinel values under provider-, cloud-, and arbitrary-looking names in the parent environment, dynamically read the child environment, and require all sentinels to be absent while normal Python execution still succeeds. Exercise both foreground and background while both paths still exist, and cross the real `.env` loader plus profile `apply_env()` producers with fake values.

- [x] **Step 2: Run the focused RED test**

Run: `pytest -q tests/test_code_executor.py -k child_environment`

Expected: FAIL because the current subprocess inherits the sentinel values.

- [x] **Step 3: Pass a closed environment to every surviving Python subprocess**

Build a fresh mapping instead of copying `os.environ`; preserve only `LANG`, `LANGUAGE`, `LC_*`, and `TZ`, and set deterministic Python UTF-8/unbuffered values. Pass it through `subprocess.run(..., env=...)`.

- [x] **Step 4: Run focused executor tests**

Run: `pytest -q tests/test_code_executor.py`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/tools/code_executor.py tests/test_code_executor.py
git commit -m "fix(tools): stop Python child credential inheritance"
```

### Task 2: Replace Obsolete OAuth And PATH Probes

**Files:**
- Modify: `tests/test_claude_oauth_probe.py`
- Modify: `src/auth_drivers/claude_oauth_probe.py`
- Modify: `src/api/routes/config_routes.py`
- Modify: `tests/test_oauth_import_route.py`
- Modify: `tests/test_chatgpt_oauth_routes.py`
- Delete: `src/auth_drivers/claude_code_oauth_driver.py`
- Delete: `tests/test_claude_code_oauth_driver.py`
- Modify: `src/auth_drivers/factory.py`
- Modify: `tests/test_subscription_account_usage.py`
- Modify: `src/auth_drivers/codex_account_usage.py`

**Interfaces:**
- Consumes: `run_subscription_structured_output(...)`, whose Claude path already enforces the reviewed bundled CLI, closed environment, isolated config/cwd, and literal `apiKeySource == "none"`.
- Produces: a one-call Settings credential probe keyed by `credential_id` and token store; the obsolete raw-token-as-API-key negative probe and superseded external-CLI driver are absent. Default Codex account-usage launch uses only `openai-codex`'s bundled executable.

- [x] **Step 1: Write the failing probe-contract tests**

Assert the Settings route passes credential identity and token-store authority, the probe delegates exactly once to the Claude structured-output adapter with no retry/fallback, and only a valid closed response passes. Assert the old external CLI and raw-SDK negative surfaces are absent.

- [x] **Step 2: Run the focused RED test**

Run: `pytest -q tests/test_claude_oauth_probe.py tests/test_oauth_import_route.py -k 'probe or bundled'`

Expected: FAIL because the current implementation receives a raw token, uses `shutil.which("claude")`, and treats any raw-SDK exception as successful evidence.

- [x] **Step 3: Replace the P3 probes and remove dead external CLI code**

Call the existing bounded Claude structured-output path once with a fixed boolean schema. It already verifies `apiKeySource == "none"` before accepting output. Remove the raw-SDK rejection probe and superseded `claude_code_oauth_driver.py`; update the factory comments so no product code suggests the external CLI remains a supported diagnostic.

- [x] **Step 4: Run auth-focused tests**

Run: `pytest -q tests/test_claude_oauth_probe.py tests/test_oauth_import_route.py tests/test_chatgpt_oauth_routes.py tests/test_claude_agent_sdk_runtime.py tests/test_claude_code_sdk_driver.py tests/test_subscription_structured_output.py`

Expected: PASS.

- [x] **Step 5: Make Codex account usage fail closed without its bundle**

Replace the `return "codex"` default with the existing typed `adapter_unavailable` error. Keep explicit executable injection for deterministic tests, but prove a `PATH` sentinel is never selected by the product default.

- [x] **Step 6: Run account-usage tests**

Run: `pytest -q tests/test_subscription_account_usage.py`

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add -A src/auth_drivers src/api/routes/config_routes.py tests/test_claude_oauth_probe.py tests/test_claude_code_oauth_driver.py tests/test_oauth_import_route.py tests/test_chatgpt_oauth_routes.py tests/test_subscription_account_usage.py
git commit -m "fix(auth): remove external CLI probe fallbacks"
```

### Task 3: Retire Nested Code Generation

**Files:**
- Delete: `src/tools/code_generator.py`
- Delete: `tests/test_code_generator.py`
- Modify: `src/tools/code_executor.py`
- Modify: `src/tools/registry.py`
- Modify: `src/agents/openai_agent/tools.py`
- Modify: `src/agents/anthropic_agent/tools.py`
- Modify: `src/agents/shared/prompts.py`
- Modify: `src/agents/shared/subagent.py`
- Modify: `src/agents/shared/compressor/reducers.py`
- Modify: `src/agents/config.py`
- Modify: `config/user_profile.yaml`
- Modify: `tests/test_tool_calling.py`
- Modify: `tests/test_fable_5_1_runtime.py`

**Interfaces:**
- Consumes: direct caller-authored Python and JSON data.
- Produces: if admitted by the open safety decision, one three-surface contract with required `code`, optional `data_json`, and optional bounded `timeout`; otherwise no agent registration until OS containment lands. In either case there is no `task`, `background`, `generated_code`, PID, output file, code model, code backend, hidden retry, CLI, or billing fallback.

- [x] **Step 1: Rewrite contract tests first**

Require exact parameter parity across registry, OpenAI, and Anthropic surfaces; require direct code execution; require the obsolete generator module and three config fields to be absent. Remove tests whose sole purpose was to preserve the retired behavior.

- [x] **Step 2: Run the focused RED contract tests**

Run: `pytest -q tests/test_tool_calling.py tests/test_code_executor.py tests/test_fable_5_1_runtime.py`

Expected: FAIL on the still-present task/background/config/generator surfaces.

- [x] **Step 3: Remove the retired implementation and narrow every product surface**

Delete `code_generator.py`; remove the task/background dispatch and result fields; make each bridge expose only the common direct-code schema; update prompts so the current model writes code and uses its normal tool loop to inspect errors and retry explicitly.

- [x] **Step 4: Remove stale configuration and references**

Delete `code_model`, `code_max_retries`, and `code_backend` from `AgentConfig` and profile loading; remove the sample config entry and stale compressor comments. Keep historical design records unchanged unless they claim to describe the current surface.

- [x] **Step 5: Run the focused convergence suite**

Run: `pytest -q tests/test_code_executor.py tests/test_tool_calling.py tests/test_agents.py tests/test_tools.py tests/test_subagent.py tests/test_compressor_reducers.py tests/test_fable_5_1_runtime.py`

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add -A src/tools src/agents config/user_profile.yaml tests
git commit -m "refactor(tools): retire nested code generation"
```

### Task 4: Current Documentation And Verification

**Files:**
- Modify: `docs/design/ARKSCOPE_TOOL_CATALOG.md`
- Modify: `docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: the narrowed direct-code tool contract.
- Produces: current documentation that calls the runtime a restricted subprocess and records full OS containment as an unresolved security prerequisite.

- [x] **Step 1: Add documentation contract tests or existing-doc assertions where appropriate**

Extend the exact tool-surface tests to reject `task` and `background` in current catalog rows and to require explicit non-sandbox wording.

- [x] **Step 2: Run the RED documentation checks**

Run: `pytest -q tests/test_tool_calling.py`

Expected: FAIL against the stale catalog/product wording.

- [x] **Step 3: Update current documentation and decision history**

Record the security source-to-sink, the retired hidden model/fallback path, the remaining filesystem/network/resource containment gap, and the fact that no live provider call was made.

- [ ] **Step 4: Verify scope and behavior**

Run focused tests, `git diff --check`, repository reference scans for `code_generator`, external PATH Claude/Codex use in product code, and then the complete backend suite.

- [ ] **Step 5: Independent post-patch security review**

Have a read-only reviewer attempt to disprove direct-environment isolation, find remaining generator/fallback entry points, and distinguish residual OS-sandbox risk from fixed inheritance.

- [ ] **Step 6: Commit**

```bash
git add docs/design/ARKSCOPE_TOOL_CATALOG.md docs/design/ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md docs/design/PROJECT_PRIORITY_MAP.md tests/test_tool_calling.py docs/superpowers/plans/2026-09-03-code-execution-convergence.md
git commit -m "docs(tools): record code execution boundary"
```
