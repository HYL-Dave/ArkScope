"""
OpenAI Agents SDK agent implementation.

Uses GPT-5.4 with configurable reasoning effort for tool calling.
Provides run_query(), run_query_sync(), and run_query_stream().
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback as _traceback_mod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from ..config import get_agent_config, ReasoningEffort
from ..shared.events import AgentEvent, EventType
from ..shared.prompts import SYSTEM_PROMPT
from ..shared.replay import (
    ReplayCapture,
    _SERVER_TOOL_KINDS_BY_PROVIDER,
    _canonical_tool_name,
    classify_attachments,
    is_capture_enabled,
)
from ..shared.server_tools import openai_server_tools
from ..shared.scratchpad import Scratchpad
from ..shared.token_tracker import TokenTracker

logger = logging.getLogger(__name__)

# ── Responses transport ─────────────────────────────────────────
# Scope: ONLY the OpenAI Agents SDK Responses transport global. This does not
# affect frontend SSE, Anthropic streaming, market-data websockets, or native
# host capture. The Agents SDK defaults to HTTP. ArkScope previously forced
# websocket for speed, but desktop Research runs have seen websocket close-frame
# failures. Keep websocket available as an explicit opt-in for selected long /
# tool-heavy runs, while defaulting to HTTP for correctness and easier live
# verification.
def _openai_responses_transport_from_env() -> str:
    raw = os.environ.get("ARKSCOPE_OPENAI_RESPONSES_TRANSPORT", "http").strip().lower()
    return "websocket" if raw == "websocket" else "http"


def _configure_openai_responses_transport(*, set_transport=None) -> None:
    try:
        if set_transport is None:
            from agents import set_default_openai_responses_transport as set_transport
        transport = _openai_responses_transport_from_env()
        set_transport(transport)
        logger.info("OpenAI Responses API transport: %s", transport)
    except (ImportError, Exception) as _transport_err:
        logger.debug("OpenAI Responses transport configuration skipped: %s", _transport_err)


_configure_openai_responses_transport()

# ── Model output limits ────────────────────────────────────────
# GPT-5.x 全系列 max output tokens = 128K
# max_output_tokens 包含 reasoning tokens + visible output（跟 Anthropic max_tokens 相同概念）
# 不設此值時 API 預設未文件化，可能僅 2K-4K，對高 reasoning effort 不夠
_OPENAI_MODEL_MAX_OUTPUT = {
    "gpt-5.5": 128000,
    "gpt-5.4-mini": 128000,
    "gpt-5.4-nano": 128000,
    # Legacy / fallback (kept resolvable so configs that pin gpt-5.4 still
    # work — useful if gpt-5.5 isn't yet served by the API for an account).
    "gpt-5.4": 128000,
    "gpt-5.2": 128000,
}
_OPENAI_DEFAULT_MAX_OUTPUT = 128000


def _get_openai_max_output(model: str) -> int:
    """Return the model's maximum output token limit."""
    for prefix, limit in _OPENAI_MODEL_MAX_OUTPUT.items():
        if model.startswith(prefix):
            return limit
    return _OPENAI_DEFAULT_MAX_OUTPUT


def _make_compaction_session():
    """Create a CompactionSession for within-run context compaction (Phase 7a).

    Returns None if CompactionSession is not available or import fails.
    Uses an in-memory session (no persistence across runs).
    """
    try:
        from agents.memory import OpenAIResponsesCompactionSession
        session = OpenAIResponsesCompactionSession()
        logger.info("Using OpenAI CompactionSession for server-side compaction")
        return session
    except (ImportError, Exception) as e:
        logger.warning(f"CompactionSession not available: {e}")
        return None


@dataclass
class ToolExtraction:
    """Result of extracting tool info from Runner.run() result."""
    tools_used: List[str] = field(default_factory=list)
    tool_calls_detail: List[Dict[str, Any]] = field(default_factory=list)
    tickers: Set[str] = field(default_factory=set)


def _extract_tool_info(
    result,
    pad: Scratchpad,
    tracker: TokenTracker,
    model_name: str,
    capture: Optional[ReplayCapture] = None,
) -> ToolExtraction:
    """Extract tool calls, results, tickers from Runner result.

    Shared by all 3 run functions to avoid logic drift.
    Uses call_id mapping to correctly associate results with calls.

    When ``capture`` is supplied, each (call, result) pair is also
    forwarded to ``ReplayCapture.record_tool_call`` with canonical
    tool names + the bridge name on ``provider_tool_name``. Capture
    failures are logged but do not interrupt extraction.
    """
    ext = ToolExtraction()
    if not hasattr(result, "raw_responses"):
        return ext

    tracker.record_openai_result(result, model=model_name)

    # Build call_id → detail index mapping for correct result association
    call_id_map: Dict[str, int] = {}
    unmatched_results = 0
    # P0.1 full-v1: parallel structure tracking the (canonical name,
    # raw bridge name, args dict) per detail index, so the result-side
    # branch can call ``capture.record_tool_call`` once it has the
    # output_str. Avoids walking raw_responses twice.
    capture_pending: List[Optional[Dict[str, Any]]] = []

    for response in result.raw_responses:
        if not hasattr(response, "output"):
            continue
        for item in response.output:
            item_type = getattr(item, "type", None)

            if item_type == "function_call" or (
                item_type is None and hasattr(item, "name") and hasattr(item, "arguments")
            ):
                # Tool call item
                call_id = getattr(item, "call_id", None) or getattr(item, "id", None)
                args = getattr(item, "arguments", {})
                ext.tools_used.append(item.name)
                pad.log_tool_call(item.name, args if isinstance(args, dict) else {"raw": args})

                # Parse arguments
                if isinstance(args, str):
                    try:
                        args_dict = json.loads(args)
                    except (ValueError, TypeError):
                        args_dict = {"raw": args}
                else:
                    args_dict = args or {}

                # Extract tickers from params
                for k in ("ticker", "tickers"):
                    v = args_dict.get(k)
                    if isinstance(v, str) and v:
                        ext.tickers.add(v.upper())
                    elif isinstance(v, list):
                        ext.tickers.update(t.upper() for t in v if isinstance(t, str))

                detail: Dict[str, Any] = {"name": item.name, "params": args_dict}
                ext.tool_calls_detail.append(detail)
                if call_id:
                    call_id_map[call_id] = len(ext.tool_calls_detail) - 1
                # Track for capture so the result-side branch can record
                # the (call, result) pair with canonical name.
                if capture is not None:
                    raw_name = item.name
                    canonical = _canonical_tool_name(raw_name)
                    capture_pending.append({
                        "raw_name": raw_name,
                        "canonical": canonical,
                        "args": args_dict,
                    })
                else:
                    capture_pending.append(None)

            elif item_type == "function_call_output" or (
                item_type is None and hasattr(item, "output")
            ):
                # Tool result item — match by call_id, fallback to positional
                output_str = str(item.output) if item.output else ""
                result_call_id = getattr(item, "call_id", None)
                target_idx = call_id_map.get(result_call_id) if result_call_id else None
                if target_idx is not None:
                    target_detail = ext.tool_calls_detail[target_idx]
                elif ext.tool_calls_detail:
                    target_detail = ext.tool_calls_detail[-1]
                    target_idx = len(ext.tool_calls_detail) - 1
                    unmatched_results += 1
                else:
                    unmatched_results += 1
                    continue
                target_detail["result_preview"] = output_str[:200]
                pad.log_tool_result(
                    target_detail["name"],
                    result_data=output_str[:5000],
                    tool_input=target_detail.get("params"),
                )
                # P0.1 full-v1: forward to capture if armed and we have
                # a matching pending entry.
                if (
                    capture is not None
                    and target_idx is not None
                    and target_idx < len(capture_pending)
                    and capture_pending[target_idx] is not None
                ):
                    pending = capture_pending[target_idx]
                    try:
                        capture.record_tool_call(
                            pending["canonical"],
                            pending["args"],
                            output_str,
                            provider_tool_name=(
                                pending["raw_name"]
                                if pending["raw_name"] != pending["canonical"]
                                else None
                            ),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Replay capture record_tool_call failed: %s", exc,
                        )

    if unmatched_results:
        logger.debug(
            "_extract_tool_info: %d tool results could not be matched by call_id",
            unmatched_results,
        )
    return ext


def _replay_tools_available_openai(all_tools: list) -> List[str]:
    """Convert the OpenAI tool list (function-tool wrappers + WebSearchTool
    etc.) into canonical replay names.

    - ``WebSearchTool()`` → ``"server:web_search"`` (per ``_SERVER_TOOL_KINDS_BY_PROVIDER``).
    - ``@function_tool``-decorated wrappers → canonical registry name
      via ``_canonical_tool_name``.
    - Anything we cannot classify is silently skipped (capture is best-effort).
    """
    server_map = _SERVER_TOOL_KINDS_BY_PROVIDER.get("openai", {})
    out: List[str] = []
    for t in all_tools:
        cls_name = type(t).__name__
        if cls_name in server_map:
            out.append(server_map[cls_name])
            continue
        raw_name = getattr(t, "name", None)
        if isinstance(raw_name, str) and raw_name:
            out.append(_canonical_tool_name(raw_name))
    return out


def _install_capture(
    *,
    question: str,
    system_prompt: str,
    all_tools: list,
    model_name: str,
    entrypoint: str,
    attachments: Optional[list] = None,
) -> Optional[ReplayCapture]:
    """Build + arm a ``ReplayCapture`` for the OpenAI path. Returns
    ``None`` when the env flag is off or any wiring step raises (the
    agent path stays alive — capture is best-effort).

    ``attachments`` is the same list later passed to
    ``AttachmentManager.to_openai_blocks``; the capture records its
    classification at install time so ``attachments_shape`` reflects
    what the provider WILL produce, independent of when the content
    blocks themselves are built.
    """
    if not is_capture_enabled():
        return None
    try:
        capture = ReplayCapture(
            provider="openai",
            model=model_name,
            entrypoint=entrypoint,
        )
        capture.set_initial(
            question=question,
            system_prompt=system_prompt,
            tools_available=_replay_tools_available_openai(all_tools),
            attachments_shape=classify_attachments("openai", attachments),
        )
        return capture
    except Exception as exc:
        logger.warning("Replay capture init failed: %s", exc)
        return None


def _build_openai_all_tools(base_tools: list, config) -> list:
    """Return the full tool list to give to ``agents.Agent``, including
    every hosted server tool that ``config`` enables.

    LOAD-BEARING: this is the SINGLE wiring point for OpenAI hosted
    server tools. ``_build_agent`` MUST call this helper — never
    re-implement the loop. Bypassing it (e.g. Phase C unified runner
    appending ``WebSearchTool()`` directly) makes the replay validator's
    ``_currently_wired_server_tools`` lie about what's wired. The
    sentinel-based safeguard test in ``tests/test_replay_openai.py``
    catches that drift.
    """
    all_tools = list(base_tools)
    for _kind, tool_obj in openai_server_tools(config):
        all_tools.append(tool_obj)
    return all_tools


def _build_agent(
    model_name: str,
    tools: list,
    reasoning_effort: ReasoningEffort = "high",
    max_tokens: int = 16384,
    system_prompt: Optional[str] = None,
):
    """Build an Agent with ModelSettings including reasoning config.

    設計決策（與 Anthropic thinking 模式一致）：
    - reasoning_effort != "none" → max_tokens = 模型 max output (128K)
      reasoning tokens 從 max_output_tokens 扣，需要足夠空間
    - reasoning_effort == "none" → max_tokens = config.max_tokens (16384)
      不消耗 reasoning tokens，只需 visible output 空間
    """
    from agents import Agent, ModelSettings
    from openai.types.shared import Reasoning

    # Per-query OpenAI auth bootstrap (api_key wire-in, Slice 6): register the SDK
    # default client from the ACTIVE credential. _build_agent is called once per
    # query by all 3 entrypoints immediately before Runner.run, so it is the
    # per-run choke-point. OAuth-active / none → leaves the SDK env default
    # (logged). NOTE: set_default_openai_client is a process-global — concurrent
    # OpenAI runs in one process share it (set immediately before the run).
    from src.auth_drivers.live_resolver import apply_openai_live_client
    apply_openai_live_client()

    # Build full tool list including any hosted server tools (single
    # wiring point — see ``_build_openai_all_tools`` docstring).
    config = get_agent_config()
    all_tools = _build_openai_all_tools(tools, config)

    # 自動決定 effective_max_tokens
    if reasoning_effort == "none":
        effective_max_tokens = max_tokens
    else:
        effective_max_tokens = _get_openai_max_output(model_name)

    return Agent(
        name="ArkScope Assistant",
        instructions=system_prompt or SYSTEM_PROMPT,
        model=model_name,
        tools=all_tools,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort=reasoning_effort),
            max_tokens=effective_max_tokens,
        ),
    )


async def run_query(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
    max_tool_calls: Optional[int] = None,
    attachments: list | None = None,
) -> Dict[str, Any]:
    """
    Run a natural language query using OpenAI Agents SDK.

    Args:
        question: The user's question
        model: Override model (default: gpt-5.4 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)
        max_tool_calls: Override max tool calls (default from AgentConfig)

    Returns:
        Dict with:
            answer: str - The agent's response
            tools_used: List[str] - Names of tools called
            provider: str - "openai"
            model: str - Model used
    """
    try:
        from agents import Runner
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Run: pip install openai-agents"
        )

    from .tools import create_openai_tools

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort

    # Create tools bound to DAL
    tools = create_openai_tools(dal)

    # Build effective prompt: always includes RL status; freshness only when flag is on
    effective_prompt = _build_effective_prompt(dal, config)

    # Create agent with reasoning settings
    agent = _build_agent(
        model_name, tools, reasoning_effort=effort,
        max_tokens=config.max_tokens, system_prompt=effective_prompt,
    )

    # Run query
    logger.info(
        f"Running OpenAI agent: model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    pad = Scratchpad(query=question, provider="openai", model=model_name)
    tracker = TokenTracker()
    tools_used: List[str] = []

    # P0.1 full-v1: replay capture (gated by ARKSCOPE_REPLAY_CAPTURE).
    # ``attachments`` flows in so the capture can classify and store
    # ``attachments_shape`` even though the actual content blocks are
    # built later (line ~426 below). Order-independence keeps capture
    # a true side-channel of the agent path.
    capture = _install_capture(
        question=question,
        system_prompt=effective_prompt,
        all_tools=getattr(agent, "tools", tools),
        model_name=model_name,
        entrypoint="api",
        attachments=attachments,
    )

    # Server-side compaction (Phase 7a)
    session = _make_compaction_session() if config.server_compaction else None

    # Build input (with optional attachment content blocks)
    if attachments:
        from ..shared.attachments import AttachmentManager
        content_blocks = AttachmentManager.to_openai_blocks(attachments)
        content_blocks.append({"type": "input_text", "text": question})
        input_data = [{"role": "user", "content": content_blocks}]
    else:
        input_data = question

    effective_max_turns = max_tool_calls or config.max_tool_calls
    runner_kwargs = dict(
        input=input_data,
        max_turns=effective_max_turns,
        auto_previous_response_id=True,
    )
    if session:
        runner_kwargs["session"] = session

    # Outer try ensures ANY exception (runner or post-processing) logs to scratchpad
    try:
        logger.debug(
            "Runner.run starting: model=%s effort=%s max_turns=%d compaction=%s",
            model_name, effort, effective_max_turns, bool(session),
        )

        # Retry on transient SDK errors (e.g. "No tool output found" race condition)
        _max_retries = 2
        for _attempt in range(_max_retries):
            try:
                result = await Runner.run(agent, **runner_kwargs)
                break
            except Exception as e:
                err_str = str(e)
                is_retryable = "No tool output found" in err_str
                if is_retryable and _attempt < _max_retries - 1:
                    logger.warning(
                        "Retryable SDK error (attempt %d/%d): %s",
                        _attempt + 1, _max_retries, err_str[:200],
                    )
                    reason = "no_tool_output" if "No tool output found" in err_str else "unknown"
                    pad.log_retry(
                        attempt=_attempt + 1, error_message=err_str[:200],
                        retryable=True, reason_code=reason,
                    )
                    continue
                raise  # let outer try handle logging

        raw_count = len(result.raw_responses) if hasattr(result, "raw_responses") else 0
        logger.debug(
            "Runner.run completed: %d raw_responses, final_output=%d chars",
            raw_count, len(str(result.final_output)) if result.final_output else 0,
        )

        # Extract tools used, tool details, tickers, and token usage from result
        ext = _extract_tool_info(result, pad, tracker, model_name, capture=capture)
        tools_used = ext.tools_used

        answer = str(result.final_output) if result.final_output else ""
        logger.debug("Extraction done: %d unique tools, tokens=%s", len(set(tools_used)), tracker.summary())
        pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
        pad.close()

        # P0.1 full-v1: finalise replay capture (best-effort; never raises).
        if capture is not None:
            try:
                capture.record_final(answer, tracker.summary())
                capture.save()
            except Exception as exc:
                logger.warning("Replay capture save failed: %s", exc)

        logger.info(f"OpenAI agent done: {tracker}")

        return {
            "answer": answer,
            "tools_used": list(set(tools_used)),
            "provider": "openai",
            "model": model_name,
            "token_usage": tracker.summary(),
            "tickers": sorted(ext.tickers) if ext.tickers else [],
            "tool_calls_detail": ext.tool_calls_detail if ext.tool_calls_detail else [],
        }

    except Exception as exc:
        pad.log_error(
            error_type=type(exc).__name__,
            message=str(exc),
            traceback_str=_traceback_mod.format_exc(),
            tools_used=list(set(tools_used)) if tools_used else None,
            token_usage=tracker.summary() if tracker.turn_count > 0 else None,
        )
        pad.close()
        raise


def run_query_sync(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
    max_tool_calls: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Synchronous wrapper for run_query().

    Args:
        question: The user's question
        model: Override model (default: gpt-5.4 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)
        max_tool_calls: Override max tool calls (default from AgentConfig)

    Returns:
        Dict with answer, tools_used, provider, model
    """
    try:
        from agents import Runner
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Run: pip install openai-agents"
        )

    from .tools import create_openai_tools

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort

    # Create tools bound to DAL
    tools = create_openai_tools(dal)

    # Build effective prompt: always includes RL status; freshness only when flag is on
    effective_prompt = _build_effective_prompt(dal, config)

    # Create agent with reasoning settings
    agent = _build_agent(
        model_name, tools, reasoning_effort=effort,
        max_tokens=config.max_tokens, system_prompt=effective_prompt,
    )

    # Run query synchronously
    logger.info(
        f"Running OpenAI agent (sync): model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    pad = Scratchpad(query=question, provider="openai", model=model_name)
    tracker = TokenTracker()
    tools_used: List[str] = []

    # P0.1 full-v1: replay capture (gated by ARKSCOPE_REPLAY_CAPTURE).
    capture = _install_capture(
        question=question,
        system_prompt=effective_prompt,
        all_tools=getattr(agent, "tools", tools),
        model_name=model_name,
        entrypoint="api",
    )

    # Server-side compaction (Phase 7a)
    session = _make_compaction_session() if config.server_compaction else None

    effective_max_turns = max_tool_calls or config.max_tool_calls
    runner_kwargs = dict(
        input=question,
        max_turns=effective_max_turns,
        auto_previous_response_id=True,
    )
    if session:
        runner_kwargs["session"] = session

    # Outer try ensures ANY exception (runner or post-processing) logs to scratchpad
    try:
        logger.debug(
            "Runner.run_sync starting: model=%s effort=%s max_turns=%d compaction=%s",
            model_name, effort, effective_max_turns, bool(session),
        )

        # Retry on transient SDK errors
        _max_retries = 2
        for _attempt in range(_max_retries):
            try:
                result = Runner.run_sync(agent, **runner_kwargs)
                break
            except Exception as e:
                err_str = str(e)
                is_retryable = "No tool output found" in err_str
                if is_retryable and _attempt < _max_retries - 1:
                    logger.warning(
                        "Retryable SDK error (attempt %d/%d): %s",
                        _attempt + 1, _max_retries, err_str[:200],
                    )
                    reason = "no_tool_output" if "No tool output found" in err_str else "unknown"
                    pad.log_retry(
                        attempt=_attempt + 1, error_message=err_str[:200],
                        retryable=True, reason_code=reason,
                    )
                    continue
                raise  # let outer try handle logging

        raw_count = len(result.raw_responses) if hasattr(result, "raw_responses") else 0
        logger.debug(
            "Runner.run_sync completed: %d raw_responses, final_output=%d chars",
            raw_count, len(str(result.final_output)) if result.final_output else 0,
        )

        # Extract tools used and token usage
        ext = _extract_tool_info(result, pad, tracker, model_name, capture=capture)
        tools_used = ext.tools_used

        answer = str(result.final_output) if result.final_output else ""
        logger.debug("Extraction done: %d unique tools, tokens=%s", len(set(tools_used)), tracker.summary())
        pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
        pad.close()

        # P0.1 full-v1: finalise replay capture (best-effort; never raises).
        if capture is not None:
            try:
                capture.record_final(answer, tracker.summary())
                capture.save()
            except Exception as exc:
                logger.warning("Replay capture save failed: %s", exc)

        logger.info(f"OpenAI agent done (sync): {tracker}")

        return {
            "answer": answer,
            "tools_used": list(set(tools_used)),
            "provider": "openai",
            "model": model_name,
            "token_usage": tracker.summary(),
            "tickers": sorted(ext.tickers) if ext.tickers else [],
            "tool_calls_detail": ext.tool_calls_detail if ext.tool_calls_detail else [],
        }

    except Exception as exc:
        pad.log_error(
            error_type=type(exc).__name__,
            message=str(exc),
            traceback_str=_traceback_mod.format_exc(),
            tools_used=list(set(tools_used)) if tools_used else None,
            token_usage=tracker.summary() if tracker.turn_count > 0 else None,
        )
        pad.close()
        raise


def _compose_stream_input(history: list, question: str):
    """OpenAI Runner input (C-2c multi-turn): a message-list (prior history + this
    turn) when there is context, else the bare question string — keeping
    single-turn behaviour byte-identical. The Agents SDK accepts both forms."""
    return [*history, {"role": "user", "content": question}] if history else question


async def run_query_stream(
    question: str,
    model: Optional[str] = None,
    dal: Optional[Any] = None,
    reasoning_effort: Optional[ReasoningEffort] = None,
    history: list | None = None,
    max_tool_calls: Optional[int] = None,
) -> AsyncGenerator[AgentEvent, None]:
    """
    Run a query yielding events for progress tracking.

    OpenAI Agents SDK handles the tool loop internally (black box),
    so we can only emit events before and after the run. Tool events
    are extracted post-run from raw_responses.

    Args:
        question: The user's question
        model: Override model (default: gpt-5.4 from AgentConfig)
        dal: DataAccessLayer instance (auto-created if None)
        reasoning_effort: Override reasoning effort (default from AgentConfig)
        max_tool_calls: Override max turns for AI Research (default from AgentConfig)

    Yields:
        AgentEvent for thinking, tool_end (post-run), and done
    """
    try:
        from agents import Runner
    except ImportError:
        raise ImportError(
            "OpenAI Agents SDK not installed. Run: pip install openai-agents"
        )

    from .tools import create_openai_tools

    # Get or create DAL
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer(db_dsn="auto")

    # Get config
    config = get_agent_config()
    model_name = model or config.openai_model
    effort = reasoning_effort or config.reasoning_effort

    # Create tools bound to DAL
    tools = create_openai_tools(dal)

    # Build effective prompt: always includes RL status; freshness only when flag is on
    effective_prompt = _build_effective_prompt(dal, config)

    # Multi-turn (C-2c): prior thread turns are context only — note staleness.
    _hist = [{"role": h["role"], "content": h["content"]} for h in (history or [])]
    if _hist:
        effective_prompt = (
            effective_prompt
            + "\n\n[多輪脈絡] 以下對話歷史僅供理解使用者意圖與指代；價格、新聞、SA、"
            "基本面等時效性事實一律以工具即時查詢為準，歷史內容可能已過期。"
        )

    # Create agent with reasoning settings
    agent = _build_agent(
        model_name, tools, reasoning_effort=effort,
        max_tokens=config.max_tokens, system_prompt=effective_prompt,
    )

    logger.info(
        f"Running OpenAI agent (stream): model={model_name} reasoning={effort} "
        f"question={question[:50]}..."
    )

    yield AgentEvent(EventType.thinking, {"turn": 1, "model": model_name})

    pad = Scratchpad(query=question, provider="openai", model=model_name)
    tracker = TokenTracker()
    tools_used: List[str] = []

    # P0.1 full-v1: replay capture (gated by ARKSCOPE_REPLAY_CAPTURE).
    capture = _install_capture(
        question=question,
        system_prompt=effective_prompt,
        all_tools=getattr(agent, "tools", tools),
        model_name=model_name,
        entrypoint="api",
    )

    # Server-side compaction (Phase 7a)
    session = _make_compaction_session() if config.server_compaction else None

    effective_max_turns = max_tool_calls if max_tool_calls is not None else config.max_tool_calls
    runner_kwargs = dict(
        input=_compose_stream_input(_hist, question),
        max_turns=effective_max_turns,
        auto_previous_response_id=True,
    )
    if session:
        runner_kwargs["session"] = session

    # Outer try ensures ANY exception (runner or post-processing) logs to scratchpad
    try:
        logger.debug(
            "Runner.run starting (stream): model=%s effort=%s max_turns=%d compaction=%s",
            model_name, effort, effective_max_turns, bool(session),
        )

        # Retry on transient SDK errors
        _max_retries = 2
        result = None
        for _attempt in range(_max_retries):
            try:
                result = await Runner.run(agent, **runner_kwargs)
                break
            except Exception as e:
                err_str = str(e)
                is_retryable = "No tool output found" in err_str
                if is_retryable and _attempt < _max_retries - 1:
                    logger.warning(
                        "Retryable SDK error (attempt %d/%d): %s",
                        _attempt + 1, _max_retries, err_str[:200],
                    )
                    reason = "no_tool_output" if "No tool output found" in err_str else "unknown"
                    pad.log_retry(
                        attempt=_attempt + 1, error_message=err_str[:200],
                        retryable=True, reason_code=reason,
                    )
                    continue
                raise  # let outer try handle logging

        raw_count = len(result.raw_responses) if hasattr(result, "raw_responses") else 0
        logger.debug(
            "Runner.run completed (stream): %d raw_responses, final_output=%d chars",
            raw_count, len(str(result.final_output)) if result.final_output else 0,
        )

        # Extract tools used and token usage from result
        ext = _extract_tool_info(result, pad, tracker, model_name, capture=capture)
        tools_used = ext.tools_used

        # Emit tool_end events for stream consumers
        for detail in ext.tool_calls_detail:
            yield AgentEvent(EventType.tool_end, {"tool": detail["name"]})

        answer = str(result.final_output) if result.final_output else ""
        logger.debug("Extraction done: %d unique tools, tokens=%s", len(set(tools_used)), tracker.summary())
        pad.log_final_answer(answer, token_usage=tracker.summary(), tools_used=list(set(tools_used)))
        pad.close()

        # P0.1 full-v1: finalise replay capture (best-effort; never raises).
        if capture is not None:
            try:
                capture.record_final(answer, tracker.summary())
                capture.save()
            except Exception as exc:
                logger.warning("Replay capture save failed: %s", exc)

        logger.info(f"OpenAI agent done (stream): {tracker}")

        yield AgentEvent(EventType.done, {
            "answer": answer,
            "tools_used": list(set(tools_used)),
            "provider": "openai",
            "model": model_name,
            "token_usage": tracker.summary(),
        })

    except Exception as exc:
        pad.log_error(
            error_type=type(exc).__name__,
            message=str(exc),
            traceback_str=_traceback_mod.format_exc(),
            tools_used=list(set(tools_used)) if tools_used else None,
            token_usage=tracker.summary() if tracker.turn_count > 0 else None,
        )
        pad.close()
        yield AgentEvent(EventType.error, {
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
            "scratchpad": str(pad.filepath) if pad.filepath else None,
        })


# ── Freshness prompt helper ──────────────────────────────────

def _get_freshness_prompt(dal) -> Optional[str]:
    """Build system prompt with freshness summary if DB backend available."""
    try:
        from src.tools.backends.db_backend import DatabaseBackend
        if hasattr(dal, "_backend") and isinstance(dal._backend, DatabaseBackend):
            from src.tools.freshness import get_registry
            from ..shared.prompts import build_system_prompt
            fr = get_registry(db_backend=dal._backend)
            if fr:
                fr.scan()
                summary = fr.format_summary()
                if summary:
                    return build_system_prompt(summary)
    except Exception as e:
        logger.debug("Freshness prompt build failed: %s", e)
    return None


def _build_effective_prompt(dal, config) -> str:
    """Build system prompt with dynamic sections (always includes RL status).

    Freshness is only included when config.freshness_in_prompt is True.
    RL status section is always included regardless of any flag.
    """
    from ..shared.prompts import build_system_prompt
    freshness_summary = ""
    if config.freshness_in_prompt:
        prompt = _get_freshness_prompt(dal)
        if prompt:
            return prompt  # Already includes RL status via build_system_prompt
        # Freshness unavailable but flag on — still build with RL status
    return build_system_prompt(freshness_summary)
