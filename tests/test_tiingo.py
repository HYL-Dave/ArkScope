#!/usr/bin/env python3
"""
Tiingo API Test Script

This script validates your Tiingo API setup and demonstrates basic usage.

Usage:
    # Set your API key first
    export TIINGO_API_KEY=your_key_here

    # Or create .env file with TIINGO_API_KEY=your_key_here

    # Run the test
    python data_sources/test_tiingo.py
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to load .env file
try:
    from dotenv import load_dotenv
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded .env from {env_path}")
    else:
        # Try config/.env
        env_path = project_root / 'config' / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[OK] Loaded .env from {env_path}")
except ImportError:
    print("[INFO] python-dotenv not installed, using environment variables only")


def print_header(title: str):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result."""
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        print(f"       {details}")


def test_api_key():
    """Test if API key is configured."""
    print_header("1. API Key Configuration")

    api_key = os.environ.get('TIINGO_API_KEY')

    if not api_key:
        print_result("API Key Present", False, "TIINGO_API_KEY not found in environment")
        print("\n[ACTION REQUIRED]")
        print("  1. Get your free API key from: https://www.tiingo.com/")
        print("  2. Set it via one of these methods:")
        print("     - export TIINGO_API_KEY=your_key_here")
        print("     - Create .env file with: TIINGO_API_KEY=your_key_here")
        return False

    # Mask the key for display
    masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print_result("API Key Present", True, f"Key: {masked}")
    return True


def test_connection():
    """Test basic API connectivity."""
    print_header("2. API Connection Test")

    try:
        from data_sources import TiingoDataSource

        tiingo = TiingoDataSource()

        if tiingo.validate_credentials():
            print_result("API Connection", True, "Successfully connected to Tiingo")
            return True
        else:
            print_result("API Connection", False, "Failed to validate credentials")
            return False

    except Exception as e:
        print_result("API Connection", False, f"Error: {e}")
        return False


def test_fetch_news():
    """Test news fetching functionality."""
    print_header("3. News Fetching Test")

    try:
        from data_sources import TiingoDataSource

        tiingo = TiingoDataSource()

        # Fetch recent news for a popular stock
        test_tickers = ['AAPL']
        days_back = 3

        print(f"\n  Fetching news for {test_tickers} (last {days_back} days)...")

        articles = tiingo.fetch_news(
            tickers=test_tickers,
            days_back=days_back,
            limit=5,
        )

        if articles:
            print_result("News Fetch", True, f"Retrieved {len(articles)} articles")

            print("\n  Sample articles:")
            for i, article in enumerate(articles[:3], 1):
                print(f"\n  [{i}] {article.title[:60]}...")
                print(f"      Source: {article.source}")
                print(f"      Date: {article.published_date.strftime('%Y-%m-%d %H:%M')}")
                print(f"      Tickers: {article.related_tickers}")

            return True
        else:
            print_result("News Fetch", False, "No articles returned")
            return False

    except Exception as e:
        print_result("News Fetch", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_prices():
    """Test price fetching functionality."""
    print_header("4. Price Data Test")

    try:
        from data_sources import TiingoDataSource

        tiingo = TiingoDataSource()

        # Fetch recent prices
        test_ticker = 'AAPL'
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        print(f"\n  Fetching prices for {test_ticker} ({start_date} to {end_date})...")

        prices = tiingo.fetch_prices(
            tickers=[test_ticker],
            start_date=start_date,
            end_date=end_date,
        )

        if prices:
            print_result("Price Fetch", True, f"Retrieved {len(prices)} price records")

            print("\n  Sample prices:")
            for price in prices[-5:]:  # Show last 5 days
                print(f"    {price.date}: Open={price.open:.2f}, Close={price.close:.2f}, Vol={price.volume:,}")

            return True
        else:
            print_result("Price Fetch", False, "No prices returned")
            return False

    except Exception as e:
        print_result("Price Fetch", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rate_limiting():
    """Test rate limit awareness."""
    print_header("5. Rate Limit Check")

    try:
        from data_sources import TiingoDataSource

        tiingo = TiingoDataSource()

        # Make a request to trigger rate limit tracking
        tiingo.fetch_news(['MSFT'], days_back=1, limit=1)

        status = tiingo.get_rate_limit_status()
        print(f"  Rate limit remaining: {status.get('remaining', 'N/A')}")
        print(f"  Reset time: {status.get('reset_time', 'N/A')}")

        print_result("Rate Limit Tracking", True, "Rate limit info available")
        return True

    except Exception as e:
        print_result("Rate Limit Tracking", False, f"Error: {e}")
        return False


def test_multi_ticker():
    """Test fetching data for multiple tickers."""
    print_header("6. Multi-Ticker Test")

    try:
        from data_sources import TiingoDataSource

        tiingo = TiingoDataSource()

        # Test with multiple tickers
        tickers = ['AAPL', 'MSFT', 'GOOGL']

        print(f"\n  Fetching news for {tickers}...")

        articles = tiingo.fetch_news(
            tickers=tickers,
            days_back=1,
            limit=10,
        )

        if articles:
            # Count articles per ticker
            ticker_counts = {}
            for article in articles:
                for t in article.related_tickers:
                    if t in tickers:
                        ticker_counts[t] = ticker_counts.get(t, 0) + 1

            print_result("Multi-Ticker Fetch", True, f"Retrieved {len(articles)} articles")
            print(f"  Distribution: {ticker_counts}")
            return True
        else:
            print_result("Multi-Ticker Fetch", False, "No articles returned")
            return False

    except Exception as e:
        print_result("Multi-Ticker Fetch", False, f"Error: {e}")
        return False


def show_summary(results: dict):
    """Show test summary."""
    print_header("TEST SUMMARY")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\n  Passed: {passed}/{total}")
    print()

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")

    print()

    if passed == total:
        print("  All tests passed! Your Tiingo setup is ready.")
    else:
        print("  Some tests failed. Please check the errors above.")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("       TIINGO API TEST SUITE")
    print("       MindfulRL-Intraday Project")
    print("=" * 60)

    results = {}

    # Test 1: API Key
    results['API Key Configuration'] = test_api_key()

    if not results['API Key Configuration']:
        print("\n[STOPPED] Cannot continue without API key.")
        return

    # Test 2: Connection
    results['API Connection'] = test_connection()

    if not results['API Connection']:
        print("\n[STOPPED] Cannot continue without valid connection.")
        show_summary(results)
        return

    # Test 3: News
    results['News Fetching'] = test_fetch_news()

    # Test 4: Prices
    results['Price Data'] = test_fetch_prices()

    # Test 5: Rate Limiting
    results['Rate Limit Tracking'] = test_rate_limiting()

    # Test 6: Multi-Ticker
    results['Multi-Ticker'] = test_multi_ticker()

    # Summary
    show_summary(results)


if __name__ == '__main__':
    main()