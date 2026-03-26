---
name: earnings_analysis
description: Post-earnings financial analysis and quality assessment
trigger: earnings analysis|earnings quality|post earnings|quarterly results
required_params: [ticker]
aliases: [earnings_review, er]
category: equity-research
data_sources:
  required: [get_detailed_financials, get_analyst_consensus]
  optional: [get_sec_filings, get_earnings_impact, tavily_search, get_ticker_news]
output: report
---

# Earnings Analysis for {ticker}

## Objective

Analyze {ticker}'s most recent earnings report to assess financial quality,
identify trends, and evaluate forward guidance against expectations.

## Data Source Priority

1. **get_detailed_financials** — Comprehensive financial metrics from SEC EDGAR
2. **get_analyst_consensus** — Consensus estimates and earnings surprise history
3. **get_earnings_impact** — Price reaction and historical earnings patterns
4. **get_sec_filings** — Actual 10-Q/10-K for detailed segment data
5. **get_ticker_news** — Post-earnings analyst commentary
6. **tavily_search** — Earnings call transcript highlights, management commentary

## Workflow

### Step 1: Beat/Miss Assessment
- Compare actual results vs consensus:
  - Revenue: beat/miss and magnitude
  - EPS: beat/miss and magnitude
  - Key segment metrics (if applicable)
- Historical context: Is this beat/miss pattern consistent?

### Step 2: Financial Quality Assessment
Use execute_python_analysis for calculations:

**Revenue Quality**:
- Organic vs acquisition-driven growth
- One-time items vs recurring revenue
- Geographic/segment mix shifts
- Revenue recognition timing

**Earnings Quality**:
- Operating earnings vs adjusted earnings gap
- Stock-based compensation impact
- Tax rate normalization
- Cash EPS vs reported EPS

**Cash Flow Quality**:
- FCF conversion ratio (FCF/Net Income)
- Working capital changes (are they sustainable?)
- Capex as % of revenue (increasing or decreasing?)
- Days sales outstanding trend

### Step 3: Forward Guidance Analysis
- Management guidance vs prior consensus
- Guidance raise/lower/maintain pattern over time
- Qualitative tone (confident, cautious, hedging)
- Key assumptions embedded in guidance

### Step 4: Market Reaction Context
- Immediate post-earnings price move
- How does the move compare to implied move from options?
- Revision activity: Are analysts raising or lowering estimates?
- Is the market rewarding/punishing the right things?

## Quality Checks

- [ ] Compared actual vs consensus AND vs prior quarter AND vs year-ago
- [ ] Identified any one-time items that distort the headline numbers
- [ ] Checked FCF vs earnings divergence
- [ ] Assessed whether guidance change is meaningful or just sandbagging
- [ ] Cross-referenced management commentary with the numbers

## Required Output

1. **Earnings scorecard**: Revenue, EPS, key metrics — actual vs estimate vs prior
2. **Quality assessment**: Revenue quality, earnings quality, cash flow quality ratings
3. **Key trends**: 3-5 most important trends from this report
4. **Guidance summary**: Forward guidance vs consensus with magnitude
5. **Analyst reaction**: Post-earnings estimate revisions and price target changes
6. **Investment implications**: Does this report change the thesis? How?

AFTER ANALYSIS: Save as a research report using save_report() with report_type="earnings_analysis".
