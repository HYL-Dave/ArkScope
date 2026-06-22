"""S3 — OpenAI ChatGPT/Codex-backend OAuth driver.

This driver makes an openai ``chatgpt_oauth`` credential report ITS OWN available
models — the ChatGPT/Codex backend's list, NOT the api-key seed catalog — so the
plan's "availability is PER (provider, auth_mode), NEVER shared" lock becomes real
on the wire. Discovery uses the P2c shape (plain ``models.list`` may 400; the codex
backend needs a Codex-style ``client_version`` via ``extra_query``), reusing the
probe's model-id extraction.

Discovery is live (ChatGPT-backend model list). Execution uses the raw Responses
API against the ChatGPT/Codex backend — NOT the normal OpenAI API-key Agents SDK
path. Load-bearing request differences: no ``max_output_tokens``, forced
``stream=True`` + ``store=False``, no ``previous_response_id``.

The OpenAI client is built behind ``_discovery_client`` (a monkeypatchable seam),
and the token is loaded from the token-store ONLY (never ``credential.secret``).
Any surfaced error is redacted — the token can never leak into a result.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
from typing import Any, AsyncIterator, Optional

from src.agents.shared.compressor.reducers import get_reducer
from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.protocol import LLMRequest, LLMResponse, TokenUsage
from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult, _seed_models

from .chatgpt_oauth_login import ChatGPTOAuthLoginError
from .chatgpt_oauth_login import refresh_if_needed as _refresh_login
from .chatgpt_oauth_probe import CHATGPT_BACKEND_BASE_URL, _CLIENT_VERSION, _PROBE_MODEL, _model_ids, _to_dict
from .probe_harness import redact

_PER_TOOL_TIMEOUT_S = 45.0
_DEFAULT_TIMEOUT_S = 900.0
_BRIDGE_RESULT_BUDGET = 12_000
_SUMMARY_CAP = 200
_DEFAULT_MAX_TURNS = 60

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
        "get_fundamentals_analysis",
        "get_sec_filings",
        "get_economic_calendar",
    }
)

# A well-formed model id: starts alphanumeric, then [A-Za-z0-9._:-], ≤80 chars. Real
# model ids — gpt-5.4-mini, gpt-3.5-turbo, claude-opus-4-8, ft:gpt-..., dated ids —
# all satisfy it; it rejects spaces / @ / / + = (email + base64/JWT padding). Because
# a SHORT JWT (eyJ....eyJ....sig) uses only [A-Za-z0-9.], the regex alone can't catch
# it (version dots like 5.4 are legitimate), so an id is kept ONLY if it ALSO survives
# the fail-closed redact() unchanged (which catches JWT/base64/high-entropy shapes).
# Defense-in-depth: a hostile/odd backend can't reflect a token-shaped string into the
# picker; non-matching discovered ids are DROPPED, not shown.
_VALID_MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,79}$")


def _well_formed_ids(ids: list[str]) -> list[str]:
    return [mid for mid in ids if _VALID_MODEL_ID.fullmatch(mid) and redact(mid) == mid]


def _discovery_client(token: str) -> Any:  # seam for tests
    """A sync OpenAI client pointed at the ChatGPT/Codex backend, with a short
    timeout (discovery must not hang the request thread)."""
    from openai import OpenAI

    return OpenAI(api_key=token, base_url=CHATGPT_BACKEND_BASE_URL, timeout=15)


def _execution_client(token: str) -> Any:  # seam for tests
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=token, base_url=CHATGPT_BACKEND_BASE_URL, timeout=300)


def _err(exc: BaseException) -> str:
    """Token-free, shape-only error string (redacted as defense-in-depth)."""
    return redact(f"{type(exc).__name__}: {exc}")[:200]


def _redact_token(text: Any, token: Optional[str]) -> str:
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    if token and token in text:
        text = text.replace(token, "[REDACTED]")
    return redact(text)


def _coerce_result_str(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        try:
            return json.dumps(result.model_dump(), ensure_ascii=False, default=str)
        except Exception:
            return str(result)
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            return str(result)
    return str(result)


def _ark_input_schema(tool_def: Any) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []
    for p in getattr(tool_def, "parameters", None) or []:
        prop: dict = {"type": getattr(p, "type", "string")}
        if getattr(p, "description", None):
            prop["description"] = p.description
        if getattr(p, "enum", None):
            prop["enum"] = p.enum
        properties[p.name] = prop
        if getattr(p, "required", True):
            required.append(p.name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _tool_schema(name: str, tool_def: Any) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": getattr(tool_def, "description", name) or name,
        "parameters": _ark_input_schema(tool_def),
    }


def _request_input_items(request: LLMRequest) -> list[dict]:
    out: list[dict] = []
    for m in request.input_messages or []:
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": str(content)})
    return out


def _reasoning(effort: Optional[str]) -> Optional[dict]:
    if not effort or effort in ("default", "none"):
        return None
    return {"effort": "high" if effort in ("xhigh", "max") else effort}


def _response_output_items(response: Any) -> list[dict]:
    if not response:
        return []
    raw = _to_dict(response)
    output = raw.get("output")
    return output if isinstance(output, list) else []


def _text_from_output_items(items: list[dict]) -> str:
    parts: list[str] = []
    for item in items:
        if item.get("type") != "message":
            continue
        for block in item.get("content") or []:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts)


def _call_from_item(item: dict, arg_fallback: dict[str, str]) -> Optional[dict]:
    if item.get("type") != "function_call":
        return None
    name = item.get("name")
    call_id = item.get("call_id") or item.get("id")
    if not isinstance(name, str) or not isinstance(call_id, str):
        return None
    arguments = item.get("arguments")
    if not isinstance(arguments, str):
        arguments = arg_fallback.get(call_id) or ""
    try:
        args = json.loads(arguments) if arguments else {}
    except (TypeError, ValueError):
        args = {}
    if not isinstance(args, dict):
        args = {}
    return {"name": name, "call_id": call_id, "arguments": arguments or "{}", "args": args}


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value


async def _aiter_stream(stream: Any):
    if hasattr(stream, "__aiter__"):
        async for item in stream:
            yield item
    else:
        for item in stream:
            yield item


class OpenAIChatGPTOAuthDriver:
    """ResearchProviderDriver for (openai, chatgpt_oauth). Discovery is real;
    Research execution uses the ChatGPT-backend raw Responses loop."""

    provider = "openai"
    auth_mode = "chatgpt_oauth"

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

    async def authenticate(self) -> None:  # token arrives via the in-app OAuth login
        return None

    async def refresh_if_needed(self) -> None:
        # Refresh the rotating ChatGPT access token if expired (the login core handles
        # the 5-min buffer + the actual grant). No-op when there's nothing to refresh.
        if self._token_store is None or not self._credential_id:
            return None
        _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
        return None

    async def get_quota_status(self) -> dict[str, Any]:
        return {"provider": self.provider, "auth_mode": self.auth_mode, "status": "unknown"}

    async def logout(self) -> None:  # token lives in the token-store; logout is instance-local
        return None

    def _load_token(self) -> Optional[str]:
        # Token from the token-store ONLY — NEVER credential.secret.
        if self._token_store is None or not self._credential_id:
            return None
        rec = self._token_store.load(
            provider="openai", auth_mode="chatgpt_oauth", credential_id=self._credential_id,
        )
        return rec.access_token if rec and getattr(rec, "access_token", None) else None

    # --- ResearchProviderDriver surface ---------------------------------
    async def discover_models(self) -> ModelDiscoveryResult:
        if self._token_store is None or not self._credential_id or not self._load_token():
            # No token → can't query the backend; the seed is the honest candidate list.
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
            )
        # Refresh the (possibly expired) access token FIRST so "available models" doesn't
        # intermittently degrade. A refresh failure means the login is stale → surface a
        # clear re-login hint (redacted), not a silent seed fallback with no reason.
        try:
            rec = _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
            token = rec.access_token if rec else None
        except ChatGPTOAuthLoginError as exc:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error=f"re-login needed (token refresh failed): {_err(exc)}",
            )
        if not token:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
            )
        try:
            client = _discovery_client(token)
            try:
                page = client.models.list()  # may 400 if the backend requires client_version
            except Exception:  # noqa: BLE001 — fall through to the Codex-style extra_query
                page = client.models.list(extra_query={"client_version": _CLIENT_VERSION})
            ids = _well_formed_ids(_model_ids(page))  # drop token/PII-shaped ids (defense-in-depth)
        except Exception as exc:  # noqa: BLE001 — never raise discovery; degrade to seed
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"), error=_err(exc),
            )
        if not ids:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error="the ChatGPT backend returned no model ids",
            )
        models = [DiscoveredModel(id=mid, provider="openai", label=mid, source="provider_api") for mid in ids]
        return ModelDiscoveryResult(
            provider="openai", credential_id=self._credential_id,
            status="ok", models=models, source_url=CHATGPT_BACKEND_BASE_URL,
        )

    async def test(self) -> ModelTestResult:
        # Honest deferral: the real backend capability check is the P1/P2 probe route
        # (run_chatgpt_oauth_probe), NOT this method. Never report a fake "ok".
        if not self._load_token():
            return ModelTestResult(
                provider="openai", credential_id=self._credential_id, model="", effort="",
                status="missing_credential", error="no ChatGPT OAuth token stored for this credential",
            )
        return ModelTestResult(
            provider="openai", credential_id=self._credential_id, model=_PROBE_MODEL, effort="",
            status="error",
            warning="run the ChatGPT OAuth probe (P1/P2) from Settings; this driver does not call the backend here",
        )

    # --- execution -------------------------------------------------------
    async def call_llm(self, request: Any):
        text = ""
        usage = TokenUsage()
        async for event in self.stream_llm(request):
            if event.type == EventType.done:
                data = event.data
                text = data.get("answer", "")
                tok = data.get("token_usage") or {}
                usage = TokenUsage(
                    input_tokens=tok.get("input_tokens", 0),
                    output_tokens=tok.get("output_tokens", 0),
                    total_tokens=tok.get("total_tokens", 0),
                )
                break
            if event.type == EventType.error:
                raise RuntimeError(event.data.get("error") or event.data.get("message") or "chatgpt_oauth error")
        return LLMResponse(text=text, usage=usage)

    def stream_llm(self, request: Any):
        return self._stream(request)

    def _build_tools(self) -> list[dict]:
        if self._registry is None:
            return []
        tools: list[dict] = []
        for name in sorted(_RESEARCH_READONLY_TOOLS):
            tool_def = self._registry.get(name)
            if tool_def is not None:
                tools.append(_tool_schema(name, tool_def))
        return tools

    async def _invoke_tool(self, *, name: str, args: dict, token: Optional[str]) -> tuple[bool, str]:
        try:
            if name not in _RESEARCH_READONLY_TOOLS:
                return False, f"tool '{name}' is not allowed (allowlist veto)"
            tool_def = self._registry.get(name) if self._registry is not None else None
            if tool_def is None:
                return False, f"tool '{name}' is not registered"
            fn = tool_def.function
            requires_dal = getattr(tool_def, "requires_dal", True)

            async def _run():
                if asyncio.iscoroutinefunction(fn):
                    return await (fn(self._dal, **args) if requires_dal else fn(**args))
                call = (lambda: fn(self._dal, **args)) if requires_dal else (lambda: fn(**args))
                loop = asyncio.get_running_loop()
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ark-openai-oauth")
                try:
                    return await loop.run_in_executor(pool, call)
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)

            try:
                raw = await asyncio.wait_for(_run(), timeout=self._per_tool_timeout_s)
            except asyncio.TimeoutError:
                return False, f"tool '{name}' timed out after {self._per_tool_timeout_s}s"
            result = _coerce_result_str(raw)
            sized, _meta = get_reducer(name)(result, budget=_BRIDGE_RESULT_BUDGET)
            return True, _redact_token(sized, token)
        except BaseException as exc:  # noqa: BLE001
            return False, _redact_token(str(exc), token)[:500]

    async def _stream(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        token = self._load_token()
        if not token:
            raise MissingCredentialError("no ChatGPT OAuth token stored for this credential -- log in from Settings")
        try:
            rec = _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
            token = rec.access_token if rec and rec.access_token else token
        except ChatGPTOAuthLoginError as exc:
            yield AgentEvent(EventType.error, {"error": f"ChatGPT OAuth refresh failed: {_err(exc)}", "provider": "openai", "model": request.model})
            return

        client = _execution_client(token)
        input_items = _request_input_items(request)
        tools = self._build_tools()
        used: list[str] = []
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        yield AgentEvent(EventType.thinking, {"turn": 1, "model": request.model})

        max_turns = self._max_turns if self._max_turns > 0 else 1000000
        loop = asyncio.get_running_loop()
        deadline = None if self._timeout_s <= 0 else loop.time() + self._timeout_s

        def _remaining() -> Optional[float]:
            if deadline is None:
                return None
            return max(0.0, deadline - loop.time())

        async def _with_deadline(awaitable):
            remaining = _remaining()
            if remaining is None:
                return await awaitable
            if remaining <= 0:
                raise asyncio.TimeoutError
            return await asyncio.wait_for(awaitable, timeout=remaining)

        for _turn in range(max_turns):
            if deadline is not None and _remaining() <= 0:
                yield AgentEvent(EventType.error, {
                    "error": f"ChatGPT OAuth driver timed out after {self._timeout_s}s",
                    "provider": "openai",
                    "model": request.model,
                })
                return
            kwargs: dict[str, Any] = {
                "model": request.model,
                "input": input_items,
                "instructions": request.instructions or "",
                "stream": True,
                "store": False,
            }
            if tools:
                kwargs["tools"] = tools
            reasoning = _reasoning(request.reasoning_effort)
            if reasoning:
                kwargs["reasoning"] = reasoning

            response_obj = None
            arg_fallback: dict[str, str] = {}
            call_items: list[dict] = []
            text_parts: list[str] = []
            current_call_id: Optional[str] = None
            try:
                stream = await _with_deadline(_maybe_await(client.responses.create(**kwargs)))
                stream_iter = _aiter_stream(stream).__aiter__()
                while True:
                    try:
                        event = await _with_deadline(stream_iter.__anext__())
                    except StopAsyncIteration:
                        break
                    raw = _to_dict(event)
                    etype = raw.get("type")
                    if etype == "response.output_text.delta":
                        delta = raw.get("delta")
                        if isinstance(delta, str) and delta:
                            text_parts.append(delta)
                            yield AgentEvent(EventType.text, {"content": _redact_token(delta, token)})
                    elif etype == "response.function_call_arguments.done":
                        call_id = raw.get("call_id") or raw.get("item_id") or current_call_id
                        args = raw.get("arguments")
                        if isinstance(call_id, str) and isinstance(args, str):
                            arg_fallback[call_id] = args
                    elif etype in ("response.output_item.added", "response.output_item.done"):
                        item = raw.get("item") or raw.get("output_item")
                        if isinstance(item, dict) and item.get("type") == "function_call":
                            maybe_id = item.get("call_id") or item.get("id")
                            if isinstance(maybe_id, str):
                                current_call_id = maybe_id
                            call_items.append(item)
                    elif etype == "response.completed":
                        response_obj = raw.get("response")
                    elif etype in ("response.failed", "response.incomplete"):
                        yield AgentEvent(EventType.error, {"error": f"ChatGPT backend stream ended with {etype}", "provider": "openai", "model": request.model})
                        return
            except asyncio.TimeoutError:
                yield AgentEvent(EventType.error, {
                    "error": f"ChatGPT OAuth driver timed out after {self._timeout_s}s",
                    "provider": "openai",
                    "model": request.model,
                })
                return
            except BaseException as exc:  # noqa: BLE001
                yield AgentEvent(EventType.error, {"error": _redact_token(str(exc), token)[:500], "provider": "openai", "model": request.model})
                return

            output_items = _response_output_items(response_obj) or call_items
            usage = _to_dict(response_obj).get("usage") if response_obj else None
            if isinstance(usage, dict):
                in_tokens = int(usage.get("input_tokens") or 0)
                out_tokens = int(usage.get("output_tokens") or 0)
                total_usage["input_tokens"] += in_tokens
                total_usage["output_tokens"] += out_tokens
                total_usage["total_tokens"] += int(usage.get("total_tokens") or (in_tokens + out_tokens))

            calls = [c for c in (_call_from_item(item, arg_fallback) for item in output_items) if c]
            if calls:
                for call in calls:
                    name = call["name"]
                    args = call["args"]
                    if name not in _RESEARCH_READONLY_TOOLS:
                        yield AgentEvent(EventType.error, {"error": f"tool '{name}' is not allowed (allowlist veto)", "provider": "openai", "model": request.model})
                        return
                    yield AgentEvent(EventType.tool_start, {"tool": name, "input": _redact_jsonish(args, token)})
                    ok, result = await self._invoke_tool(name=name, args=args, token=token)
                    summary = result[:_SUMMARY_CAP]
                    yield AgentEvent(EventType.tool_end, {"tool": name, "summary": summary, "chars": len(result), "is_error": not ok})
                    if ok:
                        used.append(name)
                    input_items.append({
                        "type": "function_call",
                        "name": name,
                        "call_id": call["call_id"],
                        "arguments": call["arguments"],
                    })
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": call["call_id"],
                        "output": summary,
                    })
                continue

            answer = _text_from_output_items(output_items) or "".join(text_parts)
            yield AgentEvent(EventType.done, {
                "answer": _redact_token(answer, token),
                "tools_used": sorted(set(used)),
                "provider": "openai",
                "model": request.model,
                "token_usage": total_usage,
            })
            return

        yield AgentEvent(EventType.error, {
            "error": f"Reached maximum number of turns ({self._max_turns})",
            "provider": "openai",
            "model": request.model,
        })


def _redact_jsonish(obj: Any, token: Optional[str]) -> Any:
    if isinstance(obj, dict):
        return {k: _redact_jsonish(v, token) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_jsonish(v, token) for v in obj]
    if isinstance(obj, str):
        return _redact_token(obj, token)
    return obj
