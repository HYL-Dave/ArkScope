from dataclasses import replace

import pytest

from src.auth_drivers.lifecycle_web_models import ModelCall, WebModelError
from src.security_lifecycle_web_contract import validate_selection


def test_completed_invalid_reply_retains_output_and_usage_only_when_explicitly_enabled():
    from src.auth_drivers.lifecycle_web_models import completed_reply
    call = ModelCall(validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7"),
        "step-1", "analysis", "public input", {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        "high", None, 1, 60)
    with pytest.raises(WebModelError, match="model_output_invalid"):
        completed_reply(call, "owned-1", "not JSON", {"input_tokens": 3, "output_tokens": 4})
    reply = completed_reply(replace(call, retain_rejected_output=True), "owned-1", "not JSON", {"input_tokens": 3, "output_tokens": 4})
    assert reply.output_error == "model_output_invalid"
    assert reply.output == "not JSON" and reply.usage == {"input_tokens": 3, "output_tokens": 4}
