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
                        "description": "Max articles to return, 1-500 (default: 20)"
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
            "description": "Search news articles by keyword using full-text search. Returns up to `limit` most recent matches.",
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
                        "description": "Max articles to return, 1-500 (default: 20)"
                    }
                },
                "required": ["keyword"]
            }
        },
        # News Tools — Smart Data Retrieval
        {
            "name": "get_news_brief",
            "description": (
                "Get a lightweight news overview for multiple tickers: "
                "article count, avg sentiment, avg risk, date range. "
                "Call this FIRST before get_ticker_news() to decide which "
                "tickers need detailed investigation. Very fast, minimal output."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ticker symbols (default: watchlist)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 7)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "search_news_advanced",
            "description": (
                "Advanced news search combining full-text search + multi-ticker + "
                "date range + score filters. Use for cross-ticker theme searches "
                "(e.g. 'tariff impact' across AI_CHIPS sector). All filtering at DB level."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search query"
                    },
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by multiple tickers"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default: 30)"
                    },
                    "scored_only": {
                        "type": "boolean",
                        "description": "Only return scored articles (default: false)"
                    },
                    "min_sentiment": {
                        "type": "integer",
                        "description": "Minimum sentiment score (1-5)"
                    },
                    "max_risk": {
                        "type": "integer",
                        "description": "Maximum risk score (1-5)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max articles to return (default: 20)"
                    }
                },
                "required": []
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
        {
            "name": "get_option_chain",
            "description": (
                "Get live option chain from IBKR with analysis: "
                "call/put quotes around ATM, P/C ratio (volume + OI), max pain, "
                "OI concentration, IV term structure, and bid-ask quality. "
                "Requires IBKR gateway running. Takes ~30 seconds."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "expiry": {
                        "type": "string",
                        "description": "Target expiration YYYYMMDD (default: nearest with >=7 DTE)"
                    },
                    "num_strikes": {
                        "type": "integer",
                        "description": "Strikes above/below ATM (default: 10)"
                    },
                    "max_expirations_for_term_structure": {
                        "type": "integer",
                        "description": "Expirations for IV term structure (default: 6)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_iv_skew_analysis",
            "description": (
                "Analyze IV skew from live option chain: call-put skew, "
                "smile/smirk shape classification, 25-delta skew, skew gradient, "
                "and term structure skew across expirations. Requires IBKR gateway."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "expiry": {
                        "type": "string",
                        "description": "Target expiration YYYYMMDD (default: nearest with >=7 DTE)"
                    },
                    "num_strikes": {
                        "type": "integer",
                        "description": "Strikes above/below ATM (default: 10)"
                    }
                },
                "required": ["ticker"]
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
                    },
                    "as_of_date": {
                        "type": "string",
                        "description": "Anchor date YYYY-MM-DD (default: latest date in data)"
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
                    },
                    "as_of_date": {
                        "type": "string",
                        "description": "Anchor date YYYY-MM-DD (default: latest date in data)"
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
            "name": "get_detailed_financials",
            "description": (
                "Get comprehensive financial metrics for valuation: "
                "EV/EBITDA, EV/Revenue, PEG, ROIC, FCF yield, margins, growth, "
                "tech-specific (SBC/Revenue, R&D/Revenue, Rule of 40), "
                "and earnings surprise. IBKR real-time + SEC EDGAR cached."
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
        {
            "name": "get_peer_comparison",
            "description": (
                "Compare a ticker vs sector peers on key metrics: PE, EV/EBITDA, "
                "margins, growth, ROE, ROIC, Rule of 40. Returns comparison matrix, "
                "percentile rankings, and sector medians. Provide ticker (auto-detect "
                "sector), sector name, or explicit tickers list."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Target ticker to rank vs peers"
                    },
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Explicit peer list (overrides sector)"
                    },
                    "sector": {
                        "type": "string",
                        "description": "Sector from sectors.yaml (e.g. AI_CHIPS)"
                    }
                },
                "required": []
            }
        },
        {
            "name": "get_sec_filings",
            "description": (
                "Get SEC filing metadata (10-K, 10-Q, 8-K, etc.) for a ticker. "
                "Returns filing type, date, and URL — metadata only, not content."
            ),
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
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of filings to return (default: 10)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "get_insider_trades",
            "description": (
                "Get recent insider trades (SEC Form 4) for a ticker. Fully parsed: "
                "insider name, title, transaction date, shares (negative=sale), "
                "price, and holdings before/after."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of trades to return (default: 10)"
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
        # Portfolio Tools (Batch 3a)
        {
            "name": "get_portfolio_analysis",
            "description": (
                "Analyze portfolio or watchlist: P&L (if holdings provided), "
                "beta vs SPY, pairwise correlation matrix, and portfolio metrics "
                "(weighted beta, HHI concentration, sector diversification). "
                "Pass holdings dict for full P&L, or tickers for beta/correlation only."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ticker symbols (default: watchlist)"
                    },
                    "holdings": {
                        "type": "object",
                        "description": 'Holdings: {"NVDA": {"qty": 100, "entry_price": 120.50}, ...}'
                    }
                },
                "required": []
            }
        },
        # Earnings Impact (Batch 3c)
        {
            "name": "get_earnings_impact",
            "description": (
                "Analyze historical earnings price reactions: earnings-day moves, "
                "average absolute move, directional bias, surprise correlation, "
                "expected move estimation, and pre/post earnings drift. "
                "Combines Finnhub earnings history with price data."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    },
                    "quarters": {
                        "type": "integer",
                        "description": "Past quarters to analyze (default: 4)"
                    }
                },
                "required": ["ticker"]
            }
        },
        # Execution Tools
        {
            "name": "execute_python_analysis",
            "description": (
                "Run Python for ANY numerical calculation or data analysis. "
                "PREFERRED: pass `task` (natural language) — the system auto-generates "
                "code and retries on errors. Only use `code` for precise hand-crafted "
                "implementations. Do not calculate mentally; always use this tool. "
                "Sandbox with numpy, pandas, scipy. Pass data via data_json."
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
                            "Natural language task description (PREFERRED over code). "
                            "System auto-generates Python and retries on errors."
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
                "Use for multi-step research+compute (code_analyst), deep investigation "
                "(deep_researcher), fast summarization (data_summarizer), or "
                "adversarial review of conclusions (reviewer). "
                "For single calculations with data you already have, use "
                "execute_python_analysis directly instead."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "subagent": {
                        "type": "string",
                        "enum": ["code_analyst", "deep_researcher", "data_summarizer", "reviewer"],
                        "description": (
                            "Subagent to delegate to: "
                            "code_analyst (quantitative Python analysis + autonomous design), "
                            "deep_researcher (multi-source investigation), "
                            "data_summarizer (fast bulk summarization), "
                            "reviewer (critical analysis review, finds flaws/risks)"
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

    if config.web_codex_research:
        tools.append({
            "name": "codex_web_research",
            "description": (
                "Deep web research using Codex CLI with live web browsing. "
                "An autonomous AI research agent that searches multiple sources, "
                "cross-references information, and produces a structured report. "
                "Use for deep investigation (earnings analysis, event research, "
                "competitive landscape). Takes 1-5 minutes."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Research question or topic to investigate"},
                    "context": {"type": "string",
                                "description": "Optional context from earlier tool calls to inform research"},
                    "timeout": {"type": "integer",
                                "description": "Max seconds for research (default: 300)"},
                },
                "required": ["query"],
            },
        })

    # Report tools (Phase B)
    tools.extend([
        {
            "name": "save_report",
            "description": (
                "Save a research report after completing a thorough analysis. "
                "Persists full Markdown content to data/reports/ and metadata to DB. "
                "Call this at the end of any detailed analysis to preserve results for review."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Report title (e.g. 'AFRM Entry Analysis')"},
                    "tickers": {"type": "array", "items": {"type": "string"},
                                "description": "List of analyzed ticker symbols"},
                    "report_type": {"type": "string",
                                    "enum": ["entry_analysis", "sector_review", "earnings_review",
                                             "comparison", "thesis", "morning_brief", "custom"],
                                    "description": "Report category"},
                    "summary": {"type": "string", "description": "1-2 sentence conclusion"},
                    "content": {"type": "string",
                                "description": "Full Markdown report content with analysis details"},
                    "conclusion": {"type": "string",
                                   "enum": ["BUY", "HOLD", "SELL", "WATCH", "NEUTRAL"],
                                   "description": "Trading conclusion"},
                    "confidence": {"type": "number",
                                   "description": "Confidence score 0-1"},
                },
                "required": ["title", "tickers", "report_type", "summary", "content"],
            },
        },
        {
            "name": "list_reports",
            "description": "List saved research reports, optionally filtered by ticker or type.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Filter by ticker symbol"},
                    "days": {"type": "integer", "description": "Lookback period in days (default: 30)"},
                    "report_type": {"type": "string", "description": "Filter by report type"},
                    "limit": {"type": "integer", "description": "Max reports to return (default: 20)"},
                },
                "required": [],
            },
        },
        {
            "name": "get_report",
            "description": "Retrieve a saved research report by ID or file path.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "report_id": {"type": "integer", "description": "Report ID from database"},
                    "file_path": {"type": "string", "description": "Relative path to Markdown file"},
                },
                "required": [],
            },
        },
    ])

    # Memory tools (Phase 15)
    tools.extend([
        {
            "name": "save_memory",
            "description": (
                "Save a piece of knowledge to long-term memory for future recall. "
                "Use after completing analyses, discovering insights, or when the user "
                "asks to remember something. Memories persist across sessions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short descriptive title"},
                    "content": {"type": "string", "description": "Full content to remember (Markdown supported)"},
                    "category": {"type": "string",
                                 "enum": ["analysis", "insight", "preference", "fact", "note"],
                                 "description": "Memory category (default: note)"},
                    "tickers": {"type": "array", "items": {"type": "string"},
                                "description": "Related ticker symbols"},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Free-form tags for categorization"},
                    "importance": {"type": "integer",
                                   "description": "Importance 1-10 (10=critical, 5=normal, 1=trivial)"},
                },
                "required": ["title", "content"],
            },
        },
        {
            "name": "recall_memories",
            "description": (
                "Search long-term memory for relevant past knowledge. "
                "Use when the user references past analyses, asks 'what did we discuss about X', "
                "or when you need context from previous sessions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (keywords or natural language)"},
                    "category": {"type": "string",
                                 "enum": ["analysis", "insight", "preference", "fact", "note"],
                                 "description": "Filter by category"},
                    "tickers": {"type": "array", "items": {"type": "string"},
                                "description": "Filter by related tickers"},
                    "tags": {"type": "array", "items": {"type": "string"},
                             "description": "Filter by tags"},
                    "days": {"type": "integer", "description": "Lookback period in days (default: 90)"},
                    "limit": {"type": "integer", "description": "Max memories to return (default: 10)"},
                },
                "required": [],
            },
        },
        {
            "name": "list_memories",
            "description": "List saved memories (metadata only, no full content).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {"type": "string",
                                 "enum": ["analysis", "insight", "preference", "fact", "note"],
                                 "description": "Filter by category"},
                    "days": {"type": "integer", "description": "Lookback period in days (default: 90)"},
                    "limit": {"type": "integer", "description": "Max memories to return (default: 20)"},
                },
                "required": [],
            },
        },
        {
            "name": "delete_memory",
            "description": "Delete a memory by its ID.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer", "description": "Memory ID to delete"},
                },
                "required": ["memory_id"],
            },
        },
    ])

    # Monitor tools (Phase E1)
    tools.extend([
        {
            "name": "scan_alerts",
            "description": (
                "Scan watchlist or specific tickers for price, sentiment, signal, "
                "and sector alerts based on configured thresholds. "
                "Returns a summary of all triggered alerts."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "string",
                        "description": "Comma-separated ticker symbols (empty = scan full watchlist from config)",
                    },
                },
                "required": [],
            },
        },
        # Data Freshness
        {
            "name": "check_data_freshness",
            "description": (
                "Check health and freshness of all data sources (news, prices, IV, fundamentals). "
                "Returns staleness status, latest data timestamps, and record counts. "
                "Use to verify data quality before analysis."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        # RL Pipeline Tools
        {
            "name": "get_rl_model_status",
            "description": (
                "List all trained RL models (PPO/CPPO) with backtest performance: "
                "Sharpe ratio, information ratio, max drawdown, CVaR. "
                "Shows which models are available for prediction queries."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_rl_prediction",
            "description": (
                "Get RL model trading signal for a ticker. Uses PPO/CPPO model "
                "trained on historical prices + LLM sentiment to produce a "
                "daily-frequency buy/sell/hold signal. Not a trade instruction — "
                "use as one input among many."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol",
                    },
                    "model_id": {
                        "type": "string",
                        "description": "Model ID to use (default: 'latest' = most recent)",
                    },
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_rl_backtest_report",
            "description": (
                "Get detailed backtest report for a trained RL model: "
                "Sharpe, IR, CVaR, max drawdown, win rate, training parameters, "
                "feature set, and train/test periods."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "model_id": {
                        "type": "string",
                        "description": "Model ID (default: 'latest' = most recent)",
                    },
                },
                "required": [],
            },
        },
    ])

    # SA Alpha Picks (Phase 11c)
    tools.extend([
        {
            "name": "get_sa_alpha_picks",
            "description": (
                "Get Seeking Alpha Alpha Picks portfolio. Returns current and/or "
                "closed picks with return %, sector, rating, and freshness metadata."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter: 'all' (default), 'current', or 'closed'",
                        "enum": ["all", "current", "closed"],
                    },
                    "sector": {
                        "type": "string",
                        "description": "Filter by sector prefix (e.g. 'Tech')",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_sa_pick_detail",
            "description": (
                "Get detail report for a specific Alpha Pick. "
                "If picked_date is omitted, returns the latest current (non-stale) pick."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g. NVDA)",
                    },
                    "picked_date": {
                        "type": "string",
                        "description": "Specific pick date (YYYY-MM-DD). Omit for latest.",
                    },
                },
                "required": ["symbol"],
            },
        },
        {
            "name": "refresh_sa_alpha_picks",
            "description": (
                "Force refresh Alpha Picks from Seeking Alpha website. "
                "Scrapes both tabs, updates cache, syncs symbols to watchlist."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        # SA Articles (Phase 11c-v3)
        {
            "name": "get_sa_articles",
            "description": (
                "Search SA Alpha Picks articles. Returns article list with title, "
                "date, ticker, type (analysis/recap/webinar/commentary/removal), "
                "and comment count. Use get_sa_article_detail for full content."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Filter by stock ticker"},
                    "keyword": {"type": "string", "description": "Full-text search in title and body"},
                    "article_type": {"type": "string", "enum": ["analysis", "recap", "webinar", "commentary", "removal"]},
                    "limit": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": [],
            },
        },
        {
            "name": "get_sa_article_detail",
            "description": (
                "Get full SA Alpha Picks article content + comments. "
                "Returns body as Markdown + nested comment tree."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Article ID (from get_sa_articles)"},
                },
                "required": ["article_id"],
            },
        },
        {
            "name": "get_sa_market_news",
            "description": (
                "Search recent Seeking Alpha market-news feed items captured by the "
                "Chrome extension. Returns metadata only: title, URL, publish time, "
                "tickers, summary, and comment count."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Filter by mentioned ticker"},
                    "keyword": {"type": "string", "description": "Full-text search in title and summary"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"},
                },
                "required": [],
            },
        },
        {
            "name": "list_high_value_comments",
            "description": (
                "List high-scoring SA comments within a time window. Reads "
                "sa_comment_signals (rule-based: ticker_mentions, candidate_mentions, "
                "keyword_buckets with matched terms, high_value_score 0-10, "
                "needs_verification). Surfaces community signals like earnings "
                "hints, eligibility queries, and catalyst chatter."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "window_days": {"type": "integer", "description": "Lookback in days (1-90, default 7)"},
                    "ticker": {"type": "string", "description": "Filter by ticker_mentions (case-insensitive)"},
                    "min_score": {"type": "number", "description": "Minimum high_value_score (default 2.0)"},
                    "limit": {"type": "integer", "description": "Max comments returned (1-50, default 20)"},
                },
                "required": [],
            },
        },
    ])

    return tools


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
    from src.tools.option_chain_tools import get_option_chain
    from src.tools.iv_skew_tools import get_iv_skew_analysis
    from src.tools.portfolio_tools import get_portfolio_analysis
    from src.tools.earnings_tools import get_earnings_impact
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
    from src.tools.web_tools import web_search, web_fetch, web_browse, codex_web_research
    from src.tools.analyst_tools import get_analyst_consensus
    from src.tools.report_tools import save_report, list_reports, get_report
    from src.tools.memory_tools import (
        save_memory, recall_memories, list_memories, delete_memory,
    )
    from src.tools.monitor_tools import scan_alerts
    from src.tools.freshness import check_data_freshness
    from src.tools.rl_tools import get_rl_model_status, get_rl_prediction, get_rl_backtest_report
    from src.tools.sa_tools import (
        get_sa_alpha_picks, get_sa_pick_detail, refresh_sa_alpha_picks,
        get_sa_articles, get_sa_article_detail, get_sa_market_news,
        list_high_value_comments,
    )

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
        "get_news_brief": lambda: get_news_brief(
            dal,
            tickers=tool_input.get("tickers"),
            days=tool_input.get("days", 7),
        ),
        "search_news_advanced": lambda: search_news_advanced(
            dal,
            query=tool_input.get("query", ""),
            tickers=tool_input.get("tickers"),
            days=tool_input.get("days", 30),
            scored_only=tool_input.get("scored_only", False),
            min_sentiment=tool_input.get("min_sentiment"),
            max_risk=tool_input.get("max_risk"),
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
        "get_option_chain": lambda: get_option_chain(
            ticker=tool_input["ticker"],
            expiry=tool_input.get("expiry"),
            num_strikes=tool_input.get("num_strikes", 10),
            max_expirations_for_term_structure=tool_input.get(
                "max_expirations_for_term_structure", 6),
        ),
        "detect_anomalies": lambda: detect_anomalies(
            dal,
            tool_input["ticker"],
            days=tool_input.get("days", 30),
            as_of_date=tool_input.get("as_of_date"),
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
            strategy=tool_input.get("strategy"),
            as_of_date=tool_input.get("as_of_date"),
        ),
        "get_fundamentals_analysis": lambda: get_fundamentals_analysis(
            dal,
            tool_input["ticker"]
        ),
        "get_detailed_financials": lambda: get_detailed_financials(
            dal,
            tool_input["ticker"]
        ),
        "get_peer_comparison": lambda: get_peer_comparison(
            dal,
            ticker=tool_input.get("ticker"),
            tickers=tool_input.get("tickers"),
            sector=tool_input.get("sector"),
        ),
        "get_sec_filings": lambda: get_sec_filings(
            ticker=tool_input["ticker"],
            filing_types=tool_input.get("filing_types"),
            limit=tool_input.get("limit", 10),
        ),
        "get_insider_trades": lambda: get_insider_trades(
            ticker=tool_input["ticker"],
            limit=tool_input.get("limit", 10),
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
        # IV Skew (Batch 3b) — no DAL needed
        "get_iv_skew_analysis": lambda: get_iv_skew_analysis(
            ticker=tool_input["ticker"],
            expiry=tool_input.get("expiry"),
            num_strikes=tool_input.get("num_strikes", 10),
        ),
        # Portfolio (Batch 3a)
        "get_portfolio_analysis": lambda: get_portfolio_analysis(
            dal,
            tickers=tool_input.get("tickers"),
            holdings=tool_input.get("holdings"),
        ),
        # Earnings Impact (Batch 3c)
        "get_earnings_impact": lambda: get_earnings_impact(
            dal,
            ticker=tool_input["ticker"],
            quarters=tool_input.get("quarters", 4),
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
        "codex_web_research": lambda: codex_web_research(
            query=tool_input["query"],
            context=tool_input.get("context", ""),
            timeout=tool_input.get("timeout", 300),
        ),
        # Report tools (Phase B)
        "save_report": lambda: save_report(
            dal,
            title=tool_input["title"],
            tickers=tool_input["tickers"],
            report_type=tool_input["report_type"],
            summary=tool_input["summary"],
            content=tool_input["content"],
            conclusion=tool_input.get("conclusion"),
            confidence=tool_input.get("confidence"),
        ),
        "list_reports": lambda: list_reports(
            dal,
            ticker=tool_input.get("ticker"),
            days=tool_input.get("days", 30),
            report_type=tool_input.get("report_type"),
            limit=tool_input.get("limit", 20),
        ),
        "get_report": lambda: get_report(
            dal,
            report_id=tool_input.get("report_id"),
            file_path=tool_input.get("file_path"),
        ),
        # Memory tools (Phase 15)
        "save_memory": lambda: save_memory(
            dal,
            title=tool_input["title"],
            content=tool_input["content"],
            category=tool_input.get("category", "note"),
            tickers=tool_input.get("tickers"),
            tags=tool_input.get("tags"),
            importance=tool_input.get("importance", 5),
            source="agent_auto",
        ),
        "recall_memories": lambda: recall_memories(
            dal,
            query=tool_input.get("query", ""),
            category=tool_input.get("category"),
            tickers=tool_input.get("tickers"),
            tags=tool_input.get("tags"),
            days=tool_input.get("days", 90),
            limit=tool_input.get("limit", 10),
        ),
        "list_memories": lambda: list_memories(
            dal,
            category=tool_input.get("category"),
            days=tool_input.get("days", 90),
            limit=tool_input.get("limit", 20),
        ),
        "delete_memory": lambda: delete_memory(
            dal,
            memory_id=tool_input["memory_id"],
        ),
        # Monitor tools (Phase E1)
        "scan_alerts": lambda: scan_alerts(
            dal,
            tickers=tool_input.get("tickers", ""),
        ),
        # Data Freshness
        "check_data_freshness": lambda: check_data_freshness(dal),
        # RL Pipeline
        "get_rl_model_status": lambda: get_rl_model_status(dal),
        "get_rl_prediction": lambda: get_rl_prediction(
            dal,
            ticker=tool_input["ticker"],
            model_id=tool_input.get("model_id", "latest"),
        ),
        "get_rl_backtest_report": lambda: get_rl_backtest_report(
            dal,
            model_id=tool_input.get("model_id", "latest"),
        ),
        # SA Alpha Picks (Phase 11c)
        "get_sa_alpha_picks": lambda: get_sa_alpha_picks(
            dal,
            status=tool_input.get("status", "all"),
            sector=tool_input.get("sector"),
        ),
        "get_sa_pick_detail": lambda: get_sa_pick_detail(
            dal,
            symbol=tool_input["symbol"],
            picked_date=tool_input.get("picked_date"),
        ),
        "refresh_sa_alpha_picks": lambda: refresh_sa_alpha_picks(dal),
        "get_sa_articles": lambda: get_sa_articles(
            dal,
            ticker=tool_input.get("ticker"),
            keyword=tool_input.get("keyword"),
            article_type=tool_input.get("article_type"),
            limit=tool_input.get("limit", 10),
        ),
        "get_sa_article_detail": lambda: get_sa_article_detail(
            dal, tool_input["article_id"]
        ),
        "get_sa_market_news": lambda: get_sa_market_news(
            dal,
            ticker=tool_input.get("ticker"),
            keyword=tool_input.get("keyword"),
            limit=tool_input.get("limit", 20),
        ),
        "list_high_value_comments": lambda: list_high_value_comments(
            dal,
            window_days=tool_input.get("window_days", 7),
            ticker=tool_input.get("ticker"),
            min_score=tool_input.get("min_score", 2.0),
            limit=tool_input.get("limit", 20),
        ),
    }

    if tool_name not in tool_map:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = tool_map[tool_name]()
        return _serialize_result(result, tool_name=tool_name)
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})
