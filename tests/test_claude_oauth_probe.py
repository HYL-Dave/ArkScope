"""S4 Step 3: P3 probe — Claude setup-token (claude_code_oauth).

P3 proves the C≠D distinction from the auth plan:
  P3a: `claude -p` with CLAUDE_CODE_OAUTH_TOKEN set + ANTHROPIC_API_KEY unset → works.
  P3b: the raw Anthropic SDK passing that token as x-api-key → REJECTED (it is NOT
       an api.anthropic.com API key).
Both side effects are dependency-injected, so these tests use a FAKE token and
make NO real subprocess/network call. Results flow through the redacted harness.
"""

from __future__ import annotations

import json

import pytest

from src.auth_drivers.claude_oauth_probe import run_claude_code_oauth_probe

_TOK = "claude-setup-FAKEtok-AbCdEf0123456789ZyXwVu"


def test_p3_pass_cli_works_and_raw_sdk_rejects():
    res = run_claude_code_oauth_probe(
        _TOK,
        cli_fn=lambda: (True, "claude -p exited rc=0 with output"),
        raw_sdk_fn=lambda: (True, "raw SDK rejected: authentication_error"),
    )
    assert res["passed"] is True
    names = [p["name"] for p in res["probes"]]
    assert any("P3a" in n for n in names) and any("P3b" in n for n in names)
    assert all(p["passed"] for p in res["probes"])
    assert _TOK not in json.dumps(res)  # token never in the result


def test_p3a_fail_when_cli_errors():
    res = run_claude_code_oauth_probe(
        _TOK,
        cli_fn=lambda: (_ for _ in ()).throw(RuntimeError(f"claude -p rc=1 with {_TOK}")),
        raw_sdk_fn=lambda: (True, "rejected"),
    )
    assert res["passed"] is False
    p3a = next(p for p in res["probes"] if "P3a" in p["name"])
    assert p3a["passed"] is False
    assert _TOK not in json.dumps(res)  # token in the exception must be redacted


def test_p3b_fail_when_raw_sdk_unexpectedly_accepts():
    # If the raw SDK ACCEPTS the token, the C≠D invariant is violated → P3b fails.
    res = run_claude_code_oauth_probe(
        _TOK,
        cli_fn=lambda: (True, "ok"),
        raw_sdk_fn=lambda: (False, "raw SDK ACCEPTED the token — invariant violated"),
    )
    assert res["passed"] is False
    p3b = next(p for p in res["probes"] if "P3b" in p["name"])
    assert p3b["passed"] is False and "violated" in p3b["observed"]


def test_probe_never_raises_even_if_both_fail():
    res = run_claude_code_oauth_probe(
        _TOK,
        cli_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        raw_sdk_fn=lambda: (_ for _ in ()).throw(RuntimeError("kaboom")),
    )
    assert res["passed"] is False and len(res["probes"]) == 2


# --- the default raw-SDK reject probe: an auth error means PASS ---------------
def test_default_raw_sdk_probe_treats_auth_error_as_pass(monkeypatch):
    import src.auth_drivers.claude_oauth_probe as mod

    class FakeAuthError(Exception):
        pass

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        class messages:  # noqa: N801
            @staticmethod
            def create(*a, **k):
                raise FakeAuthError("401 authentication_error: invalid x-api-key")

    monkeypatch.setattr(mod, "_anthropic_client", lambda token: FakeClient())
    passed, observed = mod._default_raw_sdk_reject_probe(_TOK)
    assert passed is True and "reject" in observed.lower()


def test_default_raw_sdk_probe_fails_if_call_succeeds(monkeypatch):
    import src.auth_drivers.claude_oauth_probe as mod

    class FakeClient:
        class messages:  # noqa: N801
            @staticmethod
            def create(*a, **k):
                return object()  # unexpected success

    monkeypatch.setattr(mod, "_anthropic_client", lambda token: FakeClient())
    passed, observed = mod._default_raw_sdk_reject_probe(_TOK)
    assert passed is False and "accept" in observed.lower()
