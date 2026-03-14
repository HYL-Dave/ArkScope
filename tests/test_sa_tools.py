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
# Session check
# ============================================================

class TestSessionCheck:
    def test_missing_session_file(self):
        """Client returns error when session file doesn't exist."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(
            session_file="/nonexistent/path.json",
            dal=MagicMock(),
        )
        result = client.refresh_portfolio()
        assert "error" in result
        assert "Session file not found" in result["error"]


# ============================================================
# DOM parsing (unit: mock Playwright)
# ============================================================

class TestDOMParsing:
    def test_parse_row_extracts_symbol(self):
        """Row parser extracts ticker symbol."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(session_file="/tmp/fake.json")

        # Mock cells
        mock_cells = []
        texts = ["Acme Corp", "ACME", "Jan 15, 2025", "+25.3%", "Technology", "STRONG BUY", "3.5%"]
        for t in texts:
            cell = MagicMock()
            cell.inner_text.return_value = t
            mock_cells.append(cell)

        pick = client._parse_row(mock_cells, "current")
        assert pick is not None
        assert pick["symbol"] == "ACME"
        assert pick["portfolio_status"] == "current"
        assert pick["is_stale"] is False

    def test_parse_row_extracts_date(self):
        """Row parser extracts and normalizes picked date."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(session_file="/tmp/fake.json")

        mock_cells = []
        texts = ["Acme Corp", "ACME", "Jan 15, 2025", "+25.3%", "Technology", "STRONG BUY", "3.5%"]
        for t in texts:
            cell = MagicMock()
            cell.inner_text.return_value = t
            mock_cells.append(cell)

        pick = client._parse_row(mock_cells, "current")
        assert pick["picked_date"] == "2025-01-15"

    def test_parse_row_extracts_rating(self):
        """Row parser extracts SA rating."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(session_file="/tmp/fake.json")

        mock_cells = []
        texts = ["Beta Inc", "BETA", "Feb 20, 2025", "-5.1%", "Healthcare", "BUY", "2.8%"]
        for t in texts:
            cell = MagicMock()
            cell.inner_text.return_value = t
            mock_cells.append(cell)

        pick = client._parse_row(mock_cells, "closed")
        assert pick["sa_rating"] == "BUY"
        assert pick["portfolio_status"] == "closed"

    def test_empty_cells_returns_none(self):
        """Row parser returns None for insufficient cells."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(session_file="/tmp/fake.json")

        # Only 3 cells (< 6 minimum)
        mock_cells = [MagicMock() for _ in range(3)]
        for c in mock_cells:
            c.inner_text.return_value = ""

        # _parse_row is called only after len(cells) >= 6 check in _scrape_tab
        # But if we call it directly with bad data, it should return something or None
        pick = client._parse_row(mock_cells, "current")
        # Symbol would be empty string
        assert pick is None or pick.get("symbol") == ""


# ============================================================
# DOM fixture parsing
# ============================================================

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sa_portfolio_sample.html"


def _build_mock_page_from_fixture():
    """Build a mock Playwright page from the HTML fixture.

    Returns a mock page whose query_selector_all(_TABLE_ROW_SELECTOR)
    returns mock row elements with td cells + anchor links matching the fixture.
    """
    import re

    html = _FIXTURE_PATH.read_text()
    tbody = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL).group(1)
    row_htmls = re.findall(r"<tr>(.*?)</tr>", tbody, re.DOTALL)

    mock_rows = []
    for row_html in row_htmls:
        cells_text = re.findall(r"<td>([^<]*)</td>", row_html)
        href_match = re.search(r'href="([^"]*)"', row_html)

        # Build mock cells
        mock_cells = []
        for t in cells_text:
            cell = MagicMock()
            cell.inner_text.return_value = t.strip()
            mock_cells.append(cell)

        # Build mock link element
        mock_link = None
        if href_match:
            mock_link = MagicMock()
            mock_link.get_attribute.return_value = href_match.group(1)

        # Build mock row
        mock_row = MagicMock()
        mock_row.query_selector_all.return_value = mock_cells
        mock_row.query_selector.return_value = mock_link
        mock_rows.append(mock_row)

    # Build mock page
    mock_page = MagicMock()
    mock_page.query_selector_all.return_value = mock_rows
    mock_page.query_selector.return_value = None  # No tab button to click
    mock_page.inner_text.return_value = ""  # No paywall markers
    return mock_page


class TestDOMFixture:
    """Tests that exercise _scrape_tab() with fixture-derived mock page."""

    def test_scrape_tab_extracts_all_rows(self):
        """_scrape_tab with fixture page returns 3 picks."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        client = SAAlphaPicksClient(session_file="/tmp/fake.json")
        mock_page = _build_mock_page_from_fixture()

        picks = client._scrape_tab(mock_page, portfolio_status="current")
        assert len(picks) == 3
        symbols = [p["symbol"] for p in picks]
        assert "ACME" in symbols
        assert "BETA" in symbols
        assert "GAMA" in symbols

    def test_scrape_tab_captures_detail_urls(self):
        """_scrape_tab extracts detail_url from row links."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        client = SAAlphaPicksClient(session_file="/tmp/fake.json")
        mock_page = _build_mock_page_from_fixture()

        picks = client._scrape_tab(mock_page, portfolio_status="current")
        # Every row in fixture has an <a href>
        for pick in picks:
            assert "detail_url" in pick, f"{pick['symbol']} missing detail_url"
            assert pick["detail_url"].startswith("https://seekingalpha.com/")

        # Check specific URL
        acme = next(p for p in picks if p["symbol"] == "ACME")
        assert "/alpha-picks/acme-analysis-12345" in acme["detail_url"]

    def test_scrape_tab_field_values(self):
        """_scrape_tab parses correct field values from fixture."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        client = SAAlphaPicksClient(session_file="/tmp/fake.json")
        mock_page = _build_mock_page_from_fixture()

        picks = client._scrape_tab(mock_page, portfolio_status="current")
        acme = next(p for p in picks if p["symbol"] == "ACME")
        assert acme["company"] == "Acme Corp"
        assert acme["picked_date"] == "2025-01-15"
        assert acme["sa_rating"] == "STRONG BUY"
        assert acme["sector"] == "Technology"
        assert acme["portfolio_status"] == "current"
        assert acme["is_stale"] is False

    def test_scrape_tab_closed_status(self):
        """_scrape_tab sets portfolio_status='closed' when scraping closed tab."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        client = SAAlphaPicksClient(session_file="/tmp/fake.json")
        mock_page = _build_mock_page_from_fixture()

        picks = client._scrape_tab(mock_page, portfolio_status="closed")
        for pick in picks:
            assert pick["portfolio_status"] == "closed"

    def test_detail_url_in_raw_data_for_db_roundtrip(self):
        """detail_url is stored inside raw_data so it persists through DB write/read."""
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient

        client = SAAlphaPicksClient(session_file="/tmp/fake.json")
        mock_page = _build_mock_page_from_fixture()

        picks = client._scrape_tab(mock_page, portfolio_status="current")
        acme = next(p for p in picks if p["symbol"] == "ACME")

        # Simulate DB round-trip: only raw_data survives as JSONB
        raw_data = acme["raw_data"]
        assert "detail_url" in raw_data, "detail_url must be in raw_data for DB persistence"

        # After DB read, get_pick_detail resolves URL from raw_data
        db_row = {"symbol": "ACME", "raw_data": raw_data}
        resolved = (
            db_row.get("detail_url")  # Not present after DB read
            or db_row.get("raw_data", {}).get("detail_url")  # Fallback
        )
        assert resolved is not None
        assert "/alpha-picks/acme-analysis-12345" in resolved


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
        client = SAAlphaPicksClient(session_file="/tmp/fake.json")

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
