---
name: dcf_model
description: Discounted cash flow valuation model with scenario analysis
trigger: dcf|discounted cash flow|intrinsic value|fair value model
required_params: [ticker]
aliases: [dcf, valuation]
category: financial-analysis
data_sources:
  required: [get_detailed_financials, get_fundamentals_analysis, calculate_compound_growth, calculate_dcf, calculate_weighted_scenarios, list_sec_filings, get_sec_financial_facts, read_sec_filing]
  optional: [get_analyst_consensus]
output: report
---

# DCF Valuation Model for {ticker}

## Objective

Build a discounted cash flow model for {ticker} with base, bull, and bear scenarios
to estimate intrinsic value and margin of safety.

## Data Source Priority

1. **get_detailed_financials** — Historical financials from SEC EDGAR (revenue, FCF, margins, ROIC)
2. **get_fundamentals_analysis** — Current market data (market cap, shares outstanding)
3. **calculate_compound_growth** — Auditable historical growth from cited endpoints
4. **calculate_dcf** — Discount projections and bridge enterprise value to equity value
5. **calculate_weighted_scenarios** — Combine explicit scenario values and probabilities
6. **list_sec_filings + read_sec_filing** — Management guidance, segment data, capex plans
7. **get_analyst_consensus** — Consensus estimates for revenue/earnings growth

## Workflow

### Step 1: Historical Analysis
- Gather 3-5 years of historical data:
  - Revenue, gross profit, EBITDA, operating income
  - Capital expenditures, depreciation & amortization
  - Working capital changes
  - Free cash flow (FCF = Operating CF - Capex)
- Call `calculate_compound_growth` for each historical growth rate used
- Identify trends and inflection points

### Step 2: Build Assumptions
Use only values and deterministic metrics returned by ArkScope tools. Show the
formula and cited inputs for each projection. If a custom calculation cannot be
verified with available tool output, mark it as a data gap instead of inventing
a precise result.

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
- Call `calculate_dcf` separately for each scenario; cite its returned inputs and formulas

### Step 4: Scenario Analysis
- **Base case**: Consensus-aligned, most likely outcome
- **Bull case**: Higher growth, margin expansion, successful execution
- **Bear case**: Growth deceleration, margin compression, competitive pressure
- Weight: 50% base, 25% bull, 25% bear (or adjust based on conviction)
- Call `calculate_weighted_scenarios` for the final weighted fair value

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

SEC EVIDENCE:
- Call list_sec_filings(issuer="{ticker}") to select observed filing IDs, then
  read_sec_filing(filing_id=...) for document indexes and complete cited passages.
- Use get_sec_financial_facts(issuer="{ticker}") for exact decimal observations;
  preserve units, periods, revisions, source hashes, and provenance.
- Keep the same filters, limit, and max_chars on cursor continuation. Stored or
  pinned reads acquire nothing; freshness="refresh" cannot replace a pin.
- Report status, gaps, coverage, and whole-record size gaps. Missing required SEC
  tools or unavailable evidence is a research gap, not an empty successful result.
