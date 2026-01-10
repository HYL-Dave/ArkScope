#!/usr/bin/env python3
"""
yfinance (Yahoo Finance) Test Script

Tests:
1. Stock price history (daily, weekly, monthly)
2. Intraday data (1m, 5m, 15m intervals)
3. Company info
4. News articles
5. Multiple tickers at once

Note: yfinance is unofficial and may be rate-limited or blocked
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import() -> bool:
    """Test 0: Import yfinance"""
    print("\n" + "="*60)
    print("TEST 0: Import yfinance")
    print("="*60)

    try:
        import yfinance as yf
        print(f"✅ yfinance version: {yf.__version__}")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("   Install with: pip install yfinance")
        return False


def test_daily_prices() -> bool:
    """Test 1: Daily historical prices"""
    print("\n" + "="*60)
    print("TEST 1: Daily Historical Prices (3 years)")
    print("="*60)

    try:
        import yfinance as yf

        ticker = yf.Ticker("AAPL")
        end_date = date.today()
        start_date = end_date - timedelta(days=3*365)  # 3 years

        hist = ticker.history(start=str(start_date), end=str(end_date))

        if not hist.empty:
            print(f"✅ Retrieved {len(hist)} daily records")
            print(f"   Date range: {hist.index[0].date()} to {hist.index[-1].date()}")
            print(f"   Columns: {list(hist.columns)}")

            # Show recent prices
            print("\nRecent prices:")
            for idx, row in hist.tail(5).iterrows():
                print(f"   {idx.date()}: ${row['Close']:.2f} (vol: {int(row['Volume']):,})")

            return True
        else:
            print("❌ No data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_intraday_data() -> bool:
    """Test 2: Intraday (minute-level) data"""
    print("\n" + "="*60)
    print("TEST 2: Intraday Data (1-minute intervals)")
    print("="*60)

    try:
        import yfinance as yf

        ticker = yf.Ticker("MSFT")

        # yfinance limits: 1m data only for last 7 days
        hist = ticker.history(period="5d", interval="1m")

        if not hist.empty:
            print(f"✅ Retrieved {len(hist)} minute bars")
            print(f"   Date range: {hist.index[0]} to {hist.index[-1]}")

            # Show sample data
            print("\nSample minute bars:")
            for idx, row in hist.tail(5).iterrows():
                print(f"   {idx}: ${row['Close']:.2f} (vol: {int(row['Volume']):,})")

            return True
        else:
            print("❌ No intraday data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_company_info() -> bool:
    """Test 3: Company information"""
    print("\n" + "="*60)
    print("TEST 3: Company Information")
    print("="*60)

    try:
        import yfinance as yf

        ticker = yf.Ticker("NVDA")
        info = ticker.info

        if info:
            print(f"✅ Company: {info.get('longName', 'N/A')}")
            print(f"   Sector: {info.get('sector', 'N/A')}")
            print(f"   Industry: {info.get('industry', 'N/A')}")
            print(f"   Market Cap: ${info.get('marketCap', 0):,}")
            print(f"   Current Price: ${info.get('currentPrice', 0):.2f}")
            print(f"   P/E Ratio: {info.get('trailingPE', 'N/A')}")
            print(f"   52-Week High: ${info.get('fiftyTwoWeekHigh', 0):.2f}")
            print(f"   52-Week Low: ${info.get('fiftyTwoWeekLow', 0):.2f}")
            print(f"   Volume: {info.get('volume', 0):,}")
            return True
        else:
            print("❌ No company info returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_news() -> bool:
    """Test 4: News articles"""
    print("\n" + "="*60)
    print("TEST 4: News Articles")
    print("="*60)

    try:
        import yfinance as yf

        ticker = yf.Ticker("GOOGL")
        news = ticker.news

        if news:
            print(f"✅ Retrieved {len(news)} news articles")
            print("\nSample articles:")
            for i, article in enumerate(news[:3], 1):
                title = article.get('title', 'N/A')[:60]
                publisher = article.get('publisher', 'N/A')
                # providerPublishTime is Unix timestamp
                pub_time = article.get('providerPublishTime', 0)
                from datetime import datetime
                pub_date = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M') if pub_time else 'N/A'

                print(f"\n  [{i}] {title}...")
                print(f"      Publisher: {publisher}")
                print(f"      Published: {pub_date}")

            return True
        else:
            print("⚠️ No news articles returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_multiple_tickers() -> bool:
    """Test 5: Multiple tickers at once"""
    print("\n" + "="*60)
    print("TEST 5: Multiple Tickers Download")
    print("="*60)

    try:
        import yfinance as yf

        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        # Download multiple tickers
        data = yf.download(tickers, start=str(start_date), end=str(end_date), progress=False)

        if not data.empty:
            print(f"✅ Downloaded data for {len(tickers)} tickers")
            print(f"   Records per ticker: {len(data)}")
            print(f"   Date range: {data.index[0].date()} to {data.index[-1].date()}")

            # Show latest close prices
            print("\nLatest close prices:")
            latest = data['Close'].iloc[-1]
            for ticker in tickers:
                price = latest[ticker] if ticker in latest else 0
                print(f"   {ticker}: ${price:.2f}")

            return True
        else:
            print("❌ No data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_extended_history() -> bool:
    """Test 6: Extended history (30+ years)"""
    print("\n" + "="*60)
    print("TEST 6: Extended History (Max available)")
    print("="*60)

    try:
        import yfinance as yf

        ticker = yf.Ticker("IBM")
        hist = ticker.history(period="max")

        if not hist.empty:
            years = (hist.index[-1] - hist.index[0]).days / 365
            print(f"✅ Retrieved {len(hist)} daily records")
            print(f"   Date range: {hist.index[0].date()} to {hist.index[-1].date()}")
            print(f"   Total years: {years:.1f}")

            # Show some historical data points
            print("\nHistorical snapshots:")
            # First record
            first = hist.iloc[0]
            print(f"   {hist.index[0].date()}: ${first['Close']:.2f}")
            # Middle
            mid_idx = len(hist) // 2
            mid = hist.iloc[mid_idx]
            print(f"   {hist.index[mid_idx].date()}: ${mid['Close']:.2f}")
            # Last
            last = hist.iloc[-1]
            print(f"   {hist.index[-1].date()}: ${last['Close']:.2f}")

            return True
        else:
            print("❌ No data returned")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("yfinance (Yahoo Finance) Test Suite")
    print("="*60)
    print("\n⚠️  Note: yfinance is unofficial and may be rate-limited")

    # Run tests
    results = {}

    results['import'] = test_import()

    if results['import']:
        results['daily_prices'] = test_daily_prices()
        results['intraday'] = test_intraday_data()
        results['company_info'] = test_company_info()
        results['news'] = test_news()
        results['multiple_tickers'] = test_multiple_tickers()
        results['extended_history'] = test_extended_history()

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

    # Stability assessment
    print("\n" + "="*60)
    print("STABILITY ASSESSMENT")
    print("="*60)

    if passed >= 5:
        print("✅ yfinance appears stable for most use cases")
        print("   - Good for historical daily data")
        print("   - Limited intraday (7 days max for 1-minute)")
        print("   - News available but limited")
        print("   - May be blocked with heavy usage")
    else:
        print("⚠️ yfinance may have issues")
        print("   - Consider using official APIs")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)