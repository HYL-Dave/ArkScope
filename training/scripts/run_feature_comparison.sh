#!/bin/bash
# A/B feature comparison: baseline (8 indicators) vs extended (+ATR +volume_ratio +sector_return)
# 5 seeds × 2 groups = 10 PPO models, then backtest on trade split
#
# Data: Polygon 2022-2026, IBKR prices, 143 tickers
#   Train: 2022-01-01 → 2024-12-31
#   Trade: 2025-01-01 → 2026-04-14
#
# Resource: ~20GB RAM, 10/48 CPU cores, 2-3 per GPU
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   nohup bash training/scripts/run_feature_comparison.sh > training/scripts/feature_comparison.log 2>&1 &
#   tail -f training/scripts/feature_comparison.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
PYTHON=~/.virtualenvs/FinRL/bin/python

TRAIN_BASE="training/data_prep/output/train_polygon_multi_both.csv"
TRADE_BASE="training/data_prep/output/trade_polygon_multi_both.csv"
TRAIN_EXT="training/data_prep/output/train_polygon_multi_both_ext.csv"
TRADE_EXT="training/data_prep/output/trade_polygon_multi_both_ext.csv"

COMMON="--epochs 100 --full-batch --target-kl 0.05 --steps 40000"
SEEDS=(42 0 1 2 3)

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "============================================================"
echo "  Feature A/B Comparison: baseline vs extended"
echo "  Seeds: ${SEEDS[*]}"
echo "  Started: $(timestamp)"
echo "============================================================"
echo ""

# ── Step 1: Generate baseline data (if not exists) ──
if [ ! -f "$TRAIN_BASE" ] || [ ! -f "$TRADE_BASE" ]; then
    echo "  Generating baseline data..."
    python -m training.data_prep.prepare_training_data \
        --source polygon --score-type both --price-source ibkr \
        --train-start 2022-01-01 --train-end 2024-12-31 \
        --trade-start 2025-01-01 --trade-end 2026-04-14 \
        --baseline
    echo "  Baseline data ready: $(timestamp)"
    echo ""
fi

# ── Step 2: Train baseline models (5 seeds) ──
echo "  === Training BASELINE (8 indicators) ==="
PIDS=()
GPU=0
for seed in "${SEEDS[@]}"; do
    echo "  Baseline seed=$seed → cuda:$GPU"
    $PYTHON training/train_ppo_sb3.py \
        --data "$TRAIN_BASE" $COMMON \
        --seed $seed --device cuda:$GPU &
    PIDS+=($!)
    GPU=$(( (GPU + 1) % 4 ))
done

echo "  5 baseline launched. Waiting..."
wait "${PIDS[@]}"
echo "  Baseline training done: $(timestamp)"
echo ""

# ── Step 3: Train extended models (5 seeds) ──
echo "  === Training EXTENDED (+ATR +volume_ratio +sector_return) ==="
PIDS=()
GPU=0
for seed in "${SEEDS[@]}"; do
    echo "  Extended seed=$seed → cuda:$GPU"
    $PYTHON training/train_ppo_sb3.py \
        --data "$TRAIN_EXT" $COMMON \
        --seed $seed --device cuda:$GPU &
    PIDS+=($!)
    GPU=$(( (GPU + 1) % 4 ))
done

echo "  5 extended launched. Waiting..."
wait "${PIDS[@]}"
echo "  Extended training done: $(timestamp)"
echo ""

# ── Step 4: Backtest all models ──
echo "  === Backtesting ==="

echo "  Baseline backtests:"
for model_dir in trained_models/ppo_sb3_train_polygon_multi_both_100ep_s{42,0,1,2,3}_*; do
    if [ -d "$model_dir" ] && [[ ! "$model_dir" == *"_ext_"* ]] && [[ ! "$model_dir" == *"srnd"* ]]; then
        model_zip="$model_dir/model_sb3.zip"
        if [ -f "$model_zip" ]; then
            echo "    $(basename $model_dir)"
            $PYTHON training/backtest_sb3.py \
                --data "$TRADE_BASE" --model "$model_zip" 2>&1 | grep -E "Sharpe|Annual"
        fi
    fi
done

echo ""
echo "  Extended backtests:"
for model_dir in trained_models/ppo_sb3_train_polygon_multi_both_ext_100ep_s{42,0,1,2,3}_*; do
    if [ -d "$model_dir" ]; then
        model_zip="$model_dir/model_sb3.zip"
        if [ -f "$model_zip" ]; then
            echo "    $(basename $model_dir)"
            $PYTHON training/backtest_sb3.py \
                --data "$TRADE_EXT" --model "$model_zip" 2>&1 | grep -E "Sharpe|Annual"
        fi
    fi
done

echo ""
echo "============================================================"
echo "  Feature comparison complete: $(timestamp)"
echo "============================================================"