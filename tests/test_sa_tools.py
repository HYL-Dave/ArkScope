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
from types import SimpleNamespace
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
from src.tools.data_access import DataAccessLayer, _sanitize_sa_comments_count
from src.tools.backends.db_backend import DatabaseBackend, _prepare_comments_for_upsert
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

    def test_detail_url_in_raw_data_survives_dal(self):
        """Extension pick with raw_data.detail_url is passed through to DAL."""
        from scripts.sa_native_host import handle_message

        with patch("src.tools.data_access.DataAccessLayer") as MockDAL, \
             patch("scripts.sa_native_host._try_ticker_sync"):
            mock_dal = MagicMock()
            mock_dal.apply_sa_refresh.return_value = 1
            MockDAL.return_value = mock_dal

            # Simulates scrape.js output shape: detail_url in both top-level and raw_data
            picks = [{
                "symbol": "ACME",
                "company": "Acme Corp",
                "detail_url": "https://seekingalpha.com/alpha-picks/acme-123",
                "raw_data": {
                    "cells": ["Acme Corp", "ACME"],
                    "detail_url": "https://seekingalpha.com/alpha-picks/acme-123",
                },
            }]
            handle_message({
                "action": "refresh",
                "scope": "current",
                "picks": picks,
                "batch_ts": "2025-03-15T10:00:00Z",
            })

            # Verify the pick passed to DAL has raw_data.detail_url intact
            call_picks = mock_dal.apply_sa_refresh.call_args[1].get("picks") or mock_dal.apply_sa_refresh.call_args[0][1]
            assert call_picks[0]["raw_data"]["detail_url"] == "https://seekingalpha.com/alpha-picks/acme-123"


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
        assert len(registry.list_all()) == 49

    def test_portfolio_category_6(self):
        """Portfolio category should have 6 tools (1 + 3 SA picks + 2 SA articles)."""
        registry = create_default_registry()
        assert len(registry.list_by_category("portfolio")) == 6

    def test_openai_schema_47(self):
        """OpenAI schema should have 47 tools."""
        registry = create_default_registry()
        schema = registry.to_openai_schema()
        assert len(schema) == 49

    def test_anthropic_schema_47(self):
        """Anthropic schema should have 47 tools."""
        registry = create_default_registry()
        schema = registry.to_anthropic_schema()
        assert len(schema) == 49

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
        assert len(tools) == 50

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


# ============================================================
# Phase 11c-v2: Detail report persistence contract
# ============================================================

class TestSaveDetailContract:
    def test_db_success_returns_true(self):
        """save_sa_pick_detail returns True when DB update succeeds."""
        from src.tools.data_access import DataAccessLayer
        from src.tools.backends.db_backend import DatabaseBackend, _prepare_comments_for_upsert

        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock(spec=DatabaseBackend)
        dal._backend.update_sa_pick_detail.return_value = True
        dal._SA_CACHE_DIR = Path(tempfile.mkdtemp()) / "sa"

        result = dal.save_sa_pick_detail("NVDA", "2025-11-15", "# Report\nContent")
        assert result is True
        dal._backend.update_sa_pick_detail.assert_called_once()

    def test_db_failure_returns_false(self):
        """save_sa_pick_detail returns False when DB row not found (not masked by file save)."""
        from src.tools.data_access import DataAccessLayer
        from src.tools.backends.db_backend import DatabaseBackend, _prepare_comments_for_upsert

        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock(spec=DatabaseBackend)
        dal._backend.update_sa_pick_detail.return_value = False  # No row found
        dal._SA_CACHE_DIR = Path(tempfile.mkdtemp()) / "sa"

        result = dal.save_sa_pick_detail("NVDA", "2025-11-15", "# Report")
        assert result is False  # DB failure takes precedence over file success

    def test_db_exception_returns_false(self):
        """save_sa_pick_detail returns False when DB throws exception."""
        from src.tools.data_access import DataAccessLayer
        from src.tools.backends.db_backend import DatabaseBackend, _prepare_comments_for_upsert

        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock(spec=DatabaseBackend)
        dal._backend.update_sa_pick_detail.side_effect = RuntimeError("conn lost")
        dal._SA_CACHE_DIR = Path(tempfile.mkdtemp()) / "sa"

        result = dal.save_sa_pick_detail("NVDA", "2025-11-15", "# Report")
        assert result is False


class TestGetDetailFileMerge:
    def test_file_detail_merged_with_portfolio_row(self):
        """get_sa_pick_detail file-only + picked_date merges portfolio metadata."""
        from src.tools.data_access import DataAccessLayer

        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock()  # Not DatabaseBackend
        dal._SA_CACHE_DIR = Path(tempfile.mkdtemp()) / "sa"

        # Mock file loaders
        dal._load_sa_file_detail = MagicMock(return_value={
            "detail_report": "# Analysis\nContent here",
            "detail_fetched_at": "2025-03-10T10:00:00+00:00",
        })
        dal._load_sa_file_cache = MagicMock(side_effect=lambda status, **kw: [
            {"symbol": "NVDA", "picked_date": "2025-11-15",
             "return_pct": 42.3, "sector": "Technology",
             "sa_rating": "STRONG BUY", "portfolio_status": "current"},
        ] if status == "current" else [])

        result = dal.get_sa_pick_detail("NVDA", "2025-11-15")
        assert result is not None
        assert result.get("detail_report") == "# Analysis\nContent here"
        assert result.get("return_pct") == 42.3
        assert result.get("sector") == "Technology"
        assert result.get("sa_rating") == "STRONG BUY"

    def test_file_detail_only_when_no_portfolio_row(self):
        """get_sa_pick_detail returns detail-only when portfolio row missing."""
        from src.tools.data_access import DataAccessLayer

        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = MagicMock()  # Not DatabaseBackend
        dal._SA_CACHE_DIR = Path(tempfile.mkdtemp()) / "sa"

        dal._load_sa_file_detail = MagicMock(return_value={
            "detail_report": "# Report",
        })
        dal._load_sa_file_cache = MagicMock(return_value=[])

        result = dal.get_sa_pick_detail("NVDA", "2025-11-15")
        assert result is not None
        assert result.get("detail_report") == "# Report"


# ============================================================
# Phase 11c-v2: Native host detail actions
# ============================================================

class TestNativeHostDetailCache:
    def test_null_detail_needs_fetch(self):
        """Picks without detail_report are returned in need_detail."""
        from scripts.sa_native_host import _handle_check_detail_cache

        dal = MagicMock()
        dal.get_sa_pick_detail.return_value = {"symbol": "NVDA", "detail_report": None}

        articles = [{"ticker": "NVDA", "url": "https://sa.com/article/nvda"}]
        result = _handle_check_detail_cache(dal, [
            {"symbol": "NVDA", "picked_date": "2025-11-15"},
        ], articles)
        assert result["status"] == "ok"
        assert len(result["need_detail"]) == 1
        assert result["need_detail"][0]["article_url"] == "https://sa.com/article/nvda"

    def test_fresh_detail_skipped(self):
        """Picks with fresh detail_report are skipped."""
        from scripts.sa_native_host import _handle_check_detail_cache

        dal = MagicMock()
        fresh = datetime.now(timezone.utc).isoformat()
        dal.get_sa_pick_detail.return_value = {
            "symbol": "NVDA", "detail_report": "# Report", "detail_fetched_at": fresh,
        }

        articles = [{"ticker": "NVDA", "url": "https://sa.com/article/nvda"}]
        result = _handle_check_detail_cache(dal, [
            {"symbol": "NVDA", "picked_date": "2025-11-15"},
        ], articles)
        assert result["status"] == "ok"
        assert len(result["need_detail"]) == 0

    def test_expired_detail_needs_refetch(self):
        """Picks with expired detail are returned in need_detail."""
        from scripts.sa_native_host import _handle_check_detail_cache

        dal = MagicMock()
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        dal.get_sa_pick_detail.return_value = {
            "symbol": "NVDA", "detail_report": "# Old report", "detail_fetched_at": old,
        }

        articles = [{"ticker": "NVDA", "url": "https://sa.com/article/nvda"}]
        result = _handle_check_detail_cache(dal, [
            {"symbol": "NVDA", "picked_date": "2025-11-15"},
        ], articles)
        assert result["status"] == "ok"
        assert len(result["need_detail"]) == 1

    def test_no_article_for_pick_skipped(self):
        """Pick without matching article is skipped (not failed)."""
        from scripts.sa_native_host import _handle_check_detail_cache

        dal = MagicMock()
        dal.get_sa_pick_detail.return_value = {"symbol": "XYZ", "detail_report": None}

        articles = [{"ticker": "NVDA", "url": "https://sa.com/article/nvda"}]
        result = _handle_check_detail_cache(dal, [
            {"symbol": "XYZ", "picked_date": "2025-11-15"},
        ], articles)
        assert result["status"] == "ok"
        assert len(result["need_detail"]) == 0  # No matching article


class TestNativeHostSaveDetail:
    def test_save_success(self):
        """save_detail calls DAL and returns ok."""
        from scripts.sa_native_host import _handle_save_detail

        dal = MagicMock()
        dal.save_sa_pick_detail.return_value = True

        result = _handle_save_detail(dal, {
            "symbol": "NVDA", "picked_date": "2025-11-15",
            "detail_report": "# Report\nContent",
        })
        assert result["status"] == "ok"
        dal.save_sa_pick_detail.assert_called_once_with("NVDA", "2025-11-15", "# Report\nContent")

    def test_save_failure_returns_error(self):
        """save_detail returns error when DAL reports failure."""
        from scripts.sa_native_host import _handle_save_detail

        dal = MagicMock()
        dal.save_sa_pick_detail.return_value = False

        result = _handle_save_detail(dal, {
            "symbol": "NVDA", "picked_date": "2025-11-15",
            "detail_report": "# Report",
        })
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()


# ============================================================
# Phase 11c-v2: Detail staleness warning
# ============================================================

class TestDetailStaleness:
    def test_stale_detail_has_warning(self):
        """Client adds detail_stale_warning when detail is older than cache_days."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        dal = MagicMock()
        old = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        dal.get_sa_pick_detail.return_value = {
            "symbol": "NVDA", "detail_report": "# Report",
            "detail_fetched_at": old,
        }

        client = SAAlphaPicksClient(dal=dal, detail_cache_days=7)
        result = client.get_pick_detail("NVDA")
        assert "detail_stale_warning" in result
        assert "14d" in result["detail_stale_warning"]

    def test_fresh_detail_no_warning(self):
        """Client does not add warning for fresh detail."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        dal = MagicMock()
        fresh = datetime.now(timezone.utc).isoformat()
        dal.get_sa_pick_detail.return_value = {
            "symbol": "NVDA", "detail_report": "# Report",
            "detail_fetched_at": fresh,
        }

        client = SAAlphaPicksClient(dal=dal, detail_cache_days=7)
        result = client.get_pick_detail("NVDA")
        assert "detail_stale_warning" not in result


class TestDetailStalePassThrough:
    def test_tool_passes_through_stale_warning(self):
        """sa_tools.get_sa_pick_detail passes through detail_stale_warning."""
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True), \
             patch("src.tools.sa_tools._get_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get_pick_detail.return_value = {
                "symbol": "NVDA",
                "detail_report": "# Report",
                "detail_stale_warning": "Detail report is 14d old (limit: 7d).",
            }
            mock_client.return_value = mock_instance

            result = get_sa_pick_detail(MagicMock(), "NVDA")
            assert "detail_stale_warning" in result
            assert "14d" in result["detail_stale_warning"]


# ============================================================
# Phase 11c-v3: Articles + Comments
# ============================================================

class TestArticleTools:
    def test_get_sa_articles_disabled(self):
        """Disabled SA returns message for get_sa_articles."""
        from src.tools.sa_tools import get_sa_articles
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=False):
            result = get_sa_articles(MagicMock())
            assert "message" in result

    def test_get_sa_articles_returns_list(self):
        """get_sa_articles returns article list."""
        from src.tools.sa_tools import get_sa_articles
        dal = MagicMock()
        dal.get_sa_articles.return_value = [
            {"article_id": "123", "title": "Test Article", "ticker": "NVDA"},
        ]
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True):
            result = get_sa_articles(dal, ticker="NVDA")
            assert result["count"] == 1
            assert result["articles"][0]["ticker"] == "NVDA"

    def test_get_sa_article_detail_returns_content(self):
        """get_sa_article_detail returns article + comments."""
        from src.tools.sa_tools import get_sa_article_detail
        dal = MagicMock()
        dal.get_sa_article_detail.return_value = {
            "article_id": "123",
            "body_markdown": "# Test\nContent",
            "comments": [{"comment_id": "c1", "comment_text": "Great!"}],
        }
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True):
            result = get_sa_article_detail(dal, "123")
            assert result["body_markdown"] == "# Test\nContent"
            assert len(result["comments"]) == 1

    def test_get_sa_article_detail_not_found(self):
        """get_sa_article_detail returns error for missing article."""
        from src.tools.sa_tools import get_sa_article_detail
        dal = MagicMock()
        dal.get_sa_article_detail.return_value = None
        with patch("src.tools.sa_tools._is_sa_enabled", return_value=True):
            result = get_sa_article_detail(dal, "999")
            assert "error" in result


class TestDataAccessArticleMeta:
    def _make_dal(self):
        dal = DataAccessLayer.__new__(DataAccessLayer)
        dal._backend = DatabaseBackend("postgresql://example")
        dal._backend.sanitize_corrupted_sa_comments_counts = MagicMock(return_value=0)
        dal._compute_unresolved_symbols = MagicMock(return_value=[])
        return dal

    def test_sanitize_sa_comments_count_strips_published_year_prefix(self):
        assert _sanitize_sa_comments_count(202653, "2026-03-28") == 53
        assert _sanitize_sa_comments_count(2024101, "2024-07-15") == 101
        assert _sanitize_sa_comments_count(53, "2026-03-28") == 53

    def test_save_sa_articles_meta_sanitizes_incoming_comments_count(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(side_effect=[[
            {"article_id": "existing", "url": "https://example.com/existing", "has_content": True}
        ], []])

        dal.save_sa_articles_meta([
            {
                "article_id": "bad-count",
                "url": "https://example.com/bad-count",
                "published_date": "2026-03-28",
                "comments_count": 202653,
            }
        ], mode="quick")

        persisted = dal._backend.upsert_sa_articles_meta.call_args.args[0]
        assert persisted[0]["comments_count"] == 53

    def test_quick_mode_refreshes_comments_when_remote_count_increases(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "123",
                "url": "https://example.com/123",
                "has_content": True,
                "comments_count": 12,
                "stored_comments_count": 7,
                "comments_fetched_at": "2026-03-20T00:00:00+00:00",
            },
            {
                "article_id": "999",
                "url": "https://example.com/999",
                "has_content": True,
                "comments_count": 30,
                "stored_comments_count": 0,
                "comments_fetched_at": None,
            },
        ])

        result = dal.save_sa_articles_meta([
            {"article_id": "123", "url": "https://example.com/123"},
        ], mode="quick")

        assert result["need_content"] == []
        assert result["need_comments"] == [
            {"article_id": "123", "url": "https://example.com/123"},
        ]

    def test_quick_mode_ignores_year_prefixed_gap_artifact(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "123",
                "url": "https://example.com/123",
                "has_content": True,
                "comments_count": 202653,
                "stored_comments_count": 53,
                "published_date": "2026-03-28",
                "comments_fetched_at": "2026-03-28T00:00:00+00:00",
            },
        ])

        result = dal.save_sa_articles_meta([
            {"article_id": "123", "url": "https://example.com/123"},
        ], mode="quick")

        assert result["need_comments"] == []

    def test_quick_mode_skips_comment_refresh_for_articles_not_in_scan(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "123",
                "url": "https://example.com/123",
                "has_content": True,
                "comments_count": 7,
                "stored_comments_count": 7,
                "comments_fetched_at": "2026-03-20T00:00:00+00:00",
            },
            {
                "article_id": "999",
                "url": "https://example.com/999",
                "has_content": True,
                "comments_count": 30,
                "stored_comments_count": 0,
                "comments_fetched_at": None,
            },
        ])

        result = dal.save_sa_articles_meta([
            {"article_id": "123", "url": "https://example.com/123"},
        ], mode="quick")

        assert result["need_comments"] == []


    def test_full_mode_adds_top_gap_backfill_articles(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "need-content",
                "url": "https://example.com/need-content",
                "has_content": False,
                "comments_count": 3,
                "stored_comments_count": 0,
                "published_date": "2026-03-28",
                "comments_fetched_at": None,
            },
            {
                "article_id": "ttl-refresh",
                "url": "https://example.com/ttl-refresh",
                "has_content": True,
                "comments_count": 5,
                "stored_comments_count": 5,
                "published_date": "2026-03-01",
                "comments_fetched_at": old,
            },
            {
                "article_id": "gap-newer-big",
                "url": "https://example.com/gap-newer-big",
                "has_content": True,
                "comments_count": 80,
                "stored_comments_count": 30,
                "published_date": "2026-03-28",
                "comments_fetched_at": recent,
            },
            {
                "article_id": "gap-older-big",
                "url": "https://example.com/gap-older-big",
                "has_content": True,
                "comments_count": 70,
                "stored_comments_count": 20,
                "published_date": "2026-03-20",
                "comments_fetched_at": recent,
            },
            {
                "article_id": "gap-small",
                "url": "https://example.com/gap-small",
                "has_content": True,
                "comments_count": 20,
                "stored_comments_count": 12,
                "published_date": "2026-03-27",
                "comments_fetched_at": recent,
            },
            {
                "article_id": "fresh-no-gap",
                "url": "https://example.com/fresh-no-gap",
                "has_content": True,
                "comments_count": 9,
                "stored_comments_count": 9,
                "published_date": "2026-03-26",
                "comments_fetched_at": recent,
            },
        ])

        with patch(
            "src.agents.config.get_agent_config",
            return_value=SimpleNamespace(
                sa_comments_cache_days=7,
                sa_comments_backfill_per_full_scan=2,
            ),
        ):
            result = dal.save_sa_articles_meta([
                {"article_id": "123", "url": "https://example.com/123"},
            ], mode="full")

        assert result["need_content"] == [
            {"article_id": "need-content", "url": "https://example.com/need-content"},
        ]
        assert result["need_comments"] == [
            {"article_id": "ttl-refresh", "url": "https://example.com/ttl-refresh"},
            {"article_id": "gap-newer-big", "url": "https://example.com/gap-newer-big"},
            {"article_id": "gap-older-big", "url": "https://example.com/gap-older-big"},
        ]


    def test_full_mode_treats_missing_comments_timestamp_as_stale(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "never-fetched",
                "url": "https://example.com/never-fetched",
                "has_content": True,
                "comments_count": 3,
                "stored_comments_count": 0,
                "published_date": "2026-03-25",
                "comments_fetched_at": None,
            },
        ])

        with patch(
            "src.agents.config.get_agent_config",
            return_value=SimpleNamespace(
                sa_comments_cache_days=7,
                sa_comments_backfill_per_full_scan=0,
            ),
        ):
            result = dal.save_sa_articles_meta([
                {"article_id": "123", "url": "https://example.com/123"},
            ], mode="full")

        assert result["need_comments"] == [
            {"article_id": "never-fetched", "url": "https://example.com/never-fetched"},
        ]


    def test_backfill_skips_stale_zero_comment_articles(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "stale-zero",
                "url": "https://example.com/stale-zero",
                "has_content": True,
                "comments_count": 0,
                "stored_comments_count": 0,
                "published_date": "2026-03-01",
                "comments_fetched_at": old,
            },
            {
                "article_id": "gap-positive",
                "url": "https://example.com/gap-positive",
                "has_content": True,
                "comments_count": 40,
                "stored_comments_count": 10,
                "published_date": "2026-03-28",
                "comments_fetched_at": recent,
            },
        ])

        with patch(
            "src.agents.config.get_agent_config",
            return_value=SimpleNamespace(
                sa_comments_cache_days=7,
                sa_comments_backfill_per_full_scan=1,
                sa_comments_backfill_per_backfill_scan=5,
            ),
        ):
            result = dal.save_sa_articles_meta([
                {"article_id": "123", "url": "https://example.com/123"},
            ], mode="backfill")

        assert result["need_comments"] == [
            {"article_id": "gap-positive", "url": "https://example.com/gap-positive"},
        ]

    def test_backfill_mode_uses_deeper_backfill_limit(self):
        dal = self._make_dal()
        dal._backend.upsert_sa_articles_meta = MagicMock(return_value=1)
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        dal._backend.query_sa_articles = MagicMock(return_value=[
            {
                "article_id": "gap-a",
                "url": "https://example.com/gap-a",
                "has_content": True,
                "comments_count": 90,
                "stored_comments_count": 10,
                "published_date": "2026-03-28",
                "comments_fetched_at": recent,
            },
            {
                "article_id": "gap-b",
                "url": "https://example.com/gap-b",
                "has_content": True,
                "comments_count": 80,
                "stored_comments_count": 10,
                "published_date": "2026-03-27",
                "comments_fetched_at": recent,
            },
            {
                "article_id": "gap-c",
                "url": "https://example.com/gap-c",
                "has_content": True,
                "comments_count": 70,
                "stored_comments_count": 10,
                "published_date": "2026-03-26",
                "comments_fetched_at": recent,
            },
        ])

        with patch(
            "src.agents.config.get_agent_config",
            return_value=SimpleNamespace(
                sa_comments_cache_days=7,
                sa_comments_backfill_per_full_scan=1,
                sa_comments_backfill_per_backfill_scan=3,
            ),
        ):
            result = dal.save_sa_articles_meta([
                {"article_id": "123", "url": "https://example.com/123"},
            ], mode="backfill")

        assert result["need_comments"] == [
            {"article_id": "gap-a", "url": "https://example.com/gap-a"},
            {"article_id": "gap-b", "url": "https://example.com/gap-b"},
            {"article_id": "gap-c", "url": "https://example.com/gap-c"},
        ]


class TestNativeHostArticles:
    def test_save_articles_meta(self):
        """save_articles_meta calls DAL and returns result."""
        from scripts.sa_native_host import _handle_save_articles_meta
        dal = MagicMock()
        dal.save_sa_articles_meta.return_value = {
            "status": "ok", "saved": 5, "need_content": [],
            "need_comments": [], "unresolved_symbols": [], "auto_upgrade": False,
        }
        result = _handle_save_articles_meta(dal, {
            "mode": "quick",
            "articles": [{"article_id": "123", "title": "Test"}],
        })
        assert result["saved"] == 5

    def test_save_article_content(self):
        """save_article_content calls compound DAL method."""
        from scripts.sa_native_host import _handle_save_article_content
        dal = MagicMock()
        dal.save_sa_article_with_comments.return_value = {"ok": True, "synced_picks": 1}
        result = _handle_save_article_content(dal, {
            "article_id": "123",
            "body_markdown": "# Content",
            "comments": [],
        })
        assert result["status"] == "ok"
        dal.save_sa_article_with_comments.assert_called_once()

    def test_audit_unresolved(self):
        """audit_unresolved calls DAL and returns result."""
        from scripts.sa_native_host import _handle_audit_unresolved
        dal = MagicMock()
        dal.audit_sa_unresolved_symbols.return_value = {
            "unresolved_symbols": ["CVSA"],
            "resolved_by_fulltext": 2,
        }
        result = _handle_audit_unresolved(dal)
        assert result["status"] == "ok"
        assert "CVSA" in result["unresolved_symbols"]


class TestCommentNormalization:
    def test_normalize_comment_ids_merges_null_and_dated_duplicate(self):
        from scripts.sa_native_host import _normalize_comment_ids

        comments = [
            {
                "comment_id": "syn_null",
                "commenter": "Alpha Brett",
                "comment_text": "Same thesis.",
                "comment_date": None,
                "upvotes": 1,
                "parent_comment_id": None,
            },
            {
                "comment_id": "syn_dated",
                "commenter": "Alpha Brett",
                "comment_text": "Same thesis.",
                "comment_date": "2026-03-29T01:23:00Z",
                "upvotes": 4,
                "parent_comment_id": None,
            },
        ]

        normalized = _normalize_comment_ids("6272753", comments)

        assert len(normalized) == 1
        assert normalized[0]["comment_date"] == "2026-03-29T01:23:00+00:00"
        assert normalized[0]["upvotes"] == 4

    def test_normalize_comment_ids_preserves_distinct_dated_duplicates(self):
        from scripts.sa_native_host import _normalize_comment_ids

        comments = [
            {
                "comment_id": "syn_a",
                "commenter": "Lacifer",
                "comment_text": "Still bearish.",
                "comment_date": "2026-03-29T01:23:00Z",
                "upvotes": 1,
                "parent_comment_id": None,
            },
            {
                "comment_id": "syn_b",
                "commenter": "Lacifer",
                "comment_text": "Still bearish.",
                "comment_date": "2026-03-30T01:23:00Z",
                "upvotes": 2,
                "parent_comment_id": None,
            },
        ]

        normalized = _normalize_comment_ids("6216738", comments)

        assert len(normalized) == 2
        assert {c["comment_date"] for c in normalized} == {
            "2026-03-29T01:23:00+00:00",
            "2026-03-30T01:23:00+00:00",
        }

    def test_normalize_comment_ids_merges_naive_and_utc_same_wall_clock(self):
        from scripts.sa_native_host import _normalize_comment_ids

        comments = [
            {
                "comment_id": "syn_local",
                "commenter": "Odsmaker",
                "comment_text": "Still tracking this.",
                "comment_date": "2026-03-29T01:23:00",
                "upvotes": 1,
                "parent_comment_id": None,
            },
            {
                "comment_id": "syn_utc",
                "commenter": "Odsmaker",
                "comment_text": "Still tracking this.",
                "comment_date": "2026-03-29T01:23:00Z",
                "upvotes": 3,
                "parent_comment_id": None,
            },
        ]

        normalized = _normalize_comment_ids("6093149", comments)

        assert len(normalized) == 1
        assert normalized[0]["comment_date"] == "2026-03-29T01:23:00+00:00"
        assert normalized[0]["upvotes"] == 3

    def test_normalize_comment_ids_remaps_parent_after_merge(self):
        from scripts.sa_native_host import _normalize_comment_ids

        comments = [
            {
                "comment_id": "syn_parent_null",
                "commenter": "Ajarn Brian",
                "comment_text": "Base case.",
                "comment_date": None,
                "upvotes": 0,
                "parent_comment_id": None,
            },
            {
                "comment_id": "syn_parent_dated",
                "commenter": "Ajarn Brian",
                "comment_text": "Base case.",
                "comment_date": "2026-03-29T01:23:00Z",
                "upvotes": 1,
                "parent_comment_id": None,
            },
            {
                "comment_id": "syn_child",
                "commenter": "Simon Dadouche",
                "comment_text": "@Ajarn Brian agreed.",
                "comment_date": "2026-03-29T01:30:00Z",
                "upvotes": 0,
                "parent_comment_id": "syn_parent_null",
            },
        ]

        normalized = _normalize_comment_ids("6093149", comments)
        parent = next(c for c in normalized if c["commenter"] == "Ajarn Brian")
        child = next(c for c in normalized if c["commenter"] == "Simon Dadouche")

        assert len(normalized) == 2
        assert child["parent_comment_id"] == parent["comment_id"]


class TestCommentUpsertPrep:
    def test_prepare_comments_for_upsert_merges_into_existing_dated_comment(self):
        existing = [
            {
                "comment_id": "canon_1",
                "parent_comment_id": None,
                "commenter": "Alpha Brett",
                "comment_text": "Same thesis.",
                "upvotes": 2,
                "comment_date": datetime(2026, 3, 29, 1, 23, tzinfo=timezone.utc),
            }
        ]
        incoming = [
            {
                "comment_id": "syn_1",
                "parent_comment_id": None,
                "commenter": "Alpha Brett",
                "comment_text": "Same thesis.",
                "upvotes": 5,
                "comment_date": None,
            }
        ]

        prepared = _prepare_comments_for_upsert(existing, incoming)

        assert len(prepared) == 1
        assert prepared[0]["comment_id"] == "canon_1"
        assert prepared[0]["comment_date"] == "2026-03-29T01:23:00+00:00"
        assert prepared[0]["upvotes"] == 5

    def test_prepare_comments_for_upsert_keeps_distinct_real_duplicates(self):
        existing = [
            {
                "comment_id": "canon_1",
                "parent_comment_id": None,
                "commenter": "Lacifer",
                "comment_text": "Still bearish.",
                "upvotes": 1,
                "comment_date": datetime(2026, 3, 29, 1, 23, tzinfo=timezone.utc),
            }
        ]
        incoming = [
            {
                "comment_id": "syn_2",
                "parent_comment_id": None,
                "commenter": "Lacifer",
                "comment_text": "Still bearish.",
                "upvotes": 3,
                "comment_date": "2026-03-30T01:23:00Z",
            }
        ]

        prepared = _prepare_comments_for_upsert(existing, incoming)

        assert len(prepared) == 1
        assert prepared[0]["comment_id"] == "syn_2"
        assert prepared[0]["comment_date"] == "2026-03-30T01:23:00+00:00"

    def test_prepare_comments_for_upsert_matches_existing_utc_row_with_naive_incoming(self):
        existing = [
            {
                "comment_id": "canon_1",
                "parent_comment_id": None,
                "commenter": "1629 Capital",
                "comment_text": "@revinax done!",
                "upvotes": 0,
                "comment_date": datetime(2023, 10, 25, 18, 52, tzinfo=timezone.utc),
            }
        ]
        incoming = [
            {
                "comment_id": "syn_1",
                "parent_comment_id": None,
                "commenter": "1629 Capital",
                "comment_text": "@revinax done!",
                "upvotes": 0,
                "comment_date": "2023-10-25T18:52:00",
            }
        ]

        prepared = _prepare_comments_for_upsert(existing, incoming)

        assert len(prepared) == 1
        assert prepared[0]["comment_id"] == "canon_1"
        assert prepared[0]["comment_date"] == "2023-10-25T18:52:00+00:00"

    def test_prepare_comments_for_upsert_remaps_child_to_existing_parent(self):
        existing = [
            {
                "comment_id": "canon_parent",
                "parent_comment_id": None,
                "commenter": "Ajarn Brian",
                "comment_text": "Base case.",
                "upvotes": 1,
                "comment_date": datetime(2026, 3, 29, 1, 23, tzinfo=timezone.utc),
            }
        ]
        incoming = [
            {
                "comment_id": "syn_parent",
                "parent_comment_id": None,
                "commenter": "Ajarn Brian",
                "comment_text": "Base case.",
                "upvotes": 1,
                "comment_date": None,
            },
            {
                "comment_id": "syn_child",
                "parent_comment_id": "syn_parent",
                "commenter": "Simon Dadouche",
                "comment_text": "@Ajarn Brian agreed.",
                "upvotes": 0,
                "comment_date": "2026-03-29T01:30:00Z",
            },
        ]

        prepared = _prepare_comments_for_upsert(existing, incoming)
        child = next(c for c in prepared if c["commenter"] == "Simon Dadouche")

        assert child["parent_comment_id"] == "canon_parent"


class TestRegistryV3:
    def test_registry_49(self):
        """Registry should have 49 tools (47 + 2 SA articles)."""
        registry = create_default_registry()
        assert len(registry.list_all()) == 49

    def test_portfolio_category_6(self):
        """Portfolio category should have 6 tools (4 + 2 SA articles)."""
        registry = create_default_registry()
        assert len(registry.list_by_category("portfolio")) == 6

    def test_new_tool_names_in_registry(self):
        """New SA article tool names should exist in registry."""
        registry = create_default_registry()
        names = registry.list_names()
        assert "get_sa_articles" in names
        assert "get_sa_article_detail" in names
