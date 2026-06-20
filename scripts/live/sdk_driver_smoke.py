"""7B live driver smoke — STANDALONE, NOT in the pytest suite; makes ONE real
billing call against the Claude subscription.

  HOW TO RUN:  python scripts/live/sdk_driver_smoke.py   (exit 0 = PASS)
  REQUIRES:    an ACTIVE anthropic `claude_code_oauth` credential in the local
               CredentialStore + its token in the token-store; network.
  COST:        ~one short Sonnet turn on the subscription (the §9 smoke model).

Drives the REAL AnthropicClaudeCodeSdkDriver via the repointed factory, with the real
ToolRegistry + DAL + token-store. Verifies the four §9 conditions the fake-SDK unit
tests cannot:
  1. subscription auth, NO API-key billing (a `done` terminal implies it — the driver
     ABORTS with an error if the init apiKeySource != none).
  2. a Tier-1 tool (get_sa_feed) actually invoked through the in-process bridge.
  3. Claude Code built-ins (Bash/Read/...) absent (dontAsk + tools=[] lock).
  4. the OAuth token never appears in any yielded event (no leak).
Fail-FAST pre-checks run BEFORE any live call (no wasted billing if the wiring is off).
The token is loaded at runtime from the token-store — it is NEVER hardcoded here.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.env_keys import ensure_env_loaded
ensure_env_loaded()
from src.auth_drivers.token_store import get_token_store
from src.auth_drivers.factory import build_driver
from src.auth_drivers.protocol import LLMRequest
from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS
from src.model_credentials import CredentialStore
from src.tools.registry import ToolRegistry

BASH_MARKER = "ARK_SMOKE_BASH"
BUILTINS = ["Bash", "Read", "Edit", "Write", "WebFetch", "WebSearch", "Glob", "Grep", "Task"]


def main() -> bool:
    # --- credential + token (pre-check; no live call yet) ---
    store = CredentialStore()
    cred = next((c for c in store.list("anthropic") if c.active and c.auth_type == "claude_code_oauth"), None)
    if cred is None:
        cred = next((c for c in store.list("anthropic") if c.auth_type == "claude_code_oauth"), None)
    if cred is None:
        print("FATAL: no anthropic claude_code_oauth credential in the store")
        return False
    print(f"credential: local:{cred.id} active={cred.active}")

    ts = get_token_store()
    rec = ts.load(provider="anthropic", auth_mode="claude_code_oauth", credential_id=f"local:{cred.id}")
    token = rec.access_token if rec else None
    if not token:
        print(f"FATAL: no token stored for local:{cred.id}")
        return False

    # --- real registry + allowlist↔registry pre-check (the fake-test blind spot) ---
    reg = ToolRegistry()
    reg.register_all()
    missing = sorted(n for n in _RESEARCH_READONLY_TOOLS if reg.get(n) is None)
    if missing:
        print(f"FATAL: allowlist names absent from the real registry: {missing} (no live call made)")
        return False
    print(f"registry: all {len(_RESEARCH_READONLY_TOOLS)} Tier-1 allowlist tools present")

    from src.api.dependencies import get_dal
    dal = get_dal()
    driver = build_driver(
        provider="anthropic", auth_mode="claude_code_oauth",
        credential=cred, token_store=ts, registry=reg, dal=dal,
    )
    print("driver:", type(driver).__name__)

    req = LLMRequest(
        model="claude-sonnet-4-6",
        instructions="You are a terse research assistant. Use the provided tools when asked.",
        input_messages=[{"role": "user", "content": (
            "Step 1: call the get_sa_feed tool for ticker AAPL and tell me in ONE line what it returned. "
            f"Step 2: try to run the shell command `echo {BASH_MARKER}` using the Bash tool and report its "
            "exact stdout; if you cannot, say exactly why."
        )}],
    )

    events = []
    err_raised = None

    async def run():
        async for ev in driver.stream_llm(req):
            kind = ev.type.value if hasattr(ev.type, "value") else str(ev.type)
            events.append((kind, ev.data))

    try:
        asyncio.run(asyncio.wait_for(run(), timeout=240))
    except Exception as e:  # surface a pre-flight raise (e.g. bridge build) without leaking token; operator signals (KeyboardInterrupt/SystemExit) propagate
        err_raised = type(e).__name__ + ": " + (str(e).replace(token, "[REDACTED]") if token else str(e))

    kinds = [k for k, _ in events]
    tool_starts = [d.get("tool") for k, d in events if k == "tool_start"]
    tool_ends = [d.get("tool") for k, d in events if k == "tool_end"]
    terminal = kinds[-1] if kinds else None
    blob = json.dumps(events, default=str, ensure_ascii=False)

    print("\n=== event kinds ===", kinds)
    print("tool_start:", tool_starts)
    print("tool_end:", tool_ends)
    done = next((d for k, d in events if k == "done"), None)
    err = next((d for k, d in events if k == "error"), None)
    if done:
        print("done.answer[:240]:", str(done.get("answer", ""))[:240].replace("\n", " "))
        print("done.tools_used:", done.get("tools_used"), "| token_usage:", done.get("token_usage"))
    if err:
        print("error.data:", err)
    if err_raised:
        print("raised:", err_raised)

    ark_called = "mcp__ark__get_sa_feed" in tool_starts
    ark_ended = any(t and "get_sa_feed" in t for t in tool_ends)
    builtin_called = [t for t in tool_starts if t in BUILTINS]
    token_leak = bool(token) and token in blob

    print("\n===== VERDICT =====")
    print("CHECK 1 subscription auth (done terminal; driver aborts on apiKeySource!=none):", terminal == "done")
    print("CHECK 2 Tier-1 bridge tool invoked (mcp__ark__get_sa_feed start+end):", ark_called and ark_ended)
    print("CHECK 3 built-ins absent (no built-in tool_start):", not builtin_called, "| seen:", builtin_called)
    print("CHECK 4 no token leak (token absent from every event):", not token_leak)
    ok = (terminal == "done") and ark_called and (not builtin_called) and (not token_leak)
    print("OVERALL:", "PASS" if ok else "FAIL")
    return ok


sys.exit(0 if main() else 1)
