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
    'sentiment_claude': int,    # Claude 情緒分數 (1-5)
    'sentiment_gpt5': int,      # GPT-5 情緒分數 (1-5)
    'risk_claude': int,         # Claude 風險分數 (1-5)
    'risk_gpt5': int,           # GPT-5 風險分數 (1-5)

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

## 10. 現有新聞數據清單 (2025-12-26)

### 10.1 數據來源總覽

| 數據來源 | 位置 | 行數 | 時間範圍 | 情緒分數狀態 | 內容完整度 |
|----------|------|------|----------|--------------|-----------|
| **FinRL DeepSeek** | `/mnt/md0/finrl/huggingface_datasets/` | 2,092,986 | 歷史 | ✅ 已有 `sentiment_deepseek` | ✅ Article + 4種摘要 |
| **FNSPID** | `NewsExtraction/fnspid_89_2013_2023_cleaned.csv` | 218,654 | 2013-2023 | ❌ 全部是 0 (佔位符) | ✅ Article + Lsa_summary |
| **Polygon** | `data/news/polygon_for_scoring.csv` | 63,412 | 2022-2025 | ❌ 82% NULL | ❌ 只有 description |
| **IBKR** | `data/news/raw/ibkr/` | 52,755 | 2023-2025 | ❌ 100% NULL | ✅ content 全文 |
| **Finnhub** | `data/news/raw/finnhub/2025/` | ~9,419 | 2025 | 未評分 | 待確認 |

### 10.2 已處理數據 (`/mnt/md0/finrl/`)

```
/mnt/md0/finrl/
├── gpt-5/
│   ├── summary/          # gpt-5 生成的摘要 (各種 reasoning/verbosity 組合)
│   ├── sentiment/        # gpt-5 情緒評分
│   └── risk/             # gpt-5 風險評分
├── gpt-5-mini/
│   ├── summary/          # gpt-5-mini 生成的摘要
│   ├── sentiment/        # gpt-5-mini 情緒評分
│   └── risk/             # gpt-5-mini 風險評分
├── o3/
│   └── risk/             # o3 風險評分
└── huggingface_datasets/
    └── FinRL_DeepSeek_sentiment/  # 原始 FinRL DeepSeek 數據 (209萬條)
```

### 10.3 合併文件

| 文件 | 位置 | 行數 | 說明 |
|------|------|------|------|
| IBKR 全部新聞 | `data/news/ibkr_all_news.parquet` | 52,755 | 2023-2025 IBKR 新聞合併 |

### 10.4 評分優先順序建議

| 優先級 | 數據集 | 任務 | 原因 |
|--------|--------|------|------|
| **1** | IBKR (52K) | sentiment + risk | 最新數據 (2023-2025)，有全文，完全沒有評分 |
| **2** | Polygon (63K) | sentiment + risk | 較新數據，無評分 |
| **3** | FNSPID (218K) | sentiment + risk | 歷史數據，Sentiment=0 是佔位符 |
| 低 | FinRL DeepSeek (2M) | 可選 Anthropic 評分對照 | 已有 DeepSeek 評分 |

### 10.5 Title vs Content 評分差異研究 (2025-12-26)

使用 IBKR 新聞數據 (45,246 筆同時有 title 和 content) 進行對比實驗：

#### 實驗設計
- **模型**: Claude Haiku (Batch API)
- **輸入 A**: `title` 欄位 (平均 69 chars)
- **輸入 B**: `content` 欄位 (平均 2,969 chars)
- **任務**: Sentiment scoring (1-5)

#### 結果摘要

| 指標 | 數值 | 說明 |
|------|------|------|
| 完全一致 | 53.6% | 同分數 |
| 差異 ±1 內 | 94.1% | 可接受範圍 |
| 差異 ≥2 | 5.9% | 顯著差異 |
| 相關係數 | 0.548 | 中等相關 |
| Title 平均分 | 3.25 | 偏樂觀 |
| Content 平均分 | 3.09 | 較中性 |

#### 差異分佈
```
差異值  筆數    說明
-4      1      Content 極度悲觀
-3      31
-2      1,850  Content 更悲觀
-1      11,737
 0      24,266 一致
+1      6,575
+2      728    Content 更樂觀
+3      50
+4      8      Content 極度樂觀
```

#### 關鍵發現

1. **Title 傾向樂觀偏差**: 標題為吸引點擊，用詞偏正面
2. **Content 提供修正資訊**: 全文包含風險、不確定性等細節
3. **相關性中等 (r=0.55)**: Title 可作為快速評估，但 Content 評分更可靠

#### 案例分析

同一則 NVDA 收購 Groq 新聞：
- Title: "Nvidia to Buy Chip-Designer Groq for $20B" → Score: 5 (very bullish)
- Content: 包含整合風險、監管審查等細節 → Score: 2 (bearish)

#### 建議

1. **有全文時優先用 Content 評分** — 更準確反映新聞影響
2. **無全文時用 Title 評分** — 作為 fallback
3. **研究應用**: 可用 Title-Content 差異作為「標題黨」指標

---

### 10.6 Title vs Content 風險評分差異研究 (2025-12-26)

使用 IBKR 新聞數據 (45,151 筆同時有 title 和 content) 進行風險評分對比：

#### 實驗設計
- **模型**: Claude Haiku (Batch API)
- **輸入 A**: `title` 欄位
- **輸入 B**: `content` 欄位
- **任務**: Risk scoring (1-5)

#### 結果摘要

| 指標 | Risk | Sentiment (對比) |
|------|------|------------------|
| 完全一致 | 45.7% | 53.6% |
| 差異 ±1 內 | 71.7% | 94.1% |
| 差異 ≥2 | 28.3% | 5.9% |
| 相關係數 | 0.262 | 0.548 |
| Title 平均分 | 1.834 | 3.25 |
| Content 平均分 | 2.213 | 3.09 |

#### 差異分佈
```
差異值  筆數    說明
-4      5      Content 極高風險
-3      179
-2      9,496  Content 更高風險 (21.0%)
-1      7,782
 0      20,642 一致 (45.7%)
+1      3,942
+2      3,064  Title 更高風險
+3      41
```

#### 關鍵發現

1. **風險評分差異比情緒更大**: 一致率僅 45.7% (vs 情緒 53.6%)
2. **Title 系統性低估風險**: 平均 1.83 vs Content 2.21
3. **21% 案例 Content 比 Title 高 2+ 分**: 標題傾向淡化風險
4. **相關性較低 (r=0.26)**: Title 無法可靠代表 Content 的風險評估

#### 結論

| 評分類型 | Title 可靠度 | 建議 |
|----------|-------------|------|
| Sentiment | 中等 (r=0.55) | Title 可作為快速評估 |
| Risk | 低 (r=0.26) | **必須使用 Content** |

風險評分對 Content 的依賴程度遠高於情緒評分。標題通常為吸引讀者而簡化或淡化風險細節，而全文包含具體的風險因素、不確定性和負面影響說明。

---

### 10.7 Claude 跨模型比較研究 (2025-12-26)

使用 FinRL 數據集 (77,871 筆有 gpt_5_summary) 對 Claude Haiku/Sonnet/Opus 進行評分比較：

#### 實驗設計
- **輸入**: `gpt_5_summary` 欄位 (GPT-5 生成的新聞摘要)
- **模型**: Claude Haiku, Sonnet, Opus (Batch API)
- **任務**: Sentiment (1-5) 和 Risk (1-5) 評分

#### Sentiment 評分結果

| Model | Mean | Std | 1分 | 2分 | 3分 | 4分 | 5分 |
|-------|------|-----|-----|-----|-----|-----|-----|
| Haiku | 3.344 | 0.899 | 1,047 | 12,701 | 29,334 | 27,967 | 6,822 |
| Sonnet | 3.307 | 0.781 | 614 | 11,682 | 30,723 | 32,913 | 1,939 |
| Opus | 3.287 | 0.694 | 364 | 8,390 | 38,978 | 28,829 | 1,310 |

**觀察**: Opus 最保守 (集中於中間值)，Haiku 最極端 (5分最多)

#### Risk 評分結果

| Model | Mean | Std | 1分 | 2分 | 3分 | 4分 | 5分 |
|-------|------|-----|-----|-----|-----|-----|-----|
| Haiku | 1.872 | 0.911 | 31,943 | 29,809 | 10,412 | 5,562 | 145 |
| Sonnet | 2.117 | 0.858 | 19,749 | 34,011 | 19,474 | 4,513 | 124 |
| Opus | 2.397 | 0.809 | 10,173 | 32,425 | 29,588 | 5,543 | 142 |

**觀察**: Haiku 偏低風險 (41% 給 1 分)，Opus 風險評估最高 (mean 2.40)

#### 跨模型相關性

**Sentiment 相關係數矩陣:**
```
          Haiku  Sonnet   Opus  DeepSeek
Haiku     1.000   0.833  0.805     0.496
Sonnet    0.833   1.000  0.826     0.484
Opus      0.805   0.826  1.000     0.471
DeepSeek  0.496   0.484  0.471     1.000
```

**Risk 相關係數矩陣:**
```
        Haiku  Sonnet   Opus
Haiku   1.000   0.645  0.578
Sonnet  0.645   1.000  0.571
Opus    0.578   0.571  1.000
```

#### 模型一致性

| 比較項目 | Sentiment | Risk |
|----------|-----------|------|
| 三模型完全一致 | **67.2%** | **34.1%** |
| Haiku-Sonnet | 78.2% | 57.2% |
| Sonnet-Opus | 81.3% | 60.3% |
| Haiku-Opus | 74.1% | 45.2% |

#### 關鍵發現

1. **Sentiment 一致性遠高於 Risk**: 67% vs 34% 三模型一致
2. **模型規模與保守程度正相關**:
   - Opus 最保守 (sentiment 偏中性，risk 評估最高)
   - Haiku 最極端 (sentiment 給高分多，risk 給低分多)
3. **Claude 與 DeepSeek 相關性中等** (~0.48)
   - 不同 LLM 對同一新聞的評分標準存在系統性差異
4. **Risk 評分主觀性更強**: 模型間相關性 (0.57-0.65) 低於 Sentiment (0.80-0.83)

#### 應用建議

| 場景 | 推薦模型 | 原因 |
|------|----------|------|
| 快速篩選 | Haiku | 成本低，分佈較廣 |
| 平衡選擇 | Sonnet | 中等保守，性價比高 |
| 謹慎評估 | Opus | 最保守，適合風險敏感場景 |
| 研究對照 | 多模型投票 | 可用一致性作為信心指標 |

---

### 10.8 Anthropic 評分命令

```bash
# IBKR 新聞評分 (使用 Batch API 省 50%)
python score_sentiment_anthropic.py \
    --input data/news/ibkr_all_news.parquet \
    --output data/news/ibkr_sentiment.parquet \
    --batch --model haiku \
    --symbol-column ticker \
    --text-column title

python score_risk_anthropic.py \
    --input data/news/ibkr_all_news.parquet \
    --output data/news/ibkr_risk.parquet \
    --batch --model haiku \
    --symbol-column ticker \
    --text-column title

# Polygon 新聞評分
python score_sentiment_anthropic.py \
    --input data/news/polygon_for_scoring.csv \
    --output data/news/polygon_sentiment.csv \
    --batch --model haiku

python score_risk_anthropic.py \
    --input data/news/polygon_for_scoring.csv \
    --output data/news/polygon_risk.csv \
    --batch --model haiku
```

---

### 10.9 FinRL 跨模型評分比較分析

使用 `/mnt/md0/finrl` 數據集（約 209 萬筆新聞）進行完整分析。

#### 實驗設計
- **數據源**: HuggingFace FinRL DeepSeek dataset
- **評分模型**: o3, o4-mini, gpt-4.1系列, gpt-5系列, Claude系列
- **輸入源**: Lsa_summary (原版), o3_summary, gpt_5_summary
- **Reasoning levels**: minimal, low, medium, high

#### 📊 資料完整性調查 (2025-12-27)

**原始資料:**
- HuggingFace dataset: **127,176 rows** (原始基準)

**Summary 生成結果:**

| 輸入源 | 行數 | 差異 | 說明 |
|--------|------|------|------|
| gpt_5_summary | 127,176 | 0 | 完整保留 |
| o3_summary | 127,176 | 0 | ✅ 修復完成 (2025-12-27) |

**o3_summary 遺失記錄追蹤:**
```
遺失 6 筆全部為 BKR (Baker Hughes) 股票，2020年7月：
- Row 19334: 2020-07-20 (Oil firm BJ Services files...)
- Row 19335: 2020-07-17 (Energy Sector Update...)
- Row 19336: 2020-07-16 (Interesting BKR Put And Call...)
- Row 19337: 2020-07-12 (Validea's Top Five Energy...)
- Row 19338: 2020-07-10 (Energy Sector Update...)
- Row 19339: 2020-07-07 (Down to handful of active rigs...)
```

**對齊驗證結果:** ✓ 無錯置，僅有跳過
```
檢查方式: 隨機抽樣 100 行 + 邊界區域逐行比對
結果: 0 筆錯置，所有分數都對應正確的文章

對齊模式:
  - o3_summary[0:19333] = 原始[0:19333]     ✓ 完全對齊
  - o3_summary[19334:] = 原始[19340:]       ✓ 偏移 6 後對齊
  - 所有使用 o3_summary 的評分檔案都繼承相同結構
```

**為什麼只有 ~77,871 筆可評分？**
```
原始 HuggingFace 資料 (127,176 rows):
- 有 Article 內容: 77,871 筆 (61.2%)
- 無 Article 內容: 49,305 筆 (38.8%) ← 無法生成 summary

Summary 來源限制:
- Lsa_summary: 77,871 有效 (從 Article 生成)
- gpt_5_summary: 77,871 有效 (從 Article 生成)
- o3_summary: 77,871 有效 ✅ (修復完成 2025-12-27)

DeepSeek 原始評分: 126,224 有效 (可能基於 title 評分)
```

**N 值差異完整解釋 (更新 2025-12-28):**

| 輸入源 | 原始行數 | 有效 Summary | 有效評分數 | 狀態 |
|--------|----------|--------------|------------|------|
| gpt_5_summary | 127,176 | 77,871 | 77,871 | ✅ 基準值 |
| o3_summary | 127,176 | 77,871 | 77,871 | ✅ 修復完成 |
| by_o3_summary (sentiment) | 127,176 | 77,871 | 77,871 | ✅ 修復完成 |
| by_o3_summary (risk) | 127,176 | 77,871 | 77,871 | ✅ 修復完成 |
| Lsa_summary (o3 high_4) | 127,176 | 77,871 | 85,119 | ⚠️ 舊版評分 |
| Lsa_summary (o4-mini high_1) | 127,176 | 77,871 | 79,631 | ⚠️ 舊版評分 |

**⚠️ 舊版評分檔案問題診斷 (high_4 / high_1):**

這些是較早期使用 HuggingFace 原始檔案進行評分的結果，**存在資料混合問題**：

| 檔案 | 模型 | text-column | 有效分數 | 問題 |
|------|------|-------------|----------|------|
| `sentiment_o3_high_4.csv` | o3 | `Lsa_summary` | 85,119 | 混合 DeepSeek 分數 |
| `sentiment_o4_mini_high_1.csv` | o4-mini | `Lsa_summary` | 79,631 | 混合 DeepSeek 分數 |

**✅ 污染假設驗證 (2025-12-28):**

經過詳細數據分析，確認符合**單純污染**假設：

```
基礎數據結構 (o3_news_with_summary.csv):
├── 總行數: 127,176
├── 有 Lsa_summary: 77,871 筆
├── 有 Article 但無 Lsa_summary: 0 筆 ← 關鍵！
└── 無 Article: 49,305 筆

high_4 交叉分析:
├── 有 Lsa_summary 且有評分: 77,871 筆 ← 100% 覆蓋 ✓
├── 有 Lsa_summary 但無評分: 0 筆
├── 無 Lsa_summary 但有評分: 7,248 筆 ← 污染
│   ├── 其中有 Article: 0 筆
│   └── 其中無 Article: 7,248 筆 ← 無法被 o3 評分
└── 無 Lsa_summary 且無評分: 42,057 筆

high_1 交叉分析:
├── 有 Lsa_summary 且有評分: 77,870 筆 (缺 1 筆)
├── 無 Lsa_summary 但有評分: 1,761 筆 ← 污染
└── 其中無 Article: 1,761 筆
```

**額外評分來源分析:**

| 類型 | high_4 | high_1 | 說明 |
|------|--------|--------|------|
| 與 DeepSeek 相同 | 6,100 (84.2%) | 1,460 (82.9%) | 直接複製 |
| 與 DeepSeek 不同 | 1,148 (15.8%) | 301 (17.1%) | 模型評了 Article_title |
| 不同分數值 | 全部 = 3.0 | - | 因無 Lsa_summary，返回預設值 |

**結論:** 這是單純污染，可使用**方案 A (過濾修復)**處理

**修復方案:**

| 方案 | 操作 | 優點 | 缺點 | 成本 |
|------|------|------|------|------|
| **A. 過濾修復** ✓ | 刪除無 Lsa_summary 的行 | 簡單、免費 | 損失 1,148 筆 Article_title 評分 | 免費 |
| **B. 棄用舊版** | 使用 by_o3_summary 替代 | 資料乾淨 | 輸入源不同 (Lsa vs o3) | 免費 |
| **C. 重新評分** | 用 Lsa_summary 重跑 | 完全乾淨 | 需 API 費用 | ~$934 (o3) / ~$69 (o4-mini) |

**建議:**
- 方案 A 最符合成本效益：損失的 1,148 筆都是因缺少 Lsa_summary 而返回預設值 3 的無效評分
- 若研究需要 `Lsa_summary` 作為輸入源 → 選方案 A
- 若只需乾淨資料且可接受 `o3_summary` 輸入 → 選方案 B (已有 by_o3_summary)

**過濾修復命令:**
```bash
# 過濾 high_4: 只保留有 Lsa_summary 的行
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('/mnt/md0/finrl/o3/sentiment/sentiment_o3_high_4.csv', low_memory=False)
has_lsa = df['Lsa_summary'].notna() & (df['Lsa_summary'].astype(str).str.strip() != '')
df[has_lsa].to_csv('/mnt/md0/finrl/o3/sentiment/sentiment_o3_high_4_filtered.csv', index=False)
print(f"過濾後: {has_lsa.sum()} 行")
EOF
```

**原始評分命令參考 (從 bash history):**
```bash
# o4-mini 評分命令 (早期版本)
python score_sentiment_openai.py \
    --input /mnt/md0/finrl/huggingface_datasets/FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv \
    --output /mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_1.csv \
    --model o4-mini --symbol-column Stock_symbol --text-column Lsa_summary \
    --date-column Date --chunk-size 20 --api-keys-file api_keys_tier5.txt
```

---

#### ⚠️ 重要：欄位命名問題 (2025-12-28 發現)

**問題描述：**

`score_sentiment_openai.py` 和 `score_risk_openai.py` 腳本將所有評分結果寫入固定欄位名：
- Sentiment → `sentiment_deepseek`
- Risk → `risk_deepseek`

**這導致嚴重的命名誤導：**
- 使用 o3 模型評分 → 結果仍寫入 `sentiment_deepseek`
- 使用 gpt-5 模型評分 → 結果仍寫入 `sentiment_deepseek`
- **欄位名不代表實際使用的模型！**

**實際數據狀態：**

| 檔案類型 | `sentiment_deepseek` 欄位內容 | 來源                         |
|----------|------------------------------|----------------------------|
| HuggingFace 原始 | 原始 DeepSeek 評分 (126,224) | DeepSeek 模型                |
| by_o3_summary 檔案 | **o3/gpt-5 等模型評分** (77,871) | OpenAI 模型                  |
| high_4/high_1 | 混合（原始 + 部分新評分） | o3 (high) / o4-mini (high) |

**驗證結果：**
```
HuggingFace vs by_o3_summary sentiment_deepseek 比較:
- 完全匹配: 31,374 (40.7%)  ← 僅因偶然相同
- 不匹配:   45,774 (59.3%)  ← 證明是不同評分
```

**建議修正（開源前必須執行）：**
1. 修改腳本使用模型特定欄位名（如 `sentiment_o3`, `risk_gpt5`）
2. 或創建統一欄位名（如 `sentiment_score`, `risk_score`）並在 metadata 記錄模型
3. 重新處理現有檔案以消除命名歧義

**修復完成狀態 (2025-12-28):**

| 階段 | 內容 | 狀態 |
|------|------|------|
| Stage 0 | 強制備份 | ✅ 完成 (2025-12-27) |
| Stage 1 | 修復 o3_summary 6 筆 BKR | ✅ 完成 |
| Stage 2 | 修復 13 個 sentiment 評分 (6 BKR) | ✅ 完成 |
| Stage 3 | 修復 o4-mini high sentiment 額外遺失 (Row 12543, 44893) | ✅ 完成 |
| Stage 4 | 修復 13 個 risk 評分 (6 BKR) | ✅ 完成 (2025-12-28) |
| Stage 5 | 修復 o4-mini high risk 額外遺失 (Row 18077, 52326) | ✅ 完成 (2025-12-28) |

**已知資料品質問題 (不需修復):**
```
Row 44887: 2015-11-25 | GILD → 原始 Article 為空 (NaN)，所有模型皆為 NaN
```
這是原始資料品質問題，不是處理錯誤。

> 📋 **修復記錄**: 詳見 `REPAIR_PLAN_O3_SUMMARY.md`
> 備份位置: `/mnt/md0/finrl/backups/repair_20251227/`

---

#### 按模型分組統計

> ⚠️ 注意：同一模型可能有多種配置（reasoning level、輸入源），因此總 N 為所有配置的加總。
> 公平比較請參考 10.10.2 節（控制輸入源為 o3_summary）。

**Sentiment 評分:**

| Model | 配置數 | 總 N | Mean | Std | 特徵 |
|-------|--------|------|------|-----|------|
| claude-haiku | 1 | 77,871 | 3.344 | 0.899 | 分佈較廣 |
| claude-opus | 1 | 77,871 | 3.287 | 0.694 | **最穩定** (std 最低) |
| claude-sonnet | 1 | 77,871 | 3.307 | 0.781 | 中等 |
| gpt-4.1 | 1 | 77,865 | 3.455 | 0.923 | **最樂觀** |
| gpt-4.1-mini | 6 | 467,220 | 3.460 | 0.957 | 樂觀 |
| gpt-4.1-nano | 1 | 77,865 | 3.319 | 0.886 | 中等 |
| gpt-5 | 8 | 622,944 | 3.304 | 0.769 | 保守，受 reasoning 影響 |
| gpt-5-mini | 1 | 77,871 | 3.408 | 0.943 | 略樂觀 |
| o3 | 5 | 396,585 | 3.293 | 0.797 | **最保守** |
| o4-mini | 4 | 313,224 | 3.379 | 0.937 | 偏樂觀 |

**Risk 評分:**

| Model | 配置數 | 總 N | Mean | Std | 特徵 |
|-------|--------|------|------|-----|------|
| claude-haiku | 1 | 77,871 | 1.872 | 0.911 | **最低風險傾向** (41%給1分) |
| claude-sonnet | 1 | 77,871 | 2.117 | 0.858 | 低風險 |
| gpt-4.1 | 1 | 77,865 | 2.236 | 0.924 | 低風險 |
| o4-mini | 4 | 311,464 | 2.248 | 0.884 | 低風險 |
| gpt-4.1-nano | 1 | 77,865 | 2.282 | 0.820 | 中低風險 |
| gpt-4.1-mini | 6 | 467,220 | 2.295 | 0.893 | 中低風險 |
| claude-opus | 1 | 77,871 | 2.397 | 0.809 | 中等風險 |
| gpt-5-mini | 1 | 77,871 | 2.433 | 0.720 | 中等風險 |
| o3 | 5 | 389,337 | 2.498 | 0.640 | 中高風險 |
| gpt-5 | 8 | 622,944 | 2.613 | 0.633 | **最高風險傾向** |

---

#### 分組兩兩比較

**Claude vs OpenAI 系列:**

| 比較項 | Claude (3模型) | OpenAI (7模型) | Δ (OpenAI - Claude) |
|--------|---------------|----------------|---------------------|
| **Sentiment** | N=233,613, Mean=3.313 | N=2,033,574, Mean=3.360 | **+0.047** (OpenAI 略樂觀) |
| **Risk** | N=233,613, Mean=2.129 | N=2,024,566, Mean=2.427 | **+0.298** (OpenAI 評估風險較高) |

**Reasoning vs Non-reasoning 模型:**

| 比較項 | Reasoning (o3, o4-mini, gpt-5) | Non-reasoning (gpt-4.1系列, claude) | Δ |
|--------|-------------------------------|-------------------------------------|---|
| **Sentiment** | N=1,410,624, Mean=3.323 | N=856,563, Mean=3.407 | **-0.083** (Reasoning 較保守) |
| **Risk** | N=1,401,616, Mean=2.490 | N=856,563, Mean=2.243 | **+0.247** (Reasoning 評估風險較高) |

**關鍵發現:**
1. **OpenAI 比 Claude 更樂觀** — Sentiment 高 0.05 分，Risk 高 0.30 分
2. **Reasoning 模型更謹慎** — Sentiment 向中性集中 (低 0.08)，Risk 評估更高 (高 0.25)
3. **風險評估差異大於情緒** — Risk 的模型間差異約為 Sentiment 的 3-6 倍

---

#### 配置命名說明

在以下表格中，配置名稱使用以下縮寫：

| 縮寫 | 全稱 | 說明 |
|------|------|------|
| R= | Reasoning effort | 評分模型的推理強度 (僅適用於 reasoning models) |
| S= | Summary reasoning | gpt-5 生成 summary 時使用的推理強度 |
| V= | Verbosity | gpt-5 生成 summary 時的詳細程度 |
| in= | Input source | 輸入的 summary 來源 |

**標準 Summary 來源說明:**

| 輸入源名稱 | 實際檔案 | 生成模型 | 配置 |
|-----------|----------|----------|------|
| `o3_summary` | `o3_news_with_summary.csv` | o3 | 預設 |
| `gpt_5_summary` | `gpt-5_reason_high_verbosity_high_summary.csv` | gpt-5 | R=high, V=high |
| `Lsa_summary` | HuggingFace 原始 CSV | 傳統演算法 | LSA 摘要 |

**使用標準 Summary 的模型:**
- **Claude (haiku/sonnet/opus)**: 全部使用 `gpt_5_summary` (R=high, V=high)
- **o3**: 使用 `o3_summary` 或 `gpt_5_summary` (R=high, V=high)
- **gpt-5**: 使用 `o3_summary` 或 `gpt_5_summary` (R=high, V=high)
- **gpt-4.1 / gpt-4.1-nano**: 使用 `o3_summary`
- **gpt-4.1-mini**: 使用 `o3_summary` 或 5 種不同的 gpt-5 summary 配置 (見下方)

**gpt-4.1-mini 特殊說明**: 此模型本身是非推理模型 (無 R 參數)，但其輸入的 `gpt_5_summary` 有 5 種不同的 gpt-5 生成配置組合：

| 配置 | 對應檔案 |
|------|----------|
| S=high, V=high | `gpt-5_reason_high_verbosity_high_summary.csv` |
| S=high, V=medium | `gpt-5_reason_high_verbosity_medium_summary.csv` |
| S=medium, V=high | `gpt-5_reason_medium_verbosity_high_summary.csv` |
| S=low, V=high | `gpt-5_reason_low_verbosity_high_summary.csv` |
| S=minimal, V=high | `gpt-5_reason_minimal_verbosity_high_summary.csv` |

---

#### Sentiment 評分結果 (每配置獨立 N 值)

| 配置 | N | Mean | Std | 輸入源 |
|------|---|------|-----|--------|
| gpt-5 (R=high, in=gpt_5_summary) | 77,871 | 3.234 | 0.716 | gpt_5_summary |
| gpt-5 (R=high, in=o3_summary) | 77,865 | 3.236 | 0.717 | o3_summary |
| gpt-5 (R=medium, in=o3_summary) | 77,865 | 3.271 | 0.748 | o3_summary |
| o3 (R=high, in=Lsa_summary) | 85,119 | 3.276 | 0.729 | Lsa_summary |
| claude-opus (in=gpt_5_summary) | 77,871 | 3.287 | 0.694 | gpt_5_summary |
| o3 (R=low, in=o3_summary) | 77,865 | 3.294 | 0.794 | o3_summary |
| o3 (R=high, in=o3_summary) | 77,865 | 3.298 | 0.824 | o3_summary |
| o3 (R=medium, in=o3_summary) | 77,865 | 3.299 | 0.817 | o3_summary |
| o3 (in=gpt_5_summary) | 77,871 | 3.300 | 0.822 | gpt_5_summary |
| gpt-5 (R=low, in=o3_summary) | 77,865 | 3.304 | 0.778 | o3_summary |
| claude-sonnet (in=gpt_5_summary) | 77,871 | 3.307 | 0.781 | gpt_5_summary |
| gpt-4.1-nano (in=o3_summary) | 77,865 | 3.319 | 0.886 | o3_summary |
| claude-haiku (in=gpt_5_summary) | 77,871 | 3.344 | 0.899 | gpt_5_summary |
| o4-mini (R=high, in=Lsa_summary) | 79,631 | 3.346 | 0.892 | Lsa_summary |
| o4-mini (R=low, in=o3_summary) | 77,865 | 3.374 | 0.933 | o3_summary |
| o4-mini (R=medium, in=o3_summary) | 77,865 | 3.392 | 0.953 | o3_summary |
| gpt-5 (R=minimal, in=o3_summary) | 77,865 | 3.402 | 0.839 | o3_summary |
| o4-mini (R=high, in=o3_summary) | **77,863** | 3.405 | 0.969 | o3_summary |
| gpt-5-mini (R=high, in=gpt_5_summary) | 77,871 | 3.408 | 0.943 | gpt_5_summary |
| gpt-5 (R=minimal, in=gpt_5_summary) | 77,871 | 3.412 | 0.834 | gpt_5_summary |
| gpt-4.1-mini (in=o3_summary) | 77,865 | 3.439 | 0.961 | o3_summary |
| gpt-4.1 (in=o3_summary) | 77,865 | 3.455 | 0.923 | o3_summary |
| gpt-4.1-mini (S=medium, V=high) | 77,871 | 3.458 | 0.954 | gpt_5_summary |
| gpt-4.1-mini (S=high, V=high) | 77,871 | 3.459 | 0.956 | gpt_5_summary |
| gpt-4.1-mini (S=minimal, V=high) | 77,871 | 3.463 | 0.949 | gpt_5_summary |
| gpt-4.1-mini (S=high, V=medium) | 77,871 | 3.465 | 0.961 | gpt_5_summary |
| gpt-4.1-mini (S=low, V=high) | 77,871 | 3.476 | 0.960 | gpt_5_summary |

#### Risk 評分結果 (每配置獨立 N 值)

| 配置 | N | Mean | Std | 輸入源 |
|------|---|------|-----|--------|
| claude-haiku (in=gpt_5_summary) | 77,871 | 1.872 | 0.911 | gpt_5_summary |
| claude-sonnet (in=gpt_5_summary) | 77,871 | 2.117 | 0.858 | gpt_5_summary |
| o4-mini (R=medium, in=Lsa_summary) | 77,871 | 2.152 | 0.906 | Lsa_summary |
| gpt-4.1 (in=o3_summary) | 77,865 | 2.236 | 0.924 | o3_summary |
| o4-mini (R=medium, in=o3_summary) | 77,865 | 2.271 | 0.880 | o3_summary |
| gpt-4.1-nano (in=o3_summary) | 77,865 | 2.282 | 0.820 | o3_summary |
| o4-mini (R=low, in=o3_summary) | 77,865 | 2.284 | 0.875 | o3_summary |
| o4-mini (R=high, in=o3_summary) | **77,863** | 2.287 | 0.875 | o3_summary |
| gpt-4.1-mini (S=minimal, V=high) | 77,871 | 2.283 | 0.884 | gpt_5_summary |
| gpt-4.1-mini (S=low, V=high) | 77,871 | 2.286 | 0.892 | gpt_5_summary |
| gpt-4.1-mini (S=high, V=medium) | 77,871 | 2.291 | 0.892 | gpt_5_summary |
| gpt-4.1-mini (S=medium, V=high) | 77,871 | 2.299 | 0.891 | gpt_5_summary |
| gpt-4.1-mini (S=high, V=high) | 77,871 | 2.300 | 0.894 | gpt_5_summary |
| gpt-4.1-mini (in=o3_summary) | 77,865 | 2.309 | 0.905 | o3_summary |
| claude-opus (in=gpt_5_summary) | 77,871 | 2.397 | 0.809 | gpt_5_summary |
| gpt-5-mini (R=high, in=gpt_5_summary) | 77,871 | 2.433 | 0.720 | gpt_5_summary |
| o3 (R=medium, in=Lsa_summary) | 77,871 | 2.450 | 0.614 | Lsa_summary |
| o3 (R=medium, in=o3_summary) | 77,865 | 2.496 | 0.646 | o3_summary |
| o3 (R=low, in=o3_summary) | 77,865 | 2.513 | 0.647 | o3_summary |
| o3 (R=high, in=o3_summary) | 77,865 | 2.515 | 0.647 | o3_summary |
| o3 (in=gpt_5_summary) | 77,871 | 2.516 | 0.647 | gpt_5_summary |
| gpt-5 (R=high, in=gpt_5_summary) | 77,871 | 2.578 | 0.637 | gpt_5_summary |
| gpt-5 (R=high, in=o3_summary) | 77,865 | 2.586 | 0.634 | o3_summary |
| gpt-5 (R=medium, in=o3_summary) | 77,865 | 2.617 | 0.630 | o3_summary |
| gpt-5 (R=medium, in=gpt_5_summary) | 77,871 | 2.616 | 0.629 | gpt_5_summary |
| gpt-5 (R=low, in=o3_summary) | 77,865 | 2.623 | 0.630 | o3_summary |
| gpt-5 (R=low, in=gpt_5_summary) | 77,871 | 2.621 | 0.629 | gpt_5_summary |
| gpt-5 (R=minimal, in=o3_summary) | 77,865 | 2.633 | 0.636 | o3_summary |
| gpt-5 (R=minimal, in=gpt_5_summary) | 77,871 | 2.627 | 0.636 | gpt_5_summary |

#### 關鍵發現

**Sentiment 評分趨勢:**

1. **模型一致性高**: 所有模型的 sentiment 均值集中在 3.28-3.46 範圍內，差異不超過 0.2 分
2. **Claude Opus 最穩定**: std=0.694 為最低，極少給出極端評分 (1分0.5%, 5分1.7%)
3. **GPT-4.1 系列偏樂觀**: mean ≈ 3.46，5分比例最高 (12-15%)
4. **Reasoning level 影響微弱**: 所有 reasoning levels 的 sentiment 均值差距 < 0.1 分
5. **輸入源影響有限**: 三種 summary 來源的評分差距僅 0.06 分

**Risk 評分趨勢:**

1. **模型差異顯著**: Risk 評分跨模型差異明顯 (1.87-2.61)，比 sentiment 大得多
2. **Claude 系列偏保守**:
   - Haiku 最保守 (mean=1.87, 41%給1分)
   - Opus 相對中立 (mean=2.40)
   - Sonnet 介於兩者之間 (mean=2.12)
3. **GPT-5 評估風險最高**: mean=2.61，且 std=0.63 為最低，分佈集中在 2-3 分
4. **Reasoning level 影響明顯**:
   - minimal → 更高風險評估 (mean=2.63)
   - high → 較低風險評估 (mean=2.48)
   - 非推理模型 (default) → 最低風險評估 (mean=2.27)
5. **輸入源有影響**:
   - o3_summary → 較高風險 (mean=2.44)
   - Lsa_summary → 較低風險 (mean=2.30)

**實驗意涵:**

| 應用場景 | 推薦配置 | 理由 |
|---------|---------|------|
| 需要穩定 sentiment | Claude Opus | std 最低，避免極端值 |
| 需要保守風控 | Claude Haiku | 傾向低估風險，適合風險敏感場景 |
| 需要中性風險評估 | GPT-5 + high reasoning | 分佈集中，reasoning 可降低極端判斷 |
| 成本敏感 | gpt-4.1-nano | 表現與其他模型相近，成本最低 |

**分數分佈視覺化:**

```
Sentiment 分佈 (所有模型平均):
1分 ▓░░░░░░░░░ 1.5%
2分 ▓▓▓▓▓▓░░░░ 14%
3分 ▓▓▓▓▓▓▓▓▓▓ 39%
4分 ▓▓▓▓▓▓▓▓▓░ 38%
5分 ▓▓▓░░░░░░░ 6%

Risk 分佈 (所有模型平均):
1分 ▓▓▓▓▓░░░░░ 17%
2分 ▓▓▓▓▓▓▓▓▓▓ 40%
3分 ▓▓▓▓▓▓▓▓░░ 35%
4分 ▓▓░░░░░░░░ 7%
5分 ░░░░░░░░░░ <1%
```

*分析日期: 2025-12-27*
*總分析記錄數: 約 226 萬筆 (sentiment) + 226 萬筆 (risk)*

---

### 10.10 控制變因詳細分析

為增強結論說服力，以下透過**控制其他變因**進行比較分析。

#### 10.10.1 Reasoning Level 效果 (控制模型+輸入源)

**GPT-5 在相同輸入源 (o3_summary) 下的 reasoning 效果:**

| Reasoning | Mean | Std | 1分% | 2分% | 3分% | 4分% | 5分% |
|-----------|------|-----|------|------|------|------|------|
| **Sentiment** |||||||
| minimal | 3.402 | 0.839 | 0.6 | 14.7 | 35.1 | 42.9 | 6.6 |
| low | 3.304 | 0.778 | 1.3 | 13.0 | 42.6 | 40.2 | 2.9 |
| medium | 3.271 | 0.748 | 1.3 | 11.6 | 48.4 | 36.2 | 2.5 |
| high | 3.236 | 0.717 | 1.4 | 10.4 | **54.0** | 32.0 | 2.3 |
| **Risk** |||||||
| minimal | 2.633 | 0.634 | 1.9 | 39.6 | 52.2 | 6.3 | 0.1 |
| low | 2.623 | 0.630 | 0.7 | 43.7 | 48.3 | 7.3 | 0.0 |
| medium | 2.617 | 0.630 | 1.2 | 42.7 | 49.3 | 6.7 | 0.0 |
| high | 2.586 | 0.634 | 1.6 | **44.4** | 47.7 | 6.2 | 0.0 |

**Sentiment 分佈轉移 (minimal → high):**
- 3分: 35.1% → 54.0% (**↑18.9%**) — 向中性集中
- 4分: 42.9% → 32.0% (↓10.9%)
- 5分: 6.6% → 2.3% (↓4.3%)

**結論**: Reasoning effort 越高:
- Sentiment 向中性 (3分) 集中，極端評分減少
- Risk 同樣向 2 分集中，表示更謹慎的風險評估

**O3 和 O4-mini 的 reasoning 效果 (o3_summary 輸入):**

| Model | low | medium | high | Δ(low→high) | 分佈變化 |
|-------|-----|--------|------|-------------|----------|
| **Sentiment** |||||
| o3 | 3.294 | 3.299 | 3.298 | +0.004 | <2% |
| o4-mini | 3.374 | 3.392 | 3.405 | +0.031 | 3分↓3.6% |
| **Risk** |||||
| o3 | 2.513 | 2.496 | 2.515 | +0.002 | <2% |
| o4-mini | 2.284 | 2.271 | 2.287 | +0.003 | <2% |

**結論**: O3 和 O4-mini 的 reasoning level 對評分影響極小，分佈變化亦不顯著

#### 10.10.2 模型差異 — 公平比較 (控制輸入源 = o3_summary)

> ⚠️ **注意**: Claude 模型使用 `gpt_5_summary` 作為輸入，因此不納入此比較。
> 下方所有模型均使用相同輸入源 `o3_summary`，每配置 N ≈ 77,865。

**Sentiment 評分排序 (低→高):**

| Model | N | Mean | Std | 特徵 |
|-------|---|------|-----|------|
| gpt-5 (R=high) | 77,865 | 3.236 | 0.717 | 最保守，54%給3分 |
| gpt-5 (R=medium) | 77,865 | 3.271 | 0.748 | 保守 |
| o3 (R=high) | 77,865 | 3.298 | 0.824 | 穩定，不受 reasoning 影響 |
| gpt-4.1-nano | 77,865 | 3.319 | 0.886 | 中等 |
| o4-mini (R=low) | 77,865 | 3.374 | 0.933 | 偏樂觀 |
| gpt-5 (R=minimal) | 77,865 | 3.402 | 0.839 | 較樂觀 |
| o4-mini (R=high) | 77,863 | 3.405 | 0.969 | 偏樂觀，5分比例高 |
| gpt-4.1-mini | 77,865 | 3.439 | 0.961 | 樂觀 |
| gpt-4.1 | 77,865 | 3.455 | 0.923 | 最樂觀，12%給5分 |

**Risk 評分排序 (低→高):**

| Model | N | Mean | Std | 特徵 |
|-------|---|------|-----|------|
| gpt-4.1 | 77,865 | 2.236 | 0.924 | 低風險傾向 |
| o4-mini (R=medium) | 77,865 | 2.271 | 0.880 | 低風險傾向 |
| gpt-4.1-nano | 77,865 | 2.282 | 0.820 | 低風險 |
| o4-mini (R=high) | 77,863 | 2.287 | 0.875 | 低風險 |
| gpt-4.1-mini | 77,865 | 2.309 | 0.905 | 低風險 |
| o3 (R=medium) | 77,865 | 2.496 | 0.646 | 中等風險 |
| o3 (R=high) | 77,865 | 2.515 | 0.647 | 中等風險 |
| gpt-5 (R=high) | 77,865 | 2.586 | 0.634 | 較高風險 |
| gpt-5 (R=minimal) | 77,865 | 2.633 | 0.634 | 最高風險傾向 |

**關鍵發現**: GPT-4.1 系列評估風險系統性偏低，GPT-5 系列評估風險較高

#### 10.10.3 輸入源效果 (控制模型+reasoning)

**GPT-5 各 reasoning level 在不同輸入源的表現:**

| Config | o3_summary | gpt_5_summary | Δ |
|--------|------------|---------------|---|
| **Sentiment** |||
| R=high | 3.236 | 3.234 | -0.002 |
| R=medium | 3.271 | 3.271 | 0.000 |
| R=low | 3.304 | 3.304 | 0.000 |
| R=minimal | 3.402 | 3.412 | +0.010 |
| **Risk** |||
| R=high | 2.586 | 2.578 | -0.008 |
| R=medium | 2.617 | 2.616 | -0.001 |
| R=low | 2.623 | 2.621 | -0.002 |
| R=minimal | 2.633 | 2.627 | -0.006 |

**結論**: 輸入源 (o3_summary vs gpt_5_summary) 對 GPT-5 評分影響 < 0.01 分，可忽略

**O3/O4-mini 在 Lsa_summary vs o3_summary:**

| Model | Lsa_summary | o3_summary | Δ |
|-------|-------------|------------|---|
| **Sentiment** |||
| o3 (R=high) | 3.276 | 3.298 | +0.022 |
| o4-mini (R=high) | 3.346 | 3.405 | +0.059 |
| **Risk** |||
| o3 (R=medium) | 2.450 | 2.496 | +0.046 |
| o4-mini (R=medium) | 2.152 | 2.271 | +0.119 |

**結論**: 原始 Lsa_summary 相比 o3_summary，會使評分略微降低

#### 10.10.4 綜合結論

| 變因 | Sentiment 影響 | Risk 影響 | 重要性 |
|------|---------------|-----------|--------|
| **模型選擇** | 0.22 分 | 0.40 分 | ⭐⭐⭐ 高 |
| **Reasoning level** (GPT-5) | 0.17 分 | 0.05 分 | ⭐⭐ 中 |
| **Reasoning level** (O3/O4) | <0.04 分 | <0.02 分 | ⭐ 低 |
| **輸入源** (GPT-5) | <0.01 分 | <0.01 分 | ⭐ 低 |
| **輸入源** (O3/O4) | ~0.05 分 | ~0.10 分 | ⭐ 低 |

**最終建議**:
1. **模型選擇是最重要的變因** — 應優先根據應用場景選擇模型
2. **GPT-5 的 reasoning level 有意義** — high reasoning 使評分更保守
3. **輸入源影響可忽略** — 不需為此優化 pipeline

---

### 10.11 Token 使用與成本經驗

#### O4-mini vs O3 實際成本

**表面價格 vs 實際成本:**

| 模型 | 單位 Token 價格 | 實際 Token 消耗 | 失敗重試率 | 實際成本 |
|------|----------------|----------------|-----------|----------|
| o3 | 較高 | 較低 | 低 | 基準 |
| o4-mini | 較低 | **高很多** | **高** | ≈ o3 甚至更高 |

**O4-mini 問題:**
- Token 消耗量遠超 o3
- 失敗率高，需要更多重試
- 在 `max_completion_tokens` 限制過低時容易失敗
- 建議：放寬 `max_completion_tokens` 限制

**失敗原因分析:**
- 早期為避免 token 過多導致的幻覺 (hallucination)，限制了 `max_completion_tokens`
- O4-mini 需要更多 token 才能完成任務，限制過緊導致失敗
- High_1 缺少 1 筆評分就是這個原因造成的

#### GPT-5 世代的 Token 消耗

**GPT-5 Token 消耗特徵:**
- 單位 token 價格大幅下降
- 但實際消耗量大幅增加（o3 的數倍）
- 若 reasoning 和 verbosity 都設為最高，消耗量可達 **o3 的 7 倍以上**

**配置對 token 消耗的影響:**

| 配置 | 相對 Token 消耗 | 說明 |
|------|----------------|------|
| R=minimal, V=low | 1x | 最節省 |
| R=high, V=high | 7x+ | 最耗 token |

**建議:**
1. 對於批量任務，使用 R=medium 或 R=low 平衡品質與成本
2. 放寬 `max_completion_tokens` 限制以減少失敗重試
3. 監控實際 token 消耗而非僅看單位價格

---

*創建日期: 2024-12-14*
*更新日期: 2025-12-28*
*版本: 2.0*

> ✅ **修復完成 (2025-12-28)**: 全部 6 階段修復已完成。
> - o3_summary 6 筆 BKR 資料已修復
> - 27 個下游評分檔案已更新並替換原始檔案
> - 暫存檔案已清理 (122 個 .repaired.csv/.pre_repair.csv/.backup_*.csv)
> - Row 44887 (GILD) 因原始資料品質問題無法修復（所有模型皆為 NaN）
> - 備份位置: `/mnt/md0/finrl/backups/repair_20251227/`