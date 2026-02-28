# Training Module

RL 訓練模組：PPO（情緒信號）和 CPPO（情緒+風險信號）交易策略。

基於 OpenAI SpinningUp 框架，使用 LLM 評分增強 Gymnasium 環境。

## 目錄結構

```
training/
├── config.py                        # 超參數、指標、情緒縮放設定
├── models.py                        # MLPActorCritic 神經網路架構
├── ppo.py                           # PPOBuffer + ppo() 演算法核心
├── cppo.py                          # CPPOBuffer + cppo() (CVaR 風險約束)
├── train_ppo_llm.py                 # PPO 訓練入口（資料載入、環境設定、存檔）
├── train_cppo_llm_risk.py           # CPPO 訓練入口
├── backtest.py                      # 回測腳本
├── preprocessor.py                  # 資料前處理
├── envs/
│   ├── stocktrading_llm.py          # 情緒增強交易環境
│   └── stocktrading_llm_risk.py     # 情緒+風險增強交易環境
├── data_prep/                       # LLM 評分資料準備腳本
│   ├── prepare_training_data.py     # 統一入口（支援 4 種資料來源）
│   ├── README.md                    # 資料格式規格 + 來源文件
│   └── output/                      # 產出目錄（.gitignore）
├── scripts/
│   ├── capture_baseline.py          # 回歸驗證：擷取訓練指標基線
│   └── train.sh                     # Shell 包裝腳本
├── baselines/                       # capture_baseline.py 輸出目錄
└── UPSTREAM.md                      # 上游 FinRL 代碼溯源與已知問題
```

## 環境準備

### 必要條件

- Python 3.10+
- virtualenv（建議使用 `virtualenvwrapper`）

### 在 FinRL virtualenv 安裝依賴

```bash
workon FinRL

# 1. 確認 PyTorch 已安裝（FinRL env 通常已有）
python -c "import torch; print(torch.__version__)"

# 2. 安裝訓練核心依賴
pip install gymnasium stable-baselines3 mpi4py scipy datasets matplotlib yfinance stockstats

# 3. 安裝 SpinningUp（需要特殊處理，見下文）
```

### SpinningUp 安裝（重要）

SpinningUp 是 OpenAI 的 RL 教學框架，**已停止維護（2020 年）**。
它的 `setup.py` 要求 `tensorflow<2.0`，但我們只用 PyTorch 後端。

**安裝步驟：**

```bash
# 進入 SpinningUp 目錄
cd /mnt/md0/PycharmProjects/spinningup

# 跳過依賴安裝（避免 tensorflow<2.0 衝突）
pip install -e . --no-deps

# 手動裝 runtime 需要的依賴（PyTorch 和大部分已在 FinRL env）
pip install cloudpickle joblib psutil tqdm
```

### SpinningUp 修補（3 個檔案）

SpinningUp 有 3 處需要修補才能在無 TensorFlow 環境下運行：

**1. `spinup/__init__.py`** — TF import 保護

將頂部的 `import tensorflow as tf` 替換為：

```python
try:
    import tensorflow as tf
    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
except ImportError:
    tf = None  # TF backend unavailable; PyTorch-only mode

# Algorithms - TF1 (skip if tensorflow not installed)
if tf is not None:
    from spinup.algos.tf1.ddpg.ddpg import ddpg as ddpg_tf1
    # ... (other TF1 imports)
```

**2. `spinup/utils/logx.py`** — 同樣的 TF import 保護

第 12 行左右：

```python
try:
    import tensorflow as tf
except ImportError:
    tf = None  # TF backend unused; we only use PyTorch
```

**3. `spinup/algos/pytorch/ppo/core.py`** — Gymnasium 相容

第 3-6 行：

```python
try:
    from gymnasium.spaces import Box, Discrete
except ImportError:
    from gym.spaces import Box, Discrete
```

### 驗證安裝

```bash
workon FinRL
python -c "
import torch, gymnasium, stable_baselines3, scipy, mpi4py, datasets, matplotlib
import spinup.algos.pytorch.ppo.core
from training.ppo import ppo
from training.cppo import cppo
from training.models import MLPActorCritic
from training.config import INDICATORS, SENTIMENT_SCALES
print('All training deps OK')
"
```

## 完整使用流程

以下是從原始新聞到回測結果的 end-to-end 流程。

```
┌─────────────────────────────────────────────────────┐
│  Step 0: 新聞評分（上游，可選）                        │
│  score_ibkr_news.py --mode sentiment/risk            │
│  → Parquet 檔加入 sentiment_*/risk_* 欄位             │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  Step 1: 資料準備                                     │
│  prepare_training_data.py --source X --score-type Y  │
│  → output/train_*.csv + trade_*.csv                  │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  Step 2: 訓練                                        │
│  train_ppo_llm.py --data train_*.csv (sentiment)     │
│  train_cppo_llm_risk.py --data train_*.csv (+ risk)  │
│  → trained_models/agent_*.pth                        │
└──────────────────────┬──────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│  Step 3: 回測                                        │
│  backtest.py --data trade_*.csv --model agent_*.pth  │
│  → equity_curve.png + 績效指標                        │
└─────────────────────────────────────────────────────┘
```

### 範例 A: Claude Opus → PPO（最快上手）

```bash
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
workon FinRL

# 1. 準備資料（sentiment only）
python -m training.data_prep.prepare_training_data --source claude --model opus

# 2. 訓練（快速測試 3 epochs）
python training/train_ppo_llm.py \
  --data training/data_prep/output/train_claude_opus.csv \
  --epochs 3 --seed 42

# 3. 回測
python training/backtest.py \
  --data training/data_prep/output/trade_claude_opus.csv \
  --model trained_models/agent_ppo_claude_opus_3ep_s42.pth \
  --env sentiment
```

### 範例 B: Claude Opus → CPPO（sentiment + risk）

```bash
# 1. 準備資料（sentiment + risk）
python -m training.data_prep.prepare_training_data \
  --source claude --model opus --score-type both

# 2. 訓練 CPPO
python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_claude_opus_both.csv \
  --epochs 3 --seed 42

# 3. 回測
python training/backtest.py \
  --data training/data_prep/output/trade_claude_opus_both.csv \
  --model trained_models/agent_cppo_claude_opus_both_3ep_s42.pth \
  --env risk
```

### 範例 C: Polygon 現代資料 → PPO

```bash
# 1. 準備資料（自訂日期範圍）
python -m training.data_prep.prepare_training_data \
  --source polygon \
  --train-start 2022-06-01 --train-end 2024-12-31 \
  --trade-start 2025-01-01 --trade-end 2026-02-28

# 2. 訓練
python training/train_ppo_llm.py \
  --data training/data_prep/output/train_polygon_gpt52xhigh.csv \
  --epochs 100

# 3. 回測
python training/backtest.py \
  --data training/data_prep/output/trade_polygon_gpt52xhigh.csv \
  --model trained_models/agent_ppo_polygon_gpt52xhigh_100ep_s42.pth \
  --env sentiment
```

### 範例 D: Polygon → CPPO（需先完成 risk 評分）

```bash
# 0. 評分（如尚未完成 risk）
python scripts/scoring/score_ibkr_news.py \
  --mode risk --model gpt-5.2 --reasoning-effort xhigh \
  --daily-token-limit 1000000 --save-every 10 \
  --data-dir data/news/raw/polygon

# 1. 準備資料
python -m training.data_prep.prepare_training_data \
  --source polygon --score-type both \
  --train-start 2022-06-01 --train-end 2024-12-31 \
  --trade-start 2025-01-01 --trade-end 2026-02-28

# 2. 訓練 CPPO
python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_polygon_gpt52xhigh_both.csv \
  --epochs 100

# 3. 回測
python training/backtest.py \
  --data training/data_prep/output/trade_polygon_gpt52xhigh_both.csv \
  --model trained_models/agent_cppo_polygon_gpt52xhigh_both_100ep_s0.pth \
  --env risk
```

### 範例 E: MPI 分散式正式訓練

```bash
# PPO 8 核心
mpirun -np 8 python training/train_ppo_llm.py \
  --data training/data_prep/output/train_claude_opus.csv \
  --epochs 100

# CPPO 4 核心（root 需額外環境變數）
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
  mpirun -np 4 python training/train_cppo_llm_risk.py \
  --data training/data_prep/output/train_claude_opus_both.csv \
  --epochs 100
```

---

## 參考：資料準備

詳細格式規格見 [data_prep/README.md](data_prep/README.md)。

### 資料來源

| 來源 | `--source` | sentiment | risk | 日期範圍 |
|------|-----------|-----------|------|----------|
| HuggingFace DeepSeek | `huggingface` | `sentiment_deepseek` | `risk_deepseek` | 2009-2024 |
| Claude（Opus/Sonnet/Haiku） | `claude` | `sentiment_opus` 等 | `risk_opus` 等 | 同上 |
| GPT-5（high/medium/low/minimal） | `gpt5` | `sentiment_gpt_5` | `risk_gpt_5` | 同上 |
| Polygon API | `polygon` | `sentiment_gpt_5_2_xhigh` | `risk_gpt_5_2_xhigh` | 2022-2026 |

### data_prep 參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--source` | **必填** | 資料來源: `huggingface`, `claude`, `gpt5`, `polygon` |
| `--model` | 依 source | 模型/effort 選擇（claude: opus/sonnet/haiku, gpt5: high/medium/low/minimal） |
| `--score-type` | `sentiment` | 評分類型: `sentiment`, `risk`, `both`（Polygon risk 需先評分） |
| `--train-start` | `2013-01-01` | 訓練集起始日 |
| `--train-end` | `2018-12-31` | 訓練集結束日 |
| `--trade-start` | `2019-01-01` | 回測集起始日 |
| `--trade-end` | `2023-12-31` | 回測集結束日 |

產出檔案在 `training/data_prep/output/`：
- `train_{tag}.csv` / `trade_{tag}.csv`
- tag 範例：`claude_opus`, `claude_opus_both`, `gpt5_high`, `polygon_gpt52xhigh`

## 參考：訓練參數

| 參數 | 預設 | 說明 |
|------|------|------|
| `--data` | None | 本地 CSV 路徑（跳過 HuggingFace 下載） |
| `--epochs` | 100 | 訓練輪數 |
| `--seed` / `-s` | 42 (PPO) / 0 (CPPO) | 隨機種子 |
| `--hid` | 512 | 隱藏層大小 |
| `--l` | 2 | 隱藏層層數 |
| `--steps` | 20000 | 每輪步數（僅 PPO） |
| `--gamma` | 0.995 | 折扣因子（僅 PPO） |
| `--sentiment-scale` | strong | 情緒縮放: `strong` (±10%) / `weak` (±0.1%) |

模型輸出檔名格式：`agent_{algo}_{data_tag}_{epochs}ep_s{seed}.pth`

## 參考：回測參數

```bash
python training/backtest.py \
  --data trade_*.csv \
  --model trained_models/agent_*.pth \
  --env sentiment \
  --hid 512 --l 2 \
  --sentiment-scale strong
```

| 參數 | 預設 | 說明 |
|------|------|------|
| `--data` | **必填** | 回測資料 CSV（data_prep 的 trade_*.csv） |
| `--model` | **必填** | 訓練產出的 .pth 模型檔 |
| `--env` | `sentiment` | 環境類型: `baseline`, `sentiment`, `risk` |
| `--hid` | 512 | 隱藏層大小（**必須與訓練一致**） |
| `--l` | 2 | 隱藏層層數（**必須與訓練一致**） |
| `--sentiment-scale` | `strong` | 情緒縮放（**必須與訓練一致**） |
| `--output-plot` | `equity_curve.png` | 權益曲線圖輸出路徑 |

輸出指標：Final Equity, Information Ratio, CVaR (95%)

## 回歸驗證（Regression Validation）

重構前後用 `capture_baseline.py` 擷取訓練指標，比較 JSON 確認行為一致：

```bash
# 重構前
python training/scripts/capture_baseline.py --epochs 3 --seed 42

# 重構後
python training/scripts/capture_baseline.py --epochs 3 --seed 42

# 比較
diff training/baselines/ppo_baseline.json training/baselines/ppo_baseline_after.json
```

## 情緒縮放（Sentiment Scaling）

上游 FinRL_DeepSeek 有兩種環境變體（`_01` 和非 `_01` 檔案）用不同幅度的情緒影響。
我們統一為可設定參數：

| 預設 | 強匹配 | 中匹配 | 持有抑制 | 中不匹配 | 強不匹配 |
|------|--------|--------|----------|----------|----------|
| `strong` (±10%) | 1.10 | 1.05 | 0.98 | 0.95 | 0.90 |
| `weak` (±0.1%) | 1.001 | 1.0005 | 1.0 | 0.9995 | 0.999 |

CPPO 的風險權重也跟隨：

| 風險分數 | strong 權重 | weak 權重 |
|----------|------------|-----------|
| 1 (低風險) | 0.99 | 0.999 |
| 2 | 0.995 | 0.9995 |
| 3 (中性) | 1.00 | 1.00 |
| 4 | 1.005 | 1.0005 |
| 5 (高風險) | 1.01 | 1.001 |

## 超參數

### PPO

| 參數 | 值 | 說明 |
|------|-----|------|
| epochs | 100 | 訓練輪數 |
| steps_per_epoch | 20000 | 每輪步數 |
| gamma | 0.995 | 折扣因子 |
| clip_ratio | 0.7 | PPO 裁剪比率 |
| hidden_sizes | [512, 512] | 神經網路結構（`--hid 512 --l 2`）|
| pi_lr | 3e-5 | 策略網路學習率 |
| vf_lr | 1e-4 | 價值函數學習率 |

### CPPO

| 參數 | 值 | 說明 |
|------|-----|------|
| alpha | 0.85 | 風險敏感度（CVaR 閾值）|
| beta | 3000.0 | 風險約束拉格朗日係數 |
| cvar_clip_ratio | 0.05 | CVaR 裁剪比率 |
| steps_per_epoch | 20000 | 每輪步數 |
| gamma | 0.995 | 折扣因子 |

## 已知問題

### CPPOBuffer.finish_path 上游 bug（已修復）

上游代碼在 `finish_path()` 中對整個 buffer 而非當前 path slice 做減法，
導致先前軌跡的 advantage 值被重複修改。我們的 `cppo.py` 已修復：

```python
# 修復前（上游 bug）:
self.adv_buf = self.adv_buf - self.valupdate_buf

# 修復後:
self.adv_buf[path_slice] = self.adv_buf[path_slice] - self.valupdate_buf[path_slice]
```

### DummyVecEnv API 差異

SpinningUp 預期 Gymnasium 原生 API（`reset()` 回傳 `obs, info`），
但 SB3 的 `DummyVecEnv` 包裝後 `reset()` 只回傳 `obs`，`step()` 回傳 4 值。
`ppo.py` / `cppo.py` 中已有對應處理。

### 其他上游問題

見 [UPSTREAM.md](UPSTREAM.md) 了解完整的上游代碼溯源和已知問題列表。

---

*最後更新: 2026-03-01*
