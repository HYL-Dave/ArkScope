#!/usr/bin/env python3
"""
Option Mispricing Scanner.

This script scans for potentially mispriced options by comparing
theoretical prices (based on historical volatility) with market prices.

Usage:
    # Scan single ticker
    python scan_option_mispricing.py NVDA

    # Scan multiple tickers
    python scan_option_mispricing.py NVDA AMD AAPL

    # Custom parameters
    python scan_option_mispricing.py NVDA --threshold 15 --min-dte 14 --max-dte 45

    # Use different HV method
    python scan_option_mispricing.py NVDA --hv-method garman_klass --hv-window 20

Requirements:
    - IBKR TWS or Gateway running
    - OPRA subscription ($1.50/month)
    - Historical price data (local or via IBKR)
"""

import argparse
import sys
import json
import logging
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from config/.env
load_dotenv(project_root / "config" / ".env")

# Use random client ID to avoid conflicts
import os
os.environ['IBKR_CLIENT_ID'] = str(random.randint(100, 999))

from data_sources import IBKRDataSource, OptionFilter
from analysis import (
    calculate_historical_volatility,
    calculate_implied_volatility,
    analyze_option_mispricing,
    scan_options_for_mispricing,
    analyze_iv_environment,
    get_risk_free_rate,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_local_price_data(ticker: str, days: int = 60) -> Optional[pd.DataFrame]:
    """
    Load local historical price data for HV calculation.

    Args:
        ticker: Stock symbol.
        days: Number of days of data needed.

    Returns:
        DataFrame with OHLCV data or None.
    """
    # Try daily data first
    daily_path = project_root / 'data' / 'prices' / 'daily' / f'{ticker}.parquet'
    if daily_path.exists():
        df = pd.read_parquet(daily_path)
        return df.tail(days)

    # Try 15min data and resample
    intraday_path = project_root / 'data' / 'prices' / '15min' / f'{ticker}.parquet'
    if intraday_path.exists():
        df = pd.read_parquet(intraday_path)
        # Resample to daily
        df['date'] = pd.to_datetime(df['datetime']).dt.date
        daily = df.groupby('date').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).reset_index()
        return daily.tail(days)

    return None


def calculate_hv_from_data(
    df: pd.DataFrame,
    method: str = 'garman_klass',
    window: int = 30,
) -> float:
    """
    Calculate historical volatility from DataFrame.

    Args:
        df: DataFrame with OHLC columns.
        method: Volatility calculation method.
        window: Number of periods to use.

    Returns:
        Annualized volatility as decimal.
    """
    if df is None or len(df) < 5:
        return 0.30  # Default 30%

    df = df.tail(window)

    prices = df.to_dict('records')
    return calculate_historical_volatility(prices, method=method, window=window)


def get_spot_price(ibkr: IBKRDataSource, ticker: str) -> Optional[float]:
    """
    Get spot price, trying multiple methods.

    1. First try real-time quote
    2. Fall back to local historical data
    3. Fall back to IBKR historical data
    """
    # Try real-time quote first
    quote = ibkr.get_current_quote(ticker)
    if quote:
        price = quote.get('last') or quote.get('close')
        if price and not (isinstance(price, float) and (price != price)):  # Check for NaN
            return price

    # Fall back to local historical data
    price_data = load_local_price_data(ticker, days=5)
    if price_data is not None and len(price_data) > 0:
        last_close = price_data['close'].iloc[-1]
        if not pd.isna(last_close):
            logger.info(f"  Using local historical close: ${last_close:.2f}")
            return float(last_close)

    # Fall back to IBKR historical data
    try:
        from datetime import date as date_type
        bars = ibkr.fetch_prices([ticker], start_date=date_type.today() - timedelta(days=5))
        if bars:
            return bars[-1].close
    except Exception as e:
        logger.debug(f"  Could not fetch IBKR historical: {e}")

    return None


def scan_ticker(
    ibkr: IBKRDataSource,
    ticker: str,
    option_filter: OptionFilter,
    hv_method: str = 'garman_klass',
    hv_window: int = 30,
    mispricing_threshold: float = 10.0,
    risk_free_rate: float = 0.05,
    max_contracts: int = 50,
) -> Dict:
    """
    Scan a single ticker for mispriced options.

    Args:
        ibkr: Connected IBKR data source.
        ticker: Stock symbol.
        option_filter: Filter for interesting options.
        hv_method: Historical volatility method.
        hv_window: HV calculation window (days).
        mispricing_threshold: Threshold % for signals.
        risk_free_rate: Risk-free rate.
        max_contracts: Maximum contracts to fetch quotes for.

    Returns:
        Dict with 'iv_analysis' (IVAnalysis or None) and 'signals' (list of dicts).
    """
    logger.info(f"Scanning {ticker}...")

    # Get current stock price (with fallbacks)
    spot_price = get_spot_price(ibkr, ticker)
    if not spot_price:
        logger.warning(f"Cannot get price for {ticker} (try adding market data subscription)")
        return {'iv_analysis': None, 'signals': []}

    logger.info(f"  Current price: ${spot_price:.2f}")

    # Calculate historical volatility
    price_data = load_local_price_data(ticker, days=hv_window + 10)
    if price_data is not None:
        hv = calculate_hv_from_data(price_data, method=hv_method, window=hv_window)
        logger.info(f"  Historical Vol ({hv_method}, {hv_window}d): {hv:.1%}")
    else:
        # Fallback: try to get from IBKR
        logger.warning(f"  No local data, using default HV")
        hv = 0.30  # Default 30%

    # Get interesting option contracts
    contracts = ibkr.filter_interesting_options(
        ticker,
        filter_config=option_filter,
        current_price=spot_price,
    )

    if not contracts:
        logger.warning(f"  No contracts found matching filter")
        return {'iv_analysis': None, 'signals': []}

    logger.info(f"  Found {len(contracts)} contracts matching filter")

    # Limit contracts to avoid timeout (prioritize nearest expiry)
    if len(contracts) > max_contracts:
        contracts = contracts[:max_contracts]
        logger.info(f"  Limited to {max_contracts} contracts (use --max-contracts to adjust)")

    # Get quotes for each contract
    quotes = []
    for i, contract in enumerate(contracts):
        if i > 0 and i % 10 == 0:
            logger.info(f"    Fetching quote {i}/{len(contracts)}...")

        opt_quote = ibkr.get_option_quote(
            ticker=contract['underlying'],
            expiry=contract['expiry'],
            strike=contract['strike'],
            right=contract['right'],
            delayed=True,
        )

        # Validate quote: bid/ask must be positive numbers (not -1 placeholder)
        if opt_quote and opt_quote.bid is not None and opt_quote.ask is not None:
            if opt_quote.bid > 0 and opt_quote.ask > 0:
                quotes.append({
                    'underlying': ticker,
                    'expiry': contract['expiry'],
                    'strike': contract['strike'],
                    'right': contract['right'],
                    'bid': opt_quote.bid,
                    'ask': opt_quote.ask,
                })

    logger.info(f"  Got {len(quotes)} valid quotes")

    if not quotes:
        return {'iv_analysis': None, 'signals': []}

    # Calculate ATM IV from nearest-ATM quotes
    atm_ivs = []
    for q in quotes:
        moneyness = abs(q['strike'] - spot_price) / spot_price
        if moneyness < 0.03:  # Within 3% of ATM
            mid = (q['bid'] + q['ask']) / 2
            exp_date = datetime.strptime(q['expiry'], '%Y%m%d').date()
            dte = (exp_date - date.today()).days
            T = max(dte, 1) / 365.0
            iv = calculate_implied_volatility(mid, spot_price, q['strike'], T, risk_free_rate, q['right'])
            if iv and 0.01 < iv < 3.0:
                atm_ivs.append(iv)

    current_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else None

    # IV environment analysis
    iv_analysis = None
    if current_iv:
        # Load historical IV data if available
        iv_history_path = project_root / 'data' / 'options' / 'iv_history' / f'{ticker}.parquet'
        iv_history = None
        if iv_history_path.exists():
            try:
                iv_df = pd.read_parquet(iv_history_path)
                iv_history = iv_df['atm_iv'].dropna().tolist()
            except Exception:
                pass

        iv_analysis = analyze_iv_environment(
            ticker=ticker,
            current_iv=current_iv,
            hv=hv,
            iv_history=iv_history,
        )
        logger.info(f"  ATM IV: {current_iv:.1%}, HV: {hv:.1%}, VRP: {iv_analysis.vrp:.1%}")
        if iv_analysis.iv_percentile is not None:
            logger.info(f"  IV Percentile: {iv_analysis.iv_percentile:.0f}% ({iv_analysis.lookback_days}d)")
        logger.info(f"  Signal: {iv_analysis.signal}")
    else:
        logger.warning(f"  Could not calculate ATM IV (no near-ATM quotes)")

    # Scan for mispricing (still useful as supplementary data)
    signals = scan_options_for_mispricing(
        quotes=quotes,
        spot_price=spot_price,
        historical_vol=hv,
        risk_free_rate=risk_free_rate,
        mispricing_threshold_pct=mispricing_threshold,
        min_confidence='LOW',
    )

    logger.info(f"  Found {len(signals)} mispricing signals")

    # Convert to dicts for output
    results = []
    for sig in signals:
        results.append({
            'ticker': sig.underlying,
            'expiry': sig.expiry,
            'strike': sig.strike,
            'right': sig.right,
            'theoretical': round(sig.theoretical_price, 2),
            'market_mid': round(sig.market_mid, 2),
            'bid': round(sig.market_bid, 2),
            'ask': round(sig.market_ask, 2),
            'mispricing_pct': round(sig.mispricing_pct, 1),
            'spread_pct': round(sig.spread_pct, 1),
            'signal': sig.signal,
            'confidence': sig.confidence,
            'delta': round(sig.delta, 3),
            'iv_market': round(sig.iv_market, 3) if sig.iv_market else None,
            'hv_used': round(sig.hv_used, 3) if sig.hv_used else None,
        })

    return {'iv_analysis': iv_analysis, 'signals': results}


def print_results(scan_result: Dict, ticker: str):
    """Pretty print scan results with IV analysis."""
    iv_analysis = scan_result.get('iv_analysis')
    results = scan_result.get('signals', [])

    print(f"\n{'='*80}")
    print(f" {ticker} Option Analysis")
    print(f"{'='*80}")

    # IV Environment Summary (most important section)
    if iv_analysis:
        print(f"\n--- IV Environment ---")
        print(f"  ATM Implied Vol:     {iv_analysis.current_iv:.1%}")
        print(f"  Historical Vol:      {iv_analysis.hv:.1%}")
        print(f"  Vol Risk Premium:    {iv_analysis.vrp:+.1%}")

        if iv_analysis.iv_percentile is not None:
            print(f"  IV Rank:             {iv_analysis.iv_rank:.0f}%")
            print(f"  IV Percentile:       {iv_analysis.iv_percentile:.0f}% ({iv_analysis.lookback_days}d lookback)")
            print(f"  IV Range:            {iv_analysis.iv_min:.1%} - {iv_analysis.iv_max:.1%} (mean: {iv_analysis.iv_mean:.1%})")
        else:
            print(f"  IV History:          Not available (start collecting to enable IV percentile)")

        signal_map = {
            'IV_HIGH': 'IV HIGH - Options expensive, favor selling strategies',
            'IV_LOW': 'IV LOW - Options cheap, favor buying strategies',
            'NEUTRAL': 'NEUTRAL - IV in normal range',
        }
        print(f"  Signal:              {signal_map.get(iv_analysis.signal, iv_analysis.signal)}")
    else:
        print(f"\n  Could not calculate IV environment (no valid ATM quotes)")

    # Mispricing details (supplementary, with caveat)
    if results:
        print(f"\n--- HV-Based Mispricing Signals ({len(results)} found) ---")
        print(f"  Note: These compare HV-based theoretical prices with market prices.")
        print(f"  Market prices include VRP, so most options will appear 'overpriced'.")
        print(f"  Focus on the IV Environment analysis above for actionable signals.")

        # Show top 10 only
        top_n = min(10, len(results))
        print(f"\n  Top {top_n} by mispricing magnitude:")
        print(f"  {'Expiry':<10} {'Strike':>8} {'Type':<4} {'Theo':>8} {'Market':>8} "
              f"{'Misprice':>10} {'IV_mkt':>8}")
        print(f"  {'-'*68}")

        for r in results[:top_n]:
            iv_str = f"{r['iv_market']:.1%}" if r.get('iv_market') else "  N/A"
            print(f"  {r['expiry']:<10} {r['strike']:>8.1f} {r['right']:<4} "
                  f"${r['theoretical']:>7.2f} ${r['market_mid']:>7.2f} "
                  f"{r['mispricing_pct']:>+9.1f}% {iv_str:>8}")
    else:
        print(f"\n  No HV-based mispricing signals found")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='Scan for mispriced options based on HV vs market prices'
    )
    parser.add_argument('tickers', nargs='+', help='Stock symbols to scan')
    parser.add_argument('--threshold', type=float, default=10.0,
                        help='Mispricing threshold %% (default: 10)')
    parser.add_argument('--min-dte', type=int, default=7,
                        help='Minimum days to expiration (default: 7)')
    parser.add_argument('--max-dte', type=int, default=60,
                        help='Maximum days to expiration (default: 60)')
    parser.add_argument('--strike-range', type=float, default=0.10,
                        help='Strike range as %% of spot (default: 0.10 = ±10%%)')
    parser.add_argument('--hv-method', choices=['close_to_close', 'parkinson', 'garman_klass'],
                        default='garman_klass', help='HV calculation method')
    parser.add_argument('--hv-window', type=int, default=30,
                        help='HV calculation window in days (default: 30)')
    parser.add_argument('--max-contracts', type=int, default=50,
                        help='Max contracts to fetch quotes for (default: 50)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file (JSON format)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create option filter
    option_filter = OptionFilter(
        strike_range_pct=args.strike_range,
        min_dte=args.min_dte,
        max_dte=args.max_dte,
        rights=['C', 'P'],
    )

    # Risk-free rate
    rfr = get_risk_free_rate()
    logger.info(f"Using risk-free rate: {rfr:.2%}")

    # Connect to IBKR
    all_results = {}

    try:
        with IBKRDataSource() as ibkr:
            for ticker in args.tickers:
                results = scan_ticker(
                    ibkr=ibkr,
                    ticker=ticker.upper(),
                    option_filter=option_filter,
                    hv_method=args.hv_method,
                    hv_window=args.hv_window,
                    mispricing_threshold=args.threshold,
                    risk_free_rate=rfr,
                    max_contracts=args.max_contracts,
                )

                all_results[ticker.upper()] = results
                print_results(results, ticker.upper())

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    # Save results if output specified
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize: convert IVAnalysis dataclass to dict for JSON
        serializable = {}
        for tk, res in all_results.items():
            iv = res.get('iv_analysis')
            serializable[tk] = {
                'iv_analysis': {
                    'ticker': iv.ticker,
                    'current_iv': round(iv.current_iv, 4),
                    'hv': round(iv.hv, 4),
                    'vrp': round(iv.vrp, 4),
                    'iv_rank': round(iv.iv_rank, 1) if iv.iv_rank is not None else None,
                    'iv_percentile': round(iv.iv_percentile, 1) if iv.iv_percentile is not None else None,
                    'iv_min': round(iv.iv_min, 4) if iv.iv_min is not None else None,
                    'iv_max': round(iv.iv_max, 4) if iv.iv_max is not None else None,
                    'iv_mean': round(iv.iv_mean, 4) if iv.iv_mean is not None else None,
                    'lookback_days': iv.lookback_days,
                    'signal': iv.signal,
                    'as_of_date': iv.as_of_date.isoformat(),
                } if iv else None,
                'signals': res.get('signals', []),
            }

        with open(output_path, 'w') as f:
            json.dump({
                'scan_time': datetime.now().isoformat(),
                'parameters': {
                    'threshold': args.threshold,
                    'min_dte': args.min_dte,
                    'max_dte': args.max_dte,
                    'strike_range': args.strike_range,
                    'hv_method': args.hv_method,
                    'hv_window': args.hv_window,
                },
                'results': serializable,
            }, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    # Summary
    total_signals = sum(len(r.get('signals', [])) for r in all_results.values())
    tickers_with_iv = sum(1 for r in all_results.values() if r.get('iv_analysis'))
    print(f"\n{'='*80}")
    print(f" Summary: {len(args.tickers)} tickers scanned, "
          f"{tickers_with_iv} with IV analysis, "
          f"{total_signals} HV-based signals")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()