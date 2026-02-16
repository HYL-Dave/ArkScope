"""
Anthropic SDK tool definitions and execution.

Provides tool schemas in Anthropic format and execute_tool() for dispatching.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.tools.data_access import DataAccessLayer

logger = logging.getLogger(__name__)


def get_anthropic_tools() -> List[Dict[str, Any]]:
    """
    Get tool definitions in Anthropic format.

    Returns list of tool schemas for messages.create(tools=[...]).
    Web tools (tavily_search, tavily_fetch, web_browse) are conditionally
    included based on AgentConfig flags.
    """
    from ..config import get_agent_config
    config = get_agent_config()

    tools = [
        # News Tools
        {
            "name": "get_ticker_news",
            "description": "Get recent news articles for a stock ticker. Returns up to `limit` most recent articles (default 20). The response includes `count` (total available) so you know if more exist.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g. NVDA, AMD)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    },
                    "source": {
                        "type": "string",
                        "enum": ["auto", "ibkr", "polygon"],
                        "description": "Data source (default: auto)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max articles to return, 1-500 (default: 50)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_news_sentiment_summary",
            "description": "Get aggregated sentiment statistics (mean, bullish/bearish ratio) for a ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 7)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "search_news_by_keyword",
            "description": "Search news articles by keyword in titles and descriptions. Returns up to `limit` most recent matches (default 20).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Search keyword"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    },
                    "ticker": {
                        "type": "string",
                        "description": "Optionally filter by ticker"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max articles to return, 1-500 (default: 50)"
                    }
                },
                "required": ["keyword"]
            }
        },
        # Price Tools
        {
            "name": "get_ticker_prices",
            "description": "Get OHLCV price bars for a stock ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "interval": {
                        "type": "string",
                        "enum": ["15min", "1h", "1d"],
                        "description": "Bar interval (default: 15min)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_price_change",
            "description": "Calculate price change percentage and high/low range for a ticker over a period.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 7)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_sector_performance",
            "description": "Calculate average performance of all tickers in a sector.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sector": {
                        "type": "string",
                        "description": "Sector name (e.g. AI_CHIPS, FINTECH, EV, SPACE)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 7)"
                    }
                },
                "required": ["sector"]
            }
        },
        # Options Tools
        {
            "name": "get_iv_analysis",
            "description": "Full implied volatility analysis: IV rank, percentile, VRP, and trading signal.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_iv_history_data",
            "description": "Get raw IV history data points (ATM IV, HV, VRP) for a ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "scan_mispricing",
            "description": "Scan for mispriced options comparing theoretical vs market prices.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ticker symbols to scan"
                    },
                    "mispricing_threshold_pct": {
                        "type": "number",
                        "description": "Minimum mispricing % to report (default: 10.0)"
                    },
                    "min_confidence": {
                        "type": "string",
                        "enum": ["HIGH", "MEDIUM", "LOW"],
                        "description": "Minimum confidence level (default: MEDIUM)"
                    }
                },
                "required": ["tickers"]
            }
        },
        {
            "name": "calculate_greeks",
            "description": "Calculate Black-Scholes Greeks (delta, gamma, theta, vega, rho) for an option.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "S": {
                        "type": "number",
                        "description": "Spot price of the underlying"
                    },
                    "K": {
                        "type": "number",
                        "description": "Strike price"
                    },
                    "T": {
                        "type": "number",
                        "description": "Time to expiry in years (e.g. 0.25 for 3 months)"
                    },
                    "r": {
                        "type": "number",
                        "description": "Risk-free rate (e.g. 0.05 for 5%)"
                    },
                    "sigma": {
                        "type": "number",
                        "description": "Volatility (e.g. 0.30 for 30%)"
                    },
                    "option_type": {
                        "type": "string",
                        "enum": ["C", "P"],
                        "description": "Option type: C for call, P for put (default: C)"
                    }
                },
                "required": ["S", "K", "T", "r", "sigma"]
            }
        },
        # Signal Tools
        {
            "name": "detect_anomalies",
            "description": "Detect statistical anomalies in sentiment and news volume for a ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "detect_event_chains",
            "description": "Detect event chain patterns (earnings -> guidance -> analyst reactions).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "synthesize_signal",
            "description": "Synthesize a multi-factor trading signal combining sector momentum, events, and sentiment.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    },
                    "strategy": {
                        "type": "string",
                        "description": "Strategy name for custom weights (from user_profile.yaml)"
                    }
                },
                "required": ["ticker"]
            }
        },
        # Analysis Tools
        {
            "name": "get_fundamentals_analysis",
            "description": "Get fundamental analysis (P/E, ROE, market cap, margins) for a ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_sec_filings",
            "description": "Get SEC filing metadata (10-K, 10-Q, 8-K) for a ticker.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "filing_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by filing types (e.g. ['10-K', '10-Q'])"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_watchlist_overview",
            "description": "Get a summary of all watchlist tickers' current status (price, sentiment, IV).",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "get_morning_brief",
            "description": "Generate a personalized morning briefing with holdings, sector highlights, and notable news.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # Analyst Tools (Phase 11b)
        {
            "name": "get_analyst_consensus",
            "description": (
                "Get analyst consensus for a ticker: recommendation distribution "
                "(buy/hold/sell trend), last 4 quarters earnings (actual vs estimate with "
                "surprise %), upcoming earnings date and estimates, and analyst price "
                "target (if available). Uses Finnhub free API."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        },
        # Execution Tools
        {
            "name": "execute_python_analysis",
            "description": (
                "Execute Python code for custom financial calculations and data analysis. "
                "Provide `code` for direct execution, or `task` for auto code generation "
                "using a coding model with error-correcting retry. "
                "Code runs in isolated subprocess with numpy, pandas, scipy available. "
                "Pass data via data_json (accessible as `data` variable). "
                "Set background=true for long-running tasks (results written to temp file)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute (direct mode)"
                    },
                    "task": {
                        "type": "string",
                        "description": (
                            "Task description for auto code generation with error correction "
                            "(alternative to code)"
                        )
                    },
                    "data_json": {
                        "type": "string",
                        "description": "JSON string of data to inject (accessible as `data` variable)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Execution timeout in seconds (default: 120)"
                    },
                    "background": {
                        "type": "boolean",
                        "description": "Run in background, write results to temp file (default: false)"
                    }
                },
                "required": []
            }
        },
        # Subagent Delegation
        {
            "name": "delegate_to_subagent",
            "description": (
                "Delegate a subtask to a specialized subagent. Each subagent has its own "
                "model, system prompt, and tool subset. Returns structured JSON results. "
                "Use for complex calculations (code_analyst), deep multi-source investigation "
                "(deep_researcher), or fast bulk summarization (data_summarizer)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "subagent": {
                        "type": "string",
                        "enum": ["code_analyst", "deep_researcher", "data_summarizer"],
                        "description": (
                            "Subagent to delegate to: "
                            "code_analyst (quantitative Python analysis), "
                            "deep_researcher (multi-source investigation), "
                            "data_summarizer (fast bulk summarization)"
                        )
                    },
                    "task": {
                        "type": "string",
                        "description": "Natural language task description for the subagent"
                    },
                    "context_json": {
                        "type": "string",
                        "description": "Optional JSON data context from earlier tool calls (max 5000 chars)"
                    }
                },
                "required": ["subagent", "task"]
            }
        },
    ]

    # ── Conditional web tools (Phase 10) ─────────────────────────
    if config.web_tavily:
        tools.extend([
            {
                "name": "tavily_search",
                "description": (
                    "Search the web for real-time information using Tavily. "
                    "Returns AI summary and ranked results with relevance scores. "
                    "Use topic='finance' for financial queries, topic='news' for current events."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Max results 1-10 (default: 5)"},
                        "search_depth": {"type": "string", "enum": ["basic", "advanced"],
                                         "description": "basic (1 credit) or advanced (2 credits)"},
                        "topic": {"type": "string", "enum": ["general", "news", "finance"],
                                  "description": "Search topic category (default: general)"},
                        "days": {"type": "integer",
                                 "description": "Limit to results from last N days (0=no limit)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "tavily_fetch",
                "description": (
                    "Fetch and extract content from a specific URL using Tavily. "
                    "Supports pagination via offset/max_chars for long pages. "
                    "Check was_truncated and use offset to read more."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch content from"},
                        "extract_depth": {"type": "string", "enum": ["basic", "advanced"],
                                          "description": "Extraction depth (default: basic)"},
                        "offset": {"type": "integer",
                                   "description": "Start position in chars for pagination (default: 0)"},
                        "max_chars": {"type": "integer",
                                      "description": "Max chars to return per call (default: 3000)"},
                    },
                    "required": ["url"],
                },
            },
        ])
    if config.web_playwright:
        tools.append({
            "name": "web_browse",
            "description": (
                "Browse a URL with headless Chromium browser (Playwright). "
                "Handles JavaScript-rendered pages that Tavily cannot extract. "
                "Supports pagination via offset/max_chars."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to browse"},
                    "wait_for": {"type": "string",
                                 "enum": ["networkidle", "load", "domcontentloaded"],
                                 "description": "Page load wait strategy (default: networkidle)"},
                    "extract_links": {"type": "boolean",
                                      "description": "Also extract page links (default: false)"},
                    "offset": {"type": "integer",
                               "description": "Start position in chars for pagination (default: 0)"},
                    "max_chars": {"type": "integer",
                                  "description": "Max chars to return per call (default: 5000)"},
                },
                "required": ["url"],
            },
        })

    return tools


def _serialize_result(result: Any) -> str:
    """Serialize result to JSON string for LLM consumption."""
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), default=str)
    elif isinstance(result, list) and result and hasattr(result[0], "model_dump"):
        return json.dumps([r.model_dump() for r in result], default=str)
    elif isinstance(result, dict):
        return json.dumps(result, default=str)
    else:
        return str(result)


def _dispatch_subagent(tool_input: Dict[str, Any], dal: "DataAccessLayer") -> Dict:
    """Dispatch to a specialized subagent (Phase 6)."""
    from src.agents.shared.subagent import dispatch_subagent
    return dispatch_subagent(
        subagent_name=tool_input["subagent"],
        task=tool_input["task"],
        context_json=tool_input.get("context_json", ""),
        dal=dal,
    )


def execute_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    dal: "DataAccessLayer"
) -> str:
    """
    Execute a tool by name with given input.

    Args:
        tool_name: Name of the tool to execute
        tool_input: Input parameters as dict
        dal: DataAccessLayer instance

    Returns:
        JSON string result
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
        get_sec_filings,
        get_watchlist_overview,
        get_morning_brief,
    )
    from src.tools.code_executor import execute_python_code
    from src.tools.web_tools import web_search, web_fetch, web_browse
    from src.tools.analyst_tools import get_analyst_consensus

    # Tool dispatch map
    tool_map = {
        "get_ticker_news": lambda: get_ticker_news(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 30),
            source=tool_input.get("source", "auto"),
            limit=tool_input.get("limit", 20),
        ),
        "get_news_sentiment_summary": lambda: get_news_sentiment_summary(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 7)
        ),
        "search_news_by_keyword": lambda: search_news_by_keyword(
            dal,
            tool_input["keyword"],
            days=tool_input.get("days", 30),
            ticker=tool_input.get("ticker"),
            limit=tool_input.get("limit", 20),
        ),
        "get_ticker_prices": lambda: get_ticker_prices(
            dal,
            tool_input["ticker"],
            interval=tool_input.get("interval", "15min"),
            days=tool_input.get("days", 30)
        ),
        "get_price_change": lambda: get_price_change(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 7)
        ),
        "get_sector_performance": lambda: get_sector_performance(
            dal,
            tool_input["sector"],
            days=tool_input.get("days", 7)
        ),
        "get_iv_analysis": lambda: get_iv_analysis(
            dal,
            tool_input["ticker"]
        ),
        "get_iv_history_data": lambda: get_iv_history_data(
            dal,
            tool_input["ticker"]
        ),
        "scan_mispricing": lambda: scan_mispricing(
            dal,
            tool_input["tickers"],
            mispricing_threshold_pct=tool_input.get("mispricing_threshold_pct", 10.0),
            min_confidence=tool_input.get("min_confidence", "MEDIUM")
        ),
        "calculate_greeks": lambda: calculate_greeks(
            S=tool_input["S"],
            K=tool_input["K"],
            T=tool_input["T"],
            r=tool_input["r"],
            sigma=tool_input["sigma"],
            option_type=tool_input.get("option_type", "C")
        ),
        "detect_anomalies": lambda: detect_anomalies(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 30)
        ),
        "detect_event_chains": lambda: detect_event_chains(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 30)
        ),
        "synthesize_signal": lambda: synthesize_signal(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 30),
            strategy=tool_input.get("strategy")
        ),
        "get_fundamentals_analysis": lambda: get_fundamentals_analysis(
            dal,
            tool_input["ticker"]
        ),
        "get_sec_filings": lambda: get_sec_filings(
            dal,
            tool_input["ticker"],
            filing_types=tool_input.get("filing_types")
        ),
        "get_watchlist_overview": lambda: get_watchlist_overview(dal),
        "get_morning_brief": lambda: get_morning_brief(dal),
        "execute_python_analysis": lambda: execute_python_code(
            code=tool_input.get("code", ""),
            task=tool_input.get("task", ""),
            data_json=tool_input.get("data_json", ""),
            timeout=tool_input.get("timeout", 120),
            background=tool_input.get("background", False),
        ),
        "delegate_to_subagent": lambda: _dispatch_subagent(tool_input, dal),
        # Analyst tools (Phase 11b) — no DAL needed
        "get_analyst_consensus": lambda: get_analyst_consensus(
            ticker=tool_input["ticker"],
        ),
        # Web tools (Phase 10) — no DAL needed
        "tavily_search": lambda: web_search(
            query=tool_input["query"],
            max_results=tool_input.get("max_results", 5),
            search_depth=tool_input.get("search_depth", "basic"),
            topic=tool_input.get("topic", "general"),
            days=tool_input.get("days", 0),
        ),
        "tavily_fetch": lambda: web_fetch(
            url=tool_input["url"],
            extract_depth=tool_input.get("extract_depth", "basic"),
            offset=tool_input.get("offset", 0),
            max_chars=tool_input.get("max_chars", 3000),
        ),
        "web_browse": lambda: web_browse(
            url=tool_input["url"],
            wait_for=tool_input.get("wait_for", "networkidle"),
            extract_links=tool_input.get("extract_links", False),
            offset=tool_input.get("offset", 0),
            max_chars=tool_input.get("max_chars", 5000),
        ),
    }

    if tool_name not in tool_map:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = tool_map[tool_name]()
        return _serialize_result(result)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})