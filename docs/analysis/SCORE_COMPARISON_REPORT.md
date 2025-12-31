# A/B Score Comparison Report

**Generated**: 2025-12-31 08:50:35

**Score Type**: sentiment

**Sample Size**: 3000 per comparison


---

## 1. Score File Inventory

| Model | Files | Input Sources |
|-------|-------|---------------|
| claude | 3 | unknown |
| gpt-4.1 | 1 | o3_summary |
| gpt-4.1-mini | 6 | o3_summary, gpt_5_summary |
| gpt-4.1-nano | 1 | o3_summary |
| gpt-5 | 8 | o3_summary, gpt_5_summary |
| gpt-5-mini | 1 | gpt_5_summary |
| o3 | 5 | o3_summary, gpt_5_summary, unknown |
| o4-mini | 4 | o3_summary, unknown |


---

## 2. Input Source Impact Analysis

*How does the input (Title vs Summary) affect scores?*

### 2.6 gpt-4.1-mini

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs o3_summary | 46.5% | 62.0% | 0.829 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=minimal_verbosity_high_summary V=high_summary | 48.8% | 62.3% | 0.856 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 50.7% | 62.5% | 0.880 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 49.5% | 62.3% | 0.865 | 3,000 |
| gpt_5_summary R=high_verbosity_high_summary V=high_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 50.0% | 62.5% | 0.873 | 3,000 |
| o3_summary vs gpt_5_summary R=minimal_verbosity_high_summary V=high_summary | 47.4% | 61.9% | 0.830 | 3,000 |
| o3_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 46.6% | 61.9% | 0.827 | 3,000 |
| o3_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 46.2% | 61.6% | 0.820 | 3,000 |
| o3_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 46.5% | 62.0% | 0.827 | 3,000 |
| gpt_5_summary R=minimal_verbosity_high_summary V=high_summary vs gpt_5_summary R=high_verbosity_medium_summary V=medium_summary | 48.8% | 62.1% | 0.852 | 3,000 |
| gpt_5_summary R=minimal_verbosity_high_summary V=high_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 49.2% | 62.3% | 0.862 | 3,000 |
| gpt_5_summary R=minimal_verbosity_high_summary V=high_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 49.0% | 62.4% | 0.858 | 3,000 |
| gpt_5_summary R=high_verbosity_medium_summary V=medium_summary vs gpt_5_summary R=low_verbosity_high_summary V=high_summary | 49.3% | 62.3% | 0.861 | 3,000 |
| gpt_5_summary R=high_verbosity_medium_summary V=medium_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 49.9% | 62.6% | 0.875 | 3,000 |
| gpt_5_summary R=low_verbosity_high_summary V=high_summary vs gpt_5_summary R=medium_verbosity_high_summary V=high_summary | 49.0% | 62.7% | 0.870 | 3,000 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| gpt_5_summary R=high_verbosity_high_summ | 3.45 | 0.95 | 3.0 |
| o3_summary | 3.44 | 0.95 | 3.0 |
| gpt_5_summary R=minimal_verbosity_high_s | 3.46 | 0.94 | 3.0 |
| gpt_5_summary R=high_verbosity_medium_su | 3.48 | 0.96 | 4.0 |
| gpt_5_summary R=low_verbosity_high_summa | 3.50 | 0.96 | 4.0 |
| gpt_5_summary R=medium_verbosity_high_su | 3.47 | 0.95 | 3.0 |

### 2.4 gpt-5

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| o3_summary vs gpt_5_summary R=high_verbosity_high_summary V=high_summary | 48.2% | 62.8% | 0.811 | 3,000 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| o3_summary | 3.31 | 0.76 | 3.0 |
| gpt_5_summary R=high_verbosity_high_summ | 3.41 | 0.82 | 3.0 |

### 2.7 o3

**Pairwise Agreement:**

| Comparison | Exact Match | Within ±1 | Correlation | N |
|------------|-------------|-----------|-------------|---|
| o3_summary vs unknown | 67.9% | 96.3% | 0.641 | 81 |
| o3_summary vs gpt_5_summary R=high_verbosity_high V=high | 49.8% | 62.7% | 0.828 | 3,000 |
| unknown vs gpt_5_summary R=high_verbosity_high V=high | 65.4% | 93.8% | 0.590 | 81 |

**Score Distributions:**

| Input Source | Mean | Std | Median |
|--------------|------|-----|--------|
| o3_summary | 3.30 | 0.81 | 3.0 |
| unknown | 3.32 | 0.76 | 3.0 |
| gpt_5_summary R=high_verbosity_high V=hi | 3.31 | 0.82 | 3.0 |


---

## 3. Scoring Model Comparison

*Using same input source (o3_summary), how do different models score?*

### 3.1 Pairwise Agreement (o3_summary input)

| Model A vs Model B | Exact Match | Within ±1 | Correlation |
|-------------------|-------------|-----------|-------------|
| gpt-5_low vs o3_high | 54.1% | 62.9% | 0.880 |
| gpt-4.1 vs gpt-4.1-mini | 50.0% | 62.4% | 0.864 |
| o4-mini_medium vs o3_high | 47.8% | 62.1% | 0.827 |
| gpt-4.1 vs gpt-5_low | 47.6% | 62.7% | 0.847 |
| gpt-4.1 vs o4-mini_medium | 47.5% | 62.4% | 0.840 |
| gpt-4.1 vs o3_high | 47.1% | 62.8% | 0.847 |
| o4-mini_medium vs gpt-5_low | 46.9% | 62.2% | 0.816 |
| o4-mini_medium vs gpt-4.1-mini | 46.9% | 62.0% | 0.831 |
| gpt-5_low vs gpt-4.1-mini | 43.9% | 62.2% | 0.799 |
| gpt-4.1-mini vs o3_high | 42.8% | 62.1% | 0.787 |
| gpt-4.1-nano vs gpt-5_low | 40.7% | 60.5% | 0.636 |
| gpt-4.1-nano vs gpt-4.1-mini | 39.4% | 61.4% | 0.726 |
| gpt-4.1-nano vs o4-mini_medium | 39.2% | 60.1% | 0.673 |
| gpt-4.1-nano vs o3_high | 39.1% | 60.1% | 0.618 |
| gpt-4.1 vs gpt-4.1-nano | 38.6% | 60.3% | 0.674 |

### 3.2 Score Distribution by Model

| Model | Mean | Std | Median |
|-------|------|-----|--------|
| gpt-4.1 | 3.46 | 0.92 | 4.0 |
| gpt-4.1-mini | 3.44 | 0.95 | 3.0 |
| gpt-4.1-nano | 3.33 | 0.87 | 3.0 |
| gpt-5_low | 3.31 | 0.76 | 3.0 |
| o3_high | 3.30 | 0.81 | 3.0 |
| o4-mini_medium | 3.40 | 0.94 | 3.0 |


---

## 4. Symbol-Title Relevance Impact

### 4.1 Score Comparison by Symbol Presence in Title

| Category | Count | Mean Score | Std |
|----------|-------|------------|-----|
| Symbol In Title | 556 | 3.43 | 0.93 |
| Symbol Not In Title | 1,335 | 3.46 | 0.92 |

### 4.2 Roundup vs Non-Roundup Articles

| Category | Count | Mean Score | Std |
|----------|-------|------------|-----|
| Roundup Articles | 141 | 3.40 | 0.90 |
| Non Roundup Articles | 1,750 | 3.46 | 0.92 |


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
| o3_summary vs gpt5_R_high_V_high | 46.5% | 0.829 |
| o3_summary vs gpt5_R_minimal_V_high | 47.4% | 0.830 |
| o3_summary vs gpt5_R_medium_V_high | 46.5% | 0.827 |
| o3_summary vs gpt5_R_low_V_high | 46.2% | 0.820 |
| o3_summary vs gpt5_R_high_V_medium | 46.6% | 0.827 |

**結論**: 不同 input source 造成 ~46-47% exact match，correlation ~0.82-0.83

---

### 7.2 實驗 B: 固定 Input，比較不同 Scoring Model

**實驗設計:**

| 變因 | 設定 |
|------|------|
| **Input Source** (固定) | o3_summary |
| **Scoring Model** (變動) | 13 種不同模型 |

**結果 (from Section 3.1, 完整版):**

| Model A vs Model B | Exact Match | Correlation |
|-------------------|-------------|-------------|
| gpt-5_low vs o3_high | 54.1% | 0.880 |
| gpt-4.1 vs gpt-4.1-mini | 50.0% | 0.864 |
| o4-mini_medium vs o3_high | 47.8% | 0.827 |
| gpt-4.1 vs gpt-5_low | 47.6% | 0.847 |
| gpt-4.1 vs o4-mini_medium | 47.5% | 0.840 |
| gpt-4.1 vs o3_high | 47.1% | 0.847 |
| gpt-4.1-mini vs o3_high | 42.8% | 0.787 |
| gpt-4.1-nano vs gpt-5_low | 40.7% | 0.636 |
| gpt-4.1 vs gpt-4.1-nano | 38.6% | 0.674 |

**結論**: 不同 scoring model 造成 ~38-54% exact match，差異比 input source 更大

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

| Comparison | Exact Match | Within ±1 | Mean A | Mean B |
|------------|-------------|-----------|--------|--------|
| low vs medium | 53.9% | 61.1% | 3.294 | 3.299 |
| low vs high | 53.3% | 61.1% | 3.294 | 3.298 |
| medium vs high | 54.0% | 61.1% | 3.299 | 3.298 |

**O3 平均一致性: 53.7% exact match**

#### 7.3.2 GPT-5 Scoring Model (4 reasoning levels: minimal/low/medium/high)
- Input: `o3_summary` (固定)
- Scoring Model: GPT-5 (固定)
- Variable: GPT-5 的 scoring reasoning effort

| Comparison | Exact Match | Within ±1 | Mean A | Mean B |
|------------|-------------|-----------|--------|--------|
| minimal vs low | 50.3% | 61.0% | 3.402 | 3.304 |
| minimal vs medium | 47.5% | 61.0% | 3.402 | 3.270 |
| minimal vs high | 44.6% | 60.9% | 3.402 | 3.236 |
| low vs medium | 54.1% | 61.1% | 3.304 | 3.270 |
| low vs high | 51.6% | 61.1% | 3.304 | 3.236 |
| medium vs high | 53.7% | 61.2% | 3.270 | 3.236 |

**GPT-5 平均一致性: 50.3% exact match**

#### 7.3.3 Risk Score Consistency (同樣實驗設計)

| Model | Comparison | Exact Match | Note |
|-------|------------|-------------|------|
| O3 | all levels | 99.3% | 幾乎完全一致 |
| GPT-5 | minimal vs high | 79.9% | 高度一致 |

**結論**: Risk 評分比 Sentiment 更穩定，不受 reasoning effort 影響

---

### 7.4 Score Drift Analysis

**GPT-5 顯示系統性評分偏移 (Systematic Score Drift):**

| Reasoning Level | Mean Sentiment Score | Trend |
|-----------------|---------------------|-------|
| minimal | 3.402 | ↑ Most optimistic |
| low | 3.304 | |
| medium | 3.270 | |
| high | 3.236 | ↓ Most conservative |

**O3 無明顯評分偏移:**

| Reasoning Level | Mean Sentiment Score |
|-----------------|---------------------|
| low | 3.294 |
| medium | 3.299 |
| high | 3.298 |

### 7.5 Adjacent vs Non-Adjacent Comparison

| Category | Average Exact Match | Note |
|----------|---------------------|------|
| GPT-5 Adjacent (minimal↔low, low↔medium, medium↔high) | 52.7% | 鄰近層級較一致 |
| GPT-5 Non-adjacent (minimal↔high, etc.) | 47.9% | 遠離層級差異較大 |

### 7.6 Key Insights

1. **Risk scoring is more robust**: 79.9%-99.3% consistency vs 44.6%-54.0% for sentiment
2. **GPT-5 has systematic bias**: Higher reasoning → more conservative (lower) scores
3. **O3 is more stable**: No significant score drift across reasoning levels
4. **Adjacent levels agree more**: Score changes are gradual, not random
5. **Sentiment is harder to score consistently**: ~50% disagreement rate even with same input

### 7.7 Sample Disagreement Cases (GPT-5 minimal vs high)

| Article Title | Stock | Score (minimal) | Score (high) | Diff |
|---------------|-------|-----------------|--------------|------|
| PACCAR Inc. Keeps Cruising, but the Market's Worried... | PCAR | 3 | 1 | +2 |
| Weak Crypto-Mining Demand Is Hurting NVIDIA's Cash Flow... | AMD | 4 | 2 | +2 |
| Did the Merger Between Major Dollar Stores Stall Due to Antitrust? | DLTR | 4 | 2 | +2 |
| Why the Post-Earnings Dip in AMD Stock Is a Prime Opportunity... | AMD | 4 | 2 | +2 |
| The Best Stocks to Invest $20,000 in Right Now | VRTX | 5 | 3 | +2 |

*Higher reasoning tends to give more cautious/pessimistic sentiment scores.*

---

## 8. Claude Model Input Source

**Confirmed**: Claude models use `gpt_5_summary` as input source.

Evidence from file naming:
- `sentiment_haiku_by_gpt5_summary.csv`
- `sentiment_sonnet_by_gpt5_summary.csv`
- `sentiment_opus_by_gpt5_summary.csv`

---


*Report generated by ab_score_comparison.py*
*Deep analysis added: 2025-12-31*