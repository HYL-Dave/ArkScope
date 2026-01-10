#!/usr/bin/env python3
"""
Finnhub API Test Suite

Tests the Finnhub data source implementation for news and price fetching.
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
env_path = Path(__file__).parent.parent / 'config' / '.env'
if env_path.exists():
    print(f"[OK] Loaded .env from {env_path}")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Remove surrounding quotes if present
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        print(f"       {details}")


def run_tests():
    from data_sources import FinnhubDataSource

    print("\n" + "="*60)
    print("       FINNHUB API TEST SUITE")
    print("       MindfulRL-Intraday Project")
    print("="*60)

    results = []

    # Test 1: API Key Configuration
    print_header("1. API Key Configuration")
    finnhub = FinnhubDataSource()
    api_key = finnhub.api_key

    if api_key:
        print_result("API Key Present", True, f"Key: {api_key[:8]}...{api_key[-4:]}")
        results.append(("API Key Configuration", True))
    else:
        print_result("API Key Present", False, "No FINNHUB_API_KEY found")
        results.append(("API Key Configuration", False))
        print("\nPlease set FINNHUB_API_KEY environment variable or add to config/.env")
        return results

    # Test 2: API Connection
    print_header("2. API Connection Test")
    try:
        is_valid = finnhub.validate_credentials()
        if is_valid:
            print_result("API Connection", True, "Successfully connected to Finnhub")
            results.append(("API Connection", True))
        else:
            print_result("API Connection", False, "Credentials validation failed")
            results.append(("API Connection", False))
    except Exception as e:
        print_result("API Connection", False, str(e))
        results.append(("API Connection", False))

    # Test 3: News Fetching
    print_header("3. News Fetching Test")
    print(f"\n  Fetching news for ['AAPL'] (last 3 days)...")

    try:
        news = finnhub.fetch_news(['AAPL'], days_back=3)
        if news:
            print_result("News Fetch", True, f"Retrieved {len(news)} articles")
            print(f"\n  Sample articles:")
            for article in news[:3]:
                print(f"    [{article.published_date.strftime('%Y-%m-%d')}] {article.title[:60]}...")
            results.append(("News Fetching", True))
        else:
            print_result("News Fetch", False, "No articles returned")
            results.append(("News Fetching", False))
    except Exception as e:
        print_result("News Fetch", False, str(e))
        results.append(("News Fetching", False))

    # Test 4: Price Data
    print_header("4. Price Data Test")
    start_date = date.today() - timedelta(days=7)
    end_date = date.today()
    print(f"\n  Fetching prices for AAPL ({start_date} to {end_date})...")

    try:
        prices = finnhub.fetch_prices(['AAPL'], start_date=start_date, end_date=end_date)
        if prices:
            print_result("Price Fetch", True, f"Retrieved {len(prices)} price records")
            print(f"\n  Sample prices:")
            for price in prices[:5]:
                print(f"    {price.date}: Open={price.open:.2f}, Close={price.close:.2f}, Vol={price.volume:,}")
            results.append(("Price Data", True))
        else:
            print_result("Price Fetch", False, "No price data returned")
            results.append(("Price Data", False))
    except Exception as e:
        print_result("Price Fetch", False, str(e))
        results.append(("Price Data", False))

    # Test 5: Real-time Quote
    print_header("5. Real-time Quote Test")
    print(f"\n  Fetching quote for AAPL...")

    try:
        quote = finnhub.fetch_quote('AAPL')
        if quote and 'c' in quote:
            print_result("Quote Fetch", True, f"Current price: ${quote['c']:.2f}")
            print(f"    Open: ${quote.get('o', 0):.2f}")
            print(f"    High: ${quote.get('h', 0):.2f}")
            print(f"    Low: ${quote.get('l', 0):.2f}")
            print(f"    Prev Close: ${quote.get('pc', 0):.2f}")
            results.append(("Real-time Quote", True))
        else:
            print_result("Quote Fetch", False, "No quote data returned")
            results.append(("Real-time Quote", False))
    except Exception as e:
        print_result("Quote Fetch", False, str(e))
        results.append(("Real-time Quote", False))

    # Test 6: Multi-Ticker News
    print_header("6. Multi-Ticker News Test")
    print(f"\n  Fetching news for ['AAPL', 'MSFT', 'GOOGL']...")

    try:
        news = finnhub.fetch_news(['AAPL', 'MSFT', 'GOOGL'], days_back=3, limit=5)
        if news:
            print_result("Multi-Ticker Fetch", True, f"Retrieved {len(news)} unique articles")

            # Count by ticker
            ticker_counts = {}
            for article in news:
                ticker_counts[article.ticker] = ticker_counts.get(article.ticker, 0) + 1

            print(f"  Articles by ticker:")
            for ticker, count in ticker_counts.items():
                print(f"    {ticker}: {count}")
            results.append(("Multi-Ticker", True))
        else:
            print_result("Multi-Ticker Fetch", False, "No articles returned")
            results.append(("Multi-Ticker", False))
    except Exception as e:
        print_result("Multi-Ticker Fetch", False, str(e))
        results.append(("Multi-Ticker", False))

    # Test 7: Company Profile
    print_header("7. Company Profile Test")
    print(f"\n  Fetching company profile for AAPL...")

    try:
        profile = finnhub.fetch_company_profile('AAPL')
        if profile and 'name' in profile:
            print_result("Company Profile", True, f"Company: {profile.get('name')}")
            print(f"    Industry: {profile.get('finnhubIndustry', 'N/A')}")
            print(f"    Market Cap: ${profile.get('marketCapitalization', 0):,.0f}M")
            print(f"    IPO: {profile.get('ipo', 'N/A')}")
            results.append(("Company Profile", True))
        else:
            print_result("Company Profile", False, "No profile data returned")
            results.append(("Company Profile", False))
    except Exception as e:
        print_result("Company Profile", False, str(e))
        results.append(("Company Profile", False))

    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n  Passed: {passed}/{total}")

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    if passed == total:
        print("\n  All tests passed! Finnhub integration is ready.")
    else:
        print("\n  Some tests failed. Please check the errors above.")

    return results


if __name__ == "__main__":
    run_tests()