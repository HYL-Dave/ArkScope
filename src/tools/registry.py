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
        """Register all 17 built-in tool functions."""
        self._register_news_tools()
        self._register_price_tools()
        self._register_options_tools()
        self._register_signal_tools()
        self._register_analysis_tools()

    def _register_news_tools(self) -> None:
        from .news_tools import (
            get_ticker_news,
            get_news_sentiment_summary,
            search_news_by_keyword,
        )

        self.register(ToolDefinition(
            name="get_ticker_news",
            description="Get recent news articles for a stock ticker with sentiment and risk scores.",
            function=get_ticker_news,
            category="news",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol (e.g. NVDA)"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("source", "string", "Data source", required=False, default="auto",
                              enum=["auto", "ibkr", "polygon"]),
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
            description="Search news articles by keyword in titles and descriptions.",
            function=search_news_by_keyword,
            category="news",
            parameters=[
                ToolParameter("keyword", "string", "Search keyword"),
                ToolParameter("days", "integer", "Lookback period in days", required=False, default=30),
                ToolParameter("ticker", "string", "Optionally filter by ticker", required=False),
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
            description="Calculate Black-Scholes Greeks (delta, gamma, theta, vega, rho) for an option.",
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
            ],
        ))

    def _register_signal_tools(self) -> None:
        from .signal_tools import (
            detect_anomalies,
            detect_event_chains,
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
            ],
        ))

    def _register_analysis_tools(self) -> None:
        from .analysis_tools import (
            get_fundamentals_analysis,
            get_sec_filings,
            get_watchlist_overview,
            get_morning_brief,
        )

        self.register(ToolDefinition(
            name="get_fundamentals_analysis",
            description="Get fundamental analysis (P/E, ROE, market cap, margins) for a ticker.",
            function=get_fundamentals_analysis,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
            ],
        ))

        self.register(ToolDefinition(
            name="get_sec_filings",
            description="Get SEC filing metadata (10-K, 10-Q, 8-K) for a ticker.",
            function=get_sec_filings,
            category="analysis",
            parameters=[
                ToolParameter("ticker", "string", "Stock ticker symbol"),
                ToolParameter("filing_types", "array",
                              "Filter by filing types (e.g. ['10-K', '10-Q'])",
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


def create_default_registry() -> ToolRegistry:
    """Create and return a registry with all 17 tools registered."""
    registry = ToolRegistry()
    registry.register_all()
    return registry