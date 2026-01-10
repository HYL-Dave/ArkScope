# LLM 評分驗證方法論

本文件說明驗證 LLM 情緒/風險評分預測能力所使用的量化金融方法。

## 驗證工具

| 腳本 | 用途 |
|------|------|
| `scripts/analysis/validate_scoring_value.py` | 評分預測力驗證 (IC, Hit Rate, Correlation) |
| `scripts/analysis/sentiment_backtest.py` | 策略回測 (Sharpe, Sortino, Max Drawdown) |

---

## 一、評分預測力驗證 (`validate_scoring_value.py`)

### 1.1 相關性分析 (Spearman Correlation)

**問題**: 評分高的新聞，股價真的會漲嗎？

**方法**:
- 計算 `sentiment_score` 和 `forward_return` 的 Spearman 相關係數
- Spearman 適合非線性關係，比 Pearson 更穩健
- 測試 1 天、2 天、5 天、10 天的未來報酬

**判讀標準**:
| 相關係數 r | p 值 | 解讀 |
|------------|------|------|
| r > 0.05 | p < 0.05 | ✅ 有統計顯著的正向關係 |
| 0.02 < r < 0.05 | p < 0.05 | ⚠️ 弱正向關係 |
| \|r\| < 0.02 | - | ❌ 無預測能力 |

### 1.2 命中率分析 (Hit Rate)

**問題**: 評分 4-5 分的新聞，真的能預測股價上漲嗎？

**方法**:
- `bullish_hit_rate`: 評分 4-5 的新聞，隔天股價真的**漲**的比例
- `bearish_hit_rate`: 評分 1-2 的新聞，隔天股價真的**跌**的比例

**判讀標準**:
| Hit Rate | 解讀 |
|----------|------|
| > 55% | ✅ 有參考價值 |
| 52-55% | ⚠️ 略有預測能力 |
| 50% | ❌ 和丟硬幣一樣，無預測能力 |
| < 50% | ❌ 反向指標 |

### 1.3 Information Coefficient (IC) - 業界標準

**問題**: 評分能可靠地區分「漲幅大」和「漲幅小」的股票嗎？

**方法**:
1. 每天計算: 評分排名 vs 報酬排名 的 Spearman 相關
2. 統計所有天的 IC 平均值和標準差
3. IC IR = mean(IC) / std(IC) → 信號穩定性指標

**計算公式**:
```
IC_t = Spearman(score_rank_t, return_rank_t)
Mean IC = average(IC_1, IC_2, ..., IC_T)
IC IR = Mean IC / Std(IC)
```

**判讀標準 (業界標準)**:
| IC 絕對值 | 解讀 |
|-----------|------|
| \|IC\| > 0.05 | ✅ 優秀因子 |
| \|IC\| > 0.02 | ⚠️ 可用因子 |
| \|IC\| < 0.01 | ❌ 無效因子 |

| IC IR | 解讀 |
|-------|------|
| > 0.5 | ✅ 信號穩定 |
| 0.3-0.5 | ⚠️ 信號一般 |
| < 0.3 | ❌ 信號不穩定 |

### 1.4 五分位分析 (Quintile Analysis)

**問題**: 分數 1-5 的股票，報酬率有明顯差異嗎？

**方法**:
- 把所有新聞按評分 1-5 分組
- 計算每組的平均報酬、標準差、Sharpe Ratio

**理想結果** (單調遞增):
```
分數 1: -0.3% 平均報酬  ↓ 最差
分數 2: -0.1%
分數 3:  0.0%           → 中性
分數 4: +0.1%
分數 5: +0.3%           ↑ 最好
```

**判讀**:
- 分數越高，報酬越高 → 評分有預測能力
- 非單調關係 → 評分系統可能有問題

---

## 二、策略回測 (`sentiment_backtest.py`)

### 2.1 Long-Only Top 策略

**規則**:
- 每天買入 sentiment >= 5 的所有股票
- 等權重配置
- 隔天賣出

**適用場景**: 保守做法，只做多強烈正面信號

### 2.2 Long-Short 策略

**規則**:
- Long: sentiment >= 5 (50% 資金)
- Short: sentiment <= 1 (50% 資金)
- 每日換倉

**目的**: 消除市場 beta，純粹測試**選股能力**

**優點**: 市場中性，無論大盤漲跌都能獲利（如果評分有效）

### 2.3 Score-Weighted 策略

**規則**:
```
分數 1 → 權重 -1 (做空)
分數 2 → 權重 -0.5
分數 3 → 權重 0 (不動)
分數 4 → 權重 +0.5
分數 5 → 權重 +1 (做多)
```

**特點**: 連續信號利用，部位大小依據確信度縮放

---

## 三、績效指標

### 3.1 風險調整報酬指標

| 指標 | 公式 | 意義 | 好的標準 |
|------|------|------|---------|
| **Sharpe Ratio** | (R - Rf) / σ | 每單位風險的超額報酬 | > 1.0 良好, > 2.0 優秀 |
| **Sortino Ratio** | (R - Rf) / σ_downside | 只考慮下行風險的 Sharpe | > Sharpe = 下跌控制好 |
| **Information Ratio** | α / σ_tracking | 超額報酬 / 追蹤誤差 | > 0.5 有 alpha |

### 3.2 風險指標

| 指標 | 意義 | 好的標準 |
|------|------|---------|
| **Max Drawdown** | 最大虧損幅度 (峰值到谷底) | < -20% 可接受 |
| **Volatility** | 年化波動率 | 視策略而定 |
| **Calmar Ratio** | 年化報酬 / 最大回撤 | > 1.0 良好 |

### 3.3 交易統計

| 指標 | 意義 | 好的標準 |
|------|------|---------|
| **Win Rate** | 獲利天數比例 | > 50% 且穩定 |
| **Profit Factor** | 總獲利 / 總虧損 | > 1.5 良好 |

---

## 四、驗證流程建議

### 步驟 1: 預測力驗證 (validate_scoring_value.py)

```bash
python scripts/analysis/validate_scoring_value.py --file <scoring.csv> --score-col sentiment_gpt_5
```

**檢查項**:
- [ ] IC 絕對值 > 0.02
- [ ] Hit Rate > 52%
- [ ] 五分位報酬呈單調遞增

### 步驟 2: 策略回測 (sentiment_backtest.py)

```bash
python scripts/analysis/sentiment_backtest.py --file <scoring.csv> --score-col sentiment_gpt_5
```

**檢查項**:
- [ ] Sharpe Ratio > 0.5
- [ ] Long-Short 策略正報酬
- [ ] Max Drawdown 可接受

### 步驟 3: 穩健性檢驗

- [ ] 不同時間段的 IC 是否穩定
- [ ] 移除極端值後結果是否一致
- [ ] 不同股票池的表現

---

## 五、參考文獻

1. Grinold, R. C., & Kahn, R. N. (2000). *Active Portfolio Management*. McGraw-Hill.
2. Clarke, R., de Silva, H., & Thorley, S. (2002). Portfolio Constraints and the Fundamental Law of Active Management. *Financial Analysts Journal*.
3. Qian, E., & Hua, R. (2004). Active Risk and Information Ratio. *Journal of Investment Management*.

---

## 六、相關檔案

| 檔案 | 說明 |
|------|------|
| `scripts/analysis/validate_scoring_value.py` | 評分驗證腳本 |
| `scripts/analysis/sentiment_backtest.py` | 回測腳本 |
| `scripts/analysis/analyze_finrl_scores.py` | 跨模型評分分析 |
| `scripts/analysis/detailed_factor_comparison.py` | 因子比較分析 |
| `docs/analysis/SCORING_VALUE_VALIDATION_REPORT.md` | 驗證結果報告 |

---

*最後更新: 2026-01-10*