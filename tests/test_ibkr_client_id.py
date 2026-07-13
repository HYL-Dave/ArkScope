"""IBKR client-id partition helper — domain ids derived from the IBKR_CLIENT_ID base.

Offsets are a wire-level contract with the running Gateway (logs/diagnostics read
them); pin them exactly. options=+10 mirrors option_chain_tools' pre-existing
convention — changing it would silently re-identify live connections.
"""
import pytest

from data_sources.ibkr_client_id import DOMAIN_OFFSETS, ibkr_client_id_for


def test_domain_ids_pinned_with_default_base(monkeypatch):
    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    assert ibkr_client_id_for("manual") == 1
    assert ibkr_client_id_for("options") == 11   # matches existing base+10 convention
    assert ibkr_client_id_for("prices") == 21
    assert ibkr_client_id_for("news") == 31
    assert ibkr_client_id_for("iv") == 41        # reserved for the IV reboot line
    assert ibkr_client_id_for("quotes") == 51
    assert ibkr_client_id_for("holdings") == 61
    assert ibkr_client_id_for("portfolio_capture") == 71


def test_portfolio_capture_band_caps_base_before_legacy_100(monkeypatch):
    monkeypatch.setenv("IBKR_CLIENT_ID", "29")
    assert ibkr_client_id_for("portfolio_capture") == 99
    monkeypatch.setenv("IBKR_CLIENT_ID", "30")
    with pytest.raises(ValueError, match="0 through 29"):
        ibkr_client_id_for("portfolio_capture")
    monkeypatch.setenv("IBKR_CLIENT_ID", "-1")
    with pytest.raises(ValueError, match="0 through 29"):
        ibkr_client_id_for("portfolio_capture")


def test_base_env_respected(monkeypatch):
    monkeypatch.setenv("IBKR_CLIENT_ID", "5")
    assert ibkr_client_id_for("manual") == 5
    assert ibkr_client_id_for("prices") == 25


def test_empty_env_falls_back_to_default_base(monkeypatch):
    monkeypatch.setenv("IBKR_CLIENT_ID", "")
    assert ibkr_client_id_for("news") == 31


def test_unknown_domain_fails_loud(monkeypatch):
    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    with pytest.raises(ValueError, match="unknown IBKR client-id domain"):
        ibkr_client_id_for("orders")


def test_non_numeric_base_fails_loud(monkeypatch):
    # matches ibkr_source.py's existing int(os.getenv(...)) fail-loud behavior
    monkeypatch.setenv("IBKR_CLIENT_ID", "abc")
    with pytest.raises(ValueError, match="IBKR_CLIENT_ID"):
        ibkr_client_id_for("prices")


def test_offsets_are_distinct_and_spaced():
    values = sorted(DOMAIN_OFFSETS.values())
    assert len(set(values)) == len(values)
    assert all(b - a >= 10 for a, b in zip(values, values[1:]))
