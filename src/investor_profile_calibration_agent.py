"""Calibration assistant prompt, parser, and responder seam (Track A.5).

This module has no DAL/tool imports by design. It only turns calibration dialogue
into assistant text plus an optional structured profile proposal.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Protocol

from src.investor_profile_calibration import normalize_proposal_payload

CALIBRATION_SYSTEM_PROMPT = """You are ArkScope's Investor Profile calibration assistant.

Purpose:
- Ask targeted questions to understand investment style, risk appetite, real risk capacity,
  drawdown behavior, concentration limits, holding horizon, behavioral patterns, and desired
  assistant behavior.
- Produce a profile proposal only when enough information exists.

Hard boundaries:
- Do not give investment advice.
- Do not recommend securities.
- No market data, news lookup, web browsing, code execution, database write, or tool use.
- Raw calibration dialogue is not research evidence.
- The only durable output is a user-reviewed profile proposal.

Return JSON only:
{
  "assistant_message": "short user-facing reply or follow-up question",
  "proposal": null | {
    "profile_patch": {
      "enabled": true,
      "primary_preset": "growth",
      "risk_appetite": 8,
      "risk_capacity": 4,
      "holding_horizon": "months",
      "drawdown_tolerance_pct": 20,
      "concentration_limit_pct": 15,
      "preferred_edge": ["growth", "catalyst"],
      "avoidances": ["leverage"],
      "behavioral_flags": ["FOMO"],
      "freeform_notes": "concise user-confirmed working model",
      "default_stance": "complementary"
    },
    "rationales": {
      "risk_capacity": "User said a 10% drawdown would likely trigger selling."
    }
  }
}

Allowed field values (use EXACTLY these tokens; anything else is rejected):
- primary_preset: growth | value | momentum | income | event_driven | balanced | custom
- holding_horizon: intraday | days_weeks | months | multi_year | mixed
- default_stance: off | neutral | aligned | complementary | strict_risk_control | valuation_rationalist | growth_opportunity
- risk_appetite / risk_capacity: integers 1-10
- drawdown_tolerance_pct / concentration_limit_pct: numbers, or null when unknown

Never output risk_mismatch; the server derives it.
"""


@dataclass(frozen=True)
class CalibrationAgentResult:
    assistant_message: str
    profile_patch: Optional[dict]
    rationales: dict


class CalibrationResponder(Protocol):
    async def __call__(
        self, *, messages: list[dict], provider: str | None, model: str | None
    ) -> CalibrationAgentResult: ...


def parse_calibration_model_json(raw: str) -> CalibrationAgentResult:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("calibration model output must be a JSON object")
    msg = str(data.get("assistant_message") or "").strip()
    if not msg:
        raise ValueError("assistant_message is required")
    proposal = data.get("proposal")
    if proposal is None:
        return CalibrationAgentResult(msg, None, {})
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be null or an object")
    patch = proposal.get("profile_patch") or {}
    rationales = proposal.get("rationales") or {}
    if not isinstance(patch, dict) or not isinstance(rationales, dict):
        raise ValueError("proposal.profile_patch and proposal.rationales must be objects")
    # Models sometimes emit risk_mismatch despite the prompt ban (live 2026-07-10).
    # Strip it before validation: the server re-derives it on save, so dropping the
    # model's value keeps the server-derived contract; direct API callers still get
    # the hard reject in normalize_proposal_payload.
    patch.pop("risk_mismatch", None)
    normalized, _raw, rats = normalize_proposal_payload(patch, rationales)
    # normalize_* returns the full merged profile INCLUDING the derived risk_mismatch;
    # create_proposal re-validates with the same rejection, so the derived key must
    # not travel in the patch either (live 2026-07-10: no model could ever produce
    # an acceptable proposal before this pop).
    normalized.pop("risk_mismatch", None)
    return CalibrationAgentResult(msg, normalized, rats)


async def unavailable_responder(
    *, messages: list[dict], provider: str | None, model: str | None
) -> CalibrationAgentResult:
    del messages, provider, model
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
    """Provider call seam. No registry, no DAL, no tools."""
    from src.auth_drivers.live_resolver import resolve_live_auth

    if provider == "openai":
        auth = resolve_live_auth("openai")
        if auth.source == "oauth_driver_unwired":
            from src.auth_drivers.factory import build_driver
            from src.auth_drivers.protocol import LLMRequest
            from src.auth_drivers.token_store import get_token_store
            from src.model_credentials import CredentialStore

            cred = CredentialStore().get(auth.credential_id)
            driver = build_driver(
                provider="openai",
                auth_mode="chatgpt_oauth",
                credential=cred,
                token_store=get_token_store(),
                registry=None,
                dal=None,
            )
            resp = await driver.call_llm(
                LLMRequest(model=model, instructions=instructions, input_messages=input_messages)
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
    *, messages: list[dict], provider: str | None, model: str | None
) -> CalibrationAgentResult:
    chosen_provider = (provider or "openai").lower().strip()
    if chosen_provider not in ("openai", "anthropic"):
        raise ValueError(f"unsupported calibration provider: {chosen_provider}")
    chosen_model = _default_model(chosen_provider, model)
    raw = await _call_calibration_llm(
        provider=chosen_provider,
        model=chosen_model,
        instructions=CALIBRATION_SYSTEM_PROMPT,
        input_messages=messages,
    )
    return parse_calibration_model_json(raw)
