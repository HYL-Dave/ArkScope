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

### 發布商完整比較 (2022/1 ~ 2025/12)

| Publisher | Polygon | Finnhub | IBKR | 狀態 |
|-----------|---------|---------|------|------|
| The Motley Fool | 41,114 (2022~2025) | - | - | ✓ 活躍 |
| Zacks Investment Research | 28,837 (2022~2025/06) | - | - | ⚠️ 停用 |
| DJ-N (Dow Jones) | - | - | 24,810 (2025/06~) | ✓ 活躍 |
| Benzinga | 18,312 (2022~2025) | - | - | ✓ 活躍 |
| MarketWatch | 6,252 (2022~2025/09) | 5 | - | ⚠️ 減少 |
| GlobeNewswire | 5,121 (2022~2025) | - | - | ✓ 活躍 |
| Investing.com | 3,960 (2022~2025) | - | - | ✓ 活躍 |
| Yahoo | - | 3,943 (2020~2025) | - | ✓ 活躍 |
| Seeking Alpha | 3,512 (2022~2024/07) | - | - | ⚠️ 停用 |
| FLY (The Fly) | - | - | 2,823 (2025/11~) | ✓ 活躍 |
| SeekingAlpha | - | 1,295 (2025/12~) | - | ✓ 活躍 |
| BRFUPDN (Briefing) | - | - | 891 (2024~2025) | ✓ 活躍 |
| DJ-RTA (Dow Jones RTA) | - | - | 576 (2025/06~) | ✓ 活躍 |
| Invezz | 523 (2022~2024/07) | - | - | ⚠️ 停用 |
| CNBC | - | 343 (2025/12~) | - | ✓ 活躍 |
| BRFG (Briefing) | - | - | 193 (2023~2025) | ✓ 活躍 |

**已停用 Publishers (Polygon)**:
- `Seeking Alpha`: 最後出現 2024-07-02
- `Zacks Investment Research`: 最後出現 2025-06-20
- `Invezz`: 最後出現 2024-07-18
- `Quartz`: 最後出現 2022-07-22

> 注：Finnhub 中 `SeekingAlpha` 仍活躍，只是 Polygon 停止提供

**IBKR 獨有高品質來源**:

| 發布商 | 說明 | 內容類型 |
|--------|------|----------|
| DJ-N | Dow Jones Newswires | 完整財經報導 (HTML) |
| DJ-RTA | Dow Jones Real-Time Analysis | 即時分析 (HTML) |
| FLY | The Fly | 盤前/盤後快訊 (純文字) |
| BRFG | Briefing.com | 市場分析 (純文字) |
| BRFUPDN | Briefing Upgrades/Downgrades | 升降級快訊 |

### 欄位一致性

三個來源的 Parquet 欄位**結構一致** (18 欄位)，但**內容完整度不同**：

| 欄位                   | Polygon | Finnhub | IBKR       |
|------------------------|---------|---------|------------|
| `title`                | ✓       | ✓       | ✓          |
| `published_at`         | ✓       | ✓       | ✓          |
| `publisher`            | ✓       | ✓       | ✓          |
| `description`          | ✓       | ✓ (1%空)| ✓ (需fetch)|
| `content`              | ✓       | ✓ (1%空)| ✓ (需fetch)|
| `url`                  | ✓       | ✓       | **空**     |
| `author`               | ✓       | **空**  | **空**     |
| `category`             | **空**  | ✓       | **空**     |
| `tags`                 | ✓       | ✓       | **空**     |
| `source_sentiment`     | ✓       | **None**| **None**   |
| `source_sentiment_label`| ✓      | **空**  | **空**     |

> **IBKR 說明**: 預設會呼叫 `reqNewsArticle` 取得完整內容。
> 使用 `--headlines-only` 可只取標題 (快速模式)。
> 使用 `--backfill-body` 可補抓現有標題的內文。

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

## API 限制與內容截斷

### 呼叫頻率限制

| 來源    | Rate Limit          | 歷史深度     | 說明                          |
|---------|---------------------|--------------|-------------------------------|
| Polygon | 5 calls/min (免費)  | 3+ 年        | 付費版無限制                  |
| Finnhub | 60 calls/min        | ~7 天        | API 只支援天數範圍 (from/to)  |
| IBKR    | 60 requests/10min   | ~1 個月      | 文章內容保留 2+ 年            |

### ⚠️ 內容截斷分析

各 API 回傳的內容類型和長度限制不同，需特別注意：

| 來源    | 內容類型     | 最大長度      | 截斷風險          |
|---------|--------------|---------------|-------------------|
| Polygon | 摘要/節錄    | ~8,300 chars  | 低 (明確標示)     |
| Finnhub | 摘要         | ~2,300 chars  | **高 (隱性截斷)** |
| IBKR    | 完整文章     | ~12,400 chars | 低 (無固定截斷)   |

**Finnhub 截斷深度分析**：

經過深度分析，發現截斷行為有以下特徵：

| 特徵 | 說明 |
|------|------|
| 影響來源 | **僅 Yahoo** (SeekingAlpha/CNBC 無截斷) |
| 截斷點 | 100 chars 和 500 chars |
| 截斷位置 | 80-88% 在單字中間 (letter_end) |
| 發生機制 | **Finnhub API 端動態截斷** (非 Yahoo 端) |

**截斷證據**：
- 同一篇文章對不同 ticker 查詢可能返回不同長度
- 同一篇文章在不同時間收集可能返回不同長度

```
# 範例：同篇文章不同長度
"Nvidia Vs. Alphabet: Which Could Be The World's Biggest..."
  12/18 收集 (GOOGL, GOOG, NVDA): 253 chars
  12/20 收集 (相同 tickers):      500 chars ← 截斷點
```

**各發布商截斷統計**：

| 發布商       | 總數    | 100-cut | 500-cut | 結尾正常率 | 說明           |
|--------------|---------|---------|---------|-----------|----------------|
| Yahoo        | 4,405   | 5.0%    | 5.5%    | ~85%      | 有截斷問題     |
| SeekingAlpha | 1,295   | 0.3%    | 0%      | 95.5%     | 自然短 (摘要式)|
| CNBC         | 343     | 0.9%    | 0%      | 75.5%     | 自然短 (摘要式)|

**結論**：Finnhub 截斷是 API 端的動態行為，無法透過調整參數避免。

**Polygon 說明**：

Polygon 提供的是文章摘要，非完整內容，結尾常見：
- `"Full story available on Benzinga.com"`
- `"...first on Invezz."`

這是設計如此，非截斷問題。

**IBKR 內容分析**：

| 發布商  | 內容長度範圍        | 格式     |
|---------|---------------------|----------|
| DJ-N    | 558 - 12,415 chars  | HTML     |
| DJ-RTA  | 1,216 - 12,083 chars| HTML     |
| FLY     | 211 - 2,963 chars   | 純文字   |
| BRFG    | 947 - 3,667 chars   | 純文字   |
| BRFUPDN | 125 - 229 chars     | 升降級快訊|

### 失敗類型

| 來源    | 錯誤碼    | 訊息         | 原因           | 比例   |
|---------|-----------|--------------|----------------|--------|
| IBKR    | 10172     | 無數據       | 文章已刪除/過期| ~0.32% |

**IBKR 下載失敗詳細分析 (2025-12-21)**:

| Publisher | 失敗數 | 失敗率 | 說明 |
|-----------|--------|--------|------|
| FLY       | 86     | 3.0%   | 即時快訊，過期後被移除 |
| DJ-N      | 7      | 0.03%  | 極少數舊文章不可用 |
| BRFUPDN   | 1      | 0.1%   | 極少數 |
| DJ-RTA    | 1      | 0.2%   | 極少數 |

**失敗特徵**:
- 81/95 失敗集中於 2025-11-19
- 47 篇 title 以 `!` 開頭 (FLY 即時快訊格式)
- 原因: IBKR API 返回 error 10172 (文章不可用)
- FLY 來源的即時快訊可能有時效性限制

### Finnhub 截斷文章處理決策 (2025-12-21)

**決策**: 收集時直接跳過截斷文章，不儲存。

**原因**:

經深度分析，截斷文章對 LLM 情緒/風險評分價值極低：

| 截斷類型 | 完整句子 | 標題關鍵詞覆蓋 | LLM 評分可靠度 |
|----------|----------|----------------|----------------|
| 100 chars| 86.9% 無 | 38%            | 不可靠         |
| 500 chars| 87.6% 有1+句 | 58%        | 部分可靠       |

**具體問題**:
1. **100 chars**: 幾乎無法理解文章重點，91% 在單字中間截斷
2. **500 chars**: 可理解主旨但缺細節，可能導致 LLM 誤判

**跳過比例**: ~7.6% (462/6084 篇)

**替代方案評估**:
- ❌ 標記 `is_truncated` 欄位 → 增加資料結構複雜度，下游仍需處理
- ❌ 僅用標題評分 → 標題本身資訊量不足
- ✅ 收集時跳過 → 簡化資料流，確保所有文章品質一致

**實作**: `collect_finnhub_news.py` 中跳過 `publisher=='Yahoo' && content_length in [100, 500]`

### 建議對策

1. **Finnhub**:
   - 截斷文章已在收集時自動跳過，無需額外處理
   - 所有儲存的文章都是完整可用的

2. **Polygon**:
   - 接受其為摘要來源，適合快速情緒分析
   - 不適合需要完整上下文的深度分析

3. **IBKR**:
   - 優先使用，提供最完整的內容
   - 失敗的文章 (~0.6%) 可忽略

4. **合併策略**:
   - 有重複時優先保留 IBKR 版本
   - 其次 Polygon (有情緒分數)
   - 最後 Finnhub

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

*最後更新: 2025-12-21*