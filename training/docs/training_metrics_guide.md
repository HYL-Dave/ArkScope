# 訓練指標指南

本文件解釋 PPO/CPPO 訓練過程中輸出的所有指標，以及如何判讀訓練狀態。

## 先理解核心概念

### RL 訓練在做什麼

想像你僱了一個新手交易員（agent），給他一段歷史行情（environment），讓他反覆練習：

```
Episode 1: 從 2022-01-03 走到 2024-12-31，最終虧了 80 萬
Episode 2: 同樣的行情再走一次，但策略稍微調整，虧了 50 萬
Episode 3: 又走一次，虧 20 萬
...
Episode N: 走完，賺了 17 萬
```

每次走完（一個 **episode**），agent 會根據結果更新自己的策略（**policy**）：
- 哪些 state 下買入賺了？→ 強化這個行為
- 哪些 state 下賣出虧了？→ 抑制這個行為

一個 **epoch** = 收集固定步數的經驗（20,000 步）→ 用這些經驗更新一次策略。
100 epochs = 更新 100 次策略，每次都基於最新的經驗。

### 兩個神經網路

PPO 有兩個網路，各司其職：

| 網路 | 角色 | 輸入 | 輸出 |
|------|------|------|------|
| **Policy (π)** | 交易員的「直覺」 | 當前 state（價格、指標、情緒分數） | 每支股票買/賣多少 |
| **Value (V)** | 交易員的「預期」 | 當前 state | 「從現在到結束，我估計還能賺多少」 |

Policy 決定行動，Value 用來評估行動的好壞（計算 advantage）。

### State 向量（你的 1475 維）

agent 每天看到的「世界狀態」：

```
[現金] + [134 支股票價格] + [134 支持股數] + [134 × 8 個技術指標] + [134 個情緒分數]
= 1 + 134 + 134 + 1072 + 134 = 1475
```

### Action（你的 134 維）

每天對 134 支股票各輸出一個 [-1, 1] 的值：
- 正值 = 買入（越大買越多）
- 負值 = 賣出
- 接近 0 = 不動

這個值會被環境裡的情緒縮放（sentiment scaling）調整後，再乘以 hmax=100 得到實際交易股數。

### Reward（回報）

每步的 reward = portfolio 價值變化 × reward_scaling (1e-4)。
累計 reward（EpRet）= 整個 episode 的總回報，反映策略的盈虧。

---

## 每 Epoch 指標詳解

### 回報指標 — 策略賺不賺錢

| 指標 | 含義 | 怎麼看 |
|------|------|--------|
| **AverageEpRet** | 所有完成 episode 的平均總回報 | **最重要**。正 = 賺，越高越好。100 epochs 內應穩定上升 |
| **StdEpRet** | 回報的標準差 | 越小越好 = 策略穩定。初期大是正常的 |
| **MaxEpRet** | 最好的 episode 回報 | 參考上限 |
| **MinEpRet** | 最差的 episode 回報 | 如果一直很負，策略可能有系統性問題 |
| **EpLen** | Episode 平均長度（步數） | 你的 752 = 完整走完 train 期的所有交易日 |

**典型的學習曲線：**

```
Epoch  0: AverageEpRet =   10  ← 幾乎隨機
Epoch 10: AverageEpRet =  100  ← 開始學到東西
Epoch 30: AverageEpRet =  250  ← 策略在改善
Epoch 60: AverageEpRet =  300  ← 趨於穩定
Epoch 80: AverageEpRet =  310  ← 接近收斂
Epoch 99: AverageEpRet =  320  ← 收斂
```

如果 AverageEpRet 一直在 0 附近震盪不上去 → 超參數可能需要調整。

### Value Function 指標 — agent 的自我評估準不準

| 指標 | 含義 | 怎麼看 |
|------|------|--------|
| **AverageVVals** | Value 函數的平均預測值 | 應該逐漸接近 AverageEpRet（V 在學習預測真實回報） |
| **StdVVals** | V 值的離散度 | 初期高（agent 不確定），後期應穩定 |
| **MaxVVals / MinVVals** | 最樂觀和最悲觀的估值 | 差距太大 = V 函數還沒校準好 |

**健康信號：** AverageVVals 隨訓練慢慢追上 AverageEpRet。
**警告信號：** VVals 遠大於 EpRet → V 過度樂觀（overestimation）。

### PPO 演算法指標 — 訓練過程穩不穩定

| 指標 | 含義 | 怎麼看 |
|------|------|--------|
| **LossPi** | Policy 損失 | 絕對值不重要，看**趨勢**。應該在波動中緩慢下降 |
| **LossV** | Value 函數損失（MSE） | 應該隨訓練下降（V 預測越來越準） |
| **DeltaLossPi** | 更新後 policy loss 變化 | 負 = 更新改善了策略 |
| **DeltaLossV** | 更新後 V loss 變化 | 負 = V 預測更準了 |
| **Entropy** | Policy 的隨機性 | 高 (>0.8) = 還在探索；低 (<0.1) = 可能過早收斂 |
| **KL** | 新舊 policy 的差異 | PPO 核心：限制每次更新不要改太多 |
| **ClipFrac** | 被 PPO clip 裁剪的比例 | 0.3-0.6 正常；>0.8 = policy 劇烈震盪 |
| **StopIter** | 實際 gradient steps（上限 100） | 10 = KL 太大提前停了；99 = 跑滿（KL 小，可以多更新） |

**PPO 的 Clip 機制（簡單理解）：**

PPO 的核心想法：每次更新策略時不要改太多，否則可能「走歪」。

```
如果這次的行動比舊策略好很多 → 想大幅更新
PPO 說：等一下，最多只能改 clip_ratio (0.7) 這麼多
→ 防止 policy 突然劇變導致崩壞
```

`ClipFrac = 0.55` 意味著 55% 的更新被裁剪了。
`KL > 1.5 × target_kl` 時整輪提前結束（StopIter < 100）。

### 環境摘要 — 每個 Episode 結束時

```
day: 751, episode: 20
begin_total_asset: 1000000.00     ← 初始資金 100 萬
end_total_asset: 1174806.42       ← 最終 portfolio 價值
total_reward: 174806.42           ← 淨利（= end - begin）
total_cost: 23878.97              ← 累計交易手續費
total_trades: 55584               ← 累計交易筆數
Sharpe: 0.340                     ← 該 episode 的年化 Sharpe ratio
```

**Sharpe ratio 解讀：**

| Sharpe | 含義 |
|--------|------|
| < 0 | 虧損 |
| 0 ~ 0.5 | 差，但開始有正回報 |
| 0.5 ~ 1.0 | 一般 |
| 1.0 ~ 2.0 | 不錯 |
| > 2.0 | 很好（但要檢查是否過擬合） |

### 其他

| 指標 | 含義 |
|------|------|
| **TotalEnvInteracts** | 累計環境互動步數，每 epoch +20,000 |
| **Time** | 累計訓練時間（秒） |
| **trajectory cut off** | MPI worker 分到的步數不是 episode 長度的整數倍，最後一個 episode 被截斷。正常現象，不影響訓練 |

---

## 觀察 100 Epochs 訓練時要看什麼

### 好的信號

- AverageEpRet 穩定上升並收斂
- LossV 下降（V 函數越來越準）
- Entropy 緩慢下降（從探索轉向利用）
- StdEpRet 縮小（策略越來越一致）
- Sharpe 穩定為正

### 警告信號

- AverageEpRet 一直在 0 附近震盪 → 學習率或超參數問題
- AverageEpRet 先上升後暴跌 → Policy collapse，clip_ratio 可能太大
- Entropy 突然歸零 → 策略崩潰為確定性行為
- ClipFrac 持續 > 0.8 → 更新太激進
- StopIter 每次都是個位數 → KL 太大，學習率太高

### 需要調參的跡象

| 現象 | 可能原因 | 調整方向 |
|------|----------|----------|
| 學不動（EpRet 不上升） | 學習率太低 | 提高 `--lr` |
| 震盪劇烈 | 學習率太高 or clip 太大 | 降低 lr 或降低 clip_ratio |
| 過早收斂（Entropy → 0） | 探索不足 | 加 entropy bonus 或增大初始隨機性 |
| 訓練不穩（EpRet 暴漲暴跌） | 步數太少 | 增大 `--steps` 收集更多經驗 |

---

## Backtest 指標

訓練完成後用 `backtest.py` 在 trade 資料上跑的指標：

| 指標 | 含義 | 怎麼看 |
|------|------|--------|
| **Final Equity** | 最終 portfolio 價值 | 起始 $1M，>$1M = 賺 |
| **Total Return** | 總回報率 | 正 = 賺，負 = 虧 |
| **Sharpe Ratio** | 風險調整後回報（年化） | >1 不錯，>2 很好 |
| **Max Drawdown** | 最大回撤（從高點到低點的最大跌幅） | -0.10 = 最多虧了高點的 10%。越接近 0 越好 |
| **Calmar Ratio** | 年化回報 / 最大回撤 | >1 代表回報能覆蓋回撤 |
| **Sortino Ratio** | 類似 Sharpe 但只看下行風險 | >1 不錯 |
| **Win Rate** | 每日正回報的天數比例 | >0.5 = 過半的天在賺 |
| **CVaR (95%)** | 最差 5% 天的平均日虧損 | 尾部風險指標，越接近 0 越好 |

**Train 表現好但 Trade 表現差 → 過擬合**（agent 記住了歷史，但沒學到泛化規律）。
這就是為什麼要分 train/trade，trade 指標才是真正的成績單。

---

*最後更新: 2026-03-28*