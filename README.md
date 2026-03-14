# MindfulRL-Intraday

> Reinforcement learning trading system with dual-provider AI agents (Anthropic + OpenAI), 47 financial tools, Discord bot, and multi-source news/price/options data pipeline.

## Overview

MindfulRL-Intraday combines RL-based trading strategies with LLM-powered analysis:

- **Dual AI Agent CLI** — Anthropic (Claude Opus 4.6) + OpenAI (GPT-5.2) with 47 tools, 4 skills, 4 subagents
- **Discord Bot** — Slash commands, interactive buttons, free-chat analysis, model selection
- **HTTP API** — 24 RESTful endpoints (FastAPI + Swagger UI)
- **News Pipeline** — Multi-source collection (Polygon, Finnhub, IBKR) with LLM scoring
- **Analysis Toolkit** — Fundamentals (SEC EDGAR + Financial Datasets), options (IV/Greeks/chain), signals, web search
- **RL Pipeline** — PPO/CPPO agents with sentiment/risk-enhanced data, model registry, 3 agent tools
- **Monitor System** — Watchlist alerts (price, sentiment, signal, sector) with Discord notifications
- **Self-hosted PostgreSQL** — pgvector-enabled, Docker deployment, 7 migrations

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp config/.env.template config/.env
# Edit config/.env: OPENAI_API_KEY, ANTHROPIC_API_KEY, POLYGON_API_KEY, etc.

# 3. Start database
docker compose up -d

# 4. Launch AI Agent CLI
python -m src.agents

# 5. (Optional) Start HTTP API
python -m src.api

# 6. (Optional) Start Discord bot
python scripts/monitor_service.py --discord
```

---

## AI Agent CLI

```bash
python -m src.agents                                    # Default: Anthropic Opus 4.6
python -m src.agents --provider openai                  # Use GPT-5.2
python -m src.agents --model sonnet                     # Use Sonnet 4.6
python -m src.agents --thinking                         # Enable extended thinking
python -m src.agents --effort medium                    # Anthropic effort level
python -m src.agents --provider openai --reasoning xhigh  # GPT-5.2 max reasoning
```

### Available Models

| # | Provider | Model | Aliases | Context | Output | Features |
|---|----------|-------|---------|---------|--------|----------|
| 1 | Anthropic | Claude Opus 4.6 | opus, o46 | 200K (1M beta) | 128K | Effort, thinking, compaction |
| 2 | Anthropic | Claude Sonnet 4.6 | sonnet, s46 | 200K (1M beta) | 64K | Effort, thinking |
| 3 | OpenAI | GPT-5.2 | gpt5, 5.2 | 400K | 128K | Reasoning effort |
| 4 | OpenAI | GPT-5.2 Codex | codex, 5.2-codex | 400K | 128K | Agentic coding |

### Slash Commands (21)

| Command | Alias | Description |
|---------|-------|-------------|
| `/model [name]` | `/m` | Show model picker / switch model |
| `/code-model [name]` | `/cm` | Set code generation model |
| `/code-backend [name]` | `/cb` | Set code generation backend (api/codex/claude) |
| `/reasoning <level>` | `/r` | Set OpenAI reasoning (none/minimal/low/medium/high/xhigh) |
| `/effort <level>` | `/e` | Set Anthropic effort (max/high/medium/low) |
| `/thinking` | `/t` | Toggle extended thinking (Anthropic) |
| `/context` | `/ctx` | Toggle 1M context beta (Anthropic) |
| `/compaction` | `/cmp` | Toggle server-side compaction (Opus 4.6) |
| `/skill <name> [args]` | `/sk` | Run a skill workflow (e.g. `/sk fa NVDA`) |
| `/subagent [name] [model]` | `/sa` | View/change subagent models |
| `/scratchpad` | `/pad` | List recent scratchpad sessions |
| `/history [N]` | `/h` | Show current session Q&A history |
| `/turns <n>` | | Set max tool calls per query |
| `/attach <path> [pages]` | `/at` | Attach PDF/image/text to next query |
| `/save [N\|N-M] ["title"]` | `/sv` | Save session exchanges as report |
| `/reports [ticker]` | `/rp` | List/view saved research reports |
| `/memory [save\|search\|delete]` | `/mem` | Episodic memory (cross-session knowledge) |
| `/alpha-picks [symbol\|refresh]` | `/ap` | Seeking Alpha Alpha Picks portfolio & detail |
| `/monitor` | `/mon` | Scan watchlist for alerts |
| `/status` | `/s` | Show session config |
| `/help` | | Show all commands |

### Tools (47)

| Category | Tool | Description |
|----------|------|-------------|
| **News** | `get_ticker_news` | Recent articles for a ticker |
| | `get_news_sentiment_summary` | Aggregated sentiment statistics |
| | `search_news_by_keyword` | Keyword search across news |
| | `get_news_brief` | Lightweight news stats per ticker (scout phase) |
| | `search_news_advanced` | Multi-filter full-text search with DB-level FTS |
| **Prices** | `get_ticker_prices` | OHLCV bars (15min/1h/1d) |
| | `get_price_change` | Price change %, high/low range |
| | `get_sector_performance` | Sector-level average performance |
| **Options** | `get_iv_analysis` | IV rank, percentile, VRP, signal |
| | `get_iv_history_data` | Raw IV/HV history points |
| | `scan_mispricing` | Options mispricing vs theoretical |
| | `calculate_greeks` | BS2002 American option Greeks |
| | `get_option_chain` | Live option chain (IBKR), P/C ratio, max pain, IV term structure |
| | `get_iv_skew_analysis` | IV skew shape, 25d skew, gradient, term structure |
| **Signals** | `detect_anomalies` | Sentiment/volume anomaly detection |
| | `detect_event_chains` | Event sequence patterns |
| | `synthesize_signal` | Multi-factor trading signal |
| **Analysis** | `get_fundamentals_analysis` | Fundamentals with 3-tier fallback (IBKR → SEC EDGAR → Financial Datasets) |
| | `get_detailed_financials` | EV/EBITDA, ROIC, tech metrics (SEC cached + IBKR real-time) |
| | `get_sec_filings` | 10-K, 10-Q, 8-K metadata |
| | `get_insider_trades` | SEC Form 4 insider transactions |
| | `get_analyst_consensus` | Analyst recommendations, price targets |
| | `get_peer_comparison` | Cross-ticker valuation & growth ranking |
| | `get_earnings_impact` | Historical earnings-day moves, drift, surprise correlation |
| | `get_watchlist_overview` | Watchlist status overview |
| | `get_morning_brief` | Personalized morning briefing |
| | `check_data_freshness` | Health & staleness check for all data sources |
| **Portfolio** | `get_portfolio_analysis` | P&L, beta vs SPY, correlation matrix, HHI |
| | `get_sa_alpha_picks` | Seeking Alpha Alpha Picks portfolio (cached, auto-refresh) |
| | `get_sa_pick_detail` | Alpha Picks detail report for a specific pick |
| | `refresh_sa_alpha_picks` | Force refresh from SA website + sync tickers |
| **Reports** | `save_report` | Save research report (Markdown + DB) |
| | `list_reports` | List reports by ticker/type |
| | `get_report` | Retrieve report by ID |
| **Memory** | `save_memory` | Store analysis/insight for cross-session recall |
| | `recall_memories` | Search memories by keyword (full-text) |
| | `list_memories` | List recent memories by category |
| | `delete_memory` | Remove a memory entry |
| **Web** | `tavily_search` | AI-powered web search |
| | `tavily_fetch` | URL content extraction |
| | `web_browse` | Headless browser (Playwright) |
| | `codex_web_research` | Deep research via Codex CLI (OAuth, --search) |
| **Code** | `execute_python_analysis` | Python code execution with auto code gen |
| **Monitor** | `scan_alerts` | Scan watchlist for price/sentiment/signal/sector alerts |
| **RL Models** | `get_rl_model_status` | List trained PPO/CPPO models with backtest metrics |
| | `get_rl_prediction` | Model availability check (live inference pending Phase 2) |
| | `get_rl_backtest_report` | Detailed backtest report (Sharpe, Sortino, Calmar, CVaR) |

### Skills

Goal-oriented prompt templates that orchestrate multi-tool analysis:

| Skill | Aliases | Usage | Description |
|-------|---------|-------|-------------|
| `full_analysis` | fa, analyze | `/sk fa NVDA` | Comprehensive entry analysis with adversarial check |
| `portfolio_scan` | scan, ps | `/sk scan` | Watchlist screening with drill-down on movers |
| `earnings_prep` | ep, earnings | `/sk ep TSLA` | Pre-earnings risk/reward assessment |
| `sector_rotation` | sr, sectors | `/sk sr` | Cross-sector relative strength analysis |

Custom skills can be added via YAML files in `config/skills/`.

### Subagents

Specialized agents delegated for specific tasks:

| Subagent | Default Model | Purpose |
|----------|---------------|---------|
| `code_analyst` | GPT-5.2 Codex | Quantitative Python analysis, calculations |
| `deep_researcher` | GPT-5.2 | Multi-source investigation across 14 tools |
| `data_summarizer` | Sonnet 4.6 | Fast data retrieval and summarization |
| `reviewer` | Opus 4.6 | Critical analysis review (adversarial) |

---

## Discord Bot

Interactive Discord gateway for trading analysis and alerts.

```bash
python scripts/monitor_service.py --discord
```

### Features

- **8 Slash Commands** — `/analyze`, `/watchlist`, `/price`, `/news`, `/options`, `/fundamentals`, `/model`, `/status`
- **Interactive Buttons** — Quick drill-down on analysis results
- **Free Chat** — `@mention` or dedicated `#agent-channel` for natural language queries
- **Model Selection** — `/model`, `/effort`, `/reasoning` with per-session state
- **Alert Routing** — Severity-based color-coded embeds (critical/warning/info)
- **Admin Controls** — Permission-gated commands via `manage_guild`

### Monitor System

4 watchers scan your watchlist on a configurable schedule (default 5 min):

| Watcher | Trigger | Description |
|---------|---------|-------------|
| **PriceWatcher** | >3% move | Intraday price alert |
| **SentimentWatcher** | Avg <2.5 or >4.0 | News sentiment shift |
| **SignalWatcher** | Anomaly detected | Sentiment/volume anomaly |
| **SectorWatcher** | Sector >2% divergence | Sector rotation signal |

Alerts are deduplicated (30-min cooldown + value threshold) and routed to Discord/console/log.

---

## HTTP API

```bash
python -m src.api
# Server: http://localhost:8420
# Swagger UI: http://localhost:8420/docs
```

**Example Requests:**

```bash
# News
curl "http://localhost:8420/news/NVDA?days=7"
curl "http://localhost:8420/news/NVDA/sentiment?days=30"

# Prices
curl "http://localhost:8420/prices/AMD?interval=15min&days=30"

# Options
curl "http://localhost:8420/options/PLTR"

# Fundamentals
curl "http://localhost:8420/fundamentals/AAPL"

# AI Agent query
curl -X POST "http://localhost:8420/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "Compare AMD and NVDA recent performance", "provider": "anthropic"}'
```

---

## Database Setup (Self-Hosted PostgreSQL)

### Docker Deployment

```bash
# Start with default port (15432)
docker compose up -d

# Custom port
POSTGRES_PORT=25432 docker compose up -d
```

Default connection: `postgresql://postgres:mindfulrl_dev_2026@localhost:15432/mindfulrl`

### Configure Connection

Edit `config/.env`:

```bash
DATABASE_URL=postgresql://postgres:mindfulrl_dev_2026@localhost:15432/mindfulrl
```

### Schema Migrations

Applied automatically on first Docker startup, or manually:

```sql
-- sql/001_init_schema.sql         — Core tables (news, prices, iv_history, fundamentals, signals, agent_queries)
-- sql/002_add_news_scores.sql     — Multi-model news scoring
-- sql/003_add_reports.sql         — Research reports
-- sql/004_add_memories.sql        — Episodic memory (full-text search, GIN + tsvector)
-- sql/005_add_financial_cache.sql — Financial data cache (paid API responses)
-- sql/006_add_news_search.sql     — Full-text search on news (GIN index) + pgvector embedding column
-- sql/007_add_sa_alpha_picks.sql  — Seeking Alpha Alpha Picks portfolio + refresh metadata
```

### Migrate Data from Parquet Files

```bash
python scripts/migrate_to_supabase.py              # Import all data
python scripts/migrate_to_supabase.py --prices      # Prices only
python scripts/migrate_to_supabase.py --news        # News only
python scripts/migrate_to_supabase.py --dry-run     # Count only
```

---

## Data Collection

### Daily Update

```bash
python scripts/collection/daily_update.py --status       # Check data status
python scripts/collection/daily_update.py --news          # Update all news
python scripts/collection/daily_update.py --all --sync-db # Everything + DB sync
```

### Individual Scripts

```bash
python scripts/collection/collect_polygon_news.py --incremental    # Polygon (3+ years)
python scripts/collection/collect_finnhub_news.py --incremental    # Finnhub (7 days)
python scripts/collection/collect_ibkr_news.py --incremental       # IBKR (requires TWS)
python scripts/collection/collect_ibkr_prices.py --incremental     # IBKR prices
python scripts/collection/collect_iv_history.py                    # IV history
```

---

## LLM Scoring Pipeline

### Current Models

| Model | Usage |
|-------|-------|
| **gpt-5.2** | Sentiment/risk scoring (primary) |
| **gpt-5.2** | Summary generation |

> **Strategy:** Use latest reasoning models only. Upgrade path: gpt-5 → gpt-5.1 → gpt-5.2 → ...

### Sentiment Scoring

```bash
python scripts/scoring/score_sentiment_openai.py \
  --input data.csv --output sentiment_scored.csv \
  --model gpt-5.2 --reasoning-effort high \
  --chunk-size 5000 --retry 3 --verbose
```

### Risk Scoring

```bash
python scripts/scoring/score_risk_openai.py \
  --input data.csv --output risk_scored.csv \
  --model gpt-5.2 --reasoning-effort high \
  --chunk-size 5000 --retry 3
```

### IBKR News Scoring (Parquet → DB)

```bash
python scripts/scoring/score_ibkr_news.py --continue-from   # Score unscored articles
python scripts/scoring/score_ibkr_news.py --rescore          # Re-score all
```

### Parameters

- `--reasoning-effort`: minimal, low, medium, high (gpt-5.x)
- `--chunk-size`: Rows per batch (default 5000, auto-resume on interrupt)
- `--allow-flex`: Flex mode for 50% cost savings (longer latency)
- `--daily-token-limit`: Auto-stop after budget (resume next day)

---

## RL Training Pipeline

### Prepare Dataset

```bash
# Basic: merge price + sentiment + risk
python training/data_prep/prepare_training_data.py \
  --price-data data/intraday.csv \
  --sentiment sentiment_scored.csv \
  --risk risk_scored.csv \
  --output-dir data/rl_ready/

# With derived features (MA, momentum, volatility)
python training/data_prep/prepare_training_data.py \
  --price-data data/intraday.csv \
  --sentiment sentiment_scored.csv \
  --risk risk_scored.csv \
  --output-dir data/rl_ready/ \
  --features                              # All defaults
  # --features sentiment_7d_ma risk_7d_ma  # Or specific features
```

Features are Z-score standardized; scaler saved as `feature_scaler_{tag}.json` alongside the CSV.

### Train

```bash
# PPO with sentiment signals
python training/train_ppo_llm.py --data data/rl_ready/train.csv --epochs 100 --seed 42

# CPPO with sentiment + risk signals
python training/train_cppo_llm_risk.py --data data/rl_ready/train.csv --epochs 100 --seed 42

# On-the-fly feature engineering (skips prepare step)
python training/train_ppo_llm.py --data raw.csv --epochs 50 --features
```

Models are saved to `trained_models/<model_id>/` with metadata and scaler automatically registered.

### Backtest

```bash
# By model ID (auto-loads metadata + features)
python training/backtest.py --data data/rl_ready/trade.csv --model-id latest

# By specific model ID
python training/backtest.py --data trade.csv --model-id ppo_claude_100ep_s42_20260301T120000Z_abc123

# By model path (derives model_id from directory)
python training/backtest.py --data trade.csv --model trained_models/xxx/model.pth
```

Outputs: Sharpe, Sortino, Calmar, max drawdown, CVaR 95%, win rate, daily returns CSV, equity curve PNG.
Results are appended to `backtest_runs[]` in the model registry for traceability.

### Model Storage

```
trained_models/
├── registry.json
├── ppo_claude_100ep_s42_.../
│   ├── model.pth
│   ├── metadata.json
│   ├── feature_scaler.json    # If --features was used
│   ├── daily_returns.csv      # Backtest artifact
│   ├── actions_log.csv        # Backtest artifact
│   └── equity_curve.png       # Backtest artifact
```

### Agent Integration

RL models are exposed to the agent via 3 tools (config-guarded, default off):

```yaml
# config/user_profile.yaml
rl_pipeline:
  enabled: false          # Set true when trained models exist
  models_dir: "trained_models"
```

- `get_rl_model_status` — List all models with backtest metrics
- `get_rl_backtest_report` — Detailed backtest report (Sharpe, Sortino, Calmar, CVaR, etc.)
- `get_rl_prediction` — Model availability check (live inference pending Phase 2)

---

## Seeking Alpha Alpha Picks (Optional)

Scrapes the [Alpha Picks](https://seekingalpha.com/alpha-picks/portfolio) portfolio page via Playwright with a saved browser session. Requires SA Premium + Alpha Picks subscription ($199/yr). Disabled by default.

### Setup

```bash
# 1. Install Playwright + browser
pip install playwright && playwright install chromium

# 2. Save browser session (one-time) — connects to your running Chrome via CDP
python scripts/sa_login.py --cdp --launch
# → Restarts Chrome with CDP (port 9222), reuses your existing SA login, saves session
# → All windows/tabs auto-restore; debug port has no effect on normal browsing

# Custom CDP port:
#   python scripts/sa_login.py --cdp --launch --cdp-port 9333

# Or manually: restart Chrome with CDP, then run:
#   google-chrome --remote-debugging-port=9222
#   python scripts/sa_login.py --cdp

# 3. Enable in config/user_profile.yaml
# seeking_alpha:
#   enabled: true
```

Session credentials are stored outside the repo (`~/.config/mindfulrl/seeking_alpha/storage_state.json`, 0600 permissions). Session validity is checked on each scrape (URL redirect + table selector + paywall marker).

### CLI

```bash
/ap                    # Current picks table (cached, auto-refresh if >24h stale)
/ap closed             # Closed positions
/ap all                # Both current + closed
/ap NVDA               # Detail report for a specific pick
/ap NVDA 2025-06-15    # Specific pick date (disambiguates re-picks)
/ap refresh            # Force refresh + sync tickers to collection watchlist
```

---

## Project Structure

### Agent Layer (`src/agents/`)

| Module | Description |
|--------|-------------|
| `cli.py` | Interactive CLI (21 slash commands, prompt caching, token tracking) |
| `config.py` | Model configuration, defaults, aliases |
| `anthropic_agent/agent.py` | Anthropic messages loop (streaming, thinking, effort) |
| `openai_agent/agent.py` | OpenAI Agents SDK wrapper (Responses API) |
| `shared/prompts.py` | System prompts with dynamic sections (freshness, RL status) |
| `shared/skills.py` | Skill registry + custom YAML loading |
| `shared/subagent.py` | Subagent registry + dispatch |
| `shared/token_tracker.py` | Per-turn token + cache tracking |
| `shared/context_manager.py` | Context compaction for long sessions (L1 client-side) |
| `shared/scratchpad.py` | JSONL session logging (10 event types) |
| `shared/attachments.py` | PDF/image/text file attachment processing |
| `shared/security.py` | Tool result wrapping for input safety |
| `shared/model_catalog.py` | Shared model catalog (CLI + Discord bot) |
| `shared/events.py` | Event types for async streaming |

### Tool Layer (`src/tools/`)

| Module | Description |
|--------|-------------|
| `registry.py` | ToolRegistry (47 tools, dual-format for Anthropic + OpenAI) |
| `data_access.py` | DataAccessLayer with backend abstraction |
| `backends/file_backend.py` | Parquet file backend |
| `backends/db_backend.py` | PostgreSQL backend (psycopg3) + `query_health_stats()` |
| `news_tools.py`, `price_tools.py`, `sa_tools.py`, etc. | Individual tool implementations |
| `report_tools.py` | Research report save/list/get |
| `memory_tools.py` | Episodic memory CRUD + full-text search |
| `web_tools.py` | Tavily search + Playwright browser + Codex deep research |
| `code_tools.py` | Python code execution + auto code gen |
| `freshness.py` | FreshnessRegistry singleton + data source health |
| `rl_tools.py` | RL model status, prediction, backtest report |

### Monitor Layer (`src/monitor/`)

| Module | Description |
|--------|-------------|
| `discord_bot.py` | Discord gateway (slash commands, buttons, free chat) |
| `engine.py` | MonitorEngine orchestrates watchers |
| `watchers.py` | 4 watchers (Price, Sentiment, Signal, Sector) |
| `scheduler.py` | MonitorScheduler (asyncio, configurable interval) |
| `notifiers.py` | Console, Log, Discord notifiers |
| `dedup.py` | AlertDeduplicator (cooldown + value threshold) |

### Training Layer (`training/`)

| Module | Description |
|--------|-------------|
| `train_ppo_llm.py` | PPO training with MPI, `--features` support, auto-registry |
| `train_cppo_llm_risk.py` | CPPO training (sentiment + risk), `--features` support |
| `backtest.py` | Full backtest metrics, artifact saving, registry integration |
| `train_utils.py` | Shared utilities (model ID, artifact saving, feature detection) |
| `data_prep/prepare_training_data.py` | Merge + split + optional feature engineering |
| `data_prep/feature_engineering.py` | Derived features (MA, momentum, volatility) + FeatureScaler |
| `envs/stocktrading_llm.py` | PPO trading env with `extra_feature_cols` + state invariants |
| `envs/stocktrading_llm_risk.py` | CPPO trading env with risk tail invariant |
| `model_registry.py` | ModelMetadata + ModelRegistry (JSON file-based, backtest_runs) |
| `UPSTREAM.md` | Lineage documentation for FinRL_DeepSeek fork |

### Data Sources (`data_sources/`)

| Source | Data | Tier |
|--------|------|------|
| **Finnhub** | News, quotes, company profiles, analyst consensus | Free |
| **Tiingo** | Historical stock prices (30+ years) | Free |
| **SEC EDGAR** | XBRL financial data (income, balance, cashflow) | Free |
| **Financial Datasets** | Structured financials (Q4, TTM, segmented) | PAYG $0.01/req |
| **Polygon** | News (3+ years), reference data | Free/Paid |
| **IBKR** | Real-time news, intraday prices, options | Requires TWS |
| **Seeking Alpha** | Alpha Picks portfolio & analysis reports | Premium + Alpha Picks ($199/yr) |

### Configuration (`config/`)

| File | Description |
|------|-------------|
| `.env` | API keys (from `.env.template`) |
| `user_profile.yaml` | 13 sections: watchlists, strategy, models, alerts, RL pipeline, Seeking Alpha, etc. |
| `sectors.yaml` | Sector definitions and ticker mappings |
| `tickers_core.json` | Core ticker list (Tier 1/2/3) |
| `skills/*.yaml` | Custom skill definitions |

---

## Web Search Configuration

The system has 6 web search capabilities across 3 layers:

| # | Tool | Type | Config Key | Default | Cost | Notes |
|---|------|------|-----------|---------|------|-------|
| 1 | `tavily_search` | Agent tool | `web_search.tavily` | ON | Free 1000/mo | AI-summarized results |
| 2 | `tavily_fetch` | Agent tool | `web_search.tavily` | ON | (same quota) | URL content extraction |
| 3 | `web_browse` | Agent tool | `web_search.playwright` | ON | Free (local) | Headless browser, JS pages |
| 4 | `codex_web_research` | Agent tool | `web_search.codex_research` | ON | OAuth quota | Deep research via Codex CLI |
| 5 | Claude `web_search` | Server tool | `web_search.claude_search` | OFF | $10/1K | Anthropic agent only |
| 6 | OpenAI `WebSearchTool` | SDK built-in | `web_search.openai_search` | ON | Included | OpenAI agent only |

**Tools 1-4** are registered in the tool registry (available to both agents).
**Tools 5-6** are SDK server-side tools (only active in their respective agent).

### Setup

```bash
# Tavily (tools 1-2): set API key in config/.env
TAVILY_API_KEY=tvly-...

# Playwright (tool 3): install browsers
playwright install chromium

# Codex CLI (tool 4): install + OAuth login (uses subscription quota, not API billing)
npm install -g @openai/codex
codex login

# Claude web search (tool 5): no setup, just enable in config
# OpenAI web search (tool 6): no setup, uses existing OPENAI_API_KEY
```

### Toggle in `config/user_profile.yaml`

```yaml
web_search:
  tavily: true
  playwright: true
  codex_research: true
  claude_search: false          # $10/1K searches, enable when needed
  claude_search_max_uses: 5     # per-conversation limit
  openai_search: true
```

### When to use which

| Scenario | Recommended Tool |
|----------|-----------------|
| Quick fact check, latest news | `tavily_search` |
| Read specific URL content | `tavily_fetch` or `web_browse` |
| JS-heavy page, interactive site | `web_browse` |
| Deep investigation (earnings, events, trends) | `codex_web_research` |
| Agent auto-decides during analysis | Claude/OpenAI native search |

---

## Advanced Features

### Score Validation

```bash
python scripts/analysis/validate_scoring_value.py --file scored_data.csv --score-col sentiment_gpt_5
python scripts/analysis/sentiment_backtest.py --file scored_data.csv --score-col sentiment_gpt_5
```

### News Dashboard (Streamlit)

```bash
streamlit run scripts/visualization/news_dashboard.py
```

### Fundamentals CLI

```bash
python scripts/visualization/fundamentals_query.py
> AAPL                    # Single stock
> AAPL MSFT GOOGL         # Compare multiple
> top roe                 # ROE ranking
> pe<20 roe>15            # Filter by conditions
```

### Model Comparison

```bash
python scripts/comparison/compare_scores.py --files a.csv,b.csv --column sentiment_gpt_5
python scripts/comparison/ab_score_comparison.py --file-a a.csv --file-b b.csv
```

---

## Development

### Run Tests

```bash
pytest tests/                                # All tests
pytest tests/test_agents.py -v               # Agent tests
pytest tests/test_subagent.py -v             # Subagent tests
pytest tests/test_tools.py -v                # Tool tests
pytest tests/test_skills.py -v               # Skills tests
pytest tests/test_api.py -v                  # API tests
pytest tests/test_rl_tools.py -v             # RL pipeline agent tools
pytest tests/test_feature_engineering.py -v  # Feature engineering + scaler
pytest tests/test_env_extra_features.py -v   # Env state vector invariants
pytest tests/test_train_utils.py -v          # Training utilities
pytest tests/test_backtest_enhanced.py -v    # Backtest metrics + artifacts
pytest tests/test_integration_pipeline.py -v # E2E features→train→backtest
pytest tests/test_monitor.py -v              # Monitor tests
pytest tests/ --cov=src --cov-report=html    # With coverage
```

### Development Server

```bash
uvicorn src.api.app:create_app --factory --reload --port 8420
```

### Documentation

| Category | Files |
|----------|-------|
| **Architecture** | `docs/design/MINDFULRL_ARCHITECTURE.md`, `SERVICE_ARCHITECTURE.md`, `DATA_STORAGE_ACCESS.md` |
| **Agent Evolution** | `docs/design/AGENT_EVOLUTION_TRACKER.md` (detailed changelog, Phase 0-15 + A-F) |
| **RL Pipeline** | `docs/design/RL_PIPELINE_DESIGN.md` (end-to-end integration design) |
| **Data** | `docs/data/DATA_SUBSCRIPTION_GUIDE.md`, `OPTIONS_FLOW_GUIDE.md`, `OPTIONS_PRICING_THEORY.md` |
| **Analysis** | `docs/analysis/SCORING_VALIDATION_METHODOLOGY.md` |
| **Scripts** | `scripts/scoring/README.md`, `scripts/visualization/README.md` |
| **Training** | `training/UPSTREAM.md` (FinRL_DeepSeek lineage) |

---

## License

MIT License - see LICENSE file for details.
