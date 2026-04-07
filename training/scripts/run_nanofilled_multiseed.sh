#!/bin/bash
# Multi-seed validation for top nanofilled combinations
# 5 combinations × 5 seeds = 25 experiments, all parallel
#
# Resource: ~60GB RAM (25 × ~2GB avg), 25/48 CPU cores, 6-7 per GPU
#
# Top 5 by Sharpe (seed=42):
#   1. Claude Opus PPO   — 1.005
#   2. GPT-5 high CPPO   — 0.940
#   3. GPT-5+sum CPPO    — 0.917
#   4. GPT-5+sum PPO     — 0.913
#   5. GPT-5 high PPO    — 0.903
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_nanofilled_multiseed.sh > training/scripts/nanofilled_multiseed.log 2>&1 &
#   tail -f training/scripts/nanofilled_multiseed.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

DIR="training/data_prep/output"
PPO_COMMON="--epochs 100 --full-batch --target-kl 0.05"
PIDS=()

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "============================================================"
echo "  Nanofilled multi-seed: 5 combos × 5 seeds = 25"
echo "  Started: $(timestamp)"
echo "============================================================"
echo ""

GPU=0
next_gpu() { GPU=$(( (GPU + 1) % 4 )); }

# ── 1. Claude Opus PPO (seeds 0-4) ────────────────────────
DATA="$DIR/train_claude_opus_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    echo "  Claude Opus PPO  seed=$seed → cuda:$GPU"
    python training/train_ppo_sb3.py --data "$DATA" $PPO_COMMON --device cuda:$GPU --seed $seed &
    PIDS+=($!)
    next_gpu
done

# ── 2. GPT-5 high CPPO (seeds 0-4) ────────────────────────
DATA="$DIR/train_gpt5_high_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    echo "  GPT-5 high CPPO  seed=$seed → cuda:$GPU"
    python training/train_cppo_sb3.py --data "$DATA" $PPO_COMMON --device cuda:$GPU --seed $seed &
    PIDS+=($!)
    next_gpu
done

# ── 3. GPT-5+sum CPPO (seeds 0-4) ─────────────────────────
DATA="$DIR/train_gpt5_high_gpt5sum_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    echo "  GPT-5+sum CPPO   seed=$seed → cuda:$GPU"
    python training/train_cppo_sb3.py --data "$DATA" $PPO_COMMON --device cuda:$GPU --seed $seed &
    PIDS+=($!)
    next_gpu
done

# ── 4. GPT-5+sum PPO (seeds 0-4) ──────────────────────────
DATA="$DIR/train_gpt5_high_gpt5sum_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    echo "  GPT-5+sum PPO    seed=$seed → cuda:$GPU"
    python training/train_ppo_sb3.py --data "$DATA" $PPO_COMMON --device cuda:$GPU --seed $seed &
    PIDS+=($!)
    next_gpu
done

# ── 5. GPT-5 high PPO (seeds 0-4) ─────────────────────────
DATA="$DIR/train_gpt5_high_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    echo "  GPT-5 high PPO   seed=$seed → cuda:$GPU"
    python training/train_ppo_sb3.py --data "$DATA" $PPO_COMMON --device cuda:$GPU --seed $seed &
    PIDS+=($!)
    next_gpu
done

echo ""
echo "  25 launched. PIDs: ${PIDS[*]}"
echo "  Waiting for all to complete..."
wait "${PIDS[@]}"
echo "  All training done: $(timestamp)"

# ── Backtests ──────────────────────────────────────────────

echo ""
echo "=== Backtests ==="

# 1. Claude Opus PPO
TRADE="$DIR/trade_claude_opus_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/ppo_sb3_train_claude_opus_both_nanofilled_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting Claude Opus PPO seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

# 2. GPT-5 high CPPO
TRADE="$DIR/trade_gpt5_high_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/cppo_sb3_train_gpt5_high_both_nanofilled_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting GPT-5 high CPPO seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --env risk --device cpu
    fi
done

# 3. GPT-5+sum CPPO
TRADE="$DIR/trade_gpt5_high_gpt5sum_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/cppo_sb3_train_gpt5_high_gpt5sum_both_nanofilled_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting GPT-5+sum CPPO seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --env risk --device cpu
    fi
done

# 4. GPT-5+sum PPO
TRADE="$DIR/trade_gpt5_high_gpt5sum_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/ppo_sb3_train_gpt5_high_gpt5sum_both_nanofilled_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting GPT-5+sum PPO seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

# 5. GPT-5 high PPO
TRADE="$DIR/trade_gpt5_high_both_nanofilled.csv"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/ppo_sb3_train_gpt5_high_both_nanofilled_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting GPT-5 high PPO seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

# ── Summary ────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  Multi-seed validation complete: $(timestamp)"
echo "  5 combinations × 5 seeds = 25 experiments"
echo "============================================================"