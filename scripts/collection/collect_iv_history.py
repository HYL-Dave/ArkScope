#!/usr/bin/env python3
"""
IV History Collector — 每日收集 ATM Implied Volatility 歷史數據

收集每個 ticker 的 ATM IV，儲存到 data/options/iv_history/{TICKER}.parquet，
供 IV percentile rank 分析使用。

使用方式:
    # 收集所有 watchlist tickers
    python collect_iv_history.py

    # 指定 tickers
    python collect_iv_history.py --tickers NVDA AMD AAPL

    # 查看目前收集狀態
    python collect_iv_history.py --status

Requirements:
    - IBKR TWS or Gateway running
    - OPRA subscription ($1.50/month) or delayed data
"""

import argparse
import sys
import logging
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yaml
from dotenv import load_dotenv

# Project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / "config" / ".env")

# Random client ID to avoid conflicts
import os
os.environ['IBKR_CLIENT_ID'] = str(random.randint(100, 999))

from data_sources import IBKRDataSource, OptionFilter
from analysis import calculate_historical_volatility, calculate_implied_volatility

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output directory
IV_HISTORY_DIR = project_root / 'data' / 'options' / 'iv_history'


def get_watchlist_tickers() -> List[str]:
    """Load tickers from user_profile.yaml watchlists."""
    profile_path = project_root / 'config' / 'user_profile.yaml'
    if not profile_path.exists():
        return ['NVDA', 'AMD']  # Sensible defaults

    with open(profile_path) as f:
        config = yaml.safe_load(f)

    tickers = set()

    watchlists = config.get('watchlists', {})
    for key in ['core_holdings', 'interested']:
        wl = watchlists.get(key, {})
        tickers.update(wl.get('tickers', []))

    # Also check options_preferences
    opts = config.get('options_preferences', {})
    opt_tickers = opts.get('tickers_for_options', [])
    if opt_tickers:
        tickers.update(opt_tickers)

    return sorted(tickers) if tickers else ['NVDA', 'AMD']


def load_local_prices(ticker: str, days: int = 40) -> Optional[pd.DataFrame]:
    """Load local historical price data for HV calculation."""
    # Try daily data (parquet or csv)
    daily_dir = project_root / 'data' / 'prices' / 'daily'
    for ext, reader in [('.parquet', pd.read_parquet), ('.csv', pd.read_csv)]:
        daily_path = daily_dir / f'{ticker}{ext}'
        if daily_path.exists():
            return reader(daily_path).tail(days)

    # Try 15min data and resample
    intraday_dir = project_root / 'data' / 'prices' / '15min'
    intraday_df = None

    parquet_path = intraday_dir / f'{ticker}.parquet'
    if parquet_path.exists():
        intraday_df = pd.read_parquet(parquet_path)
    else:
        csv_matches = sorted(intraday_dir.glob(f'{ticker}_*.csv'))
        if csv_matches:
            intraday_df = pd.read_csv(csv_matches[-1])

    if intraday_df is not None:
        intraday_df['date'] = pd.to_datetime(intraday_df['datetime']).dt.date
        daily = intraday_df.groupby('date').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum',
        }).reset_index()
        return daily.tail(days)

    return None


def get_spot_price(ibkr: IBKRDataSource, ticker: str) -> Optional[float]:
    """Get spot price with multiple fallbacks."""
    # 1. Try real-time / delayed quote
    quote = ibkr.get_current_quote(ticker)
    if quote:
        price = quote.get('last') or quote.get('close')
        if price and isinstance(price, (int, float)) and price == price and price > 0:
            return float(price)

    # 2. Fall back to local historical data
    price_data = load_local_prices(ticker, days=5)
    if price_data is not None and len(price_data) > 0:
        last_close = price_data['close'].iloc[-1]
        if not pd.isna(last_close):
            logger.info(f"  {ticker}: Using local historical close: ${last_close:.2f}")
            return float(last_close)

    # 3. Fall back to IBKR historical bars
    try:
        bars = ibkr.fetch_prices([ticker], start_date=date.today() - timedelta(days=5))
        if bars:
            return bars[-1].close
    except Exception as e:
        logger.debug(f"  {ticker}: IBKR historical fallback failed: {e}")

    return None


def collect_atm_iv(ibkr: IBKRDataSource, ticker: str) -> Optional[dict]:
    """
    Collect current ATM IV for a ticker.

    Returns dict with: date, ticker, atm_iv, hv_30d, vrp, spot_price, num_quotes
    """
    # Get spot price (with fallbacks for after-hours)
    spot = get_spot_price(ibkr, ticker)
    if not spot:
        logger.warning(f"  {ticker}: Cannot determine spot price")
        return None

    logger.info(f"  {ticker}: spot=${spot:.2f}")

    # Get option chain (narrow filter: near-ATM, nearest expiry)
    opt_filter = OptionFilter(
        strike_range_pct=0.05,  # ±5% ATM only
        min_dte=7,
        max_dte=45,
        rights=['C', 'P'],
    )

    contracts = ibkr.filter_interesting_options(
        ticker, filter_config=opt_filter, current_price=spot,
    )

    if not contracts:
        logger.warning(f"  {ticker}: No option contracts found")
        return None

    # Limit to 20 nearest-ATM contracts
    contracts = contracts[:20]

    # Fetch quotes and calculate IV
    atm_ivs = []
    for contract in contracts:
        opt_quote = ibkr.get_option_quote(
            ticker=contract['underlying'],
            expiry=contract['expiry'],
            strike=contract['strike'],
            right=contract['right'],
            delayed=True,
        )

        if not opt_quote or opt_quote.bid is None or opt_quote.ask is None:
            continue
        if opt_quote.bid <= 0 or opt_quote.ask <= 0:
            continue

        moneyness = abs(contract['strike'] - spot) / spot
        if moneyness > 0.05:
            continue

        mid = (opt_quote.bid + opt_quote.ask) / 2
        exp_date = datetime.strptime(contract['expiry'], '%Y%m%d').date()
        dte = (exp_date - date.today()).days
        T = max(dte, 1) / 365.0

        iv = calculate_implied_volatility(
            mid, spot, contract['strike'], T, 0.05, contract['right'],
        )
        if iv and 0.01 < iv < 3.0:
            atm_ivs.append(iv)

    if not atm_ivs:
        logger.warning(f"  {ticker}: Could not calculate ATM IV (no valid near-ATM quotes)")
        return None

    current_iv = sum(atm_ivs) / len(atm_ivs)

    # Calculate HV for VRP
    price_data = load_local_prices(ticker, days=40)
    if price_data is not None and len(price_data) >= 5:
        prices = price_data.to_dict('records')
        hv = calculate_historical_volatility(prices, method='garman_klass', window=30)
    else:
        hv = None

    vrp = (current_iv - hv) if hv else None

    logger.info(f"  {ticker}: ATM IV={current_iv:.1%}, HV={hv:.1%} VRP={vrp:+.1%}"
                if hv else f"  {ticker}: ATM IV={current_iv:.1%}, HV=N/A")

    return {
        'date': date.today().isoformat(),
        'ticker': ticker,
        'atm_iv': round(current_iv, 6),
        'hv_30d': round(hv, 6) if hv else None,
        'vrp': round(vrp, 6) if vrp else None,
        'spot_price': round(spot, 2),
        'num_quotes': len(atm_ivs),
    }


def save_iv_record(record: dict):
    """Append IV record to ticker's parquet file."""
    IV_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    ticker = record['ticker']
    path = IV_HISTORY_DIR / f'{ticker}.parquet'

    new_row = pd.DataFrame([record])

    if path.exists():
        existing = pd.read_parquet(path)
        # Avoid duplicates for same date
        existing = existing[existing['date'] != record['date']]
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row

    combined = combined.sort_values('date').reset_index(drop=True)
    combined.to_parquet(path, index=False)

    logger.info(f"  {ticker}: Saved ({len(combined)} total records)")


def show_status():
    """Display current IV history collection status."""
    print(f"\n{'='*60}")
    print(f" IV History Collection Status")
    print(f"{'='*60}")

    if not IV_HISTORY_DIR.exists():
        print(f"\n  No IV history data found.")
        print(f"  Run: python collect_iv_history.py")
        return

    files = sorted(IV_HISTORY_DIR.glob('*.parquet'))
    if not files:
        print(f"\n  No IV history data found.")
        return

    print(f"\n  {'Ticker':<8} {'Records':>8} {'First Date':<12} {'Latest Date':<12} "
          f"{'Latest IV':>10} {'Latest HV':>10}")
    print(f"  {'-'*68}")

    for f in files:
        ticker = f.stem
        df = pd.read_parquet(f)
        n = len(df)
        first = df['date'].min()
        latest = df['date'].max()
        last_row = df.iloc[-1]
        iv_str = f"{last_row['atm_iv']:.1%}" if pd.notna(last_row.get('atm_iv')) else "N/A"
        hv_str = f"{last_row['hv_30d']:.1%}" if pd.notna(last_row.get('hv_30d')) else "N/A"

        print(f"  {ticker:<8} {n:>8} {first:<12} {latest:<12} {iv_str:>10} {hv_str:>10}")

    print(f"\n  IV Percentile Rank requires ~60+ days of data for meaningful results.")
    print(f"  252 trading days (1 year) is ideal.\n")


def main():
    parser = argparse.ArgumentParser(
        description='Collect daily ATM IV history for IV percentile rank analysis'
    )
    parser.add_argument('--tickers', nargs='+',
                        help='Tickers to collect (default: from user_profile.yaml)')
    parser.add_argument('--status', action='store_true',
                        help='Show current IV history status')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.status:
        show_status()
        return

    tickers = [t.upper() for t in args.tickers] if args.tickers else get_watchlist_tickers()

    logger.info(f"Collecting ATM IV for {len(tickers)} tickers: {', '.join(tickers)}")

    collected = 0
    failed = 0

    try:
        with IBKRDataSource() as ibkr:
            for ticker in tickers:
                try:
                    record = collect_atm_iv(ibkr, ticker)
                    if record:
                        save_iv_record(record)
                        collected += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"  {ticker}: {e}")
                    failed += 1

    except Exception as e:
        logger.error(f"IBKR connection error: {e}")
        sys.exit(1)

    logger.info(f"\nDone: {collected} collected, {failed} failed")

    if collected > 0:
        show_status()


if __name__ == '__main__':
    main()