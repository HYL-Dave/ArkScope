---
name: catalyst_calendar
description: Upcoming catalysts and event-driven analysis
trigger: catalyst calendar|upcoming catalysts|event calendar|catalyst timeline
required_params: [ticker]
aliases: [catalysts, cat]
category: equity-research
data_sources:
  required: [get_analyst_consensus, tavily_search]
  optional: [get_sec_filings, get_ticker_news, get_iv_analysis, get_earnings_impact]
output: report
---

# Catalyst Calendar for {ticker}

## Objective

Identify and analyze upcoming catalysts for {ticker} over the next 1-6 months,
assess their potential impact, and provide a timeline for monitoring.

## Data Source Priority

1. **get_analyst_consensus** — Earnings dates, estimate revisions, price target changes
2. **tavily_search** — Product launches, FDA decisions, conferences, regulatory events
3. **get_ticker_news** — Recent announcements and upcoming events
4. **get_sec_filings** — Scheduled filings, shareholder meetings, proxy events
5. **get_iv_analysis** — Options market pricing of upcoming events
6. **get_earnings_impact** — Historical earnings reaction patterns

## Workflow

### Step 1: Event Discovery
Search for upcoming catalysts across categories:

**Scheduled Events**:
- Earnings report date (next and following quarter)
- Ex-dividend dates
- Annual shareholder meeting
- Scheduled SEC filings (10-K, 10-Q deadlines)
- Index reconstitution dates (if applicable)

**Company-Specific**:
- Product launches or updates
- Analyst/investor day
- Conference presentations
- Clinical trial readouts (biotech)
- Regulatory decisions (FDA, FCC, etc.)
- M&A transaction closings
- Debt maturity/refinancing

**Macro/Industry**:
- Fed meetings and rate decisions
- Industry conferences
- Regulatory changes affecting the sector
- Competitor earnings (read-through potential)

### Step 2: Impact Assessment
For each catalyst, evaluate:
- **Probability**: Likelihood of occurring as scheduled
- **Magnitude**: Potential price impact (High/Medium/Low)
- **Direction**: Positive, negative, or binary (could go either way)
- **Market expectation**: Is this already priced in?

### Step 3: Options Market Check
- Current IV rank — is the market pricing in event risk?
- Term structure — is there an IV bump around catalyst dates?
- Skew — is the market pricing more downside or upside?

### Step 4: Build Timeline
Create a calendar view sorted by date with impact ratings.

## Required Output

1. **Catalyst timeline table**: Date, event, category, probability, expected impact
2. **Top 3 catalysts**: Deep dive on the highest-impact upcoming events
3. **Options positioning**: What the options market implies about catalyst pricing
4. **Risk events**: Catalysts that could move the stock significantly against you
5. **Monitoring checklist**: What to watch for and when to re-evaluate
6. **Strategic implications**: How to position around the catalyst calendar

AFTER ANALYSIS: Save as a research report using save_report() with report_type="catalyst_calendar".
