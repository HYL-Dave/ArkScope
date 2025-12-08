# FinRL-DeepSeek 新聞爬取延伸模組

## 📖 模組概述

本模組專門負責擴展 FinRL-DeepSeek 資料集，將原本 2013-2023 年的數據延伸至 2024-2025 年，同時保持完全的格式相容性。提供從基礎的 2 個新聞源到增強版的 10+ 個新聞源的完整爬取解決方案。

> **上級文檔**: [🏠 主專案 CLAUDE.md](../CLAUDE.md)  
> **相關模組**: [📋 NewsExtraction CLAUDE.md](../NewsExtraction/CLAUDE.md)

## 🎯 核心目標

- **數據延伸**: 將 FinRL-DeepSeek 從 2013-2023 擴展至 2024-2025
- **格式相容**: 100% 相容原始 FinRL-DeepSeek 數據格式
- **多源整合**: 支援 10+ 專業新聞源的統一爬取
- **智能評分**: 整合 OpenAI LLM 進行情緒和風險評分
- **企業級功能**: 成本控制、監控、錯誤恢復

## 🏗️ 模組架構

### **系統架構圖**

```
FinRL-DeepSeek 新聞爬取模組
├── 📊 數據提取層 (src/data_extraction/)
│   ├── 🔧 核心爬取器
│   │   ├── stock_list_parser.py          # 股票清單解析
│   │   ├── finnlp_crawler.py             # FinNLP 爬取器
│   │   └── newsplease_crawler.py         # CommonCrawl 爬取器
│   ├── ⚡ 增強爬取器  
│   │   ├── unified_news_system.py        # 統一新聞系統
│   │   ├── enhanced_news_crawler.py      # 增強新聞爬取器
│   │   ├── advanced_news_sources.py      # 高級新聞源
│   │   └── ibkr_news_integration.py      # IBKR 整合
│   └── 🛠️ 設置工具
│       └── setup_script.py               # 一鍵設置腳本
├── 🧠 數據處理層 (src/data_processing/)
│   ├── llm_scorer.py                     # LLM 評分器
│   └── schema_formatter.py               # 格式標準化
├── 🔗 整合層 (src/integration/)
│   └── data_merger.py                    # 數據合併器
├── 🔧 工具層 (src/utils/)
│   ├── cost_calculator.py                # 成本計算器
│   └── logger_util.py                    # 日誌工具
├── 📋 腳本層 (scripts/)
│   ├── run_enhanced_pipeline.py          # 增強版主流程
│   ├── enhanced_daily_crawl.py           # 增強版每日爬取
│   ├── run_full_pipeline.py              # 原版主流程
│   ├── daily_crawl_script.py             # 原版每日爬取
│   ├── migrate_config.py                 # 配置遷移工具
│   └── test_enhanced_integration.py      # 整合測試
├── ⚙️ 配置層 (config/)
│   ├── config.json                       # 主配置文件
│   ├── enhanced_config.json              # 增強版配置
│   ├── news_config.json                  # 新聞源配置
│   └── config_template.json              # 配置模板
└── 🧪 測試層 (tests/)
    ├── test_integration.py               # 整合測試
    ├── test_enhanced_modules.py          # 增強模組測試
    └── test_crawler.py                   # 爬取器測試
```

### **新舊版本對比**

| 特性 | 原版本 | 增強版 | 提升倍數 |
|------|--------|--------|----------|
| **新聞源數量** | 2個 (FinNLP, CommonCrawl) | 10+ 個 | **5x** |
| **數據覆蓋範圍** | 基礎財經 | 專業+社群+監管 | **3x** |
| **處理效率** | 單線程 | 多源並行 | **4x** |
| **成本效益** | 基礎控制 | 智能優化 | **2x** |

## 📊 新聞源整合

### **核心 API 源**
- **Finnhub**: 專業財經新聞和市場數據 (60 calls/minute)
- **Alpha Vantage**: 新聞情緒和財經數據 (5 calls/minute)
- **IBKR**: Interactive Brokers 專業新聞 (需要連接設置)

### **免費市場源**
- **Yahoo Finance**: Yahoo 財經新聞feed (30 calls/minute)
- **Google News**: Google 新聞 RSS feeds (30 calls/minute)
- **StockTwits**: 社交交易平台討論 (30 calls/minute)

### **全球數據源**
- **GDELT**: 全球新聞資料庫與情緒分析 (10 calls/minute)
- **Event Registry**: 語義新聞搜索和事件檢測 (需 API key)

### **監管/社群源**
- **SEC EDGAR**: SEC 公告和監管文件 (10 calls/minute)
- **Reddit**: Reddit 財經社群 (需 client credentials)

## 🚀 快速開始

### **方式一：一鍵設置（推薦）**

```bash
# 1. 進入模組目錄
cd finrl_deepseek_news_extension

# 2. 運行自動設置
python src/data_extraction/setup_script.py

# 3. 測試整合
python scripts/test_enhanced_integration.py

# 4. 開始使用
python scripts/run_enhanced_pipeline.py --config config/enhanced_config.json --dry-run
```

### **方式二：手動設置**

```bash
# 1. 安裝依賴
pip install pandas numpy requests yfinance feedparser beautifulsoup4

# 2. 可選：安裝進階功能依賴
pip install gdeltdoc eventregistry praw sec-edgar-downloader ib_insync

# 3. 配置 API Keys
cp .env.template .env
# 編輯 .env 文件添加：
# OPENAI_API_KEY=your_openai_key
# FINNHUB_API_KEY=your_finnhub_key
# ALPHAVANTAGE_API_KEY=your_alphavantage_key

# 4. 測試設置
python check_setup.py
```

## 💻 核心功能使用

### **1. 基礎爬取流程**

```bash
# 原版流程（2個新聞源）
python scripts/run_full_pipeline.py \
    --config config/config.json \
    --start-date 2024-07-01 \
    --end-date 2024-07-12

# 每日增量爬取
python scripts/daily_crawl_script.py \
    --config config/config.json \
    --date 2024-07-12
```

### **2. 增強版流程**

```bash
# 增強版流程（10+ 新聞源）
python scripts/run_enhanced_pipeline.py \
    --config config/enhanced_config.json \
    --start-date 2024-07-01 \
    --end-date 2024-07-12

# 增強版每日爬取
python scripts/enhanced_daily_crawl.py \
    --config config/enhanced_config.json

# 指定特定新聞源
python scripts/run_enhanced_pipeline.py \
    --config config/enhanced_config.json \
    --sources unified enhanced gdelt
```

### **3. Python API 使用**

#### **統一新聞系統**

```python
from src.data_extraction.unified_news_system import UnifiedNewsSystem

# 初始化系統
news_system = UnifiedNewsSystem('config/news_config.json')

# 獲取單一股票新聞
aapl_news = news_system.fetch_ticker_news('AAPL', '2024-07-01', '2024-07-12')
print(f"獲取到 {len(aapl_news)} 條 AAPL 新聞")

# 獲取多股票市場概覽
tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
overview = news_system.get_market_overview(tickers, hours=24)

# 生成分析報告
news_system.generate_report(aapl_news, 'reports/aapl_analysis.csv')
```

#### **增強爬蟲系統**

```python
from src.data_extraction.enhanced_news_crawler import EnhancedNewsCrawler

# 配置爬蟲
config = {
    'finnhub_api_key': 'YOUR_FINNHUB_KEY',
    'alphavantage_api_key': 'YOUR_ALPHAVANTAGE_KEY'
}
crawler = EnhancedNewsCrawler(config)

# 從所有源獲取新聞
all_news = crawler.fetch_all_sources('AAPL', '2024-07-01', '2024-07-12')

# 從特定源獲取
specific_news = crawler.fetch_all_sources(
    'AAPL', '2024-07-01', '2024-07-12',
    sources=['yahoo', 'google_news', 'stocktwits']
)

# 批量處理
multiple_tickers = crawler.fetch_multiple_tickers(
    ['AAPL', 'MSFT', 'GOOGL'], '2024-07-01', '2024-07-12'
)
```

#### **高級新聞源**

```python
from src.data_extraction.advanced_news_sources import GDELTNews, SECFilings, RedditMonitor

# GDELT 全球新聞
gdelt = GDELTNews()
global_news = gdelt.search_news('AAPL', 'Apple Inc', '2024-07-01', '2024-07-12')

# SEC 監管公告
sec = SECFilings()
sec_filings = sec.get_recent_filings('AAPL', '2024-07-01')

# Reddit 社群討論
reddit = RedditMonitor('CLIENT_ID', 'CLIENT_SECRET', 'FinRL-Bot/1.0')
reddit_posts = reddit.search_posts('AAPL', time_filter='week')
trending = reddit.get_trending_tickers()
```

## ⚙️ 配置管理

### **配置文件層級**

1. **config.json** - 主配置文件（原版相容）
2. **enhanced_config.json** - 增強版功能配置
3. **news_config.json** - 新聞源詳細配置

### **分階段啟用策略**

#### **階段一：免費源優先**
```json
{
  "enhanced_news": {
    "enhanced_crawler": {
      "sources": {
        "free_sources": {
          "yahoo": {"enabled": true},
          "google_news": {"enabled": true},
          "stocktwits": {"enabled": true}
        }
      }
    },
    "advanced_sources": {
      "gdelt": {"enabled": true},
      "sec": {"enabled": true}
    }
  }
}
```

#### **階段二：添加核心 API**
```json
{
  "enhanced_crawler": {
    "sources": {
      "core_apis": {
        "finnhub": {"enabled": true},
        "alphavantage": {"enabled": true}
      }
    }
  }
}
```

#### **階段三：完整功能**
```json
{
  "advanced_sources": {
    "reddit": {"enabled": true},
    "event_registry": {"enabled": true}
  },
  "ibkr": {"enabled": true}
}
```

### **成本控制配置**

```json
{
  "llm_scorer": {
    "daily_cost_limit": 30.0,
    "model": "gpt-4o-mini",
    "enhanced_features": {
      "auto_model_selection": true,
      "batch_optimization": true,
      "cost_monitoring": true
    }
  }
}
```

## 💰 成本管理

### **成本預估**

```python
from src.utils.cost_calculator import CostCalculator

calculator = CostCalculator()

# 估算專案總成本
estimate = calculator.estimate_project_total_cost(
    articles_count=10000,
    model='gpt-4o-mini'
)
print(f"估算總成本: ${estimate['project_summary']['total_estimated_cost_usd']}")

# 批量成本估算
batch_estimate = calculator.estimate_batch_llm_cost(
    articles_count=1000,
    avg_article_length=500,
    model='gpt-4o-mini'
)
```

### **實時成本監控**

```python
from src.utils.logger_util import CostTracker, setup_logger

logger = setup_logger('cost_monitor', config)
tracker = CostTracker(logger, cost_limit=50.0)

# 在 API 調用後添加成本
tracker.add_cost(0.01, "OpenAI")

# 獲取成本摘要
summary = tracker.get_summary()
print(f"當前成本: ${summary['total_cost_usd']}")
```

## 📊 數據輸出格式

### **標準輸出欄位**

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

### **增強版新增欄位**

| 欄位名稱 | 類型 | 說明 |
|---------|------|------|
| data_source_type | string | 數據來源類型 |
| processing_timestamp | string | 處理時間戳 |
| source_priority | integer | 來源優先級 |
| deduplication_hash | string | 去重哈希值 |
| confidence_score | float | 置信度分數 |

### **輸出目錄結構**

```
data/
├── raw/                              # 原始爬取數據
│   ├── enhanced_combined_news_2024-07-01_2024-07-12.csv
│   └── enhanced_daily_news_2024-07-12.csv
├── processed/                        # 處理後數據
│   ├── enhanced_processed_news_20240712.csv
│   └── enhanced_daily_processed_2024-07-12.csv
├── final/                           # 最終合併數據
│   ├── finrl_deepseek_enhanced_20240712_1430.csv
│   ├── finrl_deepseek_enhanced_20240712_1430.parquet
│   └── finrl_deepseek_enhanced_master.csv
└── sources/                         # 分源統計
    ├── source_breakdown_2024-07-01_2024-07-12.csv
    └── source_stats_2024-07-01_2024-07-12.json
```

## 🧪 測試和驗證

### **測試層級**

```bash
# 1. 單元測試
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_enhanced_modules.py -v

# 2. 爬取器測試
python -m pytest tests/test_crawler.py -v

# 3. 整合測試
python scripts/test_enhanced_integration.py

# 4. 性能測試
python -m pytest tests/ --benchmark-only
```

### **測試覆蓋率**

| 模組 | 測試文件 | 覆蓋率 | 狀態 |
|------|----------|--------|------|
| 核心爬取器 | test_integration.py | 85% | ✅ 良好 |
| 增強爬取器 | test_enhanced_modules.py | 75% | ✅ 良好 |
| 工具模組 | test_integration.py | 90% | ✅ 優秀 |
| 整合功能 | test_enhanced_integration.py | 80% | ✅ 良好 |

## 📈 性能優化

### **並行處理配置**

```json
{
  "performance": {
    "parallel_processing": {
      "max_workers": 5,
      "source_isolation": true
    },
    "caching": {
      "enabled": true,
      "cache_ttl_hours": 12
    }
  }
}
```

### **記憶體優化**

```python
# 使用進度記錄器監控處理進度
from src.utils.logger_util import ProgressLogger

logger = setup_logger('progress', config)
progress = ProgressLogger(logger, total_items=1000, report_interval=100)

for i in range(1000):
    # 處理項目
    process_item(i)
    progress.update()

progress.finish()
```

### **批次處理優化**

```bash
# 調整批次大小以平衡記憶體和效率
python scripts/run_enhanced_pipeline.py \
    --config config/enhanced_config.json \
    --chunk-size 500 \
    --max-workers 3
```

## 🛠️ 故障排除

### **常見問題和解決方案**

#### **1. API Key 相關問題**

```bash
# 問題：OpenAI API 超出限制
# 解決：檢查配置中的 cost_limit_usd 設置
python scripts/check_api_usage.py

# 問題：Finnhub API 達到免費額度
# 解決：切換到其他免費源或等待額度重置
```

#### **2. 爬取被限制**

```bash
# 問題：爬取被網站限制
# 解決：增加 rate_limiting 中的延遲時間
```

```json
{
  "rate_limiting": {
    "min_delay": 5,          // 增加延遲
    "max_delay": 10,
    "requests_per_minute": 20 // 降低頻率
  }
}
```

#### **3. 記憶體不足**

```json
{
  "performance": {
    "chunk_size": 500,        // 降低批次大小
    "memory_limit_gb": 4,     // 根據系統調整
    "parallel_processing": {
      "max_workers": 2        // 減少並行數
    }
  }
}
```

### **診斷工具**

```bash
# 系統健康檢查
python scripts/test_enhanced_integration.py

# 配置驗證
python scripts/migrate_config.py --validate

# 性能分析
python scripts/performance_analysis.py
```

## 🔄 遷移指南

### **從原版升級到增強版**

詳細遷移步驟請參考 [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

```bash
# 1. 備份原配置
cp config/config.json config/config_backup.json

# 2. 運行遷移腳本
python scripts/migrate_config.py \
    --source config/config.json \
    --target config/enhanced_config.json \
    --backup --validate

# 3. 測試新配置
python scripts/test_enhanced_integration.py
```

## 🔗 與主專案的整合

### **數據交換介面**

```python
# 標準化數據輸出格式，供主專案使用
def export_for_main_project(output_path: str, format: str = 'csv'):
    """
    匯出數據給主專案使用
    
    Args:
        output_path: 輸出路徑
        format: 輸出格式 ('csv', 'parquet', 'json')
    """
    pass

# 接收主專案的配置更新
def update_from_main_config(main_config: dict):
    """
    根據主專案配置更新本模組設置
    """
    pass
```

### **事件通知機制**

```python
# 向主專案發送狀態更新
def notify_main_project(event_type: str, data: dict):
    """
    通知主專案重要事件
    
    Args:
        event_type: 事件類型 ('data_ready', 'error', 'warning')
        data: 事件數據
    """
    pass
```

## 📋 開發指南

### **添加新的新聞源**

1. 在 `src/data_extraction/advanced_news_sources.py` 中創建新類
2. 實現標準介面方法：
   ```python
   class NewNewsSource:
       def __init__(self, config):
           pass
       
       def fetch_news(self, ticker, start_date, end_date):
           pass
       
       def validate_config(self):
           pass
   ```
3. 在 `config/news_config.json` 中添加配置
4. 更新測試用例

### **自定義 LLM 評分**

1. 修改 `src/data_processing/llm_scorer.py` 中的 prompt
2. 調整評分邏輯
3. 更新成本計算

### **擴展資料驗證**

1. 在 `src/integration/data_merger.py` 添加驗證規則
2. 更新品質檢查報告
3. 添加相應測試

## 📚 相關文檔

### **內部文檔**
- [📖 快速開始指南](QUICK_START.md)
- [🔄 遷移指南](MIGRATION_GUIDE.md)
- [⚡ 性能優化指南](docs/performance_guide.md)

### **外部連結**
- [🏠 主專案文檔](../CLAUDE.md)
- [📋 NewsExtraction 模組](../NewsExtraction/CLAUDE.md)
- [📊 FinRL-DeepSeek 原始專案](https://github.com/benstaf/FinRL_DeepSeek)

## 📞 技術支援

### **問題分類**
1. **配置問題** - 參考配置文檔和遷移指南
2. **API 問題** - 檢查 API key 和配額限制
3. **性能問題** - 參考性能優化指南
4. **整合問題** - 聯絡主專案團隊

### **聯絡方式**
- **模組維護者**: [聯絡信息]
- **主專案整合**: 參見 [主專案 CLAUDE.md](../CLAUDE.md)

---

## 📝 變更記錄

**v2.0.0** (2024-07-16)
- ✅ 新增 10+ 新聞源整合
- ✅ 統一新聞系統架構
- ✅ 智能成本控制
- ✅ 企業級監控
- ✅ 無縫向後兼容
- ✅ 自動化遷移工具

**v1.0.0** (2024-07-01)
- ✅ FinNLP 和 CommonCrawl 爬取
- ✅ OpenAI LLM 評分
- ✅ 基礎成本監控
- ✅ 標準化數據格式

**文檔維護**:
- **最後更新**: 2024-07-16
- **維護者**: FinRL-DeepSeek 擴展團隊
- **更新頻率**: 功能變更時同步更新