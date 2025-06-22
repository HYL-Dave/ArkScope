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

Path: `score_sentiment_openai.py`

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
python score_sentiment_openai.py \
  --input data/headlines.csv \
  --output data/sentiment_scored.csv \
  --model o4-mini
```

### Output
- CSV with original columns plus `sentiment_score` (integer 1–5)

## Script: score_risk_openai.py

Path: `score_risk_openai.py`

### Description
Scores each news headline for downside risk using an OpenAI LLM.

### Input CSV Format
Same as sentiment script.

### Usage
```bash
python score_risk_openai.py \
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
   python score_sentiment_openai.py \
     --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
     --output sentiment_scored.csv \
     --model o4-mini \
     --chunk-size 5000 \
     --symbol-column Stock_symbol \
     --text-column Lsa_summary \
     --date-column Date
   ```
2. Score risk:
   ```bash
   python score_risk_openai.py \
     --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
     --output risk_scored.csv \
     --model o4-mini \
     --chunk-size 5000 \
     --symbol-column Stock_symbol \
     --text-column Lsa_summary \
     --date-column Date
   ```
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
python score_sentiment_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output sentiment_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys.txt \
  --daily-token-limit 1000000
```

#### 参数说明

| 参数                 | 默认值     | 说明                                                                 |
|----------------------|-----------|----------------------------------------------------------------------|
| `--input`            | 必填       | 输入 CSV 文件路径，必须包含 symbol, headline（或通过 --symbol-column/--text-column 指定）|
| `--output`           | 必填       | 输出 CSV 文件路径，会添加 `sentiment_deepseek` 列                      |
| `--model`            | o4-mini   | OpenAI 模型名称（如 o4-mini, gpt-4.1, o3 等）                          |
| `--symbol-column`    | symbol    | 输入 CSV 中股票代码列名                                                |
| `--text-column`      | headline  | 输入 CSV 中文本列名                                                    |
| `--date-column`      | None      | 输入 CSV 中日期列名，用于保留日期用于后续合并                          |
| `--chunk-size`       | 1000      | 分块大小，用于断点续跑                                                 |
| `--api-key`          | None      | 单个 OpenAI API Key，如未指定则使用环境变量 `OPENAI_API_KEY`            |
| `--api-keys-file`    | None      | API Key 文件路径，文件内每行一个 key，达到限额时自动轮转                |
| `--daily-token-limit`| None      | 单个 Key token 限额（近似值），达到后自动轮转                          |

### score_risk_openai.py
Score financial news headlines for downside risk using OpenAI, with resumable chunked processing.


Usage:
```bash
python score_risk_openai.py \
  --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
  --output risk_scored.csv \
  --model o4-mini \
  --chunk-size 5000 \
  --symbol-column Stock_symbol \
  --text-column Lsa_summary \
  --date-column Date \
  --api-keys-file api_keys.txt \
  --daily-token-limit 250000
```

#### 参数说明

| 参数                 | 默认值     | 说明                                                                 |
|----------------------|-----------|----------------------------------------------------------------------|
| `--input`            | 必填       | 输入 CSV 文件路径，必须包含 symbol, headline（或通过 --symbol-column/--text-column 指定）|
| `--output`           | 必填       | 输出 CSV 文件路径，会添加 `risk_deepseek` 列                          |
| `--model`            | o4-mini   | OpenAI 模型名称（如 o4-mini, gpt-4.1, o3 等）                          |
| `--symbol-column`    | symbol    | 输入 CSV 中股票代码列名                                                |
| `--text-column`      | headline  | 输入 CSV 中文本列名                                                    |
| `--date-column`      | None      | 输入 CSV 中日期列名，用于保留日期用于后续合并                          |
| `--chunk-size`       | 1000      | 分块大小，用于断点续跑                                                 |
| `--api-key`          | None      | 单个 OpenAI API Key，如未指定则使用环境变量 `OPENAI_API_KEY`            |
| `--api-keys-file`    | None      | API Key 文件路径，文件内每行一个 key，达到限额时自动轮转                |
| `--daily-token-limit`| None      | 单个 Key token 限额（近似值），达到后自动轮转                          |

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