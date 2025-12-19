#!/usr/bin/env python3
"""
IBKR 新聞收集腳本

IBKR 特點:
- 需要 IB Gateway/TWS 連線 (非 REST API)
- 來源品質最高: Dow Jones, Briefing.com, The Fly
- 歷史深度: ~1 個月
- 每次查詢上限: 300 篇/股票
- 抓取速度: ~0.5 秒/股票 (比 Polygon 快 24 倍)

適合用於:
- 需要高品質新聞來源 (Dow Jones)
- 最近一個月的新聞補充
- 與 Polygon 新聞做交叉驗證

使用方式:
    # 收集最近 7 天新聞 (預設)
    python collect_ibkr_news.py

    # 收集最近 30 天
    python collect_ibkr_news.py --days 30

    # 收集指定日期範圍 (最遠約 1 個月)
    python collect_ibkr_news.py --start 2025-11-20 --end 2025-12-19

    # 僅收集指定股票
    python collect_ibkr_news.py --tickers AAPL,MSFT

    # 使用不同的 IB Gateway 連接
    python collect_ibkr_news.py --port 4001 --host 192.168.0.152

    # 查看現有資料狀態
    python collect_ibkr_news.py --status

    # 增量更新
    python collect_ibkr_news.py --incremental

需求:
    - IB Gateway 或 TWS 運行中
    - 新聞訂閱 (Dow Jones, The Fly, Briefing.com)
    - pip install ib_insync
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data_sources.ibkr_source import IBKRDataSource

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('collect_ibkr_news.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class IBKRConfig:
    """IBKR 收集設定"""
    # Connection settings
    host: str = "127.0.0.1"
    port: int = 4002  # 4002 = IB Gateway Paper, 4001 = IB Gateway Live
    client_id: int = 50  # Use a unique client ID for news collection
    timeout: int = 30

    # Collection settings
    max_articles_per_ticker: int = 300  # IBKR max
    max_history_days: int = 30  # IBKR typically has ~1 month

    # Storage paths
    data_dir: Path = Path("data/news/raw/ibkr")

    # Rate limiting (IBKR is fast, but be conservative)
    request_delay: float = 0.5


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class NewsArticle:
    """新聞文章資料結構"""
    article_id: str
    ticker: str
    title: str
    published_at: str
    source_api: str = "ibkr"

    description: str = ""
    content: str = ""
    url: str = ""

    publisher: str = ""
    author: str = ""

    related_tickers: str = ""
    tags: str = ""
    category: str = ""

    source_sentiment: Optional[float] = None
    source_sentiment_label: str = ""

    collected_at: str = ""
    content_length: int = 0
    dedup_hash: str = ""


# =============================================================================
# Storage Manager
# =============================================================================

class StorageManager:
    """管理 Parquet 檔案儲存"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Cache for dedup hashes
        self._hash_cache: Dict[Tuple[int, int], set] = {}

    def get_parquet_path(self, year: int, month: int) -> Path:
        """取得指定月份的 parquet 檔案路徑"""
        year_dir = self.data_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir / f"{year}-{month:02d}.parquet"

    def _load_hashes(self, year: int, month: int) -> set:
        """載入並快取 dedup hashes"""
        key = (year, month)
        if key in self._hash_cache:
            return self._hash_cache[key]

        path = self.get_parquet_path(year, month)
        if path.exists():
            df = pd.read_parquet(path, engine='pyarrow')
            hashes = set(df['dedup_hash'].tolist()) if 'dedup_hash' in df.columns else set()
        else:
            hashes = set()

        self._hash_cache[key] = hashes
        return hashes

    def save_articles(
        self,
        articles: List[NewsArticle],
        year: int,
        month: int,
        append: bool = True,
    ) -> int:
        """儲存文章到 parquet 檔案"""
        if not articles:
            return 0

        path = self.get_parquet_path(year, month)

        # Convert to DataFrame
        new_df = pd.DataFrame([asdict(a) for a in articles])

        # Load existing if appending
        if append and path.exists():
            existing_df = pd.read_parquet(path, engine='pyarrow')
            existing_hashes = set(existing_df['dedup_hash'].tolist())

            # Deduplicate by hash
            new_df = new_df[~new_df['dedup_hash'].isin(existing_hashes)]

            if len(new_df) == 0:
                logger.debug(f"  All articles already exist")
                return 0

            # Ensure consistent dtypes
            for col in new_df.columns:
                if col in existing_df.columns:
                    if existing_df[col].dtype != new_df[col].dtype:
                        try:
                            new_df[col] = new_df[col].astype(existing_df[col].dtype)
                        except (ValueError, TypeError):
                            pass

            # Append
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Save
        combined_df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"  Saved {len(new_df)} new articles (total: {len(combined_df)})")

        # Update hash cache
        key = (year, month)
        if key in self._hash_cache:
            self._hash_cache[key].update(set(new_df['dedup_hash'].tolist()))

        return len(new_df)

    def get_data_status(self) -> Dict[str, any]:
        """取得現有資料的狀態統計"""
        status = {
            'total_articles': 0,
            'total_files': 0,
            'date_range': {'earliest': None, 'latest': None},
            'by_year': {},
            'by_publisher': {},
        }

        if not self.data_dir.exists():
            return status

        earliest_date = None
        latest_date = None

        for year_dir in sorted(self.data_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            year = year_dir.name
            year_count = 0

            for parquet_file in year_dir.glob("*.parquet"):
                try:
                    df = pd.read_parquet(parquet_file, engine='pyarrow')
                    status['total_files'] += 1
                    status['total_articles'] += len(df)
                    year_count += len(df)

                    # Track by publisher
                    if 'publisher' in df.columns:
                        for pub, count in df['publisher'].value_counts().items():
                            status['by_publisher'][pub] = status['by_publisher'].get(pub, 0) + count

                    # Track date range
                    if 'published_at' in df.columns:
                        df['_pub_date'] = pd.to_datetime(df['published_at'], errors='coerce')
                        file_min = df['_pub_date'].min()
                        file_max = df['_pub_date'].max()

                        if pd.notna(file_min):
                            if earliest_date is None or file_min < earliest_date:
                                earliest_date = file_min
                        if pd.notna(file_max):
                            if latest_date is None or file_max > latest_date:
                                latest_date = file_max

                except Exception as e:
                    logger.warning(f"Error reading {parquet_file}: {e}")

            status['by_year'][year] = year_count

        status['date_range']['earliest'] = earliest_date.isoformat() if earliest_date else None
        status['date_range']['latest'] = latest_date.isoformat() if latest_date else None

        return status

    def get_latest_date(self) -> Optional[date]:
        """取得最新的發布日期"""
        if not self.data_dir.exists():
            return None

        for year_dir in sorted(self.data_dir.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue

            for parquet_file in sorted(year_dir.glob("*.parquet"), reverse=True):
                try:
                    df = pd.read_parquet(parquet_file, engine='pyarrow')
                    if df.empty or 'published_at' not in df.columns:
                        continue

                    df['_pub_date'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_dt = df['_pub_date'].max()

                    if pd.notna(max_dt):
                        return max_dt.date()

                except Exception as e:
                    logger.warning(f"Error reading {parquet_file}: {e}")

        return None


# =============================================================================
# IBKR News Collector
# =============================================================================

class IBKRNewsCollector:
    """IBKR 新聞收集器"""

    def __init__(self, config: IBKRConfig):
        self.config = config
        self.ibkr: Optional[IBKRDataSource] = None
        self.providers: List[Dict] = []

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_tickers': 0,
            'errors': 0,
            'by_provider': {},
        }

    def connect(self) -> bool:
        """建立 IBKR 連線"""
        try:
            self.ibkr = IBKRDataSource(
                host=self.config.host,
                port=self.config.port,
                client_id=self.config.client_id,
                timeout=self.config.timeout,
            )

            if not self.ibkr.connect():
                logger.error("Failed to connect to IB Gateway")
                return False

            # Get available providers
            self.providers = self.ibkr.get_news_providers()
            if not self.providers:
                logger.warning("No news providers available! Check your subscription.")
                return False

            logger.info(f"Connected. Available providers: {len(self.providers)}")
            for p in self.providers:
                logger.info(f"  - {p['code']}: {p['name']}")

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def disconnect(self):
        """斷開連線"""
        if self.ibkr:
            self.ibkr.disconnect()
            logger.info("Disconnected from IB Gateway")

    def fetch_news(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """抓取單一股票的新聞"""
        if not self.ibkr:
            raise RuntimeError("Not connected to IBKR")

        collected_at = datetime.now()
        articles = []

        try:
            # Use IBKR fetch_news method
            raw_articles = self.ibkr.fetch_news(
                tickers=[ticker],
                start_date=start_date,
                end_date=end_date,
                limit=self.config.max_articles_per_ticker,
            )

            for raw in raw_articles:
                # Parse the article
                pub_time = raw.published_date
                if isinstance(pub_time, datetime):
                    published_at = pub_time.isoformat() + 'Z'
                else:
                    published_at = str(pub_time)

                # Generate dedup hash
                pub_date = published_at[:10] if published_at else ''
                title = raw.title or ''
                hash_input = f"{ticker.upper()}|{title.strip().lower()}|{pub_date}"
                dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

                # Extract article_id from description if present
                article_id = dedup_hash
                if raw.description and '[Article ID:' in raw.description:
                    try:
                        start = raw.description.index('[Article ID: ') + 13
                        end = raw.description.index(']', start)
                        article_id = raw.description[start:end]
                    except ValueError:
                        pass

                # Track by provider
                provider = raw.source or 'unknown'
                self.stats['by_provider'][provider] = self.stats['by_provider'].get(provider, 0) + 1

                articles.append(NewsArticle(
                    article_id=article_id,
                    ticker=ticker,
                    title=title,
                    published_at=published_at,
                    source_api="ibkr",
                    description="",  # IBKR doesn't provide description in headlines
                    content="",
                    url=raw.url or "",
                    publisher=provider,
                    author="",
                    related_tickers=json.dumps([ticker]),
                    tags="",
                    category="",
                    source_sentiment=None,
                    source_sentiment_label="",
                    collected_at=collected_at.isoformat(),
                    content_length=0,
                    dedup_hash=dedup_hash,
                ))

            return articles

        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            self.stats['errors'] += 1
            return []


# =============================================================================
# Main Collection Logic
# =============================================================================

def load_tickers(tickers_arg: Optional[str] = None) -> List[str]:
    """Load tickers from config or argument."""
    if tickers_arg:
        return [t.strip().upper() for t in tickers_arg.split(',')]

    config_path = Path("config/tickers_core.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)

        settings = config.get('settings', {})
        tier_names = ['tier1_core']
        if settings.get('include_tier2', True):
            tier_names.append('tier2_expanded')
        if settings.get('include_tier3', True):
            tier_names.append('tier3_user_watchlist')

        tickers = set()
        for tier_name in tier_names:
            tier_data = config.get(tier_name, {})
            for category in tier_data.values():
                if isinstance(category, dict) and 'tickers' in category:
                    tickers.update(category['tickers'])

        tickers = sorted(list(tickers))
        if tickers:
            logger.info(f"Loaded {len(tickers)} tickers from config")
            return tickers

    # Fallback to key stocks
    return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']


def collect_news(
    tickers: List[str],
    start_date: date,
    end_date: date,
    config: IBKRConfig,
) -> dict:
    """Main collection function."""

    # Validate date range (IBKR has ~1 month history)
    max_lookback = config.max_history_days
    oldest_allowed = date.today() - timedelta(days=max_lookback)

    if start_date < oldest_allowed:
        logger.warning(f"IBKR typically has ~{max_lookback} days of history!")
        logger.warning(f"Adjusting start_date from {start_date} to {oldest_allowed}")
        start_date = oldest_allowed

    # Initialize
    collector = IBKRNewsCollector(config)
    storage = StorageManager(config.data_dir)

    # Connect
    if not collector.connect():
        logger.error("Failed to connect. Check IB Gateway is running.")
        sys.exit(1)

    try:
        target_year = end_date.year
        target_month = end_date.month

        logger.info(f"\nStarting IBKR news collection")
        logger.info(f"Tickers: {len(tickers)}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Storage: {config.data_dir}")

        all_articles = []
        start_time = time.time()

        for i, ticker in enumerate(tickers):
            progress = (i + 1) / len(tickers) * 100
            logger.info(f"[{progress:.1f}%] {ticker}")

            articles = collector.fetch_news(ticker, start_date, end_date)

            if articles:
                all_articles.extend(articles)
                logger.info(f"  Found {len(articles)} articles")
            else:
                logger.debug(f"  No articles")

            collector.stats['total_tickers'] += 1

            # Small delay between requests
            time.sleep(config.request_delay)

        # Save all articles
        if all_articles:
            saved = storage.save_articles(all_articles, target_year, target_month)
            collector.stats['total_articles'] = saved

        elapsed = time.time() - start_time

        # Final stats
        logger.info("\n" + "=" * 60)
        logger.info("Collection Complete")
        logger.info("=" * 60)
        logger.info(f"Total articles: {len(all_articles)}")
        logger.info(f"Saved (deduplicated): {collector.stats['total_articles']}")
        logger.info(f"Tickers processed: {collector.stats['total_tickers']}")
        logger.info(f"Errors: {collector.stats['errors']}")
        logger.info(f"Time elapsed: {elapsed:.1f}s ({len(tickers) / elapsed:.2f} tickers/sec)")

        if collector.stats['by_provider']:
            logger.info("\nBy provider:")
            for provider, count in sorted(collector.stats['by_provider'].items(), key=lambda x: -x[1]):
                logger.info(f"  {provider}: {count}")

        return collector.stats

    finally:
        collector.disconnect()


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Collect news from IBKR (requires IB Gateway)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Collect last 7 days for all tier1 stocks
    python collect_ibkr_news.py

    # Collect last 30 days (max ~1 month history)
    python collect_ibkr_news.py --days 30

    # Specific tickers
    python collect_ibkr_news.py --tickers AAPL,MSFT,GOOGL

    # Use different IB Gateway connection
    python collect_ibkr_news.py --host 192.168.0.152 --port 4001

    # Show data status
    python collect_ibkr_news.py --status

Note: IBKR provides ~1 month of news history with highest quality sources
      (Dow Jones, Briefing.com, The Fly). Requires news subscription.
        """
    )

    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--days', type=int, default=7, help='Days back from today (default: 7)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IB Gateway host')
    parser.add_argument('--port', type=int, default=4002, help='IB Gateway port (4001=live, 4002=paper)')
    parser.add_argument('--client-id', type=int, default=50, help='Client ID for connection')
    parser.add_argument('--status', action='store_true', help='Show current data status')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: fetch since last collected date')

    args = parser.parse_args()

    # Build config
    config = IBKRConfig(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
    )

    # Handle --status mode
    if args.status:
        storage = StorageManager(config.data_dir)
        status = storage.get_data_status()

        logger.info("\n" + "=" * 60)
        logger.info("IBKR NEWS DATA STATUS")
        logger.info("=" * 60)
        logger.info(f"Total articles: {status['total_articles']:,}")
        logger.info(f"Total files: {status['total_files']}")
        logger.info(f"Date range: {status['date_range']['earliest']} to {status['date_range']['latest']}")

        if status['by_year']:
            logger.info("\nBy year:")
            for year, count in sorted(status['by_year'].items()):
                logger.info(f"  {year}: {count:,} articles")

        if status['by_publisher']:
            logger.info("\nBy publisher:")
            for pub, count in sorted(status['by_publisher'].items(), key=lambda x: -x[1])[:10]:
                logger.info(f"  {pub}: {count:,}")

        # Show incremental update info
        latest = storage.get_latest_date()
        if latest:
            days_behind = (date.today() - latest).days
            logger.info(f"\nLast collected: {latest} ({days_behind} days ago)")
            if days_behind > 0:
                logger.info(f"Run --incremental to fetch {min(days_behind, config.max_history_days)} days of new data")
        else:
            logger.info("\nNo existing data. Run without --status to start collection.")

        return

    # Determine date range
    end_date = date.today()
    if args.end:
        end_date = date.fromisoformat(args.end)

    # Handle --incremental mode
    if args.incremental:
        storage = StorageManager(config.data_dir)
        latest = storage.get_latest_date()

        if latest:
            start_date = latest + timedelta(days=1)
            if start_date > end_date:
                logger.info(f"Data is already up to date (latest: {latest})")
                return
            logger.info(f"INCREMENTAL MODE: Fetching from {start_date} to {end_date}")
        else:
            start_date = end_date - timedelta(days=config.max_history_days)
            logger.info(f"No existing data. Fetching last {config.max_history_days} days.")
    elif args.start:
        start_date = date.fromisoformat(args.start)
    else:
        start_date = end_date - timedelta(days=args.days)

    # Load tickers
    tickers = load_tickers(args.tickers)

    logger.info(f"Tickers: {len(tickers)} stocks")
    logger.info(f"Date range: {start_date} to {end_date}")

    # Collect
    stats = collect_news(tickers, start_date, end_date, config)

    # Save stats
    stats_path = Path("data/news/metadata/ibkr_collection_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w') as f:
        json.dump({
            'completed_at': datetime.now().isoformat(),
            'tickers': tickers,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            **stats,
        }, f, indent=2)

    logger.info(f"\nStats saved to: {stats_path}")


if __name__ == "__main__":
    main()