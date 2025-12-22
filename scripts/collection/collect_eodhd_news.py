#!/usr/bin/env python3
"""
EODHD 新聞收集腳本

EODHD 特點:
- 免費方案: 20 calls/day (極為有限!)
- 新聞每次請求消耗 5 API calls (實際僅 4 次新聞查詢/天)
- 付費方案: $19.99+/month, 100k calls/day
- 提供 AI 情緒分析 (-1 到 1)
- 覆蓋 150,000+ 全球代號, 60+ 交易所

適合用於:
- 付費用戶的批量歷史新聞收集
- 需要內建情緒分析的場景
- 全球市場新聞 (非僅美股)

使用方式:
    # 收集最近 7 天新聞
    python collect_eodhd_news.py --days 7

    # 收集指定日期範圍
    python collect_eodhd_news.py --start 2024-01-01 --end 2024-12-31

    # 僅收集指定股票
    python collect_eodhd_news.py --tickers AAPL,MSFT --days 30

    # 查看現有資料狀態
    python collect_eodhd_news.py --status

    # 增量更新
    python collect_eodhd_news.py --incremental
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
        logging.FileHandler('collect_eodhd_news.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class EODHDConfig:
    """EODHD 收集設定"""
    # Rate limiting
    # Free tier: 20 calls/day, News costs 5 calls each = 4 news requests/day
    # Paid tier: 100,000 calls/day
    request_delay: float = 1.0  # 1 second between requests
    requests_per_minute: int = 60  # Paid tier allows high rate

    # Pagination
    articles_per_request: int = 1000  # Max per request

    # Storage paths
    data_dir: Path = Path("data/news/raw/eodhd")

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 10.0


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class NewsArticle:
    """新聞文章資料結構 (符合統一 schema)"""
    article_id: str
    ticker: str
    title: str
    published_at: str
    source_api: str = "eodhd"

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

class EODHDRateLimiter:
    """Rate limiting for EODHD API"""

    def __init__(self, config: EODHDConfig):
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
# EODHD API Client
# =============================================================================

class EODHDNewsCollector:
    """EODHD 新聞收集器"""

    BASE_URL = "https://eodhd.com/api"

    def __init__(self, api_key: str, config: EODHDConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = EODHDRateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'api_calls_used': 0,  # EODHD news costs 5 calls each
            'by_source': {},
        }

    def fetch_news(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[dict]:
        """
        Fetch news for a ticker from EODHD.

        Note: Each news request costs 5 API calls on EODHD!
        """
        self.rate_limiter.wait()
        self.stats['total_requests'] += 1
        self.stats['api_calls_used'] += 5  # News costs 5 calls

        # EODHD uses .US suffix for US stocks
        symbol = f"{ticker}.US" if '.' not in ticker else ticker

        params = {
            's': symbol,
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'limit': limit,
            'offset': offset,
            'api_token': self.api_key,
            'fmt': 'json',
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/news",
                params=params,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning("Rate limit hit (429), waiting 60s...")
                time.sleep(60)
                return self.fetch_news(ticker, start_date, end_date, limit, offset)

            if response.status_code == 401:
                logger.error("Invalid API key or insufficient permissions")
                self.stats['errors'] += 1
                return []

            if response.status_code != 200:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                self.stats['errors'] += 1
                return []

            data = response.json()

            # EODHD returns list directly or dict with error
            if isinstance(data, dict) and 'error' in data:
                logger.error(f"API error: {data.get('error')}")
                return []

            return data if isinstance(data, list) else []

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            self.stats['errors'] += 1
            return []

    def fetch_sentiment(self, ticker: str, start_date: date, end_date: date) -> List[dict]:
        """
        Fetch sentiment data for a ticker.

        Sentiment API provides daily aggregated sentiment scores.
        """
        self.rate_limiter.wait()
        self.stats['total_requests'] += 1
        self.stats['api_calls_used'] += 5

        symbol = f"{ticker}.US" if '.' not in ticker else ticker

        params = {
            's': symbol,
            'from': start_date.isoformat(),
            'to': end_date.isoformat(),
            'api_token': self.api_key,
            'fmt': 'json',
        }

        try:
            response = self.session.get(
                f"{self.BASE_URL}/sentiments",
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                return []

            data = response.json()
            return data if isinstance(data, list) else []

        except requests.RequestException:
            return []

    def parse_article(self, raw: dict, ticker: str, collected_at: datetime) -> NewsArticle:
        """Parse raw API response to NewsArticle."""

        # Parse published date (EODHD format: "2024-01-15 14:30:00")
        date_str = raw.get('date', '')
        if date_str:
            try:
                pub_dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                published_at = pub_dt.isoformat() + 'Z'
            except ValueError:
                published_at = date_str
        else:
            published_at = ''

        # Get content
        title = raw.get('title', '')
        content = raw.get('content', '')
        content_length = len(content)

        # Publisher
        publisher = raw.get('source', '')
        if publisher:
            self.stats['by_source'][publisher] = self.stats['by_source'].get(publisher, 0) + 1

        # Sentiment from EODHD (if available)
        sentiment_score = None
        sentiment_label = ""
        if 'sentiment' in raw:
            sent = raw.get('sentiment', {})
            if isinstance(sent, dict):
                # EODHD sentiment object: {polarity, neg, neu, pos}
                polarity = sent.get('polarity')
                if polarity is not None:
                    sentiment_score = float(polarity)
                    if polarity > 0.1:
                        sentiment_label = "positive"
                    elif polarity < -0.1:
                        sentiment_label = "negative"
                    else:
                        sentiment_label = "neutral"

        # Tags from EODHD
        tags = raw.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        # Related tickers
        symbols = raw.get('symbols', [])
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(',') if s.strip()]

        # Generate dedup hash
        pub_date = published_at[:10] if published_at else ''
        hash_input = f"{ticker.upper()}|{title.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Article ID (use link hash if no ID)
        link = raw.get('link', '')
        article_id = hashlib.md5(link.encode()).hexdigest() if link else dedup_hash

        return NewsArticle(
            article_id=article_id,
            ticker=ticker,
            title=title,
            published_at=published_at,
            source_api="eodhd",
            description=content[:500] if content else '',
            content=content,
            url=link,
            publisher=publisher,
            author='',
            related_tickers=json.dumps(symbols if symbols else [ticker]),
            tags=json.dumps(tags),
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

            # Ensure consistent dtypes
            for col in new_df.columns:
                if col in existing_df.columns:
                    if existing_df[col].dtype != new_df[col].dtype:
                        try:
                            new_df[col] = new_df[col].astype(existing_df[col].dtype)
                        except (ValueError, TypeError):
                            pass

            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            combined_df = new_df

        # Save
        combined_df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"  Saved {len(new_df)} new articles to {path.name} (total: {len(combined_df)})")

        return len(new_df)

    def get_data_status(self) -> Dict[str, any]:
        """取得現有資料的狀態統計"""
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

                    if 'ticker' in df.columns:
                        all_tickers.update(df['ticker'].unique())

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
        """取得最新的發布時間戳"""
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
                        if key == 'EODHD_API_KEY' and not value.startswith('your_'):
                            return value

    return os.environ.get('EODHD_API_KEY', '')


def collect_news(
    tickers: List[str],
    start_date: date,
    end_date: date,
) -> dict:
    """Main collection function."""

    # Load API key
    api_key = load_env()
    if not api_key:
        logger.error("EODHD_API_KEY not found in config/.env or environment")
        sys.exit(1)

    # Initialize
    config = EODHDConfig()
    collector = EODHDNewsCollector(api_key, config)
    storage = StorageManager(config.data_dir)

    collected_at = datetime.now()

    logger.info(f"Starting EODHD collection: {len(tickers)} tickers")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Note: Each news request costs 5 API calls on EODHD!")

    all_articles = []

    for i, ticker in enumerate(tickers):
        progress = (i + 1) / len(tickers) * 100
        logger.info(f"[{progress:.1f}%] {ticker}")

        # Fetch news
        raw_articles = collector.fetch_news(ticker, start_date, end_date)

        if raw_articles:
            articles = [collector.parse_article(raw, ticker, collected_at) for raw in raw_articles]
            all_articles.extend(articles)
            logger.info(f"  Found {len(articles)} articles")
        else:
            logger.debug(f"  No articles found")

    # Group by month and save
    from collections import defaultdict
    by_month = defaultdict(list)
    for article in all_articles:
        pub_date = article.published_at[:10] if article.published_at else ''
        if pub_date:
            year, month = int(pub_date[:4]), int(pub_date[5:7])
            by_month[(year, month)].append(article)

    total_saved = 0
    for (year, month), month_articles in by_month.items():
        saved = storage.save_articles(month_articles, year, month)
        total_saved += saved

    collector.stats['total_articles'] = total_saved

    # Final stats
    logger.info("\n" + "=" * 60)
    logger.info("Collection Complete")
    logger.info("=" * 60)
    logger.info(f"Total articles fetched: {len(all_articles)}")
    logger.info(f"Saved (deduplicated): {total_saved}")
    logger.info(f"Total requests: {collector.stats['total_requests']}")
    logger.info(f"API calls used: {collector.stats['api_calls_used']} (news costs 5 calls each)")
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
        description='Collect news from EODHD API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Collect last 7 days for all tier1 stocks
    python collect_eodhd_news.py --days 7

    # Specific date range
    python collect_eodhd_news.py --start 2024-01-01 --end 2024-06-30

    # Specific tickers
    python collect_eodhd_news.py --tickers AAPL,MSFT,GOOGL --days 30

    # Show data status
    python collect_eodhd_news.py --status

Note: Free tier only allows 20 API calls/day.
News requests cost 5 calls each = only 4 news queries per day!
        """
    )

    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--days', type=int, default=7, help='Days back from today (default: 7)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers')
    parser.add_argument('--status', action='store_true',
                       help='Show current data status without collecting')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: fetch since last collected date')

    args = parser.parse_args()

    # Handle --status mode first
    if args.status:
        config = EODHDConfig()
        storage = StorageManager(config.data_dir)
        status = storage.get_data_status()

        logger.info("\n" + "=" * 60)
        logger.info("EODHD NEWS DATA STATUS")
        logger.info("=" * 60)
        logger.info(f"Total articles: {status['total_articles']:,}")
        logger.info(f"Total files: {status['total_files']}")
        logger.info(f"Unique tickers: {status.get('unique_tickers', 0)}")
        logger.info(f"Date range: {status['date_range']['earliest']} to {status['date_range']['latest']}")

        if status['by_year']:
            logger.info("\nBy year:")
            for year, count in sorted(status['by_year'].items()):
                logger.info(f"  {year}: {count:,} articles")

        return

    # Determine date range
    end_date = date.today()
    if args.end:
        end_date = date.fromisoformat(args.end)

    if args.incremental:
        config = EODHDConfig()
        storage = StorageManager(config.data_dir)
        latest_ts = storage.get_latest_timestamp()

        if latest_ts:
            if latest_ts.tzinfo is not None:
                latest_ts = latest_ts.replace(tzinfo=None)
            start_date = latest_ts.date() + timedelta(days=1)

            if start_date > end_date:
                logger.info(f"Data is already up to date (latest: {latest_ts.isoformat()})")
                return

            logger.info(f"INCREMENTAL MODE")
            logger.info(f"  Latest article: {latest_ts.isoformat()}")
            logger.info(f"  Fetching from: {start_date}")
        else:
            start_date = end_date - timedelta(days=7)
            logger.info(f"No existing data. Fetching last 7 days.")
    elif args.start:
        start_date = date.fromisoformat(args.start)
    else:
        start_date = end_date - timedelta(days=args.days)

    # Load tickers
    tickers = load_tickers(args.tickers)

    # Warn about free tier limits
    estimated_calls = len(tickers) * 5  # 5 calls per news request
    logger.warning(f"Estimated API calls: {estimated_calls} (free tier: 20/day)")
    if estimated_calls > 20:
        logger.warning("This will exceed free tier limits! Consider using paid plan.")

    # Collect
    stats = collect_news(tickers, start_date, end_date)

    # Save stats
    stats_path = Path("data/news/metadata/eodhd_collection_stats.json")
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