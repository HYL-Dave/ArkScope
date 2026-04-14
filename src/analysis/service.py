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
