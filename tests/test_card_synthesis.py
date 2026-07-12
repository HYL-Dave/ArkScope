"""Tests for card synthesis: packet → validated ResultCard merge + rendering.

The live provider call is mocked — these lock the merge contract (metadata
stamped from the packet, per-claim citations carried into traceability,
single-model flag) and the markdown promotion path.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from src.card_synthesis import (
    CardSynthesis,
    _SynthClaim,
    render_card_markdown,
    synthesize_card,
)
from src.evidence_packet import EvidenceItem, EvidencePacket
from src.result_card import ResultCard, Traceability


def _packet() -> EvidencePacket:
    return EvidencePacket(
        ticker="AAPL",
        generated_at="2026-06-05T00:00:00Z",
        question="thesis into the print?",
        items=[
            EvidenceItem(evidence_id="E1", source="price_summary", source_type="observed_market",
                         as_of="2026-06-04", data={"latest_close": 124.0}),
            EvidenceItem(evidence_id="E2", source="technical_metrics", source_type="deterministic_metric",
                         data={"return_20d_pct": 19.2}),
            EvidenceItem(evidence_id="E3", source="news_rows", source_type="observed_news",
                         data={"count": 2}),
            EvidenceItem(evidence_id="C", source="coverage", source_type="coverage",
                         data={"present": ["price", "technicals", "news"], "missing": ["iv", "fundamentals"]}),
        ],
    )


def _synth() -> CardSynthesis:
    return CardSynthesis(
        conclusion="Constructive but data is thin.",
        primary_reasons=["20d momentum positive"],
        counter_thesis=["No fundamentals in packet — low conviction"],
        risks=["IV unavailable"],
        confidence_level="low",
        confidence_rationale="fundamentals + iv missing",
        claims=[
            _SynthClaim(claim="20d momentum positive", evidence_ids=["E2"]),
            _SynthClaim(claim="thin data", evidence_ids=["C"]),
        ],
    )


def test_synthesize_merges_metadata_and_citations(monkeypatch):
    monkeypatch.setattr(
        "src.card_synthesis._synthesize_anthropic",
        lambda packet, model, effort="default", model_timeout_s=None: (
            _synth(), {"effort": effort}
        ),
    )
    card, meta = synthesize_card(
        _packet(), now_iso="2026-06-05T00:00:00Z", provider="anthropic",
        question="thesis into the print?", horizon="swing", model_timeout_s=900,
    )
    assert isinstance(card, ResultCard)
    assert card.ticker == "AAPL"
    assert card.horizon == "swing"
    assert card.analysis_time == "2026-06-05T00:00:00Z"
    assert card.card_type == "analysis"
    assert card.confidence_level == "low"
    # traceability: one DataSourceRef per non-coverage evidence item
    assert len(card.traceability.data_sources) == 3
    assert {d.name for d in card.traceability.data_sources} == {
        "price_summary", "technical_metrics", "news_rows"
    }
    assert card.traceability.is_single_model_inference is True
    # per-claim citations carried through
    assert len(card.traceability.claims) == 2
    assert card.traceability.claims[0].evidence_ids == ["E2"]
    # completeness derived from source types present
    assert card.traceability.completeness.news is True
    assert card.traceability.completeness.technicals is True
    assert card.traceability.completeness.fundamentals is False
    assert "iv" in (card.traceability.completeness.note or "")
    assert meta == {"provider": "anthropic", "model": meta["model"], "effort": "default"}


def test_synthesize_rejects_unknown_provider():
    with pytest.raises(ValueError):
        synthesize_card(
            _packet(), now_iso="t", provider="grok", model_timeout_s=900
        )  # type: ignore[arg-type]


def test_translation_validation_rejects_list_count_change():
    from src.card_synthesis import _validate_translation

    card = ResultCard(
        ticker="AAPL", analysis_time="t", conclusion="c",
        primary_reasons=["a", "b"], counter_thesis=["x"],
        confidence_level="low", traceability=Traceability(),
    ).model_dump()
    # same structure → ok
    _validate_translation(card, {**card, "conclusion": "結論", "primary_reasons": ["甲", "乙"]})
    # dropped a list item → reject (would silently lose a reason)
    with pytest.raises(ValueError):
        _validate_translation(card, {**card, "primary_reasons": ["只剩一條"]})


def test_task_model_routing(tmp_path, monkeypatch):
    from src.agents import config as cfg_mod
    from src.agents.config import get_agent_config, task_model, task_route

    monkeypatch.setattr(cfg_mod, "_MAIN_CONFIG_PATH", tmp_path / "missing.yaml")
    monkeypatch.setattr(cfg_mod, "_LOCAL_CONFIG_PATH", tmp_path / "user_profile.local.yaml")
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_PROVIDER", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_TRANSLATION_MODEL", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_PROVIDER", raising=False)
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", raising=False)
    get_agent_config.cache_clear()
    # translation defaults to the fast model (not the Opus synthesis model)
    assert task_model("card_translation") == "claude-sonnet-4-6"
    # env override wins for either task
    monkeypatch.setenv("ARKSCOPE_CARD_TRANSLATION_MODEL", "claude-haiku-4-5")
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", "test-model-x")
    assert task_model("card_translation") == "claude-haiku-4-5"
    assert task_model("card_synthesis") == "test-model-x"
    # provider can be set independently; model-only OpenAI ids infer provider.
    monkeypatch.delenv("ARKSCOPE_CARD_SYNTHESIS_MODEL")
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_MODEL", "gpt-5.4-mini")
    assert task_route("card_synthesis").provider == "openai"
    monkeypatch.setenv("ARKSCOPE_CARD_SYNTHESIS_PROVIDER", "anthropic")
    assert task_route("card_synthesis").provider == "anthropic"


def test_render_card_markdown_has_core_sections(monkeypatch):
    monkeypatch.setattr(
        "src.card_synthesis._synthesize_anthropic",
        lambda packet, model, effort="default", model_timeout_s=None: (
            _synth(), {"effort": effort}
        ),
    )
    card, _ = synthesize_card(
        _packet(),
        now_iso="2026-06-05T00:00:00Z",
        provider="anthropic",
        model_timeout_s=900,
    )
    md = render_card_markdown(card)
    assert "## Conclusion" in md
    assert "Counter-thesis" in md
    assert "## Confidence" in md
    assert "LOW" in md
    assert "## Data sources" in md


# ── P2.7 Task 5B: structured refusal handling (card seams) ────────


def _refusal_response():
    response = MagicMock()
    response.stop_reason = "refusal"
    response.content = []
    response.stop_details = {"category": "safety"}
    return response


def test_card_synthesis_raises_structured_refusal(monkeypatch):
    from src import card_synthesis as cs
    from src.anthropic_refusal import AnthropicRefusalError

    client = MagicMock()
    client.with_options.return_value = client
    client.messages.create.return_value = _refusal_response()
    # Function-local import → patch the SOURCE module.
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda **kw: client,
    )
    with pytest.raises(AnthropicRefusalError):
        cs._synthesize_anthropic(
            _packet(), "claude-fable-5", model_timeout_s=900
        )


def test_card_translation_raises_structured_refusal(monkeypatch):
    # _translate_anthropic shares the refusal error (same forced-tool pattern).
    from src import card_synthesis as cs
    from src.anthropic_refusal import AnthropicRefusalError

    client = MagicMock()
    client.with_options.return_value = client
    client.messages.create.return_value = _refusal_response()
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda **kw: client,
    )
    with pytest.raises(AnthropicRefusalError):
        cs._translate_anthropic(
            "claude-fable-5",
            "sys",
            "user",
            {},
            "zh-TW",
            model_timeout_s=900,
        )


def test_refusal_never_triggers_effort_fallback(monkeypatch):
    # Review MF6: AnthropicRefusalError's text/category can contain "effort",
    # which the effort-fallback heuristic matches — a refusal must NEVER retry
    # (zero-fallback contract); pin exactly one provider call.
    from src import card_synthesis as cs
    from src.anthropic_refusal import AnthropicRefusalError

    client = MagicMock()
    client.with_options.return_value = client
    refusal = _refusal_response()
    refusal.stop_details = {"category": "effort_extraction"}
    client.messages.create.return_value = refusal
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda **kw: client,
    )
    with pytest.raises(AnthropicRefusalError):
        cs._synthesize_anthropic(
            _packet(), "claude-fable-5", effort="xhigh", model_timeout_s=900
        )
    assert client.messages.create.call_count == 1

    client.messages.create.reset_mock()
    with pytest.raises(AnthropicRefusalError):
        cs._translate_anthropic(
            "claude-fable-5",
            "sys",
            "user",
            {},
            "zh-TW",
            effort="xhigh",
            model_timeout_s=900,
        )
    assert client.messages.create.call_count == 1


# ── 2026-07-12: subscription-backed card tasks ────────────────────────────


def _oauth_resolution(provider: str, credential_id: str):
    from src.auth_drivers.live_resolver import LiveAuthResolution

    return LiveAuthResolution(
        provider=provider,
        source="oauth_driver_unwired",
        credential_id=credential_id,
    )


def test_openai_synthesis_uses_chatgpt_subscription_when_oauth_is_active(monkeypatch):
    from src import card_synthesis as cs

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: _oauth_resolution(provider, "local:7"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_openai_client",
        lambda: (_ for _ in ()).throw(AssertionError("API-key client must not be built")),
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: calls.append(kwargs) or _synth().model_dump(),
    )

    result, meta = cs._synthesize_openai(
        _packet(), "gpt-5.4-mini", effort="high", model_timeout_s=321
    )

    assert result == _synth()
    assert meta == {"effort": "high"}
    assert calls[0]["provider"] == "openai"
    assert calls[0]["auth_mode"] == "chatgpt_oauth"
    assert calls[0]["credential_id"] == "local:7"
    assert calls[0]["model"] == "gpt-5.4-mini"
    assert calls[0]["output_name"] == "emit_result_card"
    assert calls[0]["effort"] == "high"
    assert calls[0]["timeout_s"] == 321.0


def test_openai_translation_uses_chatgpt_subscription_when_oauth_is_active(monkeypatch):
    from src import card_synthesis as cs

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: _oauth_resolution(provider, "local:7"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_openai_client",
        lambda: (_ for _ in ()).throw(AssertionError("API-key client must not be built")),
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: calls.append(kwargs) or {"conclusion": "結論"},
    )

    result = cs._translate_openai(
        "gpt-5.4-mini",
        "system",
        '{"conclusion":"view"}',
        {"type": "object"},
        "Traditional Chinese",
        effort="medium",
        model_timeout_s=322,
    )

    assert result == {"conclusion": "結論"}
    assert calls[0]["auth_mode"] == "chatgpt_oauth"
    assert calls[0]["output_name"] == "emit_translation"
    assert calls[0]["effort"] == "medium"
    assert calls[0]["timeout_s"] == 322.0


def test_anthropic_synthesis_uses_claude_subscription_when_oauth_is_active(monkeypatch):
    from src import card_synthesis as cs

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: _oauth_resolution(provider, "local:2"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: (_ for _ in ()).throw(AssertionError("API-key client must not be built")),
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: calls.append(kwargs) or _synth().model_dump(),
    )

    result, meta = cs._synthesize_anthropic(
        _packet(), "claude-sonnet-5", effort="low", model_timeout_s=323
    )

    assert result == _synth()
    assert meta == {"effort": "low"}
    assert calls[0]["provider"] == "anthropic"
    assert calls[0]["auth_mode"] == "claude_code_oauth"
    assert calls[0]["credential_id"] == "local:2"
    assert calls[0]["output_name"] == "emit_result_card"
    assert "emit_result_card tool" not in calls[0]["system"]
    assert "JSON" in calls[0]["system"]
    assert calls[0]["timeout_s"] == 323.0


def test_anthropic_translation_uses_claude_subscription_when_oauth_is_active(monkeypatch):
    from src import card_synthesis as cs

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: _oauth_resolution(provider, "local:2"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: (_ for _ in ()).throw(AssertionError("API-key client must not be built")),
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: calls.append(kwargs) or {"conclusion": "結論"},
    )

    result = cs._translate_anthropic(
        "claude-sonnet-5",
        "Respond ONLY via the emit_translation tool.",
        '{"conclusion":"view"}',
        {"type": "object"},
        "Traditional Chinese",
        effort="medium",
        model_timeout_s=324,
        subscription_system="Return ONLY one JSON object matching the schema.",
    )

    assert result == {"conclusion": "結論"}
    assert calls[0]["auth_mode"] == "claude_code_oauth"
    assert calls[0]["output_name"] == "emit_translation"
    assert "emit_translation tool" not in calls[0]["system"]
    assert "JSON" in calls[0]["system"]
    assert calls[0]["timeout_s"] == 324.0


@pytest.mark.parametrize(
    ("provider", "invoke"),
    [
        (
            "openai",
            lambda cs: cs._synthesize_openai(
                _packet(), "gpt-5.4-mini", effort="high", model_timeout_s=900
            ),
        ),
        (
            "openai",
            lambda cs: cs._translate_openai(
                "gpt-5.4-mini",
                "system",
                '{"conclusion":"view"}',
                {"type": "object"},
                "Traditional Chinese",
                effort="high",
                model_timeout_s=900,
            ),
        ),
        (
            "anthropic",
            lambda cs: cs._synthesize_anthropic(
                _packet(), "claude-sonnet-5", effort="high", model_timeout_s=900
            ),
        ),
        (
            "anthropic",
            lambda cs: cs._translate_anthropic(
                "claude-sonnet-5",
                "system",
                '{"conclusion":"view"}',
                {"type": "object"},
                "Traditional Chinese",
                effort="high",
                model_timeout_s=900,
            ),
        ),
    ],
)
def test_subscription_effort_errors_never_retry_with_default(
    monkeypatch,
    provider,
    invoke,
):
    from src import card_synthesis as cs
    from src.auth_drivers.subscription_structured_output import (
        SubscriptionStructuredOutputError,
    )

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda selected_provider: _oauth_resolution(
            selected_provider,
            "local:7" if selected_provider == "openai" else "local:2",
        ),
    )

    def fail(**kwargs):
        calls.append(kwargs)
        raise SubscriptionStructuredOutputError(
            "provider_call_failed",
            "Provider rejected the selected effort parameter.",
        )

    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        fail,
    )

    with pytest.raises(SubscriptionStructuredOutputError):
        invoke(cs)

    assert [call["provider"] for call in calls] == [provider]
    assert calls[0]["effort"] == "high"


def test_openai_api_key_synthesis_keeps_existing_chat_completions_shape(monkeypatch):
    from types import SimpleNamespace

    from src import card_synthesis as cs
    from src.auth_drivers.live_resolver import LiveAuthResolution

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="emit_result_card",
                                arguments=_synth().model_dump_json(),
                            )
                        )
                    ]
                )
            )
        ]
    )
    client = MagicMock()
    bounded = MagicMock()
    bounded.chat.completions.create.return_value = response
    client.with_options.return_value = bounded
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "db_api_key", "local:3"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_openai_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("API-key route must not call the subscription adapter")
        ),
    )

    result, meta = cs._synthesize_openai(
        _packet(), "gpt-5.4-mini", effort="high", model_timeout_s=456
    )

    assert result == _synth() and meta == {"effort": "high"}
    client.with_options.assert_called_once_with(timeout=456, max_retries=0)
    kwargs = bounded.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["max_completion_tokens"] == 8192
    assert kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "emit_result_card"},
    }


def test_anthropic_api_key_synthesis_keeps_existing_messages_shape(monkeypatch):
    from types import SimpleNamespace

    from src import card_synthesis as cs
    from src.auth_drivers.live_resolver import LiveAuthResolution

    response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(
                type="tool_use",
                name="emit_result_card",
                input=_synth().model_dump(),
            )
        ],
    )
    client = MagicMock()
    bounded = MagicMock()
    bounded.messages.create.return_value = response
    client.with_options.return_value = bounded
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "db_api_key", "local:4"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: client,
    )
    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("API-key route must not call the subscription adapter")
        ),
    )

    result, meta = cs._synthesize_anthropic(
        _packet(), "claude-sonnet-5", effort="high", model_timeout_s=457
    )

    assert result == _synth() and meta == {"effort": "high"}
    client.with_options.assert_called_once_with(timeout=457, max_retries=0)
    kwargs = bounded.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["max_tokens"] == 8192
    assert kwargs["output_config"] == {"effort": "high"}
    assert kwargs["tool_choice"] == {"type": "tool", "name": "emit_result_card"}


def test_openai_api_timeout_uses_one_attempt(monkeypatch):
    import httpx
    from openai import OpenAI

    from src import card_synthesis as cs
    from src.auth_drivers.live_resolver import LiveAuthResolution

    attempts = []

    def timeout(request):
        attempts.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = OpenAI(
        api_key="sk-test",
        base_url="https://openai.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(timeout)),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "env_fallback"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_openai_client", lambda: client
    )

    try:
        with pytest.raises(cs.ModelExecutionTimeout):
            cs._synthesize_openai(
                _packet(), "gpt-5.4-mini", effort="high", model_timeout_s=0.01
            )
    finally:
        client.close()

    assert len(attempts) == 1


def test_anthropic_api_timeout_uses_one_attempt(monkeypatch):
    import httpx
    from anthropic import Anthropic

    from src import card_synthesis as cs
    from src.auth_drivers.live_resolver import LiveAuthResolution

    attempts = []

    def timeout(request):
        attempts.append(request)
        raise httpx.ReadTimeout("timed out", request=request)

    client = Anthropic(
        api_key="test-key",
        base_url="https://anthropic.invalid",
        http_client=httpx.Client(transport=httpx.MockTransport(timeout)),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda provider: LiveAuthResolution(provider, "env_fallback"),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client", lambda: client
    )

    try:
        with pytest.raises(cs.ModelExecutionTimeout):
            cs._synthesize_anthropic(
                _packet(), "claude-sonnet-5", effort="high", model_timeout_s=0.01
            )
    finally:
        client.close()

    assert len(attempts) == 1


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_subscription_sdk_timeout_cause_is_typed(monkeypatch, provider):
    import httpx
    import openai
    import anthropic

    from src import card_synthesis as cs
    from src.auth_drivers.subscription_structured_output import (
        SubscriptionStructuredOutputError,
    )

    credential_id = "local:7" if provider == "openai" else "local:2"
    timeout_type = openai.APITimeoutError if provider == "openai" else anthropic.APITimeoutError
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.resolve_live_auth",
        lambda selected: _oauth_resolution(selected, credential_id),
    )

    def fail(**kwargs):
        try:
            raise timeout_type(request=httpx.Request("POST", "https://provider.invalid"))
        except timeout_type as exc:
            raise SubscriptionStructuredOutputError(
                "provider_call_failed", "provider timed out"
            ) from exc

    monkeypatch.setattr(
        "src.auth_drivers.subscription_structured_output.run_subscription_structured_output",
        fail,
    )

    with pytest.raises(cs.ModelExecutionTimeout) as caught:
        cs._subscription_structured_output_if_active(
            provider=provider,
            model="gpt-5.4-mini" if provider == "openai" else "claude-sonnet-5",
            system="system",
            user="user",
            output_name="emit_result_card",
            output_description="Emit a card",
            schema={"type": "object"},
            effort="high",
            model_timeout_s=123,
        )

    assert caught.value.effective_seconds == 123.0
