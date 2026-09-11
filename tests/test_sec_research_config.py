"""SEC capture-budget ownership and persistence contracts."""

import sqlite3
from pathlib import Path

import pytest

from src.profile_state import ProfileStateStore


ROOT = Path(__file__).resolve().parents[1]
KEY = "sec_research.capture_budget_bytes"


@pytest.mark.parametrize("name", ["__init__.py", "config.py"])
def test_sec_configuration_owner_exists(name):
    assert (ROOT / "src" / "sec_research" / name).is_file()


def _config():
    assert (ROOT / "src" / "sec_research" / "config.py").is_file()
    from src.sec_research import config

    return config


@pytest.fixture
def profile(tmp_path):
    return ProfileStateStore(tmp_path / "profile" / "state.db")


def _settings_rows(profile):
    with sqlite3.connect(profile.db_path) as conn:
        return conn.execute(
            "SELECT key, value, updated_at FROM profile_settings ORDER BY key"
        ).fetchall()


def test_budget_defaults_only_when_the_key_is_absent(profile):
    config = _config()
    assert config.get_capture_budget_bytes(profile) == 107374182400
    assert profile.get_settings_snapshot([KEY]) == {}
    assert _settings_rows(profile) == []
    profile.set_setting(KEY, None)
    before = _settings_rows(profile)
    with pytest.raises(ValueError):
        config.get_capture_budget_bytes(profile)
    assert _settings_rows(profile) == before


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("1", 1),
        ("107374182399", 107374182399),
        ("107374182400", 107374182400),
        ("214748364800", 214748364800),
        ("9007199254740989", 9007199254740989),
        ("9007199254740991", 9007199254740991),
    ],
    ids=["minimum", "below-default", "default", "above-default", "large-odd", "maximum"],
)
def test_budget_reads_exact_canonical_integers_without_writes(profile, stored, expected):
    config = _config()
    profile.set_setting(KEY, stored)
    before = _settings_rows(profile)
    result = config.get_capture_budget_bytes(profile)
    assert type(result) is int
    assert result == expected
    assert _settings_rows(profile) == before


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param("", id="empty"),
        pytest.param("0", id="zero"),
        pytest.param("-1", id="negative"),
        pytest.param("+1", id="plus"),
        pytest.param("01", id="leading-zero"),
        pytest.param(" 1", id="leading-space"),
        pytest.param("1 ", id="trailing-space"),
        pytest.param("1\n", id="newline"),
        pytest.param("1\x00", id="nul"),
        pytest.param("1.0", id="whole-float"),
        pytest.param("1.5", id="fraction"),
        pytest.param("1e3", id="exponent"),
        pytest.param("NaN", id="nan"),
        pytest.param("Infinity", id="infinity"),
        pytest.param("-inf", id="negative-infinity"),
        pytest.param("true", id="true-text"),
        pytest.param("false", id="false-text"),
        pytest.param("NULL", id="null-text"),
        pytest.param("1_024", id="underscore"),
        pytest.param("0x400", id="hex"),
        pytest.param("\u0661", id="unicode-digit"),
        pytest.param("\uff11", id="fullwidth-digit"),
        pytest.param("9007199254740992", id="overflow"),
        pytest.param("9" * 5000, id="huge-overflow"),
        pytest.param(b"1", id="blob"),
    ],
)
def test_budget_rejects_corrupt_persisted_values_without_repair(profile, stored):
    config = _config()
    profile.set_setting(KEY, stored)
    before = _settings_rows(profile)
    with pytest.raises(ValueError):
        config.get_capture_budget_bytes(profile)
    assert _settings_rows(profile) == before


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param(True, id="bool-true"),
        pytest.param(False, id="bool-false"),
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative"),
        pytest.param(1.0, id="whole-float"),
        pytest.param(1.5, id="fraction"),
        pytest.param(107374182400.0, id="default-float"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param("1", id="numeric-text"),
        pytest.param(b"1", id="bytes"),
        pytest.param([], id="list"),
        pytest.param({}, id="dict"),
        pytest.param(9007199254740992, id="overflow"),
        pytest.param(10**200, id="huge-overflow"),
    ],
)
def test_budget_setter_rejects_invalid_values_before_writing(profile, value):
    config = _config()
    profile.set_setting(KEY, "4096")
    before = _settings_rows(profile)
    with pytest.raises(ValueError):
        config.set_capture_budget_bytes(profile, value)
    assert _settings_rows(profile) == before


def test_rejected_budget_does_not_create_an_absent_setting(profile):
    config = _config()
    with pytest.raises(ValueError):
        config.set_capture_budget_bytes(profile, True)
    assert _settings_rows(profile) == []


def test_budget_changes_persist_exact_text_and_leave_other_settings_untouched(profile):
    config = _config()
    profile.update_settings(
        {
            "security_lifecycle.automation.enabled": "false",
            "security_lifecycle.automation.interval_minutes": "5",
            "use_local_market": "true",
            "default_watchlist_id": None,
        }
    )
    with sqlite3.connect(profile.db_path) as conn:
        conn.execute("UPDATE profile_settings SET updated_at = '2001-01-01T00:00:00Z'")
        schema_before = conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall()
    unrelated_before = _settings_rows(profile)

    for value, text in [
        (107374182400, "107374182400"),
        (214748364800, "214748364800"),
        (9007199254740991, "9007199254740991"),
        (9007199254740989, "9007199254740989"),
        (1, "1"),
    ]:
        result = config.set_capture_budget_bytes(profile, value)
        assert type(result) is int
        assert result == value
        assert profile.get_settings_snapshot([KEY]) == {KEY: text}
        assert config.get_capture_budget_bytes(profile) == value
        assert [row for row in _settings_rows(profile) if row[0] != KEY] == unrelated_before

    with sqlite3.connect(profile.db_path) as conn:
        assert conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
        ).fetchall() == schema_before
    reopened = ProfileStateStore(profile.db_path)
    assert config.get_capture_budget_bytes(reopened) == 1


def test_budget_accessors_do_not_create_market_or_capture_files(profile, tmp_path, monkeypatch):
    config = _config()
    market = tmp_path / "uncreated" / "market.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market))
    assert config.get_capture_budget_bytes(profile) == 107374182400
    assert config.set_capture_budget_bytes(profile, 214748364800) == 214748364800
    assert not market.parent.exists()
