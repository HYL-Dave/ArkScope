"""Convenience factories for assembling the default Phase D pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .context_builder import build_dal_context_builder
from .pipeline import AnalysisPipeline
from .strategies import build_default_strategies

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer


def build_default_pipeline(
    *,
    dal: "DataAccessLayer | None" = None,
) -> AnalysisPipeline:
    """Build the default Phase D pipeline with an optional DAL-backed context builder."""
    context_builder = build_dal_context_builder(dal) if dal is not None else None
    return AnalysisPipeline(
        build_default_strategies(),
        context_builder=context_builder,
    )
