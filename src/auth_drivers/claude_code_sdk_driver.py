"""Slice 7B-4 — AnthropicClaudeCodeSdkDriver: run Research on a Claude
subscription via the in-process Claude **Agent SDK** (`claude_agent_sdk.query`),
mapping its message stream to the existing `AgentEvent` vocabulary.

This supersedes the experimental 7A `claude -p --bare` driver
(`claude_code_oauth_driver.py`), which cannot read `CLAUDE_CODE_OAUTH_TOKEN`.
Design of record: docs/design/SLICE_7B3_SDK_DRIVER_DESIGN.md (all section refs
below are to it). The 7A driver's *concepts* carry over verbatim — the sync
``stream_llm`` returning ``self._stream`` (the async generator); the ``_err``
terminal-event shape; the exact-token ``_redact`` scrub; ``_DEFAULT_TIMEOUT_S``;
``discover_models`` via ``_seed_models`` — only the transport (subprocess+NDJSON)
is swapped for ``query()`` + SDK-message mapping + an in-process MCP bridge.

ISOLATION + POSTURE (validated by the live spike 2026-06-19 — §7 Option 2):
``permission_mode="dontAsk"`` + ``tools=[]`` + ``allowed_tools=[mcp__ark__*]`` +
``setting_sources=[]`` + a fresh empty ``CLAUDE_CONFIG_DIR`` + the OAuth token and
``ANTHROPIC_API_KEY=""`` injected via ``options.env`` (NEVER os.environ). No
``bypassPermissions``, no hook. The tool surface is the in-process
``create_sdk_mcp_server`` bridge over a hardcoded read-only allowlist.

This module is the DRIVER + the ToolRegistry→SDK-tool bridge ONLY. It is NOT
wired onto the live Research path here (no factory repoint / Research-path
change — that is 7B-5/7B-6).

SECURITY (load-bearing, §4/§5/§6):
- The token lives ONLY in the token-store; it is read at call time and placed in
  ``options.env``, NEVER in argv, NEVER in ``llm_credentials.secret``, NEVER
  logged, and NEVER in any yielded ``AgentEvent``.
- Every bridge handler is wrapped in ``try/except BaseException`` that NEVER
  re-raises (an escaping exception would be echoed verbatim into model context by
  the SDK at ``query.py:716-721``).
- A Python-side in-process veto (allowlist check co-located with execution) is the
  ONE control independent of the bundled CLI.
- args / results / errors are redacted (exact-token scrub ∘ project-standard
  fail-closed regex), and results are SIZE-capped FIRST then redacted.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import shutil
import tempfile
from typing import Any, AsyncIterator, Optional

from src.agents.shared.compressor.reducers import get_reducer  # default = truncate_with_marker
from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.probe_harness import redact as _regex_redact
from src.auth_drivers.protocol import LLMRequest
from src.model_credentials import ModelDiscoveryResult, ModelTestResult, _seed_models

# query is imported at module level so tests can monkeypatch
# ``claude_code_sdk_driver.query`` with a fake async generator (NO live calls).
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    ServerToolResultBlock,
    ServerToolUseBlock,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

logger = logging.getLogger(__name__)

# --- constants (from §4; 7A values reused where noted) ----------------------
_DEFAULT_TIMEOUT_S = 900.0      # session/stream wall-clock; 0 disables (§6 channel f)
_PER_TOOL_TIMEOUT_S = 45.0      # NEW — bounds one in-process tool call (§4)
_BRIDGE_RESULT_BUDGET = 12_000  # = LAYER_5_CHAR_CAP; model-facing result cap (§4)
_SUMMARY_CAP = 200              # reuse 7A — event/history preview (§4)
_DEFAULT_MAX_TURNS = 60         # mirrors AgentConfig.max_tool_calls; no hidden 8-turn cap

_MCP_SERVER_NAME = "ark"
_MCP_PREFIX = "mcp__ark__"

# §3 Tier-1 allowlist (12 read-only tools). Hardcoded frozenset — NOT derived
# from the registry `category` field (which is free-text, not a safety boundary).
_RESEARCH_READONLY_TOOLS: frozenset[str] = frozenset(
    {
        "get_sa_feed",
        "get_sa_digest",
        "get_sa_alpha_picks",
        "get_ticker_news",
        "get_news_brief",
        "search_news_advanced",
        "get_ticker_prices",
        "get_price_change",
        "get_ticker_data_coverage",
        "get_fundamentals_analysis",
        "get_sec_filings",
        "get_economic_calendar",
    }
)


# ===========================================================================
# Redaction (§4 §b — load-bearing). Exact-token scrub FIRST, then the project
# fail-closed regex. Applied to args, results, AND errors.
# ===========================================================================
def _redact_bridge(text: Any, token: Optional[str]) -> str:
    """Scrub the live OAuth token (exact) then any token/secret/PII shape (regex).

    Order matters: the exact-token replace guarantees *this* token is gone with
    zero false positives; the regex is the safety net for unknown secrets.
    """
    if not isinstance(text, str):
        # _regex_redact reduces non-strings to a type name; coerce defensively.
        text = "" if text is None else str(text)
    if token and token in text:
        text = text.replace(token, "[REDACTED]")
    return _regex_redact(text)


def _int_token(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _usage_get(usage: Any, key: str) -> Any:
    if isinstance(usage, dict):
        return usage.get(key)
    return getattr(usage, key, None)


def _aggregate_model_usage(model_usage: Any) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }
    if not isinstance(model_usage, dict):
        return totals
    for usage in model_usage.values():
        totals["input_tokens"] += _int_token(_usage_get(usage, "input_tokens"))
        totals["output_tokens"] += _int_token(_usage_get(usage, "output_tokens"))
        totals["cache_creation_tokens"] += _int_token(_usage_get(usage, "cache_creation_input_tokens"))
        totals["cache_read_tokens"] += _int_token(_usage_get(usage, "cache_read_input_tokens"))
    return totals


def _result_token_usage(msg: ResultMessage) -> dict[str, Any]:
    usage = msg.usage or {}
    model_totals = _aggregate_model_usage(getattr(msg, "model_usage", None))
    in_tokens = _int_token(_usage_get(usage, "input_tokens")) or model_totals["input_tokens"]
    out_tokens = _int_token(_usage_get(usage, "output_tokens")) or model_totals["output_tokens"]
    cache_create = _int_token(_usage_get(usage, "cache_creation_input_tokens")) or model_totals["cache_creation_tokens"]
    cache_read = _int_token(_usage_get(usage, "cache_read_input_tokens")) or model_totals["cache_read_tokens"]
    token_usage: dict[str, Any] = {
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_tokens": in_tokens + out_tokens,
    }
    if isinstance(msg.total_cost_usd, (int, float)):
        token_usage["cost_usd"] = msg.total_cost_usd
    if cache_create:
        token_usage["cache_creation_tokens"] = cache_create
    if cache_read:
        token_usage["cache_read_tokens"] = cache_read
    return token_usage


def _scrub_token(text: Any, token: Optional[str]) -> str:
    """Exact-token scrub ONLY (zero false positives) — for model-authored prose
    (intermediate text / thinking / the final answer) where the heavier
    fail-closed regex would over-redact legitimate output. Guarantees the OAuth
    token is gone without mangling a base64 chart or a CUSIP in the answer.
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    return text.replace(token, "[REDACTED]") if (token and token in text) else text


def _redact_bridge_dict(obj: Any, token: Optional[str]) -> Any:
    """Recursively redact string values in a dict/list (for tool-arg echoes)."""
    if isinstance(obj, dict):
        return {k: _redact_bridge_dict(v, token) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_bridge_dict(v, token) for v in obj]
    if isinstance(obj, str):
        return _redact_bridge(obj, token)
    return obj


def _coerce_result_str(result: Any) -> str:
    """Stringify a tool result for sizing/redaction (mirrors the agent bridges)."""
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        try:
            return json.dumps(result.model_dump(), default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001 — fall through to str()
            return str(result)
    if isinstance(result, list) and result and hasattr(result[0], "model_dump"):
        try:
            return json.dumps([r.model_dump() for r in result], default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return str(result)
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return str(result)
    return str(result)


# ===========================================================================
# ToolRegistry → SDK-tool BRIDGE (§4)
# ===========================================================================
async def _invoke_bridged_tool(
    *,
    name: str,
    registry: Any,
    dal: Any,
    token: Optional[str],
    per_tool_timeout_s: float,
    args: Optional[dict],
) -> dict:
    """Run ONE allow-listed ArkScope tool and return an SDK tool-result dict.

    The CRITICAL §4 invariant: this function is *structurally incapable* of
    letting an exception escape — everything is inside ``try/except
    BaseException``. On any failure (off-allowlist veto, timeout, handler raise)
    it returns ``{"content": [...], "is_error": True}`` with REDACTED text.

    Ordering of guarantees:
      1. Python-side veto: name must be in the allowlist (CLI-independent gate).
      2. ``asyncio.wait_for(per_tool_timeout_s)`` bounds a hung tool.
      3. Result is SIZE-capped first (``get_reducer``/``truncate_with_marker``)
         THEN redacted (OQ-5 STRICT: regex+token over the full model-facing body).
    """
    args = args or {}
    try:
        # (1) Python-side in-process veto — fail-closed, CLI-independent (§4).
        if name not in _RESEARCH_READONLY_TOOLS:
            return {
                "content": [{"type": "text", "text": f"tool '{name}' is not allowed (allowlist veto)"}],
                "is_error": True,
            }

        tool_def = registry.get(name) if registry is not None else None
        if tool_def is None:
            return {
                "content": [{"type": "text", "text": f"tool '{name}' is not registered"}],
                "is_error": True,
            }

        fn = tool_def.function
        requires_dal = getattr(tool_def, "requires_dal", True)

        async def _run() -> Any:
            # Async handlers: await directly (wait_for cancels the coroutine cleanly).
            if asyncio.iscoroutinefunction(fn):
                return await (fn(dal, **args) if requires_dal else fn(**args))
            # Sync ArkScope handlers (``function(dal, **kwargs)``) run OFF the loop so
            # wait_for can interrupt the *await*. Use a DEDICATED single-thread pool,
            # NOT asyncio.to_thread: to_thread uses the loop's DEFAULT executor, and
            # asyncio.run() blocks on shutdown_default_executor(wait=True) at teardown
            # — a flaky hang (worse if a wait_for timeout orphans the worker thread,
            # which Python cannot kill). A dedicated pool shut down wait=False +
            # cancel_futures=True leaves the default executor untouched and never
            # blocks the loop/run on an orphaned call.
            call = (lambda: fn(dal, **args)) if requires_dal else (lambda: fn(**args))
            loop = asyncio.get_running_loop()
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ark-bridge")
            try:
                return await loop.run_in_executor(pool, call)
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

        # (2) per-tool wall-clock.
        try:
            raw = await asyncio.wait_for(_run(), timeout=per_tool_timeout_s)
        except asyncio.TimeoutError:
            return {
                "content": [{"type": "text", "text": f"tool '{name}' timed out after {per_tool_timeout_s}s"}],
                "is_error": True,
            }

        # (3) size FIRST, then redact the full model-facing body (OQ-5 STRICT).
        as_str = _coerce_result_str(raw)
        reducer = get_reducer(name)
        sized, _meta = reducer(as_str, budget=_BRIDGE_RESULT_BUDGET)
        safe = _redact_bridge(sized, token)
        return {"content": [{"type": "text", "text": safe}], "is_error": False}
    except BaseException as exc:  # noqa: BLE001 — §4 CRITICAL: NEVER let it escape.
        # An escaping exception would be echoed VERBATIM into model context
        # (query.py:716-721). Redact str(exc) (token + regex) and cap to 500.
        return {
            "content": [{"type": "text", "text": _redact_bridge(str(exc), token)[:500]}],
            "is_error": True,
        }


def _ark_input_schema(tool_def: Any) -> dict:
    """Build a JSON-Schema dict from ArkScope ToolParameters.

    Preferred passthrough form (§4): ``{"type":"object","properties":{...},
    "required":[...]}`` — preserves OPTIONAL args (the dict-of-types form marks
    every key required).
    """
    properties: dict = {}
    required: list[str] = []
    _JSON_TYPES = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }
    for p in getattr(tool_def, "parameters", None) or []:
        prop: dict = {"type": _JSON_TYPES.get(getattr(p, "type", "string"), "string")}
        if getattr(p, "description", None):
            prop["description"] = p.description
        if getattr(p, "enum", None):
            prop["enum"] = p.enum
        properties[p.name] = prop
        if getattr(p, "required", True):
            required.append(p.name)
    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_ark_mcp_server(
    *,
    registry: Any,
    dal: Any,
    token: Optional[str],
    per_tool_timeout_s: float = _PER_TOOL_TIMEOUT_S,
):
    """Build the in-process ``ark`` MCP server over the read-only allowlist.

    Returns ``(server_config, sdk_tools)``. FAIL-FAST: asserts at build time that
    EVERY name in the allowlist exists in the registry (catches registry drift).
    """
    # Build-time fail-fast on registry drift (§3).
    missing = sorted(n for n in _RESEARCH_READONLY_TOOLS if (registry is None or registry.get(n) is None))
    if missing:
        raise RuntimeError(
            f"ToolRegistry is missing allow-listed Research tools: {missing} "
            "(allowlist/registry drift — fix the allowlist or registry)"
        )

    sdk_tools = []
    for name in sorted(_RESEARCH_READONLY_TOOLS):
        tool_def = registry.get(name)
        description = getattr(tool_def, "description", name) or name
        schema = _ark_input_schema(tool_def)

        def _make_handler(_name: str):
            async def _handler(args: dict) -> dict:
                return await _invoke_bridged_tool(
                    name=_name,
                    registry=registry,
                    dal=dal,
                    token=token,
                    per_tool_timeout_s=per_tool_timeout_s,
                    args=args,
                )

            return _handler

        sdk_tool = tool(name, description, schema)(_make_handler(name))
        sdk_tools.append(sdk_tool)

    server = create_sdk_mcp_server(name=_MCP_SERVER_NAME, tools=sdk_tools)
    return server, sdk_tools


# ===========================================================================
# Terminal/error event helpers (§6 — mirror 7A so the reducer reads identical keys)
# ===========================================================================
def _err(request: LLMRequest, message: str) -> AgentEvent:
    return AgentEvent(EventType.error, {"error": message, "provider": "anthropic", "model": request.model})


# ===========================================================================
# The driver
# ===========================================================================
class AnthropicClaudeCodeSdkDriver:
    """ResearchProviderDriver for (anthropic, claude_code_oauth) via the Agent SDK."""

    provider = "anthropic"
    auth_mode = "claude_code_oauth"

    def __init__(
        self,
        *,
        credential: Any = None,
        token_store: Any = None,
        registry: Any = None,
        dal: Any = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        per_tool_timeout_s: float = _PER_TOOL_TIMEOUT_S,
    ):
        self.credential = credential
        self._token_store = token_store
        self._registry = registry
        self._dal = dal
        self._max_turns = max_turns
        self._timeout_s = timeout_s
        self._per_tool_timeout_s = per_tool_timeout_s
        self._credential_id = (
            f"local:{credential.id}"
            if credential is not None and getattr(credential, "id", None) is not None
            else None
        )

    # --- auth state ------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self._load_token() is not None

    async def authenticate(self) -> None:  # token is pasted via the import route
        return None

    async def refresh_if_needed(self) -> None:  # setup-token is a long-lived paste
        return None

    async def get_quota_status(self) -> dict[str, Any]:
        # Honest UNKNOWN — there is no real subscription-remaining probe (§ R-COST).
        return {"provider": self.provider, "auth_mode": self.auth_mode, "status": "unknown"}

    async def logout(self) -> None:  # token lives in the token-store; logout is instance-local
        return None

    async def call_llm(self, request: LLMRequest):
        raise NotImplementedError(
            "AnthropicClaudeCodeSdkDriver is stream-only; use stream_llm"
        )

    def _load_token(self) -> Optional[str]:
        # The token comes from the token-store ONLY — NEVER credential.secret (§5).
        if self._token_store is None or not self._credential_id:
            return None
        rec = self._token_store.load(
            provider="anthropic", auth_mode="claude_code_oauth", credential_id=self._credential_id,
        )
        return rec.access_token if rec and getattr(rec, "access_token", None) else None

    # --- the Research stream --------------------------------------------
    def stream_llm(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        # sync def returning an async generator (per the AuthDriver contract —
        # do NOT await this; ``async for`` over it).
        return self._stream(request)

    def _build_options(self, request: LLMRequest, token: str, server: Any, config_dir: str) -> ClaudeAgentOptions:
        # §1/§2/§5/§7. The token + empty API key + isolated config dir go via
        # options.env (NEVER os.environ). dontAsk + tools=[] + allowed_tools +
        # setting_sources=[] is the validated locked posture.
        allowed = [_MCP_PREFIX + n for n in sorted(_RESEARCH_READONLY_TOOLS)]
        effort = request.reasoning_effort
        if effort in ("", "default"):
            effort = None
        max_turns = self._max_turns if self._max_turns > 0 else None
        return ClaudeAgentOptions(
            model=request.model,
            effort=effort,
            system_prompt=request.instructions,
            mcp_servers={_MCP_SERVER_NAME: server},
            allowed_tools=allowed,
            tools=[],                       # disable ALL built-ins (--tools "")
            setting_sources=[],             # no user/project/local .claude
            strict_mcp_config=True,         # ignore any auto-loaded MCP config
            permission_mode="dontAsk",      # deny anything not pre-approved
            max_turns=max_turns,
            env={
                "CLAUDE_CODE_OAUTH_TOKEN": token,   # subscription auth (token-store)
                "ANTHROPIC_API_KEY": "",            # never bill the API key (§5)
                "CLAUDE_CONFIG_DIR": config_dir,    # fresh empty dir — isolation (§1)
            },
        )

    async def _stream(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        # Pre-flight failures may raise on first iteration (the only sanctioned
        # exceptions, mirroring 7A). Once query() begins, every failure becomes a
        # single in-band terminal `error`.
        token = self._load_token()
        if not token:
            raise MissingCredentialError(
                "no Claude setup-token stored for this credential -- import it in Settings"
            )

        server, _sdk_tools = build_ark_mcp_server(
            registry=self._registry, dal=self._dal, token=token,
            per_tool_timeout_s=self._per_tool_timeout_s,
        )
        config_dir = tempfile.mkdtemp(prefix="ark_claude_cfg_")
        options = self._build_options(request, token, server, config_dir)
        logger.info(
            "claude agent-sdk (subscription) model=%s max_turns=%s timeout_s=%s",
            request.model, self._max_turns, self._timeout_s,
        )

        prompt = _compose_input(request.input_messages)
        tool_names: dict[str, str] = {}  # tool_use_id -> name, to label tool_end
        terminal = False
        loop = asyncio.get_event_loop()
        deadline = None if self._timeout_s <= 0 else loop.time() + self._timeout_s

        agen = query(prompt=prompt, options=options)
        try:
            while True:
                try:
                    if deadline is None:
                        msg = await agen.__anext__()
                    else:
                        remaining = deadline - loop.time()
                        if remaining <= 0:
                            yield _err(request, f"claude agent-sdk timed out after {self._timeout_s}s")
                            terminal = True
                            return
                        msg = await asyncio.wait_for(agen.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break  # EOF
                except asyncio.TimeoutError:
                    yield _err(request, f"claude agent-sdk timed out after {self._timeout_s}s")
                    terminal = True
                    return
                except BaseException as exc:  # noqa: BLE001 — SDK exception while streaming (§6c)
                    yield _err(request, _redact_bridge(str(exc), token)[:500])
                    terminal = True
                    return

                for ev in self._map(msg, request, token, tool_names):
                    if ev.type in (EventType.done, EventType.error):
                        terminal = True
                    yield ev
                    if terminal:
                        return

            # EOF without a terminal -> synthesize ONE error (never a silent done).
            if not terminal:
                yield _err(request, "claude agent-sdk stream ended without a result")
        finally:
            # cancel / GeneratorExit / any exit -> tear down the SDK session FIRST
            # (the subprocess uses CLAUDE_CONFIG_DIR), then remove the per-call temp
            # config dir so /tmp/ark_claude_cfg_* does not accumulate over long
            # AI-研究 use. Both best-effort; teardown must never raise out.
            aclose = getattr(agen, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except BaseException:  # noqa: BLE001 — teardown must never raise out
                    pass
            shutil.rmtree(config_dir, ignore_errors=True)

    # --- SDK message -> AgentEvent (§6) ---------------------------------
    def _map(
        self, msg: Any, request: LLMRequest, token: Optional[str], tool_names: dict[str, str]
    ) -> list[AgentEvent]:
        """Map one SDK message to zero-or-more AgentEvents. Any unmapped type is
        IGNORED (non-terminal) per the §6 by-policy catch-all."""
        out: list[AgentEvent] = []

        if isinstance(msg, AssistantMessage):
            for block in msg.content or []:
                if isinstance(block, TextBlock):
                    txt = (block.text or "").strip()
                    if txt:
                        # Intermediate model prose: exact-token scrub (a model that
                        # echoes the token into text would otherwise leak it via
                        # this event — hard security rule, never in any event).
                        # Token-only (not the full regex) to avoid mangling prose.
                        out.append(AgentEvent(EventType.text, {"content": _scrub_token(txt, token)}))
                elif isinstance(block, ThinkingBlock):
                    out.append(
                        AgentEvent(EventType.thinking_content, {"thinking": _scrub_token(block.thinking, token)})
                    )
                elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                    name = block.name or "tool"
                    if getattr(block, "id", None):
                        tool_names[block.id] = name
                    out.append(
                        AgentEvent(
                            EventType.tool_start,
                            {"tool": name, "input": _redact_bridge_dict(block.input or {}, token)},
                        )
                    )
                elif isinstance(block, ServerToolResultBlock):
                    out.append(self._tool_end_event(block.tool_use_id, block.content, None, token, tool_names))
            return out

        if isinstance(msg, UserMessage):
            content = msg.content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, ToolResultBlock):
                        out.append(
                            self._tool_end_event(
                                block.tool_use_id, block.content, block.is_error, token, tool_names
                            )
                        )
            return out

        if isinstance(msg, ResultMessage):
            # The SOLE terminal. Guard BOTH is_error AND subtype=="error".
            if msg.is_error or msg.subtype == "error":
                err_text = (
                    msg.result
                    or (str(msg.errors) if getattr(msg, "errors", None) else None)
                    or "claude agent reported an error"
                )
                return [_err(request, _redact_bridge(err_text, token))]
            return [
                AgentEvent(
                    EventType.done,
                    {
                        "answer": _scrub_token(msg.result or "", token),
                        "tools_used": sorted(set(tool_names.values())),
                        "provider": "anthropic",
                        "model": request.model,
                        "token_usage": _result_token_usage(msg),
                    },
                )
            ]

        if isinstance(msg, SystemMessage):
            # init/hook noise -> IGNORE, except read apiKeySource ONCE for the
            # abort guard (§6 — advisory, env-side guarantee is primary).
            if getattr(msg, "subtype", None) == "init":
                src = (getattr(msg, "data", {}) or {}).get("apiKeySource")
                if src not in (None, "none"):
                    return [
                        _err(
                            request,
                            "subscription auth not active (apiKeySource="
                            f"{src!r}) — refusing to bill an API key",
                        )
                    ]
            return out

        # RateLimitEvent / StreamEvent / Task*/Mirror*/Hook* / anything else -> IGNORE.
        return out

    def _tool_end_event(
        self,
        tool_use_id: Optional[str],
        content: Any,
        is_error: Optional[bool],
        token: Optional[str],
        tool_names: dict[str, str],
    ) -> AgentEvent:
        name = tool_names.get(tool_use_id, "tool")
        as_str = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        # size FIRST then redact the preview (redacting then sizing risks the
        # marker splitting a [REDACTED]).
        preview = _redact_bridge(as_str[:_SUMMARY_CAP], token)
        data = {"tool": name, "summary": preview, "chars": len(as_str)}
        if is_error is not None:
            data["is_error"] = bool(is_error)
        return AgentEvent(EventType.tool_end, data)

    # --- ResearchProviderDriver surface ---------------------------------
    async def discover_models(self) -> ModelDiscoveryResult:
        # OAuth has no API-key discovery; the seed catalog is the candidate list.
        return ModelDiscoveryResult(
            provider="anthropic",
            credential_id=self._credential_id,
            status="ok",
            models=_seed_models("anthropic"),
        )

    async def test(self) -> ModelTestResult:
        # Honest: NO live call here (the live smoke is §9, run by the orchestrator).
        # NEVER report a fake "ok". ModelTestResult.status is only
        # ok|missing_credential|error, so: missing_credential if no token, else a
        # deferred "error" whose warning says verify is not run in-process.
        models = _seed_models("anthropic")
        model_id = models[0].id if models else ""
        if not self._load_token():
            return ModelTestResult(
                provider="anthropic",
                credential_id=self._credential_id,
                model=model_id,
                effort="",
                status="missing_credential",
                error="no Claude setup-token stored for this credential",
            )
        return ModelTestResult(
            provider="anthropic",
            credential_id=self._credential_id,
            model=model_id,
            effort="",
            status="error",
            warning="subscription verify is deferred to the live smoke (not run in-process)",
        )


def _compose_input(input_messages: list[dict]) -> str:
    """Fold the conversation into a single prompt string for query().

    The SDK session is ISOLATED (no resume/session_store — §1), so multi-turn
    history must ride INSIDE the prompt rather than via session continuation.
    System messages are NOT folded here (they go to options.system_prompt). A lone
    user turn returns its bare content (clean single-turn); a multi-turn
    conversation is role-labeled so the model sees the prior exchange. The
    7B-6 /query/stream consumer passes input_messages=[*history, current-user]; this
    must NOT silently collapse to the last message (that was the v1 regression)."""
    turns = [m for m in (input_messages or []) if m.get("role") != "system" and m.get("content")]
    if not turns:
        return ""
    if len(turns) == 1 and turns[0].get("role") == "user":
        return str(turns[0]["content"])
    labels = {"user": "User", "assistant": "Assistant"}
    return "\n\n".join(f"{labels.get(m.get('role'), str(m.get('role')))}: {m['content']}" for m in turns)
