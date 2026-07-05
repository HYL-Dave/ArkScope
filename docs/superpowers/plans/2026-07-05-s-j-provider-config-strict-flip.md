# S-J Provider Config Strict Flip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip FieldDef-managed provider configuration to strict DB-first authority by default, with `provider_env_fallback=true` as the explicit legacy rollback lever and structured `provider_config_missing` results at runtime surfaces.

**Architecture:** Keep authority centralized in `src/data_provider_config.py`: one tri-state policy resolver, one env bridge, one structured missing-config shape. Keep `config/.env` available for legacy env-only variables and per-field import, but prevent it from being runtime authority for managed provider fields unless fallback is explicitly enabled. Runtime call sites preflight against the same helper before provider construction, so legacy collector modules that read `config/.env` directly cannot bypass strict mode.

**Tech Stack:** Python 3, SQLite `profile_state.db`, FastAPI route handlers, pytest, React/Vite/Vitest Settings UI.

---

## Map Check / Authority

**Priority map:** `docs/design/PROJECT_PRIORITY_MAP.md` P0-D says Provider config authority Phase 2 is schedulable; soak gate is satisfied on the primary machine.

**Design contract:** `docs/design/PG_EXIT_REMAINDER_SCOPING.md` §13 is the authority:

- strict scope is **FieldDefs-managed vars only**;
- real shell env remains the operator escape hatch;
- `config/.env` is import/export and migration material, not default runtime authority;
- `provider_env_fallback` tri-state uses the news S3.2 pattern: unset -> strict, explicit `true` -> legacy fallback, explicit `false` -> strict pinned;
- missing required managed config returns the shared machine shape:

```json
{"code":"provider_config_missing","status":"not_configured","provider":"polygon","field":"api_key"}
```

**Out of scope:**

- LLM credentials, OAuth, and model auth;
- PG DSN / `DATABASE_URL`;
- OS keyring;
- sweeping every `os.getenv()` in retiring scripts;
- adding new provider keys or bulk-importing `.env`.

## Decisions Locked For This Slice

1. **Blocking applies to required FieldDefs.** Fields with `optional=True` (currently `sec_edgar.user_agent`) still show missing/import affordances but do not block the provider or change `default_available`.
2. **Canonical env vars are the configured surface.** `FieldDef.env_var` values are the managed runtime authority. `FieldDef.import_aliases` are import material. Strict mode must stop file-loaded aliases from leaking into the sidecar process; a real shell alias remains an explicit operator escape hatch and is recorded as legacy env-only behavior, not an app-managed source.
3. **`profile_settings` is reused.** Store the profile setting in the existing `profile_state.db` key/value table as `provider_env_fallback`; expose `ARKSCOPE_PROVIDER_ENV_FALLBACK` as the env override.
4. **No silent provider construction.** Scheduler routes and tool surfaces call the shared helper before constructing providers. This is required because Polygon/Finnhub collector `load_env()` functions can read `config/.env` directly.
5. **No UI mainline toggle for normal use.** Settings may render the policy and offer a guarded rollback control, but the default state is strict. The normal user path remains per-field import/save.

## File Map

- Modify `src/env_keys.py`
  - Add non-mutating env-file parsing helpers and strict-mode loading helpers:
    - `read_env_file_values()`
    - `peek_env_file_value(name)`
    - `ensure_env_loaded_excluding(excluded_keys)`
    - `discard_loaded_key(name)`
- Modify `src/data_provider_config.py`
  - Add `profile_settings` schema to `DataProviderConfigStore`.
  - Add `provider_env_fallback` tri-state resolver.
  - Add managed env-var/alias inventory helpers.
  - Change `apply_env()` / `unapply_env()` to default strict and only restore file fallback when explicit fallback is enabled.
  - Add `ProviderConfigMissing`, `provider_config_missing_detail()`, `missing_required_provider_fields()`, and `require_provider_configured()`.
- Modify `src/provider_config_runtime.py`
  - No new state required, but tests should keep setup-only behavior separate from missing-provider-field behavior.
- Modify `src/api/routes/providers_config.py`
  - Include policy state in GET `/providers/config`.
  - Add a profile-setting route for explicit fallback rollback.
  - Use strict-aware `peek_env_file_value()` for import affordances without making `.env` authoritative.
  - Return `provider_config_missing` from provider connection tests before live probes.
- Modify `src/service/provider_health.py`
  - Stop calling raw `ensure_env_loaded()` for managed-key presence.
  - Report `not_configured` + `config_error` for required missing managed fields.
  - Keep `legacy_env_only` warnings as notes, not blockers.
- Modify `src/service/data_scheduler.py`
  - Preflight managed provider config before Polygon/Finnhub/IBKR provider construction.
  - Return `status="not_configured"` with the shared machine code for missing required config, without recording a durable provider failure.
- Modify `src/tools/analyst_tools.py`
  - Return the shared structured `provider_config_missing` payload for Finnhub analyst tools when `FINNHUB_API_KEY` is not configured under strict mode.
- Modify `src/news_normalized/ibkr_cli.py` and `src/prices_runtime.py`
  - No runtime logic expected beyond using updated `apply_env()`.
  - Add tests proving standalone workers inherit strict policy via `apply_env(DataProviderConfigStore())`.
- Modify `apps/arkscope-web/src/api.ts`
  - Update provider status union and config DTO for fallback policy / config errors.
- Modify `apps/arkscope-web/src/Settings.tsx`
  - Render `not_configured` distinctly.
  - Update stale precedence copy.
  - Show strict policy / explicit fallback state without re-blessing `.env`.
- Modify tests:
  - `tests/test_data_provider_config.py`
  - `tests/test_provider_health.py`
  - `tests/test_data_scheduler.py`
  - `tests/test_analyst_tools.py`
  - `tests/test_prices_runtime.py`
  - `tests/test_normalized_ibkr_worker.py`
  - `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

## Task 1: Policy Store + Env-File Primitives

**Files:**
- Modify: `src/env_keys.py`
- Modify: `src/data_provider_config.py`
- Test: `tests/test_data_provider_config.py`

- [ ] **Step 0: Make `test_data_provider_config.py` file-loader hermetic**

Update the existing `hermetic()` autouse fixture in `tests/test_data_provider_config.py` so the whole file uses a throwaway empty env file. This is required because strict `apply_env()` will discard unmanaged file-loaded managed keys; without an isolated `env_file_path`, a developer machine with a real `config/.env` and a virgin worktree without one take different paths.

Add this inside the fixture before the `delenv` loop:

```python
    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")
    monkeypatch.setattr("src.env_keys.env_file_path", lambda: empty_env)
```

Change the fixture signature:

```python
def hermetic(monkeypatch, tmp_path):
```

Keep the existing `_loaded=True`, `_loaded_keys=set()`, `_APP_APPLIED=set()`, and `reload_var_from_file` stubbing. Tests that need a non-empty env file override `env_file_path` themselves.

- [ ] **Step 1: Add RED tests for the tri-state setting**

Append these tests near the env bridge tests in `tests/test_data_provider_config.py`:

```python
def test_provider_env_fallback_defaults_strict(store, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", raising=False)
    assert dpc.provider_env_fallback_enabled(store) is False
    assert dpc.provider_env_fallback_source(store) == "default"


def test_provider_env_fallback_profile_true_is_legacy_rollback(store, monkeypatch):
    monkeypatch.delenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", raising=False)
    store.set_setting("provider_env_fallback", "true")
    assert dpc.provider_env_fallback_enabled(store) is True
    assert dpc.provider_env_fallback_source(store) == "profile"


def test_provider_env_fallback_env_override_wins(store, monkeypatch):
    store.set_setting("provider_env_fallback", "true")
    monkeypatch.setenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", "false")
    assert dpc.provider_env_fallback_enabled(store) is False
    assert dpc.provider_env_fallback_source(store) == "env"

    monkeypatch.setenv("ARKSCOPE_PROVIDER_ENV_FALLBACK", "yes")
    assert dpc.provider_env_fallback_enabled(store) is True
    assert dpc.provider_env_fallback_source(store) == "env"
```

- [ ] **Step 2: Run the RED tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_provider_env_fallback_defaults_strict or test_provider_env_fallback_profile_true_is_legacy_rollback or test_provider_env_fallback_env_override_wins" \
  -q
```

Expected: FAIL with missing `set_setting` / `provider_env_fallback_enabled` symbols.

- [ ] **Step 3: Extend the store schema and setting helpers**

In `src/data_provider_config.py`, extend `_SCHEMA`:

```python
CREATE TABLE IF NOT EXISTS profile_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
```

Add methods to `DataProviderConfigStore`:

```python
    def get_setting(self, key: str) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM profile_settings WHERE key = ?", (key,)
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None

    def set_setting(self, key: str, value: Optional[str]) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO profile_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            conn.commit()
        finally:
            conn.close()
```

Add constants and policy helpers near `provider_default_available()`:

```python
PROVIDER_ENV_FALLBACK_KEY = "provider_env_fallback"
ENV_PROVIDER_ENV_FALLBACK = "ARKSCOPE_PROVIDER_ENV_FALLBACK"
_TRUTHY = ("1", "true", "yes", "on")
_FALSY = ("0", "false", "no", "off")


def parse_provider_env_fallback(value: Any) -> Optional[bool]:
    text = str(value).strip().lower() if value is not None else ""
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return None


def provider_env_fallback_enabled(store: DataProviderConfigStore | None = None) -> bool:
    env_value = parse_provider_env_fallback(os.environ.get(ENV_PROVIDER_ENV_FALLBACK))
    if env_value is not None:
        return env_value
    if store is not None:
        try:
            profile_value = parse_provider_env_fallback(store.get_setting(PROVIDER_ENV_FALLBACK_KEY))
            if profile_value is not None:
                return profile_value
        except Exception:  # noqa: BLE001 - strict default on setting read failure
            logger.warning("provider_env_fallback setting read failed; defaulting strict", exc_info=True)
    return False


def provider_env_fallback_source(store: DataProviderConfigStore | None = None) -> str:
    if parse_provider_env_fallback(os.environ.get(ENV_PROVIDER_ENV_FALLBACK)) is not None:
        return "env"
    if store is not None:
        try:
            if parse_provider_env_fallback(store.get_setting(PROVIDER_ENV_FALLBACK_KEY)) is not None:
                return "profile"
        except Exception:  # noqa: BLE001
            return "default"
    return "default"
```

- [ ] **Step 4: Run the tri-state tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_provider_env_fallback_defaults_strict or test_provider_env_fallback_profile_true_is_legacy_rollback or test_provider_env_fallback_env_override_wins" \
  -q
```

Expected: PASS.

- [ ] **Step 5: Add RED tests for selective env-file loading**

Append:

```python
def test_env_file_peek_reads_without_mutating_process(monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text("POLYGON_API_KEY='pk_file'\nALPHA_VANTAGE_API_KEY=av_file\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)

    assert env_keys.peek_env_file_value("POLYGON_API_KEY") == "pk_file"
    assert "POLYGON_API_KEY" not in os.environ
    assert "POLYGON_API_KEY" not in env_keys.keys_loaded_from_file()


def test_env_loader_excludes_managed_key_but_loads_legacy_key(monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text("POLYGON_API_KEY=pk_file\nALPHA_VANTAGE_API_KEY=av_file\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    env_keys.ensure_env_loaded_excluding({"POLYGON_API_KEY"})

    assert "POLYGON_API_KEY" not in os.environ
    assert os.environ["ALPHA_VANTAGE_API_KEY"] == "av_file"
    assert env_keys.keys_loaded_from_file() == frozenset({"ALPHA_VANTAGE_API_KEY"})
```

- [ ] **Step 6: Run the RED tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_env_file_peek_reads_without_mutating_process or test_env_loader_excludes_managed_key_but_loads_legacy_key" \
  -q
```

Expected: FAIL with missing `peek_env_file_value` / `ensure_env_loaded_excluding`.

- [ ] **Step 7: Implement env-file primitives**

In `src/env_keys.py`, refactor parsing without changing current behavior:

```python
def read_env_file_values() -> dict[str, str]:
    env_path = env_file_path()
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = unquote_env_value(value)
        if key and value:
            out[key] = value
    return out


def peek_env_file_value(name: str) -> str | None:
    return read_env_file_values().get(name)
```

Change `ensure_env_loaded()` to delegate:

```python
def ensure_env_loaded() -> None:
    ensure_env_loaded_excluding(set())


def ensure_env_loaded_excluding(excluded_keys: set[str] | frozenset[str]) -> None:
    """Load config/.env once, skipping explicit keys.

    Strict provider config uses this to keep legacy_env_only variables alive while
    preventing managed provider keys from becoming runtime authority.
    """
    global _loaded
    if _loaded:
        return
    excluded = set(excluded_keys or set())
    for key, value in read_env_file_values().items():
        if key in excluded:
            continue
        if key not in os.environ:
            os.environ[key] = value
            _loaded_keys.add(key)
    _loaded = True


def discard_loaded_key(name: str) -> bool:
    """Remove a key only when this loader supplied it from config/.env."""
    if name not in _loaded_keys:
        return False
    os.environ.pop(name, None)
    _loaded_keys.discard(name)
    return True
```

- [ ] **Step 8: Run the env primitive tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_env_file_peek_reads_without_mutating_process or test_env_loader_excludes_managed_key_but_loads_legacy_key" \
  -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add src/env_keys.py src/data_provider_config.py tests/test_data_provider_config.py
git commit -m "feat: add provider env fallback policy"
```

## Task 2: Strict Env Bridge

**Files:**
- Modify: `src/data_provider_config.py`
- Modify: `src/env_keys.py`
- Test: `tests/test_data_provider_config.py`

- [ ] **Step 1: Add RED tests for strict apply behavior**

Append:

```python
def test_apply_env_strict_excludes_managed_file_key_but_keeps_legacy_env_only(store, monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text(
        "POLYGON_API_KEY=pk_file\n"
        "SEC_CONTACT_EMAIL=legacy@example.com\n"
        "ALPHA_VANTAGE_API_KEY=av_file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    dpc.apply_env(store)

    assert "POLYGON_API_KEY" not in os.environ
    assert "SEC_CONTACT_EMAIL" not in os.environ  # import alias; not runtime authority
    assert os.environ["ALPHA_VANTAGE_API_KEY"] == "av_file"  # legacy_env_only keeps working
    assert dpc.effective_source("POLYGON_API_KEY") == "missing"


def test_apply_env_strict_db_value_wins_without_file_source_tracking(store, monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text("POLYGON_API_KEY=pk_file\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    store.set_field("polygon", "api_key", "pk_app")

    dpc.apply_env(store)

    assert os.environ["POLYGON_API_KEY"] == "pk_app"
    assert "POLYGON_API_KEY" not in env_keys.keys_loaded_from_file()
    assert dpc.effective_source("POLYGON_API_KEY") == "app"


def test_apply_env_explicit_fallback_true_restores_legacy_file_fallback(store, monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text("POLYGON_API_KEY=pk_file\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    store.set_setting("provider_env_fallback", "true")

    dpc.apply_env(store)

    assert os.environ["POLYGON_API_KEY"] == "pk_file"
    assert dpc.effective_source("POLYGON_API_KEY") == "config/.env"
```

- [ ] **Step 2: Run the RED tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_apply_env_strict_excludes_managed_file_key_but_keeps_legacy_env_only or test_apply_env_strict_db_value_wins_without_file_source_tracking or test_apply_env_explicit_fallback_true_restores_legacy_file_fallback" \
  -q
```

Expected: FAIL because `apply_env()` still uses legacy fallback.

- [ ] **Step 3: Add managed-key inventory helpers**

In `src/data_provider_config.py`, add:

```python
def managed_env_vars() -> frozenset[str]:
    return frozenset(f.env_var for defs in PROVIDER_FIELDS.values() for f in defs)


def managed_import_aliases() -> frozenset[str]:
    return frozenset(
        alias for defs in PROVIDER_FIELDS.values() for f in defs for alias in f.import_aliases
    )


def managed_runtime_file_keys() -> frozenset[str]:
    """Keys config/.env must not load into runtime authority under strict mode."""
    return managed_env_vars() | managed_import_aliases()
```

- [ ] **Step 4: Replace `apply_env()` strict/fallback behavior**

In `src/data_provider_config.py`, update `apply_env()`:

```python
def apply_env(store: DataProviderConfigStore) -> frozenset:
    """Inject stored values into os.environ.

    Default strict mode:
      real shell env > app DB > missing
    Explicit provider_env_fallback=true:
      real shell env > app DB > config/.env
    """
    from src.env_keys import (
        discard_loaded_key,
        ensure_env_loaded,
        ensure_env_loaded_excluding,
        keys_loaded_from_file,
        reload_var_from_file,
    )

    store.seed_defaults()
    fallback = provider_env_fallback_enabled(store)
    excluded = managed_runtime_file_keys()
    if fallback:
        ensure_env_loaded()
    else:
        ensure_env_loaded_excluding(excluded)

    file_keys = keys_loaded_from_file()
    stored = store.get_all()
    configured_vars: set[str] = set()

    for provider, fields in stored.items():
        for field, value in fields.items():
            fdef = _FIELD_BY_KEY.get((provider, field))
            if fdef is None or not value:
                continue
            var = fdef.env_var
            configured_vars.add(var)
            if var in os.environ and var not in file_keys and var not in _APP_APPLIED:
                continue
            os.environ[var] = value
            _APP_APPLIED.add(var)

    if fallback:
        for var in managed_env_vars() - configured_vars:
            if var in os.environ and var not in file_keys and var not in _APP_APPLIED:
                continue
            reload_var_from_file(var)
        logger.warning("provider_env_fallback=true: managed provider fields may use config/.env")
    else:
        for var in excluded:
            if var in configured_vars:
                continue
            if var in _APP_APPLIED:
                _APP_APPLIED.discard(var)
                os.environ.pop(var, None)
            else:
                discard_loaded_key(var)
    return frozenset(_APP_APPLIED)
```

- [ ] **Step 5: Update `unapply_env()`**

Replace `unapply_env()` with strict-aware behavior:

```python
def unapply_env(env_var: str, store: DataProviderConfigStore | None = None) -> None:
    """After clearing an app value: strict mode unsets it; fallback mode reloads file value."""
    if env_var not in _APP_APPLIED:
        return
    _APP_APPLIED.discard(env_var)
    if store is not None and provider_env_fallback_enabled(store):
        from src.env_keys import reload_var_from_file

        reload_var_from_file(env_var)
    else:
        os.environ.pop(env_var, None)
```

Task 5 updates the route caller to pass `store`.

- [ ] **Step 6: Run strict env bridge tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_apply_env_strict_excludes_managed_file_key_but_keeps_legacy_env_only or test_apply_env_strict_db_value_wins_without_file_source_tracking or test_apply_env_explicit_fallback_true_restores_legacy_file_fallback or test_apply_env_injects_and_tracks or test_real_env_var_wins_over_app or test_app_overrides_file_loaded_value or test_unapply_falls_back_to_file" \
  -q
```

Expected: the three new tests PASS; the old `test_unapply_falls_back_to_file` FAILS because it encodes legacy default.

- [ ] **Step 7: Flip the old unapply contract**

Replace `test_unapply_falls_back_to_file` with two tests:

```python
def test_unapply_strict_unsets_app_value(store, monkeypatch):
    store.set_field("finnhub", "api_key", "fk_app")
    dpc.apply_env(store)
    assert os.environ["FINNHUB_API_KEY"] == "fk_app"
    dpc.unapply_env("FINNHUB_API_KEY", store)
    assert "FINNHUB_API_KEY" not in os.environ
    assert dpc.effective_source("FINNHUB_API_KEY") == "missing"


def test_unapply_explicit_fallback_reloads_file_value(store, monkeypatch):
    calls = []

    def _reload(name):
        calls.append(name)
        os.environ[name] = "fk_from_file_again"
        return True

    monkeypatch.setattr("src.env_keys.reload_var_from_file", _reload)
    store.set_setting("provider_env_fallback", "true")
    store.set_field("finnhub", "api_key", "fk_app")
    dpc.apply_env(store)
    dpc.unapply_env("FINNHUB_API_KEY", store)
    assert calls == ["FINNHUB_API_KEY"]
    assert os.environ["FINNHUB_API_KEY"] == "fk_from_file_again"
```

- [ ] **Step 8: Run the full data-provider config test file**

Run:

```bash
pytest tests/test_data_provider_config.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add src/env_keys.py src/data_provider_config.py tests/test_data_provider_config.py
git commit -m "feat: make provider env bridge strict by default"
```

## Task 3: Structured Missing Config Surfaces

**Files:**
- Modify: `src/data_provider_config.py`
- Modify: `src/api/routes/providers_config.py`
- Modify: `src/service/provider_health.py`
- Modify: `src/tools/analyst_tools.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Test: `tests/test_data_provider_config.py`
- Test: `tests/test_provider_health.py`
- Test: `tests/test_analyst_tools.py`

- [ ] **Step 1: Add RED tests for the shared payload**

Append to `tests/test_data_provider_config.py`:

```python
def test_required_provider_missing_detail_uses_machine_contract(store):
    detail = dpc.provider_config_missing_detail("polygon", "api_key")
    assert detail == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "polygon",
        "field": "api_key",
        "env_var": "POLYGON_API_KEY",
    }


def test_missing_required_provider_fields_ignores_optional_sec_user_agent(store):
    missing = dpc.missing_required_provider_fields("sec_edgar")
    assert missing == []
    assert dpc.missing_required_provider_fields("polygon")[0]["field"] == "api_key"
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_required_provider_missing_detail_uses_machine_contract or test_missing_required_provider_fields_ignores_optional_sec_user_agent" \
  -q
```

Expected: FAIL with missing helper symbols.

- [ ] **Step 3: Implement the shared missing-config helper**

In `src/data_provider_config.py`, add:

```python
class ProviderConfigMissing(RuntimeError):
    def __init__(self, provider: str, field: str, env_var: str):
        super().__init__(f"{provider}.{field} is not configured")
        self.provider = provider
        self.field = field
        self.env_var = env_var

    def as_dict(self) -> dict[str, str]:
        return provider_config_missing_detail(self.provider, self.field)


def provider_config_missing_detail(provider: str, field: str) -> dict[str, str]:
    fdef = _FIELD_BY_KEY[(provider, field)]
    return {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": provider,
        "field": field,
        "env_var": fdef.env_var,
    }


def missing_required_provider_fields(provider: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for fdef in PROVIDER_FIELDS.get(provider, []):
        if fdef.optional:
            continue
        if not os.getenv(fdef.env_var):
            out.append(provider_config_missing_detail(provider, fdef.field))
    return out


def require_provider_configured(provider: str) -> None:
    missing = missing_required_provider_fields(provider)
    if missing:
        first = missing[0]
        raise ProviderConfigMissing(first["provider"], first["field"], first["env_var"])
```

- [ ] **Step 4: Run payload tests**

Run:

```bash
pytest tests/test_data_provider_config.py \
  -k "test_required_provider_missing_detail_uses_machine_contract or test_missing_required_provider_fields_ignores_optional_sec_user_agent" \
  -q
```

Expected: PASS.

- [ ] **Step 5: Add RED route test for provider connection tests**

Append to `tests/test_data_provider_config.py`:

```python
def test_provider_test_missing_required_config_returns_structured_detail(store, monkeypatch):
    from fastapi import HTTPException
    from src.api.routes import providers_config as pc
    import src.provider_config_runtime as runtime

    runtime.clear_provider_config_setup_required()
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    with pytest.raises(HTTPException) as e:
        pc.test_provider("polygon")
    assert e.value.status_code == 409
    assert e.value.detail["code"] == "provider_config_missing"
    assert e.value.detail["status"] == "not_configured"
    assert e.value.detail["provider"] == "polygon"
    assert e.value.detail["field"] == "api_key"
```

- [ ] **Step 6: Implement route preflight**

In `src/api/routes/providers_config.py`, import `ProviderConfigMissing` and `require_provider_configured`. Update `test_provider()`:

```python
    try:
        require_provider_configured(provider)
    except ProviderConfigMissing as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict())
```

Place this after the unknown-provider check and before `run_connection_test(provider)`.

- [ ] **Step 7: Add provider-health RED test**

Append to `tests/test_provider_health.py`:

```python
def test_provider_health_missing_managed_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    dal = _FakeDAL(_FakeBackend(stats=_stats(
        news_rows=[("polygon", _WEDNESDAY - timedelta(hours=1), 9)])))
    p = _by_id(compute_provider_health(dal, now=_WEDNESDAY), "polygon")
    assert p["status"] == "not_configured"
    assert p["config_error"] == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "polygon",
        "field": "api_key",
        "env_var": "POLYGON_API_KEY",
    }
```

- [ ] **Step 8: Implement provider-health strict key info**

In `src/service/provider_health.py`:

1. Extend provider statuses in comments/docstrings to include `not_configured`.
2. Import `missing_required_provider_fields`.
3. Stop calling raw `ensure_env_loaded()` for managed key presence. Instead:

```python
    try:
        from src.data_provider_config import app_applied_keys, missing_required_provider_fields
        from src.env_keys import keys_loaded_from_file
        loaded_file_keys = keys_loaded_from_file()
        app_keys = app_applied_keys()
    except Exception as e:  # noqa: BLE001
        notes.append(f"provider config tracking failed: {e}")
```

4. Add a `config_error` parameter to `_add()`:

```python
             config_error: Optional[dict] = None) -> None:
```

5. Compute status with config error taking precedence unless the provider is disabled:

```python
            "status": (
                "not_configured"
                if config_error is not None and enabled is not False
                else _status(...)
            ),
            "config_error": config_error,
```

6. For required providers, pass `config_error`:

```python
polygon_missing = missing_required_provider_fields(pid)
config_error=polygon_missing[0] if polygon_missing else None
```

For IBKR, use `"ibkr"`. For FRED, keep `disabled` precedence when macro ingestion is off.

- [ ] **Step 9: Update frontend status type**

In `apps/arkscope-web/src/api.ts`:

```ts
export type ProviderStatus =
  | "connected" | "stale" | "maintenance" | "no_signal"
  | "missing_key" | "not_configured" | "disabled";
```

Add to `ProviderHealth`:

```ts
  config_error?: {
    code: string;
    status: string;
    provider: string;
    field: string;
    env_var: string;
  } | null;
```

- [ ] **Step 10: Add analyst-tool RED test**

Append to `tests/test_analyst_tools.py`:

```python
def test_analyst_consensus_missing_finnhub_returns_provider_config_missing(monkeypatch):
    import src.tools.analyst_tools as mod

    mod._session = None
    mod._api_key = None
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    result = get_analyst_consensus("NVDA")

    assert result["code"] == "provider_config_missing"
    assert result["status"] == "not_configured"
    assert result["provider"] == "finnhub"
    assert result["field"] == "api_key"
    assert result["ticker"] == "NVDA"
```

- [ ] **Step 11: Implement analyst-tool structured return**

In `src/tools/analyst_tools.py`, import `ProviderConfigMissing` / `require_provider_configured`, and update `get_analyst_consensus()`:

```python
    ticker = ticker.upper()
    try:
        require_provider_configured("finnhub")
    except ProviderConfigMissing as exc:
        return {"ticker": ticker, **exc.as_dict()}
```

Keep `_get_finnhub_session()` as a low-level helper; the public tool surface is the structured contract.

- [ ] **Step 11.5: Flip named old contracts surgically**

Do not use a vague "fix whatever fails" pass here. These are the old contracts known to be superseded by strict mode:

In `tests/test_provider_health.py`:

1. `test_missing_key_wins_over_signal`
   - Rename to `test_missing_required_config_wins_over_signal`.
   - Change status expectation from `"missing_key"` to `"not_configured"`.
   - Add `config_error["code"] == "provider_config_missing"` and `field == "api_key"`.
2. `test_key_source_reports_effective_origin`
   - Keep the real-env cases (`POLYGON_API_KEY`, `IBKR_HOST`) as `env`.
   - Remove the expectation that a file-loaded managed key is effective `config/.env`.
   - Add a separate assertion that file-loaded `FINNHUB_API_KEY` is ignored under strict and yields `not_configured`.
3. `test_config_file_key_source_sets_import_suggestion`
   - Move the import-suggestion assertion to `tests/test_data_provider_config.py::test_strict_view_peeks_config_file_for_import_without_effective_source`.
   - Change provider-health expectation to `not_configured` with `provider_config_missing`; provider-health no longer re-blesses `.env` as source.
4. `test_disabled_outranks_missing_key`
   - Keep the status expectation as `"disabled"` for Financial Datasets when disabled.
   - Add an assertion that disabled state still outranks `provider_config_missing`.

In `tests/test_analyst_tools.py`:

1. `TestFinnhubGet.test_no_api_key`
   - Keep the low-level `_finnhub_get("/test")` / `_get_finnhub_session()` exception behavior because that helper still models the raw client.
   - Add the public-tool test from Step 10 so `get_analyst_consensus()` returns structured `provider_config_missing`.
   - Do not delete the low-level test; it still protects the helper surface.

- [ ] **Step 12: Run Task 3 focused tests**

Run:

```bash
pytest tests/test_data_provider_config.py tests/test_provider_health.py tests/test_analyst_tools.py -q
```

Expected: PASS after only the named old contracts in Step 11.5 are flipped. Do not delete unrelated assertions; preserve coverage outside the superseded `.env` authority expectations.

- [ ] **Step 13: Commit Task 3**

Run:

```bash
git add src/data_provider_config.py src/api/routes/providers_config.py src/service/provider_health.py src/tools/analyst_tools.py apps/arkscope-web/src/api.ts tests/test_data_provider_config.py tests/test_provider_health.py tests/test_analyst_tools.py
git commit -m "feat: surface missing provider config structurally"
```

## Task 4: Runtime Preflight Before Provider Construction

**Files:**
- Modify: `src/service/data_scheduler.py`
- Modify: `src/news_normalized/ibkr_cli.py`
- Modify: `src/prices_runtime.py`
- Test: `tests/test_data_scheduler.py`
- Test: `tests/test_normalized_ibkr_worker.py`
- Test: `tests/test_prices_runtime.py`

- [ ] **Step 0: Seed provider config in the scheduler hermetic fixture**

Update the existing autouse `hermetic()` fixture in `tests/test_data_scheduler.py`. Add dummy configured values after the `ARKSCOPE_MARKET_DB` / lock-dir setup and before provider stubs:

```python
    # S-J Phase 2 strict preflight reads the resolved runtime env before provider
    # construction. Scheduler tests stub providers/writers, so seed dummy values
    # here to exercise the configured path without touching config/.env or live
    # credentials. Tests for not_configured explicitly delenv the relevant key.
    monkeypatch.setenv("POLYGON_API_KEY", "pk_test")
    monkeypatch.setenv("FINNHUB_API_KEY", "fk_test")
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4001")
    monkeypatch.setenv("IBKR_CLIENT_ID", "1")
```

Do **not** monkeypatch `_provider_config_missing_for_source` globally; the point is to test the real preflight happy path for existing scheduler tests.

- [ ] **Step 1: Add RED scheduler test for Polygon/Finnhub strict missing**

Append to `tests/test_data_scheduler.py` near normalized news source tests:

```python
def test_run_source_provider_config_missing_returns_not_configured(monkeypatch, hermetic):
    import src.service.data_scheduler as ds
    from src.news_normalized.routing import NewsWriteMode, NewsWriteRoute

    hermetic.set_setting("use_local_news", None)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.setattr(ds, "_read_news_write_route_for_scheduler",
                        lambda: NewsWriteRoute(NewsWriteMode.NORMALIZED, "test"))
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["NVDA"])

    def _must_not_construct_provider(source):
        raise AssertionError("provider construction must be blocked by config preflight")

    monkeypatch.setattr(ds, "_make_normalized_news_provider", _must_not_construct_provider)

    out = ds.run_source("polygon_news", trigger_source="api", tickers=["NVDA"])

    assert out["status"] == "not_configured"
    assert out["code"] == "provider_config_missing"
    assert out["provider"] == "polygon"
    assert out["field"] == "api_key"
```

- [ ] **Step 2: Implement source -> provider preflight mapping**

In `src/service/data_scheduler.py`, add near source helpers:

```python
_SOURCE_PROVIDER_CONFIG = {
    "polygon_news": "polygon",
    "finnhub_news": "finnhub",
    "ibkr_news": "ibkr",
    "ibkr_prices": "ibkr",
    "price_backfill": "ibkr",
}


def _provider_config_missing_for_source(source: str) -> Optional[dict]:
    provider = _SOURCE_PROVIDER_CONFIG.get(source)
    if not provider:
        return None
    try:
        from src.data_provider_config import ProviderConfigMissing, require_provider_configured

        require_provider_configured(provider)
        return None
    except ProviderConfigMissing as exc:
        return exc.as_dict()
```

In `run_source()`, after setup-only check and before per-source locks:

```python
    missing_config = _provider_config_missing_for_source(source)
    if missing_config is not None:
        return _record_result({"source": source, **missing_config})
```

This makes not-configured a visible scheduler result without marking durable provider failure.

- [ ] **Step 3: Add worker tests proving `apply_env()` remains mandatory**

In `tests/test_prices_runtime.py`, add:

```python
def test_prices_worker_applies_provider_config_before_connect(monkeypatch):
    import src.prices_runtime as rt

    calls = []
    monkeypatch.setattr("src.data_provider_config.DataProviderConfigStore", lambda: "store")
    monkeypatch.setattr("src.data_provider_config.apply_env", lambda store: calls.append(store))
    monkeypatch.setattr(rt, "_run_worker", lambda **kwargs: {"provider": "ibkr", "tickers_scanned": 1, "gaps_found": 0, "rows_added": 0})

    assert rt.main(["--source", "ibkr_prices", "--tickers", "NVDA", "--gateway-lock-held"]) == 0
    assert calls == ["store"]
```

In `tests/test_normalized_ibkr_worker.py`, add the equivalent for `src.news_normalized.ibkr_cli.main()` if an equivalent test does not already exist. The expected assertion is:

```python
assert calls == ["store"]
```

- [ ] **Step 4: Run Task 4 tests**

Run:

```bash
pytest tests/test_data_scheduler.py tests/test_prices_runtime.py tests/test_normalized_ibkr_worker.py -q
```

Expected: PASS for the full scheduler file. This is intentional: the new preflight is cross-cutting, and a single new node-id test would miss existing `run_source(...)` tests that rely on stubbed providers.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add src/service/data_scheduler.py src/prices_runtime.py src/news_normalized/ibkr_cli.py tests/test_data_scheduler.py tests/test_prices_runtime.py tests/test_normalized_ibkr_worker.py
git commit -m "feat: preflight provider config before runtime fetch"
```

## Task 5: Settings API + UI Policy Display

**Files:**
- Modify: `src/api/routes/providers_config.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Test: `tests/test_data_provider_config.py`
- Test: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

- [ ] **Step 1: Add RED route tests for import affordance without authority**

Append to `tests/test_data_provider_config.py`:

```python
def test_strict_view_peeks_config_file_for_import_without_effective_source(store, monkeypatch, tmp_path):
    import src.env_keys as env_keys
    from src.api.routes import providers_config as pc

    env_file = tmp_path / ".env"
    env_file.write_text("POLYGON_API_KEY=pk_from_file\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)

    dpc.apply_env(store)
    row = pc.providers_config(store=store)["providers"]["polygon"]["fields"][0]

    assert row["effective_source"] == "missing"
    assert row["needs_import"] is True
    assert row["import_source"] == "POLYGON_API_KEY"
    assert "POLYGON_API_KEY" not in env_keys.keys_loaded_from_file()
    assert "POLYGON_API_KEY" not in os.environ
```

- [ ] **Step 2: Add RED route tests for fallback setting endpoint**

Append:

```python
def test_provider_env_fallback_route_sets_profile_setting(store, monkeypatch):
    from src.api.routes import providers_config as pc

    monkeypatch.setattr(pc, "require_profile_state_write", lambda *a, **k: None)
    out = pc.put_provider_env_fallback(pc.ProviderEnvFallbackUpdate(enabled=True), store=store)
    assert out["env_fallback"]["enabled"] is True
    assert out["env_fallback"]["source"] == "profile"
    assert store.get_setting("provider_env_fallback") == "true"

    out2 = pc.put_provider_env_fallback(pc.ProviderEnvFallbackUpdate(enabled=None), store=store)
    assert out2["env_fallback"]["enabled"] is False
    assert out2["env_fallback"]["source"] == "default"
    assert store.get_setting("provider_env_fallback") is None
```

- [ ] **Step 3: Implement strict-aware config view**

In `src/api/routes/providers_config.py`:

1. Import:

```python
from src.env_keys import peek_env_file_value
```

2. Add helper:

```python
def _fallback_state(store: DataProviderConfigStore) -> dict:
    from src.data_provider_config import provider_env_fallback_enabled, provider_env_fallback_source

    return {
        "enabled": provider_env_fallback_enabled(store),
        "source": provider_env_fallback_source(store),
    }
```

3. In `_view()`, replace `ensure_env_loaded()` import probing with `peek_env_file_value()`:

```python
            elif source == "missing":
                for candidate in imports:
                    if candidate and peek_env_file_value(candidate):
                        import_source = candidate
                        break
```

4. Return `env_fallback` at top level:

```python
    return {
        "providers": providers,
        "setup": provider_config_setup_state().as_dict(),
        "env_fallback": _fallback_state(store),
    }
```

5. Add model and route:

```python
class ProviderEnvFallbackUpdate(BaseModel):
    enabled: bool | None


@router.put("/providers/config/env-fallback")
def put_provider_env_fallback(
    body: ProviderEnvFallbackUpdate,
    store: DataProviderConfigStore = Depends(get_data_provider_store),
):
    require_profile_state_write("set_provider_env_fallback", {"enabled": body.enabled})
    if body.enabled is None:
        store.set_setting("provider_env_fallback", None)
    else:
        store.set_setting("provider_env_fallback", "true" if body.enabled else "false")
    apply_env(store)
    return {"env_fallback": _fallback_state(store)}
```

- [ ] **Step 4: Update `unapply_env()` caller**

In `put_provider_config()`, replace:

```python
unapply_env(by_name[field].env_var)
```

with:

```python
unapply_env(by_name[field].env_var, store)
```

- [ ] **Step 5: Update frontend DTOs**

In `apps/arkscope-web/src/api.ts`, update `ProvidersConfigResponse`:

```ts
export interface ProviderEnvFallbackState {
  enabled: boolean;
  source: "default" | "profile" | "env" | string;
}

export interface ProvidersConfigResponse {
  providers: Record<string, ProviderConfigEntry>;
  setup: ProviderConfigSetupState;
  env_fallback: ProviderEnvFallbackState;
}
```

Add:

```ts
export function putProviderEnvFallback(
  enabled: boolean | null,
): Promise<{ env_fallback: ProviderEnvFallbackState }> {
  return sendJSON("/providers/config/env-fallback", "PUT", { enabled }, 8_000);
}
```

- [ ] **Step 6: Update Settings copy and rendering**

In `apps/arkscope-web/src/Settings.tsx`:

1. Import `putProviderEnvFallback`.
2. Change the provider config copy to:

```tsx
App 管理各 provider 的金鑰與連線設定（存本地、僅顯示遮罩值）。預設嚴格模式不再用 config/.env 當 managed provider 的 runtime 來源；若 config/.env 有舊值，請逐欄匯入到 App 設定。真實環境變數仍可作 operator escape hatch。
```

3. Render a compact strict/fallback line above the config table:

```tsx
{cfgEnvFallback && (
  <p className="muted tiny">
    Provider env fallback：
    {cfgEnvFallback.enabled ? "舊 .env fallback 已啟用（rollback）" : "嚴格模式（預設）"}
    {cfgEnvFallback.source === "env" && " · 由環境變數控制"}
  </p>
)}
```

Keep rollback control guarded; if a button is added, confirm with text:

```tsx
window.confirm("啟用 legacy .env fallback 只作救援用途；managed provider 欄位將可重新從 config/.env 讀取。確定啟用？")
```

- [ ] **Step 7: Add frontend tests**

In `apps/arkscope-web/src/SettingsProviderConfig.test.ts`, update mocked config:

```ts
env_fallback: { enabled: false, source: "default" },
```

Add:

```ts
it("renders strict provider env fallback state", async () => {
  await renderDataSources();
  expect(host!.textContent).toContain("嚴格模式");
  expect(host!.textContent).not.toContain("舊 .env fallback 已啟用");
});
```

Update the status fixture for missing provider config to include:

```ts
status: "not_configured",
config_error: {
  code: "provider_config_missing",
  status: "not_configured",
  provider: "polygon",
  field: "api_key",
  env_var: "POLYGON_API_KEY",
},
```

- [ ] **Step 8: Run route and frontend tests**

Run:

```bash
pytest tests/test_data_provider_config.py -q
npm --prefix apps/arkscope-web test -- SettingsProviderConfig.test.ts
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

Run:

```bash
git add src/api/routes/providers_config.py apps/arkscope-web/src/api.ts apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts tests/test_data_provider_config.py
git commit -m "feat: expose provider strict mode in settings"
```

## Task 6: Focused Regression Gates

**Files:**
- Test only

- [ ] **Step 1: Run backend focused suite**

Run:

```bash
pytest \
  tests/test_data_provider_config.py \
  tests/test_provider_config_startup.py \
  tests/test_provider_health.py \
  tests/test_data_scheduler.py \
  tests/test_analyst_tools.py \
  tests/test_prices_runtime.py \
  tests/test_normalized_ibkr_worker.py \
  tests/test_collector_load_env.py \
  tests/test_fundamentals_sec_cache.py \
  tests/test_sec_user_agent.py \
  -q
```

Expected: PASS. `test_collector_load_env.py` may still pin standalone collector fallback for CLI use; if a failure appears, only flip sidecar/runtime expectations, not retiring-script standalone behavior.

- [ ] **Step 2: Run frontend focused suite**

Run:

```bash
npm --prefix apps/arkscope-web test -- SettingsProviderConfig.test.ts
npm --prefix apps/arkscope-web run build
```

Expected: PASS.

- [ ] **Step 3: Run stale-copy grep gate**

Run:

```bash
rg -n "real env var > app value > config/.env|real env > app DB > config/.env|falls back to config/.env|keys stay in config/.env|not found in config/.env or environment|建議匯入到 App 設定" src apps/arkscope-web/src data_sources scripts tests docs/design docs/superpowers/plans
```

Expected:

- no hit in active sidecar/runtime comments claiming fallback is default;
- allowed hits in retiring CLI/scripts or old docs only when the surrounding text says legacy/standalone;
- if a runtime error string still says `config/.env or environment`, update it to `provider is not configured in Settings or env`.

- [ ] **Step 4: Commit any focused-gate fixes**

If Step 1-3 required corrections:

```bash
git add <changed files>
git commit -m "test: align provider strict flip regressions"
```

If no corrections were needed, do not create an empty commit.

## Task 7: Live Smoke + Full A/B

**Files:**
- No code expected
- Scratch output under `scratchpad/` is allowed and must not be committed

- [ ] **Step 0: Verify the live flip precondition**

Before running any smoke, confirm the primary profile has no remaining managed fields sourced from `config/.env`:

```bash
python - <<'PY'
from src.api.routes.providers_config import providers_config
from src.data_provider_config import DataProviderConfigStore, apply_env

store = DataProviderConfigStore()
apply_env(store)
cfg = providers_config(store=store)["providers"]
rows = [
    (provider, field["field"], field["effective_source"])
    for provider, info in cfg.items()
    for field in info["fields"]
]
bad = [row for row in rows if row[2] == "config/.env"]
print({"fields": len(rows), "config_env_fields": bad})
if bad:
    raise SystemExit(1)
PY
```

Expected on the primary machine before the flip: `fields` is 8 and `config_env_fields` is `[]` (8/8 app/env/missing but not config/.env; on the reviewed machine it was 8/8 app). If any managed field still reports `config/.env`, stop and import or consciously record the exception before continuing.

- [ ] **Step 1: Record base SHA**

Run:

```bash
git rev-parse HEAD
```

Expected: record this as the S-J Phase 2 implementation SHA in review notes.

- [ ] **Step 2: Fresh-profile poison smoke**

Run a sidecar smoke with:

```bash
ARKSCOPE_PROFILE_DB=/tmp/arkscope-sj-phase2-empty-profile.db \
ARKSCOPE_DISABLE_SCHEDULER=1 \
ARKSCOPE_PROVIDER_ENV_FALLBACK=false \
python -m scripts.smoke.pg_unreachable_e2e --poison-dsn postgresql://invalid.invalid/arkscope
```

Expected:

- app starts;
- `/healthz` is ok;
- provider-config surfaces are reachable;
- no managed provider key is sourced from `config/.env`;
- missing required provider config surfaces `provider_config_missing`, not raw provider exceptions.

If `scripts.smoke.pg_unreachable_e2e` does not cover provider config endpoints yet, extend the smoke in this slice with:

```python
def _assert_provider_config_strict_missing(body):
    assert body["env_fallback"]["enabled"] is False
    assert body["providers"]["polygon"]["fields"][0]["effective_source"] == "missing"


CheckSpec(
    "provider_config_strict_missing",
    "GET",
    "/providers/config",
    200,
    _assert_provider_config_strict_missing,
)
```

- [ ] **Step 3: Rollback smoke**

Run:

```bash
ARKSCOPE_PROFILE_DB=/tmp/arkscope-sj-phase2-empty-profile.db \
ARKSCOPE_DISABLE_SCHEDULER=1 \
ARKSCOPE_PROVIDER_ENV_FALLBACK=true \
python -m scripts.smoke.pg_unreachable_e2e --poison-dsn postgresql://invalid.invalid/arkscope
```

Expected: app starts; provider-config response says `env_fallback.enabled=true` and source `env`. Do not assert that any real key exists in the report because developer machines differ.

- [ ] **Step 4: Full A/B**

Use the repo’s established virgin worktree A/B method. The acceptance rule is:

- failure sets are identical;
- head has only the expected added tests;
- any new deterministic failure blocks merge even if unrelated-looking.

Record:

```text
base SHA:
head SHA:
base passed:
head passed:
failure-set diff:
```

- [ ] **Step 5: Commit live-smoke harness changes if any**

If Step 2 required smoke script changes:

```bash
git add scripts/smoke/pg_unreachable_e2e.py tests/test_pg_unreachable_e2e.py
git commit -m "test: add provider strict smoke coverage"
```

If no harness changes were needed, do not create an empty commit.

## Task 8: Docs Closeout

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md`

- [ ] **Step 1: Update scoping doc §13.6**

Change Phase 2 status from pending to complete. Include:

```markdown
Phase 2 implementation status 2026-07-05: strict-by-default is live. Unset
`provider_env_fallback` resolves strict; explicit `true` is the documented
rollback lever; explicit `false` pins strict. FieldDefs-managed vars no longer
use `config/.env` as runtime authority by default. Real shell env remains the
operator escape hatch; `legacy_env_only` vars remain warning-only.
```

- [ ] **Step 2: Update priority map P0-D**

In `docs/design/PROJECT_PRIORITY_MAP.md`, change P0-D status to shipped and add a top §10 entry:

```markdown
- **2026-07-05 (S-J Phase 2 provider-config strict flip COMPLETE)**: FieldDefs-managed provider configuration now defaults strict (`provider_env_fallback` unset/false => no `config/.env` runtime fallback); explicit `provider_env_fallback=true` is the rollback lever. Missing required managed fields surface `provider_config_missing` across provider health, routes, scheduler, and agent tool surfaces. Fresh-profile poison smoke and full A/B passed. `config/.env` remains import/export and legacy-env-only material, not desktop provider authority.
```

- [ ] **Step 3: Mark this plan complete**

At the top of this plan, add:

```markdown
**Status:** LIVE COMPLETE 2026-07-05
```

Under it, record:

```markdown
**Verification:** focused backend suite, SettingsProviderConfig vitest/build, fresh-profile poison smoke, rollback smoke, full A/B.
```

- [ ] **Step 4: Commit docs closeout**

Run:

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/plans/2026-07-05-s-j-provider-config-strict-flip.md
git commit -m "docs: close S-J provider strict flip"
```

## Review Gates

Before merging implementation:

1. `provider_env_fallback` default is strict on a truly empty profile DB.
2. Strict mode keeps legacy env-only values available but excludes FieldDef env vars and aliases from `config/.env`.
3. Real shell env canonical vars still win over app DB.
4. Explicit fallback true restores legacy file fallback and logs a warning.
5. `provider_config_missing` appears at all committed surfaces:
   - provider health;
   - provider test route;
   - scheduler `run_source`;
   - Finnhub analyst tool.
6. SEC EDGAR remains `default_available=true`; missing optional UA does not block.
7. Worker entrypoints call `apply_env(DataProviderConfigStore())` before provider construction.
8. No new code path directly reads a managed provider key from `config/.env`.
9. Full A/B has identical failure sets.

## Known Watch Items For Review

- `ensure_env_loaded()` is global and sticky. Tests must reset `src.env_keys._loaded` and `_loaded_keys` when asserting strict import behavior.
- Polygon/Finnhub collector modules still support standalone `config/.env` fallback. That is allowed only outside the sidecar process tree; scheduler preflight is the guard.
- `SEC_CONTACT_EMAIL` and `SEC_USER_AGENT` are import aliases. Under strict, file-loaded aliases must not leak into sidecar runtime; real shell aliases are explicit operator escape.
- Provider-health must not call raw `ensure_env_loaded()` and accidentally re-load managed keys after strict `apply_env()`.
- Do not convert disabled product states into `not_configured`. Example: FRED with `macro_calendar_enabled=false` remains `disabled`, not `not_configured`.
