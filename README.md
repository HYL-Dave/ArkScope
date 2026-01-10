# MindfulRL-Intraday: Comprehensive RL Trading System
> A comprehensive reinforcement learning trading system integrating multiple data sources, advanced news processing, and sophisticated model comparison capabilities. Built upon FinRL foundations with extensive OpenAI LLM integration for sentiment analysis, risk assessment, and content summarization.

## Project Overview

MindfulRL-Intraday is a comprehensive financial trading system that combines:
- **Multi-source news data processing** via `data_sources/` and `NewsExtraction/` modules
- **Advanced LLM integration** with configurable reasoning effort and verbosity parameters
- **Sophisticated model comparison** capabilities for analyzing different LLM outputs
- **Enterprise-grade cost control** and monitoring systems
- **Flexible RL training** pipelines with sentiment and risk enhancement

### Key Features:
1. **News Data Pipeline**: Extract and process news from 10+ sources (Finnhub, Alpha Vantage, Yahoo, etc.)
2. **LLM Scoring**: Score financial news headlines for sentiment and risk using OpenAI models
3. **Content Summarization**: Generate intelligent summaries with configurable parameters
4. **Advanced Model Comparison**: Compare outputs across different models with statistical analysis
5. **Dynamic Analysis Toolkit**: Interactive tools for large-scale model comparison and visualization
6. **RL Training**: Train PPO/CPPO agents on sentiment and risk-enhanced data
7. **Backtesting**: Comprehensive backtesting with performance visualization

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

#### Recommended Models

**Current Strategy:** Use latest reasoning models only, continuously upgrade as new versions release.

| Model | Usage | Best For |
|-------|-------|----------|
| **gpt-5.1** | Latest | All tasks (when available) |
| **gpt-5** | Primary | Sentiment/risk scoring |
| **gpt-5-mini** | Primary | Summary generation (cost-effective) |

> **Note:** Non-reasoning models (gpt-4.1-mini, etc.) and o-series (o3, o4-mini) are deprecated. Historical data retained for comparison only.
>
> **Upgrade Path:** gpt-5 → gpt-5.1 → gpt-5.2 (upcoming) → ...

**Typical Workflow:**
1. Generate summaries with **gpt-5-mini** (cost-effective, quality sufficient for summarization)
2. Score sentiment/risk with **gpt-5** (higher quality for scoring tasks)
3. Use `--reasoning-effort high --verbosity high` for best quality

**Model Parameters:**
- `--reasoning-effort`: "minimal", "low", "medium", "high"
- `--verbosity`: "low", "medium", "high" (gpt-5 family)
- `--allow-flex`: Enable Flex mode for 50% cost savings (longer wait times)

#### Advanced Parameter Configuration

All scoring scripts now support advanced reasoning model parameters:

- `--reasoning-effort`: Reasoning effort level ("low", "medium", "high"; gpt-5 also supports "minimal")
- `--verbosity`: Verbosity level for gpt-5 models only ("low", "medium", "high")
- `--symbol-column`: Stock symbol column name (default: `Stock_symbol`)
- `--text-column`: Text/summary column to score (choices: `Article_title`, `Article`, `Lsa_summary`, `Luhn_summary`, `Textrank_summary`, `Lexrank_summary`, `o3_summary`, `gpt_5_summary`)

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
  * The output CSV will include all original columns from the input plus a new column `sentiment_{model}` (e.g., `sentiment_gpt_5`, `sentiment_o4_mini`).
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
* The output CSV will include all original columns from the input plus a new column `risk_{model}` (e.g., `risk_gpt_5`, `risk_o4_mini`).
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

#### Score Comparison
```bash
# Compare scores across multiple CSV files from different models
python scripts/comparison/compare_scores.py \
  --files sentiment_o3_high.csv,sentiment_o4_mini.csv,sentiment_gpt4o.csv \
  --column sentiment_gpt_5 \
  --display-count 10

# Enhanced comparison with automatic directory scanning
python scripts/comparison/compare_scores_enhanced.py \
  --root-dir /mnt/md0/finrl \
  --score-type sentiment \
  --output sentiment_comparison.csv

# A/B score comparison between two models
python scripts/comparison/ab_score_comparison.py \
  --file-a model_a_scores.csv \
  --file-b model_b_scores.csv \
  --column sentiment_gpt_5
```

#### Summary Comparison
```bash
# Compare text summaries across models
python scripts/comparison/compare_summaries.py \
  --files summaries_o3.csv,summaries_gpt5.csv \
  --column gpt_5_summary
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
- **`data_sources/`**: Unified data source interface
  - **Finnhub**: News, real-time quotes, company profiles (free tier: 60 calls/min)
  - **Tiingo**: Historical stock prices (free tier: 30+ years EOD data)
  - **SEC EDGAR**: Official SEC filings, XBRL financial data (free, no API key)
- **`NewsExtraction/`**: Historical news data processing and quality analysis

### Scoring Scripts
- **`score_sentiment_openai.py`**: Sentiment analysis with configurable reasoning effort
- **`score_risk_openai.py`**: Risk assessment with advanced parameter control
- **`openai_summary.py`**: Article summarization with verbosity control

### Analysis and Comparison (`scripts/comparison/`, `scripts/analysis/`)
- **`scripts/comparison/compare_scores.py`**: Statistical comparison across multiple score files
- **`scripts/comparison/compare_scores_enhanced.py`**: Enhanced comparison with auto-scanning and caching
- **`scripts/comparison/compare_summaries.py`**: Text similarity analysis for summary comparison
- **`scripts/comparison/ab_score_comparison.py`**: A/B score comparison between two models
- **`scripts/analysis/sentiment_backtest.py`**: Sentiment-based trading strategy backtest
- **`scripts/analysis/validate_scoring_value.py`**: Validate LLM score predictive power (IC, Hit Rate)
- **`scripts/analysis/detailed_factor_comparison.py`**: Factor comparison with distribution analysis

### Visualization (`scripts/visualization/`)
- **`scripts/visualization/news_dashboard.py`**: Streamlit news dashboard (Polygon, Finnhub, IBKR)
- **`scripts/visualization/fundamentals_query.py`**: CLI for querying stock fundamentals

### Utility Scripts
- **`filter_fns_data_by_date.py`**: Filter news data by date ranges
- **`audit_stock_news.py`**: Data quality auditing and validation

### Training and Backtesting
- **`prepare_dataset_openai.py`**: Feature merging and dataset preparation
- **`train_openai.sh`**: Training pipeline wrapper
- **`backtest_openai.py`**: Backtesting with performance visualization
- **`train_ppo_llm.py`, `train_cppo_llm_risk.py`**: Core training implementations
- **`env_stocktrading_llm.py`, `env_stocktrading_llm_risk.py`**: Trading environment definitions

### Configuration
- **`config/tickers_core.json`**: Core stock ticker list (tiered: Tier 1 must-have, Tier 2 expanded, Tier 3 custom)
- **`config/.env.template`**: API credentials template (copy to `.env` and fill in your keys)

## Documentation
- **`PROJECT_STRUCTURE.md`**: Detailed project structure and directory organization
- **`OPENAI_SCRIPTS.md`**: OpenAI scoring scripts usage guide
- **`data_sources/`**: Unified data source module documentation
- **`NewsExtraction/README.md`**: Historical news processing documentation
- **`docs/analysis/SCORING_VALIDATION_METHODOLOGY.md`**: LLM scoring validation methodology
- **`scripts/visualization/README.md`**: Visualization tools guide
- **`scripts/scoring/README.md`**: Batch scoring scripts guide

## Advanced Features

### Score Validation and Backtesting
Validate LLM scoring effectiveness with quantitative finance methods:

```bash
# Validate score predictive power (IC, Hit Rate, Quintile Analysis)
python scripts/analysis/validate_scoring_value.py \
  --file scored_data.csv \
  --score-col sentiment_gpt_5

# Backtest sentiment-based trading strategies
python scripts/analysis/sentiment_backtest.py \
  --file scored_data.csv \
  --score-col sentiment_gpt_5
```

### News Dashboard
Interactive Streamlit dashboard for exploring news data:

```bash
streamlit run scripts/visualization/news_dashboard.py
```

### Fundamentals Query CLI
Interactive command-line tool for stock fundamentals:

```bash
python scripts/visualization/fundamentals_query.py

# Example commands:
> AAPL                    # Query single stock
> AAPL MSFT GOOGL         # Compare multiple stocks
> top roe                 # ROE ranking (high→low)
> pe<20 roe>15            # Filter by conditions
```