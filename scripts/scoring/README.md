# Scoring Scripts

LLM-based sentiment and risk scoring tools for financial news.

## Directory Structure

```
scripts/scoring/
├── batch_risk_scoring.sh        # Multi-API-key risk scoring pipeline
├── batch_sentiment_scoring.sh   # Multi-API-key sentiment scoring pipeline
├── batch_scoring_template.sh    # Advanced configuration template (Flex mode, timeout)
├── validate_scores.py           # CSV validation tool
├── score_ibkr_news.py          # IBKR news scoring integration
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

IBKR news scoring integration (uses IBKR API news data).

## Related Files

- Root scoring scripts: `score_sentiment_openai.py`, `score_risk_openai.py`
- API key files: `api_keys_tier1.txt`, `api_keys_tier5.txt` (gitignored)
- Documentation: `OPENAI_SCRIPTS.md`

## Migration Notes (2026-01-08)

Files moved from project root:
- `run_risk_scoring_multi_keys.sh` -> `batch_risk_scoring.sh`
- `run_sentiment_scoring_multi_keys.sh` -> `batch_sentiment_scoring.sh`
- `run_risk_scoring_custom.sh` -> `batch_scoring_template.sh`
- `check_sentiment_csv.py` -> `validate_scores.py`

After moving, update shell script paths to call Python scripts from the new location.