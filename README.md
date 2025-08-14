# MindfulRL-Intraday: Comprehensive RL Trading System
> A comprehensive reinforcement learning trading system integrating multiple data sources, advanced news processing, and sophisticated model comparison capabilities. Built upon FinRL foundations with extensive OpenAI LLM integration for sentiment analysis, risk assessment, and content summarization.

## Project Overview

MindfulRL-Intraday is a comprehensive financial trading system that combines:
- **Multi-source news data processing** via the `finrl_deepseek_news_extension/` and `NewsExtraction/` modules
- **Advanced LLM integration** with configurable reasoning effort and verbosity parameters
- **Sophisticated model comparison** capabilities for analyzing different LLM outputs
- **Enterprise-grade cost control** and monitoring systems
- **Flexible RL training** pipelines with sentiment and risk enhancement

### Key Features:
1. **News Data Pipeline**: Extract and process news from 10+ sources (Finnhub, Alpha Vantage, Yahoo, etc.)
2. **LLM Scoring**: Score financial news headlines for sentiment and risk using OpenAI models
3. **Content Summarization**: Generate intelligent summaries with configurable parameters
4. **Model Comparison**: Compare outputs across different models with statistical analysis
5. **RL Training**: Train PPO/CPPO agents on sentiment and risk-enhanced data
6. **Backtesting**: Comprehensive backtesting with performance visualization

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

#### Advanced Parameter Configuration

All scoring scripts now support advanced reasoning model parameters:

- `--reasoning-effort`: Reasoning effort level ("low", "medium", "high"; gpt-5 also supports "minimal")
- `--verbosity`: Verbosity level for gpt-5 models only ("low", "medium", "high")
- `--symbol-column`: Stock symbol column name (default: `Stock_symbol`)
- `--text-column`: Text/summary column to score (choices: `Article_title`, `Article`, `Lsa_summary`, `Luhn_summary`, `Textrank_summary`, `Lexrank_summary`, `o3_summary`)

#### Sentiment Scoring (resumable, chunked):
  ```bash
  python score_sentiment_openai.py \
    --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
    --output sentiment_scored.csv \
    --model o4-mini \
    --reasoning-effort high \
    --verbosity low \
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

  # Example with gpt-5 using minimal reasoning effort:
  python score_sentiment_openai.py \
    --input data.csv \
    --output sentiment_o3_minimal.csv \
    --model gpt-5 \
    --reasoning-effort minimal \
    --verbosity high

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
  * The script will auto-create the output directory if needed.
  * The output CSV will include all original columns from the input plus a new column 'sentiment_deepseek'.
  * Runs in chunks and writes each chunk immediately, so you can interrupt (Ctrl+C) and re-run to resume.
  * 当触发每日 token 限额时，会在当前 chunk 写入完成后自动退出，以便第二天继续执行并重用剩余行。
#### Risk (resumable, chunked):
  ```bash
  python score_risk_openai.py \
    --input /mnt/md0/finrl/huggingface_datasets/FNSPID_raw_news/Stock_news/nasdaq_exteral_data.csv \
    --output risk_scored.csv \
    --model o4-mini \
    --reasoning-effort high \
    --verbosity low \
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
* The script will auto-create the output directory if needed.
* The output CSV will include all original columns from the input plus a new column 'risk_deepseek'.
* Runs in chunks and writes each chunk immediately, so you can interrupt (Ctrl+C) and re-run to resume.

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

### 2. Content Summarization
```bash
# Generate article summaries with configurable parameters
python openai_summary.py \
  --input data.csv \
  --output summarized.csv \
  --model o4-mini \
  --reasoning-effort medium \
  --text-column Article \
  --summary-column o4_summary

# gpt-5 with custom verbosity
python openai_summary.py \
  --input data.csv \
  --output summarized.csv \
  --model gpt-5 \
  --reasoning-effort high \
  --verbosity medium
```

### 3. Model Comparison and Analysis
```bash
# Compare scores across multiple CSV files from different models
python compare_scores.py \
  --files sentiment_o3_high.csv,sentiment_o4_mini.csv,sentiment_gpt4o.csv \
  --column sentiment_deepseek \
  --display-count 10

# Compare risk scores with full display
python compare_scores.py \
  --files risk_o3_low.csv,risk_o3_medium.csv,risk_o3_high.csv \
  --column risk_deepseek \
  --display-count all
```

### 4. Prepare Dataset
```bash
python prepare_dataset_openai.py \
  --price-data data/intraday.csv \
  --sentiment sentiment_scored.csv \
  --risk risk_scored.csv \
  --date-col Date \
  --symbol-col Stock_symbol \
  --output merged_dataset.csv
```

### 5. Train Agents
```bash
bash train_openai.sh merged_dataset.csv ppo sentiment
bash train_openai.sh merged_dataset.csv cppo risk
```

### 6. Backtest
```bash
python backtest_openai.py --data merged_dataset.csv \
  --model trained_models/agent_ppo_llm_100_epochs_sentiment.pth \
  --env sentiment --output-plot equity.png
```

## Project Structure

### Core Modules
- **`finrl_deepseek_news_extension/`**: Advanced news data extraction and processing system
- **`NewsExtraction/`**: Specialized news content extraction and preprocessing

### Scoring Scripts
- **`score_sentiment_openai.py`**: Sentiment analysis with configurable reasoning effort
- **`score_risk_openai.py`**: Risk assessment with advanced parameter control
- **`openai_summary.py`**: Article summarization with verbosity control

### Analysis and Comparison
- **`compare_scores.py`**: Advanced statistical comparison of model outputs
  - Supports reasoning effort file naming (e.g., `o3_high`, `o3_medium`, `o3_low`)
  - Multiple similarity metrics: Pearson correlation, Spearman correlation, Cohen's Kappa
  - Configurable display options for rankings

### Utility Scripts
- **`compare_sentiment.py`**: Compare sentiment columns between CSVs
- **`filter_fns_data_by_date.py`**: Filter news data by date ranges
- **`audit_stock_news.py`**: Data quality auditing and validation

### Training and Backtesting
- **`prepare_dataset_openai.py`**: Feature merging and dataset preparation
- **`train_openai.sh`**: Training pipeline wrapper
- **`backtest_openai.py`**: Backtesting with performance visualization
- **`train_ppo_llm.py`, `train_cppo_llm_risk.py`**: Core training implementations
- **`env_stocktrading_llm.py`, `env_stocktrading_llm_risk.py`**: Trading environment definitions

