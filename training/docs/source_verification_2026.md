# 研究來源驗證報告

**日期**: 2026-04-03
**目的**: 驗證 algorithm_survey_2026.md 中引用的論文聲明是否準確

---

## 驗證結果摘要

| 論文 | 嚴重度 | 問題 |
|------|--------|------|
| Paper 1 (meta-study) | **中** | p=0.640 是 PG vs DQN，不是 PPO vs SAC |
| Paper 2 (Ensemble) | **低** | 數字正確，但遺漏了 solo PPO 其實更好的資訊 |
| Paper 3 (LLM Guide) | **低** | 數字正確 |
| Paper 4 (FLAG-Trader) | **高** | 「ACL 2025」為偽 — 是未審查的 preprint |
| Paper 5 (FinRL Contest) | **嚴重** | 62.16%、1.96 Sharpe、Oct 2025-Mar 2026 全部不存在於論文中 |
| Paper 6 (Distributional RL) | **低** | 數字正確 |

---

## Paper 1: Meta-Study — 演算法重要性

**論文**: "Reinforcement Learning in Financial Decision Making: A Systematic Review"
**作者**: Hoque, Ferdaus, Hassan — University of New Orleans
**URL**: https://arxiv.org/abs/2512.10913
**狀態**: arXiv preprint，聲稱投稿 Management Science，**尚未接受**

| 聲明 | 實際 | 判定 |
|------|------|------|
| 167 studies | 167 articles (2017-2025, 從 2,847 篇篩選) | 正確 |
| Algorithm importance = 0.08 | "Algorithm family" = 0.08 (Random Forest feature importance, Figure 4) | **標籤略有差異** — 原文是 "Algorithm family" |
| Implementation complexity = 0.31 | "Complexity score" = 0.31 (最高預測因子) | **標籤有差異** — 原文是 "Complexity score" |
| PPO vs SAC p=0.640 | **PG (Policy Gradient) vs DQN, p=0.640** | **錯誤** — 比較的演算法被搞混了 |

**修正**：p=0.640 表示的是 Policy Gradient 類（包含 PPO、A2C 等）vs DQN 類的差異不顯著。
這仍然支持「演算法選擇不是最重要因素」的結論，但比較對象不是 PPO vs SAC。

**注意**：此論文未經 peer review，且 feature importance 分析基於 meta-data 的 proxy 指標
而非直接的 A/B 實驗。結論方向可能正確但具體數字的精確度有限。

---

## Paper 2: Ensemble — FinRL Contest

**論文**: "Revisiting Ensemble Methods for Stock Trading and Crypto Trading Tasks at ACM ICAIF FinRL Contest 2023-2024"
**作者**: Holzer, Wang, Xiao, Liu
**URL**: https://arxiv.org/abs/2501.10709
**狀態**: arXiv preprint，描述 ACM ICAIF contest 工作

| 聲明 | 實際 (Table 5) | 判定 |
|------|---------------|------|
| PPO+SAC+DDPG ensemble | Ensemble-1: 1 PPO + 1 SAC + 1 DDPG | 正確 |
| MDD -8.98% | -8.98% | 正確 |
| Sharpe 1.48 | 1.48 | 正確 |

**遺漏的重要資訊**：
- **Solo PPO 表現其實更好**：Return 63.37% vs Ensemble 62.60%，Sharpe 1.55 vs 1.48
- Ensemble 的優勢**僅在 MDD**：-8.98% vs PPO -9.96%、DDPG -13.15%
- 資產：30 支 Dow Jones 股票，2021-01-01 ~ 2023-12-01

**修正**：之前說「Ensemble 是冠軍做法」有誤導 — Ensemble 的 Sharpe 和 Return 比 solo PPO 差，
只有 MDD 更好。Ensemble 的價值在**風險控制**而非回報最大化。

---

## Paper 3: LLM Strategy Guide（第二代）

**論文**: "Language Model Guided Reinforcement Learning in Quantitative Trading"
**作者**: Darmanin, Vella（機構未註明）
**URL**: https://arxiv.org/abs/2508.02366
**狀態**: arXiv preprint，**無 peer review**

| 聲明 | 實際 | 判定 |
|------|------|------|
| Strategist + Analyst LLMs | Strategist (LONG/SHORT + confidence 1-3) + Analyst (sentiment) | 正確 |
| Guidance scalar | tau = dir(π_g) × str(π_g)，追加到 RL obs | 正確 |
| Mean Sharpe 1.10 vs 0.64 | LLM+RL = 1.10, RL-Only = 0.64 (Table, Experiment 2) | 正確 |

**補充細節**：
- LLM: GPT-4o Mini (128k context)
- RL: **DDQN**（不是 PPO/SAC）
- 測試: 2018-2020, **只有 6 支 mega-cap 科技股** (AAPL, AMZN, GOOGL, META, MSFT, TSLA)
- **LLM-Only baseline 也達到 Sharpe 1.03** — 很接近 LLM+RL 的 1.10
- 未註明作者機構，未經 peer review

**注意**：LLM-Only (1.03) vs LLM+RL (1.10) 差距很小，RL 的實際增量貢獻存疑。
6 支科技股在 2018-2020 的表現可能不具泛化性。

---

## Paper 4: FLAG-Trader（第三代）

**論文**: "FLAG-Trader: Fusion LLM-Agent with Gradient-based Reinforcement Learning for Financial Trading"
**作者**: Xiong, Deng, Wang, Cao, Li, Yu, Peng, Lin, Smith, Liu, Huang, Ananiadou, Xie
**機構**: Harvard, Stevens, Columbia, UMN, NVIDIA, RPI, TheFinAI, U of Manchester
**URL**: https://arxiv.org/abs/2502.11433
**狀態**: **arXiv preprint，非 ACL 2025**

| 聲明 | 實際 | 判定 |
|------|------|------|
| ACL 2025 接收 | **論文中完全沒有提到 ACL** | **錯誤 — 是 agent 幻覺** |
| 135M model | SmolLM2-135M-Instruct | 正確 |
| Outperforms GPT-4 | 在部分資產上勝出（MSFT SR 1.373 vs 0.932），非全面勝出 | **部分正確** |
| Harvard/Columbia/NVIDIA | 是 8 個機構中的 3 個 | 正確但不完整 |

**修正**：FLAG-Trader **不是** ACL 2025 論文，是未審查的 arXiv preprint。
「outperforms GPT-4」有限定條件 — 只在部分資產/指標上。
135M 模型是經過 RL fine-tuning 的，跟 GPT-4 的 zero-shot 比較不完全公平。
只測了 6 個資產（5 股票 + BTC），短期測試窗口。

---

## Paper 5: FinRL Contest

**論文**: "FinRL Contests: Benchmarking Data-driven Financial Reinforcement Learning Agents"
**作者**: Wang, Holzer, Xia, Cao, Gao, Walid, Xiao, Liu
**URL**: https://arxiv.org/abs/2504.02281
**狀態**: arXiv preprint

| 聲明 | 實際 | 判定 |
|------|------|------|
| 62.16% annualized return | **不存在於論文中** | **虛構** |
| 1.96 Sharpe | **不存在於論文中** | **虛構** |
| Oct 2025 - Mar 2026 | **不存在於論文中** | **虛構** |

**論文中實際的數字** (Table 6, 2025 Contest):
- Otago Alpha (PPO): Return 191.14%, Sharpe 1.0800, MDD -28.16%
- Ruijian & Sally (GRPO): Return 335.57%, Sharpe 0.9500, MDD -50.24%

**修正**：62.16%、1.96 Sharpe、Oct 2025-Mar 2026 這三個數字是 agent 搜索過程中的幻覺，
論文中完全不存在。必須從所有文檔中移除。

---

## Paper 6: Distributional RL (C51/IQN)

**論文**: "Risk-averse policies for natural gas futures trading using distributional reinforcement learning"
**作者**: Heche, Nigro, Barakat, Robert-Nicoud
**URL**: https://arxiv.org/abs/2501.04421
**狀態**: arXiv preprint

| 聲明 | 實際 (Table 1) | 判定 |
|------|---------------|------|
| C51 32% improvement | C51 (881.86) vs DQN (663.6) = 32.9% improvement in P&L | 正確 |
| IQN CVaR maximization | IQN_alpha 修改 sampling distribution 實現 CVaR | 正確 |

**補充**：
- 資產: 天然氣期貨 (TTF, Dutch hub)，不是股票
- 風險敏感版本（C51_0.7, IQN_0.7）的 P&L **反而下降** — 風險控制有回報代價
- 指標是 EUR/MWh P&L，不是 Sharpe ratio

---

## 對文檔的影響

### 必須修正

1. **algorithm_survey_2026.md**: 移除「PPO vs SAC p=0.640」→ 改為「PG vs DQN p=0.640」
2. **algorithm_survey_2026.md**: 移除 FinRL-X 的 62.16%/1.96 Sharpe（虛構數字）
3. **algorithm_survey_2026.md**: FLAG-Trader 「ACL 2025」→「arXiv preprint（未審查）」
4. **experiment_log.md**: 如有引用以上數字也需修正

### 應補充的 caveat

1. Ensemble 的 Sharpe/Return 其實比 solo PPO 差，只有 MDD 更好
2. LLM Strategy Guide 的 LLM-Only baseline 已經 Sharpe 1.03（RL 增量很小）
3. FLAG-Trader 的「超越 GPT-4」是 fine-tuned vs zero-shot 的不公平比較
4. meta-study 是未審查 preprint，feature importance 基於 proxy 指標

---

*驗證方法: agent 直接 fetch 論文 PDF/HTML 內容，逐一比對具體數字*