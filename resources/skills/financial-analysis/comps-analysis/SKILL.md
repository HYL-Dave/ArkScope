---
name: comps_analysis
description: Build comparable company analyses with valuation multiples
trigger: comps|comparable|peer comparison|valuation comparison|relative valuation
required_params: [ticker]
aliases: [comps, comp]
category: financial-analysis
data_sources:
  required: [get_fundamentals_analysis, get_detailed_financials]
  optional: [tavily_search, get_sec_filings, get_peer_comparison]
output: report
---

# Comparable Company Analysis for {ticker}

## Objective

Build a rigorous comparable company analysis for {ticker}, identifying appropriate peers
and comparing valuation multiples to determine relative value.

## Data Source Priority

1. **get_detailed_financials** — SEC EDGAR fundamentals (EV/EBITDA, EV/Revenue, PEG, ROIC, margins)
2. **get_fundamentals_analysis** — IBKR snapshot (P/E, P/B, P/S, market cap, real-time)
3. **get_peer_comparison** — Pre-built peer group with comparative metrics
4. **get_sec_filings** — Recent 10-K/10-Q for segment data and guidance
5. **tavily_search** — Industry reports, recent analyst notes on peer group

## Workflow

### Step 1: Identify Peer Group
- Start with get_peer_comparison for {ticker} to get pre-built peer list
- Validate peers by checking:
  - Similar market cap range (0.5x to 2x)
  - Same industry/sub-industry
  - Similar business model (subscription vs transactional, B2B vs B2C)
  - Similar growth profile
- Target 4-8 peers (fewer is better than irrelevant peers)

### Step 2: Gather Financial Data
- For {ticker} AND each peer, collect:
  - Revenue, EBITDA, net income (TTM and forward estimates if available)
  - Market cap, enterprise value
  - Key ratios: EV/EBITDA, EV/Revenue, P/E, PEG
  - Growth rates: revenue growth YoY, earnings growth
  - Profitability: gross margin, EBITDA margin, net margin
  - Returns: ROE, ROIC

### Step 3: Build Comparison Table
- Use execute_python_analysis to build a structured comparison matrix
- Include median and mean for each metric across the peer group
- Flag outliers (>2 standard deviations from median)

### Step 4: Valuation Assessment
- Compare {ticker}'s multiples to peer median:
  - **Premium justified if**: Higher growth, better margins, stronger moat
  - **Discount warranted if**: Lower growth, weaker margins, higher risk
- Calculate implied value using peer median multiples applied to {ticker}'s financials
- Provide a valuation range (low/mid/high) based on different multiples

## Quality Checks

- [ ] Peer group has 4+ companies in the same sector
- [ ] All multiples are calculated on comparable basis (TTM or NTM, not mixed)
- [ ] Outliers are flagged and explained (not silently averaged in)
- [ ] Growth rates are normalized for one-time events
- [ ] Cross-check: Does the implied valuation make directional sense?

## Industry-Specific Guidance

### SaaS / Technology
- Prioritize: EV/Revenue, Rule of 40, NRR, ARR growth
- De-prioritize: P/E (many unprofitable), EV/EBITDA (SBC distortion)

### Manufacturing / Industrials
- Prioritize: EV/EBITDA, P/E, asset turnover, capex intensity
- Watch for: Cyclical adjustments, normalize earnings over cycle

### Financial Services
- Prioritize: P/B, P/E, ROE, efficiency ratio
- Note: EV-based multiples often inappropriate (debt is operating asset)

## Required Output

1. **Peer group table**: Name, ticker, market cap, key business description
2. **Valuation multiples matrix**: All peers with EV/EBITDA, EV/Revenue, P/E, PEG
3. **Statistical summary**: Median, mean, high, low for each multiple
4. **{ticker} positioning**: Premium/discount to median with justification
5. **Implied valuation range**: Low/mid/high with methodology
6. **Key risks to the comparison**: Why peers may not be truly comparable

AFTER ANALYSIS: Save as a research report using save_report() with report_type="comps_analysis".
