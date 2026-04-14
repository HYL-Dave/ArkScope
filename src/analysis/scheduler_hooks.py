"""Thin scheduler adapters for recurring Phase D analysis jobs."""

from __future__ import annotations

from typing import Callable, Iterable, List

from .contracts import AnalysisArtifact, AnalysisRequest
from .integrity import IntegrityResult, validate_and_repair_artifact
from .pipeline import AnalysisPipeline
from .renderer import render_report

ArtifactConsumer = Callable[[AnalysisArtifact], None]


def run_scheduled_batch(
    pipeline: AnalysisPipeline,
    tickers: Iterable[str],
    *,
    artifact_consumer: ArtifactConsumer | None = None,
) -> List[IntegrityResult]:
    """Execute a batch of scheduled analysis requests through the Phase D pipeline."""
    results: List[IntegrityResult] = []
    for ticker in tickers:
        artifact = pipeline.run(
            AnalysisRequest(
                ticker=ticker,
                mode="batch",
                source="scheduled",
            )
        )
        integrity_result = validate_and_repair_artifact(artifact)
        if artifact_consumer is not None:
            artifact_consumer(integrity_result.artifact)
        results.append(integrity_result)
    return results


def render_scheduled_batch(
    pipeline: AnalysisPipeline,
    tickers: Iterable[str],
) -> List[str]:
    """Run scheduled batch analysis and return rendered Markdown reports."""
    rendered: List[str] = []
    for integrity_result in run_scheduled_batch(pipeline, tickers):
        report = render_report(integrity_result, fmt="markdown")
        if report is not None:
            rendered.append(report.content)
    return rendered
