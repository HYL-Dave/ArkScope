# S-J Provider-Config Authority Phase 0-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make data-provider configuration visibly DB-first for the desktop runtime by auditing provider env use, promoting SEC UA and IBKR client-id defaults into app-managed config, adding per-field `.env` import, and failing closed into setup-only mode when the provider config store is unavailable.

**Architecture:** Phase 0 is a read-only classification audit appended to `PG_EXIT_REMAINDER_SCOPING.md`. Phase 1 keeps the current fallback behavior for managed fields, but makes `config/.env` provenance visible and importable, seeds safe defaults, and prevents provider work when the profile DB cannot be opened. Phase 2 strict-by-default is explicitly out of scope for this plan.

**Tech Stack:** Python 3, FastAPI, SQLite `profile_state.db`, pytest, React/TypeScript Settings UI, Vitest.

---

## Boundaries

This plan implements §13 Phase 0-1 only:

- keep real shell env precedence unchanged;
- keep per-field `config/.env` fallback temporarily available but visible;
- do not add `provider_env_fallback`;
- do not implement `provider_config_missing` strict-mode routing;
- do not harden CLI or retiring `scripts/` entrypoints except the existing normalized IBKR worker assertion;
- do not touch LLM credentials, PG DSN, keyring, or market data tables.

## File Map

Create:

- `src/provider_config_runtime.py` — process-local setup-only state and route/scheduler guard.
- `tests/test_provider_config_startup.py` — lifespan/setup-only and route guard tests.
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts` — Settings provider-config provenance/import/guard tests.

Modify:

- `docs/design/PG_EXIT_REMAINDER_SCOPING.md` — append Phase 0 classification table and update S-J progress note.
- `src/data_provider_config.py` — FieldDef metadata, SEC UA FieldDef, IBKR default seeding, import helpers, guarded-change helper.
- `src/api/routes/providers_config.py` — safe GET, guarded PUT, per-field import endpoint, setup status in response, provider-test setup guard.
- `src/api/routes/schedule.py` — run-now setup guard.
- `src/service/data_scheduler.py` — runtime run-source setup guard and comments.
- `src/api/app.py` — startup setup-only behavior and scheduler suppression on config-store failure.
- `src/api/routes/health.py` — expose provider-config setup state in `/status`.
- `src/service/provider_health.py` — update key-source comments and expose import-needed provenance without changing status vocabulary.
- `tests/test_data_provider_config.py` — FieldDef/default/import/guard/route tests.
- `tests/test_provider_health.py` — provenance warning tests.
- `tests/test_data_scheduler.py` — setup-only run_source guard.
- `tests/test_normalized_ibkr_worker.py` — ensure worker applies DB config before provider construction.
- `apps/arkscope-web/src/api.ts` — provider config DTO and import API.
- `apps/arkscope-web/src/Settings.tsx` — source badges, import button, guarded IBKR client-id edit, copy update.

---

### Task 1: Phase 0 Audit Table

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`

- [ ] **Step 1: Re-run the audit grep and save output for review**

Run:

```bash
rg -n "getenv\\(|os\\.environ\\[|ensure_env_loaded\\(|load_dotenv|_load_env\\(|config/\\.env|SEC_CONTACT_EMAIL|ARKSCOPE_SEC_USER_AGENT|SEC_USER_AGENT|ALPHA_VANTAGE_API_KEY|TIINGO_API_KEY|EODHD_API_KEY|FMP|REDDIT|DISCORD" src data_sources scripts tests > /tmp/s-j-provider-env-audit.txt
```

Expected: command exits 0 and `/tmp/s-j-provider-env-audit.txt` contains provider-env references only; no secrets are printed because values are not read.

- [ ] **Step 2: Append the Phase 0 classification table**

In `docs/design/PG_EXIT_REMAINDER_SCOPING.md`, under `### 13.2 Phase 0 — audit`, append this table:

```markdown
#### Phase 0 classification result (2026-07-02)

| Env var / family | Class | Runtime owner | Decision |
|---|---|---|---|
| `POLYGON_API_KEY` | managed | `polygon.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FINNHUB_API_KEY` | managed | `finnhub.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FRED_API_KEY` | managed | `fred.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FINANCIAL_DATASETS_API_KEY` | managed | `financial_datasets.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `IBKR_HOST` / `IBKR_PORT` | managed | `ibkr.host` / `ibkr.port` | already FieldDef-managed. |
| `IBKR_CLIENT_ID` | managed-with-default | `ibkr.client_id` | already FieldDef-managed; Phase 1 seeds explicit default `1` and guards edits. |
| `ARKSCOPE_SEC_USER_AGENT` | promote | `sec_edgar.user_agent` | canonical SEC User-Agent; promote to FieldDef in Phase 1. |
| `SEC_CONTACT_EMAIL` | legacy import alias | `sec_edgar.user_agent` | explicit per-field import only; imported value is normalized to `ArkScope <email>`. |
| `SEC_USER_AGENT` | legacy import alias | `sec_edgar.user_agent` | explicit per-field import only; imported value is treated as already full User-Agent. |
| `ALPHA_VANTAGE_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until an Alpha Vantage feature is reintroduced DB-native. |
| `TIINGO_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until a Tiingo feature is reintroduced DB-native. |
| `EODHD_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until an EODHD feature is reintroduced DB-native. |
| `DISCORD_*` | legacy_env_only | ops monitor | not a data provider; keep out of provider FieldDefs. |
| `REDDIT_*` / `FMP*` | retiring/defer | no active reader | do not promote; revisit only if a real desktop feature is designed. |
| `DATABASE_URL` / `SUPABASE_DB_URL` | out of scope | PG-exit target | leave transitional until full PG exit removes the consumer. |
| LLM keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, OAuth tokens) | out of scope | auth-driver thread | do not mix with data-provider config. |
```

- [ ] **Step 3: Add one sequencing note**

In the same section, add:

```markdown
Phase 1 promotes only `sec_edgar.user_agent` plus the existing `ibkr.client_id`
default/guard. Alpha Vantage, Tiingo, and EODHD remain `legacy_env_only` in this
slice because they are not active desktop ingest paths; any future S-C/S-F
provider selected for IV or fundamentals must be added DB-native instead of
expanding `.env` fallback.
```

- [ ] **Step 4: Commit**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md
git commit -m "docs: record provider config authority audit"
```

---

### Task 2: FieldDef Metadata, SEC UA, and IBKR Default

**Files:**
- Modify: `src/data_provider_config.py`
- Modify: `tests/test_data_provider_config.py`

- [ ] **Step 1: Write failing tests for SEC UA FieldDef and IBKR default seeding**

Append to `tests/test_data_provider_config.py`:

```python
def test_sec_edgar_user_agent_field_defined():
    fields = {f.field: f for f in dpc.PROVIDER_FIELDS["sec_edgar"]}
    assert "user_agent" in fields
    f = fields["user_agent"]
    assert f.env_var == "ARKSCOPE_SEC_USER_AGENT"
    assert f.secret is False
    assert f.import_aliases == ("SEC_CONTACT_EMAIL", "SEC_USER_AGENT")


def test_apply_env_seeds_ibkr_client_id_default(store):
    assert store.get_all() == {}
    dpc.apply_env(store)
    stored = store.get_all()
    assert stored["ibkr"]["client_id"] == "1"
    assert os.environ["IBKR_CLIENT_ID"] == "1"
    assert dpc.effective_source("IBKR_CLIENT_ID") == "app"
```

Update the `hermetic` fixture env cleanup tuple to include:

```python
"ARKSCOPE_SEC_USER_AGENT", "SEC_CONTACT_EMAIL", "SEC_USER_AGENT"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_data_provider_config.py::test_sec_edgar_user_agent_field_defined tests/test_data_provider_config.py::test_apply_env_seeds_ibkr_client_id_default -q
```

Expected: both fail because `sec_edgar` has no fields and `apply_env()` does not seed defaults.

- [ ] **Step 3: Extend FieldDef and registry**

In `src/data_provider_config.py`, replace `FieldDef` with:

```python
@dataclass(frozen=True)
class FieldDef:
    field: str
    env_var: str
    secret: bool
    label: str
    default_value: str | None = None
    defaulted: bool = False
    guarded: bool = False
    guard_reason: str | None = None
    import_aliases: tuple[str, ...] = ()
```

Change the `ibkr.client_id` FieldDef to:

```python
FieldDef(
    "client_id",
    "IBKR_CLIENT_ID",
    False,
    "Client ID",
    default_value="1",
    defaulted=True,
    guarded=True,
    guard_reason=(
        "Changing IBKR client_id can disturb active Gateway sessions; this is the "
        "base id, and option_chain_tools uses base+10."
    ),
),
```

Change `sec_edgar` from an empty list to:

```python
"sec_edgar": [
    FieldDef(
        "user_agent",
        "ARKSCOPE_SEC_USER_AGENT",
        False,
        "SEC User-Agent",
        import_aliases=("SEC_CONTACT_EMAIL", "SEC_USER_AGENT"),
    )
],
```

- [ ] **Step 4: Add default seeding on the store**

Add to `DataProviderConfigStore`:

```python
    def seed_defaults(self) -> list[tuple[str, str]]:
        """Persist app-owned default values that should be visible in Settings.

        Today this is only ibkr.client_id=1. It is stored, not implicit, so the
        desktop UI can show an app-managed value instead of falling through to
        code-level defaults or legacy env names.
        """
        seeded: list[tuple[str, str]] = []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn = self._connect()
        try:
            for provider, defs in PROVIDER_FIELDS.items():
                for fdef in defs:
                    if fdef.default_value is None:
                        continue
                    before = conn.execute(
                        "SELECT 1 FROM data_provider_config WHERE provider = ? AND field = ?",
                        (provider, fdef.field),
                    ).fetchone()
                    conn.execute(
                        "INSERT OR IGNORE INTO data_provider_config "
                        "(provider, field, value, updated_at) VALUES (?, ?, ?, ?)",
                        (provider, fdef.field, fdef.default_value, now),
                    )
                    if before is None:
                        seeded.append((provider, fdef.field))
            conn.commit()
            return seeded
        finally:
            conn.close()
```

At the start of `apply_env(store)`, before `ensure_env_loaded()`, add:

```python
    store.seed_defaults()
```

- [ ] **Step 5: Add import helper primitives**

Add below `mask_value`:

```python
def importable_env_vars(fdef: FieldDef) -> tuple[str, ...]:
    return (fdef.env_var, *fdef.import_aliases)


def normalize_import_value(fdef: FieldDef, source_env_var: str, value: str) -> str:
    value = value.strip()
    if fdef.env_var == "ARKSCOPE_SEC_USER_AGENT" and source_env_var == "SEC_CONTACT_EMAIL":
        return value if value.startswith("ArkScope ") else f"ArkScope {value}"
    return value


def guarded_change_detail(provider: str, field: str, fdef: FieldDef) -> dict[str, str]:
    return {
        "code": "provider_config_change_guard",
        "status": "confirmation_required",
        "provider": provider,
        "field": field,
        "message": fdef.guard_reason or "Changing this provider setting requires confirmation.",
    }
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_data_provider_config.py -q
```

Expected: all tests in the file pass after updating any `sec_edgar has no configurable fields` assertion in Task 3.

- [ ] **Step 7: Commit**

```bash
git add src/data_provider_config.py tests/test_data_provider_config.py
git commit -m "feat: add provider config defaults and import metadata"
```

---

### Task 3: Provider Config Route View, Guarded PUT, and Per-Field Import

**Files:**
- Modify: `src/api/routes/providers_config.py`
- Modify: `tests/test_data_provider_config.py`

- [ ] **Step 1: Write failing route tests**

Append to `tests/test_data_provider_config.py`:

```python
def test_route_marks_file_source_as_importable(store, monkeypatch):
    from src.api.routes import providers_config as pc

    monkeypatch.setenv("POLYGON_API_KEY", "pk_from_file")
    monkeypatch.setattr("src.env_keys._loaded_keys", {"POLYGON_API_KEY"})
    view = pc.providers_config(store=store)["providers"]
    row = view["polygon"]["fields"][0]
    assert row["effective_source"] == "config/.env"
    assert row["needs_import"] is True
    assert row["import_source"] == "POLYGON_API_KEY"
    assert row["importable_env_vars"] == ["POLYGON_API_KEY"]


def test_import_env_field_promotes_file_value_to_db(store, monkeypatch):
    from src.api.routes import providers_config as pc

    monkeypatch.setenv("POLYGON_API_KEY", "pk_from_file")
    monkeypatch.setattr("src.env_keys._loaded_keys", {"POLYGON_API_KEY"})
    out = pc.import_provider_config_field(
        "polygon",
        "api_key",
        pc.ProviderConfigImportEnv(source_env_var=None),
        store=store,
    )
    row = out["fields"][0]
    assert store.get_all()["polygon"]["api_key"] == "pk_from_file"
    assert row["effective_source"] == "app"
    assert row["needs_import"] is False
    assert "pk_from_file" not in str(out)


def test_sec_contact_email_import_normalizes_to_canonical_user_agent(store, monkeypatch):
    from src.api.routes import providers_config as pc

    monkeypatch.setenv("SEC_CONTACT_EMAIL", "ops@example.com")
    out = pc.import_provider_config_field(
        "sec_edgar",
        "user_agent",
        pc.ProviderConfigImportEnv(source_env_var="SEC_CONTACT_EMAIL"),
        store=store,
    )
    assert store.get_all()["sec_edgar"]["user_agent"] == "ArkScope ops@example.com"
    row = next(f for f in out["fields"] if f["field"] == "user_agent")
    assert row["effective_source"] == "app"
    assert os.environ["ARKSCOPE_SEC_USER_AGENT"] == "ArkScope ops@example.com"


def test_guarded_ibkr_client_id_requires_confirmation(store):
    from fastapi import HTTPException
    from src.api.routes import providers_config as pc

    dpc.apply_env(store)  # seeds ibkr.client_id=1
    with pytest.raises(HTTPException) as e:
        pc.put_provider_config(
            "ibkr",
            pc.ProviderConfigUpdate(fields={"client_id": "7"}),
            store=store,
        )
    assert e.value.status_code == 409
    assert e.value.detail["code"] == "provider_config_change_guard"

    out = pc.put_provider_config(
        "ibkr",
        pc.ProviderConfigUpdate(fields={"client_id": "7"}, confirm_guarded={"client_id": True}),
        store=store,
    )
    row = next(f for f in out["fields"] if f["field"] == "client_id")
    assert row["app_value_masked"] == "7"
    assert row["effective_source"] == "app"
```

Update the old validation test:

```python
with pytest.raises(HTTPException) as e:
    pc.put_provider_config("sec_edgar", pc.ProviderConfigUpdate(fields={"api_key": "x"}), store=store)
assert e.value.status_code == 400
```

because `sec_edgar` now has a configurable `user_agent` field.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_data_provider_config.py::test_route_marks_file_source_as_importable tests/test_data_provider_config.py::test_import_env_field_promotes_file_value_to_db tests/test_data_provider_config.py::test_sec_contact_email_import_normalizes_to_canonical_user_agent tests/test_data_provider_config.py::test_guarded_ibkr_client_id_requires_confirmation -q
```

Expected: fail because route fields and import endpoint do not exist.

- [ ] **Step 3: Extend route models and imports**

In `src/api/routes/providers_config.py`, import the new helpers:

```python
from src.data_provider_config import (
    PROVIDER_FIELDS,
    DataProviderConfigStore,
    apply_env,
    effective_source,
    guarded_change_detail,
    importable_env_vars,
    mask_value,
    normalize_import_value,
    run_connection_test,
    unapply_env,
)
from src.env_keys import ensure_env_loaded
```

Change `ProviderConfigUpdate`:

```python
class ProviderConfigUpdate(BaseModel):
    fields: dict[str, str | None]
    confirm_guarded: dict[str, bool] = {}


class ProviderConfigImportEnv(BaseModel):
    source_env_var: str | None = None
    confirm_guarded: bool = False
```

- [ ] **Step 4: Make `_view` expose import metadata**

Inside `_view`, call `store.seed_defaults()` before reading stored values. Replace the row construction with:

```python
            source = effective_source(f.env_var)
            imports = importable_env_vars(f)
            import_source = None
            if source == "config/.env":
                import_source = f.env_var
            elif source == "missing":
                ensure_env_loaded()
                for candidate in f.import_aliases:
                    if candidate and __import__("os").getenv(candidate):
                        import_source = candidate
                        break
            rows.append({
                "field": f.field,
                "label": f.label,
                "secret": f.secret,
                "env_var": f.env_var,
                "app_value_set": bool(raw),
                "app_value_masked": mask_value(raw, f.secret) if raw else None,
                "effective_source": source,
                "needs_import": import_source is not None and source != "app",
                "import_source": import_source,
                "importable_env_vars": list(imports),
                "defaulted": f.defaulted and bool(raw),
                "guarded": f.guarded,
                "guard_reason": f.guard_reason,
            })
```

Use a normal `import os` at the top instead of `__import__("os")` when implementing.

- [ ] **Step 5: Add guarded PUT behavior**

Before `store.set_field(...)` in `put_provider_config`, add:

```python
        current = (store.get_all().get(provider) or {}).get(field)
        if by_name[field].guarded and (value or None) != (current or None):
            if not body.confirm_guarded.get(field):
                raise HTTPException(
                    status_code=409,
                    detail=guarded_change_detail(provider, field, by_name[field]),
                )
```

- [ ] **Step 6: Add per-field import endpoint**

Add below `put_provider_config`:

```python
@router.post("/providers/config/{provider}/{field}/import-env")
def import_provider_config_field(
    provider: str,
    field: str,
    body: ProviderConfigImportEnv,
    store: DataProviderConfigStore = Depends(get_data_provider_store),
):
    defs = PROVIDER_FIELDS.get(provider)
    if defs is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider!r}")
    by_name = {f.field: f for f in defs}
    fdef = by_name.get(field)
    if fdef is None:
        raise HTTPException(status_code=400, detail=f"unknown field {field!r}")
    ensure_env_loaded()
    candidates = importable_env_vars(fdef)
    source_env_var = body.source_env_var or fdef.env_var
    if source_env_var not in candidates:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "provider_config_import_source_invalid",
                "provider": provider,
                "field": field,
                "source_env_var": source_env_var,
            },
        )
    import os

    raw = (os.getenv(source_env_var) or "").strip()
    if not raw:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "provider_config_import_source_missing",
                "provider": provider,
                "field": field,
                "source_env_var": source_env_var,
            },
        )
    current = (store.get_all().get(provider) or {}).get(field)
    value = normalize_import_value(fdef, source_env_var, raw)
    if fdef.guarded and value != (current or "") and not body.confirm_guarded:
        raise HTTPException(
            status_code=409,
            detail=guarded_change_detail(provider, field, fdef),
        )
    require_profile_state_write("import_provider_config_env", {
        "provider": provider,
        "field": field,
        "source_env_var": source_env_var,
    })
    store.set_field(provider, field, value)
    apply_env(store)
    return _view(store)["providers"][provider]
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_data_provider_config.py -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/api/routes/providers_config.py tests/test_data_provider_config.py
git commit -m "feat: add provider config import and guarded edits"
```

---

### Task 4: Setup-Only Runtime State and Provider Work Guards

**Files:**
- Create: `src/provider_config_runtime.py`
- Create: `tests/test_provider_config_startup.py`
- Modify: `src/api/app.py`
- Modify: `src/api/routes/health.py`
- Modify: `src/api/routes/providers_config.py`
- Modify: `src/api/routes/schedule.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write failing startup tests**

Create `tests/test_provider_config_startup.py`:

```python
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient


def test_profile_db_failure_boots_setup_only(monkeypatch):
    from src.api.app import create_app
    import src.provider_config_runtime as runtime

    runtime.clear_provider_config_setup_required()
    started = {"scheduler": False}

    async def _scheduler_loop():
        started["scheduler"] = True

    def _fail_apply_env(store):
        raise sqlite3.OperationalError("profile_state.db readonly")

    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)
    monkeypatch.setattr("src.data_provider_config.apply_env", _fail_apply_env)
    monkeypatch.setattr("src.service.data_scheduler.scheduler_loop", _scheduler_loop)

    with TestClient(create_app()) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        cfg = client.get("/providers/config").json()
        assert cfg["setup"]["required"] is True
        assert cfg["setup"]["code"] == "provider_config_setup_required"
        assert "profile_state.db readonly" in cfg["setup"]["reason"]
        assert started["scheduler"] is False


def test_provider_work_routes_refuse_in_setup_only(monkeypatch):
    from fastapi import HTTPException
    from src.api.routes import providers_config, schedule
    import src.provider_config_runtime as runtime

    runtime.mark_provider_config_setup_required("profile DB unavailable")
    try:
        with pytest.raises(HTTPException) as e1:
            providers_config.test_provider("polygon")
        assert e1.value.status_code == 503
        assert e1.value.detail["code"] == "provider_config_setup_required"

        with pytest.raises(HTTPException) as e2:
            schedule.run_now("polygon_news")
        assert e2.value.status_code == 503
        assert e2.value.detail["code"] == "provider_config_setup_required"
    finally:
        runtime.clear_provider_config_setup_required()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_provider_config_startup.py -q
```

Expected: fail because `src.provider_config_runtime` does not exist.

- [ ] **Step 3: Add setup-only runtime module**

Create `src/provider_config_runtime.py`:

```python
"""Runtime state for provider-config authority failures.

This state is process-local. It exists only to keep the desktop sidecar useful
when the profile DB is unavailable: read-only setup/status surfaces remain up,
but provider work is refused until the app-managed provider config store is
reachable again.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class ProviderConfigSetupState:
    required: bool
    code: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {"required": self.required, "code": self.code, "reason": self.reason}


_STATE = ProviderConfigSetupState(required=False)


def mark_provider_config_setup_required(reason: str) -> None:
    global _STATE
    _STATE = ProviderConfigSetupState(
        required=True,
        code="provider_config_setup_required",
        reason=reason[:500],
    )


def clear_provider_config_setup_required() -> None:
    global _STATE
    _STATE = ProviderConfigSetupState(required=False)


def provider_config_setup_state() -> ProviderConfigSetupState:
    return _STATE


def require_provider_config_ready(operation: str) -> None:
    state = provider_config_setup_state()
    if not state.required:
        return
    raise HTTPException(
        status_code=503,
        detail={
            "code": "provider_config_setup_required",
            "status": "needs_setup",
            "operation": operation,
            "reason": state.reason,
        },
    )
```

- [ ] **Step 4: Change lifespan to setup-only on apply_env failure**

In `src/api/app.py`, replace the `try/except` block around `apply_env(...)` with:

```python
    provider_config_ready = True
    try:
        from src.data_provider_config import apply_env
        from src.provider_config_runtime import clear_provider_config_setup_required

        from .dependencies import get_data_provider_store

        apply_env(get_data_provider_store())
        clear_provider_config_setup_required()
    except Exception as e:  # noqa: BLE001 — setup-only, never silent pure-.env runtime
        from src.provider_config_runtime import mark_provider_config_setup_required

        provider_config_ready = False
        mark_provider_config_setup_required(str(e))
        logger.warning("data-provider env bridge failed; booting setup-only: %s", e)
```

Change scheduler start condition to:

```python
    if (
        provider_config_ready
        and os.environ.get("ARKSCOPE_DISABLE_SCHEDULER", "").strip().lower()
        not in ("1", "true", "yes", "on")
    ):
        sched_task = asyncio.create_task(scheduler_loop(), name="data-scheduler")
    elif not provider_config_ready:
        logger.warning("data scheduler disabled: provider config setup required")
    else:
        logger.info("data scheduler disabled via ARKSCOPE_DISABLE_SCHEDULER")
```

- [ ] **Step 5: Expose setup state in `/status`**

In `src/api/routes/health.py`, import inside `status()`:

```python
    from src.provider_config_runtime import provider_config_setup_state
```

Add to returned dict:

```python
        "provider_config": provider_config_setup_state().as_dict(),
```

- [ ] **Step 6: Make providers-config GET safe when store construction fails**

In `src/api/routes/providers_config.py`, add:

```python
def _empty_view_with_setup(reason: str) -> dict:
    from src.provider_config_runtime import mark_provider_config_setup_required, provider_config_setup_state

    mark_provider_config_setup_required(reason)
    providers = {
        provider: {
            "fields": [],
            "testable": provider in _TESTABLE,
            "default_available": not fields and provider != "seeking_alpha",
        }
        for provider, fields in PROVIDER_FIELDS.items()
    }
    return {"providers": providers, "setup": provider_config_setup_state().as_dict()}
```

Change `_view` to include setup state:

```python
    from src.provider_config_runtime import provider_config_setup_state
    ...
    return {"providers": providers, "setup": provider_config_setup_state().as_dict()}
```

Change `providers_config` signature from dependency injection to:

```python
@router.get("/providers/config")
def providers_config(store: DataProviderConfigStore | None = None):
    if store is None:
        try:
            store = get_data_provider_store()
        except Exception as e:  # noqa: BLE001
            return _empty_view_with_setup(str(e))
    return _view(store)
```

Keep tests that call `providers_config(store=store)` working.

- [ ] **Step 7: Guard provider test and run-now**

At the start of `test_provider` in `src/api/routes/providers_config.py`:

```python
    from src.provider_config_runtime import require_provider_config_ready
    require_provider_config_ready("provider_test")
```

At the start of `run_now` in `src/api/routes/schedule.py`, after source validation:

```python
    from src.provider_config_runtime import require_provider_config_ready
    require_provider_config_ready("schedule_run_now")
```

At the start of `run_source` in `src/service/data_scheduler.py`, after unknown-source check:

```python
    from src.provider_config_runtime import provider_config_setup_state
    setup_state = provider_config_setup_state()
    if setup_state.required and trigger_source in ("api", "scheduler"):
        return _record_result({
            "source": source,
            "status": "failed",
            "error": setup_state.reason or "provider config setup required",
            "code": setup_state.code,
        })
```

- [ ] **Step 8: Add scheduler guard test**

Append to `tests/test_data_scheduler.py`:

```python
def test_run_source_refuses_provider_work_when_provider_config_setup_required(monkeypatch):
    import src.provider_config_runtime as runtime
    import src.service.data_scheduler as ds

    runtime.mark_provider_config_setup_required("profile DB unavailable")
    try:
        monkeypatch.setattr(ds, "_run_subprocess", lambda argv: (_ for _ in ()).throw(AssertionError("subprocess used")))
        res = ds.run_source("polygon_news", trigger_source="api")
        assert res["status"] == "failed"
        assert res["code"] == "provider_config_setup_required"
    finally:
        runtime.clear_provider_config_setup_required()
```

- [ ] **Step 9: Run tests**

Run:

```bash
pytest tests/test_provider_config_startup.py tests/test_data_scheduler.py::test_run_source_refuses_provider_work_when_provider_config_setup_required -q
```

Expected: pass.

- [ ] **Step 10: Commit**

```bash
git add src/provider_config_runtime.py src/api/app.py src/api/routes/health.py src/api/routes/providers_config.py src/api/routes/schedule.py src/service/data_scheduler.py tests/test_provider_config_startup.py tests/test_data_scheduler.py
git commit -m "feat: fail closed into provider config setup mode"
```

---

### Task 5: Provider Health and Worker Authority Assertions

**Files:**
- Modify: `src/service/provider_health.py`
- Modify: `tests/test_provider_health.py`
- Modify: `tests/test_normalized_ibkr_worker.py`

- [ ] **Step 1: Write failing provider-health provenance test**

Append to `tests/test_provider_health.py`:

```python
def test_config_file_key_source_sets_import_suggestion(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "pk_from_file")
    monkeypatch.setattr("src.env_keys._loaded_keys", {"POLYGON_API_KEY"})
    out = compute_provider_health(_FakeDAL(_FakeBackend()), now=_WEDNESDAY)
    p = _by_id(out, "polygon")
    assert p["key_source"] == "config/.env"
    assert p["key_import_suggested"] is True
```

- [ ] **Step 2: Write failing worker ordering test**

In `tests/test_normalized_ibkr_worker.py`, add:

```python
def test_worker_applies_provider_config_before_gateway_construction(monkeypatch):
    import json
    import src.news_normalized.ibkr_cli as worker

    order: list[str] = []
    monkeypatch.setattr(worker, "_apply_provider_config", lambda: order.append("apply"))

    def _fake_run_worker(*args, **kwargs):
        order.append("run_worker")
        raise RuntimeError("stop before provider construction")

    monkeypatch.setattr(worker, "_run_worker", _fake_run_worker)
    code = worker.main(["--tickers", "AAPL", "--max-articles", "0", "--max-body-fetches", "0"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert order == ["apply", "run_worker"]
```

Add `capsys` to the test signature. This pins the ordering at `main()`: `_run_worker`
is the function that constructs `IBKRDataSource` / `IBKRRuntimeGateway`, so
`_apply_provider_config` must occur first.

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
pytest tests/test_provider_health.py::test_config_file_key_source_sets_import_suggestion tests/test_normalized_ibkr_worker.py::test_worker_applies_provider_config_before_gateway_construction -q
```

Expected: provider-health test fails because the field is absent; worker test either passes already or fails if ordering is not pinned.

- [ ] **Step 4: Add key import suggestion in provider health**

In `src/service/provider_health.py`, update comments to stop saying keys live only in `config/.env`.

Where provider rows are built, add:

```python
"key_import_suggested": key.get("source") == "config/.env",
```

for each provider row that already includes `key_source`. Do not change `status`, `key_present`, or `key_source`.

- [ ] **Step 5: Keep worker ordering test green**

If the worker ordering test failed, move `_apply_provider_config()` to the first line in the worker path before `IBKRRuntimeGateway`, `IBKRDataSource`, or any provider object is constructed. Do not change the sanitization contract.

- [ ] **Step 6: Run tests**

Run:

```bash
pytest tests/test_provider_health.py::test_config_file_key_source_sets_import_suggestion tests/test_normalized_ibkr_worker.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/service/provider_health.py tests/test_provider_health.py tests/test_normalized_ibkr_worker.py
git commit -m "test: pin provider config provenance and worker ordering"
```

---

### Task 6: Settings UI Provenance, Import, and IBKR Guard

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Create: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

- [ ] **Step 1: Write failing Settings tests**

Create `apps/arkscope-web/src/SettingsProviderConfig.test.ts`:

```typescript
/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, ProvidersHealthResponse, TaskRoute } from "./api";

const mocked = vi.hoisted(() => ({
  providersConfig: {
    providers: {
      polygon: {
        fields: [{
          field: "api_key",
          label: "API key",
          secret: true,
          env_var: "POLYGON_API_KEY",
          app_value_set: false,
          app_value_masked: null,
          effective_source: "config/.env",
          needs_import: true,
          import_source: "POLYGON_API_KEY",
          importable_env_vars: ["POLYGON_API_KEY"],
          defaulted: false,
          guarded: false,
          guard_reason: null,
        }],
        testable: true,
        default_available: false,
      },
      ibkr: {
        fields: [{
          field: "client_id",
          label: "Client ID",
          secret: false,
          env_var: "IBKR_CLIENT_ID",
          app_value_set: true,
          app_value_masked: "1",
          effective_source: "app",
          needs_import: false,
          import_source: null,
          importable_env_vars: ["IBKR_CLIENT_ID"],
          defaulted: true,
          guarded: true,
          guard_reason: "Changing IBKR client_id can disturb active Gateway sessions.",
        }],
        testable: true,
        default_available: false,
      },
    },
    setup: { required: false, code: null, reason: null },
  },
  importCalls: [] as Array<{ provider: string; field: string; sourceEnvVar?: string | null }>,
  putCalls: [] as Array<{ provider: string; fields: Record<string, string | null>; confirmGuarded?: Record<string, boolean> }>,
}));

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

const health: ProvidersHealthResponse = {
  providers: [
    { id: "polygon", label: "Polygon", kind: "news", status: "missing_key", enabled: true, key_present: true, key_source: "config/.env", key_vars: ["POLYGON_API_KEY"], last_success_at: null, last_attempt_at: null, last_error: null, detail: "", signals: {}, key_import_suggested: true },
    { id: "ibkr", label: "IBKR", kind: "market", status: "no_signal", enabled: true, key_present: true, key_source: "app", key_vars: ["IBKR_HOST", "IBKR_PORT"], last_success_at: null, last_attempt_at: null, last_error: null, detail: "", signals: {}, key_import_suggested: false },
  ],
  generated_at: "2026-07-02T00:00:00+00:00",
  jobs: {},
  local_market: { db_exists: true, sync: {} },
  notes: [],
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getModelCatalog: vi.fn(async () => emptyCatalog),
    getSchedule: vi.fn(async () => ({ sources: {} })),
    getProvidersHealth: vi.fn(async () => health),
    getProvidersConfig: vi.fn(async () => mocked.providersConfig),
    importProviderConfigField: vi.fn(async (provider: string, field: string, sourceEnvVar?: string | null) => {
      mocked.importCalls.push({ provider, field, sourceEnvVar });
      return mocked.providersConfig.providers[provider];
    }),
    putProviderConfig: vi.fn(async (provider: string, fields: Record<string, string | null>, confirmGuarded?: Record<string, boolean>) => {
      mocked.putCalls.push({ provider, fields, confirmGuarded });
      return mocked.providersConfig.providers[provider];
    }),
    testProvider: vi.fn(),
  };
});

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
  mocked.importCalls = [];
  mocked.putCalls = [];
  vi.restoreAllMocks();
});

async function renderDataSources() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
  });
  await act(async () => { await Promise.resolve(); });
  const dataButton = Array.from(host.querySelectorAll("button")).find((button) =>
    button.textContent?.includes("Data Sources"));
  if (!dataButton) throw new Error("missing Data Sources section button");
  await act(async () => {
    dataButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await act(async () => { await Promise.resolve(); });
}

describe("Settings provider config authority", () => {
  it("renders config-file provenance with per-field import", async () => {
    await renderDataSources();
    expect(host!.textContent).toContain("config/.env");
    expect(host!.textContent).toContain("建議匯入");
    const importButton = Array.from(host!.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("匯入"));
    if (!importButton) throw new Error("missing import button");
    await act(async () => {
      importButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(mocked.importCalls).toEqual([{ provider: "polygon", field: "api_key", sourceEnvVar: "POLYGON_API_KEY" }]);
  });

  it("confirms guarded IBKR client id edits", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderDataSources();
    const input = Array.from(host!.querySelectorAll("input")).find((node) =>
      node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
    if (!input) throw new Error("missing client-id input");
    await act(async () => {
      input.value = "7";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const saveButton = Array.from(host!.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("儲存"));
    if (!saveButton) throw new Error("missing save button");
    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(window.confirm).toHaveBeenCalled();
    expect(mocked.putCalls.at(-1)).toEqual({
      provider: "ibkr",
      fields: { client_id: "7" },
      confirmGuarded: { client_id: true },
    });
  });
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd apps/arkscope-web && npm test -- --run SettingsProviderConfig.test.ts
```

Expected: fail because DTO fields/API function/UI behavior are absent.

- [ ] **Step 3: Extend API DTOs**

In `apps/arkscope-web/src/api.ts`, extend `ProviderHealth`:

```typescript
  key_import_suggested: boolean;
```

Then extend `ProviderConfigField`:

```typescript
  needs_import: boolean;
  import_source: string | null;
  importable_env_vars: string[];
  defaulted: boolean;
  guarded: boolean;
  guard_reason: string | null;
```

Change `getProvidersConfig` return type to include setup:

```typescript
export interface ProviderConfigSetupState {
  required: boolean;
  code: string | null;
  reason: string | null;
}

export interface ProvidersConfigResponse {
  providers: Record<string, ProviderConfigEntry>;
  setup: ProviderConfigSetupState;
}

export function getProvidersConfig(): Promise<ProvidersConfigResponse> {
  return getJSON<ProvidersConfigResponse>("/providers/config", 8_000);
}
```

Change `putProviderConfig`:

```typescript
export function putProviderConfig(
  provider: string,
  fields: Record<string, string | null>,
  confirmGuarded?: Record<string, boolean>,
): Promise<ProviderConfigEntry> {
  return sendJSON(
    `/providers/config/${encodeURIComponent(provider)}`,
    "PUT",
    { fields, confirm_guarded: confirmGuarded ?? {} },
    8_000,
  );
}
```

Add:

```typescript
export function importProviderConfigField(
  provider: string,
  field: string,
  sourceEnvVar?: string | null,
  confirmGuarded = false,
): Promise<ProviderConfigEntry> {
  return sendJSON(
    `/providers/config/${encodeURIComponent(provider)}/${encodeURIComponent(field)}/import-env`,
    "POST",
    { source_env_var: sourceEnvVar ?? null, confirm_guarded: confirmGuarded },
    8_000,
  );
}
```

- [ ] **Step 4: Update Settings UI**

In `apps/arkscope-web/src/Settings.tsx`, add `importProviderConfigField` to the value imports from `./api`, and add `type ProviderConfigField` to the type imports from `./api`.

Add helper near `PROVIDER_STATUS_LABEL`:

```typescript
function providerConfigSourceLabel(source: string): string {
  if (source === "app") return "App";
  if (source === "env") return "環境變數";
  if (source === "config/.env") return "config/.env";
  if (source === "missing") return "未設定";
  return source;
}
```

Add handler inside `DataSourcesSection`:

```typescript
  async function importField(provider: string, field: string, sourceEnvVar: string | null) {
    if (busy) return;
    setBusy(`import.${provider}.${field}`);
    try {
      await importProviderConfigField(provider, field, sourceEnvVar);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
```

Change `saveField` signature and body:

```typescript
  async function saveField(provider: string, field: string, value: string | null, fieldMeta?: ProviderConfigField) {
    if (busy) return;
    const confirmGuarded =
      fieldMeta?.guarded && value !== null
        ? window.confirm(fieldMeta.guard_reason ?? "此設定需要確認後才會變更。")
        : true;
    if (!confirmGuarded) return;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(
        provider,
        { [field]: value },
        fieldMeta?.guarded ? { [field]: true } : undefined,
      );
      setKeyDrafts((d) => ({ ...d, [`${provider}.${field}`]: "" }));
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }
```

Update all `saveField(pid, f.field, ...)` calls to pass `f` as the fourth argument.

Replace the provider-config copy:

```tsx
App 管理各 provider 的金鑰與連線設定（存本地、僅顯示遮罩值）。真實環境變數仍可作為 operator escape hatch；
若目前來源是 config/.env，請逐欄匯入到 App 設定。儲存即生效（毋須重啟）。
```

In the value cell, render import/default/guard state:

```tsx
{f.defaulted && <span className="muted tiny"> · 預設</span>}
<span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
{f.needs_import && (
  <button className="btn-ghost tiny"
    disabled={busy === `import.${pid}.${f.field}`}
    onClick={() => void importField(pid, f.field, f.import_source)}>
    匯入
  </button>
)}
{f.needs_import && <span className="muted tiny">建議匯入</span>}
```

- [ ] **Step 5: Run frontend test**

Run:

```bash
cd apps/arkscope-web && npm test -- --run SettingsProviderConfig.test.ts
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "feat: show provider config provenance in settings"
```

---

### Task 7: Verification and Documentation Sync

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Test-only command outputs, no new source files unless a failure requires a fix.

- [ ] **Step 1: Update S-J progress text**

In `docs/design/PG_EXIT_REMAINDER_SCOPING.md`, under §13.6, add:

```markdown
Phase 0-1 implementation status: audit table recorded; SEC UA and IBKR
client-id defaults are app-managed; `config/.env` fallback is still allowed but
visible/importable; profile DB startup failure now enters setup-only mode.
Phase 2 strict-by-default remains pending.
```

- [ ] **Step 2: Run backend focused suite**

Run:

```bash
pytest \
  tests/test_data_provider_config.py \
  tests/test_provider_config_startup.py \
  tests/test_provider_health.py \
  tests/test_data_scheduler.py::test_run_source_refuses_provider_work_when_provider_config_setup_required \
  tests/test_normalized_ibkr_worker.py \
  -q
```

Expected: pass.

- [ ] **Step 3: Run frontend focused suite**

Run:

```bash
cd apps/arkscope-web && npm test -- --run SettingsProviderConfig.test.ts SettingsNewsStorage.test.ts
```

Expected: pass.

- [ ] **Step 4: Run import/provenance grep gate**

Run:

```bash
rg -n "keys live in config/.env|優先序：環境變數 ＞ App 設定 ＞ config/.env|keys stay in config/.env|SEC_CONTACT_EMAIL not set" src apps/arkscope-web/src data_sources | tee /tmp/s-j-stale-copy.txt
```

Expected: no stale data-provider UI copy remains in `src/api/routes/providers_config.py`, `src/service/provider_health.py`, or `apps/arkscope-web/src/Settings.tsx`. It is acceptable for retiring `scripts/`, old tests, or legacy SEC modules not touched by this slice to remain; those should be listed in the Phase 0 audit table.

- [ ] **Step 5: Verify docs-only plus intended source paths**

Run:

```bash
git diff --name-only HEAD~7..HEAD
```

Expected paths are limited to:

```text
docs/design/PG_EXIT_REMAINDER_SCOPING.md
src/data_provider_config.py
src/provider_config_runtime.py
src/api/app.py
src/api/routes/health.py
src/api/routes/providers_config.py
src/api/routes/schedule.py
src/service/data_scheduler.py
src/service/provider_health.py
tests/test_data_provider_config.py
tests/test_provider_config_startup.py
tests/test_data_scheduler.py
tests/test_provider_health.py
tests/test_normalized_ibkr_worker.py
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/SettingsProviderConfig.test.ts
```

- [ ] **Step 6: Commit documentation sync**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md
git commit -m "docs: mark provider config authority phase one"
```

---

## Final Acceptance Checklist

- [ ] Phase 0 audit table exists and classifies managed, legacy-env-only, retiring, and out-of-scope provider env vars.
- [ ] `sec_edgar.user_agent` is FieldDef-managed with canonical `ARKSCOPE_SEC_USER_AGENT` and explicit import aliases.
- [ ] `ibkr.client_id` is seeded as app-managed value `1`, and edits require confirmation.
- [ ] `/providers/config` exposes `needs_import`, `import_source`, `guarded`, `defaulted`, and setup state.
- [ ] Per-field import promotes a selected env value into `data_provider_config` without printing raw secrets.
- [ ] Profile DB startup failure boots setup-only: `/healthz` and provider config status work; scheduler is not started; run-now/provider-test refuse with structured 503.
- [ ] Current Phase 1 does not add `provider_env_fallback` and does not implement strict `provider_config_missing`.
- [ ] Frontend Settings renders `config/.env` as an import suggestion, not as an invisible authority.
- [ ] Focused backend and frontend tests pass.
