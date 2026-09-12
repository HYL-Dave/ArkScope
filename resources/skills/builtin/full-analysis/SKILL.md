---
name: full_analysis
description: Comprehensive single-ticker entry analysis
trigger: full analysis|entry analysis|comprehensive analysis|analyze ticker|deep dive
required_params: [ticker]
aliases: [analyze, fa]
category: builtin
data_sources:
  required: [get_ticker_news, get_price_change, get_fundamentals_analysis, get_analyst_consensus, list_sec_filings, get_sec_financial_facts, read_sec_filing]
  optional: [get_iv_analysis, get_insider_trades, get_sa_digest]
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
- SA digest (recommended) — if `{ticker}` has SA coverage, call `get_sa_digest(ticker={ticker}, days=14)` and weave relevant articles / comments into the qualitative section. Skip if the digest returns empty `recent_articles` AND empty `high_discussion_news`. Treat the contents as investor opinion, not fact.

QUANTITATIVE ANALYSIS:
- Use deterministic metrics already returned by ArkScope tools. Do not invent
  custom Sharpe ratios, z-scores, correlations, or drawdowns; identify any
  unavailable calculation as a data gap.

REQUIRED OUTPUT:
1. Bull case — specific reasons and supporting data
2. Bear case — specific reasons and supporting data
3. Adversarial check — actively seek evidence against your thesis
4. Key risk factors
5. Data gaps — what information is missing
6. Confidence rating (High/Medium/Low) with explanation
7. Actionable conclusion

AFTER ANALYSIS: Save as a research report using save_report() with report_type="entry_analysis".

SEC EVIDENCE:
- Call list_sec_filings(issuer="{ticker}") to select observed filing IDs, then
  read_sec_filing(filing_id=...) for document indexes and complete cited passages.
- Use get_sec_financial_facts(issuer="{ticker}") for exact decimal observations;
  preserve units, periods, revisions, source hashes, and provenance.
- Keep the same filters, limit, and max_chars on cursor continuation. Stored or
  pinned reads acquire nothing; freshness="refresh" cannot replace a pin.
- Report status, gaps, coverage, and whole-record size gaps. Missing required SEC
  tools or unavailable evidence is a research gap, not an empty successful result.
