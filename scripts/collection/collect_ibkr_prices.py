#!/usr/bin/env python3
"""
Collect historical stock prices from IBKR for MindfulRL training.

Data Collection Strategy (per plan):
- 2023/01 - 2023/12: 1 hour bars (IBKR, ~7 bars/day)
- 2024/01 - present: 15 minute bars (IBKR, ~26 bars/day)

This gives:
- 3 years of hourly data for baseline model training
- 2 years of 15-minute data for fine-grained model training

Requirements:
- IBKR TWS or IB Gateway running locally
- ib_insync library: pip install ib_insync
- config/tickers_core.json for stock list

Usage:
    python collect_ibkr_prices.py --output data/prices/
    python collect_ibkr_prices.py --tickers AAPL,MSFT --output data/prices/
    python collect_ibkr_prices.py --tier tier1_core --output data/prices/
    python collect_ibkr_prices.py --hourly-only --output data/prices/  # Only 2023 hourly data
    python collect_ibkr_prices.py --minute-only --output data/prices/  # Only 2024 15-min data

Resume from interruption:
    python collect_ibkr_prices.py --resume  # Continue from last checkpoint
    python collect_ibkr_prices.py --resume --tier all  # Resume with all tickers

Incremental update (daily):
    python collect_ibkr_prices.py --incremental  # Only fetch new data since last update
    python collect_ibkr_prices.py --incremental --tier all  # Incremental for all tickers

Checkpoint file is saved at: data/prices/ibkr_checkpoint.json
"""

import os
import sys
import json
import argparse
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

# Add project root to path (scripts/collection/ -> scripts/ -> project_root/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_script_dir))
sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_ibkr_config_from_env(env_path: str = "config/.env") -> Dict[str, str]:
    """
    Load IBKR configuration from .env file.

    Returns:
        Dictionary with IBKR_HOST, IBKR_PORT, IBKR_CLIENT_ID.
    """
    config = {
        'IBKR_HOST': '127.0.0.1',
        'IBKR_PORT': '7497',
        'IBKR_CLIENT_ID': '1',
    }

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key in config:
                        config[key] = value

    return config


def load_tickers_from_config(
    config_path: str = "config/tickers_core.json",
    tier: str = "tier1_core"
) -> List[str]:
    """
    Load tickers from configuration file.

    Args:
        config_path: Path to tickers configuration JSON.
        tier: Tier to load ('tier1_core', 'tier2_expanded', 'all').

    Returns:
        List of ticker symbols.
    """
    with open(config_path, 'r') as f:
        config = json.load(f)

    tickers = []

    if tier == "all":
        # Load all tiers (including user watchlist for complete coverage)
        for key in ["tier1_core", "tier2_expanded", "tier3_user_watchlist"]:
            tier_data = config.get(key, {})
            for category, data in tier_data.items():
                if isinstance(data, dict) and "tickers" in data:
                    tickers.extend(data["tickers"])
    elif tier in config:
        tier_data = config[tier]
        for category, data in tier_data.items():
            if isinstance(data, dict) and "tickers" in data:
                tickers.extend(data["tickers"])
    else:
        raise ValueError(f"Unknown tier: {tier}")

    # Remove duplicates while preserving order
    seen = set()
    unique_tickers = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique_tickers.append(t)

    return unique_tickers


# ============================================================================
# Checkpoint Functions
# ============================================================================

def get_checkpoint_path(output_dir: str) -> str:
    """Get the checkpoint file path."""
    return os.path.join(output_dir, 'ibkr_checkpoint.json')


def load_checkpoint(output_dir: str) -> Dict:
    """
    Load checkpoint from file.

    Returns:
        Dictionary with 'hourly_completed', '15min_completed', 'hourly_results', '15min_results'.
    """
    checkpoint_path = get_checkpoint_path(output_dir)
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
            logger.info(f"Loaded checkpoint: {len(checkpoint.get('hourly_completed', []))} hourly, "
                       f"{len(checkpoint.get('15min_completed', []))} 15-min tickers completed")
            return checkpoint
    return {
        'hourly_completed': [],
        '15min_completed': [],
        'hourly_results': {},
        '15min_results': {},
        'started_at': datetime.now().isoformat(),
    }


def save_checkpoint(
    output_dir: str,
    hourly_completed: List[str],
    minute_completed: List[str],
    hourly_results: Dict[str, int],
    minute_results: Dict[str, int],
) -> None:
    """Save checkpoint to file."""
    checkpoint = {
        'hourly_completed': hourly_completed,
        '15min_completed': minute_completed,
        'hourly_results': hourly_results,
        '15min_results': minute_results,
        'updated_at': datetime.now().isoformat(),
    }
    checkpoint_path = get_checkpoint_path(output_dir)
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint, f, indent=2)


def clear_checkpoint(output_dir: str) -> None:
    """Remove checkpoint file after successful completion."""
    checkpoint_path = get_checkpoint_path(output_dir)
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
        logger.info("Checkpoint cleared (collection complete)")


# ============================================================================
# Incremental Update Functions
# ============================================================================

def get_last_datetime_from_csv(csv_path: str) -> Optional[datetime]:
    """
    Get the last datetime from an existing CSV file.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        The last datetime in the file, or None if file doesn't exist or is empty.
    """
    if not os.path.exists(csv_path):
        return None

    try:
        df = pd.read_csv(csv_path)
        if df.empty or 'datetime' not in df.columns:
            return None

        # Parse the last datetime
        last_dt_str = df['datetime'].iloc[-1]
        # Handle both ISO format and other formats
        try:
            return datetime.fromisoformat(last_dt_str.replace('Z', '+00:00'))
        except ValueError:
            return pd.to_datetime(last_dt_str).to_pydatetime()
    except Exception as e:
        logger.warning(f"Error reading {csv_path}: {e}")
        return None


def find_existing_price_files(output_dir: str, ticker: str, data_type: str) -> List[str]:
    """
    Find existing price files for a ticker.

    Args:
        output_dir: Base output directory (e.g., data/prices/).
        ticker: Stock ticker symbol.
        data_type: Either 'hourly' or '15min'.

    Returns:
        List of matching file paths.
    """
    subdir = os.path.join(output_dir, data_type)
    if not os.path.exists(subdir):
        return []

    pattern = f"{ticker}_{data_type.replace('min', 'min')}_"
    files = [
        os.path.join(subdir, f)
        for f in os.listdir(subdir)
        if f.startswith(f"{ticker}_") and f.endswith('.csv')
    ]
    return sorted(files)


def get_incremental_start_date(
    output_dir: str,
    ticker: str,
    data_type: str,
    default_start: date
) -> date:
    """
    Determine the start date for incremental update.

    Args:
        output_dir: Base output directory.
        ticker: Stock ticker symbol.
        data_type: Either 'hourly' or '15min'.
        default_start: Default start date if no existing data.

    Returns:
        The date to start fetching from (day after last existing data).
    """
    files = find_existing_price_files(output_dir, ticker, data_type)

    if not files:
        return default_start

    # Check all files and find the latest datetime
    latest_dt = None
    for f in files:
        last_dt = get_last_datetime_from_csv(f)
        if last_dt and (latest_dt is None or last_dt > latest_dt):
            latest_dt = last_dt

    if latest_dt is None:
        return default_start

    # Return the next day to avoid overlap
    return (latest_dt + timedelta(days=1)).date()


def merge_price_data(existing_path: str, new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge new price data with existing data, removing duplicates.

    Args:
        existing_path: Path to existing CSV file.
        new_df: New data DataFrame.

    Returns:
        Merged DataFrame with duplicates removed.
    """
    if os.path.exists(existing_path):
        existing_df = pd.read_csv(existing_path)
        # Combine and remove duplicates based on datetime and ticker
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['datetime', 'ticker'], keep='last')
        combined = combined.sort_values('datetime').reset_index(drop=True)
        return combined
    return new_df


def get_incremental_status(output_dir: str, tickers: List[str]) -> Dict[str, Dict]:
    """
    Get the incremental update status for all tickers.

    Args:
        output_dir: Base output directory.
        tickers: List of ticker symbols.

    Returns:
        Dictionary with status info for each ticker.
    """
    status = {}
    for ticker in tickers:
        hourly_files = find_existing_price_files(output_dir, ticker, 'hourly')
        minute_files = find_existing_price_files(output_dir, ticker, '15min')

        hourly_last = None
        for f in hourly_files:
            dt = get_last_datetime_from_csv(f)
            if dt and (hourly_last is None or dt > hourly_last):
                hourly_last = dt

        minute_last = None
        for f in minute_files:
            dt = get_last_datetime_from_csv(f)
            if dt and (minute_last is None or dt > minute_last):
                minute_last = dt

        status[ticker] = {
            'hourly_last': hourly_last.isoformat() if hourly_last else None,
            '15min_last': minute_last.isoformat() if minute_last else None,
            'hourly_files': len(hourly_files),
            '15min_files': len(minute_files),
        }

    return status


# ============================================================================
# Data Collection Functions
# ============================================================================

def collect_hourly_data(
    ibkr,
    tickers: List[str],
    start_date: date,
    end_date: date,
    output_dir: str,
) -> Dict[str, int]:
    """
    Collect 1-hour bar data for specified date range.

    Args:
        ibkr: IBKRDataSource instance.
        tickers: List of tickers to collect.
        start_date: Start date.
        end_date: End date.
        output_dir: Directory to save CSV files.

    Returns:
        Dictionary of ticker -> bar count.
    """
    results = {}
    os.makedirs(output_dir, exist_ok=True)

    for ticker in tickers:
        logger.info(f"Collecting 1-hour data for {ticker}: {start_date} to {end_date}")

        try:
            bars = ibkr.fetch_historical_intraday(
                tickers=[ticker],
                start_date=start_date,
                end_date=end_date,
                interval='1 hour',
                include_extended=False,
            )

            ticker_bars = bars.get(ticker, [])
            results[ticker] = len(ticker_bars)

            if ticker_bars:
                # Convert to DataFrame and save
                df = pd.DataFrame([
                    {
                        'datetime': bar.datetime.isoformat() if hasattr(bar.datetime, 'isoformat') else str(bar.datetime),
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume,
                        'ticker': bar.ticker,
                    }
                    for bar in ticker_bars
                ])

                output_path = os.path.join(output_dir, f"{ticker}_hourly_{start_date.year}.csv")
                df.to_csv(output_path, index=False)
                logger.info(f"  Saved {len(ticker_bars)} bars to {output_path}")
            else:
                logger.warning(f"  No data for {ticker}")

        except Exception as e:
            logger.error(f"  Error collecting {ticker}: {e}")
            results[ticker] = 0

    return results


def collect_15min_data(
    ibkr,
    tickers: List[str],
    start_date: date,
    end_date: date,
    output_dir: str,
) -> Dict[str, int]:
    """
    Collect 15-minute bar data for specified date range.

    Args:
        ibkr: IBKRDataSource instance.
        tickers: List of tickers to collect.
        start_date: Start date.
        end_date: End date.
        output_dir: Directory to save CSV files.

    Returns:
        Dictionary of ticker -> bar count.
    """
    results = {}
    os.makedirs(output_dir, exist_ok=True)

    for ticker in tickers:
        logger.info(f"Collecting 15-min data for {ticker}: {start_date} to {end_date}")

        try:
            bars = ibkr.fetch_historical_intraday(
                tickers=[ticker],
                start_date=start_date,
                end_date=end_date,
                interval='15 mins',
                include_extended=False,
            )

            ticker_bars = bars.get(ticker, [])
            results[ticker] = len(ticker_bars)

            if ticker_bars:
                # Convert to DataFrame and save
                df = pd.DataFrame([
                    {
                        'datetime': bar.datetime.isoformat() if hasattr(bar.datetime, 'isoformat') else str(bar.datetime),
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume,
                        'ticker': bar.ticker,
                    }
                    for bar in ticker_bars
                ])

                output_path = os.path.join(output_dir, f"{ticker}_15min_{start_date.year}_{end_date.year}.csv")
                df.to_csv(output_path, index=False)
                logger.info(f"  Saved {len(ticker_bars)} bars to {output_path}")
            else:
                logger.warning(f"  No data for {ticker}")

        except Exception as e:
            logger.error(f"  Error collecting {ticker}: {e}")
            results[ticker] = 0

    return results


def generate_summary_report(
    hourly_results: Dict[str, int],
    minute_results: Dict[str, int],
    output_dir: str,
) -> None:
    """Generate collection summary report."""
    report = {
        'generated_at': datetime.now().isoformat(),
        'hourly_data': {
            'period': '2023',
            'interval': '1 hour',
            'tickers_collected': len([t for t, c in hourly_results.items() if c > 0]),
            'total_bars': sum(hourly_results.values()),
            'by_ticker': hourly_results,
        },
        '15min_data': {
            'period': '2024-present',
            'interval': '15 mins',
            'tickers_collected': len([t for t, c in minute_results.items() if c > 0]),
            'total_bars': sum(minute_results.values()),
            'by_ticker': minute_results,
        },
    }

    report_path = os.path.join(output_dir, 'collection_summary.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"\nCollection Summary saved to: {report_path}")
    logger.info(f"Hourly data: {report['hourly_data']['total_bars']} bars from {report['hourly_data']['tickers_collected']} tickers")
    logger.info(f"15-min data: {report['15min_data']['total_bars']} bars from {report['15min_data']['tickers_collected']} tickers")


def main():
    parser = argparse.ArgumentParser(
        description="Collect historical stock prices from IBKR"
    )
    parser.add_argument(
        '--output', type=str, default='data/prices/',
        help='Output directory for price data (default: data/prices/)'
    )
    parser.add_argument(
        '--tickers', type=str, default=None,
        help='Comma-separated list of tickers (overrides --tier)'
    )
    parser.add_argument(
        '--tier', type=str, default='tier1_core',
        choices=['tier1_core', 'tier2_expanded', 'all'],
        help='Ticker tier from config (default: tier1_core)'
    )
    parser.add_argument(
        '--config', type=str, default='config/tickers_core.json',
        help='Path to tickers configuration file'
    )
    parser.add_argument(
        '--host', type=str, default=None,
        help='IBKR TWS/Gateway host (default: from config/.env or 127.0.0.1)'
    )
    parser.add_argument(
        '--port', type=int, default=None,
        help='IBKR TWS/Gateway port (default: from config/.env or 7497)'
    )
    parser.add_argument(
        '--hourly-only', action='store_true',
        help='Only collect 2023 hourly data'
    )
    parser.add_argument(
        '--minute-only', action='store_true',
        help='Only collect 2024 15-minute data'
    )
    parser.add_argument(
        '--hourly-start', type=str, default='2023-01-01',
        help='Start date for hourly data collection (default: 2023-01-01)'
    )
    parser.add_argument(
        '--hourly-end', type=str, default='2023-12-31',
        help='End date for hourly data collection (default: 2023-12-31)'
    )
    parser.add_argument(
        '--minute-start', type=str, default='2024-01-01',
        help='Start date for 15-min data collection (default: 2024-01-01)'
    )
    parser.add_argument(
        '--minute-end', type=str, default=None,
        help='End date for 15-min data collection (default: today)'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be collected without making IBKR calls'
    )
    parser.add_argument(
        '--resume', action='store_true',
        help='Resume from last checkpoint (skip already collected tickers)'
    )
    parser.add_argument(
        '--clear-checkpoint', action='store_true',
        help='Clear existing checkpoint and start fresh'
    )
    parser.add_argument(
        '--incremental', action='store_true',
        help='Incremental update: only fetch data since last update, merge with existing'
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Show current data status for all tickers (no collection)'
    )
    parser.add_argument(
        '--verbose', action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        tickers = load_tickers_from_config(args.config, args.tier)

    logger.info(f"Loaded {len(tickers)} tickers: {tickers[:10]}{'...' if len(tickers) > 10 else ''}")

    # Parse dates
    hourly_start = date.fromisoformat(args.hourly_start)
    hourly_end = date.fromisoformat(args.hourly_end)
    minute_start = date.fromisoformat(args.minute_start)
    minute_end = date.fromisoformat(args.minute_end) if args.minute_end else date.today()

    # Status mode - show current data status
    if args.status:
        logger.info("\n=== DATA STATUS ===")
        status = get_incremental_status(args.output, tickers)

        # Count tickers with data
        has_hourly = sum(1 for s in status.values() if s['hourly_last'])
        has_minute = sum(1 for s in status.values() if s['15min_last'])

        logger.info(f"Tickers with hourly data: {has_hourly}/{len(tickers)}")
        logger.info(f"Tickers with 15-min data: {has_minute}/{len(tickers)}")

        # Show details for each ticker
        logger.info("\nPer-ticker status:")
        for ticker, s in sorted(status.items()):
            hourly_str = s['hourly_last'][:10] if s['hourly_last'] else 'None'
            minute_str = s['15min_last'][:10] if s['15min_last'] else 'None'
            logger.info(f"  {ticker}: hourly={hourly_str}, 15min={minute_str}")

        return

    # Dry run mode
    if args.dry_run:
        logger.info("\n=== DRY RUN MODE ===")
        logger.info(f"Tickers to collect: {tickers}")
        logger.info(f"Hourly data: {hourly_start} to {hourly_end}")
        logger.info(f"15-min data: {minute_start} to {minute_end}")
        logger.info(f"Output directory: {args.output}")

        # Estimate collection time
        num_tickers = len(tickers)
        hourly_requests = num_tickers * ((hourly_end - hourly_start).days // 365 + 1)
        minute_requests = num_tickers * ((minute_end - minute_start).days // 60 + 1)
        total_requests = hourly_requests + minute_requests
        estimated_time = total_requests * 1.5 / 60  # ~1.5 seconds per request

        logger.info(f"\nEstimated IBKR requests: {total_requests}")
        logger.info(f"Estimated time: {estimated_time:.1f} minutes")
        return

    # Import IBKR source (requires ib_insync)
    try:
        from data_sources import IBKRDataSource
    except ImportError as e:
        logger.error(f"Failed to import IBKRDataSource: {e}")
        logger.error("Make sure ib_insync is installed: pip install ib_insync")
        sys.exit(1)

    # Create output directories
    hourly_dir = os.path.join(args.output, 'hourly')
    minute_dir = os.path.join(args.output, '15min')
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(hourly_dir, exist_ok=True)
    os.makedirs(minute_dir, exist_ok=True)

    # Handle checkpoint
    if args.clear_checkpoint:
        clear_checkpoint(args.output)
        logger.info("Checkpoint cleared, starting fresh")

    # Load checkpoint if resuming
    checkpoint = load_checkpoint(args.output) if args.resume else {
        'hourly_completed': [],
        '15min_completed': [],
        'hourly_results': {},
        '15min_results': {},
    }

    hourly_completed = set(checkpoint.get('hourly_completed', []))
    minute_completed = set(checkpoint.get('15min_completed', []))
    hourly_results = checkpoint.get('hourly_results', {})
    minute_results = checkpoint.get('15min_results', {})

    # Filter out already completed tickers
    hourly_tickers = [t for t in tickers if t not in hourly_completed] if not args.minute_only else []
    minute_tickers = [t for t in tickers if t not in minute_completed] if not args.hourly_only else []

    if args.resume:
        logger.info(f"Resuming: {len(hourly_tickers)} hourly tickers remaining, "
                   f"{len(minute_tickers)} 15-min tickers remaining")

    if not hourly_tickers and not minute_tickers:
        logger.info("All tickers already collected! Use --clear-checkpoint to start fresh.")
        generate_summary_report(hourly_results, minute_results, args.output)
        return

    # Load IBKR config from .env (command line args override)
    ibkr_config = load_ibkr_config_from_env()
    ibkr_host = args.host if args.host else ibkr_config['IBKR_HOST']
    ibkr_port = args.port if args.port else int(ibkr_config['IBKR_PORT'])
    ibkr_client_id = int(ibkr_config['IBKR_CLIENT_ID'])

    # Connect to IBKR
    logger.info(f"\nConnecting to IBKR at {ibkr_host}:{ibkr_port} (client_id={ibkr_client_id})...")

    interrupted = False
    try:
        with IBKRDataSource(host=ibkr_host, port=ibkr_port, client_id=ibkr_client_id) as ibkr:
            # Validate connection
            if not ibkr.validate_credentials():
                logger.error("Failed to validate IBKR connection")
                sys.exit(1)

            logger.info("Connected to IBKR successfully")

            # Collect hourly data (2023)
            if hourly_tickers and not args.minute_only:
                logger.info(f"\n{'='*60}")
                logger.info(f"Collecting HOURLY data: {hourly_start} to {hourly_end}")
                logger.info(f"Tickers: {len(hourly_tickers)} remaining")
                logger.info('='*60)

                for i, ticker in enumerate(hourly_tickers):
                    logger.info(f"[{i+1}/{len(hourly_tickers)}] Collecting 1-hour data for {ticker}")

                    try:
                        bars = ibkr.fetch_historical_intraday(
                            tickers=[ticker],
                            start_date=hourly_start,
                            end_date=hourly_end,
                            interval='1 hour',
                            include_extended=False,
                        )

                        ticker_bars = bars.get(ticker, [])
                        hourly_results[ticker] = len(ticker_bars)

                        if ticker_bars:
                            df = pd.DataFrame([
                                {
                                    'datetime': bar.datetime.isoformat() if hasattr(bar.datetime, 'isoformat') else str(bar.datetime),
                                    'open': bar.open,
                                    'high': bar.high,
                                    'low': bar.low,
                                    'close': bar.close,
                                    'volume': bar.volume,
                                    'ticker': bar.ticker,
                                }
                                for bar in ticker_bars
                            ])
                            output_path = os.path.join(hourly_dir, f"{ticker}_hourly_{hourly_start.year}.csv")
                            df.to_csv(output_path, index=False)
                            logger.info(f"  Saved {len(ticker_bars)} bars to {output_path}")
                        else:
                            logger.warning(f"  No data for {ticker}")

                        # Mark as completed and save checkpoint
                        hourly_completed.add(ticker)
                        save_checkpoint(args.output, list(hourly_completed), list(minute_completed),
                                       hourly_results, minute_results)

                    except KeyboardInterrupt:
                        logger.warning("\n\nInterrupted! Saving checkpoint...")
                        save_checkpoint(args.output, list(hourly_completed), list(minute_completed),
                                       hourly_results, minute_results)
                        interrupted = True
                        break
                    except Exception as e:
                        logger.error(f"  Error collecting {ticker}: {e}")
                        hourly_results[ticker] = 0

                if interrupted:
                    raise KeyboardInterrupt()

            # Collect 15-minute data (2024+)
            if minute_tickers and not args.hourly_only and not interrupted:
                logger.info(f"\n{'='*60}")
                if args.incremental:
                    logger.info(f"INCREMENTAL 15-MIN data update (from last data to {minute_end})")
                else:
                    logger.info(f"Collecting 15-MIN data: {minute_start} to {minute_end}")
                logger.info(f"Tickers: {len(minute_tickers)} remaining")
                logger.info('='*60)

                for i, ticker in enumerate(minute_tickers):
                    # Determine start date for this ticker
                    if args.incremental:
                        ticker_start = get_incremental_start_date(
                            args.output, ticker, '15min', minute_start
                        )
                        if ticker_start > minute_end:
                            logger.info(f"[{i+1}/{len(minute_tickers)}] {ticker}: already up to date (last: {ticker_start - timedelta(days=1)})")
                            minute_completed.add(ticker)
                            continue
                        logger.info(f"[{i+1}/{len(minute_tickers)}] {ticker}: incremental from {ticker_start} to {minute_end}")
                    else:
                        ticker_start = minute_start
                        logger.info(f"[{i+1}/{len(minute_tickers)}] Collecting 15-min data for {ticker}")

                    try:
                        bars = ibkr.fetch_historical_intraday(
                            tickers=[ticker],
                            start_date=ticker_start,
                            end_date=minute_end,
                            interval='15 mins',
                            include_extended=False,
                        )

                        ticker_bars = bars.get(ticker, [])

                        if ticker_bars:
                            df = pd.DataFrame([
                                {
                                    'datetime': bar.datetime.isoformat() if hasattr(bar.datetime, 'isoformat') else str(bar.datetime),
                                    'open': bar.open,
                                    'high': bar.high,
                                    'low': bar.low,
                                    'close': bar.close,
                                    'volume': bar.volume,
                                    'ticker': bar.ticker,
                                }
                                for bar in ticker_bars
                            ])

                            # For incremental mode, merge with existing data
                            output_path = os.path.join(minute_dir, f"{ticker}_15min_{minute_start.year}_{minute_end.year}.csv")
                            if args.incremental:
                                df = merge_price_data(output_path, df)
                                logger.info(f"  Merged {len(ticker_bars)} new bars (total: {len(df)} bars)")

                            df.to_csv(output_path, index=False)
                            minute_results[ticker] = len(df) if args.incremental else len(ticker_bars)

                            if not args.incremental:
                                logger.info(f"  Saved {len(ticker_bars)} bars to {output_path}")
                        else:
                            logger.warning(f"  No new data for {ticker}")
                            minute_results[ticker] = minute_results.get(ticker, 0)

                        # Mark as completed and save checkpoint
                        minute_completed.add(ticker)
                        save_checkpoint(args.output, list(hourly_completed), list(minute_completed),
                                       hourly_results, minute_results)

                    except KeyboardInterrupt:
                        logger.warning("\n\nInterrupted! Saving checkpoint...")
                        save_checkpoint(args.output, list(hourly_completed), list(minute_completed),
                                       hourly_results, minute_results)
                        interrupted = True
                        break
                    except Exception as e:
                        logger.error(f"  Error collecting {ticker}: {e}")
                        minute_results[ticker] = 0

    except ConnectionError as e:
        logger.error(f"Cannot connect to IBKR: {e}")
        logger.error("Make sure TWS or IB Gateway is running and API is enabled")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nCollection interrupted. Use --resume to continue later.")
        generate_summary_report(hourly_results, minute_results, args.output)
        sys.exit(0)

    # Generate summary
    generate_summary_report(hourly_results, minute_results, args.output)

    # Clear checkpoint on successful completion
    all_hourly_done = len(hourly_completed) >= len(tickers) or args.minute_only
    all_minute_done = len(minute_completed) >= len(tickers) or args.hourly_only
    if all_hourly_done and all_minute_done:
        clear_checkpoint(args.output)
        logger.info("\nCollection complete!")
    else:
        logger.info(f"\nPartial collection complete. Use --resume to continue.")


if __name__ == '__main__':
    main()