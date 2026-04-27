"""
ToolRegistry — central catalog of all tool functions.

Provides:
- Registration and lookup of tool definitions
- Schema export for OpenAI Agents SDK (function_tool format)
- Schema export for Anthropic SDK (tool_use format)
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolParameter:
    """Single parameter definition for a tool."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """Complete definition of a tool function."""
    name: str
    description: str
    function: Callable
    parameters: List[ToolParameter] = field(default_factory=list)
    category: str = "general"
    requires_dal: bool = True  # Whether first arg is DataAccessLayer


class ToolRegistry:
    """
    Central registry for all tool functions.

    Usage:
        registry = ToolRegistry()
        registry.register_all()  # Register all built-in tools

        # Lookup
        tool = registry.get("get_ticker_news")
        tool.function(dal, ticker="NVDA", days=7)

        # Export for Agent SDKs
        openai_tools = registry.to_openai_schema()
        anthropic_tools = registry.to_anthropic_schema()
    """

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> List[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_category(self, category: str) -> List[ToolDefinition]:
        """List tools filtered by category."""
        return [t for t in self._tools.values() if t.category == category]

    def list_names(self) -> List[str]:
        """List all tool names."""
        return sorted(self._tools.keys())

    # ============================================================
    # Schema Export
    # ============================================================

    def to_openai_schema(self) -> List[dict]:
        """
        Export tool definitions in OpenAI function calling format.

        Compatible with OpenAI Agents SDK @function_tool schema.
        """
        tools = []
        for tool in self._tools.values():
            properties = {}
            required = []

            for p in tool.parameters:
                prop: dict = {
                    "type": p.type,
                    "description": p.description,
                }
                if p.enum:
                    prop["enum"] = p.enum
                properties[p.name] = prop
                if p.required:
                    required.append(p.name)

            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return tools

    def to_anthropic_schema(self) -> List[dict]:
        """
        Export tool definitions in Anthropic tool_use format.

        Compatible with Anthropic SDK messages.create(tools=[...]).
        """
        tools = []
        for tool in self._tools.values():
            properties = {}
            required = []

            for p in tool.parameters:
                prop: dict = {
                    "type": p.type,
                    "description": p.description,
                }
                if p.enum:
                    prop["enum"] = p.enum
                properties[p.name] = prop
                if p.required:
                    required.append(p.name)

            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return tools

    # ============================================================
    # Bulk Registration
    # ============================================================

    def register_all(self) -> None:
        """Register all built-in tool functions."""
        self._register_news_tools()
        self._register_price_tools()
        self._register_options_tools()
        self._register_signal_tools()
        self._register_analysis_tools()
        self._register_portfolio_tools()
        self._register_report_tools()
        self._register_memory_tools()
        self._register_web_tools()
        self._register_execution_tools()
        self._register_monitor_tools()
        self._register_freshness_tools()
        self._register_rl_tools()
        self._register_sa_tools()
        self._register_macro_calendar_tools()

    def _register_news_tools(self) -> None:
        from .news_tools import (
            get_ticker_news,
            get_news_sentiment_summary,
            search_news_by_keyword,
            get_news_brief,
            search_news_advanced,
        )

        self.register(ToolDefinition(
            name="get_ticker_news",
            description=(
                "Get recent news articles for a stock ticker. "
                "Returns up to `limit` most recent articles (default 20). "
                "The response includes `count` (total available) so you know if more exist."
            ),
            function=get_ticker_news,
            category="news",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol (e.g. NVDA)"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("source", "string", "Data source", required=False, default="auto",
                              enum=["auto", "ibkr", "polygon"]),
                ToolParameter("limit", "integer", "Max articles to return (1-500, default 20)", required=False, default=20),
            ],
        ))

        self.register(ToolDefinition(
            name="get_news_sentiment_summary",
            description="Get aggregated sentiment statistics (mean, bullish/bearish ratio) for a ticker.",
            function=get_news_sentiment_summary,
            category="news",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=7),
            ],
        ))

        self.register(ToolDefinition(
            name="search_news_by_keyword",
            description=(
                "Search news articles by keyword in titles and descriptions using "
                "full-text search. Returns up to `limit` most recent matches."
            ),
            function=search_news_by_keyword,
            category="news",
            parameters=[
                ToolParameter("keyword", "string", "Search keyword (supports multi-word)"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("ticker", "string", "Optionally filter by ticker", required=False),
                ToolParameter("limit", "integer", "Max articles to return (1-500, default 20)", required=False, default=20),
            ],
        ))

        self.register(ToolDefinition(
            name="get_news_brief",
            description=(
                "Get a lightweight news overview for multiple tickers: "
                "article count, avg sentiment, avg risk, date range. "
                "Call this FIRST before get_ticker_news() to decide which "
                "tickers need detailed investigation. Very fast, minimal output."
            ),
            function=get_news_brief,
            category="news",
            parameters=[
                ToolParameter("tickers", "array", "List of ticker symbols (default: watchlist)", required=False),
                ToolParameter("days", "integer", "Lookback period in days (default: 7)", required=False, default=7),
            ],
        ))

        self.register(ToolDefinition(
            name="search_news_advanced",
            description=(
                "Advanced news search combining full-text search + multi-ticker + "
                "date range + score filters. Use for cross-ticker theme searches "
                "(e.g. 'tariff impact' across AI_CHIPS sector). All filtering at DB level."
            ),
            function=search_news_advanced,
            category="news",
            parameters=[
                ToolParameter("query", "string", "Full-text search query", required=False, default=""),
                ToolParameter("tickers", "array", "Filter by multiple tickers", required=False),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("scored_only", "boolean", "Only return scored articles", required=False, default=False),
                ToolParameter("min_sentiment", "integer", "Minimum sentiment score (1-5)", required=False),
                ToolParameter("max_risk", "integer", "Maximum risk score (1-5)", required=False),
                ToolParameter("limit", "integer", "Max articles to return (default: 20)", required=False, default=20),
            ],
        ))

    def _register_price_tools(self) -> None:
        from .price_tools import (
            get_ticker_prices,
            get_price_change,
            get_sector_performance,
        )

        self.register(ToolDefinition(
            name="get_ticker_prices",
            description="Get OHLCV price bars for a stock ticker.",
            function=get_ticker_prices,
            category="prices",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("interval", "string", "Bar interval", required=False, default="15min",
                              enum=["15min", "1h", "1d"]),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
            ],
        ))

        self.register(ToolDefinition(
            name="get_price_change",
            description="Calculate price change percentage and high/low range for a ticker over a period.",
            function=get_price_change,
            category="prices",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=7),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sector_performance",
            description="Calculate average performance of all tickers in a sector.",
            function=get_sector_performance,
            category="prices",
            parameters=[
                ToolParameter("sector", "string", "Sector name (e.g. AI_CHIPS, FINTECH, EV)"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=7),
            ],
        ))

    def _register_options_tools(self) -> None:
        from .options_tools import (
            get_iv_analysis,
            get_iv_history_data,
            scan_mispricing,
            calculate_greeks,
        )
        from .option_chain_tools import get_option_chain
        from .iv_skew_tools import get_iv_skew_analysis

        self.register(ToolDefinition(
            name="get_iv_analysis",
            description="Full implied volatility analysis: IV rank, percentile, VRP, and trading signal.",
            function=get_iv_analysis,
            category="options",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_iv_history_data",
            description="Get raw IV history data points (ATM IV, HV, VRP) for a ticker.",
            function=get_iv_history_data,
            category="options",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

        self.register(ToolDefinition(
            name="scan_mispricing",
            description="Scan for mispriced options comparing theoretical vs market prices.",
            function=scan_mispricing,
            category="options",
            parameters=[
                ToolParameter("tickers", "array", "List of ticker symbols to scan"),
                ToolParameter("mispricing_threshold_pct", "number",
                              "Minimum mispricing % to report", required=False, default=10.0),
                ToolParameter("min_confidence", "string",
                              "Minimum confidence level", required=False, default="MEDIUM",
                              enum=["HIGH", "MEDIUM", "LOW"]),
            ],
        ))

        self.register(ToolDefinition(
            name="calculate_greeks",
            description="Calculate option Greeks (delta, gamma, theta, vega, rho). Supports American (Bjerksund-Stensland 2002) and European (Black-Scholes) pricing models.",
            function=calculate_greeks,
            category="options",
            requires_dal=False,
            parameters=[
                ToolParameter("S", "number", "Spot price of the underlying"),
                ToolParameter("K", "number", "Strike price"),
                ToolParameter("T", "number", "Time to expiry in years (e.g. 0.25 for 3 months)"),
                ToolParameter("r", "number", "Risk-free rate (e.g. 0.05 for 5%)"),
                ToolParameter("sigma", "number", "Volatility (e.g. 0.30 for 30%)"),
                ToolParameter("option_type", "string", "Option type", required=False, default="C",
                              enum=["C", "P"]),
                ToolParameter("model", "string",
                              "Pricing model: 'american' (BS2002) or 'black_scholes' (European)",
                              required=False, default="american",
                              enum=["american", "black_scholes"]),
                ToolParameter("dividend_yield", "number",
                              "Continuous dividend yield (e.g. 0.02 for 2%)",
                              required=False, default=0.0),
            ],
        ))

        self.register(ToolDefinition(
            name="get_option_chain",
            description=(
                "Get live option chain from IBKR with analysis: "
                "call/put quotes around ATM, P/C ratio (volume + OI), max pain, "
                "OI concentration, IV term structure, and bid-ask quality. "
                "Requires IBKR gateway running. Takes ~30 seconds."
            ),
            function=get_option_chain,
            category="options",
            requires_dal=False,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("expiry", "string",
                              "Target expiration YYYYMMDD (default: nearest with >=7 DTE)",
                              required=False),
                ToolParameter("num_strikes", "integer",
                              "Strikes above/below ATM to fetch (default: 10)",
                              required=False),
                ToolParameter("max_expirations_for_term_structure", "integer",
                              "Expirations for IV term structure (default: 6)",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_iv_skew_analysis",
            description=(
                "Analyze IV skew from live option chain: call-put skew, "
                "smile/smirk shape classification, 25-delta skew, skew gradient, "
                "and term structure skew across expirations. Requires IBKR gateway."
            ),
            function=get_iv_skew_analysis,
            category="options",
            requires_dal=False,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("expiry", "string",
                              "Target expiration YYYYMMDD (default: nearest with >=7 DTE)",
                              required=False),
                ToolParameter("num_strikes", "integer",
                              "Strikes above/below ATM (default: 10)",
                              required=False),
            ],
        ))

    def _register_signal_tools(self) -> None:
        from .signal_tools import (
            detect_anomalies,
            detect_event_chains,
            get_signal_factors,
            synthesize_signal,
        )

        self.register(ToolDefinition(
            name="detect_anomalies",
            description="Detect statistical anomalies in sentiment and news volume for a ticker.",
            function=detect_anomalies,
            category="signals",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("as_of_date", "string", "Anchor date YYYY-MM-DD (default: latest in data)", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="detect_event_chains",
            description="Detect event chain patterns (sequences of related events like earnings → guidance → analyst reactions).",
            function=detect_event_chains,
            category="signals",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
            ],
        ))

        self.register(ToolDefinition(
            name="synthesize_signal",
            description="Synthesize a multi-factor trading signal combining sector momentum, event chains, and sentiment anomalies.",
            function=synthesize_signal,
            category="signals",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("strategy", "string",
                              "Strategy name for custom weights (from user_profile.yaml)",
                              required=False),
                ToolParameter("as_of_date", "string",
                              "Anchor date YYYY-MM-DD (default: latest in data)",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_signal_factors",
            description=(
                "Return the multi-factor breakdown that backs synthesize_signal: "
                "per-factor impact / weight / contribution plus a data_quality "
                "block (news_count, scored_news_count, missing_factors, errors). "
                "Recommendation only — not a price prediction. SECTOR_MOMENTUM is "
                "shared across same-sector tickers, so its contribution is not "
                "ticker-specific conviction."
            ),
            function=get_signal_factors,
            category="signals",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("as_of_date", "string",
                              "Anchor date YYYY-MM-DD (default: ticker's latest news date)",
                              required=False),
                ToolParameter("strategy", "string",
                              "Strategy name for custom weights (from user_profile.yaml)",
                              required=False),
            ],
        ))

    def _register_analysis_tools(self) -> None:
        from .analysis_tools import (
            get_fundamentals_analysis,
            get_detailed_financials,
            get_peer_comparison,
            get_watchlist_overview,
            get_morning_brief,
        )
        from .sec_tools import (
            get_sec_filings,
            get_insider_trades,
        )

        self.register(ToolDefinition(
            name="get_fundamentals_analysis",
            description=(
                "Get fundamental analysis (P/E, ROE, margins, financial statements) for a ticker. "
                "Use period='quarterly' for recent quarterly trends (QoQ/YoY growth)."
            ),
            function=get_fundamentals_analysis,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("period", "string", "Report period type",
                              required=False, default="annual",
                              enum=["annual", "quarterly"]),
            ],
        ))

        self.register(ToolDefinition(
            name="get_detailed_financials",
            description=(
                "Get comprehensive financial metrics for valuation: "
                "EV/EBITDA, EV/Revenue, PEG, ROIC, FCF yield, margins, growth, "
                "tech-specific (SBC/Revenue, R&D/Revenue, Rule of 40), "
                "and earnings surprise. IBKR real-time + SEC EDGAR cached."
            ),
            function=get_detailed_financials,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sec_filings",
            description=(
                "Get SEC filing metadata (10-K, 10-Q, 8-K, etc.) for a ticker. "
                "Returns filing type, date, and URL — metadata only, not content."
            ),
            function=get_sec_filings,
            category="analysis",
            requires_dal=False,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("filing_types", "array",
                              "Filter by filing types (e.g. ['10-K', '10-Q'])",
                              required=False),
                ToolParameter("limit", "integer",
                              "Maximum number of filings to return (default: 10)",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_insider_trades",
            description=(
                "Get recent insider trades (SEC Form 4) for a ticker. Fully parsed: "
                "insider name, title, transaction date, shares (negative=sale), "
                "price, and holdings before/after."
            ),
            function=get_insider_trades,
            category="analysis",
            requires_dal=False,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("limit", "integer",
                              "Maximum number of trades to return (default: 10)",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_watchlist_overview",
            description="Get a summary of all watchlist tickers' current status (price, sentiment, IV).",
            function=get_watchlist_overview,
            category="analysis",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_morning_brief",
            description="Generate a personalized morning briefing with holdings, sector highlights, and notable news.",
            function=get_morning_brief,
            category="analysis",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_peer_comparison",
            description=(
                "Compare a ticker vs sector peers on key metrics: "
                "PE, EV/EBITDA, margins, growth, ROE, ROIC, Rule of 40. "
                "Returns comparison matrix, percentile rankings, and sector medians. "
                "Auto-detects sector from sectors.yaml, or accepts explicit peer list."
            ),
            function=get_peer_comparison,
            category="analysis",
            requires_dal=True,
            parameters=[
                ToolParameter("ticker", "string",
                              "Target ticker to rank vs peers (auto-detects sector)",
                              required=False),
                ToolParameter("tickers", "array",
                              "Explicit list of tickers for custom peer group",
                              required=False),
                ToolParameter("sector", "string",
                              "Sector name from sectors.yaml (e.g. AI_CHIPS, FINTECH)",
                              required=False),
            ],
        ))


        # Earnings impact analysis (Batch 3c)
        from .earnings_tools import get_earnings_impact

        self.register(ToolDefinition(
            name="get_earnings_impact",
            description=(
                "Analyze historical earnings price reactions: earnings-day moves, "
                "average absolute move, directional bias, surprise correlation, "
                "expected move estimation, and pre/post earnings drift. "
                "Combines Finnhub earnings history with price data."
            ),
            function=get_earnings_impact,
            category="analysis",
            requires_dal=True,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("quarters", "integer",
                              "Past quarters to analyze (default: 4, max: 4 on free tier)",
                              required=False),
            ],
        ))

        # Analyst consensus (Finnhub free API — Phase 11b)
        from .analyst_tools import get_analyst_consensus

        self.register(ToolDefinition(
            name="get_analyst_consensus",
            description=(
                "Get analyst consensus for a ticker: recommendation distribution "
                "(buy/hold/sell), earnings history (last 4 quarters actual vs estimate), "
                "upcoming earnings date, and price target (if available)."
            ),
            function=get_analyst_consensus,
            category="analysis",
            requires_dal=False,
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

    def _register_portfolio_tools(self) -> None:
        from .portfolio_tools import get_portfolio_analysis

        self.register(ToolDefinition(
            name="get_portfolio_analysis",
            description=(
                "Analyze portfolio or watchlist: P&L (if holdings provided), "
                "beta vs SPY, pairwise correlation matrix, and portfolio-level "
                "metrics (weighted beta, HHI concentration, sector diversification). "
                "Pass holdings dict for full P&L, or tickers list for beta/correlation only."
            ),
            function=get_portfolio_analysis,
            category="portfolio",
            requires_dal=True,
            parameters=[
                ToolParameter("tickers", "array",
                              "List of ticker symbols (default: watchlist from config)",
                              required=False),
                ToolParameter("holdings", "object",
                              'Holdings dict: {"NVDA": {"qty": 100, "entry_price": 120.50}, ...}',
                              required=False),
            ],
        ))

    def _register_report_tools(self) -> None:
        from .report_tools import save_report, list_reports, get_report

        self.register(ToolDefinition(
            name="save_report",
            description=(
                "Save a research report (Markdown + DB metadata). "
                "Call this after completing a thorough analysis to persist results."
            ),
            function=save_report,
            category="reports",
            parameters=[
                ToolParameter("title", "string", "Report title"),
                ToolParameter("tickers", "array", "List of analyzed ticker symbols"),
                ToolParameter("report_type", "string",
                              "Report type (entry_analysis, sector_review, earnings_review, comparison, thesis)"),
                ToolParameter("summary", "string", "1-2 sentence conclusion"),
                ToolParameter("content", "string", "Full Markdown report content"),
                ToolParameter("conclusion", "string",
                              "Trading conclusion: BUY, HOLD, SELL, WATCH, NEUTRAL",
                              required=False),
                ToolParameter("confidence", "number", "Confidence score 0-1", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="list_reports",
            description="List saved research reports, optionally filtered by ticker or type.",
            function=list_reports,
            category="reports",
            parameters=[
                ToolParameter("ticker", "string", "Filter by ticker symbol", required=False),
                ToolParameter("days", "integer", "Lookback period in days (default: 30)", required=False),
                ToolParameter("report_type", "string", "Filter by report type", required=False),
                ToolParameter("limit", "integer", "Max reports to return (default: 20)", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_report",
            description="Retrieve a saved research report by ID or file path.",
            function=get_report,
            category="reports",
            parameters=[
                ToolParameter("report_id", "integer", "Report ID from database", required=False),
                ToolParameter("file_path", "string", "Relative path to Markdown file", required=False),
            ],
        ))

    def _register_memory_tools(self) -> None:
        from .memory_tools import save_memory, recall_memories, list_memories, delete_memory

        self.register(ToolDefinition(
            name="save_memory",
            description=(
                "Save a piece of knowledge to long-term memory for future recall. "
                "Use after completing analyses, discovering insights, or when the user "
                "asks to remember something. Memories persist across sessions."
            ),
            function=save_memory,
            category="memory",
            parameters=[
                ToolParameter("title", "string", "Short descriptive title for this memory"),
                ToolParameter("content", "string", "Full content to remember (Markdown supported)"),
                ToolParameter("category", "string", "Memory category",
                              required=False, default="note",
                              enum=["analysis", "insight", "preference", "fact", "note"]),
                ToolParameter("tickers", "array", "Related ticker symbols", required=False),
                ToolParameter("tags", "array", "Free-form tags for categorization", required=False),
                ToolParameter("importance", "integer",
                              "Importance 1-10 (10=critical, 5=normal, 1=trivial)",
                              required=False, default=5),
            ],
        ))

        self.register(ToolDefinition(
            name="recall_memories",
            description=(
                "Search long-term memory for relevant past knowledge. "
                "Use when the user references past analyses, asks 'what did we discuss about X', "
                "or when you need context from previous sessions."
            ),
            function=recall_memories,
            category="memory",
            parameters=[
                ToolParameter("query", "string",
                              "Search query (keywords or natural language)",
                              required=False, default=""),
                ToolParameter("category", "string", "Filter by category",
                              required=False,
                              enum=["analysis", "insight", "preference", "fact", "note"]),
                ToolParameter("tickers", "array", "Filter by related tickers", required=False),
                ToolParameter("tags", "array", "Filter by tags", required=False),
                ToolParameter("days", "integer",
                              "Lookback period in days (default: 90)", required=False),
                ToolParameter("limit", "integer",
                              "Max memories to return (default: 10)", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="list_memories",
            description="List saved memories (metadata only, no full content).",
            function=list_memories,
            category="memory",
            parameters=[
                ToolParameter("category", "string", "Filter by category",
                              required=False,
                              enum=["analysis", "insight", "preference", "fact", "note"]),
                ToolParameter("days", "integer",
                              "Lookback period in days (default: 90)", required=False),
                ToolParameter("limit", "integer",
                              "Max memories to return (default: 20)", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="delete_memory",
            description="Delete a memory by its ID.",
            function=delete_memory,
            category="memory",
            parameters=[
                ToolParameter("memory_id", "integer", "Memory ID to delete"),
            ],
        ))

    def _register_web_tools(self) -> None:
        from .web_tools import web_search, web_fetch, web_browse, codex_web_research

        self.register(ToolDefinition(
            name="tavily_search",
            description=(
                "Search the web for real-time information using Tavily. "
                "Returns AI summary and ranked results with relevance scores. "
                "Use topic='finance' for financial queries, topic='news' for current events."
            ),
            function=web_search,
            category="web",
            requires_dal=False,
            parameters=[
                ToolParameter("query", "string", "Search query string", required=True),
                ToolParameter("max_results", "integer", "Max results 1-10 (default: 5)", required=False, default=5),
                ToolParameter("search_depth", "string", "Search depth", required=False,
                              default="basic", enum=["basic", "advanced"]),
                ToolParameter("topic", "string", "Search topic category", required=False,
                              default="general", enum=["general", "news", "finance"]),
                ToolParameter("days", "integer", "Limit to results from last N days (0=no limit)", required=False, default=0),
            ],
        ))

        self.register(ToolDefinition(
            name="tavily_fetch",
            description=(
                "Fetch and extract content from a specific URL using Tavily. "
                "Supports pagination via offset/max_chars for long pages."
            ),
            function=web_fetch,
            category="web",
            requires_dal=False,
            parameters=[
                ToolParameter("url", "string", "URL to fetch content from", required=True),
                ToolParameter("extract_depth", "string", "Extraction depth", required=False,
                              default="basic", enum=["basic", "advanced"]),
                ToolParameter("offset", "integer", "Start position in chars for pagination (default: 0)", required=False, default=0),
                ToolParameter("max_chars", "integer", "Max chars to return per call (default: 3000)", required=False, default=3000),
            ],
        ))

        self.register(ToolDefinition(
            name="web_browse",
            description=(
                "Browse a URL with headless Chromium browser (Playwright). "
                "Handles JavaScript-rendered pages that Tavily cannot extract. "
                "Supports pagination via offset/max_chars."
            ),
            function=web_browse,
            category="web",
            requires_dal=False,
            parameters=[
                ToolParameter("url", "string", "URL to browse", required=True),
                ToolParameter("wait_for", "string", "Page load wait strategy", required=False,
                              default="networkidle", enum=["networkidle", "load", "domcontentloaded"]),
                ToolParameter("extract_links", "boolean", "Also extract page links", required=False, default=False),
                ToolParameter("offset", "integer", "Start position in chars for pagination (default: 0)", required=False, default=0),
                ToolParameter("max_chars", "integer", "Max chars to return per call (default: 5000)", required=False, default=5000),
            ],
        ))

        self.register(ToolDefinition(
            name="codex_web_research",
            description=(
                "Deep web research using Codex CLI with live web browsing. "
                "An autonomous AI research agent that searches multiple sources, "
                "cross-references information, and produces a structured report. "
                "Use for deep investigation (earnings analysis, event research, "
                "competitive landscape). Takes 1-5 minutes. For quick lookups "
                "use tavily_search instead."
            ),
            function=codex_web_research,
            category="web",
            requires_dal=False,
            parameters=[
                ToolParameter("query", "string", "Research question or topic to investigate", required=True),
                ToolParameter("context", "string", "Optional context from earlier tool calls to inform research", required=False, default=""),
                ToolParameter("timeout", "integer", "Max seconds for research (default: 300, increase for complex topics)", required=False, default=300),
            ],
        ))

    def _register_execution_tools(self) -> None:
        from .code_executor import execute_python_code

        self.register(ToolDefinition(
            name="execute_python_analysis",
            description=(
                "Run Python for ANY numerical calculation or data analysis. "
                "PREFERRED: pass `task` (natural language) — the system auto-generates "
                "code and retries on errors. Only use `code` for precise hand-crafted "
                "implementations. Do not calculate mentally; always use this tool. "
                "Sandbox with numpy, pandas, scipy. Pass data via data_json."
            ),
            function=execute_python_code,
            category="execution",
            requires_dal=False,
            parameters=[
                ToolParameter("code", "string", "Python code to execute (direct mode)",
                              required=False, default=""),
                ToolParameter("task", "string",
                              "Natural language task description (PREFERRED over code). "
                              "System auto-generates Python and retries on errors.",
                              required=False, default=""),
                ToolParameter("data_json", "string",
                              "JSON string of data to inject (accessible as `data` variable)",
                              required=False, default=""),
                ToolParameter("timeout", "integer",
                              "Execution timeout in seconds (default: 120)",
                              required=False, default=120),
                ToolParameter("background", "boolean",
                              "Run in background, write results to temp file (default: false)",
                              required=False, default=False),
            ],
        ))


    def _register_monitor_tools(self) -> None:
        from .monitor_tools import scan_alerts

        self.register(ToolDefinition(
            name="scan_alerts",
            description=(
                "Scan watchlist or specific tickers for price, sentiment, signal, "
                "and sector alerts based on configured thresholds. "
                "Returns a summary of all triggered alerts."
            ),
            function=scan_alerts,
            category="monitor",
            parameters=[
                ToolParameter(
                    "tickers", "string",
                    "Comma-separated ticker symbols to scan (empty = scan full watchlist from config)",
                    required=False, default="",
                ),
            ],
        ))


    def _register_freshness_tools(self) -> None:
        from .freshness import check_data_freshness

        self.register(ToolDefinition(
            name="check_data_freshness",
            description=(
                "Check health and freshness of all data sources (news, prices, "
                "IV history, fundamentals cache). Returns staleness status, "
                "latest data timestamps, and record counts."
            ),
            function=check_data_freshness,
            category="analysis",
            parameters=[],
            requires_dal=True,
        ))


    def _register_rl_tools(self) -> None:
        from .rl_tools import get_rl_model_status, get_rl_prediction, get_rl_backtest_report

        self.register(ToolDefinition(
            name="get_rl_model_status",
            description=(
                "List all trained RL models (PPO/CPPO) with backtest performance: "
                "Sharpe ratio, information ratio, max drawdown, CVaR. "
                "Shows which models are available for prediction queries."
            ),
            function=get_rl_model_status,
            category="rl",
            parameters=[],
            requires_dal=True,
        ))

        self.register(ToolDefinition(
            name="get_rl_prediction",
            description=(
                "Get RL model trading signal for a ticker. Uses PPO/CPPO model "
                "trained on historical prices + LLM sentiment to produce a "
                "daily-frequency buy/sell/hold signal. Not a trade instruction — "
                "use as one input among many."
            ),
            function=get_rl_prediction,
            category="rl",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("model_id", "string",
                              "Model ID to use (default: 'latest' = most recent)",
                              required=False, default="latest"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_rl_backtest_report",
            description=(
                "Get detailed backtest report for a trained RL model: "
                "Sharpe, IR, CVaR, max drawdown, win rate, training parameters, "
                "feature set, and train/test periods."
            ),
            function=get_rl_backtest_report,
            category="rl",
            parameters=[
                ToolParameter("model_id", "string",
                              "Model ID (default: 'latest' = most recent)",
                              required=False, default="latest"),
            ],
        ))


    def _register_sa_tools(self) -> None:
        from .sa_tools import (
            get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
            get_sa_articles, get_sa_article_detail, get_sa_market_news,
            list_high_value_comments,
        )

        self.register(ToolDefinition(
            name="get_sa_alpha_picks",
            description=(
                "Get Seeking Alpha Alpha Picks portfolio. Returns current and/or "
                "closed picks with return %, sector, rating, and freshness metadata. "
                "Cached with auto-refresh when stale."
            ),
            function=get_sa_alpha_picks,
            category="portfolio",
            requires_dal=True,
            parameters=[
                ToolParameter("status", "string",
                              "Filter: 'all' (default), 'current', or 'closed'",
                              required=False, default="all",
                              enum=["all", "current", "closed"]),
                ToolParameter("sector", "string",
                              "Filter by sector prefix (e.g. 'Tech')",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sa_pick_detail",
            description=(
                "Get detail report for a specific Alpha Pick. "
                "If picked_date is omitted, returns the latest current (non-stale) pick. "
                "Shows company analysis, thesis, and rating rationale."
            ),
            function=get_sa_pick_detail,
            category="portfolio",
            requires_dal=True,
            parameters=[
                ToolParameter("symbol", "string", "Stock ticker symbol (e.g. NVDA)"),
                ToolParameter("picked_date", "string",
                              "Specific pick date (YYYY-MM-DD). Omit for latest current.",
                              required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="refresh_sa_alpha_picks",
            description=(
                "Force refresh Alpha Picks from Seeking Alpha website. "
                "Scrapes both current and closed tabs, updates cache, "
                "and syncs new symbols to data collection watchlist."
            ),
            function=refresh_sa_alpha_picks,
            category="portfolio",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_sa_articles",
            description=(
                "Search SA Alpha Picks articles. Returns article list with title, "
                "date, ticker, type (analysis/recap/webinar/commentary/removal), "
                "and comment count. Use get_sa_article_detail for full content."
            ),
            function=get_sa_articles,
            category="portfolio",
            requires_dal=True,
            parameters=[
                ToolParameter("ticker", "string",
                              "Filter by stock ticker (e.g. NVDA)",
                              required=False),
                ToolParameter("keyword", "string",
                              "Full-text search in title and body",
                              required=False),
                ToolParameter("article_type", "string",
                              "Filter by type",
                              required=False,
                              enum=["analysis", "recap", "webinar", "commentary", "removal"]),
                ToolParameter("limit", "integer",
                              "Max results (default 10)",
                              required=False, default=10),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sa_article_detail",
            description=(
                "Get full SA Alpha Picks article content + comments. "
                "Returns body as Markdown + nested comment tree."
            ),
            function=get_sa_article_detail,
            category="portfolio",
            requires_dal=True,
            parameters=[
                ToolParameter("article_id", "string",
                              "Article ID (from get_sa_articles results)"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sa_market_news",
            description=(
                "Search recent Seeking Alpha market-news feed items captured by the "
                "Chrome extension. Returns metadata only: title, URL, publish time, "
                "tickers, summary, and comment count."
            ),
            function=get_sa_market_news,
            category="news",
            requires_dal=True,
            parameters=[
                ToolParameter("ticker", "string",
                              "Filter by mentioned ticker (e.g. NVDA)",
                              required=False),
                ToolParameter("keyword", "string",
                              "Full-text search in title and summary",
                              required=False),
                ToolParameter("limit", "integer",
                              "Max results (default 20, max 100)",
                              required=False, default=20),
            ],
        ))

        self.register(ToolDefinition(
            name="list_high_value_comments",
            description=(
                "List high-scoring SA comments within a time window. "
                "Reads sa_comment_signals (rule-based extraction). "
                "Each comment carries ticker_mentions, candidate_mentions "
                "(off-universe candidates), keyword_buckets (with matched "
                "terms), high_value_score (0-10), and needs_verification "
                "(claim with hedging language). Use this to surface community "
                "signals — earnings hints, eligibility queries, catalyst chatter."
            ),
            function=list_high_value_comments,
            category="news",
            requires_dal=True,
            parameters=[
                ToolParameter("window_days", "integer",
                              "Lookback window in days (1-90, default 7)",
                              required=False, default=7),
                ToolParameter("ticker", "string",
                              "Filter by ticker_mentions membership (case-insensitive)",
                              required=False),
                ToolParameter("min_score", "number",
                              "Minimum high_value_score (default 2.0)",
                              required=False, default=2.0),
                ToolParameter("limit", "integer",
                              "Max comments returned (1-50, default 20)",
                              required=False, default=20),
            ],
        ))


    def _register_macro_calendar_tools(self) -> None:
        """Register the two read-only macro_calendar tools (P1.2 commit 6)."""
        from .macro_calendar_tools import get_economic_calendar, get_macro_value

        self.register(ToolDefinition(
            name="get_economic_calendar",
            description=(
                "List recent + upcoming economic-calendar events (CPI, FOMC, "
                "GDP, unemployment, etc.) from Finnhub's free economic "
                "calendar, persisted via the macro_calendar layer. Each row "
                "carries country, event_time (UTC), impact, actual / "
                "estimate / prev. Pass as_of (ISO timestamp) for lookahead-"
                "safe replay — events first observed AFTER as_of are "
                "excluded entirely. Requires macro_calendar.enabled=true."
            ),
            function=get_economic_calendar,
            category="analysis",
            requires_dal=True,
            parameters=[
                ToolParameter(
                    "country", "string",
                    "ISO 2-letter country code (e.g. US, CN). CSV like 'US,CN' supported.",
                    required=False,
                ),
                ToolParameter(
                    "importance", "string",
                    "Filter by impact level. CSV supported.",
                    required=False, enum=["low", "medium", "high"],
                ),
                ToolParameter(
                    "days_back", "integer",
                    "Window start = today - days_back (default 7).",
                    required=False, default=7,
                ),
                ToolParameter(
                    "days_forward", "integer",
                    "Window end = today + days_forward (default 14).",
                    required=False, default=14,
                ),
                ToolParameter(
                    "as_of", "string",
                    "ISO-8601 timestamp for vintage replay; omit for current view.",
                    required=False,
                ),
                ToolParameter(
                    "limit", "integer",
                    "Hard cap on rows (1-500, default 50).",
                    required=False, default=50,
                ),
            ],
        ))

        self.register(ToolDefinition(
            name="get_macro_value",
            description=(
                "Point-in-time macro lookup. Returns the value of a FRED "
                "series for a specific observation_date, optionally "
                "constrained by an as_of vintage (ALFRED replay). Use this "
                "to read CPI / FFR / GDP / unemployment / yield-spread "
                "values lookahead-safely from a backtest perspective. "
                "Requires macro_calendar.enabled=true."
            ),
            function=get_macro_value,
            category="analysis",
            requires_dal=True,
            parameters=[
                ToolParameter(
                    "series_id", "string",
                    "FRED series id (e.g. CPIAUCNS, FEDFUNDS, GDP, UNRATE, DGS10).",
                ),
                ToolParameter(
                    "observation_date", "string",
                    "ISO YYYY-MM-DD — the date the value REFERS to "
                    "(e.g. '2024-03-01' for March 2024 CPI).",
                ),
                ToolParameter(
                    "as_of", "string",
                    "ISO YYYY-MM-DD — caller's effective vintage date. "
                    "Omit for current value.",
                    required=False,
                ),
            ],
        ))


def create_default_registry() -> ToolRegistry:
    """Create and return a registry with all built-in tools registered."""
    registry = ToolRegistry()
    registry.register_all()
    return registry
