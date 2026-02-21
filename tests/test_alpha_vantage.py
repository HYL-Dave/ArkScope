#!/usr/bin/env python3
"""
Alpha Vantage API Test Script

Tests:
1. API connection
2. News with sentiment
3. Stock quote
4. Daily prices (compact)
5. Company overview

Note: Free tier only allows 25 calls/day!
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
pytestmark = pytest.mark.skip("manual test script — run directly with python")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources.alpha_vantage_source import AlphaVantageDataSource


def load_env():
    """Load environment variables from config/.env"""
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Strip quotes from value
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value


def test_connection(client: AlphaVantageDataSource) -> bool:
    """Test 1: API connection"""
    print("\n" + "="*60)
    print("TEST 1: API Connection")
    print("="*60)

    try:
        result = client.test_connection()
        if result:
            print("✅ Connection successful")
            remaining = client.get_remaining_calls()
            print(f"   Remaining API calls today: {remaining['remaining']}/{remaining['daily_limit']}")
            return True
        else:
            print("❌ Connection failed")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_news_sentiment(client: AlphaVantageDataSource) -> bool:
    """Test 2: News with sentiment analysis"""
    print("\n" + "="*60)
    print("TEST 2: News with Sentiment Analysis")
    print("="*60)

    try:
        # Fetch recent news for a popular stock (using raw API for full details)
        articles = client.fetch_news_raw(
            tickers=['AAPL'],
            limit=10
        )

        if articles:
            print(f"✅ Retrieved {len(articles)} articles")
            print("\nSample articles:")
            for i, article in enumerate(articles[:3], 1):
                title = article['title'][:60] if article['title'] else 'N/A'
                print(f"\n  [{i}] {title}...")
                print(f"      Source: {article['source']}")
                print(f"      Published: {article['published']}")
                print(f"      Sentiment: {article['overall_sentiment_label']} ({article['overall_sentiment_score']})")

                # Show ticker-specific sentiment
                for ts in article['ticker_sentiments'][:2]:
                    print(f"      → {ts['ticker']}: {ts['sentiment_label']} (relevance: {ts['relevance_score']})")

            remaining = client.get_remaining_calls()
            print(f"\n   Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return True
        else:
            print("⚠️ No articles returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_quote(client: AlphaVantageDataSource) -> bool:
    """Test 3: Real-time stock quote"""
    print("\n" + "="*60)
    print("TEST 3: Stock Quote")
    print("="*60)

    try:
        quote = client.fetch_quote('MSFT')

        if quote and quote.get('ticker'):
            print(f"✅ Quote for {quote['ticker']}:")
            print(f"   Price: ${quote['price']:.2f}")
            print(f"   Change: {quote['change']:+.2f} ({quote['change_percent']})")
            print(f"   Volume: {quote['volume']:,}")
            print(f"   Trading Day: {quote['latest_trading_day']}")

            remaining = client.get_remaining_calls()
            print(f"\n   Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return True
        else:
            print("❌ No quote data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_daily_prices(client: AlphaVantageDataSource) -> bool:
    """Test 4: Daily historical prices"""
    print("\n" + "="*60)
    print("TEST 4: Daily Historical Prices (compact)")
    print("="*60)

    try:
        # Use BaseDataSource interface with date range
        end_date = date.today()
        start_date = end_date - timedelta(days=30)  # Last 30 days
        prices = client.fetch_prices(['NVDA'], start_date=start_date, end_date=end_date)

        if prices:
            print(f"✅ Retrieved {len(prices)} daily records")
            print(f"   Date range: {prices[0].date} to {prices[-1].date}")

            # Show recent prices
            print("\nRecent prices:")
            for p in prices[-5:]:
                print(f"   {p.date}: ${p.adj_close:.2f} (vol: {p.volume:,})")

            remaining = client.get_remaining_calls()
            print(f"\n   Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return True
        else:
            print("❌ No price data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_company_overview(client: AlphaVantageDataSource) -> bool:
    """Test 5: Company overview/fundamentals"""
    print("\n" + "="*60)
    print("TEST 5: Company Overview")
    print("="*60)

    try:
        overview = client.fetch_company_overview('GOOGL')

        if overview and overview.get('Symbol'):
            print(f"✅ Company: {overview.get('Name')}")
            print(f"   Sector: {overview.get('Sector')}")
            print(f"   Industry: {overview.get('Industry')}")
            print(f"   Market Cap: ${int(overview.get('MarketCapitalization', 0)):,}")
            print(f"   P/E Ratio: {overview.get('PERatio')}")
            print(f"   EPS: ${overview.get('EPS')}")
            print(f"   52-Week High: ${overview.get('52WeekHigh')}")
            print(f"   52-Week Low: ${overview.get('52WeekLow')}")
            print(f"   Dividend Yield: {overview.get('DividendYield')}")

            remaining = client.get_remaining_calls()
            print(f"\n   Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return True
        else:
            print("❌ No overview data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("Alpha Vantage API Test Suite")
    print("="*60)
    print("\n⚠️  WARNING: Free tier only allows 25 API calls/day!")
    print("    This test uses ~5 calls.\n")

    # Load environment
    load_env()

    api_key = os.getenv('ALPHA_VANTAGE_API_KEY', '')
    if not api_key:
        print("❌ ALPHA_VANTAGE_API_KEY not found in environment")
        print("   Please set it in config/.env")
        print("   Get a free key at: https://www.alphavantage.co/support/#api-key")
        return

    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")

    # Initialize client
    client = AlphaVantageDataSource(api_key)

    # Run tests
    results = {}

    results['connection'] = test_connection(client)

    if results['connection']:
        results['news_sentiment'] = test_news_sentiment(client)
        results['quote'] = test_quote(client)
        results['daily_prices'] = test_daily_prices(client)
        results['company_overview'] = test_company_overview(client)

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅" if passed_test else "❌"
        print(f"  {status} {test_name.replace('_', ' ').title()}")

    print(f"\nTotal: {passed}/{total} tests passed")

    # Show remaining calls
    remaining = client.get_remaining_calls()
    print(f"\n⚠️  API calls remaining today: {remaining['remaining']}/{remaining['daily_limit']}")
    print(f"   Resets on: {remaining['reset_date']}")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)