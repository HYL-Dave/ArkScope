#!/usr/bin/env python3
"""
Alpha Vantage 新聞收集腳本

Alpha Vantage 特點:
- 免費方案: 25 calls/DAY (極為有限!), 5 calls/minute
- 新聞 API 包含詳細 AI 情緒分析:
  - 整體情緒分數 (-1 到 1)
  - 每個 ticker 的個別情緒分數
  - 相關度分數 (0-1)
- 官方 NASDAQ 授權數據提供商
- 覆蓋 200,000+ 股票代號, 20+ 交易所

適合用於:
- 需要高品質 AI 情緒分析的場景
- 補充其他來源的情緒標籤
- 付費用戶的批量收集

使用方式:
    # 收集最近新聞 (依 ticker 篩選)
    python collect_alphavantage_news.py --tickers AAPL,MSFT

    # 使用時間範圍 (Alpha Vantage 用 time_from/time_to)
    python collect_alphavantage_news.py --start 2024-01-01 --end 2024-01-31

    # 查看現有資料狀態
    python collect_alphavantage_news.py --status

    # 增量更新
    python collect_alphavantage_news.py --incremental
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
        logging.FileHandler('collect_alphavantage_news.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class AlphaVantageConfig:
    """Alpha Vantage 收集設定"""
    # Rate limiting
    # Free tier: 25 calls/day, 5 calls/minute
    # Paid tier: 75-1200 calls/minute depending on plan
    request_delay: float = 12.0  # 12 seconds between requests (5 calls/min)
    requests_per_minute: int = 5
    daily_limit: int = 25  # Free tier daily limit

    # Pagination
    articles_per_request: int = 200  # Alpha Vantage max per request

    # Storage paths
    data_dir: Path = Path("data/news/raw/alphavantage")

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 30.0


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
    source_api: str = "alphavantage"

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

    # Alpha Vantage specific fields (stored as JSON)
    ticker_sentiment: str = ""  # Per-ticker sentiment scores
    relevance_score: Optional[float] = None


# =============================================================================
# Rate Limiter
# =============================================================================

class AlphaVantageRateLimiter:
    """Rate limiting for Alpha Vantage API (very strict!)"""

    def __init__(self, config: AlphaVantageConfig):
        self.config = config
        self._last_request_time = 0
        self._request_count = 0
        self._minute_start = time.time()
        self._daily_count = 0
        self._day_start = datetime.now().date()

    def wait(self):
        """Wait to respect rate limits."""
        current_time = time.time()
        today = datetime.now().date()

        # Reset daily counter at midnight
        if today != self._day_start:
            self._daily_count = 0
            self._day_start = today

        # Check daily limit
        if self._daily_count >= self.config.daily_limit:
            logger.error(f"Daily limit reached ({self.config.daily_limit} calls)!")
            logger.error("Please wait until tomorrow or upgrade to a paid plan.")
            raise RuntimeError("Daily API limit exceeded")

        # Reset minute counter every minute
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # If we've hit the per-minute limit, wait
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
        self._daily_count += 1

    def get_remaining_calls(self) -> int:
        """Get remaining daily calls."""
        return max(0, self.config.daily_limit - self._daily_count)


# =============================================================================
# Alpha Vantage API Client
# =============================================================================

class AlphaVantageNewsCollector:
    """Alpha Vantage 新聞收集器"""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, config: AlphaVantageConfig):
        self.api_key = api_key
        self.config = config
        self.session = requests.Session()
        self.rate_limiter = AlphaVantageRateLimiter(config)

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_requests': 0,
            'errors': 0,
            'by_source': {},
            'with_sentiment': 0,
        }

    def fetch_news(
        self,
        tickers: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        time_from: Optional[datetime] = None,
        time_to: Optional[datetime] = None,
        sort: str = "LATEST",
        limit: int = 200,
    ) -> List[dict]:
        """
        Fetch news from Alpha Vantage NEWS_SENTIMENT endpoint.

        Args:
            tickers: List of tickers to filter (e.g., ['AAPL', 'MSFT'])
            topics: List of topics (e.g., ['technology', 'earnings'])
            time_from: Start datetime (format: YYYYMMDDTHHMM)
            time_to: End datetime
            sort: LATEST, EARLIEST, or RELEVANCE
            limit: Max articles (up to 1000)
        """
        self.rate_limiter.wait()
        self.stats['total_requests'] += 1

        params = {
            'function': 'NEWS_SENTIMENT',
            'apikey': self.api_key,
            'sort': sort,
            'limit': min(limit, 1000),
        }

        # Add tickers filter
        if tickers:
            params['tickers'] = ','.join(tickers)

        # Add topics filter
        if topics:
            params['topics'] = ','.join(topics)

        # Add time range (Alpha Vantage format: YYYYMMDDTHHMM)
        if time_from:
            params['time_from'] = time_from.strftime('%Y%m%dT%H%M')
        if time_to:
            params['time_to'] = time_to.strftime('%Y%m%dT%H%M')

        try:
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"API error {response.status_code}: {response.text[:200]}")
                self.stats['errors'] += 1
                return []

            data = response.json()

            # Check for API errors
            if 'Error Message' in data:
                logger.error(f"API error: {data['Error Message']}")
                self.stats['errors'] += 1
                return []

            if 'Note' in data:
                # Rate limit warning
                logger.warning(f"API Note: {data['Note']}")

            if 'Information' in data:
                # Usually indicates limit reached
                logger.warning(f"API Info: {data['Information']}")
                return []

            return data.get('feed', [])

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            self.stats['errors'] += 1
            return []

    def parse_article(
        self,
        raw: dict,
        target_ticker: str,
        collected_at: datetime
    ) -> Optional[NewsArticle]:
        """
        Parse raw API response to NewsArticle.

        Args:
            raw: Raw article data from API
            target_ticker: The ticker we searched for
            collected_at: Collection timestamp

        Returns:
            NewsArticle or None if relevance is too low
        """

        # Parse published date (Alpha Vantage format: 20241215T143000)
        time_published = raw.get('time_published', '')
        if time_published:
            try:
                pub_dt = datetime.strptime(time_published, '%Y%m%dT%H%M%S')
                published_at = pub_dt.isoformat() + 'Z'
            except ValueError:
                published_at = time_published
        else:
            published_at = ''

        # Get content
        title = raw.get('title', '')
        summary = raw.get('summary', '')
        content_length = len(summary)

        # Publisher (source field)
        publisher = raw.get('source', '')
        if publisher:
            self.stats['by_source'][publisher] = self.stats['by_source'].get(publisher, 0) + 1

        # Overall sentiment
        overall_score = raw.get('overall_sentiment_score')
        overall_label = raw.get('overall_sentiment_label', '')

        if overall_score is not None:
            self.stats['with_sentiment'] += 1

        # Per-ticker sentiment
        ticker_sentiments = raw.get('ticker_sentiment', [])
        ticker_sentiment_json = json.dumps(ticker_sentiments)

        # Find relevance score for target ticker
        relevance_score = None
        ticker_specific_sentiment = None
        for ts in ticker_sentiments:
            if ts.get('ticker', '').upper() == target_ticker.upper():
                relevance_score = float(ts.get('relevance_score', 0))
                ticker_specific_sentiment = float(ts.get('ticker_sentiment_score', 0))
                break

        # Skip low relevance articles (too much noise otherwise)
        # Alpha Vantage returns articles that merely mention the ticker
        if relevance_score is not None and relevance_score < 0.3:
            return None

        # Use ticker-specific sentiment if available, else overall
        sentiment_score = ticker_specific_sentiment if ticker_specific_sentiment is not None else overall_score
        sentiment_label = overall_label

        # Get topics/categories
        topics = raw.get('topics', [])
        if topics:
            tags = [t.get('topic', '') for t in topics if t.get('topic')]
            category = tags[0] if tags else ''
        else:
            tags = []
            category = ''

        # Related tickers (all mentioned tickers)
        related_tickers = [ts.get('ticker', '') for ts in ticker_sentiments]

        # Generate dedup hash
        pub_date = published_at[:10] if published_at else ''
        hash_input = f"{target_ticker.upper()}|{title.strip().lower()}|{pub_date}"
        dedup_hash = hashlib.md5(hash_input.encode()).hexdigest()

        # Article ID (use URL hash)
        url = raw.get('url', '')
        article_id = hashlib.md5(url.encode()).hexdigest() if url else dedup_hash

        return NewsArticle(
            article_id=article_id,
            ticker=target_ticker,
            title=title,
            published_at=published_at,
            source_api="alphavantage",
            description=summary,
            content=summary,
            url=url,
            publisher=publisher,
            author=','.join(raw.get('authors', [])),
            related_tickers=json.dumps(related_tickers),
            tags=json.dumps(tags),
            category=category,
            source_sentiment=sentiment_score,
            source_sentiment_label=sentiment_label,
            collected_at=collected_at.isoformat(),
            content_length=content_length,
            dedup_hash=dedup_hash,
            ticker_sentiment=ticker_sentiment_json,
            relevance_score=relevance_score,
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
                        if key == 'ALPHA_VANTAGE_API_KEY' and not value.startswith('your_'):
                            return value

    return os.environ.get('ALPHA_VANTAGE_API_KEY', '')


def collect_news(
    tickers: List[str],
    time_from: Optional[datetime] = None,
    time_to: Optional[datetime] = None,
) -> dict:
    """Main collection function."""

    # Load API key
    api_key = load_env()
    if not api_key:
        logger.error("ALPHA_VANTAGE_API_KEY not found in config/.env or environment")
        sys.exit(1)

    # Initialize
    config = AlphaVantageConfig()
    collector = AlphaVantageNewsCollector(api_key, config)
    storage = StorageManager(config.data_dir)

    collected_at = datetime.now()

    logger.info(f"Starting Alpha Vantage collection: {len(tickers)} tickers")
    if time_from and time_to:
        logger.info(f"Time range: {time_from} to {time_to}")
    logger.info(f"Rate limit: {config.requests_per_minute} calls/min, {config.daily_limit} calls/day")
    logger.info(f"Remaining calls today: {collector.rate_limiter.get_remaining_calls()}")

    all_articles = []

    try:
        for i, ticker in enumerate(tickers):
            progress = (i + 1) / len(tickers) * 100
            remaining = collector.rate_limiter.get_remaining_calls()
            logger.info(f"[{progress:.1f}%] {ticker} (remaining calls: {remaining})")

            if remaining <= 0:
                logger.error("Daily limit reached! Stopping collection.")
                break

            # Fetch news for this ticker
            raw_articles = collector.fetch_news(
                tickers=[ticker],
                time_from=time_from,
                time_to=time_to,
                sort="LATEST",
                limit=200,
            )

            if raw_articles:
                # Parse articles (filter out None for low relevance)
                articles = [
                    a for a in
                    (collector.parse_article(raw, ticker, collected_at) for raw in raw_articles)
                    if a is not None
                ]
                all_articles.extend(articles)
                logger.info(f"  Found {len(articles)} relevant articles (filtered from {len(raw_articles)})")
            else:
                logger.debug(f"  No articles found")

    except RuntimeError as e:
        if "Daily API limit exceeded" in str(e):
            logger.warning("Collection stopped due to daily limit.")
        else:
            raise

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
    logger.info(f"With sentiment: {collector.stats['with_sentiment']}")
    logger.info(f"Errors: {collector.stats['errors']}")
    logger.info(f"Remaining daily calls: {collector.rate_limiter.get_remaining_calls()}")

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
        description='Collect news from Alpha Vantage API (with AI sentiment)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Collect recent news for specific tickers
    python collect_alphavantage_news.py --tickers AAPL,MSFT

    # Collect with time range
    python collect_alphavantage_news.py --start 2024-12-01 --end 2024-12-15

    # Show data status
    python collect_alphavantage_news.py --status

Note: Free tier only allows 25 API calls per DAY!
Each ticker uses 1 call, so you can only query ~25 tickers/day.

Alpha Vantage provides detailed AI sentiment analysis:
- Overall sentiment score (-1 to 1)
- Per-ticker sentiment and relevance scores
- Sentiment labels (Bullish, Somewhat-Bullish, Neutral, etc.)
        """
    )

    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers')
    parser.add_argument('--status', action='store_true',
                       help='Show current data status without collecting')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: fetch since last collected date')

    args = parser.parse_args()

    # Handle --status mode first
    if args.status:
        config = AlphaVantageConfig()
        storage = StorageManager(config.data_dir)
        status = storage.get_data_status()

        logger.info("\n" + "=" * 60)
        logger.info("ALPHA VANTAGE NEWS DATA STATUS")
        logger.info("=" * 60)
        logger.info(f"Total articles: {status['total_articles']:,}")
        logger.info(f"Total files: {status['total_files']}")
        logger.info(f"Unique tickers: {status.get('unique_tickers', 0)}")
        logger.info(f"Date range: {status['date_range']['earliest']} to {status['date_range']['latest']}")

        if status['by_year']:
            logger.info("\nBy year:")
            for year, count in sorted(status['by_year'].items()):
                logger.info(f"  {year}: {count:,} articles")

        logger.info("\nNote: Alpha Vantage free tier allows only 25 calls/day.")

        return

    # Determine time range
    time_to = datetime.now()
    time_from = None

    if args.end:
        time_to = datetime.fromisoformat(args.end)

    if args.incremental:
        config = AlphaVantageConfig()
        storage = StorageManager(config.data_dir)
        latest_ts = storage.get_latest_timestamp()

        if latest_ts:
            if latest_ts.tzinfo is not None:
                latest_ts = latest_ts.replace(tzinfo=None)
            time_from = latest_ts + timedelta(seconds=1)

            if time_from > time_to:
                logger.info(f"Data is already up to date (latest: {latest_ts.isoformat()})")
                return

            logger.info(f"INCREMENTAL MODE")
            logger.info(f"  Latest article: {latest_ts.isoformat()}")
            logger.info(f"  Fetching from: {time_from}")
        else:
            # No existing data, fetch last 7 days
            time_from = time_to - timedelta(days=7)
            logger.info(f"No existing data. Fetching last 7 days.")
    elif args.start:
        time_from = datetime.fromisoformat(args.start)

    # Load tickers
    tickers = load_tickers(args.tickers)

    # Warn about free tier limits
    logger.warning(f"Will query {len(tickers)} tickers (free tier: 25 calls/day)")
    if len(tickers) > 25:
        logger.warning("This exceeds free tier! Consider using fewer tickers or paid plan.")
        # Truncate to 25 for safety
        tickers = tickers[:25]
        logger.warning(f"Truncated to first 25 tickers: {', '.join(tickers[:5])}...")

    # Collect
    stats = collect_news(tickers, time_from, time_to)

    # Save stats
    stats_path = Path("data/news/metadata/alphavantage_collection_stats.json")
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, 'w') as f:
        json.dump({
            'completed_at': datetime.now().isoformat(),
            'tickers': tickers,
            'time_from': time_from.isoformat() if time_from else None,
            'time_to': time_to.isoformat() if time_to else None,
            **stats,
        }, f, indent=2)

    logger.info(f"\nStats saved to: {stats_path}")


if __name__ == "__main__":
    main()