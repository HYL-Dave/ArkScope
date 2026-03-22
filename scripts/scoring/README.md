# Scoring Scripts

LLM-based sentiment and risk scoring tools for financial news.

## Directory Structure

```
scripts/scoring/
├── batch_risk_scoring.sh        # Multi-API-key risk scoring pipeline
├── batch_sentiment_scoring.sh   # Multi-API-key sentiment scoring pipeline
├── batch_scoring_template.sh    # Advanced configuration template (Flex mode, timeout)
├── validate_scores.py           # CSV validation tool
├── score_ibkr_news.py          # Universal parquet news scoring (Polygon/Finnhub/IBKR)
└── README.md
```

## Historical Context

These scripts were developed to maximize the daily free quota across multiple OpenAI API accounts (Tier 1 and Tier 5). The multi-key rotation strategy allowed efficient processing of large news datasets.

### Usage History (2024-2025)

| Script | Original Name | Executions | Output Size |
|--------|---------------|------------|-------------|
| batch_risk_scoring.sh | run_risk_scoring_multi_keys.sh | 10+ | ~3GB |
| batch_sentiment_scoring.sh | run_sentiment_scoring_multi_keys.sh | 10+ | ~3GB |
| batch_scoring_template.sh | run_risk_scoring_custom.sh | 0 (template) | - |
| validate_scores.py | check_sentiment_csv.py | - | - |

Output files stored at:
- `/mnt/md0/finrl/o3/risk/` (~3GB)
- `/mnt/md0/finrl/o3/sentiment/` (~3GB)

## Scripts

### batch_risk_scoring.sh / batch_sentiment_scoring.sh

Multi-stage scoring with API key rotation and resume capability.

**Features:**
- Multiple API key files processed in sequence
- Automatic resume from last checkpoint
- Daily token limit per key file
- Chunk-based processing

**Configuration:**
```bash
# Input/Output
INPUT_CSV="..."
OUTPUT_CSV="..."

# Model settings
MODEL="o3"
REASONING_EFFORT="high"

# API keys (processed in order)
API_KEY_FILES=(
    "api_keys_tier1.txt"
    "api_keys_tier5.txt"
)
```

**Usage:**
```bash
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
./scripts/scoring/batch_risk_scoring.sh
./scripts/scoring/batch_sentiment_scoring.sh
```

### batch_scoring_template.sh

Advanced configuration template with additional options:
- Flex mode (50% cost reduction)
- Max runtime limits
- Verbose logging

**Additional Options:**
```bash
# Flex mode (uncomment to enable)
# FLEX_MODE="--allow-flex"
# FLEX_TIMEOUT="--flex-timeout 900.0"

# Runtime limit
# MAX_RUNTIME="--max-runtime 3600"

# Logging
VERBOSE="--verbose"
```

### validate_scores.py

Validates CSV files with sentiment/risk scores.

**Checks:**
- Required columns exist
- Score values are integers 1-5
- No missing values in key columns

**Usage:**
```bash
python scripts/scoring/validate_scores.py <csv_file>
```

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

- Scoring scripts (now in this directory): `score_sentiment_openai.py`, `score_risk_openai.py`, `score_sentiment_anthropic.py`, `score_risk_anthropic.py`
- API key files: `api_keys_tier1.txt`, `api_keys_tier5.txt` (gitignored)
- Documentation: `OPENAI_SCRIPTS.md`

## Migration Notes (2026-01-08)

Files moved from project root:
- `run_risk_scoring_multi_keys.sh` -> `batch_risk_scoring.sh`
- `run_sentiment_scoring_multi_keys.sh` -> `batch_sentiment_scoring.sh`
- `run_risk_scoring_custom.sh` -> `batch_scoring_template.sh`
- `check_sentiment_csv.py` -> `validate_scores.py`

After moving, update shell script paths to call Python scripts from the new location.

## Migration Notes (2026-01-12)

### Scripts Consolidated to scripts/scoring/

Moved from project root:
- `score_sentiment_openai.py` - OpenAI sentiment scoring (CSV)
- `score_risk_openai.py` - OpenAI risk scoring (CSV)
- `score_sentiment_anthropic.py` - Anthropic sentiment scoring (CSV)
- `score_risk_anthropic.py` - Anthropic risk scoring (CSV)

### score_ibkr_news.py: Dynamic Column Naming

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
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-5.4 \
    --reasoning-effort xhigh --data-dir data/news/raw/polygon \
    --continue-from gpt-5.2 --continue-from-effort xhigh
```

**Example: Three-generation chain**
```
Timeline:  2022 ───── 2026-03 ── 2026-04 ─── 2026-09 ── 2026-10 ─── 2027
Model:     ◄─ gpt-5.2 ─►       ◄─ gpt-5.4 ─►          ◄── gpt-6 ──►
```

```bash
# Step 3: gpt-6 picks up new articles, skipping BOTH gpt-5.2 and gpt-5.4
python scripts/scoring/score_ibkr_news.py --mode sentiment --model gpt-6 \
    --reasoning-effort high --data-dir data/news/raw/polygon \
    --continue-from gpt-5.2,gpt-5.4 --continue-from-effort xhigh
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