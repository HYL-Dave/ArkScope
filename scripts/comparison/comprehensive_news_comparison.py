#!/usr/bin/env python3
"""
Comprehensive News Source Comparison

This script performs actual data collection from all available news APIs
to evaluate:
1. Historical depth (how far back can we get data?)
2. Content completeness (full article vs summary only)
3. Publisher diversity and quality
4. Sentiment availability
5. Rate limits and collection speed

Usage:
    python comprehensive_news_comparison.py --output comparison_results/
    python comprehensive_news_comparison.py --ticker AAPL --output comparison_results/
"""

import os
import sys
import json
import argparse
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_env_file(env_path: str = None) -> Dict[str, str]:
    """
    Load environment variables from .env file.

    Searches in order:
    1. Provided path
    2. config/.env
    3. .env
    """
    search_paths = []
    if env_path:
        search_paths.append(env_path)

    project_root = Path(__file__).parent
    search_paths.extend([
        project_root / "config" / ".env",
        project_root / ".env",
    ])

    loaded = {}
    for path in search_paths:
        if Path(path).exists():
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        # Only set if not already in environment and not a placeholder
                        if key not in os.environ and not value.startswith('your_'):
                            os.environ[key] = value
                            loaded[key] = value
            if loaded:
                logger.info(f"Loaded {len(loaded)} environment variables from {path}")
            break

    return loaded


@dataclass
class SourceTestResult:
    """Result of testing a single news source."""
    source_name: str
    ticker: str
    date_range: str

    # Availability
    is_available: bool
    error_message: str = ""

    # Quantity
    article_count: int = 0

    # Content Quality
    has_full_content: int = 0  # Articles with full content
    has_description: int = 0   # Articles with description/summary
    has_title_only: int = 0    # Articles with title only
    avg_content_length: float = 0
    avg_description_length: float = 0
    avg_title_length: float = 0

    # Sentiment
    has_sentiment: int = 0
    sentiment_type: str = ""  # "numeric", "label", "none"

    # Publishers
    unique_publishers: int = 0
    publishers_list: List[str] = None

    # Performance
    fetch_time_seconds: float = 0
    rate_limit_hit: bool = False

    # Sample articles for manual review
    sample_articles: List[Dict] = None

    def __post_init__(self):
        if self.publishers_list is None:
            self.publishers_list = []
        if self.sample_articles is None:
            self.sample_articles = []


def test_polygon(
    ticker: str,
    start_date: date,
    end_date: date,
) -> SourceTestResult:
    """Test Polygon news API."""
    result = SourceTestResult(
        source_name="Polygon",
        ticker=ticker,
        date_range=f"{start_date} to {end_date}",
        is_available=False,
    )

    try:
        from data_sources import PolygonDataSource

        api_key = os.environ.get('POLYGON_API_KEY')
        if not api_key:
            result.error_message = "POLYGON_API_KEY not set"
            return result

        source = PolygonDataSource(api_key=api_key)

        start_time = time.time()
        articles = source.fetch_news(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            limit=500,
        )
        result.fetch_time_seconds = time.time() - start_time

        result.is_available = True
        result.article_count = len(articles)

        if articles:
            publishers = set()
            for art in articles:
                publishers.add(art.source)

                # Content analysis
                content_len = len(art.content) if art.content else 0
                desc_len = len(art.description) if art.description else 0
                title_len = len(art.title) if art.title else 0

                if content_len > 100:
                    result.has_full_content += 1
                elif desc_len > 50:
                    result.has_description += 1
                else:
                    result.has_title_only += 1

                if art.sentiment_score is not None:
                    result.has_sentiment += 1

            result.unique_publishers = len(publishers)
            result.publishers_list = sorted(list(publishers))

            # Calculate averages
            result.avg_content_length = sum(len(a.content or '') for a in articles) / len(articles)
            result.avg_description_length = sum(len(a.description or '') for a in articles) / len(articles)
            result.avg_title_length = sum(len(a.title or '') for a in articles) / len(articles)

            if result.has_sentiment > 0:
                result.sentiment_type = "numeric (-1/0/1)"

            # Sample articles for review
            result.sample_articles = [
                {
                    'title': a.title[:100],
                    'description': (a.description or '')[:200],
                    'content_length': len(a.content or ''),
                    'source': a.source,
                    'date': a.published_date.isoformat() if a.published_date else '',
                    'sentiment': a.sentiment_score,
                }
                for a in articles[:5]
            ]

    except Exception as e:
        result.error_message = str(e)
        logger.error(f"Polygon test failed: {e}")

    return result


def test_finnhub(
    ticker: str,
    start_date: date,
    end_date: date,
) -> SourceTestResult:
    """Test Finnhub news API."""
    result = SourceTestResult(
        source_name="Finnhub",
        ticker=ticker,
        date_range=f"{start_date} to {end_date}",
        is_available=False,
    )

    try:
        from data_sources import FinnhubDataSource

        api_key = os.environ.get('FINNHUB_API_KEY')
        if not api_key:
            result.error_message = "FINNHUB_API_KEY not set"
            return result

        source = FinnhubDataSource(api_key=api_key)

        start_time = time.time()
        articles = source.fetch_news(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
        )
        result.fetch_time_seconds = time.time() - start_time

        result.is_available = True
        result.article_count = len(articles)

        if articles:
            publishers = set()
            for art in articles:
                publishers.add(art.source)

                content_len = len(art.content) if art.content else 0
                desc_len = len(art.description) if art.description else 0

                if content_len > 100:
                    result.has_full_content += 1
                elif desc_len > 50:
                    result.has_description += 1
                else:
                    result.has_title_only += 1

                if art.sentiment_score is not None:
                    result.has_sentiment += 1

            result.unique_publishers = len(publishers)
            result.publishers_list = sorted(list(publishers))

            result.avg_content_length = sum(len(a.content or '') for a in articles) / len(articles)
            result.avg_description_length = sum(len(a.description or '') for a in articles) / len(articles)
            result.avg_title_length = sum(len(a.title or '') for a in articles) / len(articles)

            result.sample_articles = [
                {
                    'title': a.title[:100],
                    'description': (a.description or '')[:200],
                    'content_length': len(a.content or ''),
                    'source': a.source,
                    'date': a.published_date.isoformat() if a.published_date else '',
                }
                for a in articles[:5]
            ]

    except Exception as e:
        result.error_message = str(e)
        logger.error(f"Finnhub test failed: {e}")

    return result


def test_tiingo(
    ticker: str,
    start_date: date,
    end_date: date,
) -> SourceTestResult:
    """Test Tiingo news API."""
    result = SourceTestResult(
        source_name="Tiingo",
        ticker=ticker,
        date_range=f"{start_date} to {end_date}",
        is_available=False,
    )

    try:
        from data_sources import TiingoDataSource

        api_key = os.environ.get('TIINGO_API_KEY')
        if not api_key:
            result.error_message = "TIINGO_API_KEY not set"
            return result

        source = TiingoDataSource(api_key=api_key)

        start_time = time.time()
        articles = source.fetch_news(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            limit=500,
        )
        result.fetch_time_seconds = time.time() - start_time

        result.is_available = True
        result.article_count = len(articles)

        if articles:
            publishers = set()
            for art in articles:
                publishers.add(art.source)

                content_len = len(art.content) if art.content else 0
                desc_len = len(art.description) if art.description else 0

                if content_len > 100:
                    result.has_full_content += 1
                elif desc_len > 50:
                    result.has_description += 1
                else:
                    result.has_title_only += 1

            result.unique_publishers = len(publishers)
            result.publishers_list = sorted(list(publishers))

            result.avg_content_length = sum(len(a.content or '') for a in articles) / len(articles)
            result.avg_description_length = sum(len(a.description or '') for a in articles) / len(articles)
            result.avg_title_length = sum(len(a.title or '') for a in articles) / len(articles)

            result.sample_articles = [
                {
                    'title': a.title[:100],
                    'description': (a.description or '')[:200],
                    'content_length': len(a.content or ''),
                    'source': a.source,
                    'date': a.published_date.isoformat() if a.published_date else '',
                }
                for a in articles[:5]
            ]

    except Exception as e:
        result.error_message = str(e)
        logger.error(f"Tiingo test failed: {e}")

    return result


def test_alpha_vantage(
    ticker: str,
    start_date: date,
    end_date: date,
) -> SourceTestResult:
    """Test Alpha Vantage news API (WARNING: very limited calls!)."""
    result = SourceTestResult(
        source_name="Alpha Vantage",
        ticker=ticker,
        date_range=f"{start_date} to {end_date}",
        is_available=False,
    )

    try:
        from data_sources import AlphaVantageDataSource

        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            result.error_message = "ALPHA_VANTAGE_API_KEY not set"
            return result

        source = AlphaVantageDataSource(api_key=api_key)

        # Check remaining calls
        remaining = source.get_remaining_calls()
        if remaining['remaining'] < 1:
            result.error_message = f"No API calls remaining today ({remaining})"
            result.rate_limit_hit = True
            return result

        start_time = time.time()
        articles = source.fetch_news(
            tickers=[ticker],
            start_date=start_date,
            end_date=end_date,
            limit=50,  # Conservative limit
        )
        result.fetch_time_seconds = time.time() - start_time

        result.is_available = True
        result.article_count = len(articles)

        if articles:
            publishers = set()
            for art in articles:
                publishers.add(art.source)

                content_len = len(art.content) if art.content else 0
                desc_len = len(art.description) if art.description else 0

                if content_len > 100:
                    result.has_full_content += 1
                elif desc_len > 50:
                    result.has_description += 1
                else:
                    result.has_title_only += 1

                if art.sentiment_score is not None:
                    result.has_sentiment += 1

            result.unique_publishers = len(publishers)
            result.publishers_list = sorted(list(publishers))

            result.avg_content_length = sum(len(a.content or '') for a in articles) / len(articles)
            result.avg_description_length = sum(len(a.description or '') for a in articles) / len(articles)
            result.avg_title_length = sum(len(a.title or '') for a in articles) / len(articles)

            if result.has_sentiment > 0:
                result.sentiment_type = "numeric (detailed per-ticker)"

            result.sample_articles = [
                {
                    'title': a.title[:100],
                    'description': (a.description or '')[:200],
                    'content_length': len(a.content or ''),
                    'source': a.source,
                    'date': a.published_date.isoformat() if a.published_date else '',
                    'sentiment': a.sentiment_score,
                }
                for a in articles[:5]
            ]

    except Exception as e:
        result.error_message = str(e)
        if "Rate limit" in str(e) or "daily" in str(e).lower():
            result.rate_limit_hit = True
        logger.error(f"Alpha Vantage test failed: {e}")

    return result


def run_comprehensive_test(
    tickers: List[str],
    output_dir: str,
    skip_alpha_vantage: bool = False,
) -> Dict[str, Any]:
    """
    Run comprehensive test across all news sources.

    Tests multiple date ranges:
    - Recent (last 7 days)
    - 1 month ago
    - 6 months ago
    - 1 year ago
    - 2 years ago
    - 3 years ago
    """
    os.makedirs(output_dir, exist_ok=True)

    today = date.today()

    # Date ranges to test
    date_ranges = [
        ("recent_7d", today - timedelta(days=7), today),
        ("1_month_ago", date(2024, 11, 1), date(2024, 11, 30)),
        ("6_months_ago", date(2024, 6, 1), date(2024, 6, 30)),
        ("1_year_ago", date(2023, 12, 1), date(2023, 12, 31)),
        ("2_years_ago", date(2022, 12, 1), date(2022, 12, 31)),
        ("3_years_ago", date(2021, 12, 1), date(2021, 12, 31)),
    ]

    # Test functions for each source
    test_functions = [
        ("Polygon", test_polygon),
        ("Finnhub", test_finnhub),
        ("Tiingo", test_tiingo),
    ]

    if not skip_alpha_vantage:
        test_functions.append(("Alpha Vantage", test_alpha_vantage))

    all_results = {
        "generated_at": datetime.now().isoformat(),
        "tickers_tested": tickers,
        "date_ranges_tested": [
            {"name": name, "start": str(start), "end": str(end)}
            for name, start, end in date_ranges
        ],
        "results_by_source": {},
        "summary": {},
    }

    for source_name, test_func in test_functions:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing {source_name}")
        logger.info('='*60)

        source_results = []

        for ticker in tickers:
            for range_name, start_date, end_date in date_ranges:
                logger.info(f"  {ticker} / {range_name}: {start_date} to {end_date}")

                result = test_func(ticker, start_date, end_date)

                # Convert dataclass to dict for JSON serialization
                result_dict = asdict(result)
                result_dict['range_name'] = range_name
                source_results.append(result_dict)

                logger.info(f"    -> {result.article_count} articles, {result.has_sentiment} with sentiment")

                if result.error_message:
                    logger.warning(f"    -> Error: {result.error_message}")

                # Small delay between requests
                time.sleep(0.5)

        all_results["results_by_source"][source_name] = source_results

    # Generate summary
    summary = generate_summary(all_results)
    all_results["summary"] = summary

    # Save results
    output_path = os.path.join(output_dir, "comprehensive_news_comparison.json")
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info(f"\nResults saved to: {output_path}")

    # Print summary
    print_summary(summary)

    return all_results


def generate_summary(results: Dict) -> Dict:
    """Generate summary statistics from test results."""
    summary = {
        "historical_depth": {},
        "content_quality": {},
        "sentiment_support": {},
        "publisher_diversity": {},
        "rate_limits": {},
    }

    for source_name, source_results in results["results_by_source"].items():
        # Find oldest date range with data
        oldest_with_data = None
        total_articles = 0
        total_with_sentiment = 0
        all_publishers = set()
        total_content_length = 0
        articles_with_content = 0

        for r in source_results:
            if r.get('article_count', 0) > 0:
                oldest_with_data = r.get('range_name')
                total_articles += r['article_count']
                total_with_sentiment += r.get('has_sentiment', 0)
                all_publishers.update(r.get('publishers_list', []))
                total_content_length += r.get('avg_content_length', 0) * r['article_count']
                articles_with_content += r.get('has_full_content', 0)

        summary["historical_depth"][source_name] = oldest_with_data or "none"
        summary["content_quality"][source_name] = {
            "total_articles": total_articles,
            "with_full_content": articles_with_content,
            "avg_content_length": total_content_length / total_articles if total_articles > 0 else 0,
        }
        summary["sentiment_support"][source_name] = {
            "articles_with_sentiment": total_with_sentiment,
            "percentage": (total_with_sentiment / total_articles * 100) if total_articles > 0 else 0,
        }
        summary["publisher_diversity"][source_name] = {
            "unique_publishers": len(all_publishers),
            "publishers": sorted(list(all_publishers)),
        }

        # Check for rate limit issues
        rate_limited = any(r.get('rate_limit_hit', False) for r in source_results)
        summary["rate_limits"][source_name] = {
            "hit_rate_limit": rate_limited,
        }

    return summary


def print_summary(summary: Dict):
    """Print formatted summary."""
    print("\n" + "="*70)
    print("COMPREHENSIVE NEWS SOURCE COMPARISON SUMMARY")
    print("="*70)

    print("\n📅 HISTORICAL DEPTH (oldest data available):")
    for source, depth in summary["historical_depth"].items():
        print(f"  {source:20s}: {depth}")

    print("\n📊 CONTENT QUALITY:")
    for source, quality in summary["content_quality"].items():
        print(f"  {source:20s}: {quality['total_articles']} articles, "
              f"{quality['with_full_content']} with full content, "
              f"avg {quality['avg_content_length']:.0f} chars")

    print("\n💭 SENTIMENT SUPPORT:")
    for source, sentiment in summary["sentiment_support"].items():
        print(f"  {source:20s}: {sentiment['articles_with_sentiment']} articles "
              f"({sentiment['percentage']:.1f}%)")

    print("\n📰 PUBLISHER DIVERSITY:")
    for source, diversity in summary["publisher_diversity"].items():
        print(f"  {source:20s}: {diversity['unique_publishers']} publishers")
        for pub in diversity['publishers'][:5]:
            print(f"    - {pub}")
        if len(diversity['publishers']) > 5:
            print(f"    ... and {len(diversity['publishers']) - 5} more")

    print("\n⚠️  RATE LIMITS:")
    for source, limits in summary["rate_limits"].items():
        status = "⛔ HIT" if limits['hit_rate_limit'] else "✅ OK"
        print(f"  {source:20s}: {status}")

    print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive news source comparison"
    )
    parser.add_argument(
        '--tickers', type=str, default='AAPL,MSFT,NVDA',
        help='Comma-separated tickers to test (default: AAPL,MSFT,NVDA)'
    )
    parser.add_argument(
        '--output', type=str, default='comparison_results',
        help='Output directory (default: comparison_results)'
    )
    parser.add_argument(
        '--skip-alpha-vantage', action='store_true',
        help='Skip Alpha Vantage (has very limited API calls)'
    )
    parser.add_argument(
        '--env-file', type=str, default=None,
        help='Path to .env file (default: auto-detect config/.env or .env)'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load environment variables from .env file
    loaded_vars = load_env_file(args.env_file)
    if loaded_vars:
        logger.info(f"Loaded API keys: {', '.join(k for k in loaded_vars.keys() if 'KEY' in k)}")

    tickers = [t.strip().upper() for t in args.tickers.split(',')]

    logger.info(f"Testing tickers: {tickers}")
    logger.info(f"Output directory: {args.output}")

    run_comprehensive_test(
        tickers=tickers,
        output_dir=args.output,
        skip_alpha_vantage=args.skip_alpha_vantage,
    )


if __name__ == '__main__':
    main()