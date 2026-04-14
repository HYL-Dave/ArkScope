"""Minimal risk strategy for the Phase D pipeline."""

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


class RiskStrategy:
    """Estimate a compact risk posture from volatility, beta, and drawdown."""

    name = "risk"

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        del upstream  # independent first-pass risk snapshot

        market_data: Dict[str, Any] = dict(context.market_data or {})
        volatility = _to_float(market_data.get("volatility"))
        beta = _to_float(market_data.get("beta_60d") or market_data.get("beta"))
        max_drawdown = _to_float(market_data.get("max_drawdown"))

        if volatility is None and beta is None and max_drawdown is None:
            return StrategyResult(
                name=self.name,
                status="skipped",
                score=None,
                errors=["missing risk metrics"],
                payload={"risk_level": "unknown"},
            )

        score = 65.0
        signals = []
        risks = []
        available_count = sum(1 for value in (volatility, beta, max_drawdown) if value is not None)

        if volatility is not None:
            if volatility <= 0.25:
                score += 8
                signals.append(f"Contained volatility {volatility:.2f}")
            elif volatility >= 0.45:
                score -= 12
                risks.append(f"Elevated volatility {volatility:.2f}")

        if beta is not None:
            if beta <= 1.1:
                score += 6
                signals.append(f"Beta {beta:.2f}")
            elif beta >= 1.5:
                score -= 10
                risks.append(f"High beta {beta:.2f}")

        if max_drawdown is not None:
            if max_drawdown >= -0.15:
                score += 6
                signals.append(f"Drawdown {max_drawdown:.1%}")
            elif max_drawdown <= -0.30:
                score -= 12
                risks.append(f"Deep drawdown {max_drawdown:.1%}")

        score = max(0.0, min(100.0, score))
        risk_level = "low" if score >= 70 else "high" if score <= 35 else "moderate"
        status = "ok" if available_count >= 2 else "partial"
        errors = [] if status == "ok" else ["limited risk coverage"]

        return StrategyResult(
            name=self.name,
            status=status,
            score=score,
            signals=signals,
            risks=risks,
            evidence=[
                {
                    "type": "risk_snapshot",
                    "volatility": volatility,
                    "beta": beta,
                    "max_drawdown": max_drawdown,
                }
            ],
            payload={
                "risk_level": risk_level,
                "volatility": volatility,
                "beta": beta,
                "max_drawdown": max_drawdown,
            },
            errors=errors,
        )
