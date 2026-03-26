---
name: portfolio_scan
description: Watchlist-wide screening with drill-down on movers
trigger: portfolio scan|watchlist scan|morning scan|market scan|screen watchlist
required_params: []
aliases: [scan, ps]
category: builtin
auto_apply: false
data_sources:
  required: [get_watchlist_overview, get_morning_brief, get_price_change]
  optional: [get_ticker_news, get_fundamentals_analysis, get_analyst_consensus, get_iv_analysis]
output: report
---

Perform a comprehensive scan of the current watchlist.

GOAL: Identify the most actionable opportunities and risks across all positions.

MINIMUM DATA SOURCES:
- Watchlist overview (current positions and status)
- Morning brief (market context)
- Price changes for each ticker (7d and 30d)
- News sentiment for tickers with significant moves

ANALYSIS APPROACH:
- Screen all tickers for significant movers (price, sentiment, volume)
- Rank by opportunity/risk
- For the top 3 most actionable tickers, perform deeper analysis (fundamentals, analyst consensus, IV if available)

REQUIRED OUTPUT:
1. Market context summary
2. Watchlist status table (ticker, price change, sentiment, key event)
3. Top 3 opportunities with brief analysis
4. Risk alerts (any position with concerning signals)
5. Recommended actions

AFTER ANALYSIS: Save as a research report using save_report() with report_type="morning_brief".
