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

from .result_policy import PUBLIC_JSON, PUBLIC_TEXT, ResultPolicy


@dataclass
class ToolParameter:
    """Single parameter definition for a tool."""
    name: str
    type: str  # "string", "integer", "number", "boolean", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    items: Optional[dict] = None


@dataclass
class ToolDefinition:
    """Complete definition of a tool function."""
    name: str
    description: str
    function: Callable
    parameters: List[ToolParameter] = field(default_factory=list)
    category: str = "general"
    requires_dal: bool = True  # Whether first arg is DataAccessLayer
    result_policy: ResultPolicy | None = None


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
                if p.items is not None:
                    prop["items"] = p.items
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
                if p.items is not None:
                    prop["items"] = p.items
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
        self._register_financial_calculation_tools()
        self._register_news_event_tools()
        self._register_analysis_tools()
        self._register_sec_research_tools()
        self._register_security_lifecycle_tools()
        self._register_portfolio_tools()
        self._register_report_tools()
        self._register_memory_tools()
        self._register_web_tools()
        self._register_monitor_tools()
        self._register_freshness_tools()
        self._register_sa_tools()
        self._register_macro_calendar_tools()

    def _register_news_tools(self) -> None:
        from .news_tools import (
            get_ticker_news,
            search_news_by_keyword,
            get_news_brief,
            search_news_advanced,
        )

        self.register(ToolDefinition(
            name="get_ticker_news",
            result_policy=PUBLIC_JSON,
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
                ToolParameter(
                    "source",
                    "string",
                    "Data source (auto, ibkr, or massive)",
                    required=False,
                    default="auto",
                    enum=["auto", "ibkr", "massive"],
                ),
                ToolParameter("limit", "integer", "Max articles to return (1-500, default 20)", required=False, default=20),
            ],
        ))

        self.register(ToolDefinition(
            name="search_news_by_keyword",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description=(
                "Get a lightweight news overview for multiple tickers: "
                "article count and date range. "
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
            result_policy=PUBLIC_JSON,
            description=(
                "Advanced news search combining full-text search + multi-ticker + "
                "date range. Use for cross-ticker theme searches "
                "(e.g. 'tariff impact' across AI_CHIPS sector). All filtering at DB level."
            ),
            function=search_news_advanced,
            category="news",
            parameters=[
                ToolParameter("query", "string", "Full-text search query", required=False, default=""),
                ToolParameter("tickers", "array", "Filter by multiple tickers", required=False),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("limit", "integer", "Max articles to return (default: 20)", required=False, default=20),
            ],
        ))

    def _register_price_tools(self) -> None:
        from .current_quote import get_current_quote
        from .price_tools import (
            get_ticker_prices,
            get_price_change,
            get_sector_performance,
        )

        self.register(ToolDefinition(
            name="get_current_quote",
            result_policy=PUBLIC_JSON,
            description=(
                "Get a read-through current quote for a stock ticker. Uses IBKR snapshot "
                "when available; source='auto' may fall back to the latest local bar, "
                "explicitly marked as local_last_bar."
            ),
            function=get_current_quote,
            category="prices",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("source", "string", "Quote source", required=False, default="auto",
                              enum=["auto", "ibkr", "local"]),
            ],
        ))

        self.register(ToolDefinition(
            name="get_ticker_prices",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description="Calculate average performance of all tickers in a sector.",
            function=get_sector_performance,
            category="prices",
            parameters=[
                ToolParameter("sector", "string", "Sector name (e.g. AI_CHIPS, FINTECH, EV)"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=7),
            ],
        ))

    def _register_options_tools(self) -> None:
        from .options_tools import calculate_greeks
        from .option_chain_tools import get_option_chain
        from .iv_skew_tools import get_iv_skew_analysis

        self.register(ToolDefinition(
            name="calculate_greeks",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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

    def _register_financial_calculation_tools(self) -> None:
        from .financial_calculation_tools import (
            calculate_compound_growth,
            calculate_dcf,
            calculate_implied_valuation,
            calculate_peer_statistics,
            calculate_weighted_scenarios,
        )

        self.register(ToolDefinition(
            name="calculate_compound_growth",
            result_policy=PUBLIC_JSON,
            description=(
                "Calculate total change and compound annual or period growth "
                "from explicit positive start/end values."
            ),
            function=calculate_compound_growth,
            category="calculation",
            requires_dal=False,
            parameters=[
                ToolParameter("start_value", "number", "Positive starting value"),
                ToolParameter("end_value", "number", "Positive ending value"),
                ToolParameter("periods", "number", "Positive number of periods"),
            ],
        ))
        self.register(ToolDefinition(
            name="calculate_dcf",
            result_policy=PUBLIC_JSON,
            description=(
                "Discount an explicit free-cash-flow projection, calculate a "
                "perpetuity-growth terminal value, and bridge enterprise value "
                "to equity and optional per-share value."
            ),
            function=calculate_dcf,
            category="calculation",
            requires_dal=False,
            parameters=[
                ToolParameter("free_cash_flows", "array", "Ordered projected FCF values"),
                ToolParameter("discount_rate", "number", "Decimal discount rate, e.g. 0.10"),
                ToolParameter("terminal_growth_rate", "number", "Decimal terminal growth rate below the discount rate"),
                ToolParameter("cash", "number", "Cash in the same units as FCF", required=False, default=0.0),
                ToolParameter("total_debt", "number", "Debt in the same units as FCF", required=False, default=0.0),
                ToolParameter("shares_outstanding", "number", "Positive shares in compatible units", required=False),
                ToolParameter("current_price", "number", "Positive current price for upside/downside", required=False),
            ],
        ))
        self.register(ToolDefinition(
            name="calculate_peer_statistics",
            result_policy=PUBLIC_JSON,
            description=(
                "Calculate auditable peer mean, median, range, quartiles, "
                "dispersion, and population-z-score outliers."
            ),
            function=calculate_peer_statistics,
            category="calculation",
            requires_dal=False,
            parameters=[
                ToolParameter("values", "array", "Finite comparable peer metric values"),
                ToolParameter("target_value", "number", "Optional target metric for premium to median", required=False),
            ],
        ))
        self.register(ToolDefinition(
            name="calculate_implied_valuation",
            result_policy=PUBLIC_JSON,
            description=(
                "Apply explicit peer multiples to a target metric while keeping "
                "enterprise-value and equity-value bases distinct."
            ),
            function=calculate_implied_valuation,
            category="calculation",
            requires_dal=False,
            parameters=[
                ToolParameter("target_metric", "number", "Positive target financial metric"),
                ToolParameter("multiples", "array", "Positive valuation multiples"),
                ToolParameter(
                    "value_basis",
                    "string",
                    "Whether the multiple yields enterprise or equity value",
                    enum=["enterprise_value", "equity_value"],
                ),
                ToolParameter("cash", "number", "Cash for EV-to-equity bridge", required=False, default=0.0),
                ToolParameter("total_debt", "number", "Debt for EV-to-equity bridge", required=False, default=0.0),
                ToolParameter("shares_outstanding", "number", "Positive shares for per-share value", required=False),
                ToolParameter("current_price", "number", "Positive current price for upside/downside", required=False),
            ],
        ))
        self.register(ToolDefinition(
            name="calculate_weighted_scenarios",
            result_policy=PUBLIC_JSON,
            description=(
                "Calculate a probability-weighted value from explicit scenario "
                "values and weights that sum to one."
            ),
            function=calculate_weighted_scenarios,
            category="calculation",
            requires_dal=False,
            parameters=[
                ToolParameter("values", "array", "Scenario values"),
                ToolParameter("weights", "array", "Nonnegative probabilities summing to 1"),
                ToolParameter("labels", "array", "Optional labels matching the values", required=False),
                ToolParameter("current_price", "number", "Positive current price for upside/downside", required=False),
            ],
        ))

    def _register_news_event_tools(self) -> None:
        from .news_event_tools import detect_event_chains, detect_news_volume_anomaly

        self.register(ToolDefinition(
            name="detect_news_volume_anomaly",
            result_policy=PUBLIC_JSON,
            description="Detect a raw news-volume anomaly for a ticker.",
            function=detect_news_volume_anomaly,
            category="news",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("as_of_date", "string", "Anchor date YYYY-MM-DD (default: latest in data)", required=False),
            ],
        ))

        self.register(ToolDefinition(
            name="detect_event_chains",
            result_policy=PUBLIC_JSON,
            description="Detect deterministic event sequences from raw news titles.",
            function=detect_event_chains,
            category="news",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
            ],
        ))

    def _register_sec_research_tools(self) -> None:
        from typing import get_args, get_origin, get_type_hints
        from .sec_research_tools import list_sec_filings, get_sec_financial_facts, read_sec_filing

        for function in (list_sec_filings, get_sec_financial_facts, read_sec_filing):
            hints = get_type_hints(function)
            parameters = []
            for name, parameter in inspect.signature(function).parameters.items():
                annotation = hints[name]
                variants = get_args(annotation)
                if type(None) in variants:
                    annotation = next(t for t in variants if t is not type(None))
                kind = "array" if get_origin(annotation) is list else {str: "string", int: "integer", bool: "boolean"}[annotation]
                required = parameter.default is inspect.Parameter.empty
                parameters.append(ToolParameter(name, kind, name.replace("_", " "),
                    required=required, default=None if required else parameter.default,
                    enum={"freshness": ["auto", "stored", "refresh"],
                          "period": ["all", "instant", "annual", "quarterly", "ytd"],
                          "revisions": ["latest", "all"]}.get(name),
                    items={"type": "string"} if kind == "array" else None))
            self.register(ToolDefinition(name=function.__name__, description=inspect.getdoc(function),
                function=function, category="analysis", requires_dal=False, parameters=parameters))

    def _register_analysis_tools(self) -> None:
        from .analysis_tools import (
            get_fundamentals_analysis,
            get_detailed_financials,
            get_peer_comparison,
            get_watchlist_overview,
            get_morning_brief,
        )
        from .sec_tools import get_insider_trades

        self.register(ToolDefinition(
            name="get_fundamentals_analysis",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description=(
                "Get comprehensive financial metrics for valuation: "
                "EV/EBITDA, EV/Revenue, PEG, ROIC, FCF yield, margins, growth, "
                "tech-specific (SBC/Revenue, R&D/Revenue, Rule of 40), "
                "and earnings surprise. "
                "Static SEC facts plus a qualified local completed-session price, or typed unavailable."
            ),
            function=get_detailed_financials,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_insider_trades",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description="Get a summary of all watchlist tickers' current status (price, sentiment, IV).",
            function=get_watchlist_overview,
            category="analysis",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_morning_brief",
            result_policy=PUBLIC_JSON,
            description="Generate a personalized morning briefing with holdings, sector highlights, and notable news.",
            function=get_morning_brief,
            category="analysis",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_peer_comparison",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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

    def _register_security_lifecycle_tools(self) -> None:
        from .security_lifecycle_tools import (
            get_security_lifecycle_review,
            list_security_lifecycle_reviews,
        )

        self.register(ToolDefinition(
            name="list_security_lifecycle_reviews",
            result_policy=PUBLIC_JSON,
            description=(
                "List current tracking exceptions or their history, with actual collection "
                "state, listing/continuation findings, missing checks and next actions. "
                "Healthy listings are summarized. Performs no provider request or write."
            ),
            function=list_security_lifecycle_reviews,
            category="analysis",
            requires_dal=False,
            parameters=[
                ToolParameter(
                    "ticker",
                    "string",
                    "Optional ticker filter.",
                    required=False,
                ),
                ToolParameter(
                    "view",
                    "string",
                    "Attention or historical reviews (default attention).",
                    required=False,
                    default="attention",
                    enum=["attention", "history"],
                ),
                ToolParameter(
                    "limit",
                    "integer",
                    "Maximum reviews to return (1-200, default 50).",
                    required=False,
                    default=50,
                ),
                ToolParameter("offset", "integer", "Pagination offset (default 0).", required=False, default=0),
            ],
        ))
        self.register(ToolDefinition(
            name="get_security_lifecycle_review",
            result_policy=PUBLIC_JSON,
            description=(
                "Read one current review by review_id from the review list, including "
                "source checks and current application state. Reading is not approval. "
                "Performs no provider request or write."
            ),
            function=get_security_lifecycle_review,
            category="analysis",
            requires_dal=False,
            parameters=[
                ToolParameter("review_id", "string", "Security-lifecycle review ID from the review list."),
            ],
        ))

    def _register_portfolio_tools(self) -> None:
        from .portfolio_tools import get_portfolio_analysis
        from .portfolio_holdings_tools import get_portfolio_holdings

        self.register(ToolDefinition(
            name="get_portfolio_analysis",
            result_policy=PUBLIC_JSON,
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
        self.register(ToolDefinition(
            name="get_portfolio_holdings",
            result_policy=PUBLIC_JSON,
            description=(
                "Read the user's local portfolio holdings from profile_state.db. "
                "This is a local read-only snapshot; it never calls IBKR and never syncs."
            ),
            function=get_portfolio_holdings,
            category="portfolio",
            requires_dal=False,
            parameters=[
                ToolParameter("account_id", "integer", "Optional portfolio account id", required=False),
                ToolParameter("include_closed", "boolean", "Include closed/archived positions", required=False),
            ],
        ))

    def _register_report_tools(self) -> None:
        from .report_tools import save_report, list_reports, get_report

        self.register(ToolDefinition(
            name="save_report",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description="Delete a memory by its ID.",
            function=delete_memory,
            category="memory",
            parameters=[
                ToolParameter("memory_id", "integer", "Memory ID to delete"),
            ],
        ))

    def _register_web_tools(self) -> None:
        from .web_tools import web_browse

        self.register(ToolDefinition(
            name="web_browse",
            result_policy=PUBLIC_JSON,
            description=(
                "Browse a URL with headless Chromium browser (Playwright). "
                "Reads a known JavaScript-rendered page. "
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

    def _register_monitor_tools(self) -> None:
        from .monitor_tools import scan_alerts

        self.register(ToolDefinition(
            name="scan_alerts",
            result_policy=PUBLIC_TEXT,
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
        from .data_coverage_tools import get_ticker_data_coverage

        self.register(ToolDefinition(
            name="check_data_freshness",
            result_policy=PUBLIC_TEXT,
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

        self.register(ToolDefinition(
            name="get_ticker_data_coverage",
            result_policy=PUBLIC_JSON,
            description=(
                "Explain local market-data coverage for one ticker. Reports latest "
                "local price/news/IV/fundamentals dates and, for a target date, "
                "whether missing price bars are expected (weekend/US market holiday) "
                "or a local data gap. Read-only; never fetches provider data."
            ),
            function=get_ticker_data_coverage,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("target_date", "string", "Optional YYYY-MM-DD date to explain price coverage for", required=False),
            ],
            requires_dal=False,
        ))


    def _register_sa_tools(self) -> None:
        from .sa_tools import (
            get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
            get_sa_articles, get_sa_article_detail, get_sa_market_news,
            list_high_value_comments, get_sa_comment_focus, get_sa_feed,
        )
        from .sa_digest_tools import get_sa_digest

        self.register(ToolDefinition(
            name="get_sa_alpha_picks",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
            description=(
                "Return the cached Seeking Alpha Alpha Picks state (current + "
                "closed picks, freshness) plus a refresh_hint. Read-only status: "
                "the actual refresh is done by the Chrome extension; this tool "
                "does not scrape, write config, or change the watchlist."
            ),
            function=refresh_sa_alpha_picks,
            category="portfolio",
            requires_dal=True,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_sa_articles",
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            result_policy=PUBLIC_JSON,
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
            name="get_sa_digest",
            result_policy=PUBLIC_JSON,
            description=(
                "Return a deterministic SA evidence pack for one ticker — composes "
                "sa_articles (Alpha Picks articles) + sa_market_news (feed items "
                "with comments_count >= 10) + sa_comment_signals (Stage 1 rule-based "
                "scoring) over a configurable window. Output keys: recent_articles, "
                "high_discussion_news, high_value_comments.{ticker_mentions, "
                "candidate_mentions}, data_quality, source_notes. needs_verification "
                "rows pass through — treat as investor opinion needing audit, not "
                "verified fact. No internal LLM call; agent produces any summary in "
                "its own context. Requires SA layer enabled."
            ),
            function=get_sa_digest,
            category="news",
            requires_dal=True,
            parameters=[
                ToolParameter("ticker", "string",
                              "Symbol (case-insensitive)."),
                ToolParameter("days", "integer",
                              "Lookback window 1-90 (default 14).",
                              required=False, default=14),
                ToolParameter("max_articles", "integer",
                              "Cap on recent_articles 1-20 (default 5).",
                              required=False, default=5),
                ToolParameter("max_news", "integer",
                              "Cap on high_discussion_news 1-20 (default 5).",
                              required=False, default=5),
                ToolParameter("max_comments", "integer",
                              "Per-kind cap on comments 1-30 (default 8). Total "
                              "comments returned <= 2 * max_comments.",
                              required=False, default=8),
                ToolParameter("min_comment_score", "number",
                              "Stage 1 high_value_score floor 0.0-10.0 "
                              "(default 4.0). Out-of-range values are clamped.",
                              required=False, default=4.0),
            ],
        ))

        self.register(ToolDefinition(
            name="list_high_value_comments",
            result_policy=PUBLIC_JSON,
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

        self.register(ToolDefinition(
            name="get_sa_comment_focus",
            result_policy=PUBLIC_JSON,
            description=(
                "Cross-ticker view of what the Seeking Alpha COMMENT crowd is "
                "focused on lately — a deterministic, rule-based aggregation over "
                "sa_comment_signals (NOT LLM sentiment). Answers 'what is SA "
                "discussing recently': ranks top_tickers by recent high-value "
                "comment attention (sum_score desc, mention_count desc), the "
                "top_keyword_buckets driving it, and candidate_watch (off-universe "
                "tickers gaining mentions). Every figure is traceable — each sample "
                "carries comment_row_id/comment_id/article_id/url/score/preview. "
                "Use this for portfolio-wide community-attention questions; use "
                "get_sa_digest for ONE ticker. Reads the local sa_capture.db. "
                "Returns empty_reason (e.g. extraction_backlog_pending, "
                "no_comment_above_min_score) so empty != 'no attention'."
            ),
            function=get_sa_comment_focus,
            category="news",
            requires_dal=True,
            parameters=[
                ToolParameter("window_days", "integer",
                              "Lookback over comment_date (1-90, default 14)",
                              required=False, default=14),
                ToolParameter("min_score", "number",
                              "high_value_score floor (default 2.0, clamped >= 0)",
                              required=False, default=2.0),
                ToolParameter("limit", "integer",
                              "Max tickers / candidates / buckets (1-50, default 10)",
                              required=False, default=10),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sa_feed",
            result_policy=PUBLIC_JSON,
            description=(
                "Unified Seeking Alpha evidence feed — SA analysis articles + "
                "market-news items in ONE newest-first, paginated list with "
                "per-type/per-day facets. Score-free; reads the local sa_capture.db. "
                "Use to pull recent SA coverage for a ticker or topic as evidence, "
                "then cite item url / detail_route. q uses FTS5 (short or symbol "
                "queries fall back to LIKE); ticker filters by mention; item_type = "
                "article | market_news. Each item: type, title, tickers, "
                "published_at, url, snippet, has_detail, comments_count, detail_route. "
                "For per-ticker comment attention use get_sa_comment_focus; for one "
                "article's body+comments use get_sa_article_detail."
            ),
            function=get_sa_feed,
            category="news",
            requires_dal=True,
            parameters=[
                ToolParameter("q", "string",
                              "Search terms (FTS5; short/symbol queries → LIKE)",
                              required=False),
                ToolParameter("ticker", "string",
                              "Filter by mentioned ticker", required=False),
                ToolParameter("item_type", "string", "Filter item type",
                              required=False, enum=["article", "market_news"]),
                ToolParameter("days", "integer",
                              "Lookback window (1-3650, default 30)",
                              required=False, default=30),
                ToolParameter("limit", "integer",
                              "Max items (1-200, default 50)",
                              required=False, default=50),
                ToolParameter("offset", "integer",
                              "Pagination offset (default 0)", required=False, default=0),
            ],
        ))


    def _register_macro_calendar_tools(self) -> None:
        """Register the two read-only macro_calendar tools (P1.2 commit 6)."""
        from .macro_calendar_tools import get_economic_calendar, get_macro_value

        self.register(ToolDefinition(
            name="get_economic_calendar",
            result_policy=PUBLIC_TEXT,
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
                    "Filter by impact level: 'low', 'medium', 'high'. "
                    "CSV multi-select like 'high,medium' supported.",
                    required=False,
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
                    "ISO-8601 date or timestamp for vintage replay. Date "
                    "inputs (YYYY-MM-DD) are interpreted as end-of-day UTC. "
                    "Omit for current view.",
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
            result_policy=PUBLIC_TEXT,
            description=(
                "Point-in-time macro lookup. Returns the value of a FRED "
                "series for a specific observation_date, optionally "
                "constrained by an as_of vintage (ALFRED replay). Use this "
                "to read CPI / FFR / GDP / unemployment / yield-spread "
                "values lookahead-safely from a backtest perspective. Reads "
                "the local FRED snapshot even when automatic refresh is disabled."
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
