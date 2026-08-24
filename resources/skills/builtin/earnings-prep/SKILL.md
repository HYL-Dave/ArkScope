---
name: earnings_prep
description: Pre-earnings research and risk assessment
trigger: earnings prep|pre-earnings|earnings risk|earnings report preparation
required_params: [ticker]
aliases: [earnings, ep]
category: builtin
data_sources:
  required: [get_analyst_consensus, get_option_chain, get_earnings_impact, get_sa_digest]
  optional: [get_sec_filings, get_insider_trades, execute_python_analysis]
output: report
---

Prepare a pre-earnings analysis for {ticker}.

GOAL: Assess the risk/reward of holding {ticker} through its upcoming earnings report.

MINIMUM DATA SOURCES:
- Analyst consensus (EPS estimates, recommendation distribution, earnings date)
- Historical earnings surprise pattern (beat/miss history)
- Option-chain analysis (ATM implied volatility, term structure, and estimated implied move)
- SEC filings (recent 10-K/10-Q for guidance clues)
- Insider trades (Form 4 — any unusual pre-earnings activity)
- SA evidence pack — you **must** call `get_sa_digest(ticker={ticker}, days=30, max_articles=8, max_news=8, max_comments=12)` to surface SA articles, high-discussion market-news, and high-value investor comments from the last 30 days. Treat this as **investor-opinion evidence**, not fact-verified data; cite specific articles / commenters with their dates so the user can audit. needs_verification rows in the digest are claims that pair concrete information with hedging language — flag, don't filter.

QUANTITATIVE ANALYSIS:
- Estimate the implied move from the option chain and compare it with historical actual moves around earnings
- Assess whether options are pricing in too much or too little risk
- Calculate risk/reward scenarios (beat, meet, miss)

REQUIRED OUTPUT:
1. Earnings date and consensus estimates
2. Historical surprise pattern (last 4-8 quarters)
3. Expected move vs IV implied move
4. Pre-earnings insider activity
5. Key metrics to watch
6. Risk assessment (High/Medium/Low)
7. Strategy recommendation (hold/trim/hedge/avoid)

AFTER ANALYSIS: Save as a research report using save_report() with report_type="earnings_review".
