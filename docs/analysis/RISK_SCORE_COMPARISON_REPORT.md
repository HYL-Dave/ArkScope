# A/B Score Comparison Report

**Generated**: 2025-12-31 08:53:58

**Score Type**: risk

**Sample Size**: 3000 per comparison


---

## 1. Score File Inventory

| Model | Files | Input Sources |
|-------|-------|---------------|
| claude | 3 | unknown |
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

### 3.1 Pairwise Agreement (o3_summary input)

| Model A vs Model B | Exact Match | Within ±1 | Correlation |
|-------------------|-------------|-----------|-------------|
| gpt-5_high vs o3_low | 50.1% | 62.7% | 0.729 |
| gpt-4.1 vs gpt-4.1-mini | 43.4% | 59.4% | 0.706 |
| o4-mini_medium vs gpt-4.1-mini | 39.6% | 60.6% | 0.678 |
| gpt-4.1-nano vs gpt-4.1-mini | 38.4% | 61.6% | 0.678 |
| gpt-4.1 vs o4-mini_medium | 37.6% | 59.9% | 0.656 |
| o4-mini_medium vs o3_low | 37.4% | 60.8% | 0.634 |
| gpt-4.1-mini vs o3_low | 37.1% | 60.4% | 0.608 |
| o4-mini_medium vs gpt-5_high | 35.9% | 59.8% | 0.607 |
| gpt-5_high vs gpt-4.1-mini | 35.5% | 59.1% | 0.566 |
| gpt-4.1-nano vs o4-mini_medium | 34.8% | 60.6% | 0.585 |
| gpt-4.1 vs o3_low | 34.8% | 60.6% | 0.660 |
| gpt-4.1-nano vs o3_low | 34.5% | 60.7% | 0.513 |
| gpt-4.1 vs gpt-5_high | 34.3% | 58.3% | 0.609 |
| gpt-4.1 vs gpt-4.1-nano | 33.5% | 59.7% | 0.565 |
| gpt-4.1-nano vs gpt-5_high | 31.9% | 59.8% | 0.469 |

### 3.2 Score Distribution by Model

| Model | Mean | Std | Median |
|-------|------|-----|--------|
| gpt-4.1 | 2.22 | 0.93 | 2.0 |
| gpt-4.1-mini | 2.30 | 0.88 | 2.0 |
| gpt-4.1-nano | 2.27 | 0.80 | 2.0 |
| gpt-5_high | 2.58 | 0.62 | 3.0 |
| o3_low | 2.49 | 0.64 | 2.0 |
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

## 7. Deep Reasoning Effort Analysis

### 7.0 實驗設計 (Controlled Variables)

本分析測試 **評分模型 (Scoring Model)** 的 reasoning effort 對 Risk 評分一致性的影響。

**控制變因說明:**

| 變因 | 說明 | 本實驗設定 |
|------|------|-----------|
| **Input Source** (固定) | 餵給評分模型的摘要來源 | `o3_summary` (所有比較都使用相同 input) |
| **Scoring Model** (固定) | 執行評分的模型 | O3 或 GPT-5 (同一組比較內模型固定) |
| **Scoring Reasoning Effort** (變動) | 評分模型的推理強度 | minimal / low / medium / high |

**注意**: 這裡的 reasoning effort 是指 **評分時** 的參數，不是生成摘要時的參數。

**資料來源**: 127,176 筆記錄 (完整 FinRL 數據集)

---

### 7.1 Risk Score Consistency by Scoring Model Reasoning Effort

**O3 Scoring Model (3 reasoning levels: low/medium/high):**
- Input: `o3_summary` (固定)
- Scoring Model: O3 (固定)
- Variable: O3 的 reasoning effort

| Comparison | Exact Match | Within ±1 |
|------------|-------------|-----------|
| low vs medium | 99.3% | 99.3% |
| low vs high | 99.3% | 99.3% |
| medium vs high | 99.3% | 99.3% |

**O3 Risk scores are virtually identical across reasoning levels!**

**GPT-5 Scoring Model (minimal vs high):**
- Input: `o3_summary` (固定)
- Scoring Model: GPT-5 (固定)
- Variable: GPT-5 的 reasoning effort

| Comparison | Exact Match | Records |
|------------|-------------|---------|
| minimal vs high | 79.9% | 77,871 |

### 7.2 Comparison with Sentiment Scores

| Score Type | Model | Avg Exact Match | Note |
|------------|-------|-----------------|------|
| Risk | O3 | 99.3% | Near-perfect consistency |
| Risk | GPT-5 | 79.9% | High consistency |
| Sentiment | O3 | 53.7% | Moderate consistency |
| Sentiment | GPT-5 | 50.3% | Lower consistency |

**Key Finding**: Risk scoring is significantly more robust to reasoning effort changes than sentiment scoring.

### 7.3 Why Risk Scores Are More Consistent

Risk scoring appears to be a more objective task:
- Risk factors (debt, litigation, regulatory issues) are more concrete
- Sentiment involves subjective interpretation of tone and outlook
- Risk has clearer decision boundaries (is there a risk or not?)

### 7.4 Risk Score Distribution

| Score | Percentage | Interpretation |
|-------|------------|----------------|
| 1 | 1.6% | Very High Risk |
| 2 | 44.4% | High Risk |
| 3 | 47.7% | Moderate Risk |
| 4 | 6.3% | Low Risk |
| 5 | 0.02% | Very Low Risk |

Most articles are scored as moderate-to-high risk (scores 2-3).

### 7.5 Sample Risk Score Differences (GPT-5 minimal vs high)

| Article Title | Stock | Risk (minimal) | Risk (high) |
|---------------|-------|----------------|-------------|
| Apple To Halt Sale Of Watch Series 9... | AAPL | 4 | 3 |
| US STOCKS-Wall St subdued... | Various | 3 | 2 |
| Guru Fundamental Report for AAPL | AAPL | 1 | 2 |

*Even with 20% disagreement, differences are typically only ±1 point.*

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