"""
OpenAI Agents SDK tool wrappers.

Wraps the 18 tool functions with @function_tool decorator for use with
the OpenAI Agents SDK.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    from agents import function_tool, RunContextWrapper
except ImportError:
    # Fallback for when openai-agents is not installed
    def function_tool(fn):
        return fn
    RunContextWrapper = Any

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)


def _serialize_result(result: Any, tool_name: str = "") -> str:
    """Serialize result to JSON string for LLM consumption.

    Wraps output in <tool_output> boundary tags when tool_name is provided
    to prevent prompt injection from external data sources.
    """
    if hasattr(result, "model_dump"):
        content = json.dumps(result.model_dump(), default=str)
    elif isinstance(result, list) and result and hasattr(result[0], "model_dump"):
        content = json.dumps([r.model_dump() for r in result], default=str)
    elif isinstance(result, dict):
        content = json.dumps(result, default=str)
    else:
        content = str(result)

    if tool_name:
        from src.agents.shared.security import wrap_tool_result
        return wrap_tool_result(content, tool_name)
    return content


def create_openai_tools(dal: "DataAccessLayer") -> List:
    """
    Create OpenAI function tools that are bound to a DataAccessLayer instance.

    Returns a list of @function_tool decorated functions ready for Agent.tools.
    """
    from src.tools.news_tools import (
        get_ticker_news,
        get_news_sentiment_summary,
        search_news_by_keyword,
        get_news_brief,
        search_news_advanced,
    )
    from src.tools.price_tools import (
        get_ticker_prices,
        get_price_change,
        get_sector_performance,
    )
    from src.tools.options_tools import (
        get_iv_analysis,
        get_iv_history_data,
        scan_mispricing,
        calculate_greeks,
    )
    from src.tools.option_chain_tools import get_option_chain as _get_option_chain
    from src.tools.iv_skew_tools import get_iv_skew_analysis as _get_iv_skew_analysis
    from src.tools.portfolio_tools import get_portfolio_analysis as _get_portfolio_analysis
    from src.tools.earnings_tools import get_earnings_impact as _get_earnings_impact
    from src.tools.signal_tools import (
        detect_anomalies,
        detect_event_chains,
        synthesize_signal,
    )
    from src.tools.analysis_tools import (
        get_fundamentals_analysis,
        get_detailed_financials,
        get_peer_comparison,
        get_watchlist_overview,
        get_morning_brief,
    )
    from src.tools.sec_tools import (
        get_sec_filings,
        get_insider_trades,
    )
    from src.tools.code_executor import execute_python_code
    from src.tools.analyst_tools import get_analyst_consensus
    from src.tools.report_tools import (
        save_report as _save_report,
        list_reports as _list_reports,
        get_report as _get_report,
    )
    from src.tools.memory_tools import (
        save_memory as _save_memory,
        recall_memories as _recall_memories,
        list_memories as _list_memories,
        delete_memory as _delete_memory,
    )
    from src.tools.monitor_tools import scan_alerts as _scan_alerts
    from src.tools.freshness import check_data_freshness as _check_data_freshness
    from src.tools.rl_tools import (
        get_rl_model_status as _get_rl_model_status,
        get_rl_prediction as _get_rl_prediction,
        get_rl_backtest_report as _get_rl_backtest_report,
    )

    # ================================================================
    # News Tools
    # ================================================================

    @function_tool
    def tool_get_ticker_news(
        ticker: str,
        days: int = 30,
        source: str = "auto",
        limit: int = 20,
    ) -> str:
        """Get recent news articles for a stock ticker. Returns up to `limit` most recent articles. The response includes `count` (total available) so you know if more exist.

        Args:
            ticker: Stock ticker symbol (e.g. NVDA, AMD)
            days: Lookback period in days (default: 30)
            source: Data source - auto, ibkr, or polygon (default: auto)
            limit: Max articles to return, 1-500 (default: 20)
        """
        result = get_ticker_news(dal, ticker, days=days, source=source, limit=limit)
        return _serialize_result(result, "get_ticker_news")

    @function_tool
    def tool_get_news_sentiment_summary(ticker: str, days: int = 7) -> str:
        """Get aggregated sentiment statistics for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 7)

        Returns mean sentiment, bullish/bearish ratio, and scored article count.
        """
        result = get_news_sentiment_summary(dal, ticker, days=days)
        return _serialize_result(result, "get_news_sentiment_summary")

    @function_tool
    def tool_search_news_by_keyword(
        keyword: str,
        days: int = 30,
        ticker: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """Search news articles by keyword using full-text search. Returns up to `limit` most recent matches.

        Args:
            keyword: Search keyword (supports multi-word)
            days: Lookback period in days (default: 30)
            ticker: Optionally filter by ticker
            limit: Max articles to return, 1-500 (default: 20)
        """
        result = search_news_by_keyword(dal, keyword, days=days, ticker=ticker, limit=limit)
        return _serialize_result(result, "search_news_by_keyword")

    # ================================================================
    # News Tools — Smart Data Retrieval
    # ================================================================

    @function_tool
    def tool_get_news_brief(
        tickers: Optional[List[str]] = None,
        days: int = 7,
    ) -> str:
        """Get a lightweight news overview for multiple tickers: article count, avg sentiment, avg risk, date range. Call this FIRST before get_ticker_news() to decide which tickers need detailed investigation. Very fast, minimal output.

        Args:
            tickers: List of ticker symbols (default: watchlist from config)
            days: Lookback period in days (default: 7)
        """
        result = get_news_brief(dal, tickers=tickers, days=days)
        return _serialize_result(result, "get_news_brief")

    @function_tool
    def tool_search_news_advanced(
        query: str = "",
        tickers: Optional[List[str]] = None,
        days: int = 30,
        scored_only: bool = False,
        min_sentiment: Optional[int] = None,
        max_risk: Optional[int] = None,
        limit: int = 20,
    ) -> str:
        """Advanced news search combining full-text search + multi-ticker + date range + score filters. Use for cross-ticker theme searches (e.g. 'tariff impact' across AI_CHIPS sector).

        Args:
            query: Full-text search query
            tickers: Filter by multiple tickers
            days: Lookback period in days (default: 30)
            scored_only: Only return scored articles (default: false)
            min_sentiment: Minimum sentiment score (1-5)
            max_risk: Maximum risk score (1-5)
            limit: Max articles to return (default: 20)
        """
        result = search_news_advanced(
            dal, query=query, tickers=tickers, days=days,
            scored_only=scored_only, min_sentiment=min_sentiment,
            max_risk=max_risk, limit=limit,
        )
        return _serialize_result(result, "search_news_advanced")

    # ================================================================
    # Price Tools
    # ================================================================

    @function_tool
    def tool_get_ticker_prices(
        ticker: str,
        interval: str = "15min",
        days: int = 30
    ) -> str:
        """Get OHLCV price bars for a stock ticker.

        Args:
            ticker: Stock ticker symbol
            interval: Bar interval - 15min, 1h, or 1d (default: 15min)
            days: Lookback period in days (default: 30)
        """
        result = get_ticker_prices(dal, ticker, interval=interval, days=days)
        return _serialize_result(result, "get_ticker_prices")

    @function_tool
    def tool_get_price_change(ticker: str, days: int = 7) -> str:
        """Calculate price change percentage and high/low range for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 7)

        Returns change_pct, period_high, period_low, and total_volume.
        """
        result = get_price_change(dal, ticker, days=days)
        return _serialize_result(result, "get_price_change")

    @function_tool
    def tool_get_sector_performance(sector: str, days: int = 7) -> str:
        """Calculate average performance of all tickers in a sector.

        Args:
            sector: Sector name (e.g. AI_CHIPS, FINTECH, EV, SPACE)
            days: Lookback period in days (default: 7)

        Returns avg_change_pct, best/worst ticker, and per-ticker details.
        """
        result = get_sector_performance(dal, sector, days=days)
        return _serialize_result(result, "get_sector_performance")

    # ================================================================
    # Options Tools
    # ================================================================

    @function_tool
    def tool_get_iv_analysis(ticker: str) -> str:
        """Full implied volatility analysis: IV rank, percentile, VRP, and trading signal.

        Args:
            ticker: Stock ticker symbol

        Returns current_iv, hv, vrp, iv_rank, iv_percentile, and trading signal.
        """
        result = get_iv_analysis(dal, ticker)
        return _serialize_result(result, "get_iv_analysis")

    @function_tool
    def tool_get_iv_history_data(ticker: str) -> str:
        """Get raw IV history data points (ATM IV, HV, VRP) for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns list of historical IV data points with dates.
        """
        result = get_iv_history_data(dal, ticker)
        return _serialize_result(result, "get_iv_history_data")

    @function_tool
    def tool_scan_mispricing(
        tickers: List[str],
        mispricing_threshold_pct: float = 10.0,
        min_confidence: str = "MEDIUM"
    ) -> str:
        """Scan for mispriced options comparing theoretical vs market prices.

        Args:
            tickers: List of ticker symbols to scan
            mispricing_threshold_pct: Minimum mispricing % to report (default: 10.0)
            min_confidence: Minimum confidence level - HIGH, MEDIUM, or LOW (default: MEDIUM)
        """
        result = scan_mispricing(
            dal, tickers,
            mispricing_threshold_pct=mispricing_threshold_pct,
            min_confidence=min_confidence
        )
        return _serialize_result(result, "scan_mispricing")

    @function_tool
    def tool_calculate_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = "C"
    ) -> str:
        """Calculate Black-Scholes Greeks for an option.

        Args:
            S: Spot price of the underlying
            K: Strike price
            T: Time to expiry in years (e.g. 0.25 for 3 months)
            r: Risk-free rate (e.g. 0.05 for 5%)
            sigma: Volatility (e.g. 0.30 for 30%)
            option_type: C for call, P for put (default: C)

        Returns delta, gamma, theta, vega, and rho.
        """
        result = calculate_greeks(S=S, K=K, T=T, r=r, sigma=sigma, option_type=option_type)
        return _serialize_result(result, "calculate_greeks")

    @function_tool
    def tool_get_option_chain(
        ticker: str,
        expiry: Optional[str] = None,
        num_strikes: int = 10,
        max_expirations_for_term_structure: int = 6,
    ) -> str:
        """Get live option chain from IBKR: P/C ratio, max pain, OI concentration, IV term structure. Takes ~30 seconds.

        Args:
            ticker: Stock ticker symbol
            expiry: Target expiration YYYYMMDD (default: nearest with >=7 DTE)
            num_strikes: Strikes above/below ATM (default: 10)
            max_expirations_for_term_structure: Expirations for IV term structure (default: 6)
        """
        result = _get_option_chain(
            ticker=ticker, expiry=expiry,
            num_strikes=num_strikes,
            max_expirations_for_term_structure=max_expirations_for_term_structure,
        )
        return _serialize_result(result, "get_option_chain")

    @function_tool
    def tool_get_iv_skew_analysis(
        ticker: str,
        expiry: Optional[str] = None,
        num_strikes: int = 10,
    ) -> str:
        """Analyze IV skew: shape classification (put_skew/smile/call_skew/flat), 25-delta skew, gradient, term structure skew. Requires IBKR.

        Args:
            ticker: Stock ticker symbol
            expiry: Target expiration YYYYMMDD (default: nearest with >=7 DTE)
            num_strikes: Strikes above/below ATM (default: 10)
        """
        result = _get_iv_skew_analysis(ticker=ticker, expiry=expiry, num_strikes=num_strikes)
        return _serialize_result(result, "get_iv_skew_analysis")

    # ================================================================
    # Signal Tools
    # ================================================================

    @function_tool
    def tool_detect_anomalies(
        ticker: str, days: int = 30, as_of_date: Optional[str] = None
    ) -> str:
        """Detect statistical anomalies in sentiment and news volume for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 30)
            as_of_date: Anchor date YYYY-MM-DD (default: latest date in data)

        Returns sentiment_anomaly, volume_anomaly, and their z-scores.
        """
        result = detect_anomalies(dal, ticker, days=days, as_of_date=as_of_date)
        return _serialize_result(result, "detect_anomalies")

    @function_tool
    def tool_detect_event_chains(ticker: str, days: int = 30) -> str:
        """Detect event chain patterns (earnings -> guidance -> analyst reactions).

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 30)

        Returns list of detected event chains with confidence scores.
        """
        result = detect_event_chains(dal, ticker, days=days)
        return _serialize_result(result, "detect_event_chains")

    @function_tool
    def tool_synthesize_signal(
        ticker: str,
        days: int = 30,
        strategy: Optional[str] = None,
        as_of_date: Optional[str] = None,
    ) -> str:
        """Synthesize a multi-factor trading signal combining sector momentum, events, and sentiment.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 30)
            strategy: Strategy name for custom weights (from user_profile.yaml)
            as_of_date: Anchor date YYYY-MM-DD (default: latest date in data)

        Returns action (BUY/SELL/HOLD), confidence, composite_score, and reasoning.
        """
        result = synthesize_signal(
            dal, ticker, days=days, strategy=strategy, as_of_date=as_of_date,
        )
        return _serialize_result(result, "synthesize_signal")

    # ================================================================
    # Analysis Tools
    # ================================================================

    @function_tool
    def tool_get_fundamentals_analysis(ticker: str) -> str:
        """Get fundamental analysis (P/E, ROE, market cap, margins) for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns market_cap, pe_ratio, roe, profit_margin, etc.
        """
        result = get_fundamentals_analysis(dal, ticker)
        return _serialize_result(result, "get_fundamentals_analysis")

    @function_tool
    def tool_get_detailed_financials(ticker: str) -> str:
        """Get comprehensive financial metrics: EV/EBITDA, EV/Revenue, PEG, ROIC, FCF yield, margins, growth, tech-specific (SBC/Revenue, R&D/Revenue, Rule of 40), and earnings surprise.

        Args:
            ticker: Stock ticker symbol
        """
        result = get_detailed_financials(dal, ticker)
        return _serialize_result(result, "get_detailed_financials")

    @function_tool
    def tool_get_peer_comparison(
        ticker: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        sector: Optional[str] = None,
    ) -> str:
        """Compare a ticker vs sector peers: PE, EV/EBITDA, margins, growth, ROE, ROIC, Rule of 40. Returns matrix, rankings, medians.

        Args:
            ticker: Target ticker to rank vs peers (auto-detects sector)
            tickers: Explicit peer list (overrides sector)
            sector: Sector from sectors.yaml (e.g. AI_CHIPS, FINTECH)
        """
        result = get_peer_comparison(dal, ticker=ticker, tickers=tickers, sector=sector)
        return _serialize_result(result, "get_peer_comparison")

    @function_tool
    def tool_get_sec_filings(
        ticker: str,
        filing_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> str:
        """Get SEC filing metadata (10-K, 10-Q, 8-K, etc.) for a ticker. Returns filing type, date, and URL — metadata only, not content.

        Args:
            ticker: Stock ticker symbol
            filing_types: Filter by filing types (e.g. ['10-K', '10-Q'])
            limit: Maximum number of filings to return (default: 10)
        """
        result = get_sec_filings(ticker, filing_types=filing_types, limit=limit)
        return _serialize_result(result, "get_sec_filings")

    @function_tool
    def tool_get_insider_trades(
        ticker: str,
        limit: int = 10,
    ) -> str:
        """Get recent insider trades (SEC Form 4) for a ticker. Fully parsed: insider name, title, transaction date, shares (negative=sale), price, and holdings before/after.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of trades to return (default: 10)
        """
        result = get_insider_trades(ticker=ticker, limit=limit)
        return _serialize_result(result, "get_insider_trades")

    @function_tool
    def tool_get_watchlist_overview() -> str:
        """Get a summary of all watchlist tickers' current status.

        Returns ticker_count, sector breakdown, and top movers.
        """
        result = get_watchlist_overview(dal)
        return _serialize_result(result, "get_watchlist_overview")

    @function_tool
    def tool_get_morning_brief() -> str:
        """Generate a personalized morning briefing with holdings, sector highlights, and notable news.

        Returns date, holdings status, sector performance, and news highlights.
        """
        result = get_morning_brief(dal)
        return _serialize_result(result, "get_morning_brief")

    # ================================================================
    # Analyst Tools (Phase 11b)
    # ================================================================

    @function_tool
    def tool_get_analyst_consensus(ticker: str) -> str:
        """Get analyst consensus for a ticker: recommendation distribution (buy/hold/sell trend), last 4 quarters earnings (actual vs estimate with surprise %), upcoming earnings date and estimates, and analyst price target (if available). Uses Finnhub free API."""
        result = get_analyst_consensus(ticker=ticker)
        return _serialize_result(result, "get_analyst_consensus")

    # ================================================================
    # Portfolio Tools (Batch 3a)
    # ================================================================

    @function_tool
    def tool_get_portfolio_analysis(
        tickers: Optional[List[str]] = None,
        holdings_json: str = "",
    ) -> str:
        """Analyze portfolio or watchlist: P&L, beta vs SPY, correlation matrix, portfolio metrics (weighted beta, HHI, sector diversification).

        Args:
            tickers: List of ticker symbols (default: watchlist from config)
            holdings_json: Holdings as JSON string, e.g. '{"NVDA": {"qty": 100, "entry_price": 120.50}}'
        """
        holdings = None
        if holdings_json:
            try:
                holdings = json.loads(holdings_json)
            except (json.JSONDecodeError, TypeError):
                return json.dumps({"error": f"Invalid holdings_json: {holdings_json}"})
        result = _get_portfolio_analysis(dal, tickers=tickers, holdings=holdings)
        return _serialize_result(result, "get_portfolio_analysis")

    # ================================================================
    # Earnings Impact (Batch 3c)
    # ================================================================

    @function_tool
    def tool_get_earnings_impact(
        ticker: str,
        quarters: int = 4,
    ) -> str:
        """Analyze historical earnings price reactions: earnings-day moves, directional bias, surprise correlation, expected move, and pre/post drift.

        Args:
            ticker: Stock ticker symbol
            quarters: Past quarters to analyze (default: 4)
        """
        result = _get_earnings_impact(dal, ticker=ticker, quarters=quarters)
        return _serialize_result(result, "get_earnings_impact")

    # ================================================================
    # Execution Tools
    # ================================================================

    @function_tool
    def tool_execute_python_analysis(
        code: str = "",
        task: str = "",
        data_json: str = "",
        timeout: int = 120,
        background: bool = False,
    ) -> str:
        """Run Python for ANY numerical calculation or data analysis.

        IMPORTANT: Always use this tool instead of calculating mentally.
        Results are reproducible, auditable, and auto-corrected on errors.

        PREFERRED: Pass `task` (natural language description). The system
        auto-generates Python code and retries up to 3 times on errors.
        Only use `code` for precise, hand-crafted implementations.

        Args:
            task: Natural language task description (PREFERRED). Example:
                "Calculate 30-day Sharpe ratio from the provided OHLCV data"
            code: Python code to execute directly (alternative to task)
            data_json: JSON data passed as `data` variable in code
            timeout: Execution timeout in seconds (default: 120)
            background: Run in background for long tasks (default: False)
        """
        result = execute_python_code(
            code=code, task=task, data_json=data_json,
            timeout=timeout, background=background,
        )
        return _serialize_result(result, "execute_python_analysis")

    # ================================================================
    # Subagent Delegation
    # ================================================================

    @function_tool
    def tool_delegate_to_subagent(
        subagent: str,
        task: str,
        context_json: str = "",
    ) -> str:
        """Delegate a subtask to a specialized subagent. Each subagent has its own model, system prompt, and tool subset. Returns structured JSON results. For single calculations with data you already have, use execute_python_analysis directly instead.

        Available subagents:
        - code_analyst: Multi-step quantitative research — fetches data AND computes (anomaly detection, custom models)
        - deep_researcher: Thorough multi-source investigation (news, prices, fundamentals, options, signals)
        - data_summarizer: Fast bulk data retrieval and concise summarization
        - reviewer: Critical analysis review — finds logical flaws, overlooked risks, confidence adjustment

        Args:
            subagent: Subagent name - code_analyst, deep_researcher, data_summarizer, or reviewer
            task: Natural language task description for the subagent
            context_json: Optional JSON data context from earlier tool calls (max 5000 chars)
        """
        from src.agents.shared.subagent import dispatch_subagent
        result = dispatch_subagent(
            subagent_name=subagent,
            task=task,
            context_json=context_json,
            dal=dal,
        )
        return _serialize_result(result, "delegate_to_subagent")

    # ================================================================
    # Web Tools (Phase 10) — conditional on config
    # ================================================================

    from ..config import get_agent_config
    from src.tools.web_tools import web_search, web_fetch, web_browse, codex_web_research as _codex_web_research
    web_config = get_agent_config()

    @function_tool
    def tool_tavily_search(
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        topic: str = "general",
        days: int = 0,
    ) -> str:
        """Search the web for real-time information using Tavily. Returns AI summary and ranked results with relevance scores. Use topic='finance' for financial queries, topic='news' for current events.

        Args:
            query: Search query string
            max_results: Max results 1-10 (default: 5)
            search_depth: basic (1 credit) or advanced (2 credits)
            topic: general, news, or finance (default: general)
            days: Limit to results from last N days (0=no limit)
        """
        result = web_search(
            query=query, max_results=max_results,
            search_depth=search_depth, topic=topic, days=days,
        )
        return _serialize_result(result, "tavily_search")

    @function_tool
    def tool_tavily_fetch(
        url: str,
        extract_depth: str = "basic",
        offset: int = 0,
        max_chars: int = 3000,
    ) -> str:
        """Fetch and extract content from a specific URL using Tavily. Supports pagination via offset/max_chars for long pages. Check was_truncated and use offset to read more.

        Args:
            url: URL to fetch content from
            extract_depth: basic or advanced (default: basic)
            offset: Start position in chars for pagination (default: 0)
            max_chars: Max chars to return per call (default: 3000)
        """
        result = web_fetch(url=url, extract_depth=extract_depth, offset=offset, max_chars=max_chars)
        return _serialize_result(result, "tavily_fetch")

    @function_tool
    def tool_web_browse(
        url: str,
        wait_for: str = "networkidle",
        extract_links: bool = False,
        offset: int = 0,
        max_chars: int = 5000,
    ) -> str:
        """Browse a URL with headless Chromium browser (Playwright). Handles JavaScript-rendered pages that Tavily cannot extract. Supports pagination via offset/max_chars.

        Args:
            url: URL to browse
            wait_for: Page load wait strategy - networkidle, load, or domcontentloaded (default: networkidle)
            extract_links: Also extract page links (default: false)
            offset: Start position in chars for pagination (default: 0)
            max_chars: Max chars to return per call (default: 5000)
        """
        result = web_browse(
            url=url, wait_for=wait_for, extract_links=extract_links,
            offset=offset, max_chars=max_chars,
        )
        return _serialize_result(result, "web_browse")

    # ================================================================
    # Codex Deep Research (Phase 10+)
    # ================================================================

    @function_tool
    def tool_codex_web_research(
        query: str,
        context: str = "",
        timeout: int = 300,
    ) -> str:
        """Deep web research using Codex CLI with live web browsing. An autonomous AI research agent that searches multiple sources, cross-references information, and produces a structured report. Use for deep investigation (earnings analysis, event research, competitive landscape). Takes 1-5 minutes.

        Args:
            query: Research question or topic to investigate
            context: Optional context from earlier tool calls to inform research
            timeout: Max seconds for research (default: 300, increase for complex topics)
        """
        result = _codex_web_research(query=query, context=context, timeout=timeout)
        return _serialize_result(result, "codex_web_research")

    # ================================================================
    # Report Tools (Phase B)
    # ================================================================

    @function_tool
    def tool_save_report(
        title: str,
        tickers: List[str],
        report_type: str,
        summary: str,
        content: str,
        conclusion: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        """Save a research report after completing a thorough analysis. Persists full Markdown to data/reports/ and metadata to DB.

        Args:
            title: Report title (e.g. "AFRM Entry Analysis")
            tickers: List of analyzed ticker symbols
            report_type: Category - entry_analysis, sector_review, earnings_review, comparison, thesis, morning_brief, custom
            summary: 1-2 sentence conclusion
            content: Full Markdown report with analysis details
            conclusion: Trading conclusion - BUY, HOLD, SELL, WATCH, or NEUTRAL
            confidence: Confidence score 0-1
        """
        result = _save_report(
            dal, title=title, tickers=tickers, report_type=report_type,
            summary=summary, content=content, conclusion=conclusion,
            confidence=confidence,
        )
        return _serialize_result(result, "save_report")

    @function_tool
    def tool_list_reports(
        ticker: Optional[str] = None,
        days: int = 30,
        report_type: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """List saved research reports, optionally filtered by ticker or type.

        Args:
            ticker: Filter by ticker symbol
            days: Lookback period in days (default: 30)
            report_type: Filter by report type
            limit: Max reports to return (default: 20)
        """
        result = _list_reports(dal, ticker=ticker, days=days, report_type=report_type, limit=limit)
        return _serialize_result(result, "list_reports")

    @function_tool
    def tool_get_report(
        report_id: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> str:
        """Retrieve a saved research report by ID or file path.

        Args:
            report_id: Report ID from database
            file_path: Relative path to Markdown file
        """
        result = _get_report(dal, report_id=report_id, file_path=file_path)
        return _serialize_result(result, "get_report")

    # ================================================================
    # Memory Tools (Phase 15)
    # ================================================================

    @function_tool
    def tool_save_memory(
        title: str,
        content: str,
        category: str = "note",
        tickers: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        importance: int = 5,
    ) -> str:
        """Save a piece of knowledge to long-term memory for future recall. Use after completing analyses, discovering insights, or when the user asks to remember something. Memories persist across sessions.

        Args:
            title: Short descriptive title for this memory
            content: Full content to remember (Markdown supported)
            category: Memory category - analysis, insight, preference, fact, or note (default: note)
            tickers: Related ticker symbols
            tags: Free-form tags for categorization
            importance: Importance 1-10 (10=critical, 5=normal, 1=trivial)
        """
        result = _save_memory(
            dal, title=title, content=content, category=category,
            tickers=tickers, tags=tags, importance=importance,
            source="agent_auto",
        )
        return _serialize_result(result, "save_memory")

    @function_tool
    def tool_recall_memories(
        query: str = "",
        category: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        days: int = 90,
        limit: int = 10,
    ) -> str:
        """Search long-term memory for relevant past knowledge. Use when the user references past analyses, asks 'what did we discuss about X', or when you need context from previous sessions.

        Args:
            query: Search query (keywords or natural language)
            category: Filter by category - analysis, insight, preference, fact, or note
            tickers: Filter by related tickers
            tags: Filter by tags
            days: Lookback period in days (default: 90)
            limit: Max memories to return (default: 10)
        """
        result = _recall_memories(
            dal, query=query, category=category,
            tickers=tickers, tags=tags, days=days, limit=limit,
        )
        return _serialize_result(result, "recall_memories")

    @function_tool
    def tool_list_memories(
        category: Optional[str] = None,
        days: int = 90,
        limit: int = 20,
    ) -> str:
        """List saved memories (metadata only, no full content).

        Args:
            category: Filter by category - analysis, insight, preference, fact, or note
            days: Lookback period in days (default: 90)
            limit: Max memories to return (default: 20)
        """
        result = _list_memories(dal, category=category, days=days, limit=limit)
        return _serialize_result(result, "list_memories")

    @function_tool
    def tool_delete_memory(memory_id: int) -> str:
        """Delete a memory by its ID.

        Args:
            memory_id: Memory ID to delete
        """
        result = _delete_memory(dal, memory_id=memory_id)
        return _serialize_result(result, "delete_memory")

    # ================================================================
    # Monitor Tools (Phase E1)
    # ================================================================

    @function_tool
    def tool_scan_alerts(tickers: str = "") -> str:
        """Scan watchlist or specific tickers for price, sentiment, signal, and sector alerts.

        Args:
            tickers: Comma-separated ticker symbols (empty = scan full watchlist from config)
        """
        result = _scan_alerts(dal, tickers=tickers)
        return _serialize_result(result, "scan_alerts")

    # ================================================================
    # Data Freshness
    # ================================================================

    @function_tool
    def tool_check_data_freshness() -> str:
        """Check health and freshness of all data sources (news, prices, IV, fundamentals).

        Returns staleness status, latest data timestamps, and record counts.
        Use to verify data quality before analysis.
        """
        result = _check_data_freshness(dal)
        return _serialize_result(result, "check_data_freshness")

    # ================================================================
    # RL Pipeline Tools
    # ================================================================

    @function_tool
    def tool_get_rl_model_status() -> str:
        """List all trained RL models (PPO/CPPO) with backtest performance.

        Returns:
            Sharpe ratio, information ratio, max drawdown, CVaR for each model.
        """
        result = _get_rl_model_status(dal)
        return _serialize_result(result, "get_rl_model_status")

    @function_tool
    def tool_get_rl_prediction(ticker: str, model_id: str = "latest") -> str:
        """Get RL model trading signal for a ticker.

        Args:
            ticker: Stock ticker symbol
            model_id: Model ID to use (default: 'latest' = most recent)
        """
        result = _get_rl_prediction(dal, ticker=ticker, model_id=model_id)
        return _serialize_result(result, "get_rl_prediction")

    @function_tool
    def tool_get_rl_backtest_report(model_id: str = "latest") -> str:
        """Get detailed backtest report for a trained RL model.

        Args:
            model_id: Model ID (default: 'latest' = most recent)
        """
        result = _get_rl_backtest_report(dal, model_id=model_id)
        return _serialize_result(result, "get_rl_backtest_report")

    # Return all tools as a list
    tools = [
        tool_get_ticker_news,
        tool_get_news_sentiment_summary,
        tool_search_news_by_keyword,
        tool_get_news_brief,
        tool_search_news_advanced,
        tool_get_ticker_prices,
        tool_get_price_change,
        tool_get_sector_performance,
        tool_get_iv_analysis,
        tool_get_iv_history_data,
        tool_scan_mispricing,
        tool_calculate_greeks,
        tool_get_option_chain,
        tool_get_iv_skew_analysis,
        tool_detect_anomalies,
        tool_detect_event_chains,
        tool_synthesize_signal,
        tool_get_fundamentals_analysis,
        tool_get_detailed_financials,
        tool_get_peer_comparison,
        tool_get_sec_filings,
        tool_get_insider_trades,
        tool_get_watchlist_overview,
        tool_get_morning_brief,
        tool_get_analyst_consensus,
        tool_get_portfolio_analysis,
        tool_get_earnings_impact,
        tool_execute_python_analysis,
        tool_delegate_to_subagent,
        tool_save_report,
        tool_list_reports,
        tool_get_report,
        tool_save_memory,
        tool_recall_memories,
        tool_list_memories,
        tool_delete_memory,
        tool_scan_alerts,
        tool_check_data_freshness,
        tool_get_rl_model_status,
        tool_get_rl_prediction,
        tool_get_rl_backtest_report,
    ]

    # Conditionally add web tools
    if web_config.web_tavily:
        tools.extend([tool_tavily_search, tool_tavily_fetch])
    if web_config.web_playwright:
        tools.append(tool_web_browse)
    if web_config.web_codex_research:
        tools.append(tool_codex_web_research)

    return tools