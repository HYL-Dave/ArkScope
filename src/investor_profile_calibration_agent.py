"""Calibration assistant prompt, parser, and responder seam (Track A.5).

This module has no DAL/tool imports by design. It only turns calibration dialogue
into assistant text plus an optional structured profile proposal.
"""

from __future__ import annotations

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
    normalized, _raw, rats = normalize_proposal_payload(patch, rationales)
    return CalibrationAgentResult(msg, normalized, rats)


async def unavailable_responder(
    *, messages: list[dict], provider: str | None, model: str | None
) -> CalibrationAgentResult:
    del messages, provider, model
    raise RuntimeError("calibration live responder is not wired yet")
