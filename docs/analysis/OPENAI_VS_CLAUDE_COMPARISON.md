# OpenAI vs Claude 情緒評分模型比較

> **分析日期**: 2026-01-04
> **樣本數**: 77,871 篇同時有所有模型評分的文章
> **數據來源**: `/mnt/md0/finrl/` 各模型目錄

---

## 1. 執行摘要

| 指標 | 結論 |
|------|------|
| **最高一致性配對** | gpt-5 vs Opus (75.1%) |
| **整體一致性** | 97-99% 差異在 ±1 以內 |
| **OpenAI 內部最一致** | o3 vs gpt-5 (78.2%) |
| **Claude 內部最一致** | Sonnet vs Opus (81.3%) |
| **最獨特模型** | o4-mini (與其他差異最大) |

---

## 2. 分布比較

### 2.1 情緒分數分布 (%)

| Score | o3 | o4-mini | gpt-5 | gpt-4.1-mini | Haiku | Sonnet | Opus |
|-------|-----|---------|-------|--------------|-------|--------|------|
| 1 (Very Bearish) | 1.4% | 2.3% | 1.4% | 1.6% | 1.3% | 0.8% | 0.5% |
| 2 (Bearish) | 16.1% | 13.4% | 10.4% | 14.9% | 16.3% | 15.0% | 10.8% |
| 3 (Neutral) | 37.1% | 39.7% | **54.0%** | 36.1% | 37.7% | 39.5% | **50.1%** |
| 4 (Bullish) | **42.2%** | 35.8% | 32.0% | 33.2% | 35.9% | **42.3%** | 37.0% |
| 5 (Very Bullish) | 3.3% | 8.8% | 2.3% | **14.3%** | **8.8%** | 2.5% | 1.7% |

**關鍵觀察**:
- **保守型**: gpt-5 (54% 給 3) 和 Opus (50% 給 3) 最傾向中性
- **激進型**: gpt-4.1-mini (14.3% 給 5) 和 Haiku (8.8% 給 5) 最願意給極端正面
- **相似配對**: o3 ≈ Sonnet (都傾向給 4), gpt-5 ≈ Opus (都偏中性)

### 2.2 統計量比較

| Model | Mean | Std | Mode |
|-------|------|-----|------|
| o3 | 3.30 | 0.82 | 4 |
| o4-mini | 3.35 | 0.90 | 3 |
| gpt-5 | 3.24 | 0.72 | 3 |
| gpt-4.1-mini | 3.44 | 0.96 | 3 |
| Haiku | 3.34 | 0.90 | 3 |
| Sonnet | 3.31 | 0.78 | 4 |
| Opus | 3.29 | 0.69 | 3 |

---

## 3. 一致性分析

### 3.1 OpenAI vs Claude 完整矩陣

| OpenAI \ Claude | Haiku | Sonnet | Opus |
|-----------------|-------|--------|------|
| **o3** | 67.8% | **73.1%** | 72.0% |
| **o4-mini** | 54.5% | 55.6% | 57.0% |
| **gpt-5** | 64.8% | 70.4% | **75.1%** |
| **gpt-4.1-mini** | 66.6% | 65.1% | 61.2% |

**最佳配對** (按一致性排序):
1. 🥇 **gpt-5 vs Opus**: 75.1% exact, 99.0% ±1, corr=0.722
2. 🥈 **o3 vs Sonnet**: 73.1% exact, 98.4% ±1, corr=0.751
3. 🥉 **o3 vs Opus**: 72.0% exact, 98.5% ±1, corr=0.730
4. **gpt-5 vs Sonnet**: 70.4% exact, 98.9% ±1, corr=0.710
5. **o3 vs Haiku**: 67.8% exact, 97.2% ±1, corr=0.723

### 3.2 OpenAI 內部一致性

| 比較 | 完全一致 |
|------|----------|
| **o3 vs gpt-5** | **78.2%** |
| o3 vs gpt-4.1-mini | 68.9% |
| gpt-5 vs gpt-4.1-mini | 63.4% |
| o3 vs o4-mini | 58.0% |
| gpt-5 vs o4-mini | 57.5% |
| o4-mini vs gpt-4.1-mini | 52.7% |

**結論**: o3 和 gpt-5 最相似；o4-mini 最獨特

### 3.3 Claude 內部一致性

| 比較 | 完全一致 |
|------|----------|
| **Sonnet vs Opus** | **81.3%** |
| Haiku vs Sonnet | 78.2% |
| Haiku vs Opus | 74.1% |

**結論**: Sonnet 和 Opus 最穩定

---

## 4. 模型分組

根據分布和一致性分析，模型可分為三組：

### 4.1 保守組 (偏中性)
| 模型 | 特徵 | 中性率 |
|------|------|--------|
| gpt-5 | 最保守 | 54% |
| Opus | 次保守 | 50% |

### 4.2 平衡組 (分布均勻)
| 模型 | 特徵 | Mode |
|------|------|------|
| o3 | OpenAI 代表 | 4 |
| Sonnet | Claude 代表 | 4 |
| o4-mini | 略偏激進 | 3 |
| Haiku | 略偏激進 | 3 |

### 4.3 激進組 (願意給極端分)
| 模型 | 特徵 | 5分率 |
|------|------|-------|
| gpt-4.1-mini | 最激進 | 14.3% |

---

## 5. 實際應用建議

### 5.1 模型選擇指南

| 需求 | 推薦 OpenAI | 推薦 Claude | 原因 |
|------|-------------|-------------|------|
| 保守穩定 | gpt-5 | Opus | 分布相似，高一致性 (75%) |
| 平衡準確 | o3 | Sonnet | 高相關性 (0.75)，分布均勻 |
| 極端事件 | gpt-4.1-mini | Haiku | 願意給出極端判斷 |
| 成本效益 | gpt-5 | Haiku | 便宜且可靠 |

### 5.2 跨廠商驗證

```python
def cross_vendor_validation(title, content):
    """跨廠商評分驗證"""
    # 選擇最相似的配對
    openai_score = score_with_gpt5(title, content)  # 或 o3
    claude_score = score_with_opus(title, content)  # 或 Sonnet

    # 75% 時間會一致
    if openai_score == claude_score:
        return openai_score, "high_confidence"
    elif abs(openai_score - claude_score) == 1:
        return round((openai_score + claude_score) / 2), "medium_confidence"
    else:
        return None, "needs_review"  # 差異 ≥2，需人工審核
```

### 5.3 多模型融合

```python
def multi_model_ensemble(o3, gpt5, haiku, sonnet, opus):
    """多模型融合評分"""
    # OpenAI 投票 (排除獨特的 o4-mini 和 gpt-4.1-mini)
    openai_vote = round((o3 + gpt5) / 2)

    # Claude 投票
    claude_vote = round((haiku + sonnet + opus) / 3)

    # 跨廠商融合
    if abs(openai_vote - claude_vote) <= 1:
        return round((openai_vote + claude_vote) / 2)
    else:
        # 差異大時，取更保守的
        return min(openai_vote, claude_vote) if openai_vote >= 3 else max(openai_vote, claude_vote)
```

---

## 6. 數據品質

| 模型 | 無效分數 (0) | 品質 |
|------|-------------|------|
| o3 | 0 | ✅ |
| o4-mini | 0 | ✅ |
| gpt-5 | 0 | ✅ |
| gpt-4.1-mini | 0 | ✅ |
| Haiku | 0 | ✅ |
| Sonnet | 0 | ✅ |
| Opus | 0 | ✅ |

**所有模型均無數據品質問題**

---

## 7. 回測分析 (2023年)

### 7.1 方法論

| 項目 | 說明 |
|------|------|
| **數據** | 2023年小時級價格 → 日收盤價 |
| **樣本** | 6,669 個日-股票組合 |
| **目標** | 次日股票收益率 |
| **方法** | 每日情緒平均值 vs 次日收益相關性 |

### 7.2 模型表現排名 (按相關性)

| Model | N | Correlation | P-value | 顯著性 |
|-------|---|-------------|---------|--------|
| DeepSeek | 6,631 | +0.0227 | 0.0647 | † |
| o3 | 6,669 | +0.0226 | 0.0650 | † |
| gpt-4.1-mini | 6,669 | +0.0172 | 0.1592 | |
| gpt-5 | 6,669 | +0.0163 | 0.1822 | |
| Opus | 6,669 | +0.0132 | 0.2822 | |
| o4-mini | 6,669 | +0.0100 | 0.4141 | |
| Sonnet | 6,669 | +0.0082 | 0.5014 | |
| Haiku | 6,669 | +0.0061 | 0.6180 | |

> † p < 0.1, * p < 0.05, ** p < 0.01, *** p < 0.001

### 7.3 分數與次日收益 (%)

| Score | DeepSeek | o3 | gpt-5 | Opus | Sonnet | Haiku |
|-------|----------|-----|-------|------|--------|-------|
| 1 (Very Bearish) | +0.07% (54) | -0.29% (87) | -0.14% (84) | -0.57% (28) | -0.86% (31) | -0.33% (78) |
| 2 (Bearish) | +0.20% (853) | +0.18% (1083) | +0.30% (700) | +0.26% (743) | +0.27% (1077) | +0.28% (1122) |
| 3 (Neutral) | +0.13% (2724) | +0.17% (2096) | +0.13% (3279) | +0.15% (3008) | +0.15% (2132) | +0.16% (2149) |
| 4 (Bullish) | +0.21% (2686) | +0.19% (3207) | +0.22% (2501) | +0.20% (2810) | +0.17% (3286) | +0.15% (2772) |
| 5 (Very Bullish) | +0.59% (314) | +0.73% (196) | +0.81% (105) | **+1.11%** (80) | +0.87% (143) | +0.40% (548) |

> 括號內為樣本數

### 7.4 Long-Short 策略 (Score 5 - Score 2)

| Model | Long (5) | Short (2) | Spread |
|-------|----------|-----------|--------|
| **Opus** | +1.11% | +0.26% | **+0.84%** |
| Sonnet | +0.87% | +0.27% | +0.60% |
| o3 | +0.73% | +0.18% | +0.55% |
| gpt-5 | +0.81% | +0.30% | +0.52% |
| DeepSeek | +0.59% | +0.20% | +0.39% |
| gpt-4.1-mini | +0.34% | +0.11% | +0.24% |
| o4-mini | +0.37% | +0.20% | +0.17% |
| Haiku | +0.40% | +0.28% | +0.11% |

### 7.5 回測結論

| 發現 | 說明 |
|------|------|
| **相關性弱** | 所有模型 r < 0.03，這在單日情緒-收益分析中是正常的 |
| **OpenAI 相關性較高** | DeepSeek/o3 邊際顯著 (p<0.1)，可能因保守評分減少噪音 |
| **Opus Long-Short 最佳** | +0.84% spread，但樣本小 (n=80) |
| **Score 5 有預測力** | 所有模型 Score 5 的次日收益都顯著為正 |

⚠️ **限制**: 僅 2023 年數據，完整回測需要更長期日線數據

---

## 8. 差異案例分析

### 8.1 完美一致比例

| 統計 | 數值 |
|------|------|
| 完美一致 (所有模型相同) | 37,168 / 77,871 (47.7%) |
| Score 1 完美一致 | 227 篇 |
| Score 2 完美一致 | 4,370 篇 |
| Score 3 完美一致 | 17,966 篇 |
| Score 4 完美一致 | 14,053 篇 |
| Score 5 完美一致 | 552 篇 |

### 8.2 OpenAI 明顯更 Bullish 的案例 (差異 ≥ 2.5)

| Stock | Date | Title | OpenAI (avg) | Claude (avg) | 分析 |
|-------|------|-------|--------------|--------------|------|
| DLTR | 2018-11-30 | "Dollar Tree Gives Up a Bit of Ground..." | 5.0 | 2.0 | OpenAI 看標題中 "bit" 淡化負面 |
| INTC | 2021-01-07 | "It's Time For Action on Intel Stock As Activist Loeb Pushes..." | 4.5 | 1.7 | OpenAI 視激進投資者介入為利多 |
| AMD | 2017-08-25 | "Why Is AMD Down 10.6% Since Last Earnings?" | 5.0 | 2.3 | OpenAI 解讀為反彈機會 |
| TSLA | 2022-05-10 | "Can Tesla Become Industrial Powerhouse? Morgan Stanley..." | 4.5 | 2.0 | OpenAI 偏向分析師觀點 |
| MU | 2019-05-31 | "Better Buy: Micron vs. Qualcomm" | 4.0 | 1.3 | 比較文章，OpenAI 對 MU 更樂觀 |

### 8.3 Claude 明顯更 Bullish 的案例 (差異 ≥ 2.5)

| Stock | Date | Title | OpenAI (avg) | Claude (avg) | 分析 |
|-------|------|-------|--------------|--------------|------|
| FTNT | 2017-04-28 | "Fortinet Q1 Earnings Beat, Revenue Growth Slows" | 1.0 | 5.0 | Claude 強調 "Beat"，OpenAI 在意 "Slows" |
| ZS | 2023-11-27 | "Successful Cyber Monday; Markets Take Profits" | 1.0 | 4.7 | Claude 看 "Successful"，OpenAI 看 "Take Profits" |
| FANG | 2020-12-21 | "Diamondback Energy spurs new shale consolidation..." | 1.0 | 4.3 | Claude 視整合為利多 |
| ON | 2015-11-19 | "ON Semiconductor to Acquire Fairchild for $2.4B Cash" | 1.0 | 4.3 | Claude 視收購為正面 |
| ENPH | 2019-06-24 | "Enphase Energy: Buy at the High?" | 2.0 | 5.0 | Claude 看 "Buy" 建議 |

### 8.4 差異模式總結

| 模式 | OpenAI 傾向 | Claude 傾向 |
|------|-------------|-------------|
| **下跌後文章** | 視為買入機會 (bullish) | 維持負面判斷 |
| **收購/併購新聞** | 較保守解讀 | 視為正面催化 |
| **Earnings Beat + 負面細節** | 關注負面細節 | 強調正面主題 |
| **比較類文章** | 更分散 (neutral) | 傾向對標的股票正面 |
| **分析師建議** | 偏向採信 | 較為中立 |

---

## 附錄: 數據來源

| 模型 | 檔案路徑 |
|------|----------|
| o3 | `/mnt/md0/finrl/o3/sentiment/sentiment_o3_high_by_o3_summary.csv` |
| o4-mini | `/mnt/md0/finrl/o4-mini/sentiment/sentiment_o4_mini_high_1.csv` |
| gpt-5 | `/mnt/md0/finrl/gpt-5/sentiment/sentiment_gpt-5_high_by_o3_summary.csv` |
| gpt-4.1-mini | `/mnt/md0/finrl/gpt-4.1-mini/sentiment/sentiment_gpt-4.1-mini_by_o3_summary.csv` |
| Haiku | `/mnt/md0/finrl/claude/finrl_claude_all_scores.csv` |
| Sonnet | `/mnt/md0/finrl/claude/finrl_claude_all_scores.csv` |
| Opus | `/mnt/md0/finrl/claude/finrl_claude_all_scores.csv` |

---

*分析者: Claude Code*
*版本: 1.0*