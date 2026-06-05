"""
The §2 AI output contract — the typed result card.

ProductSpec §2 makes the structured result card *product law*: any output bearing
a judgment, recommendation, saved artifact, comparison, or trading view MUST
conform to this fixed schema with per-claim traceability. This module is the
typed contract boundary; the reasoning layer (which provider, which tools) stays
behind it, and generated cards are validated against these models before they
are shown or stored.

v1 populates the analysis (non-trading) card. Trading key-levels (§2.1) and
thesis versioning (§2.2 "what changed vs last") are reserved here as optional
fields so the schema can grow without a migration, but are not produced in v1.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DataSourceRef(BaseModel):
    """A single evidence source with its freshness, for §2.3 traceability."""

    name: str
    as_of: Optional[str] = None  # ISO date/time the data is as-of
    is_real_time: bool = False
    detail: Optional[str] = None


class Completeness(BaseModel):
    """Which evidence categories were actually available (§2.3)."""

    news: bool = False
    fundamentals: bool = False
    technicals: bool = False
    note: Optional[str] = None


class Traceability(BaseModel):
    """§2.3 per-claim traceability: what data, as-of when, real-time?, single-model?."""

    data_sources: list[DataSourceRef] = Field(default_factory=list)
    is_single_model_inference: bool = True
    completeness: Completeness = Field(default_factory=Completeness)


class KeyLevels(BaseModel):
    """Reserved trading-card levels (§2.1). Not produced in v1."""

    ideal_entry: Optional[float] = None
    secondary_entry: Optional[float] = None
    stop: Optional[float] = None
    upside_target: Optional[float] = None


class ResultCard(BaseModel):
    """The fixed-schema §2 result card (analysis variant for v1)."""

    # --- identity / metadata ---
    ticker: str
    question: Optional[str] = None
    horizon: Optional[str] = None  # e.g. "swing (2-6 wks)" / "long-term"
    card_type: Literal["analysis", "trading"] = "analysis"
    analysis_time: str  # ISO timestamp the card was generated

    # --- §2.1 fixed fields ---
    conclusion: str
    primary_reasons: list[str] = Field(default_factory=list)
    counter_thesis: list[str] = Field(default_factory=list)  # 反方理由
    key_assumptions: list[str] = Field(default_factory=list)
    trigger_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    watch_list: list[str] = Field(default_factory=list)

    # --- §2.2 decisional questions (those not covered by fields above) ---
    market_narrative: Optional[str] = None  # main narrative / consensus
    divergence: Optional[str] = None  # where my judgment differs from consensus
    changes_vs_last: Optional[str] = None  # reserved — thesis versioning (not v1)

    # --- §2.3 confidence + traceability ---
    confidence_level: Literal["high", "medium", "low"]
    confidence_rationale: Optional[str] = None
    traceability: Traceability

    # --- reserved trading extension (v1: None) ---
    core_observation: Optional[str] = None
    action_suggestion: Optional[str] = None
    trend_outlook: Optional[str] = None
    key_levels: Optional[KeyLevels] = None


# Fields the LLM is responsible for filling during synthesis. Identity/metadata
# (ticker, analysis_time, traceability source list) are stamped by the generator
# from the evidence packet, so the synthesis schema can omit them and we merge.
SYNTHESIS_FIELDS = (
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
    "confidence_level",
    "confidence_rationale",
)
