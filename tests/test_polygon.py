#!/usr/bin/env python3
"""
Polygon.io API Test Suite

Tests the Polygon data source implementation for news, prices, and intraday data.
Free tier: 5 calls/minute, 2 years historical minute-level data.
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
    from data_sources.polygon_source import PolygonDataSource

    print("\n" + "="*60)
    print("       POLYGON.IO API TEST SUITE")
    print("       MindfulRL-Intraday Project")
    print("       (Free tier: 5 calls/min)")
    print("="*60)

    results = []

    # Test 1: API Key Configuration
    print_header("1. API Key Configuration")
    polygon = PolygonDataSource()
    api_key = polygon.api_key

    if api_key:
        print_result("API Key Present", True, f"Key: {api_key[:8]}...{api_key[-4:]}")
        results.append(("API Key Configuration", True))
    else:
        print_result("API Key Present", False, "No POLYGON_API_KEY found")
        results.append(("API Key Configuration", False))
        print("\nPlease set POLYGON_API_KEY environment variable or add to config/.env")
        print("Get free API key at: https://polygon.io/")
        return results

    # Test 2: API Connection
    print_header("2. API Connection Test")
    print("  (This may take ~12 seconds due to rate limiting)")
    try:
        is_valid = polygon.validate_credentials()
        if is_valid:
            print_result("API Connection", True, "Successfully connected to Polygon.io")
            results.append(("API Connection", True))
        else:
            print_result("API Connection", False, "Credentials validation failed")
            results.append(("API Connection", False))
    except Exception as e:
        print_result("API Connection", False, str(e))
        results.append(("API Connection", False))

    # Test 3: Ticker Details
    print_header("3. Ticker Details Test")
    print(f"\n  Fetching details for AAPL...")

    try:
        details = polygon.fetch_ticker_details('AAPL')
        if details:
            print_result("Ticker Details", True, f"Company: {details.get('name')}")
            print(f"    Market: {details.get('market')}")
            print(f"    Type: {details.get('type')}")
            print(f"    List Date: {details.get('list_date')}")
            print(f"    Market Cap: ${details.get('market_cap', 0)/1e9:.1f}B" if details.get('market_cap') else "    Market Cap: N/A")
            results.append(("Ticker Details", True))
        else:
            print_result("Ticker Details", False, "No details returned")
            results.append(("Ticker Details", False))
    except Exception as e:
        print_result("Ticker Details", False, str(e))
        results.append(("Ticker Details", False))

    # Test 4: Daily Price Data
    print_header("4. Daily Price Data Test")
    start_date = date.today() - timedelta(days=30)
    end_date = date.today()
    print(f"\n  Fetching daily prices for AAPL ({start_date} to {end_date})...")

    try:
        prices = polygon.fetch_prices(['AAPL'], start_date=start_date, end_date=end_date)
        if prices:
            print_result("Daily Prices", True, f"Retrieved {len(prices)} price records")
            print(f"\n  Sample prices:")
            for price in prices[-5:]:
                print(f"    {price.date}: Open={price.open:.2f}, Close={price.close:.2f}, Vol={price.volume:,}")
            results.append(("Daily Prices", True))
        else:
            print_result("Daily Prices", False, "No price data returned")
            results.append(("Daily Prices", False))
    except Exception as e:
        print_result("Daily Prices", False, str(e))
        results.append(("Daily Prices", False))

    # Test 5: Historical Data Range (2 years for free tier)
    print_header("5. Historical Data Range Test (Free Tier: 2 Years)")
    two_years_ago = date.today() - timedelta(days=730)
    print(f"\n  Testing if 2-year history is available (from {two_years_ago})...")

    try:
        prices = polygon.fetch_prices(['AAPL'], start_date=two_years_ago, end_date=two_years_ago + timedelta(days=7))
        if prices:
            earliest = min(p.date for p in prices)
            print_result("2-Year History", True, f"Data available from {earliest}")
            results.append(("2-Year History", True))
        else:
            print_result("2-Year History", False, "No historical data returned")
            results.append(("2-Year History", False))
    except Exception as e:
        print_result("2-Year History", False, str(e))
        results.append(("2-Year History", False))

    # Test 6: Intraday (Minute) Data
    print_header("6. Intraday (Minute) Data Test")
    # Use a recent trading day
    test_date = date.today() - timedelta(days=3)
    # Adjust for weekend
    while test_date.weekday() >= 5:
        test_date -= timedelta(days=1)
    print(f"\n  Fetching minute-level data for AAPL on {test_date}...")

    try:
        intraday = polygon.fetch_intraday_prices('AAPL', test_date)
        if intraday:
            print_result("Intraday Data", True, f"Retrieved {len(intraday)} minute bars")
            print(f"\n  Sample data (first 5 bars):")
            for bar in intraday[:5]:
                dt = bar.get('datetime', '')
                print(f"    {dt}: O={bar.get('o'):.2f}, H={bar.get('h'):.2f}, L={bar.get('l'):.2f}, C={bar.get('c'):.2f}")
            results.append(("Intraday Data", True))
        else:
            print_result("Intraday Data", False, "No intraday data returned")
            results.append(("Intraday Data", False))
    except Exception as e:
        print_result("Intraday Data", False, str(e))
        results.append(("Intraday Data", False))

    # Test 7: News Data
    print_header("7. News Data Test")
    print(f"\n  Fetching news for AAPL (last 7 days)...")

    try:
        news = polygon.fetch_news(['AAPL'], days_back=7)
        if news:
            print_result("News Fetch", True, f"Retrieved {len(news)} articles")
            print(f"\n  Sample articles:")
            for article in news[:3]:
                sentiment = f" [Sentiment: {article.sentiment_score}]" if article.sentiment_score else ""
                print(f"    [{article.published_date.strftime('%Y-%m-%d')}] {article.title[:50]}...{sentiment}")
            results.append(("News Fetch", True))
        else:
            print_result("News Fetch", False, "No news returned")
            results.append(("News Fetch", False))
    except Exception as e:
        print_result("News Fetch", False, str(e))
        results.append(("News Fetch", False))

    # Test 8: Previous Close
    print_header("8. Previous Close Test")
    print(f"\n  Fetching previous close for AAPL...")

    try:
        prev = polygon.fetch_previous_close('AAPL')
        if prev:
            print_result("Previous Close", True, f"Close: ${prev.get('c', 0):.2f}")
            print(f"    Open: ${prev.get('o', 0):.2f}")
            print(f"    High: ${prev.get('h', 0):.2f}")
            print(f"    Low: ${prev.get('l', 0):.2f}")
            print(f"    Volume: {prev.get('v', 0):,}")
            results.append(("Previous Close", True))
        else:
            print_result("Previous Close", False, "No data returned")
            results.append(("Previous Close", False))
    except Exception as e:
        print_result("Previous Close", False, str(e))
        results.append(("Previous Close", False))

    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n  Passed: {passed}/{total}")

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")

    if passed == total:
        print("\n  All tests passed! Polygon.io integration is ready.")
    else:
        print("\n  Some tests failed. Please check the errors above.")

    # Additional info
    print_header("FREE TIER CAPABILITIES")
    print("""
  Polygon.io Free Tier includes:
  - 5 API calls/minute (rate limited)
  - 2 years of minute-level historical data
  - End-of-day (EOD) data
  - 15-minute delayed quotes
  - News API with sentiment

  Paid plans ($99-$199/month) add:
  - Unlimited API calls
  - 10-15 years historical data
  - Real-time data
  - Tick-level data
    """)

    return results


if __name__ == "__main__":
    run_tests()