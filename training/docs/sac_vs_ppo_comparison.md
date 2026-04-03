# SAC vs PPO 實測比較

## 演算法差異

| | PPO (On-policy) | SAC (Off-policy) |
|---|---|---|
| **核心機制** | Clipped surrogate + KL early stop | Maximum entropy + twin critics |
| **經驗使用** | 用完即丟（每輪收集新的） | Replay buffer 反覆使用 |
| **探索** | 靠 policy 的隨機性（σ） | Entropy bonus 自動調節 |
| **需要調的超參** | target_kl, full-batch, vf_coef | 幾乎不用調（ent_coef="auto"） |
| **預設學習率** | 3e-5 | 3e-4（高 10 倍，off-policy 可以更激進） |
| **預設網路** | [512, 512] pi + [512, 512] vf | [256, 256] actor + 2 × [256, 256] critic |
| **Optimizer** | 1 個共用 Adam（SB3）| 分離（actor optimizer + critic optimizer） |

注意：SAC 在 SB3 裡天然就是**分離 optimizer** — actor 和 critic 各有自己的 Adam。
這正是 PPO 在 SB3 裡缺少的（PPO 的分離 optimizer 需要大改，見 `sb3_vs_spinup_optimizer_finding.md`）。

## 實測資源佔用（HuggingFace G5 資料，82 stocks，RTX 4090）

| 資源 | PPO (--full-batch --device cuda) | SAC (--device cuda) |
|------|--------------------------------|---------------------|
| **CPU** | 1 core 滿載（env.step 佔用） | **更低**（off-policy 更新不需等 rollout 完成） |
| **RAM** | ~35-40 GB | ~40 GB（replay buffer 佔額外空間） |
| **VRAM** | ~50 MB | **1.5-2 GB**（twin critics + replay buffer 的 GPU tensor） |

### VRAM 差異說明

PPO VRAM 極低（~50MB）因為模型只有 2M 參數，沒有 replay buffer。
SAC 需要 1.5-2GB 因為：
- Twin critics（2 × Q 網路 + 2 × target Q 網路）
- Replay buffer 中的 batch 在 GPU 上做 gradient
- Actor + critic 的 optimizer states

### 並行容量估算（400GB RAM, 24 cores, 4× RTX 4090 各 24GB）

| 演算法 | 限制因素 | 最大並行 |
|--------|---------|---------|
| PPO full-batch cuda | RAM (~40GB/exp) | ~9-10 個 |
| SAC cuda | RAM (~40GB/exp) + VRAM (~2GB/exp) | ~9 個（RAM 先到限） |

RAM 是兩者的共同瓶頸。VRAM 方面 SAC 每張 4090 可跑 ~12 個（24GB / 2GB），
但 24 cores / RAM 會先不夠。實際差異不大。

## 超參數調校的痛點對比

### PPO 需要手動校準的

1. **target_kl** — SB3 和 SpinningUp 的 KL 公式不同，同一個值行為完全不同
   （詳見 `sb3_kl_divergence_analysis.md`）
2. **full-batch vs minibatch** — full-batch 好 +0.11 Sharpe，但佔更多 CPU
3. **vf_coef** — 需要設成 ~3.33 補償共用 optimizer 的 lr 差異

### SAC 不需要調的

1. **ent_coef="auto"** — 自動調整探索 vs 利用的平衡
2. **target_entropy="auto"** — 自動設為 -dim(action)
3. **無 clip/KL 機制** — SAC 用 soft update (tau) 自然穩定

### SAC 可能需要調的

1. **learning_starts** — 開始學習前的隨機探索步數（預設 1000，可能需要更多）
2. **buffer_size** — 太小丟失早期經驗，太大佔記憶體
3. **gamma** — SAC 預設 0.99，PPO 用 0.995，可能需要對齊測試

## 訓練腳本對照

```bash
# PPO (最佳配置)
python training/train_ppo_sb3.py \
  --data train.csv --epochs 100 --device cuda:0 --seed 42 \
  --full-batch --target-kl 0.05

# SAC
python training/train_sac_sb3.py \
  --data train.csv --epochs 100 --device cuda:0 --seed 42

# 回測（自動偵測 PPO/SAC）
python training/backtest_sb3.py \
  --data trade.csv --model trained_models/<id>/model_sb3.zip
```

---

*最後更新: 2026-04-04*