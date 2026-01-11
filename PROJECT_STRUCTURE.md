# 專案結構說明

## 目錄規劃

```
MindfulRL-Intraday/
│
├── config/                          # 設定檔
│   ├── .env                         # API keys (gitignored)
│   ├── .env.template               # API keys 範本
│   ├── tickers_core.json           # 核心股票清單 (89 檔)
│   ├── sectors.yaml                # 板塊定義 (for src/signals)
│   └── event_types.yaml            # 事件類型定義 (for src/signals)
│
├── training/                        # ★ RL 訓練模組 (已整理)
│   ├── __init__.py
│   ├── README.md                   # 訓練模組使用指南
│   ├── train_ppo_llm.py            # PPO 訓練 (情緒信號)
│   ├── train_cppo_llm_risk.py      # CPPO 訓練 (風險約束)
│   ├── backtest.py                 # 回測腳本
│   ├── envs/                       # RL 環境
│   │   ├── stocktrading_llm.py     # 情緒增強環境
│   │   └── stocktrading_llm_risk.py # 風險增強環境
│   ├── data_prep/                  # 數據準備
│   │   ├── train_trade_data_deepseek_sentiment.py
│   │   └── train_trade_data_deepseek_risk.py
│   └── scripts/                    # Shell 腳本
│       └── train.sh                # 統一訓練入口
│
├── src/                             # 核心模組
│   └── signals/                    # 多因子信號偵測系統
│       ├── __init__.py
│       ├── README.md               # 完整使用指南
│       ├── event_tagger.py         # 事件分類器 (13 種事件類型)
│       ├── sector_aggregator.py    # 板塊分析器 (13 個板塊)
│       ├── event_chain.py          # 事件鏈偵測 (7 種模式)
│       ├── anomaly_detector.py     # Z-score 異常偵測
│       └── synthesizer.py          # 多因子信號綜合器
│
├── data_sources/                    # 數據源 API 整合
│   ├── __init__.py
│   ├── base.py                     # 基礎類別
│   ├── polygon_source.py           # Polygon API (新聞)
│   ├── finnhub_source.py           # Finnhub API (新聞/報價)
│   ├── tiingo_source.py            # Tiingo API (歷史股價)
│   ├── sec_edgar_source.py         # SEC EDGAR (財報)
│   ├── alpha_vantage_source.py     # Alpha Vantage API
│   ├── eodhd_source.py             # EODHD API (基本面)
│   ├── ibkr_source.py              # IBKR TWS API (需 ib_insync)
│   └── source_factory.py           # 數據源工廠
│
├── scripts/                         # 執行腳本
│   ├── collection/                 # 數據收集
│   │   ├── collect_polygon_news.py
│   │   ├── collect_finnhub_news.py
│   │   ├── collect_ibkr_fundamentals.py
│   │   └── ...
│   │
│   ├── scoring/                    # LLM 評分工具
│   │   ├── README.md               # 評分工具指南
│   │   ├── score_ibkr_news.py      # IBKR 新聞評分
│   │   ├── validate_scores.py      # 評分驗證
│   │   ├── batch_sentiment_scoring.sh  # 批次情緒評分
│   │   └── batch_risk_scoring.sh   # 批次風險評分
│   │
│   ├── comparison/                 # 數據比較分析
│   │   ├── compare_scores.py       # 分數比較
│   │   ├── compare_scores_enhanced.py  # 增強版分數比較
│   │   ├── compare_summaries.py    # 摘要比較
│   │   ├── compare_news_sources.py # 新聞來源比較
│   │   ├── ab_score_comparison.py  # A/B 分數比較
│   │   └── comprehensive_news_comparison.py
│   │
│   ├── analysis/                   # 資料分析
│   │   ├── analyze_finrl_scores.py # FinRL 評分分析
│   │   ├── sentiment_backtest.py   # 情緒回測
│   │   ├── validate_scoring_value.py  # 評分預測力驗證
│   │   ├── detailed_factor_comparison.py  # 因子比較
│   │   └── ab_summary_comparison.py  # A/B 摘要比較
│   │
│   └── visualization/              # 視覺化
│       ├── README.md               # 視覺化工具指南
│       ├── news_dashboard.py       # Streamlit 新聞儀表板
│       ├── data_loader.py          # 數據載入模組
│       └── fundamentals_query.py   # 基本面查詢 CLI
│
├── NewsExtraction/                  # 歷史資料處理 (FNSPID)
│   ├── finrl_news_pipeline_read_csvs.py
│   ├── checkpoints/                # 處理檢查點
│   └── ...
│
├── docs/                            # 文檔
│   ├── strategy/                   # 策略相關
│   │   ├── STRATEGIC_DIRECTION_2026Q1.md
│   │   └── SIDEQUEST_CLAUDE_CODE_PLUGINS.md
│   ├── design/                     # 設計文檔
│   │   ├── MULTI_FACTOR_SIGNAL_DETECTION.md
│   │   ├── FINRL_INTEGRATION_DESIGN.md
│   │   └── IBKR_NEWS_COLLECTION_IMPROVEMENTS.md
│   ├── data/                       # 數據相關
│   │   ├── NEWS_DATA_INVENTORY.md
│   │   ├── SCORING_DATA_INVENTORY.md
│   │   └── IBKR_NEWS_API_LIMITATIONS.md
│   ├── features/                   # 功能規格
│   │   └── SENTIMENT_DERIVED_FEATURES.md
│   └── analysis/                   # 分析報告
│       └── HISTORICAL_ANALYSIS_LOG.md
│
├── data/                            # 資料儲存 (gitignored)
│   ├── news/
│   │   ├── raw/                    # 原始新聞 (by source)
│   │   ├── merged/                 # 合併去重後
│   │   ├── scored/                 # LLM 評分後
│   │   └── metadata/               # 收集統計
│   └── prices/                     # 股價資料
│
├── data_lake/                       # 大型資料湖 (gitignored)
│   └── raw/                        # 原始資料
│
├── results/                         # 分析結果 (gitignored)
│   └── finrl_full_analysis/
│
├── comparison_results/              # 比較結果輸出 (gitignored)
│
├── out/                             # 輸出目錄 (gitignored)
│
└── 根目錄腳本 (待整理)
    ├── train_ppo_llm.py            # PPO 訓練
    └── env_stocktrading_llm.py     # RL 環境
    # 評分腳本已移至 scripts/scoring/ (2026-01-12)
```

## 核心模組說明

### src/signals/ - 多因子信號偵測系統

從 LLM 評分的新聞數據中提取交易信號。詳見 [src/signals/README.md](src/signals/README.md)

```
輸入: DataFrame (ticker, date, title, llm_sentiment)
  ↓
├─ EventTagger      → 事件分類
├─ SectorAggregator → 板塊動能
├─ EventChainDetector → 事件鏈
├─ AnomalyDetector  → 統計異常
  ↓
└─ SignalSynthesizer → TradingSignal (STRONG_BUY/SELL/HOLD)
```

### data_sources/ - 數據源整合

統一 API 介面，支援多數據源切換：

| 數據源 | 用途 | 方案 |
|--------|------|------|
| Polygon | 歷史新聞 | 免費 |
| Finnhub | 即時新聞/報價/基本面 | 免費/付費 |
| Tiingo | 歷史股價 | 免費 (30+年) |
| SEC EDGAR | 官方財報 | 免費 |
| Alpha Vantage | 新聞/股價 | 免費 (限額) |
| EODHD | 基本面數據 | 付費 |
| IBKR | TWS 即時數據 | 需訂閱 |

## 使用方式

### 信號分析 (新)

```python
from src.signals import (
    EventTagger, SectorAggregator, EventChainDetector,
    AnomalyDetector, SignalSynthesizer
)
import pandas as pd

# 載入評分後的數據
df = pd.read_csv('data/news/scored/2025.csv')

# 事件分類
tagger = EventTagger()
df['event_type'] = df['title'].apply(lambda t: tagger.tag(t).primary_type)

# 綜合信號
synthesizer = SignalSynthesizer()
# ... (詳見 src/signals/README.md)
```

### 數據收集

```bash
# 歷史收集
python scripts/collection/collect_polygon_news.py --full-history

# 每日更新
python scripts/collection/collect_finnhub_news.py

# 查看統計
python scripts/collection/collect_all_news.py --stats
```

### LLM 評分

```bash
# OpenAI (gpt-5.x) - CSV 評分
python scripts/scoring/score_sentiment_openai.py --input data/news/merged/2024 --output data/news/scored/

# Anthropic (Claude) - CSV 評分
python scripts/scoring/score_sentiment_anthropic.py --input data/news/merged/2024 --output data/news/scored/

# IBKR Parquet 評分 (支援多 API key 輪換)
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2
```

## 目錄追蹤策略

### 應追蹤 (Git)

| 目錄 | 說明 |
|------|------|
| `src/` | 核心模組代碼 |
| `data_sources/` | API 整合代碼 |
| `scripts/` | 執行腳本 |
| `config/*.yaml`, `config/*.json` | 配置檔 (不含 .env) |
| `docs/` | 文檔 |
| `NewsExtraction/*.py` | 處理腳本 |

### 應排除 (gitignore)

| 目錄 | 說明 |
|------|------|
| `data/` | 數據儲存 |
| `data_lake/` | 大型資料湖 |
| `results/` | 分析結果 |
| `comparison_results/` | 比較輸出 |
| `out/` | 輸出目錄 |
| `config/.env` | API 密鑰 |
| `NewsExtraction/checkpoints/` | 處理檢查點 |
| `*.json` (根目錄) | 臨時輸出 |

### training/ - RL 訓練模組

強化學習訓練管道。詳見 [training/README.md](training/README.md)

```
數據準備 (data_prep/)
    ↓ (sentiment_{model} → llm_sentiment)
訓練 (train_ppo_llm.py / train_cppo_llm_risk.py)
    ↓
模型輸出 (agent_*.pth)
```

## 待整理項目

| 檔案 | 建議位置 | 狀態 |
|------|---------|------|
| score_sentiment_openai.py | scripts/scoring/ | ✅ 已移動 (2026-01-12) |
| score_risk_openai.py | scripts/scoring/ | ✅ 已移動 (2026-01-12) |
| score_sentiment_anthropic.py | scripts/scoring/ | ✅ 已移動 (2026-01-12) |
| score_risk_anthropic.py | scripts/scoring/ | ✅ 已移動 (2026-01-12) |
| openai_summary.py | scripts/scoring/ | ✅ 已移動 (2026-01-12) |

## 相關文檔

- [CLAUDE.md](CLAUDE.md) - AI 助手指南
- [README.md](README.md) - 專案總覽
- [docs/strategy/STRATEGIC_DIRECTION_2026Q1.md](docs/strategy/STRATEGIC_DIRECTION_2026Q1.md) - 2026 Q1 策略方向
- [docs/analysis/SCORING_VALIDATION_METHODOLOGY.md](docs/analysis/SCORING_VALIDATION_METHODOLOGY.md) - 評分驗證方法論

---

*最後更新: 2026-01-12*