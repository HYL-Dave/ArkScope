#!/bin/bash
# Multi-seed validation: 18 experiments in 3 batches of 6
# Uses --full-batch --target-kl 0.05 (best SB3 config)
# Distributes across 4x RTX 4090 GPUs
#
# Batch 1: CPPO s0-4 + PPO s0       (6 parallel, ~210GB RAM)
# Batch 2: PPO s1-3 + TD3 s0-2      (6 parallel, ~210GB RAM)
# Batch 3: SAC s0-4 + TD3 s3        (6 parallel, ~210GB RAM, SAC grouped)
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
echo "  Multi-seed validation (3 batches × 6 parallel)"
echo "  Started: $(timestamp)"
echo "  18 experiments: 5 CPPO + 4 PPO + 5 SAC + 4 TD3"
echo "  GPUs: cuda:0~3, ~1-2 per GPU per batch"
echo "============================================================"

# ── Batch 1: CPPO s0-4 + PPO s0 ────────────────────────────

echo ""
echo "=== Batch 1: CPPO s0-4 + PPO s0 (6 parallel) ==="
echo "  Started: $(timestamp)"

python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 0 &
PID1=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:1 --seed 1 &
PID2=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:2 --seed 2 &
PID3=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:3 --seed 3 &
PID4=$!
python training/train_cppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 4 &
PID5=$!
python training/train_ppo_sb3.py  --data "$DATA" $COMMON --device cuda:1 --seed 0 &
PID6=$!

echo "  6 launched. PIDs: $PID1 $PID2 $PID3 $PID4 $PID5 $PID6"
wait $PID1 $PID2 $PID3 $PID4 $PID5 $PID6
echo "  Batch 1 training done: $(timestamp)"

# Backtest Batch 1
echo "--- Batch 1 Backtests ---"
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

model_dir=$(ls -td trained_models/ppo_sb3_train_gpt5mini_high_both_100ep_s0_* 2>/dev/null | head -1)
if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
    echo "  Backtesting PPO seed=0: $(basename $model_dir)"
    python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
fi

echo "=== Batch 1 complete: $(timestamp) ==="
echo ""

# ── Batch 2: PPO s1-3 + TD3 s0-2 ───────────────────────────

echo "=== Batch 2: PPO s1-3 + TD3 s0-2 (6 parallel) ==="
echo "  Started: $(timestamp)"

python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:0 --seed 1 &
PID1=$!
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:1 --seed 2 &
PID2=$!
python training/train_ppo_sb3.py --data "$DATA" $COMMON --device cuda:2 --seed 3 &
PID3=$!
python training/train_td3_sb3.py --data "$DATA" --epochs 100 --device cuda:3 --seed 0 &
PID4=$!
python training/train_td3_sb3.py --data "$DATA" --epochs 100 --device cuda:0 --seed 1 &
PID5=$!
python training/train_td3_sb3.py --data "$DATA" --epochs 100 --device cuda:1 --seed 2 &
PID6=$!

echo "  6 launched. PIDs: $PID1 $PID2 $PID3 $PID4 $PID5 $PID6"
wait $PID1 $PID2 $PID3 $PID4 $PID5 $PID6
echo "  Batch 2 training done: $(timestamp)"

# Backtest Batch 2
echo "--- Batch 2 Backtests ---"
for seed in 1 2 3; do
    model_dir=$(ls -td trained_models/ppo_sb3_train_gpt5mini_high_both_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting PPO seed=$seed: $(basename $model_dir)"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

for seed in 0 1 2; do
    model_dir=$(ls -td trained_models/td3_sb3_train_gpt5mini_high_both_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting TD3 seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

echo "=== Batch 2 complete: $(timestamp) ==="
echo ""

# ── Batch 3: SAC s0-4 + TD3 s3 ─────────────────────────────

echo "=== Batch 3: SAC s0-4 + TD3 s3 (6 parallel) ==="
echo "  Started: $(timestamp)"

python training/train_sac_sb3.py --data "$DATA" --epochs 100 --device cuda:0 --seed 0 &
PID1=$!
python training/train_sac_sb3.py --data "$DATA" --epochs 100 --device cuda:1 --seed 1 &
PID2=$!
python training/train_sac_sb3.py --data "$DATA" --epochs 100 --device cuda:2 --seed 2 &
PID3=$!
python training/train_sac_sb3.py --data "$DATA" --epochs 100 --device cuda:3 --seed 3 &
PID4=$!
python training/train_sac_sb3.py --data "$DATA" --epochs 100 --device cuda:0 --seed 4 &
PID5=$!
python training/train_td3_sb3.py --data "$DATA" --epochs 100 --device cuda:1 --seed 3 &
PID6=$!

echo "  6 launched. PIDs: $PID1 $PID2 $PID3 $PID4 $PID5 $PID6"
wait $PID1 $PID2 $PID3 $PID4 $PID5 $PID6
echo "  Batch 3 training done: $(timestamp)"

# Backtest Batch 3
echo "--- Batch 3 Backtests ---"
for seed in 0 1 2 3 4; do
    model_dir=$(ls -td trained_models/sac_sb3_train_gpt5mini_high_both_100ep_s${seed}_* 2>/dev/null | head -1)
    if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
        echo "  Backtesting SAC seed=$seed"
        python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
    fi
done

model_dir=$(ls -td trained_models/td3_sb3_train_gpt5mini_high_both_100ep_s3_* 2>/dev/null | head -1)
if [ -n "$model_dir" ] && [ -f "$model_dir/model_sb3.zip" ]; then
    echo "  Backtesting TD3 seed=3"
    python training/backtest_sb3.py --data "$TRADE" --model "$model_dir/model_sb3.zip" --device cpu
fi

echo "=== Batch 3 complete: $(timestamp) ==="

# ── Final Summary ───────────────────────────────────────────

echo ""
echo "============================================================"
echo "  All multi-seed complete: $(timestamp)"
echo "  Batch 1: 5 CPPO + 1 PPO"
echo "  Batch 2: 3 PPO + 3 TD3"
echo "  Batch 3: 5 SAC + 1 TD3"
echo "  Total: 18 experiments (+ 4 existing seed=42)"
echo "============================================================"
echo ""
echo "Quick results summary:"
echo "--- CPPO ---"
grep -B1 -A3 "cppo_sb3.*Backtest Results" training/scripts/multi_seed.log 2>/dev/null | grep -E "Backtest|Return|Sharpe|Drawdown" || true
echo "--- PPO ---"
grep -B1 -A3 "ppo_sb3.*Backtest Results" training/scripts/multi_seed.log 2>/dev/null | grep -E "Backtest|Return|Sharpe|Drawdown" || true
echo "--- SAC ---"
grep -B1 -A3 "sac_sb3.*Backtest Results" training/scripts/multi_seed.log 2>/dev/null | grep -E "Backtest|Return|Sharpe|Drawdown" || true
echo "--- TD3 ---"
grep -B1 -A3 "td3_sb3.*Backtest Results" training/scripts/multi_seed.log 2>/dev/null | grep -E "Backtest|Return|Sharpe|Drawdown" || true