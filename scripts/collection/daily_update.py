#!/usr/bin/env python3
"""
Daily Data Update - thin CLI wrapper over the app scheduler core (3e-E)

定位 (2026-06, F6 落定): 這是 app scheduler 的 CLI 薄包裝，不再自帶編排。每個
source 都走 src/service/data_scheduler.run_source() —— 與 app Settings 的
「Run now」完全同一條路：同 per-source 鎖（重疊直接 skip）、同 IBKR Gateway 鎖
（序列化）、同 job_runs telemetry（collect.<source>，trigger='cli'）、同
collect → PG sync → 本地鏡像 流程。news 來源在進程內跑（adapter），IBKR 來源
維持 subprocess（進程隔離）。

CLI 與 app 跨進程共用 file lock（data/locks/，flock）：同一 source 重疊會直接
skip，IBKR Gateway 跨進程序列化（等待，最長 30 分鐘）。app 排程開啟時手動跑同一
source 不會雙抓——但會被 skip，所以仍建議錯開。

使用方式:
    # 查看所有資料狀態
    python daily_update.py --status

    # 更新所有新聞 (顯式 scope 必填——tickers_core.json 已非 runtime 預設)
    python daily_update.py --news --scope active-universe

    # 更新所有新聞 + 股價 (--all 不含 IV)
    python daily_update.py --all --scope active-universe

    # 單一 source / 顯式清單
    python daily_update.py --polygon --scope active-universe
    python daily_update.py --ibkr-prices --tickers AAPL,MSFT,NVDA

    # 模擬執行 (印出 per-source 計畫，不碰 IBKR/DB/job_runs)
    python daily_update.py --all --scope active-universe --dry-run

    # 收集後同步 PG + 本地鏡像（不加 --sync-db 則純收集：只寫 Parquet，
    # 不碰 PG 也不動本地鏡像）
    python daily_update.py --all --scope active-universe --sync-db

    # 同步多模型 news_scores（opt-in，與 --news/--sync-db 脫鉤；唯一仍是
    # 獨立 subprocess 的步驟）
    python daily_update.py --scores

重要限制 — 新 Ticker 的歷史資料:
    --all / --news 底層用 --incremental，以「全域最新文章時間」為起點。
    新加入的 ticker 不會被自動補抓歷史新聞。補抓方式 (Polygon 為例):
        python scripts/collection/collect_polygon_news.py \\
            --tickers GM,NEM,AFRM --start 2022-01-01
"""

import os
import sys
import json
import subprocess
import logging
import argparse
from datetime import datetime, date, timezone
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


class _RunTelemetry:
    """Best-effort job_runs telemetry for the backfill runner (slice 3e-B).

    Before this, a failed collection run left ZERO queryable trace (the only
    signal was the process exit code). Each step now lands one terminal-state
    ``job_runs`` row (``daily_update.<step>``, trigger_source='cli') via
    record_completed_run — the same terminal-only pattern the Chrome extension
    uses. STRICTLY additive: never raises, never alters flags/exit-code
    semantics, and is fully disabled on --dry-run (dry runs must not touch the
    DB — protected contract). The app's provider-health/ops views read these
    rows; the runner itself behaves byte-identically.
    """

    def __init__(self, enabled: bool, payload: Dict):
        self._store = None
        self._payload = payload
        if not enabled:
            return
        try:
            from src.service.job_runs_store import JobRunsStore
            from src.tools.data_access import DataAccessLayer

            store = JobRunsStore(DataAccessLayer(db_dsn="auto"))
            if store.is_available():
                self._store = store
            else:
                logger.debug("job telemetry: no DB backend — runs will not be recorded")
        except Exception as e:  # noqa: BLE001 — telemetry must never break the runner
            logger.debug(f"job telemetry unavailable: {e}")

    def record(self, step: str, ok: bool, started_at: datetime,
               finished_at: Optional[datetime] = None) -> None:
        if self._store is None:
            return
        try:
            self._store.record_completed_run(
                f"daily_update.{step}",
                status="succeeded" if ok else "failed",
                started_at=started_at,
                finished_at=finished_at or datetime.now(timezone.utc),
                trigger_source="cli",
                payload=self._payload,
                error=None if ok else "step failed (non-zero exit); see runner output",
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"job telemetry record failed for {step}: {e}")

    def timed(self, step: str, fn, *args, **kwargs) -> bool:
        """Run one step, record its outcome with real timing, return it unchanged."""
        t0 = datetime.now(timezone.utc)
        ok = fn(*args, **kwargs)
        self.record(step, bool(ok), t0)
        return ok


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
        logger.info("   - Run: python daily_update.py --ibkr-prices --scope active-universe (requires TWS/Gateway)")

    if polygon['exists'] and finnhub['exists'] and ibkr_news['exists']:
        if (polygon['latest_date'] and (today - polygon['latest_date']).days <= 1 and
            finnhub['latest_date'] and (today - finnhub['latest_date']).days <= 1 and
            ibkr_news['latest_date'] and (today - ibkr_news['latest_date']).days <= 1):
            logger.info("   ✅ News data is up to date!")

    logger.info("")


def _sync_scores(dry_run: bool = False) -> bool:
    """Push multi-model news_scores to the DB (opt-in, decoupled from --news /
    --sync-db — locked Q6). The ONE step that stays a subprocess in the thin
    wrapper: scores are not a scheduler source."""
    migrate_script = SCRIPT_DIR.parent / "migrate_to_supabase.py"
    if not migrate_script.exists():
        logger.error(f"Migration script not found: {migrate_script}")
        return False
    logger.info("\nSyncing news scores to database...")
    success, _ = run_command([sys.executable, str(migrate_script), "--scores"], dry_run)
    return success


def main():
    parser = argparse.ArgumentParser(
        description='Daily Data Update - thin CLI wrapper over the app scheduler core',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show all data status
    python daily_update.py --status

    # Update all news (Polygon + Finnhub + IBKR news)
    python daily_update.py --news --scope active-universe

    # Update all news + prices (explicit scope required; nothing guesses)
    python daily_update.py --all --scope active-universe

    # Update specific source
    python daily_update.py --polygon --scope active-universe
    python daily_update.py --ibkr-prices --tickers AAPL,MSFT
    python daily_update.py --iv-history --scope active-universe   # heavy, opt-in (NOT in --all)

    # Dry run (prints the per-source plan; never touches IBKR/DB)
    python daily_update.py --all --scope active-universe --dry-run

    # Collect and sync to DB in one step
    python daily_update.py --all --scope active-universe --sync-db
    python daily_update.py --scores                  # sync news_scores (opt-in, separate)

Note: IBKR sources require TWS/Gateway running.
      Every run is the SAME code path as the app's Run now (per-source locks,
      IBKR serialization, job_runs telemetry collect.<source> trigger='cli').
      Locks are CROSS-PROCESS (flock under data/locks/): overlapping the app
      scheduler skips the run instead of double-fetching; IBKR serializes.
      Without --sync-db a run is TRUE collect-only (Parquet only — no PG sync,
      no local-mirror refresh).
      Explicit scope (--tickers / --scope active-universe) is required —
      config/tickers_core.json serves no runtime default in this path (legacy
      touchpoints remain elsewhere: SA native-host ticker sync writes tier3;
      orphan collectors + --tier debug flags still read it).
        """
    )

    parser.add_argument('--status', action='store_true',
                       help='Show current data status for all sources')
    parser.add_argument('--all', action='store_true',
                       help='Update all news sources + prices (needs --scope/--tickers; IV is separate)')
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
                       help='Run sources concurrently (per-source/IBKR locks still apply)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress collector output (for background runs)')
    parser.add_argument('--sync-db', action='store_true',
                       help='Sync collected data to database after collection')
    parser.add_argument('--scores', action='store_true',
                       help='Sync multi-model news_scores to DB (opt-in; decoupled from --news/--sync-db)')
    parser.add_argument('--tickers', type=str, default=None,
                       help='Explicit comma-separated ticker scope (overrides --scope)')
    parser.add_argument('--scope', choices=['active-universe'], default=None,
                       help='Ticker scope: active-universe reads the local profile DB (read-only)')

    args = parser.parse_args()

    args.ibkr_news = getattr(args, 'ibkr_news', False)
    args.ibkr_prices = getattr(args, 'ibkr_prices', False)
    args.iv_history = getattr(args, 'iv_history', False)
    args.sync_db = getattr(args, 'sync_db', False)

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Default to status if no action specified (--scores is an action).
    if not any([args.status, args.all, args.news, args.polygon, args.finnhub,
                args.ibkr_news, args.ibkr_prices, args.iv_history, args.scores]):
        args.status = True

    if args.status:
        show_status()
        return

    # The ordered per-source plan (same step set as before the thin-wrapper
    # rewrite; IV stays opt-in, never swept by --all).
    sources: List[str] = []
    if args.all or args.news or args.polygon:
        sources.append("polygon_news")
    if args.all or args.news or args.finnhub:
        sources.append("finnhub_news")
    if args.all or args.news or args.ibkr_news:
        sources.append("ibkr_news")
    if args.all or args.ibkr_prices:
        sources.append("ibkr_prices")
    if args.iv_history:
        sources.append("iv_history")

    # Resolve the EXPLICIT scope once (Q7, now for every source: the collectors'
    # legacy tickers_core default is retired).
    tickers: Optional[List[str]] = None
    if sources:
        if args.tickers:
            tickers = [x.strip().upper() for x in args.tickers.split(',') if x.strip()]
        elif args.scope == 'active-universe':
            from src.universe_scope import resolve_active_universe
            tickers = resolve_active_universe()
            if not tickers:
                logger.error("active-universe scope is empty/unavailable (profile DB)")
                sys.exit(1)
        else:
            logger.error(
                "explicit ticker scope required: --tickers A,B,... or --scope "
                "active-universe (config/tickers_core.json is no longer a runtime default)")
            sys.exit(1)

    start_time = datetime.now()
    logger.info(f"\n{'#' * 70}")
    logger.info(f"DAILY UPDATE STARTED: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'#' * 70}")

    if args.dry_run:
        # Print the per-source plan and exit — a dry run never touches IBKR, the
        # DB, or job_runs (protected contract).
        logger.info("*** DRY RUN MODE - No actual collection ***")
        logger.info(f"\nPLAN (scope: {len(tickers or [])} tickers):")
        for s in sources:
            # without --sync-db the run is TRUE collect-only: Parquet only, no PG
            # sync and no local-mirror refresh (PG unchanged → nothing to mirror)
            steps = "collect -> db sync -> local mirror refresh" if args.sync_db else "collect (only)"
            logger.info(f"  {s}: {steps}")
        if args.scores:
            logger.info("  db_sync_scores: migrate_to_supabase --scores")
            _sync_scores(dry_run=True)
        logger.info("\nDry run complete (nothing executed).")
        sys.exit(0)

    from src.env_keys import ensure_env_loaded
    ensure_env_loaded()
    from src.service.data_scheduler import run_source

    telem = _RunTelemetry(enabled=True, payload={
        "flags": {k: bool(getattr(args, k, False)) for k in (
            "all", "news", "polygon", "finnhub", "ibkr_news", "ibkr_prices",
            "iv_history", "sync_db", "scores", "parallel")},
        "scope": args.scope,
        "tickers": args.tickers,
        "ticker_count": len(tickers or []),
    })
    run_started = datetime.now(timezone.utc)

    # Execute through the scheduler core — the SAME path as the app's Run now:
    # per-source locks (overlap skips), shared IBKR gateway lock, job_runs rows
    # collect.<source> trigger='cli', collect -> PG sync -> local mirror refresh.
    results: Dict[str, bool] = {}

    def _run(s: str) -> bool:
        r = run_source(s, trigger_source="cli", tickers=tickers,
                       skip_sync=not args.sync_db)
        if r.get("status") == "skipped":
            logger.warning(f"{s}: skipped — {r.get('reason')}")
            return False
        return r.get("status") == "succeeded"

    if args.parallel and sources:
        # Locks make this safe: news sources truly parallel, IBKR serialized.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            futures = {s: pool.submit(_run, s) for s in sources}
            for s, fut in futures.items():
                results[s] = fut.result()
    else:
        for s in sources:
            results[s] = _run(s)

    if args.scores:
        results['db_sync_scores'] = telem.timed('db_sync_scores', _sync_scores, False)

    # Summary
    end_time = datetime.now()
    logger.info(f"\n{'#' * 70}")
    logger.info(f"DAILY UPDATE COMPLETED: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Duration: {end_time - start_time}")
    logger.info(f"{'#' * 70}")

    logger.info("\nRESULTS:")
    for source, success in results.items():
        logger.info(f"  {source}: {'✅ Success' if success else '❌ Failed'}")

    show_status()

    # Whole-run summary row (the "last backfill" line the ops view shows); the
    # per-source rows are written by run_source as collect.<source>.
    telem.record("run", all(results.values()) if results else True, run_started)

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
