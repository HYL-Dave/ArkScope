# 實驗記錄

追蹤所有訓練實驗、結果、和待辦事項。

## 實驗環境

- **機器**: AMD Ryzen Threadripper PRO 5965WX 24-Cores, ~400GB RAM
- **GPU**: NVIDIA RTX 4090（目前未用於訓練，SB3 版本可用）
- **框架**: SpinningUp (CPU + MPI) / SB3 PPO (GPU, 待測)
- **數據**: Polygon 2022-01 ~ 2026-03, 134 tickers, sentiment + risk (coalesce: gpt_5_2 96% + gpt_5_4 2%)

## 數據分割

```
方案 A（目前使用）:
  Train:  2022-01-01 → 2024-12-31  (36 months, 100,768 rows)
  Trade:  2025-01-01 → 2026-03-26  (15 months, 41,004 rows)
  比例:   70:30
```

---

## 已完成實驗

### EXP-001: PPO + Sentiment, Polygon, seed=42

| 項目 | 值 |
|------|-----|
| **腳本** | `train_ppo_llm.py` (SpinningUp, CPU) |
| **指令** | `mpirun -np 8 python training/train_ppo_llm.py --data .../train_polygon_multi_both.csv --epochs 100 --seed 42` |
| **Model ID** | `ppo_train_polygon_multi_both_100ep_s42_20260328T184504Z_d49531` |
| **訓練時間** | 5.4 小時 (8 MPI workers) |
| **訓練曲線** | EpRet: -3 → 147 → 851 → 1,116（穩定上升，無崩壞） |
| **Entropy** | 0.919 → 0.909（正常緩降） |

**Backtest (OOS: 2025-01 ~ 2026-03)**:

| 指標 | 值 | 評估 |
|------|-----|------|
| Final Equity | $2,230,987 | +123.1% |
| Sharpe Ratio | 1.66 | 優秀 |
| Max Drawdown | -21.1% | 可接受 |
| Calmar Ratio | 4.43 | 優秀 |
| Sortino Ratio | 2.49 | 優秀 |
| Win Rate | 56.5% | 良好 |
| CVaR (95%) | -5.9% | -- |

**同期 Benchmark**:

| | 回報 |
|---|---|
| Our PPO | +123.1% |
| QQQ | +15.8% |
| SPY | +13.7% |
| Alpha over QQQ | +107.3% |

**判斷**: 訓練過程健康，OOS 結果顯著跑贏大盤。但：
- 僅一個 seed，需要多 seed 驗證穩定性
- 2025-01~2026-03 整體偏牛市，alpha 可能被高估
- 論文顯示 PPO + 情緒在 DeepSeek 數據上反而變差，我們的正面結果可能來自不同數據源（Polygon + GPT-5.x）
- 需要無情緒 baseline 對照才能確認情緒分數的貢獻

### EXP-002: CPPO + Sentiment + Risk, Polygon, seed=0

| 項目 | 值 |
|------|-----|
| **腳本** | `train_cppo_llm_risk.py` (SpinningUp, CPU) |
| **指令** | `mpirun -np 8 python training/train_cppo_llm_risk.py --data .../train_polygon_multi_both.csv --epochs 100 --seed 0` |
| **Model ID** | `cppo_train_polygon_multi_both_100ep_s0_20260329T090355Z_d49531` |
| **訓練時間** | 4.8 小時 (8 MPI workers) |
| **訓練曲線** | EpRet: 83 → 135 → 433 → 461（穩定上升，Epoch 50 後收斂） |
| **Entropy** | 0.919 → 0.913（正常） |

**Backtest (OOS: 2025-01 ~ 2026-03)**:

| 指標 | 值 | 評估 |
|------|-----|------|
| Final Equity | $1,088,535 | +8.9% |
| Sharpe Ratio | 0.32 | 差（低於大盤 QQQ +15.8%） |
| Max Drawdown | -26.2% | 比 PPO 差 |
| Calmar Ratio | 0.28 | 差 |
| Sortino Ratio | 0.46 | 一般 |
| Win Rate | 52.9% | 一般 |
| CVaR (95%) | -4.7% | 比 PPO 好（-5.9%），符合 CVaR 約束設計 |

**判斷**: CPPO 的 OOS 表現明顯弱於 EXP-001 PPO。但注意：
- seed 不同（PPO=42, CPPO=0），不能直接歸因於演算法
- CVaR 確實改善（-4.7% vs -5.9%），風險約束在起作用
- 訓練 EpRet 較低（471 vs 1160），CVaR 約束限制了回報上限
- **需要 EXP-003 (PPO seed=0) 做公平對比**

### 對比摘要

| 指標 | EXP-001 PPO (s42) | EXP-002 CPPO (s0) |
|------|-------------------|-------------------|
| Total Return | +123.1% | +8.9% |
| Sharpe | 1.66 | 0.32 |
| Max Drawdown | -21.1% | -26.2% |
| CVaR (95%) | -5.9% | **-4.7%** |
| 訓練 EpRet | 1,160 | 471 |

---

## 待執行實驗（按優先級）

### EXP-003: PPO, seed=0 (公平對比 CPPO) ⬅ 下一個

**目的**: 用和 CPPO 相同的 seed=0 跑 PPO，才能公平比較演算法差異。
同時也驗證 EXP-001 (seed=42) 是否為異常好的結果。

```bash
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_polygon_multi_both.csv \
  --epochs 100 --seed 0
```

### EXP-004: PPO, seed=1 (穩定性驗證)

```bash
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_polygon_multi_both.csv \
  --epochs 100 --seed 1
```

### EXP-005: PPO 無情緒 Baseline

**目的**: 確認情緒分數到底有沒有幫助。把 sentiment 全部填 0，等同「無 LLM」。

**做法**: 複製 train/trade CSV，把 `llm_sentiment` 和 `llm_risk` 全部設為填充值。
或直接在 `prepare_training_data.py` 加 `--no-scores` flag。

### EXP-006: SB3 PPO GPU vs SpinningUp CPU 比較

**目的**: 驗證 SB3 版本的結果是否 comparable，以及速度差異。

```bash
python training/train_ppo_sb3.py \
  --data training/data_prep/output/train_polygon_multi_both.csv \
  --epochs 100 --device auto --seed 42
```

比較 EXP-001 (SpinningUp) vs EXP-006 (SB3) 的 Sharpe、Drawdown、訓練時間。

---

## 系列 B：HuggingFace 資料跨 LLM 比較（FNSPID 同文章，不同評分模型）

### 實驗設計

**控制變量**：同一批文章（FNSPID / benstaf/nasdaq_2013_2023）、同一批 tickers（NASDAQ 100）、
相同 train/trade 分割（論文原設定 2013-2018 / 2019-2023）、相同超參數。

**唯一變量**：哪個 LLM 做的 sentiment + risk 評分。

**目的**：驗證更好的 LLM 評分是否能改善 RL 策略效果。
結果和評分資料預計開源到 HuggingFace。

### 評分品質對比

| LLM | 評分率 | 中性 (3) 比例 | 說明 |
|-----|--------|--------------|------|
| DeepSeek V3 (原版) | 99.3% | 66.9% | 覆蓋高但信號弱，2/3 都是中性 |
| Claude Opus | 61.2% | 50.1% | 分佈更平衡，辨別力更好 |
| GPT-5 high | 61.2% | 54.0% | 類似 Opus，稍偏中性 |

### 實驗矩陣

使用論文原始分割：`--train-start 2013-01-01 --train-end 2018-12-31 --trade-start 2019-01-01 --trade-end 2023-12-31`

| 組別 | LLM 評分 | PPO | CPPO | 目的 |
|------|----------|-----|------|------|
| **G1** | DeepSeek V3 (原版) | G1-PPO | G1-CPPO | 重現論文 baseline |
| **G2** | Claude Opus | G2-PPO | G2-CPPO | 最高品質 Claude 評分 |
| **G3** | GPT-5 high | G3-PPO | G3-CPPO | GPT 系列最高 effort |

共 6 個實驗，每個 ~5h。可平行跑 2-3 個（`mpirun -np 8` 各佔 8 核，24 核可跑 3 個）。

### G1: DeepSeek V3 (原版 baseline)

**G1-PPO**:
```bash
python -m training.data_prep.prepare_training_data \
  --source huggingface --score-type both

mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_deepseek_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_deepseek_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

**G1-CPPO**:
```bash
mpirun -np 8 python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_deepseek_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_deepseek_both.csv \
  --model trained_models/<model_id>/model.pth --env risk
```

### G2: Claude Opus

**G2-PPO**:
```bash
python -m training.data_prep.prepare_training_data \
  --source claude --model opus --score-type both

mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_claude_opus_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_claude_opus_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

**G2-CPPO**:
```bash
mpirun -np 8 python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_claude_opus_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_claude_opus_both.csv \
  --model trained_models/<model_id>/model.pth --env risk
```

### G3: GPT-5 high

**G3-PPO**:
```bash
python -m training.data_prep.prepare_training_data \
  --source gpt5 --model high --score-type both

mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_gpt5_high_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_gpt5_high_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

**G3-CPPO**:
```bash
mpirun -np 8 python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_gpt5_high_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_gpt5_high_both.csv \
  --model trained_models/<model_id>/model.pth --env risk
```

### 結果對照表（待填）

| 實驗 | Return | Sharpe | MDD | CVaR | 訓練時間 |
|------|--------|--------|-----|------|---------|
| G1-PPO (DeepSeek) | | | | | |
| G1-CPPO (DeepSeek) | | | | | |
| G2-PPO (Opus) | | | | | |
| G2-CPPO (Opus) | | | | | |
| G3-PPO (GPT-5 high) | | | | | |
| G3-CPPO (GPT-5 high) | | | | | |

**論文原始結果（Table 1, 2M steps）供參考**：

| 模型 | Information Ratio | CVaR |
|------|------------------|------|
| PPO (no LLM) | 0.0100 | -0.0394 |
| PPO-DeepSeek | -0.0093 | -0.0338 |
| CPPO (no LLM) | -0.0148 | -0.0439 |
| CPPO-DeepSeek | 0.0078 | -0.0437 |

### 後續擴展（視結果決定）

如果 G2/G3 明顯優於 G1，可追加弱模型組做 cost-performance 分析：
- GPT-5 minimal（最低成本 GPT）
- Claude Haiku（最低成本 Claude）
- Claude Sonnet（中間檔）

---

## 備註

- 每個實驗完成後更新本文件，記錄 Model ID、指標、判斷
- 所有 model artifacts 在 `trained_models/` 下，含 metadata.json
- Equity curve 圖在各 model 目錄下的 `equity_curve.png`
- 訓練 log 在 `/mnt/md0/PycharmProjects/spinningup/data/` 下
- 系列 A（Polygon）和系列 B（HuggingFace）是獨立的，不直接比較（不同資料源、不同日期、不同 tickers）

---

*最後更新: 2026-03-29*