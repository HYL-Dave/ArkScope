#!/usr/bin/env python3
"""
統一新聞收集腳本

結合 Polygon (歷史) 和 Finnhub (即時) 的優勢:

| 來源 | 歷史深度 | 速度 | 用途 |
|------|---------|------|------|
| Polygon | 3+ 年 | 5/min | 歷史數據收集 |
| Finnhub | ~7 天 | 60/min | 即時/每日更新 |

使用方式:
    # 完整收集 (建議)
    # 1. 先用 Polygon 收集歷史 (需要很長時間)
    python collect_all_news.py --full-history

    # 2. 每日用 Finnhub 更新最新新聞 (快速)
    python collect_all_news.py --daily

    # 3. 合併兩個來源
    python collect_all_news.py --merge

    # 也可以分開執行:
    python collect_polygon_news.py --full-history
    python collect_finnhub_news.py
"""

import subprocess
import sys
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path
import json

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def collect_polygon_history(tickers: str = None, resume: bool = False):
    """Run Polygon historical collection."""
    logger.info("=" * 60)
    logger.info("Starting Polygon historical collection")
    logger.info("=" * 60)

    cmd = [sys.executable, "collect_polygon_news.py", "--full-history"]

    if tickers:
        cmd.extend(["--tickers", tickers])
    if resume:
        cmd.append("--resume")

    subprocess.run(cmd)


def collect_finnhub_recent(tickers: str = None, days: int = 7):
    """Run Finnhub recent news collection."""
    logger.info("=" * 60)
    logger.info("Starting Finnhub recent collection")
    logger.info("=" * 60)

    cmd = [sys.executable, "collect_finnhub_news.py", "--days", str(days)]

    if tickers:
        cmd.extend(["--tickers", tickers])

    subprocess.run(cmd)


def merge_sources():
    """Merge news from both sources with deduplication."""
    logger.info("=" * 60)
    logger.info("Merging news sources")
    logger.info("=" * 60)

    polygon_dir = Path("data/news/raw/polygon")
    finnhub_dir = Path("data/news/raw/finnhub")
    merged_dir = Path("data/news/merged")
    merged_dir.mkdir(parents=True, exist_ok=True)

    # Find all year-month combinations
    all_files = {}

    # Scan Polygon
    for parquet in polygon_dir.glob("*/*.parquet"):
        key = parquet.name  # e.g., "2024-01.parquet"
        if key not in all_files:
            all_files[key] = []
        all_files[key].append(('polygon', parquet))

    # Scan Finnhub
    for parquet in finnhub_dir.glob("*/*.parquet"):
        key = parquet.name
        if key not in all_files:
            all_files[key] = []
        all_files[key].append(('finnhub', parquet))

    # Merge each month
    total_merged = 0
    for key, sources in sorted(all_files.items()):
        dfs = []

        for source_name, path in sources:
            df = pd.read_parquet(path)
            df['_source'] = source_name
            dfs.append(df)
            logger.debug(f"  Loaded {len(df)} from {source_name}/{key}")

        # Combine
        combined = pd.concat(dfs, ignore_index=True)

        # Deduplicate by hash, prefer Polygon (has sentiment)
        # Sort so Polygon comes first
        combined['_priority'] = combined['source_api'].map({'polygon': 0, 'finnhub': 1})
        combined = combined.sort_values('_priority')
        combined = combined.drop_duplicates(subset=['dedup_hash'], keep='first')
        combined = combined.drop(columns=['_priority', '_source'])

        # Save
        year = key.split('-')[0]
        year_dir = merged_dir / year
        year_dir.mkdir(parents=True, exist_ok=True)

        output_path = year_dir / key
        combined.to_parquet(output_path, index=False, compression='snappy')

        logger.info(f"{key}: {len(combined)} articles (from {len(sources)} source(s))")
        total_merged += len(combined)

    logger.info(f"\nTotal merged: {total_merged} articles")
    logger.info(f"Output: {merged_dir}")


def show_stats():
    """Show collection statistics."""
    logger.info("=" * 60)
    logger.info("News Collection Statistics")
    logger.info("=" * 60)

    for source, data_dir in [
        ("Polygon", Path("data/news/raw/polygon")),
        ("Finnhub", Path("data/news/raw/finnhub")),
        ("Merged", Path("data/news/merged")),
    ]:
        if not data_dir.exists():
            continue

        total = 0
        files = list(data_dir.glob("*/*.parquet"))

        for parquet in files:
            df = pd.read_parquet(parquet)
            total += len(df)

        logger.info(f"\n{source}:")
        logger.info(f"  Files: {len(files)}")
        logger.info(f"  Articles: {total:,}")

        if files:
            # Date range
            dates = [f.stem for f in files]
            logger.info(f"  Range: {min(dates)} to {max(dates)}")


def main():
    parser = argparse.ArgumentParser(
        description='Unified news collection from multiple sources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('--full-history', action='store_true',
                        help='Run full Polygon historical collection (slow)')
    parser.add_argument('--daily', action='store_true',
                        help='Run Finnhub daily update (fast)')
    parser.add_argument('--merge', action='store_true',
                        help='Merge all sources')
    parser.add_argument('--stats', action='store_true',
                        help='Show collection statistics')
    parser.add_argument('--tickers', type=str,
                        help='Comma-separated tickers')
    parser.add_argument('--resume', action='store_true',
                        help='Resume Polygon collection from checkpoint')

    args = parser.parse_args()

    # If no action specified, show help
    if not any([args.full_history, args.daily, args.merge, args.stats]):
        parser.print_help()
        print("\n" + "=" * 60)
        print("Recommended workflow:")
        print("=" * 60)
        print("""
1. First time - collect historical data (takes ~10 hours):
   python collect_all_news.py --full-history

2. Daily update - collect recent news (takes ~1 minute):
   python collect_all_news.py --daily

3. Merge sources - combine and deduplicate:
   python collect_all_news.py --merge

4. Check status:
   python collect_all_news.py --stats
""")
        return

    if args.stats:
        show_stats()

    if args.full_history:
        collect_polygon_history(args.tickers, args.resume)

    if args.daily:
        collect_finnhub_recent(args.tickers)

    if args.merge:
        merge_sources()


if __name__ == "__main__":
    main()