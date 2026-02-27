"""
Regression tests for agent tool-calling behaviour (Issue C).

Tests cover:
1. System prompt contains mandatory calculation guidance
2. Tool descriptions emphasise task mode and forbid mental math
3. Tool vs subagent boundary is clearly delineated in prompt
4. Deterministic mock: agent dispatch routes execute_python_analysis correctly
5. OpenAI function schema advertises task as preferred parameter
"""

import json

import pytest

from src.agents.shared.prompts import SYSTEM_PROMPT


# ============================================================
# Prompt Guidance — mandatory calculation rules
# ============================================================

class TestPromptCalculationGuidance:
    """System prompt MUST contain explicit rules that forbid mental math."""

    def test_mandatory_tool_usage_keyword(self):
        """Prompt explicitly says ALWAYS use execute_python_analysis."""
        assert "ALWAYS use execute_python_analysis" in SYSTEM_PROMPT

    def test_forbids_mental_math(self):
        """Prompt forbids estimating or calculating mentally."""
        upper = SYSTEM_PROMPT.upper()
        assert "DO NOT ESTIMATE" in upper or "DO NOT CALCULATE MENTALLY" in upper

    def test_wrong_vs_right_example(self):
        """Prompt has a WRONG/RIGHT contrast to anchor expected behaviour."""
        assert "WRONG:" in SYSTEM_PROMPT
        assert "RIGHT:" in SYSTEM_PROMPT
        # The RIGHT example must reference the tool
        right_idx = SYSTEM_PROMPT.index("RIGHT:")
        right_line = SYSTEM_PROMPT[right_idx:right_idx + 200]
        assert "execute_python_analysis" in right_line

    def test_task_mode_emphasized(self):
        """Prompt recommends task (natural language) over code."""
        assert "task" in SYSTEM_PROMPT.lower()
        # Must mention auto-retry
        assert "retries" in SYSTEM_PROMPT.lower() or "retry" in SYSTEM_PROMPT.lower()

    def test_section_header_present(self):
        """Dedicated section header exists for code execution rules."""
        assert "CODE EXECUTION" in SYSTEM_PROMPT


# ============================================================
# Tool vs Subagent boundary in prompt
# ============================================================

class TestToolSubagentBoundary:
    """Prompt must clearly distinguish execute_python_analysis from code_analyst."""

    def test_subagent_section_exists(self):
        """SUBAGENT DELEGATION section is present."""
        assert "SUBAGENT DELEGATION" in SYSTEM_PROMPT

    def test_tool_vs_subagent_guidance(self):
        """Prompt has explicit TOOL vs SUBAGENT guidance."""
        assert "TOOL vs SUBAGENT" in SYSTEM_PROMPT

    def test_direct_tool_for_single_calculation(self):
        """Prompt routes single calculations to the tool, not subagent."""
        # Find the guidance section
        idx = SYSTEM_PROMPT.find("TOOL vs SUBAGENT")
        assert idx != -1
        section = SYSTEM_PROMPT[idx:idx + 600]
        # Should mention "direct" for single calculation
        assert "direct" in section.lower()
        # Should mention code_analyst only for multi-step
        assert "code_analyst" in section

    def test_rule_of_thumb_present(self):
        """There's a clear rule of thumb for the decision."""
        assert "rule of thumb" in SYSTEM_PROMPT.lower() or "Rule of thumb" in SYSTEM_PROMPT


# ============================================================
# Tool description quality (all 3 surfaces)
# ============================================================

class TestToolDescriptions:
    """Tool descriptions across registry + both bridges must emphasise task mode."""

    def test_registry_description_prefers_task(self):
        """Registry tool description says PREFERRED for task param."""
        from src.tools.registry import create_default_registry
        reg = create_default_registry()
        tool = reg.get("execute_python_analysis")
        assert tool is not None
        assert "PREFERRED" in tool.description

    def test_registry_description_forbids_mental_math(self):
        """Registry description says do not calculate mentally."""
        from src.tools.registry import create_default_registry
        reg = create_default_registry()
        tool = reg.get("execute_python_analysis")
        assert "mentally" in tool.description.lower()

    def test_registry_task_param_preferred(self):
        """Registry task parameter description mentions PREFERRED."""
        from src.tools.registry import create_default_registry
        reg = create_default_registry()
        tool = reg.get("execute_python_analysis")
        task_param = next(p for p in tool.parameters if p.name == "task")
        assert "PREFERRED" in task_param.description

    def test_anthropic_description_prefers_task(self):
        """Anthropic bridge tool description says PREFERRED."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        tool = next(t for t in tools if t["name"] == "execute_python_analysis")
        assert "PREFERRED" in tool["description"]

    def test_anthropic_task_param_preferred(self):
        """Anthropic bridge task parameter says PREFERRED."""
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        tools = get_anthropic_tools()
        tool = next(t for t in tools if t["name"] == "execute_python_analysis")
        task_desc = tool["input_schema"]["properties"]["task"]["description"]
        assert "PREFERRED" in task_desc

    def test_openai_tool_description_prefers_task(self):
        """OpenAI tool description (from docstring) mentions PREFERRED."""
        from unittest.mock import MagicMock
        from src.agents.openai_agent.tools import create_openai_tools
        dal = MagicMock()
        tools = create_openai_tools(dal)
        # Find the execute_python_analysis tool by name attribute
        tool = next(
            (t for t in tools if getattr(t, "name", "").endswith("execute_python_analysis")),
            None,
        )
        assert tool is not None, "execute_python_analysis not found in OpenAI tools"
        # The tool description is derived from the docstring
        desc = getattr(tool, "description", "") or ""
        assert "PREFERRED" in desc or "preferred" in desc.lower(), (
            f"OpenAI tool description should mention PREFERRED: {desc[:200]}"
        )

    def test_openai_tool_description_forbids_mental_math(self):
        """OpenAI tool description tells model not to calculate mentally."""
        from unittest.mock import MagicMock
        from src.agents.openai_agent.tools import create_openai_tools
        dal = MagicMock()
        tools = create_openai_tools(dal)
        tool = next(
            (t for t in tools if getattr(t, "name", "").endswith("execute_python_analysis")),
            None,
        )
        assert tool is not None
        desc = getattr(tool, "description", "") or ""
        assert "mentally" in desc.lower(), (
            f"OpenAI tool description should forbid mental math: {desc[:200]}"
        )


# ============================================================
# Deterministic dispatch: execute_python_analysis routing
# ============================================================

class TestExecutePythonAnalysisDispatch:
    """Mock-based tests verifying tool dispatch works correctly."""

    def test_task_mode_invokes_code_generator(self):
        """When task is provided (no code), code generator is called."""
        from unittest.mock import patch
        from src.tools.code_executor import CodeExecutionResult

        mock_result = CodeExecutionResult(
            success=True,
            output="Sharpe ratio: 1.42",
            error="",
            execution_time=0.5,
            generated_code="import pandas as pd\n...",
        )
        with patch(
            "src.tools.code_generator.generate_and_execute",
            return_value=mock_result,
        ) as mock_gen:
            from src.tools.code_executor import execute_python_code
            result = execute_python_code(
                task="Calculate Sharpe ratio",
                data_json='{"prices": [100, 101, 99]}',
            )
            mock_gen.assert_called_once()
            assert result.success is True

    def test_code_mode_skips_code_generator(self):
        """When code is provided, code generator is NOT called."""
        from unittest.mock import patch

        with patch(
            "src.tools.code_generator.generate_and_execute",
        ) as mock_gen:
            from src.tools.code_executor import execute_python_code
            result = execute_python_code(code='print("hello")')
            mock_gen.assert_not_called()
            assert result.success is True
            assert "hello" in result.output

    def test_task_mode_passes_data_json(self):
        """data_json is forwarded to the code generator."""
        from unittest.mock import patch
        from src.tools.code_executor import CodeExecutionResult

        mock_result = CodeExecutionResult(
            success=True, output="ok", error="", execution_time=0.1,
        )
        with patch(
            "src.tools.code_generator.generate_and_execute",
            return_value=mock_result,
        ) as mock_gen:
            from src.tools.code_executor import execute_python_code
            execute_python_code(
                task="Summarize data",
                data_json='{"tickers": ["NVDA", "AAPL"]}',
            )
            call_kwargs = mock_gen.call_args
            # data_json should be in the call
            assert "tickers" in str(call_kwargs)

    def test_empty_code_runs_as_noop(self):
        """Empty code (no task) runs as a no-op — valid but empty output."""
        from src.tools.code_executor import execute_python_code
        result = execute_python_code(code="", task="")
        # Empty Python script is valid — subprocess exits 0
        assert result.success is True
        assert result.output == ""


# ============================================================
# OpenAI function schema structure
# ============================================================

class TestOpenAIFunctionSchema:
    """OpenAI function tool schema must list task before code."""

    def test_tool_registered_in_openai_bridge(self):
        """execute_python_analysis is available in OpenAI tools list."""
        from unittest.mock import MagicMock
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(MagicMock())
        names = [getattr(t, "name", "") for t in tools]
        assert any("execute_python_analysis" in n for n in names)

    def test_task_param_listed_before_code_in_description(self):
        """In the OpenAI tool description, task is mentioned before code."""
        from unittest.mock import MagicMock
        from src.agents.openai_agent.tools import create_openai_tools
        tools = create_openai_tools(MagicMock())
        tool = next(
            (t for t in tools if getattr(t, "name", "").endswith("execute_python_analysis")),
            None,
        )
        assert tool is not None
        desc = getattr(tool, "description", "") or ""
        task_pos = desc.lower().find("task")
        code_pos = desc.lower().find("code")
        assert task_pos != -1 and code_pos != -1
        assert task_pos < code_pos, (
            f"task ({task_pos}) should appear before code ({code_pos}) in description"
        )
