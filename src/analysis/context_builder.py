"""Minimal context builder helpers for the Phase D analysis pipeline."""

from __future__ import annotations

import math
from statistics import pstdev
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional

from .contracts import AnalysisContext, AnalysisRequest

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

ContextResolver = Callable[[AnalysisRequest], Mapping[str, Any] | None]


def build_analysis_context(
    request: AnalysisRequest,
    *,
    quote_resolver: Optional[ContextResolver] = None,
    market_data_resolver: Optional[ContextResolver] = None,
    fundamentals_resolver: Optional[ContextResolver] = None,
    news_resolver: Optional[ContextResolver] = None,
    social_resolver: Optional[ContextResolver] = None,
    memory_resolver: Optional[ContextResolver] = None,
    provider_status: Optional[Dict[str, Any]] = None,
) -> AnalysisContext:
    """Build a normalized analysis context from optional resolver callbacks."""
    quote = dict(quote_resolver(request) or {}) if quote_resolver else None
    market_data = dict(market_data_resolver(request) or {}) if market_data_resolver else None
    fundamentals = dict(fundamentals_resolver(request) or {}) if fundamentals_resolver else None
    news = list(news_resolver(request) or []) if news_resolver else []
    social = list(social_resolver(request) or []) if social_resolver else []
    memory = dict(memory_resolver(request) or {}) if memory_resolver else {}
    return AnalysisContext(
        request=request,
        quote=quote,
        market_data=market_data,
        fundamentals=fundamentals,
        news=news,
        social=social,
        memory=memory,
        provider_status=dict(provider_status or {}),
    )


def _rolling_mean(values: List[float], window: int) -> Optional[float]:
    """Return the mean of the last `window` values when enough history exists."""
    if len(values) < window:
        return None
    subset = values[-window:]
    return sum(subset) / len(subset)


def _compute_annualized_volatility(closes: List[float]) -> Optional[float]:
    """Compute simple annualized volatility from daily close returns."""
    if len(closes) < 20:
        return None
    returns: List[float] = []
    for prev_close, curr_close in zip(closes[:-1], closes[1:]):
        if prev_close <= 0:
            continue
        returns.append((curr_close - prev_close) / prev_close)
    if len(returns) < 10:
        return None
    return pstdev(returns) * math.sqrt(252)


def _compute_max_drawdown(closes: List[float]) -> Optional[float]:
    """Compute max drawdown from a close-price series."""
    if not closes:
        return None
    peak = closes[0]
    max_drawdown = 0.0
    for close in closes:
        if close > peak:
            peak = close
        if peak > 0:
            drawdown = (close - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
    return max_drawdown


def _news_days_for_depth(depth: str) -> int:
    """Map pipeline depth to a news lookback window."""
    if depth == "quick":
        return 7
    if depth == "full":
        return 30
    return 14


def build_dal_context_builder(
    dal: "DataAccessLayer",
    *,
    price_days: int = 90,
    price_interval: str = "1d",
) -> Callable[[AnalysisRequest], AnalysisContext]:
    """Build a thin context builder backed by the existing DataAccessLayer."""

    def _quote_resolver(request: AnalysisRequest) -> Mapping[str, Any] | None:
        prices = dal.get_prices(request.ticker, interval=price_interval, days=price_days)
        if not prices.bars:
            return None
        latest = prices.bars[-1]
        return {
            "price": latest.close,
            "datetime": latest.datetime,
        }

    def _market_data_resolver(request: AnalysisRequest) -> Mapping[str, Any] | None:
        prices = dal.get_prices(request.ticker, interval=price_interval, days=price_days)
        if not prices.bars:
            return None
        closes = [float(bar.close) for bar in prices.bars]
        latest = closes[-1]
        return {
            "price": latest,
            "ma5": _rolling_mean(closes, 5),
            "ma10": _rolling_mean(closes, 10),
            "ma20": _rolling_mean(closes, 20),
            "volatility": _compute_annualized_volatility(closes),
            "max_drawdown": _compute_max_drawdown(closes),
        }

    def _fundamentals_resolver(request: AnalysisRequest) -> Mapping[str, Any] | None:
        from src.tools.analysis_tools import get_detailed_financials

        detailed = get_detailed_financials(dal, request.ticker)
        model_dump = getattr(detailed, "model_dump", None)
        if callable(model_dump):
            return model_dump(exclude_none=True)
        return None

    def _news_resolver(request: AnalysisRequest) -> List[Dict[str, Any]]:
        lookback_days = _news_days_for_depth(request.depth)
        news = dal.get_news(
            ticker=request.ticker,
            days=lookback_days,
            scored_only=True,
        )
        return [
            {
                "date": article.date,
                "title": article.title,
                "source": article.source,
                "publisher": article.publisher,
                "sentiment_score": article.sentiment_score,
                "risk_score": article.risk_score,
                "description": article.description,
                "url": article.url,
            }
            for article in news.articles
        ]

    def _build(request: AnalysisRequest) -> AnalysisContext:
        provider_status = {
            "backend_type": dal.backend_type,
            "price_interval": price_interval,
            "price_days": price_days,
        }
        return build_analysis_context(
            request,
            quote_resolver=_quote_resolver,
            market_data_resolver=_market_data_resolver,
            fundamentals_resolver=_fundamentals_resolver,
            news_resolver=_news_resolver,
            provider_status=provider_status,
        )

    return _build
