#!/usr/bin/env python3
"""
Daily Data Update Script - 每日資料更新統一入口

整合所有資料收集腳本，一鍵更新：
- Polygon 新聞 (增量更新)
- Finnhub 新聞 (最近 7 天)
- IBKR 股價 (增量更新，需要 TWS/Gateway 運行)

使用方式:
    # 查看所有資料狀態
    python daily_update.py --status

    # 更新所有新聞資料 (不包含股價)
    python daily_update.py --news

    # 更新所有資料 (包含股價，需要 IBKR 連線)
    python daily_update.py --all

    # 只更新 Polygon 新聞
    python daily_update.py --polygon

    # 只更新 Finnhub 新聞
    python daily_update.py --finnhub

    # 只更新 IBKR 股價
    python daily_update.py --ibkr

    # 模擬執行 (不實際收集)
    python daily_update.py --all --dry-run

    # 平行執行 (Polygon + Finnhub 同時跑，節省時間)
    python daily_update.py --news --parallel

    # 靜默模式 (適合 cron，不顯示進度)
    python daily_update.py --news --quiet
"""

import os
import sys
import json
import subprocess
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Script directory
SCRIPT_DIR = Path(__file__).parent


def run_command(cmd: list, dry_run: bool = False, stream_output: bool = True) -> tuple:
    """
    Execute a command and return (success, output).

    Args:
        cmd: Command and arguments as list.
        dry_run: If True, just print command without running.
        stream_output: If True, stream output in real-time (default: True).

    Returns:
        Tuple of (success: bool, output: str)
    """
    cmd_str = ' '.join(cmd)

    if dry_run:
        logger.info(f"[DRY RUN] Would execute: {cmd_str}")
        return True, "Dry run - no output"

    logger.info(f"Executing: {cmd_str}")

    try:
        if stream_output:
            # Stream output in real-time (user can see progress)
            result = subprocess.run(
                cmd,
                timeout=7200,  # 2 hour timeout
            )
            success = result.returncode == 0
            if not success:
                logger.error(f"Command failed with code {result.returncode}")
            return success, ""
        else:
            # Capture output (for background/silent mode)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200,
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                logger.error(f"Command failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr[:500]}")
                return False, result.stderr

    except subprocess.TimeoutExpired:
        logger.error("Command timed out")
        return False, "Timeout"
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False, str(e)


def run_commands_parallel(commands: list, dry_run: bool = False) -> Dict[str, bool]:
    """
    Execute multiple commands in parallel.

    Args:
        commands: List of (name, cmd_list) tuples.
        dry_run: If True, just print commands without running.

    Returns:
        Dict of {name: success} results.
    """
    if dry_run:
        for name, cmd in commands:
            logger.info(f"[DRY RUN] Would execute {name}: {' '.join(cmd)}")
        return {name: True for name, _ in commands}

    processes = {}
    results = {}

    # Start all processes
    for name, cmd in commands:
        logger.info(f"Starting {name}: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
            )
            processes[name] = proc
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")
            results[name] = False

    # Monitor all processes and stream output
    import select
    import sys

    active = dict(processes)
    while active:
        # Check each process
        for name, proc in list(active.items()):
            # Read available output
            while True:
                line = proc.stdout.readline()
                if line:
                    # Prefix output with source name
                    print(f"[{name}] {line.rstrip()}")
                    sys.stdout.flush()
                else:
                    break

            # Check if process finished
            if proc.poll() is not None:
                # Read remaining output
                for line in proc.stdout:
                    print(f"[{name}] {line.rstrip()}")
                results[name] = proc.returncode == 0
                if not results[name]:
                    logger.error(f"{name} failed with code {proc.returncode}")
                else:
                    logger.info(f"{name} completed successfully")
                del active[name]

        if active:
            import time
            time.sleep(0.1)

    return results


def get_polygon_status() -> Dict:
    """Get Polygon news data status."""
    data_dir = Path("data/news/raw/polygon")

    if not data_dir.exists():
        return {'exists': False, 'total_articles': 0, 'latest_date': None}

    total = 0
    latest_date = None

    try:
        import pandas as pd

        for year_dir in data_dir.iterdir():
            if not year_dir.is_dir():
                continue
            for pq in year_dir.glob("*.parquet"):
                df = pd.read_parquet(pq)
                total += len(df)

                if 'published_at' in df.columns:
                    df['_dt'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_dt = df['_dt'].max()
                    if pd.notna(max_dt):
                        if latest_date is None or max_dt > latest_date:
                            latest_date = max_dt
    except Exception as e:
        logger.warning(f"Error reading Polygon data: {e}")

    return {
        'exists': True,
        'total_articles': total,
        'latest_date': latest_date.date() if latest_date else None,
    }


def get_finnhub_status() -> Dict:
    """Get Finnhub news data status."""
    data_dir = Path("data/news/raw/finnhub")

    if not data_dir.exists():
        return {'exists': False, 'total_articles': 0, 'latest_date': None}

    total = 0
    latest_date = None

    try:
        import pandas as pd

        for year_dir in data_dir.iterdir():
            if not year_dir.is_dir():
                continue
            for pq in year_dir.glob("*.parquet"):
                df = pd.read_parquet(pq)
                total += len(df)

                if 'published_at' in df.columns:
                    df['_dt'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_dt = df['_dt'].max()
                    if pd.notna(max_dt):
                        if latest_date is None or max_dt > latest_date:
                            latest_date = max_dt
    except Exception as e:
        logger.warning(f"Error reading Finnhub data: {e}")

    return {
        'exists': True,
        'total_articles': total,
        'latest_date': latest_date.date() if latest_date else None,
    }


def get_ibkr_status() -> Dict:
    """Get IBKR price data status."""
    data_dir = Path("data/prices")

    if not data_dir.exists():
        return {'exists': False, 'total_bars': 0, 'latest_date': None, 'tickers': 0}

    total_bars = 0
    latest_date = None
    tickers = set()

    try:
        import pandas as pd

        for subdir in ['hourly', '15min']:
            sub_path = data_dir / subdir
            if not sub_path.exists():
                continue

            for csv in sub_path.glob("*.csv"):
                df = pd.read_csv(csv)
                total_bars += len(df)

                if 'ticker' in df.columns:
                    tickers.update(df['ticker'].unique())

                if 'datetime' in df.columns:
                    df['_dt'] = pd.to_datetime(df['datetime'], errors='coerce', utc=True)
                    max_dt = df['_dt'].max()
                    if pd.notna(max_dt):
                        if latest_date is None or max_dt > latest_date:
                            latest_date = max_dt
    except Exception as e:
        logger.warning(f"Error reading IBKR data: {e}")

    return {
        'exists': True,
        'total_bars': total_bars,
        'latest_date': latest_date.date() if latest_date else None,
        'tickers': len(tickers),
    }


def show_status():
    """Display status of all data sources."""
    logger.info("\n" + "=" * 70)
    logger.info("DATA STATUS SUMMARY")
    logger.info("=" * 70)

    today = date.today()

    # Polygon status
    polygon = get_polygon_status()
    if polygon['exists']:
        days_behind = (today - polygon['latest_date']).days if polygon['latest_date'] else '?'
        logger.info(f"\n📰 POLYGON NEWS:")
        logger.info(f"   Total articles: {polygon['total_articles']:,}")
        logger.info(f"   Latest data:    {polygon['latest_date']} ({days_behind} days ago)")
    else:
        logger.info(f"\n📰 POLYGON NEWS: No data found")

    # Finnhub status
    finnhub = get_finnhub_status()
    if finnhub['exists']:
        days_behind = (today - finnhub['latest_date']).days if finnhub['latest_date'] else '?'
        logger.info(f"\n📰 FINNHUB NEWS:")
        logger.info(f"   Total articles: {finnhub['total_articles']:,}")
        logger.info(f"   Latest data:    {finnhub['latest_date']} ({days_behind} days ago)")
        logger.info(f"   Note: Finnhub only provides ~7 days of history")
    else:
        logger.info(f"\n📰 FINNHUB NEWS: No data found")

    # IBKR status
    ibkr = get_ibkr_status()
    if ibkr['exists']:
        days_behind = (today - ibkr['latest_date']).days if ibkr['latest_date'] else '?'
        logger.info(f"\n📈 IBKR PRICES:")
        logger.info(f"   Total bars:     {ibkr['total_bars']:,}")
        logger.info(f"   Tickers:        {ibkr['tickers']}")
        logger.info(f"   Latest data:    {ibkr['latest_date']} ({days_behind} days ago)")
    else:
        logger.info(f"\n📈 IBKR PRICES: No data found")

    logger.info("\n" + "=" * 70)

    # Recommendations
    logger.info("\n📋 RECOMMENDED ACTIONS:")

    if not polygon['exists'] or (polygon['latest_date'] and (today - polygon['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --polygon")

    if not finnhub['exists'] or (finnhub['latest_date'] and (today - finnhub['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --finnhub")

    if not ibkr['exists'] or (ibkr['latest_date'] and (today - ibkr['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --ibkr (requires TWS/Gateway)")

    if polygon['exists'] and finnhub['exists']:
        if (polygon['latest_date'] and (today - polygon['latest_date']).days <= 1 and
            finnhub['latest_date'] and (today - finnhub['latest_date']).days <= 1):
            logger.info("   ✅ News data is up to date!")

    logger.info("")


def update_polygon(dry_run: bool = False) -> bool:
    """Run Polygon incremental update."""
    logger.info("\n" + "=" * 50)
    logger.info("UPDATING POLYGON NEWS")
    logger.info("=" * 50)

    script = SCRIPT_DIR / "collect_polygon_news.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [sys.executable, str(script), "--incremental"]
    success, output = run_command(cmd, dry_run)

    return success


def update_finnhub(dry_run: bool = False) -> bool:
    """Run Finnhub incremental update."""
    logger.info("\n" + "=" * 50)
    logger.info("UPDATING FINNHUB NEWS")
    logger.info("=" * 50)

    script = SCRIPT_DIR / "collect_finnhub_news.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [sys.executable, str(script), "--incremental"]
    success, output = run_command(cmd, dry_run)

    return success


def update_ibkr(dry_run: bool = False) -> bool:
    """Run IBKR incremental update."""
    logger.info("\n" + "=" * 50)
    logger.info("UPDATING IBKR PRICES")
    logger.info("=" * 50)

    script = SCRIPT_DIR / "collect_ibkr_prices.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [sys.executable, str(script), "--incremental", "--minute-only"]

    if dry_run:
        cmd.append("--dry-run")

    success, output = run_command(cmd, dry_run=False)  # Always run, script handles dry-run

    return success


def main():
    parser = argparse.ArgumentParser(
        description='Daily Data Update - Unified scheduler for all data collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show all data status
    python daily_update.py --status

    # Update all news (Polygon + Finnhub)
    python daily_update.py --news

    # Update everything (news + prices)
    python daily_update.py --all

    # Update specific source
    python daily_update.py --polygon
    python daily_update.py --finnhub
    python daily_update.py --ibkr

    # Dry run (show what would be done)
    python daily_update.py --all --dry-run

Cron example (daily at 6 AM):
    0 6 * * * cd /path/to/project && python scripts/collection/daily_update.py --news
        """
    )

    parser.add_argument('--status', action='store_true',
                       help='Show current data status for all sources')
    parser.add_argument('--all', action='store_true',
                       help='Update all sources (news + prices)')
    parser.add_argument('--news', action='store_true',
                       help='Update all news sources (Polygon + Finnhub)')
    parser.add_argument('--polygon', action='store_true',
                       help='Update Polygon news only')
    parser.add_argument('--finnhub', action='store_true',
                       help='Update Finnhub news only')
    parser.add_argument('--ibkr', action='store_true',
                       help='Update IBKR prices only')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without executing')
    parser.add_argument('--parallel', action='store_true',
                       help='Run news sources in parallel (faster but mixed output)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress subprocess output (for cron/background)')

    args = parser.parse_args()

    # Default to status if no action specified
    if not any([args.status, args.all, args.news, args.polygon, args.finnhub, args.ibkr]):
        args.status = True

    if args.status:
        show_status()
        return

    # Track results
    results = {}

    start_time = datetime.now()
    logger.info(f"\n{'#' * 70}")
    logger.info(f"DAILY UPDATE STARTED: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'#' * 70}")

    if args.dry_run:
        logger.info("*** DRY RUN MODE - No actual collection ***")

    if args.parallel:
        logger.info("*** PARALLEL MODE - Running sources concurrently ***")

    # Determine which sources to update
    update_polygon_flag = args.all or args.news or args.polygon
    update_finnhub_flag = args.all or args.news or args.finnhub
    update_ibkr_flag = args.all or args.ibkr

    # Parallel execution for news sources
    if args.parallel and (update_polygon_flag or update_finnhub_flag):
        commands = []

        if update_polygon_flag:
            script = SCRIPT_DIR / "collect_polygon_news.py"
            if script.exists():
                commands.append(("polygon", [sys.executable, str(script), "--incremental"]))

        if update_finnhub_flag:
            script = SCRIPT_DIR / "collect_finnhub_news.py"
            if script.exists():
                commands.append(("finnhub", [sys.executable, str(script), "--incremental"]))

        if commands:
            logger.info(f"\nStarting {len(commands)} news collectors in parallel...")
            parallel_results = run_commands_parallel(commands, args.dry_run)
            results.update(parallel_results)

        # IBKR runs separately (needs dedicated connection)
        if update_ibkr_flag:
            results['ibkr'] = update_ibkr(args.dry_run)

    else:
        # Sequential execution (default)
        if update_polygon_flag:
            results['polygon'] = update_polygon(args.dry_run)

        if update_finnhub_flag:
            results['finnhub'] = update_finnhub(args.dry_run)

        if update_ibkr_flag:
            results['ibkr'] = update_ibkr(args.dry_run)

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    logger.info(f"\n{'#' * 70}")
    logger.info(f"DAILY UPDATE COMPLETED: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Duration: {duration}")
    logger.info(f"{'#' * 70}")

    logger.info("\nRESULTS:")
    for source, success in results.items():
        status = "✅ Success" if success else "❌ Failed"
        logger.info(f"  {source}: {status}")

    # Show final status
    if not args.dry_run:
        show_status()

    # Exit code
    if all(results.values()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()