# Scoring Scripts

LLM-based sentiment and risk scoring tools for financial news.

## Directory Structure

```
scripts/scoring/
├── score_ibkr_news.py           # Universal parquet news scoring (Polygon/Finnhub/IBKR) — active
├── score_sentiment_anthropic.py # Claude sentiment scorer (parquet + CSV, Batch API)
├── score_risk_anthropic.py      # Claude risk scorer (parquet + CSV, Batch API)
├── openai_summary.py            # Article → summary (scoring input for some columns)
├── validate_scores.py           # Score-output validator (CSV; to be reworked for parquet)
└── README.md
```

## Open-dataset provenance (retired CSV/FNSPID pipeline)

The OpenAI CSV scoring pipeline that produced the open dataset
[HYL/NASDAQ-News-Multi-LLM-Scores](https://huggingface.co/datasets/HYL/NASDAQ-News-Multi-LLM-Scores)
— `score_sentiment_openai.py`, `score_risk_openai.py`, the `batch_*_scoring.sh`
multi-API-key shells (hard-wired to `/mnt/md0/finrl/...` FNSPID/o3 paths), and the root
`OPENAI_SCRIPTS.md` — was retired in the 2026-05 local-first pivot. The exact sentiment /
risk / summary prompts are preserved for reproducibility at
[`../huggingface/SCORING_PROMPTS.md`](../huggingface/SCORING_PROMPTS.md); the dataset
column mapping is in [`../huggingface/column_mapping.md`](../huggingface/column_mapping.md).

## Scripts

### validate_scores.py

Validates CSV files with sentiment/risk scores.

**Checks:**
- Required columns exist
- Score values are integers 1-5
- No missing values in key columns

**Usage:**
```bash
python scripts/scoring/validate_scores.py --input <csv_file> \
    --sentiment-column sentiment_<model>   # e.g. --sentiment-column sentiment_gpt_5_4_high
```
(Also accepts `--symbol-column`, `--text-column`, `--date-column`; see `--help`.)

### score_ibkr_news.py

Universal parquet news scoring. Works with **any** news source using the unified parquet schema
(`ticker`, `title`, `content`, `content_length`), including Polygon, Finnhub, and IBKR.

```bash
# Score different data sources via --data-dir
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --data-dir data/news/raw/polygon

python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --data-dir data/news/raw/finnhub

python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --data-dir data/news/raw/ibkr  # default
```

## Related Files

- Active scorers: `score_ibkr_news.py`, `score_sentiment_anthropic.py`, `score_risk_anthropic.py`, `openai_summary.py`
- API key files: `api_keys_tier1.txt`, `api_keys_tier5.txt` (gitignored)
- Open-dataset prompts (provenance): `../huggingface/SCORING_PROMPTS.md`

## score_ibkr_news.py — detailed reference

### Dynamic Column Naming

**Breaking Change**: Column names are now dynamically generated based on model AND reasoning effort.

**Column naming convention:**
```
{mode}_{model}_{reasoning_effort}
```

| Model | Reasoning Effort | Sentiment Column | Risk Column |
|-------|------------------|------------------|-------------|
| gpt-5 | high | `sentiment_gpt_5_high` | `risk_gpt_5_high` |
| gpt-5.2 | high | `sentiment_gpt_5_2_high` | `risk_gpt_5_2_high` |
| gpt-5.2 | xhigh | `sentiment_gpt_5_2_xhigh` | `risk_gpt_5_2_xhigh` |
| gpt-5.4 | high | `sentiment_gpt_5_4_high` | `risk_gpt_5_4_high` |
| gpt-5.4-mini | high | `sentiment_gpt_5_4_mini_high` | `risk_gpt_5_4_mini_high` |
| gpt-5.4-nano | high | `sentiment_gpt_5_4_nano_high` | `risk_gpt_5_4_nano_high` |
| o4-mini | medium | `sentiment_o4_mini_medium` | `risk_o4_mini_medium` |

**Conversion rule**: `-` and `.` in model name → `_`

Previously hardcoded as `sentiment_deepseek` / `risk_deepseek`.

### Reasoning Effort Levels (GPT-5.x / o-series)

Column naming includes `reasoning_effort` to distinguish different scoring configurations.

> **Important**: `reasoning_effort` controls model thinking depth and affects scoring quality.
> `verbosity` is a legacy parameter only supported on gpt-5, gpt-5-mini, and gpt-5.1 (removed in gpt-5.2+).

**Available levels:**

| Level | Description | Models |
|-------|-------------|--------|
| `none` | No extended thinking | gpt-5.x |
| `minimal` | Minimal reasoning | gpt-5.x |
| `low` | Light reasoning | gpt-5.x, o-series |
| `medium` | Balanced reasoning | gpt-5.x, o-series |
| `high` | Deep reasoning (recommended) | gpt-5.x, o-series |
| `xhigh` | Maximum reasoning (Pro only) | gpt-5.x Pro |

**Usage:**
```bash
# Default: high reasoning effort
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2

# Explicit reasoning effort
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --reasoning-effort high

# Maximum reasoning (requires Pro subscription)
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --reasoning-effort xhigh
```

### score_ibkr_news.py: Feature Summary

```bash
# Preview (dry-run)
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 --dry-run

# Multiple API keys with rotation
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --api-keys-file ~/.openai_keys --daily-token-limit 1000000

# Enable Flex mode fallback (50% cost reduction)
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --daily-token-limit 1000000 --allow-flex
```

**Capabilities:**
- ✅ Multiple API keys (`--api-keys-file`)
- ✅ Token limit per key (`--daily-token-limit`)
- ✅ Automatic key rotation when limit reached
- ✅ Flex mode fallback (`--allow-flex`)
- ✅ Incremental scoring (skips already-scored articles)
- ✅ Model chain switching (`--continue-from`)
- ✅ Progress checkpoints (`--save-every`)
- ✅ Dry-run preview (`--dry-run`)

### Model Chain Switching (`--continue-from`)

When new models are released and old models are retired, `--continue-from` lets you
switch scoring models without re-scoring articles that previous models already covered.

**How it works:**
- Each model writes to its own column (e.g., `sentiment_gpt_5_2_xhigh`, `sentiment_gpt_5_4_xhigh`)
- `--continue-from` skips articles where ANY listed predecessor model has a score
- Multiple predecessors are comma-separated to support multi-generation chains
- `--reasoning-effort` controls the **new model's** API reasoning depth
- `--continue-from-effort` is for column name lookup only (usually not needed, see below)

**About `--continue-from-effort` (usually omit it):**

`--continue-from-effort` specifies which effort column to look for in the predecessor model.
When **omitted**, the script auto-detects ALL effort columns for each predecessor
(e.g., both `sentiment_gpt_5_2_high` and `sentiment_gpt_5_2_xhigh`) and skips articles
scored by any of them. This is the **recommended usage** — it handles mixed-effort
predecessors and multi-model chains without extra configuration.

Only specify `--continue-from-effort` if you need to restrict to a specific effort column
(rare edge case where you want to re-score articles from one effort level but keep another).

**Example: Two-generation handoff**
```
Timeline:  2022 ────────────────── 2026-03 ── 2026-04 ──────────── 2026-12
Model:     ◄── gpt-5.2 scored ──►           ◄── gpt-5.4 scores ──►
```

```bash
# Step 1: gpt-5.2 scores everything available (2022 ~ 2026-03)
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.2 \
    --reasoning-effort xhigh --data-dir data/news/raw/polygon

# Step 2: gpt-5.4 picks up new articles only (2026-04+)
# No --continue-from-effort needed — auto-detects gpt-5.2's columns
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \
    --reasoning-effort xhigh --data-dir data/news/raw/polygon \
    --continue-from gpt-5.2
```

**Example: Three-generation chain**
```
Timeline:  2022 ───── 2026-03 ── 2026-04 ─── 2026-09 ── 2026-10 ─── 2027
Model:     ◄─ gpt-5.2 ─►       ◄─ gpt-5.4 ─►          ◄── gpt-6 ──►
```

```bash
# Step 3: gpt-6 picks up new articles, skipping BOTH gpt-5.2 and gpt-5.4
# Auto-detect handles different effort levels across predecessors
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-6 \
    --reasoning-effort high --data-dir data/news/raw/polygon \
    --continue-from gpt-5.2,gpt-5.4
```

**Important: Always list ALL predecessor models in the chain.** If you only list the
most recent predecessor (e.g., `--continue-from gpt-5.4`), articles scored by earlier
models (gpt-5.2) but not by gpt-5.4 will appear as "unscored" and get re-scored.

**Resulting parquet columns:**
```
sentiment_gpt_5_2_xhigh | sentiment_gpt_5_4_xhigh | sentiment_gpt_6_high
4                        | NULL                     | NULL         (old, gpt-5.2)
NULL                     | 3                        | NULL         (mid, gpt-5.4)
NULL                     | NULL                     | 5            (new, gpt-6)
```

**Downstream usage:** Training/analysis code should merge columns with coalesce logic
(prefer newest model, fallback to older). See `training/data_prep/prepare_training_data.py`.