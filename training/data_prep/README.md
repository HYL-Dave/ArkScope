# Data Preparation for RL Training

本目錄負責將各來源的新聞評分 + 股價資料合併為訓練用 CSV。

## 訓練資料格式規格（Training Data Contract）

RL 環境（`training/envs/`）期望的 DataFrame 必須符合以下格式，
否則 `_initiate_state()` / `_update_state()` 會報錯或產生錯誤的 state 向量。

### Index 結構

```
Index: 連續整數（0, 1, 2, ...），每個唯一日期對應一個值
       同一天的多支股票共享相同 index 值
       由 train script 的 load_data() 建立，data_prep 不需處理
```

### 必要欄位

| 欄位 | 類型 | 說明 | 用途 |
|------|------|------|------|
| `date` | str (YYYY-MM-DD) | 交易日期 | `_get_date()`, merge key |
| `tic` | str | 股票代號 (e.g. AAPL) | `df.tic.unique()` 計算 stock_dim |
| `close` | float | 收盤價 | state 向量的價格部分，交易計算 |
| `macd` | float | MACD 指標 | ┐ |
| `boll_ub` | float | 布林帶上軌 | │ |
| `boll_lb` | float | 布林帶下軌 | │ |
| `rsi_30` | float | 30日 RSI | ├ 8 個技術指標 |
| `cci_30` | float | 30日 CCI | │ (config.INDICATORS) |
| `dx_30` | float | 30日 DX | │ |
| `close_30_sma` | float | 30日均線 | │ |
| `close_60_sma` | float | 60日均線 | ┘ |
| `llm_sentiment` | int/float | 1-5 情緒分數 | PPO + CPPO 環境使用 |
| `llm_risk` | int/float | 1-5 風險分數 | **僅 CPPO 環境需要** |

### 技術指標來源

技術指標從 OHLCV（Open/High/Low/Close/Volume）價格資料計算：

| 縮寫 | 全名 | 說明 |
|------|------|------|
| O | Open | 開盤價 |
| H | High | 最高價 |
| L | Low | 最低價 |
| C | Close | 收盤價 |
| V | Volume | 成交量 |

OHLCV 是所有技術指標的基礎。本專案透過 `preprocessor.py` 的 `FeatureEngineer`
（底層使用 stockstats 套件）從 OHLCV 計算 8 個技術指標。

### State 向量結構

環境將 DataFrame 轉為 state 向量，結構如下：

```
PPO (stocktrading_llm.py):
  [cash] + [close * N] + [shares * N] + [indicator * N * 8] + [sentiment * N]
  長度 = 1 + 2*N + (1 + 8)*N = 1 + 11*N

CPPO (stocktrading_llm_risk.py):
  [cash] + [close * N] + [shares * N] + [indicator * N * 8] + [sentiment * N] + [risk * N]
  長度 = 1 + 2*N + (2 + 8)*N = 1 + 12*N

其中 N = stock_dim（股票數量）
```

### 缺失值處理

| 欄位 | 填充值 | 原因 |
|------|--------|------|
| `llm_sentiment` | 0 (PPO) | 0 在 1-5 範圍外，環境不會匹配任何條件 |
| `llm_risk` | 3 (CPPO) | 3 = 中性風險，權重 = 1.0（無影響） |
| 技術指標 | forward-fill (per ticker) | 避免跨股票資料洩漏 |
| 價格欄位 | drop NaN | 無價格的交易日無法計算 |

### 資料結構範例

```
     date    tic    close   macd  ... llm_sentiment  llm_risk
0  2013-01-02  AAPL  78.43  0.12  ...      4           3
0  2013-01-02  AMZN  257.31  1.23  ...      3           2
0  2013-01-02  GOOGL  723.25  2.45  ...      3           3
1  2013-01-03  AAPL  79.01  0.15  ...      5           1
1  2013-01-03  AMZN  258.48  1.30  ...      3           3
...
```

注意：index 是日期序號（不是 row number），同一天的多支股票共享相同 index。

---

## 資料來源

### 來源 1: HuggingFace DeepSeek（現有 pipeline）

- **路徑**: `/mnt/md0/finrl/huggingface_datasets/`
- **評分檔案**:
  - `FinRL_DeepSeek_sentiment/sentiment_deepseek_new_cleaned_nasdaq_news_full.csv`
  - `FinRL_DeepSeek_risk/risk_deepseek_cleaned_nasdaq_news_full.csv`
- **評分欄位**: `sentiment_deepseek`, `risk_deepseek`
- **日期範圍**: 2009-2024（127K 筆已評分）
- **股票**: 89 支 NASDAQ
- **品質問題**: 評分嚴重偏中性（sentiment 66.3%, risk 84.5% 為分數 3）
- **價格來源**: yfinance 下載

### 來源 2: Claude 模型（Opus/Sonnet/Haiku）

- **路徑**: `/mnt/md0/finrl/claude/sentiment/`
- **評分檔案**:
  - `sentiment_opus_by_gpt5_summary.csv` (sentiment_opus)
  - `sentiment_sonnet_by_gpt5_summary.csv` (sentiment_sonnet)
  - `sentiment_haiku_by_gpt5_summary.csv` (sentiment_haiku)
- **評分欄位**: `sentiment_opus` / `sentiment_sonnet` / `sentiment_haiku`
- **日期範圍**: 同 HuggingFace（同批文章重新評分）
- **品質**: 比 DeepSeek 平衡（中性 30.6% vs 66.3%），但 38.7% 未評分
- **欄位格式**: 與 HuggingFace 相同（`Date`, `Stock_symbol`, ...）
- **價格來源**: 需 yfinance 下載（與來源 1 共用）
- **現有腳本**: 無 — 需新增

### 來源 3: GPT-5（多 effort 等級）

- **路徑**: `/mnt/md0/finrl/gpt-5/sentiment/`
- **評分檔案**:
  - `sentiment_gpt-5_high_by_o3_summary.csv`
  - `sentiment_gpt-5_medium_by_o3_summary.csv`
  - `sentiment_gpt-5_low_by_o3_summary.csv`
  - `sentiment_gpt-5_minimal_by_o3_summary.csv`
- **評分欄位**: `sentiment_gpt_5`
- **日期範圍**: 同 HuggingFace
- **品質**: 與 Claude 相近（中性 33%），38.7% 未評分
- **欄位格式**: 與 HuggingFace 相同
- **價格來源**: 需 yfinance 下載（與來源 1 共用）
- **現有腳本**: 無 — 需新增

### 來源 4: Polygon API（現代資料）

- **路徑**: `data/news/raw/polygon/` (本專案內)
- **格式**: Parquet（月檔，如 `2025/2025-01.parquet`）
- **評分欄位**: `sentiment_gpt_5_2_xhigh`
- **日期範圍**: 2022-01 至 2026-02（110K 筆，持續更新）
- **股票**: ~97 支/月
- **品質**: 評分分佈較歷史資料平衡
- **重要差異**:
  - Parquet 格式（非 CSV）
  - 欄位名不同：`ticker`(非 `Stock_symbol`), `published_at`(非 `Date`)
  - **沒有 OHLCV 價格資料** — 需另外下載
  - **沒有 risk 評分** — 僅能用於 PPO，無法用於 CPPO
  - 一篇文章可能對應多個 ticker（`related_tickers` 欄位）
- **價格來源**: 需 yfinance 或 Tiingo 下載（日期範圍 2022-2026）
- **現有腳本**: 無 — 需新增

---

## 資料處理 Pipeline

```
Step 1: 取得 OHLCV 價格資料
  ticker list + 日期範圍 → yfinance / Tiingo → OHLCV DataFrame

Step 2: 計算技術指標
  OHLCV → FeatureEngineer (stockstats) → 8 個技術指標

Step 3: 建立完整矩陣
  所有日期 × 所有 ticker → Cartesian product → per-ticker forward-fill

Step 4: 合併 LLM 評分
  價格+指標 + 評分 CSV → left merge on (date, tic)
  缺失值填充: sentiment → 0 (PPO) 或 3 (neutral), risk → 3

Step 5: 分割 Train / Trade
  依日期分割為訓練集和回測集
```

### 各來源的欄位映射

| 來源 | 日期欄位 | 股票欄位 | 情緒欄位 | 風險欄位 |
|------|----------|----------|----------|----------|
| HuggingFace | `Date` | `Stock_symbol` | `sentiment_deepseek` | `risk_deepseek` |
| Claude | `Date` | `Stock_symbol` | `sentiment_opus` 等 | 無 |
| GPT-5 | `Date` | `Stock_symbol` | `sentiment_gpt_5` | 無 |
| Polygon | `published_at` | `ticker` | `sentiment_gpt_5_2_xhigh` | 無 |

所有來源最終都要 rename 為 `llm_sentiment`（和 `llm_risk`）才能被訓練環境使用。

---

---

## OHLCV 價格來源比較

### IBKR vs yfinance 實測比對（2026-03-01）

以 AAPL 為測試標的，比較已收集的 IBKR 資料與 yfinance 日線。

**收盤價差異**

| 資料集 | 天數 | 平均差距 | 最大差距 | 原因 |
|--------|------|----------|----------|------|
| 2023 hourly | 250 | $2.20 | $2.57 | yfinance 自動調整股息（auto_adjust=True） |
| 2026 15min | 39 | $0.57 | $6.52 | 調整累積較少；極端值為 IBKR 部分交易日 |

**原因**：yfinance 預設 `auto_adjust=True`，會把歷史價格回溯調整股息。
IBKR 回傳的是當時的實際交易價格（unadjusted）。兩者都正確，只是不同的表示方式。
越久之前的資料差距越大（股息調整累積效應）。

**成交量差異**

| 資料集 | 平均差距 | 原因 |
|--------|----------|------|
| 2023 hourly | -32% | IBKR = RTH only (9:30-16:00)，yfinance = 含盤前盤後 |
| 2026 15min | -58% | 同上，部分天數 IBKR 資料不完整（< 26 bars） |

**結論：IBKR volume 始終低於 yfinance**，因為只涵蓋正常交易時段。

### 訓練用價格來源建議

| 場景 | 推薦來源 | 原因 |
|------|----------|------|
| 日線訓練（現有 pipeline） | **yfinance** | 歷史最長、免費、自動調整、已有 YahooDownloader 整合 |
| Polygon 新聞→日線訓練 | **yfinance** | 只需日線，一次拉完最簡單 |
| 日內交易策略（未來） | **IBKR** | 唯一有 15min/1hr 歷史資料的來源 |

**重要**：同一次訓練中所有價格必須來自同一來源，不可混用 adjusted 和 unadjusted。

### 已收集的 IBKR 資料

```
data/prices/
├── 15min/          # 211 files, 135 tickers, 2024-present
│   ├── AAPL_15min_2024_2026.csv  (853 bars)
│   └── ...
├── hourly/         # 75 files, 2023
│   ├── AAPL_hourly_2023.csv  (1744 bars, ~7 bars/day)
│   └── ...
└── collection_summary.json
```

格式：`datetime,open,high,low,close,volume,ticker`（datetime 含時區 offset）

---

## 統一資料準備腳本

### `prepare_training_data.py`

統一入口，支援所有 4 種資料來源。流程：
1. 載入 LLM 評分（根據 `--source` 選擇來源）
2. yfinance 下載 OHLCV + 計算技術指標
3. Left merge 評分到價格矩陣
4. 分割 train / trade 時段
5. 輸出 CSV（格式符合訓練資料合約）

```bash
# Claude Opus 情緒
python -m training.data_prep.prepare_training_data \
  --source claude --model opus

# GPT-5 high effort
python -m training.data_prep.prepare_training_data \
  --source gpt5 --model high

# HuggingFace DeepSeek (sentiment + risk, for CPPO)
python -m training.data_prep.prepare_training_data \
  --source huggingface --score-type both

# Polygon 現代資料（自訂日期範圍）
python -m training.data_prep.prepare_training_data \
  --source polygon \
  --train-start 2022-06-01 --train-end 2024-12-31 \
  --trade-start 2025-01-01 --trade-end 2026-02-28

# 訓練
python training/train_ppo_llm.py --data training/data_prep/output/train_claude_opus.csv
```

輸出目錄：`training/data_prep/output/`

---

*最後更新: 2026-03-01*
