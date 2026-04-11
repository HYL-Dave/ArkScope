#!/bin/bash
# Production ensemble: 10 PPO models, seed=None, n_steps=40K
# Full Polygon data (2022-01 ~ 2026-04), 143 tickers (IBKR price source)
#
# No seed selection, no cherry-picking. All 10 models go into ensemble.
# This is the FinRL-standard approach (diversity > selection).
#
# Resource: ~20GB RAM, 10/48 CPU cores, ~3 per GPU
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_polygon_production.sh > training/scripts/polygon_production.log 2>&1 &
#   tail -f training/scripts/polygon_production.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

TRAIN="training/data_prep/output/train_polygon_multi_both.csv"
COMMON="--epochs 100 --full-batch --target-kl 0.05 --steps 40000"
PIDS=()

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

echo "============================================================"
echo "  Production ensemble: 10 PPO, seed=None, n_steps=40K"
echo "  Data: $TRAIN (IBKR prices, 143 tickers, 2022-2026)"
echo "  Started: $(timestamp)"
echo "============================================================"
echo ""

GPU=0
for i in $(seq 1 10); do
    echo "  Model $i/10 → cuda:$GPU (no seed)"
    ~/.virtualenvs/FinRL/bin/python training/train_ppo_sb3.py \
        --data "$TRAIN" $COMMON \
        --device cuda:$GPU &
    PIDS+=($!)
    GPU=$(( (GPU + 1) % 4 ))
done

echo ""
echo "  10 launched. PIDs: ${PIDS[*]}"
echo "  Waiting for all to complete..."
wait "${PIDS[@]}"
echo "  All training done: $(timestamp)"

echo ""
echo "============================================================"
echo "  Production training complete: $(timestamp)"
echo "  10 PPO models ready for ensemble"
echo "============================================================"