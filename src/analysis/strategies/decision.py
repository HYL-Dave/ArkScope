"""Minimal decision strategy that aggregates upstream strategy outputs."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from ..contracts import AnalysisContext, StrategyResult, StrategyResultMap


class DecisionStrategy:
    """Aggregate upstream strategy scores into one final action."""

    name = "decision"

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "technical": 1.0,
        "fundamental": 1.0,
        "sentiment": 0.8,
        "risk": 1.2,
    }

    def __init__(self, weights: Dict[str, float] | None = None) -> None:
        self._weights = dict(weights or self.DEFAULT_WEIGHTS)

    def _weighted_scores(self, upstream: StrategyResultMap) -> List[Tuple[str, float, float]]:
        weighted: List[Tuple[str, float, float]] = []
        for name, result in upstream.items():
            if result.score is None:
                continue
            weight = self._weights.get(name, 1.0)
            weighted.append((name, float(result.score), weight))
        return weighted

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        weighted = self._weighted_scores(upstream)
        if not weighted:
            return StrategyResult(
                name=self.name,
                status="partial",
                score=50.0,
                signals=["No upstream strategy scores available"],
                payload={
                    "summary": f"{context.request.ticker}: insufficient strategy coverage",
                    "action": "hold",
                    "confidence": "low",
                },
                errors=["missing upstream scores"],
            )

        total_weight = sum(weight for _, _, weight in weighted)
        aggregate_score = sum(score * weight for _, score, weight in weighted) / total_weight

        if aggregate_score >= 65:
            action = "buy"
            confidence = "high" if aggregate_score >= 75 else "medium"
        elif aggregate_score <= 35:
            action = "sell"
            confidence = "high" if aggregate_score <= 25 else "medium"
        else:
            action = "hold"
            confidence = "medium"

        drivers = [f"{name}:{score:.1f}" for name, score, _ in weighted]
        summary = (
            f"{context.request.ticker}: {action.upper()} bias from "
            + ", ".join(drivers)
        )

        signals = [f"Aggregate score={aggregate_score:.1f}"]
        risks: List[str] = []
        for result in upstream.values():
            risks.extend(result.risks)

        return StrategyResult(
            name=self.name,
            status="ok",
            score=aggregate_score,
            signals=signals,
            risks=risks,
            evidence=[
                {
                    "type": "aggregate_scores",
                    "components": [
                        {"strategy": name, "score": score, "weight": weight}
                        for name, score, weight in weighted
                    ],
                }
            ],
            payload={
                "summary": summary,
                "action": action,
                "confidence": confidence,
                "aggregate_score": aggregate_score,
                "drivers": drivers,
            },
        )
