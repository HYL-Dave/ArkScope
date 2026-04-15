"""Phase D analysis pipeline primitives."""

from .contracts import (
    AnalysisArtifact,
    AnalysisContext,
    AnalysisRequest,
    IntegrityResult,
    RenderedReport,
    StrategyResult,
)
from .integrity import (
    apply_placeholder_fill,
    collect_missing_required_fields,
    validate_and_repair_artifact,
)
from .pipeline import AnalysisPipeline
from .context_builder import build_analysis_context
from .factory import build_default_pipeline
from .renderer import render_report
from .scheduler_hooks import render_scheduled_batch, run_scheduled_batch
from .service import AnalysisRunOutput, SavedAnalysisReport, run_analysis_request, save_analysis_run
from .strategies import build_default_strategies

__all__ = [
    "AnalysisArtifact",
    "AnalysisContext",
    "AnalysisPipeline",
    "AnalysisRequest",
    "AnalysisRunOutput",
    "SavedAnalysisReport",
    "IntegrityResult",
    "RenderedReport",
    "StrategyResult",
    "apply_placeholder_fill",
    "build_analysis_context",
    "build_default_pipeline",
    "build_default_strategies",
    "collect_missing_required_fields",
    "render_report",
    "render_scheduled_batch",
    "run_scheduled_batch",
    "run_analysis_request",
    "save_analysis_run",
    "validate_and_repair_artifact",
]
