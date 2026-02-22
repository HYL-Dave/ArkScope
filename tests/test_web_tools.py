"""
Tests for Phase 10 web search tools.

All external calls (Tavily, Playwright) are mocked — no live API needed.
"""

import json
import os
import re
from unittest.mock import MagicMock, patch

import pytest


def _unwrap(result: str) -> str:
    """Strip <tool_output> wrapping (Phase 15) to get raw JSON."""
    m = re.search(r"<tool_output[^>]*>\n(.*)\n</tool_output>", result, re.DOTALL)
    return m.group(1) if m else result


# ── _days_to_time_range ──────────────────────────────────────────

class TestDaysToTimeRange:
    def test_day(self):
        from src.tools.web_tools import _days_to_time_range
        assert _days_to_time_range(1) == "day"

    def test_week(self):
        from src.tools.web_tools import _days_to_time_range
        assert _days_to_time_range(7) == "week"
        assert _days_to_time_range(3) == "week"

    def test_month(self):
        from src.tools.web_tools import _days_to_time_range
        assert _days_to_time_range(30) == "month"
        assert _days_to_time_range(14) == "month"

    def test_year(self):
        from src.tools.web_tools import _days_to_time_range
        assert _days_to_time_range(365) == "year"
        assert _days_to_time_range(31) == "year"


# ── Tavily Search ────────────────────────────────────────────────

class TestTavilySearch:
    @patch("src.tools.web_tools._get_tavily_client")
    def test_basic_search(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "NVDA rose 5%",
            "results": [
                {"title": "NVDA News", "url": "https://example.com/1",
                 "content": "Short content", "score": 0.9},
            ],
        }
        mock_get_client.return_value = mock_client

        result = web_search("NVDA earnings")
        assert result["query"] == "NVDA earnings"
        assert result["answer"] == "NVDA rose 5%"
        assert result["result_count"] == 1
        assert result["results"][0]["title"] == "NVDA News"
        assert result["results"][0]["score"] == 0.9

    @patch("src.tools.web_tools._get_tavily_client")
    def test_finance_topic(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}
        mock_get_client.return_value = mock_client

        web_search("NVDA", topic="finance")
        kwargs = mock_client.search.call_args[1]
        assert kwargs["topic"] == "finance"

    @patch("src.tools.web_tools._get_tavily_client")
    def test_time_range(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}
        mock_get_client.return_value = mock_client

        web_search("test", days=7)
        kwargs = mock_client.search.call_args[1]
        assert kwargs["time_range"] == "week"

    @patch("src.tools.web_tools._get_tavily_client")
    def test_no_time_range_when_zero(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}
        mock_get_client.return_value = mock_client

        web_search("test", days=0)
        kwargs = mock_client.search.call_args[1]
        assert "time_range" not in kwargs

    @patch("src.tools.web_tools._get_tavily_client")
    def test_max_results_clamped(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.return_value = {"answer": "", "results": []}
        mock_get_client.return_value = mock_client

        web_search("test", max_results=99)
        kwargs = mock_client.search.call_args[1]
        assert kwargs["max_results"] == 10

    @patch("src.tools.web_tools._get_tavily_client")
    def test_content_truncation(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        long_content = "x" * 1000
        mock_client.search.return_value = {
            "answer": "",
            "results": [{"title": "T", "url": "u", "content": long_content, "score": 0.5}],
        }
        mock_get_client.return_value = mock_client

        result = web_search("test")
        assert len(result["results"][0]["content"]) == 503  # 500 + "..."

    def test_no_api_key(self):
        """When TAVILY_API_KEY is not set, should return error dict."""
        import src.tools.web_tools as wt
        # Reset cached client
        wt._tavily_client = None
        original = os.environ.get("TAVILY_API_KEY")
        try:
            os.environ.pop("TAVILY_API_KEY", None)
            result = wt.web_search("test")
            assert "error" in result
            assert "TAVILY_API_KEY" in result["error"]
        finally:
            if original is not None:
                os.environ["TAVILY_API_KEY"] = original
            wt._tavily_client = None

    @patch("src.tools.web_tools._get_tavily_client")
    def test_search_exception(self, mock_get_client):
        from src.tools.web_tools import web_search

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("API timeout")
        mock_get_client.return_value = mock_client

        result = web_search("test")
        assert "error" in result
        assert "API timeout" in result["error"]


# ── Tavily Fetch ─────────────────────────────────────────────────

class TestTavilyFetch:
    @patch("src.tools.web_tools._get_tavily_client")
    def test_basic_fetch(self, mock_get_client):
        from src.tools.web_tools import web_fetch

        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "results": [{"raw_content": "Hello World! " * 100}],
        }
        mock_get_client.return_value = mock_client

        result = web_fetch("https://example.com")
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["offset"] == 0
        assert result["total_chars"] == len("Hello World! " * 100)

    @patch("src.tools.web_tools._get_tavily_client")
    def test_pagination(self, mock_get_client):
        from src.tools.web_tools import web_fetch

        full_content = "A" * 10000
        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "results": [{"raw_content": full_content}],
        }
        mock_get_client.return_value = mock_client

        result = web_fetch("https://example.com", offset=0, max_chars=3000)
        assert result["was_truncated"] is True
        assert result["remaining_chars"] == 7000
        assert len(result["content"]) == 3000

        result2 = web_fetch("https://example.com", offset=3000, max_chars=3000)
        assert result2["offset"] == 3000
        assert len(result2["content"]) == 3000

    @patch("src.tools.web_tools._get_tavily_client")
    def test_failed_results(self, mock_get_client):
        from src.tools.web_tools import web_fetch

        mock_client = MagicMock()
        mock_client.extract.return_value = {
            "results": [],
            "failed_results": [{"error": "403 Forbidden"}],
        }
        mock_get_client.return_value = mock_client

        result = web_fetch("https://example.com")
        assert result["success"] is False
        assert "403" in result["error"]


# ── Playwright Browse ────────────────────────────────────────────

class TestWebBrowse:
    @patch("playwright.sync_api.sync_playwright")
    def test_basic_browse(self, mock_pw_factory):
        """Mock Playwright to test web_browse."""
        from src.tools.web_tools import web_browse

        # Build mock chain: sync_playwright() → context_manager → p → chromium → browser → page
        mock_page = MagicMock()
        mock_page.title.return_value = "Test Page"
        mock_page.inner_text.return_value = "Page content here"
        mock_page.query_selector_all.return_value = []

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw_factory.return_value = mock_ctx

        result = web_browse("https://example.com")

        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert "Page content" in result["content"]

    @patch("playwright.sync_api.sync_playwright")
    def test_pagination(self, mock_pw_factory):
        """Test web_browse pagination with offset/max_chars."""
        from src.tools.web_tools import web_browse

        full_text = "A" * 10000
        mock_page = MagicMock()
        mock_page.title.return_value = "Long Page"
        mock_page.inner_text.return_value = full_text

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw_factory.return_value = mock_ctx

        result = web_browse("https://example.com", max_chars=5000)
        assert result["was_truncated"] is True
        assert result["remaining_chars"] == 5000
        assert len(result["content"]) == 5000

    @patch("playwright.sync_api.sync_playwright")
    def test_extract_links(self, mock_pw_factory):
        """Test web_browse with extract_links=True."""
        from src.tools.web_tools import web_browse

        mock_link = MagicMock()
        mock_link.get_attribute.return_value = "https://link.com"
        mock_link.inner_text.return_value = "Click here"

        mock_page = MagicMock()
        mock_page.title.return_value = "Links Page"
        mock_page.inner_text.return_value = "Content"
        mock_page.query_selector_all.return_value = [mock_link]

        mock_browser = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw_factory.return_value = mock_ctx

        result = web_browse("https://example.com", extract_links=True)
        assert "links" in result
        assert len(result["links"]) == 1
        assert result["links"][0]["text"] == "Click here"

    @patch("playwright.sync_api.sync_playwright")
    def test_browse_error(self, mock_pw_factory):
        """Test web_browse when page.goto fails."""
        from src.tools.web_tools import web_browse

        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_page.goto.side_effect = Exception("Timeout")
        mock_browser.new_page.return_value = mock_page
        mock_pw.chromium.launch.return_value = mock_browser
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pw)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_pw_factory.return_value = mock_ctx

        result = web_browse("https://example.com")
        assert result["success"] is False
        assert "Timeout" in result["error"]


# ── Bridge Integration ───────────────────────────────────────────

class TestBridgeIntegration:
    def test_anthropic_tools_include_web(self):
        """get_anthropic_tools() should include web tools when config enables them."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = [t["name"] for t in tools]
        # Default config has web_tavily=True, web_playwright=True
        assert "tavily_search" in names
        assert "tavily_fetch" in names
        assert "web_browse" in names

    def test_anthropic_tools_excludes_claude_search(self):
        """Claude web search server tool should NOT be in get_anthropic_tools()
        (it's added in the agent runner, not the tools list)."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = [t["name"] for t in tools]
        assert "web_search" not in names

    def test_execute_tool_tavily_search(self):
        """execute_tool should dispatch tavily_search correctly."""
        from src.agents.anthropic_agent.tools import execute_tool
        with patch("src.tools.web_tools._get_tavily_client") as mock_get:
            mock_client = MagicMock()
            mock_client.search.return_value = {"answer": "test", "results": []}
            mock_get.return_value = mock_client
            result = json.loads(_unwrap(execute_tool("tavily_search", {"query": "test"}, None)))
            assert result["query"] == "test"

    def test_execute_tool_web_browse(self):
        """execute_tool should dispatch web_browse correctly."""
        from src.agents.anthropic_agent.tools import execute_tool
        with patch("playwright.sync_api.sync_playwright") as mock_pw:
            mock_page = MagicMock()
            mock_page.title.return_value = "T"
            mock_page.inner_text.return_value = "content"
            mock_browser = MagicMock()
            mock_browser.new_page.return_value = mock_page
            mock_p = MagicMock()
            mock_p.chromium.launch.return_value = mock_browser
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_p)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            mock_pw.return_value = mock_ctx

            result = json.loads(_unwrap(execute_tool("web_browse", {"url": "https://x.com"}, None)))
            assert result["success"] is True

    def test_openai_tools_include_web(self):
        """create_openai_tools() should include web tools when config enables them."""
        from src.tools.data_access import DataAccessLayer
        from src.agents.openai_agent.tools import create_openai_tools
        dal = DataAccessLayer(db_dsn="auto")
        tools = create_openai_tools(dal)
        names = [getattr(t, "name", "") for t in tools]
        assert "tool_tavily_search" in names
        assert "tool_tavily_fetch" in names
        assert "tool_web_browse" in names

    def test_registry_web_tools(self):
        """ToolRegistry should register 4 web tools."""
        from src.tools.registry import create_default_registry
        reg = create_default_registry()
        web = reg.list_by_category("web")
        names = [t.name for t in web]
        assert "tavily_search" in names
        assert "tavily_fetch" in names
        assert "web_browse" in names
        assert "codex_web_research" in names
        assert len(web) == 4


# ── Config Integration ───────────────────────────────────────────

class TestConfigIntegration:
    def test_config_defaults(self):
        from src.agents.config import AgentConfig
        c = AgentConfig()
        assert c.web_tavily is True
        assert c.web_claude_search is False
        assert c.web_openai_search is True
        assert c.web_playwright is True
        assert c.web_codex_research is True
        assert c.web_claude_max_uses == 5

    def test_config_disabling_tavily(self):
        """When web_tavily=False, Anthropic tools should NOT include tavily_search."""
        from src.agents.config import get_agent_config
        config = get_agent_config()
        original = config.web_tavily
        try:
            config.web_tavily = False
            from src.agents.anthropic_agent.tools import get_anthropic_tools
            tools = get_anthropic_tools()
            names = [t["name"] for t in tools]
            assert "tavily_search" not in names
            assert "tavily_fetch" not in names
        finally:
            config.web_tavily = original