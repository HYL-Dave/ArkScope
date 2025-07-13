```markdown
# FinRL-DeepSeek 新聞爬取延伸專案

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 專案簡介

本專案旨在將 FinRL-DeepSeek 資料集從原本的 2013-2023 年擴展至 2024-2025 年，保持相同的 89 檔 Nasdaq 股票和資料格式。專案提供完整的新聞爬取、處理和合併流程，支援多種新聞來源和 LLM 評分。

### 🎯 主要目標

- 擴展 FinRL-DeepSeek 資料集時間範圍至 2024-2025
- 維持原始 89 檔 Nasdaq 股票的一致性
- 保持相同的資料格式和評分系統
- 提供可重複、可擴展的爬取流程

### ⭐ 主要特色

- **多源新聞爬取**: 支援 FinNLP、CommonCrawl 等多種來源
- **智能LLM評分**: 使用 OpenAI API 進行情緒和風險評分
- **格式完全對齊**: 生成與原始資料集完全相容的格式
- **成本控制**: 內建成本估算和監控機制
- **品質保證**: 多層次的資料驗證和品質檢查

## 🏗️ 系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   股票清單解析   │ -> │   新聞爬取模組   │ -> │   資料處理模組   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              v                        v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  FinNLP 爬取器   │    │   LLM 評分器    │    │   格式轉換器    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              v                        v
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ CommonCrawl補充  │    │   傳統摘要生成   │    │   資料合併器    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 快速開始

### 系統需求

- Python 3.8+
- 8GB+ RAM
- 50GB+ 可用硬碟空間
- OpenAI API 密鑰

### 使用步驟

#### 1. 替換修改後的檔案
```bash
# 備份原檔案（可選）
cp src/data_processing/llm_scorer.py src/data_processing/llm_scorer.py.bak
cp src/utils/cost_calculator.py src/utils/cost_calculator.py.bak

# 使用修改後的版本替換原檔案
```

#### 2. 執行設置檢查
```bash
python check_setup.py
```

#### 3. 準備配置
```bash
cp config/config_template.json config/config.json
# 編輯 config.json，填入您的 OpenAI API 密鑰
```

#### 4. 安裝依賴
```bash
pip install -r requirements.txt
```

#### 5. 執行測試
```bash
# 測試關鍵模組
python -m pytest tests/test_integration.py::TestLLMScorer -v
python -m pytest tests/test_integration.py::TestCostCalculator -v
```

#### 6. 開始使用
```bash
# 小規模測試
python scripts/run_daily_crawl.py --config config/config.json --date 2024-07-12

# 完整執行
python scripts/run_full_pipeline.py \
    --config config/config.json \
    --start-date 2024-01-01 \
    --end-date 2024-07-12
```

### 環境設置

#### 建立虛擬環境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows
```

#### 準備原始數據
```bash
# 下載原始 FinRL-DeepSeek 資料集
mkdir -p huggingface_datasets/FinRL_DeepSeek_sentiment/
# 將 sentiment_deepseek_new_cleaned_nasdaq_news_full.csv 放入上述目錄
```

## 📋 詳細使用說明

### 配置文件設置

編輯 `config/config.json` 中的關鍵參數：

```json
{
  "llm_scorer": {
    "openai_api_key": "YOUR_API_KEY_HERE",
    "model": "gpt-4o-mini",
    "cost_limit_usd": 100.0
  },
  "crawl_strategy": {
    "primary_method": "finnlp",
    "max_articles_per_day": 1000
  }
}
```

### 分步執行

如果需要分步執行，可以使用個別腳本：

```bash
# 1. 每日增量爬取
python scripts/run_daily_crawl.py --date 2024-07-12

# 2. 歷史回補
python scripts/run_historical_backfill.py \
    --start-date 2024-01-01 --end-date 2024-06-30

# 3. 僅處理已有數據
python scripts/process_existing_data.py --input data/raw/news_data.csv
```

### 成本控制

專案內建多種成本控制機制：

```python
# 估算處理成本
from src.utils.cost_calculator import CostCalculator

calculator = CostCalculator()
estimate = calculator.estimate_project_total_cost(
    articles_count=10000,
    model='gpt-4o-mini'
)
print(f"估算總成本: ${estimate['project_summary']['total_estimated_cost_usd']}")
```

## 📊 輸出格式

專案輸出的資料格式與原始 FinRL-DeepSeek 完全相容：

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| Date | string | 日期 (YYYY-MM-DD) |
| Article_title | string | 新聞標題 |
| Stock_symbol | string | 股票代號 |
| Url | string | 新聞來源URL |
| Publisher | string | 發佈者 |
| Author | string | 作者 |
| Article | string | 新聞正文 |
| Lsa_summary | string | LSA摘要 |
| Luhn_summary | string | Luhn摘要 |
| Textrank_summary | string | TextRank摘要 |
| Lexrank_summary | string | LexRank摘要 |
| sentiment_u | integer | 情緒分數 (1-5) |
| risk_q | integer | 風險分數 (1-5) |

## 🧪 測試

執行測試套件：

```bash
# 執行所有測試
python -m pytest tests/ -v

# 執行特定測試
python -m pytest tests/test_integration.py -v

# 生成覆蓋率報告
python -m pytest tests/ --cov=src --cov-report=html
```

## 📈 監控和日誌

專案提供完整的監控和日誌功能：

- **即時進度追蹤**: 顯示爬取和處理進度
- **成本實時監控**: 追蹤 API 使用成本
- **品質檢查報告**: 自動生成資料品質報告
- **詳細錯誤日誌**: 記錄所有錯誤和警告

查看日誌：
```bash
tail -f logs/finrl_extension.log
```

## 🛠️ 故障排除

### 常見問題

**Q: OpenAI API 超出限制**
```
A: 檢查配置中的 cost_limit_usd 設置，或使用 gpt-4o-mini 模型降低成本
```

**Q: 爬取被網站限制**
```
A: 增加 rate_limiting 中的延遲時間，或啟用代理設置
```

**Q: 記憶體不足**
```
A: 減少 batch_size 或啟用 chunk_size 分批處理
```

### 日誌分析

檢查關鍵日誌訊息：
```bash
# 查看錯誤
grep "ERROR" logs/finrl_extension.log

# 查看成本資訊
grep "成本" logs/finrl_extension.log

# 查看進度
grep "進度" logs/finrl_extension.log
```

## 📝 開發指南

### 添加新的新聞源

1. 在 `src/data_extraction/` 創建新的爬取器
2. 實現必要的介面方法
3. 在配置文件中添加新源設置
4. 更新測試用例

### 自定義 LLM 評分

1. 修改 `src/data_processing/llm_scorer.py` 中的 prompt
2. 調整評分邏輯
3. 更新成本計算

### 擴展資料驗證

1. 在 `src/integration/data_merger.py` 添加驗證規則
2. 更新品質檢查報告
3. 添加相應測試

## 🤝 貢獻指南

歡迎提交 Issue 和 Pull Request！

1. Fork 專案
2. 創建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 許可證

本專案採用 MIT 許可證 - 詳見 [LICENSE](LICENSE) 文件。

## 🙏 致謝

- [FinRL-DeepSeek](https://github.com/benstaf/FinRL_DeepSeek) 原始專案
- [FinNLP](https://github.com/AI4Finance-Foundation/FinNLP) 新聞爬取框架
- [news-please](https://github.com/fhamborg/news-please) CommonCrawl 爬取工具

## 📞 聯絡資訊

如有問題或建議，請：
- 開啟 [GitHub Issue](https://github.com/your-username/finrl-deepseek-extension/issues)
- 發送郵件至 your-email@example.com

---

**免責聲明**: 本專案僅供研究和教育用途。請遵守相關網站的 robots.txt 和使用條款。
```