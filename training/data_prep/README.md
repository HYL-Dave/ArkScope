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
- **現有腳本**: `train_trade_data_deepseek_sentiment.py`, `train_trade_data_deepseek_risk.py`

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

## 現有腳本說明

### `train_trade_data_deepseek_sentiment.py`

HuggingFace DeepSeek 情緒 → 訓練 CSV。流程：
1. 讀取 `sentiment_deepseek.csv`
2. yfinance 下載 NASDAQ 100 價格（2013-2023）
3. FeatureEngineer 計算技術指標
4. `add_sentiment()` 合併評分（rename `sentiment_deepseek` → `llm_sentiment`）
5. 輸出: `train_data_deepseek_sentiment_2013_2018.csv`, `trade_data_deepseek_sentiment_2019_2023.csv`

### `train_trade_data_deepseek_risk.py`

同上，但額外合併 risk 評分（rename `risk_deepseek` → `llm_risk`）。
輸出: `train_data_deepseek_risk_2013_2018.csv`, `trade_data_deepseek_risk_2019_2023.csv`

### `sentiment_deepseek_deepinfra.py` / `risk_deepseek_deepinfra.py`

LLM 評分腳本（使用 DeepSeek V3 via DeepInfra API）。
輸入文章 CSV → 批量 API 呼叫 → 輸出帶評分的 CSV。
與訓練資料準備無直接關係，屬於上游評分步驟。

---

## 訓練腳本的資料載入

### 現狀（HuggingFace 固定路徑）

```python
# train_ppo_llm.py / train_cppo_llm_risk.py
dataset = load_dataset("benstaf/nasdaq_2013_2023",
    data_files="train_data_deepseek_sentiment_2013_2018.csv")
train = pd.DataFrame(dataset['train'])
```

### 目標（支援本地 CSV）

```python
# --data 參數指定本地 CSV，跳過 HuggingFace 下載
python training/train_ppo_llm.py --data path/to/prepared_data.csv
```

這樣 data_prep 產出的 CSV 可以直接被訓練腳本使用，不需要上傳 HuggingFace。

---

*最後更新: 2026-03-01*
