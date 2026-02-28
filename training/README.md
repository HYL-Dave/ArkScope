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
│   ├── train_trade_data_deepseek_sentiment.py
│   ├── train_trade_data_deepseek_risk.py
│   ├── sentiment_deepseek_deepinfra.py
│   └── risk_deepseek_deepinfra.py
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
pip install gymnasium stable-baselines3 mpi4py scipy datasets matplotlib

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

## 訓練指令

### PPO 訓練（情緒信號）

```bash
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
workon FinRL

# 單進程快速測試
python training/train_ppo_llm.py --epochs 3 --seed 42

# MPI 分散式訓練（正式）
mpirun -np 8 python training/train_ppo_llm.py --epochs 100

# 使用弱情緒縮放
python training/train_ppo_llm.py --sentiment-scale weak --epochs 100

# 使用本地 CSV（data_prep 產出的資料）
python training/train_ppo_llm.py --data path/to/prepared_sentiment.csv
```

### CPPO 訓練（情緒+風險信號）

```bash
# 如果以 root 執行 MPI，需要額外環境變數
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
  mpirun -np 4 python training/train_cppo_llm_risk.py --epochs 100

# 快速測試
python training/train_cppo_llm_risk.py --epochs 3 --seed 42

# 使用本地 CSV
python training/train_cppo_llm_risk.py --data path/to/prepared_risk.csv
```

### 命令列參數

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
| `--cpu` | 4 | MPI 核心數（目前未被 script 使用） |

## 回測

```bash
python training/backtest.py \
  --data trade_data.csv \
  --model trained_models/agent_ppo_deepseek_100_epochs_20k_steps_01.pth \
  --env sentiment \
  --sentiment-scale strong
```

`--env` 選項：
- `baseline` — 無 LLM 信號
- `sentiment` — 情緒信號（使用 `stocktrading_llm.py`）
- `risk` — 情緒+風險信號（使用 `stocktrading_llm_risk.py`）

`--sentiment-scale` 必須與訓練時使用的一致。

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
| pi_lr / vf_lr | 3e-4 | 策略/價值函數學習率 |

### CPPO

| 參數 | 值 | 說明 |
|------|-----|------|
| alpha | 0.85 | 風險敏感度（CVaR 閾值）|
| beta | 3000.0 | 風險約束拉格朗日係數 |
| cvar_clip_ratio | 0.05 | CVaR 裁剪比率 |
| steps_per_epoch | 20000 | 每輪步數 |
| gamma | 0.995 | 折扣因子 |

## 資料流程

```
HuggingFace (benstaf/nasdaq_2013_2023)
    ↓
load_data() — train_ppo_llm.py / train_cppo_llm_risk.py
    ↓  欄位: date, tic, close, volume, llm_sentiment, [llm_risk], 技術指標...
    ↓
make_env() → StockTradingEnv → DummyVecEnv
    ↓
ppo() / cppo() — SpinningUp 演算法
    ↓
torch.save() → trained_models/agent_*.pth
```

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

*最後更新: 2026-02-28*
