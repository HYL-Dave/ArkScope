"""
Sector-level sentiment aggregation.

Calculates sector-wide metrics from individual stock news to identify
sector rotation and momentum patterns.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import yaml
from pathlib import Path


@dataclass
class SectorMetrics:
    """Sector-level metrics."""
    sector: str
    sentiment_mean: float
    sentiment_std: float
    risk_mean: float
    article_count: int
    bullish_ratio: float
    bearish_ratio: float
    extreme_count: int
    tickers_covered: List[str]


@dataclass
class SectorMomentum:
    """Sector momentum analysis."""
    sector: str
    momentum: float
    trend: str  # ACCELERATING, DECELERATING, STABLE
    recent_sentiment: float
    prior_sentiment: float
    days_analyzed: int


class SectorAggregator:
    """
    Sector sentiment aggregator.

    Groups stocks by sector and calculates aggregate metrics to identify
    sector-level trends and rotation patterns.
    """

    # Default sector definitions
    DEFAULT_SECTORS = {
        'SPACE': ['RKLB', 'ASTS', 'LUNR', 'SPCE', 'ASTR', 'RDW', 'MNTS', 'BKSY', 'PL'],
        'AI_CHIPS': ['NVDA', 'AMD', 'AVGO', 'MRVL', 'INTC', 'QCOM', 'MU', 'ARM'],
        'AI_SOFTWARE': ['MSFT', 'GOOGL', 'META', 'PLTR', 'AI', 'PATH', 'SNOW'],
        'EV': ['TSLA', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'PTRA', 'GOEV'],
        'BIOTECH': ['MRNA', 'BNTX', 'REGN', 'GILD', 'AMGN', 'BIIB', 'VRTX'],
        'FINTECH': ['SQ', 'PYPL', 'COIN', 'AFRM', 'UPST', 'SOFI', 'HOOD'],
        'CLOUD': ['SNOW', 'NET', 'DDOG', 'MDB', 'CRWD', 'ZS', 'OKTA'],
        'CYBERSECURITY': ['CRWD', 'PANW', 'ZS', 'OKTA', 'FTNT', 'S'],
        'CLEAN_ENERGY': ['ENPH', 'SEDG', 'FSLR', 'RUN', 'PLUG', 'BE', 'CHPT'],
        'DEFENSE': ['LMT', 'RTX', 'NOC', 'BA', 'GD', 'HII'],
        'RETAIL': ['AMZN', 'WMT', 'TGT', 'COST', 'HD', 'LOW'],
        'HEALTHCARE': ['UNH', 'JNJ', 'PFE', 'LLY', 'ABBV', 'MRK'],
        'BANKS': ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS'],
    }

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize sector aggregator.

        Args:
            config_path: Optional path to YAML config with sector definitions.
                        If not provided, uses default definitions.
        """
        if config_path and config_path.exists():
            with open(config_path) as f:
                self.sectors = yaml.safe_load(f)
        else:
            self.sectors = self.DEFAULT_SECTORS

        # Build reverse mapping: ticker -> sector
        self.ticker_to_sector: Dict[str, str] = {}
        for sector, tickers in self.sectors.items():
            for ticker in tickers:
                self.ticker_to_sector[ticker] = sector

    def get_sector(self, ticker: str) -> Optional[str]:
        """Get sector for a ticker."""
        return self.ticker_to_sector.get(ticker.upper())

    def get_sector_tickers(self, sector: str) -> List[str]:
        """Get all tickers in a sector."""
        return self.sectors.get(sector, [])

    def calculate_sector_metrics(
        self,
        df: pd.DataFrame,
        date: str,
        ticker_col: str = 'ticker',
        sentiment_col: str = 'llm_sentiment',
        risk_col: str = 'llm_risk',
        date_col: str = 'date'
    ) -> Dict[str, SectorMetrics]:
        """
        Calculate sector-level metrics for a specific date.

        Args:
            df: DataFrame with news data
            date: Date to calculate metrics for (YYYY-MM-DD)
            ticker_col: Column name for ticker symbols
            sentiment_col: Column name for sentiment scores
            risk_col: Column name for risk scores
            date_col: Column name for dates

        Returns:
            Dict mapping sector names to SectorMetrics
        """
        results = {}

        # Filter to date if date column exists
        if date_col in df.columns:
            date_df = df[df[date_col] == date].copy()
        else:
            date_df = df.copy()

        for sector, tickers in self.sectors.items():
            sector_df = date_df[date_df[ticker_col].str.upper().isin(tickers)]

            if len(sector_df) == 0:
                continue

            sentiment = sector_df[sentiment_col]
            risk = sector_df[risk_col] if risk_col in sector_df.columns else pd.Series([3])

            results[sector] = SectorMetrics(
                sector=sector,
                sentiment_mean=sentiment.mean(),
                sentiment_std=sentiment.std() if len(sentiment) > 1 else 0,
                risk_mean=risk.mean(),
                article_count=len(sector_df),
                bullish_ratio=(sentiment >= 4).mean(),
                bearish_ratio=(sentiment <= 2).mean(),
                extreme_count=((sentiment >= 4.5) | (sentiment <= 1.5)).sum(),
                tickers_covered=sector_df[ticker_col].str.upper().unique().tolist()
            )

        return results

    def detect_sector_momentum(
        self,
        df: pd.DataFrame,
        sector: str,
        lookback: int = 7,
        ticker_col: str = 'ticker',
        sentiment_col: str = 'llm_sentiment',
        date_col: str = 'date'
    ) -> SectorMomentum:
        """
        Detect momentum changes in sector sentiment.

        Args:
            df: DataFrame with news data
            sector: Sector name
            lookback: Number of days to analyze
            ticker_col: Column name for ticker symbols
            sentiment_col: Column name for sentiment scores
            date_col: Column name for dates

        Returns:
            SectorMomentum with trend analysis
        """
        tickers = self.sectors.get(sector, [])
        if not tickers:
            return SectorMomentum(
                sector=sector,
                momentum=0,
                trend='UNKNOWN_SECTOR',
                recent_sentiment=0,
                prior_sentiment=0,
                days_analyzed=0
            )

        sector_df = df[df[ticker_col].str.upper().isin(tickers)].copy()

        if len(sector_df) == 0:
            return SectorMomentum(
                sector=sector,
                momentum=0,
                trend='NO_DATA',
                recent_sentiment=0,
                prior_sentiment=0,
                days_analyzed=0
            )

        # Aggregate by date
        daily = sector_df.groupby(date_col)[sentiment_col].mean().sort_index()

        if len(daily) < lookback:
            return SectorMomentum(
                sector=sector,
                momentum=0,
                trend='INSUFFICIENT_DATA',
                recent_sentiment=daily.iloc[-1] if len(daily) > 0 else 0,
                prior_sentiment=daily.iloc[0] if len(daily) > 0 else 0,
                days_analyzed=len(daily)
            )

        # Recent vs prior period comparison
        recent_days = min(3, lookback // 2)
        recent_mean = daily.tail(recent_days).mean()
        prior_mean = daily.tail(lookback).head(lookback - recent_days).mean()
        momentum = recent_mean - prior_mean

        # Classify trend
        if momentum > 0.5:
            trend = 'ACCELERATING'
        elif momentum < -0.5:
            trend = 'DECELERATING'
        else:
            trend = 'STABLE'

        return SectorMomentum(
            sector=sector,
            momentum=momentum,
            trend=trend,
            recent_sentiment=recent_mean,
            prior_sentiment=prior_mean,
            days_analyzed=len(daily)
        )

    def detect_sector_rotation(
        self,
        df: pd.DataFrame,
        lookback: int = 7
    ) -> List[Dict]:
        """
        Detect sector rotation patterns.

        Identifies which sectors are gaining/losing momentum relative to others.

        Args:
            df: DataFrame with news data
            lookback: Number of days to analyze

        Returns:
            List of sector momentum changes, sorted by momentum
        """
        results = []

        for sector in self.sectors:
            momentum = self.detect_sector_momentum(df, sector, lookback)
            if momentum.trend not in ['UNKNOWN_SECTOR', 'NO_DATA', 'INSUFFICIENT_DATA']:
                results.append({
                    'sector': sector,
                    'momentum': momentum.momentum,
                    'trend': momentum.trend,
                    'recent_sentiment': momentum.recent_sentiment,
                    'prior_sentiment': momentum.prior_sentiment
                })

        # Sort by momentum (highest first)
        results.sort(key=lambda x: x['momentum'], reverse=True)
        return results