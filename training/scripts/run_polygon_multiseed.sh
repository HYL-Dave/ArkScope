#!/bin/bash
# Polygon PPO multi-seed + n_steps comparison
# 3 batches × 10 seeds = 30 experiments
#
# Seeds: generated from master RNG to ensure wide distribution:
#   np.random.RandomState(2026).randint(0, 2**31, size=10)
#   Master seed 2026 chosen arbitrarily; any user can reproduce.
#
# n_steps comparison (one batch per value, sequential):
#   Batch 1: n_steps=20000 (current default, baseline)
#   Batch 2: n_steps=40000 (2× more env steps per update)
#   Batch 3: n_steps=60000 (3× more, lowest gradient variance)
#
# Each batch: 10 parallel PPO, ~20GB RAM, 10/48 CPU cores
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_polygon_multiseed.sh > training/scripts/polygon_multiseed.log 2>&1 &
#   tail -f training/scripts/polygon_multiseed.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

TRAIN="training/data_prep/output/train_polygon_multi_both.csv"
TRADE="training/data_prep/output/trade_polygon_multi_both.csv"
COMMON="--epochs 100 --full-batch --target-kl 0.05"

# 10 seeds from np.random.RandomState(2026).randint(0, 2**31, size=10)
SEEDS=(942082305 1145077126 1773871898 1980789688 2047133773 1988008269 381818397 889207412 2058534300 84665779)

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "============================================================"
echo "  Polygon PPO: 3 batches × 10 seeds = 30 experiments"
echo "  Started: $(timestamp)"
echo "  Seeds: master=2026, np.random.RandomState(2026).randint(0, 2^31, 10)"
echo "  n_steps: 20000 → 40000 → 60000 (sequential batches)"
echo "============================================================"

# ── Batch function ─────────────────────────────────────────

run_batch() {
    local steps=$1
    local PIDS=()
    local GPU=0

    echo ""
    echo "=== Batch: n_steps=$steps (10 parallel) ==="
    echo "  Started: $(timestamp)"

    for seed in "${SEEDS[@]}"; do
        echo "  PPO n=$steps seed=$seed → cuda:$GPU"
        python training/train_ppo_sb3.py \
            --data "$TRAIN" $COMMON \
            --steps $steps \
            --device cuda:$GPU --seed $seed &
        PIDS+=($!)
        GPU=$(( (GPU + 1) % 4 ))
    done

    echo "  10 launched. Waiting..."
    wait "${PIDS[@]}"
    echo "  Batch n=$steps training done: $(timestamp)"

    # Backtest each (models are the newest per seed)
    echo "--- Backtests n=$steps ---"
    for seed in "${SEEDS[@]}"; do
        model_dir=$(ls -td trained_models/ppo_sb3_train_polygon_multi_both_100ep_s${seed}_* 2>/dev/null | head -1)
        if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
            echo "  Backtest n=$steps seed=$seed"
            python training/backtest_sb3.py \
                --data "$TRADE" \
                --model "$model_dir/model_sb3.zip" \
                --device cpu
        else
            echo "  [WARN] n=$steps seed=$seed model not found"
        fi
    done

    echo "=== Batch n=$steps complete: $(timestamp) ==="
}

# ── Run 3 batches sequentially ─────────────────────────────

run_batch 20000
run_batch 40000
run_batch 60000

# ── Final Summary ──────────────────────────────────────────

echo ""
echo "============================================================"
echo "  All complete: $(timestamp)"
echo "  3 × 10 = 30 PPO experiments on Polygon data"
echo "============================================================"