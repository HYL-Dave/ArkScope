#!/usr/bin/env bash
# Wrapper script to train RL agents on LLM-enhanced dataset
# Usage: train.sh <merged_dataset.csv> <algorithm> <mode>
#   algorithm: ppo or cppo
#   mode: sentiment or risk
#
# Run from project root:
#   ./training/scripts/train.sh <dataset.csv> ppo sentiment

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRAINING_DIR="$PROJECT_ROOT/training"

if [ $# -ne 3 ]; then
  echo "Usage: $0 <merged_dataset.csv> <algorithm> <mode>"
  echo "  algorithm: ppo or cppo"
  echo "  mode: sentiment or risk"
  exit 1
fi

DATA=$1
ALG=$2
MODE=$3

echo "Training $ALG with $MODE signals using dataset $DATA"
echo "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

case "$ALG" in
  ppo)
    if [ "$MODE" = "sentiment" ]; then
      cp "$DATA" train_data_deepseek_sentiment_2013_2018.csv
      mpirun -np 8 python -m training.train_ppo_llm
    else
      echo "PPO mode 'risk' not supported; use 'sentiment'"
      exit 1
    fi
    ;;
  cppo)
    if [ "$MODE" = "risk" ]; then
      cp "$DATA" train_data_deepseek_risk_2013_2018.csv
      mpirun -np 8 python -m training.train_cppo_llm_risk
    else
      echo "CPPO mode 'sentiment' not supported; use 'risk'"
      exit 1
    fi
    ;;
  *)
    echo "Unknown algorithm: $ALG (choose ppo or cppo)"
    exit 1
    ;;
esac