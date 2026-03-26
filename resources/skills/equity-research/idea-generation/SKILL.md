---
name: idea_generation
description: Systematic stock screening and idea generation
trigger: idea generation|stock screen|find opportunities|stock ideas|generate ideas
required_params: []
aliases: [ideas, screen]
category: equity-research
auto_apply: false
data_sources:
  required: [get_sector_performance, get_watchlist_overview]
  optional: [tavily_search, get_sa_alpha_picks, get_ticker_news, get_price_change]
output: report
---

# Investment Idea Generation

## Objective

Systematically screen for investment opportunities using a multi-factor approach,
combining quantitative screening with qualitative analysis.

## Data Source Priority

1. **get_sector_performance** — Identify sectors with momentum or mean-reversion potential
2. **get_watchlist_overview** — Current holdings context to avoid overlap
3. **get_sa_alpha_picks** — Seeking Alpha curated picks with ratings
4. **tavily_search** — Thematic trends, emerging sectors, contrarian opportunities
5. **get_ticker_news** — Recent catalysts for screened candidates
6. **get_price_change** — Price momentum/value screening for candidates

## Workflow

### Step 1: Top-Down Screening
- Review sector performance across multiple timeframes
- Identify:
  - **Momentum sectors**: Strong relative strength, improving fundamentals
  - **Contrarian sectors**: Oversold with improving fundamentals
  - **Thematic plays**: Secular trends (AI, energy transition, reshoring, etc.)

### Step 2: Idea Sources
Scan multiple sources for candidates:

**Quantitative Screens**:
- Sector leaders with pullbacks (relative strength + short-term weakness)
- Earnings momentum (positive revisions + recent beat)
- Value with catalyst (cheap multiples + upcoming event)

**Qualitative Sources**:
- Seeking Alpha top picks (get_sa_alpha_picks)
- Recent analyst upgrades or initiations
- Insider buying clusters
- Industry conference highlights

### Step 3: Quick Filter
For each candidate, quick-check:
- Market cap > $2B (liquidity)
- Average volume > 500K (tradeable)
- Not already in watchlist (avoid doubling)
- No imminent binary event unless that's the thesis

### Step 4: Rank and Prioritize
Score candidates on:
- **Conviction**: How strong is the thesis? (1-5)
- **Timeliness**: Is there an upcoming catalyst? (1-5)
- **Risk/Reward**: Asymmetry of potential outcomes (1-5)
- **Data availability**: Can we do deep research? (1-5)

Present top 5-10 ideas, ranked by composite score.

## Required Output

1. **Market context**: Current regime (risk-on/risk-off), sector leadership
2. **Screening summary**: How many candidates from each source/method
3. **Top ideas table**: Ticker, sector, thesis (1 line), score, key catalyst
4. **Deep dive on top 3**: For the highest-ranked ideas, provide:
   - Brief company description
   - Investment thesis (2-3 sentences)
   - Key catalyst and timeline
   - Primary risk
   - Suggested next step (full_analysis, earnings_prep, etc.)
5. **Watchlist additions**: Which tickers should be added to monitoring

AFTER ANALYSIS: Save as a research report using save_report() with report_type="idea_generation".
