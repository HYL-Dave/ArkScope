#!/bin/bash
# Multi-stage risk scoring script with different API key files
# Uses resume capability - each run continues from where the previous stopped
#
# Original: run_risk_scoring_multi_keys.sh (moved 2026-01-08)
# Usage: Run from project root or any directory
#   ./scripts/scoring/batch_risk_scoring.sh

set -e  # Exit on error

# Navigate to project root (for API key files; Python scripts are in scripts/scoring/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Common parameters
INPUT_CSV="/mnt/md0/finrl/gpt-5/summary/gpt-5_reason_high_verbosity_high_news_with_summary.csv"
OUTPUT_CSV="/mnt/md0/finrl/o3/risk/risk_o3_high_by_gpt-5_reason_high_verbosity_high.csv"
MODEL="o3"
SYMBOL_COL="Stock_symbol"
TEXT_COL="gpt_5_summary"
DATE_COL="Date"
CHUNK_SIZE=20
DAILY_LIMIT=1000000
RETRY_MISSING=5
RETRY=4
REASONING_EFFORT="high"

# API key files to use (in order)
API_KEY_FILES=(
    "api_keys_tier1.txt"
    "api_keys_tier5.txt"
)

echo "=========================================="
echo "Multi-stage Risk Scoring Pipeline"
echo "=========================================="
echo "Input: $INPUT_CSV"
echo "Output: $OUTPUT_CSV"
echo "Model: $MODEL"
echo "API Key Files: ${API_KEY_FILES[@]}"
echo "Daily Token Limit per file: $DAILY_LIMIT"
echo "=========================================="
echo ""

# Loop through each API key file
for i in "${!API_KEY_FILES[@]}"; do
    KEY_FILE="${API_KEY_FILES[$i]}"
    STAGE=$((i + 1))

    echo "----------------------------------------"
    echo "Stage $STAGE/${#API_KEY_FILES[@]}: Using $KEY_FILE"
    echo "----------------------------------------"

    # Check if key file exists
    if [ ! -f "$KEY_FILE" ]; then
        echo "WARNING: $KEY_FILE not found, skipping..."
        continue
    fi

    # Count number of keys in file
    NUM_KEYS=$(grep -c . "$KEY_FILE" || echo 0)
    echo "Found $NUM_KEYS API keys in $KEY_FILE"

    # Check if output already complete
    if [ -f "$OUTPUT_CSV" ]; then
        PROCESSED_ROWS=$(wc -l < "$OUTPUT_CSV")
        echo "Output file exists with $PROCESSED_ROWS rows (including header)"
        echo "Will resume from this point..."
    else
        echo "Starting fresh processing..."
    fi

    echo ""
    echo "Executing scoring script..."

    # Run the scoring script
    python scripts/scoring/score_risk_openai.py \
        --input "$INPUT_CSV" \
        --output "$OUTPUT_CSV" \
        --model "$MODEL" \
        --symbol-column "$SYMBOL_COL" \
        --text-column "$TEXT_COL" \
        --date-column "$DATE_COL" \
        --chunk-size "$CHUNK_SIZE" \
        --api-keys-file "$KEY_FILE" \
        --daily-token-limit "$DAILY_LIMIT" \
        --retry-missing "$RETRY_MISSING" \
        --retry "$RETRY" \
        --reasoning-effort "$REASONING_EFFORT" \
#        --verbose

    EXIT_CODE=$?

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ Stage $STAGE completed successfully"
    else
        echo "✗ Stage $STAGE failed with exit code $EXIT_CODE"
        exit $EXIT_CODE
    fi

    # Check if processing is complete
    if [ -f "$OUTPUT_CSV" ]; then
        FINAL_ROWS=$(wc -l < "$OUTPUT_CSV")
        echo "Current output has $FINAL_ROWS rows"

        # Optional: Check if all rows are processed (you can add more sophisticated check)
        # For now, just report the count
    fi

    echo ""
done

echo "=========================================="
echo "All stages completed!"
echo "=========================================="
echo "Final output: $OUTPUT_CSV"

# Show final statistics
if [ -f "$OUTPUT_CSV" ]; then
    TOTAL_ROWS=$(wc -l < "$OUTPUT_CSV")
    echo "Total rows in output: $TOTAL_ROWS"

    # Show sample of completed rows (optional)
    echo ""
    echo "First few rows of output:"
    head -n 5 "$OUTPUT_CSV"
fi

echo ""
echo "Done!"