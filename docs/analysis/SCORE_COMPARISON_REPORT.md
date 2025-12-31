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


*Report generated by ab_score_comparison.py*