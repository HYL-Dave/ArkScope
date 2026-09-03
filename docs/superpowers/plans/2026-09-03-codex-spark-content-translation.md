# Codex Spark Content Translation Implementation Plan

> **Historical plan notice (2026-09-03):** The original Pro-name admission
> described below is superseded by the current authority in
> `docs/superpowers/specs/2026-09-02-codex-spark-content-translation-design.md`.
> Exact same-credential `model/list` observation now controls Spark execution;
> raw `planType` is diagnostic and a Spark usage bucket is only a revalidation
> hint. This file is retained as the RED-first implementation record and must
> not be used as current admission policy.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit `gpt-5.3-codex-spark` as an optional Content Translation model only for an exact, discovered ChatGPT Pro OAuth credential, using the bundled Codex app-server with no fallback.

**Architecture:** Extend the reviewed model registry with closed task/auth/plan/adapter facts, then derive picker and route admission from those facts. Extract the existing Codex app-server process boundary into a shared bundled-only runtime and add a single-turn Spark structured-output adapter behind the existing subscription dispatcher. Keep the shared translation schema and validation authoritative; lifecycle storage keeps its existing 16,000-character boundary.

**Tech Stack:** Python 3.10, Pydantic, `jsonschema`, FastAPI, SQLite discovery cache, `openai-codex==0.147.0`, Codex app-server JSON-RPC/JSONL, React 18, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-02-codex-spark-content-translation-design.md`

## Global Constraints

- The only admitted tuple is `card_translation/openai/gpt-5.3-codex-spark/chatgpt_oauth/pro/codex_app_server`.
- Spark remains non-default, exact-ID only, text-only, and unavailable to API keys, Plus, AI Research, synthesis, generic agents, subagents, compression, calibration, and code execution.
- All Codex operations use the `openai-codex` bundled binary; external `PATH` lookup and provider/model/auth fallback are forbidden.
- One fresh process, Codex home, config home, temp directory, and empty working directory are created for each Spark translation.
- The adapter performs no retry, starts one thread and one turn, and terminates/reaps the process on every result, refusal, protocol error, timeout, or cancellation.
- `ModelCapability.max_output=None` means unknown provider fact and may never enter token arithmetic or provider parameters.
- Shared Content Translation never truncates and has no ArkScope character/token ceiling; lifecycle API/cache/SQLite limits remain unchanged.
- No database migration, provider call, production profile read/write, App restart, merge, or push occurs during offline implementation.
- The current Plus account must receive an honest Pro-required refusal before `turn/start`; a successful live Spark canary remains separately authorized and requires an eligible Pro account.
- Account observation retains its existing 64 KiB request / 256 KiB stdout / 64 KiB stderr protocol budgets. Spark uses 2 MiB per request line / 16 MiB aggregate stdout / 256 KiB stderr; these encoded-byte guards exceed a 600,000-character translation fixture and are local process-containment limits, not model token claims.

---

### Task 1: Closed Spark Capability And Unknown Output Fact

**Files:**
- Modify: `src/model_capabilities.py`
- Modify: `src/agents/openai_agent/agent.py`
- Modify: `src/agents/anthropic_agent/agent.py`
- Test: `tests/test_model_capabilities.py`
- Test: `tests/test_agents.py`

**Interfaces:**
- Produces: `ModelCapability.allowed_tasks`, `allowed_auth_modes`, `required_plans`, `exact_model_id`, `execution_adapter`, and `max_output: int | None`.
- Produces: task/auth/plan-aware `model_execution_admission_detail(model, *, task=None, auth_mode=None, plan_type=None)`.
- Consumed by: Tasks 2, 4, 5, and 6.

- [ ] **Step 1: Write failing registry and admission tests**

```python
def test_spark_is_exact_pro_oauth_content_translation_only():
    cap = capability_for("gpt-5.3-codex-spark")
    assert cap is not None
    assert cap.max_output is None
    assert cap.allowed_tasks == ("card_translation",)
    assert cap.allowed_auth_modes == ("chatgpt_oauth",)
    assert cap.required_plans == ("pro",)
    assert cap.exact_model_id is True
    assert cap.execution_adapter == "codex_app_server"
    assert capability_for("gpt-5.3-codex-spark-preview") is None

def test_spark_generic_and_plus_execution_fail_closed():
    assert model_execution_admission_detail("gpt-5.3-codex-spark") == {
        "code": "model_task_unsupported", "field": "task"
    }
    assert model_execution_admission_detail(
        "gpt-5.3-codex-spark", task="card_translation",
        auth_mode="chatgpt_oauth", plan_type="plus",
    ) == {"code": "subscription_plan_required", "field": "credential"}
```

- [ ] **Step 2: Run RED tests**

Run: `pytest -q tests/test_model_capabilities.py tests/test_agents.py`

Expected: fail because the policy fields, Spark row, and unknown-output handling do not exist.

- [ ] **Step 3: Add the capability row and task-aware admission**

Implement exact matching before prefix matching, normalize plan strings by `strip().lower()`, and return only closed `{code, field}` payloads. Existing unrestricted models keep current behavior through empty policy tuples and `execution_adapter="provider_native"`.

- [ ] **Step 4: Keep unknown maxima out of eager maps**

```python
_OPENAI_MODEL_MAX_OUTPUT = {
    c.id: c.max_output
    for c in _all_capabilities("openai")
    if c.max_output is not None
}

def _get_openai_max_output(model: str) -> int:
    cap = _capability_for(model)
    if cap is not None and cap.provider == "openai":
        if cap.max_output is None:
            raise ValueError({"code": "model_output_limit_unknown", "field": "model"})
        return cap.max_output
    return _OPENAI_DEFAULT_MAX_OUTPUT
```

Apply the same filter-and-reject rule to Anthropic's `_MODEL_MAX_OUTPUT` and `_get_model_max_output`.

- [ ] **Step 5: Run focused tests and commit**

Run: `pytest -q tests/test_model_capabilities.py tests/test_agents.py tests/test_fable_5_1_runtime.py`

Commit: `feat(models): admit Spark translation capability`

---

### Task 2: Credential Plan, Discovery, Picker, And Route Admission

**Files:**
- Modify: `src/model_effective.py`
- Modify: `src/model_credentials.py`
- Modify: `src/model_routing.py`
- Modify: `src/api/routes/config_routes.py`
- Modify: `src/auth_drivers/chatgpt_oauth_driver.py`
- Test: `tests/test_model_effective.py`
- Test: `tests/test_model_routing.py`
- Test: `tests/test_chatgpt_oauth_driver.py`
- Test: `tests/test_chatgpt_oauth_routes.py`

**Interfaces:**
- Produces: `ActiveCredential.plan_type: str | None` from the authoritative token-store record.
- Produces: task-aware route admission that requires the exact Spark tuple before a route save or task test.
- Consumed by: Tasks 5, 6, and 7.

- [ ] **Step 1: Write failing eligibility matrix tests**

```python
@pytest.mark.parametrize(
    ("task", "auth_mode", "plan_type", "visible", "eligible", "reason"),
    [
        ("card_translation", "chatgpt_oauth", "pro", True, True, None),
        ("card_translation", "chatgpt_oauth", "plus", True, False, "subscription_plan_required"),
        ("card_synthesis", "chatgpt_oauth", "pro", True, False, "model_task_unsupported"),
        ("ai_research", "chatgpt_oauth", "pro", True, False, "model_task_unsupported"),
        ("card_translation", "api_key", None, True, False, "task_auth_mode_unsupported"),
    ],
)
def test_spark_effective_picker_matrix(
    tmp_path, task, auth_mode, plan_type, visible, eligible, reason,
):
    cache = ModelDiscoveryCache(tmp_path / "profile.db")
    cache.record_run(
        provider="openai",
        auth_mode=auth_mode,
        credential_id="local:1",
        secret_fingerprint="oauth",
        status="ok",
        models=[{
            "id": "gpt-5.3-codex-spark",
            "label": "GPT-5.3-Codex-Spark",
            "source": "provider_api",
        }],
    )
    route = TaskRoute(
        task=task,
        provider="openai",
        model="gpt-5.3-codex-spark",
        effort="medium",
    )
    view = effective_model_view_v2(
        cache=cache,
        routes={task: route},
        credentials={
            "openai": ActiveCredential(
                provider="openai",
                credential_id="local:1",
                auth_mode=auth_mode,
                secret_fingerprint="oauth",
                plan_type=plan_type,
            ),
            "anthropic": None,
        },
    )
    entry = next(
        item
        for item in view["tasks"][task]["providers"]["openai"]["models"]
        if item["id"] == "gpt-5.3-codex-spark"
    )
    assert entry["visible_to_credential"] is visible
    assert entry["eligible"] is eligible
    assert entry["reason_code"] == reason
```

Add a real token-store test proving `resolve_active_credential()` reads `plan_type` from the selected OAuth record and never infers it from aliases such as `ChatGPT subscription Pro`.

- [ ] **Step 2: Run RED tests**

Run: `pytest -q tests/test_model_effective.py tests/test_model_routing.py tests/test_chatgpt_oauth_driver.py tests/test_chatgpt_oauth_routes.py`

Expected: Plus and task restrictions are not represented in the effective view.

- [ ] **Step 3: Thread task and plan through backend admission**

Add `plan_type` to `ActiveCredential`, pass `task` at every `task_route_admission_detail` call site, and make save/import/test routes fail closed for Spark when task, auth, plan, or exact discovery is wrong. Existing model behavior must remain byte-for-byte equivalent in tests.

- [ ] **Step 4: Make discovery task projection exact**

`chatgpt_oauth_driver._task_route_tasks()` must return `[]` for Spark unless task admission is evaluated with `card_translation`, `chatgpt_oauth`, and `pro`. The provider model-list observation remains displayable for Plus, but its executable task list stays empty.

- [ ] **Step 5: Run focused tests and commit**

Run: `pytest -q tests/test_model_effective.py tests/test_model_routing.py tests/test_chatgpt_oauth_driver.py tests/test_chatgpt_oauth_routes.py tests/test_model_task_test.py`

Commit: `feat(models): enforce Spark entitlement admission`

---

### Task 3: Shared Bundled Codex App-Server Runtime

**Files:**
- Create: `src/auth_drivers/codex_app_server_runtime.py`
- Modify: `src/auth_drivers/codex_account_usage.py`
- Create: `tests/test_codex_app_server_runtime.py`
- Modify: `tests/test_subscription_account_usage.py`

**Interfaces:**
- Produces: `CodexAppServerRuntime`, `CodexJsonlSession`, and `run_authenticated_codex_operation(*, record, client_name, timeout_seconds, executable, allowed_notifications, operation)` with closed runtime errors.
- Produces: a notification-aware JSONL reader with one monotonic deadline and configurable encoded-byte budgets.
- Consumed by: Task 4 and the existing account observation adapter.

- [ ] **Step 1: Write failing runtime parity and security tests**

```python
def test_default_runtime_is_inside_codex_cli_bundle_and_never_uses_path(monkeypatch):
    monkeypatch.setenv("PATH", str(fake_external_codex.parent))
    runtime = resolve_codex_app_server_runtime()
    assert runtime.target.is_relative_to(runtime.bundle_root)
    assert runtime.target != fake_external_codex

def test_authenticated_runtime_child_environment_excludes_parent_secrets(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "sentinel")
    executable, transcript = write_runtime_fixture(tmp_path)
    run_authenticated_codex_operation(
        record=token_record(plan_type="plus"),
        client_name="runtime-test",
        timeout_seconds=2.0,
        executable=executable,
        allowed_notifications=frozenset(),
        operation=lambda session, context: session.request(4, "fixture/read"),
    )
    captured_environment = json.loads(transcript.read_text())["environment"]
    assert "OPENAI_API_KEY" not in captured_environment
```

Add parity tests showing account usage still accepts the reviewed 0.147/0.151 versions, NVM-style shebang fixtures, and the existing account notifications.

- [ ] **Step 2: Run RED tests**

Run: `pytest -q tests/test_codex_app_server_runtime.py tests/test_subscription_account_usage.py`

Expected: shared runtime interfaces are missing.

- [ ] **Step 3: Extract process ownership without changing account parsing**

Move bundled-path resolution, launcher/target checks, version probe, clean environment, process-group termination, and JSONL framing into the new module. `codex_account_usage.py` retains account/rate-limit/model projection and delegates runtime ownership to the new module.

- [ ] **Step 4: Add notification-aware framing**

The reader accepts only a caller-provided notification set, rejects every server request (`id` plus `method`), enforces exact response IDs, and counts encoded stdout/stderr/request bytes. It never returns partial JSON or silently ignores unknown methods.

- [ ] **Step 5: Run focused tests and commit**

Run: `pytest -q tests/test_codex_app_server_runtime.py tests/test_subscription_account_usage.py tests/test_chatgpt_oauth_driver.py`

Commit: `refactor(auth): share bundled Codex runtime`

---

### Task 4: Single-Turn Spark Protocol Adapter

**Files:**
- Create: `src/auth_drivers/codex_translation_adapter.py`
- Create: `tests/fixtures/codex_translation/codex-app-server-0.147.0-contract.json`
- Create: `tests/test_codex_translation_adapter.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `run_codex_translation(*, credential_id, record, model, effort, system, user, schema, timeout_s, executable=None) -> dict[str, Any]` and `CodexTranslationError(code)`.
- Consumes: the shared runtime from Task 3 and the token-store `StoredTokenRecord`.
- Consumed by: Task 5.

- [ ] **Step 1: Commit a reviewed schema projection and failing contract test**

The fixture records the exact properties/required fields consumed from `initialize`, `account/login/start`, `account/read`, `model/list`, `thread/start`, `turn/start`, `thread/started`, `turn/started`, `item/started`, `item/completed`, and `turn/completed`, plus SHA-256 values of the generated source schemas. The test compares this projection with adapter constants and the reviewed version allowlist.

- [ ] **Step 2: Write fake app-server RED tests**

Cover one successful sequence and one test for every rejection family: Plus/unknown plan, exact model absent, model echo mismatch, non-empty instruction/workspace sources, command/file/MCP/browser/image/dynamic/subagent item, server request, wrong thread/turn ID, duplicate/missing final message, malformed/fenced/extra-key JSON, non-completed turn, byte exhaustion, timeout, and cancellation. Each rejection test records that the fake server reached the intended guard and that its PID exited.

- [ ] **Step 3: Run RED tests**

Run: `pytest -q tests/test_codex_translation_adapter.py`

Expected: adapter module is missing.

- [ ] **Step 4: Implement exact pre-turn admission**

The adapter must authenticate, require token-store plan `pro`, require live `account/read.planType == "pro"`, require exact Spark in `model/list`, then send exactly one `thread/start` with an empty temporary cwd, `approvalPolicy="never"`, `sandbox="read-only"`, `ephemeral=true`, empty dynamic tools/environments/workspace roots, and `allowProviderModelFallback=false`. It validates the complete echo before sending `turn/start`.

- [ ] **Step 5: Implement exact turn admission and cleanup**

Send one text input and the existing output schema with `sandboxPolicy={"type":"readOnly","networkAccess":false}`. Accept reasoning/status events plus exactly one completed `agentMessage`; reject all tool-bearing items and server requests. Parse one bare JSON object, validate against the supplied schema, terminate/reap the process, and delete temporary state in `finally`.

- [ ] **Step 6: Run focused tests and commit**

Run: `pytest -q tests/test_codex_translation_adapter.py tests/test_codex_app_server_runtime.py`

Commit: `feat(auth): add isolated Spark translation adapter`

---

### Task 5: Shared Translation Dispatch And Failure Semantics

**Files:**
- Modify: `src/auth_drivers/subscription_structured_output.py`
- Modify: `src/card_synthesis.py`
- Modify: `src/content_translation_failures.py`
- Modify: `src/security_lifecycle_translation.py`
- Test: `tests/test_subscription_structured_output.py`
- Test: `tests/test_card_synthesis.py`
- Test: `tests/test_content_translation_failures.py`
- Test: `tests/test_security_lifecycle_translation.py`

**Interfaces:**
- Consumes: `run_codex_translation` from Task 4.
- Produces: the existing translation result shape plus `harness="codex_app_server"`.

- [ ] **Step 1: Write failing dispatch and no-fallback tests**

```python
def test_spark_translation_uses_codex_adapter_once_and_never_builds_raw_client(
    monkeypatch,
):
    calls = []
    raw_openai_clients = []
    monkeypatch.setattr(
        "src.auth_drivers.codex_translation_adapter.run_codex_translation",
        lambda **kwargs: calls.append((kwargs["model"], kwargs["effort"]))
        or {"translated_text": "營收成長 12%。"},
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output._openai_client",
        lambda *args, **kwargs: raw_openai_clients.append((args, kwargs)),
    )
    result = translate_text(
        "Revenue grew 12%.",
        lang="zh-Hant",
        provider="openai",
        model="gpt-5.3-codex-spark",
        model_timeout_s=30.0,
    )
    assert result["harness"] == "codex_app_server"
    assert calls == [("gpt-5.3-codex-spark", "medium")]
    assert raw_openai_clients == []

def test_spark_failure_never_changes_model_auth_or_provider(monkeypatch):
    raw_openai_clients = []
    anthropic_clients = []
    monkeypatch.setattr(
        "src.auth_drivers.codex_translation_adapter.run_codex_translation",
        lambda **kwargs: (_ for _ in ()).throw(
            CodexTranslationError("protocol_incompatible")
        ),
    )
    with pytest.raises(SubscriptionStructuredOutputError):
        run_subscription_structured_output(
            task="card_translation",
            provider="openai",
            auth_mode="chatgpt_oauth",
            credential_id="local:1",
            model="gpt-5.3-codex-spark",
            system="Translate exactly.",
            user='{"text":"Revenue grew 12%."}',
            output_name="emit_translation",
            output_description="Emit translated text.",
            schema={
                "type": "object",
                "properties": {"translated_text": {"type": "string"}},
                "required": ["translated_text"],
                "additionalProperties": False,
            },
            effort="medium",
            token_store=FakeTokenStore(token_record(plan_type="pro")),
            timeout_s=30.0,
        )
    assert raw_openai_clients == []
    assert anthropic_clients == []
```

Add positive controls proving non-Spark ChatGPT OAuth and both API-key paths keep their current adapters.

- [ ] **Step 2: Write former-16k boundary tests**

Prove `translate_text()` accepts a 16,001-character source and output without truncation while `security_lifecycle_translation._validated_result()` still rejects a 16,001-character persisted lifecycle translation.

- [ ] **Step 3: Run RED tests**

Run: `pytest -q tests/test_subscription_structured_output.py tests/test_card_synthesis.py tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py`

- [ ] **Step 4: Dispatch only the exact adapter tuple**

Pass `task` through the subscription dispatcher. Select Codex app-server only when capability policy admits the exact Spark tuple. Map context-window rejection and local protocol exhaustion to distinct closed translation codes; never expose raw provider text, IDs, paths, or protocol messages.

- [ ] **Step 5: Remove only shared translation character checks**

Delete `len(text) > 16000` and `len(translated_text) > 16000` from `translate_text()`. Keep NUL, empty, type, lifecycle API, lifecycle cache, and SQLite checks unchanged.

- [ ] **Step 6: Run focused tests and commit**

Run: `pytest -q tests/test_subscription_structured_output.py tests/test_card_synthesis.py tests/test_content_translation_failures.py tests/test_security_lifecycle_translation.py tests/test_security_lifecycle_routes.py`

Commit: `feat(translation): route Spark through Codex app-server`

---

### Task 6: Bounded Settings Task Test

**Files:**
- Modify: `src/model_task_canary.py`
- Modify: `src/api/routes/config_routes.py`
- Test: `tests/test_model_task_test.py`
- Test: `tests/test_model_routing.py`

**Interfaces:**
- Consumes: Task 2 admission and Task 5 dispatcher.
- Produces: the existing `TaskModelTestResult` with honest Pro/visibility/protocol failure codes.

- [ ] **Step 1: Write failing pre-dispatch matrix tests**

Prove Plus, unknown plan, missing discovery, wrong task, API key, and model mismatch produce `unsupported` without constructing any provider client or starting app-server. Prove an eligible fake Pro record performs one Spark adapter call and returns measured latency.

- [ ] **Step 2: Run RED tests**

Run: `pytest -q tests/test_model_task_test.py tests/test_model_routing.py`

- [ ] **Step 3: Route the exact task canary**

Pass `token_store` to `resolve_active_credential`, run task-aware model admission before visibility, and use the subscription structured-output dispatcher for the admitted Spark tuple. Preserve all existing API-key, Claude OAuth, and non-Spark ChatGPT behavior.

- [ ] **Step 4: Run focused tests and commit**

Run: `pytest -q tests/test_model_task_test.py tests/test_model_routing.py tests/test_subscription_structured_output.py`

Commit: `feat(settings): test Spark translation admission`

---

### Task 7: Honest Settings Presentation

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/modelRoutingUx.ts`
- Modify: `apps/arkscope-web/src/settings/ModelRoutingSection.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/common.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/common.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Test: `apps/arkscope-web/src/ModelRoutingSection.test.ts`
- Test: `apps/arkscope-web/src/SettingsModelRouting.test.ts`
- Test: `apps/arkscope-web/src/i18n/resources.test.ts`

**Interfaces:**
- Consumes: effective model `plan_type`, reason codes, exact effort list, and eligibility from Task 2.
- Produces: a task-only advanced Spark option and localized Pro-required explanation.

- [ ] **Step 1: Write failing UI tests**

Prove Spark appears enabled only in Content Translation for an effective Pro/discovered record; appears disabled with a localized Pro-required reason for Plus; is absent or blocked for synthesis and AI Research; exposes exactly low/medium/high/xhigh; and never becomes the default. Add an old-sidecar positive control that does not fabricate Spark eligibility.

- [ ] **Step 2: Run RED tests**

Run: `npm test -- --run ModelRoutingSection.test.ts SettingsModelRouting.test.ts i18n/resources.test.ts`

Working directory: `apps/arkscope-web`

- [ ] **Step 3: Add closed frontend types and localized reasons**

Extend the effective provider summary with `plan_type: string | null`, add `subscription_plan_required`, `model_task_unsupported`, `model_output_limit_unknown`, and adapter/context failure presentation, and render provider/model IDs as raw diagnostics while translating all product labels.

- [ ] **Step 4: Run focused tests and commit**

Run: `npm test -- --run ModelRoutingSection.test.ts SettingsModelRouting.test.ts i18n/resources.test.ts`

Working directory: `apps/arkscope-web`

Commit: `feat(settings): expose eligible Spark translation route`

---

### Task 8: Cross-Surface Verification And Closeout

**Files:**
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/specs/2026-09-02-codex-spark-content-translation-design.md`
- Test: `tests/test_legacy_agent_surface_retirement.py`

**Interfaces:**
- Produces: a locally mergeable, unpushed hand-test branch and exact verification report.

- [ ] **Step 1: Add repository tripwires**

Prove there is no `shutil.which("codex")`, literal PATH `codex` process launch, Spark API-key route, Spark generic-agent route, or reintroduced `execute_python_analysis` registration. Positive controls must prove each scanner sees a synthetic forbidden example.

- [ ] **Step 2: Run focused backend**

Run: `pytest -q tests/test_model_capabilities.py tests/test_model_effective.py tests/test_model_routing.py tests/test_codex_app_server_runtime.py tests/test_codex_translation_adapter.py tests/test_subscription_account_usage.py tests/test_subscription_structured_output.py tests/test_card_synthesis.py tests/test_content_translation_failures.py tests/test_model_task_test.py tests/test_legacy_agent_surface_retirement.py`

- [ ] **Step 3: Run complete product backend**

Run: `pytest -q tests`

Expected: zero failures. The immutable 2026-08-28 listing packet is replayed only by its own sealed command and is not modified by this slice.

- [ ] **Step 4: Run complete frontend gates**

Run: `npm test -- --run`

Run: `npx tsc --noEmit`

Run: `npm run build`

Working directory: `apps/arkscope-web`

- [ ] **Step 5: Run integrity gates**

Run: `git diff --check master...HEAD`

Run the repository i18n debt scanner and secret-shape scanner over the exact branch diff. Confirm no provider call, production DB access, migration, restart, or push occurred.

- [ ] **Step 6: Record closeout and commit**

Update the spec status to offline green, record exact test counts and the Plus-account live limitation in `PROJECT_PRIORITY_MAP.md`, and commit:

`docs(models): close Spark translation implementation`
