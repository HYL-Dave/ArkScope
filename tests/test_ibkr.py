#!/usr/bin/env python3
"""
Interactive Brokers (IBKR) Data Source Test Suite

Tests IBKR connectivity and historical data fetching capabilities.
Measures pacing and estimates time for full dataset retrieval.

Prerequisites:
1. TWS or IB Gateway running locally
2. API enabled in TWS/Gateway settings (Configure > API > Settings):
   - Enable ActiveX and Socket Clients
   - Socket port: 7497 (paper) or 7496 (live)
   - Allow localhost connections
3. ib_insync library: pip install ib_insync

Usage:
    # Test with default settings (TWS Paper on port 7497)
    python test_ibkr.py

    # Test with specific port (IB Gateway Paper on port 4002)
    python test_ibkr.py --port 4002

    # Full historical data test from 2023-01-01
    python test_ibkr.py --full-history

    # Save test results to parquet
    python test_ibkr.py --save-parquet
"""

import os
import sys
import time

import pytest
pytestmark = pytest.mark.skip("manual test script — requires IBKR TWS")
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
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


def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_result(test_name: str, passed: bool, details: str = ""):
    status = "[ OK ]" if passed else "[FAIL]"
    print(f"{status} {test_name}")
    if details:
        print(f"       {details}")


def check_dependencies():
    """Check if required dependencies are installed."""
    print_header("Checking Dependencies")

    dependencies = []

    # Check ib_insync
    try:
        import ib_insync
        dependencies.append(("ib_insync", True, ib_insync.__version__))
    except ImportError:
        dependencies.append(("ib_insync", False, "Not installed - run: pip install ib_insync"))

    # Check pandas
    try:
        import pandas
        dependencies.append(("pandas", True, pandas.__version__))
    except ImportError:
        dependencies.append(("pandas", False, "Not installed - run: pip install pandas"))

    # Check pyarrow (for parquet)
    try:
        import pyarrow
        dependencies.append(("pyarrow", True, pyarrow.__version__))
    except ImportError:
        dependencies.append(("pyarrow", False, "Not installed - run: pip install pyarrow"))

    all_ok = True
    for name, ok, info in dependencies:
        print_result(name, ok, info)
        if not ok:
            all_ok = False

    return all_ok


def test_connection(host: str, port: int, client_id: int):
    """Test basic connectivity to TWS/IB Gateway."""
    print_header("1. Connection Test")
    print(f"\n  Attempting to connect to {host}:{port}...")
    print(f"  (Make sure TWS/IB Gateway is running with API enabled)")

    from data_sources.ibkr_source import IBKRDataSource

    try:
        ibkr = IBKRDataSource(host=host, port=port, client_id=client_id)

        start_time = time.time()
        connected = ibkr.connect()
        connect_time = time.time() - start_time

        if connected:
            print_result("Connection", True, f"Connected in {connect_time:.2f}s")

            # Get server info
            if ibkr._ib:
                managed_accounts = ibkr._ib.managedAccounts()
                print(f"       Managed accounts: {managed_accounts}")

            return ibkr
        else:
            print_result("Connection", False, "Failed to connect")
            return None

    except Exception as e:
        print_result("Connection", False, str(e))
        print("\n  Troubleshooting tips:")
        print("  1. Ensure TWS or IB Gateway is running")
        print("  2. Enable API in TWS: Configure > API > Settings")
        print("     - Check 'Enable ActiveX and Socket Clients'")
        print("     - Socket port should match (7497 for TWS Paper)")
        print("  3. Allow connections from localhost")
        return None


def test_contract_qualification(ibkr, tickers: list):
    """Test contract qualification for tickers."""
    print_header("2. Contract Qualification Test")

    results = []
    for ticker in tickers:
        try:
            contract = ibkr._create_contract(ticker)
            ibkr._ib.qualifyContracts(contract)
            details = ibkr.get_contract_details(ticker)

            if details:
                print_result(ticker, True, f"{details.get('long_name', 'N/A')}")
            else:
                print_result(ticker, True, "Qualified (no details)")
            results.append((ticker, True))
        except Exception as e:
            print_result(ticker, False, str(e))
            results.append((ticker, False))

    return results


def test_daily_prices(ibkr, tickers: list, days_back: int = 30):
    """Test daily price data retrieval."""
    print_header("3. Daily Price Data Test")

    start_date = date.today() - timedelta(days=days_back)
    end_date = date.today()
    print(f"\n  Fetching daily prices from {start_date} to {end_date}...")

    start_time = time.time()
    prices = ibkr.fetch_prices(tickers, start_date=start_date, end_date=end_date)
    fetch_time = time.time() - start_time

    if prices:
        print_result("Daily Prices", True, f"Retrieved {len(prices)} records in {fetch_time:.2f}s")

        # Group by ticker
        import pandas as pd
        df = pd.DataFrame([p.to_dict() for p in prices])

        print(f"\n  Summary by ticker:")
        for ticker in df['ticker'].unique():
            ticker_df = df[df['ticker'] == ticker]
            print(f"    {ticker}: {len(ticker_df)} days, "
                  f"{ticker_df['date'].min()} to {ticker_df['date'].max()}")

        print(f"\n  Sample prices (last 5):")
        for price in prices[-5:]:
            print(f"    {price.ticker} {price.date}: "
                  f"O={price.open:.2f}, H={price.high:.2f}, L={price.low:.2f}, C={price.close:.2f}, V={price.volume:,}")

        return prices
    else:
        print_result("Daily Prices", False, "No data returned")
        return None


def test_intraday_prices(ibkr, ticker: str, interval: str = '15 mins'):
    """Test intraday price data retrieval."""
    print_header("4. Intraday Price Data Test")

    # Use a recent trading day
    test_date = date.today() - timedelta(days=1)
    while test_date.weekday() >= 5:  # Skip weekends
        test_date -= timedelta(days=1)

    print(f"\n  Fetching {interval} bars for {ticker} on {test_date}...")

    start_time = time.time()
    bars = ibkr.fetch_intraday_prices(ticker, test_date, interval=interval)
    fetch_time = time.time() - start_time

    if bars:
        print_result(f"Intraday ({interval})", True,
                     f"Retrieved {len(bars)} bars in {fetch_time:.2f}s")

        print(f"\n  Sample bars (first 5):")
        for bar in bars[:5]:
            print(f"    {bar.datetime.strftime('%Y-%m-%d %H:%M')}: "
                  f"O={bar.open:.2f}, H={bar.high:.2f}, L={bar.low:.2f}, C={bar.close:.2f}, V={bar.volume:,}")

        # Calculate trading hours coverage
        if len(bars) > 1:
            first_bar = bars[0].datetime
            last_bar = bars[-1].datetime
            print(f"\n  Trading session: {first_bar.strftime('%H:%M')} to {last_bar.strftime('%H:%M')}")

        return bars
    else:
        print_result(f"Intraday ({interval})", False, "No data returned")
        return None


def test_historical_intraday(ibkr, ticker: str, days: int = 5, interval: str = '15 mins'):
    """Test multi-day historical intraday data."""
    print_header("5. Multi-Day Historical Intraday Test")

    start_date = date.today() - timedelta(days=days)
    end_date = date.today()

    print(f"\n  Fetching {days} days of {interval} bars for {ticker}...")
    print(f"  Date range: {start_date} to {end_date}")

    start_time = time.time()
    result = ibkr.fetch_historical_intraday(
        [ticker],
        start_date=start_date,
        end_date=end_date,
        interval=interval
    )
    fetch_time = time.time() - start_time

    bars = result.get(ticker, [])

    if bars:
        print_result("Historical Intraday", True,
                     f"Retrieved {len(bars)} bars in {fetch_time:.2f}s")

        # Calculate bars per day
        import pandas as pd
        df = pd.DataFrame([{
            'datetime': b.datetime,
            'date': b.datetime.date(),
            'open': b.open,
            'high': b.high,
            'low': b.low,
            'close': b.close,
            'volume': b.volume
        } for b in bars])

        bars_per_day = df.groupby('date').size()
        print(f"\n  Bars per trading day:")
        for d, count in bars_per_day.items():
            print(f"    {d}: {count} bars")

        # Estimate full dataset retrieval time
        avg_fetch_rate = len(bars) / fetch_time if fetch_time > 0 else 0
        print(f"\n  Fetch rate: {avg_fetch_rate:.1f} bars/second")

        return bars, df
    else:
        print_result("Historical Intraday", False, "No data returned")
        return None, None


def estimate_full_dataset_time(ibkr, tickers: list, interval: str = '15 mins'):
    """Estimate time to fetch full dataset from 2023-01-01."""
    print_header("6. Full Dataset Time Estimation")

    start_date = date(2023, 1, 1)
    end_date = date.today()
    total_days = (end_date - start_date).days
    trading_days = int(total_days * 252 / 365)  # Approximate trading days

    print(f"\n  Target dataset:")
    print(f"    Tickers: {len(tickers)} ({', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''})")
    print(f"    Date range: {start_date} to {end_date} ({total_days} calendar days, ~{trading_days} trading days)")
    print(f"    Interval: {interval}")

    # Estimate bars per day based on interval
    bars_per_day_estimate = {
        '1 min': 390,    # 6.5 hours * 60 mins
        '5 mins': 78,    # 6.5 hours / 5 mins
        '15 mins': 26,   # 6.5 hours / 15 mins
        '30 mins': 13,   # 6.5 hours / 30 mins
        '1 hour': 7,     # 6.5 hours
    }
    bars_per_day = bars_per_day_estimate.get(interval, 26)

    total_bars = trading_days * bars_per_day * len(tickers)
    print(f"    Estimated total bars: {total_bars:,}")

    # Estimate time based on IBKR pacing limits
    # Conservative: 1 request per 0.5 seconds, ~60 days per request for 15-min bars
    days_per_request = 60
    requests_per_ticker = trading_days / days_per_request
    total_requests = requests_per_ticker * len(tickers)
    time_per_request = 2.0  # seconds (including data transfer)

    estimated_seconds = total_requests * time_per_request
    estimated_minutes = estimated_seconds / 60
    estimated_hours = estimated_minutes / 60

    print(f"\n  Estimated retrieval time:")
    print(f"    Requests needed: ~{int(total_requests)}")
    print(f"    Time per request: ~{time_per_request}s")
    print(f"    Total time: ~{estimated_minutes:.1f} minutes ({estimated_hours:.2f} hours)")

    # IBKR pacing warning
    if estimated_minutes > 10:
        print(f"\n  [WARNING] Long retrieval time expected!")
        print(f"  IBKR pacing limits may cause delays or temporary blocks.")
        print(f"  Consider:")
        print(f"    1. Fetching data in multiple sessions")
        print(f"    2. Using Polygon.io as backup for historical data")
        print(f"    3. Saving intermediate results to resume later")

    return {
        'total_bars': total_bars,
        'total_requests': int(total_requests),
        'estimated_minutes': estimated_minutes,
        'estimated_hours': estimated_hours,
    }


def test_full_history_sample(ibkr, ticker: str, interval: str = '15 mins'):
    """Test fetching a longer historical period."""
    print_header("7. Historical Data Sample (30 days)")

    start_date = date.today() - timedelta(days=30)
    end_date = date.today()

    print(f"\n  Fetching 30 days of {interval} bars for {ticker}...")
    print(f"  This tests IBKR pacing with a longer request...")

    start_time = time.time()
    result = ibkr.fetch_historical_intraday(
        [ticker],
        start_date=start_date,
        end_date=end_date,
        interval=interval
    )
    fetch_time = time.time() - start_time

    bars = result.get(ticker, [])

    if bars:
        import pandas as pd
        df = pd.DataFrame([{
            'datetime': b.datetime,
            'ticker': b.ticker,
            'date': b.datetime.date(),
            'open': b.open,
            'high': b.high,
            'low': b.low,
            'close': b.close,
            'volume': b.volume
        } for b in bars])

        print_result("30-Day Historical", True,
                     f"Retrieved {len(bars)} bars in {fetch_time:.2f}s")

        bars_per_day = df.groupby('date').size()
        print(f"\n  Trading days retrieved: {len(bars_per_day)}")
        print(f"  Avg bars per day: {bars_per_day.mean():.1f}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")

        # Pacing analysis
        actual_rate = len(bars) / fetch_time if fetch_time > 0 else 0
        print(f"\n  Fetch performance:")
        print(f"    Actual rate: {actual_rate:.1f} bars/second")
        print(f"    Time per trading day: {fetch_time/len(bars_per_day):.2f}s")

        return bars, df
    else:
        print_result("30-Day Historical", False, "No data returned")
        return None, None


def save_to_parquet(df, filename: str, output_dir: str = "data_lake/raw/ibkr"):
    """Save DataFrame to parquet file."""
    print_header("Saving to Parquet")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filepath = output_path / filename
    df.to_parquet(filepath, index=False)

    print(f"\n  Saved to: {filepath}")
    print(f"  Records: {len(df):,}")
    print(f"  File size: {filepath.stat().st_size / 1024:.1f} KB")

    return filepath


def run_tests(args):
    """Run all IBKR tests."""
    print("\n" + "="*70)
    print("       INTERACTIVE BROKERS (IBKR) DATA SOURCE TEST SUITE")
    print("       MindfulRL-Intraday Project")
    print("="*70)
    print(f"\n  Connection target: {args.host}:{args.port}")
    print(f"  Client ID: {args.client_id}")

    # Check dependencies first
    if not check_dependencies():
        print("\n[ERROR] Missing required dependencies. Please install them first.")
        return

    results = []
    ibkr = None

    try:
        # Test 1: Connection
        ibkr = test_connection(args.host, args.port, args.client_id)
        results.append(("Connection", ibkr is not None))

        if ibkr is None:
            print("\n[ERROR] Cannot proceed without connection. Exiting.")
            return

        # Test tickers
        test_tickers = args.tickers.split(',')

        # Test 2: Contract qualification
        contract_results = test_contract_qualification(ibkr, test_tickers)
        results.extend([("Contract: " + t, ok) for t, ok in contract_results])

        # Test 3: Daily prices
        prices = test_daily_prices(ibkr, test_tickers, days_back=args.days_back)
        results.append(("Daily Prices", prices is not None))

        # Test 4: Intraday prices
        bars = test_intraday_prices(ibkr, test_tickers[0], interval=args.interval)
        results.append(("Intraday Prices", bars is not None))

        # Test 5: Multi-day historical
        bars, df = test_historical_intraday(ibkr, test_tickers[0], days=5, interval=args.interval)
        results.append(("Historical Intraday", bars is not None))

        # Test 6: Time estimation
        estimate = estimate_full_dataset_time(ibkr, test_tickers, interval=args.interval)
        results.append(("Time Estimation", True))

        # Test 7: Longer history test (if requested)
        if args.full_history:
            bars_30d, df_30d = test_full_history_sample(ibkr, test_tickers[0], interval=args.interval)
            results.append(("30-Day History", bars_30d is not None))

            if args.save_parquet and df_30d is not None:
                ticker = test_tickers[0]
                filename = f"{ticker}_{args.interval.replace(' ', '')}_{date.today().isoformat()}.parquet"
                save_to_parquet(df_30d, filename)

        # Summary
        print_header("TEST SUMMARY")
        passed = sum(1 for _, p in results if p)
        total = len(results)
        print(f"\n  Passed: {passed}/{total}")

        for name, ok in results:
            status = "[ OK ]" if ok else "[FAIL]"
            print(f"  {status} {name}")

        # Recommendations
        print_header("RECOMMENDATIONS FOR FINRL TRAINING")
        print(f"""
  Based on test results:

  1. DATA SOURCE STRATEGY:
     - IBKR: Good for 15-min bars, moderate pacing limits
     - For 2023-01-01 to now: ~{estimate['estimated_hours']:.1f} hours retrieval time
     - Consider: Running data fetch overnight or in batches

  2. SUGGESTED WORKFLOW:
     a. Use this script to fetch 30-day samples for testing
     b. Run full historical fetch as background job
     c. Save to parquet for FinRL training
     d. Use Polygon.io as backup if IBKR pacing is too slow

  3. INTERVAL RECOMMENDATION:
     - 15 mins: Best for intraday RL (26 bars/day)
     - 30 mins: Faster fetch, still captures intraday patterns
     - 1 hour: Fastest, good for initial prototyping

  4. NEXT STEPS:
     # Test with more tickers
     python test_ibkr.py --tickers AAPL,MSFT,GOOGL,AMZN,META

     # Full 30-day test with save
     python test_ibkr.py --full-history --save-parquet

     # Use 30-min bars for faster testing
     python test_ibkr.py --interval "30 mins" --full-history
        """)

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if ibkr:
            ibkr.disconnect()
            print("\n  Disconnected from IBKR")


def main():
    parser = argparse.ArgumentParser(
        description="Test IBKR data source for MindfulRL-Intraday",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test with TWS Paper Trading
  python test_ibkr.py

  # Test with IB Gateway Paper
  python test_ibkr.py --port 4002

  # Test multiple tickers
  python test_ibkr.py --tickers AAPL,MSFT,GOOGL

  # Full 30-day test with parquet save
  python test_ibkr.py --full-history --save-parquet

  # Test 30-minute bars
  python test_ibkr.py --interval "30 mins"
        """
    )

    # Defaults from config/.env, fallback to local connection
    default_host = os.environ.get('IBKR_HOST', '127.0.0.1')
    default_port = int(os.environ.get('IBKR_PORT', '7497'))
    default_client_id = int(os.environ.get('IBKR_CLIENT_ID', '999'))

    parser.add_argument(
        '--host',
        default=default_host,
        help=f'TWS/Gateway host (default: from config/.env or 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=default_port,
        help=f'TWS/Gateway port (default: from config/.env or 7497)'
    )
    parser.add_argument(
        '--client-id',
        type=int,
        default=default_client_id,
        help=f'Client ID (default: from config/.env or 999)'
    )
    parser.add_argument(
        '--tickers',
        default='AAPL,MSFT',
        help='Comma-separated tickers to test (default: AAPL,MSFT)'
    )
    parser.add_argument(
        '--interval',
        default='15 mins',
        help='Bar interval (default: "15 mins")'
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=30,
        help='Days back for daily price test (default: 30)'
    )
    parser.add_argument(
        '--full-history',
        action='store_true',
        help='Run extended 30-day historical test'
    )
    parser.add_argument(
        '--save-parquet',
        action='store_true',
        help='Save test data to parquet files'
    )

    args = parser.parse_args()
    run_tests(args)


if __name__ == "__main__":
    main()