# 新聞數據儲存設計

## 目標

設計一個可持續收集、易於查詢、支援多來源的新聞儲存系統。

---

## 1. 目錄結構

```
data/
├── news/
│   ├── raw/                          # 原始數據 (按來源)
│   │   ├── polygon/
│   │   │   ├── 2024/
│   │   │   │   ├── 2024-01.parquet
│   │   │   │   ├── 2024-02.parquet
│   │   │   │   └── ...
│   │   │   └── 2025/
│   │   ├── finnhub/
│   │   ├── tiingo/
│   │   └── alpha_vantage/
│   │
│   ├── merged/                       # 合併去重後的數據
│   │   ├── 2024/
│   │   │   ├── 2024-01.parquet
│   │   │   └── ...
│   │   └── 2025/
│   │
│   ├── scored/                       # LLM 評分後的數據
│   │   ├── sentiment/
│   │   │   ├── claude_sonnet/
│   │   │   │   └── 2024-01.parquet
│   │   │   ├── gpt5/
│   │   │   └── ...
│   │   └── risk/
│   │       ├── claude_sonnet/
│   │       └── gpt5/
│   │
│   └── metadata/
│       ├── collection_log.json       # 收集日誌
│       ├── dedup_hashes.db           # 去重 hash (SQLite)
│       └── source_stats.json         # 來源統計
│
└── prices/                           # 股價數據 (獨立)
    ├── hourly/
    └── 15min/
```

---

## 2. 數據格式

### 2.1 推薦：Parquet

| 特性 | Parquet | CSV | JSON |
|------|---------|-----|------|
| 壓縮率 | ✅ 高 (~10x) | ❌ 無 | ❌ 無 |
| 查詢速度 | ✅ 快 (列式) | ❌ 慢 | ❌ 慢 |
| Schema | ✅ 強制 | ❌ 無 | ❌ 弱 |
| 增量寫入 | ⚠️ 需追加 | ✅ 易 | ⚠️ 需處理 |
| Python 支援 | ✅ pandas/pyarrow | ✅ pandas | ✅ json |

**決定**: 使用 Parquet 作為主要格式，CSV 作為交換格式

### 2.2 Schema 定義

```python
NEWS_SCHEMA = {
    # === 核心欄位 (必填) ===
    'article_id': str,          # UUID 或 hash
    'ticker': str,              # 主要股票代號
    'title': str,               # 標題
    'published_at': datetime,   # 發布時間 (UTC)
    'source_api': str,          # 來源 API (polygon/finnhub/tiingo)

    # === 內容欄位 ===
    'description': str,         # 摘要/描述
    'content': str,             # 完整內容 (如有)
    'url': str,                 # 原文連結

    # === 來源資訊 ===
    'publisher': str,           # 發布商 (Benzinga, CNBC, etc.)
    'author': str,              # 作者

    # === 分類標籤 ===
    'related_tickers': list,    # 相關股票
    'tags': list,               # 標籤
    'category': str,            # 類別 (earnings, merger, etc.)

    # === 內建情緒 (如有) ===
    'source_sentiment': float,  # 來源 API 提供的情緒分數
    'source_sentiment_label': str,  # 情緒標籤

    # === LLM 評分 (後處理) ===
    # 欄位名稱遵循 sentiment_{model} / risk_{model} 模式
    # Claude: sentiment_haiku, sentiment_sonnet, sentiment_opus
    # OpenAI: sentiment_o4_mini, sentiment_gpt_5, etc.
    'sentiment_{model}': int,   # 情緒分數 (1-5)
    'risk_{model}': int,        # 風險分數 (1-5)

    # === 元數據 ===
    'collected_at': datetime,   # 收集時間
    'content_length': int,      # 內容長度
    'dedup_hash': str,          # 去重 hash
}
```

---

## 3. 去重策略

### 3.1 Hash 計算

```python
import hashlib

def compute_article_hash(ticker: str, title: str, published_date: date) -> str:
    """
    基於 ticker + title + date 計算 hash。
    同一天同股票同標題視為重複。
    """
    hash_input = f"{ticker.upper()}|{title.strip().lower()}|{published_date.isoformat()}"
    return hashlib.md5(hash_input.encode()).hexdigest()
```

### 3.2 跨來源去重

不同 API 可能返回相同新聞（例如 Seeking Alpha 同時出現在 Polygon 和 Finnhub）：

```python
# 合併時優先順序
SOURCE_PRIORITY = {
    'polygon': 1,    # 最高優先 (有情緒)
    'alpha_vantage': 2,  # 有詳細情緒
    'tiingo': 3,
    'finnhub': 4,
}

def merge_duplicates(articles: List[NewsArticle]) -> List[NewsArticle]:
    """合併重複文章，保留優先來源的版本。"""
    by_hash = {}
    for art in articles:
        if art.dedup_hash not in by_hash:
            by_hash[art.dedup_hash] = art
        else:
            existing = by_hash[art.dedup_hash]
            # 保留優先級較高的來源
            if SOURCE_PRIORITY.get(art.source_api, 99) < SOURCE_PRIORITY.get(existing.source_api, 99):
                by_hash[art.dedup_hash] = art
            # 或保留內容較完整的版本
            elif len(art.content or '') > len(existing.content or ''):
                by_hash[art.dedup_hash] = art
    return list(by_hash.values())
```

---

## 4. 收集策略

### 4.1 歷史數據收集 (一次性)

```
2022-01 到 2024-12:
├── Polygon (主要) - 有歷史
├── Tiingo (補充) - 需測試歷史深度
└── Alpha Vantage - 跳過 (API 限制太嚴)

Finnhub: 無法用於歷史收集 (僅 ~7 天)
```

### 4.2 持續收集 (每日)

```
每日 00:00 UTC:
1. Polygon - 收集前一天新聞
2. Finnhub - 收集前一天新聞 (速度快，補充)
3. Tiingo - 收集前一天新聞
4. 合併去重
5. (可選) 觸發 LLM 評分
```

### 4.3 增量收集腳本

```bash
# 每日收集
python collect_daily_news.py --date yesterday --output data/news/raw/

# 指定日期範圍
python collect_daily_news.py --start 2024-12-01 --end 2024-12-14

# 僅特定來源
python collect_daily_news.py --sources polygon,finnhub --date yesterday
```

---

## 5. 查詢介面

### 5.1 按股票查詢

```python
def get_news_for_ticker(
    ticker: str,
    start_date: date,
    end_date: date,
    sources: List[str] = None,
    min_content_length: int = 0,
) -> pd.DataFrame:
    """獲取指定股票的新聞。"""
    pass
```

### 5.2 按時間查詢

```python
def get_news_for_date_range(
    start_date: date,
    end_date: date,
    tickers: List[str] = None,
) -> pd.DataFrame:
    """獲取指定時間範圍的所有新聞。"""
    pass
```

### 5.3 訓練數據導出

```python
def export_training_data(
    start_date: date,
    end_date: date,
    tickers: List[str],
    include_scores: bool = True,
    output_format: str = 'parquet',
) -> str:
    """導出訓練用數據集。"""
    pass
```

---

## 6. 內容品質處理

### 6.1 內容級別分類

```python
class ContentLevel(Enum):
    FULL = "full"           # 完整文章 (>500 chars)
    DESCRIPTION = "desc"    # 有摘要 (100-500 chars)
    TITLE_ONLY = "title"    # 僅標題 (<100 chars)
    EMPTY = "empty"         # 無內容

def classify_content(article: NewsArticle) -> ContentLevel:
    content_len = len(article.content or '')
    desc_len = len(article.description or '')

    if content_len > 500:
        return ContentLevel.FULL
    elif content_len > 100 or desc_len > 100:
        return ContentLevel.DESCRIPTION
    elif len(article.title or '') > 0:
        return ContentLevel.TITLE_ONLY
    return ContentLevel.EMPTY
```

### 6.2 品質過濾

```python
# 訓練時可選擇僅使用高品質內容
df_high_quality = df[
    (df['content_length'] > 100) &
    (df['publisher'].isin(HIGH_QUALITY_PUBLISHERS))
]
```

---

## 7. 估算儲存空間

### 每月數據量估算

| 來源 | 文章數/月 (5 stocks) | 平均大小 | 月儲存 |
|------|---------------------|---------|--------|
| Polygon | ~2,000 | 1 KB | ~2 MB |
| Finnhub | ~1,000 | 0.5 KB | ~0.5 MB |
| Tiingo | ~500 | 0.3 KB | ~0.15 MB |
| **合併去重後** | ~2,500 | 1 KB | ~2.5 MB |

**50 支股票 × 3 年 ≈ 4.5 GB** (Parquet 壓縮後 ~500 MB)

---

## 8. 實作優先順序

1. ✅ 定義 Schema 和目錄結構
2. ✅ 建立 `StorageManager` 類別
3. ✅ 實作去重邏輯 (MD5 hash)
4. ✅ 建立收集腳本
5. ⬜ 建立查詢介面
6. ⬜ 整合 LLM 評分流程

---

## 9. 已實作的收集腳本

### 9.1 腳本清單

| 腳本 | 用途 | Rate Limit | 歷史深度 |
|------|------|-----------|---------|
| `collect_polygon_news.py` | 歷史新聞收集 | 5/min (12s) | 3+ 年 |
| `collect_finnhub_news.py` | 即時新聞收集 | 60/min (1s) | ~7 天 |
| `collect_all_news.py` | 統一入口 | - | - |

### 9.2 使用方式

```bash
# === 完整歷史收集 (需要 ~10 小時) ===
python collect_polygon_news.py --full-history

# 估算時間
python collect_polygon_news.py --full-history --estimate

# 中斷後繼續
python collect_polygon_news.py --resume

# === 每日更新 (需要 ~1 分鐘) ===
python collect_finnhub_news.py

# === 統一入口 ===
python collect_all_news.py --full-history  # Polygon 歷史
python collect_all_news.py --daily         # Finnhub 每日
python collect_all_news.py --merge         # 合併去重
python collect_all_news.py --stats         # 查看統計
```

### 9.3 已實作功能

- ✅ Rate limiting (遵守免費額度限制)
- ✅ Checkpoint/Resume (長時間收集可中斷)
- ✅ Pagination (自動處理分頁)
- ✅ Deduplication (MD5 hash 去重)
- ✅ Parquet storage (壓縮儲存)
- ✅ Progress tracking (進度顯示)
- ✅ Error retry (錯誤重試)

### 9.4 資料品質比較 (2025-12-15 實測)

| 來源 | 7 天文章數 | 主要發布商 | 有情緒分數 |
|------|----------|-----------|----------|
| Polygon | 19-38 | Motley Fool (79%) | ✅ |
| Finnhub | 157+ | Yahoo (77%) | ❌ |

**結論**:
- Polygon: 文章較少但品質較高，有內建情緒
- Finnhub: 文章數量多但 77% 是 Yahoo 轉載

---


---

## 📚 相關文件 (Related Documents)

此設計文件已拆分為多個模組化文件：

| 文件 | 內容 | 位置 |
|------|------|------|
| **本文件** | 核心設計：目錄結構、Schema、收集策略 | `NEWS_STORAGE_DESIGN.md` |
| [新聞數據清單](docs/data/NEWS_DATA_INVENTORY.md) | 現有新聞數據來源總覽 | `docs/data/` |
| [評分數據清單](docs/data/SCORING_DATA_INVENTORY.md) | LLM 評分數據狀態 | `docs/data/` |
| [歷史分析紀錄](docs/analysis/HISTORICAL_ANALYSIS_LOG.md) | 分析實驗紀錄 | `docs/analysis/` |
| [評分比較報告](docs/analysis/SCORE_COMPARISON_REPORT.md) | A/B 評分比較分析 | `docs/analysis/` |
| [摘要比較報告](docs/analysis/SUMMARY_COMPARISON_REPORT.md) | Summary 類型比較 | `docs/analysis/` |

---

*文件拆分日期: 2025-12-31*
