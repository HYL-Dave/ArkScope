#!/usr/bin/env python3
"""
EODHD API Test Script

Tests:
1. API connection
2. Real-time quote
3. EOD prices (1 API call)
4. News with sentiment (5 API calls!)
5. Fundamentals (optional)

CRITICAL: Free tier only allows 20 calls/day!
         News costs 5 calls each = only 4 news queries/day!
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
pytestmark = pytest.mark.skip("manual test script — run directly with python")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


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
        print(f"[OK] Loaded .env from {env_path}")


def test_connection(client) -> bool:
    """Test 1: API connection"""
    print("\n" + "=" * 60)
    print("TEST 1: API Connection")
    print("=" * 60)

    try:
        result = client.test_connection()
        if result:
            print("[PASS] Connection successful")
            remaining = client.get_remaining_calls()
            print(f"       Remaining API calls today: {remaining['remaining']}/{remaining['daily_limit']}")
            print(f"       Note: {remaining['note']}")
            return True
        else:
            print("[FAIL] Connection failed")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False


def test_quote(client) -> dict:
    """Test 2: Real-time quote"""
    print("\n" + "=" * 60)
    print("TEST 2: Real-time Quote (1 API call)")
    print("=" * 60)

    try:
        quote = client.fetch_quote('AAPL')

        if quote and quote.get('close'):
            print(f"[PASS] Quote for {quote.get('code', 'AAPL')}:")
            print(f"       Price: ${quote.get('close', 0):.2f}")
            print(f"       Change: {quote.get('change', 0):+.2f} ({quote.get('change_percent', 0):.2f}%)")
            print(f"       Volume: {quote.get('volume', 0):,}")
            print(f"       Open: ${quote.get('open', 0):.2f}")
            print(f"       High: ${quote.get('high', 0):.2f}")
            print(f"       Low: ${quote.get('low', 0):.2f}")

            remaining = client.get_remaining_calls()
            print(f"\n       Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return quote
        else:
            print("[FAIL] No quote data returned")
            return {}
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return {}


def test_eod_prices(client) -> list:
    """Test 3: EOD prices"""
    print("\n" + "=" * 60)
    print("TEST 3: EOD Historical Prices (1 API call)")
    print("=" * 60)

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        prices = client.fetch_prices(['AAPL'], start_date=start_date, end_date=end_date)

        if prices:
            print(f"[PASS] Retrieved {len(prices)} daily records")
            print(f"       Date range: {prices[0].date} to {prices[-1].date}")

            print("\n       Recent prices:")
            for p in prices[-5:]:
                print(f"       {p.date}: O=${p.open:.2f} H=${p.high:.2f} L=${p.low:.2f} C=${p.close:.2f}")

            remaining = client.get_remaining_calls()
            print(f"\n       Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return [p.to_dict() for p in prices[-10:]]
        else:
            print("[FAIL] No price data returned")
            return []
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return []


def test_news(client) -> list:
    """Test 4: News with sentiment"""
    print("\n" + "=" * 60)
    print("TEST 4: News with Sentiment (5 API calls!)")
    print("=" * 60)

    remaining = client.get_remaining_calls()
    if remaining['remaining'] < 5:
        print(f"[SKIP] Not enough API calls remaining ({remaining['remaining']} < 5)")
        print("       News requests cost 5 API calls each!")
        return []

    try:
        # Fetch recent news
        articles = client.fetch_news_raw(
            tickers=['AAPL'],
            limit=10
        )

        if articles:
            print(f"[PASS] Retrieved {len(articles)} articles")
            print("\n       Sample articles:")

            result_articles = []
            for i, article in enumerate(articles[:5], 1):
                title = article.get('title', 'N/A')[:55]
                print(f"\n       [{i}] {title}...")
                print(f"           Source: {article.get('source', 'N/A')}")
                print(f"           Date: {article.get('date', 'N/A')}")

                # Show sentiment if available
                sentiment = article.get('sentiment', {})
                if sentiment:
                    print(f"           Sentiment: polarity={sentiment.get('polarity', 'N/A')}")
                    print(f"                      pos={sentiment.get('pos', 'N/A')}, "
                          f"neg={sentiment.get('neg', 'N/A')}, "
                          f"neu={sentiment.get('neu', 'N/A')}")

                result_articles.append({
                    'title': article.get('title'),
                    'source': article.get('source'),
                    'date': article.get('date'),
                    'link': article.get('link'),
                    'sentiment': sentiment,
                    'symbols': article.get('symbols', []),
                    'content_preview': article.get('content', '')[:200] if article.get('content') else ''
                })

            remaining = client.get_remaining_calls()
            print(f"\n       Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")
            return result_articles
        else:
            print("[WARN] No articles returned")
            return []
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return []


def test_fundamentals(client) -> dict:
    """Test 5: Company fundamentals"""
    print("\n" + "=" * 60)
    print("TEST 5: Company Fundamentals (1 API call)")
    print("=" * 60)

    remaining = client.get_remaining_calls()
    if remaining['remaining'] < 1:
        print(f"[SKIP] No API calls remaining")
        return {}

    try:
        fundamentals = client.fetch_fundamentals('AAPL')

        if fundamentals and fundamentals.get('General'):
            general = fundamentals.get('General', {})
            highlights = fundamentals.get('Highlights', {})

            print(f"[PASS] Fundamentals for {general.get('Name', 'N/A')}:")
            print(f"       Sector: {general.get('Sector', 'N/A')}")
            print(f"       Industry: {general.get('Industry', 'N/A')}")
            print(f"       Exchange: {general.get('Exchange', 'N/A')}")
            print(f"       Market Cap: ${highlights.get('MarketCapitalization', 0):,.0f}")
            print(f"       P/E Ratio: {highlights.get('PERatio', 'N/A')}")
            print(f"       EPS: ${highlights.get('EarningsShare', 'N/A')}")
            print(f"       Dividend Yield: {highlights.get('DividendYield', 'N/A')}")

            remaining = client.get_remaining_calls()
            print(f"\n       Remaining API calls: {remaining['remaining']}/{remaining['daily_limit']}")

            return {
                'name': general.get('Name'),
                'sector': general.get('Sector'),
                'industry': general.get('Industry'),
                'exchange': general.get('Exchange'),
                'market_cap': highlights.get('MarketCapitalization'),
                'pe_ratio': highlights.get('PERatio'),
                'eps': highlights.get('EarningsShare'),
                'dividend_yield': highlights.get('DividendYield'),
                '52_week_high': highlights.get('52WeekHigh'),
                '52_week_low': highlights.get('52WeekLow')
            }
        else:
            print("[WARN] Limited fundamentals data (may require paid tier)")
            return {}
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return {}


def save_comparison_data(data: dict, output_dir: Path):
    """Save test results for comparison."""
    output_file = output_dir / 'aapl_eodhd.json'
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"\n[OK] Saved comparison data to {output_file}")


def main():
    """Run all tests."""
    from datetime import datetime

    print("=" * 60)
    print("EODHD API Test Suite")
    print("=" * 60)
    print("\nWARNING: Free tier only allows 20 API calls/day!")
    print("         News requests cost 5 calls each!")
    print("         This test uses ~8 calls (or 3 without news).\n")

    # Load environment
    load_env()

    api_key = os.getenv('EODHD_API_KEY', '').strip()
    if not api_key or api_key == 'your_eodhd_api_key_here':
        print("[FAIL] EODHD_API_KEY not found or not configured")
        print("       Please set it in config/.env")
        print("       Get a free key at: https://eodhd.com/register")
        return

    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")

    # Initialize client
    from data_sources.eodhd_source import EODHDDataSource
    client = EODHDDataSource(api_key)

    # Collect results for comparison
    results = {
        'source': 'eodhd',
        'ticker': 'AAPL',
        'collected_at': datetime.now().isoformat(),
        'free_tier_limits': {
            'api_calls': '20 calls/DAY total',
            'news_cost': '5 calls per news request!',
            'max_news_queries': '4 per day on free tier',
            'rate_limit': 'No documented per-minute limit',
            'price_history': '1 year (free), 1972+ (paid)',
            'coverage': '150,000+ tickers, 60+ exchanges'
        },
        'limitations': [
            'Only 20 API calls per DAY',
            'Each news request costs 5 API calls!',
            'Free tier: 1 year EOD history only',
            'Fundamentals may require paid tier',
            'Intraday data requires $29.99/month tier'
        ],
        'data': {},
        'test_results': {}
    }

    # Run tests
    results['test_results']['connection'] = test_connection(client)

    if results['test_results']['connection']:
        # Test 2: Quote (1 call)
        quote_data = test_quote(client)
        if quote_data:
            results['data']['quote'] = quote_data
            results['test_results']['quote'] = True
        else:
            results['test_results']['quote'] = False

        # Test 3: EOD Prices (1 call)
        prices_data = test_eod_prices(client)
        if prices_data:
            results['data']['prices'] = {
                'count': len(prices_data),
                'sample': prices_data
            }
            results['test_results']['prices'] = True
        else:
            results['test_results']['prices'] = False

        # Test 4: News (5 calls!)
        news_data = test_news(client)
        if news_data:
            results['data']['news'] = {
                'count': len(news_data),
                'sample': news_data
            }
            results['test_results']['news'] = True
        else:
            results['test_results']['news'] = False

        # Test 5: Fundamentals (1 call)
        fundamentals_data = test_fundamentals(client)
        if fundamentals_data:
            results['data']['fundamentals'] = fundamentals_data
            results['test_results']['fundamentals'] = True
        else:
            results['test_results']['fundamentals'] = False

    # Final status
    remaining = client.get_remaining_calls()
    results['api_calls_used'] = remaining['used_today']
    results['api_calls_remaining'] = remaining['remaining']

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results['test_results'].values() if v)
    total = len(results['test_results'])

    for test_name, passed_test in results['test_results'].items():
        status = "[PASS]" if passed_test else "[FAIL]"
        print(f"  {status} {test_name.replace('_', ' ').title()}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"\nAPI calls used: {results['api_calls_used']}")
    print(f"API calls remaining: {results['api_calls_remaining']}/20")

    # Save comparison data
    output_dir = Path(__file__).parent / 'comparison_data'
    save_comparison_data(results, output_dir)

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)