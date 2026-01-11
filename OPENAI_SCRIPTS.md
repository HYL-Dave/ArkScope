# OpenAI LLM Inference Scripts

This document describes scripts for scoring financial news headlines with OpenAI LLMs (GPT-4.1, o3, o4-mini) to generate sentiment and risk signals.
For a fully standalone workflow, see `README.md` in this folder.

## Prerequisites
- Python 3.7 or higher
- Install dependencies:
  ```bash
  pip install openai pandas
  ```
- Set your OpenAI API key:
  ```bash
  export OPENAI_API_KEY="your_api_key"
  ```

## Script: score_sentiment_openai.py

Path: `scripts/scoring/score_sentiment_openai.py`

### Description
Scores each news headline for sentiment using an OpenAI LLM.

### Input CSV Format
- Required columns: `symbol`, `headline`
- Example:
  ```csv
  symbol,headline
  AAPL,Apple announces record quarterly earnings
  TSLA,Elon Musk tweets about pricing cuts
  ```

### Usage
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input data/headlines.csv \
  --output data/sentiment_scored.csv \
  --model o4-mini
```

### Output
- CSV with original columns plus `sentiment_score` (integer 1–5)

## Script: score_risk_openai.py

Path: `scripts/scoring/score_risk_openai.py`

### Description
Scores each news headline for downside risk using an OpenAI LLM.

### Input CSV Format
Same as sentiment script.

### Usage
```bash
python scripts/scoring/score_risk_openai.py \
  --input data/headlines.csv \
  --output data/risk_scored.csv \
  --model o4-mini
```

### Output
- CSV with original columns plus `risk_score` (integer 1–5)

## Workflow Integration
1. Prepare news dataset: collect headlines per stock per 30-min interval.
2. Run `score_sentiment_openai.py` and `score_risk_openai.py` to generate signals.
3. Merge scores with price and technical indicator data.
4. Feed merged DataFrame into `env_stocktrading_intraday.py` or daily env.

## Customization
- Change `--model` to `gpt-4.1`, `o3`, or `o4-mini` as needed.
- Adjust retry/pause logic in scripts for rate limits.

## Notes
- Scripts score each headline individually; for batch/grouped scoring, consider grouping by symbol and batching in one API call.
 - Monitor logs for parsing errors and unexpected formats.

## Reusing Existing Code
- The following existing modules support LLM-driven sentiment and risk and can be reused directly:
  - `env_stocktrading_llm.py`: Gym environment with `llm_sentiment` injection.
  - `env_stocktrading_llm_risk.py`: Gym environment with both `llm_sentiment` and `llm_risk`.
  - `train_trade_data_deepseek_sentiment.py` / `train_trade_data_deepseek_risk.py`: data merge pipelines (replace DeepSeek CSVs with OpenAI CSVs).
  - `train_ppo_llm.py`: trains PPO with sentiment; expects `train_data_deepseek_sentiment_2013_2018.csv`.
  - `train_cppo_llm_risk.py`: trains CPPO with sentiment+risk; expects `train_data_deepseek_risk_2013_2018.csv`.

Rather than duplicating full env/train scripts, follow this workflow:
1. Score sentiment:
   ```bash
   python scripts/scoring/score_sentiment_openai.py \
     --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
     --output sentiment_scored.csv \
     --model o4-mini \
     --chunk-size 5000 \
     --symbol-column Stock_symbol \
     --text-column Lsa_summary \
     --date-column Date \
     --verbose
   ```
   # The script will auto-create the output directory if needed.
   # The output CSV will preserve all input columns plus the new 'sentiment_{model}' column (e.g., sentiment_o4_mini).
   # Results are appended chunk by chunk; interrupt (Ctrl+C) anytime and re-run with the same arguments to resume.
2. Score risk:
   ```bash
   python scripts/scoring/score_risk_openai.py \
     --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
     --output risk_scored.csv \
     --model o4-mini \
     --chunk-size 5000 \
     --symbol-column Stock_symbol \
     --text-column Lsa_summary \
     --date-column Date \
     --verbose
   ```
   # The script will auto-create the output directory if needed.
   # The output CSV will preserve all input columns plus the new 'risk_{model}' column (e.g., risk_o4_mini).
   # Results are appended chunk by chunk; interrupt (Ctrl+C) anytime and re-run with the same arguments to resume.
3. Prepare merged dataset:
   ```bash
   python prepare_dataset_openai.py \
     --price-data data/intraday.csv \
     --sentiment sentiment_scored.csv \
     --risk risk_scored.csv \
     --date-col Date \
     --symbol-col Stock_symbol \
     --output data/merged_dataset.csv
   ```
4. Train RL agents:
   ```bash
   python train_ppo_llm.py     # uses llm_sentiment
   mpirun -np 4 python train_cppo_llm_risk.py   # uses llm_sentiment + llm_risk
   ```
5. Backtest:
   ```bash
   python backtest_openai.py \
     --data data/merged_dataset.csv \
     --model trained_models/agent_ppo_llm_100_epochs_sentiment.pth \
     --env sentiment \
     --output-plot outputs/equity.png
   ```

## Additional Scripts

### score_sentiment_openai.py
Score financial news headlines for sentiment using OpenAI, with resumable chunked processing.

Usage:
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output sentiment_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 1000000 \
  --retry 3 \
  --retry-missing 3 \
  --max-runtime 3600
```

# Flex mode: after daily token limit, switch to flex service_tier with longer timeout and retry
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output sentiment_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 1000000 \
  --retry 3 \
  --retry-missing 3 \
  --max-runtime 3600 \
  --allow-flex --flex-timeout 900 --flex-retries 1
```

> **Note:** 脚本在执行完触发每日 token 限额的整个 chunk 并写入输出后会自动退出，便于您根据 `--daily-token-limit` 调整 `--chunk-size`。

#### score_sentiment_openai.py 完整參數說明

| 參數                 | 默認值     | 說明                                                                 |
|----------------------|-----------|----------------------------------------------------------------------|
| `--input`            | 必填       | 輸入 CSV 文件路徑，必須包含 symbol, headline（或通過 --symbol-column/--text-column 指定）|
| `--output`           | 必填       | 輸出 CSV 文件路徑，會添加 `sentiment_{model}` 列 (如 sentiment_o4_mini)  |
| `--model`            | o4-mini   | OpenAI 模型名稱（如 o4-mini, gpt-4.1, o3, gpt-5, gpt-5-mini 等）        |
| `--symbol-column`    | Stock_symbol | 輸入 CSV 中股票代碼列名                                             |
| `--text-column`      | Article_title | 輸入 CSV 中文本列名（可選：Article_title, Article, Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary, o3_summary, gpt_5_summary） |
| `--date-column`      | None      | 輸入 CSV 中日期列名，用於保留日期用於後續合併                          |
| `--chunk-size`       | 1000      | 分塊大小，用於斷點續跑                                                 |
| `--api-key`          | None      | 單個 OpenAI API Key，如未指定則使用環境變量 `OPENAI_API_KEY`            |
| `--api-keys-file`    | None      | API Key 文件路徑，文件內每行一個 key，達到限額時自動輪轉                |
| `--daily-token-limit`| None      | 單個 Key token 限額（近似值），達到後自動輪轉或停止                     |
| `--allow-flex`       | False     | 啟用 Flex 模式：達到 token 限額後切換到 service_tier='flex'                 |
| `--flex-timeout`     | 900.0     | Flex 模式下的超時時間（秒），默認為 900                                |
| `--flex-retries`     | 1         | Flex 模式下的重試次數，默認為 1                                       |
| `--verbose`          | False     | 啟用詳細日誌輸出                                                     |
| `--retry`            | 3         | score_headline() 內部解析失敗時的重試次數                             |
| `--retry-missing`    | 3         | 對未獲取到分數的行進行額外重試次數                                    |
| `--max-runtime`      | None      | 最大運行時間（秒），超時後在當前 chunk 完成後停止腳本                  |
| `--reasoning-effort` | high      | 推理努力等級（o3, o4-mini 等模型：low, medium, high；gpt-5 額外支援 minimal） |
| `--verbosity`        | low       | 詳細程度等級（僅 gpt-5 模型：low, medium, high）                       |

#### 實用範例

##### 範例 1：使用 Flex 模式連續運行（不受 daily token limit 停止）
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv \
  --output /mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_R_medium_V_low_by_gpt-5_reason_high_verbosity_high_summary.csv \
  --model gpt-5 \
  --symbol-column Stock_symbol \
  --text-column gpt_5_summary \
  --date-column Date \
  --chunk-size 20 \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 0 \
  --retry-missing 5 \
  --retry 6 \
  --reasoning-effort medium \
  --verbosity low \
  --allow-flex \
  --flex-timeout 1000 \
  --flex-retries 5
```
> **說明**：`--daily-token-limit 0` 關閉 token 限制檢測，`--allow-flex` 啟用 flex 服務層以獲得更高的可用性和更長的超時時間。

##### 範例 2：受 daily token limit 控制的運行
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv \
  --output /mnt/md0/finrl/gpt-5-mini/sentiment/sentiment_gpt-5-mini_by_gpt-5_reason_high_verbosity_high_summary.csv \
  --model gpt-5-mini \
  --symbol-column Stock_symbol \
  --text-column gpt_5_summary \
  --date-column Date \
  --chunk-size 20 \
  --api-keys-file api_keys_tier1.txt \
  --daily-token-limit 2480000 \
  --retry-missing 5 \
  --retry 6 \
  --reasoning-effort high \
  --verbosity low
```
> **說明**：達到 `--daily-token-limit 2480000` 後會完成當前 chunk 並停止運行，適合成本控制。

### check_sentiment_csv.py
Validate sentiment-scored CSV output for missing or invalid scores and required columns.

Usage:
```bash
python check_sentiment_csv.py \
  --input /mnt/md0/finrl/o3/sentiment/sentiment_o3_2.csv \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --sentiment-column sentiment_deepseek
```

### score_risk_openai.py
Score financial news headlines for downside risk using OpenAI, with resumable chunked processing.

### Script: audit_stock_news.py
Path: `audit_stock_news.py`

### Description
Audit one or more CSV files for issues in the date column and per-stock duplicates:
1. Rows where the date column cannot be parsed into datetime (`bad_date`).
2. Date column not strictly monotonic (`order`).
3. Same stock symbol has multiple news entries on the same calendar date (`duplicate`).

Outputs a CSV report (`file,issue,detail`) capturing any issues found.

### Usage example
```bash
python audit_stock_news.py \
  --path /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news \
  --date-column Date \
  --symbol-column Stock_symbol \
  --output audit_report.csv
```

The output `audit_report.csv` will have columns `[file, issue, detail]`, capturing any ordering or duplicate issues found.

# Script: openai_summary.py

Path: `scripts/scoring/openai_summary.py`

### Description
Summarizes the full `Article` text of each news entry into a new `<model>_summary` column, skipping empty articles. Supports resumable chunked processing, API key rotation, and daily token limits.

### 完整參數說明

| 參數                 | 默認值     | 說明                                                                 |
|----------------------|-----------|----------------------------------------------------------------------|
| `--input`            | 必填       | 輸入 CSV 文件路徑，必須包含 symbol, article（或通過 --symbol-column/--text-column 指定）|
| `--output`           | 必填       | 輸出 CSV 文件路徑，會添加 `<model>_summary`、`prompt_tokens`、`completion_tokens` 列 |
| `--model`            | o4-mini   | OpenAI 模型名稱（如 o4-mini, gpt-4.1, o3, gpt-5, gpt-5-mini 等）        |
| `--symbol-column`    | Stock_symbol | 輸入 CSV 中股票代碼列名                                              |
| `--text-column`      | Article   | 輸入 CSV 中文本列名                                                    |
| `--summary-column`   | None      | 輸出摘要列名（默認為 `<model>_summary`）                              |
| `--chunk-size`       | 1000      | 分塊大小，用於斷點續跑                                                 |
| `--api-key`          | None      | 單個 OpenAI API Key，如未指定則使用環境變量 `OPENAI_API_KEY`            |
| `--api-keys-file`    | None      | API Key 文件路徑，文件內每行一個 key，達到限額時自動輪轉                |
| `--daily-token-limit`| None      | 單個 Key token 限額（近似值），達到後自動輪轉或停止                     |
| `--allow-flex`       | False     | 啟用 Flex 模式：達到 token 限額後切換到 service_tier='flex'                 |
| `--flex-timeout`     | 900.0     | Flex 模式下的超時時間（秒），默認為 900                                |
| `--flex-retries`     | 1         | Flex 模式下的重試次數，默認為 1                                       |
| `--verbose`          | False     | 啟用詳細日誌輸出                                                     |
| `--retry`            | 3         | summarize_article() 內部解析失敗時的重試次數                          |
| `--retry-missing`    | 1         | 對未獲取到摘要的行進行額外重試次數                                    |
| `--max-runtime`      | None      | 最大運行時間（秒），超時後在當前 chunk 完成後停止腳本                  |
| `--reasoning-effort` | high      | 推理努力等級（o3, o4-mini 等模型：low, medium, high；gpt-5 額外支援 minimal） |
| `--verbosity`        | low       | 詳細程度等級（僅 gpt-5 模型：low, medium, high）                       |

### Usage examples

#### 基本用法
```bash
python scripts/scoring/openai_summary.py \
  --input sentiment_deepseek_new_cleaned_nasdaq_news_full.csv \
  --output news_with_summary.csv \
  --model o4-mini \
  --symbol-column Stock_symbol \
  --text-column Article \
  --summary-column o4_mini_summary \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 9260000 \
  --chunk-size 500 \
  --verbose
```

#### 使用 GPT-5 模型與新參數
```bash
python scripts/scoring/openai_summary.py \
  --input /mnt/md0/finrl/news_data/full_articles.csv \
  --output /mnt/md0/finrl/gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv \
  --model gpt-5 \
  --symbol-column Stock_symbol \
  --text-column Article \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 2480000 \
  --chunk-size 20 \
  --reasoning-effort high \
  --verbosity high \
  --retry 6 \
  --retry-missing 5
```

#### Flex 模式範例
```bash
python scripts/scoring/openai_summary.py \
  --input large_dataset.csv \
  --output news_with_summary.csv \
  --model gpt-5-mini \
  --symbol-column Stock_symbol \
  --text-column Article \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 0 \
  --allow-flex \
  --flex-timeout 1000 \
  --flex-retries 5 \
  --chunk-size 50
```

### 輸出格式
輸出 CSV 將保留所有原始列並添加：
- `<model>_summary`: 生成的摘要文本
- `prompt_tokens`: 每個摘要使用的 prompt tokens 數量
- `completion_tokens`: 每個摘要使用的 completion tokens 數量

# Script: compare_sentiment.py

Path: `compare_sentiment.py`

### Description
Compares sentiment score columns between two CSV files and writes all rows where the scores differ, along with key columns, the old/new scores, and any other shared columns.

### Usage example
```bash
python compare_sentiment.py \
  --old old_sentiment.csv \
  --new new_sentiment.csv \
  --score-col sentiment_deepseek \
  --on Date Stock_symbol \
  --output diff_sentiment.csv
```

The output CSV will include all join key columns plus two score columns (`sentiment_deepseek_old`, `sentiment_deepseek_new`) and any other common columns shared between the inputs.

Usage:
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output risk_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 250000
```

# Flex mode: after daily token limit, switch to flex service_tier with longer timeout and retry
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output risk_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 250000 \
  --allow-flex --flex-timeout 900 --flex-retries 1
```

#### score_risk_openai.py 完整參數說明

| 參數                 | 默認值     | 說明                                                                 |
|----------------------|-----------|----------------------------------------------------------------------|
| `--input`            | 必填       | 輸入 CSV 文件路徑，必須包含 symbol, headline（或通過 --symbol-column/--text-column 指定）|
| `--output`           | 必填       | 輸出 CSV 文件路徑，會添加 `risk_{model}` 列 (如 risk_o4_mini)            |
| `--model`            | o4-mini   | OpenAI 模型名稱（如 o4-mini, gpt-4.1, o3, gpt-5, gpt-5-mini 等）        |
| `--symbol-column`    | Stock_symbol | 輸入 CSV 中股票代碼列名                                             |
| `--text-column`      | Article_title | 輸入 CSV 中文本列名（可選：Article_title, Article, Lsa_summary, Luhn_summary, Textrank_summary, Lexrank_summary, o3_summary, gpt_5_summary） |
| `--date-column`      | None      | 輸入 CSV 中日期列名，用於保留日期用於後續合併                          |
| `--chunk-size`       | 1000      | 分塊大小，用於斷點續跑                                                 |
| `--api-key`          | None      | 單個 OpenAI API Key，如未指定則使用環境變量 `OPENAI_API_KEY`            |
| `--api-keys-file`    | None      | API Key 文件路徑，文件內每行一個 key，達到限額時自動輪轉                |
| `--daily-token-limit`| None      | 單個 Key token 限額（近似值），達到後自動輪轉或停止                     |
| `--allow-flex`       | False     | 啟用 Flex 模式：達到 token 限額後切換到 service_tier='flex'                 |
| `--flex-timeout`     | 900.0     | Flex 模式下的超時時間（秒），默認為 900                                |
| `--flex-retries`     | 1         | Flex 模式下的重試次數，默認為 1                                       |
| `--verbose`          | False     | 啟用詳細日誌輸出                                                     |
| `--retry`            | 3         | score_headline() 內部解析失敗時的重試次數                             |
| `--retry-missing`    | 3         | 對未獲取到風險分數的行進行額外重試次數                                |
| `--max-runtime`      | None      | 最大運行時間（秒），超時後在當前 chunk 完成後停止腳本                  |
| `--reasoning-effort` | high      | 推理努力等級（o3, o4-mini 等模型：low, medium, high；gpt-5 額外支援 minimal） |
| `--verbosity`        | low       | 詳細程度等級（僅 gpt-5 模型：low, medium, high）                       |

#### 實用範例

##### 基本風險評分
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output risk_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 250000
```

##### Flex 模式風險評分
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output risk_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys_tier5.txt \
  --daily-token-limit 250000 \
  --allow-flex \
  --flex-timeout 900 \
  --flex-retries 1
```

##### 使用 GPT-5 模型進行風險評分
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/gpt-5/summary/gpt-5_summaries.csv \
  --output /mnt/md0/finrl/gpt-5/risk/risk_gpt-5_analysis.csv \
  --model gpt-5 \
  --symbol-column Stock_symbol \
  --text-column gpt_5_summary \
  --date-column Date \
  --chunk-size 20 \
  --api-keys-file api_keys_tier1.txt \
  --daily-token-limit 2480000 \
  --reasoning-effort high \
  --verbosity medium \
  --retry 6 \
  --retry-missing 5
```

### prepare_dataset_openai.py
Merge base price+indicator CSV with sentiment and risk score CSVs into a single dataset for RL.
Usage:
```bash
python prepare_dataset_openai.py \
  --price-data data/intraday.csv \
  --sentiment data/sentiment_scored.csv \
  --risk data/risk_scored.csv \
  --date-col Date \
  --symbol-col Stock_symbol \
  --output data/merged_dataset.csv
```

### train_openai.sh
Wrapper to train PPO/CPPO agents using OpenAI-enhanced dataset.
Usage:
```bash
bash train_openai.sh \
  data/merged_dataset.csv \
  ppo sentiment
bash train_openai.sh \
  data/merged_dataset.csv \
  cppo risk
```

### backtest_openai.py
Runs a backtest of a trained agent with specified environment (baseline, sentiment, or risk).
Usage:
```bash
python backtest_openai.py \
  --data data/test_dataset.csv \
  --model trained_models/agent_sentiment.pth \
  --env sentiment \
  --output-plot outputs/equity.png
```

## 新模型特性：GPT-5 和 GPT-5-mini

### 新參數說明

所有三個腳本現在都支援新的 GPT-5 系列模型，並包含兩個新的參數：

#### `--reasoning-effort`
控制推理模型的推理深度和詳細程度：

**支援的模型和選項**：
- **o3, o4-mini 系列**：`low`, `medium`, `high` (默認: `high`)
- **gpt-5, gpt-5-mini 系列**：`minimal`, `low`, `medium`, `high` (默認: `high`)

**使用邏輯**：
- `high`: 最深度的推理，質量最高但消耗更多 tokens
- `medium`: 平衡的推理深度和效率
- `low`: 快速推理，較少 token 消耗
- `minimal`: 僅 gpt-5 系列支援，最少的推理步驟

#### `--verbosity`
控制模型輸出的詳細程度（僅 gpt-5 系列支援）：

**選項**：`low`, `medium`, `high` (默認: `low`)

**使用邏輯**：
- `low`: 簡潔的輸出，適合批量處理
- `medium`: 適中的詳細程度
- `high`: 詳細的輸出，包含更多推理過程

### 應用邏輯與策略

#### 1. 成本控制策略

**高成本控制（使用 daily-token-limit）**：
```bash
# 範例：嚴格控制成本，達到 2.48M tokens 後停止
python scripts/scoring/score_sentiment_openai.py \
  --model gpt-5-mini \
  --daily-token-limit 2480000 \
  --reasoning-effort high \
  --verbosity low
```

**無限制運行（Flex 模式）**：
```bash
# 範例：不受 token 限制，持續運行直到完成
python scripts/scoring/score_sentiment_openai.py \
  --model gpt-5 \
  --daily-token-limit 0 \
  --allow-flex \
  --flex-timeout 1000 \
  --flex-retries 5 \
  --reasoning-effort medium \
  --verbosity low
```

#### 2. 模型選擇與參數配置建議

| 場景 | 模型 | reasoning_effort | verbosity | 適用情況 |
|------|------|------------------|-----------|----------|
| 快速批量處理 | gpt-5-mini | low | low | 大量數據，追求速度 |
| 平衡質量與效率 | gpt-5-mini | medium | low | 日常使用，中等質量要求 |
| 高質量分析 | gpt-5 | high | medium | 關鍵決策，需要高質量結果 |
| 研究探索 | gpt-5 | high | high | 深度分析，需要詳細推理過程 |

#### 3. Flex 模式使用時機

**啟用 Flex 模式的情況**：
- 處理大型數據集，需要長時間運行
- 不希望因 token 限制中斷處理
- 可以接受更高的 API 調用延遲

**關閉 Flex 模式的情況**：
- 嚴格的成本控制需求
- 需要快速響應時間
- 分批處理，希望在達到限制後停止

### 實際應用範例

#### 場景1：研究級高質量情感分析
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/research_data/critical_news.csv \
  --output /mnt/md0/finrl/gpt-5/high_quality_sentiment.csv \
  --model gpt-5 \
  --reasoning-effort high \
  --verbosity high \
  --daily-token-limit 0 \
  --allow-flex \
  --chunk-size 10 \
  --retry 8 \
  --retry-missing 5
```

#### 場景2：生產環境批量處理
```bash
python scripts/scoring/score_sentiment_openai.py \
  --input /mnt/md0/finrl/production_data/daily_news.csv \
  --output /mnt/md0/finrl/gpt-5-mini/daily_sentiment.csv \
  --model gpt-5-mini \
  --reasoning-effort medium \
  --verbosity low \
  --daily-token-limit 5000000 \
  --chunk-size 100 \
  --retry 3 \
  --retry-missing 2
```

#### 場景3：成本敏感的試驗性分析
```bash
python scripts/scoring/score_risk_openai.py \
  --input /mnt/md0/finrl/test_data/sample_news.csv \
  --output /mnt/md0/finrl/gpt-5-mini/test_risk.csv \
  --model gpt-5-mini \
  --reasoning-effort low \
  --verbosity low \
  --daily-token-limit 1000000 \
  --chunk-size 50 \
  --retry 2 \
  --retry-missing 1
```

### 注意事項

1. **模型特性**：`reasoning_effort` 和 `verbosity` 參數會顯著影響 token 消耗
2. **成本控制**：使用 `--daily-token-limit 0` 時需謹慎，可能產生意外的高額費用
3. **Flex 模式**：提供更高的可用性，但可能有更長的響應延遲
4. **參數驗證**：腳本會自動驗證模型和參數的兼容性，無效組合會報錯