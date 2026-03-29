#!/bin/bash
# Series B: Cross-LLM comparison experiments
# Run all 9 experiments in 3 batches (3 parallel per batch, 8 cores each)
# Total estimated time: ~15-18 hours
#
# Usage:
#   cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
#   workon FinRL
#   nohup bash training/scripts/run_series_b.sh > training/scripts/series_b.log 2>&1 &
#   tail -f training/scripts/series_b.log

set -e
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday

TRAIN_DIR="training/data_prep/output"
MODEL_DIR="trained_models"
EPOCHS=100
SEED=42
NP=8

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

# Find latest model matching a pattern
find_model() {
    local pattern="$1"
    ls -td "$MODEL_DIR"/$pattern 2>/dev/null | head -1
}

# Run backtest for a PPO model
backtest_ppo() {
    local trade_csv="$1"
    local model_pattern="$2"
    local model_dir=$(find_model "$model_pattern")
    if [ -z "$model_dir" ]; then
        echo "  [WARN] No model found for pattern: $model_pattern"
        return 1
    fi
    echo "  Backtesting: $(basename $model_dir)"
    python training/backtest.py \
        --data "$trade_csv" \
        --model "$model_dir/model.pth" \
        --env sentiment
}

# Run backtest for a CPPO model
backtest_cppo() {
    local trade_csv="$1"
    local model_pattern="$2"
    local model_dir=$(find_model "$model_pattern")
    if [ -z "$model_dir" ]; then
        echo "  [WARN] No model found for pattern: $model_pattern"
        return 1
    fi
    echo "  Backtesting: $(basename $model_dir)"
    python training/backtest.py \
        --data "$trade_csv" \
        --model "$model_dir/model.pth" \
        --env risk
}

echo "============================================================"
echo "  Series B: Cross-LLM Comparison"
echo "  Started: $(timestamp)"
echo "  Batches: 3 (3 parallel each, $NP cores per experiment)"
echo "============================================================"

# ── Batch 1: PPO (G1, G2, G3a) ─────────────────────────────
echo ""
echo "=== Batch 1/3: PPO — G1 (DeepSeek), G2 (Opus), G3a (GPT-5 high/o3sum) ==="
echo "  Started: $(timestamp)"

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_deepseek_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G1_PPO=$!

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_claude_opus_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G2_PPO=$!

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_gpt5_high_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G3A_PPO=$!

wait $PID_G1_PPO $PID_G2_PPO $PID_G3A_PPO
echo "  Batch 1 done: $(timestamp)"

# Backtests for batch 1
echo ""
echo "--- Batch 1 Backtests ---"
backtest_ppo "$TRAIN_DIR/trade_deepseek_both.csv" "ppo_train_deepseek_both_${EPOCHS}ep_s${SEED}_*"
backtest_ppo "$TRAIN_DIR/trade_claude_opus_both.csv" "ppo_train_claude_opus_both_${EPOCHS}ep_s${SEED}_*"
backtest_ppo "$TRAIN_DIR/trade_gpt5_high_both.csv" "ppo_train_gpt5_high_both_${EPOCHS}ep_s${SEED}_*"

# ── Batch 2: CPPO (G1, G2, G3a) ────────────────────────────
echo ""
echo "=== Batch 2/3: CPPO — G1 (DeepSeek), G2 (Opus), G3a (GPT-5 high/o3sum) ==="
echo "  Started: $(timestamp)"

mpirun -np $NP python training/train_cppo_llm_risk.py \
    --data "$TRAIN_DIR/train_deepseek_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G1_CPPO=$!

mpirun -np $NP python training/train_cppo_llm_risk.py \
    --data "$TRAIN_DIR/train_claude_opus_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G2_CPPO=$!

mpirun -np $NP python training/train_cppo_llm_risk.py \
    --data "$TRAIN_DIR/train_gpt5_high_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G3A_CPPO=$!

wait $PID_G1_CPPO $PID_G2_CPPO $PID_G3A_CPPO
echo "  Batch 2 done: $(timestamp)"

# Backtests for batch 2
echo ""
echo "--- Batch 2 Backtests ---"
backtest_cppo "$TRAIN_DIR/trade_deepseek_both.csv" "cppo_train_deepseek_both_${EPOCHS}ep_s${SEED}_*"
backtest_cppo "$TRAIN_DIR/trade_claude_opus_both.csv" "cppo_train_claude_opus_both_${EPOCHS}ep_s${SEED}_*"
backtest_cppo "$TRAIN_DIR/trade_gpt5_high_both.csv" "cppo_train_gpt5_high_both_${EPOCHS}ep_s${SEED}_*"

# ── Batch 3: PPO (G3b, G4, G5) ─────────────────────────────
echo ""
echo "=== Batch 3/3: PPO — G3b (GPT-5 high/gpt5sum), G4 (o3), G5 (GPT-5-mini) ==="
echo "  Started: $(timestamp)"

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_gpt5_high_gpt5sum_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G3B_PPO=$!

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_o3_high_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G4_PPO=$!

mpirun -np $NP python training/train_ppo_llm.py \
    --data "$TRAIN_DIR/train_gpt5mini_high_both.csv" \
    --epochs $EPOCHS --seed $SEED &
PID_G5_PPO=$!

wait $PID_G3B_PPO $PID_G4_PPO $PID_G5_PPO
echo "  Batch 3 done: $(timestamp)"

# Backtests for batch 3
echo ""
echo "--- Batch 3 Backtests ---"
backtest_ppo "$TRAIN_DIR/trade_gpt5_high_gpt5sum_both.csv" "ppo_train_gpt5_high_gpt5sum_both_${EPOCHS}ep_s${SEED}_*"
backtest_ppo "$TRAIN_DIR/trade_o3_high_both.csv" "ppo_train_o3_high_both_${EPOCHS}ep_s${SEED}_*"
backtest_ppo "$TRAIN_DIR/trade_gpt5mini_high_both.csv" "ppo_train_gpt5mini_high_both_${EPOCHS}ep_s${SEED}_*"

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Series B Complete: $(timestamp)"
echo "============================================================"
echo ""
echo "Models saved in $MODEL_DIR/:"
ls -d $MODEL_DIR/ppo_train_{deepseek,claude_opus,gpt5_high,gpt5_high_gpt5sum,o3_high,gpt5mini_high}_both_* \
      $MODEL_DIR/cppo_train_{deepseek,claude_opus,gpt5_high}_both_* 2>/dev/null | while read d; do
    echo "  $(basename $d)"
done
echo ""
echo "Check results: grep -A5 'Backtest Results' training/scripts/series_b.log"