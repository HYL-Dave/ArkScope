#!/usr/bin/env python3
"""
Daily Data Update Script - 每日資料更新統一入口

整合所有資料收集腳本，一鍵更新：
- Polygon 新聞 (增量更新，3+ 年歷史)
- Finnhub 新聞 (最近 7 天)
- IBKR 新聞 (增量更新，~1 個月歷史，高品質來源)
- IBKR 股價 (增量更新，需要 TWS/Gateway 運行)

使用方式:
    # 查看所有資料狀態
    python daily_update.py --status

    # 更新所有新聞資料 (不包含股價)
    python daily_update.py --news

    # 更新所有新聞 + 股價 (股價需顯式 scope，--all 不會自動猜)
    python daily_update.py --all --scope active-universe

    # 只更新 Polygon 新聞
    python daily_update.py --polygon

    # 只更新 Finnhub 新聞
    python daily_update.py --finnhub

    # 只更新 IBKR 新聞 (需要 TWS/Gateway)
    python daily_update.py --ibkr-news

    # 只更新 IBKR 股價 (需 TWS/Gateway + 顯式 scope)
    python daily_update.py --ibkr-prices --scope active-universe   # 讀 profile DB（唯讀）
    python daily_update.py --ibkr-prices --tickers AAPL,MSFT,NVDA  # 或顯式清單

    # 模擬執行 (不實際收集)
    python daily_update.py --all --dry-run

    # 平行執行 (Polygon + Finnhub 同時跑，節省時間)
    python daily_update.py --news --parallel

    # 靜默模式 (適合 cron，不顯示進度)
    python daily_update.py --news --quiet

    # 收集後自動同步到 DB
    python daily_update.py --ibkr-prices --scope active-universe --sync-db

    # 更新所有新聞並同步到 DB（不含 scores）
    python daily_update.py --news --sync-db

    # 同步多模型 news_scores 到 DB（opt-in，已與 --news/--sync-db 脫鉤）
    python daily_update.py --scores

定位 (2026-06): 這是「手動 / cron 的 backfill runner」，不是桌面 app 的持續同步器。
    它只寫遠端 PG，不寫任何 config（已移除舊的 user_profile.yaml → tickers_core.json
    回寫），也不碰本地 profile DB（--scope active-universe 僅唯讀讀取）。

重要限制 — 新 Ticker 的歷史資料:
    --all / --news 底層用 --incremental，以「全域最新文章時間」為起點。
    新加入的 ticker 不會被自動補抓歷史新聞，只會從「當前最新時間點之後」開始收集。

    補抓方式 (Polygon 為例，Finnhub 只有 7 天歷史影響不大):
        python scripts/collection/collect_polygon_news.py \\
            --tickers GM,NEM,AFRM --start 2022-01-01
"""

import os
import sys
import json
import subprocess
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Script directory
SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent.parent / "config"

# Repo root on sys.path so `--scope active-universe` can read the local
# profile-state DB (scripts/collection/ -> scripts/ -> repo root). Read-only.
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))


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
            # No total timeout - individual scripts handle their own per-request timeouts
            result = subprocess.run(cmd)
            success = result.returncode == 0
            if not success:
                logger.error(f"Command failed with code {result.returncode}")
            return success, ""
        else:
            # Capture output (for background/silent mode)
            # No total timeout - individual scripts handle their own per-request timeouts
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return True, result.stdout
            else:
                logger.error(f"Command failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr[:500]}")
                return False, result.stderr

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


def get_ibkr_news_status() -> Dict:
    """Get IBKR news data status."""
    data_dir = Path("data/news/raw/ibkr")

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
        logger.warning(f"Error reading IBKR news data: {e}")

    return {
        'exists': True,
        'total_articles': total,
        'latest_date': latest_date.date() if latest_date else None,
    }


def get_ibkr_prices_status() -> Dict:
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

    # IBKR news status
    ibkr_news = get_ibkr_news_status()
    if ibkr_news['exists'] and ibkr_news['total_articles'] > 0:
        days_behind = (today - ibkr_news['latest_date']).days if ibkr_news['latest_date'] else '?'
        logger.info(f"\n📰 IBKR NEWS (Dow Jones, Briefing, The Fly):")
        logger.info(f"   Total articles: {ibkr_news['total_articles']:,}")
        logger.info(f"   Latest data:    {ibkr_news['latest_date']} ({days_behind} days ago)")
        logger.info(f"   Note: IBKR provides ~1 month of high-quality news history")
    else:
        logger.info(f"\n📰 IBKR NEWS: No data found (requires TWS/Gateway)")

    # IBKR prices status
    ibkr_prices = get_ibkr_prices_status()
    if ibkr_prices['exists'] and ibkr_prices['total_bars'] > 0:
        days_behind = (today - ibkr_prices['latest_date']).days if ibkr_prices['latest_date'] else '?'
        logger.info(f"\n📈 IBKR PRICES:")
        logger.info(f"   Total bars:     {ibkr_prices['total_bars']:,}")
        logger.info(f"   Tickers:        {ibkr_prices['tickers']}")
        logger.info(f"   Latest data:    {ibkr_prices['latest_date']} ({days_behind} days ago)")
    else:
        logger.info(f"\n📈 IBKR PRICES: No data found (requires TWS/Gateway)")

    logger.info("\n" + "=" * 70)

    # Recommendations
    logger.info("\n📋 RECOMMENDED ACTIONS:")

    if not polygon['exists'] or (polygon['latest_date'] and (today - polygon['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --polygon")

    if not finnhub['exists'] or (finnhub['latest_date'] and (today - finnhub['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --finnhub")

    if not ibkr_news['exists'] or (ibkr_news['latest_date'] and (today - ibkr_news['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --ibkr-news (requires TWS/Gateway)")

    if not ibkr_prices['exists'] or (ibkr_prices['latest_date'] and (today - ibkr_prices['latest_date']).days > 1):
        logger.info("   - Run: python daily_update.py --ibkr-prices (requires TWS/Gateway)")

    if polygon['exists'] and finnhub['exists'] and ibkr_news['exists']:
        if (polygon['latest_date'] and (today - polygon['latest_date']).days <= 1 and
            finnhub['latest_date'] and (today - finnhub['latest_date']).days <= 1 and
            ibkr_news['latest_date'] and (today - ibkr_news['latest_date']).days <= 1):
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


def update_ibkr_news(dry_run: bool = False) -> bool:
    """Run IBKR news incremental update."""
    logger.info("\n" + "=" * 50)
    logger.info("UPDATING IBKR NEWS (Dow Jones, Briefing, The Fly)")
    logger.info("=" * 50)

    script = SCRIPT_DIR / "collect_ibkr_news.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [sys.executable, str(script), "--incremental"]
    success, output = run_command(cmd, dry_run)

    return success


def _resolve_price_scope(args) -> List[str]:
    """Resolve the EXPLICIT IBKR-price ticker scope (Q7: no implicit tier sweep).

    Returns the tickers from ``--tickers``, or — for ``--scope active-universe`` —
    the local profile-state active universe via a READ-ONLY read of
    ``profile_state.db`` (it never writes ``user_profile.yaml`` /
    ``tickers_core.json``). Returns ``[]`` when no scope was given; callers must
    NOT fall back to the retired ``--tier all`` universe.
    """
    if args.tickers:
        return [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if args.scope == "active-universe":
        try:
            from src.profile_state import ProfileStateStore
            db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
                SCRIPT_DIR.parent.parent / "data" / "profile_state.db"
            )
            tickers = ProfileStateStore(db_path).all_tickers()  # read-only
            logger.info(f"--scope active-universe → {len(tickers)} tickers from profile DB")
            return tickers
        except Exception as e:
            logger.error(f"--scope active-universe: could not read profile DB ({e})")
            return []
    return []


def update_ibkr_prices(tickers: List[str], dry_run: bool = False) -> bool:
    """Run IBKR price incremental update for an EXPLICIT ticker scope.

    The retired ``--tier all`` default is gone (it expanded the three retired
    tiers). The caller passes an explicit ticker list resolved from ``--tickers``
    or ``--scope active-universe``; ``--all`` never implicitly sweeps a universe.
    """
    logger.info("\n" + "=" * 50)
    logger.info("UPDATING IBKR PRICES")
    logger.info("=" * 50)

    if not tickers:
        logger.warning(
            "Skipping IBKR prices: no explicit scope. "
            "Pass --tickers <list> or --scope active-universe."
        )
        return False

    script = SCRIPT_DIR / "collect_ibkr_prices.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [
        sys.executable, str(script), "--incremental", "--minute-only",
        "--tickers", ",".join(tickers),
    ]

    if dry_run:
        cmd.append("--dry-run")

    success, output = run_command(cmd, dry_run=False)  # Always run, script handles dry-run

    return success


def update_iv_history(dry_run: bool = False) -> bool:
    """Run IV history collection."""
    logger.info("\n" + "=" * 50)
    logger.info("COLLECTING IV HISTORY")
    logger.info("=" * 50)

    script = SCRIPT_DIR / "collect_iv_history.py"
    if not script.exists():
        logger.error(f"Script not found: {script}")
        return False

    cmd = [sys.executable, str(script)]
    success, output = run_command(cmd, dry_run)

    return success


def sync_to_db(
    sync_news: bool = False,
    sync_prices: bool = False,
    sync_iv: bool = False,
    sync_scores: bool = False,
    dry_run: bool = False,
) -> Dict[str, bool]:
    """
    Sync collected data to database.

    Runs migrate_to_supabase.py with appropriate flags based on what was collected.

    Args:
        sync_news: Sync news data (polygon, finnhub, ibkr news)
        sync_prices: Sync price data (ibkr prices)
        sync_iv: Sync IV history data
        sync_scores: Sync multi-model news_scores (opt-in; decoupled from news)
        dry_run: Show what would be done without executing

    Returns:
        Dict of {data_type: success} results.
    """
    logger.info("\n" + "=" * 50)
    logger.info("SYNCING TO DATABASE")
    logger.info("=" * 50)

    # Locate the migration script
    migrate_script = SCRIPT_DIR.parent / "migrate_to_supabase.py"
    if not migrate_script.exists():
        logger.error(f"Migration script not found: {migrate_script}")
        return {}

    results = {}

    # Build command based on what needs to be synced
    # We run each type separately for clearer logging and error handling
    if sync_news:
        logger.info("\nSyncing news articles to database...")
        cmd = [sys.executable, str(migrate_script), "--news"]
        if dry_run:
            cmd.append("--dry-run")
        success, _ = run_command(cmd, dry_run=False)  # Always run, script handles dry-run
        results['db_sync_news'] = success

    if sync_scores:
        # Multi-model news_scores — opt-in, decoupled from the news sync above
        # (was previously force-pushed on every --news --sync-db).
        logger.info("\nSyncing news scores to database...")
        cmd = [sys.executable, str(migrate_script), "--scores"]
        if dry_run:
            cmd.append("--dry-run")
        success, _ = run_command(cmd, dry_run=False)
        results['db_sync_scores'] = success

    if sync_prices:
        logger.info("\nSyncing prices to database...")
        cmd = [sys.executable, str(migrate_script), "--prices"]
        if dry_run:
            cmd.append("--dry-run")
        success, _ = run_command(cmd, dry_run=False)
        results['db_sync_prices'] = success

    if sync_iv:
        logger.info("\nSyncing IV history to database...")
        cmd = [sys.executable, str(migrate_script), "--iv"]
        if dry_run:
            cmd.append("--dry-run")
        success, _ = run_command(cmd, dry_run=False)
        results['db_sync_iv'] = success

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Daily Data Update - Unified scheduler for all data collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show all data status
    python daily_update.py --status

    # Update all news (Polygon + Finnhub + IBKR news)
    python daily_update.py --news

    # Update everything (news + prices)
    python daily_update.py --all

    # Update specific source
    python daily_update.py --polygon
    python daily_update.py --finnhub
    python daily_update.py --ibkr-news     # High-quality: Dow Jones, Briefing, The Fly
    python daily_update.py --ibkr-prices   # Intraday price data

    # Dry run (show what would be done)
    python daily_update.py --all --dry-run

    # Collect and sync to DB in one step
    python daily_update.py --ibkr-prices --sync-db
    python daily_update.py --news --sync-db
    python daily_update.py --all --sync-db

Note: IBKR sources require TWS/Gateway running.
      --sync-db requires DATABASE_URL in config/.env
        """
    )

    parser.add_argument('--status', action='store_true',
                       help='Show current data status for all sources')
    parser.add_argument('--all', action='store_true',
                       help='Update all sources (news + prices)')
    parser.add_argument('--news', action='store_true',
                       help='Update all news sources (Polygon + Finnhub + IBKR news)')
    parser.add_argument('--polygon', action='store_true',
                       help='Update Polygon news only')
    parser.add_argument('--finnhub', action='store_true',
                       help='Update Finnhub news only')
    parser.add_argument('--ibkr-news', action='store_true',
                       help='Update IBKR news only (requires TWS/Gateway)')
    parser.add_argument('--ibkr-prices', action='store_true',
                       help='Update IBKR prices only (requires TWS/Gateway)')
    parser.add_argument('--iv-history', action='store_true',
                       help='Collect ATM IV history (requires TWS/Gateway)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without executing')
    parser.add_argument('--parallel', action='store_true',
                       help='Run news sources in parallel (faster but mixed output)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress subprocess output (for cron/background)')
    parser.add_argument('--sync-db', action='store_true',
                       help='Sync collected data to database after collection')
    parser.add_argument('--scores', action='store_true',
                       help='Sync multi-model news_scores to DB (opt-in; decoupled from --news/--sync-db)')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Explicit comma-separated ticker scope for IBKR prices (overrides --scope)')
    parser.add_argument('--scope', choices=['active-universe'], default=None,
                       help='IBKR-price scope: active-universe reads the local profile DB (read-only)')

    args = parser.parse_args()

    # Handle hyphenated arguments
    args.ibkr_news = getattr(args, 'ibkr_news', False)
    args.ibkr_prices = getattr(args, 'ibkr_prices', False)
    args.iv_history = getattr(args, 'iv_history', False)
    args.sync_db = getattr(args, 'sync_db', False)

    # Default to status if no action specified (--scores is an action: it pushes
    # scores to the DB on its own).
    if not any([args.status, args.all, args.news, args.polygon, args.finnhub,
                args.ibkr_news, args.ibkr_prices, args.iv_history, args.scores]):
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

    # (Removed: the old user_profile.yaml → tickers_core.json writeback. Lists
    # now live in the local profile DB; this batch runner never mutates config.)

    # Determine which sources to update
    update_polygon_flag = args.all or args.news or args.polygon
    update_finnhub_flag = args.all or args.news or args.finnhub
    update_ibkr_news_flag = args.all or args.news or args.ibkr_news
    update_ibkr_prices_flag = args.all or args.ibkr_prices
    update_iv_history_flag = args.all or args.iv_history

    # Resolve the EXPLICIT price scope once (Q7: --all never guesses a universe).
    price_tickers = _resolve_price_scope(args) if update_ibkr_prices_flag else []

    # Parallel execution for news sources (Polygon + Finnhub only, IBKR needs dedicated connection)
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
        if update_ibkr_news_flag:
            results['ibkr_news'] = update_ibkr_news(args.dry_run)
        if update_ibkr_prices_flag and price_tickers:
            results['ibkr_prices'] = update_ibkr_prices(price_tickers, args.dry_run)
        elif update_ibkr_prices_flag:
            logger.warning(
                "IBKR prices requested but no scope — skipping (not failing). "
                "Add --tickers <list> or --scope active-universe."
            )
        if update_iv_history_flag:
            results['iv_history'] = update_iv_history(args.dry_run)

    else:
        # Sequential execution (default)
        if update_polygon_flag:
            results['polygon'] = update_polygon(args.dry_run)

        if update_finnhub_flag:
            results['finnhub'] = update_finnhub(args.dry_run)

        if update_ibkr_news_flag:
            results['ibkr_news'] = update_ibkr_news(args.dry_run)

        if update_ibkr_prices_flag and price_tickers:
            results['ibkr_prices'] = update_ibkr_prices(price_tickers, args.dry_run)
        elif update_ibkr_prices_flag:
            logger.warning(
                "IBKR prices requested but no scope — skipping (not failing). "
                "Add --tickers <list> or --scope active-universe."
            )

        if update_iv_history_flag:
            results['iv_history'] = update_iv_history(args.dry_run)

    # Sync to database if requested. --sync-db syncs what was COLLECTED;
    # --scores is an independent opt-in (scores no longer ride on --news).
    if args.sync_db or args.scores:
        sync_news = args.sync_db and (update_polygon_flag or update_finnhub_flag or update_ibkr_news_flag)
        sync_prices = args.sync_db and update_ibkr_prices_flag and bool(price_tickers)
        sync_iv = args.sync_db and update_iv_history_flag
        sync_scores = args.scores  # opt-in, on its own flag

        if sync_news or sync_prices or sync_iv or sync_scores:
            sync_results = sync_to_db(
                sync_news=sync_news,
                sync_prices=sync_prices,
                sync_iv=sync_iv,
                sync_scores=sync_scores,
                dry_run=args.dry_run,
            )
            results.update(sync_results)
        else:
            logger.info("No data types to sync (nothing was collected)")

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