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

Use `subscribeNews` to receive articles as they're published.

```python
# ib_insync real-time news subscription
def on_news(news):
    # Process and store immediately
    save_article(news)

ib.newsBulletinEvent += on_news
ib.subscribeNewsBulletins(allMessages=True)
```

**Pros**: Never miss articles, real-time processing
**Cons**: Requires always-on process, more complex infrastructure

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

## Recommendations

1. **Remove time-based splitting code** - It's useless and wastes API requests
2. **Implement real-time streaming** - Essential for complete coverage
3. **Run daily collection** - As backup and for batch processing
4. **Use alternative sources for historical** - Finnhub/Polygon for date-range queries
5. **Monitor collection gaps** - Alert if collector hasn't run in 24+ hours

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