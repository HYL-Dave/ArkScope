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

*創建日期: 2024-12-14*
*更新日期: 2025-12-26*
*版本: 1.4*