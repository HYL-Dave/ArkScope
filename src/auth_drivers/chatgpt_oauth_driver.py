"""S3 — OpenAI ChatGPT/Codex-backend OAuth driver.

This driver makes an openai ``chatgpt_oauth`` credential report ITS OWN available
models — the ChatGPT/Codex backend's list, NOT the api-key seed catalog — so the
plan's "availability is PER (provider, auth_mode), NEVER shared" lock becomes real
on the wire. Discovery uses the reviewed Codex app-server ``model/list`` contract,
including provider-ordered reasoning efforts and input modalities.

Discovery is live (ChatGPT-backend model list). Execution uses the raw Responses
API against the ChatGPT/Codex backend — NOT the normal OpenAI API-key Agents SDK
path. Load-bearing request differences: no ``max_output_tokens``, forced
``stream=True`` + ``store=False``, no ``previous_response_id``.

The catalog adapter and execution client are monkeypatchable seams, and the token is
loaded from the token-store ONLY (never ``credential.secret``). Any surfaced error
is redacted — the token can never leak into a result.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from contextvars import copy_context
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from src.agents.shared.compressor.reducers import get_reducer
from src.agents.shared.events import AgentEvent, EventType
from src.agents.shared.output_boundary import remember_output_secret
from src.agents.shared.output_events import check_output_value, protect_events
# MissingCredentialError raise removed (S3 D4): early exits yield classified error events.
from src.auth_drivers.protocol import LLMRequest, LLMResponse, TokenUsage
from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult, _seed_models

from .chatgpt_oauth_login import ChatGPTOAuthLoginError
from .chatgpt_oauth_login import persist_chatgpt_plan_observation
from .chatgpt_oauth_login import provider_error_requires_reauth
from .chatgpt_oauth_login import refresh_if_needed as _refresh_login
from .chatgpt_oauth_probe import CHATGPT_BACKEND_BASE_URL, _PROBE_MODEL, _to_dict
from .probe_harness import redact

_PER_TOOL_TIMEOUT_S = 45.0
_DEFAULT_TIMEOUT_S = 900.0
_BRIDGE_RESULT_BUDGET = 12_000
_SUMMARY_CAP = 200
_DEFAULT_MAX_TURNS = 60

logger = logging.getLogger(__name__)

_RESEARCH_READONLY_TOOLS: frozenset[str] = frozenset(
    {
        "get_sa_feed",
        "get_sa_digest",
        "get_sa_alpha_picks",
        "get_ticker_news",
        "get_news_brief",
        "search_news_advanced",
        "get_ticker_prices",
        "get_current_quote",
        "get_price_change",
        "get_ticker_data_coverage",
        "get_fundamentals_analysis",
        "list_sec_filings",
        "get_sec_financial_facts",
        "read_sec_filing",
        "get_economic_calendar",
        "get_security_lifecycle_review",
        "list_security_lifecycle_reviews",
    }
)

def _subscription_catalog_adapter():
    from src.auth_drivers.codex_account_usage import CodexAccountUsageAdapter

    return CodexAccountUsageAdapter()


def _task_route_tasks(model: str, *, plan_type: str | None = None) -> list[str]:
    from src.model_capabilities import capability_for
    from src.model_effective import task_auth_executable
    from src.model_routing import TASK_IDS

    capability = capability_for(model)
    if capability is None or capability.task_route_status != "current":
        return []
    if capability.exact_model_id and model != capability.id:
        return []
    return [
        task
        for task in TASK_IDS
        if task_auth_executable(
            task,
            "openai",
            "chatgpt_oauth",
            capability,
            plan_type=plan_type,
        )
    ]


def _execution_client(token: str) -> Any:  # seam for tests
    from openai import AsyncOpenAI
    from src.auth_drivers.runtime_binding import pinned_auth_headers

    return AsyncOpenAI(
        api_key=token, base_url=CHATGPT_BACKEND_BASE_URL, timeout=300,
        default_headers=pinned_auth_headers("openai", token),
    )


def _err(exc: BaseException) -> str:
    """Token-free, shape-only error string (redacted as defense-in-depth)."""
    return redact(f"{type(exc).__name__}: {exc}")[:200]


def _redact_token(text: Any, token: Optional[str]) -> str:
    from src.auth_drivers.runtime_binding import sanitize_runtime_error

    return sanitize_runtime_error(text, api_key=token)


def _int_token(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dict_get(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _usage_cache_read_tokens(usage: dict[str, Any]) -> int:
    for details_key in ("prompt_tokens_details", "input_tokens_details"):
        details = usage.get(details_key)
        cached = _dict_get(details, "cached_tokens") if details is not None else None
        if cached:
            return _int_token(cached)
    return _int_token(usage.get("cached_tokens"))


def _accumulate_token_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    in_tokens = _int_token(usage.get("input_tokens") or usage.get("prompt_tokens"))
    out_tokens = _int_token(usage.get("output_tokens") or usage.get("completion_tokens"))
    total["input_tokens"] = total.get("input_tokens", 0) + in_tokens
    total["output_tokens"] = total.get("output_tokens", 0) + out_tokens
    total["total_tokens"] = total.get("total_tokens", 0) + _int_token(usage.get("total_tokens") or (in_tokens + out_tokens))
    cache_read = _usage_cache_read_tokens(usage)
    if cache_read:
        total["cache_read_tokens"] = total.get("cache_read_tokens", 0) + cache_read
    cache_create = _int_token(usage.get("cache_creation_input_tokens"))
    if cache_create:
        total["cache_creation_tokens"] = total.get("cache_creation_tokens", 0) + cache_create


def _ark_input_schema(tool_def: Any) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []
    for p in getattr(tool_def, "parameters", None) or []:
        prop: dict = {"type": getattr(p, "type", "string")}
        if getattr(p, "description", None):
            prop["description"] = p.description
        if getattr(p, "enum", None):
            prop["enum"] = p.enum
        if getattr(p, "items", None) is not None:
            prop["items"] = p.items
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
        # Responses otherwise normalizes optional registry parameters to required.
        "strict": False,
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
    if not effort or effort == "default":
        return None
    return {"effort": effort}


async def _close_execution_client(client: Any) -> None:
    close = getattr(client, "close", None) or getattr(client, "aclose", None)
    if close is None:
        return
    try:
        await _maybe_await(close())
    except Exception:  # noqa: BLE001 - cleanup must not replace the provider result
        logger.warning("failed to close ChatGPT OAuth execution client")


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


class _ToolCallIdentityError(ValueError):
    pass


def _resolve_call_item(
    item: dict,
    output_index: Any,
    call_items: dict[int, dict],
    call_keys: dict[tuple[str, str | int], int],
    *,
    allow_new: bool = False,
) -> dict:
    identities = {name: item[name] for name in ("call_id", "id") if item.get(name) is not None}
    if any(not isinstance(value, str) or not value for value in identities.values()):
        raise _ToolCallIdentityError
    if output_index is not None:
        if type(output_index) is not int or output_index < 0:
            raise _ToolCallIdentityError
        identities["output_index"] = output_index
    if not identities:
        if not allow_new and len(call_items) == 1:
            return next(iter(call_items.values()))
        raise _ToolCallIdentityError

    # Every supplied identity must resolve to the same call, without rebinding.
    matches = {call_keys[identity] for identity in identities.items() if identity in call_keys}
    if len(matches) > 1:
        raise _ToolCallIdentityError
    if matches:
        key = next(iter(matches))
    elif allow_new and ("call_id" in identities or "id" in identities):
        key = len(call_items)
    else:
        raise _ToolCallIdentityError
    call = call_items.get(key, {})
    if any(call.get(name) is not None and call[name] != value for name, value in identities.items()):
        raise _ToolCallIdentityError
    call.update(identities)
    call_items[key] = call
    call_keys.update((identity, key) for identity in identities.items())
    return call


def _call_from_item(item: dict, arg_fallback: dict[str, str]) -> Optional[dict]:
    if item.get("type") != "function_call" or item.get("status") not in (None, "completed"):
        return None
    name = item.get("name")
    call_id = item.get("call_id") or item.get("id")
    if not isinstance(name, str) or not name or not isinstance(call_id, str) or not call_id:
        return None
    arguments = item.get("arguments")
    if not isinstance(arguments, str) or not arguments.strip():
        arguments = arg_fallback.get(call_id)
        item_id = item.get("id")
        if not arguments and isinstance(item_id, str):
            arguments = arg_fallback.get(item_id)
    if not isinstance(arguments, str) or not arguments.strip():
        raise ValueError("invalid_tool_arguments")
    try:
        args = json.loads(arguments)
    except (TypeError, ValueError):
        raise ValueError("invalid_tool_arguments") from None
    if not isinstance(args, dict):
        raise ValueError("invalid_tool_arguments")
    return {"name": name, "call_id": call_id, "arguments": arguments, "args": args}


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
        # The pre-refresh early exits are SPLIT (S3 plan D4): a missing token-store
        # dependency or credential id is driver wiring — re-login cannot repair it;
        # only "store + id present, stored token absent" earns the reauth code.
        if self._token_store is None or not self._credential_id:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
                error_code="missing_credential",
            )
        if not self._load_token():
            # No stored token for an existing OAuth row → repairable ONLY by re-login.
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
                error_code="reauth_required",
            )
        # Refresh the (possibly expired) access token FIRST so "available models" doesn't
        # intermittently degrade. A refresh failure means the login is stale → surface a
        # clear re-login hint (redacted), not a silent seed fallback with no reason.
        try:
            rec = _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
            token = rec.access_token if rec else None
        except ChatGPTOAuthLoginError as exc:
            # F3 (round 4): the human-readable text must agree with the code —
            # only a classified reauth failure may demand a re-login.
            reauth = getattr(exc, "reauth_required", False)
            message = (
                f"re-login needed (token refresh failed): {_err(exc)}" if reauth
                else f"token refresh failed (temporary — retry later): {_err(exc)}"
            )
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error=message,
                error_code="reauth_required" if reauth else None,
            )
        if not token:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="missing_credential", models=_seed_models("openai"),
                error_code="reauth_required",
            )
        try:
            adapter = _subscription_catalog_adapter()
            if hasattr(adapter, "read_model_catalog_with_plan"):
                catalog, observed_plan = adapter.read_model_catalog_with_plan(record=rec)
                if observed_plan is not None:
                    try:
                        rec = persist_chatgpt_plan_observation(
                            credential_id=self._credential_id,
                            token_store=self._token_store,
                            expected_record=rec,
                            plan_type=observed_plan,
                            observed_at=datetime.now(timezone.utc),
                        )
                    except ChatGPTOAuthLoginError as exc:
                        if exc.error_code != "plan_observation_store_failed":
                            raise
                        logger.warning("ChatGPT plan diagnostic could not be stored")
            else:
                catalog = adapter.read_model_catalog(record=rec)
        except Exception as exc:  # noqa: BLE001 — never raise discovery; degrade to seed
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"), error=_err(exc),
            )
        if not catalog:
            return ModelDiscoveryResult(
                provider="openai", credential_id=self._credential_id,
                status="error", models=_seed_models("openai"),
                error="the Codex app-server returned no subscription models",
            )
        models = [
            DiscoveredModel(
                id=row.model,
                provider="openai",
                label=row.display_name,
                source="provider_api",
                effort_options=list(row.supported_reasoning_efforts),
                default_effort=row.default_reasoning_effort,
                input_modalities=list(row.input_modalities),
                task_route_tasks=_task_route_tasks(row.model, plan_type=rec.plan_type),
            )
            for row in catalog
        ]
        return ModelDiscoveryResult(
            provider="openai", credential_id=self._credential_id,
            status="ok",
            models=models,
            source_url="https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#models",
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
        return protect_events(self._managed_stream(request))

    async def _managed_stream(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        clients: list[Any] = []
        stream = self._stream(request, client_sink=clients.append)
        try:
            async for event in stream:
                yield event
        finally:
            await stream.aclose()
            for client in clients:
                await _close_execution_client(client)

    def _build_tools(self) -> list[dict]:
        if self._registry is None:
            return []
        tools: list[dict] = []
        from src.sec_research.tool_results import require_sec_inventory
        require_sec_inventory(n for n in _RESEARCH_READONLY_TOOLS
                              if self._registry is not None and self._registry.get(n) is not None)
        for name in sorted(_RESEARCH_READONLY_TOOLS):
            tool_def = self._registry.get(name)
            if tool_def is not None:
                tools.append(_tool_schema(name, tool_def))
        return tools

    async def _invoke_tool(self, *, name: str, args: dict, token: Optional[str]) -> tuple[bool, str]:
        try:
            if name not in _RESEARCH_READONLY_TOOLS:
                return False, "invalid_value: tool is not allowed (allowlist veto)"
            tool_def = self._registry.get(name) if self._registry is not None else None
            if tool_def is None:
                return False, "invalid_value: tool is not registered"
            from src.tools.result_policy import tool_output_guard

            args = check_output_value(args, guard=tool_output_guard(token))
            fn = tool_def.function
            requires_dal = getattr(tool_def, "requires_dal", True)
            from src.sec_research.tool_results import SEC_TOOL_NAMES, active_budget

            async def _run():
                if name in SEC_TOOL_NAMES:
                    from src.sec_research.tool_execution import invoke_sec_tool
                    return await invoke_sec_tool(name, args, timeout_s=self._per_tool_timeout_s)
                if asyncio.iscoroutinefunction(fn):
                    return await (fn(self._dal, **args) if requires_dal else fn(**args))
                call = (lambda: fn(self._dal, **args)) if requires_dal else (lambda: fn(**args))
                loop = asyncio.get_running_loop()
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ark-openai-oauth")
                try:
                    return await loop.run_in_executor(pool, copy_context().run, call)
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)

            try:
                # SEC owns its deadline and waits for stopped acquisition before
                # returning a complete timeout envelope. Do not race a second timer.
                raw = (await _run() if name in SEC_TOOL_NAMES else
                       await asyncio.wait_for(_run(), timeout=self._per_tool_timeout_s))
            except asyncio.TimeoutError:
                return False, f"tool '{name}' timed out after {self._per_tool_timeout_s}s"
            from src.tools.result_policy import admit_tool_result, tool_output_guard

            result = admit_tool_result(
                raw, policy=getattr(tool_def, "result_policy", None), guard=tool_output_guard(token),
            )
            budget = _BRIDGE_RESULT_BUDGET
            if name in SEC_TOOL_NAMES:
                from src.agents.shared.security import wrap_tool_result
                result = wrap_tool_result(result, name)
                budget = active_budget()
            sized, _meta = get_reducer(name)(result, budget=budget)
            return True, sized
        except BaseException as exc:  # noqa: BLE001
            from src.tools.result_policy import sanitize_tool_error

            return False, sanitize_tool_error(exc, token=token)

    async def _stream(
        self,
        request: LLMRequest,
        *,
        client_sink=None,
    ) -> AsyncIterator[AgentEvent]:
        # Classified early exits (S3 plan D4) — one machine-readable error event,
        # never a bare exception, never a backend call. Wiring vs token-absent
        # arms are split exactly like discover_models.
        if self._token_store is None or not self._credential_id:
            # getattr: these exits must stay reachable even for a malformed/None
            # request — the classified event IS the fail-closed surface.
            yield AgentEvent(EventType.error, {
                "error": "ChatGPT OAuth driver is missing its token store or credential id",
                "code": "missing_credential", "provider": "openai",
                "model": getattr(request, "model", None),
            })
            return
        token = self._load_token()
        if not token:
            yield AgentEvent(EventType.error, {
                "error": "no ChatGPT OAuth token stored for this credential -- log in from Settings",
                "code": "reauth_required", "provider": "openai",
                "model": getattr(request, "model", None),
            })
            return
        try:
            rec = _refresh_login(credential_id=self._credential_id, token_store=self._token_store)
            token = rec.access_token if rec and rec.access_token else token
        except ChatGPTOAuthLoginError as exc:
            payload = {"error": f"ChatGPT OAuth refresh failed: {_err(exc)}", "provider": "openai", "model": request.model}
            if getattr(exc, "reauth_required", False):
                payload["code"] = "reauth_required"
            yield AgentEvent(EventType.error, payload)
            return

        remember_output_secret(token)
        client = _execution_client(token)
        if client_sink is not None:
            client_sink(client)
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
            response_completed = False
            arg_fallback: dict[str, str] = {}
            call_items: dict[int, dict] = {}
            call_keys: dict[tuple[str, str | int], int] = {}
            invalid_call_identity = False
            text_parts: list[str] = []
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
                            yield AgentEvent(EventType.text, {"content": delta})
                    elif etype == "response.function_call_arguments.done":
                        try:
                            call = _resolve_call_item(
                                {"call_id": raw.get("call_id"), "id": raw.get("item_id")},
                                raw.get("output_index"), call_items, call_keys,
                            )
                        except _ToolCallIdentityError:
                            invalid_call_identity = True
                            continue
                        args = raw.get("arguments")
                        if isinstance(args, str):
                            for name in ("call_id", "id"):
                                if isinstance(call.get(name), str):
                                    arg_fallback[call[name]] = args
                        if call.get("status") == "in_progress":
                            call.update(arguments=args, status="completed")
                    elif etype in ("response.output_item.added", "response.output_item.done"):
                        item = raw.get("item") or raw.get("output_item")
                        if isinstance(item, dict) and item.get("type") == "function_call":
                            try:
                                call = _resolve_call_item(
                                    item, raw.get("output_index"), call_items, call_keys, allow_new=True,
                                )
                            except _ToolCallIdentityError:
                                invalid_call_identity = True
                                continue
                            if etype == "response.output_item.done":
                                snapshot = {name: value for name, value in item.items()
                                            if name not in ("id", "call_id") or value is not None}
                                call.update(snapshot, status=item.get("status") or "completed")
                            elif "type" not in call:
                                call.update(item, status="in_progress")
                    elif etype == "response.completed":
                        response_obj = raw.get("response")
                        response_completed = True
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
            except GeneratorExit:
                raise
            except BaseException as exc:  # noqa: BLE001
                payload = {
                    "error": _redact_token(str(exc), token)[:500],
                    "provider": "openai",
                    "model": request.model,
                }
                if provider_error_requires_reauth(exc):
                    payload["code"] = "reauth_required"
                yield AgentEvent(EventType.error, payload)
                return

            if not response_completed:
                yield AgentEvent(EventType.error, {
                    "error": "ChatGPT backend stream ended before response.completed",
                    "code": "incomplete_response", "provider": "openai", "model": request.model,
                })
                return

            # The backend can complete with output=[] despite completed streamed calls.
            final_output = _response_output_items(response_obj)
            if invalid_call_identity and not final_output:
                yield AgentEvent(EventType.error, {
                    "error": "ChatGPT backend returned ambiguous or conflicting tool call identity",
                    "code": "invalid_tool_call_identity", "provider": "openai", "model": request.model,
                })
                return
            output_items = final_output or list(call_items.values())
            # A complete final snapshot may supersede bad provisional identities,
            # but it must not borrow arguments from that ambiguous fallback.
            fallback = {} if invalid_call_identity else arg_fallback
            usage = _to_dict(response_obj).get("usage") if response_obj else None
            if isinstance(usage, dict):
                _accumulate_token_usage(total_usage, usage)

            try:
                calls = [c for c in (_call_from_item(item, fallback) for item in output_items) if c]
            except ValueError:
                yield AgentEvent(EventType.error, {
                    "error": "ChatGPT backend returned invalid tool arguments",
                    "code": "invalid_tool_arguments", "provider": "openai", "model": request.model,
                })
                return
            if calls:
                for call in calls:
                    name = call["name"]
                    args = call["args"]
                    check_output_value(call)
                    if name not in _RESEARCH_READONLY_TOOLS:
                        yield AgentEvent(EventType.error, {"error": f"tool '{name}' is not allowed (allowlist veto)", "provider": "openai", "model": request.model})
                        return
                    yield AgentEvent(EventType.tool_start, {
                        "tool": name, "input": args, "call_id": call["call_id"],
                    })
                    ok, result = await self._invoke_tool(name=name, args=args, token=token)
                    from src.tools.result_policy import tool_output_guard

                    result = check_output_value(result, guard=tool_output_guard(token))
                    from src.sec_research.citations import citation_event_fields

                    citation_fields = citation_event_fields(name, result if ok else {
                        "content": [{"type": "text", "text": result}], "is_error": True,
                    })
                    summary = result[:_SUMMARY_CAP]
                    yield AgentEvent(EventType.tool_end, {
                        "tool": name, "summary": summary, "chars": len(result), "is_error": not ok,
                        "call_id": call["call_id"], "input": args, **citation_fields,
                    })
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
                        "output": result,
                    })
                continue

            answer = _text_from_output_items(output_items) or "".join(text_parts)
            yield AgentEvent(EventType.done, {
                "answer": answer,
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
