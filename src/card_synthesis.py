"""
Card synthesis — EvidencePacket → validated ResultCard (ProductSpec §2.4 step 2).

A SINGLE forced-structured LLM call turns the objective evidence packet into the
fixed §2 schema. The model *integrates and cites* evidence; it does not re-score
it. The structured-output boundary is enforced at the tool-call layer (the model
must emit via the ``emit_result_card`` tool), then validated with Pydantic, so a
malformed card never reaches storage or the UI.

Provider-agnostic: Anthropic (default, Opus-class) and OpenAI are parallel paths
behind one ``synthesize_card`` entry point. Identity/metadata (ticker, time) and
the traceability source list are stamped by the generator from the packet — the
model only fills the judgment fields + per-claim citations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from src.agents.config import get_agent_config, task_route
from src.env_keys import ensure_env_loaded
from src.evidence_packet import EvidencePacket
from src.model_credentials import looks_like_effort_error
from src.result_card import (
    ClaimCitation,
    Completeness,
    DataSourceRef,
    ResultCard,
    Traceability,
)

logger = logging.getLogger(__name__)

Provider = Literal["anthropic", "openai"]
_TOOL_NAME = "emit_result_card"
_MAX_TOKENS = 8192  # card JSON is small; well under the 21333 streaming threshold


class _SynthClaim(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)


class CardSynthesis(BaseModel):
    """The judgment fields the model fills (merged with packet metadata after)."""

    conclusion: str
    primary_reasons: list[str] = Field(default_factory=list)
    counter_thesis: list[str] = Field(default_factory=list)
    key_assumptions: list[str] = Field(default_factory=list)
    trigger_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    watch_list: list[str] = Field(default_factory=list)
    market_narrative: Optional[str] = None
    divergence: Optional[str] = None
    confidence_level: Literal["high", "medium", "low"]
    confidence_rationale: Optional[str] = None
    claims: list[_SynthClaim] = Field(default_factory=list)


# Hand-written JSON Schema for the forced tool — flat (no $ref/$defs) so it is
# accepted verbatim by both Anthropic input_schema and OpenAI function params.
_CARD_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "conclusion": {"type": "string", "description": "The bottom-line view in 1-3 sentences."},
        "primary_reasons": {"type": "array", "items": {"type": "string"}},
        "counter_thesis": {
            "type": "array",
            "items": {"type": "string"},
            "description": "反方理由 — the strongest good-faith opposing view. REQUIRED.",
        },
        "key_assumptions": {"type": "array", "items": {"type": "string"}},
        "trigger_conditions": {"type": "array", "items": {"type": "string"}},
        "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "watch_list": {"type": "array", "items": {"type": "string"}},
        "market_narrative": {"type": "string", "description": "Main narrative / consensus."},
        "divergence": {"type": "string", "description": "Where this view differs from consensus."},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence_rationale": {"type": "string"},
        "claims": {
            "type": "array",
            "description": "Per-claim citations. Each material claim → the evidence_id(s) supporting it.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["claim", "evidence_ids"],
            },
        },
    },
    "required": ["conclusion", "counter_thesis", "confidence_level", "claims"],
}

_SYSTEM_PROMPT = """You are the synthesis layer for ArkScope's structured research card (ProductSpec §2).

You are given an EvidencePacket: a set of OBJECTIVE evidence items, each with an `evidence_id`. The packet INTENTIONALLY excludes ArkScope-generated LLM sentiment/risk scores — do not reconstruct or assert any such score.

Rules:
1. Use ONLY facts present in the packet. Never invent prices, dates, events, or figures. Cite specific numbers from the packet where they matter.
2. Do NOT re-score sentiment or risk. The packet excludes those by design; respect that.
3. For every material claim (each primary reason, counter-thesis point, key assumption, trigger, invalidation, and risk), add an entry to `claims[]` citing the supporting `evidence_id`(s). If a statement genuinely rests on no packet evidence, give it `evidence_ids: []` and phrase it as an explicit assumption, not a fact.
4. `counter_thesis` is REQUIRED: state the strongest good-faith opposing view.
5. Calibrate `confidence_level` to evidence completeness and consistency. Thin, missing, or conflicting evidence ⇒ "low". Read the packet's `coverage` item to see what was unavailable.
6. Be concrete and decision-useful; avoid hedging filler.
7. Respond ONLY by calling the emit_result_card tool exactly once. Do not write prose outside the tool call."""


def _build_user_message(packet: EvidencePacket) -> str:
    parts: list[str] = []
    if packet.question:
        parts.append(f"Question: {packet.question}")
    if packet.horizon:
        parts.append(f"Horizon: {packet.horizon}")
    parts.append(f"Ticker: {packet.ticker}")
    parts.append("EvidencePacket (objective evidence only — LLM scores excluded):")
    parts.append(json.dumps(packet.model_dump(), default=str, indent=2))
    return "\n".join(parts)


# ── provider calls ──────────────────────────────────────────────────────────


def _synthesize_anthropic(
    packet: EvidencePacket,
    model: str,
    effort: str = "default",
) -> tuple[CardSynthesis, dict[str, Any]]:

    def run_once(selected_effort: str) -> CardSynthesis:
        kwargs: dict[str, Any] = {}
        if selected_effort != "default":
            kwargs["output_config"] = {"effort": selected_effort}
        from src.auth_drivers.live_resolver import live_anthropic_client
        client = live_anthropic_client()
        resp = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(packet)}],
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Emit the structured §2 result card.",
                    "input_schema": _CARD_TOOL_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            **kwargs,
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
                return CardSynthesis(**block.input)
        raise RuntimeError("Anthropic synthesis did not return the emit_result_card tool call")

    try:
        return run_once(effort), {"effort": effort}
    except Exception as exc:
        if effort != "default" and looks_like_effort_error(exc):
            synth = run_once("default")
            return synth, {
                "effort": effort,
                "fallback_effort": "default",
                "warning": (
                    f"Provider rejected effort '{effort}', so synthesis fell back "
                    "to provider default."
                ),
            }
        raise


def _synthesize_openai(
    packet: EvidencePacket,
    model: str,
    effort: str = "default",
) -> tuple[CardSynthesis, dict[str, Any]]:

    def run_once(selected_effort: str) -> CardSynthesis:
        kwargs: dict[str, Any] = {}
        if selected_effort != "default":
            kwargs["reasoning_effort"] = selected_effort
        from src.auth_drivers.live_resolver import live_openai_client
        client = live_openai_client()
        resp = client.chat.completions.create(
            model=model,
            max_completion_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(packet)},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": _TOOL_NAME,
                        "description": "Emit the structured §2 result card.",
                        "parameters": _CARD_TOOL_SCHEMA,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            **kwargs,
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            if tc.function.name == _TOOL_NAME:
                return CardSynthesis(**json.loads(tc.function.arguments))
        raise RuntimeError("OpenAI synthesis did not return the emit_result_card tool call")

    try:
        return run_once(effort), {"effort": effort}
    except Exception as exc:
        if effort != "default" and looks_like_effort_error(exc):
            synth = run_once("default")
            return synth, {
                "effort": effort,
                "fallback_effort": "default",
                "warning": (
                    f"Provider rejected effort '{effort}', so synthesis fell back "
                    "to provider default."
                ),
            }
        raise


# ── merge + entry point ──────────────────────────────────────────────────────

_CONFIDENCE_TO_SCORE = {"high": 0.8, "medium": 0.55, "low": 0.3}


def _merge_to_card(
    packet: EvidencePacket,
    synth: CardSynthesis,
    *,
    now_iso: str,
    question: Optional[str],
    horizon: Optional[str],
) -> ResultCard:
    evidence_items = [it for it in packet.items if it.source_type != "coverage"]
    data_sources = [
        DataSourceRef(
            name=it.source,
            as_of=it.as_of,
            is_real_time=it.is_real_time,
            detail=it.note,
        )
        for it in evidence_items
    ]
    sources_present = {it.source_type for it in evidence_items}
    coverage = next((it for it in packet.items if it.source_type == "coverage"), None)
    missing = coverage.data.get("missing", []) if coverage else []
    completeness = Completeness(
        news="observed_news" in sources_present,
        fundamentals="institutional" in sources_present,
        technicals="deterministic_metric" in sources_present,
        note=f"missing: {', '.join(missing)}" if missing else None,
    )
    trace = Traceability(
        data_sources=data_sources,
        is_single_model_inference=True,
        completeness=completeness,
        claims=[ClaimCitation(claim=c.claim, evidence_ids=c.evidence_ids) for c in synth.claims],
    )
    return ResultCard(
        ticker=packet.ticker,
        question=question,
        horizon=horizon,
        card_type="analysis",
        analysis_time=now_iso,
        conclusion=synth.conclusion,
        primary_reasons=synth.primary_reasons,
        counter_thesis=synth.counter_thesis,
        key_assumptions=synth.key_assumptions,
        trigger_conditions=synth.trigger_conditions,
        invalidation_conditions=synth.invalidation_conditions,
        risks=synth.risks,
        watch_list=synth.watch_list,
        market_narrative=synth.market_narrative,
        divergence=synth.divergence,
        confidence_level=synth.confidence_level,
        confidence_rationale=synth.confidence_rationale,
        traceability=trace,
    )


def synthesize_card(
    packet: EvidencePacket,
    *,
    now_iso: str,
    provider: Provider = "anthropic",
    model: Optional[str] = None,
    question: Optional[str] = None,
    horizon: Optional[str] = None,
) -> tuple[ResultCard, dict]:
    """Synthesize a validated ResultCard from an objective EvidencePacket.

    Returns ``(card, meta)`` where ``meta`` carries provider/model for the run
    record. Raises on provider failure or malformed output (validated by Pydantic).
    """
    ensure_env_loaded()
    route = task_route("card_synthesis")
    if provider == "anthropic":
        model = model or (route.model if route.provider == "anthropic" else get_agent_config().anthropic_model_advanced)
        effort = route.effort if route.provider == "anthropic" else "default"
        synth, effort_meta = _synthesize_anthropic(packet, model, effort)
    elif provider == "openai":
        model = model or (route.model if route.provider == "openai" else get_agent_config().openai_model_advanced)
        effort = route.effort if route.provider == "openai" else "default"
        synth, effort_meta = _synthesize_openai(packet, model, effort)
    else:
        raise ValueError(f"unknown provider: {provider}")
    card = _merge_to_card(
        packet, synth, now_iso=now_iso, question=question, horizon=horizon
    )
    return card, {"provider": provider, "model": model, **effort_meta}


def confidence_to_score(level: str) -> float:
    return _CONFIDENCE_TO_SCORE.get(level, 0.5)


# ── markdown rendering (for "Save as report") ─────────────────────────────────


def render_card_markdown(card: ResultCard) -> str:
    """Render a ResultCard to Markdown for durable report storage."""

    def section(title: str, items: list[str]) -> list[str]:
        if not items:
            return []
        return [f"## {title}", "", *[f"- {x}" for x in items], ""]

    lines: list[str] = [f"## Conclusion", "", card.conclusion, ""]
    lines += section("Primary reasons", card.primary_reasons)
    lines += section("Counter-thesis (反方理由)", card.counter_thesis)
    lines += section("Key assumptions", card.key_assumptions)
    lines += section("Trigger conditions", card.trigger_conditions)
    lines += section("Invalidation conditions", card.invalidation_conditions)
    lines += section("Risks", card.risks)
    lines += section("Watch list", card.watch_list)
    if card.market_narrative:
        lines += ["## Market narrative", "", card.market_narrative, ""]
    if card.divergence:
        lines += ["## Divergence from consensus", "", card.divergence, ""]
    lines += [
        "## Confidence",
        "",
        f"**{card.confidence_level.upper()}**"
        + (f" — {card.confidence_rationale}" if card.confidence_rationale else ""),
        "",
    ]
    ds = card.traceability.data_sources
    if ds:
        lines += ["## Data sources", ""]
        for s in ds:
            asof = f" (as of {s.as_of})" if s.as_of else ""
            lines.append(f"- **{s.name}**{asof}")
        lines.append("")
    lines += ["---", f"_Single-model inference · generated {card.analysis_time}_"]
    return "\n".join(lines)


# ── on-demand translation ─────────────────────────────────────────────────────

_LANG_NAMES = {"zh-Hant": "Traditional Chinese (繁體中文)", "zh-Hans": "Simplified Chinese"}
_TRANSLATABLE_FIELDS = (
    "question",
    "conclusion",
    "primary_reasons",
    "counter_thesis",
    "key_assumptions",
    "trigger_conditions",
    "invalidation_conditions",
    "risks",
    "watch_list",
    "market_narrative",
    "divergence",
    "confidence_rationale",
)


def translate_card(
    card: dict,
    *,
    lang: str = "zh-Hant",
    provider: Optional[Provider] = None,
    model: Optional[str] = None,
) -> dict:
    """Translate a card's natural-language fields into ``lang``; return a full card dict.

    Only prose fields are translated; ticker, numbers, %, evidence_ids,
    confidence_level, traceability and metadata are preserved unchanged. A forced
    tool guarantees the structure (and list item counts) survive.
    """
    ensure_env_loaded()
    route = task_route("card_translation")
    provider = provider or route.provider
    model = model or route.model
    target = _LANG_NAMES.get(lang, lang)

    payload = {k: card.get(k) for k in _TRANSLATABLE_FIELDS if card.get(k) not in (None, "", [])}
    if not payload:
        return dict(card)

    props: dict[str, Any] = {}
    for k, v in payload.items():
        props[k] = (
            {"type": "array", "items": {"type": "string"}}
            if isinstance(v, list)
            else {"type": "string"}
        )
    schema = {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}

    system = (
        f"You are a precise financial translator. Translate every value into {target}. "
        "Keep tickers, numbers, %, currency, dates, and evidence ids (E1, E2, …) exactly as-is. "
        "Preserve list structure and item COUNT — translate each item in place, never add, drop, "
        "merge, or reorder items. Respond ONLY via the emit_translation tool."
    )
    user = json.dumps(payload, ensure_ascii=False, indent=2)

    effort = route.effort if provider == route.provider else "default"
    if provider == "anthropic":
        translated = _translate_anthropic(model, system, user, schema, target, effort)
    elif provider == "openai":
        translated = _translate_openai(model, system, user, schema, target, effort)
    else:
        raise ValueError(f"unknown provider: {provider}")

    out = dict(card)
    for k, v in translated.items():
        if k in _TRANSLATABLE_FIELDS:
            out[k] = v
    _validate_translation(card, out)
    return out


def _translate_anthropic(
    model: str,
    system: str,
    user: str,
    schema: dict,
    target: str,
    effort: str = "default",
) -> dict:

    def run_once(selected_effort: str) -> dict:
        kwargs: dict[str, Any] = {}
        if selected_effort != "default":
            kwargs["output_config"] = {"effort": selected_effort}
        from src.auth_drivers.live_resolver import live_anthropic_client
        client = live_anthropic_client()
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[
                {
                    "name": "emit_translation",
                    "description": f"Emit the {target} translation of the given fields.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "emit_translation"},
            **kwargs,
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "emit_translation":
                return block.input
        raise RuntimeError("Anthropic translation did not return emit_translation")

    try:
        return run_once(effort)
    except Exception as exc:
        if effort != "default" and looks_like_effort_error(exc):
            logger.warning(
                "Anthropic translation effort %s was rejected; retrying with provider default",
                effort,
            )
            return run_once("default")
        raise


def _translate_openai(
    model: str,
    system: str,
    user: str,
    schema: dict,
    target: str,
    effort: str = "default",
) -> dict:

    def run_once(selected_effort: str) -> dict:
        kwargs: dict[str, Any] = {}
        if selected_effort != "default":
            kwargs["reasoning_effort"] = selected_effort
        from src.auth_drivers.live_resolver import live_openai_client
        client = live_openai_client()
        resp = client.chat.completions.create(
            model=model,
            max_completion_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "emit_translation",
                        "description": f"Emit the {target} translation of the given fields.",
                        "parameters": schema,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": "emit_translation"}},
            **kwargs,
        )
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []
        for tc in tool_calls:
            if tc.function.name == "emit_translation":
                return json.loads(tc.function.arguments)
        raise RuntimeError("OpenAI translation did not return emit_translation")

    try:
        return run_once(effort)
    except Exception as exc:
        if effort != "default" and looks_like_effort_error(exc):
            logger.warning(
                "OpenAI translation effort %s was rejected; retrying with provider default",
                effort,
            )
            return run_once("default")
        raise


def _validate_translation(card: dict, out: dict) -> None:
    """Guard the translation: list item counts must match and the typed §2
    contract must still validate. Raises ValueError on any drift (the route
    turns this into a 502 and does NOT cache the result)."""
    for k in _TRANSLATABLE_FIELDS:
        src = card.get(k)
        if isinstance(src, list) and len(out.get(k) or []) != len(src):
            raise ValueError(f"translation changed list length for '{k}'")
    ResultCard(**out)  # re-validate the typed result-card schema
