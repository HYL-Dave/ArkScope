#!/bin/bash
# Nanofilled training: compare nano-title-filled scores vs originals
# 5 datasets × 4 algorithms = 20 experiments, all parallel
#
# Resource: ~70GB RAM total (SAC ~8GB each, others ~2GB), 20 CPU cores
# GPUs: 5 per GPU, ~10GB VRAM each
#
# Datasets (all _both, nanofilled):
#   claude_opus_both, gpt5_high_both, gpt5_high_gpt5sum_both,
#   gpt5mini_high_both, o3_high_both
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_nanofilled.sh > training/scripts/nanofilled.log 2>&1 &
#   tail -f training/scripts/nanofilled.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

DIR="training/data_prep/output"
PPO_COMMON="--epochs 100 --full-batch --target-kl 0.05"
PIDS=()

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

# Dataset shortnames → file paths
declare -A TRAIN TRADE
for name in claude_opus_both gpt5_high_both gpt5_high_gpt5sum_both gpt5mini_high_both o3_high_both; do
    TRAIN[$name]="$DIR/train_${name}_nanofilled.csv"
    TRADE[$name]="$DIR/trade_${name}_nanofilled.csv"
done

echo "============================================================"
echo "  Nanofilled training: 5 datasets × 4 algorithms = 20"
echo "  Started: $(timestamp)"
echo "  All 20 parallel, seed=42"
echo "============================================================"
echo ""

# ── GPU assignment: round-robin across cuda:0-3 ────────────
GPU=0
next_gpu() { GPU=$(( (GPU + 1) % 4 )); }

# ── Launch all 20 ──────────────────────────────────────────

for name in claude_opus_both gpt5_high_both gpt5_high_gpt5sum_both gpt5mini_high_both o3_high_both; do
    data="${TRAIN[$name]}"

    # PPO
    echo "  PPO  $name → cuda:$GPU"
    python training/train_ppo_sb3.py --data "$data" $PPO_COMMON --device cuda:$GPU --seed 42 &
    PIDS+=($!)
    next_gpu

    # CPPO
    echo "  CPPO $name → cuda:$GPU"
    python training/train_cppo_sb3.py --data "$data" $PPO_COMMON --device cuda:$GPU --seed 42 &
    PIDS+=($!)
    next_gpu

    # SAC
    echo "  SAC  $name → cuda:$GPU"
    python training/train_sac_sb3.py --data "$data" --epochs 100 --device cuda:$GPU --seed 42 &
    PIDS+=($!)
    next_gpu

    # TD3
    echo "  TD3  $name → cuda:$GPU"
    python training/train_td3_sb3.py --data "$data" --epochs 100 --device cuda:$GPU --seed 42 &
    PIDS+=($!)
    next_gpu
done

echo ""
echo "  20 launched. PIDs: ${PIDS[*]}"
echo "  Waiting for all to complete..."
wait "${PIDS[@]}"
echo "  All training done: $(timestamp)"

# ── Backtest all ───────────────────────────────────────────

echo ""
echo "=== Backtests ==="

for name in claude_opus_both gpt5_high_both gpt5_high_gpt5sum_both gpt5mini_high_both o3_high_both; do
    trade="${TRADE[$name]}"

    # PPO
    model_dir=$(ls -td trained_models/ppo_sb3_train_${name}_nanofilled_100ep_s42_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting PPO $name"
        python training/backtest_sb3.py --data "$trade" --model "$model_dir/model_sb3.zip" --device cpu
    else
        echo "  [WARN] PPO $name model not found"
    fi

    # CPPO
    model_dir=$(ls -td trained_models/cppo_sb3_train_${name}_nanofilled_100ep_s42_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting CPPO $name"
        python training/backtest_sb3.py --data "$trade" --model "$model_dir/model_sb3.zip" --env risk --device cpu
    else
        echo "  [WARN] CPPO $name model not found"
    fi

    # SAC
    model_dir=$(ls -td trained_models/sac_sb3_train_${name}_nanofilled_100ep_s42_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting SAC $name"
        python training/backtest_sb3.py --data "$trade" --model "$model_dir/model_sb3.zip" --device cpu
    else
        echo "  [WARN] SAC $name model not found"
    fi

    # TD3
    model_dir=$(ls -td trained_models/td3_sb3_train_${name}_nanofilled_100ep_s42_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting TD3 $name"
        python training/backtest_sb3.py --data "$trade" --model "$model_dir/model_sb3.zip" --device cpu
    else
        echo "  [WARN] TD3 $name model not found"
    fi
done

# ── Summary ────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  Nanofilled training complete: $(timestamp)"
echo "  5 datasets × 4 algorithms = 20 experiments"
echo "============================================================"
echo ""
echo "Quick results:"
for algo in ppo cppo sac td3; do
    echo "--- ${algo^^} ---"
    grep -A8 "${algo}_sb3_train.*nanofilled.*Backtest Results" training/scripts/nanofilled.log 2>/dev/null \
        | grep -E "Backtest|Return|Sharpe|Drawdown" || true
done