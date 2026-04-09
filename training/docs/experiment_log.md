# 實驗記錄

追蹤所有訓練實驗、結果、和待辦事項。

## 實驗環境

- **機器**: AMD Ryzen Threadripper PRO 5965WX 24-Cores (48 threads), 503GB RAM
- **GPU**: 4× NVIDIA RTX 4090 24GB（SB3 訓練用 `--device cuda:N`）
- **框架**: SB3 (PPO/CPPO/SAC/TD3, GPU) — SpinningUp 已棄用
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

### 已取消的 Polygon 實驗

以下實驗在系列 A 時規劃但未執行，原因是已轉向 SB3 + HuggingFace 資料進行系統性驗證。
系列 A 的結論（seed 影響極大）已由後續多 seed 驗證（18+25 實驗）充分確認。

- ~~EXP-004: PPO seed=1~~ → 被多 seed 驗證取代
- ~~EXP-005: 無情緒 Baseline~~ → 待 Polygon 下一階段實驗
- ~~EXP-006: SB3 vs SpinningUp~~ → SB3 已成為標準框架，SpinningUp 已棄用

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

## 系列 C：SB3 驗證 + 大規模並行 ✅ 完成

### SB3 vs SpinningUp 的並行效益

| | SpinningUp (mpirun -np 8) | SB3 (--device cuda) |
|---|---|---|
| CPU cores / 實驗 | 8 | ~1 |
| RAM / 實驗 | ~2GB | PPO/CPPO/TD3 ~1-2GB, SAC ~8GB |
| 48 核同時跑 | 6 個 | ~25-30 個 |
| 每個實驗耗時 | ~18h (HF 資料) | PPO/CPPO ~3-5h, SAC ~19h, TD3 ~8h |
| **吞吐量** | **基準** | **~20-30x** |

SB3 `--device cuda` 將 NN 計算 offload 到 GPU，降低 CPU 負載。
每個實驗 VRAM: PPO ~1.2GB, SAC ~8.1GB。瓶頸是 CPU cores。

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

**`--separate-vf` 反而有害**。原因可能是額外的 VF-only backward 改變了 vf 參數的
Adam momentum states，使後續 combined loss 的 update 方向偏移。
（注意：Adam 的 per-parameter states 在同一 optimizer 中不會跨參數干擾，
但額外的 update 步驟本身改變了優化軌跡。）

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
| **v5 full-batch kl=0.05** | **0.90** | **0.98** | **KL 公式差異修正** |
| SpinningUp (參考) | 1.03 | — | 獨立 optimizer |

**已確認的 gap 來源**（按影響大小排序）：
1. **KL 散度公式差異**（Sharpe +0.11）：已透過 target_kl=0.05 修正
2. **Full-batch vs minibatch**（Sharpe +0.11）：已透過 --full-batch 修正
3. **剩餘 gap 原因未確定**（Sharpe ~0.13, MDD ~17%）：見下方分析

~~之前歸因為「共用 Adam optimizer 限制」，但經分析 Adam 的 per-parameter states
不會互相影響（每個 weight 有獨立的 m 和 v），且 vf_coef 的梯度縮放在 Adam 下
會被約掉（尺度不變性）。此歸因已撤回。~~

剩餘 gap 的可能來源（未驗證）：
- MPI advantage normalization（8 worker 的跨軌跡統計 vs 單進程）
- Seed 隨機性（系列 A 顯示單一 seed 不可靠）
- Update 順序（SpinningUp 先完成所有 pi 更新再做 vf，SB3 每步同時更新）

**已測**：SB3 CPPO full-batch + target_kl=0.05 → **Sharpe 0.98, Return +271%**（超過 v3 的 0.93）。
Model ID: `cppo_sb3_train_gpt5mini_high_both_100ep_s42_20260403T160516Z_e7521d`

並行資源分配：
- 每個實驗 ~1-2GB RAM、~1-2GB VRAM（修復 state_memory leak 後）
- 瓶頸是 **CPU 核心**（每個實驗 100% 佔用 1 core），不是 RAM 或 VRAM
- `--device cuda:N` 分散到 4 張 GPU → 每張可跑 12+ 個（VRAM 不是限制）
- 實際配置：**3 批 × 6 並行**（按演算法速度分組，SAC 集中在同一批）

> 注意：修復前因 `state_memory` 未在 `reset()` 清空，每個進程會洩漏 ~71GB RAM
> （2M timesteps × 985-dim state × Python float），導致 9 並行時 OOM 當機。
> 修復：commit 900c48d。

### 多 seed 驗證結果（2026-04-05 完成）

18 個實驗（3 批 × 6 並行），全部使用 SB3 + `--full-batch --target-kl 0.05`。
資料：`train_gpt5mini_high_both.csv` (82 stocks)，回測：`trade_gpt5mini_high_both.csv`。

#### CPPO (seeds 0-4)

| Seed | Return | Sharpe | MDD |
|------|--------|--------|-----|
| 0 | +173.9% | 0.776 | -42.7% |
| 1 | +96.7% | 0.509 | -53.6% |
| 2 | +127.9% | 0.606 | -49.6% |
| 3 | +140.5% | 0.686 | -41.9% |
| 4 | +205.4% | 0.823 | -35.9% |
| **Mean±Std** | **148.9±41.1%** | **0.680±0.121** | **-44.7±6.7%** |

#### PPO (seeds 0-3)

| Seed | Return | Sharpe | MDD |
|------|--------|--------|-----|
| 0 | +187.5% | 0.832 | -44.2% |
| 1 | +199.5% | 0.849 | -40.8% |
| 2 | +197.8% | 0.799 | -36.7% |
| 3 | +122.6% | 0.629 | -43.1% |
| **Mean±Std** | **176.8±36.0%** | **0.777±0.098** | **-41.2±3.3%** |

#### SAC (seeds 0-4)

| Seed | Return | Sharpe | MDD |
|------|--------|--------|-----|
| 0 | +169.6% | 0.831 | -36.5% |
| 1 | +174.0% | 0.795 | -39.4% |
| 2 | +159.3% | 0.799 | -35.3% |
| 3 | +147.0% | 0.766 | -36.0% |
| 4 | +111.5% | 0.706 | -30.4% |
| **Mean±Std** | **152.3±24.4%** | **0.780±0.047** | **-35.5±3.3%** |

#### TD3 (seeds 0-3)

| Seed | Return | Sharpe | MDD |
|------|--------|--------|-----|
| 0 | +140.6% | 0.752 | -34.3% |
| 1 | +144.3% | 0.752 | -33.3% |
| 2 | +151.5% | 0.770 | -36.1% |
| 3 | +139.4% | 0.751 | -32.1% |
| **Mean±Std** | **143.9±5.3%** | **0.756±0.009** | **-33.9±1.7%** |

#### 跨算法比較（多 seed 平均）

| 算法 | Sharpe (mean±std) | Return (mean) | MDD (mean) | Seed 穩定性 |
|------|-------------------|---------------|------------|-------------|
| SAC | **0.780±0.047** | +152.3% | -35.5% | 穩定 |
| PPO | 0.777±0.098 | **+176.8%** | -41.2% | 中等 |
| TD3 | 0.756±0.009 | +143.9% | **-33.9%** | **最穩定** |
| CPPO | 0.680±0.121 | +148.9% | -44.7% | 波動最大 |

#### 關鍵發現

1. **SAC 和 PPO 平均 Sharpe 幾乎一樣**（0.780 vs 0.777），但 SAC 穩定得多（std 0.047 vs 0.098）
2. **TD3 最穩定**（Sharpe std 0.009，MDD std 1.7%），但報酬和 Sharpe 略低
3. **CPPO 多 seed 下表現最差**（Sharpe 0.680±0.121），seed=42 的 0.98 是異常值
4. **seed=42 結果有偏**：CPPO 0.98、PPO 0.90 都在各自分佈上端，不可作為算法代表值
5. **MDD 排序**：TD3 (-33.9%) < SAC (-35.5%) < PPO (-41.2%) < CPPO (-44.7%)
6. **SAC 記憶體較高**：~8GB RAM/process（1M replay buffer），其他算法 ~1-2GB

> 結論：綜合 Sharpe、穩定性和 MDD，**SAC 是最佳選擇**（高 Sharpe + 低波動 + 低 MDD）。
> TD3 適合風險厭惡場景（最低 MDD 和最高穩定性）。CPPO 的 CVaR 約束在此資料上無正面效果。

---

## 系列 D：Title-only 補齊評分實驗 ✅ 完成

### 背景

DeepSeek 有 49,102 筆 title-only 的評分（97.5% 為中性 3）。
我們的評分（Claude/GPT-5 等）在這些記錄上完全缺失（填 0 或 3）。

使用 gpt-5.4-nano (reasoning=xhigh) 對全部 127,176 筆標題評分完成。
`fill_missing_scores.py --all` 產出 `_nanofilled` 版本（原始檔案不動）。

### 評分完成

- [x] Sentiment: 127,176 / 127,176 ✅
- [x] Risk: 127,176 / 127,176 ✅

填補效果：HuggingFace 各資料集 sentiment 覆蓋率 18.5% → 37.6%（train +23,612 行）。
仍有 ~77K 行缺失 = 該 (date, tic) 完全無新聞文章，無法補齊。

### Nanofilled 訓練結果（20 experiments, seed=42, 2026-04-07）

5 個資料集 × 4 算法，全部使用 SB3 + `--full-batch --target-kl 0.05`。
排除 DeepSeek（比較對象）和 Polygon（不同資料源）。

#### Sharpe Ratio 總表

| Dataset | PPO | CPPO | TD3 | SAC |
|---------|-----|------|-----|-----|
| claude_opus | **1.005** | 0.887 | 0.721 | 0.521 |
| gpt5_high | 0.903 | **0.940** | 0.778 | 0.712 |
| gpt5_high_gpt5sum | 0.913 | 0.917 | 0.803 | 0.481 |
| gpt5mini_high | 0.896 | 0.874 | 0.798 | 0.639 |
| o3_high | 0.825 | 0.810 | 0.784 | 0.734 |
| **平均** | **0.908** | **0.886** | **0.777** | **0.617** |

#### Return 總表

| Dataset | PPO | CPPO | TD3 | SAC |
|---------|-----|------|-----|-----|
| claude_opus | +266% | +226% | +148% | +74% |
| gpt5_high | +261% | +278% | +167% | +127% |
| gpt5_high_gpt5sum | +248% | +249% | +175% | +69% |
| gpt5mini_high | +205% | +287% | +173% | +111% |
| o3_high | +291% | +229% | +169% | +150% |

#### MDD 總表

| Dataset | PPO | CPPO | TD3 | SAC |
|---------|-----|------|-----|-----|
| claude_opus | -37.7% | -48.4% | -38.6% | **-32.5%** |
| gpt5_high | -48.8% | -46.4% | **-37.9%** | -36.5% |
| gpt5_high_gpt5sum | -44.5% | -47.4% | **-35.5%** | -42.3% |
| gpt5mini_high | **-37.2%** | -51.4% | -37.4% | -39.1% |
| o3_high | -56.2% | -50.7% | **-37.8%** | -44.4% |

#### 觀察（⚠️ 全部為 seed=42 單次結果，存在 seed bias）

1. Claude Opus + PPO Sharpe 1.005（seed=42），但多 seed 驗證後平均僅 0.757±0.073
2. PPO 在 nanofilled 上 seed=42 平均 0.908，但這很可能受 seed=42 系統性偏高影響
3. SAC 在 nanofilled 上 0.617（原始 0.780）— 退化可能是真的，也可能是 seed 效應
4. LLM 排名需要多 seed 驗證才可信（目前只有 seed=42 的單點比較）
5. TD3 跨資料集 Sharpe 0.72-0.80，MDD 最低 — 穩定性觀察可能較可靠

#### 與原始資料比較（gpt5mini_high_both, seed=42）

| 算法 | 原始 | Nanofilled | 變化 |
|------|------|-----------|------|
| PPO | 0.90 | 0.896 | ≈持平 |
| CPPO | 0.98 | 0.874 | -0.11 |
| TD3 | 0.77 | 0.798 | +0.03 |
| SAC | 0.76 | 0.639 | **-0.12** |

> gpt5mini 的 nanofill 效果不明顯（填補比例低，且 nano 品質可能弱於 summary-based）。
> 真正的收益在跨 LLM 比較：Claude Opus nanofilled 比 gpt5mini 原始高出 +0.10 Sharpe。

### 假設驗證

**H1**：title-only 補齊 vs 無覆蓋 → **部分成立**
  - PPO/TD3 持平或微升，CPPO/SAC 下降。填補不是萬靈丹，取決於算法對信號分佈的敏感度。

**H2**：nano title-only 品質 > DeepSeek title-only → **待定**
  - nano 中性率 60.8%（vs DeepSeek 97.5%），但低中性率不等於高品質。
  - DeepSeek 可能正確判斷 title-only 文章缺乏明確信號而給中性分。
  - nano 可能過度解讀標題。需要透過訓練結果驗證實際品質差異。

**H3**：高品質 summary + 低成本 title 補齊 → **待定**
  - Claude Opus + nano fill + PPO = Sharpe 1.005，但缺少 Claude Opus 原始（未填補）的 SB3 基線。
  - 需要對比 nanofilled vs 原始才能確認填補本身是否有正面效果。

### Nanofilled 多 seed 驗證（2026-04-07，25 experiments）

Top 5 組合 × 5 seeds (0-4)，驗證 seed=42 結果的代表性。

| 組合 | s0 | s1 | s2 | s3 | s4 | **Mean±Std** | s42 |
|------|----|----|----|----|-----|-------------|-----|
| Claude Opus PPO | 0.835 | 0.652 | 0.704 | 0.803 | 0.789 | **0.757±0.073** | 1.005 |
| GPT-5 high CPPO | **1.022** | 0.503 | 0.609 | 0.544 | 0.824 | **0.700±0.215** | 0.940 |
| GPT-5+sum PPO | 0.843 | 0.737 | 0.606 | 0.600 | 0.780 | **0.713±0.103** | 0.913 |
| GPT-5+sum CPPO | 0.670 | 0.567 | 0.563 | 0.605 | 0.807 | **0.642±0.100** | 0.917 |
| GPT-5 high PPO | 0.808 | 0.285 | 0.680 | 0.540 | 0.791 | **0.621±0.212** | 0.903 |

**seed=42 全部偏高**：5 個組合的 s42 結果都在分佈上端或遠超平均，確認不具代表性。

#### 穩定性排名

| 排名 | 組合 | Mean Sharpe | Std |
|------|------|-----------|-----|
| 1 | **Claude Opus PPO** | **0.757** | **0.073** |
| 2 | GPT-5+sum PPO | 0.713 | 0.103 |
| 3 | GPT-5 high CPPO | 0.700 | 0.215 |
| 4 | GPT-5+sum CPPO | 0.642 | 0.100 |
| 5 | GPT-5 high PPO | 0.621 | 0.212 |

#### 分析與反思

**1. CPPO 的 CVaR 約束未必有效**

股票市場的複雜性遠超模擬環境。CPPO 的風險懲罰基於 LLM risk score，但：
- Risk score 本身的品質和校準未驗證（不同 LLM 給出不同分數，誰對？）
- 對高風險的行為懲罰可能同時懲罰了高報酬機會
- 多 seed 下 CPPO std (0.100-0.215) 始終高於同資料的 PPO，說明約束增加了不穩定性

**2. Seed 敏感度的兩種解釋**

(a) **初始化非常重要**：神經網路初始權重決定了優化軌跡，不同起點可能收斂到
    品質差距巨大的局部最優。對金融這種信噪比極低的領域尤其嚴重。

(b) **方法本身不穩定**：RL 用有限的交易日數據學習策略，樣本效率低，
    微小的隨機差異被放大。不是初始化的問題，而是學習過程的固有缺陷。

兩者可能同時存在。FinRL GitHub Issue #190 報告了 DDPG 同一超參數不同 seed 的
Sharpe 從 0.16 到 2.39（15 倍差距），說明這不是我們的特例。

**3. PPO 的穩健性**

跨所有實驗（原始 + nanofilled + 多 seed），PPO 從未是最高但也從未災難性失敗：
- 不像 CPPO 那樣 seed 依賴極強
- 不像 SAC 那樣在 nanofilled 上整體退化
- 不像 TD3 那樣 Sharpe 天花板偏低
PPO 是「不敢說最好，但沒有劣勢」的算法。

**4. LLM 評分品質的影響可能被低估**

Claude Opus 在 seed=42 nanofilled 實驗中排名第一，但這是單 seed 觀察。
不同 LLM 的評分標準差異（什麼算「正面」？什麼算「高風險」？）
可能比算法選擇更重要。Sonnet 4.5 評分資料已存在（77,871 行），但尚未用於訓練。

**5. 對本輪實驗方法論的反思**

我們犯了幾個常見的 RL 評估錯誤：
- 過度依賴 seed=42 的單點結果做結論（series B/D/E 全部如此）
- 用回測數據同時選模型和報告結果（ensemble top-K selection bias）
- 沒有三段式 train/validation/test 分割

這些問題不影響實驗資料本身的價值，但影響結論的可信度。
未來實驗應採用 Agarwal et al. 2021 的 IQM + CI 報告方式，
並用 held-out test period 做最終評估。

#### 文獻參考：Seed 敏感度是 RL 的已知問題

| 論文 | 發現 |
|------|------|
| Henderson et al. 2018 "Deep RL that Matters" (AAAI) | 同一超參不同 seed 可產生統計上不同的分佈；多數論文用 <5 seeds |
| Colas et al. 2018 "How Many Random Seeds?" | 可靠結論需 10-20 seeds，取決於效應量和統計檢定力 |
| Agarwal et al. 2021 (NeurIPS Outstanding Paper) | Mean/median over 3-5 seeds 不可靠；推薦 IQM + bootstrap CI |
| Bjorck et al. 2022 "Is High Variance Unavoidable?" (ICLR) | Variance 來自早期數值不穩定；penultimate feature normalization 可降低 |
| Holzer et al. 2025 (FinRL Contest) | Ensemble 的 std 約為單一 agent 的一半；RL 策略對 seed 敏感是已知前提 |
| FinRL Issue #190 | DDPG 同一設定不同 seed：Sharpe 0.16 ~ 2.39 |

**結論**：Seed 敏感度不是 bug，是 RL 的固有特性。「如何選種子或降低 seed 敏感度」
是活躍的研究方向，已知的緩解方式包括：
- Ensemble（多 seed 組合，FinRL Contest 的主流做法）
- Penultimate feature normalization（Bjorck et al. 2022）
- 更大的 batch / 更多並行環境（降低 gradient variance）
- 報告 IQM + CI 而非 mean（Agarwal et al. 2021）

---

## 系列 E：SB3 CPPO ✅ 已開發

`train_cppo_sb3.py` 已完成。使用 `make_cppo_class()` factory 繼承 PPO，
override `collect_rollouts()` 在 advantage 上加 CVaR penalty。
支援 `--full-batch`, `--target-kl`, `--device cuda:N`。

✅ 已測：CPPO full-batch + target_kl=0.05 → seed=42 Sharpe 0.98（但多 seed 平均 0.680±0.121，不穩定）。

---

## 系列 F：Polygon PPO 多 seed + n_steps 對比（規劃中）

### 目標

回到 Polygon 自有資料（134 tickers, 2022-2024），用 PPO 做系統性驗證：
1. 確認 PPO 在不同資料源上的表現
2. 比較 n_steps (20K/40K/60K) 對 gradient variance 的影響
3. 為最終 Ensemble 建立模型池

### Seed 選擇方法

放棄連續整數 (0-9)，改用 **Master RNG 生成法**確保 seed 散佈在 2^31 空間：

```python
import numpy as np
rng = np.random.RandomState(2026)  # master seed = 2026
seeds = rng.randint(0, 2**31, size=10)
# → [942082305, 1145077126, 1773871898, 1980789688, 2047133773,
#    1988008269, 381818397, 889207412, 2058534300, 84665779]
```

理由：
- 現代 PRNG (MT19937) 中不同 seed 數學上已統計獨立
- 但大間隔 seed 在 PyTorch seeding pipeline 的 hash 過程中 collision 機率更低
- Master seed 固定 → 完全可重現
- 10 個 seed 覆蓋 92% 的 2^31 空間（span: 1.97B / 2.15B）

### 實驗設計

3 批 × 10 seeds = 30 個 PPO 實驗（順序執行，每批 10 並行）

| Batch | n_steps | 目的 |
|-------|---------|------|
| 1 | 20,000 | 基線（與 HuggingFace 實驗一致） |
| 2 | 40,000 | 2× rollout，降低 gradient variance |
| 3 | 60,000 | 3× rollout，最低 variance |

完成後：選最佳 n_steps → 10 個模型做 Sharpe-weighted Ensemble。

### 結果（2026-04-09 完成，30 experiments）

#### 逐 seed 對比

| Seed | n=20K | n=40K | n=60K |
|------|-------|-------|-------|
| 942082305 | 0.438 | 0.189 | 0.400 |
| 1145077126 | -0.011 | 0.492 | 0.548 |
| 1773871898 | **0.902** | 0.404 | **0.673** |
| 1980789688 | 0.725 | 0.525 | 0.091 |
| 2047133773 | -0.031 | 0.249 | 0.358 |
| 1988008269 | 0.502 | 0.541 | 0.396 |
| 381818397 | 0.052 | 0.509 | 0.401 |
| 889207412 | **1.151** | **0.648** | 0.582 |
| 2058534300 | 0.508 | 0.633 | 0.452 |
| 84665779 | 0.388 | 0.542 | 0.506 |

#### 統計摘要

| n_steps | Mean Sharpe | Std | Min | Max | Mean Return | Mean MDD |
|---------|-----------|-----|-----|-----|------------|---------|
| 20,000 | 0.462 | **0.377** | -0.031 | 1.151 | +15.2% | -24.7% |
| **40,000** | **0.473** | **0.138** | 0.189 | 0.648 | +17.7% | -33.3% |
| 60,000 | 0.441 | 0.152 | 0.091 | 0.673 | +15.6% | -34.9% |

#### 分析

1. **Mean Sharpe 三組幾乎一樣**（0.44-0.47）— n_steps 對平均表現影響不大
2. **n=40K Std 最低（0.138）** — 比 n=20K 低 64%，穩定性顯著改善
3. **n=20K 有最高峰也有最低谷** — 高 variance 不適合 production
4. **n=60K 沒有進一步改善** — MDD 反而更差，可能 100 epoch × 60K steps 過度更新
5. **Polygon 比 HuggingFace 難得多** — 平均 Sharpe 0.47 vs HF 的 0.78
   - Polygon: 134 tickers, 752 天 (2022-2024，含 2022 熊市)
   - HuggingFace: 82 tickers, 1509 天 (2019-2023，含 2020-2021 牛市)
   - 評分覆蓋率 Polygon 35% vs HF 19%（Polygon 反而更高但效果更差）

**結論：n_steps=40,000 是最佳配置**（穩定性最高，mean Sharpe 不犧牲）。

#### Top Seeds（跨 n_steps 一致表現好的初始化點）

篩選標準：跨 3 個 n_steps 設定的平均 Sharpe 高且 worst case > 0.4。

| 排名 | Seed | Avg Sharpe | Std | Min | 特性 |
|------|------|-----------|-----|-----|------|
| #1 | **889207412** | **0.794** | 0.254 | 0.582 | 最高均值，所有設定都最強 |
| #2 | **1773871898** | **0.660** | 0.204 | 0.404 | 次高，n=20K 達 0.902 |
| #3 | **2058534300** | **0.531** | **0.076** | 0.452 | 最穩定（std 最低） |

這 3 個 seed 在不同 n_steps 下表現一致，暗示它們的初始化權重落在 loss landscape 的較好區域。

> ⚠️ **Selection bias 警告**：從 10 個 seed 中選 top 3 本身就是一種 overfitting。
> 即使 10 個 seed 的真實能力相同，排名前 3 的回測 Sharpe 也會系統性偏高
> （極值理論，Bailey & Lopez de Prado 2014）。
> 這些 seed 在同資料集的其他實驗中可能表現好，也可能只是巧合。
> 正確做法是用 held-out test set 驗證，或用 Deflated Sharpe Ratio 校正。

#### seed=42 異常：跨資料集一致偏高

統計所有有多 seed 對照的實驗，seed=42 高於平均的比率：

| 資料集 | 算法 | seed=42 | 多seed平均 | 偏離 |
|--------|------|---------|-----------|------|
| HF gpt5mini | PPO | 0.900 | 0.777 | +0.123 |
| HF gpt5mini | CPPO | 0.980 | 0.680 | **+0.300** |
| HF gpt5mini | SAC | 0.760 | 0.780 | -0.020 |
| HF gpt5mini | TD3 | 0.770 | 0.756 | +0.014 |
| HF claude_opus NF | PPO | 1.005 | 0.757 | **+0.248** |
| HF gpt5_high NF | CPPO | 0.940 | 0.700 | **+0.240** |
| HF gpt5sum NF | PPO | 0.913 | 0.713 | +0.200 |
| HF gpt5sum NF | CPPO | 0.917 | 0.642 | **+0.275** |
| HF gpt5_high NF | PPO | 0.903 | 0.621 | **+0.282** |
| Polygon | PPO (SpinUp) | 1.660 | — | seed=0: 0.51 |

**8/9 次高於平均（89%）**，多數偏離 2-3σ。唯一例外是 SAC。

可能解釋：
1. 42 在 MT19937 PRNG 中恰好產生對 on-policy RL 友好的初始化權重分佈
2. 42 是深度學習社群最常用的測試 seed，不排除某些框架對其有間接優化
3. 純巧合（但 89% 高於平均的 p-value 相當低）

#### Polygon SB3 seed=42 補測結果

| n_steps | Sharpe | Return | MDD |
|---------|--------|--------|-----|
| 20K | 0.178 | +4.3% | -21.2% |
| 40K | 0.462 | +16.0% | -33.5% |
| 60K | 0.618 | +25.4% | -33.8% |
| **平均** | **0.419** | | |

seed=42 在 Polygon SB3 上排名 8/11（平庸）。**跨資料集一致偏高的現象不成立。**

修正結論：seed=42 在 HuggingFace 資料上的偏高可能是 state_dim (985) 和資料結構特異性，
不是 seed=42 本身有特殊屬性。SpinningUp Polygon seed=42 Sharpe 1.66 更可能歸因於
框架差異（MPI normalization、KL 公式等）而非 seed。

#### Ensemble 結果（n=40K 模型）

| 方案 | 組成 | 加權 | Sharpe | Return | MDD | Sortino |
|------|------|------|--------|--------|-----|---------|
| **Top 3 Sharpe-wt** | **3 best seeds** | **Sharpe** | **0.785** | **+40.5%** | -36.2% | **1.022** |
| All 10 equal | 10 seeds | Equal | 0.668 | +32.4% | -40.3% | 0.877 |
| All 10 Sharpe-wt | 10 seeds | Sharpe | 0.633 | +29.5% | -37.7% | 0.803 |
| Top 3 equal | 3 best seeds | Equal | 0.630 | +27.5% | **-34.2%** | 0.825 |
| 最佳單模型 | seed=889207412 | — | 0.648 | +30.6% | -40.5% | — |

#### 跨資料集 Ensemble 比較

| 資料集 + 算法 | Top 3 Sharpe-wt | All seeds Sharpe-wt | All seeds equal | 最佳單模型 |
|---------------|----------------|---------------------|-----------------|-----------|
| Polygon PPO | 0.785 | 0.633 | 0.668 | 0.648 |
| HF PPO | 0.809 | 0.545 | 0.522 | 0.900 |
| HF SAC | 0.803 | 0.757 | 0.749 | 0.831 |

三組實驗中 Top 3 均高於 All seeds ensemble，但此結果存在嚴重的方法論問題（見下方）。

#### ⚠️ 方法論修正：Selection Bias 警告

**上述 Top 3 ensemble 結果存在 selection bias，不應直接作為策略評估依據。**

問題：我們用 trade period 的 backtest Sharpe 選出 top 3 seeds，再用**同一份 trade data**
報告 ensemble 結果。這是經典的 data leakage — 選擇和評估使用相同資料。

**Bailey & Lopez de Prado (2014) "Deflated Sharpe Ratio"** 指出：從 N 個策略中選最佳者，
即使所有策略的真實 Sharpe = 0（純噪音），極值理論預測最佳者的期望 Sharpe ≈ √(2×ln(N))σ。
N=10 時 ≈ 2.15σ，足以看起來「顯著」。

**Cawley & Talbot (2010, JMLR)** 證明 validation-based model selection 引入的 optimistic bias
「量級可以跟算法間的差異一樣大」。

**Agarwal et al. (2021, NeurIPS Outstanding Paper)** 建議使用 IQM + bootstrap CI 報告所有 seeds
的結果，而不是 cherry-pick subset。

具體影響：
- Top 3 的 Sharpe 0.785（Polygon）有一部分是 selection bias 灌水
- 「Top 3 > All seeds」可能只是在說「從 10 個裡挑最好的 3 個，當然比全部平均好」
  — 這是統計上的必然，不是策略洞察
- 我們無法從回測數據本身判斷這個優勢是否會延續到未來

**正確的做法（未來實驗應採用）：**

1. **三段式分割**：Train / Validation（選 seed）/ Test（最終報告）
   - 目前只有 train/trade 兩段，trade 同時用於選擇和評估
2. **Deflated Sharpe Ratio**：用 N=10 校正，扣除多次嘗試的運氣成分
3. **報告所有 seeds 的 IQM + CI**：而非只報 top-K
4. **如果要 ensemble，考慮用 All seeds**：避免 selection bias，靠多樣性而非 cherry-pick

**修正後的可信結論（不依賴 selection）：**
- n_steps=40K 的 10 seeds 平均 Sharpe 0.473±0.138 — 這是無偏估計
- All 10 equal-weight ensemble Sharpe 0.668 — 超過平均單模型，且不涉及 selection
- Ensemble 確實提供價值（降低 variance），但來源是多樣性而非挑選

#### 降低 Seed Sensitivity 的已知方法（文獻）

| 方法 | 論文 | 效果 |
|------|------|------|
| Policy head 用 100× 更小權重 | Andrychowicz et al. 2021 (ICLR) | 顯著降低 variance |
| Orthogonal init + sqrt(2) scaling | Huang et al. 2022 (ICLR Blog) | SB3 PPO 已採用 |
| Penultimate feature normalization | Bjorck et al. 2022 (ICLR) | 減少 outlier runs |
| Layer normalization | Lyle et al. 2023 (ICML) | 保持 plasticity |
| 定期 reset 最後幾層 | Nikishin et al. 2022 (ICML) | 防止初始化主導學習 |
| Spectral normalization | Bjorck et al. 2021 (NeurIPS) | 穩定 Q-value |

SB3 PPO 已採用 orthogonal init，但其餘方法均未嘗試。
若要進一步降低 seed sensitivity，Layer normalization 和 penultimate feature normalization
是最容易實現的改善方向。

#### 上游專案做法調查（2026-04-09）

| | FinRL (SB3 backend) | FinRL_DeepSeek |
|---|---|---|
| Seed | **不設**（seed=None） | PPO 固定 42，CPPO 固定 0 |
| 多 seed 評估 | 無 | 無（note.md 提 ±0.02，未驗證） |
| 分割方式 | 基本 2 段；Ensemble 版 **3 段 rolling** | 2 段固定（6 年 train / 5 年 trade） |
| Validation | Ensemble 版有 63 天 validation window | 無 |
| 初始化 | SB3 默認（PPO orthogonal） | PyTorch 默認 Kaiming uniform |
| Ensemble | **Winner-takes-all**（每季選最佳 1 個） | 無 |
| 統計嚴謹度 | 單次結果 | 單次結果 |

**FinRL 的 3 段 rolling split** 是正確做法：
- Train（expanding window）→ Validation（63 天，選模型）→ Trade（63 天，評估）
- 每個 rebalance window 重新訓練和選擇，不依賴固定 seed
- 這解決了我們遇到的 selection bias 問題

**FinRL SB3 不設 seed 的啟示**：

不設 seed（seed=None）在以下場景反而是最正確的做法：

| 目的 | Seed 策略 |
|------|----------|
| Production ensemble | **不設** — 每個模型自然隨機，多樣性最大，無法 cherry-pick |
| 算法比較（A vs B） | 固定同一組 seed — 控制變數 |
| 可重現性 | 設但不選 — 記錄用了什麼，不挑好的 |
| 調參 | 固定一個 — 排除隨機干擾 |

我們之前的 seed 分析（Master RNG、top 3 挑選、seed=42 調查）本身是有價值的
學習過程，但如果一開始就不設 seed + 全部 ensemble，selection bias 問題不會存在。

**未來實驗方向：**
1. 採用 FinRL 的 rolling 3-way split（train / validation / trade）
2. Production ensemble 用 seed=None，訓練 N 個模型全部 ensemble
3. 算法比較用固定 seed 組
4. 報告所有模型的 IQM + CI，不做 top-K selection

#### 文獻參考

| 論文 | 核心觀點 |
|------|---------|
| Henderson et al. 2018 (AAAI) | 不同 seed subset 的平均可以來自不同統計分佈 |
| Colas et al. 2018 | 可靠比較需 10-20 seeds |
| Agarwal et al. 2021 (NeurIPS) | 用 IQM + bootstrap CI，不要 cherry-pick |
| Bailey & Lopez de Prado 2014 | Deflated Sharpe Ratio：校正多次嘗試的運氣 |
| Cawley & Talbot 2010 (JMLR) | Validation-based selection 的 bias 可以很大 |
| Patterson et al. 2024 (JMLR) | RL 實驗設計完整指南 |

---

## 已完成項目總結

| 項目 | 狀態 | 結果 |
|------|------|------|
| SB3 PPO 基準驗證 | ✅ | --full-batch --target-kl 0.05，多 seed 平均 Sharpe 0.777±0.098 |
| SB3 CPPO | ✅ | 多 seed 平均 0.680±0.121，波動最大 |
| SAC 訓練腳本 + 基準 | ✅ | 多 seed 平均 0.780±0.047（原始資料最穩定） |
| TD3 訓練腳本 + 基準 | ✅ | 多 seed 平均 0.756±0.009（最穩定） |
| Ensemble backtest 工具 | ✅ | `backtest_ensemble.py`，單 seed 測試未優於最佳單模型 |
| 多 seed 驗證 (gpt5mini × 4 algo) | ✅ | 18 實驗，見上方「多 seed 驗證結果」 |
| Title-only nano 評分 | ✅ | 127,176 行 sentiment + risk 完成 |
| 評分合併工具 | ✅ | `fill_missing_scores.py`，覆蓋率 18.5%→37.6% |
| Nanofilled 訓練 (5 dataset × 4 algo) | ✅ | 20 實驗，PPO 最佳（avg 0.908） |
| Nanofilled 多 seed (top 5 × 5 seeds) | ✅ | 25 實驗，Claude Opus PPO 最穩（0.757±0.073） |

### G5 GPT-5-mini 全演算法多 seed 對照（HF 資料 2019-2023）

> ⚠️ seed=42 結果全部偏高，以下以多 seed 平均為準

| 演算法 | Mean Sharpe | Std | seed=42 | 評價 |
|--------|-----------|-----|---------|------|
| SAC | 0.780 | **0.047** | 0.76 | 原始資料最穩定 |
| PPO | 0.777 | 0.098 | 0.90 | 穩健 |
| TD3 | 0.756 | **0.009** | 0.77 | 最低波動 |
| CPPO | 0.680 | 0.121 | **0.98** | 不穩定，seed=42 是異常值 |

### 追蹤觀望

| 方向 | 原因 | 狀態 |
|------|------|------|
| LLM Strategy Guide（第二代） | RL 增量僅 Sharpe +0.07；未審查 preprint；只測 6 支科技股 | 追蹤 |
| FLAG-Trader（第三代） | 未審查 preprint（非 ACL 2025）；只測 6 資產 | 追蹤 |
| WCSAC / DSAC | 需大量自訂實現；SAC 在 nanofilled 上退化，基礎不穩 | 暫緩 |
| Penultimate feature normalization | Bjorck et al. 2022，可降低 seed variance | 值得嘗試 |

### 技術筆記

**Ensemble 做法**（FinRL Contest, arXiv:2501.10709）：
1. 分別訓練多個 agent（同演算法不同 seed，或不同演算法）
2. 交易時用 Sharpe 加權平均 actions
3. Ensemble std ≈ 單一 agent 的一半（Holzer et al. 2025）
4. 主要價值是**降低 variance 和 MDD**，不是提升 Sharpe

> ⚠️ 引用數據驗證記錄見 `source_verification_2026.md`
> 演算法調查見 `algorithm_survey_2026.md`

---

## 備註

- 所有 model artifacts 在 `trained_models/` 下，含 metadata.json
- 系列 A（Polygon 2022-2024）和系列 B（HuggingFace 2019-2023）是獨立的
- Sonnet 4.5 評分資料已存在（77,871 行），但尚未用於訓練
- HuggingFace 資料的實驗已充分，下一階段轉向 Polygon 資料

---

*最後更新: 2026-04-07*