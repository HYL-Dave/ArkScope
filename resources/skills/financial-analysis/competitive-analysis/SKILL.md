---
name: competitive_analysis
description: Competitive landscape and moat assessment
trigger: competitive analysis|competitive landscape|moat assessment|competitive position
required_params: [ticker]
aliases: [competitive, moat]
category: financial-analysis
data_sources:
  required: [get_fundamentals_analysis, tavily_search]
  optional: [get_detailed_financials, get_peer_comparison, get_sec_filings]
output: report
---

# Competitive Analysis for {ticker}

## Objective

Assess {ticker}'s competitive position, identify key competitors, evaluate the
durability of competitive advantages (moat), and identify emerging threats.

## Data Source Priority

1. **tavily_search** — Industry reports, competitor news, market share data
2. **get_fundamentals_analysis** — Financial metrics for comparison
3. **get_peer_comparison** — Quantitative peer benchmarking
4. **get_detailed_financials** — Margin trends, R&D intensity, SBC
5. **get_sec_filings** — Management commentary on competition, risk factors

## Workflow

### Step 1: Industry Mapping
- Identify {ticker}'s primary market(s) and addressable market size
- Map the competitive landscape:
  - Direct competitors (same product/service)
  - Indirect competitors (substitute products)
  - Potential entrants (adjacent companies expanding)
- Search for recent industry reports and market share data

### Step 2: Moat Assessment (Porter's Five Forces + Buffett Framework)
Evaluate each moat source:

**Switching Costs**: How painful is it for customers to leave?
- Contract lengths, integration depth, data lock-in
- Evidence: Net revenue retention, churn rates

**Network Effects**: Does the product get better with more users?
- Type: Direct (social), indirect (marketplace), data
- Evidence: User growth correlation with engagement

**Cost Advantages**: Can {ticker} produce at lower cost?
- Economies of scale, proprietary technology, geographic advantages
- Evidence: Gross margin vs peers, operating leverage

**Intangible Assets**: Patents, brands, regulatory licenses?
- Patent portfolio, brand recognition, regulatory barriers
- Evidence: R&D spend, brand surveys, regulatory filings

**Efficient Scale**: Is the market too small for another entrant?
- Natural monopoly characteristics, high fixed costs
- Evidence: Market concentration, entry barriers

### Step 3: Competitor Deep Dive
For top 3-5 competitors:
- Compare financial metrics (growth, margins, returns)
- Identify competitive advantages and weaknesses
- Recent strategic moves (acquisitions, product launches, pivots)
- Relative valuation

### Step 4: Threat Assessment
- Technological disruption risk
- Regulatory changes
- New entrants from adjacent markets
- Customer concentration risk
- Supply chain dependencies

## Required Output

1. **Industry map**: Market structure, key players, market share estimates
2. **Moat scorecard**: Rate each moat source (Strong/Moderate/Weak/None)
3. **Competitor comparison table**: Key metrics across top competitors
4. **SWOT summary**: Strengths, weaknesses, opportunities, threats
5. **Moat durability assessment**: Is the moat widening, stable, or narrowing?
6. **Key competitive risks**: What could erode {ticker}'s position
7. **Investment implications**: How competitive position affects valuation

AFTER ANALYSIS: Save as a research report using save_report() with report_type="competitive_analysis".
