#!/usr/bin/env python3
"""
Finnhub 新聞收集腳本

Finnhub 特點:
- 免費方案: 60 calls/min (比 Polygon 快 12 倍)
- 歷史限制: 僅 ~7 天 (無法取得歷史)
- 來源: Yahoo, SeekingAlpha, CNBC

適合用於:
- 即時/最近的新聞收集 (每日更新)
- 補充 Polygon 的 Yahoo 新聞 (Polygon 沒有)

使用方式:
    # 收集最近 7 天新聞
    python collect_finnhub_news.py

    # 收集指定日期範圍 (注意: 只有最近 ~7 天有效)
    python collect_finnhub_news.py --start 2025-12-08 --end 2025-12-15

    # 僅收集指定股票
    python collect_finnhub_news.py --tickers AAPL,MSFT

    # 查看現有資料狀態
    python collect_finnhub_news.py --status

    # 增量更新 (每日執行)
    python collect_finnhub_news.py --incremental
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
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

import requests
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('collect_finnhub_news.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class FinnhubConfig:
    """Finnhub 收集設定"""
    # Rate limiting (free tier: 60 calls/min)
    request_delay: float = 1.0  # 1 second between requests
    requests_per_minute: int = 60

    # Storage paths
    data_dir: Path = Path("data/news/raw/finnhub")

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 10.0


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
    source_api: str = "finnhub"

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
# Rate Limiter
# =============================================================================

class FinnhubRateLimiter:
    """60 calls/minute rate limiting"""

    def __init__(self, config: FinnhubConfig):
        self.config = config
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()

    def wait(self):
        """Wait to respect rate limits."""
        current_time = time.time()

        # Reset counter every minute
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # If we've hit the limit, wait
        if self._request_count >= self.config.requests_per_minute:
            wait_time = 60 - (current_time - self._minute_start)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                self._request_count = 0
                self._minute_start = time.time()

        # Minimum delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.config.request_delay:
            time.sleep(self.config.request_delay - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1


# =============================================================================
# Finnhub API Client
# =============================================================================

class FinnhubNewsCollector:
    """Finnhub 新聞收集器"""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str, config: FinnhubConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = FinnhubRateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'by_source': {},
        }

    def fetch_news(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """Fetch news for a ticker."""
        self.rate_limiter.wait()
        self.stats['total_requests'] += 1

        params = {
            'symbol': ticker,
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'token': self.api_key,
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/company-news",
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning("Rate limit hit (429), waiting 60s...")
                time.sleep(60)
                return self.fetch_news(ticker, start_date, end_date)

            if response.status_code != 200:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                self.stats['errors'] += 1
                return []

            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            self.stats['errors'] += 1
            return []

    def parse_article(self, raw: dict, ticker: str, collected_at: datetime) -> NewsArticle:
        """Parse raw API response to NewsArticle."""

        # Parse timestamp (Finnhub uses Unix timestamp)
        timestamp = raw.get('datetime', 0)
        if timestamp:
            pub_dt = datetime.fromtimestamp(timestamp)
            published_at = pub_dt.isoformat() + 'Z'
        else:
            published_at = ''

        # Get content
        headline = raw.get('headline', '')
        summary = raw.get('summary', '')
        content = summary

        # Publisher (source field)
        publisher = raw.get('source', '')

        # Track by source
        if publisher:
            self.stats['by_source'][publisher] = self.stats['by_source'].get(publisher, 0) + 1

        # Generate dedup hash
        pub_date = published_at[:10] if published_at else ''
        hash_input = f"{ticker.upper()}|{headline.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Article ID
        article_id = str(raw.get('id', dedup_hash))

        return NewsArticle(
            article_id=article_id,
            ticker=ticker,
            title=headline,
            published_at=published_at,
            source_api="finnhub",
            description=summary,
            content=content,
            url=raw.get('url', ''),
            publisher=publisher,
            author='',
            related_tickers=json.dumps(raw.get('related', []) or [ticker]),
            tags=json.dumps(raw.get('category', '').split(',') if raw.get('category') else []),
            category=raw.get('category', ''),
            source_sentiment=None,  # Finnhub doesn't provide sentiment
            source_sentiment_label='',
            collected_at=collected_at.isoformat(),
            content_length=len(content),
            dedup_hash=dedup_hash,
        )


# =============================================================================
# Storage Manager
# =============================================================================

class StorageManager:
    """管理 Parquet 檔案儲存"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_parquet_path(self, year: int, month: int) -> Path:
        """取得指定月份的 parquet 檔案路徑"""
        year_dir = self.data_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir / f"{year}-{month:02d}.parquet"

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
            existing_df = pd.read_parquet(path)

            # Deduplicate by hash
            existing_hashes = set(existing_df['dedup_hash'].tolist())
            new_df = new_df[~new_df['dedup_hash'].isin(existing_hashes)]

            if len(new_df) == 0:
                logger.debug(f"  All articles already exist")
                return 0

            # Ensure consistent dtypes to avoid FutureWarning
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

        return len(new_df)

    def get_data_status(self) -> Dict[str, any]:
        """
        取得現有資料的狀態統計。

        Returns:
            包含統計資訊的字典。
        """
        status = {
            'total_articles': 0,
            'total_files': 0,
            'date_range': {'earliest': None, 'latest': None},
            'by_year': {},
        }

        if not self.data_dir.exists():
            return status

        all_tickers = set()
        earliest_date = None
        latest_date = None

        for year_dir in sorted(self.data_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            year = year_dir.name
            year_count = 0

            for parquet_file in year_dir.glob("*.parquet"):
                try:
                    df = pd.read_parquet(parquet_file)
                    status['total_files'] += 1
                    status['total_articles'] += len(df)
                    year_count += len(df)

                    # Track tickers
                    if 'ticker' in df.columns:
                        all_tickers.update(df['ticker'].unique())

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
        status['unique_tickers'] = len(all_tickers)

        return status

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        取得所有現有資料中最新的發布時間戳 (精確到秒)。

        Returns:
            最新的發布時間 (datetime)，如果沒有資料則返回 None。
        """
        if not self.data_dir.exists():
            return None

        for year_dir in sorted(self.data_dir.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue

            for parquet_file in sorted(year_dir.glob("*.parquet"), reverse=True):
                try:
                    df = pd.read_parquet(parquet_file)
                    if df.empty or 'published_at' not in df.columns:
                        continue

                    df['_pub_ts'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_ts = df['_pub_ts'].max()

                    if pd.notna(max_ts):
                        return max_ts.to_pydatetime()

                except Exception as e:
                    logger.warning(f"Error reading {parquet_file}: {e}")

        return None


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

        tier1 = config.get('tier1_core', {})
        tickers = []
        for category in tier1.values():
            if isinstance(category, dict) and 'tickers' in category:
                tickers.extend(category['tickers'])

        if tickers:
            logger.info(f"Loaded {len(tickers)} tier1 tickers from config")
            return tickers

    return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']


def load_env() -> str:
    """Load API key from .env file."""
    env_paths = [
        Path("config/.env"),
        Path(".env"),
    ]

    for path in env_paths:
        if path.exists():
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == 'FINNHUB_API_KEY' and not value.startswith('your_'):
                            return value

    return os.environ.get('FINNHUB_API_KEY', '')


def collect_news(
    tickers: List[str],
    start_date: date,
    end_date: date,
) -> dict:
    """Main collection function."""

    # Validate date range
    max_lookback = 7
    oldest_allowed = date.today() - timedelta(days=max_lookback)

    if start_date < oldest_allowed:
        logger.warning(f"Finnhub only has ~{max_lookback} days of history!")
        logger.warning(f"Adjusting start_date from {start_date} to {oldest_allowed}")
        start_date = oldest_allowed

    # Load API key
    api_key = load_env()
    if not api_key:
        logger.error("FINNHUB_API_KEY not found in config/.env or environment")
        sys.exit(1)

    # Initialize
    config = FinnhubConfig()
    collector = FinnhubNewsCollector(api_key, config)
    storage = StorageManager(config.data_dir)

    collected_at = datetime.now()
    target_year = end_date.year
    target_month = end_date.month

    logger.info(f"Starting Finnhub collection: {len(tickers)} tickers")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Rate limit: {config.requests_per_minute} calls/min ({config.request_delay}s delay)")

    all_articles = []

    for i, ticker in enumerate(tickers):
        progress = (i + 1) / len(tickers) * 100
        logger.info(f"[{progress:.1f}%] {ticker}")

        # Fetch
        raw_articles = collector.fetch_news(ticker, start_date, end_date)

        if raw_articles:
            # Parse
            articles = [collector.parse_article(a, ticker, collected_at) for a in raw_articles]
            all_articles.extend(articles)
            logger.info(f"  Found {len(articles)} articles")
        else:
            logger.debug(f"  No articles found")

    # Save all articles to current month file
    if all_articles:
        saved = storage.save_articles(all_articles, target_year, target_month)
        collector.stats['total_articles'] = saved

    # Final stats
    logger.info("\n" + "=" * 60)
    logger.info("Collection Complete")
    logger.info("=" * 60)
    logger.info(f"Total articles: {len(all_articles)}")
    logger.info(f"Saved (deduplicated): {collector.stats['total_articles']}")
    logger.info(f"Total requests: {collector.stats['total_requests']}")
    logger.info(f"Errors: {collector.stats['errors']}")

    if collector.stats['by_source']:
        logger.info("\nBy source:")
        for source, count in sorted(collector.stats['by_source'].items(), key=lambda x: -x[1]):
            logger.info(f"  {source}: {count}")

    return collector.stats


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Collect news from Finnhub API (recent only, ~7 days)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Collect last 7 days for all tier1 stocks
    python collect_finnhub_news.py

    # Specific tickers
    python collect_finnhub_news.py --tickers AAPL,MSFT,GOOGL

    # Specific date range (max 7 days back)
    python collect_finnhub_news.py --start 2025-12-08 --end 2025-12-15

Note: Finnhub free tier only provides ~7 days of history!
For historical news, use collect_polygon_news.py instead.
        """
    )

    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--days', type=int, default=7, help='Days back from today (default: 7)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers')
    parser.add_argument('--status', action='store_true',
                       help='Show current data status without collecting')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: fetch last 7 days and merge with existing')

    args = parser.parse_args()

    # Handle --status mode first
    if args.status:
        config = FinnhubConfig()
        storage = StorageManager(config.data_dir)
        status = storage.get_data_status()

        logger.info("\n" + "=" * 60)
        logger.info("FINNHUB NEWS DATA STATUS")
        logger.info("=" * 60)
        logger.info(f"Total articles: {status['total_articles']:,}")
        logger.info(f"Total files: {status['total_files']}")
        logger.info(f"Unique tickers: {status.get('unique_tickers', 0)}")
        logger.info(f"Date range: {status['date_range']['earliest']} to {status['date_range']['latest']}")

        if status['by_year']:
            logger.info("\nBy year:")
            for year, count in sorted(status['by_year'].items()):
                logger.info(f"  {year}: {count:,} articles")

        logger.info("\nNote: Finnhub only provides ~7 days of history.")
        logger.info("Run without --status to collect/update recent news.")

        return

    # Determine date range
    end_date = date.today()
    if args.end:
        end_date = date.fromisoformat(args.end)

    # For incremental mode, dynamically calculate days based on latest article
    # Finnhub API only provides ~7 days of history, so we cap at 7 days
    if args.incremental:
        import math
        config = FinnhubConfig()
        storage = StorageManager(config.data_dir)
        latest_ts = storage.get_latest_timestamp()

        if latest_ts:
            # Calculate time since latest article
            now = datetime.now()
            hours_behind = (now - latest_ts).total_seconds() / 3600
            days_behind = math.ceil(hours_behind / 24)  # Round up to full days

            # Cap at 7 days (Finnhub API limitation)
            days_to_fetch = min(days_behind, 7)

            if days_to_fetch <= 0:
                logger.info(f"Data is already up to date (latest: {latest_ts.isoformat()})")
                return

            start_date = end_date - timedelta(days=days_to_fetch)
            logger.info(f"INCREMENTAL MODE (dynamic days)")
            logger.info(f"  Latest article: {latest_ts.isoformat()}")
            logger.info(f"  Hours behind: {hours_behind:.1f}h → fetching {days_to_fetch} days")
            logger.info(f"  Date range: {start_date} to {end_date}")
        else:
            # No existing data, fetch full 7 days
            start_date = end_date - timedelta(days=7)
            logger.info(f"No existing data. Fetching last 7 days ({start_date} to {end_date})")

        logger.info("Note: Existing historical data will be preserved, duplicates filtered.")
    elif args.start:
        start_date = date.fromisoformat(args.start)
    else:
        start_date = end_date - timedelta(days=args.days)

    # Load tickers
    tickers = load_tickers(args.tickers)

    # Collect
    stats = collect_news(tickers, start_date, end_date)

    # Save stats
    stats_path = Path("data/news/metadata/finnhub_collection_stats.json")
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