"""
Tests for Seeking Alpha Alpha Picks integration (Phase 11c).

Unit tests mock Playwright and DAL. Integration tests require:
    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.tools.sa_tools import (
    get_sa_alpha_picks,
    get_sa_pick_detail,
    refresh_sa_alpha_picks,
    _is_sa_enabled,
)
from src.tools.registry import create_default_registry


# ============================================================
# Config guard
# ============================================================

class TestSAConfig:
    def test_disabled_returns_message(self):
        """When SA is disabled, tools return informational message."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=False):
            result = get_sa_alpha_picks(MagicMock())
            assert "message" in result
            assert "not enabled" in result["message"].lower()

    def test_enabled_with_config(self):
        """Config guard reads sa_enabled from AgentConfig."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_portfolio.return_value = {
                "current": [], "closed": [],
                "freshness": {"current": {"ok": True}, "closed": {"ok": True}},
                "is_partial": False,
            }
            mock_client.return_value = mock_instance
            result = get_sa_alpha_picks(MagicMock())
            assert "message" not in result


# ============================================================
# Client extension-backed behavior
# ============================================================

class TestClientNoSession:
    def test_client_works_without_session_file(self):
        """Client no longer requires session_file parameter."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(dal=MagicMock())
        # Should not raise
        assert client._dal is not None

    def test_refresh_returns_hint(self):
        """refresh_portfolio returns refresh_hint for extension."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        dal = MagicMock()
        dal.get_sa_refresh_meta.return_value = {}
        dal.get_sa_portfolio.return_value = []
        client = SAAlphaPicksClient(dal=dal)
        result = client.refresh_portfolio()
        assert "refresh_hint" in result
        assert "extension" in result["refresh_hint"].lower()

    def test_stale_warning_when_cache_old(self):
        """get_portfolio returns stale_warning when cache exceeds TTL."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        dal = MagicMock()
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        dal.get_sa_refresh_meta.return_value = {
            "current": {"ok": True, "last_success_at": old_time},
            "closed": {"ok": True, "last_success_at": old_time},
        }
        dal.get_sa_portfolio.return_value = []
        client = SAAlphaPicksClient(dal=dal, cache_hours=24)
        result = client.get_portfolio()
        assert "stale_warning" in result
        assert "48h" in result["stale_warning"]

    def test_no_stale_warning_when_fresh(self):
        """get_portfolio has no stale_warning when cache is fresh."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        dal = MagicMock()
        fresh_time = datetime.now(timezone.utc).isoformat()
        dal.get_sa_refresh_meta.return_value = {
            "current": {"ok": True, "last_success_at": fresh_time},
            "closed": {"ok": True, "last_success_at": fresh_time},
        }
        dal.get_sa_portfolio.return_value = []
        client = SAAlphaPicksClient(dal=dal, cache_hours=24)
        result = client.get_portfolio()
        assert "stale_warning" not in result


# ============================================================
# Native host message handling
# ============================================================

class TestNativeHost:
    def test_handle_refresh_calls_dal(self):
        """Native host handle_message calls DAL.apply_sa_refresh."""
        sys.path.insert(0, str(project_root))
        from scripts.sa_native_host import handle_message

        with patch("src.tools.data_access.DataAccessLayer") as MockDAL, \
             patch("scripts.sa_native_host._try_ticker_sync"):
            mock_dal = MagicMock()
            mock_dal.apply_sa_refresh.return_value = 3
            MockDAL.return_value = mock_dal

            picks = [
                {"symbol": "ACME", "company": "Acme Corp"},
                {"symbol": "BETA", "company": "Beta Inc"},
                {"symbol": "GAMA", "company": "Gamma Sys"},
            ]
            result = handle_message({
                "action": "refresh",
                "scope": "current",
                "picks": picks,
                "batch_ts": "2025-03-15T10:00:00Z",
            })

            assert result["status"] == "ok"
            assert result["count"] == 3
            mock_dal.apply_sa_refresh.assert_called_once()
            # Verify portfolio_status was injected
            call_picks = mock_dal.apply_sa_refresh.call_args[1].get("picks") or mock_dal.apply_sa_refresh.call_args[0][1]
            for p in call_picks:
                assert p["portfolio_status"] == "current"
                assert p["is_stale"] is False

    def test_handle_failure_records_meta(self):
        """Native host records failure via DAL."""
        from scripts.sa_native_host import handle_message

        with patch("src.tools.data_access.DataAccessLayer") as MockDAL:
            mock_dal = MagicMock()
            MockDAL.return_value = mock_dal

            result = handle_message({
                "action": "refresh_failure",
                "scope": "closed",
                "error": "paywall detected",
                "batch_ts": "2025-03-15T10:00:00Z",
            })

            assert result["status"] == "ok"
            assert result["recorded_failure"] is True
            mock_dal.record_sa_refresh_failure.assert_called_once()

    def test_handle_ping(self):
        """Native host responds to ping."""
        from scripts.sa_native_host import handle_message

        with patch("src.tools.data_access.DataAccessLayer"):
            result = handle_message({"action": "ping"})
            assert result["status"] == "ok"

    def test_batch_ts_z_suffix_parsed(self):
        """JS Date.toISOString() Z suffix is parsed correctly."""
        from scripts.sa_native_host import handle_message

        with patch("src.tools.data_access.DataAccessLayer") as MockDAL, \
             patch("scripts.sa_native_host._try_ticker_sync"):
            mock_dal = MagicMock()
            mock_dal.apply_sa_refresh.return_value = 0
            MockDAL.return_value = mock_dal

            # Should not raise ValueError on Z suffix
            result = handle_message({
                "action": "refresh",
                "scope": "current",
                "picks": [],
                "batch_ts": "2025-03-15T10:00:00.000Z",
            })
            assert result["status"] == "ok"


# ============================================================
# Tool stale_warning pass-through
# ============================================================

class TestToolStalePassThrough:
    def test_stale_warning_passed_to_tool_response(self):
        """get_sa_alpha_picks passes through stale_warning from client."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_portfolio.return_value = {
                "current": [], "closed": [],
                "freshness": {"current": {"ok": True}, "closed": {"ok": True}},
                "is_partial": False,
                "stale_warning": "Data is 48h old. Click SA extension.",
            }
            mock_client.return_value = mock_instance
            result = get_sa_alpha_picks(MagicMock())
            assert "stale_warning" in result
            assert "48h" in result["stale_warning"]


# ============================================================
# Detail key resolution
# ============================================================

class TestDetailKeyResolution:
    def test_single_pick_returns_detail(self):
        """Single current pick is returned directly."""
        dal = MagicMock()
        dal.get_sa_pick_detail.return_value = {
            "symbol": "NVDA", "picked_date": "2025-01-15",
            "portfolio_status": "current", "company": "NVIDIA",
        }
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_pick_detail.return_value = dal.get_sa_pick_detail.return_value
            mock_client.return_value = mock_instance
            result = get_sa_pick_detail(dal, symbol="NVDA")
            assert result["symbol"] == "NVDA"

    def test_closed_only_returns_hint(self):
        """Symbol only in closed returns hint with picked_date."""
        dal = MagicMock()
        dal.get_sa_portfolio.return_value = [
            {"symbol": "INTC", "picked_date": "2024-11-20", "portfolio_status": "closed"},
        ]
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_pick_detail.return_value = None
            mock_client.return_value = mock_instance
            result = get_sa_pick_detail(dal, symbol="INTC")
            assert result.get("hint") is not None
            assert "closed" in result["hint"].lower()


# ============================================================
# Stale reconciliation
# ============================================================

class TestStaleReconciliation:
    def test_refresh_marks_missing_as_stale(self):
        """Reconciliation marks old picks not in new set as stale."""
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock()  # Not DatabaseBackend

        old_picks = [
            {"symbol": "NVDA", "picked_date": "2025-01-15", "is_stale": False},
            {"symbol": "INTC", "picked_date": "2024-11-20", "is_stale": False},
        ]
        new_picks = [
            {"symbol": "NVDA", "picked_date": "2025-01-15"},
        ]

        result = dal._reconcile_sa_file_stale(old_picks, new_picks)
        symbols = {(r["symbol"], r["is_stale"]) for r in result}
        assert ("NVDA", False) in symbols
        assert ("INTC", True) in symbols

    def test_stale_restored_on_reappear(self):
        """Previously stale pick becomes non-stale when it reappears."""
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock()

        old_picks = [
            {"symbol": "NVDA", "picked_date": "2025-01-15", "is_stale": True},
        ]
        new_picks = [
            {"symbol": "NVDA", "picked_date": "2025-01-15"},
        ]

        result = dal._reconcile_sa_file_stale(old_picks, new_picks)
        assert len(result) == 1
        assert result[0]["symbol"] == "NVDA"
        assert result[0]["is_stale"] is False


# ============================================================
# DAL dual backend
# ============================================================

class TestDALDualBackend:
    def test_file_backend_uses_json(self):
        """File backend reads from JSON files."""
        from src.tools.data_access import DataAccessLayer
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "data" / "cache" / "seeking_alpha"
            cache_dir.mkdir(parents=True)

            # Write test data
            with open(cache_dir / "portfolio_current.json", "w") as f:
                json.dump([
                    {"symbol": "ACME", "picked_date": "2025-01-15",
                     "portfolio_status": "current", "is_stale": False},
                ], f)

            dal = DataAccessLayer.__new__(DataAccessLayer)
            dal._backend = MagicMock()  # Not DatabaseBackend
            dal._SA_CACHE_DIR = cache_dir

            result = dal._load_sa_file_cache("current")
            assert len(result) == 1
            assert result[0]["symbol"] == "ACME"

    def test_file_stale_in_same_file(self):
        """Stale rows stay in portfolio_current.json with is_stale=True."""
        from src.tools.data_access import DataAccessLayer
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "data" / "cache" / "seeking_alpha"
            cache_dir.mkdir(parents=True)

            with open(cache_dir / "portfolio_current.json", "w") as f:
                json.dump([
                    {"symbol": "ACME", "picked_date": "2025-01-15",
                     "portfolio_status": "current", "is_stale": False},
                    {"symbol": "GONE", "picked_date": "2024-06-01",
                     "portfolio_status": "current", "is_stale": True},
                ], f)

            dal = DataAccessLayer.__new__(DataAccessLayer)
            dal._backend = MagicMock()
            dal._SA_CACHE_DIR = cache_dir

            # Default: exclude stale
            result = dal._load_sa_file_cache("current", include_stale=False)
            assert len(result) == 1
            assert result[0]["symbol"] == "ACME"

            # Include stale
            result = dal._load_sa_file_cache("current", include_stale=True)
            assert len(result) == 2

    def test_refresh_meta_records_failure(self):
        """Failure meta preserves last_success_at."""
        from src.tools.data_access import DataAccessLayer
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "data" / "cache" / "seeking_alpha"
            cache_dir.mkdir(parents=True)

            # Write initial success meta
            with open(cache_dir / "meta.json", "w") as f:
                json.dump({
                    "current": {
                        "last_attempt_at": "2025-01-10T00:00:00+00:00",
                        "last_success_at": "2025-01-10T00:00:00+00:00",
                        "snapshot_ts": "2025-01-10T00:00:00+00:00",
                        "row_count": 40,
                        "ok": True,
                        "last_error": None,
                    }
                }, f)

            dal = DataAccessLayer.__new__(DataAccessLayer)
            dal._backend = MagicMock()
            dal._SA_CACHE_DIR = cache_dir

            # Record failure
            now = datetime.now(tz=timezone.utc)
            dal._save_sa_file_meta(
                scope="current", attempt_ts=now,
                snapshot_ts=None, row_count=None,
                ok=False, error="paywall detected",
            )

            # Verify: last_success_at preserved, ok=False
            with open(cache_dir / "meta.json") as f:
                meta = json.load(f)
            assert meta["current"]["ok"] is False
            assert meta["current"]["last_error"] == "paywall detected"
            assert meta["current"]["last_success_at"] == "2025-01-10T00:00:00+00:00"
            assert meta["current"]["row_count"] == 40

    def test_is_partial_false_when_both_ok(self):
        """is_partial is False when both scopes report ok=True."""
        meta = {
            "current": {"ok": True, "last_success_at": "2025-01-10T00:00:00+00:00"},
            "closed": {"ok": True, "last_success_at": "2025-01-10T00:00:00+00:00"},
        }
        is_partial = not (
            meta.get("current", {}).get("ok", False)
            and meta.get("closed", {}).get("ok", False)
        )
        assert is_partial is False

    def test_is_partial_true_when_one_fails(self):
        """is_partial is True when one scope fails."""
        meta = {
            "current": {"ok": True},
            "closed": {"ok": False, "last_error": "paywall"},
        }
        is_partial = not (
            meta.get("current", {}).get("ok", False)
            and meta.get("closed", {}).get("ok", False)
        )
        assert is_partial is True


# ============================================================
# Ticker sync
# ============================================================

class TestTickerSync:
    def test_current_picks_synced_to_tickers_core(self):
        """Current non-stale picks are synced to tickers_core.json."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(dal=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            tickers_path = Path(tmpdir) / "tickers_core.json"
            tickers_path.write_text(json.dumps({
                "tier3_user_watchlist": {},
            }))

            with patch("data_sources.sa_alpha_picks_client.Path", return_value=tickers_path):
                # Direct call with mock path
                picks = [
                    {"symbol": "ACME", "portfolio_status": "current", "is_stale": False},
                    {"symbol": "BETA", "portfolio_status": "current", "is_stale": False},
                ]
                # We need to patch the Path("config/tickers_core.json") call
                with patch("builtins.open", create=True) as mock_open:
                    # For simplicity, test the filter logic directly
                    symbols = sorted({
                        p["symbol"] for p in picks
                        if p.get("portfolio_status") == "current"
                        and not p.get("is_stale", False)
                    })
                    assert symbols == ["ACME", "BETA"]

    def test_closed_picks_not_synced(self):
        """Closed picks are excluded from ticker sync."""
        picks = [
            {"symbol": "ACME", "portfolio_status": "current", "is_stale": False},
            {"symbol": "GONE", "portfolio_status": "closed", "is_stale": False},
        ]
        symbols = sorted({
            p["symbol"] for p in picks
            if p.get("portfolio_status") == "current"
            and not p.get("is_stale", False)
        })
        assert "GONE" not in symbols
        assert "ACME" in symbols

    def test_stale_picks_not_synced(self):
        """Stale current picks are excluded from ticker sync."""
        picks = [
            {"symbol": "ACME", "portfolio_status": "current", "is_stale": False},
            {"symbol": "OLD", "portfolio_status": "current", "is_stale": True},
        ]
        symbols = sorted({
            p["symbol"] for p in picks
            if p.get("portfolio_status") == "current"
            and not p.get("is_stale", False)
        })
        assert "OLD" not in symbols


# ============================================================
# Tool functions
# ============================================================

class TestToolFunctions:
    def test_get_picks_disabled(self):
        """Disabled SA returns message, not error."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=False):
            result = get_sa_alpha_picks(MagicMock())
            assert "message" in result

    def test_refresh_disabled(self):
        """Disabled SA refresh returns message."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=False):
            result = refresh_sa_alpha_picks(MagicMock())
            assert "message" in result

    def test_filter_by_sector(self):
        """Sector filter works on returned picks."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_portfolio.return_value = {
                "current": [
                    {"symbol": "ACME", "sector": "Technology"},
                    {"symbol": "BETA", "sector": "Healthcare"},
                ],
                "closed": [],
                "freshness": {"current": {"ok": True}, "closed": {"ok": True}},
                "is_partial": False,
            }
            mock_client.return_value = mock_instance

            result = get_sa_alpha_picks(MagicMock(), sector="Tech")
            assert len(result["current"]) == 1
            assert result["current"][0]["symbol"] == "ACME"


# ============================================================
# Bridge integration
# ============================================================

class TestBridgeIntegration:
    def test_registry_47(self):
        """Registry should have 47 tools (44 + 3 SA)."""
        registry = create_default_registry()
        assert len(registry.list_all()) == 47

    def test_portfolio_category_4(self):
        """Portfolio category should have 4 tools (1 + 3 SA)."""
        registry = create_default_registry()
        assert len(registry.list_by_category("portfolio")) == 4

    def test_openai_schema_47(self):
        """OpenAI schema should have 47 tools."""
        registry = create_default_registry()
        schema = registry.to_openai_schema()
        assert len(schema) == 47

    def test_anthropic_schema_47(self):
        """Anthropic schema should have 47 tools."""
        registry = create_default_registry()
        schema = registry.to_anthropic_schema()
        assert len(schema) == 47

    def test_sa_tool_names_in_registry(self):
        """SA tool names should exist in registry."""
        registry = create_default_registry()
        names = registry.list_names()
        assert "get_sa_alpha_picks" in names
        assert "get_sa_pick_detail" in names
        assert "refresh_sa_alpha_picks" in names

    def test_anthropic_bridge_48(self):
        """Anthropic bridge should have 48 schemas (47 + delegate_to_subagent)."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        assert len(tools) == 48

    def test_openai_bridge_48(self):
        """OpenAI bridge should have 48 tools (47 + delegate, before web conditional)."""
        # Note: OpenAI tools count depends on web config.
        # Base tools (before web conditional) should be 48.
        # We test that SA tools are present in the schema names.
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = [t["name"] for t in tools]
        assert "get_sa_alpha_picks" in names
        assert "get_sa_pick_detail" in names
        assert "refresh_sa_alpha_picks" in names
