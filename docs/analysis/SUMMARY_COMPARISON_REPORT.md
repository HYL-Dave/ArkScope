# Comprehensive Summary Comparison Report

**Generated**: 2025-12-31 07:44:33

**Similarity Sample Size**: 2000 records per comparison


---

## 1. Summary Data Inventory

### 1.1 Available Summary Sources

| Category | Summary Type | Source | R/V Config |
|----------|--------------|--------|------------|
| Traditional | Lsa_summary | LSA algorithm | N/A |
| Traditional | Luhn_summary | Luhn algorithm | N/A |
| Traditional | Textrank_summary | TextRank algorithm | N/A |
| Traditional | Lexrank_summary | LexRank algorithm | N/A |
| LLM | o3_summary | OpenAI o3 | default |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=minimal, V=low |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=minimal, V=medium |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=minimal, V=high |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=low, V=low |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=low, V=medium |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=low, V=high |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=medium, V=low |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=medium, V=medium |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=medium, V=high |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=high, V=low |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=high, V=medium |
| LLM | gpt_5_summary | OpenAI GPT-5 | R=high, V=high |

**Total: 4 traditional + 1 o3 + 12 gpt-5 = 17 summary types**


---

## 2. Traditional Summary Statistics

### 2.1 Length Statistics

| Summary Type | Valid Count | Coverage | Avg Words | Std | Min | Max | Median |
|--------------|-------------|----------|-----------|-----|-----|-----|--------|
| Lsa_summary | 77,871 | 61.2% | 89.7 | 47.7 | 5 | 3626 | 86 |
| Luhn_summary | 77,871 | 61.2% | 90.3 | 51.8 | 5 | 3627 | 84 |
| Textrank_summary | 77,871 | 61.2% | 96.5 | 51.6 | 5 | 3626 | 90 |
| Lexrank_summary | 77,871 | 61.2% | 83.6 | 48.2 | 4 | 3626 | 76 |
| o3_summary | 77,871 | 61.2% | 102.1 | 24.9 | 1 | 238 | 102 |


---

## 3. GPT-5 Configuration Comparison (Reason × Verbosity)

### 3.1 Length Statistics by R/V Configuration

| R \ V | low (words) | medium (words) | high (words) |
|-------|-------------|----------------|--------------|
| minimal | 76.9 ± 19.5 | 89.3 ± 21.9 | 95.9 ± 23.5 |
| low | 78.8 ± 21.7 | 92.7 ± 24.7 | 100.1 ± 26.5 |
| medium | 79.3 ± 21.5 | 94.9 ± 24.8 | 104.7 ± 28.0 |
| high | 77.3 ± 20.8 | 94.5 ± 24.7 | 106.1 ± 28.1 |


---

## 4. Pairwise Similarity Analysis

### 4.1 Traditional Summaries vs Each Other

| Comparison | Jaccard Mean | Jaccard Std | N Compared |
|------------|--------------|-------------|------------|
| Lsa_summary vs Luhn_summary | 0.551 | 0.283 | 2,000 |
| Lsa_summary vs Textrank_summary | 0.552 | 0.283 | 2,000 |
| Lsa_summary vs Lexrank_summary | 0.574 | 0.289 | 2,000 |
| Luhn_summary vs Textrank_summary | 0.673 | 0.270 | 2,000 |
| Luhn_summary vs Lexrank_summary | 0.624 | 0.273 | 2,000 |
| Textrank_summary vs Lexrank_summary | 0.651 | 0.276 | 2,000 |

### 4.2 Traditional vs O3

| Comparison | Jaccard Mean | Jaccard Std | N Compared |
|------------|--------------|-------------|------------|
| Lsa_summary vs o3_summary | 0.124 | 0.042 | 2,000 |
| Luhn_summary vs o3_summary | 0.122 | 0.042 | 2,000 |
| Textrank_summary vs o3_summary | 0.127 | 0.042 | 2,000 |
| Lexrank_summary vs o3_summary | 0.126 | 0.045 | 2,000 |

### 4.3 O3 vs GPT-5 (All Configurations)

| GPT-5 Config (R, V) | Jaccard Mean | Jaccard Std | N Compared |
|---------------------|--------------|-------------|------------|
| R=minimal, V=low | 0.237 | 0.075 | 2,000 |
| R=minimal, V=medium | 0.249 | 0.077 | 2,000 |
| R=minimal, V=high | 0.253 | 0.075 | 2,000 |
| R=low, V=low | 0.233 | 0.075 | 2,000 |
| R=low, V=medium | 0.244 | 0.074 | 2,000 |
| R=low, V=high | 0.247 | 0.074 | 2,000 |
| R=medium, V=low | 0.234 | 0.070 | 2,000 |
| R=medium, V=medium | 0.248 | 0.070 | 2,000 |
| R=medium, V=high | 0.250 | 0.070 | 2,000 |
| R=high, V=low | 0.232 | 0.068 | 2,000 |
| R=high, V=medium | 0.249 | 0.070 | 2,000 |
| R=high, V=high | 0.253 | 0.069 | 2,000 |

### 4.4 GPT-5 Configurations vs Each Other (Sample: high-high vs others)

| Comparison | Jaccard Mean | Jaccard Std |
|------------|--------------|-------------|
| R=high,V=high vs R=minimal,V=low | 0.309 | 0.090 |
| R=high,V=high vs R=minimal,V=medium | 0.325 | 0.093 |
| R=high,V=high vs R=minimal,V=high | 0.324 | 0.091 |
| R=high,V=high vs R=low,V=low | 0.325 | 0.094 |
| R=high,V=high vs R=low,V=medium | 0.341 | 0.097 |
| R=high,V=high vs R=low,V=high | 0.340 | 0.092 |
| R=high,V=high vs R=medium,V=low | 0.332 | 0.092 |
| R=high,V=high vs R=medium,V=medium | 0.353 | 0.095 |
| R=high,V=high vs R=medium,V=high | 0.355 | 0.096 |
| R=high,V=high vs R=high,V=low | 0.327 | 0.091 |
| R=high,V=high vs R=high,V=medium | 0.355 | 0.095 |

### 4.5 Lsa_summary vs GPT-5 (All Configurations)

| GPT-5 Config (R, V) | Jaccard Mean | Jaccard Std |
|---------------------|--------------|-------------|
| R=minimal, V=low | 0.127 | 0.050 |
| R=minimal, V=medium | 0.132 | 0.050 |
| R=minimal, V=high | 0.132 | 0.051 |
| R=low, V=low | 0.126 | 0.047 |
| R=low, V=medium | 0.129 | 0.048 |
| R=low, V=high | 0.130 | 0.049 |
| R=medium, V=low | 0.124 | 0.047 |
| R=medium, V=medium | 0.129 | 0.048 |
| R=medium, V=high | 0.130 | 0.049 |
| R=high, V=low | 0.123 | 0.046 |
| R=high, V=medium | 0.130 | 0.050 |
| R=high, V=high | 0.131 | 0.049 |


---

## 5. Key Findings

### 5.1 O3 vs GPT-5 Similarity Range

- **Most similar to O3**: GPT-5 R=minimal, V=high (Jaccard=0.253)
- **Least similar to O3**: GPT-5 R=high, V=low (Jaccard=0.232)

### 5.2 Summary Length Comparison

- **Traditional (Lsa)**: 89.7 words
- **O3**: 102.1 words
- **GPT-5 shortest**: R=minimal, V=low (76.9 words)
- **GPT-5 longest**: R=high, V=high (106.1 words)

### 5.3 Verbosity Effect on Length

| Reasoning | V=low → V=high Δ |
|-----------|------------------|
| minimal | +19.0 words |
| low | +21.3 words |
| medium | +25.3 words |
| high | +28.8 words |


---

## 6. Representative Sample Comparison

*Comparing same article across different summary methods*

### Sample 1: EXC (2019-12-03)

**Title**: How The Parts Add Up: RPV Targets $74

**Lsa_summary** (126 words):
> Below is a twelve month price history chart comparing the stock performance of GM, NCLH, and EXC: Below is a summary table of the current analyst target prices discussed above: Are analysts justified in these targets, or overly optimistic about where these stocks will be trading 12 months from now? Three of RPV's underlying holdings with notable upside to their analyst target prices are General Motors Co (Symbol: GM), Norwegian Cruise Line Holdings Ltd (Symbol: NCLH), and Exelon Corp (Symbol: EXC). Similarly, NCLH has 22.44% upside from the recent share price of $53.15 if the average analyst target price of $65.08/share is reached, and analysts on average are expecting EXC to reach a target price of $53.00/share, which is 20.70% above the recent price of $43.91.

**o3_summary** (77 words):
> ETF Channel analysis shows the Invesco S&P 500—Pure Value ETF (RPV) has a weighted average analyst 12-month target price of $74.10, implying about 9.8% upside from its recent $67.50 level. Key contributors to this projected gain are General Motors, Norwegian Cruise Line and Exelon, which trade 34%, 22% and 21% below their respective consensus targets. The article notes investors should assess whether these optimistic targets are warranted or subject to revision given evolving company and industry conditions.

**gpt_5_summary R=high, V=high** (83 words):
> ETF Channel estimates an implied 12-month target price of $74.10 for the Invesco S&P 500 Pure Value ETF (RPV), implying 9.78% upside from its recent $67.50 price based on the average analyst targets of its holdings. Stocks with notable gaps to targets include General Motors ($48.25 vs. $35.88, +34.48%), Norwegian Cruise Line ($65.08 vs. $53.15, +22.44%), and Exelon ($53.00 vs. $43.91, +20.70%). The article cautions that elevated targets may reflect optimism or lag industry developments and could be downgraded, urging further investor research.

**gpt_5_summary R=minimal, V=low** (73 words):
> ETF Channel analysis shows the Invesco S&P 500 Pure Value ETF (RPV) has a weighted average 12-month implied target of $74.10 versus a recent $67.50 price, implying 9.78% upside. Notable holdings with larger gaps to analysts’ targets are GM (+34.5% to $48.25), Norwegian Cruise Line (+22.4% to $65.08), and Exelon (+20.7% to $53.00). The article cautions that such targets may reflect optimism or risk future downgrades, stressing the need for further investor research.

### Sample 2: TXN (2017-05-31)

**Title**: Noteworthy ETF Inflows: MTUM, UNH, GOOGL, TXN

**Lsa_summary** (115 words):
> Among the largest underlying components of MTUM, in trading today UnitedHealth Group Inc (Symbol: UNH) is off about 0.1%, Alphabet Inc (Symbol: GOOGL) is down about 1.1%, and Texas Instruments Inc. (Symbol: TXN) is higher by about 1.4%. Looking today at week-over-week shares outstanding changes among the universe of ETFs covered at ETF Channel , one standout is the iShares Edge MSCI USA Momentum Factor ETF (Symbol: MTUM) where we have detected an approximate $825.4 million dollar inflow -- that's a 31.4% increase week over week in outstanding units (from 29,650,000 to 38,950,000). These ''units'' can be traded back and forth just like stocks, but can also be created or destroyed to accommodate investor demand.

**o3_summary** (77 words):
> The iShares Edge MSCI USA Momentum Factor ETF (MTUM) absorbed roughly $825.4 million in net inflows over the past week, boosting its shares outstanding by 31.4% to 38.95 million. The influx means the fund will have to purchase additional stakes in its largest holdings—UnitedHealth, Alphabet, and Texas Instruments—which today are down 0.1%, down 1.1%, and up 1.4%, respectively. MTUM is trading near its 52-week high at $88.71 (range: $73.15–$89.06), indicating strong investor appetite for momentum-driven U.S. equities.

**gpt_5_summary R=high, V=high** (73 words):
> The iShares Edge MSCI USA Momentum Factor ETF (MTUM) recorded an estimated $825.4 million inflow week over week, boosting shares outstanding by 31.4% to 38.95 million from 29.65 million, signaling strong demand for momentum exposure. Such creations typically require buying underlying holdings and can influence constituents; on the day, UnitedHealth slipped ~0.1%, Alphabet fell ~1.1%, and Texas Instruments rose ~1.4%. MTUM last traded at $88.71, near its 52-week high of $89.0601 (low $73.15).

**gpt_5_summary R=minimal, V=low** (56 words):
> The iShares Edge MSCI USA Momentum Factor ETF (MTUM) saw a significant ~$825.4M inflow, boosting units by 31.4% week over week (29.65M to 38.95M). Major holdings moved mixed: UNH -0.1%, GOOGL -1.1%, TXN +1.4%. MTUM trades near its 52-week high at $88.71, within a $73.15–$89.06 range. Large ETF inflows suggest potential buying pressure on underlying components.

### Sample 3: CDNS (2023-08-03)

**Title**: Analysts Forecast 10% Gains Ahead For The Holdings of VOOG

**Lsa_summary** (99 words):
> Vanguard S&P 500 Growth ETF VOOG $257.15 $282.25 9.76% Cadence Design Systems Inc CDNS $228.74 $252.54 10.40% Equifax Inc EFX $201.70 $222.44 10.28% Quest Diagnostics, Inc. DGX $134.76 $148.58 10.26% Are analysts justified in these targets, or overly optimistic about where these stocks will be trading 12 months from now? Three of VOOG's underlying holdings with notable upside to their analyst target prices are Cadence Design Systems Inc (Symbol: CDNS), Equifax Inc (Symbol: EFX), and Quest Diagnostics, Inc. (Symbol: DGX). Although CDNS has traded at a recent price of $228.74/share, the average analyst target is 10.40% higher at $252.54/share.

**o3_summary** (85 words):
> ETF Channel calculates that Vanguard S&P 500 Growth ETF (VOOG) has a weighted-average analyst 12-month target price of $282.25, about 9.8% above its recent $257.15 level. Key contributors to this potential upside are three holdings—Cadence Design Systems (CDNS), Equifax (EFX) and Quest Diagnostics (DGX)—whose average analyst targets imply gains of roughly 10% each (to $252.54, $222.44 and $148.58, respectively) from current prices. The article notes that while such gaps suggest optimism, investors should investigate whether the underlying assumptions remain valid before relying on these targets.

**gpt_5_summary R=high, V=high** (79 words):
> Analyst targets suggest roughly 10% upside for the Vanguard S&P 500 Growth ETF (VOOG), with a weighted average 12‑month target of $282.25 versus a recent $257.15 (9.76% upside). Notable holdings show similar potential: Cadence Design Systems (CDNS) at $252.54 vs. $228.74 (+10.40%), Equifax (EFX) at $222.44 vs. $201.70 (+10.28%), and Quest Diagnostics (DGX) at $148.58 vs. $134.76 (+10.26%). The article notes these targets reflect optimism but could be revised if conditions change, underscoring the need for further investor research.

**gpt_5_summary R=minimal, V=low** (66 words):
> Analyst targets for Vanguard S&P 500 Growth ETF (VOOG) imply 9.76% upside to $282.25 from $257.15 based on holdings’ averages. Notable constituents with similar upside: Cadence Design Systems (CDNS) at $252.54 vs. $228.74 (+10.40%), Equifax (EFX) at $222.44 vs. $201.70 (+10.28%), and Quest Diagnostics (DGX) at $148.58 vs. $134.76 (+10.26%). The piece notes such gaps may signal optimism or potential target downgrades, urging further investor research.


---

## 7. Conclusions and Recommendations

### 7.1 Summary

- **Total summary types analyzed**: 17 (4 traditional + 1 O3 + 12 GPT-5)
- **Traditional algorithms** produce shorter, more variable summaries
- **LLM summaries** are more consistent in length (lower std)
- **GPT-5 verbosity** significantly affects output length
- **O3 and GPT-5** show moderate similarity, with R=high configs being most similar


### 7.2 Recommendations

- For **sentiment/risk scoring**: Use LLM summaries (more focused, consistent)
- For **cost optimization**: Consider R=minimal or R=low with V=low
- For **maximum detail**: Use R=high, V=high
- For **O3/GPT-5 interchangeability**: R=high configs are most compatible



---


*Report generated by ab_summary_comparison.py (comprehensive mode)*