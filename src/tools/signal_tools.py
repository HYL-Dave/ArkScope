"""
Signal detection tool functions (3 tools).

11. detect_anomalies    — Statistical anomaly detection (sentiment + volume)
12. detect_event_chains — Identify related event sequences
13. synthesize_signal   — Multi-factor signal synthesis
"""

from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import TradingSignal

logger = logging.getLogger(__name__)


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


def synthesize_signal(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 30,
    strategy: Optional[str] = None,
    as_of_date: Optional[str] = None,
) -> TradingSignal:
    """
    Synthesize a multi-factor trading signal for a ticker.

    Combines:
        - Sector momentum (SectorAggregator)
        - Event chains (EventChainDetector)
        - Sentiment anomaly (AnomalyDetector)
        - Volume anomaly (AnomalyDetector)

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days
        strategy: Strategy name for custom weights (from user_profile.yaml)
        as_of_date: Anchor date (YYYY-MM-DD). Defaults to the latest date
                    in the data, ensuring reproducible offline analysis.

    Returns:
        TradingSignal with action, confidence, composite_score,
        risk_level, reasoning, factors
    """
    from src.signals.anomaly_detector import AnomalyDetector
    from src.signals.event_chain import EventChainDetector
    from src.signals.sector_aggregator import SectorAggregator
    from src.signals.synthesizer import SignalSynthesizer

    ticker = ticker.upper()

    # Load custom weights if strategy specified
    weights = None
    if strategy:
        w = dal.get_strategy_weights(strategy)
        if w:
            weights = w

    # Prepare news data
    df = _prepare_news_df_for_signals(dal, ticker=None, days=days)

    signals_input: Dict = {}
    # Use ticker-specific max date as anchor
    if as_of_date:
        anchor = as_of_date
    elif not df.empty:
        ticker_df = df[df["ticker"].str.upper() == ticker.upper()]
        anchor = str(ticker_df["date"].max()) if not ticker_df.empty else str(df["date"].max())
    else:
        anchor = date.today().isoformat()

    # 1. Sector momentum
    try:
        aggregator = SectorAggregator()
        sector = aggregator.get_sector(ticker)
        if sector and not df.empty:
            momentum = aggregator.detect_sector_momentum(
                df, sector=sector, lookback=days,
                ticker_col="ticker", sentiment_col="llm_sentiment", date_col="date",
            )
            signals_input["sector_momentum"] = momentum
    except Exception as e:
        logger.debug(f"Sector momentum failed for {ticker}: {e}")

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
    except Exception as e:
        logger.debug(f"Event chain detection failed for {ticker}: {e}")

    # 3. Sentiment anomaly
    try:
        if not df.empty:
            detector = AnomalyDetector()
            sent_anomaly = detector.detect_sentiment_anomaly(
                df, ticker=ticker, date=anchor,
                ticker_col="ticker", sentiment_col="llm_sentiment", date_col="date",
            )
            signals_input["sentiment_anomaly"] = sent_anomaly
    except Exception as e:
        logger.debug(f"Sentiment anomaly failed for {ticker}: {e}")

    # 4. Volume anomaly
    try:
        if not df.empty:
            detector = AnomalyDetector()
            vol_anomaly = detector.detect_volume_anomaly(
                df, ticker=ticker, date=anchor,
                ticker_col="ticker", date_col="date",
            )
            signals_input["volume_anomaly"] = vol_anomaly
    except Exception as e:
        logger.debug(f"Volume anomaly failed for {ticker}: {e}")

    # Synthesize
    synthesizer = SignalSynthesizer(weights=weights)

    try:
        sector_name = None
        try:
            aggregator = SectorAggregator()
            sector_name = aggregator.get_sector(ticker)
        except Exception:
            pass

        signal = synthesizer.synthesize(
            signals=signals_input,
            ticker=ticker,
            sector=sector_name,
        )
    except Exception as e:
        logger.warning(f"Signal synthesis failed for {ticker}: {e}")
        return TradingSignal(
            ticker=ticker,
            action="HOLD",
            confidence=0.0,
            composite_score=0.0,
            risk_level=3,
            reasoning=f"Signal synthesis failed: {e}",
        )

    # Convert to our schema
    factors = {}
    for f in signal.factors:
        factors[f.factor_type] = round(f.impact * f.weight, 4)

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