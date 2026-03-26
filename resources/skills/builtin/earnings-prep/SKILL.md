---
name: earnings_prep
description: Pre-earnings research and risk assessment
trigger: earnings prep|pre-earnings|earnings risk|earnings report preparation
required_params: [ticker]
aliases: [earnings, ep]
category: builtin
data_sources:
  required: [get_analyst_consensus, get_iv_analysis, get_earnings_impact]
  optional: [get_sec_filings, get_insider_trades, tavily_search, execute_python_analysis]
output: report
---

Prepare a pre-earnings analysis for {ticker}.

GOAL: Assess the risk/reward of holding {ticker} through its upcoming earnings report.

MINIMUM DATA SOURCES:
- Analyst consensus (EPS estimates, recommendation distribution, earnings date)
- Historical earnings surprise pattern (beat/miss history)
- IV analysis (current IV rank vs historical, implied move)
- SEC filings (recent 10-K/10-Q for guidance clues)
- Insider trades (Form 4 — any unusual pre-earnings activity)
- Web search for recent analyst commentary and guidance previews

QUANTITATIVE ANALYSIS:
- Compare implied move (from IV) with historical actual moves around earnings
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
