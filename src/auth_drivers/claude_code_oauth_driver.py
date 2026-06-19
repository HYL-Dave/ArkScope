"""Slice 7A-1 — AnthropicClaudeCodeOAuthDriver: run Research on a Claude
subscription via `claude -p`, mapping its stream-json to the existing AgentEvent.

Built on the Slice-7A spike (docs/design/LLM_AUTH_DRIVER_PLAN.md §"Slice 7A"):
- ISOLATED invocation: `claude -p --bare` (skip the dev .claude/ hooks/plugins/
  skills that otherwise inherit into the subprocess — the spike saw a $0.17 "OK"
  from hook injection) + an explicit `--model` and our own `--system-prompt`.
- AUTH: the subscription token is injected via env (CLAUDE_CODE_OAUTH_TOKEN) and
  ANTHROPIC_API_KEY is popped, so the subprocess uses the subscription, never an
  API key. The token comes from the token-store (NEVER llm_credentials.secret),
  is NEVER in argv, and is NEVER logged.
- OUTPUT: `--output-format stream-json --verbose` -> NDJSON mapped to the existing
  EventType vocab so the C-2 Research surface consumes it with zero changes.

The subprocess is launched with asyncio.create_subprocess_exec (the safe
execFile-equivalent: argv list, NO shell; the untrusted prompt is a positional
arg, never interpolated into a shell string).

This slice builds + factory-wires the driver and proves the mapping with a fake
subprocess. It is NOT yet on the live Research path -- `live_anthropic_client`
stays fail-closed for OAuth-active until the 7B wire-in.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.protocol import LLMRequest
from src.model_credentials import ModelDiscoveryResult, _seed_models

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 180.0
_DEFAULT_MAX_TURNS = 8  # a Research turn may use several tools; the API loop allows many more
_SUMMARY_CAP = 200


async def _default_spawn(argv: list[str], env: dict) -> Any:
    # create_subprocess_exec = safe execFile form: argv list, NO shell.
    return await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
    )


class AnthropicClaudeCodeOAuthDriver:
    """AuthDriver for (anthropic, claude_code_oauth) -- subscription via `claude -p`."""

    provider = "anthropic"
    auth_mode = "claude_code_oauth"

    def __init__(
        self,
        *,
        credential: Any = None,
        token_store: Any = None,
        spawn: Optional[Callable[[list[str], dict], Awaitable[Any]]] = None,
        which: Optional[Callable[[str], Optional[str]]] = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ):
        self.credential = credential
        self._token_store = token_store
        self._spawn = spawn or _default_spawn
        self._which = which or shutil.which
        self._max_turns = max_turns
        self._timeout_s = timeout_s
        self._credential_id = (
            f"local:{credential.id}" if credential is not None and getattr(credential, "id", None) is not None else None
        )

    # --- auth state ------------------------------------------------------
    @property
    def is_authenticated(self) -> bool:
        return self._load_token() is not None

    async def authenticate(self) -> None:  # token is pasted via the import route; nothing to do here
        return None

    async def refresh_if_needed(self) -> None:  # setup-token is a long-lived paste, no rotation
        return None

    async def get_quota_status(self) -> dict[str, Any]:
        return {"provider": self.provider, "auth_mode": self.auth_mode, "status": "unknown"}

    async def logout(self) -> None:  # the token lives in the token-store; logout is instance-local
        return None

    async def call_llm(self, request: LLMRequest):
        # Research uses stream_llm (the SSE surface); a non-streaming call_llm
        # isn't needed for this driver. Present so the AuthDriver contract holds.
        raise NotImplementedError("AnthropicClaudeCodeOAuthDriver is stream-only; use stream_llm")

    def _load_token(self) -> Optional[str]:
        if self._token_store is None or not self._credential_id:
            return None
        rec = self._token_store.load(
            provider="anthropic", auth_mode="claude_code_oauth", credential_id=self._credential_id,
        )
        return rec.access_token if rec and getattr(rec, "access_token", None) else None

    # --- the Research stream --------------------------------------------
    def stream_llm(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        # sync def returning an async generator (per the AuthDriver contract -- do
        # NOT await this; `async for` over it).
        return self._stream(request)

    async def _stream(self, request: LLMRequest) -> AsyncIterator[AgentEvent]:
        if self._which("claude") is None:
            raise RuntimeError(
                "Claude Code not installed. Install: npm install -g @anthropic-ai/claude-code"
            )
        token = self._load_token()
        if not token:
            raise MissingCredentialError(
                "no Claude setup-token stored for this credential -- import it in Settings"
            )

        argv = [
            "claude", "-p", "--bare",
            "--model", request.model,
            "--system-prompt", request.instructions or "",
            "--output-format", "stream-json", "--verbose",
            "--max-turns", str(self._max_turns),
            _compose_input(request.input_messages),
        ]
        env = os.environ.copy()
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token        # subscription auth
        env.pop("ANTHROPIC_API_KEY", None)            # never bill the API key
        logger.info("claude -p (subscription) model=%s max_turns=%s", request.model, self._max_turns)

        proc = await self._spawn(argv, env)
        tool_names: dict[str, str] = {}   # tool_use_id -> name, to label tool_end
        terminal = False
        loop = asyncio.get_event_loop()
        deadline = loop.time() + self._timeout_s
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    _terminate(proc)
                    yield _err(request, f"claude -p timed out after {self._timeout_s}s")
                    terminal = True
                    return
                try:
                    raw = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    _terminate(proc)
                    yield _err(request, f"claude -p timed out after {self._timeout_s}s")
                    terminal = True
                    return
                if not raw:  # EOF
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue  # malformed / partial / keepalive -- skip, not fatal
                for ev in _map(obj, request, tool_names):
                    if ev.type in (EventType.done, EventType.error):
                        terminal = True
                    yield ev
                    if terminal:
                        return
            # stdout EOF without a terminal: synthesize one error (never a silent done)
            if not terminal:
                rc = getattr(proc, "returncode", None)
                if rc is None:
                    try:
                        rc = await proc.wait()
                    except Exception:  # noqa: BLE001
                        rc = None
                if rc not in (0, None):
                    stderr = ""
                    try:
                        stderr = (await proc.stderr.read()).decode("utf-8", errors="replace")
                    except Exception:  # noqa: BLE001
                        stderr = ""
                    yield _err(request, f"claude -p exited {rc}: {_redact(stderr, token)[:500]}")
                else:
                    yield _err(request, "claude -p stream ended without a result")
        finally:
            # cancel / GeneratorExit / any exit -> never leave an orphan subprocess
            if getattr(proc, "returncode", None) is None:
                _terminate(proc)

    # --- ResearchProviderDriver surface ---------------------------------
    async def discover_models(self) -> ModelDiscoveryResult:
        # OAuth has no API-key discovery; the seed catalog is the candidate list.
        return ModelDiscoveryResult(
            provider="anthropic", credential_id=self._credential_id, status="ok",
            models=_seed_models("anthropic"),
        )


def _compose_input(input_messages: list[dict]) -> str:
    """The positional prompt for `claude -p`. v1: the last user message's content
    (multi-turn history folding is a 7B / run-manager concern)."""
    for msg in reversed(input_messages or []):
        if msg.get("role") != "system" and msg.get("content"):
            return str(msg["content"])
    return ""


def _terminate(proc: Any) -> None:
    try:
        proc.terminate()
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


def _redact(text: str, token: str) -> str:
    return text.replace(token, "[REDACTED]") if token and token in text else text


def _err(request: LLMRequest, message: str) -> AgentEvent:
    # data key 'error' first -- matches the C-2 reducer (query.py reads
    # data['error'] or data['message']) and agent.py's own error events.
    return AgentEvent(EventType.error, {"error": message, "provider": "anthropic", "model": request.model})


def _map(obj: dict, request: LLMRequest, tool_names: dict[str, str]) -> list[AgentEvent]:
    """Map one stream-json object to zero-or-more AgentEvents."""
    t = obj.get("type")
    if t == "system":
        return []  # init / hook_* setup noise
    if t == "assistant":
        out: list[AgentEvent] = []
        for block in obj.get("message", {}).get("content", []) or []:
            bt = block.get("type")
            if bt == "text":
                txt = (block.get("text") or "").strip()
                if txt:
                    out.append(AgentEvent(EventType.text, {"content": txt}))
            elif bt == "tool_use":
                name = block.get("name") or "tool"
                if block.get("id"):
                    tool_names[block["id"]] = name
                out.append(AgentEvent(EventType.tool_start, {"tool": name, "input": block.get("input") or {}}))
        return out
    if t == "user":
        out = []
        for block in obj.get("message", {}).get("content", []) or []:
            if block.get("type") == "tool_result":
                name = tool_names.get(block.get("tool_use_id"), "tool")
                summary = block.get("content")
                summary = summary if isinstance(summary, str) else json.dumps(summary, ensure_ascii=False)
                out.append(AgentEvent(EventType.tool_end, {
                    "tool": name, "summary": summary[:_SUMMARY_CAP], "chars": len(summary),
                }))
        return out
    if t == "result":
        # GOTCHA: subtype can be 'success' while is_error is true (captured live).
        if obj.get("is_error") or obj.get("subtype") == "error":
            return [_err(request, str(obj.get("result") or obj.get("error") or "claude -p reported an error"))]
        usage = obj.get("usage") or {}
        return [AgentEvent(EventType.done, {
            "answer": obj.get("result") or "",
            "tools_used": sorted(set(tool_names.values())),
            "provider": "anthropic",
            "model": request.model,
            "token_usage": {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                "cost_usd": obj.get("total_cost_usd"),
            },
        })]
    return []
