"""
Tests for the local browser tool and its agent bridges.

All Playwright calls are mocked; no live network is used.
"""

import json
import re
from unittest.mock import MagicMock, patch

def _unwrap(result: str) -> str:
    """Strip <tool_output> wrapping (Phase 15) to get raw JSON."""
    m = re.search(r"<tool_output[^>]*>\n(.*)\n</tool_output>", result, re.DOTALL)
    return m.group(1) if m else result


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
        """The Anthropic bridge exposes only the surviving local browser tool."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = {t["name"] for t in tools}
        assert "web_browse" in names
        assert {"tavily_search", "tavily_fetch"}.isdisjoint(names)

    def test_anthropic_tools_excludes_claude_search(self):
        """Claude web search server tool should NOT be in get_anthropic_tools()
        (it's added in the agent runner, not the tools list)."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = [t["name"] for t in tools]
        assert "web_search" not in names

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
        """The OpenAI bridge exposes only the surviving local browser tool."""
        from src.tools.data_access import DataAccessLayer
        from src.agents.openai_agent.tools import create_openai_tools
        dal = DataAccessLayer()
        tools = create_openai_tools(dal)
        names = {getattr(t, "name", "") for t in tools}
        assert "tool_web_browse" in names
        assert {"tool_tavily_search", "tool_tavily_fetch"}.isdisjoint(names)

    def test_registry_web_tools(self):
        """ToolRegistry should register only the local browser tool."""
        from src.tools.registry import create_default_registry
        reg = create_default_registry()
        web = reg.list_by_category("web")
        names = {t.name for t in web}
        assert names == {"web_browse"}


# ── Config Integration ───────────────────────────────────────────

class TestConfigIntegration:
    def test_config_defaults(self):
        from src.agents.config import AgentConfig
        c = AgentConfig()
        assert not hasattr(c, "web_tavily")
        assert c.web_claude_search is False
        assert c.web_openai_search is True
        assert c.web_playwright is True
        assert c.web_claude_max_uses == 5
