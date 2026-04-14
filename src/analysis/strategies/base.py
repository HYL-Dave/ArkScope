"""Base strategy protocol for Phase D analysis modules."""

from __future__ import annotations

from typing import Protocol

from ..contracts import AnalysisContext, StrategyResult, StrategyResultMap


class AnalysisStrategy(Protocol):
    """Provider-neutral contract for a pipeline strategy."""

    name: str

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        """Run the strategy against one context and prior strategy outputs."""
