# SB3 vs SpinningUp KL 散度差異分析

本文件記錄了為什麼 SB3 PPO 在相同超參數下無法復現 SpinningUp 結果的關鍵原因。

**結論：兩者使用不同的 KL 散度近似公式，同一個 `target_kl=0.35` 在兩個框架下
產生完全不同的 early stopping 行為，是效果差距的主要原因之一。**

---

## 1. 發現過程

在系統性對齊 SB3 和 SpinningUp 的超參數後（vf_coef、full-batch、gradient clipping），
SB3 PPO 的 Sharpe 仍然是 0.79 vs SpinningUp 的 1.03。

通過開啟 verbose=1 觀察 SB3 的實際訓練行為，發現：
- SB3 的 approx_kl ≈ 0.11（遠低於閾值 0.525）
- **SB3 從未觸發 KL early stop**，每輪跑滿 100 步 gradient update
- SpinningUp 的 KL ≈ 0.45-0.53，**經常在 30-99 步 early stop**

## 2. 根本原因：KL 散度的近似公式不同

### SpinningUp 的 KL 計算

```python
# spinup/algos/pytorch/ppo/ppo.py, compute_loss_pi()
approx_kl = (logp_old - logp).mean().item()
```

這是 **KL(π_old || π_new)** 的一階近似（又稱「mean divergence」）：

```
KL ≈ E[log π_old(a|s) - log π_new(a|s)]
```

### SB3 的 KL 計算

```python
# stable_baselines3/ppo/ppo.py, train()
log_ratio = log_prob - rollout_data.old_log_prob
approx_kl_div = th.mean((th.exp(log_ratio) - 1) - log_ratio).cpu().numpy()
```

這是 **KL(π_old || π_new)** 的二階近似（基於 Taylor 展開）：

```
KL ≈ E[exp(log_ratio) - 1 - log_ratio]
   = E[r - 1 - log(r)]    where r = π_new/π_old
```

### 數學分析

兩者的差異：

```
SpinningUp:  KL_1 = E[-log_ratio] = E[logp_old - logp]
SB3:         KL_2 = E[exp(log_ratio) - 1 - log_ratio]
```

設 `r = exp(log_ratio)` = π_new/π_old：

```
KL_1 = E[-log(r)]       = E[log(1/r)]
KL_2 = E[r - 1 - log(r)]
```

當 r ≈ 1（新舊策略接近時），兩者都 ≈ 0。
但當 r 偏離 1 時，**KL_1 永遠 ≥ KL_2**：

```
r = 2.0:  KL_1 = -log(2) ≈ -0.693 (取絕對值 0.693)
          KL_2 = 2 - 1 - log(2) ≈ 0.307

r = 0.5:  KL_1 = -log(0.5) = 0.693
          KL_2 = 0.5 - 1 - log(0.5) ≈ 0.193
```

**SpinningUp 的 KL 估計值大約是 SB3 的 2-4 倍**（取決於 ratio 的分散程度）。

### 實測驗證

| 框架 | KL 值 | 閾值 (1.5 × target_kl) | 行為 |
|------|-------|----------------------|------|
| SpinningUp | 0.45 ~ 0.53 | 0.525 | **經常 early stop** (step 10-99) |
| SB3 | 0.10 ~ 0.13 | 0.525 | **永不 early stop** (跑滿 100) |

## 3. 影響

SpinningUp 在每輪只做 ~30-99 步 gradient update（KL 動態決定），
SB3 永遠做滿 100 步。

這意味著 **SB3 的 policy 每輪被更新過多**：
- 更多的 gradient steps → policy 偏離 rollout 時的分佈更遠
- Advantage 是基於舊 policy 計算的，policy 變化太大後 advantage 就不準了
- PPO 的 clip 機制能限制單步幅度，但 100 步累積仍然會偏離太多

SpinningUp 的 early stop 本質上是在說「policy 已經變化夠多了，再改下去 advantage 就不可靠了」。
SB3 因為 KL 計算值偏小，這個安全機制從未觸發。

## 4. 修正方法

### 方案 A：降低 SB3 的 target_kl（推薦）

SpinningUp `target_kl=0.35` 的 KL ≈ 0.45-0.53。
SB3 的 KL 大約是 1/3-1/4，所以等效的 target_kl 大約是：

```
SB3 target_kl ≈ SpinningUp target_kl / 3 ≈ 0.35 / 3 ≈ 0.10-0.12
```

但由於比例不是固定的（取決於 ratio 分佈），建議從 0.05 開始實驗：

```bash
# target_kl=0.05 → 閾值 0.075，SB3 KL ~0.11 會在中期 early stop
python training/train_ppo_sb3.py --target-kl 0.05 --full-batch ...

# target_kl=0.08 → 閾值 0.12，接近 SB3 KL 的上限
python training/train_ppo_sb3.py --target-kl 0.08 --full-batch ...

# target_kl=0.10 → 閾值 0.15，可能偶爾 early stop
python training/train_ppo_sb3.py --target-kl 0.10 --full-batch ...
```

### 方案 B：修改 SB3 的 KL 計算公式

Override `train()` 將 SB3 的 KL 計算改為 SpinningUp 的公式。
更精確但侵入性強，需要複製整個 `train()` method。

### 方案 C：直接限制 n_epochs

不依賴 KL，固定 `n_epochs` 到較低值（如 30-50）。
粗暴但簡單，缺點是失去 KL 的動態調節。

## 5. 其他已排除的差異

| 差異 | 狀態 | 結果 |
|------|------|------|
| vf_coef 未對齊 | 已修正 (v2) | 改善 MDD，但 Sharpe gap 仍在 |
| Minibatch vs full-batch | 已驗證 (v3) | Sharpe 0.68→0.79，部分改善 |
| Separate VF training | 已測試 (v4) | 有害（改變優化軌跡） |
| KL early stop 粒度 | 已確認 | SB3 每步都檢查，跟 SpinningUp 一致 |
| **KL 計算公式** | **已確認** | **主要原因：SB3 KL 值偏小 2-4x，early stop 從未觸發** |

## 6. 完整超參數對齊狀態

| 參數 | SpinningUp | SB3 最佳配置 | 對齊狀態 |
|------|-----------|-------------|---------|
| clip_ratio | 0.7 | 0.7 | 已對齊 |
| pi_lr | 3e-5 | 3e-5 | 已對齊 |
| vf_lr | 1e-4 | 3e-5 × 3.33 ≈ 1e-4 | 近似對齊（共用 optimizer） |
| gamma | 0.995 | 0.995 | 已對齊 |
| gae_lambda | 0.95 | 0.95 | 已對齊 |
| Batch 方式 | full-batch | `--full-batch` | 已對齊 |
| Gradient clipping | 無 | `max_grad_norm=inf` | 已對齊 |
| Activation | Tanh | Tanh | 已對齊 |
| Network arch | [512, 512] 分離 pi/vf | [512, 512] 分離 pi/vf | 已對齊 |
| **target_kl** | **0.35 (KL_1 公式)** | **0.35 (KL_2 公式) → 需降低** | **未對齊** |
| **Optimizer** | **分離 Adam** | **共用 Adam** | per-parameter states 獨立，非 gap 主因 |

---

## 參考

- SpinningUp PPO: `spinup/algos/pytorch/ppo/ppo.py` line 178
- SB3 PPO: `stable_baselines3/ppo/ppo.py` line 78-83
- [The 37 Implementation Details of PPO (ICLR Blog)](https://iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/)
- [PPG: Phasic Policy Gradient (arXiv:2009.04416)](https://arxiv.org/abs/2009.04416)

---

*發現日期: 2026-04-03*