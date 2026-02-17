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
    from src.tools.signal_tools import (
        detect_anomalies,
        detect_event_chains,
        synthesize_signal,
    )
    from src.tools.analysis_tools import (
        get_fundamentals_analysis,
        get_watchlist_overview,
        get_morning_brief,
    )
    from src.tools.sec_tools import (
        get_sec_filings,
        get_insider_trades,
    )
    from src.tools.code_executor import execute_python_code
    from src.tools.analyst_tools import get_analyst_consensus

    # ================================================================
    # News Tools
    # ================================================================

    @function_tool
    def tool_get_ticker_news(
        ticker: str,
        days: int = 30,
        source: str = "auto",
        limit: int = 50,
    ) -> str:
        """Get recent news articles for a stock ticker. Returns up to `limit` most recent articles. The response includes `count` (total available) so you know if more exist.

        Args:
            ticker: Stock ticker symbol (e.g. NVDA, AMD)
            days: Lookback period in days (default: 30)
            source: Data source - auto, ibkr, or polygon (default: auto)
            limit: Max articles to return, 1-500 (default: 50)
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
        limit: int = 50,
    ) -> str:
        """Search news articles by keyword in titles and descriptions. Returns up to `limit` most recent matches.

        Args:
            keyword: Search keyword
            days: Lookback period in days (default: 30)
            ticker: Optionally filter by ticker
            limit: Max articles to return, 1-500 (default: 50)
        """
        result = search_news_by_keyword(dal, keyword, days=days, ticker=ticker, limit=limit)
        return _serialize_result(result, "search_news_by_keyword")

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

    # ================================================================
    # Signal Tools
    # ================================================================

    @function_tool
    def tool_detect_anomalies(ticker: str, days: int = 30) -> str:
        """Detect statistical anomalies in sentiment and news volume for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 30)

        Returns sentiment_anomaly, volume_anomaly, and their z-scores.
        """
        result = detect_anomalies(dal, ticker, days=days)
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
        strategy: Optional[str] = None
    ) -> str:
        """Synthesize a multi-factor trading signal combining sector momentum, events, and sentiment.

        Args:
            ticker: Stock ticker symbol
            days: Lookback period in days (default: 30)
            strategy: Strategy name for custom weights (from user_profile.yaml)

        Returns action (BUY/SELL/HOLD), confidence, composite_score, and reasoning.
        """
        result = synthesize_signal(dal, ticker, days=days, strategy=strategy)
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
        """Execute Python code for custom financial calculations and data analysis.

        Provide `code` for direct execution, or `task` for auto code generation
        using a coding model with error-correcting retry.
        Code runs in isolated subprocess with numpy, pandas, scipy available.
        Pass data via data_json parameter (accessible as `data` variable in code).
        Set background=True for long-running tasks (results written to temp file).

        Args:
            code: Python code to execute (direct mode)
            task: Task description for auto code generation with error correction (alternative to code)
            data_json: JSON string of data to inject (accessible as `data` variable)
            timeout: Execution timeout in seconds (default: 120)
            background: Run in background, write results to temp file (default: False)
        """
        result = execute_python_code(
            code=code, task=task, data_json=data_json,
            timeout=timeout, background=background,
        )
        return _serialize_result(result, "execute_python_code")

    # ================================================================
    # Subagent Delegation
    # ================================================================

    @function_tool
    def tool_delegate_to_subagent(
        subagent: str,
        task: str,
        context_json: str = "",
    ) -> str:
        """Delegate a subtask to a specialized subagent. Each subagent has its own model, system prompt, and tool subset. Returns structured JSON results.

        Available subagents:
        - code_analyst: Quantitative Python analysis (Sharpe ratios, correlations, regressions)
        - deep_researcher: Thorough multi-source investigation (news, prices, fundamentals, options, signals)
        - data_summarizer: Fast bulk data retrieval and concise summarization

        Args:
            subagent: Subagent name - code_analyst, deep_researcher, or data_summarizer
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
    from src.tools.web_tools import web_search, web_fetch, web_browse
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

    # Return all tools as a list
    tools = [
        tool_get_ticker_news,
        tool_get_news_sentiment_summary,
        tool_search_news_by_keyword,
        tool_get_ticker_prices,
        tool_get_price_change,
        tool_get_sector_performance,
        tool_get_iv_analysis,
        tool_get_iv_history_data,
        tool_scan_mispricing,
        tool_calculate_greeks,
        tool_detect_anomalies,
        tool_detect_event_chains,
        tool_synthesize_signal,
        tool_get_fundamentals_analysis,
        tool_get_sec_filings,
        tool_get_insider_trades,
        tool_get_watchlist_overview,
        tool_get_morning_brief,
        tool_get_analyst_consensus,
        tool_execute_python_analysis,
        tool_delegate_to_subagent,
    ]

    # Conditionally add web tools
    if web_config.web_tavily:
        tools.extend([tool_tavily_search, tool_tavily_fetch])
    if web_config.web_playwright:
        tools.append(tool_web_browse)

    return tools