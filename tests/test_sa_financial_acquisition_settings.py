"""Financial error policy is profile-owned, local and independently recoverable."""

import json
import sqlite3
from unittest.mock import Mock

from fastapi import HTTPException
import pytest

from src.api.routes import seeking_alpha
from src.data_provider_config import DataProviderConfigStore
from src.sa_native_host import handle_message
from tests.test_sa_article_acquisition_routes import client
from tests.test_sa_company_collector import FIREFOX


ENDPOINT = "/sa/financial-acquisition-settings"
KEY = "data_sources.sa_financial_acquisition.settings"
DEFAULTS = {"parser_failure_ticker_threshold": 3}


def test_default_read_does_not_create_database_or_run_capture(client, tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.Popen", Mock(side_effect=AssertionError("not local")))
    before = set(tmp_path.iterdir())
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    assert response.json() == {"values": DEFAULTS, "defaults": DEFAULTS, "setting_source": "default", "error_code": None}
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("threshold", [0, 1, 2, 5, 2**53 - 1])
def test_policy_roundtrip_reaches_native_reader_without_queue_or_owner_change(client, tmp_path, threshold):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    store.set_setting("unrelated", "retained")
    control_before = handle_message({"action": "sa_acquisition_control", "operation": "status", "client": FIREFOX})
    values = {"parser_failure_ticker_threshold": threshold}
    response = client.put(ENDPOINT, json=values)
    assert response.status_code == 200
    assert response.json()["values"] == values
    assert client.get(ENDPOINT).json() == response.json()
    native = handle_message({"action": "sa_acquisition_control", "operation": "status", "client": FIREFOX})
    assert native["financial_settings"]["values"] == values
    assert {k: v for k, v in native.items() if k != "financial_settings"} == {k: v for k, v in control_before.items() if k != "financial_settings"}
    assert store.get_setting("unrelated") == "retained"
    assert not (tmp_path / "sa_company_refresh.db").exists()


@pytest.mark.parametrize("change", [{"parser_failure_ticker_threshold": -1}, {"parser_failure_ticker_threshold": True},
    {"parser_failure_ticker_threshold": "3"}, {"parser_failure_ticker_threshold": 1.5},
    {"parser_failure_ticker_threshold": 2**53}, {"extra": 2}])
def test_invalid_policy_write_preserves_saved_value(client, tmp_path, change):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    raw = json.dumps(DEFAULTS)
    store.set_setting(KEY, raw)
    assert client.put(ENDPOINT, json={**DEFAULTS, **change}).status_code == 422
    assert store.get_setting(KEY) == raw


def test_unreadable_policy_is_not_default_and_does_not_pause_routine_collection(client, tmp_path):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    store.set_setting(KEY, "{")
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    assert response.json()["values"] is None
    assert response.json()["error_code"] == "sa_financial_settings_invalid"
    native = handle_message({"action": "sa_acquisition_control", "operation": "status", "client": FIREFOX})
    assert native["status"] == "ok"
    assert native["paused_reason"] is None
    assert native["financial_settings"]["error_code"] == "sa_financial_settings_invalid"
    with sqlite3.connect(tmp_path / "profile.db") as db:
        db.execute("DROP TABLE profile_settings")
    assert client.get(ENDPOINT).status_code == 503
    native = handle_message({"action": "sa_acquisition_control", "operation": "status", "client": FIREFOX})
    assert native["status"] == "ok"
    assert native["financial_settings"]["values"] is None


def test_write_requires_profile_permission(client, tmp_path, monkeypatch):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    monkeypatch.setattr(seeking_alpha, "require_profile_state_write", Mock(side_effect=HTTPException(403, "blocked")))
    assert client.put(ENDPOINT, json=DEFAULTS).status_code == 403
    assert store.get_setting(KEY) is None
