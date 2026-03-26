---
name: full_analysis
description: Comprehensive single-ticker entry analysis
trigger: full analysis|entry analysis|comprehensive analysis|analyze ticker|deep dive
required_params: [ticker]
aliases: [analyze, fa]
category: builtin
data_sources:
  required: [get_ticker_news, get_price_change, get_fundamentals_analysis, get_analyst_consensus]
  optional: [get_iv_analysis, get_sec_filings, get_insider_trades, tavily_search, execute_python_analysis]
output: report
---

Perform a comprehensive entry analysis for {ticker}.

GOAL: Determine whether {ticker} presents a compelling entry opportunity right now.

MINIMUM DATA SOURCES (use all that are relevant):
- News sentiment and recent headlines
- Price action across multiple timeframes (7d, 30d, 90d)
- Fundamental metrics (P/E, ROE, margins, revenue growth)
- Analyst consensus (recommendations, price targets, earnings surprise history)
- IV/options data (IV rank, VRP, unusual activity)
- SEC filings and insider trades (Form 4)
- Web search for recent catalysts not captured in local data

QUANTITATIVE ANALYSIS:
- Use execute_python_analysis for any calculations beyond simple lookups (Sharpe ratio, z-score of recent moves, correlation with SPY, drawdown analysis)

REQUIRED OUTPUT:
1. Bull case — specific reasons and supporting data
2. Bear case — specific reasons and supporting data
3. Adversarial check — actively seek evidence against your thesis
4. Key risk factors
5. Data gaps — what information is missing
6. Confidence rating (High/Medium/Low) with explanation
7. Actionable conclusion

AFTER ANALYSIS: Save as a research report using save_report() with report_type="entry_analysis".
