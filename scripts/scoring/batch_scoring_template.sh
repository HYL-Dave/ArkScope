#!/bin/bash
# Customizable multi-stage scoring template with advanced options
# Edit the parameters section below to customize your run
#
# Original: run_risk_scoring_custom.sh (moved 2026-01-08)
# Features: Flex mode, max runtime, verbose logging
# Usage: Copy and modify for your specific use case
#   cp scripts/scoring/batch_scoring_template.sh my_scoring_job.sh
#   ./my_scoring_job.sh

set -e  # Exit on error

# Navigate to project root (where score_*_openai.py are located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

#==============================================
# CONFIGURATION - EDIT THESE PARAMETERS
#==============================================

# Input/Output paths
INPUT_CSV="/mnt/md0/finrl/gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv"
OUTPUT_CSV="/mnt/md0/finrl/o3/risk/risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv"

# Model settings
MODEL="o3"                          # Model: o3, o4-mini, gpt-5, etc.
REASONING_EFFORT="high"             # Reasoning effort: low, medium, high (minimal for gpt-5)
VERBOSITY="low"                     # Verbosity (gpt-5 only): low, medium, high

# CSV column names
SYMBOL_COL="Stock_symbol"
TEXT_COL="gpt_5_summary"            # Options: Article_title, Article, Lsa_summary,
                                    #          Luhn_summary, Textrank_summary, Lexrank_summary,
                                    #          o3_summary, gpt_5_summary
DATE_COL="Date"

# Processing settings
CHUNK_SIZE=20                       # Rows per chunk (for resume capability)
DAILY_LIMIT=1000000                 # Token limit per API key file
RETRY_MISSING=5                     # Extra retries for missing scores
RETRY=4                             # Internal retry attempts

# API key files (processed in order)
API_KEY_FILES=(
    "api_keys_tier1.txt"
    "api_keys_tier5.txt"
    # Add more files as needed:
    # "api_keys_tier_both.txt"
    # "api_keys_backup.txt"
)

# Optional: Flex mode settings (uncomment to enable)
# FLEX_MODE="--allow-flex"
# FLEX_TIMEOUT="--flex-timeout 900.0"
# FLEX_RETRIES="--flex-retries 1"

# Optional: Max runtime per stage (uncomment to enable)
# MAX_RUNTIME="--max-runtime 3600"  # seconds

# Verbose logging
VERBOSE="--verbose"

#==============================================
# END CONFIGURATION
#==============================================

echo "=========================================="
echo "Multi-stage Risk Scoring Pipeline"
echo "=========================================="
echo "Input: $INPUT_CSV"
echo "Output: $OUTPUT_CSV"
echo "Model: $MODEL (reasoning: $REASONING_EFFORT)"
echo "Text column: $TEXT_COL"
echo "Chunk size: $CHUNK_SIZE"
echo "API Key Files: ${API_KEY_FILES[@]}"
echo "Daily Token Limit per file: $DAILY_LIMIT"
echo "=========================================="
echo ""

# Validate input file exists
if [ ! -f "$INPUT_CSV" ]; then
    echo "ERROR: Input file not found: $INPUT_CSV"
    exit 1
fi

# Loop through each API key file
TOTAL_STAGES=${#API_KEY_FILES[@]}
SUCCESS_COUNT=0

for i in "${!API_KEY_FILES[@]}"; do
    KEY_FILE="${API_KEY_FILES[$i]}"
    STAGE=$((i + 1))

    echo "=========================================="
    echo "Stage $STAGE/$TOTAL_STAGES: Using $KEY_FILE"
    echo "=========================================="

    # Check if key file exists
    if [ ! -f "$KEY_FILE" ]; then
        echo "WARNING: $KEY_FILE not found, skipping..."
        echo ""
        continue
    fi

    # Count number of keys in file
    NUM_KEYS=$(grep -c . "$KEY_FILE" || echo 0)
    echo "Found $NUM_KEYS API keys in $KEY_FILE"

    # Check if output already exists
    if [ -f "$OUTPUT_CSV" ]; then
        PROCESSED_ROWS=$(wc -l < "$OUTPUT_CSV")
        echo "Output file exists with $PROCESSED_ROWS rows (including header)"
        echo "Will resume from this point..."
    else
        echo "Starting fresh processing..."
    fi

    echo ""
    echo "Executing scoring script..."
    echo "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Build command with optional parameters
    CMD="python score_risk_openai.py \
        --input \"$INPUT_CSV\" \
        --output \"$OUTPUT_CSV\" \
        --model \"$MODEL\" \
        --symbol-column \"$SYMBOL_COL\" \
        --text-column \"$TEXT_COL\" \
        --date-column \"$DATE_COL\" \
        --chunk-size $CHUNK_SIZE \
        --api-keys-file \"$KEY_FILE\" \
        --daily-token-limit $DAILY_LIMIT \
        --retry-missing $RETRY_MISSING \
        --retry $RETRY \
        --reasoning-effort \"$REASONING_EFFORT\""

    # Add optional parameters if defined
    [ -n "$VERBOSITY" ] && CMD="$CMD --verbosity \"$VERBOSITY\""
    [ -n "$FLEX_MODE" ] && CMD="$CMD $FLEX_MODE"
    [ -n "$FLEX_TIMEOUT" ] && CMD="$CMD $FLEX_TIMEOUT"
    [ -n "$FLEX_RETRIES" ] && CMD="$CMD $FLEX_RETRIES"
    [ -n "$MAX_RUNTIME" ] && CMD="$CMD $MAX_RUNTIME"
    [ -n "$VERBOSE" ] && CMD="$CMD $VERBOSE"

    # Execute the command
    eval $CMD

    EXIT_CODE=$?

    echo ""
    echo "End time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ Stage $STAGE completed successfully"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "✗ Stage $STAGE failed with exit code $EXIT_CODE"
        echo "Stopping pipeline due to error"
        exit $EXIT_CODE
    fi

    # Show current progress
    if [ -f "$OUTPUT_CSV" ]; then
        FINAL_ROWS=$(wc -l < "$OUTPUT_CSV")
        echo "Current output has $FINAL_ROWS rows (including header)"
    fi

    echo ""
done

echo "=========================================="
echo "Pipeline Summary"
echo "=========================================="
echo "Completed stages: $SUCCESS_COUNT/$TOTAL_STAGES"
echo "Final output: $OUTPUT_CSV"

# Show final statistics
if [ -f "$OUTPUT_CSV" ]; then
    TOTAL_ROWS=$(wc -l < "$OUTPUT_CSV")
    TOTAL_DATA_ROWS=$((TOTAL_ROWS - 1))
    echo "Total rows (with header): $TOTAL_ROWS"
    echo "Total data rows: $TOTAL_DATA_ROWS"

    # Count non-null risk scores (optional, requires checking CSV content)
    echo ""
    echo "Sample output (first 3 data rows):"
    head -n 4 "$OUTPUT_CSV" | tail -n 3
fi

echo ""
echo "=========================================="
echo "All done! $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="