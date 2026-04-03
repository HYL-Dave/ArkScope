# RL 交易演算法調查 (2026)

本文件記錄了對 RL 交易演算法的調查，用於指導後續的演算法選擇和升級路徑。

## 現有方案：PPO + CPPO (SpinningUp / SB3)

- PPO: 最大化期望回報
- CPPO: 最大化期望回報 + CVaR 尾部風險約束
- CPPO 約束完全放鬆時近似等價 PPO（但不完全相同）
- LLM 情緒/風險分數作為 state 的一部分 + 環境內的 action scaling

## FinRL 支援的演算法

FinRL 核心 5 個演算法（2020 至今未新增）：

| 演算法 | 類型 | Action Space | 特點 |
|--------|------|-------------|------|
| A2C | On-policy | 連續/離散 | 快但高方差 |
| **PPO** | On-policy | 連續/離散 | 最穩定、泛用 |
| DDPG | Off-policy | 連續 | 確定性 policy |
| TD3 | Off-policy | 連續 | 修正 DDPG 的 Q 值高估 |
| **SAC** | Off-policy | 連續 | 最大 entropy 探索、自動調參 |

FinRL-X (2025) 重寫了架構但**未新增演算法**。創新在模組化設計和 ensemble 策略。

## 主要候選演算法分析

### SAC（最推薦的下一步）

| 面向 | 評估 |
|------|------|
| 適合度 | 高 — off-policy、自動 entropy、SB3 內建 |
| 對 134 股 | 優 — 隨機 policy + entropy bonus 比 PPO 更能探索高維 action |
| 樣本效率 | 優 — replay buffer 反覆使用經驗（PPO 用完即丟） |
| 超參調校 | 易 — 自動 entropy tuning（不需手動調 target_kl）|
| 風險 | 可能持股時間短（高換手 → 高交易成本） |
| 工作量 | 低 — SB3 內建，從 train_ppo_sb3.py 改幾行 |

### Ensemble (PPO + SAC + TD3)

FinRL Contest 2023-2024 冠軍方案：
- PPO + SAC + DDPG ensemble: MDD 從 -10~13% 降到 **-8.98%**
- Sharpe 穩定在 1.48（接近最佳單一模型 1.55）
- Return 方差減半
- 投票方式：Sharpe 加權的多數決

### 風險敏感演算法（CPPO 的替代）

| 方法 | 描述 | 對我們的適用性 |
|------|------|--------------|
| **WCSAC** (Worst-Case SAC) | SAC + CVaR 約束 | 高 — SAC 的探索 + CPPO 的風險控制 |
| **Distributional SAC (DSAC)** | 建模完整回報分佈 | 高 — 最原則性的風險管理 |
| **IQN + CVaR** | 任意分位數估計 + 可調風險偏好 | 中 — 需自訂實現 |
| **DRL-ORA** | 線上自適應風險 | 中 — 不需預設風險容忍度 |

### LLM + RL 的演進（三代）

| 世代 | 方式 | 代表 | 我們的位置 |
|------|------|------|-----------|
| **第一代** | LLM 評分 → RL state | FinRL-DeepSeek（我們） | ← 目前 |
| **第二代** | LLM 策略引導 → RL 執行 | Language Model Guided RL (2025) | 可升級 |
| **第三代** | LLM 本身就是 policy | FLAG-Trader (arXiv preprint, 未審查) | 需大量投資 |

第二代最實用：LLM 不只評 sentiment，還產出月度策略方向信號，追加到 RL state。
代碼改動小（state 多一個維度），但需要額外的 prompt 設計。

## 推薦的升級路徑

| 優先級 | 方向 | 預期效果 | 工作量 |
|--------|------|---------|--------|
| 1 | **SAC 訓練腳本** | 更好的探索、不需調 target_kl | 低（SB3 內建） |
| 2 | **Ensemble (PPO+SAC+TD3)** | MDD 減半、Sharpe 更穩定 | 中（3 個模型 + 投票） |
| 3 | **LLM Strategy Guide (第二代)** | 更高層的 LLM 信號 | 中（prompt + 1 維 state） |
| 4 | **WCSAC / DSAC** | 原則性風險管理取代 CPPO | 高（自訂實現） |
| 5 | **Decision Transformer** | 離線預訓練 → 線上微調 | 高 |

## 參考發現：演算法選擇的重要性

> ⚠️ 以下數據已驗證，部分有偏差。詳見 `source_verification_2026.md`。

2025 meta-study（167 篇 RL 交易研究，arXiv:2512.10913，**未經 peer review**）：

```
Random Forest feature importance（原文標籤）：
  Complexity score:  0.31（≈ 實現品質/複雜度）
  環境設計相關:      0.24
  資料品質和特徵:    0.19
  Algorithm family:  0.08（≈ 演算法類別選擇）
```

**Policy Gradient 類 vs DQN 類差異不顯著 (p=0.640)**。
~~注意~~：原始比較是 PG（含 PPO/A2C 等）vs DQN，不是 PPO vs SAC 的直接比較。

此結論來自未審查 preprint，feature importance 基於 meta-data proxy 指標而非直接 A/B 實驗。
方向可能正確但數字精確度有限。

### LLM+RL 演進的補充說明

| 世代 | 代表 | 驗證狀態 |
|------|------|---------|
| 第一代 | FinRL-DeepSeek | 我們的上游，已驗證 |
| 第二代 | Language Model Guided RL (arXiv:2508.02366) | 數字正確。但 LLM-Only baseline 也達 Sharpe 1.03（RL 增量僅 0.07）。只測 6 支科技股。未審查 preprint。 |
| 第三代 | FLAG-Trader (arXiv:2502.11433) | **非 ACL 2025**，是未審查 preprint。135M fine-tuned model vs GPT-4 zero-shot 不完全公平。只測 6 個資產。 |

### Ensemble 的補充說明

FinRL Contest Ensemble (arXiv:2501.10709) 數字正確，但：
- **Solo PPO 表現其實更好**：Return 63.37% vs Ensemble 62.60%，Sharpe 1.55 vs 1.48
- Ensemble 的優勢**僅在 MDD**：-8.98% vs PPO -9.96%
- Ensemble 的價值是**風險控制**，不是回報最大化

---

*調查日期: 2026-04-03*
*來源驗證: 見 `source_verification_2026.md`*
*原始來源: arXiv:2512.10913, arXiv:2501.10709, arXiv:2508.02366, arXiv:2502.11433, arXiv:2504.02281, arXiv:2501.04421*