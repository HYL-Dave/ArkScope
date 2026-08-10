"""Anthropic manual account-usage adapter: one bounded Messages request,
unified-header truth, typed failures, and secret-free artifacts.

Imports of the future adapter module stay inside test bodies so collection
succeeds while the module is absent (plan §3.1 RED rule)."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

import anthropic

_TOKEN = "anthropic-oauth-token-fixture-must-not-escape"
_OBSERVED_AT = "2026-08-10T12:00:00+00:00"
_IDENTITY_BLOCK = "You are Claude Code, Anthropic's official CLI for Claude."


def _probe_record(*, access_token: str | None = _TOKEN):
    from src.auth_drivers.token_store import StoredTokenRecord

    return StoredTokenRecord(
        access_token=access_token or "",
        expires_at="2027-08-10T12:00:00+00:00",
        plan_type="max",
        account_label="Claude subscription",
        metadata={},
    )


def _unified_headers(**overrides: str | None) -> dict[str, str]:
    headers = {
        "anthropic-ratelimit-unified-status": "allowed",
        "anthropic-ratelimit-unified-reset": "1786294800",
        "anthropic-ratelimit-unified-5h-status": "allowed",
        "anthropic-ratelimit-unified-5h-utilization": "0.05",
        "anthropic-ratelimit-unified-5h-reset": "1786294800",
        "anthropic-ratelimit-unified-7d-status": "allowed",
        "anthropic-ratelimit-unified-7d-utilization": "0.14",
        "anthropic-ratelimit-unified-7d-reset": "1786687200",
        "anthropic-ratelimit-unified-overage-status": "rejected",
        "anthropic-ratelimit-unified-overage-disabled-reason": "org_level_disabled",
        "anthropic-ratelimit-unified-representative-claim": "five_hour",
        "anthropic-ratelimit-unified-fallback-percentage": "0.5",
    }
    for key, value in overrides.items():
        name = key.replace("__", "-")
        if value is None:
            headers.pop(name, None)
        else:
            headers[name] = value
    return headers


class _RecordingRaw:
    def __init__(self, headers: dict[str, str] | None = None, error: Exception | None = None):
        self.headers = _unified_headers() if headers is None else headers
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(headers=httpx.Headers(self.headers))


class _FakeClient:
    def __init__(self, raw):
        self.messages = SimpleNamespace(with_raw_response=raw)
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def _client(raw: _RecordingRaw) -> _FakeClient:
    return _FakeClient(raw)


def _status_error(status_code: int, headers: dict[str, str] | None = None):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, headers=headers or {}, request=request)
    return anthropic.APIStatusError("status", response=response, body=None)


def _adapter(raw: _RecordingRaw, **kwargs):
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageAdapter

    client = _client(raw)
    adapter = AnthropicAccountUsageAdapter(client_factory=lambda token: client, **kwargs)
    adapter._test_client = client
    return adapter


def _read(raw: _RecordingRaw, *, credential_id: str = "local:9", record=None):
    return _adapter(raw).read_account_usage(
        credential_id=credential_id,
        record=record if record is not None else _probe_record(),
        observed_at=_OBSERVED_AT,
    )


def test_manual_sync_sends_one_request_with_auth_token_beta_identity_block_and_max_tokens_8(
    monkeypatch,
):
    from src.auth_drivers import anthropic_account_usage as module
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    constructed: list[dict] = []
    raw = _RecordingRaw()

    class _RecorderClient:
        def __init__(self, **kwargs):
            constructed.append(kwargs)
            self.messages = SimpleNamespace(with_raw_response=raw)
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    recorder_clients: list[_RecorderClient] = []
    _original_new = _RecorderClient.__new__

    def _tracking_new(cls, *args, **kwargs):
        instance = object.__new__(cls)
        recorder_clients.append(instance)
        return instance

    _RecorderClient.__new__ = _tracking_new

    monkeypatch.setattr(module.anthropic, "Anthropic", _RecorderClient)
    module.AnthropicAccountUsageAdapter().read_account_usage(
        credential_id="local:9", record=_probe_record(), observed_at=_OBSERVED_AT
    )
    assert len(constructed) == 1
    assert constructed[0]["auth_token"] == _TOKEN
    assert constructed[0]["api_key"] is None
    assert constructed[0]["timeout"] == 20.0
    assert constructed[0]["max_retries"] == 0
    assert len(raw.calls) == 1
    call = raw.calls[0]
    assert call["model"] == "claude-sonnet-5"
    assert call["max_tokens"] == 8
    assert call["extra_headers"] == {"anthropic-beta": "oauth-2025-04-20"}
    assert call["system"][0] == {"type": "text", "text": _IDENTITY_BLOCK}
    assert call["messages"] == [{"role": "user", "content": "Reply with exactly: OK"}]
    assert "tools" not in call and "stream" not in call
    assert len(recorder_clients) == 1
    assert recorder_clients[0].close_calls == 1

    rejected_raw = _RecordingRaw(error=_status_error(400))
    raw = rejected_raw
    with pytest.raises(AnthropicAccountUsageError) as rejected:
        module.AnthropicAccountUsageAdapter().read_account_usage(
            credential_id="local:9",
            record=_probe_record(),
            observed_at=_OBSERVED_AT,
        )
    assert rejected.value.code == "provider_request_rejected"
    assert len(rejected_raw.calls) == 1
    assert rejected_raw.calls[0] == call
    assert len(constructed) == 2
    assert constructed[1] == constructed[0]
    assert len(recorder_clients) == 2
    assert recorder_clients[1].close_calls == 1


def test_2xx_unified_headers_record_five_hour_and_seven_day_observation():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    with pytest.raises(AnthropicAccountUsageError) as empty:
        _read(_RecordingRaw(headers={}))
    assert empty.value.code == "quota_headers_unavailable"
    with pytest.raises(AnthropicAccountUsageError) as no_authority:
        _read(
            _RecordingRaw(
                headers=_unified_headers(
                    **{"anthropic__ratelimit__unified__status": None}
                )
            )
        )
    assert no_authority.value.code == "quota_headers_unavailable"

    partial = _read(
        _RecordingRaw(
            headers=_unified_headers(
                **{"anthropic__ratelimit__unified__7d__utilization": None}
            )
        )
    )
    assert partial.payload.rate_limits.secondary.used_percent is None
    assert partial.payload.rate_limits.primary.used_percent == 5.0

    observation = _read(_RecordingRaw())
    limits = observation.payload.rate_limits
    assert limits.primary.used_percent == 5.0
    assert limits.primary.window_duration_minutes == 300
    assert limits.primary.resets_at == 1786294800
    assert limits.secondary.used_percent == 14.0
    assert limits.secondary.window_duration_minutes == 10080
    assert limits.secondary.resets_at == 1786687200
    assert limits.status == "allowed"
    assert limits.overage_status == "rejected"
    assert limits.overage_disabled_reason == "org_level_disabled"
    assert limits.limit_id == "five_hour"
    assert observation.observed_at == _OBSERVED_AT


def test_429_with_unified_headers_records_rejected_quota_observation():
    headers = _unified_headers(
        **{
            "anthropic__ratelimit__unified__status": "rejected",
            "anthropic__ratelimit__unified__5h__status": "rejected",
            "anthropic__ratelimit__unified__5h__utilization": "1",
        }
    )
    raw = _RecordingRaw(error=_status_error(429, headers))
    observation = _read(raw)
    limits = observation.payload.rate_limits
    assert limits.status == "rejected"
    assert limits.primary.used_percent == 100.0
    assert limits.secondary.used_percent == 14.0

    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    with pytest.raises(AnthropicAccountUsageError) as contradictory:
        _read(_RecordingRaw(error=_status_error(429, _unified_headers())))
    assert contradictory.value.code == "quota_headers_unavailable"


def test_429_without_unified_headers_is_quota_headers_unavailable_not_a_snapshot():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    raw = _RecordingRaw(error=_status_error(429, {"retry-after": "60"}))
    with pytest.raises(AnthropicAccountUsageError) as caught:
        _read(raw)
    assert caught.value.code == "quota_headers_unavailable"


def test_provider_401_and_403_map_to_typed_rejections_and_preserve_last_snapshot():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    with pytest.raises(AnthropicAccountUsageError) as unauthorized:
        _read(_RecordingRaw(error=_status_error(401)))
    assert unauthorized.value.code == "provider_auth_rejected"
    with pytest.raises(AnthropicAccountUsageError) as forbidden:
        _read(_RecordingRaw(error=_status_error(403)))
    assert forbidden.value.code == "provider_access_rejected"


def test_missing_token_is_typed_without_provider_contact():
    from src.auth_drivers.anthropic_account_usage import (
        AnthropicAccountUsageAdapter,
        AnthropicAccountUsageError,
    )

    factory_calls: list[str] = []

    def factory(token: str):
        factory_calls.append(token)
        return _client(_RecordingRaw())

    with pytest.raises(AnthropicAccountUsageError) as caught:
        AnthropicAccountUsageAdapter(client_factory=factory).read_account_usage(
            credential_id="local:9",
            record=_probe_record(access_token=None),
            observed_at=_OBSERVED_AT,
        )
    assert caught.value.code == "missing_token"
    assert factory_calls == []


def test_malformed_utilization_reset_and_overage_fields_are_nulled_never_zeroed():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    aux_malformed = _unified_headers(
        **{
            "anthropic__ratelimit__unified__overage__disabled__reason": "ORG!!!",
            "anthropic__ratelimit__unified__representative__claim": "NOT VALID!",
            "anthropic__ratelimit__unified__overage__status": "sideways",
        }
    )
    observation = _read(_RecordingRaw(headers=aux_malformed))
    limits = observation.payload.rate_limits
    assert limits.overage_disabled_reason is None
    assert limits.limit_id is None
    assert limits.overage_status is None
    assert limits.primary.used_percent == 5.0

    window_malformed = _read(
        _RecordingRaw(
            headers=_unified_headers(
                **{
                    "anthropic__ratelimit__unified__5h__utilization": "1.7",
                    "anthropic__ratelimit__unified__5h__reset": "soon",
                    "anthropic__ratelimit__unified__7d__utilization": "abc",
                }
            )
        )
    )
    window_limits = window_malformed.payload.rate_limits
    assert window_limits.primary.used_percent is None
    assert window_limits.primary.resets_at is None
    assert window_limits.secondary.used_percent is None
    assert window_limits.secondary.resets_at == 1786687200
    assert window_limits.primary.used_percent != 0
    assert window_limits.secondary.used_percent != 0

    with pytest.raises(AnthropicAccountUsageError) as caught:
        _read(
            _RecordingRaw(
                headers=_unified_headers(
                    **{"anthropic__ratelimit__unified__status": "sideways"}
                )
            )
        )
    assert caught.value.code == "quota_headers_unavailable"


def test_snapshot_source_is_anthropic_oauth_probe_with_passive_fingerprint_shape():
    observation = _read(_RecordingRaw(), credential_id="local:9")
    assert observation.source == "anthropic_oauth_probe"
    expected = hashlib.sha256(
        "anthropic\0claude_code_oauth\0local:9".encode("utf-8")
    ).hexdigest()
    assert observation.account_fingerprint == expected


def test_no_token_body_or_raw_header_reaches_snapshot_or_error_detail():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    observation = _read(_RecordingRaw())
    serialized = json.dumps(observation.model_dump())
    assert _TOKEN not in serialized
    assert "Reply with exactly" not in serialized
    assert "fallback-percentage" not in serialized

    with pytest.raises(AnthropicAccountUsageError) as caught:
        _read(_RecordingRaw(error=_status_error(401, {"x-secret-echo": _TOKEN})))
    detail = f"{caught.value!r} {caught.value} {caught.value.code}"
    assert _TOKEN not in detail


def test_timeout_and_transport_errors_are_typed_and_preserve_last_snapshot():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    with pytest.raises(AnthropicAccountUsageError) as timed_out:
        _read(_RecordingRaw(error=anthropic.APITimeoutError(request=request)))
    assert timed_out.value.code == "timeout"
    with pytest.raises(AnthropicAccountUsageError) as transport:
        _read(
            _RecordingRaw(
                error=anthropic.APIConnectionError(message="boom", request=request)
            )
        )
    assert transport.value.code == "transport_error"


def test_sdk_unable_to_express_pinned_call_shape_is_sdk_incompatible():
    from src.auth_drivers.anthropic_account_usage import (
        AnthropicAccountUsageAdapter,
        AnthropicAccountUsageError,
    )

    class _BareClient:
        def __init__(self):
            self.messages = SimpleNamespace()
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    bare_client = _BareClient()
    with pytest.raises(AnthropicAccountUsageError) as caught:
        AnthropicAccountUsageAdapter(
            client_factory=lambda token: bare_client
        ).read_account_usage(
            credential_id="local:9", record=_probe_record(), observed_at=_OBSERVED_AT
        )
    assert caught.value.code == "sdk_incompatible"
    assert bare_client.close_calls == 1


def test_other_provider_4xx_is_provider_request_rejected_and_preserves_last_snapshot():
    from src.auth_drivers.anthropic_account_usage import AnthropicAccountUsageError

    with pytest.raises(AnthropicAccountUsageError) as caught:
        _read(_RecordingRaw(error=_status_error(400)))
    assert caught.value.code == "provider_request_rejected"
