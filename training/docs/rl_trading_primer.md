# RL 交易入門 — 基於 FinRL 和 FinRL-DeepSeek 論文

本文件從兩篇論文出發，解釋本專案的 RL 訓練在做什麼。
假設讀者有交易經驗但不熟悉 RL，遇到必要的 RL 概念會就地解釋。

**論文來源**：
- **FinRL** (arXiv:2011.09607) — 基礎框架：怎麼用 RL 做股票交易
- **FinRL-DeepSeek** (arXiv:2502.07393) — 我們的上游：加入 LLM 情緒和風險約束

---

## 第一層：為什麼用 RL 做交易

### 傳統量化 vs RL 量化

傳統量化交易是**人寫規則**：

```
如果 RSI < 30 且均線向上 → 買入
如果 RSI > 70 → 賣出
```

問題：閾值怎麼定？30 和 70 是最好的嗎？多個指標怎麼組合？134 支股票的聯動怎麼處理？

RL 的做法：**不寫規則，讓 agent（代理人）自己從數據中學習**。
你只需要告訴它「你能看到什麼」（state）、「你能做什麼」（action）、
「什麼是好的」（reward），它自己想辦法找到最佳策略。

---

## 第二層：MDP — RL 的數學框架

> FinRL 論文 Section 3：「We model automated stock trading as a Markov Decision Process (MDP)」

### 什麼是 MDP

MDP（Markov Decision Process，馬可夫決策過程）是 RL 問題的標準數學框架。
不需要深入數學，只需理解它的四個組件：

```
MDP = (State, Action, Reward, Transition)

每一步：
  Agent 觀察 State → 做出 Action → 環境給出 Reward → 進入下一個 State
  ↑_____________________________________________________________|
                    （重複直到結束）
```

**Markov 性質**（核心假設）：下一步的結果只取決於「現在的狀態」和「現在的行動」，
不取決於歷史。在交易中，這意味著 state 裡需要包含足夠的資訊（價格、指標、持股等），
讓 agent 不需要回頭看歷史就能做出好決定。

### 在股票交易中，MDP 長什麼樣

以下是 FinRL 論文定義的 MDP 組件，以及我們專案的具體實現：

#### State（狀態）— agent 每天看到的「世界」

| 成分 | 維度 | 說明 |
|------|------|------|
| 現金餘額 | 1 | 帳戶裡還有多少現金 |
| 收盤價 | N | 每支股票今天的收盤價 |
| 持股數 | N | 每支股票現在持有幾股 |
| 技術指標 | K × N | 8 個指標（MACD, RSI 等）× 每支股票 |
| 情緒分數 | N | LLM 給的 1-5 分（FinRL-DeepSeek 新增） |
| 風險分數 | N | LLM 給的 1-5 分（僅 CPPO，FinRL-DeepSeek 新增） |

我們的具體數字（134 支 Polygon 股票，8 個技術指標）：

```
PPO  state = 1 + 134 + 134 + (8 × 134) + 134 = 1,475 維
CPPO state = 1 + 134 + 134 + (8 × 134) + 134 + 134 = 1,609 維
```

#### Action（行動）— agent 每天做的「決策」

```
Action = 134 個浮點數，每個在 [-1, 1] 之間

正值 = 買入（值越大買越多）
負值 = 賣出
接近 0 = 不動

實際交易量 = action × hmax (100) → 取整數 → 扣手續費後執行
```

FinRL 論文對 action space 的定義：`a ∈ {-k, ..., -1, 0, 1, ..., k}`，
其中 k 是每次交易最大股數。我們用連續版本（Box space），更精細。

#### Reward（回報）— 怎麼定義「好」

```
reward = (本步結束後的總資產 - 本步開始時的總資產) × reward_scaling

其中 reward_scaling = 1e-4（把百萬級別的資產變化縮小到合理的數值範圍）
總資產 = 現金 + Σ(持股數 × 股價)
```

> FinRL 論文提供了多種 reward 函式（portfolio value change、log return、Sharpe ratio）。
> FinRL-DeepSeek 和我們使用最簡單的 portfolio value change。

#### Transition（轉移）— 世界怎麼變化

Agent 做完交易後，環境推進到下一個交易日，載入真實的歷史價格。
這不是模擬或預測 — 就是回放真實的歷史行情。

#### Episode（回合）— 一次完整的交易模擬

```
Episode 開始：2022-01-03，100 萬現金，0 持股
  → 每天看 state → 做 action → 拿 reward → 下一天
Episode 結束：2024-12-31（最後一個交易日）

一個 episode ≈ 752 個交易日（3 年）
```

#### Discount Factor γ（折扣因子）

未來的 reward 比現在的值錢嗎？γ 控制這個：

```
γ = 0.995（我們的設定）

今天賺 $1 的價值 = $1
明天賺 $1 的價值 = $1 × 0.995 = $0.995
一年後（252天）賺 $1 的價值 = $1 × 0.995^252 ≈ $0.28

含義：agent 重視近期回報，但不完全忽略遠期
```

---

## 第三層：PPO — agent 怎麼學習

> FinRL-DeepSeek 使用的核心演算法，基於 Schulman et al. (2017)。

### 先理解：Policy 和 Value

PPO 有兩個神經網路：

**Policy 網路 π（Actor）** — 「在這個狀態下，我該怎麼交易」

```
輸入：1475 維 state
輸出：134 維 action（每支股票的買賣量）

這是一個 Gaussian Actor：
  網路輸出每支股票的 action 均值 μ
  加上一個可學習的標準差 σ
  實際 action 從 Normal(μ, σ) 抽樣

σ 大 → 探索（多嘗試不同交易）
σ 小 → 利用（執行已學好的策略）
```

**Value 網路 V（Critic）** — 「在這個狀態下，預期還能賺多少」

```
輸入：1475 維 state
輸出：1 個數字（未來所有 reward 的折扣總和估計）

用途：計算 Advantage（見下文）
```

兩個網路各有一個 MLP（多層感知器）：`[輸入層] → [512] → [512] → [輸出層]`。
共約 210 萬個可學習的參數。

### Advantage — 「這個行動比平均好多少」

這是 PPO 的核心概念：

```
Advantage A_t = 實際得到的回報 - Value 網路預測的回報

A_t > 0 → 這個行動比「預期」好 → 應該強化
A_t < 0 → 這個行動比「預期」差 → 應該抑制
A_t ≈ 0 → 這個行動跟「預期」差不多 → 不太需要調整
```

實際計算用 **GAE-Lambda**（Generalized Advantage Estimation）：

```
δ_t = reward_t + γ × V(s_{t+1}) - V(s_t)     ← 單步 TD 誤差
A_t = δ_t + (γλ)δ_{t+1} + (γλ)²δ_{t+2} + ... ← 多步加權平均

λ = 0.95（我們的設定）
λ 接近 1 → 更多依賴實際回報（高方差，低偏差）
λ 接近 0 → 更多依賴 V 預測（低方差，高偏差）
```

### PPO 的更新規則 — 「學但不要學太猛」

每個 epoch，agent 做三件事：

```
1. 用現有策略收集經驗（20,000 步的 state-action-reward）
2. 用經驗計算每個行動的 Advantage
3. 更新策略（讓好的行動更可能、壞的行動更不可能）
```

第 3 步是 PPO 的精髓。普通的 Policy Gradient 會直接最大化：

```
L = E[π_new(a|s) / π_old(a|s) × A]
    ↑ 概率比（ratio）         ↑ 優勢
```

問題：如果某個行動的 Advantage 很大，ratio 可能被推得很高，
導致策略一步跳太遠 → 下一輪表現崩壞（這叫 policy collapse）。

PPO 的解法 — **Clip（裁剪）**：

```
L_PPO = E[min(ratio × A, clip(ratio, 1-ε, 1+ε) × A)]

clip(ratio, 0.3, 1.7) 意味著：
  ratio 最小 0.3，最大 1.7（我們用 ε = 0.7）
  → 每次更新最多只能把行動概率改變到 0.3x ~ 1.7x

標準 PPO 用 ε = 0.2（ratio 0.8~1.2），我們用 0.7 更激進
```

加上 KL 散度的 early stopping 作為第二道保險：

```
如果新策略和舊策略差異（KL）> 1.5 × target_kl (0.35)
→ 立刻停止本輪更新
→ 訓練輸出裡的 StopIter 就是這個機制觸發的位置
```

### 一個 Epoch 的完整流程

```
┌─── 收集階段 ─────────────────────────────────────────┐
│                                                      │
│  4 個 MPI worker 各收集 5,000 步經驗（共 20,000 步）   │
│  每步：                                               │
│    state → Policy 網路 → action → 環境 → reward       │
│    存到 buffer：(state, action, reward, value, logp)   │
│                                                      │
└──────────────────────┬───────────────────────────────┘
                       ↓
┌─── 更新階段 ─────────────────────────────────────────┐
│                                                      │
│  1. 用 buffer 裡的數據計算 Advantage（GAE-Lambda）     │
│  2. 更新 Policy：最多 100 步 gradient descent          │
│     每步檢查 KL，太大就提前停（StopIter）              │
│  3. 更新 Value：100 步 gradient descent                │
│  4. MPI 平均所有 worker 的 gradient                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 第四層：FinRL-DeepSeek 的兩個創新

> 論文標題：「LLM-Infused Risk-Sensitive Reinforcement Learning for Trading Agents」

FinRL-DeepSeek 在標準 FinRL 的基礎上加了兩個東西：

### 創新 1：LLM 情緒分數影響交易行動

**數據來源**：FNSPID 數據集（1570 萬條金融新聞，1999-2023），
每支股票每天隨機選一篇，用 LLM 評分。

**兩個 prompt**：

```
情緒（Stock Recommendation）：
  「你是有股票推薦經驗的金融專家。根據特定股票，評分 1-5，
   1=負面, 2=偏負面, 3=中性, 4=偏正面, 5=正面」

風險（Risk Assessment）：
  「你是專門做風險評估的金融專家。根據特定股票，評分 1-5，
   1=非常低風險, 2=低風險, 3=中等風險, 4=高風險, 5=非常高風險」
```

**情緒怎麼影響交易**（Action Modification）：

在環境的 `step()` 裡，agent 輸出 action 後，環境根據情緒分數調整幅度：

```
例：agent 對 NVDA 說「買 50 股」，同時 NVDA 的情緒 = 5（正面）

情緒正面 + 買入 = 方向一致 → 實際買 50 × 1.10 = 55 股（鼓勵）
情緒負面 + 買入 = 方向矛盾 → 實際買 50 × 0.90 = 45 股（抑制）
```

完整的縮放表（我們用的 ±10% 版本）：

| 情況 | 縮放係數 |
|------|---------|
| 情緒 5 + 買入，或情緒 1 + 賣出（強烈一致） | 1.10 |
| 情緒 4 + 買入，或情緒 2 + 賣出（中度一致） | 1.05 |
| 情緒 3（中性） | 0.98 |
| 情緒 2 + 買入，或情緒 4 + 賣出（中度矛盾） | 0.95 |
| 情緒 1 + 買入，或情緒 5 + 賣出（強烈矛盾） | 0.90 |

> **論文也測了 ±1% 和 ±0.1% 版本**。結果：
> PPO 加上情緒後效果**反而變差**（所有強度都是）。
> CPPO 加上情緒後效果**改善**，10% 強度最好。
> 這是論文的核心發現 — 情緒信號在有風險約束時才有用。

### 創新 2：CVaR-PPO（CPPO）— 加入風險約束

普通 PPO 只追求「賺最多」。CPPO 追求「賺最多，但最差情況不能太慘」。

**CVaR（Conditional Value at Risk）** — 用白話解釋：

```
「如果你的策略跑 100 次，把結果從差到好排列，
 最差的 15 次（α=0.85）的平均虧損是多少？」

CVaR 就是這個數字。越接近 0 越好（尾部風險小）。
```

**CPPO 的目標函數**：

```
標準 PPO：  max 期望回報
CPPO：      max 期望回報
            subject to CVaR ≥ 某個閾值（不能虧太慘）
```

實現方式（不用數學細節）：

```
1. 每個 episode 結束後，計算這次的回報
2. 如果回報低於門檻 ν → 在 Advantage 上加懲罰
   → agent 學到「這類行動會導致大虧」→ 避開
3. 門檻 ν 和懲罰強度自適應調整
```

**風險分數怎麼介入**：

CPPO 環境裡，LLM 風險分數有兩個作用：

1. **直接抑制高風險交易**：風險 ≥ 4 的股票，action 乘以 0.8
2. **調整 CVaR 約束**：高風險股票的倉位會加重 CVaR 計算，讓約束更嚴格

---

## 第五層：我們的專案相對於上游

### 繼承鏈

```
FinRL (AI4Finance)          ← 框架：環境設計、MDP 建模
  └→ FinRL-DeepSeek (benstaf) ← 論文：LLM 情緒 + CPPO
      └→ MindfulRL-Intraday    ← 我們：新數據、修 bug、生產化
```

### 我們改了什麼

| 改動 | 原因 |
|------|------|
| 情緒縮放從 ±0.1% 改為 ±10% | 論文結果顯示 10% 效果最好 |
| 修復 CPPOBuffer.finish_path() bug | 上游對整個 buffer 重複扣減，應只扣當前 path |
| 修復 _initiate_state() 漏 LLM 欄位 | 上游 state 維度不一致 |
| 股票從 NASDAQ 100 改為 Polygon 146 支 | 使用我們自己的數據源和 LLM 評分 |
| LLM 從 DeepSeek V3 改為 GPT-5.x | 模型升級，多模型 coalesce |
| 新增 SB3 PPO (GPU) 版本 | SpinningUp 只能 CPU |

### 我們沒改的

- 環境的 MDP 建模（state/action/reward 結構）
- PPO / CPPO 的核心演算法邏輯
- 情緒縮放的作用機制（在 env.step() 裡調整 action）
- 超參數（clip_ratio=0.7, gamma=0.995 等）

---

## 論文的關鍵發現（影響我們的決策）

### 發現 1：PPO 加情緒反而變差

| 模型 | Information Ratio |
|------|------------------|
| PPO（無 LLM） | 0.0100 |
| PPO + DeepSeek 10% | -0.0093 |
| PPO + DeepSeek 1% | -0.0252 |
| PPO + DeepSeek 0.1% | -0.0011 |

情緒信號在 PPO 上是**噪音**，干擾學習。

### 發現 2：CPPO 加情緒變好

| 模型 | Information Ratio |
|------|------------------|
| CPPO（無 LLM） | -0.0148 |
| CPPO + DeepSeek 10% | 0.0078 |

只有在**風險約束存在時**，情緒信號才有正面作用。
論文的解釋：風險約束限制了 agent 的行動空間，情緒信號在這個受限空間內
提供了有用的方向引導。沒有約束時，agent 自由度太大，情緒信號反而是噪音。

### 發現 3：訓練時間很重要

論文比較了 500K 步（25 epochs）和 2M 步（100 epochs）的差異：
- 短訓練：策略不穩定，不同 seed 結果差異大
- 長訓練：明顯更穩定

### 對我們的影響

1. **先跑 PPO 驗證 pipeline**，但不要對 PPO + 情緒抱太高期待
2. **CPPO 才是重點** — 情緒信號在 CPPO 下才有正面效果
3. **100 epochs 是合理的起點**，不要太早下結論
4. **結果有隨機性** — 同樣的設定跑不同 seed 可能差很多

---

## 推薦學習路徑

如果想更深入理解，按以下順序閱讀：

1. **SpinningUp 文件** — https://spinningup.openai.com/en/latest/
   Part 1: Key Concepts → Part 3: PPO。有直覺解釋 + 數學推導。

2. **Lilian Weng: Policy Gradient** — https://lilianweng.github.io/posts/2018-04-08-policy-gradient/
   從最基礎的 Policy Gradient 到 PPO 的演進，非常清楚。

3. **FinRL 論文** — https://arxiv.org/abs/2011.09607
   重點讀 Section 3（MDP 建模）和 Section 4（環境設計）。

4. **FinRL-DeepSeek 論文** — https://arxiv.org/abs/2502.07393
   重點讀 Section 2（LLM prompt 設計）和 Section 3（CPPO 公式）。

5. **本專案的 `training/UPSTREAM.md`** — 上游代碼的 bug 和我們的修復。

---

*最後更新: 2026-03-28*