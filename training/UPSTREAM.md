# Training Code Upstream Lineage

## 繼承鏈

```
AI4Finance-Foundation/FinRL            ← 官方 RL 交易框架 (env_stocktrading.py)
    │
    ▼
benstaf/FinRL_DeepSeek                 ← 論文 arXiv:2502.07393 配套代碼
    │                                    「FinRL-DeepSeek: LLM-Infused Risk-Sensitive RL for Trading Agents」
    │                                    Colab notebook 風格，所有檔案平鋪在根目錄
    ▼
AI4Finance-Foundation/FinRL_DeepSeek   ← org-level fork（只改 README，代碼不動）
    │                                    FinRL Contest 2025 Task 1 starter kit
    ▼
MindfulRL-Intraday/training/           ← 本專案（改 import 路徑 + env 版本）
```

本機路徑對應：
- `/mnt/md0/PycharmProjects/FinRL` → `AI4Finance-Foundation/FinRL`
- `/mnt/md0/PycharmProjects/FinRL_DeepSeek` → `benstaf/FinRL_DeepSeek` (via AI4Finance fork)

## 「merge 回 FinRL」的真實情況

README 宣稱 "The project is integrated to the original FinRL project by AI4Finance!"，
但實際上 **FinRL 主 repo 完全沒有整合這些代碼**：

- benstaf 從未向 `AI4Finance-Foundation/FinRL` 提交任何 PR
- FinRL 主 repo 的 git history 無 deepseek/llm/sentiment/cppo 相關 commit
- benstaf 在 FinRL 開過 2 個 issue (#1297, #1303)，均未解決
- 真正發生的是 AI4Finance org **fork** 了一份作為 Contest starter kit

## 我們搬入時的改動（diff 確認）

### train_ppo_llm.py / train_cppo_llm_risk.py

僅 import 路徑適配：
```
- from finrl.config import INDICATORS, TRAINED_MODEL_DIR, RESULTS_DIR
- from finrl.main import check_and_make_directories
- from env_stocktrading_llm_01 import StockTradingEnv
+ from training.config import INDICATORS, TRAINED_MODEL_DIR, RESULTS_DIR, check_and_make_directories
+ from training.envs.stocktrading_llm import StockTradingEnv
```

**注意：env 版本從 `_01`（0.1% 縮放）改成了非 `_01`（10% 縮放）。**

### env_stocktrading_llm.py / env_stocktrading_llm_risk.py

- 清理註解和 debug print
- 修 `_initiate_state()` previous-state branch 漏 LLM 欄位（上游原始 bug）
- risk env 新增 `actions[high_risk_mask] *= 0.8` 風險抑制（上游無此邏輯）
- 格式化（多行展開）

### 上游 env 版本差異

| 版本 | 縮放係數 | 用途 |
|------|---------|------|
| `env_stocktrading_llm_01.py` | 0.999/1.001 (±0.1%) | `train_ppo_llm.py` 使用 |
| `env_stocktrading_llm_1.py` | 中間值 | 測試稿 |
| `env_stocktrading_llm.py` | 0.9/1.1 (±10%) | 我們目前使用 |
| `env_stocktrading_llm_risk_01.py` | 0.999/1.001 | 測試稿 |
| `env_stocktrading_llm_risk.py` | 0.9/1.1 | `train_cppo_llm_risk.py` + 我們使用 |

## 上游已知 bug（無人在 issues 討論）

### 1. `cppo()` 讀全域 `stock_dimension`（非純函式）

```python
# train_cppo_llm_risk.py L477, L495, L496
llm_risks = np.array(next_o[0, -stock_dimension:])
prices = np.array(next_o[0, 1:stock_dimension+1])
shares = np.array(next_o[0, stock_dimension+1:stock_dimension*2+1])
```

搬到獨立模組後若不傳參，會 NameError 或行為錯誤。

### 2. `CPPOBuffer.finish_path()` 重複扣舊軌跡

```python
# L297: 每次 finish_path() 都對整個 adv_buf 扣 valupdate_buf
self.adv_buf = self.adv_buf - self.valupdate_buf
# 應該只扣 path_slice
```

### 3. env.step() 解包不一致

- Backtest notebook (`DRL_prediction`): 5 值解包 ✓
- note.md 回測範例: 4 值解包 ✗
- 訓練迴圈 (`ppo()`/`cppo()`): 4 值，但走 `DummyVecEnv` 所以正確（VecEnv API 回傳 4 值）

### 4. `_initiate_state()` previous-state branch 漏 LLM 欄位

上游 `env_stocktrading_llm.py` 和 `env_stocktrading_llm_risk.py` 的
`_initiate_state()` previous-state 分支都沒有 append `llm_sentiment` / `llm_risk`，
造成 state dimension 不一致。我們已在 commit `9baef0d` 修復。

## FinRL_DeepSeek Issues 摘要（共 7 個）

| # | 標題 | 狀態 | 技術性 |
|---|------|------|--------|
| #1 | Lacking Python scripts | closed | 早期 repo 不完整 |
| #2 | How to train models? | closed | 文件不足 |
| #3 | Improved readme + bugs (PR) | open, 未 merge | README + notebook |
| #4 | Load from HuggingFace | closed | Feature request |
| #5 | Training not using GPU | closed | SpinningUp = CPU (MPI) |
| #6 | Contest 2025 results | closed | 問比賽結果 |
| #7 | Derivative strategy? | open | 問 options |

**無人報告上述 bug。**

## 參考連結

- 論文: https://arxiv.org/abs/2502.07393
- 上游 repo: https://github.com/benstaf/FinRL_DeepSeek
- AI4Finance fork: https://github.com/AI4Finance-Foundation/FinRL_DeepSeek
- HuggingFace 數據: https://huggingface.co/datasets/benstaf/nasdaq_2013_2023
- FinRL Contest 2025 Task 1: https://finrl-contest.readthedocs.io/en/latest/finrl2025/task1.html
- FinRL 主 repo: https://github.com/AI4Finance-Foundation/FinRL
