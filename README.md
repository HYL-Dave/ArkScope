# OpenAI-Enhanced RL Trading Toolkit
> Derived from the FinRL open-source project. Goal: Extends the original with OpenAI LLM integration (sentiment & risk), intraday support, and streamlined scripts. Future extensions and improvements are planned.

## Background & Upstream Roadmap

The upstream FINRL project has recently consolidated the DeepSeek workflow into its core repository and published a comprehensive Developer Roadmap outlining planned enhancements and best practices. This toolkit will draws from those official updates—leveraging FINRL's unified data pipelines and environment abstractions—while adding OpenAI-powered sentiment and risk scoring and exploring additional feature improvements inspired by the roadmap.

This folder contains a self-contained toolkit to:
1. Score financial news headlines for sentiment and risk using OpenAI LLMs.
2. Prepare merged datasets for RL training.
3. Train PPO/CPPO agents on sentiment and risk-enhanced data.
4. Backtest trained agents.

## Setup
1. Ensure you are in this directory (project root).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your_api_key"
   ```

## Workflow

### 1. Score News Headlines

#### 可选列说明 / Column options

- `--symbol-column` : 输入 CSV 中存放股票代号的列，例如 `Stock_symbol`（默认 `Stock_symbol`）。
- `--text-column`   : 输入 CSV 中存放要打分的新闻文本／摘要的列，可选 `Article_title`、`Article`、`Lsa_summary`、`Luhn_summary`、`Textrank_summary`、`Lexrank_summary`（默认 `Article_title`）。
- Sentiment (resumable, chunked):
  ```bash
  python score_sentiment_openai.py \
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
    --verbose

  # Flex mode: after daily token limit, switch to flex service_tier with longer timeout and retry
  python score_sentiment_openai.py \
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
  # The script will auto-create the output directory if needed.
  # The output CSV will include all original columns from the input plus a new column 'sentiment_deepseek'.
  # Runs in chunks and writes each chunk immediately, so you can interrupt (Ctrl+C) and re-run to resume.
  # 当触发每日 token 限额时，会在当前 chunk 写入完成后自动退出，以便第二天继续执行并重用剩余行。
- Risk (resumable, chunked):
  ```bash
  python score_risk_openai.py \
    --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
    --output risk_scored.csv \
    --model o4-mini \
    --chunk-size 5000 \
    --symbol-column Stock_symbol \
    --text-column Lsa_summary \
    --date-column Date \
    --api-keys-file api_keys_tier5.txt \
    --daily-token-limit 250000 \
    --verbose

  # Flex mode: after daily token limit, switch to flex service_tier with longer timeout and retry
  python score_risk_openai.py \
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
  # The script will auto-create the output directory if needed.
  # The output CSV will include all original columns from the input plus a new column 'risk_deepseek'.
  # Runs in chunks and writes each chunk immediately, so you can interrupt (Ctrl+C) and re-run to resume.

### 2. Prepare Dataset
```bash
python prepare_dataset_openai.py \
  --price-data data/intraday.csv \
  --sentiment sentiment_scored.csv \
  --risk risk_scored.csv \
  --date-col Date \
  --symbol-col Stock_symbol \
  --output merged_dataset.csv
```

### 3. Train Agents
```bash
bash train_openai.sh merged_dataset.csv ppo sentiment
bash train_openai.sh merged_dataset.csv cppo risk
```

### 4. Backtest
```bash
python backtest_openai.py --data merged_dataset.csv \
  --model trained_models/agent_ppo_llm_100_epochs_sentiment.pth \
  --env sentiment --output-plot equity.png
```

## Project Structure
- `score_*.py`: headline scoring.
- `prepare_dataset_openai.py`: merges features & signals.
- `train_openai.sh`: wrapper to train agents.
- `backtest_openai.py`: runs backtest and plots.
- `train_ppo_llm.py`, `train_cppo_llm_risk.py`: core training scripts.
- `env_stocktrading_llm.py`, `env_stocktrading_llm_risk.py`: environment definitions.
- `requirements.txt`: Python dependencies.
`openai_summary.py`: summarize the Article text into a new `<model>_summary` column using OpenAI (skips empty articles). Output CSV also includes per-row `prompt_tokens` and `completion_tokens`.
`compare_sentiment.py`: compare sentiment score columns between two CSVs and dump differing rows to a new CSV for analysis.
`filter_fns_data_by_date.py`: filter FNSPID raw news CSV by a start date, e.g., extract records on/after 2022-11-01.