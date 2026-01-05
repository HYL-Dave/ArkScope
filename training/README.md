# Training Module

FinRL 強化學習訓練模組，支援 LLM 增強的股票交易策略。

## 目錄結構

```
training/
├── __init__.py
├── README.md                    # 本文件
├── train_ppo_llm.py            # PPO 訓練 (情緒信號)
├── train_cppo_llm_risk.py      # CPPO 訓練 (情緒+風險信號)
├── backtest.py                 # 回測腳本
├── envs/                       # RL 環境
│   ├── __init__.py
│   ├── stocktrading_llm.py     # 情緒增強環境
│   └── stocktrading_llm_risk.py # 情緒+風險環境
├── data_prep/                  # 數據準備腳本
│   ├── __init__.py
│   ├── train_trade_data_deepseek_sentiment.py
│   ├── train_trade_data_deepseek_risk.py
│   ├── sentiment_deepseek_deepinfra.py
│   └── risk_deepseek_deepinfra.py
└── scripts/                    # Shell 腳本
    ├── __init__.py
    └── train.sh                # 統一訓練入口
```

## 快速開始

### 1. PPO 訓練 (僅情緒)

```bash
# 使用 MPI 分散式訓練
cd /mnt/md0/PycharmProjects/MindfulRL-Intraday
mpirun -np 8 python -m training.train_ppo_llm
```

### 2. CPPO 訓練 (情緒+風險)

```bash
# 需要設置 root 權限變數 (如果以 root 執行)
OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
  mpirun -np 4 python -m training.train_cppo_llm_risk
```

### 3. 使用包裝腳本

```bash
./training/scripts/train.sh <dataset.csv> ppo sentiment
./training/scripts/train.sh <dataset.csv> cppo risk
```

### 4. 回測

```bash
python -m training.backtest \
  --data trade_data.csv \
  --model trained_models/agent_ppo_*.pth \
  --env sentiment
```

## 數據流程

```
評分輸出 (sentiment_gpt_5, risk_haiku)
    ↓
數據準備 (data_prep/train_trade_data_*.py)
    ↓
訓練輸入 (llm_sentiment, llm_risk)
    ↓
訓練 (train_ppo_llm.py / train_cppo_llm_risk.py)
    ↓
模型輸出 (agent_*.pth)
```

## 欄位命名

| 階段 | 欄位名稱 | 說明 |
|------|----------|------|
| 評分輸出 | `sentiment_{model}`, `risk_{model}` | 模型特定名稱 |
| 訓練輸入 | `llm_sentiment`, `llm_risk` | 通用名稱 |

## 超參數

### PPO (train_ppo_llm.py)

| 參數 | 值 | 說明 |
|------|-----|------|
| epochs | 100 | 訓練輪數 |
| steps_per_epoch | 20000 | 每輪步數 |
| gamma | 0.995 | 折扣因子 |
| clip_ratio | 0.7 | PPO 裁剪比率 |
| hidden_sizes | [256, 128] | 神經網路結構 |

### CPPO (train_cppo_llm_risk.py)

| 參數 | 值 | 說明 |
|------|-----|------|
| alpha | 0.85 | 風險敏感度 |
| beta | 3000.0 | 風險約束係數 |
| cvar_clip_ratio | 0.05 | CVaR 裁剪比率 |

## 風險權重映射

CPPO 將 LLM 風險分數 (1-5) 映射為權重：

| 風險分數 | 權重 | 含義 |
|----------|------|------|
| 1 (低風險) | 0.99 | 略微降低收益權重 |
| 2 | 0.995 | |
| 3 (中性) | 1.00 | 正常權重 |
| 4 | 1.005 | |
| 5 (高風險) | 1.01 | 略微提高收益權重，鼓勵規避 |

## 相關文檔

- [訓練管道架構](../docs/design/TRAINING_PIPELINE_ARCHITECTURE.md)
- [FinRL 整合設計](../docs/design/FINRL_INTEGRATION_DESIGN.md)
- [數據管道文檔](/mnt/md0/finrl/DATA_PIPELINE_DOCUMENTATION.md)

---

*最後更新: 2026-01-05*