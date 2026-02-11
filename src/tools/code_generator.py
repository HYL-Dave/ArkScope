"""
Code Generator — LLM-powered code generation with error-correcting retry loop.

Generates Python code from a task description using a configurable coding model,
then executes it via code_executor. If execution fails, feeds the error back to
the LLM for correction and retries (up to max_retries times).

This is the "coding subagent" embedded in the execute_python_analysis tool.
The main agent can call execute_python_analysis(task="...") and the coding model
handles code generation + error correction transparently.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional

from .code_executor import (
    CodeExecutionResult,
    DEFAULT_BLOCKED_MODULES,
    validate_code,
    _execute_foreground,
    _execute_background,
    _PREAMBLE,
)

logger = logging.getLogger(__name__)

# ── System prompt for code generation ────────────────────────

CODE_GEN_SYSTEM_PROMPT = """\
You are a Python code generator for financial data analysis.
Generate ONLY executable Python code. No markdown, no explanations, no code blocks.

Environment:
- A variable `data` is pre-loaded with input data (dict or list from JSON)
- Available packages: numpy, pandas, scipy, json, math, statistics, datetime, collections
- Blocked (DO NOT import): os, sys, subprocess, socket, http, urllib, requests, shutil, pathlib
- Print results to stdout using print()

Rules:
1. Output ONLY the Python code, nothing else
2. Always print() results so they appear in stdout
3. Handle edge cases (empty data, missing keys) gracefully
4. Use descriptive variable names
5. If data is empty or not provided, use inline sample data or explain via print()
"""


# ── Provider detection ───────────────────────────────────────

def _detect_provider(model: str) -> str:
    """Auto-detect provider from model name prefix."""
    if model.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "anthropic"


# ── LLM API calls ───────────────────────────────────────────
# 各 provider 讀取對應的 config 設定：
#   OpenAI  → config.reasoning_effort + model max output
#   Anthropic → config.anthropic_effort + config.anthropic_thinking + model max output
# 設計決策：code gen 一律給模型最大 output 空間（不受主 agent 的 reasoning off 限制）
# 因為 (1) reasoning tokens 從中扣，空間不足會截斷推理
#       (2) 按實際用量計費，設高不多花錢
#       (3) code gen 有 retry 機制，但 token 截斷無法修正

def _call_openai(messages: List[dict], model: str, system: str) -> str:
    """Call OpenAI chat completion API with reasoning from config.

    Code generation 一律給模型最大 output 空間 — reasoning tokens + visible output
    都從 max_completion_tokens 扣，設高不多花錢（按實際用量計費）。
    """
    from openai import OpenAI
    from ..agents.config import get_agent_config
    from ..agents.openai_agent.agent import _get_openai_max_output

    config = get_agent_config()
    effort = config.reasoning_effort

    kwargs: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "max_completion_tokens": _get_openai_max_output(model),
    }

    # reasoning 參數 (Codex 模型要求必設)
    if effort != "none":
        from openai.types.shared import Reasoning
        kwargs["reasoning"] = Reasoning(effort=effort)
    else:
        kwargs["temperature"] = 0.0

    client = OpenAI()
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _call_anthropic(messages: List[dict], model: str, system: str) -> str:
    """Call Anthropic messages API with effort + thinking from config.

    Code generation 一律給模型最大 output 空間 — thinking 開啟時 budget 從中扣，
    關閉時也直接給 model max（code 長度不可預測，不限制自由度）。
    """
    from anthropic import Anthropic
    from ..agents.config import get_agent_config
    from ..agents.anthropic_agent.agent import (
        _get_model_max_output,
        _supports_effort,
        _build_thinking_param,
    )

    config = get_agent_config()

    # thinking 開啟: _build_thinking_param 自動推導 (已用 model max)
    # thinking 關閉: 也用 model max，給 code gen 最大自由度
    thinking_param, _ = _build_thinking_param(
        model, config.anthropic_thinking, config
    )
    effective_max_tokens = _get_model_max_output(model)

    kwargs: dict = {
        "model": model,
        "system": system,
        "messages": messages,
        "max_tokens": effective_max_tokens,
    }

    # effort (Opus 4.5+ only)
    if config.anthropic_effort and _supports_effort(model):
        kwargs["output_config"] = {"effort": config.anthropic_effort}

    # thinking
    if thinking_param:
        kwargs["thinking"] = thinking_param
    else:
        kwargs["temperature"] = 0.0  # thinking 模式不支援 temperature

    client = Anthropic()
    response = client.messages.create(**kwargs)

    # Extract text from content blocks (skip thinking blocks)
    for block in response.content:
        if hasattr(block, "text") and getattr(block, "type", None) != "thinking":
            return block.text
    return ""


def _call_llm(messages: List[dict], model: str, system: str = "") -> str:
    """Single-shot LLM call. Auto-detects provider from model name."""
    system = system or CODE_GEN_SYSTEM_PROMPT
    provider = _detect_provider(model)
    if provider == "openai":
        return _call_openai(messages, model, system)
    else:
        return _call_anthropic(messages, model, system)


# ── Code extraction ──────────────────────────────────────────

def _extract_code(text: str) -> str:
    """Strip markdown code blocks if LLM wraps output in them."""
    text = text.strip()
    if not text:
        return text

    # Match ```python ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```python or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    return text


# ── Main: generate and execute ───────────────────────────────

def _resolve_code_model() -> str:
    """Get code_model from config, falling back to anthropic_model_advanced."""
    from ..agents.config import get_agent_config
    config = get_agent_config()
    if config.code_model:
        return config.code_model
    # Default: use the advanced model for the provider
    return config.anthropic_model_advanced or "claude-sonnet-4-5-20250929"


def generate_and_execute(
    task: str,
    data_json: str = "",
    code_model: str = "",
    max_retries: int = 0,
    timeout: int = 120,
    background: bool = False,
) -> CodeExecutionResult:
    """
    Generate Python code from task description and execute it.

    If execution fails, feeds the error back to the coding model for
    correction and retries up to max_retries times.

    Args:
        task: Natural language description of what the code should do
        data_json: JSON data to inject as `data` variable
        code_model: Model ID for code generation (empty = from config)
        max_retries: Max correction attempts after first failure (0 = from config)
        timeout: Execution timeout in seconds
        background: Run in background mode

    Returns:
        CodeExecutionResult with generated_code field populated
    """
    # Resolve model and config
    model = code_model or _resolve_code_model()
    if max_retries == 0:
        from ..agents.config import get_agent_config
        max_retries = get_agent_config().code_max_retries

    # Build initial prompt
    data_desc = ""
    if data_json:
        # Show a preview (first 500 chars) so model understands the shape
        preview = data_json[:500]
        if len(data_json) > 500:
            preview += "..."
        data_desc = f"\n\nInput data (accessible as `data` variable):\n{preview}"

    messages: List[dict] = [
        {"role": "user", "content": f"Task: {task}{data_desc}"}
    ]

    total_start = time.monotonic()

    for attempt in range(1 + max_retries):
        # Generate code
        try:
            logger.info(
                f"Code gen attempt {attempt + 1}/{1 + max_retries}: "
                f"model={model} task={task[:50]}..."
            )
            raw_response = _call_llm(messages, model)
            code = _extract_code(raw_response)
        except Exception as e:
            logger.error(f"Code generation LLM call failed: {e}")
            return CodeExecutionResult(
                success=False,
                output="",
                error=f"Code generation failed: {e}",
                execution_time=round(time.monotonic() - total_start, 3),
                generated_code="",
            )

        if not code.strip():
            return CodeExecutionResult(
                success=False,
                output="",
                error="Code generation returned empty code",
                execution_time=round(time.monotonic() - total_start, 3),
                generated_code="",
            )

        # AST validation
        validation_error = validate_code(code, DEFAULT_BLOCKED_MODULES)
        if validation_error is not None:
            # AST error — ask model to fix
            error_text = f"AST validation error: {validation_error}"
            logger.warning(f"Code gen attempt {attempt + 1} AST error: {validation_error}")

            if attempt < max_retries:
                messages.append({"role": "assistant", "content": code})
                messages.append({"role": "user", "content": (
                    f"The code failed validation:\n{error_text}\n\n"
                    "Please fix the code and output the complete corrected version. "
                    "Output ONLY the code, no explanations."
                )})
                continue

            return CodeExecutionResult(
                success=False,
                output="",
                error=f"Code generation failed after {attempt + 1} attempts. Last error: {error_text}",
                execution_time=round(time.monotonic() - total_start, 3),
                generated_code=code,
            )

        # Execute
        full_code = _PREAMBLE + code
        stdin_data = data_json if data_json else ""

        if background:
            result = _execute_background(full_code, stdin_data)
            result.generated_code = code
            return result

        result = _execute_foreground(full_code, stdin_data, timeout)
        result.generated_code = code

        if result.success:
            result.execution_time = round(time.monotonic() - total_start, 3)
            logger.info(f"Code gen succeeded on attempt {attempt + 1}")
            return result

        # Execution error — ask model to fix
        error_text = result.error or result.output
        logger.warning(f"Code gen attempt {attempt + 1} runtime error: {error_text[:200]}")

        if attempt < max_retries:
            messages.append({"role": "assistant", "content": code})
            messages.append({"role": "user", "content": (
                f"The code produced an error:\n{error_text}\n\n"
                "Please fix the code and output the complete corrected version. "
                "Output ONLY the code, no explanations."
            )})
            continue

        # All retries exhausted
        result.error = (
            f"Code generation failed after {attempt + 1} attempts. "
            f"Last error: {error_text}"
        )
        result.execution_time = round(time.monotonic() - total_start, 3)
        return result

    # Should not reach here, but just in case
    return CodeExecutionResult(
        success=False,
        output="",
        error="Unexpected: retry loop exited without result",
        execution_time=round(time.monotonic() - total_start, 3),
        generated_code="",
    )