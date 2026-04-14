"""Strategy interfaces and minimal Phase D strategy implementations."""

from .base import AnalysisStrategy
from .decision import DecisionStrategy
from .fundamental import FundamentalStrategy
from .risk import RiskStrategy
from .sentiment import SentimentStrategy
from .technical import TechnicalStrategy


def build_default_strategies() -> list[AnalysisStrategy]:
    """Return the default Phase D strategy chain in execution order."""
    return [
        TechnicalStrategy(),
        FundamentalStrategy(),
        SentimentStrategy(),
        RiskStrategy(),
        DecisionStrategy(),
    ]


__all__ = [
    "AnalysisStrategy",
    "DecisionStrategy",
    "FundamentalStrategy",
    "RiskStrategy",
    "SentimentStrategy",
    "TechnicalStrategy",
    "build_default_strategies",
]
