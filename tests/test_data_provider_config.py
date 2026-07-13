"""Tests for app-managed data-provider config (store + env bridge + routes + tests)."""

from __future__ import annotations

import os

import pytest

import src.data_provider_config as dpc
from src.data_provider_config import DataProviderConfigStore


@pytest.fixture()
def store(tmp_path):
    return DataProviderConfigStore(tmp_path / "state.db")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch, tmp_path):
    """Never touch the real env keys / config/.env / app-applied tracking.
    reload_var_from_file is stubbed to "file defines nothing" — tests that care
    about the fallback override it themselves."""
    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")
    monkeypatch.setattr("src.env_keys.env_file_path", lambda: empty_env)
    monkeypatch.setattr("src.env_keys._loaded", True)
    monkeypatch.setattr("src.env_keys._loaded_keys", set())
    monkeypatch.setattr(dpc, "_APP_APPLIED", set())
    monkeypatch.setattr("src.env_keys.reload_var_from_file",
                        lambda name: (os.environ.pop(name, None), False)[1])
    for var in ("POLYGON_API_KEY", "FINNHUB_API_KEY", "FRED_API_KEY",
                "FINANCIAL_DATASETS_API_KEY", "IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID",
                "ARKSCOPE_SEC_USER_AGENT", "SEC_CONTACT_EMAIL", "SEC_USER_AGENT"):
        monkeypatch.delenv(var, raising=False)


# --- store -----------------------------------------------------------------------

def test_store_roundtrip_and_clear(store):
    store.set_field("polygon", "api_key", "pk_test_123456789")
    store.set_field("ibkr", "host", "192.168.0.153")
    assert store.get_all() == {"polygon": {"api_key": "pk_test_123456789"},
                               "ibkr": {"host": "192.168.0.153"}}
    store.set_field("polygon", "api_key", None)   # clear
    assert "polygon" not in store.get_all()


def test_store_rejects_unknown_field(store):
    with pytest.raises(KeyError):
        store.set_field("polygon", "host", "x")   # polygon has no host field
    with pytest.raises(KeyError):
        store.set_field("nope", "api_key", "x")


# --- env bridge --------------------------------------------------------------------

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


def test_env_file_peek_reads_without_mutating_process(monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text(
        "POLYGON_API_KEY='pk_file'\nALPHA_VANTAGE_API_KEY=av_file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)

    assert env_keys.peek_env_file_value("POLYGON_API_KEY") == "pk_file"
    assert "POLYGON_API_KEY" not in os.environ
    assert "POLYGON_API_KEY" not in env_keys.keys_loaded_from_file()


def test_env_loader_excludes_managed_key_but_loads_legacy_key(monkeypatch, tmp_path):
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text(
        "POLYGON_API_KEY=pk_file\nALPHA_VANTAGE_API_KEY=av_file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.setattr(env_keys, "_loaded", False)
    monkeypatch.setattr(env_keys, "_loaded_keys", set())
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    env_keys.ensure_env_loaded_excluding({"POLYGON_API_KEY"})

    assert "POLYGON_API_KEY" not in os.environ
    assert os.environ["ALPHA_VANTAGE_API_KEY"] == "av_file"
    assert env_keys.keys_loaded_from_file() == frozenset({"ALPHA_VANTAGE_API_KEY"})


def test_apply_env_injects_and_tracks(store):
    store.set_field("polygon", "api_key", "pk_app")
    store.set_field("ibkr", "host", "10.0.0.5")
    store.set_field("ibkr", "port", "4001")
    applied = dpc.apply_env(store)
    assert os.environ["POLYGON_API_KEY"] == "pk_app"
    assert os.environ["IBKR_HOST"] == "10.0.0.5" and os.environ["IBKR_PORT"] == "4001"
    assert {"POLYGON_API_KEY", "IBKR_HOST", "IBKR_PORT"} <= set(applied)
    assert dpc.effective_source("POLYGON_API_KEY") == "app"


def test_real_env_var_wins_over_app(store, monkeypatch):
    # operator escape hatch: a REAL env var (not file-loaded, not app-applied)
    # is never overwritten by the app store.
    monkeypatch.setenv("POLYGON_API_KEY", "pk_real_operator")
    store.set_field("polygon", "api_key", "pk_app")
    dpc.apply_env(store)
    assert os.environ["POLYGON_API_KEY"] == "pk_real_operator"
    assert dpc.effective_source("POLYGON_API_KEY") == "env"


def test_app_overrides_file_loaded_value(store, monkeypatch):
    # a config/.env-loaded value is superseded by the app value (entering a key
    # in Settings must actually take effect).
    monkeypatch.setenv("FINNHUB_API_KEY", "fk_from_file")
    monkeypatch.setattr("src.env_keys._loaded_keys", {"FINNHUB_API_KEY"})
    store.set_field("finnhub", "api_key", "fk_app")
    dpc.apply_env(store)
    assert os.environ["FINNHUB_API_KEY"] == "fk_app"
    assert dpc.effective_source("FINNHUB_API_KEY") == "app"


def test_apply_env_strict_excludes_managed_file_key_but_keeps_legacy_env_only(
    store, monkeypatch, tmp_path
):
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
    assert "SEC_CONTACT_EMAIL" not in os.environ
    assert os.environ["ALPHA_VANTAGE_API_KEY"] == "av_file"
    assert dpc.effective_source("POLYGON_API_KEY") == "missing"


def test_apply_env_strict_db_value_wins_without_file_source_tracking(
    store, monkeypatch, tmp_path
):
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


def test_apply_env_explicit_fallback_true_restores_legacy_file_fallback(
    store, monkeypatch, tmp_path
):
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
    calls.clear()
    dpc.unapply_env("FINNHUB_API_KEY", store)
    assert calls == ["FINNHUB_API_KEY"]
    assert os.environ["FINNHUB_API_KEY"] == "fk_from_file_again"


# --- IBKR client id (Slice A: was env-only @ ibkr_source.py:277, now app-managed) -----

def test_ibkr_client_id_field_defined():
    fields = {f.field: f for f in dpc.PROVIDER_FIELDS["ibkr"]}
    assert "client_id" in fields, "IBKR client id must be app-managed, not env-only"
    cid = fields["client_id"]
    assert cid.env_var == "IBKR_CLIENT_ID"   # the var ibkr_source.py:277 actually reads
    assert cid.secret is False               # an id, not a secret → shown raw


def test_ibkr_client_id_injected_by_bridge(store):
    store.set_field("ibkr", "client_id", "7")
    dpc.apply_env(store)
    assert os.environ["IBKR_CLIENT_ID"] == "7"   # reaches IBKRDataSource via the env bridge
    assert dpc.effective_source("IBKR_CLIENT_ID") == "app"


def test_ibkr_client_id_in_route_view(store):
    from src.api.routes import providers_config as pc
    view = pc.providers_config(store=store)["providers"]
    row = next(f for f in view["ibkr"]["fields"] if f["field"] == "client_id")
    assert row["env_var"] == "IBKR_CLIENT_ID" and row["secret"] is False


def test_sec_edgar_user_agent_field_defined():
    fields = {f.field: f for f in dpc.PROVIDER_FIELDS["sec_edgar"]}
    assert "user_agent" in fields
    f = fields["user_agent"]
    assert f.env_var == "ARKSCOPE_SEC_USER_AGENT"
    assert f.label == "聯絡 Email"
    assert f.secret is False
    assert f.optional is True
    assert f.import_aliases == ("SEC_CONTACT_EMAIL", "SEC_USER_AGENT")


def test_sec_edgar_user_agent_optional_keeps_provider_default_available(store):
    from src.api.routes import providers_config as pc

    view = pc.providers_config(store=store)["providers"]
    assert view["sec_edgar"]["default_available"] is True
    row = next(f for f in view["sec_edgar"]["fields"] if f["field"] == "user_agent")
    assert row["effective_source"] == "missing"


def test_apply_env_seeds_ibkr_client_id_default(store):
    assert store.get_all() == {}
    dpc.apply_env(store)
    stored = store.get_all()
    assert stored["ibkr"]["client_id"] == "1"
    assert os.environ["IBKR_CLIENT_ID"] == "1"
    assert dpc.effective_source("IBKR_CLIENT_ID") == "app"


# --- structured missing config -----------------------------------------------------

def test_required_provider_missing_detail_uses_machine_contract():
    detail = dpc.provider_config_missing_detail("polygon", "api_key")
    assert detail == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "polygon",
        "field": "api_key",
    }


def test_missing_required_provider_fields_ignores_optional_sec_user_agent():
    assert dpc.missing_required_provider_fields("sec_edgar") == []
    missing = dpc.missing_required_provider_fields("polygon")
    assert missing == [dpc.provider_config_missing_detail("polygon", "api_key")]


def test_provider_test_missing_required_config_returns_structured_detail(store):
    from fastapi import HTTPException
    from src.api.routes import providers_config as pc

    with pytest.raises(HTTPException) as e:
        pc.test_provider("polygon", store=store)

    assert e.value.status_code == 409
    assert e.value.detail == {
        "code": "provider_config_missing",
        "status": "not_configured",
        "provider": "polygon",
        "field": "api_key",
    }


# --- connection tests ----------------------------------------------------------------

def test_ibkr_test_socket(monkeypatch):
    monkeypatch.setenv("IBKR_HOST", "127.0.0.1")
    monkeypatch.setenv("IBKR_PORT", "4001")

    class _Sock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(dpc.socket, "create_connection", lambda addr, timeout: _Sock())
    out = dpc.run_connection_test("ibkr")
    assert out["ok"] is True and "4001" in out["detail"]

    monkeypatch.setattr(dpc.socket, "create_connection",
                        lambda addr, timeout: (_ for _ in ()).throw(OSError("refused")))
    out = dpc.run_connection_test("ibkr")
    assert out["ok"] is False and "refused" in out["detail"]


def test_ibkr_test_requires_host_port():
    assert dpc.run_connection_test("ibkr")["ok"] is False  # nothing configured


def test_key_provider_test_paths(monkeypatch):
    out = dpc.run_connection_test("polygon")          # no key
    assert out["ok"] is False and "缺" in out["detail"]

    monkeypatch.setenv("POLYGON_API_KEY", "k")

    class _Resp:
        status_code = 200

    monkeypatch.setattr("requests.get", lambda url, headers=None, timeout=None: _Resp())
    out = dpc.run_connection_test("polygon")
    assert out["ok"] is True and out["latency_ms"] is not None

    _Resp.status_code = 401
    out = dpc.run_connection_test("polygon")
    assert out["ok"] is False and "金鑰" in out["detail"]


def test_paid_and_extension_have_no_live_test():
    fd = dpc.run_connection_test("financial_datasets")
    assert fd["ok"] is None and "metered" in fd["detail"]
    sa = dpc.run_connection_test("seeking_alpha")
    assert sa["ok"] is None


# --- routes ---------------------------------------------------------------------------

def test_routes_masked_view_and_put(store, monkeypatch):
    from src.api.routes import providers_config as pc

    view = pc.providers_config(store=store)["providers"]
    assert view["sec_edgar"]["default_available"] is True       # 免金鑰預設可用
    assert view["seeking_alpha"]["default_available"] is False  # extension path
    assert view["financial_datasets"]["testable"] is False
    assert view["ibkr"]["testable"] is True

    out = pc.put_provider_config(
        "polygon", pc.ProviderConfigUpdate(fields={"api_key": "pk_secret_ABCDEFGH"}),
        store=store)
    row = out["fields"][0]
    assert row["app_value_set"] is True
    assert row["app_value_masked"] == "pk_s…EFGH"               # masked, never raw
    assert "pk_secret" not in str(out).replace("pk_s…", "")     # raw value not leaked
    assert row["effective_source"] == "app"
    assert os.environ["POLYGON_API_KEY"] == "pk_secret_ABCDEFGH"  # bridge applied

    # clear → falls back (no file value in hermetic env → missing)
    out = pc.put_provider_config(
        "polygon", pc.ProviderConfigUpdate(fields={"api_key": None}), store=store)
    assert out["fields"][0]["app_value_set"] is False
    assert out["fields"][0]["effective_source"] == "missing"


def test_routes_validation(store):
    from fastapi import HTTPException

    from src.api.routes import providers_config as pc

    with pytest.raises(HTTPException) as e:
        pc.put_provider_config("nope", pc.ProviderConfigUpdate(fields={}), store=store)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        pc.put_provider_config("sec_edgar", pc.ProviderConfigUpdate(fields={"api_key": "x"}),
                               store=store)
    assert e.value.status_code == 400      # unknown field for this provider
    with pytest.raises(HTTPException) as e:
        pc.put_provider_config("polygon",
                               pc.ProviderConfigUpdate(fields={"host": "x"}), store=store)
    assert e.value.status_code == 400      # unknown field for this provider


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


def test_strict_view_peeks_config_file_for_import_without_effective_source(
    store, monkeypatch, tmp_path
):
    from src.api.routes import providers_config as pc
    import src.env_keys as env_keys

    env_file = tmp_path / ".env"
    env_file.write_text("SEC_CONTACT_EMAIL=ops@example.com\n", encoding="utf-8")
    monkeypatch.setattr(env_keys, "env_file_path", lambda: env_file)
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("ARKSCOPE_SEC_USER_AGENT", raising=False)

    view = pc.providers_config(store=store)

    row = next(f for f in view["providers"]["sec_edgar"]["fields"] if f["field"] == "user_agent")
    assert row["effective_source"] == "missing"
    assert row["needs_import"] is True
    assert row["import_source"] == "SEC_CONTACT_EMAIL"
    assert "SEC_CONTACT_EMAIL" not in os.environ


def test_provider_env_fallback_route_sets_profile_setting(store):
    from src.api.routes import providers_config as pc

    out = pc.put_provider_env_fallback(
        pc.ProviderEnvFallbackUpdate(enabled=True),
        store=store,
    )
    assert out == {"enabled": True, "source": "profile"}
    assert store.get_setting("provider_env_fallback") == "true"

    out = pc.put_provider_env_fallback(
        pc.ProviderEnvFallbackUpdate(enabled=False),
        store=store,
    )
    assert out == {"enabled": False, "source": "profile"}
    assert store.get_setting("provider_env_fallback") == "false"


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


def test_sec_user_agent_put_normalizes_bare_email(store):
    from src.api.routes import providers_config as pc

    out = pc.put_provider_config(
        "sec_edgar",
        pc.ProviderConfigUpdate(fields={"user_agent": "ops@example.com"}),
        store=store,
    )
    assert store.get_all()["sec_edgar"]["user_agent"] == "ArkScope ops@example.com"
    row = next(f for f in out["fields"] if f["field"] == "user_agent")
    assert row["label"] == "聯絡 Email"
    assert row["app_value_masked"] == "ArkScope ops@example.com"
    assert os.environ["ARKSCOPE_SEC_USER_AGENT"] == "ArkScope ops@example.com"


def test_sec_user_agent_put_preserves_full_user_agent(store):
    from src.api.routes import providers_config as pc

    value = "ArkScope Research ops@example.com"
    out = pc.put_provider_config(
        "sec_edgar",
        pc.ProviderConfigUpdate(fields={"user_agent": value}),
        store=store,
    )
    assert store.get_all()["sec_edgar"]["user_agent"] == value
    row = next(f for f in out["fields"] if f["field"] == "user_agent")
    assert row["app_value_masked"] == value
    assert os.environ["ARKSCOPE_SEC_USER_AGENT"] == value


def test_sec_user_agent_import_preserves_full_user_agent(store, monkeypatch):
    from src.api.routes import providers_config as pc

    value = "ArkScope Research ops@example.com"
    monkeypatch.setenv("SEC_USER_AGENT", value)
    out = pc.import_provider_config_field(
        "sec_edgar",
        "user_agent",
        pc.ProviderConfigImportEnv(source_env_var="SEC_USER_AGENT"),
        store=store,
    )
    assert store.get_all()["sec_edgar"]["user_agent"] == value
    row = next(f for f in out["fields"] if f["field"] == "user_agent")
    assert row["app_value_masked"] == value


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


def test_ibkr_client_id_save_rejects_non_numeric(store):
    from fastapi import HTTPException

    from src.api.routes import providers_config as pc

    dpc.apply_env(store)  # seeds ibkr.client_id=1
    with pytest.raises(HTTPException) as e:
        pc.put_provider_config(
            "ibkr",
            pc.ProviderConfigUpdate(
                fields={"client_id": "abc"}, confirm_guarded={"client_id": True}
            ),
            store=store,
        )
    assert e.value.status_code == 400
    assert e.value.detail["code"] == "provider_config_invalid_value"
    assert os.environ["IBKR_CLIENT_ID"] == "1"  # bad base never persisted/injected


def test_normalize_rejects_non_numeric_ibkr_client_id():
    cid = next(
        f for f in dpc.PROVIDER_FIELDS["ibkr"] if f.env_var == "IBKR_CLIENT_ID"
    )
    with pytest.raises(ValueError):
        dpc.normalize_provider_config_value(cid, "abc")
    with pytest.raises(ValueError):
        dpc.normalize_import_value(cid, "IBKR_CLIENT", "-5")
    with pytest.raises(ValueError, match="0 through 29"):
        dpc.normalize_provider_config_value(cid, "30")
    with pytest.raises(ValueError):
        dpc.normalize_provider_config_value(cid, "-1")
    with pytest.raises(ValueError):
        # '²'.isdigit() is True but int() rejects it — the validator must too
        dpc.normalize_provider_config_value(cid, "²")
    with pytest.raises(ValueError):
        # Gateway client ids are int32; leave headroom for the +40 offset
        dpc.normalize_provider_config_value(cid, str(2**31))
    assert dpc.normalize_provider_config_value(cid, " 7 ") == "7"
    assert dpc.normalize_provider_config_value(cid, "００７") == "7"  # canonicalized ASCII


def test_multi_field_put_is_atomic_on_invalid_value(store):
    from fastapi import HTTPException

    from src.api.routes import providers_config as pc

    dpc.apply_env(store)
    with pytest.raises(HTTPException) as e:
        pc.put_provider_config(
            "ibkr",
            pc.ProviderConfigUpdate(
                fields={"host": "10.0.0.9", "client_id": "abc"},
                confirm_guarded={"client_id": True},
            ),
            store=store,
        )
    assert e.value.status_code == 400
    # the earlier valid field must NOT have been persisted (validate-all-first)
    assert (store.get_all().get("ibkr") or {}).get("host") is None


def test_import_env_rejects_non_numeric_client_id(store, monkeypatch):
    from fastapi import HTTPException

    from src.api.routes import providers_config as pc

    dpc.apply_env(store)
    monkeypatch.setenv("IBKR_CLIENT_ID", "abc")  # real-env override of the injected base
    with pytest.raises(HTTPException) as e:
        pc.import_provider_config_field(
            "ibkr",
            "client_id",
            pc.ProviderConfigImportEnv(confirm_guarded=True),
            store=store,
        )
    assert e.value.status_code == 400
    assert e.value.detail["code"] == "provider_config_invalid_value"


def test_view_exposes_client_id_domains(store, monkeypatch):
    from src.api.routes import providers_config as pc

    dpc.apply_env(store)  # seeds base "1" and injects env
    row = next(
        f for f in pc._view(store)["providers"]["ibkr"]["fields"]
        if f["field"] == "client_id"
    )
    doms = row["client_id_domains"]
    assert [d["domain"] for d in doms] == [
        "manual", "options", "prices", "news", "iv", "quotes", "holdings",
        "portfolio_capture",
    ]
    assert [d["offset"] for d in doms] == [0, 10, 20, 30, 40, 50, 60, 70]
    assert [d["effective_id"] for d in doms] == [1, 11, 21, 31, 41, 51, 61, 71]
    assert doms[2]["label"] == "股價"
    assert doms[-1]["label"] == "持倉擷取"
    assert "quotes=+50" in row["guard_reason"]
    assert "holdings=+60" in row["guard_reason"]
    assert "portfolio_capture=+70" in row["guard_reason"]
    assert "base <= 29" in row["guard_reason"]

    # a real-env override wins precedence — effective ids must reflect it
    monkeypatch.setenv("IBKR_CLIENT_ID", "7")
    doms = next(
        f for f in pc._view(store)["providers"]["ibkr"]["fields"]
        if f["field"] == "client_id"
    )["client_id_domains"]
    assert [d["effective_id"] for d in doms] == [7, 17, 27, 37, 47, 57, 67, 77]

    # unparsable env base → ids unknown, list still present (UI shows placeholders)
    monkeypatch.setenv("IBKR_CLIENT_ID", "abc")
    doms = next(
        f for f in pc._view(store)["providers"]["ibkr"]["fields"]
        if f["field"] == "client_id"
    )["client_id_domains"]
    assert all(d["effective_id"] is None for d in doms)

    # only the client-id field carries the key
    host = next(
        f for f in pc._view(store)["providers"]["ibkr"]["fields"]
        if f["field"] == "host"
    )
    assert "client_id_domains" not in host
