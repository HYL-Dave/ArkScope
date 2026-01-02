#!/usr/bin/env python3
"""
IBKR 新聞收集腳本 (分離 metadata/content 設計)

IBKR 特點:
- 需要 IB Gateway/TWS 連線 (非 REST API)
- 來源品質最高: Dow Jones, Briefing.com, The Fly
- 歷史深度: ~1 個月
- 每次查詢上限: 300 篇/股票

收集模式 (Phase 1/2 分離設計):
- Phase 1 (metadata-only): 只取標題，快速 (~0.5 秒/股票)，不會超出 request 限制
- Phase 2 (fetch-content): 補抓 content，支持中斷恢復，追蹤每篇文章的 content_status

content_status 狀態:
- pending: 只有 metadata，尚未抓取 content
- fetched: 已成功抓取 content
- empty: API 回傳但無內容（該文章本來就沒有 body）
- failed: 抓取失敗（可重試）

使用方式:
    # ===== 基本收集 =====
    # 收集最近 7 天新聞 (含完整內容，預設)
    python collect_ibkr_news.py

    # 快速模式 Phase 1: 只取 metadata，避免 request 限制
    python collect_ibkr_news.py --metadata-only    # 或 --headlines-only

    # 收集最近 30 天
    python collect_ibkr_news.py --days 30

    # ===== 補抓 content (Phase 2) =====
    # 補抓 pending 狀態的文章內容
    python collect_ibkr_news.py --fetch-content    # 或 --backfill-body

    # 重試 failed 狀態的文章
    python collect_ibkr_news.py --fetch-content --retry-failed

    # 限制每次抓取數量 (避免長時間執行)
    python collect_ibkr_news.py --fetch-content --max-articles 1000

    # ===== 狀態查詢 =====
    # 查看現有資料狀態
    python collect_ibkr_news.py --status

    # 查看 content 收集狀態 (pending/fetched/empty/failed)
    python collect_ibkr_news.py --content-status

    # ===== 其他選項 =====
    # 增量更新
    python collect_ibkr_news.py --incremental

    # 僅收集指定股票
    python collect_ibkr_news.py --tickers AAPL,MSFT

    # 使用不同的 IB Gateway 連接 (或設置 IBKR_HOST 環境變數)
    python collect_ibkr_news.py --port 4001 --host <your-host>

典型工作流程:
    # 1. 快速收集所有 metadata (不會超出限制)
    python collect_ibkr_news.py --metadata-only --days 30

    # 2. 查看多少文章需要抓取 content
    python collect_ibkr_news.py --content-status

    # 3. 分批補抓 content (可中斷恢復)
    python collect_ibkr_news.py --fetch-content --max-articles 500
    # ... 可隨時中斷，下次繼續 ...
    python collect_ibkr_news.py --fetch-content --max-articles 500

    # 4. 重試失敗的文章
    python collect_ibkr_news.py --fetch-content --retry-failed

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


def load_ibkr_config_from_env(env_path: str = "config/.env") -> Dict[str, str]:
    """
    Load IBKR configuration from .env file.
    Same logic as collect_ibkr_prices.py for consistency.
    """
    config = {
        'IBKR_HOST': '127.0.0.1',
        'IBKR_PORT': '4002',
        'IBKR_CLIENT_ID': '50',
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
    save_every_n_tickers: int = 10  # Incremental save frequency (防止中斷時丟失數據)

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

    # Content status tracking (Phase 1/2 分離設計)
    # pending: 只有 metadata，尚未抓取 content
    # fetched: 已成功抓取 content
    # empty: API 回傳但無內容（該文章本來就沒有 body）
    # failed: 抓取失敗（可重試）
    content_status: str = "pending"
    content_fetch_attempts: int = 0
    content_fetched_at: str = ""


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
        ts = self.get_latest_timestamp()
        return ts.date() if ts else None

    def get_latest_timestamp(self) -> Optional[datetime]:
        """取得最新的發布時間戳 (精確到秒)"""
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

                    df['_pub_ts'] = pd.to_datetime(df['published_at'], errors='coerce')
                    max_ts = df['_pub_ts'].max()

                    if pd.notna(max_ts):
                        return max_ts.to_pydatetime()

                except Exception as e:
                    logger.warning(f"Error reading {parquet_file}: {e}")

        return None


# =============================================================================
# Global News Cache (優化：避免重複撈取相同文章的 body)
# =============================================================================

class GlobalNewsCache:
    """
    全域新聞快取，用 article_id 作為 key。

    由於 IBKR 的市場總覽文章會被多支股票查詢到，
    使用快取可以避免重複撈取相同文章的 body。

    效益估算:
    - 無快取: 100 tickers × 300 articles × body fetch = 30,000 body calls
    - 有快取: 只撈取唯一文章 ≈ 5,000 body calls (減少 83%)
    """

    def __init__(self):
        self.article_bodies: Dict[str, str] = {}  # article_id → body
        self.seen_article_ids: set = set()  # 已處理的 article_id

        # 統計
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_lookups': 0,
        }

    def has(self, article_id: str) -> bool:
        """檢查文章是否已在快取中"""
        return article_id in self.seen_article_ids

    def get(self, article_id: str) -> Optional[str]:
        """取得快取的 body"""
        self.stats['total_lookups'] += 1
        if article_id in self.article_bodies:
            self.stats['cache_hits'] += 1
            return self.article_bodies[article_id]
        return None

    def put(self, article_id: str, body: Optional[str]):
        """儲存 body 到快取"""
        self.seen_article_ids.add(article_id)
        if body:
            self.article_bodies[article_id] = body

    def mark_seen(self, article_id: str):
        """標記文章已處理（即使沒有 body）"""
        self.seen_article_ids.add(article_id)
        if article_id not in self.article_bodies:
            self.stats['cache_misses'] += 1

    def get_stats(self) -> dict:
        """取得快取統計"""
        hit_rate = 0
        if self.stats['total_lookups'] > 0:
            hit_rate = self.stats['cache_hits'] / self.stats['total_lookups'] * 100
        return {
            **self.stats,
            'unique_articles': len(self.seen_article_ids),
            'cached_bodies': len(self.article_bodies),
            'hit_rate_pct': round(hit_rate, 1),
        }

    def warm_up_from_existing(self, data_dir: Path):
        """從現有數據預載入已知的 article_id（不載入 body，僅標記已存在）"""
        if not data_dir.exists():
            return 0

        count = 0
        for parquet_file in data_dir.rglob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file, columns=['article_id'])
                for aid in df['article_id']:
                    self.seen_article_ids.add(aid)
                    count += 1
            except Exception:
                pass

        logger.info(f"  Cache warm-up: loaded {len(self.seen_article_ids)} unique article_ids from existing data")
        return len(self.seen_article_ids)


# =============================================================================
# IBKR News Collector
# =============================================================================

class IBKRNewsCollector:
    """IBKR 新聞收集器"""

    def __init__(self, config: IBKRConfig, fetch_body: bool = True, cache: Optional[GlobalNewsCache] = None):
        self.config = config
        self.fetch_body = fetch_body
        self.ibkr: Optional[IBKRDataSource] = None
        self.providers: List[Dict] = []
        self.cache = cache or GlobalNewsCache()  # 使用傳入的快取或建立新的

        # Statistics
        self.stats = {
            'total_articles': 0,
            'total_tickers': 0,
            'body_fetched': 0,
            'body_cached': 0,  # 從快取取得的數量
            'body_skipped': 0,  # 已知文章，跳過 body 撈取
            'body_failed': 0,
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

    def fetch_article_body(self, provider_code: str, article_id: str) -> Optional[str]:
        """抓取單篇文章的完整內容"""
        if not self.ibkr:
            return None

        try:
            time.sleep(self.config.request_delay)  # Rate limiting
            body = self.ibkr.fetch_news_article_body(provider_code, article_id)
            return body
        except Exception as e:
            logger.debug(f"Failed to fetch body for {article_id}: {e}")
            return None

    def fetch_news(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
    ) -> List[NewsArticle]:
        """抓取單一股票的新聞 (含內文，如果 fetch_body=True)"""
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
                provider = raw.source or 'unknown'
                if raw.description and '[Article ID:' in raw.description:
                    try:
                        start_idx = raw.description.index('[Article ID: ') + 13
                        end_idx = raw.description.index(']', start_idx)
                        article_id = raw.description[start_idx:end_idx]
                    except ValueError:
                        pass

                # Track by provider
                self.stats['by_provider'][provider] = self.stats['by_provider'].get(provider, 0) + 1

                # Fetch article body if enabled (使用快取優化)
                description = ""
                content = ""
                content_length = 0
                content_status = "pending"
                content_fetch_attempts = 0
                content_fetched_at = ""

                if self.fetch_body and article_id != dedup_hash:
                    # 先檢查快取
                    cached_body = self.cache.get(article_id)
                    if cached_body is not None:
                        # 快取命中
                        content = cached_body
                        description = cached_body[:500].strip()
                        if len(cached_body) > 500:
                            description += "..."
                        content_length = len(cached_body)
                        content_status = "fetched"
                        content_fetched_at = collected_at.isoformat()
                        self.stats['body_cached'] += 1
                    elif not self.cache.has(article_id):
                        # 快取未命中且未見過，需要撈取
                        content_fetch_attempts = 1
                        body = self.fetch_article_body(provider, article_id)
                        self.cache.put(article_id, body)  # 存入快取
                        content_fetched_at = datetime.now().isoformat()
                        if body:
                            content = body
                            description = body[:500].strip()
                            if len(body) > 500:
                                description += "..."
                            content_length = len(body)
                            content_status = "fetched"
                            self.stats['body_fetched'] += 1
                        elif body == "":
                            # API 回傳空內容（文章本身沒有 body）
                            content_status = "empty"
                            self.stats['body_failed'] += 1
                        else:
                            # None = 抓取失敗
                            content_status = "failed"
                            self.stats['body_failed'] += 1
                    else:
                        # 已知文章，跳過 body 撈取（從現有數據載入）
                        self.stats['body_skipped'] += 1

                articles.append(NewsArticle(
                    article_id=article_id,
                    ticker=ticker,
                    title=title,
                    published_at=published_at,
                    source_api="ibkr",
                    description=description,
                    content=content,
                    url=raw.url or "",
                    publisher=provider,
                    author="",
                    related_tickers=json.dumps([ticker]),
                    tags="",
                    category="",
                    source_sentiment=None,
                    source_sentiment_label="",
                    collected_at=collected_at.isoformat(),
                    content_length=content_length,
                    dedup_hash=dedup_hash,
                    content_status=content_status,
                    content_fetch_attempts=content_fetch_attempts,
                    content_fetched_at=content_fetched_at,
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
    fetch_body: bool = True,
    warm_up_ticker: str = "SPY",  # 用 SPY 暖機快取
) -> dict:
    """Main collection function."""

    # Validate date range (IBKR has ~1 month history)
    max_lookback = config.max_history_days
    oldest_allowed = date.today() - timedelta(days=max_lookback)

    if start_date < oldest_allowed:
        logger.warning(f"IBKR typically has ~{max_lookback} days of history!")
        logger.warning(f"Adjusting start_date from {start_date} to {oldest_allowed}")
        start_date = oldest_allowed

    # Initialize shared cache
    cache = GlobalNewsCache()

    # === 預載入已知的 article_id（避免重複處理）===
    logger.info(f"\n[Cache] Loading existing article_ids from {config.data_dir}...")
    existing_count = cache.warm_up_from_existing(config.data_dir)
    if existing_count > 0:
        logger.info(f"[Cache] Loaded {existing_count} existing article_ids")

    # Initialize
    collector = IBKRNewsCollector(config, fetch_body=fetch_body, cache=cache)
    storage = StorageManager(config.data_dir)

    # Connect
    if not collector.connect():
        logger.error("Failed to connect. Check IB Gateway is running.")
        sys.exit(1)

    try:
        target_year = end_date.year
        target_month = end_date.month

        mode_str = "完整內容" if fetch_body else "僅標題 (快速模式)"
        logger.info(f"\nStarting IBKR news collection")
        logger.info(f"Mode: {mode_str}")
        logger.info(f"Tickers: {len(tickers)}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Storage: {config.data_dir}")

        # === 快取暖機：先用 SPY 撈取市場新聞填充快取 ===
        if fetch_body and warm_up_ticker and warm_up_ticker not in tickers:
            logger.info(f"\n[Cache Warm-up] Fetching {warm_up_ticker} news to populate cache...")
            warm_up_articles = collector.fetch_news(warm_up_ticker, start_date, end_date)
            if warm_up_articles:
                logger.info(f"  Warmed up cache with {len(warm_up_articles)} articles")
                logger.info(f"  Unique bodies cached: {len(cache.article_bodies)}")

        batch_articles = []  # Current batch for incremental saving
        total_collected = 0
        total_saved = 0
        start_time = time.time()

        for i, ticker in enumerate(tickers):
            progress = (i + 1) / len(tickers) * 100
            logger.info(f"[{progress:.1f}%] {ticker}")

            articles = collector.fetch_news(ticker, start_date, end_date)

            if articles:
                batch_articles.extend(articles)
                total_collected += len(articles)
                body_info = ""
                if fetch_body:
                    with_body = sum(1 for a in articles if a.content_length > 0)
                    body_info = f" (with body: {with_body})"
                logger.info(f"  Found {len(articles)} articles{body_info}")
            else:
                logger.debug(f"  No articles")

            collector.stats['total_tickers'] += 1

            # Incremental save: save every N tickers to prevent data loss
            if (i + 1) % config.save_every_n_tickers == 0 and batch_articles:
                saved = storage.save_articles(batch_articles, target_year, target_month)
                total_saved += saved
                logger.info(f"  [Checkpoint] Saved batch: {saved} new articles (total saved: {total_saved})")
                batch_articles = []  # Clear batch after saving

            # Small delay between requests (only needed between tickers if not fetching body)
            if not fetch_body:
                time.sleep(config.request_delay)

        # Save remaining articles in the last batch
        if batch_articles:
            saved = storage.save_articles(batch_articles, target_year, target_month)
            total_saved += saved
            logger.info(f"  [Final] Saved remaining: {saved} new articles")

        collector.stats['total_articles'] = total_saved

        elapsed = time.time() - start_time

        # Final stats
        logger.info("\n" + "=" * 60)
        logger.info("Collection Complete")
        logger.info("=" * 60)
        logger.info(f"Mode: {mode_str}")
        logger.info(f"Total collected: {total_collected}")
        logger.info(f"Saved (deduplicated): {total_saved}")
        logger.info(f"Tickers processed: {collector.stats['total_tickers']}")

        if fetch_body:
            logger.info(f"Body fetched (new): {collector.stats['body_fetched']}")
            logger.info(f"Body from cache: {collector.stats['body_cached']}")
            logger.info(f"Body skipped (already known): {collector.stats['body_skipped']}")
            logger.info(f"Body failed: {collector.stats['body_failed']}")

            # Cache statistics
            cache_stats = cache.get_stats()
            logger.info(f"\nCache Statistics:")
            logger.info(f"  Unique articles seen: {cache_stats['unique_articles']}")
            logger.info(f"  Bodies cached: {cache_stats['cached_bodies']}")
            logger.info(f"  Cache hit rate: {cache_stats['hit_rate_pct']}%")

            # Calculate savings
            if collector.stats['body_cached'] > 0:
                total_body_requests = collector.stats['body_fetched'] + collector.stats['body_cached']
                savings_pct = collector.stats['body_cached'] / total_body_requests * 100
                logger.info(f"  API calls saved: {collector.stats['body_cached']} ({savings_pct:.1f}%)")

        logger.info(f"Errors: {collector.stats['errors']}")
        logger.info(f"Time elapsed: {elapsed:.1f}s")

        if len(tickers) > 0 and elapsed > 0:
            if fetch_body:
                total_requests = total_collected + len(tickers)
                logger.info(f"Rate: {total_requests / elapsed:.2f} requests/sec")
            else:
                logger.info(f"Rate: {len(tickers) / elapsed:.2f} tickers/sec")

        if collector.stats['by_provider']:
            logger.info("\nBy provider:")
            for provider, count in sorted(collector.stats['by_provider'].items(), key=lambda x: -x[1]):
                logger.info(f"  {provider}: {count}")

        return collector.stats

    finally:
        collector.disconnect()


def get_content_status(config: IBKRConfig) -> Dict[str, int]:
    """
    取得內容收集狀態統計

    Returns:
        Dict with counts for each content_status: pending, fetched, empty, failed
    """
    stats = {
        'pending': 0,
        'fetched': 0,
        'empty': 0,
        'failed': 0,
        'total': 0,
        'unique_articles': 0,
    }

    if not config.data_dir.exists():
        return stats

    seen_article_ids = set()

    for parquet_file in config.data_dir.rglob("*.parquet"):
        try:
            df = pd.read_parquet(parquet_file, engine='pyarrow')
            stats['total'] += len(df)

            # Track unique articles
            for aid in df['article_id']:
                seen_article_ids.add(aid)

            # Count by content_status (with backward compatibility)
            if 'content_status' in df.columns:
                for status_val in ['pending', 'fetched', 'empty', 'failed']:
                    stats[status_val] += int((df['content_status'] == status_val).sum())
            else:
                # Backward compatibility: infer from content_length
                stats['fetched'] += int((df['content_length'] > 0).sum())
                stats['pending'] += int((df['content_length'] == 0).sum())

        except Exception as e:
            logger.warning(f"Error reading {parquet_file}: {e}")

    stats['unique_articles'] = len(seen_article_ids)
    return stats


def backfill_body(
    config: IBKRConfig,
    retry_failed: bool = False,
    max_articles: Optional[int] = None,
    save_every: int = 50,
) -> dict:
    """
    補抓現有標題的內文（支持中斷恢復）

    Args:
        config: IBKR configuration
        retry_failed: If True, also retry articles with content_status='failed'
        max_articles: Maximum number of articles to process (for rate limiting)
        save_every: Save progress every N articles
    """
    from collections import defaultdict

    if not config.data_dir.exists():
        logger.error("No existing data to backfill")
        return {'error': 'no_data'}

    # Find articles to update based on content_status
    articles_to_update = []
    target_statuses = ['pending']
    if retry_failed:
        target_statuses.append('failed')

    for year_dir in sorted(config.data_dir.iterdir()):
        if not year_dir.is_dir():
            continue

        for parquet_file in year_dir.glob("*.parquet"):
            try:
                df = pd.read_parquet(parquet_file, engine='pyarrow')

                # Check if content_status column exists (backward compatibility)
                if 'content_status' in df.columns:
                    need_content = df[df['content_status'].isin(target_statuses)]
                else:
                    # Backward compatibility: use content_length
                    need_content = df[
                        (df['content'].isna()) |
                        (df['content'] == '') |
                        (df['content_length'] == 0)
                    ]

                if not need_content.empty:
                    for _, row in need_content.iterrows():
                        # Only process if we have a valid article_id (not just dedup_hash)
                        if row['article_id'] != row['dedup_hash']:
                            articles_to_update.append({
                                'file': parquet_file,
                                'article_id': row['article_id'],
                                'publisher': row['publisher'],
                                'dedup_hash': row['dedup_hash'],
                            })

            except Exception as e:
                logger.warning(f"Error reading {parquet_file}: {e}")

    # Deduplicate by article_id (same article may appear for multiple tickers)
    seen_ids = set()
    unique_articles = []
    for art in articles_to_update:
        if art['article_id'] not in seen_ids:
            seen_ids.add(art['article_id'])
            unique_articles.append(art)

    articles_to_update = unique_articles

    if not articles_to_update:
        logger.info("All articles already have content, nothing to backfill")
        return {'updated': 0}

    logger.info(f"Found {len(articles_to_update)} unique articles without content")

    if max_articles:
        articles_to_update = articles_to_update[:max_articles]
        logger.info(f"Processing first {max_articles} articles (--max-articles)")

    # Connect to IBKR
    collector = IBKRNewsCollector(config, fetch_body=True)
    if not collector.connect():
        logger.error("Failed to connect to IB Gateway")
        return {'error': 'connection_failed'}

    try:
        stats = {'updated': 0, 'failed': 0, 'empty': 0}
        start_time = time.time()

        # Group by file for efficient updates
        by_file = defaultdict(list)
        for art in articles_to_update:
            by_file[art['file']].append(art)

        processed_count = 0

        for parquet_file, articles in by_file.items():
            logger.info(f"\nProcessing {parquet_file.name}: {len(articles)} articles")

            df = pd.read_parquet(parquet_file, engine='pyarrow')

            # Ensure content_status columns exist
            if 'content_status' not in df.columns:
                df['content_status'] = df.apply(
                    lambda r: 'fetched' if r.get('content_length', 0) > 0 else 'pending',
                    axis=1
                )
            if 'content_fetch_attempts' not in df.columns:
                df['content_fetch_attempts'] = 0
            if 'content_fetched_at' not in df.columns:
                df['content_fetched_at'] = ""

            updated_count = 0

            for i, art in enumerate(articles):
                progress = (i + 1) / len(articles) * 100
                logger.info(f"  [{progress:.1f}%] Fetching body for {art['article_id'][:20]}...")

                body = collector.fetch_article_body(art['publisher'], art['article_id'])
                now_str = datetime.now().isoformat()

                mask = df['dedup_hash'] == art['dedup_hash']

                # Increment attempt count
                df.loc[mask, 'content_fetch_attempts'] = df.loc[mask, 'content_fetch_attempts'] + 1
                df.loc[mask, 'content_fetched_at'] = now_str

                if body:
                    # Success: update content
                    df.loc[mask, 'content'] = body
                    df.loc[mask, 'description'] = body[:500].strip() + ("..." if len(body) > 500 else "")
                    df.loc[mask, 'content_length'] = len(body)
                    df.loc[mask, 'content_status'] = 'fetched'
                    updated_count += 1
                    stats['updated'] += 1
                    logger.info(f"    ✓ Got {len(body)} chars")
                elif body == "":
                    # API returned empty content (article has no body)
                    df.loc[mask, 'content_status'] = 'empty'
                    stats['empty'] += 1
                    logger.info(f"    ○ Empty content (article has no body)")
                else:
                    # Failed to fetch
                    df.loc[mask, 'content_status'] = 'failed'
                    stats['failed'] += 1
                    logger.info(f"    ✗ Failed")

                processed_count += 1

                # Save progress periodically
                if processed_count % save_every == 0:
                    df.to_parquet(parquet_file, index=False, compression='snappy')
                    logger.info(f"  [Checkpoint] Saved progress ({processed_count} articles processed)")

            # Save final updates for this file
            df.to_parquet(parquet_file, index=False, compression='snappy')
            logger.info(f"  Saved {updated_count} updates to {parquet_file.name}")

        elapsed = time.time() - start_time
        logger.info("\n" + "=" * 60)
        logger.info("Backfill Complete (可中斷恢復)")
        logger.info("=" * 60)
        logger.info(f"Updated (fetched): {stats['updated']}")
        logger.info(f"Empty (no body):   {stats['empty']}")
        logger.info(f"Failed (can retry): {stats['failed']}")
        logger.info(f"Time: {elapsed:.1f}s")

        if stats['failed'] > 0:
            logger.info(f"\nTo retry failed articles: --backfill-body --retry-failed")

        return stats

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

    # Use different IB Gateway connection (or set IBKR_HOST env var)
    python collect_ibkr_news.py --host <your-host> --port 4001

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
    parser.add_argument('--host', type=str, default=None,
                       help='IB Gateway host (default: from config/.env)')
    parser.add_argument('--port', type=int, default=None,
                       help='IB Gateway port (default: from config/.env)')
    parser.add_argument('--client-id', type=int, default=None,
                       help='Client ID for connection (default: from config/.env)')
    parser.add_argument('--status', action='store_true', help='Show current data status')
    parser.add_argument('--content-status', action='store_true',
                       help='Show content collection status (pending/fetched/empty/failed)')
    parser.add_argument('--incremental', action='store_true',
                       help='Incremental update: fetch since last collected date')
    parser.add_argument('--headlines-only', '--metadata-only', action='store_true',
                       dest='headlines_only',
                       help='Fast mode: only fetch headlines/metadata, skip article body')
    parser.add_argument('--backfill-body', '--fetch-content', action='store_true',
                       dest='backfill_body',
                       help='Backfill: fetch body for existing headlines without content')
    parser.add_argument('--retry-failed', action='store_true',
                       help='With --backfill-body: also retry articles that previously failed')
    parser.add_argument('--max-articles', type=int, default=None,
                       help='With --backfill-body: limit number of articles to process')

    args = parser.parse_args()

    # Load IBKR config from .env (command line args override)
    ibkr_env = load_ibkr_config_from_env()
    ibkr_host = args.host if args.host else ibkr_env['IBKR_HOST']
    ibkr_port = args.port if args.port else int(ibkr_env['IBKR_PORT'])
    ibkr_client_id = args.client_id if args.client_id else int(ibkr_env.get('IBKR_CLIENT_ID', '50'))

    # Build config
    config = IBKRConfig(
        host=ibkr_host,
        port=ibkr_port,
        client_id=ibkr_client_id,
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

    # Handle --content-status mode
    if args.content_status:
        stats = get_content_status(config)

        logger.info("\n" + "=" * 60)
        logger.info("CONTENT COLLECTION STATUS")
        logger.info("=" * 60)
        logger.info(f"Total records:     {stats['total']:,}")
        logger.info(f"Unique articles:   {stats['unique_articles']:,}")
        logger.info("")
        logger.info(f"  Fetched (完成):  {stats['fetched']:,}")
        logger.info(f"  Pending (待抓):  {stats['pending']:,}")
        logger.info(f"  Empty (無內容):  {stats['empty']:,}")
        logger.info(f"  Failed (可重試): {stats['failed']:,}")

        if stats['pending'] > 0 or stats['failed'] > 0:
            logger.info("")
            if stats['pending'] > 0:
                logger.info(f"Run --backfill-body to fetch pending content")
            if stats['failed'] > 0:
                logger.info(f"Run --backfill-body --retry-failed to retry failed articles")

        return

    # Handle --backfill-body mode
    if getattr(args, 'backfill_body', False):
        logger.info("BACKFILL MODE: Fetching body for existing headlines")
        backfill_body(
            config,
            retry_failed=getattr(args, 'retry_failed', False),
            max_articles=getattr(args, 'max_articles', None),
        )
        return

    # Determine date range
    end_date = date.today()
    if args.end:
        end_date = date.fromisoformat(args.end)

    # Determine fetch_body mode (default: True, unless --headlines-only)
    fetch_body = not getattr(args, 'headlines_only', False)

    # Handle --incremental mode
    if args.incremental:
        storage = StorageManager(config.data_dir)
        latest_ts = storage.get_latest_timestamp()

        if latest_ts:
            # Use timestamp precision: start from 1 second after latest article
            start_timestamp = latest_ts + timedelta(seconds=1)
            start_date = start_timestamp.date()

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
    stats = collect_news(tickers, start_date, end_date, config, fetch_body=fetch_body)

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