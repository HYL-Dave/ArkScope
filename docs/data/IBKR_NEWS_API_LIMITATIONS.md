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
| Unique article_ids | 27,638 |
| Unique tickers | 127 |
| **Duplication rate** | **67.3%** |

**Key observation**: Stocks with fewer news articles have longer historical depth because the 300-article buffer cycles slower.

### ⚠️ Critical: Key Stocks Historical Depth (Verified 2026-01-03)

| Ticker | Articles | Days Span | Date Range | Impact |
|--------|----------|-----------|------------|--------|
| **NVDA** | 859 | **23 天** | 2025-12-09 ~ 2026-01-02 | 🔴 嚴重不足 |
| **AAPL** | 767 | **46 天** | 2025-11-17 ~ 2026-01-02 | 🔴 嚴重不足 |
| **TSLA** | 756 | **43 天** | 2025-11-19 ~ 2026-01-02 | 🔴 嚴重不足 |
| **MSFT** | 658 | **38 天** | 2025-11-24 ~ 2026-01-02 | 🔴 嚴重不足 |
| **GOOGL** | 755 | **30 天** | 2025-12-03 ~ 2026-01-02 | 🔴 嚴重不足 |
| **META** | 704 | **36 天** | 2025-11-26 ~ 2026-01-02 | 🔴 嚴重不足 |
| **AMZN** | 645 | **31 天** | 2025-12-01 ~ 2026-01-02 | 🔴 嚴重不足 |
| **AMD** | 816 | **50 天** | 2025-11-12 ~ 2026-01-02 | 🔴 嚴重不足 |
| PPC | 104 | 603 天 | 2024-04-16 ~ 2025-12-11 | ✅ 足夠 |
| EBAY | 885 | 977 天 | 2023-04-27 ~ 2025-12-29 | ✅ 足夠 |

> **結論**: 對 FinRL 訓練而言，NVDA/AAPL/TSLA 等重要股票只有 1-2 個月數據，**完全不足以訓練有效模型**。

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

### 3. Alternative Data Sources for Historical News

#### Comparison (2026-01-03 Research)

| Provider | 歷史深度 | 日期範圍查詢 | 每次結果上限 | 月費 | 備註 |
|----------|----------|--------------|--------------|------|------|
| **Polygon/Massive** | Starter: All history | ✅ `published_utc` | 1,000 (可分頁) | $29 | 🔥 **推薦** |
| **Finnhub** | 未明確說明 | ✅ `from/to` | 無記載 | $0-75 | 免費版可能有限 |
| **EODHD** | 有歷史 | ✅ 支援 | 1,000 | $19.99 | 便宜但新聞非主力 |
| **Tiingo** | 2014+ | ✅ 支援 | 100 per request | $0 | 免費但深度有限 |

#### Polygon/Massive News API 詳情

```python
# Polygon News API - 支援完整歷史查詢
import requests

params = {
    "ticker": "NVDA",
    "published_utc.gte": "2023-01-01",  # 從 2023 年開始
    "published_utc.lte": "2024-12-31",  # 到 2024 年底
    "limit": 1000,  # 最多 1000 篇/請求
    "apiKey": "YOUR_KEY"
}
resp = requests.get("https://api.polygon.io/v2/reference/news", params=params)

# 分頁: 使用 next_url 取得下一批
```

**結論**: 解決歷史深度問題的最佳方案是 **Polygon Starter ($29/mo)**，可查詢任意日期範圍的完整新聞歷史。

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

## Q&A (2026-01-03)

### Q1: 同一篇文章對不同股票評分會一樣嗎？

**答案**: 不一定。分析 52,755 篇已評分文章發現：

| 統計 | 數值 |
|------|------|
| 多股票文章中有不同評分的比例 | **39.4%** |

**實例**:
```
文章: "Enphase, NextEra Energy Stocks Fall on Senate Bill Surprise"
- ENPH: Sentiment=1 (very bearish)
- FSLR: Sentiment=2 (bearish)
```

**結論**: 評分系統**確實會依據股票給予不同分數**，所以目前的 per-ticker 儲存架構在評分邏輯上是合理的。建議改進儲存效率但保留 per-ticker scoring。

### Q2: BroadTape News 能取得歷史新聞嗎？

**答案**: **不能**。

| 方法 | 用途 | 歷史深度 |
|------|------|----------|
| `reqHistoricalNews` | 批次查詢 | 最近 300 篇 (無時間範圍) |
| BroadTape (即時串流) | 即時收集 | **只能從訂閱開始** |

BroadTape 是即時串流，無法查詢過去的新聞。

### Q3: Contract-Specific 即時串流也有 300 篇限制嗎？

**答案**:
- 批次查詢 (`reqHistoricalNews`): 有 300 篇限制
- 即時串流 (`reqMktData` with news tick): **沒有限制**，但只能接收新文章

### Q4: 需要重新評分嗎？

**建議順序**:
1. 先解決歷史深度問題 (訂閱 Polygon)
2. 修復儲存架構 (減少重複)
3. 最後考慮重新評分

### Q5: 解決歷史深度問題的最佳方案？

根據內容類型需求，有兩個方案：

#### 方案 A: 需要完整文章內容
**推薦**: **EODHD All-In-One ($99.99/mo)** 或 **Fundamentals ($59.99/mo)**

| 優點 | 說明 |
|------|------|
| 完整文章 | `content` 欄位有 full body |
| 有歷史深度 | 可查詢歷史新聞 |
| 全球覆蓋 | 60+ 交易所 |

| 缺點 | 說明 |
|------|------|
| API 成本高 | 每次新聞查詢消耗 5 calls |
| 免費層極限 | 20 calls/day = 4 次新聞查詢 |

#### 方案 B: 摘要即可接受
**推薦**: **Polygon/Massive Starter ($29/mo)**

| 優點 | 說明 |
|------|------|
| 完整歷史 | All history available |
| 日期範圍查詢 | `published_utc.gte/lte` |
| 高效分頁 | 1,000 篇/請求 + `next_url` |
| 便宜 | 每月 $29 |

| 缺點 | 說明 |
|------|------|
| 只有摘要 | 無完整文章內容 (付費版相同) |

---

## 新聞來源內容比較 (2026-01-03)

### 各來源內容類型 (2026-01-03 驗證)

| 來源 | 內容類型 | 欄位名稱 | 平均長度 | 歷史深度 | 月費 | 備註 |
|------|----------|----------|----------|----------|------|------|
| **IBKR** | ✅ 完整文章 | `content` | **3,467 chars** | 23-50 天 | $0 | 55% 文章有 body |
| **EODHD** | ✅ 完整文章 | `content` | **待實測** | 有歷史 | $19.99+ | 只有 200 char 預覽 |
| **Alpha Vantage** | ⚠️ 摘要 | `summary` | ~300 chars | 有歷史 | $49.99 | 比 Polygon 略長 |
| **Polygon** | ❌ 摘要 | `description` | 247 chars | 4+ 年 | $29 | 付費版相同欄位 |
| **Finnhub** | ❌ 摘要 | `summary` | ~200 chars | ~1 個月 | $0-75 | 付費版相同欄位 |
| **Tiingo** | ❌ 句子摘要 | `description` | ~50-100 chars | 2014+ | $10+ | "Sentence summary" |
| **Financial Datasets** | ❓ 未確認 | `news` | - | 有歷史 | $0.02/次 | 非新聞專長 |

### 驗證來源

| Provider | 驗證方式 | 檔案位置 |
|----------|----------|----------|
| IBKR | 實測數據 | `data/news/raw/ibkr/*.parquet` |
| EODHD | 程式碼確認 | `data_sources/eodhd_source.py:234` |
| Polygon | 實測數據 | `data/news/raw/polygon/*.parquet` |
| Finnhub | API 文檔 + 實測 | `data_sources/test_finnhub.py` |
| Alpha Vantage | 測試腳本 | `data_sources/test_alpha_vantage.py:78-86` |
| Tiingo | QuantConnect 文檔 | [Tiingo News](https://www.quantconnect.com/docs/v2/our-platform/user-guides/alternative-data/tiingo-news) |

### 關鍵發現

1. **EODHD 是 IBKR 外唯一提供完整文章的數據源**
   - 欄位: `content` (映射至 `description`)
   - 驗證: `eodhd_source.py` line 234: `description=item.get('content', '')`
   - 免費層限制: 20 calls/day，**每次新聞查詢消耗 5 calls**

2. **Polygon 付費版不提供完整文章**
   - 所有層級 (Starter/Developer/Business) 回傳相同欄位
   - 只有 `description` 欄位 (~247 chars 摘要)

3. **Alpha Vantage NEWS_SENTIMENT API 有摘要**
   - 回傳欄位: `title`, `source`, `published`, `overall_sentiment_label`, `ticker_sentiments`, **`summary`**
   - `summary` 欄位約 300 chars，比 Polygon 略長

### IBKR vs Polygon 評分比較 (抽樣分析)

**樣本**: 49 篇完全相同標題的文章

| 指標 | 數值 | 說明 |
|------|------|------|
| 情緒評分完全相同 | 34.7% (17/49) | - |
| 情緒評分差異 ≤1 | 91.8% (45/49) | - |
| 風險評分完全相同 | 83.7% (41/49) | - |
| 情緒分數 Mean 差異 | -0.58 | Polygon 略偏 bullish |
| 情緒分數相關係數 | 0.012 | 極低相關 |

**按股票比較 (不限標題匹配)**:

| 股票 | IBKR 文章數 | IBKR Sent | Polygon 文章數 | Polygon Sent | Sent 差異 |
|------|-------------|-----------|----------------|--------------|-----------|
| AAPL | 437 | 3.03 | 7,697 | 3.07 | -0.04 |
| NVDA | 413 | 2.95 | 7,770 | 3.26 | -0.31 |
| TSLA | 379 | 3.07 | 7,529 | 3.02 | +0.05 |
| MSFT | 344 | 3.06 | 3,898 | 3.25 | -0.19 |

**整體分佈差異**:

| 指標 | IBKR | Polygon |
|------|------|---------|
| Sentiment Mean | 3.09 | 3.17 |
| Sentiment Std | 0.77 | 0.73 |
| Risk Mean | 2.21 | 1.73 |
| Risk Std | 0.94 | 0.93 |

> **注意**: 此比較僅為客觀數據記錄，評分差異對 FinRL 訓練的實際影響需進一步驗證。

---

## References

- IBKR API Documentation: https://interactivebrokers.github.io/tws-api/historical_news.html
- ib_insync Documentation: https://ib-insync.readthedocs.io/
- Polygon News API: https://massive.com/docs/stocks/get_v2_reference_news
- Discovery commit: (this documentation)