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
│   ├── finnhub/
│   │   └── 2025/
│   │       └── 2025-12.parquet
│   │
│   └── ibkr/               # IBKR 高品質新聞
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
    ├── ibkr_collection_stats.json         # IBKR 收集統計
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

### 情緒分數 (僅 Polygon 有值)

| 欄位 | 類型 | 說明 | 範例 |
|------|------|------|------|
| `source_sentiment` | float | 內建情緒分數 | `-1.0` (負面) ~ `1.0` (正面) |
| `source_sentiment_label` | str | 情緒標籤 | `positive`, `neutral`, `negative` |

**各來源情緒欄位狀態**:

| 來源    | source_sentiment         | source_sentiment_label      |
|---------|--------------------------|----------------------------|
| Polygon | **100% 有值** (0=neutral, 正=positive, 負=negative) | 100% 有值 |
| Finnhub | **100% None** (空值)     | 100% 空字串                |
| IBKR    | **100% None** (空值)     | 100% 空字串                |

> 注意：Polygon 的 0 是「中性」評分，不是空值；Finnhub/IBKR 是真正沒給分數 (None)

Polygon 情緒分數分布:
- 正數 (positive): ~61%
- 零 (neutral): ~22%
- 負數 (negative): ~17%

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

| 發布商          | 佔比  |
|-----------------|-------|
| The Motley Fool | ~50%  |
| Benzinga        | ~20%  |
| Investing.com   | ~15%  |
| Zacks           | ~10%  |
| Seeking Alpha   | ~5%   |

> 注：Seeking Alpha 僅 6 個月前有資料

**Finnhub (最近 7 天)**:

| 發布商       | 文章數 | 佔比  |
|--------------|--------|-------|
| Yahoo        | 2,135  | 70%   |
| SeekingAlpha | 723    | 24%   |
| CNBC         | 176    | 6%    |
| 其他         | 34     | <1%   |

**IBKR (高品質來源)**:

| 發布商        | 說明                    |
|---------------|-------------------------|
| Dow Jones     | 頂級財經新聞            |
| Briefing.com  | 即時市場分析            |
| The Fly       | 盤前/盤後快訊           |

### 欄位一致性

三個來源的 Parquet 欄位**結構一致** (18 欄位)，但**內容完整度不同**：

| 欄位                   | Polygon | Finnhub | IBKR    |
|------------------------|---------|---------|---------|
| `title`                | ✓       | ✓       | ✓       |
| `published_at`         | ✓       | ✓       | ✓       |
| `publisher`            | ✓       | ✓       | ✓       |
| `description`          | ✓       | ✓ (1%空)| **空**  |
| `content`              | ✓       | ✓ (1%空)| **空**  |
| `url`                  | ✓       | ✓       | **空**  |
| `author`               | ✓       | **空**  | **空**  |
| `category`             | **空**  | ✓       | **空**  |
| `tags`                 | ✓       | ✓       | **空**  |
| `source_sentiment`     | ✓       | **None**| **None**|
| `source_sentiment_label`| ✓      | **空**  | **空**  |

> **IBKR 說明**: `reqHistoricalNews` API 只回傳標題/發布商，
> 完整內容需對每篇文章額外呼叫 `reqNewsArticle`。
> 目前收集腳本為求速度未取內容，可視需求調整。

### 跨來源重複分析

使用 `dedup_hash` (同股票 + 標題 + 日期) 偵測跨來源重複:

| 來源組合               | 重複筆數 | 說明                              |
|------------------------|----------|-----------------------------------|
| Finnhub ↔ Polygon      | 48       | Yahoo 轉載 The Motley Fool        |
| Finnhub ↔ IBKR         | 20       | Yahoo 轉載 The Fly                |
| IBKR ↔ Polygon         | 1        | Benzinga 與 DJ-RTA 偶有重疊       |
| 三來源皆重複           | 1        | 極少數                            |

**關鍵發現**:

1. **Yahoo 是二手來源**: Finnhub 的 Yahoo 新聞大多轉載自 The Motley Fool、The Fly 等原始來源
2. **摘要內容不同**: 同一篇新聞在不同 API 的 `description` 欄位內容不同
   - Polygon: 通常較完整 (可能有 AI 摘要)
   - Finnhub: 較簡短
   - 原因: 各 API 的摘要生成邏輯不同
3. **去重建議**: 合併時保留 Polygon 版本 (有情緒分數 + 較完整摘要)

**範例** (同一篇新聞):
```
標題: The Best Warren Buffett Stocks to Buy With $10,000 Right Now

[Polygon/The Motley Fool] (170 字)
As Warren Buffett retires, the article recommends investing equally
in Alphabet, Amazon, and Apple as top picks...

[Finnhub/Yahoo] (96 字)
Invest equally in these three companies to profit from the
expansion of artificial intelligence...
```

### 結論

| 來源        | 優點                       | 缺點                   | 用途                 |
|-------------|----------------------------|------------------------|----------------------|
| **Polygon** | 有情緒分數、3 年歷史       | 文章較少、無 Yahoo     | 歷史收集、訓練資料   |
| **Finnhub** | 文章多、有 Yahoo/CNBC      | 無情緒、僅 7 天歷史    | 每日補充、即時新聞   |
| **IBKR**    | 高品質來源 (Dow Jones 等)  | 需 IBKR 帳號、速度較慢 | 專業新聞、即時補充   |

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

*最後更新: 2025-12-20*