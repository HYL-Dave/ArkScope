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
def hermetic(monkeypatch):
    """Never touch the real env keys / config/.env / app-applied tracking.
    reload_var_from_file is stubbed to "file defines nothing" — tests that care
    about the fallback override it themselves."""
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


def test_unapply_falls_back_to_file(store, monkeypatch):
    calls = []

    def _reload(name):
        calls.append(name)
        os.environ[name] = "fk_from_file_again"
        return True

    monkeypatch.setattr("src.env_keys.reload_var_from_file", _reload)
    store.set_field("finnhub", "api_key", "fk_app")
    dpc.apply_env(store)
    assert os.environ["FINNHUB_API_KEY"] == "fk_app"
    dpc.unapply_env("FINNHUB_API_KEY")
    assert calls == ["FINNHUB_API_KEY"]
    assert os.environ["FINNHUB_API_KEY"] == "fk_from_file_again"
    assert dpc.effective_source("FINNHUB_API_KEY") != "app"


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
