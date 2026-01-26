# 數據資產盤點

> **盤點日期**: 2026-01-26
> **總文件數**: 481 個數據文件

---

## 概覽

| 目錄 | 文件數 | 主要用途 |
|------|-------:|----------|
| `data/` | 285 | 主要數據 (新聞、股價) |
| `data_lake/` | 132 | 基本面數據 |
| `comparison_results/` | 32 | API 測試結果 |
| `NewsExtraction/` | 15 | 歷史新聞 (FNSPID) |
| `data_sources/` | 11 | 數據源測試 |

| 格式 | 文件數 | 典型用途 |
|------|-------:|----------|
| CSV | 189 | 股價、評分結果 |
| JSON | 188 | API 回應、設定 |
| Parquet | 104 | 新聞、大型數據集 |

### 數據一致性

| 數據類型 | 唯一股票數 | 備註 |
|----------|------------|------|
| IBKR 已評分新聞 | 127 | |
| Polygon 已評分新聞 | 130 | |
| 15min 股價 | 75 | 需補齊 |
| IBKR 基本面 | 131 | 最完整 |

> ⚠️ **待處理**: 15min 股價只有 75 支，遠少於新聞和基本面覆蓋範圍

---

## 1. 新聞數據

### 1.1 IBKR 新聞 (主要來源)

**位置**: `data/news/raw/ibkr/`

```
data/news/raw/ibkr/
├── 2025/
│   ├── 2025-07.parquet (2.3M)
│   ├── 2025-08.parquet (4.4M)
│   ├── 2025-09.parquet (4.7M)
│   ├── 2025-10.parquet (6.0M)
│   ├── 2025-11.parquet (8.3M)
│   └── 2025-12.parquet (33M)
└── 2026/
    └── 2026-01.parquet (13M) ← 當前月份
```

**Schema**:
```
article_id          - 文章 ID
ticker              - 股票代號
title               - 標題
published_at        - 發布時間
source_api          - 來源 (ibkr)
description         - 摘要
content             - 全文
url                 - 原文連結
publisher           - 發布者
author              - 作者
related_tickers     - 相關股票
tags                - 標籤
category            - 分類
source_sentiment    - 來源情緒
collected_at        - 收集時間
content_length      - 內容長度
dedup_hash          - 去重 hash
```

**數據量**: 2026-01 約 40,000 則

> ⚠️ **RL 訓練限制**: IBKR 即時新聞 API 無法取得長期歷史數據 (目前僅 2025-07 起)。
> 若需更長歷史用於 RL 模型訓練，可考慮:
> 1. **付費下載 IBKR 歷史新聞** - 最理想，數據格式一致
> 2. **使用 Polygon 已評分數據** - 已有 2022-2026 共 107K 則
> 3. **使用 FNSPID 歷史數據** - 2013-2023 共 218K 則 (需重新評分)

### 1.2 IBKR 已評分新聞

**位置**: `data/news/ibkr_scored_final.parquet` (47M)

**額外欄位** (LLM 評分):
```
sentiment_haiku     - Haiku 情緒分數
sentiment_title     - 標題情緒
sentiment_content   - 內容情緒
sentiment_source    - 評分來源
risk_haiku          - Haiku 風險分數
risk_title          - 標題風險
risk_content        - 內容風險
risk_source         - 評分來源
```

**數據量**: 52,755 則已評分新聞

### 1.3 Finnhub 新聞 (補充)

**位置**: `data/news/raw/finnhub/`

```
data/news/raw/finnhub/
├── 2025/
│   └── 2025-12.parquet (2.3M)
└── 2026/
    └── 2026-01.parquet (3.3M)
```

### 1.4 Polygon 新聞

**位置**: `data/news/raw/polygon/`

```
data/news/raw/polygon/
├── 2022/ (12 個月)
├── 2023/ (12 個月)
├── 2024/ (12 個月)
├── 2025/ (12 個月)
└── 2026/ (1 個月)
```

**範圍**: 2022-01 ~ 2026-01 (49 個月)

### 1.5 Polygon 已評分新聞

**位置**: `data/news/polygon_scored_final.csv` (54M)

**Schema**:
```
Stock_symbol        - 股票代號
Article_title       - 標題
published_at        - 發布時間
description         - 摘要
source_sentiment    - 來源情緒
url                 - 連結
publisher           - 發布者
sentiment_haiku     - Haiku 情緒分數
risk_haiku          - Haiku 風險分數
```

**數據量**: 107,640 則 (全部已評分)
**股票數**: 130 支
**時間範圍**: 2022-01-01 ~ 2026-01-03

### 1.6 FNSPID 歷史新聞

**位置**: `NewsExtraction/`

```
fnspid_89_2013_2023_cleaned.parquet (588M)
fnspid_89_2013_2023_cleaned.csv (1.2G)
fnspid_unique_articles.csv (779M)
```

**Schema**:
```
Date                - 日期
Stock_symbol        - 股票代號
Article_title       - 標題
Article             - 全文
Sentiment           - 原始情緒
Url                 - 連結
Publisher           - 發布者
Author              - 作者
Lsa_summary         - LSA 摘要
importance_score    - 重要性分數
```

**數據量**: 218,654 則 (2013-2023，89 支股票)

---

## 2. 股價數據

### 2.1 15 分鐘線

**位置**: `data/prices/15min/`

**股票數**: 75 支 (105 個文件，部分股票有多年份檔案)

**Schema**:
```
datetime    - 時間戳
open        - 開盤價
high        - 最高價
low         - 最低價
close       - 收盤價
volume      - 成交量
ticker      - 股票代號
```

**範圍**: 2024-2026

**來源**: IBKR API

> ⚠️ 需補齊至與新聞/基本面一致的 ~130 支

---

## 3. 基本面數據

### 3.1 IBKR 基本面

**位置**: `data_lake/raw/ibkr_fundamentals/`

**文件數**: 131 個 JSON (每股票一個)

**日期**: 2025-12-25 收集

**內容**: 財務比率、估值指標等

---

## 4. 其他數據

### 4.1 比較測試結果

**位置**: `comparison_results/`

- `financial_datasets/` - Financial Datasets API 測試
- `news_source_comparison.json` - 新聞源比較
- `seeking_alpha_overlap.json` - SA 重疊分析

### 4.2 期權範例

**位置**: `data/option_examples/`

- 期權鏈範例 (TSLA, AAPL, NVDA)
- Greeks 比較數據
- 教學文檔

### 4.3 設定檔

**位置**: `config/`

- `tickers_core.json` - 核心股票清單

---

## 5. 遷移規劃

### 5.1 建議遷移到 Supabase

| 數據類型 | 來源 | 原因 |
|----------|------|------|
| **新聞** | IBKR/Finnhub/Polygon | 需要全文+向量搜尋 |
| **評分結果** | ibkr_scored_final | 需要條件查詢 |
| **信號記錄** | (新建) | 需要時間查詢 |
| **觀察累積** | (新建) | 需要結構化查詢 |

### 5.2 保持 Parquet

| 數據類型 | 原因 |
|----------|------|
| **股價 (15min)** | 時間序列，批量讀取 |
| **FNSPID 歷史** | 太大 (1.2G)，主要用於訓練 |

### 5.3 Supabase Schema 初步設計

```sql
-- 新聞表
CREATE TABLE news (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id TEXT UNIQUE,
  ticker TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT,
  published_at TIMESTAMPTZ NOT NULL,
  source_api TEXT,
  url TEXT,
  publisher TEXT,
  -- 評分欄位
  sentiment_score INT,
  risk_score INT,
  -- 向量欄位 (pg_vector)
  title_embedding vector(1536),
  content_embedding vector(1536),
  -- 索引
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_news_ticker ON news(ticker);
CREATE INDEX idx_news_published ON news(published_at DESC);
CREATE INDEX idx_news_title_fts ON news USING GIN(to_tsvector('english', title));
CREATE INDEX idx_news_title_vec ON news USING ivfflat(title_embedding vector_cosine_ops);

-- 信號表
CREATE TABLE signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_type TEXT NOT NULL,
  ticker TEXT,
  sector TEXT,
  description TEXT,
  confidence FLOAT,
  triggered_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB
);

-- 觀察表
CREATE TABLE observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic TEXT NOT NULL,
  observation TEXT NOT NULL,
  observed_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB
);
```

---

## 6. 數據量估算

| 數據 | 當前大小 | 預估年成長 |
|------|----------|------------|
| IBKR 新聞 | ~50M/月 | ~600M/年 |
| 評分結果 | ~50M | ~600M/年 |
| 股價 15min | ~100M | ~200M/年 |
| FNSPID | 1.2G | 不成長 (歷史) |

**結論**: 自建 Supabase 完全可以處理這個量級

---

## 7. 下一步

1. [ ] 設定 Supabase (Docker 自建)
2. [ ] 建立 Schema
3. [ ] 遷移 IBKR 新聞數據
4. [ ] 生成 Embedding
5. [ ] 測試搜尋能力
6. [ ] 安裝 MCP 整合

---

*文檔版本: 1.0*
*創建日期: 2026-01-26*