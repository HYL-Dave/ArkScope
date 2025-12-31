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

## 7. Content Quality Assessment (Deep Analysis)

*Based on manual review of 10 diverse article samples with full original text comparison*

### 7.1 LSA Summary Critical Issues

**嚴重缺陷 - 不建議用於情緒/風險評分**

| 問題類型 | 發生頻率 | 範例 |
|---------|---------|------|
| 包含廣告文字 | 約 40% | "Click to get this free report...", "To read this article on Zacks.com click here" |
| 隨機摘錄片段 | 約 60% | 抓取文章中間段落而非核心信息 |
| 忽略文章主旨 | 約 30% | APTV 分析文章中只摘錄結尾的 PAYX 推薦 |
| 接近全文複製 | 約 15% | 短文章（<200字）幾乎原封不動 |
| 資料表格碎片 | 約 25% | 直接摘錄 "$257.15 $282.25 9.76%" 等未解釋的數字 |

**具體案例分析**：
- **Sample 3 (AMGN Biotech Roundup)**: LSA 只摘錄廣告連結，完全丟失 FDA 批准、臨床試驗等核心新聞
- **Sample 4 (PAYX)**: 文章主題是 APTV，LSA 卻只摘錄文末的 PAYX 推薦，完全誤導
- **Sample 7 (AEP)**: 147 字原文，LSA 產出 132 字，幾乎無壓縮價值

### 7.2 O3 Summary Quality Assessment

**優勢 - 推薦用於綜合分析**

| 優勢項目 | 評分 | 說明 |
|---------|------|------|
| 信息整合 | ★★★★★ | 能從多段落提取並重組核心數據 |
| 因果分析 | ★★★★☆ | 主動添加 "this means...", "indicating..." 等推理 |
| 數據準確性 | ★★★★★ | 數字、百分比、日期準確率極高 |
| 主旨識別 | ★★★★☆ | 能正確區分主要 vs 次要信息 |
| 去廣告能力 | ★★★★★ | 完全過濾掉 "Click here", "Free report" 等噪音 |

**具體案例**：
- **Sample 2 (EXC EV Chargers)**: 114 字涵蓋：合作內容、投資金額、市場預測、同業比較、股票評級
- **Sample 3 (AMGN)**: 163 字覆蓋 5 家公司的交易細節（Amgen FDA/EC、Regeneron-Zoetis、Axovant $812M milestone）

### 7.3 GPT-5 Configuration Quality Comparison

| 配置 | 信息完整度 | 簡潔性 | 適用場景 |
|-----|-----------|--------|---------|
| R=high, V=high | ★★★★★ | ★★☆☆☆ | 研究報告、詳細分析 |
| R=high, V=low | ★★★★☆ | ★★★★☆ | 平衡選擇 |
| R=minimal, V=low | ★★★☆☆ | ★★★★★ | 快速掃描、大量處理 |

**R=minimal V=low 特殊觀察**：
- 有時過於簡略丟失上下文（Sample 5: 只有 36 字）
- 對於 stock-specific 標記的 roundup 文章，可能只聚焦該股票而忽略市場脈絡
- 信息密度最高，適合 token 成本敏感場景

### 7.4 Stock Symbol Mismatch Problem

**重要發現**：部分文章的 `Stock_symbol` 與實際主題不符

| 樣本 | Stock_symbol | 實際主題 | 影響 |
|------|--------------|---------|------|
| Sample 1 | AMAT | QQQ ETF 資金流出 | AMAT 只是成分股之一 |
| Sample 4 | PAYX | APTV 公司分析 | PAYX 只在文末被推薦 |
| Sample 6 | ASML | DHR 除息公告 | ASML 只是同行業提及 |

**對評分的影響**：
- 使用 Lsa_summary 時問題更嚴重（可能只摘錄次要股票信息）
- LLM 摘要通常能正確識別主旨，但可能與 stock_symbol 標記不符
- **建議**：評分時應結合 Article_title 驗證相關性

### 7.5 Information Preservation by Summary Type

基於 10 個樣本的關鍵信息保留率估計：

| 信息類型 | LSA | O3 | GPT-5 HH | GPT-5 ML |
|---------|-----|-----|----------|----------|
| 財務數據 (價格、百分比) | 60% | 95% | 98% | 90% |
| 事件描述 (併購、批准) | 40% | 90% | 95% | 85% |
| 因果分析 | 0% | 70% | 80% | 50% |
| 風險提示 | 20% | 60% | 70% | 40% |
| 市場脈絡 | 30% | 80% | 85% | 60% |

### 7.6 Content Quality Summary

```
質量排序（用於情緒/風險評分）：

1. O3_summary          - 最佳平衡，推薦作為主要輸入
2. GPT-5 R=high V=high - 最詳細但可能冗長
3. GPT-5 R=high V=low  - 良好平衡
4. GPT-5 R=minimal V=low - 適合大規模處理
5. Lsa_summary         - ❌ 不建議使用，噪音太多

傳統算法摘要（Lsa/Luhn/Textrank/Lexrank）
在財務新聞情緒分析場景中效果不佳，
因為它們無法理解語義、過濾噪音、或識別文章主旨。
```

---

## 8. Conclusions and Recommendations

### 8.1 統計分析總結

- **分析的摘要類型**: 17 種 (4 傳統 + 1 O3 + 12 GPT-5)
- **傳統算法**：長度變異大 (std 47-52)，質量不穩定
- **LLM 摘要**：長度一致 (std 20-28)，質量穩定
- **GPT-5 verbosity** 顯著影響輸出長度 (+19~29 words)

### 8.2 內容質量總結

- **LSA/傳統算法**: ❌ 不適合情緒/風險評分，噪音過多
- **O3**: ✅ 最佳選擇，信息整合與簡潔性平衡
- **GPT-5 R=high V=high**: ✅ 最詳細，適合深度分析
- **GPT-5 R=minimal V=low**: ⚠️ 成本最優但可能丟失上下文

### 8.3 評分輸入建議

| 用途 | 推薦 Summary | 理由 |
|-----|-------------|------|
| 情緒評分 | O3 或 GPT-5 R=high V=low | 主旨清晰、過濾噪音 |
| 風險評分 | O3 或 GPT-5 R=high V=high | 需要完整風險因素描述 |
| 大量處理 | GPT-5 R=minimal V=low | Token 成本最低 |
| 研究分析 | GPT-5 R=high V=high | 信息最完整 |

### 8.4 數據質量警告

- 約 30% 文章的 `Stock_symbol` 與實際主題不完全對應
- 使用傳統摘要時此問題會被放大
- 建議：評分前驗證 Article_title 與 Stock_symbol 相關性

---

## 9. 評分輸入源分析（Title vs Article vs Summary）

*基於 10 個樣本的深度橫向比較*

### 9.1 Title 信息密度分析

| 缺失信息類型 | 比例 | 影響 |
|-------------|------|------|
| 具體數字 (%, $) | 100% | 無法判斷幅度 |
| 業績動詞 (beat/miss) | 80% | 無法判斷方向 |
| Stock Symbol | 70% | 可能評錯股票 |
| 可操作信息 | 80% | 評分信息不足 |

**結論**: Title 單獨作為評分輸入**不可靠**

### 9.2 Stock Symbol Mismatch 問題

**嚴重發現**: 抽樣中高比例文章的 `Stock_symbol` 與實際主題不符

| 樣本 | 標記 Symbol | 實際主題 | Title |
|------|------------|---------|-------|
| 1 | AMAT | QQQ ETF | "Invesco QQQ Experiences Big Outflow" |
| 4 | PAYX | APTV | "Here's Why Investors Should Retain Aptiv (APTV)" |
| 6 | ASML | DHR | "Danaher Corporation (DHR) Ex-Dividend Date..." |
| 9 | TXN | Apple 供應鏈 | "5 Apple Supplier Stocks to Pick..." |
| 10 | WBA | Lyft/CVS | "Lyft, CVS Health partner..." |

**問題根源**:
- Roundup 類文章被拆分成多個 stock 記錄
- 同一文章內提及多個股票，每個都產生記錄
- 文末推薦股票也被標記為相關

### 9.3 各輸入源比較

```
┌─────────────────┬──────────────────────────┬──────────────────────────────┐
│ 輸入類型        │ 優點                     │ 缺點                          │
├─────────────────┼──────────────────────────┼──────────────────────────────┤
│ Article_title   │ • Token 成本最低         │ • 80%+ 信息不足               │
│                 │ • 無噪音                  │ • 不含具體數據                │
│                 │                          │ • 70% 不含 symbol             │
├─────────────────┼──────────────────────────┼──────────────────────────────┤
│ Article (原文)  │ • 信息最完整             │ • Token 成本極高              │
│                 │                          │ • 含廣告和噪音                │
│                 │                          │ • 需要模型自行過濾            │
├─────────────────┼──────────────────────────┼──────────────────────────────┤
│ Lsa_summary     │ • 成本中等               │ • 質量不穩定                  │
│                 │                          │ • 可能摘錄錯誤段落            │
│                 │                          │ • 完全無法識別 mismatch       │
├─────────────────┼──────────────────────────┼──────────────────────────────┤
│ O3/GPT-5        │ • 信息密度高             │ • 需要預生成                  │
│ Summary         │ • 過濾噪音               │ • 總成本 = 生成 + 評分        │
│                 │ • 60% 含比較分析         │                              │
│                 │ • 40% 含風險提示         │                              │
│                 │ • 質量穩定               │                              │
└─────────────────┴──────────────────────────┴──────────────────────────────┘
```

### 9.4 評分策略建議

**策略 A: 成本優先（大規模處理）**
```
1. Title 評分
2. 檢查 Title 是否含 Stock_symbol
3. 若不含 → 升級至 Summary 評分
4. 標記低信心記錄供後續審核
```

**策略 B: 質量優先（研究/回測）**
```
1. 直接使用 O3/GPT-5 Summary
2. 最穩定的評分結果
3. 適合策略開發和驗證
```

**策略 C: 混合驗證（高價值場景）**
```
1. Title 評分 + Summary 評分
2. 比較兩者差異
3. 差異 > 2 分 → 人工審核
4. 取加權平均或專家判斷
```

### 9.5 對 Score A/B Comparison 的啟示

進行分數比較時必須注意：

1. **輸入源控制**: 同一篇文章在不同評分 run 中可能使用不同輸入
   - 有的用 Title，有的用 Lsa_summary，有的用 o3_summary
   - **必須標記並控制此變因**

2. **Symbol Mismatch 過濾**:
   - 對比分數前應驗證 symbol 與 title 相關性
   - 不相關記錄可能產生無意義的分數

3. **評分一致性檢驗**:
   - 同文章不同 summary 的評分差異
   - 應小於評分模型本身的不確定性



---


*Report generated by ab_summary_comparison.py (comprehensive mode)*