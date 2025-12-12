#!/usr/bin/env python3
"""
AAPL Data Collection Script for API Comparison

Collects AAPL stock data and news from all available free APIs
and saves them for comparison.

Output directory: data_sources/comparison_data/
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Output directory
OUTPUT_DIR = Path(__file__).parent / "comparison_data"
OUTPUT_DIR.mkdir(exist_ok=True)

TICKER = "AAPL"
END_DATE = date.today()
START_DATE_7D = END_DATE - timedelta(days=7)
START_DATE_30D = END_DATE - timedelta(days=30)
START_DATE_1Y = END_DATE - timedelta(days=365)


def load_env():
    """Load environment variables from config/.env"""
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value


def save_json(data: Any, filename: str):
    """Save data to JSON file."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"   Saved: {filepath}")


def collect_tiingo_data() -> Dict:
    """Collect data from Tiingo API."""
    print("\n" + "="*60)
    print("TIINGO - Stock Prices (Free Tier)")
    print("="*60)

    result = {
        "source": "tiingo",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "500 unique symbols/month, 50/hour",
            "rate_limit": "No strict per-minute limit",
            "price_history": "30+ years EOD",
            "intraday": "NOT available (paid only)",
            "news": "NOT available (paid only)",
            "delayed": "End of day (T+1)",
        },
        "limitations": [
            "No intraday/minute-level data on free tier",
            "No news API access on free tier",
            "500 unique symbols per month limit",
            "50 unique symbols per hour limit",
            "Data is end-of-day only",
        ],
        "data": {}
    }

    try:
        from data_sources.tiingo_source import TiingoDataSource

        api_key = os.getenv('TIINGO_API_KEY')
        if not api_key:
            print("❌ TIINGO_API_KEY not found")
            result["error"] = "API key not found"
            return result

        client = TiingoDataSource(api_key)

        # Test connection
        if not client.validate_credentials():
            result["error"] = "Invalid credentials"
            return result

        # Fetch 30 days of daily prices
        print(f"   Fetching {TICKER} daily prices (30 days)...")
        prices = client.fetch_prices([TICKER], start_date=START_DATE_30D, end_date=END_DATE)

        result["data"]["daily_prices"] = {
            "count": len(prices),
            "date_range": f"{prices[0].date} to {prices[-1].date}" if prices else "N/A",
            "sample": [p.to_dict() for p in prices[-5:]] if prices else []
        }
        print(f"   ✅ Retrieved {len(prices)} daily records")

        # Fetch 1 year of prices
        print(f"   Fetching {TICKER} daily prices (1 year)...")
        prices_1y = client.fetch_prices([TICKER], start_date=START_DATE_1Y, end_date=END_DATE)
        result["data"]["yearly_prices"] = {
            "count": len(prices_1y),
            "date_range": f"{prices_1y[0].date} to {prices_1y[-1].date}" if prices_1y else "N/A",
        }
        print(f"   ✅ Retrieved {len(prices_1y)} yearly records")

        # Try news (should fail on free tier)
        print(f"   Attempting news fetch (expected to fail on free tier)...")
        try:
            news = client.fetch_news([TICKER], days_back=7)
            result["data"]["news"] = {"count": len(news), "accessible": True}
        except Exception as e:
            result["data"]["news"] = {"accessible": False, "error": str(e)}
            print(f"   ⚠️ News not available: {e}")

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def collect_finnhub_data() -> Dict:
    """Collect data from Finnhub API."""
    print("\n" + "="*60)
    print("FINNHUB - News & Quotes (Free Tier)")
    print("="*60)

    result = {
        "source": "finnhub",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "60 calls/minute",
            "news_history": "1 year only",
            "price_history": "NOT available (paid only)",
            "real_time_quotes": "Yes",
            "company_profile": "Yes",
        },
        "limitations": [
            "News history limited to 1 year",
            "No historical price data on free tier",
            "60 API calls per minute limit",
            "No intraday candlestick data",
            "Some endpoints may have additional limits",
        ],
        "data": {}
    }

    try:
        from data_sources.finnhub_source import FinnhubDataSource

        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            print("❌ FINNHUB_API_KEY not found")
            result["error"] = "API key not found"
            return result

        client = FinnhubDataSource(api_key)

        # Fetch news (7 days)
        print(f"   Fetching {TICKER} news (7 days)...")
        news = client.fetch_news([TICKER], days_back=7)
        result["data"]["news_7d"] = {
            "count": len(news),
            "sample": [
                {
                    "title": n.title,
                    "source": n.source,
                    "published": n.published_date.isoformat(),
                    "url": n.url,
                    "description": n.description[:200] if n.description else "",
                } for n in news[:10]
            ]
        }
        print(f"   ✅ Retrieved {len(news)} articles (7 days)")

        # Fetch news (30 days)
        print(f"   Fetching {TICKER} news (30 days)...")
        news_30d = client.fetch_news([TICKER], days_back=30)
        result["data"]["news_30d"] = {"count": len(news_30d)}
        print(f"   ✅ Retrieved {len(news_30d)} articles (30 days)")

        # Fetch real-time quote
        print(f"   Fetching {TICKER} real-time quote...")
        quote = client.fetch_quote(TICKER)
        result["data"]["quote"] = quote
        print(f"   ✅ Quote: ${quote.get('c', 0):.2f}")

        # Fetch company profile
        print(f"   Fetching {TICKER} company profile...")
        profile = client.fetch_company_profile(TICKER)
        result["data"]["company_profile"] = profile
        print(f"   ✅ Company: {profile.get('name', 'N/A')}")

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def collect_polygon_data() -> Dict:
    """Collect data from Polygon.io API."""
    print("\n" + "="*60)
    print("POLYGON.IO - Prices & News with Sentiment (Free Tier)")
    print("="*60)

    result = {
        "source": "polygon",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "5 calls/minute",
            "price_history": "2 years (including minute-level!)",
            "intraday": "Yes, 2 years of minute data",
            "news": "Yes, with AI sentiment",
            "delayed": "15 minutes delayed",
        },
        "limitations": [
            "Only 5 API calls per minute (very slow)",
            "15-minute delayed data",
            "2 years historical limit",
            "No tick-level data",
            "Rate limiting requires careful throttling",
        ],
        "data": {}
    }

    try:
        from data_sources.polygon_source import PolygonDataSource

        api_key = os.getenv('POLYGON_API_KEY')
        if not api_key:
            print("❌ POLYGON_API_KEY not found")
            result["error"] = "API key not found"
            return result

        client = PolygonDataSource(api_key)

        # Fetch daily prices (30 days)
        print(f"   Fetching {TICKER} daily prices (30 days)...")
        print("   (Rate limited: 12s between calls)")
        prices = client.fetch_prices([TICKER], start_date=START_DATE_30D, end_date=END_DATE)
        result["data"]["daily_prices"] = {
            "count": len(prices),
            "date_range": f"{prices[0]['date']} to {prices[-1]['date']}" if prices else "N/A",
            "sample": prices[-5:] if prices else []
        }
        print(f"   ✅ Retrieved {len(prices)} daily records")

        # Fetch intraday data (1 day)
        print(f"   Fetching {TICKER} intraday data (1 day)...")
        # Use a recent trading day
        trading_date = END_DATE - timedelta(days=1)
        if trading_date.weekday() >= 5:  # Weekend
            trading_date = trading_date - timedelta(days=trading_date.weekday() - 4)

        intraday = client.fetch_intraday_prices(TICKER, trading_date)
        result["data"]["intraday"] = {
            "date": str(trading_date),
            "count": len(intraday),
            "sample": intraday[:5] if intraday else []
        }
        print(f"   ✅ Retrieved {len(intraday)} minute bars")

        # Fetch news with sentiment
        print(f"   Fetching {TICKER} news with sentiment (7 days)...")
        try:
            news = client.fetch_news([TICKER], days_back=7)
            # Handle both dict and NewsArticle objects
            news_sample = []
            for n in news[:10]:
                if hasattr(n, 'title'):  # NewsArticle object
                    news_sample.append({
                        "title": n.title,
                        "published": str(n.published_date),
                        "source": n.source,
                        "sentiment": getattr(n, 'sentiment_score', None),
                    })
                else:  # dict
                    news_sample.append({
                        "title": n.get("title"),
                        "published": n.get("published_utc"),
                        "sentiment": n.get("sentiment"),
                        "source": n.get("publisher", {}).get("name") if isinstance(n.get("publisher"), dict) else n.get("publisher"),
                    })
            result["data"]["news"] = {
                "count": len(news),
                "sample": news_sample
            }
            print(f"   ✅ Retrieved {len(news)} articles with sentiment")
        except Exception as e:
            result["data"]["news"] = {"count": 0, "error": str(e)}
            print(f"   ⚠️ News fetch failed: {e}")

        # Fetch company details
        print(f"   Fetching {TICKER} company details...")
        details = client.fetch_ticker_details(TICKER)
        result["data"]["company_details"] = details
        print(f"   ✅ Company: {details.get('name', 'N/A')}")

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def collect_alpha_vantage_data() -> Dict:
    """Collect data from Alpha Vantage API."""
    print("\n" + "="*60)
    print("ALPHA VANTAGE - News with AI Sentiment (Free Tier)")
    print("="*60)

    result = {
        "source": "alpha_vantage",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "25 calls/DAY (very limited!)",
            "rate_limit": "5 calls/minute",
            "price_history": "NOT available (Premium only)",
            "news": "Yes, with detailed AI sentiment",
            "company_overview": "Yes",
            "quotes": "Yes",
        },
        "limitations": [
            "Only 25 API calls per DAY (extremely limited!)",
            "Historical prices require Premium subscription",
            "Technical indicators require Premium",
            "API calls count resets daily",
            "Very slow data collection due to limits",
        ],
        "data": {}
    }

    try:
        from data_sources.alpha_vantage_source import AlphaVantageDataSource

        api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if not api_key:
            print("❌ ALPHA_VANTAGE_API_KEY not found")
            result["error"] = "API key not found"
            return result

        client = AlphaVantageDataSource(api_key)

        remaining = client.get_remaining_calls()
        print(f"   API calls remaining today: {remaining['remaining']}/{remaining['daily_limit']}")

        if remaining['remaining'] < 3:
            print("   ⚠️ Not enough API calls remaining, skipping")
            result["error"] = "Daily API limit reached"
            return result

        # Fetch news with sentiment
        print(f"   Fetching {TICKER} news with sentiment...")
        news = client.fetch_news_raw(tickers=[TICKER], limit=20)
        result["data"]["news"] = {
            "count": len(news),
            "sample": [
                {
                    "title": n.get("title"),
                    "published": n.get("published"),
                    "source": n.get("source"),
                    "overall_sentiment_score": n.get("overall_sentiment_score"),
                    "overall_sentiment_label": n.get("overall_sentiment_label"),
                    "ticker_sentiments": n.get("ticker_sentiments", [])[:3],
                    "summary": n.get("summary", "")[:300],
                } for n in news[:10]
            ]
        }
        print(f"   ✅ Retrieved {len(news)} articles with sentiment")

        # Fetch quote
        print(f"   Fetching {TICKER} quote...")
        quote = client.fetch_quote(TICKER)
        result["data"]["quote"] = quote
        print(f"   ✅ Quote: ${quote.get('price', 0):.2f}")

        # Fetch company overview
        print(f"   Fetching {TICKER} company overview...")
        overview = client.fetch_company_overview(TICKER)
        result["data"]["company_overview"] = {
            "name": overview.get("Name"),
            "sector": overview.get("Sector"),
            "industry": overview.get("Industry"),
            "market_cap": overview.get("MarketCapitalization"),
            "pe_ratio": overview.get("PERatio"),
            "eps": overview.get("EPS"),
            "dividend_yield": overview.get("DividendYield"),
            "52_week_high": overview.get("52WeekHigh"),
            "52_week_low": overview.get("52WeekLow"),
        }
        print(f"   ✅ Company: {overview.get('Name', 'N/A')}")

        remaining = client.get_remaining_calls()
        result["api_calls_used"] = remaining['used_today']
        result["api_calls_remaining"] = remaining['remaining']

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def collect_yfinance_data() -> Dict:
    """Collect data from yfinance (Yahoo Finance)."""
    print("\n" + "="*60)
    print("YFINANCE - Stock Data (Unofficial, Free)")
    print("="*60)

    result = {
        "source": "yfinance",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "No official limit (unofficial API)",
            "price_history": "64+ years (complete)",
            "intraday": "7 days only (1m, 5m, 15m intervals)",
            "news": "Limited (titles only, no content)",
            "company_info": "Yes",
        },
        "limitations": [
            "UNOFFICIAL API - may break or be blocked",
            "Intraday data limited to 7 days",
            "News has minimal content (titles only)",
            "No rate limit guarantees",
            "May be blocked with heavy usage",
            "Data quality not guaranteed",
        ],
        "data": {}
    }

    try:
        import yfinance as yf

        ticker = yf.Ticker(TICKER)

        # Fetch daily prices (30 days)
        print(f"   Fetching {TICKER} daily prices (30 days)...")
        hist_30d = ticker.history(start=str(START_DATE_30D), end=str(END_DATE))
        result["data"]["daily_prices_30d"] = {
            "count": len(hist_30d),
            "date_range": f"{hist_30d.index[0].date()} to {hist_30d.index[-1].date()}" if not hist_30d.empty else "N/A",
            "sample": [
                {
                    "date": str(idx.date()),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                } for idx, row in hist_30d.tail(5).iterrows()
            ]
        }
        print(f"   ✅ Retrieved {len(hist_30d)} daily records (30 days)")

        # Fetch daily prices (1 year)
        print(f"   Fetching {TICKER} daily prices (1 year)...")
        hist_1y = ticker.history(start=str(START_DATE_1Y), end=str(END_DATE))
        result["data"]["daily_prices_1y"] = {
            "count": len(hist_1y),
            "date_range": f"{hist_1y.index[0].date()} to {hist_1y.index[-1].date()}" if not hist_1y.empty else "N/A",
        }
        print(f"   ✅ Retrieved {len(hist_1y)} daily records (1 year)")

        # Fetch intraday (1-minute, 5 days)
        print(f"   Fetching {TICKER} intraday data (1-minute, 5 days)...")
        hist_intraday = ticker.history(period="5d", interval="1m")
        result["data"]["intraday"] = {
            "count": len(hist_intraday),
            "date_range": f"{hist_intraday.index[0]} to {hist_intraday.index[-1]}" if not hist_intraday.empty else "N/A",
            "sample": [
                {
                    "datetime": str(idx),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                } for idx, row in hist_intraday.tail(5).iterrows()
            ]
        }
        print(f"   ✅ Retrieved {len(hist_intraday)} minute bars")

        # Fetch company info
        print(f"   Fetching {TICKER} company info...")
        info = ticker.info
        result["data"]["company_info"] = {
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "current_price": info.get("currentPrice"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "volume": info.get("volume"),
        }
        print(f"   ✅ Company: {info.get('longName', 'N/A')}")

        # Fetch news
        print(f"   Fetching {TICKER} news...")
        news = ticker.news
        result["data"]["news"] = {
            "count": len(news) if news else 0,
            "sample": [
                {
                    "title": n.get("title"),
                    "publisher": n.get("publisher"),
                    "link": n.get("link"),
                    "published": datetime.fromtimestamp(n.get("providerPublishTime", 0)).isoformat() if n.get("providerPublishTime") else None,
                } for n in (news[:10] if news else [])
            ],
            "note": "News titles only, no full content available"
        }
        print(f"   ✅ Retrieved {len(news) if news else 0} news items")

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def collect_sec_edgar_data() -> Dict:
    """Collect data from SEC EDGAR API."""
    print("\n" + "="*60)
    print("SEC EDGAR - Financial Filings (Official, Free)")
    print("="*60)

    result = {
        "source": "sec_edgar",
        "ticker": TICKER,
        "collected_at": datetime.now().isoformat(),
        "free_tier_limits": {
            "api_calls": "10 requests/second (courtesy limit)",
            "filings_history": "Complete (10+ years)",
            "filing_types": "All (10-K, 10-Q, 8-K, etc.)",
            "xbrl_data": "Yes, structured financial data",
            "api_key_required": "No",
        },
        "limitations": [
            "No stock price data",
            "No news data",
            "10 requests/second courtesy limit",
            "Requires User-Agent header",
            "Some filings may lack XBRL data",
            "Data parsing can be complex",
        ],
        "data": {}
    }

    try:
        from data_sources.sec_edgar_source import SECEdgarDataSource

        client = SECEdgarDataSource()

        # Fetch recent filings
        print(f"   Fetching {TICKER} SEC filings...")
        filings = client.fetch_sec_filings([TICKER], filing_types=['10-K', '10-Q', '8-K'])
        result["data"]["filings"] = {
            "count": len(filings),
            "sample": [
                {
                    "type": f.filing_type,
                    "date": str(f.filing_date),
                    "title": f.title,
                    "url": f.url,
                } for f in filings[:10]
            ]
        }
        print(f"   ✅ Retrieved {len(filings)} filings")

        # Fetch company facts (XBRL data)
        print(f"   Fetching {TICKER} company facts (XBRL)...")
        facts = client.fetch_company_facts(TICKER)

        # Extract key financial metrics
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        key_metrics = {}

        for metric in ["Revenues", "NetIncomeLoss", "Assets", "EarningsPerShareBasic"]:
            if metric in us_gaap:
                data = us_gaap[metric]
                units = data.get("units", {})
                # Get USD values if available
                if "USD" in units:
                    values = units["USD"]
                    if values:
                        latest = values[-1]
                        key_metrics[metric] = {
                            "value": latest.get("val"),
                            "end_date": latest.get("end"),
                            "form": latest.get("form"),
                        }

        result["data"]["xbrl_facts"] = {
            "available_metrics": len(us_gaap),
            "key_metrics": key_metrics,
        }
        print(f"   ✅ Retrieved {len(us_gaap)} XBRL metrics")

    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Error: {e}")

    return result


def main():
    """Collect data from all sources and save for comparison."""
    print("="*60)
    print(f"AAPL Data Collection for API Comparison")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Load environment
    load_env()

    all_results = {
        "ticker": TICKER,
        "collection_date": datetime.now().isoformat(),
        "sources": {}
    }

    # Collect from each source
    print("\nCollecting data from all sources...")

    # 1. Tiingo
    all_results["sources"]["tiingo"] = collect_tiingo_data()
    save_json(all_results["sources"]["tiingo"], "aapl_tiingo.json")

    # 2. Finnhub
    all_results["sources"]["finnhub"] = collect_finnhub_data()
    save_json(all_results["sources"]["finnhub"], "aapl_finnhub.json")

    # 3. Polygon
    all_results["sources"]["polygon"] = collect_polygon_data()
    save_json(all_results["sources"]["polygon"], "aapl_polygon.json")

    # 4. Alpha Vantage (careful with daily limit!)
    all_results["sources"]["alpha_vantage"] = collect_alpha_vantage_data()
    save_json(all_results["sources"]["alpha_vantage"], "aapl_alpha_vantage.json")

    # 5. yfinance
    all_results["sources"]["yfinance"] = collect_yfinance_data()
    save_json(all_results["sources"]["yfinance"], "aapl_yfinance.json")

    # 6. SEC EDGAR
    all_results["sources"]["sec_edgar"] = collect_sec_edgar_data()
    save_json(all_results["sources"]["sec_edgar"], "aapl_sec_edgar.json")

    # Save combined results
    save_json(all_results, "aapl_all_sources.json")

    # Generate summary
    print("\n" + "="*60)
    print("COLLECTION SUMMARY")
    print("="*60)

    summary = []
    for source, data in all_results["sources"].items():
        status = "✅" if "error" not in data else "❌"
        summary.append({
            "source": source,
            "status": "success" if "error" not in data else "error",
            "limitations": data.get("limitations", []),
            "data_collected": list(data.get("data", {}).keys()),
        })
        print(f"\n{status} {source.upper()}")
        if "error" in data:
            print(f"   Error: {data['error']}")
        else:
            for key, value in data.get("data", {}).items():
                if isinstance(value, dict) and "count" in value:
                    print(f"   - {key}: {value['count']} records")

    save_json(summary, "aapl_summary.json")

    print(f"\n\nAll data saved to: {OUTPUT_DIR}")
    print("Files created:")
    for f in OUTPUT_DIR.glob("aapl_*.json"):
        print(f"  - {f.name}")


if __name__ == '__main__':
    main()