"""Structured, no-tool calibration responder boundary."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Protocol

from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.investor_profile_calibration_policy import CALIBRATION_TOPICS

_TOPIC_CATALOG = "\n".join(
    f"{index}. {topic.id}: {', '.join(topic.fields)}"
    for index, topic in enumerate(CALIBRATION_TOPICS, start=1)
)
_RESULT_KEYS = frozenset(
    {
        "assistant_message",
        "addressed_topic_id",
        "topic_covered",
        "next_topic_id",
        "profile_patch",
        "rationales",
    }
)

CALIBRATION_SYSTEM_PROMPT = (
    """You are ArkScope's Investor Profile calibration assistant.

Purpose:
- Ask one targeted question at a time about the server-selected topic.
- Mirror the language of the latest user answer in user-facing text and rationale.
- Produce only a partial profile proposal supported by covered topics.

Hard boundaries:
- Do not give investment advice.
- Do not recommend securities.
- No market data, news lookup, web browsing, code execution, database write, or tool use.
- No tool may be called or requested.
- Raw calibration dialogue is not research evidence.
- The only durable output is a user-reviewed profile proposal.
- Never mention backend topic IDs, profile field names, JSON keys, or schema names in
  assistant_message or other user-facing prose.

Closed topic catalog (exact order and fields):
"""
    + _TOPIC_CATALOG
    + """

Return JSON only:
{
  "assistant_message": "short user-facing reply or one follow-up question",
  "addressed_topic_id": "the server-selected current topic ID",
  "topic_covered": true,
  "next_topic_id": "one uncovered catalog topic ID, or null",
  "profile_patch": null,
  "rationales": {}
}

Output rules:
- addressed_topic_id must equal current_topic_id from server-owned runtime state.
- topic_covered is a JSON boolean.
- next_topic_id is a catalog ID that remains uncovered, or null when no next question is needed.
- profile_patch is null or a partial object. Never expand it with defaults.
- rationales is an object whose keys and values are strings.
- When request_proposal is false, propose only when answers support a useful partial patch.
- When request_proposal is true, propose every supported field from covered topics and no others.
- Never output enabled, freeform_notes, skill_mode, or risk_mismatch in profile_patch.

Allowed field values (use exactly these tokens; anything else is rejected):
- primary_preset: growth | value | momentum | income | event_driven | balanced | custom
- holding_horizon: intraday | days_weeks | months | multi_year | mixed
- default_stance: off | neutral | aligned | complementary | strict_risk_control | valuation_rationalist | growth_opportunity
- risk_appetite / risk_capacity: integers 1-10
- drawdown_tolerance_pct / concentration_limit_pct: numbers, or null when unknown
"""
)


@dataclass(frozen=True)
class CalibrationAgentResult:
    assistant_message: str
    addressed_topic_id: str
    topic_covered: bool
    next_topic_id: str | None
    profile_patch: dict | None
    rationales: dict[str, str]


class CalibrationResultParseError(ValueError):
    """Structured calibration output failed the owned JSON contract."""


class CalibrationResponder(Protocol):
    async def __call__(
        self,
        *,
        messages: list[dict],
        current_topic_id: str,
        covered_topics: tuple[str, ...],
        request_proposal: bool,
        provider: str | None,
        model: str | None,
    ) -> CalibrationAgentResult: ...


def build_calibration_system_prompt(
    *,
    current_topic_id: str,
    covered_topics: tuple[str, ...],
    request_proposal: bool,
) -> str:
    """Bind persisted server state to the closed structured-output contract."""
    return (
        f"{CALIBRATION_SYSTEM_PROMPT}\n"
        "Server-owned runtime state:\n"
        f"current_topic_id: {json.dumps(current_topic_id)}\n"
        "covered_topic_ids: "
        f"{json.dumps(list(covered_topics), separators=(',', ':'))}\n"
        f"request_proposal: {'true' if request_proposal else 'false'}\n"
    )


def parse_calibration_model_json(raw: str) -> CalibrationAgentResult:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        raise CalibrationResultParseError(
            "calibration model output is not valid JSON"
        ) from None
    if not isinstance(data, dict):
        raise CalibrationResultParseError(
            "calibration model output must be a JSON object"
        )
    if set(data) != _RESULT_KEYS:
        raise CalibrationResultParseError(
            "calibration model output must contain exactly six result fields"
        )

    assistant_message = data.get("assistant_message")
    addressed_topic_id = data.get("addressed_topic_id")
    topic_covered = data.get("topic_covered")
    next_topic_id = data.get("next_topic_id")
    profile_patch = data.get("profile_patch")
    rationales = data.get("rationales")

    if not isinstance(assistant_message, str) or not assistant_message.strip():
        raise CalibrationResultParseError("assistant_message is required")
    if not isinstance(addressed_topic_id, str):
        raise CalibrationResultParseError("addressed_topic_id must be a string")
    if type(topic_covered) is not bool:
        raise CalibrationResultParseError("topic_covered must be a boolean")
    if next_topic_id is not None and not isinstance(next_topic_id, str):
        raise CalibrationResultParseError("next_topic_id must be a string or null")
    if profile_patch is not None and not isinstance(profile_patch, dict):
        raise CalibrationResultParseError("profile_patch must be an object or null")
    if not isinstance(rationales, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in rationales.items()
    ):
        raise CalibrationResultParseError("rationales must be an object of strings")

    return CalibrationAgentResult(
        assistant_message=assistant_message,
        addressed_topic_id=addressed_topic_id,
        topic_covered=topic_covered,
        next_topic_id=next_topic_id,
        profile_patch=profile_patch,
        rationales=rationales,
    )


async def unavailable_responder(
    *,
    messages: list[dict],
    current_topic_id: str,
    covered_topics: tuple[str, ...],
    request_proposal: bool,
    provider: str | None,
    model: str | None,
) -> CalibrationAgentResult:
    del messages, current_topic_id, covered_topics, request_proposal, provider, model
    raise RuntimeError("calibration live responder is not wired yet")


def _default_model(provider: str, model: str | None) -> str:
    if model:
        return model
    return "gpt-5.4-mini" if provider == "openai" else "claude-sonnet-4-6"


def _message_text_openai(resp) -> str:
    choice = (getattr(resp, "choices", None) or [None])[0]
    msg = getattr(choice, "message", None)
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    return "" if content is None else str(content)


def _message_text_anthropic(resp) -> str:
    parts: list[str] = []
    for block in getattr(resp, "content", None) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


async def _call_calibration_llm(
    *, provider: str, model: str, instructions: str, input_messages: list[dict]
) -> str:
    """Provider call seam with no registry, DAL, or tools."""
    from src.auth_drivers.live_resolver import resolve_live_auth

    if provider == "openai":
        auth = resolve_live_auth("openai")
        if auth.source == "env_fallback" and not os.environ.get(
            "OPENAI_API_KEY", ""
        ).strip():
            raise MissingCredentialError("OpenAI API key is not configured")
        if auth.source == "oauth_driver_unwired":
            from src.auth_drivers.factory import build_driver
            from src.auth_drivers.protocol import LLMRequest
            from src.auth_drivers.token_store import get_token_store
            from src.model_credentials import CredentialStore

            token_store = get_token_store()
            token_record = token_store.load(
                provider="openai",
                auth_mode="chatgpt_oauth",
                credential_id=auth.credential_id,
            )
            access_token = getattr(token_record, "access_token", None)
            if not isinstance(access_token, str) or not access_token.strip():
                raise MissingCredentialError(
                    "ChatGPT OAuth access token is not configured"
                )
            cred = CredentialStore().get(auth.credential_id)
            driver = build_driver(
                provider="openai",
                auth_mode="chatgpt_oauth",
                credential=cred,
                token_store=token_store,
                registry=None,
                dal=None,
            )
            resp = await driver.call_llm(
                LLMRequest(
                    model=model,
                    instructions=instructions,
                    input_messages=input_messages,
                )
            )
            return resp.text

        from src.auth_drivers.live_resolver import live_openai_client

        def _call() -> str:
            client = live_openai_client()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": instructions},
                    *input_messages,
                ],
                response_format={"type": "json_object"},
            )
            return _message_text_openai(resp)

        return await asyncio.to_thread(_call)

    if provider == "anthropic":
        auth = resolve_live_auth("anthropic")
        if auth.source == "oauth_driver_unwired":
            raise RuntimeError("claude_code_oauth calibration no-tool path is not wired")
        if auth.source == "env_fallback" and not os.environ.get(
            "ANTHROPIC_API_KEY", ""
        ).strip():
            raise MissingCredentialError("Anthropic API key is not configured")

        from src.auth_drivers.live_resolver import live_anthropic_client

        def _call() -> str:
            client = live_anthropic_client()
            resp = client.messages.create(
                model=model,
                max_tokens=1200,
                system=instructions,
                messages=input_messages,
            )
            return _message_text_anthropic(resp)

        return await asyncio.to_thread(_call)

    raise ValueError(f"unsupported calibration provider: {provider}")


async def live_calibration_responder(
    *,
    messages: list[dict],
    current_topic_id: str,
    covered_topics: tuple[str, ...],
    request_proposal: bool,
    provider: str | None,
    model: str | None,
) -> CalibrationAgentResult:
    chosen_provider = (provider or "openai").lower().strip()
    if chosen_provider not in ("openai", "anthropic"):
        raise ValueError(f"unsupported calibration provider: {chosen_provider}")
    chosen_model = _default_model(chosen_provider, model)
    raw = await _call_calibration_llm(
        provider=chosen_provider,
        model=chosen_model,
        instructions=build_calibration_system_prompt(
            current_topic_id=current_topic_id,
            covered_topics=covered_topics,
            request_proposal=request_proposal,
        ),
        input_messages=messages,
    )
    return parse_calibration_model_json(raw)
