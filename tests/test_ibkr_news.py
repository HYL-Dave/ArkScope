#!/usr/bin/env python3
"""
Test IBKR news API - rate limits and historical depth.

Usage:
    python data_sources/test_ibkr_news.py [port]
    python data_sources/test_ibkr_news.py 4001  # IB Gateway Live
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load config/.env file
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), value)

from data_sources.ibkr_source import IBKRDataSource


def test_news_providers(ibkr: IBKRDataSource):
    """Test getting news providers."""
    print("\n" + "=" * 60)
    print("TEST 1: Available News Providers")
    print("=" * 60)

    providers = ibkr.get_news_providers()
    if providers:
        for p in providers:
            print(f"  - {p['code']}: {p['name']}")
        print(f"\nTotal: {len(providers)} providers")
        return '+'.join([p['code'] for p in providers])
    else:
        print("  No providers available!")
        return None


def test_single_ticker_news(ibkr: IBKRDataSource):
    """Test fetching news for a single ticker."""
    print("\n" + "=" * 60)
    print("TEST 2: Single Ticker News (AAPL, last 7 days)")
    print("=" * 60)

    articles = ibkr.fetch_news(['AAPL'], days_back=7, limit=50)
    print(f"Found {len(articles)} articles")

    if articles:
        print("\nSample headlines:")
        for a in articles[:5]:
            print(f"  [{a.published_date}] {a.source}: {a.title[:60]}...")

    return len(articles)


def test_historical_depth(ibkr: IBKRDataSource):
    """Test how far back we can get news."""
    print("\n" + "=" * 60)
    print("TEST 3: Historical Depth (AAPL)")
    print("=" * 60)

    test_ranges = [
        (7, "1 week"),
        (30, "1 month"),
        (90, "3 months"),
        (180, "6 months"),
        (365, "1 year"),
    ]

    results = []
    for days, label in test_ranges:
        start = date.today() - timedelta(days=days)
        end = date.today()
        print(f"\nTesting {label} ({start} to {end})...")

        try:
            articles = ibkr.fetch_news(
                ['AAPL'],
                start_date=start,
                end_date=end,
                limit=300  # max
            )
            count = len(articles)
            oldest = min([a.published_date for a in articles]) if articles else None
            print(f"  Found {count} articles")
            if oldest:
                print(f"  Oldest: {oldest}")
            results.append((label, count, oldest))
        except Exception as e:
            print(f"  Error: {e}")
            results.append((label, 0, None))

        time.sleep(1)  # Rate limit

    print("\n--- Summary ---")
    for label, count, oldest in results:
        oldest_str = str(oldest)[:10] if oldest else "N/A"
        print(f"  {label:12} : {count:3} articles (oldest: {oldest_str})")


def test_multiple_tickers(ibkr: IBKRDataSource):
    """Test fetching news for multiple tickers."""
    print("\n" + "=" * 60)
    print("TEST 4: Multiple Tickers (5 stocks, last 7 days)")
    print("=" * 60)

    tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
    start_time = time.time()

    articles = ibkr.fetch_news(tickers, days_back=7, limit=50)
    elapsed = time.time() - start_time

    print(f"\nTotal articles: {len(articles)}")
    print(f"Time elapsed: {elapsed:.1f}s")
    print(f"Rate: {len(tickers) / elapsed:.2f} tickers/sec")

    # Count by ticker
    by_ticker = {}
    for a in articles:
        by_ticker[a.ticker] = by_ticker.get(a.ticker, 0) + 1

    print("\nBy ticker:")
    for t in tickers:
        print(f"  {t}: {by_ticker.get(t, 0)} articles")


def test_article_body(ibkr: IBKRDataSource):
    """Test fetching article body."""
    print("\n" + "=" * 60)
    print("TEST 5: Fetch Article Body")
    print("=" * 60)

    # Get one article first
    articles = ibkr.fetch_news(['AAPL'], days_back=1, limit=5)

    if articles:
        article = articles[0]
        print(f"Fetching body for: {article.title[:50]}...")
        print(f"  Provider: {article.source}")

        # Extract article_id from description field (stored as "[Article ID: xxx]")
        import re
        match = re.search(r'\[Article ID: ([^\]]+)\]', article.description)
        if match:
            article_id = match.group(1)
            print(f"  Article ID: {article_id}")

            body = ibkr.fetch_news_article_body(article.source, article_id)
            if body:
                print(f"  Body length: {len(body)} chars")
                print(f"  Preview: {body[:200]}...")
            else:
                print("  No body returned (may require additional subscription)")
        else:
            print("  Could not extract article ID from description")
    else:
        print("  No articles to test")


def test_rate_limits(ibkr: IBKRDataSource):
    """Test rate limits by making rapid requests."""
    print("\n" + "=" * 60)
    print("TEST 6: Rate Limit Test (10 rapid requests)")
    print("=" * 60)

    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
               'META', 'TSLA', 'AMD', 'INTC', 'CRM']

    start_time = time.time()
    success = 0
    errors = []

    for i, ticker in enumerate(tickers):
        try:
            articles = ibkr.fetch_news([ticker], days_back=1, limit=10)
            success += 1
            print(f"  [{i+1}/10] {ticker}: {len(articles)} articles")
        except Exception as e:
            errors.append((ticker, str(e)))
            print(f"  [{i+1}/10] {ticker}: ERROR - {e}")

    elapsed = time.time() - start_time
    print(f"\nResults: {success}/10 successful in {elapsed:.1f}s")
    if errors:
        print("Errors:")
        for t, e in errors:
            print(f"  {t}: {e}")


def main():
    # Read from config/.env (loaded at module level), command line overrides
    default_port = int(os.environ.get('IBKR_PORT', '4001'))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else default_port
    host = os.environ.get('IBKR_HOST', '127.0.0.1')

    print(f"Connecting to IB Gateway at {host}:{port}...")

    ibkr = IBKRDataSource(
        host=host,
        port=port,
        client_id=99,
        timeout=30,
    )

    try:
        if not ibkr.connect():
            print("Connection failed!")
            return

        print("Connected!\n")

        # Run tests
        providers = test_news_providers(ibkr)
        if not providers:
            print("No providers - cannot continue tests")
            return

        test_single_ticker_news(ibkr)
        test_historical_depth(ibkr)
        test_multiple_tickers(ibkr)
        test_article_body(ibkr)
        test_rate_limits(ibkr)

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED")
        print("=" * 60)

    finally:
        ibkr.disconnect()
        print("\nDisconnected.")


if __name__ == '__main__':
    main()