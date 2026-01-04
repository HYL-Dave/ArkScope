# 專案結構說明

## 目錄規劃

```
MindfulRL-Intraday/
│
├── config/                          # 設定檔
│   ├── .env                         # API keys (gitignored)
│   ├── .env.template               # API keys 範本
│   └── tickers_core.json           # 股票清單
│
├── data/                            # 資料儲存 (gitignored)
│   ├── news/
│   │   ├── raw/polygon/            # Polygon 原始新聞
│   │   ├── raw/finnhub/            # Finnhub 原始新聞
│   │   ├── merged/                 # 合併去重後
│   │   ├── scored/                 # LLM 評分後
│   │   └── metadata/               # 收集統計/checkpoint
│   └── prices/                     # 股價資料
│
├── data_sources/                    # API 整合模組
│   ├── __init__.py
│   ├── base.py                     # 基礎類別
│   ├── polygon_source.py           # Polygon API
│   ├── finnhub_source.py           # Finnhub API
│   ├── tiingo_source.py            # Tiingo API
│   ├── sec_edgar_source.py         # SEC EDGAR
│   └── ibkr_source.py              # IBKR 連接
│
├── scripts/                         # 執行腳本
│   ├── collection/                 # 新聞收集
│   │   ├── README.md               # 使用指南
│   │   ├── collect_polygon_news.py # Polygon 歷史收集
│   │   ├── collect_finnhub_news.py # Finnhub 即時收集
│   │   ├── collect_all_news.py     # 統一入口
│   │   └── collect_ibkr_prices.py  # IBKR 股價收集
│   │
│   ├── comparison/                 # 資料比較分析
│   │   ├── compare_news_sources.py # Polygon vs Finnhub
│   │   ├── comprehensive_news_comparison.py
│   │   └── analyze_seeking_alpha_overlap.py
│   │
│   ├── scoring/                    # LLM 評分 (待整理)
│   └── analysis/                   # 資料分析 (待整理)
│
├── NewsExtraction/                  # 歷史資料處理
│   ├── finrl_news_pipeline_read_csvs.py
│   └── ...
│
├── comparison_results/              # 比較結果輸出
│
├── docs/                            # 文檔 (建議建立)
│   ├── API_SETUP.md
│   └── COLLECTION_GUIDE.md
│
└── 根目錄腳本 (待整理)
    ├── score_sentiment_openai.py   → scripts/scoring/
    ├── score_risk_openai.py        → scripts/scoring/
    ├── score_sentiment_anthropic.py → scripts/scoring/
    ├── train_ppo_llm.py            → (保留或移至 training/)
    └── ...
```

## 使用方式

### 新聞收集

```bash
# 從專案根目錄執行
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

# 歷史收集 (約 10 小時)
python scripts/collection/collect_polygon_news.py --full-history

# 中斷後繼續
python scripts/collection/collect_polygon_news.py --resume

# 每日更新
python scripts/collection/collect_finnhub_news.py

# 查看統計
python scripts/collection/collect_all_news.py --stats
```

### LLM 評分 (待整理)

```bash
# 現在從根目錄執行
python score_sentiment_openai.py --input data/news/merged/2024 --output data/news/scored/

# 整理後
python scripts/scoring/score_sentiment.py --model openai --input ...
```

## 待整理項目

| 檔案 | 建議位置 | 說明 |
|------|---------|------|
| score_sentiment_openai.py | scripts/scoring/ | OpenAI 情緒評分 |
| score_risk_openai.py | scripts/scoring/ | OpenAI 風險評分 |
| score_sentiment_anthropic.py | scripts/scoring/ | Claude 情緒評分 |
| compare_scores.py | scripts/analysis/ | 評分比較 |
| compare_summaries.py | scripts/analysis/ | 摘要比較 |
| visualization_dashboard.py | scripts/analysis/ | 視覺化 |
| train_ppo_llm.py | training/ 或保留 | PPO 訓練 |
| env_stocktrading_llm.py | environments/ | RL 環境 |

---

*最後更新: 2025-12-15*