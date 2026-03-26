---
name: dcf_model
description: Discounted cash flow valuation model with scenario analysis
trigger: dcf|discounted cash flow|intrinsic value|fair value model
required_params: [ticker]
aliases: [dcf, valuation]
category: financial-analysis
data_sources:
  required: [get_detailed_financials, get_fundamentals_analysis]
  optional: [get_sec_filings, tavily_search, get_analyst_consensus]
output: report
---

# DCF Valuation Model for {ticker}

## Objective

Build a discounted cash flow model for {ticker} with base, bull, and bear scenarios
to estimate intrinsic value and margin of safety.

## Data Source Priority

1. **get_detailed_financials** — Historical financials from SEC EDGAR (revenue, FCF, margins, ROIC)
2. **get_fundamentals_analysis** — Current market data (market cap, shares outstanding)
3. **get_sec_filings** — Management guidance, segment data, capex plans
4. **get_analyst_consensus** — Consensus estimates for revenue/earnings growth
5. **tavily_search** — Industry growth rates, WACC benchmarks, recent analyst models

## Workflow

### Step 1: Historical Analysis
- Gather 3-5 years of historical data:
  - Revenue, gross profit, EBITDA, operating income
  - Capital expenditures, depreciation & amortization
  - Working capital changes
  - Free cash flow (FCF = Operating CF - Capex)
- Calculate historical growth rates and margins
- Identify trends and inflection points

### Step 2: Build Assumptions
Use execute_python_analysis for all calculations:

**Revenue Growth**:
- Historical CAGR as baseline
- Analyst consensus as cross-check
- Industry growth rate as ceiling/floor
- Base/bull/bear scenarios

**Margin Assumptions**:
- Project EBITDA margin and FCF margin
- Consider operating leverage and scale effects
- Industry peer margins as reference

**WACC Estimation**:
- Risk-free rate: 10Y Treasury yield
- Equity risk premium: 5-6% (standard)
- Beta: From peer group or historical
- Cost of debt: From SEC filings or estimate from credit rating
- Target capital structure from current or peer median

### Step 3: Project Cash Flows
- Forecast FCF for 5-10 years (depending on visibility)
- Terminal value using perpetuity growth method (2-3% terminal growth)
- Cross-check terminal value as % of total (should be 50-75%)

### Step 4: Scenario Analysis
- **Base case**: Consensus-aligned, most likely outcome
- **Bull case**: Higher growth, margin expansion, successful execution
- **Bear case**: Growth deceleration, margin compression, competitive pressure
- Weight: 50% base, 25% bull, 25% bear (or adjust based on conviction)

## Quality Checks

- [ ] Terminal value is 50-75% of enterprise value (not >85%)
- [ ] Terminal growth rate < nominal GDP growth (2-3%)
- [ ] WACC is reasonable (typically 7-12% for equities)
- [ ] Implied exit multiple from terminal value makes sense
- [ ] FCF margins converge to sustainable level, not infinitely expanding
- [ ] Sensitivity table shows impact of WACC and terminal growth changes

## Required Output

1. **Key assumptions table**: Growth rates, margins, WACC components by scenario
2. **5-10 year FCF projection**: Revenue → EBITDA → FCF bridge
3. **DCF summary**: PV of FCFs + PV of terminal value = Enterprise value
4. **Per-share value**: Enterprise value → equity value → per share, by scenario
5. **Weighted fair value**: Probability-weighted across scenarios
6. **Sensitivity table**: Fair value matrix with WACC vs terminal growth
7. **Margin of safety**: Current price vs weighted fair value
8. **Key risks**: What breaks the model

AFTER ANALYSIS: Save as a research report using save_report() with report_type="dcf_valuation".
