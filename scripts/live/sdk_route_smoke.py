"""7B-6 backend live smoke — STANDALONE, NOT in the pytest suite; makes ONE real
billing call against the Claude subscription.

  HOW TO RUN:  python scripts/live/sdk_route_smoke.py   (exit 0 = PASS)
  REQUIRES:    an ACTIVE anthropic `claude_code_oauth` credential in the local
               CredentialStore + its token in the token-store; network.
  COST:        ~one short Sonnet turn on the subscription.

Drives the NEW route helper _anthropic_subscription_stream (src/api/routes/query.py)
LIVE: resolve_live_auth -> credential_id -> CredentialStore.get -> ToolRegistry.register_all
-> build_driver -> driver.stream_llm, one real subscription call. The 7B-6 handler-direct
tests cover branch-selection / SSE / persistence with a MOCKED driver; this covers the
REAL driver build+run through the helper's exact path.
The token is loaded at runtime from the token-store — it is NEVER hardcoded here.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.env_keys import ensure_env_loaded
ensure_env_loaded()
from src.auth_drivers.live_resolver import resolve_live_auth
from src.auth_drivers.token_store import get_token_store
from src.api.dependencies import get_dal
from src.api.routes.query import _anthropic_subscription_stream

BASH_MARKER = "ARK_ROUTE_SMOKE"
BUILTINS = ["Bash", "Read", "Edit", "Write", "WebFetch", "WebSearch", "Glob", "Grep", "Task"]


def main() -> bool:
    auth = resolve_live_auth("anthropic")
    print("resolve_live_auth('anthropic') ->", auth.source, auth.credential_id)
    if auth.source != "oauth_driver_unwired":
        print(f"FATAL: expected claude_code_oauth active (oauth_driver_unwired); got {auth.source!r}. "
              "Make an anthropic claude_code_oauth credential the active one first.")
        return False
    rec = get_token_store().load(provider="anthropic", auth_mode="claude_code_oauth", credential_id=auth.credential_id)
    token = rec.access_token if rec else None
    if not token:
        print(f"FATAL: no token stored for {auth.credential_id}")
        return False

    stream = _anthropic_subscription_stream(
        credential_id=auth.credential_id,
        question=("Step 1: call the get_sa_feed tool for ticker AAPL and tell me in ONE line what it returned. "
                  f"Step 2: try to run the shell command `echo {BASH_MARKER}` via the Bash tool and report its "
                  "stdout, or say exactly why you cannot."),
        model="claude-sonnet-4-6", effort=None, dal=get_dal(), history=[],
    )

    events = []

    async def run():
        async for ev in stream:
            k = ev.type.value if hasattr(ev.type, "value") else str(ev.type)
            events.append((k, ev.data))

    asyncio.run(asyncio.wait_for(run(), timeout=240))

    kinds = [k for k, _ in events]
    tstarts = [d.get("tool") for k, d in events if k == "tool_start"]
    tends = [d.get("tool") for k, d in events if k == "tool_end"]
    blob = json.dumps(events, default=str, ensure_ascii=False)
    done = next((d for k, d in events if k == "done"), None)
    err = next((d for k, d in events if k == "error"), None)

    print("event kinds:", kinds)
    print("tool_start:", tstarts, "| tool_end:", tends)
    if done:
        print("done.answer[:240]:", str(done.get("answer", ""))[:240].replace("\n", " "))
        print("done.tools_used:", done.get("tools_used"))
    if err:
        print("error:", err)

    ark = "mcp__ark__get_sa_feed" in tstarts
    builtin = [t for t in tstarts if t in BUILTINS]
    leak = bool(token) and token in blob
    term = kinds[-1] if kinds else None

    print("\n== VERDICT ==")
    print("C1 subscription auth (done terminal):", term == "done")
    print("C2 Tier-1 tool via in-process bridge:", ark and any(t and "get_sa_feed" in t for t in tends))
    print("C3 built-ins absent:", not builtin, "|", builtin)
    print("C4 no token leak:", not leak)
    ok = (term == "done") and ark and (not builtin) and (not leak)
    print("OVERALL:", "PASS" if ok else "FAIL")
    return ok


sys.exit(0 if main() else 1)
