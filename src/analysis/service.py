"""Thin service entrypoints for the Phase D analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .contracts import AnalysisArtifact, AnalysisRequest, IntegrityResult, RenderedReport
from .factory import build_default_pipeline
from .integrity import validate_and_repair_artifact
from .renderer import render_report

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer


@dataclass
class AnalysisRunOutput:
    """Combined output of one Phase D pipeline execution."""

    artifact: AnalysisArtifact
    integrity: IntegrityResult
    report: Optional[RenderedReport] = None


@dataclass
class SavedAnalysisReport:
    """Metadata returned after persisting one Phase D analysis report."""

    id: Optional[int]
    file_path: str
    title: str
    created_at: str


def run_analysis_request(
    request: AnalysisRequest,
    *,
    dal: "DataAccessLayer | None" = None,
    render_format: str = "markdown",
) -> AnalysisRunOutput:
    """Execute the default Phase D pipeline for one request."""
    pipeline = build_default_pipeline(dal=dal)
    artifact = pipeline.run(request)
    integrity = validate_and_repair_artifact(artifact)
    report = render_report(integrity, fmt=render_format)
    return AnalysisRunOutput(
        artifact=artifact,
        integrity=integrity,
        report=report,
    )


def _confidence_label_to_score(label: Optional[str]) -> Optional[float]:
    """Map coarse confidence labels to an approximate numeric score."""
    if not label:
        return None
    norm = str(label).strip().lower()
    if norm == "high":
        return 0.8
    if norm == "medium":
        return 0.6
    if norm == "low":
        return 0.35
    return None


def save_analysis_run(
    dal: "DataAccessLayer",
    output: AnalysisRunOutput,
    *,
    title: Optional[str] = None,
    report_type: str = "phase_d_analysis",
) -> SavedAnalysisReport:
    """Persist a rendered Phase D analysis report via the shared report tooling."""
    if output.report is None:
        raise ValueError("Cannot save analysis without a rendered report")

    from src.tools.report_tools import save_report

    artifact = output.artifact
    ticker = artifact.request.ticker.upper()
    final_decision = artifact.final_decision
    summary = final_decision.get("summary") or artifact.report_sections.get("executive_summary") or ticker
    action = final_decision.get("action")
    confidence = _confidence_label_to_score(final_decision.get("confidence"))
    report_title = title or f"{ticker} Phase D Analysis"

    saved = save_report(
        dal,
        title=report_title,
        tickers=[ticker],
        report_type=report_type,
        summary=summary,
        content=output.report.content,
        conclusion=str(action).upper() if action else None,
        confidence=confidence,
        provider="phase_d",
        model="structured-pipeline",
        tools_used=list(artifact.strategy_results.keys()),
        tool_calls=len(artifact.strategy_results),
    )
    return SavedAnalysisReport(
        id=saved.get("id"),
        file_path=saved["file_path"],
        title=saved["title"],
        created_at=saved["created_at"],
    )
