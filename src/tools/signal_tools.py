"""
Signal detection tool functions (4 tools).

11. detect_anomalies     — Statistical anomaly detection (sentiment + volume)
12. detect_event_chains  — Identify related event sequences
13. synthesize_signal    — Multi-factor signal synthesis (recommendation summary)
14. get_signal_factors   — Same factors as synthesize_signal but with raw
                            value/weight/contribution per factor + data_quality
                            block. For inspection / cross-sectional ranking,
                            not as a price prediction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import TradingSignal

logger = logging.getLogger(__name__)


# Factor type strings exposed by SignalSynthesizer. Kept as a constant so
# tools and the cross-sectional ranking endpoint use the same names rather
# than letting input-bucket names ("volume_anomaly") drift into output
# semantics ("VOLUME_SPIKE").
FACTOR_TYPES = (
    "SECTOR_MOMENTUM",
    "EVENT_CHAIN",
    "SENTIMENT_ANOMALY",
    "VOLUME_SPIKE",
    "EXTREME_SENTIMENT",
)


def _prepare_news_df_for_signals(
    dal: DataAccessLayer,
    ticker: Optional[str],
    days: int,
    scored_only: bool = True,
) -> pd.DataFrame:
    """
    Prepare news DataFrame with column names expected by signals module.

    The signals module expects: llm_sentiment, llm_risk, event_type, date, ticker, title.
    Our DAL returns: sentiment_score, risk_score, date, ticker, title.
    """
    from src.signals.event_tagger import EventTagger

    result = dal.get_news(ticker=ticker, days=days, scored_only=scored_only)
    if not result.articles:
        return pd.DataFrame()

    rows = []
    for a in result.articles:
        rows.append({
            "date": a.date,
            "ticker": a.ticker,
            "title": a.title,
            "llm_sentiment": a.sentiment_score,
            "llm_risk": a.risk_score,
            "source": a.source,
        })

    df = pd.DataFrame(rows)
    if scored_only:
        df = df.dropna(subset=["llm_sentiment"])

    # Add event_type via EventTagger
    if not df.empty:
        tagger = EventTagger()
        articles_for_tagging = [{"title": t} for t in df["title"].tolist()]
        tag_results = tagger.tag_batch(articles_for_tagging)
        df["event_type"] = [r.primary_type for r in tag_results]

    return df


def detect_anomalies(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
    as_of_date: Optional[str] = None,
) -> dict:
    """
    Detect statistical anomalies in sentiment and news volume for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period for historical baseline
        as_of_date: Anchor date (YYYY-MM-DD). Defaults to the latest date
                    in the data, ensuring reproducible offline analysis.

    Returns:
        Dict with:
            ticker, date, sentiment_anomaly, volume_anomaly,
            plus details for each (z_score, direction, percentile, etc.)
    """
    from src.signals.anomaly_detector import AnomalyDetector

    df = _prepare_news_df_for_signals(dal, ticker=None, days=days, scored_only=True)
    if df.empty:
        return {
            "ticker": ticker.upper(),
            "date": as_of_date or date.today().isoformat(),
            "error": (
                "No scored news articles available. "
                "Anomaly detection requires sentiment scores from LLM scoring pipeline. "
                "Raw (unscored) articles exist but cannot be used for statistical anomaly analysis."
            ),
        }

    detector = AnomalyDetector()
    # Use ticker-specific max date to avoid NO_DATA_FOR_DATE for tickers
    # with different news update schedules.
    ticker_df = df[df["ticker"].str.upper() == ticker.upper()]
    anchor = as_of_date or (
        str(ticker_df["date"].max()) if not ticker_df.empty
        else str(df["date"].max())
    )

    # Sentiment anomaly
    try:
        sent_anomaly = detector.detect_sentiment_anomaly(
            df, ticker=ticker.upper(), date=anchor,
            ticker_col="ticker", sentiment_col="llm_sentiment", date_col="date",
        )
        sentiment_result = {
            "is_anomaly": bool(sent_anomaly.is_anomaly),
            "z_score": float(round(sent_anomaly.z_score, 3)),
            "direction": sent_anomaly.direction,
            "percentile": float(round(sent_anomaly.percentile, 1)),
            "current_value": float(round(sent_anomaly.current_value, 2)),
            "historical_mean": float(round(sent_anomaly.historical_mean, 2)),
            "reason": sent_anomaly.reason,
        }
    except Exception as e:
        sentiment_result = {"error": str(e)}

    # Volume anomaly
    try:
        vol_anomaly = detector.detect_volume_anomaly(
            df, ticker=ticker.upper(), date=anchor,
            ticker_col="ticker", date_col="date",
        )
        volume_result = {
            "is_anomaly": bool(vol_anomaly.is_anomaly),
            "z_score": float(round(vol_anomaly.z_score, 3)),
            "current_count": int(vol_anomaly.current_count),
            "historical_mean": float(round(vol_anomaly.historical_mean, 2)),
            "reason": vol_anomaly.reason,
        }
    except Exception as e:
        volume_result = {"error": str(e)}

    return {
        "ticker": ticker.upper(),
        "date": anchor,
        "sentiment_anomaly": sentiment_result,
        "volume_anomaly": volume_result,
    }


def detect_event_chains(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
) -> List[dict]:
    """
    Detect event chain patterns (sequences of related events) for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days

    Returns:
        List of dicts, each with:
            pattern, impact_score, event_count,
            start_date, end_date, events (list of event summaries)
    """
    from src.signals.event_chain import EventChainDetector

    # Event chains work with unscored data — tagging is title-based
    df = _prepare_news_df_for_signals(dal, ticker=ticker, days=days, scored_only=False)
    if df.empty or "event_type" not in df.columns:
        return []
    # Fill missing sentiment with neutral (3) so chain impact calc doesn't break
    df["llm_sentiment"] = df["llm_sentiment"].fillna(3.0).infer_objects(copy=False)

    detector = EventChainDetector()

    # Convert DataFrame rows to Event objects
    events = detector.events_from_dataframe(
        df,
        ticker_col="ticker",
        date_col="date",
        event_type_col="event_type",
        sentiment_col="llm_sentiment",
        title_col="title",
    )

    if not events:
        return []

    chains = detector.detect_chains(events)

    results = []
    for chain in chains:
        results.append({
            "pattern": chain.pattern,
            "impact_score": round(chain.impact_score, 3),
            "event_count": len(chain.events),
            "start_date": chain.start_date.isoformat() if chain.start_date else None,
            "end_date": chain.end_date.isoformat() if chain.end_date else None,
            "ticker": chain.ticker,
            "events": [
                {
                    "date": e.date.isoformat() if e.date else None,
                    "event_type": e.event_type,
                    "title": e.title,
                    "sentiment_impact": round(e.sentiment_impact, 3),
                }
                for e in chain.events
            ],
        })

    return results


@dataclass
class _SignalContext:
    """Shared output of the synthesizer orchestration loop.

    Captures both the raw synthesizer signal (rich factor objects with
    impact / weight / details) and bookkeeping that downstream tools need
    for ``data_quality`` reporting:

      - news_count / scored_count → did this ticker actually have data?
      - missing_factors → which inputs we couldn't compute (sector
        unknown, no news, exception in detector)
      - errors → exception strings, useful for debugging
    """

    ticker: str
    anchor: str
    sector: Optional[str]
    raw_signal: Any  # synthesizer.TradingSignal | None
    news_count: int
    scored_count: int
    missing_factors: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _compute_signal_context(
    dal: DataAccessLayer,
    ticker: str,
    *,
    days: int,
    strategy: Optional[str],
    as_of_date: Optional[str],
    news_df: Optional[pd.DataFrame],
) -> _SignalContext:
    """Run the multi-factor pipeline once. Used by every signal-shaped tool.

    The expensive part — preparing news_df, computing factors, calling the
    synthesizer — happens here. ``synthesize_signal`` and
    ``get_signal_factors`` differ only in how they project the result.

    Bug-prevention notes baked into this function:

      - Per-ticker anchor ONLY when caller didn't supply ``as_of_date``.
        Cross-sectional ranking MUST pass an explicit anchor to avoid
        comparing different time slices across tickers.
      - ``volume_anomaly`` here is the synthesizer's INPUT bucket name;
        the OUTPUT factor_type is ``VOLUME_SPIKE``. Don't conflate.
    """
    from src.signals.anomaly_detector import AnomalyDetector
    from src.signals.event_chain import EventChainDetector
    from src.signals.sector_aggregator import SectorAggregator
    from src.signals.synthesizer import SignalSynthesizer

    ticker = ticker.upper()
    weights = None
    if strategy:
        w = dal.get_strategy_weights(strategy)
        if w:
            weights = w

    df = news_df if news_df is not None else _prepare_news_df_for_signals(
        dal, ticker=None, days=days
    )

    if as_of_date:
        anchor = as_of_date
    elif not df.empty:
        ticker_df = df[df["ticker"].str.upper() == ticker]
        anchor = str(ticker_df["date"].max()) if not ticker_df.empty else str(df["date"].max())
    else:
        anchor = date.today().isoformat()

    if df.empty:
        ticker_df_total = df
    else:
        ticker_df_total = df[df["ticker"].str.upper() == ticker]
    news_count = int(len(ticker_df_total))
    scored_count = (
        int(ticker_df_total["llm_sentiment"].notna().sum())
        if not ticker_df_total.empty and "llm_sentiment" in ticker_df_total.columns
        else 0
    )

    signals_input: Dict[str, Any] = {}
    missing_factors: List[str] = []
    errors: List[str] = []
    sector_name: Optional[str] = None

    aggregator = SectorAggregator()

    # 1. Sector momentum
    try:
        sector_name = aggregator.get_sector(ticker)
        if sector_name and not df.empty:
            momentum = aggregator.detect_sector_momentum(
                df, sector=sector_name, lookback=days,
                ticker_col="ticker", sentiment_col="llm_sentiment", date_col="date",
            )
            signals_input["sector_momentum"] = momentum
        else:
            missing_factors.append("SECTOR_MOMENTUM")
    except Exception as e:
        logger.debug(f"Sector momentum failed for {ticker}: {e}")
        errors.append(f"sector_momentum: {e}")
        missing_factors.append("SECTOR_MOMENTUM")

    # 2. Event chains
    try:
        if not df.empty and "event_type" in df.columns:
            chain_detector = EventChainDetector()
            ticker_df = df[df["ticker"] == ticker]
            if not ticker_df.empty:
                events = chain_detector.events_from_dataframe(
                    ticker_df,
                    ticker_col="ticker", date_col="date",
                    event_type_col="event_type", sentiment_col="llm_sentiment",
                    title_col="title",
                )
                chains = chain_detector.detect_chains(events) if events else []
                signals_input["event_chains"] = chains
            else:
                missing_factors.append("EVENT_CHAIN")
        else:
            missing_factors.append("EVENT_CHAIN")
    except Exception as e:
        logger.debug(f"Event chain detection failed for {ticker}: {e}")
        errors.append(f"event_chain: {e}")
        missing_factors.append("EVENT_CHAIN")

    # 3. Sentiment anomaly
    try:
        if not df.empty:
            detector = AnomalyDetector()
            sent_anomaly = detector.detect_sentiment_anomaly(
                df, ticker=ticker, date=anchor,
                ticker_col="ticker", sentiment_col="llm_sentiment", date_col="date",
            )
            signals_input["sentiment_anomaly"] = sent_anomaly
        else:
            missing_factors.append("SENTIMENT_ANOMALY")
    except Exception as e:
        logger.debug(f"Sentiment anomaly failed for {ticker}: {e}")
        errors.append(f"sentiment_anomaly: {e}")
        missing_factors.append("SENTIMENT_ANOMALY")

    # 4. Volume anomaly (synthesizer input key) → emits VOLUME_SPIKE factor.
    try:
        if not df.empty:
            detector = AnomalyDetector()
            vol_anomaly = detector.detect_volume_anomaly(
                df, ticker=ticker, date=anchor,
                ticker_col="ticker", date_col="date",
            )
            signals_input["volume_anomaly"] = vol_anomaly
        else:
            missing_factors.append("VOLUME_SPIKE")
    except Exception as e:
        logger.debug(f"Volume anomaly failed for {ticker}: {e}")
        errors.append(f"volume_anomaly: {e}")
        missing_factors.append("VOLUME_SPIKE")

    # Synthesize
    synthesizer = SignalSynthesizer(weights=weights)
    raw_signal: Any = None
    try:
        raw_signal = synthesizer.synthesize(
            signals=signals_input,
            ticker=ticker,
            sector=sector_name,
        )
    except Exception as e:
        logger.warning(f"Signal synthesis failed for {ticker}: {e}")
        errors.append(f"synthesize: {e}")

    return _SignalContext(
        ticker=ticker,
        anchor=anchor,
        sector=sector_name,
        raw_signal=raw_signal,
        news_count=news_count,
        scored_count=scored_count,
        missing_factors=missing_factors,
        errors=errors,
    )


def synthesize_signal(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
    strategy: Optional[str] = None,
    as_of_date: Optional[str] = None,
    news_df: Optional[pd.DataFrame] = None,
) -> TradingSignal:
    """
    Synthesize a multi-factor trading signal recommendation for a ticker.

    Combines:
        - Sector momentum (SectorAggregator)
        - Event chains (EventChainDetector)
        - Sentiment anomaly (AnomalyDetector)
        - Volume anomaly (AnomalyDetector)

    The output is a recommendation summary (action / confidence /
    composite_score / risk_level / reasoning), not a price prediction.
    Use ``get_signal_factors`` for raw per-factor inspection.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days
        strategy: Strategy name for custom weights (from user_profile.yaml)
        as_of_date: Anchor date (YYYY-MM-DD). Defaults to the ticker's
                    latest news date. For cross-sectional comparison
                    callers MUST supply a shared anchor.
        news_df: Optional preloaded news DataFrame. When provided, callers can
                 reuse one prepared dataset across multiple tickers instead of
                 rebuilding the same full-news context repeatedly.

    Returns:
        TradingSignal with action, confidence, composite_score,
        risk_level, reasoning, factors (flat factor_type → contribution).
    """
    ctx = _compute_signal_context(
        dal, ticker,
        days=days, strategy=strategy, as_of_date=as_of_date, news_df=news_df,
    )

    if ctx.raw_signal is None:
        reason = ctx.errors[-1] if ctx.errors else "Signal synthesis returned no result."
        return TradingSignal(
            ticker=ctx.ticker,
            action="HOLD",
            confidence=0.0,
            composite_score=0.0,
            risk_level=3,
            reasoning=f"Signal synthesis failed: {reason}",
        )

    signal = ctx.raw_signal
    factors = {f.factor_type: round(f.impact * f.weight, 4) for f in signal.factors}

    return TradingSignal(
        ticker=signal.ticker,
        sector=signal.sector,
        action=signal.action.value if hasattr(signal.action, "value") else str(signal.action),
        confidence=round(signal.confidence, 3),
        composite_score=round(signal.composite_score, 3),
        risk_level=signal.risk_level,
        reasoning=signal.reasoning,
        factors=factors if factors else None,
    )


def get_signal_factors(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
    as_of_date: Optional[str] = None,
    strategy: Optional[str] = None,
    news_df: Optional[pd.DataFrame] = None,
) -> dict:
    """Return the same factors as ``synthesize_signal`` but with raw
    per-factor breakdown plus a ``data_quality`` block.

    Output is a recommendation breakdown (factor types, impacts, weights,
    contributions), not a price prediction. Useful for explainability,
    cross-sectional ranking, and gating decisions on data sufficiency.

    Note that ``SECTOR_MOMENTUM`` is shared across tickers in the same
    sector — its contribution should NOT be read as ticker-specific
    conviction.

    Args:
        dal: DataAccessLayer instance.
        ticker: Stock ticker symbol.
        days: Lookback window in days.
        as_of_date: Anchor date (YYYY-MM-DD). Defaults to the ticker's
                    latest news date. Cross-sectional callers must pass
                    a shared anchor.
        strategy: Optional strategy name for custom weights.
        news_df: Optional preloaded news DataFrame to share across many
                 tickers in one batch.

    Returns:
        ``{ticker, as_of_date, sector, data_quality, factors[], composite}``
        where ``factors`` is a list of ``{factor_type, impact, weight,
        contribution, details}`` and ``composite`` carries the final
        ``score / action / confidence / risk_level / reasoning``.
        ``composite.action`` is a recommendation, not a prediction.
    """
    ctx = _compute_signal_context(
        dal, ticker,
        days=days, strategy=strategy, as_of_date=as_of_date, news_df=news_df,
    )

    factors_out: List[Dict[str, Any]] = []
    if ctx.raw_signal is not None:
        for f in ctx.raw_signal.factors:
            details = dict(f.details) if isinstance(f.details, dict) else {}
            factors_out.append({
                "factor_type": f.factor_type,
                "impact": round(float(f.impact), 4),
                "weight": round(float(f.weight), 4),
                "contribution": round(float(f.impact) * float(f.weight), 4),
                "details": details,
            })

    if ctx.raw_signal is not None:
        signal = ctx.raw_signal
        composite = {
            "score": round(float(signal.composite_score), 3),
            "action": (
                signal.action.value if hasattr(signal.action, "value") else str(signal.action)
            ),
            "confidence": round(float(signal.confidence), 3),
            "risk_level": int(signal.risk_level),
            "reasoning": signal.reasoning or "",
        }
    else:
        composite = {
            "score": 0.0,
            "action": "HOLD",
            "confidence": 0.0,
            "risk_level": 3,
            "reasoning": (
                "Signal synthesis returned no result; treat as no recommendation, "
                "not as a neutral HOLD."
            ),
        }

    return {
        "ticker": ctx.ticker,
        "as_of_date": ctx.anchor,
        "sector": ctx.sector,
        "data_quality": {
            "news_count": ctx.news_count,
            "scored_news_count": ctx.scored_count,
            "missing_factors": list(ctx.missing_factors),
            "errors": list(ctx.errors),
        },
        "factors": factors_out,
        "composite": composite,
    }
