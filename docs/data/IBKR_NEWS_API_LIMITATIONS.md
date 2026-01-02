# IBKR News API Limitations

> **Discovery Date**: 2026-01-02
> **Status**: Confirmed through empirical testing

---

## Critical Finding: reqHistoricalNews Ignores Time Range Parameters

### The Problem

IBKR's `reqHistoricalNews` API **does not respect the `startDateTime` and `endDateTime` parameters**. It always returns the **300 most recent articles** for the given contract, regardless of the time range specified.

### Evidence

```python
# Test: Query two COMPLETELY DIFFERENT time ranges
# Range 1: midnight to 1am on 2026-01-02
articles1 = ibkr._fetch_news_single_query(
    start_dt=datetime(2026, 1, 2, 0, 0, 0),
    end_dt=datetime(2026, 1, 2, 1, 0, 0),
    ticker='WFC'
)

# Range 2: 6pm to 7pm on 2026-01-02
articles2 = ibkr._fetch_news_single_query(
    start_dt=datetime(2026, 1, 2, 18, 0, 0),
    end_dt=datetime(2026, 1, 2, 19, 0, 0),
    ticker='WFC'
)

# Results:
# Range 00:00-01:00: 300 articles
# Range 18:00-19:00: 300 articles
# Overlap: 300 articles (100% identical!)
#
# Sample timestamps from BOTH ranges:
#   2025-12-22 13:32:00  <- Not even from 2026!
#   2025-12-22 13:30:00
#   2025-12-19 07:32:00
```

### Implications

| Issue | Impact |
|-------|--------|
| **No historical queries** | Cannot retrieve news from specific date ranges |
| **300 article hard cap** | Maximum 300 articles per ticker per API call |
| **Time-based splitting is useless** | Recursive splitting wastes API requests |
| **High-news stocks lose history** | Popular stocks (AAPL, TSLA) have shorter historical depth |

### Data Analysis (from 84,539 collected articles)

| Metric | Value |
|--------|-------|
| Total articles collected | 84,539 |
| Unique tickers | 127 |
| Average days span | 408 days |
| Min days span | 22 days |
| Max days span | 1,076 days |

**Key observation**: Stocks with fewer news articles have longer historical depth because the 300-article buffer cycles slower.

| Ticker | Articles | Days Span | Notes |
|--------|----------|-----------|-------|
| W | 890 | 150 days | High news volume = short history |
| EBAY | 885 | 977 days | Lower news rate = long history |
| PPC | 104 | 603 days | Low news volume = deepest history |

---

## Workarounds

### 1. Regular Collection (Current Approach)

Run the collector frequently to capture new articles before they fall out of the 300-article window.

```bash
# Daily collection via cron
0 6 * * * cd /path/to/project && python scripts/collection/collect_ibkr_news.py --incremental
```

**Pros**: Simple, works with existing infrastructure
**Cons**: May miss articles during gaps in collection

### 2. Real-time Streaming (Recommended)

There are **two methods** for real-time news in IBKR:

#### Method A: BroadTape News (All News from Provider)

```python
from ib_insync import IB, Contract

ib = IB()
ib.connect()

# Create a NEWS contract for BroadTape feed
contract = Contract()
contract.symbol = "BZ:BZ_ALL"  # Benzinga all news
contract.secType = "NEWS"
contract.exchange = "BZ"

# Available BroadTape providers:
# - BZ (Benzinga)
# - FLY (Fly on the Wall)
# - DJ-N (Dow Jones)
# - BRFG (Briefing.com)

# Subscribe to news feed
ib.reqMktData(contract, "", False, False)

# Handle incoming news via tickNews callback
def on_tick_news(ticker):
    for news in ticker.newsTicks:
        print(f"[{news.timeStamp}] {news.providerCode}: {news.headline}")
        # news.articleId can be used to fetch full body

ib.pendingTickersEvent += on_tick_news
```

#### Method B: Contract-Specific News (Per-Stock)

```python
from ib_insync import IB, Stock

ib = IB()
ib.connect()

# Create stock contract
stock = Stock('AAPL', 'SMART', 'USD')
ib.qualifyContracts(stock)

# Request market data with news generic tick
# "292:BRFG" = Briefing.com news for this contract
# "292:BZ" = Benzinga news
ib.reqMktData(stock, "mdoff,292:BZ", False, False)

# Process via pendingTickersEvent same as above
```

#### News Bulletins (System Messages)

```python
# For system-wide news bulletins (not stock-specific)
def on_news_bulletin(bulletin):
    print(f"Bulletin: {bulletin.message}")

ib.newsBulletinEvent += on_news_bulletin
ib.reqNewsBulletins(allMessages=True)
```

**Pros**: Never miss articles, real-time processing
**Cons**: Requires always-on process, more complex infrastructure

#### Implementation Notes

| Aspect | Detail |
|--------|--------|
| **NewsTick fields** | `timeStamp`, `providerCode`, `articleId`, `headline`, `extraData` |
| **Body fetching** | Use `ib.reqNewsArticle(providerCode, articleId)` |
| **Rate limiting** | No documented limit for streaming, but body fetch has pacing |
| **Reconnection** | Must handle disconnects and resubscribe |
| **Default providers** | BRFG, BRFUPDN, DJNL enabled free (TWS v966+) |

### 3. Alternative Data Sources

For historical news, consider:
- **Finnhub**: Supports date range queries
- **Polygon.io**: Full historical news archive ($29/mo)
- **Tiingo**: Limited historical news

---

## Paid Subscription Investigation

### Question: Does a paid news subscription unlock historical access?

Based on IBKR documentation and community reports:

| Subscription | Historical Access | Notes |
|--------------|-------------------|-------|
| **Free (Basic)** | Last 300 articles only | Current behavior |
| **DJ News ($)** | Same 300 limit | Premium content, same API limits |
| **Briefing.com ($)** | Same 300 limit | More providers, same limits |
| **Reuters ($)** | Unknown | May have different API |

**Conclusion**: Paid subscriptions provide **more news providers** but likely have the **same API limitations**. The 300-article limit appears to be an API design choice, not a subscription tier restriction.

> **TODO**: Verify this by testing with Reuters subscription if available.

---

## Data Duplication Issue

### Current Deduplication Logic

The collector uses `dedup_hash = f"{ticker.upper()}|{title.strip().lower()}|{pub_date}"` which causes **per-ticker deduplication** instead of global.

### Impact

Analysis of 84,539 collected articles:

| Metric | Value |
|--------|-------|
| By dedup_hash (per-ticker) | 84,539 |
| By article_id (global) | ~35,800 |
| **Duplication rate** | **57.6%** |

Example: Article "CFA Technology: Insider Review" appears **56 times** (once for each ticker it mentions).

### Root Cause

Same news article tagged to multiple tickers → stored N times.

```
article_id: "DJ-N$abc123" → stored for AAPL, MSFT, GOOGL, ...
dedup_hash: "AAPL|cfa technology...|2026-01-02" ✓ unique
dedup_hash: "MSFT|cfa technology...|2026-01-02" ✓ unique (different!)
```

### Recommendation

Use `article_id` as primary key for global deduplication. Store ticker associations separately.

```python
# Proposed schema
articles:
  - article_id: "DJ-N$abc123"  # Primary key
    title: "..."
    content: "..."
    published_at: "..."
    tickers: ["AAPL", "MSFT", "GOOGL"]  # Multi-value
```

---

## Recommendations

1. **Remove time-based splitting code** - It's useless and wastes API requests ✅ Done
2. **Implement real-time streaming** - Essential for complete coverage
3. **Run daily collection** - As backup and for batch processing
4. **Use alternative sources for historical** - Finnhub/Polygon for date-range queries
5. **Monitor collection gaps** - Alert if collector hasn't run in 24+ hours
6. **Fix deduplication** - Use article_id as primary key to eliminate 57.6% redundancy

---

## Technical Details

### API Signature

```python
reqHistoricalNews(
    conId: int,           # Contract ID
    providerCodes: str,   # e.g., "DJ-N+FLY+BRFG"
    startDateTime: str,   # IGNORED by IBKR!
    endDateTime: str,     # IGNORED by IBKR!
    totalResults: int,    # Max 300
    historicalNewsOptions: list = None
)
```

### What Actually Happens

```
Request: startDateTime="20260102 00:00:00", endDateTime="20260102 01:00:00"
Response: 300 most recent articles (from any time)

Request: startDateTime="20251201 00:00:00", endDateTime="20251231 23:59:59"
Response: Same 300 most recent articles (identical to above)
```

---

## References

- IBKR API Documentation: https://interactivebrokers.github.io/tws-api/historical_news.html
- ib_insync Documentation: https://ib-insync.readthedocs.io/
- Discovery commit: (this documentation)