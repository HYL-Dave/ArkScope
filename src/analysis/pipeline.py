"""Minimal but structured Phase D analysis pipeline skeleton."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence

from .contracts import AnalysisArtifact, AnalysisContext, AnalysisRequest, StrategyResult
from .strategies.base import AnalysisStrategy

ContextBuilder = Callable[[AnalysisRequest], AnalysisContext]
ArtifactBuilder = Callable[[AnalysisContext, Dict[str, StrategyResult]], AnalysisArtifact]


def _default_context_builder(request: AnalysisRequest) -> AnalysisContext:
    """Build the smallest valid analysis context."""
    return AnalysisContext(request=request)


def _summarize_strategy_payload(payload: Dict[str, Any]) -> List[str]:
    """Build a compact list of human-readable bullet lines from one payload."""
    lines: List[str] = []
    for key in (
        "trend",
        "quality",
        "sentiment_regime",
        "risk_level",
        "action",
        "confidence",
    ):
        value = payload.get(key)
        if value not in (None, "", []):
            lines.append(f"{key}: {value}")

    if "drivers" in payload and isinstance(payload["drivers"], list) and payload["drivers"]:
        lines.append("drivers: " + ", ".join(str(driver) for driver in payload["drivers"]))

    if "metrics" in payload and isinstance(payload["metrics"], dict) and payload["metrics"]:
        metric_parts = []
        for metric_name, metric_value in payload["metrics"].items():
            metric_parts.append(f"{metric_name}={metric_value}")
        lines.append("metrics: " + ", ".join(metric_parts[:6]))

    return lines


def _default_artifact_builder(
    context: AnalysisContext,
    strategy_results: Dict[str, StrategyResult],
) -> AnalysisArtifact:
    """Build a minimal aggregate artifact from strategy outputs."""
    degradation_summary: List[str] = []
    errors: List[str] = []
    for result in strategy_results.values():
        if result.status in {"partial", "failed", "skipped"}:
            degradation_summary.append(f"{result.name}:{result.status}")
        if result.errors:
            errors.extend(result.errors)

    final_decision = dict(
        strategy_results.get("decision", StrategyResult(name="decision", status="skipped")).payload
    )

    strategy_sections: Dict[str, Dict[str, Any]] = {}
    for name, result in strategy_results.items():
        strategy_sections[name] = {
            "status": result.status,
            "score": result.score,
            "signals": list(result.signals),
            "risks": list(result.risks),
            "summary_lines": _summarize_strategy_payload(result.payload),
        }

    report_sections = {
        "executive_summary": final_decision.get("summary", ""),
        "strategies": strategy_sections,
    }
    context_summary = {
        "ticker": context.request.ticker,
        "mode": context.request.mode,
        "depth": context.request.depth,
        "provider_status": dict(context.provider_status),
        "news_count": len(context.news),
        "social_count": len(context.social),
        "has_quote": context.quote is not None,
        "has_fundamentals": context.fundamentals is not None,
    }
    return AnalysisArtifact(
        request=context.request,
        context_summary=context_summary,
        strategy_results=strategy_results,
        final_decision=final_decision,
        report_sections=report_sections,
        degradation_summary=degradation_summary,
        errors=errors,
    )


class AnalysisPipeline:
    """Sequential orchestrator for Phase D strategy execution."""

    def __init__(
        self,
        strategies: Sequence[AnalysisStrategy],
        *,
        context_builder: ContextBuilder | None = None,
        artifact_builder: ArtifactBuilder | None = None,
    ) -> None:
        self._strategies = list(strategies)
        self._context_builder = context_builder or _default_context_builder
        self._artifact_builder = artifact_builder or _default_artifact_builder

    @property
    def strategies(self) -> List[AnalysisStrategy]:
        """Return configured strategy instances in run order."""
        return list(self._strategies)

    def build_context(self, request: AnalysisRequest) -> AnalysisContext:
        """Build the normalized context for one analysis request."""
        return self._context_builder(request)

    def run_strategies(self, context: AnalysisContext) -> Dict[str, StrategyResult]:
        """Execute all strategies sequentially, passing upstream results downstream."""
        results: Dict[str, StrategyResult] = {}
        for strategy in self._strategies:
            result = strategy.run(context, results)
            results[result.name] = result
        return results

    def build_artifact(
        self,
        context: AnalysisContext,
        strategy_results: Dict[str, StrategyResult],
    ) -> AnalysisArtifact:
        """Aggregate strategy outputs into one pre-render artifact."""
        return self._artifact_builder(context, strategy_results)

    def run(self, request: AnalysisRequest) -> AnalysisArtifact:
        """Execute the full analysis pipeline for one request."""
        context = self.build_context(request)
        strategy_results = self.run_strategies(context)
        return self.build_artifact(context, strategy_results)
