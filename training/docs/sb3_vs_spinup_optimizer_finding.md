# SB3 vs SpinningUp Optimizer 設計差異：標準 vs 非標準

**發現日期**: 2026-04-03

## 結論

**SB3 的合併 loss + 單一 optimizer 是 PPO 論文原文（Schulman 2017, Equation 9）的標準實現。
SpinningUp 的分離 optimizer 是非標準的教學簡化版本。**

之前的調查方向（「SB3 有結構性限制」）是錯誤的歸因。兩者是不同的 PPO 實現變體，
各有優劣，不能簡單地說誰更好。

## PPO 論文 Equation 9

```
L^{CLIP+VF+S}_t = E_t [ L^{CLIP}_t - c1 * L^{VF}_t + c2 * S[π](s_t) ]
```

論文明確說明：「If using a neural network architecture that shares parameters between
the policy and value function, we must use a loss function that combines the policy
surrogate and a value function error term.」

即使網路不共享（我們的情況），多數主流實現仍延用此合併方式。

## 各框架的實現對照

| 實現 | Optimizer | 合併 Loss | 對齊論文 |
|------|----------|----------|---------|
| **Schulman 2017（論文）** | 單一 | 是 (Eq. 9) | 定義 |
| **OpenAI Baselines PPO2** | 單一 | 是 | 是 |
| **CleanRL** | 單一 | 是 | 是 |
| **SB3** | 單一 | 是 | **是** |
| **SpinningUp** | **分離** | **否** | **非標準** |
| PPG (Cobbe 2021) | 分階段 | 否 | 延伸研究 |

## 為什麼 SpinningUp 用分離 Optimizer

SpinningUp 是 OpenAI 的 **RL 教學框架**（2018 年），設計目標是「容易理解」而非「嚴格對齊論文」。
分離 optimizer 的好處：
- 代碼更容易讀懂（一個 for loop 更新 policy，另一個更新 value）
- 可以用不同的 learning rate（pi_lr=3e-5, vf_lr=1e-4）
- Policy 的 KL early stop 不影響 value 訓練

但這**不是 PPO 論文描述的演算法**。

## SB3 沒有內建分離 Optimizer

- `ActorCriticPolicy._build()` 建立一個 `self.optimizer`，包含所有參數
- `PPO.train()` 用一個 `loss.backward()` + `optimizer.step()`
- 沒有 kwarg、flag、或 contrib 插件提供分離選項
- 但 SB3 的 **SAC/TD3**（off-policy 演算法）確實用分離 optimizer

如果需要在 SB3 PPO 上實現分離 optimizer，需要同時 override policy 的 `_build()`
和 PPO 的 `train()`。技術上可行但改動量大。

## 之前的「SB3 結構性限制」說法的修正

之前的 experiment log 說「剩餘 gap 來自共用 optimizer 的結構性限制」。
修正：

- 共用 optimizer 是**論文標準做法**，不是限制
- SpinningUp 的分離 optimizer 是**非標準變體**，恰好在我們的任務上表現更好
- 兩者在不同 seed 下表現會有交叉，單一 seed 的比較不足以下結論
- PPG (Cobbe 2021) 研究表明分離 value 訓練**確實有理論優勢**，但這是論文之後的發現

## 對我們的影響

1. **不要執著於對齊 SpinningUp** — 它不是 gold standard
2. **SB3 的最佳配置已經很好** — `--full-batch --target-kl 0.05`，Sharpe 0.90
3. **多 seed 驗證比追 gap 更有價值** — 確認 0.90 是穩定的比追到 1.03 更重要
4. **分離 optimizer 可以作為後續實驗**，但不是必要的修正

---

*參考*:
- Schulman et al. 2017 — Proximal Policy Optimization Algorithms (arXiv:1707.06347)
- Cobbe et al. 2021 — Phasic Policy Gradient (arXiv:2009.04416)
- SB3 Issue #1533, OpenAI Baselines Issue #766
- The 37 Implementation Details of PPO (ICLR Blog Track)