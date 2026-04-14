"""Minimal sentiment strategy for the Phase D pipeline."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ..contracts import AnalysisContext, StrategyResult, StrategyResultMap


def _to_float(value: Any) -> Optional[float]:
    """Convert a scalar to float when possible."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _extract_sentiment_scores(items: Iterable[Dict[str, Any]]) -> List[float]:
    """Extract normalized 1-5 style sentiment scores from heterogeneous items."""
    scores: List[float] = []
    for item in items:
        score = (
            _to_float(item.get("sentiment_score"))
            or _to_float(item.get("llm_sentiment"))
            or _to_float(item.get("sentiment"))
            or _to_float(item.get("score"))
        )
        if score is not None:
            scores.append(score)
    return scores


class SentimentStrategy:
    """Summarize recent directional sentiment from news and social context."""

    name = "sentiment"

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        del upstream  # no dependency in the first pass

        news_items = [item for item in context.news if isinstance(item, dict)]
        social_items = [item for item in context.social if isinstance(item, dict)]

        scores = _extract_sentiment_scores(news_items) + _extract_sentiment_scores(social_items)
        if not scores:
            return StrategyResult(
                name=self.name,
                status="skipped",
                score=None,
                errors=["missing sentiment observations"],
                payload={"sentiment_regime": "unknown", "observation_count": 0},
            )

        average_score = sum(scores) / len(scores)
        normalized_score = max(0.0, min(100.0, (average_score - 1.0) / 4.0 * 100.0))
        observation_count = len(scores)

        if average_score >= 4.0:
            regime = "bullish"
            signals = [f"Average sentiment {average_score:.2f}/5 across {observation_count} observations"]
            risks = []
        elif average_score <= 2.0:
            regime = "bearish"
            signals = []
            risks = [f"Average sentiment {average_score:.2f}/5 across {observation_count} observations"]
        else:
            regime = "neutral"
            signals = [f"Mixed sentiment {average_score:.2f}/5"]
            risks = []

        status = "ok" if observation_count >= 3 else "partial"
        errors = [] if status == "ok" else ["limited sentiment coverage"]

        return StrategyResult(
            name=self.name,
            status=status,
            score=normalized_score,
            signals=signals,
            risks=risks,
            evidence=[
                {
                    "type": "sentiment_summary",
                    "observation_count": observation_count,
                    "average_score": round(average_score, 3),
                }
            ],
            payload={
                "sentiment_regime": regime,
                "average_score": average_score,
                "observation_count": observation_count,
            },
            errors=errors,
        )
