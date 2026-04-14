"""Minimal fundamental strategy for the Phase D pipeline."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..contracts import AnalysisContext, StrategyResult, StrategyResultMap


def _to_mapping(value: Any) -> Dict[str, Any]:
    """Normalize dict-like or model-like objects into a plain mapping."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dict(dumped)
    return {}


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


class FundamentalStrategy:
    """Derive a compact fundamental quality summary from normalized metrics."""

    name = "fundamental"

    def run(
        self,
        context: AnalysisContext,
        upstream: StrategyResultMap,
    ) -> StrategyResult:
        del upstream  # first-pass version does not depend on prior strategies

        fundamentals = _to_mapping(context.fundamentals)

        revenue_growth = _to_float(fundamentals.get("revenue_growth"))
        gross_margin = _to_float(fundamentals.get("gross_margin"))
        free_cash_flow = _to_float(fundamentals.get("free_cash_flow"))
        debt_to_equity = _to_float(fundamentals.get("debt_to_equity"))
        current_ratio = _to_float(fundamentals.get("current_ratio"))
        pe_ratio = _to_float(fundamentals.get("pe_ratio"))

        usable_metrics = {
            "revenue_growth": revenue_growth,
            "gross_margin": gross_margin,
            "free_cash_flow": free_cash_flow,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "pe_ratio": pe_ratio,
        }
        available_count = sum(1 for value in usable_metrics.values() if value is not None)

        if available_count == 0:
            return StrategyResult(
                name=self.name,
                status="skipped",
                score=None,
                errors=["missing fundamentals"],
                payload={"quality": "unknown"},
            )

        positive_signals = []
        risk_flags = []
        score = 50.0

        if revenue_growth is not None:
            if revenue_growth >= 0.10:
                score += 10
                positive_signals.append(f"Revenue growth {revenue_growth:.1%}")
            elif revenue_growth < 0:
                score -= 10
                risk_flags.append(f"Revenue contraction {revenue_growth:.1%}")

        if gross_margin is not None:
            if gross_margin >= 0.40:
                score += 8
                positive_signals.append(f"Gross margin {gross_margin:.1%}")
            elif gross_margin < 0.20:
                score -= 8
                risk_flags.append(f"Weak gross margin {gross_margin:.1%}")

        if free_cash_flow is not None:
            if free_cash_flow > 0:
                score += 8
                positive_signals.append("Positive free cash flow")
            elif free_cash_flow < 0:
                score -= 8
                risk_flags.append("Negative free cash flow")

        if debt_to_equity is not None:
            if debt_to_equity <= 1.0:
                score += 6
                positive_signals.append(f"Debt/equity {debt_to_equity:.2f}")
            elif debt_to_equity >= 2.0:
                score -= 8
                risk_flags.append(f"Elevated leverage {debt_to_equity:.2f}")

        if current_ratio is not None:
            if current_ratio >= 1.2:
                score += 4
            elif current_ratio < 1.0:
                score -= 4
                risk_flags.append(f"Current ratio {current_ratio:.2f}")

        if pe_ratio is not None and revenue_growth is not None:
            if pe_ratio <= 25 and revenue_growth >= 0.10:
                score += 4
                positive_signals.append(f"Reasonable P/E {pe_ratio:.1f}")
            elif pe_ratio >= 45 and revenue_growth <= 0.05:
                score -= 6
                risk_flags.append(f"Stretched P/E {pe_ratio:.1f}")

        score = max(0.0, min(100.0, score))
        status = "ok" if available_count >= 3 else "partial"
        quality = "strong" if score >= 65 else "weak" if score <= 35 else "mixed"
        errors = [] if status == "ok" else ["limited fundamental coverage"]

        return StrategyResult(
            name=self.name,
            status=status,
            score=score,
            signals=positive_signals,
            risks=risk_flags,
            evidence=[
                {
                    "type": "fundamental_snapshot",
                    "metrics": {k: v for k, v in usable_metrics.items() if v is not None},
                }
            ],
            payload={
                "quality": quality,
                "available_metrics": available_count,
                "metrics": {k: v for k, v in usable_metrics.items() if v is not None},
            },
            errors=errors,
        )
