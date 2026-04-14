"""Contracts for the future Phase D analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Mapping, Optional

AnalysisMode = Literal["interactive", "batch"]
AnalysisDepth = Literal["quick", "standard", "full"]
AnalysisSource = Literal["cli", "discord", "api", "scheduled"]
StrategyStatus = Literal["ok", "partial", "failed", "skipped"]
IntegrityStatus = Literal["clean", "repaired", "placeholder_filled"]
ReportFormat = Literal["markdown", "html"]


def utc_now() -> datetime:
    """Return timezone-aware UTC now for dataclass defaults."""
    return datetime.now(timezone.utc)


@dataclass
class AnalysisRequest:
    """Normalized input to the analysis pipeline."""

    ticker: str
    as_of: datetime = field(default_factory=utc_now)
    mode: AnalysisMode = "interactive"
    depth: AnalysisDepth = "standard"
    source: AnalysisSource = "cli"
    user_query: Optional[str] = None
    attachments: List[Any] = field(default_factory=list)
    active_skills: List[str] = field(default_factory=list)
    run_id: Optional[str] = None


@dataclass
class AnalysisContext:
    """Pre-fetched, normalized context passed to strategies."""

    request: AnalysisRequest
    quote: Optional[Dict[str, Any]] = None
    market_data: Optional[Dict[str, Any]] = None
    fundamentals: Optional[Dict[str, Any]] = None
    news: List[Dict[str, Any]] = field(default_factory=list)
    social: List[Dict[str, Any]] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    provider_status: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """Standard output contract for an analysis strategy."""

    name: str
    status: StrategyStatus
    score: Optional[float] = None
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0


@dataclass
class AnalysisArtifact:
    """Aggregate structured artifact produced before rendering."""

    request: AnalysisRequest
    context_summary: Dict[str, Any]
    strategy_results: Dict[str, StrategyResult]
    final_decision: Dict[str, Any]
    report_sections: Dict[str, Any]
    degradation_summary: List[str]
    integrity_status: IntegrityStatus = "clean"
    errors: List[str] = field(default_factory=list)


@dataclass
class IntegrityResult:
    """Artifact plus repair metadata after integrity validation."""

    artifact: AnalysisArtifact
    status: IntegrityStatus
    missing_fields: List[str] = field(default_factory=list)
    repairs_applied: List[str] = field(default_factory=list)


@dataclass
class RenderedReport:
    """Rendered report artifact generated from a validated analysis artifact."""

    format: ReportFormat
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


StrategyResultMap = Mapping[str, StrategyResult]
