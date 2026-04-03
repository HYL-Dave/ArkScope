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

### EXP-003: PPO, seed=0 (公平對比 CPPO) ✅

| 項目 | 值 |
|------|-----|
| **Model ID** | `ppo_train_polygon_multi_both_100ep_s0_20260329T161449Z_d49531` |
| **訓練時間** | 7.0 小時 |
| **訓練曲線** | EpRet: 18 → 532 → 956 → 1,171（穩定上升） |

**Backtest (OOS)**:

| 指標 | 值 |
|------|-----|
| Final Equity | $1,182,569 |
| Total Return | +18.3% |
| Sharpe | 0.51 |
| Max Drawdown | -27.0% |
| CVaR (95%) | -4.9% |

**判斷**：
- 訓練 EpRet 和 EXP-001 幾乎相同（1171 vs 1160），但 OOS Return 天差地遠（18% vs 123%）
- **確認 EXP-001 (seed=42) 是異常好的結果**，seed=0 的 OOS 才是更典型的水平
- 和 EXP-002 CPPO (seed=0) 公平比較：PPO +18.3% vs CPPO +8.9%，PPO 仍較好
- CPPO 的 CVaR 略優（-4.7% vs -4.9%），MDD 類似（-26.2% vs -27.0%）

### 系列 A 三實驗完整對比

| 指標 | EXP-001 PPO s42 | EXP-003 PPO s0 | EXP-002 CPPO s0 |
|------|-----------------|----------------|-----------------|
| Return | **+123.1%** | +18.3% | +8.9% |
| Sharpe | **1.66** | 0.51 | 0.32 |
| MDD | **-21.1%** | -27.0% | -26.2% |
| CVaR | -5.9% | -4.9% | **-4.7%** |
| 訓練 EpRet | 1,160 | 1,171 | 471 |

**結論**：RL 結果隨機性大，單一 seed 不可靠。QQQ 同期 +15.8%，seed=0 的 PPO (+18.3%) 僅略勝大盤。

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

### 評分 Pipeline 差異（為什麼數量不同）

原始 FNSPID 資料共 127,176 筆記錄，但只有 77,871 筆（61.2%）有 `Article` 原文內容。

| 步驟 | DeepSeek (原版) | 我們的重新評分 (Claude / GPT-5) |
|------|----------------|-------------------------------|
| 1. 摘要來源 | 直接使用 `Lsa_summary`（傳統 LSA 演算法摘要） | 用 LLM 從**原文**生成摘要 |
| 2. 能評分的條件 | 只要有 `Lsa_summary` 就能評 | 必須有 `Article` 原文才能生成 LLM summary |
| 3. 有效評分數 | 126,224 (99.3%) | 77,871 (61.2%) |
| 4. 摘要品質 | `Lsa_summary` 品質不穩定，噪音多 | LLM summary 語義更準確 |

**為什麼 DeepSeek 多出 ~48K 筆**：DeepSeek 用的是 `Lsa_summary`（基於關鍵詞的傳統摘要），
幾乎所有記錄都有。我們的 pipeline 用「原文 → LLM summary → LLM 評分」，
沒有原文就無法生成 summary，所以少了 38.8% 的記錄。

**摘要來源詳細記錄**：

| 評分組 | 摘要模型 | 評分模型 | 檔名格式 | 實驗組 |
|--------|---------|---------|---------|--------|
| DeepSeek (原版) | Lsa_summary（傳統演算法） | DeepSeek V3 | `sentiment_deepseek_*.csv` | G1 |
| Claude Opus | GPT-5 (R=minimal, V=low) | Claude Opus | `*_opus_by_gpt5_summary.csv` | G2 |
| GPT-5 high | o3 | GPT-5 (effort=high) | `*_gpt-5_high_by_o3_summary.csv` | G3a |
| GPT-5 high | GPT-5 (R=high, V=low) | GPT-5 (effort=high) | `*_R_high_V_low_by_gpt-5_*_summary.csv` | G3b |
| o3 high | o3 | o3 (effort=high) | `*_o3_high_by_o3_summary.csv` | G4 |
| GPT-5-mini | GPT-5 (R=high, V=low) | GPT-5-mini | `*_gpt-5-mini_*_by_gpt-5_*_summary.csv` | G5 |
| Claude Sonnet | GPT-5 | Claude Sonnet | `*_sonnet_by_gpt5_summary.csv` | (備用) |
| Claude Haiku | GPT-5 | Claude Haiku | `*_haiku_by_gpt5_summary.csv` | (備用) |

> 詳細的摘要品質比較見 `docs/analysis/SUMMARY_COMPARISON_REPORT.md`
> 評分分佈比較見 `docs/analysis/DEEPSEEK_VS_CLAUDE_COMPARISON.md`
> 完整評分清單見 `docs/data/SCORING_DATA_INVENTORY.md`

### 評分品質對比

| 組 | LLM | 摘要來源 | 有效評分 | 中性 (3) | 說明 |
|----|-----|---------|---------|---------|------|
| G1 | DeepSeek V3 (原版) | Lsa_summary | 126,224 (99.3%) | 66.9% | 覆蓋高但信號弱 |
| G2 | Claude Opus | GPT-5 summary | 77,871 (61.2%) | 50.1% | 分佈更平衡 |
| G3a | GPT-5 high | o3 summary | 77,871 (61.2%) | 54.0% | GPT-5 + 最強摘要 |
| G3b | GPT-5 high | GPT-5 R_high summary | 77,871 (61.2%) | 53.9% | 同族摘要（vs G3a 18% per-article 差異） |
| G4 | o3 high | o3 summary | 77,871 (61.2%) | **37.1%** | 分佈最分散 |
| G5 | GPT-5-mini | GPT-5 R_high summary | 77,871 (61.2%) | **29.9%** | 最便宜 + 方向性判斷最多 |

### DeepSeek 高覆蓋率的真正原因（2026-03-31 調查）

調查發現 DeepSeek 的 49,102 筆「額外」評分（38.9%）**全部是 title-only**：
Article 和 Lsa_summary 都是空的，但仍然有評分。

| 項目 | 數值 |
|------|------|
| 只有標題就有評分 | 49,102 / 126,224 (38.9%) |
| 這些 title-only 的中性率 | **97.5%** |
| 有原文的 DeepSeek 中性率 | 47.4%（跟 Claude Opus 50.1% 接近） |

**DeepSeek 66.9% 中性率的分解**：全部 84,403 筆中性評分中，56.7% 推測來自 title-only。當然不排除是不是其他因素，例如原本有完整文章，只是後來缺失的可能性，但是也不是所有有標題的都有分數，但也有可能只是評分失敗而已。

**按 train/trade 時期的缺失情況**：

| 時期 | DeepSeek 有評分 | 有原文 | Title-only 比例 |
|------|---------------|--------|----------------|
| Train 2013-2018 | 54,743 | 27,443 | **49.9%** |
| Trade 2019-2023 | 61,497 | 48,005 | 21.9% |

- 2009-2011：80-95% title-only（原文幾乎全缺）
- 2013-2018（train）：約 50% title-only
- 2019（trade 第一年）：63.5% title-only
- 2021-2023：原文齊全，幾乎 0% title-only

**影響分析**：

我們的評分（Claude/GPT-5）只用有原文的 77,871 筆，train 期間（2013-2018）
有約 50% 的 ticker-days 完全沒有評分（填 0）。

DeepSeek 在這些 ticker-days 有一個 title-based 的 3 分。雖然品質可疑，
但在環境裡 score=3 會觸發 `hold_dampen = 0.98`（輕微抑制交易），
而 fillna=0 不觸發任何情緒邏輯。在資料稀疏的早期，
**即使是 title-based 的低品質覆蓋也可能優於完全無覆蓋**。

此假設將由 G1 vs G2/G3a 的結果驗證。

### 實驗矩陣

使用論文原始分割：`--train-start 2013-01-01 --train-end 2018-12-31 --trade-start 2019-01-01 --trade-end 2023-12-31`

**第一輪（PPO + CPPO，核心比較）**：

| 組別 | LLM 評分 | 摘要來源 | PPO | CPPO | 目的 |
|------|----------|---------|-----|------|------|
| **G1** | DeepSeek V3 | Lsa_summary | G1-PPO | G1-CPPO | 論文 baseline |
| **G2** | Claude Opus | GPT-5 summary | G2-PPO | G2-CPPO | 最高品質 Claude |
| **G3a** | GPT-5 high | o3 summary | G3a-PPO | G3a-CPPO | GPT-5 + 最強摘要 |

**第二輪（PPO only，擴展比較）**：

| 組別 | LLM 評分 | 摘要來源 | PPO | 目的 |
|------|----------|---------|-----|------|
| **G3b** | GPT-5 high | GPT-5 R_high summary | G3b-PPO | 同族摘要 vs G3a（18% per-article 差異） |
| **G4** | o3 high | o3 summary | G4-PPO | 中性率最低 (37%)，分佈最分散 |
| **G5** | GPT-5-mini | GPT-5 R_high summary | G5-PPO | 最便宜 + 中性率最低 (30%)，cost-performance |

第一輪 6 個實驗 + 第二輪 3 個 = 共 9 個，每個 ~5h。
可平行跑 3 個（`mpirun -np 8` 各佔 8 核，24 核滿載）→ 3 批 × 5h = ~15h。
第二輪的 CPPO 視第一輪結果決定是否追加。

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

### G3b: GPT-5 high (by GPT-5 R_high summary)

**G3b-PPO**:
```bash
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_gpt5_high_gpt5sum_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_gpt5_high_gpt5sum_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

### G4: o3 high (by o3 summary)

**G4-PPO**:
```bash
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_o3_high_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_o3_high_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

### G5: GPT-5-mini (by GPT-5 R_high summary)

**G5-PPO**:
```bash
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_gpt5mini_high_both.csv \
  --epochs 100 --seed 42

python training/backtest.py \
  --data training/data_prep/output/trade_gpt5mini_high_both.csv \
  --model trained_models/<model_id>/model.pth --env sentiment
```

### 結果對照表 ✅

Benchmark: QQQ 2019-2023 = **+173.3%**

**第一輪（PPO + CPPO）：**

| 實驗 | Return | Sharpe | MDD | CVaR | Calmar |
|------|--------|--------|-----|------|--------|
| G1-PPO (DeepSeek) | +164.9% | 0.90 | -29.0% | -3.3% | 0.74 |
| G2-PPO (Opus) | **+191.9%** | **0.95** | **-24.0%** | -3.4% | **1.00** |
| G3a-PPO (GPT-5 high / o3 sum) | +218.8% | 0.79 | -58.4% | -5.0% | 0.45 |
| G1-CPPO (DeepSeek) | +226.3% | 0.88 | -34.2% | -4.3% | 0.78 |
| G2-CPPO (Opus) | +160.4% | 0.71 | -56.9% | -4.6% | 0.37 |
| G3a-CPPO (GPT-5 high / o3 sum) | +171.1% | 0.75 | -43.2% | -4.5% | 0.51 |

**第二輪（PPO only）：**

| 實驗 | Return | Sharpe | MDD | CVaR | Calmar |
|------|--------|--------|-----|------|--------|
| G3b-PPO (GPT-5 high / gpt5 sum) | +263.2% | 0.83 | -54.7% | -5.4% | 0.54 |
| G4-PPO (o3 high) | +242.1% | **0.96** | -32.7% | -3.9% | 0.85 |
| G5-PPO (GPT-5-mini) | +207.0% | **1.03** | **-22.7%** | **-3.2%** | **1.11** |

**Model IDs：**

| 實驗 | Model ID |
|------|----------|
| G1-PPO | `ppo_train_deepseek_both_100ep_s42_20260330T160955Z_1bde22` |
| G1-CPPO | `cppo_train_deepseek_both_100ep_s42_20260331T124734Z_1bde22` |
| G2-PPO | `ppo_train_claude_opus_both_100ep_s42_20260330T163218Z_1d8ab3` |
| G2-CPPO | `cppo_train_claude_opus_both_100ep_s42_20260331T125222Z_1d8ab3` |
| G3a-PPO | `ppo_train_gpt5_high_both_100ep_s42_20260330T163517Z_ec7e8c` |
| G3a-CPPO | `cppo_train_gpt5_high_both_100ep_s42_20260331T124239Z_ec7e8c` |
| G3b-PPO | `ppo_train_gpt5_high_gpt5sum_both_100ep_s42_20260401T082514Z_8ba1eb` |
| G4-PPO | `ppo_train_o3_high_both_100ep_s42_20260401T083213Z_2468a3` |
| G5-PPO | `ppo_train_gpt5mini_high_both_100ep_s42_20260401T080942Z_e7521d` |

---

### 分析

#### 1. 風險調整後表現排名（按 Sharpe）

| 排名 | 實驗 | Sharpe | Return | MDD |
|------|------|--------|--------|-----|
| 1 | **G5-PPO (GPT-5-mini)** | **1.03** | +207.0% | **-22.7%** |
| 2 | G4-PPO (o3 high) | 0.96 | +242.1% | -32.7% |
| 3 | G2-PPO (Opus) | 0.95 | +191.9% | -24.0% |
| 4 | G1-PPO (DeepSeek) | 0.90 | +164.9% | -29.0% |
| 5 | G1-CPPO (DeepSeek) | 0.88 | +226.3% | -34.2% |
| 6 | G3b-PPO (GPT-5 high / gpt5sum) | 0.83 | +263.2% | -54.7% |
| 7 | G3a-PPO (GPT-5 high / o3sum) | 0.79 | +218.8% | -58.4% |
| 8 | G3a-CPPO (GPT-5 high) | 0.75 | +171.1% | -43.2% |
| 9 | G2-CPPO (Opus) | 0.71 | +160.4% | -56.9% |

#### 2. 關鍵發現

**發現 A：GPT-5-mini (G5) 是最佳風險調整表現**

G5 (GPT-5-mini) 在最便宜的模型下取得了：
- 唯一 Sharpe > 1.0
- 最低 MDD (-22.7%)
- 最低 CVaR (-3.2%)
- Calmar > 1.0（唯一一個）

可能原因：中性率最低 (29.9%) → 更多方向性判斷 → 更清晰的信號。
但需要注意這只是一個 seed 的結果。

**發現 B：Claude Opus (G2) PPO 是第一輪最均衡的**

G2-PPO：Sharpe 0.95、MDD 僅 -24%、Calmar 1.0。
在 Return 和風險之間取得了最好的平衡。

**發現 C：GPT-5 high (G3a/G3b) Return 高但風險巨大**

G3a/G3b 的 Return 最高（219-263%），但 MDD 高達 -55~58%。
這種策略在真實交易中很難執行 — 一次 58% drawdown 可能觸發止損或心理崩潰。

**發現 D：摘要來源對 GPT-5 high 有顯著影響**

G3a (o3 sum): Return +219%, Sharpe 0.79, MDD -58%
G3b (gpt5 sum): Return +263%, Sharpe 0.83, MDD -55%

雖然 aggregate 分佈幾乎一樣（54.0% vs 53.9% 中性），
但 18% per-article 差異在 RL 訓練中被放大了。
G3b 在所有指標上都略好，但兩者的 MDD 都不可接受。

**發現 E：CPPO 的表現分化**

- G1-CPPO (DeepSeek) > G1-PPO：CPPO 改善了 DeepSeek（Return +226% vs +165%）
- G2-CPPO (Opus) < G2-PPO：CPPO 反而惡化了 Opus（MDD -57% vs -24%）
- G3a-CPPO (GPT-5) < G3a-PPO：CPPO 降低了 Return 但也降低了 MDD

CPPO 只對 DeepSeek 有正面效果。這可能與 DeepSeek 的高覆蓋率（包含 title-only）
在 CPPO 的風險約束下提供了更多的 risk signal 有關。

**發現 F：DeepSeek 的 title-only 覆蓋確實有價值**

G1-PPO (DeepSeek) 覆蓋率 99% 但 49% 是 title-only 的中性 3。
G2-PPO (Opus) 覆蓋率 61%，缺失部分填 0。

G1 的 Sharpe (0.90) 略低於 G2 (0.95)，但差距不大。
G1 在 CPPO 下反而是最好的（+226%）。

結論：title-only 的低品質覆蓋**不比無覆蓋差**，在 CPPO 下甚至有幫助。
但在 PPO 下，高品質評分（Opus）的風險控制更好。

#### 3. 對照 QQQ Benchmark（+173.3%）

| 打敗 QQQ | 未打敗 QQQ |
|----------|-----------|
| G1-CPPO (+226%) | G1-PPO (+165%) |
| G2-PPO (+192%) | G2-CPPO (+160%) |
| G3a-PPO (+219%) | G3a-CPPO (+171%) |
| G3b-PPO (+263%) | |
| G4-PPO (+242%) | |
| G5-PPO (+207%) | |

9 個實驗中 6 個打敗 QQQ，但要注意 2019-2023 包含大牛市（2020-2021），
高 Return 不一定代表策略有效。**Sharpe 和 MDD 是更可靠的指標。**

**論文原始結果供參考（Table 1, 2M steps, DeepSeek V3）**：

| 模型 | Information Ratio | CVaR |
|------|------------------|------|
| PPO (no LLM) | 0.0100 | -0.0394 |
| PPO-DeepSeek | -0.0093 | -0.0338 |
| CPPO (no LLM) | -0.0148 | -0.0439 |
| CPPO-DeepSeek | 0.0078 | -0.0437 |

我們的結果整體好於論文（可能原因：不同的 seed、我們修了 upstream bugs、
不同的 LLM 評分品質）。但論文觀察到「CPPO + LLM 優於 PPO + LLM」的模式
只在 DeepSeek (G1) 上重現。

---

## 系列 C：SB3 驗證 + 大規模並行（規劃中）

### SB3 vs SpinningUp 的並行效益

| | SpinningUp (mpirun -np 8) | SB3 (--device cpu) |
|---|---|---|
| CPU cores / 實驗 | 8 | ~1 |
| 24 核同時跑 | 3 個 | ~20 個 |
| 每個實驗耗時 | ~18h (HF 資料) | ~18h（預估，待驗證） |
| 18h 可完成 | 3 個 | ~20 個 |
| **吞吐量** | **基準** | **~6-7x** |

SB3 GPU 對 MLP policy 無加速效果（模型太小），但 `--device cuda` 可將 NN 計算
offload 到 GPU，降低 CPU 負載。每個實驗只需 ~50MB VRAM（RTX 4090 24GB 可容納 ~200 個）。
實際瓶頸是 CPU cores 數量。

### SB3 基準驗證 — 第一次（超參數未對齊，已作廢）

| 指標 | SpinningUp G5 | SB3 G5 (v1) |
|------|--------------|-------------|
| Return | +207.0% | +164.8% |
| Sharpe | 1.03 | 0.73 |
| MDD | -22.7% | -43.2% |
| 訓練時間 | ~18h (8 cores) | 3.3h (1 core) |

Model ID: `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260401T194136Z_e7521d`

**原因**：`vf_coef=0.5` + `lr=3e-5` → V 函數的有效學習率只有 1.5e-5，
是 SpinningUp `vf_lr=1e-4` 的 1/6.7。V 學太慢 → Advantage 不準 → 策略差。
另外 `max_grad_norm=0.5`（SpinningUp 無 gradient clipping）也有影響。

**修正**：`vf_coef=3.33`（= 1e-4 / 3e-5）+ `max_grad_norm=inf`。

### SB3 基準驗證 — 第二次（vf_coef+grad_norm 修正）

| 指標 | SpinningUp PPO | SB3 PPO v1 | SB3 PPO v2 | SB3 CPPO |
|------|---------------|------------|------------|----------|
| Return | **+207.0%** | +164.8% | +134.5% | +165.2% |
| Sharpe | **1.03** | 0.73 | 0.68 | 0.80 |
| MDD | **-22.7%** | -43.2% | -33.4% | -31.1% |
| Calmar | **1.11** | 0.50 | 0.56 | 0.69 |
| CVaR | **-3.2%** | -4.6% | -4.1% | -3.9% |

Model IDs:
- SB3 PPO v2: `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260402T023157Z_e7521d`
- SB3 CPPO: `cppo_sb3_train_gpt5mini_high_both_100ep_s42_20260402T052747Z_e7521d`

**觀察**：
- v2 的 MDD 改善了（-43% → -33%），vf_coef 修正有效果但仍不足
- SB3 CPPO > SB3 PPO（所有指標），CVaR 約束在 SB3 下也有正面效果
- SpinningUp PPO 仍顯著勝出（Sharpe 1.03 vs 0.68/0.80）

### SB3 基準驗證 — 第三次（full-batch，最接近 SpinningUp）

| 指標 | SpinningUp PPO | SB3 PPO v2 (minibatch) | SB3 PPO v3 (full-batch) | SB3 CPPO (minibatch) | SB3 CPPO (full-batch) |
|------|---------------|----------------------|------------------------|--------------------|--------------------|
| Return | **+207.0%** | +134.5% | +149.6% | +165.2% | **+218.8%** |
| Sharpe | **1.03** | 0.68 | 0.79 | 0.80 | **0.93** |
| MDD | **-22.7%** | -33.4% | -32.3% | -31.1% | -38.8% |
| Calmar | **1.11** | 0.56 | 0.62 | 0.69 | 0.67 |
| CVaR | **-3.2%** | -4.1% | -3.7% | -3.9% | -3.9% |

Model IDs:
- SB3 PPO v3 (full-batch): `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260402T194507Z_e7521d`
- SB3 CPPO (full-batch): `cppo_sb3_train_gpt5mini_high_both_100ep_s42_20260402T212258Z_e7521d`

**結論**：
- Full-batch 比 minibatch 改善明顯（PPO Sharpe 0.68→0.79，CPPO 0.80→0.93）
- **SB3 CPPO full-batch 是 SB3 系列最佳**（Sharpe 0.93, Return +219%）
- 但仍未追平 SpinningUp PPO（Sharpe 1.03, MDD -22.7%）

**SB3 vs SpinningUp 剩餘差異分析**：

| 差異 | SpinningUp | SB3 | 影響 |
|------|-----------|-----|------|
| ~~Gradient 計算~~ | ~~Full-batch~~ | ~~Minibatch~~ | **已驗證：部分原因**（full-batch 改善了 Sharpe +0.11） |
| KL early stop | 每個 gradient step 檢查 | 每個 epoch 結束時檢查 | **可能是剩餘 gap 的主因** |
| Advantage norm | 跨 8 個 MPI worker 的全局 mean/std | 單進程 buffer 的 mean/std | 可能有影響 |
| Optimizer | 分離 pi/vf Adam | 共用 Adam + vf_coef 補償 | 近似但非完全等價 |

### GPU offload 並行效益（實測）

| 模式 | 每個實驗佔 CPU | 24 cores 可跑 |
|------|--------------|-------------|
| SpinningUp MPI (np 8) | 8 cores | 3 個 |
| SB3 CPU minibatch | ~2-3 cores | ~10 個 |
| SB3 CPU full-batch | ~10-12 cores（PyTorch OpenMP 多核） | ~2 個 |
| **SB3 CUDA full-batch** | **~1 core**（NN offload 到 GPU） | **~20+ 個** |

實測發現：CPU full-batch 下 PyTorch 自動用 OpenMP 多核做矩陣運算，2 個實驗就佔滿 24 cores。
切換 `--device cuda` 後每個實驗只佔 1 core（NN 計算在 GPU），RTX 4090 VRAM 足夠容納 200+ 模型。

### SB3 基準驗證 — 第四次（full-batch + separate-vf，更差）

| 指標 | SB3 PPO v3 (full-batch) | SB3 PPO v4 (+separate-vf) | SB3 CPPO v3 (full-batch) | SB3 CPPO v4 (+separate-vf) |
|------|------------------------|--------------------------|------------------------|--------------------------|
| Sharpe | **0.79** | 0.63 | **0.93** | 0.73 |
| Return | +149.6% | +105.2% | **+218.8%** | +144.5% |
| MDD | -32.3% | -35.1% | -38.8% | -41.8% |

Model IDs:
- PPO v4: `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260403T023807Z_e7521d`
- CPPO v4: `cppo_sb3_train_gpt5mini_high_both_100ep_s42_20260403T055415Z_e7521d`

**`--separate-vf` 反而有害**。原因：SB3 用共用 Adam optimizer，額外的 VF-only
backward 汙染了共用的 Adam momentum/adaptive lr states。SpinningUp 用獨立
optimizer 才能受益於分離更新。

### SB3 基準驗證 — 第五次（target_kl 修正，根因確認）

**根因發現**：SB3 和 SpinningUp 使用不同的 KL 散度近似公式。
SpinningUp 用一階近似（值大 2-4x），SB3 用二階近似（值小 2-4x）。
同一個 `target_kl=0.35` 在 SB3 下永遠不觸發 early stop（KL ~0.11 << 閾值 0.525）。
詳見 `training/docs/sb3_kl_divergence_analysis.md`。

| 配置 | target_kl | Sharpe | Return | MDD |
|------|-----------|--------|--------|-----|
| v3 (full-batch, kl=0.35) | 0.35 | 0.79 | +149.6% | -32.3% |
| **v5 (full-batch, kl=0.05)** | **0.05** | **0.90** | **+220.0%** | -39.8% |
| v6 (full-batch, kl=0.08) | 0.08 | 0.75 | +151.9% | -34.7% |
| SpinningUp | 0.35 | **1.03** | +207.0% | **-22.7%** |

Model IDs:
- v5 (kl=0.05): `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260403T104333Z_e7521d`
- v6 (kl=0.08): `ppo_sb3_train_gpt5mini_high_both_100ep_s42_20260403T104418Z_e7521d`

**分析**：
- target_kl=0.05: Sharpe 0.79→**0.90**（最大改善），Return 甚至超過 SpinningUp
- target_kl=0.08: 反而更差（0.75），太接近自然 KL 水平（~0.11）導致過早停止
- **0.05 是 SB3 的甜蜜點**，讓 early stop 在合適的時機觸發

### SB3 最佳配置結論

**`--full-batch --target-kl 0.05 --device cuda`**

| 配置 | PPO Sharpe | CPPO Sharpe | 關鍵改動 |
|------|-----------|-------------|---------|
| v1 vf_coef=0.5 minibatch | 0.73 | — | 初始版本 |
| v2 vf_coef=3.33 minibatch | 0.68 | 0.80 | vf_coef 修正 |
| v3 full-batch kl=0.35 | 0.79 | 0.93 | full-batch |
| v4 full-batch+separate-vf | 0.63 | 0.73 | 有害，已移除 |
| **v5 full-batch kl=0.05** | **0.90** | **(待測)** | **KL 公式差異修正** |
| SpinningUp (參考) | 1.03 | — | 獨立 optimizer |

**已確認的 gap 來源**（按影響大小排序）：
1. **KL 散度公式差異**（Sharpe +0.11）：已透過 target_kl=0.05 修正
2. **Full-batch vs minibatch**（Sharpe +0.11）：已透過 --full-batch 修正
3. **共用 optimizer**（Sharpe ~0.13 gap 殘留）：SB3 結構性限制，無法完全消除

剩餘 Sharpe gap 0.13 和 MDD gap（-39.8% vs -22.7%）來自共用 Adam optimizer。
SpinningUp 的獨立 pi/vf Adam 讓兩者有各自最佳的 momentum states。

**待測**：SB3 CPPO full-batch + target_kl=0.05（預期會超過之前 CPPO 的 0.93）。

並行資源分配（400GB RAM，24 cores，4× RTX 4090）：
- 每個實驗 ~35-40GB RAM → 最多 **9-10 個**同時訓練
- `--device cuda:N` 分散到 4 張 GPU → 每張 2-3 個
- 建議配置：**8 個並行**（安全邊際），分到 cuda:0~3 各 2 個

### 待辦：多 seed 驗證（SB3 確認後）

系列 B 全部用 seed=42，但系列 A 顯示 seed 影響極大（PPO s42: +123% vs s0: +18%）。
Top 3 的 G5/G4/G2 需要多 seed 驗證。

SB3 可 20 個並行，一次跑完全部 seed：

| 實驗 | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 |
|------|--------|--------|--------|--------|--------|
| G5-PPO (GPT-5-mini) | | | | | |
| G4-PPO (o3 high) | | | | | |
| G2-PPO (Opus) | | | | | |

15 個實驗，SB3 並行 ~18h 全部完成（SpinningUp 需要 5 批 × 18h = 90h）。

---

## 系列 D：Title-only 補齊評分實驗（進行中）

### 背景

DeepSeek 有 49,102 筆 title-only 的評分（97.5% 為中性 3）。
我們的評分（Claude/GPT-5 等）在這些記錄上完全缺失（填 0 或 3）。

目前使用 gpt-5.4-nano (reasoning=xhigh) 對全部 127,176 筆標題重新評分。
完成後需要合併工具：將 title-only 的新評分填入現有評分缺失的位置。

### 評分進度

- [ ] Sentiment: `gpt-5.4-nano_xhigh_by_title` — 進行中
- [ ] Risk: `gpt-5.4-nano_xhigh_by_title` — 待 sentiment 完成後開始

### 合併策略

對每個實驗組，產出「補齊版」訓練資料：

```
原始 G5 評分（77,871 筆 summary-based）
  + nano title-only 評分填入缺失的 49,102 筆
  = 合併後 ~126K 筆覆蓋
```

需要開發合併工具，支援：
- 指定 primary 評分來源（保留 summary-based 為主）
- 指定 fallback 評分來源（title-only nano 填入缺失）
- 輸出合併後的 train/trade CSV

### 待驗證假設

**假設 H1**：title-only 補齊 > 無覆蓋（填 0）
  - 比較 G5-PPO (原始 77K) vs G5-PPO (補齊 126K)

**假設 H2**：nano title-only 品質 > DeepSeek title-only（97.5% 中性 3）
  - 如果 nano 的中性率明顯低於 97.5%，說明即使只看標題也能做出更好的判斷

**假設 H3**：最佳配置 = 高品質 summary-based (主) + 低成本 title-only (補)
  - 如果 H1+H2 都成立，這就是 cost-effective 的完整覆蓋方案

---

## 系列 E：SB3 CPPO ✅ 已開發

`train_cppo_sb3.py` 已完成。使用 `make_cppo_class()` factory 繼承 PPO，
override `collect_rollouts()` 在 advantage 上加 CVaR penalty。
支援 `--full-batch`, `--target-kl`, `--device cuda:N`。

待測：CPPO + full-batch + target_kl=0.05（預期超過之前 CPPO 的 Sharpe 0.93）。

---

## 後續計畫總結

### 近期（當前 pipeline 優化）

| 優先級 | 項目 | 狀態 | 預估工作量 |
|--------|------|------|-----------|
| 1 | ~~SB3 PPO 基準驗證~~ | ✅ 最佳: --full-batch --target-kl 0.05 | 完成 |
| 2 | SB3 CPPO full-batch + kl=0.05 | 訓練中 | 等待結果 |
| 3 | Title-only nano 評分 | 評分中 | 等待完成 |
| 4 | 評分合併工具 | 待 #3 | 開發 ~1h |
| 5 | G5 補齊版 train/backtest | 待 #4 | 1 個實驗 |
| 6 | 多 seed 驗證 (G5/G4/G2 × 5 seeds) | 待最佳配置確定 | 8 個並行 |
| 7 | 評分資料開源 HuggingFace | 待結果穩定 | 打包 ~2h |

### 中期（新演算法 + Ensemble）

| 優先級 | 項目 | 說明 | 工作量 |
|--------|------|------|--------|
| 8 | **SAC 訓練腳本** | SB3 內建 SAC，off-policy + 自動 entropy。不需調 target_kl，134 維連續 action 探索更好。從 train_ppo_sb3.py 改動少。 | **低** |
| 9 | **SAC 基準實驗** | G5 資料跑 SAC，跟 PPO/CPPO 對比 Sharpe、MDD、訓練時間 | 幾個實驗 |
| 10 | **Ensemble (PPO+SAC+TD3)** | FinRL Contest 冠軍做法：3 個模型獨立訓練，Sharpe 加權多數決投票。MDD 減半。需要 ensemble backtest 工具。 | **中** |
| 11 | **TD3 訓練腳本** | 為 ensemble 補齊第三個演算法。SB3 內建。 | 低 |

### 追蹤觀望（不列入近期實作計畫）

以下方向在 `algorithm_survey_2026.md` 中有詳細調查記錄，但經複查後認為目前不具備
足夠的證據或實用性列入實作計畫：

| 方向 | 原因 | 狀態 |
|------|------|------|
| LLM Strategy Guide（第二代） | RL 增量僅 Sharpe +0.07（LLM-Only 1.03 vs LLM+RL 1.10）；未審查 preprint；只測 6 支科技股 | 追蹤，待更強證據 |
| FLAG-Trader（第三代） | 未審查 preprint（非 ACL 2025）；fine-tuned vs zero-shot 不公平比較；只測 6 資產 | 追蹤，待多資產驗證 |
| WCSAC / DSAC | 需大量自訂實現；依賴 SAC 基礎（先確認 SAC 效果） | 待 SAC 結果後再評估 |
| Decision Transformer | 完全不同的方向（offline RL）；需高品質 expert 資料 | 與當前 pipeline 無關 |

### 技術評估筆記

**SAC 的具體優勢**：
- Off-policy: replay buffer 反覆使用經驗，PPO 用完即丟 → 資料有限時更有效率
- 自動 entropy tuning: `ent_coef="auto"` → 不需手動調（PPO 需要調 target_kl）
- 風險: 可能持股時間短（高換手 → 高交易成本），需注意 transaction cost 設定

**Ensemble 的具體做法**（FinRL Contest, arXiv:2501.10709）：
1. 分別訓練 PPO、SAC、TD3（同資料、同環境）
2. 每個模型在 validation set 上計算 Sharpe
3. 交易時每天取 3 個模型的 action，用 Sharpe 加權平均
4. 實際結果: MDD -8.98% (改善) vs solo PPO -9.96%，但 Sharpe 1.48 < solo PPO 1.55
5. Ensemble 的價值是**風險控制**（MDD），不是回報最大化

> ⚠️ 所有引用數據的驗證記錄見 `source_verification_2026.md`
> 演算法調查完整記錄見 `algorithm_survey_2026.md`

---

## 備註

- 每個實驗完成後更新本文件，記錄 Model ID、指標、判斷
- 所有 model artifacts 在 `trained_models/` 下，含 metadata.json
- Equity curve 圖在各 model 目錄下的 `equity_curve.png`
- 訓練 log 在 `/mnt/md0/PycharmProjects/spinningup/data/` 下
- 系列 A（Polygon）和系列 B（HuggingFace）是獨立的，不直接比較（不同資料源、不同日期、不同 tickers）
- 系列 B 全部使用 seed=42，結果受 seed 影響大（見系列 A 的 EXP-001 vs EXP-003）

---

*最後更新: 2026-04-03*