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

### 結果對照表（待填）

**第一輪：**

| 實驗 | Return | Sharpe | MDD | CVaR | 訓練時間 |
|------|--------|--------|-----|------|---------|
| G1-PPO (DeepSeek) | | | | | |
| G1-CPPO (DeepSeek) | | | | | |
| G2-PPO (Opus) | | | | | |
| G2-CPPO (Opus) | | | | | |
| G3a-PPO (GPT-5 high / o3 sum) | | | | | |
| G3a-CPPO (GPT-5 high / o3 sum) | | | | | |

**第二輪：**

| 實驗 | Return | Sharpe | MDD | CVaR | 訓練時間 |
|------|--------|--------|-----|------|---------|
| G3b-PPO (GPT-5 high / gpt5 sum) | | | | | |
| G4-PPO (o3 high) | | | | | |
| G5-PPO (GPT-5-mini) | | | | | |

**論文原始結果（Table 1, 2M steps）供參考**：

| 模型 | Information Ratio | CVaR |
|------|------------------|------|
| PPO (no LLM) | 0.0100 | -0.0394 |
| PPO-DeepSeek | -0.0093 | -0.0338 |
| CPPO (no LLM) | -0.0148 | -0.0439 |
| CPPO-DeepSeek | 0.0078 | -0.0437 |

### 後續擴展（視結果決定）

- 第二輪 G3b/G4/G5 的 CPPO（如果 PPO 結果有意義）
- Claude Haiku / Sonnet（最低成本 Claude，已有評分資料）
- GPT-5 minimal（最低成本 GPT，已有評分資料）
- 所有評分資料預計開源到 HuggingFace（含各 R/V 組合）

---

## 備註

- 每個實驗完成後更新本文件，記錄 Model ID、指標、判斷
- 所有 model artifacts 在 `trained_models/` 下，含 metadata.json
- Equity curve 圖在各 model 目錄下的 `equity_curve.png`
- 訓練 log 在 `/mnt/md0/PycharmProjects/spinningup/data/` 下
- 系列 A（Polygon）和系列 B（HuggingFace）是獨立的，不直接比較（不同資料源、不同日期、不同 tickers）

---

*最後更新: 2026-03-30*