"""
Statistical anomaly detection for sentiment and news volume.

Identifies unusual sentiment levels or news activity that may precede
significant price movements.
"""

from typing import Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class SentimentAnomaly:
    """Result of sentiment anomaly detection."""
    is_anomaly: bool
    z_score: float
    direction: str  # POSITIVE, NEGATIVE
    percentile: float
    historical_mean: float
    historical_std: float
    current_value: float
    reason: str = ''


@dataclass
class VolumeAnomaly:
    """Result of news volume anomaly detection."""
    is_anomaly: bool
    z_score: float
    current_count: int
    historical_mean: float
    historical_std: float
    reason: str = ''


class AnomalyDetector:
    """
    Statistical anomaly detector for sentiment and news volume.

    Uses z-score analysis to identify statistically significant
    deviations from historical patterns.
    """

    def __init__(self, min_history: int = 14, z_threshold: float = 2.0):
        """
        Initialize anomaly detector.

        Args:
            min_history: Minimum number of historical data points required
            z_threshold: Z-score threshold for anomaly classification
        """
        self.min_history = min_history
        self.z_threshold = z_threshold

    def detect_sentiment_anomaly(
        self,
        df: pd.DataFrame,
        ticker: str,
        date: str,
        ticker_col: str = 'ticker',
        sentiment_col: str = 'llm_sentiment',
        date_col: str = 'date'
    ) -> SentimentAnomaly:
        """
        Detect sentiment anomaly for a ticker on a specific date.

        Args:
            df: DataFrame with historical sentiment data
            ticker: Ticker symbol
            date: Date to check (YYYY-MM-DD)
            ticker_col, sentiment_col, date_col: Column names

        Returns:
            SentimentAnomaly with detection results
        """
        ticker_df = df[df[ticker_col].str.upper() == ticker.upper()].copy()

        if len(ticker_df) < self.min_history:
            return SentimentAnomaly(
                is_anomaly=False,
                z_score=0,
                direction='NEUTRAL',
                percentile=0.5,
                historical_mean=3.0,
                historical_std=0,
                current_value=3.0,
                reason='INSUFFICIENT_DATA'
            )

        # Get historical statistics (excluding current date)
        historical = ticker_df[ticker_df[date_col] < date][sentiment_col]
        if len(historical) < self.min_history:
            historical = ticker_df[sentiment_col]

        mean = historical.mean()
        std = historical.std()

        if std == 0:
            std = 0.1  # Avoid division by zero

        # Get current value
        current_rows = ticker_df[ticker_df[date_col] == date]
        if len(current_rows) == 0:
            return SentimentAnomaly(
                is_anomaly=False,
                z_score=0,
                direction='NEUTRAL',
                percentile=0.5,
                historical_mean=mean,
                historical_std=std,
                current_value=mean,
                reason='NO_DATA_FOR_DATE'
            )

        current = current_rows[sentiment_col].mean()
        z_score = (current - mean) / std

        # Calculate percentile
        percentile = (historical <= current).mean()

        return SentimentAnomaly(
            is_anomaly=abs(z_score) > self.z_threshold,
            z_score=z_score,
            direction='POSITIVE' if z_score > 0 else 'NEGATIVE',
            percentile=percentile,
            historical_mean=mean,
            historical_std=std,
            current_value=current
        )

    def detect_volume_anomaly(
        self,
        df: pd.DataFrame,
        ticker: str,
        date: str,
        ticker_col: str = 'ticker',
        date_col: str = 'date',
        rolling_window: int = 14
    ) -> VolumeAnomaly:
        """
        Detect news volume anomaly for a ticker.

        Args:
            df: DataFrame with historical news data
            ticker: Ticker symbol
            date: Date to check (YYYY-MM-DD)
            ticker_col, date_col: Column names
            rolling_window: Days for rolling average

        Returns:
            VolumeAnomaly with detection results
        """
        ticker_df = df[df[ticker_col].str.upper() == ticker.upper()].copy()

        # Count articles per day
        daily_counts = ticker_df.groupby(date_col).size()

        if len(daily_counts) < rolling_window:
            return VolumeAnomaly(
                is_anomaly=False,
                z_score=0,
                current_count=0,
                historical_mean=0,
                historical_std=0,
                reason='INSUFFICIENT_DATA'
            )

        # Calculate rolling statistics
        rolling_mean = daily_counts.rolling(rolling_window, min_periods=1).mean()
        rolling_std = daily_counts.rolling(rolling_window, min_periods=1).std()

        if date not in daily_counts.index:
            return VolumeAnomaly(
                is_anomaly=False,
                z_score=0,
                current_count=0,
                historical_mean=rolling_mean.iloc[-1] if len(rolling_mean) > 0 else 0,
                historical_std=rolling_std.iloc[-1] if len(rolling_std) > 0 else 0,
                reason='NO_DATA_FOR_DATE'
            )

        current = daily_counts[date]
        mean = rolling_mean[date]
        std = rolling_std[date]

        if std == 0 or pd.isna(std):
            std = 1  # Avoid division by zero

        z_score = (current - mean) / std

        return VolumeAnomaly(
            is_anomaly=z_score > self.z_threshold,  # Only positive anomalies (volume spike)
            z_score=z_score,
            current_count=int(current),
            historical_mean=mean,
            historical_std=std
        )

    def detect_sector_anomaly(
        self,
        df: pd.DataFrame,
        sector_tickers: list,
        date: str,
        ticker_col: str = 'ticker',
        sentiment_col: str = 'llm_sentiment',
        date_col: str = 'date'
    ) -> SentimentAnomaly:
        """
        Detect sentiment anomaly at sector level.

        Args:
            df: DataFrame with historical sentiment data
            sector_tickers: List of tickers in the sector
            date: Date to check
            ticker_col, sentiment_col, date_col: Column names

        Returns:
            SentimentAnomaly for the sector
        """
        sector_df = df[df[ticker_col].str.upper().isin([t.upper() for t in sector_tickers])].copy()

        if len(sector_df) < self.min_history:
            return SentimentAnomaly(
                is_anomaly=False,
                z_score=0,
                direction='NEUTRAL',
                percentile=0.5,
                historical_mean=3.0,
                historical_std=0,
                current_value=3.0,
                reason='INSUFFICIENT_DATA'
            )

        # Aggregate by date
        daily_sentiment = sector_df.groupby(date_col)[sentiment_col].mean()

        if len(daily_sentiment) < self.min_history:
            return SentimentAnomaly(
                is_anomaly=False,
                z_score=0,
                direction='NEUTRAL',
                percentile=0.5,
                historical_mean=3.0,
                historical_std=0,
                current_value=3.0,
                reason='INSUFFICIENT_DATA'
            )

        # Get historical statistics
        historical = daily_sentiment[daily_sentiment.index < date]
        if len(historical) < self.min_history:
            historical = daily_sentiment

        mean = historical.mean()
        std = historical.std()

        if std == 0:
            std = 0.1

        # Get current value
        if date not in daily_sentiment.index:
            return SentimentAnomaly(
                is_anomaly=False,
                z_score=0,
                direction='NEUTRAL',
                percentile=0.5,
                historical_mean=mean,
                historical_std=std,
                current_value=mean,
                reason='NO_DATA_FOR_DATE'
            )

        current = daily_sentiment[date]
        z_score = (current - mean) / std
        percentile = (historical <= current).mean()

        return SentimentAnomaly(
            is_anomaly=abs(z_score) > self.z_threshold,
            z_score=z_score,
            direction='POSITIVE' if z_score > 0 else 'NEGATIVE',
            percentile=percentile,
            historical_mean=mean,
            historical_std=std,
            current_value=current
        )

    def detect_cross_ticker_anomaly(
        self,
        df: pd.DataFrame,
        date: str,
        ticker_col: str = 'ticker',
        sentiment_col: str = 'llm_sentiment',
        date_col: str = 'date',
        top_n: int = 10
    ) -> list:
        """
        Find tickers with the most extreme sentiment anomalies.

        Args:
            df: DataFrame with sentiment data
            date: Date to analyze
            ticker_col, sentiment_col, date_col: Column names
            top_n: Number of top anomalies to return

        Returns:
            List of (ticker, SentimentAnomaly) tuples, sorted by |z_score|
        """
        tickers = df[ticker_col].str.upper().unique()
        anomalies = []

        for ticker in tickers:
            anomaly = self.detect_sentiment_anomaly(
                df, ticker, date, ticker_col, sentiment_col, date_col
            )
            if anomaly.reason == '':  # Valid result
                anomalies.append((ticker, anomaly))

        # Sort by absolute z-score
        anomalies.sort(key=lambda x: abs(x[1].z_score), reverse=True)

        return anomalies[:top_n]