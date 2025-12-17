# 新聞資料字典

## 資料儲存結構

```
data/news/
├── raw/                    # 原始資料 (按來源分開)
│   ├── polygon/
│   │   ├── 2022/
│   │   │   ├── 2022-01.parquet
│   │   │   └── ...
│   │   ├── 2023/
│   │   ├── 2024/
│   │   └── 2025/
│   │
│   └── finnhub/
│       └── 2025/
│           └── 2025-12.parquet
│
├── merged/                 # 合併去重後 (未來使用)
│
├── scored/                 # LLM 評分後 (未來使用)
│
└── metadata/
    ├── collection_stats.json              # Polygon 收集統計
    ├── finnhub_collection_stats.json      # Finnhub 收集統計
    └── polygon_collection_checkpoint.json # Polygon 進度檔
```

---

## Parquet 欄位定義

### 核心欄位

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `article_id` | str | 唯一識別碼 | `b409a923baf4...` |
| `ticker` | str | 主要股票代號 | `AAPL` |
| `title` | str | 新聞標題 | `Apple Reports Record Q4 Earnings` |
| `published_at` | str | 發布時間 (UTC ISO) | `2025-12-01T09:44:00Z` |
| `source_api` | str | 資料來源 API | `polygon` 或 `finnhub` |

### 內容欄位

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `description` | str | 新聞摘要 | `Apple Inc. reported...` |
| `content` | str | 完整內容 (通常同摘要) | 同上 |
| `url` | str | 原文連結 | `https://...` |
| `content_length` | int | 內容字數 | `218` |

### 來源資訊

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `publisher` | str | 發布商名稱 | `Investing.com`, `Yahoo` |
| `author` | str | 作者 (可能為空) | `Michael Kramer` |
| `category` | str | 分類 (Finnhub) | `company`, `general` |

### 相關標籤

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `related_tickers` | str (JSON) | 相關股票清單 | `["AAPL", "NVDA", "TSLA"]` |
| `tags` | str (JSON) | 標籤關鍵字 | `["earnings", "tech"]` |

### 情緒分數 (僅 Polygon)

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `source_sentiment` | float | 內建情緒分數 | `-1.0` (負面) ~ `1.0` (正面) |
| `source_sentiment_label` | str | 情緒標籤 | `positive`, `neutral`, `negative` |

**注意**: Finnhub 沒有情緒分數，這兩欄會是 `None` 和空字串。

### 元數據

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `collected_at` | str | 收集時間 (ISO) | `2025-12-15T09:21:04.047537` |
| `dedup_hash` | str | 去重用 MD5 hash | `f86b2c0c41bd...` |

---

## 去重邏輯

Hash 計算方式：
```python
hash_input = f"{ticker.upper()}|{title.strip().lower()}|{published_date}"
dedup_hash = md5(hash_input).hexdigest()
```

同一天、同股票、同標題 = 視為重複

---

## 資料來源比較

### 即時測試結果 (2025-12-15)

| 指標 | Polygon | Finnhub |
|------|---------|---------|
| 7 天文章數 (AAPL) | 19 | 158 |
| 7 天文章數 (30 stocks) | ~600 | 3,068 |
| 有情緒分數 | ✅ | ❌ |
| 歷史深度 | 3+ 年 | ~7 天 |

### 發布商分布

**Polygon (歷史數據)**:
| 發布商 | 佔比 |
|--------|------|
| The Motley Fool | ~50% |
| Benzinga | ~20% |
| Investing.com | ~15% |
| Zacks | ~10% |
| Seeking Alpha | ~5% (僅 6 個月前有) |

**Finnhub (最近 7 天)**:
| 發布商 | 文章數 | 佔比 |
|--------|--------|------|
| Yahoo | 2,135 | 70% |
| SeekingAlpha | 723 | 24% |
| CNBC | 176 | 6% |
| 其他 | 34 | <1% |

### 結論

| 來源 | 優點 | 缺點 | 用途 |
|------|------|------|------|
| **Polygon** | 有情緒分數、3 年歷史 | 文章較少、無 Yahoo | 歷史收集、訓練資料 |
| **Finnhub** | 文章多、有 Yahoo/CNBC | 無情緒、僅 7 天歷史 | 每日補充、即時新聞 |

---

## 收集策略

### 最佳實踐

```
時間軸:
           2022        2023        2024        2025.12     未來
           ←──────────────────────────────────────│──────────→
Polygon:   ██████████████████████████████████████│██████████  歷史 + 持續
Finnhub:                                   ██████│██████████  7 天前 + 持續
                                                 ↑
                                            開始收集
```

### 執行步驟

```bash
# Step 1: Finnhub 先跑 (快，~1 分鐘)
python scripts/collection/collect_finnhub_news.py

# Step 2: Polygon 歷史 (慢，~10 小時)
python scripts/collection/collect_polygon_news.py --full-history

# Step 3: 未來每天排程
0 6 * * * python scripts/collection/collect_finnhub_news.py
0 7 * * * python scripts/collection/collect_polygon_news.py --days 1
```

---

## 資料讀取範例

```python
import pandas as pd

# 讀取 Polygon 資料
df_polygon = pd.read_parquet('data/news/raw/polygon/2025/2025-12.parquet')

# 讀取 Finnhub 資料
df_finnhub = pd.read_parquet('data/news/raw/finnhub/2025/2025-12.parquet')

# 篩選特定股票
aapl_news = df_polygon[df_polygon['ticker'] == 'AAPL']

# 篩選有情緒分數的
with_sentiment = df_polygon[df_polygon['source_sentiment'].notna()]

# 合併兩個來源
combined = pd.concat([df_polygon, df_finnhub], ignore_index=True)

# 去重 (保留 Polygon 優先，因為有情緒)
combined = combined.sort_values('source_api')  # finnhub < polygon
combined = combined.drop_duplicates(subset=['dedup_hash'], keep='last')
```

---

*最後更新: 2025-12-15*