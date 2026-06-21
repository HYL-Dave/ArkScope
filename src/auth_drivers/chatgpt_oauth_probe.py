"""S3 probe — OpenAI ChatGPT/Codex-backend OAuth (chatgpt_oauth) — P1 + P2.

Falsifiable proof of the A≠B distinction + the ChatGPT-backend capability floor
(LLM_AUTH_DRIVER_PLAN.md §9), grounded in Novelloom's PROVEN probe + driver
(`scripts/probe_chatgpt_oauth_backend.py`, `shared/auth/openai_chatgpt_oauth.py`):

  P1  : the OAuth access_token is REJECTED by api.openai.com (the standard public
        API) but STREAMS against https://chatgpt.com/backend-api/codex — proving it
        is NOT an `sk-` API key. (The only auth wiring is the SDK turning api_key
        into a Bearer header; the proven path sets NO custom headers, just a
        base_url swap.)
  P2a : the ChatGPT backend 400s `max_output_tokens` (Unsupported parameter). The
        probe sends it RAW — stripping is the *driver's* job; the probe measures
        the *backend's* real behavior.
  P2b : a single inline custom function call returns a `*_call` output item
        (Responses-API FLAT tool shape: {type:function,name,...}).
  P2c : model discovery needs a Codex-style `client_version` via `extra_query`,
        and ids come back in a nonstandard `models` field.

Every probe body is dependency-injected, AND the OpenAI client is built behind a
monkeypatchable seam (`_openai_client`), so the route + tests can run with a FAKE
transport and NO network call. Results flow through the redacted probe harness —
a token can never leak into a ProbeResult, even from an exception. No persistence.

This is the START of S3 (run P2 FIRST, per the plan); the factory `(openai,
chatgpt_oauth)` branch + the Settings import/probe routes are the END, landed only
AFTER this probe shows stable streaming + tool-call against a live subscription.
The probe uses the SYNC `OpenAI` client (like ArkScope's existing model discovery)
so it stays a plain sync `run_probe` consumer and is safe to call from an async
route without an `asyncio.run`-inside-a-loop hazard.
"""

from __future__ import annotations

from typing import Any, Callable

from .probe_harness import run_probe

# Hosts (the A≠B distinction): same OpenAI SDK pointed at two different backends.
STANDARD_BASE_URL = "https://api.openai.com/v1"
CHATGPT_BACKEND_BASE_URL = "https://chatgpt.com/backend-api/codex"

_PROBE_MODEL = "gpt-5.4-mini"  # cheap; per [[feedback-live-verify-cheap-models]]
_CLIENT_VERSION = "0.0.0"  # Codex-style discovery param (sent via extra_query, NOT a header)
_LOW_REASONING = {"effort": "low"}
_PING_INPUT = [{"role": "user", "content": "ping"}]
_OK_INPUT = [{"role": "user", "content": "Return exactly OK."}]

# A single inline custom function tool — Responses-API FLAT shape (NOT nested under "function").
_FUNCTION_TOOL = [
    {
        "type": "function",
        "name": "lookup_fact",
        "description": "Look up one fact by key.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["key"],
            "properties": {"key": {"type": "string"}},
        },
    }
]

_P1_NAME = "P1: OAuth token rejected by api.openai.com, accepted (streams) by the ChatGPT/Codex backend"
_P2A_NAME = "P2a: ChatGPT backend 400s max_output_tokens (Unsupported parameter)"
_P2B_NAME = "P2b: ChatGPT backend returns a function-call output item"
_P2C_NAME = "P2c: model discovery needs extra_query client_version (ids in nonstandard 'models')"


def _openai_client(token: str, base_url: str) -> Any:  # seam for tests
    """Build a sync OpenAI client with the OAuth access_token as the api_key and an
    explicit base_url. The SDK turns api_key into the `Authorization: Bearer`
    header; the proven ChatGPT-backend path adds no other headers."""
    from openai import OpenAI

    return OpenAI(api_key=token, base_url=base_url)


# --- response-shape helpers (mirror Novelloom's to_plain_dict / extract_*) -----
def _to_dict(value: Any) -> dict:
    """Reduce an SDK event/response to a plain dict (model_dump → to_dict → type)."""
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except Exception:  # noqa: BLE001
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:  # noqa: BLE001
            pass
    return {"type": value.__class__.__name__}


def _iter_output_items(response: Any) -> list:
    if response is None:
        return []
    output = _to_dict(response).get("output")
    return output if isinstance(output, list) else []


def _model_id_of(item: Any):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("id") or item.get("slug") or item.get("name")
    return getattr(item, "id", None)


def _model_ids(page: Any) -> list[str]:
    """Read model ids defensively: page.data, else the nonstandard page.models,
    else a `models` list inside the plain-dict form."""
    data = getattr(page, "data", None)
    if data is None:
        data = getattr(page, "models", None)
    if data is None:
        maybe = _to_dict(page).get("models")
        data = maybe if isinstance(maybe, list) else None
    if not data:
        return []
    return [mid for mid in (_model_id_of(i) for i in data) if isinstance(mid, str)]


def _err_summary(exc: BaseException) -> str:
    """Short, shape-only stringification of an error (ProbeResult redacts it too)."""
    status = getattr(exc, "status_code", None)
    try:
        msg = str(exc)
    except Exception:  # noqa: BLE001
        msg = "<unstringable>"
    head = f"{type(exc).__name__}{f' {status}' if status else ''}"
    return f"{head}: {msg}"[:160]


_AUTH_REJECT_STATUS = (401, 403)
_AUTH_REJECT_TYPES = ("AuthenticationError", "PermissionDeniedError")


def _is_auth_rejection(exc: BaseException) -> bool:
    """True ONLY for an auth-class rejection (HTTP 401/403). A network/timeout,
    404 model_not_found, 400 unsupported-parameter, or 429 rate-limit is NOT proof
    the OAuth token is unusable on the standard API — it is inconclusive, so it must
    NOT count as a P1a pass (a transient error could otherwise masquerade as the
    A≠B proof)."""
    if getattr(exc, "status_code", None) in _AUTH_REJECT_STATUS:
        return True
    return type(exc).__name__ in _AUTH_REJECT_TYPES


def _rejection_label(exc: BaseException) -> str:
    """A token-free label for an auth rejection: type + status only (NEVER the
    message, which a backend may echo a credential into)."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    return f"{status} {name}" if status else name


# --- default probe bodies (record SHAPE only; return (passed, observed)) --------
def _default_p1_host_distinctness(token: str) -> tuple[bool, str]:
    """PASS = api.openai.com REJECTS the token WITH AN AUTH ERROR (401/403) AND the
    codex backend STREAMS text. A non-auth error from the standard host (network,
    404, 400, 429) is inconclusive — explicitly NOT a pass."""
    # P1a — the standard public API must reject the OAuth token with an AUTH error.
    try:
        _openai_client(token, STANDARD_BASE_URL).responses.create(
            model=_PROBE_MODEL, input=_PING_INPUT, max_output_tokens=16,
        )
    except Exception as exc:  # noqa: BLE001
        if not _is_auth_rejection(exc):
            return False, (f"api.openai.com errored but NOT with an auth rejection "
                           f"({_err_summary(exc)}) — inconclusive, not a pass")
        std_reject = _rejection_label(exc)
    else:
        return False, ("api.openai.com ACCEPTED the OAuth token as an api_key — "
                       "the A/B host invariant is violated, STOP and re-derive")
    # P1b — the ChatGPT/Codex backend must stream text (no max_output_tokens).
    stream = _openai_client(token, CHATGPT_BACKEND_BASE_URL).responses.create(
        model=_PROBE_MODEL, input=_OK_INPUT, instructions="Reply with exactly OK.",
        stream=True, store=False,
    )
    chars, completed = 0, False
    for event in stream:
        raw = _to_dict(event)
        etype = raw.get("type")
        if etype == "response.output_text.delta":
            delta = raw.get("delta")
            if isinstance(delta, str):
                chars += len(delta)
        elif etype == "response.completed":
            completed = True
        elif etype in ("response.failed", "response.incomplete"):
            return False, f"codex backend stream ended with {etype}"
    if completed or chars:
        return True, f"standard host rejected ({std_reject}); codex backend streamed {chars} chars"
    return False, "codex backend stream produced no text or terminal event"


def _default_p2a_max_output_tokens(token: str) -> tuple[bool, str]:
    """PASS = the codex backend rejects a RAW max_output_tokens with a 400."""
    client = _openai_client(token, CHATGPT_BACKEND_BASE_URL)
    try:
        stream = client.responses.create(
            model=_PROBE_MODEL, input=_PING_INPUT, stream=True, store=False,
            instructions="Reply with exactly OK.",
            reasoning=_LOW_REASONING,
            max_output_tokens=8,  # RAW — the driver strips this; the probe measures the backend
        )
        for _event in stream:  # drain in case the 400 surfaces mid-stream
            pass
    except Exception as exc:  # noqa: BLE001
        msg = _err_summary(exc)
        if "max_output_tokens" in msg or "unsupported" in msg.lower():
            return True, f"backend rejected max_output_tokens ({msg})"
        return False, f"backend raised, but not the expected max_output_tokens 400 ({msg})"
    return False, "backend ACCEPTED max_output_tokens (expected 400 Unsupported parameter)"


def _default_p2b_function_call(token: str) -> tuple[bool, str]:
    """PASS = the response carries a `*_call` output item (one inline tool call)."""
    client = _openai_client(token, CHATGPT_BACKEND_BASE_URL)
    stream = client.responses.create(
        model=_PROBE_MODEL,
        input=[{"role": "user", "content": "Call lookup_fact with key='x'. Do not answer directly."}],
        instructions="Use the provided function when the user asks for a lookup.",
        reasoning=_LOW_REASONING,
        tools=_FUNCTION_TOOL, stream=True, store=False,
    )
    terminal = None
    event_types: list[str] = []
    for event in stream:
        raw = _to_dict(event)
        etype = raw.get("type")
        if isinstance(etype, str):
            event_types.append(etype)
        if etype == "response.completed":
            terminal = raw.get("response")
        elif etype in ("response.failed", "response.incomplete"):
            return False, f"stream ended with {etype} before any tool call"
    output_types: list[str] = []
    for item in _iter_output_items(terminal):
        itype = item.get("type") if isinstance(item, dict) else None
        if isinstance(itype, str):
            output_types.append(itype)
        if isinstance(itype, str) and itype.endswith("_call"):
            return True, f"harvested a {itype} output item"
    return (
        False,
        "no *_call output item in the response "
        f"(output_types={output_types or ['<none>']}; event_types={event_types or ['<none>']})",
    )


def _default_p2c_model_discovery(token: str) -> tuple[bool, str]:
    """PASS = plain models.list() 400s AND extra_query client_version returns ids."""
    client = _openai_client(token, CHATGPT_BACKEND_BASE_URL)
    plain_400 = False
    try:
        client.models.list()
    except Exception as exc:  # noqa: BLE001 — the backend may require client_version
        summary = _err_summary(exc)
        plain_400 = ("client_version" in summary) or ("400" in summary)
    page = client.models.list(extra_query={"client_version": _CLIENT_VERSION})
    ids = _model_ids(page)
    if plain_400 and ids:
        return True, f"plain models.list 400'd; extra_query client_version returned {len(ids)} model ids"
    if not plain_400 and ids:
        return False, f"extra_query returned {len(ids)} ids but plain models.list did NOT 400 (deviation)"
    return False, "model discovery returned no ids even with extra_query client_version"


def run_chatgpt_oauth_probe(
    token: str,
    *,
    p1_fn: Callable[[], Any] | None = None,
    p2a_fn: Callable[[], Any] | None = None,
    p2b_fn: Callable[[], Any] | None = None,
    p2c_fn: Callable[[], Any] | None = None,
) -> dict:
    """Run P1 + P2a/P2b/P2c through the redacted harness. Returns
    {passed: bool, probes: [<ProbeResult dict>, ...]} — never the token."""
    p1_fn = p1_fn or (lambda: _default_p1_host_distinctness(token))
    p2a_fn = p2a_fn or (lambda: _default_p2a_max_output_tokens(token))
    p2b_fn = p2b_fn or (lambda: _default_p2b_function_call(token))
    p2c_fn = p2c_fn or (lambda: _default_p2c_model_discovery(token))
    probes = [
        run_probe(_P1_NAME, expected="api.openai.com rejects; codex backend streams text", fn=p1_fn),
        run_probe(_P2A_NAME, expected="400 Unsupported parameter: max_output_tokens", fn=p2a_fn),
        run_probe(_P2B_NAME, expected="a *_call output item is returned", fn=p2b_fn),
        run_probe(_P2C_NAME, expected="plain 400; extra_query client_version returns >=1 model id", fn=p2c_fn),
    ]
    return {"passed": all(p.passed for p in probes), "probes": [p.model_dump() for p in probes]}
