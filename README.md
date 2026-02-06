# MindfulRL-Intraday: Comprehensive RL Trading System
> A comprehensive reinforcement learning trading system integrating multiple data sources, advanced news processing, and sophisticated model comparison capabilities. Built upon FinRL foundations with extensive OpenAI/Anthropic LLM integration for sentiment analysis, risk assessment, and content summarization.

## Project Overview

MindfulRL-Intraday is a comprehensive financial trading system that combines:
- **Multi-source news data processing** via `data_sources/` and `NewsExtraction/` modules
- **Advanced LLM integration** with configurable reasoning effort and verbosity parameters
- **AI Agent Interface** for natural language queries about your portfolio and market data
- **HTTP API** with RESTful endpoints for all data and analysis functions
- **Sophisticated model comparison** capabilities for analyzing different LLM outputs
- **Enterprise-grade cost control** and monitoring systems
- **Flexible RL training** pipelines with sentiment and risk enhancement

### Key Features:
1. **News Data Pipeline**: Extract and process news from 10+ sources (Finnhub, Alpha Vantage, Yahoo, etc.)
2. **LLM Scoring**: Score financial news headlines for sentiment and risk using OpenAI/Anthropic models
3. **AI Agent CLI**: Interactive natural language interface with model switching (`/model` commands)
4. **HTTP API**: RESTful API with Swagger UI for programmatic access
5. **Content Summarization**: Generate intelligent summaries with configurable parameters
6. **Advanced Model Comparison**: Compare outputs across different models with statistical analysis
7. **Dynamic Analysis Toolkit**: Interactive tools for large-scale model comparison and visualization
8. **RL Training**: Train PPO/CPPO agents on sentiment and risk-enhanced data
9. **Backtesting**: Comprehensive backtesting with performance visualization
10. **Database Integration**: Supabase PostgreSQL for centralized data storage

## Setup
1. Ensure you are in this directory (project root).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure API keys:
   ```bash
   cp config/.env.template config/.env
   # Edit config/.env with your API keys:
   # OPENAI_API_KEY, ANTHROPIC_API_KEY, POLYGON_API_KEY, etc.
   ```

---

## AI Agent CLI (New)

Interactive CLI for natural language queries about your data:

```bash
python -m src.agents
```

**Example Session:**

```
╭─────────────────────────────────────────────────────────────────╮
│  MindfulRL AI Agent                                             │
│  Model: claude-sonnet-4-5-20250929 (Anthropic)                  │
│  Type /help for commands, /quit to exit                         │
╰─────────────────────────────────────────────────────────────────╯

You: NVDA 最近的新聞情緒如何？

Agent: 我來查詢 NVDA 最近的新聞數據。

[Tool: get_ticker_news] Getting news for NVDA...
[Tool: get_news_sentiment_summary] Analyzing sentiment...

根據最近 30 天的數據分析：

**NVDA 新聞情緒摘要**
- 文章數量: 847 篇
- 平均情緒分數: 3.42 / 5.0 (略偏多)
- 看多/看空比例: 58% / 22%
- 主要來源: Dow Jones (312), Benzinga (245), The Fly (180)
```

### Slash Commands

| 命令 | 說明 | 範例 |
|------|------|------|
| `/model` | 顯示模型選擇器 | `/model` |
| `/model <name>` | 切換到指定模型 | `/model opus`, `/model gpt5` |
| `/reasoning <level>` | 調整推理強度 (OpenAI) | `/reasoning xhigh` |
| `/status` | 顯示當前狀態 | `/status` |
| `/help` | 顯示幫助 | `/help` |

**Model Picker Example:**

```
You: /model

Available Models:
╭────────────────────────────────────────────────────────────────────╮
│  #  │ Provider  │ Model          │ Aliases              │ Info    │
├─────┼───────────┼────────────────┼──────────────────────┼─────────┤
│  1  │ anthropic │ Sonnet 4.5     │ sonnet, s45          │ Fast    │
│  2  │ anthropic │ Opus 4.5       │ opus, o45            │ Smart   │
│  3  │ anthropic │ Haiku 4.5      │ haiku, h45           │ Cheap   │
│  4  │ openai    │ GPT-5.2        │ gpt5, 5.2            │ SOTA    │
╰────────────────────────────────────────────────────────────────────╯

Enter number, name, or alias: opus

✓ Switched to Opus 4.5 (anthropic)
  Note: Provider changed, conversation history cleared.
```

### Available Tools (17 functions)

| Category | Tool | Description |
|----------|------|-------------|
| **News** | `get_ticker_news` | 取得特定股票的新聞 |
| | `get_news_sentiment_summary` | 新聞情緒摘要統計 |
| | `search_news_by_keyword` | 關鍵字搜尋新聞 |
| **Prices** | `get_ticker_prices` | 取得價格數據 |
| | `get_price_change` | 計算漲跌幅 |
| | `get_sector_performance` | 板塊表現 |
| **Options** | `get_iv_analysis` | IV 分析 (IV Rank, VRP) |
| | `get_iv_history_data` | IV 歷史數據 |
| | `scan_mispricing` | 期權定價偏差掃描 |
| | `calculate_greeks` | Greeks 計算 |
| **Signals** | `detect_anomalies` | 異常檢測 |
| | `detect_event_chains` | 事件鏈檢測 |
| | `synthesize_signal` | 合成交易信號 |
| **Analysis** | `get_fundamentals_analysis` | 基本面分析 |
| | `get_sec_filings` | SEC 文件查詢 |
| | `get_watchlist_overview` | 觀察清單概覽 |
| | `get_morning_brief` | 個人化晨報 |

---

## HTTP API (New)

Start the API server:

```bash
python -m src.api
# Server: http://localhost:8420
# Swagger UI: http://localhost:8420/docs
```

**Example Requests:**

```bash
# Get news
curl "http://localhost:8420/news/NVDA?days=7"

# Get prices
curl "http://localhost:8420/prices/AMD?interval=15min&days=30"

# IV analysis
curl "http://localhost:8420/options/PLTR"

# Synthesize trading signal
curl "http://localhost:8420/signals?ticker=NVDA"

# AI Agent query
curl -X POST "http://localhost:8420/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "比較 AMD 和 NVDA 的近期表現", "provider": "anthropic"}'
```

---

## Data Collection (New)

### Daily Update (Recommended)

One-command update with optional database sync:

```bash
# Check data status
python scripts/collection/daily_update.py --status

# Update all news sources
python scripts/collection/daily_update.py --news

# Update prices + sync to DB
python scripts/collection/daily_update.py --ibkr-prices --sync-db

# Update everything + sync to DB
python scripts/collection/daily_update.py --all --sync-db
```

### Individual Collection Scripts

```bash
# Polygon news (3+ years history)
python scripts/collection/collect_polygon_news.py --incremental

# Finnhub news (last 7 days)
python scripts/collection/collect_finnhub_news.py --incremental

# IBKR news (requires TWS/Gateway)
python scripts/collection/collect_ibkr_news.py --incremental

# IBKR prices (requires TWS/Gateway)
python scripts/collection/collect_ibkr_prices.py --incremental --minute-only

# IV history
python scripts/collection/collect_iv_history.py
```

---

## Database Setup (Supabase)

### Configure Connection

Edit `config/.env`:

```bash
SUPABASE_DB_URL=postgresql://postgres:your-password@db.xxx.supabase.co:5432/postgres
```

### Migrate Data to DB

```bash
# Import all data
python scripts/migrate_to_supabase.py

# Import prices only
python scripts/migrate_to_supabase.py --prices

# Import news only
python scripts/migrate_to_supabase.py --news

# Dry run (count only)
python scripts/migrate_to_supabase.py --dry-run
```

---

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
  python scripts/scoring/score_sentiment_openai.py \
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
  python scripts/scoring/score_sentiment_openai.py \
    --input data.csv \
    --output sentiment_o3_minimal.csv \
    --model gpt-5 \
    --reasoning-effort minimal \
    --verbosity high

  # Flex mode: after daily token limit, switch to flex service_tier with longer timeout and retry
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
  * The script will auto-create the output directory if needed.
  * The output CSV will include all original columns from the input plus a new column `sentiment_{model}` (e.g., `sentiment_gpt_5`, `sentiment_o4_mini`).
  * Runs in chunks and writes each chunk immediately, so you can interrupt (Ctrl+C) and re-run to resume.
  * 当触发每日 token 限额时，会在当前 chunk 写入完成后自动退出，以便第二天继续执行并重用剩余行。
#### Risk (resumable, chunked):
  ```bash
  python scripts/scoring/score_risk_openai.py \
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
python scripts/scoring/openai_summary.py \
  --input data.csv \
  --output summarized.csv \
  --model o4-mini \
  --reasoning-effort medium \
  --text-column Article \
  --summary-column o4_summary

# gpt-5 with custom verbosity
python scripts/scoring/openai_summary.py \
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

### New: Passive Query Layer (`src/`)
- **`src/api/`**: HTTP API (FastAPI)
  - `app.py`: Application factory
  - `routes/`: API endpoints (news, prices, options, signals, query)
  - `dependencies.py`: Dependency injection (DAL singleton)
- **`src/agents/`**: AI Agent implementations
  - `cli.py`: Interactive CLI with `/model` commands
  - `config.py`: Model configuration
  - `openai_agent/`: OpenAI Agents SDK integration
  - `anthropic_agent/`: Anthropic SDK integration
- **`src/tools/`**: Data Access Layer
  - `data_access.py`: DataAccessLayer class
  - `schemas.py`: Pydantic models (shared across layers)
  - `registry.py`: Tool registry for agent frameworks
  - `backends/`: File and database backends
  - `*_tools.py`: 17 tool functions (news, prices, options, signals, analysis)
- **`src/signals/`**: Signal detection modules
  - `anomaly_detector.py`, `event_chain_detector.py`, `signal_synthesizer.py`

### Core Modules
- **`data_sources/`**: Unified data source interface
  - **Finnhub**: News, real-time quotes, company profiles (free tier: 60 calls/min)
  - **Tiingo**: Historical stock prices (free tier: 30+ years EOD data)
  - **SEC EDGAR**: Official SEC filings, XBRL financial data (free, no API key)
- **`NewsExtraction/`**: Historical news data processing and quality analysis

### Data Collection (`scripts/collection/`)
- **`daily_update.py`**: Unified daily update with `--sync-db` option
- **`collect_polygon_news.py`**: Polygon news (3+ years history)
- **`collect_finnhub_news.py`**: Finnhub news (7 days)
- **`collect_ibkr_news.py`**: IBKR news (Dow Jones, Briefing, The Fly)
- **`collect_ibkr_prices.py`**: IBKR intraday prices
- **`collect_iv_history.py`**: ATM IV history

### Scoring Scripts (`scripts/scoring/`)
- **`score_sentiment_openai.py`**: Sentiment analysis with configurable reasoning effort
- **`score_risk_openai.py`**: Risk assessment with advanced parameter control
- **`score_ibkr_news.py`**: IBKR parquet scoring with API key rotation
- **`openai_summary.py`**: Article summarization (generates input for scoring)

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
- **`config/user_profile.yaml`**: Personal settings (watchlists, strategy weights, alerts)
- **`config/sectors.yaml`**: Sector definitions and ticker mappings

### User Profile Example (`config/user_profile.yaml`)
```yaml
watchlists:
  core_holdings:
    tickers: ["NVDA", "AMD", "ZETA"]
    priority: "high"
  interested:
    tickers: ["RKLB", "PLTR", "COIN", "PYPL"]
    priority: "medium"

tickers_for_options: ["NVDA", "AMD", "PLTR", "PYPL", "ZETA", "RKLB", "COIN"]

strategy_weights:
  my_custom:
    fundamentals: 25
    price_trend: 25
    news_sentiment: 25
    options_flow: 25
  default_strategy: "my_custom"
```

## Documentation

### Design Documents
- **`docs/design/MINDFULRL_ARCHITECTURE.md`**: System architecture design
- **`docs/design/SERVICE_ARCHITECTURE.md`**: Service-oriented architecture plan
- **`docs/design/DATA_STORAGE_ACCESS.md`**: Data access layer design

### Data Guides
- **`docs/data/DATA_SUBSCRIPTION_GUIDE.md`**: Data subscription guide
- **`docs/data/OPTIONS_FLOW_GUIDE.md`**: Options flow analysis guide
- **`docs/data/OPTIONS_PRICING_THEORY.md`**: Options pricing theory
- **`docs/analysis/SCORING_VALIDATION_METHODOLOGY.md`**: LLM scoring validation methodology

### Module Documentation
- **`PROJECT_STRUCTURE.md`**: Detailed project structure and directory organization
- **`OPENAI_SCRIPTS.md`**: OpenAI scoring scripts usage guide
- **`data_sources/`**: Unified data source module documentation
- **`NewsExtraction/README.md`**: Historical news processing documentation
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

---

## Development

### Run Tests

```bash
# All tests (98 tests)
pytest tests/

# Specific test files
pytest tests/test_data_access.py -v  # DAL tests
pytest tests/test_tools.py -v        # Tool function tests
pytest tests/test_api.py -v          # API endpoint tests
pytest tests/test_agents.py -v       # Agent integration tests

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Start Development Server

```bash
# API with auto-reload
uvicorn src.api.app:create_app --factory --reload --port 8420
```

---

## License

MIT License - see LICENSE file for details.