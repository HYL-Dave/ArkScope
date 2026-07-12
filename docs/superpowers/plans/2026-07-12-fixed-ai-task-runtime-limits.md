# Fixed AI Task Runtime Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status: LIVE COMPLETE, 2026-07-12; FF MERGE APPROVED.** Branch
> `codex/card-oauth-routing`; the user approved local fast-forward merge after
> reviewer and live gates passed.
> TDD commits: `d408b4a` (registry/store/resolver), `87bb452` (guarded
> config API), `b55efc6` (four provider paths + typed timeout), and `c311b23`
> (Settings UI + derived browser budgets). RED evidence included the missing
> registry/module, absent routes, old adapter defaults/fixed constants, SDK
> retry count, and 12 expected frontend failures before Task 4 wiring.
>
> **Automated evidence:** reviewer canonical virgin A/B is green: failures
> `30=30` with an empty bidirectional diff, passed `4042→4074` (`+32`, exactly
> the added tests), and skips/warnings/errors unchanged at `74/18/7`. Final
> fresh closeout rerun: backend focused battery `232 passed`; frontend
> focused `33 passed`, full `32 files / 296 tests`, typecheck and production
> build green; static stale-constant/call-site gates zero; no-PG smoke `24/24`
> with `ok:true` and `pg_attempts:[]`.
>
> **Live evidence:** Settings persisted both fixed tasks at `900s`
> (`source=db`, `db_saved=true`). Claude Sonnet 5 `max` generated the real MU
> card and its Traditional-Chinese translation inside the new bound, with no
> managed Claude child left behind. The remaining parent transport gate was
> then run through ChatGPT OAuth: `gpt-5.4-mini/low` generated AAPL card
> `run_id=7` and wrote a first `zh-Hant` translation (`cached=false`) with no
> effort fallback. The original Sonnet 5 `max` routes were restored exactly;
> AI Research retained its independent runtime authority.

**Goal:** Replace guessed card/translation deadlines with independently configurable, DB-backed fixed-task model limits that apply equally to API-key and subscription execution.

**Architecture:** Add one fixed-task registry/store/resolver in `profile_state.db`, expose it additively through the existing config surface, and resolve the effective task value in the card route before evidence or model execution. Thread that required value through all four provider paths; API-key SDK calls use request-scoped clients with retries disabled, subscription adapters require an explicit timeout, and both produce one typed timeout envelope. The React shell receives the same runtime object it already loads and derives each browser request budget as backend seconds plus 60 seconds.

**Tech Stack:** Python 3.10, SQLite, FastAPI/Pydantic, OpenAI and Anthropic Python SDKs, pytest/httpx fake transports, React 18, TypeScript, Vitest/jsdom.

**Implementation base:** `c136316` on `codex/card-oauth-routing`. Full A/B
compares this commit with the final implementation tip; the intervening plan/map
commits are docs-only and do not alter collection or runtime behavior. Do not
merge in this plan; stop review-ready.

---

## Locked Decisions

1. `TaskId` remains the shared task-ID vocabulary. `FIXED_TASK_RUNTIME_TASKS` is the sole registry deciding which existing task IDs receive fixed runtime settings; V1 membership is exactly `card_synthesis` and `card_translation`.
2. Each task defaults to 900 seconds and accepts finite values from 60 through 3600 inclusive. There is no unlimited value and no YAML/profile layer.
3. Resolution is `env > db > default`. Invalid env values are ignored with a warning while the DB/default value remains effective. DB read failure also degrades to default with a warning.
4. The analysis-card route resolves runtime before evidence/model work and passes `model_timeout_s` explicitly. `synthesize_card`, `translate_card`, all four provider helpers, and both subscription adapter entry points have no production timeout default.
5. API-key calls use `client.with_options(timeout=model_timeout_s, max_retries=0)`. This makes one SDK attempt and makes the configured value a real bound.
6. A timeout is a typed `model_timeout` failure with task, provider, model, effort, and effective seconds. It never triggers effort/model/provider/credential fallback and never persists a partial card or translation.
7. Existing immediate effort-compatibility fallback remains unchanged for API-key provider rejection only. Subscription errors and timeout errors never enter that fallback.
8. Task-test remains capped at 45 seconds. AI Research keeps `research_runtime_config` unchanged.
9. New frontend against an old sidecar uses 900 seconds. Browser wait is `(effective model_timeout_s + 60) * 1000`; there is no second user-editable browser timeout.
10. Existing exact-PID Claude cleanup bounds remain system-owned and unchanged.

## File Map

**Create**

- `src/fixed_task_runtime_config.py` — registry, validation, SQLite store, resolver.
- `tests/test_fixed_task_runtime_config.py` — registry/store/resolver contract.
- `apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx` — Settings component contract.

**Modify**

- `src/api/routes/config_routes.py` — additive runtime response and guarded PUT/DELETE.
- `src/api/routes/analysis_cards.py` — resolve task settings, pass timeout, structured 502.
- `src/card_synthesis.py` — required timeout threading, bounded SDK clients, typed timeout.
- `src/auth_drivers/subscription_structured_output.py` — remove silent 90-second defaults.
- `tests/test_model_routing.py` — config route and write-gate tests.
- `tests/test_api.py` — real-app mount assertion.
- `tests/test_card_synthesis.py` — four-path propagation, one-attempt SDK tests, strict fake updates.
- `tests/test_subscription_structured_output.py` — explicit adapter timeout at every call site.
- `tests/test_analysis_cards_api.py` — route resolution/envelope/no-partial persistence.
- `apps/arkscope-web/src/api.ts` — runtime DTO, save/reset clients, derived request budget.
- `apps/arkscope-web/src/Settings.tsx` — fixed-task panel and save/reset wiring.
- `apps/arkscope-web/src/SettingsModelRouting.test.ts` — Settings-level API wiring.
- `apps/arkscope-web/src/CardApiTimeout.test.ts` — compatibility and per-task budgets.
- `apps/arkscope-web/src/AICard.tsx` — consume runtime for generation and translation.
- `apps/arkscope-web/src/TickerDetail.tsx` — thread runtime to AI-card surface.
- `apps/arkscope-web/src/Home.tsx` — thread runtime to card modal.
- `apps/arkscope-web/src/App.tsx` — pass the existing runtime snapshot to both card entry points.
- `docs/design/PROJECT_PRIORITY_MAP.md` — newest-first implementation/verification record.
- `docs/superpowers/plans/2026-07-12-subscription-card-routing.md` — close only after the real max-effort gate passes.
- `docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md` — execution ledger and status.

---

### Task 1: Fixed-task registry, store, and resolver

**Files:**

- Create: `src/fixed_task_runtime_config.py`
- Create: `tests/test_fixed_task_runtime_config.py`

- [x] **Step 1: Write registry/default RED tests**

```python
from src.fixed_task_runtime_config import (
    DEFAULT_MODEL_TIMEOUT_S,
    FIXED_TASK_RUNTIME_TASKS,
    FixedTaskRuntimeStore,
    resolve_all_fixed_task_runtime,
)


def test_registry_is_the_exact_fixed_task_membership():
    assert tuple(FIXED_TASK_RUNTIME_TASKS) == (
        "card_synthesis",
        "card_translation",
    )
    assert {definition.task for definition in FIXED_TASK_RUNTIME_TASKS.values()} == {
        "card_synthesis",
        "card_translation",
    }


def test_defaults_are_900_seconds(tmp_path, monkeypatch):
    for definition in FIXED_TASK_RUNTIME_TASKS.values():
        monkeypatch.delenv(definition.env_key, raising=False)
    settings = resolve_all_fixed_task_runtime(
        store=FixedTaskRuntimeStore(tmp_path / "profile_state.db")
    )
    assert set(settings) == set(FIXED_TASK_RUNTIME_TASKS)
    for task, value in settings.items():
        assert value.task == task
        assert value.model_timeout_s == DEFAULT_MODEL_TIMEOUT_S == 900.0
        assert value.source == "default"
        assert value.db_saved is False
        assert value.warning is None
```

- [x] **Step 2: Write persistence, precedence, and degradation RED tests**

Add named tests covering all of these exact cases:

- `test_set_many_persists_both_tasks_in_one_db`
- `test_env_overrides_db_without_rewriting_saved_value`
- `test_invalid_env_keeps_db_value_and_surfaces_warning`
- `test_invalid_env_without_db_keeps_default_and_surfaces_warning`
- `test_db_read_failure_returns_defaults_with_warning`
- `test_delete_all_is_idempotent`

The precedence assertion must prove an env-owned result still reports `db_saved=True` when a DB row exists underneath it.

```python
def test_env_overrides_db_without_rewriting_saved_value(tmp_path, monkeypatch):
    store = FixedTaskRuntimeStore(tmp_path / "profile_state.db")
    store.set_many({"card_synthesis": 600.0})
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S", "1200")

    got = resolve_all_fixed_task_runtime(store=store)["card_synthesis"]

    assert got.model_timeout_s == 1200.0
    assert got.source == "env"
    assert got.db_saved is True
    assert store.get_all()["card_synthesis"].model_timeout_s == 600.0
```

- [x] **Step 3: Write validation and atomicity RED tests**

Use parametrization for `59`, `3601`, `float("nan")`, `float("inf")`, non-numeric input, and unknown task `ai_research`. The atomic test starts with synthesis `700`, attempts `{synthesis: 800, translation: 59}`, expects `ValueError`, then proves synthesis is still `700` and translation is absent.

```python
def test_set_many_validates_every_value_before_writing(tmp_path):
    store = FixedTaskRuntimeStore(tmp_path / "profile_state.db")
    store.set_many({"card_synthesis": 700.0})

    with pytest.raises(ValueError):
        store.set_many({"card_synthesis": 800.0, "card_translation": 59.0})

    rows = store.get_all()
    assert rows["card_synthesis"].model_timeout_s == 700.0
    assert "card_translation" not in rows
```

- [x] **Step 4: Run Task 1 tests and verify RED**

Run:

```bash
pytest -q tests/test_fixed_task_runtime_config.py
```

Expected: collection fails because `src.fixed_task_runtime_config` does not exist.

- [x] **Step 5: Implement the registry and DTOs**

The public shape is fixed:

```python
RuntimeSource = Literal["env", "db", "default"]
DEFAULT_MODEL_TIMEOUT_S = 900.0
MIN_MODEL_TIMEOUT_S = 60.0
MAX_MODEL_TIMEOUT_S = 3600.0


@dataclass(frozen=True)
class FixedTaskRuntimeDefinition:
    task: TaskId
    label: str
    env_key: str
    default_timeout_s: float = DEFAULT_MODEL_TIMEOUT_S


FIXED_TASK_RUNTIME_TASKS: dict[TaskId, FixedTaskRuntimeDefinition] = {
    "card_synthesis": FixedTaskRuntimeDefinition(
        task="card_synthesis",
        label="AI 卡片生成",
        env_key="ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S",
    ),
    "card_translation": FixedTaskRuntimeDefinition(
        task="card_translation",
        label="卡片翻譯",
        env_key="ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S",
    ),
}


@dataclass(frozen=True)
class FixedTaskRuntimeRow:
    task: TaskId
    model_timeout_s: float
    updated_at: str


@dataclass(frozen=True)
class FixedTaskRuntimeSettings:
    task: TaskId
    model_timeout_s: float
    source: RuntimeSource
    db_saved: bool = False
    warning: str | None = None

    def model_dump(self) -> dict:
        return asdict(self)
```

At import time, assert every registry key equals `definition.task` and belongs to `{task.id for task in model_routing.TASKS}`. This is a development invariant, not runtime discovery.

- [x] **Step 6: Implement validation and the SQLite store**

Use the existing profile DB path rule,
`sqlite3.connect(self._db_path, timeout=10.0)`, and
`PRAGMA busy_timeout = 10000`. `set_many()` validates the complete mapping before
opening its write transaction, then performs all upserts in one
connection/commit. It must never partially apply a mixed-validity payload.

```sql
CREATE TABLE IF NOT EXISTS fixed_task_runtime_config (
    task            TEXT PRIMARY KEY,
    model_timeout_s REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
```

Validation must use `math.isfinite(value)` in addition to the inclusive range. Public methods:

```python
def validate_fixed_task_runtime_updates(
    updates: Mapping[str, object],
) -> dict[TaskId, float]:
    validated: dict[TaskId, float] = {}
    for raw_task, raw_value in updates.items():
        if raw_task not in FIXED_TASK_RUNTIME_TASKS:
            raise ValueError(f"unknown fixed task: {raw_task}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{raw_task}: model_timeout_s must be numeric") from exc
        if not math.isfinite(value) or not (
            MIN_MODEL_TIMEOUT_S <= value <= MAX_MODEL_TIMEOUT_S
        ):
            raise ValueError(
                f"{raw_task}: model_timeout_s must be between 60 and 3600"
            )
        validated[cast(TaskId, raw_task)] = value
    return validated


class FixedTaskRuntimeStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
                Path(__file__).resolve().parents[1] / "data" / "profile_state.db"
            )
        self._db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> dict[TaskId, FixedTaskRuntimeRow]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT task, model_timeout_s, updated_at "
                "FROM fixed_task_runtime_config"
            ).fetchall()
        finally:
            conn.close()
        return {
            cast(TaskId, task): FixedTaskRuntimeRow(
                task=cast(TaskId, task),
                model_timeout_s=float(timeout_s),
                updated_at=updated_at,
            )
            for task, timeout_s, updated_at in rows
            if task in FIXED_TASK_RUNTIME_TASKS
        }

    def set_many(
        self,
        updates: Mapping[str, object],
    ) -> dict[TaskId, FixedTaskRuntimeRow]:
        validated = validate_fixed_task_runtime_updates(updates)
        now = _now()
        conn = self._connect()
        try:
            conn.executemany(
                "INSERT INTO fixed_task_runtime_config "
                "(task, model_timeout_s, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(task) DO UPDATE SET "
                "model_timeout_s = excluded.model_timeout_s, "
                "updated_at = excluded.updated_at",
                [(task, value, now) for task, value in validated.items()],
            )
            conn.commit()
        finally:
            conn.close()
        return {
            task: FixedTaskRuntimeRow(task, value, now)
            for task, value in validated.items()
        }

    def delete_all(self) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM fixed_task_runtime_config")
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
```

Define `_SCHEMA` as the SQL block above and `_now()` with UTC ISO seconds, matching
`research_runtime_config.py`.

- [x] **Step 7: Implement one-pass resolution**

`resolve_all_fixed_task_runtime(store=None)` reads DB rows once, then resolves each registry member independently. A malformed env value affects only its own task. DB-read exceptions are logged and become per-task warnings; they do not prevent startup.

Also expose:

```python
def resolve_fixed_task_runtime(
    task: TaskId,
    *,
    store: FixedTaskRuntimeStore | None = None,
) -> FixedTaskRuntimeSettings:
    return resolve_all_fixed_task_runtime(store=store)[task]
```

- [x] **Step 8: Run Task 1 tests and verify GREEN**

Run:

```bash
pytest -q tests/test_fixed_task_runtime_config.py
```

Expected: all Task 1 tests pass with no warnings.

- [x] **Step 9: Commit Task 1**

```bash
git add src/fixed_task_runtime_config.py tests/test_fixed_task_runtime_config.py
git commit -m "feat: add fixed task runtime store"
```

---

### Task 2: Config API and guarded atomic updates

**Files:**

- Modify: `src/api/routes/config_routes.py`
- Modify: `tests/test_model_routing.py`
- Modify: `tests/test_api.py`

- [x] **Step 1: Write additive GET and route-mount RED tests**

```python
def test_runtime_config_exposes_fixed_task_runtime(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S", raising=False)
    result = runtime_config(store=CredentialStore(db))
    assert set(result["fixed_task_runtime"]) == {
        "card_synthesis",
        "card_translation",
    }
    assert result["fixed_task_runtime"]["card_synthesis"] == {
        "task": "card_synthesis",
        "model_timeout_s": 900.0,
        "source": "default",
        "db_saved": False,
        "warning": None,
    }


def test_fixed_task_runtime_routes_mount_on_real_app():
    from src.api.app import create_app

    routes = {(getattr(route, "path", None), method)
              for route in create_app().routes
              for method in (getattr(route, "methods", None) or set())}
    assert ("/config/fixed-task-runtime", "PUT") in routes
    assert ("/config/fixed-task-runtime", "DELETE") in routes
```

- [x] **Step 2: Write PUT/DELETE RED tests with gate ordering**

Add these exact tests in `tests/test_model_routing.py`:

- `test_update_fixed_task_runtime_validates_then_gates_then_writes`
- `test_update_fixed_task_runtime_rejects_unknown_task_without_gate_or_write`
- `test_update_fixed_task_runtime_rejects_mixed_payload_atomically`
- `test_delete_fixed_task_runtime_gates_and_restores_defaults`

The success test records event order as `gate` then `set_many`. The invalid tests assert the gate was not called and the DB retained its prior rows.

```python
body = FixedTaskRuntimeUpdate(tasks={
    "card_synthesis": FixedTaskRuntimeValue(model_timeout_s=1200),
    "card_translation": FixedTaskRuntimeValue(model_timeout_s=600),
})
```

- [x] **Step 3: Run the route tests and verify RED**

Run:

```bash
pytest -q \
  tests/test_model_routing.py::test_runtime_config_exposes_fixed_task_runtime \
  tests/test_model_routing.py::test_update_fixed_task_runtime_validates_then_gates_then_writes \
  tests/test_model_routing.py::test_update_fixed_task_runtime_rejects_unknown_task_without_gate_or_write \
  tests/test_model_routing.py::test_update_fixed_task_runtime_rejects_mixed_payload_atomically \
  tests/test_model_routing.py::test_delete_fixed_task_runtime_gates_and_restores_defaults \
  tests/test_api.py::test_fixed_task_runtime_routes_mount_on_real_app
```

Expected: RED because the DTOs, response key, and routes do not exist.

- [x] **Step 4: Add DTOs and additive runtime response**

```python
class FixedTaskRuntimeValue(BaseModel):
    model_timeout_s: float


class FixedTaskRuntimeUpdate(BaseModel):
    tasks: dict[str, FixedTaskRuntimeValue]
```

Inside `runtime_config`, construct `FixedTaskRuntimeStore(store.db_path)`, call `resolve_all_fixed_task_runtime`, and serialize every registered task under `fixed_task_runtime`. Do not modify existing keys or route shapes.

- [x] **Step 5: Implement guarded PUT/DELETE**

PUT rules:

1. reject an empty `tasks` mapping with HTTP 400;
2. normalize and validate all entries with `validate_fixed_task_runtime_updates`;
3. call `require_profile_state_write("fixed_task_runtime_update", {"tasks": sorted(validated)})` once;
4. call `set_many(validated)` once;
5. return the fully resolved two-task object.

DELETE calls `require_profile_state_write("fixed_task_runtime_delete", {})`, deletes all rows, and returns `{deleted, fixed_task_runtime}`. Map `ValueError` to HTTP 400 without leaking a traceback.

- [x] **Step 6: Run config tests and verify GREEN**

Run:

```bash
pytest -q tests/test_fixed_task_runtime_config.py tests/test_model_routing.py tests/test_api.py
```

Expected: no new failures; existing model/research runtime behavior is unchanged.

Execution evidence: fixed-task + model-routing + isolated real-app mount tests
passed `66`; the whole `test_api.py` command entered the repository's known
TestClient lifespan hang after its non-lifespan tests, so the authoritative
full-file comparison remains the Task 5 canonical A/B gate.

- [x] **Step 7: Commit Task 2**

```bash
git add src/api/routes/config_routes.py tests/test_model_routing.py tests/test_api.py
git commit -m "feat: expose fixed task runtime settings"
```

---

### Task 3: Enforce the timeout across all execution paths

**Files:**

- Modify: `src/card_synthesis.py`
- Modify: `src/auth_drivers/subscription_structured_output.py`
- Modify: `src/api/routes/analysis_cards.py`
- Modify: `tests/test_card_synthesis.py`
- Modify: `tests/test_subscription_structured_output.py`
- Modify: `tests/test_analysis_cards_api.py`

- [x] **Step 1: Write required-timeout and four-path propagation RED tests**

Update all existing direct calls in `tests/test_subscription_structured_output.py` to pass an explicit task-test value such as `timeout_s=45.0` or the pre-existing test-specific bound. Then add an introspection pin:

```python
def test_subscription_entry_points_require_timeout():
    import inspect
    from src.auth_drivers import subscription_structured_output as mod

    assert inspect.signature(
        mod.run_subscription_structured_output
    ).parameters["timeout_s"].default is inspect.Parameter.empty
    assert inspect.signature(
        mod.run_subscription_structured_output_async
    ).parameters["timeout_s"].default is inspect.Parameter.empty
```

In `tests/test_card_synthesis.py`, replace the four old `210.0` assertions with caller-supplied distinct values and prove synthesis/translation send those exact values for OpenAI and Anthropic subscription auth.

- [x] **Step 2: Write API-key one-attempt RED tests with real SDK clients and fake transports**

Use `httpx.MockTransport`. The handler increments a counter then raises `httpx.ReadTimeout`. Build a real sync SDK client with a dummy key and that transport, patch the corresponding `live_*_client`, and patch `resolve_live_auth` to `env_fallback`. Invoke the provider helper with `model_timeout_s=0.01` and assert the typed timeout plus exactly one transport call.

Because `card_synthesis.py` imports these functions inside `run_once`, patch the
source module targets
`src.auth_drivers.live_resolver.live_openai_client`,
`src.auth_drivers.live_resolver.live_anthropic_client`, and
`src.auth_drivers.live_resolver.resolve_live_auth`. Do not patch nonexistent
module attributes on `src.card_synthesis`.

Required test names:

- `test_openai_api_timeout_uses_one_attempt`
- `test_anthropic_api_timeout_uses_one_attempt`

These are integration-style unit tests for
`with_options(timeout=model_timeout_s, max_retries=0)`, not MagicMock
call-shape tests.

- [x] **Step 3: Write route RED tests for resolution, envelope, and no partial writes**

Add:

- `test_generate_resolves_synthesis_timeout_before_gather_and_forwards_it`
- `test_translate_resolves_translation_timeout_and_forwards_it`
- `test_generate_timeout_returns_structured_502_and_stores_no_run`
- `test_translate_timeout_returns_structured_502_and_stores_no_translation`

The 502 detail must equal:

```python
{
    "code": "model_timeout",
    "task": "card_synthesis",
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "effort": "max",
    "effective_seconds": 900.0,
}
```

The generation test verifies `store.recent()` remains empty. The translation test creates a run first, raises during translation, reloads the run, and verifies the requested language is absent from `translations`.
Both tests monkeypatch `routes.resolve_fixed_task_runtime` to a deterministic
`FixedTaskRuntimeSettings`; they never touch the developer's real profile DB.
The generation timeout test also asserts `require_db_write` was not called.

- [x] **Step 4: Run the new focused tests and verify RED**

Run:

```bash
pytest -q \
  tests/test_card_synthesis.py \
  tests/test_subscription_structured_output.py \
  tests/test_analysis_cards_api.py
```

Expected failures: fixed 210-second forwarding, adapter defaults still present, SDK retries not disabled, route timeout not resolved, and timeout detail not structured.

- [x] **Step 5: Make subscription timeout mandatory and remove stale constants**

In both adapter entry points, change `timeout_s: float = 90.0` to the required keyword-only `timeout_s: float`. `src/model_task_canary.py` already passes its bounded value and must not change.

Delete `_SUBSCRIPTION_CARD_TIMEOUT_S` and the stale 240-second browser comment from `src/card_synthesis.py`. Add `model_timeout_s: float` as a required keyword-only argument to:

- `_subscription_structured_output_if_active`;
- `_synthesize_anthropic`;
- `_synthesize_openai`;
- `_translate_anthropic`;
- `_translate_openai`;
- `synthesize_card`;
- `translate_card`.

Every call in this module passes it explicitly.

- [x] **Step 6: Add a typed provider execution timeout**

Define `ModelExecutionTimeout` in `src/card_synthesis.py` with `provider`, `model`, `effort`, and `effective_seconds`. It must not include raw provider response text. Add a `detail(task)` method returning the exact route dictionary from Step 3.

Subscription conversion is cause-based, not message parsing: a
`SubscriptionStructuredOutputError` whose cause chain contains
`asyncio.TimeoutError`, OpenAI `APITimeoutError`, or Anthropic
`APITimeoutError` becomes `ModelExecutionTimeout`; every other subscription
error remains unchanged. The SDK timeout cases cover the single-tick race where
the subscription client's own deadline fires just before the outer async
deadline. API-key conversion catches the same provider SDK timeout classes and
raises the typed error.

All four provider functions add an explicit `except ModelExecutionTimeout: raise` before the legacy effort-rejection branch, guaranteeing timeout never retries with provider default effort.

- [x] **Step 7: Apply request-scoped SDK limits**

The API-key client shape is:

```python
client = live_anthropic_client().with_options(
    timeout=model_timeout_s,
    max_retries=0,
)
```

and equivalently for OpenAI. Do not mutate a shared SDK client and do not change endpoint/tool payloads. Update the two existing API-key call-shape tests so `with_options.return_value` is a distinct bounded client; assert the parent received the timeout/retry options and the existing request assertions apply to the bounded client.

- [x] **Step 8: Resolve runtime in analysis-card routes and map timeout only**

Generation order is:

1. validate provider and personalization;
2. resolve `card_synthesis` runtime;
3. gather evidence;
4. call synthesis with the existing route arguments and the required timeout:

   ```python
   card, meta = synthesize_card(
       packet,
       now_iso=now,
       provider=provider,
       model=model,
       question=body.question,
       horizon=body.horizon,
       model_timeout_s=setting.model_timeout_s,
       **_pctx,
   )
   ```

5. persist only after success.

Translation resolves `card_translation` only after the cached-translation fast
path misses, then calls `translate_card(run.result_card, lang=lang,
model_timeout_s=setting.model_timeout_s)`.

Catch `ModelExecutionTimeout` before the generic provider exception and return `HTTPException(status_code=502, detail=exc.detail(task))`. Preserve all existing generic 502 behavior.

- [x] **Step 9: Update strict fakes mechanically and run a residue gate**

Every direct provider-helper call in `tests/test_card_synthesis.py` receives `model_timeout_s`. Every strict `synthesize_card` or `translate_card` fake that receives the new keyword either accepts/asserts that exact key or remains `**kw` compatible.

Run:

```bash
rg -n "_SUBSCRIPTION_CARD_TIMEOUT_S|240s deadline|timeout_s: float = 90\.0" \
  src/card_synthesis.py src/auth_drivers/subscription_structured_output.py
```

Expected: zero matches.

- [x] **Step 10: Run execution tests and regressions**

Run:

```bash
pytest -q \
  tests/test_fixed_task_runtime_config.py \
  tests/test_card_synthesis.py \
  tests/test_subscription_structured_output.py \
  tests/test_analysis_cards_api.py \
  tests/test_model_task_test.py \
  tests/test_research_runtime_config.py \
  tests/test_research_routes.py
```

Expected: all pass. Existing task-test assertions continue to prove a maximum 45-second driver bound; Research runtime values remain unchanged.

Execution evidence: the focused card/adapter/route set passed `62`; the wider
fixed-runtime + canary + Research regression battery passed `165`. Both real SDK
clients used counting `httpx.MockTransport` timeouts and made exactly one
attempt. The adapter call-site AST scan and old-constant residue scan returned
zero findings.

- [x] **Step 11: Commit Task 3**

```bash
git add \
  src/card_synthesis.py \
  src/auth_drivers/subscription_structured_output.py \
  src/api/routes/analysis_cards.py \
  tests/test_card_synthesis.py \
  tests/test_subscription_structured_output.py \
  tests/test_analysis_cards_api.py
git commit -m "feat: enforce fixed task model timeouts"
```

---

### Task 4: Settings panel and derived browser budgets

**Files:**

- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Create: `apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsModelRouting.test.ts`
- Modify: `apps/arkscope-web/src/CardApiTimeout.test.ts`
- Modify: `apps/arkscope-web/src/AICard.tsx`
- Modify: `apps/arkscope-web/src/TickerDetail.tsx`
- Modify: `apps/arkscope-web/src/Home.tsx`
- Modify: `apps/arkscope-web/src/App.tsx`

- [x] **Step 1: Write API timeout derivation RED tests**

Replace the fixed `300_000` expectation with three cases:

```typescript
const runtimeWith = (synthesis: number, translation: number) => ({
  fixed_task_runtime: {
    card_synthesis: {
      task: "card_synthesis",
      model_timeout_s: synthesis,
      source: "db",
      db_saved: true,
      warning: null,
    },
    card_translation: {
      task: "card_translation",
      model_timeout_s: translation,
      source: "db",
      db_saved: true,
      warning: null,
    },
  },
}) as RuntimeConfig;

expect(fixedTaskRequestTimeoutMs(null, "card_synthesis")).toBe(960_000);
expect(fixedTaskRequestTimeoutMs(runtimeWith(1200, 600), "card_synthesis")).toBe(1_260_000);
expect(fixedTaskRequestTimeoutMs(runtimeWith(1200, 600), "card_translation")).toBe(660_000);
```

Then call `generateCard` and `translateCard` with that runtime fixture and assert `window.setTimeout` receives `1_260_000` and `660_000` respectively. This proves task independence and the old-sidecar fallback.

- [x] **Step 2: Write Settings panel RED tests using the existing DOM harness**

`FixedTaskRuntimeSection.test.tsx` uses `createRoot`, `act`, direct DOM queries, and prototype input setters, matching `ResearchRuntimeSection.test.ts`.

Required tests:

- renders both Chinese task labels, values, and independent source badges;
- env-owned value shows `env override` while a saved row still permits Reset via `db_saved`;
- Save emits one atomic `{tasks: {card_synthesis, card_translation}}` payload;
- 59, 3601, blank, NaN, and Infinity disable Save;
- Reset is hidden only when both rows have `db_saved=false`;
- explanatory copy says higher effort may take longer and the setting does not change model/effort.

Also extend `SettingsModelRouting.test.ts` with one Settings-level wiring test:
render `SettingsView` with a runtime containing both fixed-task rows, edit the
synthesis field, click the fixed-task Save button, and assert the mocked
`saveFixedTaskRuntime` receives both tasks in one request. This test guards the
page-level callback; the component-only test is not sufficient wiring proof.

- [x] **Step 3: Run frontend RED tests**

Run:

```bash
npm --workspace apps/arkscope-web test -- --run \
  CardApiTimeout.test.ts \
  FixedTaskRuntimeSection.test.tsx
```

Expected: RED because the fixed-task DTO/helper/component do not exist.

- [x] **Step 4: Add additive frontend DTOs and API calls**

```typescript
export type FixedTaskRuntimeTask = "card_synthesis" | "card_translation";

export interface FixedTaskRuntimeSettings {
  task: FixedTaskRuntimeTask;
  model_timeout_s: number;
  source: "env" | "db" | "default";
  db_saved: boolean;
  warning: string | null;
}

export interface RuntimeConfig {
  fixed_task_runtime?: Record<FixedTaskRuntimeTask, FixedTaskRuntimeSettings>;
}
```

The line above is added to the existing `RuntimeConfig` interface; all of its
current properties remain in place.

Add `saveFixedTaskRuntime` and `deleteFixedTaskRuntime` using the new endpoints and an 8-second settings request budget.

Add:

```typescript
const FIXED_TASK_COMPAT_TIMEOUT_S = 900;
const FIXED_TASK_CLIENT_MARGIN_S = 60;

export function fixedTaskRequestTimeoutMs(
  runtime: RuntimeConfig | null | undefined,
  task: FixedTaskRuntimeTask,
): number {
  const seconds = runtime?.fixed_task_runtime?.[task]?.model_timeout_s
    ?? FIXED_TASK_COMPAT_TIMEOUT_S;
  return (seconds + FIXED_TASK_CLIENT_MARGIN_S) * 1000;
}
```

Delete `CARD_GEN_TIMEOUT_MS` and both stale comments describing 210/300-second constants. `generateCard` and `translateCard` accept the current runtime snapshot and call this helper.

- [x] **Step 5: Implement `FixedTaskRuntimeSection` and Settings wiring**

Export the component from `Settings.tsx`. Render two stable numeric controls:

- `name="card_synthesis_model_timeout_s"`, label `AI 卡片生成 - 模型執行上限（秒）`;
- `name="card_translation_model_timeout_s"`, label `卡片翻譯 - 模型執行上限（秒）`.

Both use `min=60`, `max=3600`, `step=30`. Validate with `Number.isFinite` and inclusive range before enabling Save. Reuse the existing runtime grid/panel styling; do not create a nested card.

Use one parser for both fields so whitespace cannot become numeric zero:

```typescript
function parseFixedTaskTimeout(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  return Number.isFinite(value) && value >= 60 && value <= 3600
    ? value
    : null;
}
```

The component contract is:

```typescript
{
  settings: Record<FixedTaskRuntimeTask, FixedTaskRuntimeSettings>;
  saving: boolean;
  onSave: (body: {
    tasks: Record<FixedTaskRuntimeTask, { model_timeout_s: number }>;
  }) => void | Promise<void>;
  onReset: () => void | Promise<void>;
}
```

In `SettingsView`, add dedicated fixed-task save/reset callbacks, refresh `runtime` through `onRuntimeChanged`, and render the panel next to `ModelRoutingSection` and before `ResearchRuntimeSection`. Research controls and copy remain independent.

- [x] **Step 6: Thread the existing App runtime snapshot to card actions**

Production wiring is explicit:

```text
App
├── TickerDetailView(runtime)
│   └── AICardTab(runtime)
│       ├── generateCard(ticker, body, runtime)
│       └── CardView(runtime) → translateCard(runId, lang, runtime)
└── HomeView(runtime)
    └── CardModal(runtime)
        └── CardView(runtime) → translateCard(runId, lang, runtime)
```

Use nullable `RuntimeConfig | null` because App renders while runtime loads. Do not fetch `/config/runtime` again inside card actions.

- [x] **Step 7: Run focused frontend tests and typecheck**

Run:

```bash
npm --workspace apps/arkscope-web test -- --run \
  CardApiTimeout.test.ts \
  FixedTaskRuntimeSection.test.tsx \
  SettingsModelRouting.test.ts \
  ResearchRuntimeSection.test.ts \
  ModelRoutingSection.test.ts
npm --workspace apps/arkscope-web run typecheck
```

Expected: all pass; Research panel tests are unchanged.

- [x] **Step 8: Run full frontend suite and build**

Run:

```bash
npm --workspace apps/arkscope-web test
npm --workspace apps/arkscope-web run build
```

Expected: all tests pass and Vite production build succeeds.

- [x] **Step 9: Commit Task 4**

```bash
git add \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx \
  apps/arkscope-web/src/CardApiTimeout.test.ts \
  apps/arkscope-web/src/SettingsModelRouting.test.ts \
  apps/arkscope-web/src/AICard.tsx \
  apps/arkscope-web/src/TickerDetail.tsx \
  apps/arkscope-web/src/Home.tsx \
  apps/arkscope-web/src/App.tsx
git commit -m "feat: configure fixed AI task limits"
```

---

### Task 5: Boundary gates, A/B, live proof, and closeout

**Files:**

- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md`
- Modify after successful live max gate only: `docs/superpowers/plans/2026-07-12-subscription-card-routing.md`

- [x] **Step 1: Run the backend focused battery**

```bash
pytest -q \
  tests/test_fixed_task_runtime_config.py \
  tests/test_model_routing.py \
  tests/test_card_synthesis.py \
  tests/test_subscription_structured_output.py \
  tests/test_analysis_cards_api.py \
  tests/test_model_task_test.py \
  tests/test_research_runtime_config.py \
  tests/test_research_routes.py \
  tests/test_live_resolver.py
```

Record exact passed/skipped counts in the execution ledger.

- [x] **Step 2: Run static contract gates**

```bash
rg -n "_SUBSCRIPTION_CARD_TIMEOUT_S|CARD_GEN_TIMEOUT_MS|240s deadline|timeout_s: float = 90\.0" \
  src/card_synthesis.py \
  src/auth_drivers/subscription_structured_output.py \
  apps/arkscope-web/src/api.ts
```

Expected: zero matches.

Run an AST call-site check that every call to `run_subscription_structured_output` and `run_subscription_structured_output_async` outside their definitions supplies `timeout_s`. Fail if any call omits it. Also assert `src/model_task_canary.py` still contains the 45-second clamp and does not import `fixed_task_runtime_config`.

```bash
python - <<'PY'
import ast
from pathlib import Path

targets = {
    "run_subscription_structured_output",
    "run_subscription_structured_output_async",
}
missing = []
for path in [*Path("src").rglob("*.py"), *Path("tests").rglob("*.py")]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name in targets and not any(kw.arg == "timeout_s" for kw in node.keywords):
            missing.append(f"{path}:{node.lineno}:{name}")
if missing:
    raise SystemExit("missing explicit timeout_s:\n" + "\n".join(missing))
PY
test "$(rg -n 'min\(max\(float\(timeout_s\), 0\.001\), 45\.0\)' src/model_task_canary.py | wc -l)" -eq 1
test "$(rg -n 'fixed_task_runtime_config' src/model_task_canary.py | wc -l)" -eq 0
```

- [x] **Step 3: Run frontend and no-PG gates**

```bash
npm --workspace apps/arkscope-web test
npm --workspace apps/arkscope-web run typecheck
npm --workspace apps/arkscope-web run build
python src/smoke/pg_unreachable_e2e.py
```

Expected: frontend green; smoke reports `ok: true` and `pg_attempts: []`.

- [x] **Step 4: Run canonical virgin A/B**

Implementation-side attempt: virgin collect completed at `4153 → 4185`
(`+32 / -0`), but the base single-process run reproduced the known
TestClient/lifespan hang and made no output progress for over four minutes.
The run was stopped with its log preserved under `/tmp`; this is not reported
as a partial A/B pass. Reviewer canonical A/B remains required.

Compare base `c136316` with the final implementation tip using virgin archives and identical environment isolation. Acceptance:

- failure sets identical in both directions;
- skipped/warning/error counters identical;
- passed delta equals the independently collected number of newly added tests;
- no new filesystem artifacts in either archive.

If the known single-process TestClient hang appears, preserve the canonical reviewer protocol; do not replace it with an unreported partial suite.

- [x] **Step 5: Mark automated implementation review-ready**

Update this plan header to `IMPLEMENTED FOR REVIEW`, add RED/GREEN evidence and exact counts, and add a newest-first map entry. Do not mark live complete or merge.

- [x] **Step 6: Reviewer checkpoint**

Review focus:

1. registry membership/atomicity and env-over-DB semantics;
2. route resolves before execution and never writes partial output;
3. API-key fake transport count is exactly one;
4. subscription adapter has no timeout default;
5. timeout cannot enter effort fallback;
6. both card entry points receive the runtime snapshot;
7. Research and task-test bounds remain unchanged.

Stop until review is green.

- [x] **Step 7: Run the live branch gate with one sidecar**

1. Stop desktop/master sidecars; run only this branch sidecar against the real profile DB with scheduler disabled.
2. Confirm GET returns both tasks at default 900 seconds, then save synthesis/translation values through Settings and read them back with `source=db`.
3. Run Claude Sonnet 5 MU card synthesis at `max` with synthesis timeout 900. It must either complete or return a structured `model_timeout` at the exact effective limit; it must not fail at the old 210-second boundary.
4. On a successful card, run translation with its independent timeout and verify translation cache writes only after success.
5. Confirm no new managed Claude child process remains after completion/timeout.
6. Confirm task-test still stops within its short bound and AI Research still reports its independent runtime settings.
7. For an API-key credential, a low-cost card smoke may be run only with user approval; unit fake-transport evidence remains the required retry proof.

- [x] **Step 8: Close the parent only when live evidence supports it**

If the real max task succeeds within 900 seconds, mark this plan `LIVE COMPLETE`, update the map, and close the pending runtime follow-up in `2026-07-12-subscription-card-routing.md`. If it reaches 900 seconds, keep the transport plan open and record the honest timeout; do not increase the default or hide the failure without a new user decision.

- [x] **Step 9: Commit docs closeout and stop review-ready**

```bash
git add \
  docs/design/PROJECT_PRIORITY_MAP.md \
  docs/superpowers/plans/2026-07-12-fixed-ai-task-runtime-limits.md \
  docs/superpowers/plans/2026-07-12-subscription-card-routing.md
git commit -m "docs: close fixed task runtime limits"
```

Do not merge until the user approves the reviewed branch.

---

## Stop Conditions

- A fixed runtime task ID cannot be derived from the existing `TaskId` vocabulary without changing model routing.
- Making timeout a real API-key bound requires mutating a shared SDK client rather than using request-scoped `with_options`.
- OpenAI or Anthropic performs more than one transport attempt with `max_retries=0`.
- Timeout classification requires parsing provider text instead of a typed SDK error or preserved async timeout cause.
- Any timeout path writes a card run, translation, report, or research record.
- Implementing fixed-task settings changes AI Research runtime or task-test bounds.
- Frontend needs a second settings fetch per card action rather than consuming App's existing runtime snapshot.
- Supporting the limit requires model, effort, provider, credential, or billing fallback.
