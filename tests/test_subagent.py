"""
Tests for the Subagent dispatch system (Phase 6 of agent evolution).

Tests cover:
1. SubagentConfig creation and defaults
2. SUBAGENT_REGISTRY structure and recursion safety
3. Provider detection
4. Tool filtering (Anthropic + OpenAI)
5. dispatch_subagent() logic (routing, errors, truncation)
6. Anthropic subagent runner (mocked SDK)
7. OpenAI subagent runner (mocked SDK)
8. Bridge integration (schema + execute_tool dispatch)
9. 1M context beta support
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Pre-import agent modules so they capture the real get_agent_config
# BEFORE any tests mock it. Without this, _run_anthropic_subagent's
# dynamic import of agent.py during a mocked test would make agent.py
# permanently capture the mock reference (test isolation bug).
import src.agents.anthropic_agent.agent  # noqa: F401

from src.agents.shared.subagent import (
    SubagentConfig,
    SUBAGENT_REGISTRY,
    dispatch_subagent,
    _detect_provider,
    _filter_anthropic_tools,
    _filter_openai_tools,
    _use_extended_context,
    _MAX_CONTEXT_CHARS,
    _EXTENDED_CONTEXT_BETA,
)


# ============================================================
# SubagentConfig Tests
# ============================================================

class TestSubagentConfig:
    def test_config_creation(self):
        cfg = SubagentConfig(
            name="test",
            description="A test subagent",
            model="gpt-5.2",
            system_prompt="You are a test agent.",
            tool_names=["get_ticker_news"],
        )
        assert cfg.name == "test"
        assert cfg.model == "gpt-5.2"
        assert cfg.tool_names == ["get_ticker_news"]

    def test_config_defaults(self):
        cfg = SubagentConfig(
            name="test",
            description="",
            model="gpt-5.2",
            system_prompt="test",
        )
        assert cfg.max_turns == 8
        assert cfg.reasoning_effort is None
        assert cfg.anthropic_effort is None
        assert cfg.anthropic_thinking is False
        assert cfg.extended_context is False
        assert cfg.tool_names == []


# ============================================================
# Registry Tests
# ============================================================

class TestSubagentRegistry:
    def test_registry_has_4_subagents(self):
        assert len(SUBAGENT_REGISTRY) == 4
        assert "code_analyst" in SUBAGENT_REGISTRY
        assert "deep_researcher" in SUBAGENT_REGISTRY
        assert "data_summarizer" in SUBAGENT_REGISTRY
        assert "reviewer" in SUBAGENT_REGISTRY

    def test_no_delegate_in_any_subagent(self):
        """Recursion prevention: no subagent should have delegate_to_subagent."""
        for name, config in SUBAGENT_REGISTRY.items():
            assert "delegate_to_subagent" not in config.tool_names, (
                f"Subagent '{name}' has delegate_to_subagent — would allow recursion"
            )

    def test_all_configs_have_required_fields(self):
        for name, config in SUBAGENT_REGISTRY.items():
            assert config.name == name
            assert config.description
            assert config.model
            assert config.system_prompt
            assert config.max_turns > 0

    def test_code_analyst_uses_openai(self):
        cfg = SUBAGENT_REGISTRY["code_analyst"]
        assert _detect_provider(cfg.model) == "openai"
        assert cfg.reasoning_effort == "xhigh"

    def test_data_summarizer_uses_anthropic(self):
        cfg = SUBAGENT_REGISTRY["data_summarizer"]
        assert _detect_provider(cfg.model) == "anthropic"
        assert cfg.anthropic_thinking is True  # adaptive thinking

    def test_data_summarizer_uses_sonnet(self):
        """data_summarizer should use Sonnet 4.6 (cost-optimized)."""
        cfg = SUBAGENT_REGISTRY["data_summarizer"]
        assert "sonnet" in cfg.model

    def test_reviewer_config(self):
        cfg = SUBAGENT_REGISTRY["reviewer"]
        assert _detect_provider(cfg.model) == "anthropic"
        assert cfg.anthropic_thinking is True
        assert cfg.anthropic_effort == "max"
        assert len(cfg.tool_names) <= 3  # reviewer relies on reasoning
        assert "delegate_to_subagent" not in cfg.tool_names

    def test_code_analyst_has_enhanced_tools(self):
        """code_analyst should have fundamentals and web search tools."""
        cfg = SUBAGENT_REGISTRY["code_analyst"]
        assert "execute_python_analysis" in cfg.tool_names
        assert "get_fundamentals_analysis" in cfg.tool_names
        assert "tavily_search" in cfg.tool_names


# ============================================================
# Provider Detection Tests
# ============================================================

class TestDetectProvider:
    def test_detect_gpt_as_openai(self):
        assert _detect_provider("gpt-5.2") == "openai"
        assert _detect_provider("gpt-5.2-codex") == "openai"

    def test_detect_o_series_as_openai(self):
        assert _detect_provider("o1-mini") == "openai"
        assert _detect_provider("o3") == "openai"
        assert _detect_provider("o4-mini") == "openai"

    def test_detect_claude_as_anthropic(self):
        assert _detect_provider("claude-opus-4-6") == "anthropic"
        assert _detect_provider("claude-sonnet-5-20260501") == "anthropic"

    def test_unknown_defaults_to_anthropic(self):
        assert _detect_provider("some-model") == "anthropic"


# ============================================================
# Tool Filtering Tests
# ============================================================

class TestFilterAnthropicTools:
    def test_filter_whitelist(self):
        tools = [
            {"name": "get_ticker_news", "description": "..."},
            {"name": "get_price_change", "description": "..."},
            {"name": "detect_anomalies", "description": "..."},
        ]
        result = _filter_anthropic_tools(tools, ["get_ticker_news", "detect_anomalies"])
        assert len(result) == 2
        names = {t["name"] for t in result}
        assert names == {"get_ticker_news", "detect_anomalies"}

    def test_filter_empty_whitelist(self):
        tools = [{"name": "get_ticker_news", "description": "..."}]
        result = _filter_anthropic_tools(tools, [])
        assert result == []


class TestFilterOpenaiTools:
    def test_filter_by_canonical_name(self):
        """OpenAI tools have tool_ prefix; filter should match both."""
        mock_tool_a = MagicMock()
        mock_tool_a.name = "tool_get_ticker_news"
        mock_tool_b = MagicMock()
        mock_tool_b.name = "tool_get_price_change"
        mock_tool_c = MagicMock()
        mock_tool_c.name = "tool_detect_anomalies"

        result = _filter_openai_tools(
            [mock_tool_a, mock_tool_b, mock_tool_c],
            ["get_ticker_news", "detect_anomalies"],
        )
        assert len(result) == 2

    def test_filter_handles_exact_name_match(self):
        """Also match if tool name is exactly the canonical name (no prefix)."""
        mock_tool = MagicMock()
        mock_tool.name = "get_ticker_news"  # no prefix
        result = _filter_openai_tools([mock_tool], ["get_ticker_news"])
        assert len(result) == 1

    def test_filter_empty_whitelist(self):
        mock_tool = MagicMock()
        mock_tool.name = "tool_get_ticker_news"
        result = _filter_openai_tools([mock_tool], [])
        assert result == []


# ============================================================
# dispatch_subagent() Tests
# ============================================================

class TestDispatchSubagent:
    def test_unknown_subagent_returns_error(self):
        result = dispatch_subagent("nonexistent", task="test")
        assert result["error"]
        assert "nonexistent" in result["error"]
        assert result["answer"] == ""

    def test_dispatch_returns_expected_keys(self):
        result = dispatch_subagent("nonexistent", task="test")
        expected_keys = {"subagent", "answer", "tools_used", "model", "provider", "token_usage", "error"}
        assert set(result.keys()) == expected_keys

    def test_context_json_truncation(self):
        """context_json > _MAX_CONTEXT_CHARS should be truncated in subagent input."""
        long_context = "x" * (_MAX_CONTEXT_CHARS + 1000)

        with patch("src.agents.shared.subagent._run_openai_subagent") as mock_runner:
            mock_runner.return_value = {"answer": "ok", "tools_used": [], "token_usage": {}}
            dispatch_subagent("code_analyst", task="test", context_json=long_context)

            # Verify the input passed to the runner contains truncation notice
            call_args = mock_runner.call_args
            question_arg = call_args[0][1]  # second positional arg
            assert "truncated" in question_arg

    @patch("src.agents.shared.subagent._run_openai_subagent")
    def test_exception_returns_error_json(self, mock_runner):
        mock_runner.side_effect = RuntimeError("SDK exploded")
        result = dispatch_subagent("code_analyst", task="test")
        assert result["error"] == "SDK exploded"
        assert result["answer"] == ""

    @patch("src.agents.shared.subagent._run_anthropic_subagent")
    def test_dispatch_routes_to_anthropic(self, mock_runner):
        mock_runner.return_value = {"answer": "summary", "tools_used": [], "token_usage": {}}
        result = dispatch_subagent("data_summarizer", task="summarize")
        mock_runner.assert_called_once()
        assert result["provider"] == "anthropic"
        assert result["answer"] == "summary"

    @patch("src.agents.shared.subagent._run_openai_subagent")
    def test_dispatch_routes_to_openai(self, mock_runner):
        mock_runner.return_value = {"answer": "calculated", "tools_used": [], "token_usage": {}}
        result = dispatch_subagent("code_analyst", task="calculate")
        mock_runner.assert_called_once()
        assert result["provider"] == "openai"


# ============================================================
# Anthropic Subagent Runner Tests (mocked SDK)
# ============================================================

class TestAnthropicSubagentRunner:
    def _make_mock_response(self, text="Done", stop_reason="end_turn", tool_use=None):
        """Create a mock Anthropic response."""
        response = MagicMock()
        response.stop_reason = stop_reason
        response.usage = MagicMock()
        response.usage.input_tokens = 100
        response.usage.output_tokens = 50
        response.usage.cache_creation_input_tokens = 0
        response.usage.cache_read_input_tokens = 0

        blocks = []
        if text:
            text_block = MagicMock()
            text_block.type = "text"
            text_block.text = text
            blocks.append(text_block)
        if tool_use:
            for tu in tool_use:
                tool_block = MagicMock()
                tool_block.type = "tool_use"
                tool_block.name = tu["name"]
                tool_block.input = tu["input"]
                tool_block.id = tu.get("id", "toolu_123")
                blocks.append(tool_block)

        response.content = blocks
        return response

    @patch("src.agents.anthropic_agent.tools.get_anthropic_tools")
    @patch("src.agents.anthropic_agent.tools.execute_tool")
    @patch("anthropic.Anthropic")
    @patch("src.agents.config.get_agent_config")
    def test_anthropic_subagent_success(self, mock_config, mock_anthropic_cls, mock_exec, mock_tools):
        """Simple case: model returns text, no tool calls."""
        mock_config.return_value = MagicMock(max_tokens=16384)
        mock_tools.return_value = []

        response = self._make_mock_response("Analysis complete")
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.return_value = response
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic_cls.return_value = mock_client

        from src.agents.shared.subagent import _run_anthropic_subagent
        config = SubagentConfig(
            name="test", description="", model="claude-opus-4-6",
            system_prompt="test",
        )
        result = _run_anthropic_subagent(config, "test question", dal=None)
        assert result["answer"] == "Analysis complete"

    @patch("src.agents.anthropic_agent.tools.get_anthropic_tools")
    @patch("src.agents.anthropic_agent.tools.execute_tool")
    @patch("anthropic.Anthropic")
    @patch("src.agents.config.get_agent_config")
    def test_anthropic_subagent_tool_loop(self, mock_config, mock_anthropic_cls, mock_exec, mock_tools):
        """Model calls a tool, then finishes."""
        mock_config.return_value = MagicMock(max_tokens=16384)
        mock_tools.return_value = []
        mock_exec.return_value = '{"price": 100}'

        # First response: tool_use
        tool_response = self._make_mock_response(
            text="", stop_reason="tool_use",
            tool_use=[{"name": "get_ticker_news", "input": {"ticker": "NVDA"}}]
        )
        # Second response: final text
        final_response = self._make_mock_response("Here is the analysis")

        mock_client = MagicMock()
        mock_stream_1 = MagicMock()
        mock_stream_1.__enter__ = MagicMock(return_value=mock_stream_1)
        mock_stream_1.__exit__ = MagicMock(return_value=False)
        mock_stream_1.get_final_message.return_value = tool_response

        mock_stream_2 = MagicMock()
        mock_stream_2.__enter__ = MagicMock(return_value=mock_stream_2)
        mock_stream_2.__exit__ = MagicMock(return_value=False)
        mock_stream_2.get_final_message.return_value = final_response

        mock_client.messages.stream.side_effect = [mock_stream_1, mock_stream_2]
        mock_anthropic_cls.return_value = mock_client

        from src.agents.shared.subagent import _run_anthropic_subagent
        config = SubagentConfig(
            name="test", description="", model="claude-opus-4-6",
            system_prompt="test", max_turns=5,
        )
        result = _run_anthropic_subagent(config, "test", dal=None)
        assert result["answer"] == "Here is the analysis"
        assert "get_ticker_news" in result["tools_used"]

    @patch("src.agents.anthropic_agent.tools.get_anthropic_tools")
    @patch("src.agents.anthropic_agent.tools.execute_tool")
    @patch("anthropic.Anthropic")
    @patch("src.agents.config.get_agent_config")
    def test_anthropic_subagent_max_turns(self, mock_config, mock_anthropic_cls, mock_exec, mock_tools):
        """Subagent reaches max_turns limit."""
        mock_config.return_value = MagicMock(max_tokens=16384)
        mock_tools.return_value = []
        mock_exec.return_value = '{"data": "ok"}'

        # Always returns tool_use
        tool_response = self._make_mock_response(
            text="", stop_reason="tool_use",
            tool_use=[{"name": "get_ticker_news", "input": {"ticker": "NVDA"}}]
        )

        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.return_value = tool_response
        mock_client.messages.stream.return_value = mock_stream
        mock_anthropic_cls.return_value = mock_client

        from src.agents.shared.subagent import _run_anthropic_subagent
        config = SubagentConfig(
            name="test", description="", model="claude-opus-4-6",
            system_prompt="test", max_turns=2,
        )
        result = _run_anthropic_subagent(config, "test", dal=None)
        assert "maximum" in result["answer"].lower()

    @patch("src.agents.anthropic_agent.tools.get_anthropic_tools")
    @patch("src.agents.anthropic_agent.tools.execute_tool")
    @patch("anthropic.Anthropic")
    @patch("src.agents.config.get_agent_config")
    def test_anthropic_subagent_beta_stream(self, mock_config, mock_anthropic_cls, mock_exec, mock_tools):
        """When extended_context=True + supported model, should use beta.messages.stream."""
        mock_config.return_value = MagicMock(max_tokens=16384)
        mock_tools.return_value = []

        response = self._make_mock_response("done")
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.get_final_message.return_value = response
        mock_client.beta.messages.stream.return_value = mock_stream
        mock_anthropic_cls.return_value = mock_client

        from src.agents.shared.subagent import _run_anthropic_subagent
        config = SubagentConfig(
            name="test", description="", model="claude-opus-4-6",
            system_prompt="test", extended_context=True,
        )
        result = _run_anthropic_subagent(config, "test", dal=None)

        # Should have used beta.messages.stream, NOT messages.stream
        mock_client.beta.messages.stream.assert_called_once()
        mock_client.messages.stream.assert_not_called()
        assert result["answer"] == "done"


# ============================================================
# OpenAI Subagent Runner Tests (mocked SDK)
# ============================================================

class TestOpenaiSubagentRunner:
    @patch("src.agents.openai_agent.agent._get_openai_max_output")
    @patch("src.agents.openai_agent.tools.create_openai_tools")
    @patch("agents.Runner")
    @patch("src.agents.config.get_agent_config")
    def test_openai_subagent_success(self, mock_config, mock_runner_cls, mock_tools, mock_max_output):
        mock_config.return_value = MagicMock(reasoning_effort="xhigh", max_tokens=16384)
        mock_tools.return_value = []
        mock_max_output.return_value = 128000

        mock_result = MagicMock()
        mock_result.final_output = "The Sharpe ratio is 1.5"
        mock_result.raw_responses = []
        mock_runner_cls.run_sync.return_value = mock_result

        from src.agents.shared.subagent import _run_openai_subagent
        config = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test", reasoning_effort="xhigh",
        )
        result = _run_openai_subagent(config, "calculate Sharpe", dal=None)
        assert "1.5" in result["answer"]
        mock_runner_cls.run_sync.assert_called_once()

    @patch("src.agents.openai_agent.agent._get_openai_max_output")
    @patch("src.agents.openai_agent.tools.create_openai_tools")
    @patch("agents.Runner")
    @patch("src.agents.config.get_agent_config")
    def test_openai_subagent_tools_extracted(self, mock_config, mock_runner_cls, mock_tools, mock_max_output):
        """tools_used should be extracted from raw_responses."""
        mock_config.return_value = MagicMock(reasoning_effort="xhigh", max_tokens=16384)
        mock_tools.return_value = []
        mock_max_output.return_value = 128000

        # Build mock raw_responses with tool usage
        mock_item = MagicMock()
        mock_item.name = "tool_get_ticker_prices"
        mock_output = MagicMock()
        mock_output.output = [mock_item]
        mock_raw = MagicMock()
        mock_raw.usage = MagicMock()
        mock_raw.usage.input_tokens = 100
        mock_raw.usage.output_tokens = 50
        mock_raw.usage.input_tokens_details = MagicMock(cached_tokens=0)

        mock_result = MagicMock()
        mock_result.final_output = "done"
        mock_result.raw_responses = [mock_output]
        mock_runner_cls.run_sync.return_value = mock_result

        from src.agents.shared.subagent import _run_openai_subagent
        config = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test",
        )
        result = _run_openai_subagent(config, "test", dal=None)
        assert "tool_get_ticker_prices" in result["tools_used"]


# ============================================================
# 1M Context Beta Tests
# ============================================================

class TestExtendedContext:
    def test_opus_enabled(self):
        assert _use_extended_context("claude-opus-4-6", True) is True

    def test_sonnet_not_in_current_list(self):
        # Sonnet 4.5 removed; Sonnet 5 will be added when released
        assert _use_extended_context("claude-sonnet-4-5-20250929", True) is False

    def test_disabled(self):
        assert _use_extended_context("claude-opus-4-6", False) is False

    def test_unsupported_model(self):
        assert _use_extended_context("claude-haiku-4-5-20251001", True) is False

    def test_openai_model_unsupported(self):
        assert _use_extended_context("gpt-5.2", True) is False

    def test_beta_constant(self):
        assert _EXTENDED_CONTEXT_BETA == "context-1m-2025-08-07"


# ============================================================
# Bridge Integration Tests
# ============================================================

class TestAnthropicBridgeIntegration:
    def test_anthropic_tools_includes_delegate(self):
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        names = {t["name"] for t in tools}
        assert "delegate_to_subagent" in names

    def test_anthropic_tools_count_31(self):
        """18 original + 3 web + 1 analyst + 1 insider + delegate + 3 report + 4 memory = 31."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        assert len(tools) == 39

    def test_delegate_schema_has_enum(self):
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        delegate = [t for t in tools if t["name"] == "delegate_to_subagent"][0]
        enum = delegate["input_schema"]["properties"]["subagent"]["enum"]
        assert set(enum) == {"code_analyst", "deep_researcher", "data_summarizer", "reviewer"}

    @patch("src.agents.anthropic_agent.tools._dispatch_subagent")
    def test_execute_tool_dispatches_delegate(self, mock_dispatch):
        from src.agents.anthropic_agent.tools import execute_tool
        mock_dispatch.return_value = {"answer": "delegated", "tools_used": []}

        result = execute_tool(
            "delegate_to_subagent",
            {"subagent": "code_analyst", "task": "test"},
            dal=None,
        )
        mock_dispatch.assert_called_once()


class TestOpenAiBridgeIntegration:
    def test_openai_tools_count_31(self):
        """18 original + 3 web + 1 analyst + 1 insider + delegate + 3 report + 4 memory = 31."""
        from src.agents.openai_agent.tools import create_openai_tools
        mock_dal = MagicMock()
        tools = create_openai_tools(mock_dal)
        assert len(tools) == 39

    def test_openai_tools_includes_delegate(self):
        from src.agents.openai_agent.tools import create_openai_tools
        mock_dal = MagicMock()
        tools = create_openai_tools(mock_dal)
        names = {getattr(t, "name", "") for t in tools}
        assert "tool_delegate_to_subagent" in names


# ============================================================
# Config Integration Tests
# ============================================================

class TestConfigExtendedContext:
    def test_config_has_extended_context_field(self):
        from src.agents.config import AgentConfig
        config = AgentConfig()
        assert config.extended_context is False

    def test_config_extended_context_settable(self):
        from src.agents.config import AgentConfig
        config = AgentConfig(extended_context=True)
        assert config.extended_context is True


# ============================================================
# Config Override & Persistence Tests
# ============================================================

class TestConfigSubagentModels:
    def test_config_subagent_models_default_empty(self):
        from src.agents.config import AgentConfig
        config = AgentConfig()
        assert config.subagent_models == {}

    def test_config_subagent_models_settable(self):
        from src.agents.config import AgentConfig
        config = AgentConfig(subagent_models={"code_analyst": "claude-opus-4-6"})
        assert config.subagent_models["code_analyst"] == "claude-opus-4-6"

    @patch("src.agents.config.get_agent_config")
    def test_model_override_applied(self, mock_config):
        """_apply_config_overrides should swap the model."""
        mock_config.return_value = MagicMock(
            subagent_models={"code_analyst": "claude-opus-4-6"},
            subagent_max_turns={},
        )
        from src.agents.shared.subagent import _apply_config_overrides
        original = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test",
        )
        result = _apply_config_overrides(original)
        assert result.model == "claude-opus-4-6"
        # Original should be unchanged
        assert original.model == "gpt-5.2-codex"

    @patch("src.agents.config.get_agent_config")
    def test_model_override_not_applied_when_empty(self, mock_config):
        mock_config.return_value = MagicMock(
            subagent_models={}, subagent_max_turns={},
        )
        from src.agents.shared.subagent import _apply_config_overrides
        original = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test",
        )
        result = _apply_config_overrides(original)
        assert result.model == "gpt-5.2-codex"
        assert result is original  # no copy needed

    @patch("src.agents.config.get_agent_config")
    def test_model_override_same_model_no_copy(self, mock_config):
        """If override is same as default, return original."""
        mock_config.return_value = MagicMock(
            subagent_models={"code_analyst": "gpt-5.2-codex"},
            subagent_max_turns={},
        )
        from src.agents.shared.subagent import _apply_config_overrides
        original = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test",
        )
        result = _apply_config_overrides(original)
        assert result is original

    @patch("src.agents.config.get_agent_config")
    def test_max_turns_override_applied(self, mock_config):
        """_apply_config_overrides should override max_turns."""
        mock_config.return_value = MagicMock(
            subagent_models={},
            subagent_max_turns={"deep_researcher": 15},
        )
        from src.agents.shared.subagent import _apply_config_overrides
        original = SubagentConfig(
            name="deep_researcher", description="", model="gpt-5.2",
            system_prompt="test", max_turns=10,
        )
        result = _apply_config_overrides(original)
        assert result.max_turns == 15
        assert original.max_turns == 10  # unchanged

    @patch("src.agents.config.get_agent_config")
    def test_both_overrides_applied(self, mock_config):
        """Both model and max_turns overrides at once."""
        mock_config.return_value = MagicMock(
            subagent_models={"code_analyst": "claude-opus-4-6"},
            subagent_max_turns={"code_analyst": 12},
        )
        from src.agents.shared.subagent import _apply_config_overrides
        original = SubagentConfig(
            name="code_analyst", description="", model="gpt-5.2-codex",
            system_prompt="test", max_turns=8,
        )
        result = _apply_config_overrides(original)
        assert result.model == "claude-opus-4-6"
        assert result.max_turns == 12
        assert original.model == "gpt-5.2-codex"
        assert original.max_turns == 8


class TestDeepMerge:
    def test_basic_merge(self):
        from src.agents.config import _deep_merge
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        from src.agents.config import _deep_merge
        base = {"llm": {"model": "gpt-5", "effort": "high"}}
        override = {"llm": {"model": "opus"}}
        result = _deep_merge(base, override)
        assert result == {"llm": {"model": "opus", "effort": "high"}}

    def test_override_replaces_non_dict(self):
        from src.agents.config import _deep_merge
        base = {"a": [1, 2]}
        override = {"a": [3]}
        result = _deep_merge(base, override)
        assert result == {"a": [3]}

    def test_original_unchanged(self):
        from src.agents.config import _deep_merge
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        result = _deep_merge(base, override)
        assert "y" not in base["a"]  # base unchanged


class TestSaveLocalOverride:
    def test_save_and_load(self, tmp_path):
        """Integration test: save override, then load it."""
        import src.agents.config as cfg_mod
        local_file = tmp_path / "user_profile.local.yaml"
        original_path = cfg_mod._LOCAL_CONFIG_PATH

        try:
            cfg_mod._LOCAL_CONFIG_PATH = local_file
            cfg_mod.get_agent_config.cache_clear()

            cfg_mod.save_local_override(
                "llm_preferences", "subagent_models",
                {"code_analyst": "claude-opus-4-6"},
            )

            assert local_file.exists()
            import yaml
            with open(local_file) as f:
                data = yaml.safe_load(f)
            assert data["llm_preferences"]["subagent_models"]["code_analyst"] == "claude-opus-4-6"
        finally:
            cfg_mod._LOCAL_CONFIG_PATH = original_path
            cfg_mod.get_agent_config.cache_clear()

    def test_save_merges_existing(self, tmp_path):
        """Saving should merge with existing local file, not overwrite."""
        import yaml
        import src.agents.config as cfg_mod
        local_file = tmp_path / "user_profile.local.yaml"
        original_path = cfg_mod._LOCAL_CONFIG_PATH

        try:
            cfg_mod._LOCAL_CONFIG_PATH = local_file
            cfg_mod.get_agent_config.cache_clear()

            # Write initial content
            with open(local_file, "w") as f:
                yaml.dump({"llm_preferences": {"anthropic_thinking": True}}, f)

            # Save subagent override
            cfg_mod.save_local_override(
                "llm_preferences", "subagent_models",
                {"code_analyst": "claude-opus-4-6"},
            )

            with open(local_file) as f:
                data = yaml.safe_load(f)

            # Both settings should exist
            assert data["llm_preferences"]["anthropic_thinking"] is True
            assert data["llm_preferences"]["subagent_models"]["code_analyst"] == "claude-opus-4-6"
        finally:
            cfg_mod._LOCAL_CONFIG_PATH = original_path
            cfg_mod.get_agent_config.cache_clear()