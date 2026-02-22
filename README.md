# MindfulRL-Intraday

> Reinforcement learning trading system with dual-provider AI agents (Anthropic + OpenAI), 30 financial tools, and multi-source news/price/options data pipeline.

## Overview

MindfulRL-Intraday combines RL-based trading strategies with LLM-powered analysis:

- **Dual AI Agent CLI** — Anthropic (Claude Opus 4.6) + OpenAI (GPT-5.2) with 30 tools, 4 skills, 4 subagents
- **HTTP API** — 25 RESTful endpoints (FastAPI + Swagger UI)
- **News Pipeline** — Multi-source collection (Polygon, Finnhub, IBKR) with LLM scoring
- **Analysis Toolkit** — Fundamentals (SEC EDGAR + Financial Datasets), options (IV/Greeks), signals, web search
- **RL Training** — PPO/CPPO agents with sentiment and risk-enhanced data
- **Self-hosted PostgreSQL** — pgvector-enabled, Docker deployment

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

### Slash Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `/model [name]` | `/m` | Show model picker / switch model |
| `/skill <name> [args]` | `/sk` | Run a skill workflow (e.g. `/sk fa NVDA`) |
| `/subagent [name] [model]` | `/sa` | View/change subagent models |
| `/reasoning <level>` | `/r` | Set OpenAI reasoning (none/minimal/low/medium/high/xhigh) |
| `/effort <level>` | `/e` | Set Anthropic effort (max/high/medium/low) |
| `/thinking` | `/t` | Toggle extended thinking (Anthropic) |
| `/context` | `/ctx` | Toggle 1M context beta (Anthropic) |
| `/compaction` | `/cmp` | Toggle server-side compaction (Opus 4.6) |
| `/code-model [name]` | `/cm` | Set code generation model |
| `/turns <n>` | | Set max tool calls per query |
| `/memory [save\|search\|delete]` | `/mem` | Episodic memory (cross-session knowledge) |
| `/attach <path> [pages]` | `/at` | Attach PDF/image/text to next query |
| `/save [N\|N-M] ["title"]` | `/sv` | Save session exchanges as report |
| `/reports [ticker]` | `/rp` | List/view saved research reports |
| `/code-backend [name]` | `/cb` | Set code generation backend (api/codex/claude) |
| `/scratchpad` | `/pad` | List recent scratchpad sessions |
| `/history [N]` | `/h` | Show current session Q&A history |
| `/status` | `/s` | Show session config |
| `/help` | | Show all commands |

### Tools (36)

| Category | Tool | Description |
|----------|------|-------------|
| **News** | `get_ticker_news` | Recent articles for a ticker |
| | `get_news_sentiment_summary` | Aggregated sentiment statistics |
| | `search_news_by_keyword` | Keyword search across news |
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
| **Portfolio** | `get_portfolio_analysis` | P&L, beta vs SPY, correlation matrix, HHI |
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
| **Code** | `execute_python_analysis` | Python code execution with auto code gen |

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
python prepare_dataset_openai.py \
  --price-data data/intraday.csv \
  --sentiment sentiment_scored.csv \
  --risk risk_scored.csv \
  --output merged_dataset.csv
```

### Train

```bash
bash train_openai.sh merged_dataset.csv ppo sentiment
bash train_openai.sh merged_dataset.csv cppo risk
```

### Backtest

```bash
python backtest_openai.py --data merged_dataset.csv \
  --model trained_models/agent_ppo_llm_100_epochs_sentiment.pth \
  --env sentiment --output-plot equity.png
```

---

## Project Structure

### Agent Layer (`src/agents/`)

| Module | Description |
|--------|-------------|
| `cli.py` | Interactive CLI (18 slash commands, prompt caching, token tracking) |
| `config.py` | Model configuration, defaults, aliases |
| `anthropic_agent/agent.py` | Anthropic messages loop (streaming, thinking, effort) |
| `openai_agent/agent.py` | OpenAI Agents SDK wrapper (Responses API) |
| `shared/prompts.py` | System prompts shared across providers |
| `shared/skills.py` | Skill registry + custom YAML loading |
| `shared/subagent.py` | Subagent registry + dispatch |
| `shared/token_tracker.py` | Per-turn token + cache tracking |
| `shared/context_manager.py` | Context compaction for long sessions |
| `shared/scratchpad.py` | JSONL session logging + chat history |
| `shared/attachments.py` | PDF/image/text file attachment processing |
| `shared/security.py` | Tool result wrapping for input safety |

### Tool Layer (`src/tools/`)

| Module | Description |
|--------|-------------|
| `registry.py` | ToolRegistry (30 tools, dual-format for Anthropic + OpenAI) |
| `data_access.py` | DataAccessLayer with backend abstraction |
| `backends/file_backend.py` | Parquet file backend |
| `backends/db_backend.py` | PostgreSQL backend (psycopg3) |
| `news_tools.py`, `price_tools.py`, etc. | Individual tool implementations |
| `report_tools.py` | Research report save/list/get |
| `memory_tools.py` | Episodic memory CRUD + full-text search |
| `web_tools.py` | Tavily search + Playwright browser |
| `code_tools.py` | Python code execution + auto code gen |

### Data Sources (`data_sources/`)

| Source | Data | Tier |
|--------|------|------|
| **Finnhub** | News, quotes, company profiles, analyst consensus | Free |
| **Tiingo** | Historical stock prices (30+ years) | Free |
| **SEC EDGAR** | XBRL financial data (income, balance, cashflow) | Free |
| **Financial Datasets** | Structured financials (Q4, TTM, segmented) | PAYG $0.01/req |
| **Polygon** | News (3+ years), reference data | Free/Paid |
| **IBKR** | Real-time news, intraday prices, options | Requires TWS |

### Configuration (`config/`)

| File | Description |
|------|-------------|
| `.env` | API keys (from `.env.template`) |
| `user_profile.yaml` | Watchlists, strategy weights, model priority |
| `sectors.yaml` | Sector definitions and ticker mappings |
| `tickers_core.json` | Core ticker list (Tier 1/2/3) |
| `skills/*.yaml` | Custom skill definitions |

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
pytest tests/                        # All tests (~560 tests)
pytest tests/test_agents.py -v       # Agent tests
pytest tests/test_subagent.py -v     # Subagent tests
pytest tests/test_tools.py -v        # Tool tests
pytest tests/test_skills.py -v       # Skills tests
pytest tests/test_api.py -v          # API tests
pytest tests/ --cov=src --cov-report=html  # With coverage
```

### Development Server

```bash
uvicorn src.api.app:create_app --factory --reload --port 8420
```

### Documentation

| Category | Files |
|----------|-------|
| **Architecture** | `docs/design/MINDFULRL_ARCHITECTURE.md`, `SERVICE_ARCHITECTURE.md`, `DATA_STORAGE_ACCESS.md` |
| **Agent Evolution** | `docs/design/AGENT_EVOLUTION_TRACKER.md` (detailed changelog) |
| **Data** | `docs/data/DATA_SUBSCRIPTION_GUIDE.md`, `OPTIONS_FLOW_GUIDE.md`, `OPTIONS_PRICING_THEORY.md` |
| **Analysis** | `docs/analysis/SCORING_VALIDATION_METHODOLOGY.md` |
| **Scripts** | `scripts/scoring/README.md`, `scripts/visualization/README.md` |

---

## License

MIT License - see LICENSE file for details.