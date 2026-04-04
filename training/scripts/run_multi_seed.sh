#!/bin/bash
# Multi-seed validation: CPPO (5 seeds) + PPO (4 seeds) = 9 parallel
# Uses --full-batch --target-kl 0.05 (best SB3 config)
# Distributes across 4x RTX 4090 GPUs
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_multi_seed.sh > training/scripts/multi_seed.log 2>&1 &
#   tail -f training/scripts/multi_seed.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

DATA="training/data_prep/output/train_gpt5mini_high_both.csv"
TRADE="training/data_prep/output/trade_gpt5mini_high_both.csv"
COMMON="--epochs 100 --full-batch --target-kl 0.05"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "============================================================"
echo "  Multi-seed validation"
echo "  Started: $(timestamp)"
echo "  9 experiments: 5 CPPO + 4 PPO"
echo "  GPUs: cuda:0~3, ~2-3 per GPU"
echo "============================================================"

# ── Launch all 9 in parallel ────────────────────────────────

echo ""
echo "Launching CPPO seeds 0-4 + PPO seeds 0-3..."

# CPPO seeds 0-4 (spread across GPUs)
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 0 &
PID_C0=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:1 --seed 1 &
PID_C1=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:2 --seed 2 &
PID_C2=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:3 --seed 3 &
PID_C3=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 4 &
PID_C4=$!

# PPO seeds 0-3
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:1 --seed 0 &
PID_P0=$!
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:2 --seed 1 &
PID_P1=$!
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:3 --seed 2 &
PID_P2=$!
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 3 &
PID_P3=$!

echo "  All 9 launched. PIDs: $PID_C0 $PID_C1 $PID_C2 $PID_C3 $PID_C4 $PID_P0 $PID_P1 $PID_P2 $PID_P3"
echo "  Waiting for all to complete..."

wait $PID_C0 $PID_C1 $PID_C2 $PID_C3 $PID_C4 $PID_P0 $PID_P1 $PID_P2 $PID_P3
echo "  All training done: $(timestamp)"

# ── Backtest all ────────────────────────────────────────────

echo ""
echo "=== Running backtests ==="

# Find and backtest CPPO models
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/cppo_sb3_train_gpt5mini_high_both_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting CPPO seed=$seed: $(basename $model_dir)"
        python training/backtest_sb3.py \
            --data "$TRADE" \
            --model "$model_dir/model_sb3.zip" \
            --env risk --device cpu
    else
        echo "  [WARN] CPPO seed=$seed model not found"
    fi
done

# Find and backtest PPO models
for seed in 0 1 2 3; do
    model_dir=$(ls -td trained_models/ppo_sb3_train_gpt5mini_high_both_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting PPO seed=$seed: $(basename $model_dir)"
        python training/backtest_sb3.py \
            --data "$TRADE" \
            --model "$model_dir/model_sb3.zip" \
            --device cpu
    else
        echo "  [WARN] PPO seed=$seed model not found"
    fi
done

# ── Summary ─────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  Multi-seed complete: $(timestamp)"
echo "============================================================"
echo ""
echo "Results:"
grep -A12 "Backtest Results" training/scripts/multi_seed.log | grep -E "Backtest Results|Total Return|Sharpe|Max Drawdown"