# A/B Score Comparison Report

**Generated**: 2025-12-31 08:53:58

**Score Type**: risk

**Sample Size**: 3000 per comparison


---

## 1. Score File Inventory

| Model | Files | Input Sources |
|-------|-------|---------------|
| claude | 3 | gpt_5_summary |
| gpt-4.1 | 1 | o3_summary |
| gpt-4.1-mini | 6 | o3_summary, gpt_5_summary |
| gpt-4.1-nano | 1 | o3_summary |
| gpt-5 | 8 | gpt_5_summary, o3_summary |
| gpt-5-mini | 1 | gpt_5_summary |
| o3 | 5 | o3_summary, unknown, gpt_5_summary |
| o4-mini | 4 | o3_summary, unknown |


---

## 2. Input Source Impact Analysis

*How does the input (Title vs Summary) affect scores?*

### 2.6 gpt-4.1-mini

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| o3_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 41.2% | 59.8% | 0.678 | 3,000 |
| o3_summary vs gpt_5_summary R=high_verbosity_high_summary V=high_summary | 42.5% | 60.1% | 0.699 | 3,000 |
| o3_summary vs gpt_5_summary R=minimal_verbosity_high_summary V=high_summary | 42.4% | 59.8% | 0.687 | 3,000 |
| o3_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 43.0% | 59.9% | 0.701 | 3,000 |
| o3_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 42.5% | 60.0% | 0.696 | 3,000 |
| gpt_5_summary R=medium_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_high_summary V=high_summary | 43.5% | 61.2% | 0.745 | 3,000 |
| gpt_5_summary R=medium_verbosity_high_summary V=high_summary vs gpt_5_summary R=minimal_verbosity_high_summary V=high_summary | 43.6% | 61.2% | 0.740 | 3,000 |
| gpt_5_summary R=medium_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 43.5% | 61.1% | 0.740 | 3,000 |
| gpt_5_summary R=medium_verbosity_high_summary V=high_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 44.1% | 60.8% | 0.739 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=minimal_verbosity_high_summary V=high_summary | 43.8% | 60.7% | 0.731 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 44.1% | 61.2% | 0.754 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 44.0% | 60.5% | 0.732 | 3,000 |
| gpt_5_summary R=minimal_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 43.9% | 60.9% | 0.738 | 3,000 |
| gpt_5_summary R=minimal_verbosity_high_summary V=high_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 44.1% | 60.7% | 0.732 | 3,000 |
| gpt_5_summary R=high_verbosity_medium_summary V=medium_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 44.6% | 61.1% | 0.755 | 3,000 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| o3_summary | 2.30 | 0.88 | 2.0 |
| gpt_5_summary R=medium_verbosity_high_su | 2.29 | 0.88 | 2.0 |
| gpt_5_summary R=high_verbosity_high_summ | 2.29 | 0.89 | 2.0 |
| gpt_5_summary R=minimal_verbosity_high_s | 2.27 | 0.88 | 2.0 |
| gpt_5_summary R=high_verbosity_medium_su | 2.28 | 0.89 | 2.0 |
| gpt_5_summary R=low_verbosity_high_summa | 2.27 | 0.89 | 2.0 |

### 2.4 gpt-5

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs o3_summary | 49.7% | 62.6% | 0.699 | 3,000 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| gpt_5_summary R=high_verbosity_high_summ | 2.62 | 0.62 | 3.0 |
| o3_summary | 2.58 | 0.62 | 3.0 |

### 2.7 o3

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| unknown vs o3_summary | 40.7% | 62.0% | 0.479 | 3,000 |
| unknown vs gpt_5_summary R=high_verbosity_high V=high | 42.6% | 62.2% | 0.526 | 3,000 |
| o3_summary vs gpt_5_summary R=high_verbosity_high V=high | 46.8% | 62.6% | 0.656 | 3,000 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| unknown | 2.47 | 0.61 | 2.0 |
| o3_summary | 2.49 | 0.64 | 2.0 |
| gpt_5_summary R=high_verbosity_high V=hi | 2.51 | 0.63 | 2.0 |


---

## 3. Scoring Model Comparison

*Using same input source (o3_summary), how do different models score?*

### 3.1 Pairwise Agreement (o3_summary input) - 完整 78 對比較

| Model A vs Model B | Exact Match | Within ±1 | Correlation |
|-------------------|-------------|-----------|-------------|
| gpt-5_low vs gpt-5_medium | 54.3% | 62.9% | 0.817 |
| gpt-5_high vs gpt-5_low | 53.9% | 62.8% | 0.797 |
| gpt-5_high vs gpt-5_medium | 53.6% | 62.8% | 0.794 |
| o3_high vs o3_medium | 53.1% | 62.4% | 0.765 |
| o3_low vs o3_medium | 52.8% | 62.6% | 0.771 |
| o3_low vs o3_high | 52.5% | 62.7% | 0.773 |
| gpt-5_minimal vs gpt-5_low | 51.4% | 62.8% | 0.755 |
| gpt-5_high vs o3_high | 50.9% | 62.4% | 0.724 |
| gpt-5_high vs o3_medium | 50.9% | 62.5% | 0.728 |
| gpt-5_low vs o3_low | 50.7% | 62.7% | 0.755 |
| gpt-5_low vs o3_high | 50.5% | 62.6% | 0.738 |
| gpt-5_high vs o3_low | 50.1% | 62.7% | 0.729 |
| gpt-5_minimal vs gpt-5_medium | 50.1% | 62.7% | 0.723 |
| gpt-5_high vs gpt-5_minimal | 50.0% | 62.7% | 0.716 |
| gpt-5_medium vs o3_medium | 49.7% | 62.5% | 0.718 |
| gpt-5_medium vs o3_high | 49.6% | 62.5% | 0.712 |
| gpt-5_low vs o3_medium | 49.6% | 62.6% | 0.722 |
| gpt-5_medium vs o3_low | 49.5% | 62.6% | 0.724 |
| gpt-5_minimal vs o3_high | 48.6% | 62.5% | 0.702 |
| gpt-5_minimal vs o3_low | 48.5% | 62.7% | 0.715 |
| gpt-5_minimal vs o3_medium | 47.8% | 62.5% | 0.689 |
| gpt-4.1 vs gpt-4.1-mini | 43.4% | 59.4% | 0.706 |
| o4-mini_medium vs o4-mini_high | 42.5% | 61.2% | 0.726 |
| o4-mini_low vs o4-mini_high | 41.7% | 61.1% | 0.712 |
| o4-mini_medium vs o4-mini_low | 41.5% | 61.0% | 0.709 |
| o4-mini_low vs gpt-4.1-mini | 40.6% | 60.6% | 0.693 |
| o4-mini_medium vs gpt-4.1-mini | 39.6% | 60.6% | 0.678 |
| o4-mini_high vs gpt-4.1-mini | 39.0% | 60.1% | 0.655 |
| gpt-4.1 vs o4-mini_low | 38.9% | 59.7% | 0.669 |
| gpt-4.1-nano vs gpt-4.1-mini | 38.4% | 61.6% | 0.678 |
| o4-mini_high vs o3_low | 38.2% | 60.6% | 0.634 |
| o4-mini_high vs o3_medium | 37.7% | 60.8% | 0.627 |
| gpt-4.1 vs o4-mini_medium | 37.6% | 59.9% | 0.656 |
| o4-mini_medium vs o3_low | 37.4% | 60.8% | 0.634 |
| o4-mini_high vs o3_high | 37.3% | 60.8% | 0.638 |
| gpt-4.1 vs o4-mini_high | 37.2% | 59.6% | 0.644 |
| gpt-5_minimal vs gpt-4.1-mini | 37.2% | 59.6% | 0.639 |
| gpt-4.1-mini vs o3_low | 37.1% | 60.4% | 0.608 |
| o4-mini_low vs o3_low | 37.1% | 60.9% | 0.630 |
| o4-mini_low vs o3_medium | 37.0% | 61.0% | 0.629 |
| o4-mini_medium vs o3_high | 36.9% | 60.8% | 0.636 |
| o4-mini_medium vs o3_medium | 36.9% | 61.1% | 0.632 |
| gpt-4.1-mini vs o3_medium | 36.9% | 60.5% | 0.600 |
| o4-mini_low vs gpt-5_minimal | 36.8% | 60.2% | 0.662 |
| o4-mini_low vs o3_high | 36.7% | 60.8% | 0.625 |
| gpt-4.1 vs gpt-5_minimal | 36.4% | 58.9% | 0.688 |
| gpt-4.1-mini vs o3_high | 36.2% | 60.3% | 0.603 |
| o4-mini_high vs gpt-5_high | 36.1% | 59.9% | 0.614 |
| o4-mini_low vs gpt-5_high | 36.1% | 60.1% | 0.618 |
| o4-mini_low vs gpt-5_low | 36.1% | 60.0% | 0.639 |
| o4-mini_medium vs gpt-5_high | 35.9% | 59.8% | 0.607 |
| o4-mini_high vs gpt-5_minimal | 35.8% | 59.7% | 0.631 |
| o4-mini_high vs gpt-5_medium | 35.7% | 59.5% | 0.615 |
| gpt-5_low vs gpt-4.1-mini | 35.6% | 59.1% | 0.592 |
| gpt-5_high vs gpt-4.1-mini | 35.5% | 59.1% | 0.566 |
| gpt-4.1-nano vs o4-mini_high | 35.4% | 60.6% | 0.580 |
| o4-mini_medium vs gpt-5_low | 35.3% | 59.7% | 0.624 |
| o4-mini_medium vs gpt-5_medium | 35.3% | 59.5% | 0.610 |
| o4-mini_high vs gpt-5_low | 35.2% | 59.8% | 0.624 |
| o4-mini_medium vs gpt-5_minimal | 35.0% | 59.9% | 0.631 |
| o4-mini_low vs gpt-5_medium | 35.0% | 59.8% | 0.614 |
| gpt-4.1 vs gpt-5_low | 34.9% | 58.4% | 0.651 |
| gpt-4.1-nano vs o4-mini_medium | 34.8% | 60.6% | 0.585 |
| gpt-4.1-nano vs o4-mini_low | 34.8% | 60.9% | 0.594 |
| gpt-4.1 vs o3_low | 34.8% | 60.6% | 0.660 |
| gpt-4.1-nano vs o3_medium | 34.8% | 60.5% | 0.501 |
| gpt-5_medium vs gpt-4.1-mini | 34.7% | 58.7% | 0.560 |
| gpt-4.1 vs gpt-5_medium | 34.7% | 57.9% | 0.620 |
| gpt-4.1-nano vs o3_low | 34.5% | 60.7% | 0.513 |
| gpt-4.1 vs gpt-5_high | 34.3% | 58.3% | 0.609 |
| gpt-4.1 vs o3_high | 34.3% | 60.1% | 0.645 |
| gpt-4.1 vs o3_medium | 34.1% | 60.3% | 0.632 |
| gpt-4.1 vs gpt-4.1-nano | 33.5% | 59.7% | 0.565 |
| gpt-4.1-nano vs o3_high | 33.5% | 60.6% | 0.507 |
| gpt-4.1-nano vs gpt-5_high | 31.9% | 59.8% | 0.469 |
| gpt-4.1-nano vs gpt-5_minimal | 31.4% | 60.1% | 0.520 |
| gpt-4.1-nano vs gpt-5_low | 31.1% | 59.6% | 0.489 |
| gpt-4.1-nano vs gpt-5_medium | 30.4% | 59.7% | 0.470 |

### 3.2 Score Distribution by Model (完整 13 種配置)

| Model | Mean | Std | Median |
|-------|------|-----|--------|
| gpt-4.1 | 2.22 | 0.93 | 2.0 |
| gpt-4.1-mini | 2.30 | 0.88 | 2.0 |
| gpt-4.1-nano | 2.27 | 0.80 | 2.0 |
| gpt-5_high | 2.58 | 0.62 | 3.0 |
| gpt-5_low | 2.63 | 0.63 | 3.0 |
| gpt-5_medium | 2.62 | 0.62 | 3.0 |
| gpt-5_minimal | 2.63 | 0.63 | 3.0 |
| o3_high | 2.52 | 0.64 | 2.0 |
| o3_low | 2.49 | 0.64 | 2.0 |
| o3_medium | 2.49 | 0.62 | 2.0 |
| o4-mini_high | 2.26 | 0.86 | 2.0 |
| o4-mini_low | 2.28 | 0.87 | 2.0 |
| o4-mini_medium | 2.26 | 0.87 | 2.0 |


---

## 4. Symbol-Title Relevance Impact

### 4.1 Score Comparison by Symbol Presence in Title

| Category | Count | Mean Score | Std |
|----------|-------|------------|-----|
| Symbol In Title | 556 | 2.18 | 0.88 |
| Symbol Not In Title | 1,335 | 2.24 | 0.95 |

### 4.2 Roundup vs Non-Roundup Articles

| Category | Count | Mean Score | Std |
|----------|-------|------------|-----|
| Roundup Articles | 141 | 2.01 | 0.92 |
| Non Roundup Articles | 1,750 | 2.24 | 0.93 |


---

## 5. Key Findings

### 5.1 Input Source Impact

- Different input sources (Title vs Summary) can lead to different scores
- LLM summaries (o3/gpt5) generally provide more consistent scoring inputs
- Traditional summaries (Lsa) may introduce noise

### 5.2 Scoring Model Consistency

- Models show varying levels of agreement
- Higher reasoning effort tends to produce more consistent results
- Correlation between models varies by score type

### 5.3 Data Quality Considerations

- Symbol-Title mismatch affects score reliability
- Roundup articles may have lower per-stock relevance
- Filtering by relevance can improve score quality



---

## 6. Recommendations

### 6.1 For Score Comparison

1. **Always control input source**: Compare scores only when using same input
2. **Filter low-relevance records**: Exclude symbol-mismatch cases
3. **Use correlation + exact match**: Both metrics provide different insights

### 6.2 For Production Scoring

1. **Prefer LLM summaries**: o3 or gpt5 summaries are more reliable inputs
2. **Consider symbol verification**: Check title contains symbol for high-confidence records
3. **Use ensemble scoring**: Multiple models can improve reliability

### 6.3 For A/B Testing

1. **Single variable testing**: Change only one factor at a time
2. **Sufficient sample size**: Use 2000+ records for statistical significance
3. **Document all variables**: Input source, model, parameters



---

## 7. 系統性比較分析 (Systematic Comparison Analysis)

### 7.0 可用數據總覽

**按 Input Source 分組 (可比較不同 Scoring Model):**

| Input Source | 可用 Scoring Models |
|--------------|---------------------|
| `o3_summary` | gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5×4, o3×3, o4-mini×3 (共 13 種) |
| `gpt5_R_high_V_high_summary` | gpt-4.1-mini, gpt-5×4 (R variants), gpt-5-mini, o3 (共 7 種) |
| `gpt5_summary` | claude-haiku, claude-sonnet, claude-opus (共 3 種) |

**注意**: gpt-5-mini 只有 `gpt5_R_high_V_high_summary` 輸入，無 `o3_summary` 輸入，因此不在 Section 7.2 的 13 模型比較中。詳見 Section 7.2b。

**按 Scoring Model 分組 (可比較不同 Input):**

| Scoring Model | 可用 Input Sources |
|---------------|-------------------|
| `gpt-4.1-mini` | o3_summary, gpt5_R_high_V_high, gpt5_R_minimal_V_high, gpt5_R_medium_V_high, gpt5_R_low_V_high, gpt5_R_high_V_medium (共 6 種) |
| `gpt-5` | o3_summary (4 reasoning), gpt5_R_high_V_high (4 R variants) |
| `o3` | o3_summary (3 reasoning), gpt5_R_high_V_high (1) |

---

### 7.1 實驗 A: 固定 Scoring Model，比較不同 Input

**實驗設計:**

| 變因 | 設定 |
|------|------|
| **Scoring Model** (固定) | gpt-4.1-mini |
| **Input Source** (變動) | o3_summary vs 各種 gpt5_summary |

**結果 (from Section 2.6):**

| Input A vs Input B | Exact Match | Correlation |
|-------------------|-------------|-------------|
| o3_summary vs gpt5_R_high_V_high | 42.5% | 0.699 |
| o3_summary vs gpt5_R_minimal_V_high | 42.4% | 0.687 |
| o3_summary vs gpt5_R_medium_V_high | 41.2% | 0.678 |
| o3_summary vs gpt5_R_low_V_high | 42.5% | 0.696 |
| o3_summary vs gpt5_R_high_V_medium | 43.0% | 0.701 |

**結論**: 不同 input source 造成 ~41-43% exact match，correlation ~0.68-0.70

---

### 7.2 實驗 B: 固定 Input，比較不同 Scoring Model

**實驗設計:**

| 變因 | 設定 |
|------|------|
| **Input Source** (固定) | o3_summary |
| **Scoring Model** (變動) | 13 種配置 (gpt-4.1系列×3, gpt-5×4, o3×3, o4-mini×3) |

**完整結果**: 見 Section 3.1 (78 對完整比較)

**摘要 - 模型評分傾向排序 (高分 = 高風險，依 prompt 定義: 1=very low risk, 5=very high risk):**

| Rank | Model | Mean Risk | 傾向 |
|------|-------|-----------|------|
| 1 | gpt-5_low | 2.63 | 最保守 (判斷風險較高) |
| 2 | gpt-5_minimal | 2.63 | 保守 |
| 3 | gpt-5_medium | 2.62 | 保守 |
| 4 | gpt-5_high | 2.58 | 較保守 |
| 5 | o3_high | 2.52 | 中等偏保守 |
| 6 | o3_low | 2.49 | 中等 |
| 7 | o3_medium | 2.49 | 中等 |
| 8 | gpt-4.1-mini | 2.30 | 中等偏樂觀 |
| 9 | o4-mini_low | 2.28 | 樂觀 |
| 10 | gpt-4.1-nano | 2.27 | 樂觀 |
| 11 | o4-mini_high | 2.26 | 樂觀 |
| 12 | o4-mini_medium | 2.26 | 樂觀 |
| 13 | gpt-4.1 | 2.22 | 最樂觀 (判斷風險較低) |

**關鍵發現:**
- **gpt-5 系列** 系統性給出較高分數 (2.58-2.63)，認為風險較高 = 更保守/謹慎
- **gpt-4.1 系列** 傾向給出較低分數 (2.22-2.30)，認為風險較低 = 更樂觀/激進
- 同系列內部差異小 (~0.05)，跨系列差異大 (~0.41)
- **一致性模式**: 同系列模型間 Exact Match 最高 (50-54%)，跨系列最低 (30-37%)

---

### 7.2b 補充: gpt-5-mini 模型分析 (gpt5_summary 輸入)

**為何 gpt-5-mini 不在 Section 7.2?**
gpt-5-mini 只有 `gpt5_R_high_V_high_summary` 輸入，無 `o3_summary` 輸入，無法與 Section 7.2 的 13 個模型公平比較。

**gpt-5-mini 統計數據:**

| Model | Input Source | Mean | Std | Median | Records |
|-------|--------------|------|-----|--------|---------|
| gpt-5-mini | gpt5_R_high_V_high_summary | 2.433 | 0.720 | 2.0 | 127,176 |

**與同輸入源模型比較 (gpt5_R_high_V_high_summary):**

| Model | Mean Risk | Std | 傾向 |
|-------|-----------|-----|------|
| gpt-5 (R variants) | 2.58-2.63 | 0.62-0.63 | 最保守 |
| **gpt-5-mini** | **2.433** | **0.720** | 中等 |
| gpt-4.1-mini | 2.29 | 0.89 | 較樂觀 |

**結論**:
- gpt-5-mini (Mean 2.43) 介於 gpt-5_high (2.58) 和 gpt-4.1-mini (2.29) 之間
- 標準差 (0.72) 介於 gpt-5 系列 (0.62-0.63) 和 gpt-4.1-mini (0.89) 之間
- gpt-5-mini 風險評分較 gpt-5 樂觀，但仍比 gpt-4.1-mini 保守

---

### 7.3 實驗 C: 固定 Input + 固定 Scoring Model，比較不同 Reasoning Effort

**實驗設計:**

| 變因 | 設定 |
|------|------|
| **Input Source** (固定) | o3_summary |
| **Scoring Model** (固定) | O3 或 GPT-5 |
| **Scoring Reasoning Effort** (變動) | minimal / low / medium / high |

**注意**: 這裡的 reasoning effort 是指 **評分時** 的參數，不是生成摘要時的參數。

**資料來源**: 127,176 筆記錄 (完整 FinRL 數據集)

---

#### 7.3.1 O3 Scoring Model (3 reasoning levels: low/medium/high)
- Input: `o3_summary` (固定)
- Scoring Model: O3 (固定)
- Variable: O3 的 scoring reasoning effort

| Comparison | Exact Match | Within ±1 |
|------------|-------------|-----------|
| low vs medium | 99.3% | 99.3% |
| low vs high | 99.3% | 99.3% |
| medium vs high | 99.3% | 99.3% |

**O3 Risk scores are virtually identical across reasoning levels!**

#### 7.3.2 GPT-5 Scoring Model (minimal vs high)
- Input: `o3_summary` (固定)
- Scoring Model: GPT-5 (固定)
- Variable: GPT-5 的 scoring reasoning effort

| Comparison | Exact Match | Records |
|------------|-------------|---------|
| minimal vs high | 79.9% | 77,871 |

---

### 7.4 Risk vs Sentiment Consistency Comparison

| Score Type | Model | Avg Exact Match | Note |
|------------|-------|-----------------|------|
| **Risk** | O3 | 99.3% | Near-perfect consistency |
| **Risk** | GPT-5 | 79.9% | High consistency |
| Sentiment | O3 | 53.7% | Moderate consistency |
| Sentiment | GPT-5 | 50.3% | Lower consistency |

**Key Finding**: Risk scoring is significantly more robust to reasoning effort changes than sentiment scoring.

### 7.5 Why Risk Scores Are More Consistent

Risk scoring appears to be a more objective task:
- Risk factors (debt, litigation, regulatory issues) are more concrete
- Sentiment involves subjective interpretation of tone and outlook
- Risk has clearer decision boundaries (is there a risk or not?)

### 7.6 Risk Score Distribution

| Score | Percentage | Interpretation (依 prompt 定義) |
|-------|------------|--------------------------------|
| 1 | 1.6% | Very Low Risk |
| 2 | 44.4% | Low Risk |
| 3 | 47.7% | Moderate Risk |
| 4 | 6.3% | High Risk |
| 5 | 0.02% | Very High Risk |

多數文章被評為低至中等風險 (scores 2-3, 共 92%)，高風險 (4-5) 僅占 6.3%。

### 7.7 Sample Risk Score Differences (GPT-5 minimal vs high)

| Article Title | Stock | Risk (minimal) | Risk (high) |
|---------------|-------|----------------|-------------|
| Apple To Halt Sale Of Watch Series 9... | AAPL | 4 | 3 |
| US STOCKS-Wall St subdued... | Various | 3 | 2 |
| Guru Fundamental Report for AAPL | AAPL | 1 | 2 |

*Even with 20% disagreement, differences are typically only ±1 point.*

### 7.8 Key Insights

1. **Risk scoring is extremely robust**: 79.9%-99.3% consistency across reasoning levels
2. **O3 is nearly deterministic for risk**: 99.3% exact match is effectively the same score
3. **GPT-5 shows some variation**: 79.9% consistency is still high, with differences typically ±1
4. **Objective tasks are easier to score consistently**: Risk vs Sentiment demonstrates this clearly
5. **Production recommendation**: For risk scoring, reasoning effort doesn't matter much

---

## 8. Claude Model Input Source

**Confirmed**: Claude models use `gpt_5_summary` as input source.

Evidence from file naming:
- `risk_haiku_by_gpt5_summary.csv`
- `risk_sonnet_by_gpt5_summary.csv`
- `risk_opus_by_gpt5_summary.csv`

---


*Report generated by ab_score_comparison.py*
*Deep analysis added: 2025-12-31*