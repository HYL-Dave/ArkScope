"""
Tests for the Code Generator (Phase 5b of agent evolution).

Tests cover:
1. Provider detection (OpenAI vs Anthropic from model name)
2. Code extraction (strip markdown code blocks)
3. Generate-and-execute with mocked LLM (success, retry, exhausted)
4. Config integration (code_model, max_retries)
"""

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from src.tools.code_generator import (
    _detect_provider,
    _extract_code,
    generate_and_execute,
)
from src.tools.code_executor import CodeExecutionResult


# ============================================================
# Provider Detection Tests
# ============================================================

class TestDetectProvider:
    def test_gpt_detected_as_openai(self):
        assert _detect_provider("gpt-5.2") == "openai"

    def test_gpt_mini_detected_as_openai(self):
        assert _detect_provider("gpt-5-mini") == "openai"

    def test_claude_detected_as_anthropic(self):
        assert _detect_provider("claude-sonnet-4-5-20250929") == "anthropic"

    def test_claude_opus_detected_as_anthropic(self):
        assert _detect_provider("claude-opus-4-6") == "anthropic"

    def test_o_series_detected_as_openai(self):
        assert _detect_provider("o3-mini") == "openai"
        assert _detect_provider("o4-mini") == "openai"

    def test_unknown_defaults_to_anthropic(self):
        assert _detect_provider("some-custom-model") == "anthropic"


# ============================================================
# Code Extraction Tests
# ============================================================

class TestExtractCode:
    def test_plain_code_unchanged(self):
        code = 'print("hello")'
        assert _extract_code(code) == code

    def test_markdown_python_stripped(self):
        text = '```python\nprint("hello")\n```'
        assert _extract_code(text) == 'print("hello")'

    def test_markdown_no_lang_stripped(self):
        text = '```\nprint("hello")\n```'
        assert _extract_code(text) == 'print("hello")'

    def test_whitespace_trimmed(self):
        text = '  \n  print("hello")  \n  '
        assert _extract_code(text) == 'print("hello")'

    def test_multiline_code_block(self):
        text = '```python\nx = 1\ny = 2\nprint(x + y)\n```'
        assert _extract_code(text) == 'x = 1\ny = 2\nprint(x + y)'

    def test_empty_string(self):
        assert _extract_code("") == ""
        assert _extract_code("   ") == ""


# ============================================================
# Generate-and-Execute Tests (mocked LLM)
# ============================================================

class TestGenerateAndExecute:
    """Tests with mocked LLM calls to avoid real API calls."""

    @patch("src.tools.code_generator._call_llm")
    def test_simple_task_succeeds(self, mock_llm):
        """LLM generates valid code → executes successfully."""
        mock_llm.return_value = 'print("result: 42")'

        result = generate_and_execute(
            task="Calculate 6 * 7",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is True
        assert "result: 42" in result.output
        assert result.generated_code == 'print("result: 42")'

    @patch("src.tools.code_generator._call_llm")
    def test_error_correction_retry(self, mock_llm):
        """First code errors → LLM fixes → succeeds on retry."""
        # First call: bad code (NameError)
        # Second call: fixed code
        mock_llm.side_effect = [
            'print(undefined_var)',
            'print("fixed: 42")',
        ]

        result = generate_and_execute(
            task="Print 42",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is True
        assert "fixed: 42" in result.output
        assert mock_llm.call_count == 2

    @patch("src.tools.code_generator._call_llm")
    def test_max_retries_exhausted(self, mock_llm):
        """All retries fail → returns last error."""
        mock_llm.return_value = 'raise ValueError("always fails")'

        result = generate_and_execute(
            task="This will fail",
            code_model="claude-opus-4-6",
            max_retries=2,
        )
        assert result.success is False
        assert "failed after" in result.error
        # 1 initial + 2 retries = 3 calls
        assert mock_llm.call_count == 3

    @patch("src.tools.code_generator._call_llm")
    def test_generated_code_in_result(self, mock_llm):
        """Result contains the generated code."""
        mock_llm.return_value = 'x = 1\nprint(x)'

        result = generate_and_execute(
            task="Print 1",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.generated_code == 'x = 1\nprint(x)'

    @patch("src.tools.code_generator._call_llm")
    def test_data_json_passed_through(self, mock_llm):
        """Data injection works in code gen mode."""
        mock_llm.return_value = 'print(data["value"] * 2)'

        result = generate_and_execute(
            task="Double the value",
            data_json='{"value": 21}',
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is True
        assert "42" in result.output

    @patch("src.tools.code_generator._call_llm")
    def test_ast_validation_still_applies(self, mock_llm):
        """Generated code with blocked imports fails validation and retries."""
        # First: blocked import, second: fixed
        mock_llm.side_effect = [
            'import os\nprint(os.getcwd())',
            'print("safe code")',
        ]

        result = generate_and_execute(
            task="Show current dir",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is True
        assert "safe code" in result.output
        assert mock_llm.call_count == 2

    @patch("src.tools.code_generator._call_llm")
    def test_markdown_code_block_stripped(self, mock_llm):
        """LLM output wrapped in markdown is stripped before execution."""
        mock_llm.return_value = '```python\nprint("unwrapped")\n```'

        result = generate_and_execute(
            task="Print something",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is True
        assert "unwrapped" in result.output

    @patch("src.tools.code_generator._call_llm")
    def test_empty_code_returns_error(self, mock_llm):
        """Empty generated code returns error."""
        mock_llm.return_value = ""

        result = generate_and_execute(
            task="Do something",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is False
        assert "empty code" in result.error

    @patch("src.tools.code_generator._call_llm")
    def test_llm_call_failure(self, mock_llm):
        """LLM API error returns graceful error."""
        mock_llm.side_effect = Exception("API rate limit exceeded")

        result = generate_and_execute(
            task="Calculate something",
            code_model="claude-opus-4-6",
            max_retries=1,
        )
        assert result.success is False
        assert "Code generation failed" in result.error

    @patch("src.tools.code_generator._call_llm")
    @patch("src.tools.code_generator._resolve_code_model")
    def test_config_code_model_used(self, mock_resolve, mock_llm):
        """Uses config code_model when not specified."""
        mock_resolve.return_value = "claude-sonnet-4-5-20250929"
        mock_llm.return_value = 'print("from config model")'

        result = generate_and_execute(
            task="Test config",
            code_model="",  # empty = use config
            max_retries=1,
        )
        mock_resolve.assert_called_once()
        assert result.success is True

    @patch("src.tools.code_generator._call_llm")
    def test_data_preview_in_prompt(self, mock_llm):
        """Data preview is included in the LLM prompt."""
        mock_llm.return_value = 'print("ok")'
        data = '{"prices": [100, 200, 300]}'

        generate_and_execute(
            task="Analyze prices",
            data_json=data,
            code_model="claude-opus-4-6",
            max_retries=1,
        )

        # Check that the first message to LLM includes data preview
        call_args = mock_llm.call_args
        messages = call_args[0][0]
        assert "prices" in messages[0]["content"]

    @patch("src.tools.code_generator._call_llm")
    def test_error_feedback_in_messages(self, mock_llm):
        """Error feedback is properly sent to LLM for correction."""
        mock_llm.side_effect = [
            'x = 1 / 0',      # First: will raise ZeroDivisionError
            'print("fixed")',  # Second: fixed
        ]

        result = generate_and_execute(
            task="Calculate",
            code_model="claude-opus-4-6",
            max_retries=1,
        )

        # Check second call includes error feedback
        second_call = mock_llm.call_args_list[1]
        messages = second_call[0][0]
        # Should have 3 messages: original task, assistant (bad code), user (error feedback)
        assert len(messages) == 3
        assert "error" in messages[2]["content"].lower()


# ============================================================
# Task Mode Integration Tests (via code_executor)
# ============================================================

class TestTaskMode:
    """Test that code_executor properly delegates task mode."""

    @patch("src.tools.code_generator.generate_and_execute")
    def test_task_delegates_to_generator(self, mock_gen):
        """execute_python_code(task="...") delegates to generate_and_execute."""
        from src.tools.code_executor import execute_python_code
        mock_gen.return_value = CodeExecutionResult(
            success=True, output="delegated\n", error="",
            execution_time=0.5, generated_code='print("delegated")',
        )

        result = execute_python_code(task="Test delegation")
        mock_gen.assert_called_once()
        assert result.success is True
        assert "delegated" in result.output

    def test_code_takes_precedence_over_task(self):
        """When both code and task are provided, code is used (task ignored)."""
        from src.tools.code_executor import execute_python_code
        result = execute_python_code(
            code='print("direct")',
            task="This should be ignored",
        )
        assert result.success is True
        assert "direct" in result.output

    def test_empty_task_uses_code(self):
        """Empty task string falls through to normal code execution."""
        from src.tools.code_executor import execute_python_code
        result = execute_python_code(
            code='print("code mode")',
            task="",
        )
        assert result.success is True
        assert "code mode" in result.output