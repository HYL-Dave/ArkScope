#!/usr/bin/env python3
"""
Compare news sources: Polygon vs Finnhub.

This script performs comprehensive comparison between Polygon and Finnhub
for news data quality, quantity, and coverage to inform paid subscription decisions.

Comparison dimensions:
1. News quantity per ticker
2. Historical depth (how far back can we fetch?)
3. Content completeness (title, summary, full content)
4. Built-in sentiment availability
5. Source diversity (unique publishers)
6. API rate limits and collection speed

Usage:
    python compare_news_sources.py --tickers AAPL,MSFT,NVDA --output comparison_report.json
    python compare_news_sources.py --full-test  # Run comprehensive 3-year comparison
"""

import os
import sys
import json
import argparse
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
import hashlib

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables from config/.env
try:
    from dotenv import load_dotenv
    # Try multiple possible .env locations
    env_paths = [
        os.path.join(PROJECT_ROOT, 'config', '.env'),
        os.path.join(PROJECT_ROOT, '.env'),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment from: {env_path}")
            break
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
    print("Falling back to system environment variables.")

from data_sources import FinnhubDataSource, PolygonDataSource

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SourceStats:
    """Statistics for a single news source."""
    source_name: str
    ticker: str
    date_range: str
    article_count: int
    unique_publishers: int
    publishers_list: List[str]
    has_sentiment: int
    has_description: int
    has_full_content: int
    avg_title_length: float
    avg_description_length: float
    oldest_article_date: Optional[str]
    newest_article_date: Optional[str]
    fetch_time_seconds: float
    api_calls_made: int


@dataclass
class ComparisonReport:
    """Comparison report between Polygon and Finnhub."""
    generated_at: str
    tickers_tested: List[str]
    date_ranges_tested: List[Dict[str, str]]
    polygon_stats: List[SourceStats]
    finnhub_stats: List[SourceStats]
    summary: Dict[str, Any]
    recommendations: List[str]


def hash_title(title: str) -> str:
    """Create hash of title for deduplication comparison."""
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:12]


def compare_for_ticker_and_range(
    ticker: str,
    start_date: date,
    end_date: date,
    polygon: Optional[PolygonDataSource] = None,
    finnhub: Optional[FinnhubDataSource] = None,
) -> Dict[str, SourceStats]:
    """
    Compare news from both sources for a specific ticker and date range.

    Returns:
        Dictionary with 'polygon' and 'finnhub' keys containing SourceStats.
    """
    results = {}
    date_range_str = f"{start_date.isoformat()} to {end_date.isoformat()}"

    # Test Polygon
    if polygon:
        import time
        start_time = time.time()

        try:
            articles = polygon.fetch_news(
                tickers=[ticker],
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            fetch_time = time.time() - start_time

            publishers = set()
            has_sentiment = 0
            has_description = 0
            has_content = 0
            title_lengths = []
            desc_lengths = []
            oldest_date = None
            newest_date = None

            for article in articles:
                if article.source:
                    publishers.add(article.source)
                if article.sentiment_score is not None:
                    has_sentiment += 1
                if article.description and len(article.description) > 10:
                    has_description += 1
                    desc_lengths.append(len(article.description))
                if article.content and len(article.content) > 50:
                    has_content += 1
                if article.title:
                    title_lengths.append(len(article.title))

                pub_date = article.published_date.date() if hasattr(article.published_date, 'date') else article.published_date
                if oldest_date is None or pub_date < oldest_date:
                    oldest_date = pub_date
                if newest_date is None or pub_date > newest_date:
                    newest_date = pub_date

            results['polygon'] = SourceStats(
                source_name='Polygon',
                ticker=ticker,
                date_range=date_range_str,
                article_count=len(articles),
                unique_publishers=len(publishers),
                publishers_list=sorted(list(publishers)),
                has_sentiment=has_sentiment,
                has_description=has_description,
                has_full_content=has_content,
                avg_title_length=sum(title_lengths) / len(title_lengths) if title_lengths else 0,
                avg_description_length=sum(desc_lengths) / len(desc_lengths) if desc_lengths else 0,
                oldest_article_date=oldest_date.isoformat() if oldest_date else None,
                newest_article_date=newest_date.isoformat() if newest_date else None,
                fetch_time_seconds=fetch_time,
                api_calls_made=polygon._request_count if hasattr(polygon, '_request_count') else 1,
            )
            logger.info(f"Polygon: {len(articles)} articles for {ticker} ({date_range_str})")

        except Exception as e:
            logger.error(f"Polygon fetch failed for {ticker}: {e}")
            results['polygon'] = SourceStats(
                source_name='Polygon',
                ticker=ticker,
                date_range=date_range_str,
                article_count=0,
                unique_publishers=0,
                publishers_list=[],
                has_sentiment=0,
                has_description=0,
                has_full_content=0,
                avg_title_length=0,
                avg_description_length=0,
                oldest_article_date=None,
                newest_article_date=None,
                fetch_time_seconds=0,
                api_calls_made=0,
            )

    # Test Finnhub
    if finnhub:
        import time
        start_time = time.time()

        try:
            articles = finnhub.fetch_news(
                tickers=[ticker],
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            fetch_time = time.time() - start_time

            publishers = set()
            has_sentiment = 0
            has_description = 0
            has_content = 0
            title_lengths = []
            desc_lengths = []
            oldest_date = None
            newest_date = None

            for article in articles:
                if article.source:
                    publishers.add(article.source)
                # Finnhub doesn't have built-in sentiment
                if article.description and len(article.description) > 10:
                    has_description += 1
                    desc_lengths.append(len(article.description))
                if article.content and len(article.content) > 50:
                    has_content += 1
                if article.title:
                    title_lengths.append(len(article.title))

                pub_date = article.published_date.date() if hasattr(article.published_date, 'date') else article.published_date
                if oldest_date is None or pub_date < oldest_date:
                    oldest_date = pub_date
                if newest_date is None or pub_date > newest_date:
                    newest_date = pub_date

            results['finnhub'] = SourceStats(
                source_name='Finnhub',
                ticker=ticker,
                date_range=date_range_str,
                article_count=len(articles),
                unique_publishers=len(publishers),
                publishers_list=sorted(list(publishers)),
                has_sentiment=0,  # Finnhub doesn't provide sentiment
                has_description=has_description,
                has_full_content=has_content,
                avg_title_length=sum(title_lengths) / len(title_lengths) if title_lengths else 0,
                avg_description_length=sum(desc_lengths) / len(desc_lengths) if desc_lengths else 0,
                oldest_article_date=oldest_date.isoformat() if oldest_date else None,
                newest_article_date=newest_date.isoformat() if newest_date else None,
                fetch_time_seconds=fetch_time,
                api_calls_made=finnhub._request_count if hasattr(finnhub, '_request_count') else 1,
            )
            logger.info(f"Finnhub: {len(articles)} articles for {ticker} ({date_range_str})")

        except Exception as e:
            logger.error(f"Finnhub fetch failed for {ticker}: {e}")
            results['finnhub'] = SourceStats(
                source_name='Finnhub',
                ticker=ticker,
                date_range=date_range_str,
                article_count=0,
                unique_publishers=0,
                publishers_list=[],
                has_sentiment=0,
                has_description=0,
                has_full_content=0,
                avg_title_length=0,
                avg_description_length=0,
                oldest_article_date=None,
                newest_article_date=None,
                fetch_time_seconds=0,
                api_calls_made=0,
            )

    return results


def generate_summary(
    polygon_stats: List[SourceStats],
    finnhub_stats: List[SourceStats],
) -> Dict[str, Any]:
    """Generate summary statistics from comparison results."""

    def sum_stat(stats: List[SourceStats], field: str) -> int:
        return sum(getattr(s, field, 0) for s in stats)

    def avg_stat(stats: List[SourceStats], field: str) -> float:
        vals = [getattr(s, field, 0) for s in stats if getattr(s, field, 0) > 0]
        return sum(vals) / len(vals) if vals else 0

    polygon_total = sum_stat(polygon_stats, 'article_count')
    finnhub_total = sum_stat(finnhub_stats, 'article_count')

    # Collect all unique publishers
    polygon_publishers = set()
    finnhub_publishers = set()
    for s in polygon_stats:
        polygon_publishers.update(s.publishers_list)
    for s in finnhub_stats:
        finnhub_publishers.update(s.publishers_list)

    return {
        'total_articles': {
            'polygon': polygon_total,
            'finnhub': finnhub_total,
            'winner': 'polygon' if polygon_total > finnhub_total else 'finnhub',
            'ratio': round(finnhub_total / polygon_total, 2) if polygon_total > 0 else float('inf'),
        },
        'sentiment_availability': {
            'polygon': sum_stat(polygon_stats, 'has_sentiment'),
            'finnhub': 0,  # Finnhub doesn't have built-in sentiment
            'winner': 'polygon',
        },
        'content_completeness': {
            'polygon_with_description': sum_stat(polygon_stats, 'has_description'),
            'finnhub_with_description': sum_stat(finnhub_stats, 'has_description'),
            'polygon_avg_desc_length': round(avg_stat(polygon_stats, 'avg_description_length'), 1),
            'finnhub_avg_desc_length': round(avg_stat(finnhub_stats, 'avg_description_length'), 1),
        },
        'source_diversity': {
            'polygon_unique_publishers': len(polygon_publishers),
            'finnhub_unique_publishers': len(finnhub_publishers),
            'polygon_publishers': sorted(list(polygon_publishers))[:20],  # Top 20
            'finnhub_publishers': sorted(list(finnhub_publishers))[:20],
        },
        'fetch_performance': {
            'polygon_total_time': round(sum(s.fetch_time_seconds for s in polygon_stats), 1),
            'finnhub_total_time': round(sum(s.fetch_time_seconds for s in finnhub_stats), 1),
            'polygon_rate_limit': '5 calls/min (free)',
            'finnhub_rate_limit': '60 calls/min (free)',
        },
    }


def generate_recommendations(summary: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on comparison results."""
    recommendations = []

    total = summary['total_articles']
    if total['finnhub'] > total['polygon'] * 2:
        recommendations.append(
            f"Finnhub provides {total['ratio']}x more articles than Polygon. "
            "Consider Finnhub for quantity-focused collection."
        )
    elif total['polygon'] > total['finnhub'] * 2:
        recommendations.append(
            "Polygon provides significantly more articles. "
            "Consider Polygon for broader coverage."
        )
    else:
        recommendations.append(
            "Article counts are comparable between sources. "
            "Decision should be based on other factors."
        )

    # Sentiment recommendation
    if summary['sentiment_availability']['polygon'] > 0:
        recommendations.append(
            "Polygon provides built-in sentiment scores (-1/0/1), "
            "which can reduce LLM scoring costs. Consider if sentiment quality is sufficient."
        )

    # Rate limit recommendation
    recommendations.append(
        "Finnhub has 12x faster rate limit (60/min vs 5/min). "
        "For large-scale collection, Finnhub is more efficient."
    )

    # Historical depth (based on oldest article found)
    recommendations.append(
        "Test historical depth by checking 3-year-old data availability. "
        "This is critical for training data requirements."
    )

    return recommendations


def run_comparison(
    tickers: List[str],
    date_ranges: List[tuple],
    output_path: str,
    polygon_key: Optional[str] = None,
    finnhub_key: Optional[str] = None,
) -> ComparisonReport:
    """
    Run full comparison between Polygon and Finnhub.

    Args:
        tickers: List of stock symbols to test.
        date_ranges: List of (start_date, end_date) tuples.
        output_path: Path to save JSON report.
        polygon_key: Polygon API key (optional, uses env var if not provided).
        finnhub_key: Finnhub API key (optional, uses env var if not provided).

    Returns:
        ComparisonReport with all results.
    """
    # Initialize data sources
    polygon = None
    finnhub = None

    try:
        polygon = PolygonDataSource(api_key=polygon_key)
        if polygon.validate_credentials():
            logger.info("Polygon credentials validated")
        else:
            logger.warning("Polygon credentials invalid or not set")
            polygon = None
    except Exception as e:
        logger.warning(f"Failed to initialize Polygon: {e}")

    try:
        finnhub = FinnhubDataSource(api_key=finnhub_key)
        if finnhub.validate_credentials():
            logger.info("Finnhub credentials validated")
        else:
            logger.warning("Finnhub credentials invalid or not set")
            finnhub = None
    except Exception as e:
        logger.warning(f"Failed to initialize Finnhub: {e}")

    if not polygon and not finnhub:
        logger.error("No valid data sources available. Check API keys.")
        sys.exit(1)

    polygon_stats = []
    finnhub_stats = []

    for ticker in tickers:
        for start_date, end_date in date_ranges:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing {ticker}: {start_date} to {end_date}")
            logger.info('='*60)

            results = compare_for_ticker_and_range(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                polygon=polygon,
                finnhub=finnhub,
            )

            if 'polygon' in results:
                polygon_stats.append(results['polygon'])
            if 'finnhub' in results:
                finnhub_stats.append(results['finnhub'])

    # Generate summary and recommendations
    summary = generate_summary(polygon_stats, finnhub_stats)
    recommendations = generate_recommendations(summary)

    # Create report
    report = ComparisonReport(
        generated_at=datetime.now().isoformat(),
        tickers_tested=tickers,
        date_ranges_tested=[
            {'start': s.isoformat(), 'end': e.isoformat()}
            for s, e in date_ranges
        ],
        polygon_stats=polygon_stats,
        finnhub_stats=finnhub_stats,
        summary=summary,
        recommendations=recommendations,
    )

    # Save report
    report_dict = {
        'generated_at': report.generated_at,
        'tickers_tested': report.tickers_tested,
        'date_ranges_tested': report.date_ranges_tested,
        'polygon_stats': [asdict(s) for s in report.polygon_stats],
        'finnhub_stats': [asdict(s) for s in report.finnhub_stats],
        'summary': report.summary,
        'recommendations': report.recommendations,
    }

    with open(output_path, 'w') as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"\nReport saved to: {output_path}")

    # Print summary
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    print(f"\nTotal Articles:")
    print(f"  Polygon: {summary['total_articles']['polygon']}")
    print(f"  Finnhub: {summary['total_articles']['finnhub']}")
    print(f"  Winner: {summary['total_articles']['winner'].upper()}")

    print(f"\nSentiment Availability:")
    print(f"  Polygon: {summary['sentiment_availability']['polygon']} articles with sentiment")
    print(f"  Finnhub: No built-in sentiment")

    print(f"\nSource Diversity:")
    print(f"  Polygon: {summary['source_diversity']['polygon_unique_publishers']} unique publishers")
    print(f"  Finnhub: {summary['source_diversity']['finnhub_unique_publishers']} unique publishers")

    print(f"\nFetch Performance:")
    print(f"  Polygon: {summary['fetch_performance']['polygon_total_time']}s total")
    print(f"  Finnhub: {summary['fetch_performance']['finnhub_total_time']}s total")

    print("\n" + "-"*60)
    print("RECOMMENDATIONS:")
    print("-"*60)
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. {rec}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Compare news sources: Polygon vs Finnhub"
    )
    parser.add_argument(
        '--tickers', type=str, default='AAPL,MSFT,NVDA,TSLA,GOOGL',
        help='Comma-separated list of tickers to test (default: AAPL,MSFT,NVDA,TSLA,GOOGL)'
    )
    parser.add_argument(
        '--output', type=str, default='news_source_comparison.json',
        help='Output path for comparison report (default: news_source_comparison.json)'
    )
    parser.add_argument(
        '--days-back', type=int, default=7,
        help='Days to look back for recent news test (default: 7)'
    )
    parser.add_argument(
        '--full-test', action='store_true',
        help='Run comprehensive 3-year historical test'
    )
    parser.add_argument(
        '--polygon-key', type=str, default=None,
        help='Polygon API key (default: uses POLYGON_API_KEY env var)'
    )
    parser.add_argument(
        '--finnhub-key', type=str, default=None,
        help='Finnhub API key (default: uses FINNHUB_API_KEY env var)'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    tickers = [t.strip().upper() for t in args.tickers.split(',')]

    # Define date ranges to test
    today = date.today()

    if args.full_test:
        # Comprehensive test: recent, 1 year ago, 2 years ago, 3 years ago
        date_ranges = [
            (today - timedelta(days=args.days_back), today),  # Recent
            (date(2024, 1, 1), date(2024, 1, 31)),  # 1 year ago
            (date(2023, 1, 1), date(2023, 1, 31)),  # 2 years ago
            (date(2022, 1, 1), date(2022, 1, 31)),  # 3 years ago
        ]
        logger.info("Running FULL 3-year historical comparison test")
    else:
        # Quick test: just recent news
        date_ranges = [
            (today - timedelta(days=args.days_back), today),
        ]
        logger.info(f"Running quick {args.days_back}-day comparison test")

    report = run_comparison(
        tickers=tickers,
        date_ranges=date_ranges,
        output_path=args.output,
        polygon_key=args.polygon_key,
        finnhub_key=args.finnhub_key,
    )

    print(f"\nComparison complete! Report saved to: {args.output}")


if __name__ == '__main__':
    main()