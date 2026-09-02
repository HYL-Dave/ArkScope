"""Closed Settings probe for the Claude setup-token subscription path."""

from __future__ import annotations

import json
from pathlib import Path


def test_probe_uses_one_reviewed_subscription_call_without_fallback():
    from src.auth_drivers.claude_oauth_probe import run_claude_code_oauth_probe

    token_store = object()
    calls: list[dict] = []

    def structured_output(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    result = run_claude_code_oauth_probe(
        credential_id="local:7",
        token_store=token_store,
        structured_output_fn=structured_output,
    )

    assert result["passed"] is True
    assert len(result["probes"]) == 1
    assert len(calls) == 1
    assert calls[0]["provider"] == "anthropic"
    assert calls[0]["auth_mode"] == "claude_code_oauth"
    assert calls[0]["credential_id"] == "local:7"
    assert calls[0]["token_store"] is token_store
    assert calls[0]["model"] == "claude-sonnet-5"
    assert calls[0]["schema"] == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }


def test_probe_rejects_a_structurally_valid_but_false_result():
    from src.auth_drivers.claude_oauth_probe import run_claude_code_oauth_probe

    result = run_claude_code_oauth_probe(
        credential_id="local:7",
        token_store=object(),
        structured_output_fn=lambda **_kwargs: {"ok": False},
    )

    assert result["passed"] is False
    assert result["probes"][0]["observed"] == "unexpected structured result"


def test_probe_failure_is_redacted_and_never_retried():
    from src.auth_drivers.claude_oauth_probe import run_claude_code_oauth_probe

    calls = 0
    sentinel = "claude-setup-FAKEtok-AbCdEf0123456789ZyXwVu"

    def fail(**_kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError(f"provider rejected {sentinel}")

    result = run_claude_code_oauth_probe(
        credential_id="local:7",
        token_store=object(),
        structured_output_fn=fail,
    )

    assert result["passed"] is False
    assert calls == 1
    assert sentinel not in json.dumps(result)


def test_probe_module_has_no_external_cli_or_raw_sdk_fallback():
    import src.auth_drivers.claude_oauth_probe as probe

    source = Path(probe.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "shutil.which" not in source
    assert "_default_raw_sdk_reject_probe" not in source


def test_superseded_external_claude_driver_is_absent():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "src/auth_drivers/claude_code_oauth_driver.py").exists()
