"""Operator history/output choices persist without authorizing acquisition."""

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from tests.test_data_source_settings import settings_client
from tests.test_financial_local_reuse import local


KEY = "data_sources.financial_read.settings"
DEFAULTS = {
    "tool_output_chars": 48000,
    "fd_periods": {
        "annual": {"income_statement": 2, "balance_sheet": 1, "cash_flow_statement": 2},
        "quarterly": {"income_statement": 4, "balance_sheet": 1, "cash_flow_statement": 4},
    },
}
ENDPOINT = "/providers/financial-read-settings"


def test_default_settings_are_visible_without_persisting_or_dispatching(settings_client, local):
    client, store = settings_client
    path = Path(os.environ["ARKSCOPE_PROFILE_DB"])
    before = sha256(path.read_bytes()).hexdigest()
    response = client.get("/providers/data-routes")
    assert response.status_code == 200
    assert "financial_read_settings" in response.json()
    view = response.json()["financial_read_settings"]
    assert view == {"values": DEFAULTS, "defaults": DEFAULTS, "setting_source": "default", "error_code": None}
    assert store.get_setting(KEY) is None
    assert sha256(path.read_bytes()).hexdigest() == before
    local[1].assert_not_called()
    local[2].assert_not_called()


@pytest.mark.parametrize("budget", [0, 120000])
def test_settings_round_trip_preserves_unlimited_and_longer_history(settings_client, local, budget):
    client, store = settings_client
    values = deepcopy(DEFAULTS)
    values["tool_output_chars"] = budget
    values["fd_periods"]["annual"]["income_statement"] = 35
    values["fd_periods"]["quarterly"]["balance_sheet"] = 24
    response = client.put(ENDPOINT, json=values)
    assert response.status_code == 200
    assert response.json()["values"] == values
    assert response.json()["setting_source"] == "profile"
    assert json.loads(store.get_setting(KEY)) == values
    assert client.get("/providers/data-routes").json()["financial_read_settings"] == response.json()
    local[1].assert_not_called()
    local[2].assert_not_called()


@pytest.mark.parametrize("change", [
    {"tool_output_chars": True}, {"tool_output_chars": -1}, {"tool_output_chars": 1.5},
    {"tool_output_chars": "48000"}, {"tool_output_chars": 2**53}, {"override_paid": True},
    {"fd_periods": {}}, {"fd_periods": {"annual": {"income_statement": 0}}},
])
def test_invalid_settings_never_overwrite_saved_values(settings_client, change):
    client, store = settings_client
    raw = json.dumps(DEFAULTS)
    store.set_setting(KEY, raw)
    response = client.put(ENDPOINT, json={**DEFAULTS, **change})
    assert response.status_code == 422
    assert store.get_setting(KEY) == raw


@pytest.mark.parametrize("value", [True, 0, -1, 1.5, "4", 2**31])
def test_fd_periods_enforce_only_positive_api_int32_values(settings_client, value):
    client, store = settings_client
    values = deepcopy(DEFAULTS)
    values["fd_periods"]["annual"]["balance_sheet"] = value
    assert client.put(ENDPOINT, json=values).status_code == 422
    assert store.get_setting(KEY) is None


def test_invalid_stored_settings_are_disclosed_and_can_be_repaired(settings_client):
    client, store = settings_client
    store.set_setting(KEY, "{")
    response = client.get("/providers/data-routes")
    assert response.status_code == 200
    assert "financial_read_settings" in response.json()
    view = response.json()["financial_read_settings"]
    assert view["values"] is None
    assert view["error_code"] == "financial_read_settings_invalid"
    assert view["defaults"] == DEFAULTS
    assert client.put(ENDPOINT, json=DEFAULTS).status_code == 200
