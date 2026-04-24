#!/usr/bin/env bash
# V-lite instrumented short-run for policy-collapse triage.
#
# Single-seed 5-epoch PPO training with tensorboard + monitor.csv telemetry
# enabled. Uses the same hyperparameters as the collapsed production runs
# so that whatever we observe reflects the actual training dynamics — this
# is a diagnostic, NOT a fix.
#
# Output artifacts land under:
#   trained_models/<model_id>/
#     tb/ppo_1/events.out.tfevents.*   (SB3 train/* + rollout/* metrics)
#     monitor.csv                       (per-episode rewards/lengths)
#     model_sb3.zip + metadata.json     (normal artifacts)
#
# Then run:
#   python scripts/analysis/extract_sb3_train_metrics.py \
#       --model-dir trained_models/<model_id>
#
# Usage:
#   bash scripts/rl_vlite_rerun.sh                                  # ext CSV (default)
#   bash scripts/rl_vlite_rerun.sh <path/to/train_csv>              # custom CSV

set -euo pipefail

DATA="${1:-training/data_prep/output/train_polygon_multi_both_ext.csv}"

if [[ ! -f "$DATA" ]]; then
  echo "ERROR: training CSV not found: $DATA" >&2
  exit 2
fi

PYTHON="${PYTHON:-/home/hyl/.virtualenvs/FinRL/bin/python}"

echo "[vlite] CSV: $DATA"
echo "[vlite] Python: $PYTHON"
echo "[vlite] 5 epochs × 20000 steps = 100k timesteps, full-batch, seed=42"

LOG_STD_INIT="${LOG_STD_INIT:-0.0}"
VECNORMALIZE_OBS="${VECNORMALIZE_OBS:-0}"

echo "[vlite] log_std_init=$LOG_STD_INIT (initial std ≈ $(python -c "import math; print(f'{math.exp($LOG_STD_INIT):.4f}')"))"
echo "[vlite] vecnormalize_obs=$VECNORMALIZE_OBS"

EXTRA_ARGS=()
if [[ "$VECNORMALIZE_OBS" == "1" ]]; then
  EXTRA_ARGS+=(--vecnormalize-obs)
fi

"$PYTHON" training/train_ppo_sb3.py \
  --data "$DATA" \
  --epochs 5 \
  --steps 20000 \
  --seed 42 \
  --device auto \
  --n-envs 1 \
  --full-batch \
  --target-kl 0.35 \
  --sentiment-scale strong \
  --log-std-init "$LOG_STD_INIT" \
  --telemetry \
  "${EXTRA_ARGS[@]}"