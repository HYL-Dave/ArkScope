# DeepSeek vs Claude 情緒評分模型比較

> **分析日期**: 2026-01-04
> **數據來源**: `finrl_claude_all_scores.csv`
> **樣本數**: 77,122 篇同時有雙方評分的文章
>
> ⚠️ **重要說明**: 此比較為 **DeepSeek vs Claude**。
> - `sentiment_deepseek` 欄位是**原始 DeepSeek 模型**評分 (來自 HuggingFace 資料集)
> - 非 OpenAI 系列模型 (o3, gpt-5 等)
> - OpenAI 模型評分請參考 `/mnt/md0/finrl/{model}/sentiment/` 目錄

---

## 1. 執行摘要

| 指標 | 結論 |
|------|------|
| **整體一致性** | 95% 差異在 ±1 以內 |
| **數據品質** | Claude 更佳 (DeepSeek 有 228 筆無效分數 0) |
| **分布特性** | DeepSeek 偏保守 (47% 給 3)，Claude 更分散 |
| **語意理解** | Claude 對負面語意判斷更準確 |
| **建議** | 可混合使用，但 Claude 在複雜語意場景更可靠 |

---

## 2. 分布比較

### 2.1 情緒分數分布 (%)

| Score | DeepSeek | Claude Haiku | Claude Sonnet | Claude Opus |
|-------|----------|--------------|---------------|-------------|
| 1 (Very Bearish) | 1.0% | 1.3% | 0.8% | 0.5% |
| 2 (Bearish) | 14.1% | 16.3% | 15.0% | 10.8% |
| 3 (Neutral) | **47.4%** | 37.6% | 39.4% | **50.0%** |
| 4 (Bullish) | 35.0% | 35.9% | **42.3%** | 37.0% |
| 5 (Very Bullish) | 2.5% | **8.8%** | 2.5% | 1.7% |

**關鍵觀察**:
- DeepSeek 明顯集中在 3 (中性)，可能過於保守
- Haiku 較願意給出極端分數 5 (8.8%)
- Opus 分布最接近 DeepSeek
- Sonnet 傾向給 4 分 (bullish)

### 2.2 統計量比較

| Model | Mean | Median | Std | Mode |
|-------|------|--------|-----|------|
| DeepSeek | 3.24 | 3.0 | 0.76 | 3 |
| Claude Haiku | 3.34 | 3.0 | 0.90 | 3 |
| Claude Sonnet | 3.31 | 3.0 | 0.78 | **4** |
| Claude Opus | 3.29 | 3.0 | 0.69 | 3 |

---

## 3. 一致性分析

### 3.1 DeepSeek vs Claude

| 比較 | 完全一致 | 差異 ≤1 | 相關係數 |
|------|----------|---------|----------|
| DeepSeek vs Haiku | 50.9% | 93.2% | 0.496 |
| DeepSeek vs Sonnet | 54.3% | 95.1% | 0.484 |
| DeepSeek vs Opus | 56.7% | **95.9%** | 0.471 |

**結論**: Opus 與 DeepSeek 最相似，約 56.7% 完全一致。

### 3.2 Claude 內部一致性

| 比較 | 完全一致 |
|------|----------|
| Haiku vs Sonnet | 78.2% |
| Haiku vs Opus | 74.1% |
| Sonnet vs Opus | **81.3%** |

**結論**: Claude 模型之間一致性高，Sonnet 和 Opus 最相似。

---

## 4. 差異案例分析

### 4.1 DeepSeek 過度樂觀 (1,461 篇, 1.89%)

| 案例 | 標題 | DeepSeek | Claude (H/S/O) | 分析 |
|------|------|----------|----------------|------|
| ZM | "Zoom Stock Looks **Overvalued**" | 5 | 2/2/2 | ❌ DeepSeek 忽略 "overvalued" 負面語意 |
| NVDA | "3 AI Stocks Trading at Massive **Discount**" | 5 | 2/2/3 | ❌ 問句標題，DeepSeek 過度解讀 |
| AMD | "Is AMD Stock a **Buy**?" | 5 | 2/2/2 | 🤔 問句形式，需看內文 |

### 4.2 DeepSeek 過度悲觀或無效 (2,014 篇, 2.61%)

| 案例 | 標題 | DeepSeek | Claude (H/S/O) | 分析 |
|------|------|----------|----------------|------|
| AMAT | "Guru Fundamental Report - Warren Buffett" | **0** | 4/4/4 | ❌ DeepSeek 給出無效分數 |
| PDD | "5 Non-U.S. Stocks to **Buy**" | 1 | 5/5/4 | ❌ DeepSeek 對推薦文判斷錯誤 |
| CHTR | "S&P, Nasdaq **extend rally**" | 1 | 5/5/5 | ❌ DeepSeek 誤判正面市場新聞 |

### 4.3 數據品質問題

```
⚠️ DeepSeek 有 228 篇給出無效分數 0 (應為 1-5)
⚠️ Claude 無此問題
```

---

## 5. 模型特性總結

### 5.1 DeepSeek

| 優點 | 缺點 |
|------|------|
| 分布保守，減少極端判斷 | 過度集中於中性 (47%) |
| 與傳統情緒分析結果接近 | 對複雜語意理解較弱 |
| | 有無效分數問題 (228 篇) |

### 5.2 Claude 系列

| 優點 | 缺點 |
|------|------|
| 語意理解更準確 | Haiku 可能過度激進 (8.8% 給 5) |
| 無無效分數 | 成本較高 (相對 gpt-5) |
| 三模型可交叉驗證 | |
| Opus 最穩定，Sonnet 性價比最高 | |

---

## 6. 實際應用建議

### 6.1 模型選擇

| 場景 | 推薦模型 | 原因 |
|------|----------|------|
| 成本敏感 | OpenAI gpt-5 | 最便宜 |
| 追求準確 | Claude Sonnet | 性價比最佳 |
| 極端事件檢測 | Claude Haiku | 更願意給極端分數 |
| 交叉驗證 | 多模型投票 | 提高可靠性 |

### 6.2 混合策略

```python
def ensemble_sentiment(openai, haiku, sonnet, opus):
    """多模型融合策略"""
    # 方案 1: Claude 投票
    claude_vote = round((haiku + sonnet + opus) / 3)

    # 方案 2: 加權平均 (Sonnet 權重較高)
    weighted = openai * 0.2 + haiku * 0.2 + sonnet * 0.35 + opus * 0.25

    # 方案 3: 極端值觸發
    if abs(openai - claude_vote) >= 2:
        return claude_vote  # 差異大時信任 Claude
    return round((openai + claude_vote) / 2)
```

### 6.3 品質控制

```python
# 標記需人工審核的文章
def flag_for_review(openai, haiku, sonnet, opus):
    claude_std = np.std([haiku, sonnet, opus])
    diff = abs(openai - np.mean([haiku, sonnet, opus]))

    return (
        openai == 0 or                     # OpenAI 無效分數
        diff >= 2 or                       # OpenAI vs Claude 差異大
        claude_std >= 1                    # Claude 內部不一致
    )
```

---

## 7. 價格回測初步分析

### 7.1 情緒與次日收益相關性 (2023 年數據)

| 模型 | 與次日收益相關係數 |
|------|-------------------|
| OpenAI gpt-5 | **+0.0219** |
| Claude Opus | +0.0127 |
| Claude Sonnet | +0.0077 |
| Claude Haiku | +0.0054 |

**分析**:
- 所有模型相關性都很弱 (< 0.03)，這在單日情緒-收益關係中是正常的
- OpenAI 相關性最高，可能因為其保守評分減少了噪音
- Claude 模型較低相關性可能源於更分散的分數分布

**數據說明**:
- 樣本: 6,633 個日-股票組合 (2023 年)
- 價格數據: 小時級 → 日收盤價
- 情緒: 當日所有新聞平均

### 7.2 限制說明

⚠️ 此為初步分析，完整回測需要:
1. 更長期的日線價格數據 (目前只有 2023 年小時數據)
2. 更複雜的策略 (如持有期、止損等)
3. 考慮交易成本和滑點

---

## 8. 後續建議

1. ~~**回測驗證**~~: ✅ 已完成初步分析
2. **深度回測**: 獲取 2009-2024 完整日線數據進行策略回測
3. **成本效益分析**: 計算每單位準確度提升的成本
4. **特定領域微調**: 針對金融新聞領域 fine-tune

---

## 附錄: 數據來源

- **文件**: `/mnt/md0/finrl/claude/finrl_claude_all_scores.csv`
- **總行數**: 127,176
- **有效比較樣本**: 77,122 (同時有 OpenAI 和 Claude 評分)
- **日期範圍**: 2009-07-07 ~ 2024-01-09
- **股票數**: 75

---

*分析者: Claude Code*
*版本: 1.0*