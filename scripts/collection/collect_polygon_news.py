#!/usr/bin/env python3
"""
Polygon.io 新聞收集腳本

收集 3+ 年歷史新聞，遵循 NEWS_STORAGE_DESIGN.md 結構：
- 儲存位置: data/news/raw/polygon/YYYY/YYYY-MM.parquet
- 支援 checkpoint/resume (長時間收集可中斷)
- 遵守免費方案 rate limit: 5 calls/min (12 秒間隔)

使用方式:
    # 收集所有 tier1 股票的完整歷史 (3 年)
    python collect_polygon_news.py --full-history

    # 收集指定日期範圍
    python collect_polygon_news.py --start 2024-01-01 --end 2024-12-31

    # 收集最近 N 天
    python collect_polygon_news.py --days 30

    # 僅收集指定股票
    python collect_polygon_news.py --tickers AAPL,MSFT --days 30

    # 從 checkpoint 繼續
    python collect_polygon_news.py --resume

    # 增量更新 (只抓取最後收集日期之後的新聞)
    python collect_polygon_news.py --incremental

    # 查看現有資料狀態
    python collect_polygon_news.py --status

    # 補抓新加入的 ticker (incremental 不會補歷史)
    python collect_polygon_news.py --tickers GM,NEM,AFRM --start 2022-01-01

重要限制:
    --incremental 使用「所有 ticker 中最新一篇文章的時間」作為起始點，
    對每個 ticker 統一從該時間點開始查詢。這意味著：
    - 新加入 tickers_core.json 的 ticker 不會被補抓歷史資料
    - 只有「該時間點之後」發布的新聞才會被抓到
    - 若需要補抓新 ticker 的歷史，必須用 --tickers + --start 手動指定
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

import requests
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('collect_polygon_news.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class CollectionConfig:
    """收集設定"""
    # Rate limiting (free tier: 5 calls/min)
    request_delay: float = 12.0  # 12 seconds between requests
    requests_per_minute: int = 5

    # Pagination
    articles_per_request: int = 1000  # Max allowed by Polygon

    # Storage paths
    data_dir: Path = Path("data/news/raw/polygon")
    checkpoint_dir: Path = Path("data/news/metadata")

    # Default date range for full history
    default_start: date = date(2022, 1, 1)  # 3 years back

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 30.0


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class NewsArticle:
    """新聞文章資料結構 (符合 NEWS_STORAGE_DESIGN.md schema)"""
    article_id: str
    ticker: str
    title: str
    published_at: str  # ISO format
    source_api: str = "polygon"

    description: str = ""
    content: str = ""
    url: str = ""

    publisher: str = ""
    author: str = ""

    related_tickers: str = ""  # JSON string list
    tags: str = ""  # JSON string list
    category: str = ""

    source_sentiment: Optional[float] = None
    source_sentiment_label: str = ""

    collected_at: str = ""
    content_length: int = 0
    dedup_hash: str = ""


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """Free tier rate limiting: 5 calls/minute"""

    def __init__(self, config: CollectionConfig):
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

        # Ensure minimum delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.config.request_delay:
            sleep_time = self.config.request_delay - elapsed
            time.sleep(sleep_time)

        self._last_request_time = time.time()
        self._request_count += 1


# =============================================================================
# Checkpoint Manager
# =============================================================================

class CheckpointManager:
    """管理收集進度，支援中斷後繼續"""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = checkpoint_dir / "polygon_collection_checkpoint.json"

    def save(self, state: dict):
        """儲存當前進度"""
        state['last_updated'] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)
        logger.debug(f"Checkpoint saved: {state.get('current_ticker')} - {state.get('current_month')}")

    def load(self) -> Optional[dict]:
        """載入上次進度"""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def clear(self):
        """清除 checkpoint"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info("Checkpoint cleared")


# =============================================================================
# Polygon API Client
# =============================================================================

class PolygonNewsCollector:
    """Polygon 新聞收集器"""

    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str, config: CollectionConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'duplicates': 0,
        }

    def fetch_news_month(
        self,
        ticker: str,
        year: int,
        month: int,
    ) -> List[dict]:
        """
        Fetch all news for a ticker in a specific month.
        Handles pagination automatically.
        """
        start_date = date(year, month, 1)

        # Calculate end of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        return self.fetch_news_range(ticker, start_date, end_date)

    def fetch_news_range(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        start_timestamp: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Fetch all news for a ticker in a date range.
        Handles pagination automatically.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date for the range
            end_date: End date for the range
            start_timestamp: Optional precise start timestamp (for incremental updates)
        """
        all_articles = []

        # Use precise timestamp if provided, otherwise use date
        if start_timestamp:
            # Format: 2024-01-15T14:30:00Z (ISO 8601)
            start_str = start_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            start_str = start_date.isoformat()

        params = {
            'ticker': ticker,
            'published_utc.gte': start_str,
            'published_utc.lte': f"{end_date.isoformat()}T23:59:59Z",
            'limit': self.config.articles_per_request,
            'sort': 'published_utc',
            'order': 'asc',
            'apiKey': self.api_key,
        }

        url = f"{self.BASE_URL}/v2/reference/news"

        while True:
            self.rate_limiter.wait()
            self.stats['total_requests'] += 1

            try:
                response = self.session.get(url, params=params, timeout=30)

                if response.status_code == 429:
                    logger.warning("Rate limit hit (429), waiting 60s...")
                    time.sleep(60)
                    continue

                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response.text[:200]}")
                    self.stats['errors'] += 1
                    break

                data = response.json()
                results = data.get('results', [])
                all_articles.extend(results)

                logger.debug(f"  Fetched {len(results)} articles (total: {len(all_articles)})")

                # Check for pagination
                next_url = data.get('next_url')
                if not next_url:
                    break

                # Use next_url directly (it includes cursor)
                url = next_url
                params = {'apiKey': self.api_key}

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                self.stats['errors'] += 1

                # Retry logic
                for retry in range(self.config.max_retries):
                    logger.info(f"Retrying in {self.config.retry_delay}s... ({retry + 1}/{self.config.max_retries})")
                    time.sleep(self.config.retry_delay)
                    try:
                        response = self.session.get(url, params=params, timeout=30)
                        if response.status_code == 200:
                            break
                    except:
                        pass
                else:
                    logger.error("Max retries exceeded, skipping...")
                    break

        return all_articles

    def parse_article(self, raw: dict, collected_at: datetime) -> NewsArticle:
        """Parse raw API response to NewsArticle."""

        # Parse published date
        pub_str = raw.get('published_utc', '')

        # Get tickers
        tickers = raw.get('tickers', [])
        primary_ticker = tickers[0] if tickers else 'UNKNOWN'

        # Get sentiment from insights
        sentiment_score = None
        sentiment_label = ""
        insights = raw.get('insights', [])
        if insights:
            for insight in insights:
                if insight.get('sentiment'):
                    sentiment_label = insight.get('sentiment', '')
                    sentiment_map = {'positive': 1.0, 'neutral': 0.0, 'negative': -1.0}
                    sentiment_score = sentiment_map.get(sentiment_label, 0.0)
                    break

        # Calculate content length
        content = raw.get('description', '') or ''
        content_length = len(content)

        # Generate dedup hash
        title = raw.get('title', '')
        pub_date = pub_str[:10] if pub_str else ''
        hash_input = f"{primary_ticker.upper()}|{title.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Generate article_id
        article_id = raw.get('id', dedup_hash)

        return NewsArticle(
            article_id=str(article_id),
            ticker=primary_ticker,
            title=title,
            published_at=pub_str,
            source_api="polygon",
            description=content,
            content=content,
            url=raw.get('article_url', ''),
            publisher=raw.get('publisher', {}).get('name', ''),
            author=raw.get('author', ''),
            related_tickers=json.dumps(tickers),
            tags=json.dumps(raw.get('keywords', [])),
            category='',
            source_sentiment=sentiment_score,
            source_sentiment_label=sentiment_label,
            collected_at=collected_at.isoformat(),
            content_length=content_length,
            dedup_hash=dedup_hash,
        )


# =============================================================================
# Storage Manager
# =============================================================================

class StorageManager:
    """管理 Parquet 檔案儲存 (帶快取)"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Cache for parquet data: {(year, month): {'df': DataFrame, 'hashes': set}}
        self._cache: Dict[Tuple[int, int], Dict] = {}

    def get_parquet_path(self, year: int, month: int) -> Path:
        """取得指定月份的 parquet 檔案路徑"""
        year_dir = self.data_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir / f"{year}-{month:02d}.parquet"

    def _load_cache(self, year: int, month: int) -> Dict:
        """載入並快取 parquet 資料"""
        key = (year, month)
        if key in self._cache:
            return self._cache[key]

        path = self.get_parquet_path(year, month)
        if path.exists():
            df = pd.read_parquet(path)
            hashes = set(df['dedup_hash'].tolist()) if 'dedup_hash' in df.columns else set()
            self._cache[key] = {'df': df, 'hashes': hashes, 'count': len(df)}
        else:
            self._cache[key] = {'df': None, 'hashes': set(), 'count': 0}

        return self._cache[key]

    def _invalidate_cache(self, year: int, month: int):
        """清除指定月份的快取"""
        key = (year, month)
        if key in self._cache:
            del self._cache[key]

    def save_articles(
        self,
        articles: List[NewsArticle],
        year: int,
        month: int,
        append: bool = True,
    ) -> int:
        """儲存文章到 parquet 檔案 (使用快取優化)"""
        if not articles:
            return 0

        path = self.get_parquet_path(year, month)

        # Convert to DataFrame
        new_df = pd.DataFrame([asdict(a) for a in articles])

        # Load existing if appending (use cache)
        if append and path.exists():
            cache = self._load_cache(year, month)
            existing_df = cache['df']
            existing_hashes = cache['hashes']

            if existing_df is not None:
                # Deduplicate by hash using cached hashes
                new_df = new_df[~new_df['dedup_hash'].isin(existing_hashes)]

                if len(new_df) == 0:
                    logger.debug(f"  All articles already exist in {path.name}")
                    return 0

                # Ensure consistent dtypes to avoid FutureWarning
                for col in new_df.columns:
                    if col in existing_df.columns:
                        # Match dtype of existing column
                        if existing_df[col].dtype != new_df[col].dtype:
                            try:
                                new_df[col] = new_df[col].astype(existing_df[col].dtype)
                            except (ValueError, TypeError):
                                pass  # Keep original dtype if conversion fails

                # Append
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                combined_df = new_df
        else:
            combined_df = new_df

        # Save
        combined_df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"  Saved {len(new_df)} new articles to {path.name} (total: {len(combined_df)})")

        # Update cache with new data
        new_hashes = set(new_df['dedup_hash'].tolist())
        key = (year, month)
        if key in self._cache:
            self._cache[key]['df'] = combined_df
            self._cache[key]['hashes'].update(new_hashes)
            self._cache[key]['count'] = len(combined_df)
        else:
            self._cache[key] = {
                'df': combined_df,
                'hashes': set(combined_df['dedup_hash'].tolist()),
                'count': len(combined_df)
            }

        return len(new_df)

    def get_existing_count(self, year: int, month: int) -> int:
        """取得現有文章數量 (使用快取)"""
        cache = self._load_cache(year, month)
        return cache['count']

    def get_latest_date(self) -> Optional[date]:
        """
        取得所有現有資料中最新的發布日期。

        Returns:
            最新的發布日期，如果沒有資料則返回 None。
        """
        ts = self.get_latest_timestamp()
        return ts.date() if ts else None

    def get_latest_timestamp(self) -> Optional[datetime]:
        """
        取得所有現有資料中最新的發布時間戳 (精確到秒)。

        Returns:
            最新的發布時間 (datetime)，如果沒有資料則返回 None。
        """
        latest_ts = None

        if not self.data_dir.exists():
            return None

        # Scan all parquet files in reverse order (newest first)
        for year_dir in sorted(self.data_dir.iterdir(), reverse=True):
            if not year_dir.is_dir():
                continue

            for parquet_file in sorted(year_dir.glob("*.parquet"), reverse=True):
                try:
                    df = pd.read_parquet(parquet_file)
                    if df.empty or 'published_at' not in df.columns:
                        continue

                    # Parse published_at and find max
                    df['_pub_ts'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_ts = df['_pub_ts'].max()

                    if pd.notna(max_ts):
                        file_latest = max_ts.to_pydatetime()
                        if latest_ts is None or file_latest > latest_ts:
                            latest_ts = file_latest

                        # Since we're scanning in reverse order, we can stop after first file
                        # that has valid data in the latest year
                        return latest_ts

                except Exception as e:
                    logger.warning(f"Error reading {parquet_file}: {e}")
                    continue

        return latest_ts

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
            'by_ticker': {},
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


# =============================================================================
# Main Collection Logic
# =============================================================================

def load_tickers(tickers_arg: Optional[str] = None, tiers: Optional[str] = None) -> List[str]:
    """
    Load tickers from config or argument.

    Args:
        tickers_arg: Comma-separated ticker list (overrides config)
        tiers: Comma-separated tier names (e.g., "tier1,tier2,tier3")
               Default: all tiers based on settings
    """
    if tickers_arg:
        return [t.strip().upper() for t in tickers_arg.split(',')]

    # Load from config
    config_path = Path("config/tickers_core.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)

        settings = config.get('settings', {})

        # Determine which tiers to include
        if tiers:
            tier_names = [t.strip() for t in tiers.split(',')]
        else:
            # Use settings to determine tiers
            tier_names = ['tier1_core']
            if settings.get('include_tier2', True):
                tier_names.append('tier2_expanded')
            if settings.get('include_tier3', True):
                tier_names.append('tier3_user_watchlist')

        tickers = set()  # Use set to avoid duplicates

        for tier_name in tier_names:
            tier_data = config.get(tier_name, {})
            for category in tier_data.values():
                if isinstance(category, dict) and 'tickers' in category:
                    tickers.update(category['tickers'])

        tickers = sorted(list(tickers))

        if tickers:
            logger.info(f"Loaded {len(tickers)} tickers from {', '.join(tier_names)}")
            return tickers

    # Fallback to key stocks
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
                        if key == 'POLYGON_API_KEY' and not value.startswith('your_'):
                            return value

    # Try environment variable
    return os.environ.get('POLYGON_API_KEY', '')


def generate_months(start_date: date, end_date: date) -> List[Tuple[int, int]]:
    """Generate list of (year, month) tuples between dates."""
    months = []
    current = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)

    while current <= end_month:
        months.append((current.year, current.month))

        # Next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    return months


def collect_news(
    tickers: List[str],
    start_date: date,
    end_date: date,
    resume: bool = False,
) -> dict:
    """
    Main collection function.

    Returns:
        Collection statistics dictionary.
    """
    # Load API key
    api_key = load_env()
    if not api_key:
        logger.error("POLYGON_API_KEY not found in config/.env or environment")
        sys.exit(1)

    # Initialize
    config = CollectionConfig()
    collector = PolygonNewsCollector(api_key, config)
    storage = StorageManager(config.data_dir)
    checkpoint = CheckpointManager(config.checkpoint_dir)

    # Generate month list
    months = generate_months(start_date, end_date)
    total_months = len(months) * len(tickers)

    # Load checkpoint if resuming
    start_ticker_idx = 0
    start_month_idx = 0
    if resume:
        state = checkpoint.load()
        if state:
            logger.info(f"Resuming from checkpoint: {state.get('current_ticker')} - {state.get('current_month')}")

            # Find resume point
            resume_ticker = state.get('current_ticker')
            resume_month = state.get('current_month')

            if resume_ticker in tickers:
                start_ticker_idx = tickers.index(resume_ticker)

            if resume_month:
                year, month = map(int, resume_month.split('-'))
                for i, (y, m) in enumerate(months):
                    if y == year and m == month:
                        start_month_idx = i
                        break

    # Collection loop
    collected_at = datetime.now()
    processed = 0

    logger.info(f"Starting collection: {len(tickers)} tickers, {len(months)} months")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Rate limit: {config.requests_per_minute} calls/min ({config.request_delay}s delay)")

    try:
        for ticker_idx, ticker in enumerate(tickers[start_ticker_idx:], start=start_ticker_idx):

            month_start = start_month_idx if ticker_idx == start_ticker_idx else 0

            for month_idx, (year, month) in enumerate(months[month_start:], start=month_start):
                processed += 1
                progress = processed / total_months * 100

                logger.info(f"[{progress:.1f}%] {ticker} - {year}-{month:02d}")

                # Save checkpoint
                checkpoint.save({
                    'current_ticker': ticker,
                    'current_month': f"{year}-{month:02d}",
                    'ticker_idx': ticker_idx,
                    'month_idx': month_idx,
                    'stats': collector.stats,
                })

                # Check if already have data
                existing = storage.get_existing_count(year, month)

                # Fetch articles
                raw_articles = collector.fetch_news_month(ticker, year, month)

                if raw_articles:
                    # Parse
                    articles = [collector.parse_article(a, collected_at) for a in raw_articles]

                    # Filter for this ticker (in case of related articles)
                    ticker_articles = [a for a in articles if a.ticker.upper() == ticker.upper()]

                    # Save
                    saved = storage.save_articles(ticker_articles, year, month)
                    collector.stats['total_articles'] += saved
                else:
                    logger.debug(f"  No articles found")

            # Reset month index after first ticker
            start_month_idx = 0

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Progress saved in checkpoint.")
        checkpoint.save({
            'current_ticker': ticker,
            'current_month': f"{year}-{month:02d}",
            'ticker_idx': ticker_idx,
            'month_idx': month_idx,
            'stats': collector.stats,
            'interrupted': True,
        })

    # Final stats
    logger.info("\n" + "=" * 60)
    logger.info("Collection Complete")
    logger.info("=" * 60)
    logger.info(f"Total articles collected: {collector.stats['total_articles']}")
    logger.info(f"Total API requests: {collector.stats['total_requests']}")
    logger.info(f"Errors: {collector.stats['errors']}")

    # Clear checkpoint on success
    checkpoint.clear()

    return collector.stats


def estimate_time(tickers: List[str], months: int) -> str:
    """Estimate collection time based on rate limits."""
    # Assume average 2 requests per month per ticker (with pagination)
    total_requests = len(tickers) * months * 2

    # 5 requests/minute = 12 seconds each
    total_seconds = total_requests * 12

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    return f"~{hours}h {minutes}m"


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Collect news from Polygon.io API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full 3-year history for all tier1 stocks
    python collect_polygon_news.py --full-history

    # Specific date range
    python collect_polygon_news.py --start 2024-01-01 --end 2024-06-30

    # Last 30 days
    python collect_polygon_news.py --days 30

    # Specific tickers
    python collect_polygon_news.py --tickers AAPL,MSFT,GOOGL --days 30

    # Resume interrupted collection
    python collect_polygon_news.py --resume
        """
    )

    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--days', type=int, help='Days back from today')
    parser.add_argument('--full-history', action='store_true', help='Collect 3 years of history')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers (default: tier1 from config)')
    parser.add_argument('--resume', action='store_true', help='Resume from last checkpoint')
    parser.add_argument('--estimate', action='store_true', help='Estimate time without collecting')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: only fetch news since last collected date. '
                            'NOTE: uses global latest timestamp — new tickers without '
                            'history will NOT be backfilled. Use --tickers + --start instead.')
    parser.add_argument('--status', action='store_true',
                       help='Show current data status without collecting')

    args = parser.parse_args()

    # Handle --status mode first
    if args.status:
        config = CollectionConfig()
        storage = StorageManager(config.data_dir)
        status = storage.get_data_status()

        logger.info("\n" + "=" * 60)
        logger.info("POLYGON NEWS DATA STATUS")
        logger.info("=" * 60)
        logger.info(f"Total articles: {status['total_articles']:,}")
        logger.info(f"Total files: {status['total_files']}")
        logger.info(f"Unique tickers: {status.get('unique_tickers', 0)}")
        logger.info(f"Date range: {status['date_range']['earliest']} to {status['date_range']['latest']}")

        if status['by_year']:
            logger.info("\nBy year:")
            for year, count in sorted(status['by_year'].items()):
                logger.info(f"  {year}: {count:,} articles")

        # Show incremental update info
        latest = storage.get_latest_date()
        if latest:
            days_behind = (date.today() - latest).days
            logger.info(f"\nLast collected: {latest} ({days_behind} days ago)")
            if days_behind > 0:
                logger.info(f"Run --incremental to fetch {days_behind} days of new data")
        else:
            logger.info("\nNo existing data. Run --full-history to start collection.")

        return

    # Determine date range
    end_date = date.today()
    if args.end:
        end_date = date.fromisoformat(args.end)

    # Handle --incremental mode
    if args.incremental:
        config = CollectionConfig()
        storage = StorageManager(config.data_dir)
        latest_ts = storage.get_latest_timestamp()

        if latest_ts:
            # Use timestamp precision: start from 1 second after latest article
            start_timestamp = latest_ts + timedelta(seconds=1)
            start_date = start_timestamp.date()

            # Check if already up to date
            # Handle timezone: start_timestamp may be timezone-aware (UTC)
            if start_timestamp.tzinfo is not None:
                start_timestamp = start_timestamp.replace(tzinfo=None)
            now = datetime.now()
            if start_timestamp > now:
                logger.info(f"Data is already up to date (latest: {latest_ts.isoformat()})")
                return

            logger.info(f"INCREMENTAL MODE (timestamp precision)")
            logger.info(f"  Latest article: {latest_ts.isoformat()}")
            logger.info(f"  Fetching from:  {start_timestamp.isoformat()}")

            # Run incremental collection with timestamp precision
            api_key = load_env()
            if not api_key:
                logger.error("POLYGON_API_KEY not found")
                return

            collector = PolygonNewsCollector(api_key, config)
            tickers = load_tickers(args.tickers)
            collected_at = datetime.now()

            logger.info(f"Tickers: {len(tickers)} stocks")

            for i, ticker in enumerate(tickers):
                progress = (i + 1) / len(tickers) * 100
                logger.info(f"[{progress:.1f}%] {ticker}")

                # Fetch with timestamp precision
                raw_articles = collector.fetch_news_range(
                    ticker, start_date, end_date,
                    start_timestamp=start_timestamp
                )

                if raw_articles:
                    articles = [collector.parse_article(a, collected_at) for a in raw_articles]
                    ticker_articles = [a for a in articles if a.ticker.upper() == ticker.upper()]

                    # Group by month and save
                    from collections import defaultdict
                    by_month = defaultdict(list)
                    for article in ticker_articles:
                        pub_date = article.published_at[:10]
                        year, month = int(pub_date[:4]), int(pub_date[5:7])
                        by_month[(year, month)].append(article)

                    for (year, month), month_articles in by_month.items():
                        saved = storage.save_articles(month_articles, year, month)
                        collector.stats['total_articles'] += saved

            logger.info("\n" + "=" * 60)
            logger.info(f"Incremental update complete: {collector.stats['total_articles']} new articles")
            logger.info("=" * 60)

            # Save stats (same as full collection path)
            stats_path = Path("data/news/metadata/collection_stats.json")
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            with open(stats_path, 'w') as f:
                json.dump({
                    'completed_at': datetime.now().isoformat(),
                    'tickers': tickers,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    **collector.stats,
                }, f, indent=2)
            logger.info(f"Stats saved to: {stats_path}")

            return
        else:
            # No existing data, use default full history start
            start_date = date(2022, 1, 1)
            logger.info(f"No existing data found. Starting full collection from {start_date}")
    elif args.full_history:
        start_date = date(2022, 1, 1)
    elif args.days:
        start_date = end_date - timedelta(days=args.days)
    elif args.start:
        start_date = date.fromisoformat(args.start)
    else:
        # Default: last 30 days
        start_date = end_date - timedelta(days=30)

    # Load tickers
    tickers = load_tickers(args.tickers)

    # Generate months for estimate
    months = generate_months(start_date, end_date)

    logger.info(f"Tickers: {len(tickers)} stocks")
    logger.info(f"Date range: {start_date} to {end_date} ({len(months)} months)")
    logger.info(f"Estimated time: {estimate_time(tickers, len(months))}")

    if args.estimate:
        logger.info("\n(Estimate only, use without --estimate to start collection)")
        return

    # Confirm for large collections
    if len(tickers) * len(months) > 100:
        logger.info("\nThis is a large collection. It will take a while due to rate limits.")
        logger.info("Press Ctrl+C at any time to pause (progress will be saved).")
        logger.info("Use --resume to continue later.\n")
        time.sleep(3)

    # Start collection
    stats = collect_news(tickers, start_date, end_date, resume=args.resume)

    # Save final stats
    stats_path = Path("data/news/metadata/collection_stats.json")
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