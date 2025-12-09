# FinRL-DeepSeek 數據處理模組

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 模組簡介

本模組提供 **通用數據處理組件**，用於新聞數據的 LLM 評分、格式標準化、數據合併等操作。

> **注意**: 爬蟲功能已遷移至專案根目錄的 `data_sources/` 模組。本模組專注於數據處理。

## 🏗️ 模組架構

```
finrl_deepseek_news_extension/
├── src/
│   ├── data_processing/
│   │   ├── llm_scorer.py         # LLM 情緒/風險評分器
│   │   └── schema_formatter.py   # 數據格式標準化
│   ├── integration/
│   │   └── data_merger.py        # 數據合併與去重
│   ├── utils/
│   │   ├── cost_calculator.py    # API 成本計算器
│   │   └── logger_util.py        # 日誌與進度追蹤
│   └── data_extraction/
│       └── stock_list_parser.py  # 股票清單解析
├── docs/                         # 文檔
└── tests/                        # 測試
```

## 🎯 核心功能

### 1. LLM 評分器 (llm_scorer.py)

使用 OpenAI API 對新聞進行情緒和風險評分。

```python
from finrl_deepseek_news_extension.src.data_processing.llm_scorer import LLMScorer

scorer = LLMScorer(
    api_key="your_openai_key",
    model="gpt-4o-mini",
    cost_limit_usd=50.0
)

# 評分單篇文章
result = scorer.score_article(article_text, ticker="AAPL")
# 返回: {'sentiment': 4, 'risk': 2, 'reasoning': '...'}

# 批量評分
results = scorer.score_batch(articles_list)
```

**特色功能:**
- 多 API Key 輪換支援
- 智能成本追蹤與限制
- 批量處理優化
- 結構化輸出 (Function Calling)

### 2. 數據格式化器 (schema_formatter.py)

將各種新聞源的數據轉換為標準 FinRL-DeepSeek 格式。

```python
from finrl_deepseek_news_extension.src.data_processing.schema_formatter import SchemaFormatter

formatter = SchemaFormatter()
standardized_df = formatter.format_news(raw_news_df)
```

**標準輸出欄位:**

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Date | string | 日期 (YYYY-MM-DD) |
| Stock_symbol | string | 股票代號 |
| Article_title | string | 新聞標題 |
| Article | string | 新聞正文 |
| Url | string | 來源 URL |
| Publisher | string | 發佈者 |
| sentiment_u | integer | 情緒分數 (1-5) |
| risk_q | integer | 風險分數 (1-5) |

### 3. 數據合併器 (data_merger.py)

合併多個數據源，處理去重和衝突。

```python
from finrl_deepseek_news_extension.src.integration.data_merger import DataMerger

merger = DataMerger()
merged_df = merger.merge_datasets(new_data, existing_data, strategy="prefer_new")
```

### 4. 成本計算器 (cost_calculator.py)

估算和追蹤 API 使用成本。

```python
from finrl_deepseek_news_extension.src.utils.cost_calculator import CostCalculator

calc = CostCalculator()
estimate = calc.estimate_batch_llm_cost(
    articles_count=1000,
    avg_article_length=500,
    model="gpt-4o-mini"
)
print(f"預估成本: ${estimate['total_cost']:.2f}")
```

## 🔗 與數據源模組整合

```python
# 1. 從 data_sources 獲取數據
from data_sources import TiingoDataSource

tiingo = TiingoDataSource()
articles = tiingo.fetch_news(['AAPL', 'MSFT'], days_back=7)

# 2. 轉換為 DataFrame
import pandas as pd
df = pd.DataFrame([a.to_dict() for a in articles])

# 3. 使用本模組處理
from finrl_deepseek_news_extension.src.data_processing.schema_formatter import SchemaFormatter
from finrl_deepseek_news_extension.src.data_processing.llm_scorer import LLMScorer

formatter = SchemaFormatter()
formatted_df = formatter.format_news(df)

scorer = LLMScorer(api_key="...", cost_limit_usd=50.0)
scored_df = scorer.score_dataframe(formatted_df)
```

## 💰 成本管理

### 模型定價參考 (2024-12)

| 模型 | 輸入 ($/1M tokens) | 輸出 ($/1M tokens) | 建議用途 |
|------|-------------------|-------------------|---------|
| gpt-4o-mini | $0.15 | $0.60 | 日常評分 (推薦) |
| gpt-4o | $2.50 | $10.00 | 高品質分析 |

### 成本控制

```python
scorer = LLMScorer(
    api_key="...",
    model="gpt-4o-mini",       # 使用較便宜的模型
    cost_limit_usd=50.0,       # 每日上限
    batch_size=30,             # 批量處理
)
```

## 🧪 測試

```bash
cd finrl_deepseek_news_extension
python -m pytest tests/ -v
```

## 📚 相關模組

- [📋 data_sources/](../data_sources/) - 統一數據源介面 (Tiingo, Finnhub)
- [📋 NewsExtraction/](../NewsExtraction/) - 歷史新聞數據處理
- [📋 主專案 README](../README.md)

---

## 📝 變更記錄

**v3.0.0** (2024-12-09)
- ⚠️ 移除所有爬蟲代碼（遷移至 `data_sources/`）
- ✅ 保留 LLM 評分、格式化、合併等通用組件

**v2.0.0** (2024-07)
- 新增 10+ 新聞源整合（已移除）
- 統一新聞系統架構（已移除）

**v1.0.0** (2024)
- 基礎 LLM 評分系統
- 數據格式標準化

---

**License**: MIT