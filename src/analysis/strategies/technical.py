"""Minimal technical strategy for the Phase D pipeline."""

from __future__ import annotations

from typing import Any, Dict, Optional

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


class TechnicalStrategy:
    """Derive a small technical summary from price and moving averages."""

    name = "technical"

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        del upstream  # unused for the first technical stage

        market_data: Dict[str, Any] = dict(context.market_data or {})
        quote: Dict[str, Any] = dict(context.quote or {})

        price = _to_float(quote.get("price") if quote else None)
        if price is None:
            price = _to_float(market_data.get("price"))
        ma5 = _to_float(market_data.get("ma5"))
        ma10 = _to_float(market_data.get("ma10"))
        ma20 = _to_float(market_data.get("ma20"))

        if price is None:
            return StrategyResult(
                name=self.name,
                status="skipped",
                score=None,
                errors=["missing price"],
                payload={"trend": "unknown"},
            )

        if ma5 is None or ma10 is None or ma20 is None:
            return StrategyResult(
                name=self.name,
                status="partial",
                score=50.0,
                signals=["Price available, moving-average stack incomplete"],
                payload={
                    "trend": "incomplete",
                    "price": price,
                    "ma5": ma5,
                    "ma10": ma10,
                    "ma20": ma20,
                },
                errors=["incomplete moving averages"],
            )

        bullish_alignment = price > ma5 > ma10 > ma20
        bearish_alignment = price < ma5 < ma10 < ma20

        if bullish_alignment:
            score = 75.0
            trend = "bullish"
            signals = ["Price is above a bullish MA stack"]
            risks = []
        elif bearish_alignment:
            score = 25.0
            trend = "bearish"
            signals = []
            risks = ["Price is below a bearish MA stack"]
        else:
            score = 50.0
            trend = "mixed"
            signals = ["Price and moving averages are not aligned"]
            risks = []

        return StrategyResult(
            name=self.name,
            status="ok",
            score=score,
            signals=signals,
            risks=risks,
            evidence=[
                {
                    "type": "technical_snapshot",
                    "price": price,
                    "ma5": ma5,
                    "ma10": ma10,
                    "ma20": ma20,
                }
            ],
            payload={
                "trend": trend,
                "bullish_alignment": bullish_alignment,
                "bearish_alignment": bearish_alignment,
                "price": price,
                "ma5": ma5,
                "ma10": ma10,
                "ma20": ma20,
            },
        )
