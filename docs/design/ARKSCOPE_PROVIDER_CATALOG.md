# ArkScope Provider Catalog (canonical)

**Date**: 2026-06-04
**Status**: CANONICAL provider authority (draft pending reviewer adoption — all 11 connected-provider entries complete; gpt-5.5 round-2 refinements folded in). Second of three canonical docs (ProductSpec → **ProviderCatalog** → ToolCatalog).

**Authority**: this doc owns **per-provider facts** — what each data source gives, its latency/streaming, history depth, cost, auth/config, limits, quirks, what it's good/bad for, and the **app Settings fields** that expose it. Architecture/storage = `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`; product/agent boundaries = `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md`; the registry tools that *consume* these providers = `ARKSCOPE_TOOL_CATALOG.md`.

> 中文摘要：每個資料源的「能拿什麼／延遲／是否即時／歷史多深／費用／怎麼設定／限制／適合做什麼」一覽，直接餵 app Settings UI。價格一律帶 `verified_at`，且**以來源文件日期為準、未重新上網查證**（見 §0.2）。**基本盤＝IBKR＋Seeking Alpha＋web search（含政治/國際/戰爭等一般時事），其餘為支援層**（見 §0.4）。

---

## 0. How to read this catalog

### 0.1 Per-provider schema (locked: gpt-5.5 + round-2 refinements)

Every full entry carries these fields:

`provider` · `implementation_status` · `connected_via` · `asset_classes` · `data_types` · `history_depth` · `latency` · `streaming` · `cost` · `auth/config` · `limits` · `known_quirks` · `best_for` · `not_good_for` · `verified_at` · `source_links` · `app_settings_fields`

Three fields use **controlled vocabularies** (added round-2 so future readers don't misread the catalog):

- **`implementation_status`** ∈ `live` (wired + usable now) · `optional-live` (wired but paid / toggle-gated, may be off) · `protected-pipeline` (the SA extension→native-host path — operational, **must not break**) · `planned` (catalogued, not yet wired) · `reference-only`. Guards against "appears in catalog ⇒ fully productised."
- **`connected_via`** — the concrete wiring: a `data_sources/<client>.py`, a `src/tools/<tool>.py`, the `extension→native-host` pipeline, or `planned settings`. Makes explicit that the 11 providers are *not* the same kind of thing (local socket vs public REST vs scraped vs tool).
- **`streaming`** ∈ `none` · `realtime_quote` (live last price, **no** bar stream) · `realtime_bars` (streamed OHLC — **charting-grade**) · `websocket_streaming` · `extension_capture` (scraped, not a feed). **Charting feasibility derives from this**: only `realtime_bars` / `websocket_streaming` support stable low-latency price/volume charts. Per ProductSpec §5, **only IBKR clears this bar in-stack.** *This is a fact about the **currently-connected stack**, not a permanent market claim — if Polygon/Massive or another provider is later wired as true `realtime_bars` / `websocket_streaming`, update its enum value and this line.*

### 0.2 Freshness rule (IMPORTANT — read before trusting any price)

- **Capability facts** (asset classes, data types, streaming, history depth, config method, quirks) are **durable** — they change rarely and are the catalog's primary value.
- **Pricing, tier names, and rate limits are volatile.** Every such figure carries a **`verified_at`** date and is carried **from the source evaluation docs (2025-12 → 2026-05 vintage), NOT re-verified live** — those docs themselves carry an explicit "re-verify before subscribing" caveat. **Treat every `$`/limit as last-known, not current.**
- Deliberate stance: gpt-5.5 locked "all prices carry `verified_at`," not "web-verify now." A live price-verification pass is an optional later enhancement, tracked separately.

### 0.3 Provider classes

| Class | Providers |
|-------|-----------|
| **Real-time market data** | IBKR (only in-stack real-time / charting-grade) |
| **Delayed / historical market data** | Polygon, Tiingo, Alpha Vantage, Finnhub, EODHD |
| **Fundamentals** | SEC EDGAR (free), IBKR (snapshot ratios), Financial Datasets (paid), EODHD |
| **Macro / calendar** | FRED (macro series), Finnhub (earnings/IPO/economic calendar) |
| **Curated research (scraped)** | Seeking Alpha — Alpha Picks + comments + market news, via browser extension → Native Messaging host (PROTECTED; not an API) |
| **Web / world search (agent)** | Tavily |

### 0.4 Foundation tier (基本盤 — already in use) vs supporting providers

The project's **load-bearing sources are the three already in daily use.** The catalog will grow, but **incrementally** — a few well-known providers at a time — NOT via another research-everything-first sweep like the project's past.

| Tier | Providers | Why |
|------|-----------|-----|
| **Foundation (基本盤)** | **IBKR** (everything obtainable, free + paid) · **Seeking Alpha** (everything knowable via capture) · **web search** (Tavily — general world context: politics / international / geopolitics / war, **not finance-only**) | Already in use; the real spine of the product |
| **Supporting** | Polygon · Finnhub · Tiingo · Alpha Vantage · EODHD · SEC EDGAR · Financial Datasets · FRED | Fallbacks, breadth, free fundamentals, macro — valuable but swappable |

**Effort priority follows this**: strengthen **IBKR + SA + web-search** coverage first; treat the supporting tier as fallback/enrichment. New providers enter as "supporting" unless they deepen the foundation.

### 0.5 Provider Admission Tiers (which providers to wire, in what order)

Formal rubric for *which* providers earn a Settings slot and *when* — so the set grows by deliberate admission, not accretion (gpt-5.5-locked). Tier is **per-capability**, not strictly per-provider (IBKR spans 0 and 2).

| Tier | Definition | Current members | Policy |
|------|-----------|-----------------|--------|
| **0 — Foundation** | The basic spine, already in daily use | IBKR (free Gateway access), Seeking Alpha, Tavily | Strengthen stability + UX **first**; everything else is secondary |
| **1 — Free / Free-Enough** | Fully free, or free quota sufficient for personal use | SEC EDGAR, FRED/ALFRED, Finnhub, Tiingo, Alpha Vantage* | **Prioritise into Settings** — near-zero cost to admit. *(\*Alpha Vantage free = 25 req/day, quota-constrained — admit but flag.)* |
| **2 — Cheap High-Value** | Cheap, fills an obvious gap or has hard-to-replace data | Polygon/Massive (~$29), EODHD ($19.99–99), Financial Datasets (PAYG ~$30), **IBKR paid streaming add-on (~$4.50)** | Admit when the gap is real; gate spend via `metered_spend` / paid toggles |
| **3 — Expensive / Specialist** | Pricey but unique: deep options flow, institutional fundamentals, alt-data, international markets, fixed-income / commodity / crypto | *(none connected yet)* | **Do NOT pre-connect** — pulled only by an explicit feature requirement |
| **Reject / Defer** | High overlap with existing data, unstable API, licensing friction, free quota too low to use, un-cacheable, or high Settings complexity for low analytic gain | — | Document the reason; revisit only if conditions change |

**Admission principle**: the 11 current providers already cover Tiers 0–2 and are **enough to build the desktop shell + ToolCatalog** — no new survey now. New providers enter as Tier 1/2 "supporting" unless they deepen the foundation (Tier 0).

---

## 1. Provider summary table (all 11 connected sources)

> One-line orientation; full entries below. **Streaming** column shows the §0.1 enum + whether it's charting-grade. **Status** = §0.1 `implementation_status`.

| Provider | Status | Asset classes | Streaming (charting?) | History depth (key) | Cost posture | Best for | verified_at |
|----------|--------|--------------|----------------------|---------------------|--------------|----------|-------------|
| **IBKR** (IB Gateway) | live | US equities, options, futures, FX | `realtime_bars` ✅ **charting-grade (only one)** | 1-min bars ~6mo; news ~1mo | free snapshot-only; RT add-on ≈$4.50/mo | real-time charting; live quotes; options chains+Greeks | 2025-12 |
| **Polygon** (Massive) | live (free) / optional-live (paid) | US equities, options | `none` free (15-min delayed); `realtime_quote` paid | **news 3+ yr w/ AI sentiment**; prices 2yr free / 10-15yr paid | free 5 calls/min; paid ≈$29/mo | best free **news archive** + AI sentiment | 2025-12 |
| **Finnhub** | live | US equities | `realtime_quote` (no bars) | **news ~7 days** (claims 1yr) | free; paid Fundamental tiers | earnings/IPO/economic **calendar** | 2025-12 |
| **Tiingo** | live | US equities | `none` (EOD) | **30+ yr EOD** | free; paid $10+/mo | EOD price **fallback** | 2025-12 |
| **Alpha Vantage** | live | equities, FX, commodities | `none` (delayed) | EOD; intraday ~7 days | free **25 req/day** | **commodity series** → IBKR futures | 2025-12 |
| **EODHD** | optional-live (paid) | global equities, fundamentals | `none` (EOD) | long global EOD | paid $19.99–$99 | global EOD + fundamentals breadth | 2025-12 |
| **SEC EDGAR** | live | US equities (fundamentals) | `none` | full filing history | **free** | authoritative **fundamentals** (XBRL), filings, insider | 2026-01 |
| **Financial Datasets** | optional-live (paid, toggle) | US equities (fundamentals) | `none` | quarterly/annual/TTM | paid ≈$30/mo | fundamentals fallback; unique **Segmented Revenue** | 2026-01 |
| **FRED** | live | macro series | `none` | decades | **free** | macro w/ **point-in-time** (anti-lookahead) | 2026-04 |
| **Seeking Alpha** | **protected-pipeline** | US equities (curated) | `extension_capture` | per-capture | account + extension | **Alpha Picks**, **comment intelligence**, SA news | 2026-05 |
| **Tavily** | live | **web / world** (any topic) | `none` (live fetch) | live | paid; free 1000 credits/mo | **general web/world context** (incl. politics/geopolitics) | 2026-03 |

---

## 2. IBKR (Interactive Brokers) — full entry **[EXEMPLAR + FOUNDATION]**

> The keystone provider and the single biggest dedup win — facts here consolidate `data_sources/IBKR_GUIDE.md`, `docs/data/DATA_SUBSCRIPTION_GUIDE.md`, `docs/data/IBKR_NEWS_API_LIMITATIONS.md`, and the IBKR sections of the two evaluation docs.

| Field | Value |
|-------|-------|
| **provider** | IBKR (Interactive Brokers) via **IB Gateway** (headless) / TWS. |
| **implementation_status** | **live** (foundation tier). |
| **connected_via** | `data_sources/ibkr_source.py` (`IBKRDataSource`) — a **local socket** to IB Gateway (not REST). |
| **asset_classes** | US equities, **options** (chains + Greeks), futures, FX. Broadest asset coverage in the stack. |
| **data_types** | Real-time + historical OHLCV bars; L1 quotes; option chains (`reqSecDefOptParams`) + Greeks (`reqMktData`); fundamental ratios via generic ticks (258 = P/E, EPS, Beta; 456 = dividends); news (`reqHistoricalNews`, `reqNewsArticle`) from Dow Jones / Briefing.com / The Fly / IBIS. |
| **history_depth** | **1-min bars ~6 months; 10/15/30-sec ~6 months; 5-sec ~1 month; 15-min ~2 years** (baseline 2025-12). **News ~1 month only** — not for news backtesting. |
| **latency** | **Real-time** (no 15-min delay) with a market-data subscription; otherwise delayed/snapshot. |
| **streaming** | **`realtime_bars`** — `reqMktData` streams quotes/volume, `reqRealTimeBars` streams 5-sec OHLC. **The only charting-grade source in the stack** (ProductSpec §5). |
| **cost** | Free tier = **snapshot-only** (100 free snapshots/mo, then per-snapshot). Real-time streaming needs **US Equity & Options Add-On Streaming Bundle ≈ $4.50/mo** (NYSE+AMEX+NASDAQ+OPRA), which **requires the US Securities Snapshot & Futures Value Bundle ≈ $10/mo first** ($10 **waived if monthly commissions > $30**). Per-exchange L1 (NYSE/NASDAQ/AMEX) ≈ $1.50/mo each if not bundled. *(`verified_at` 2025-12 — re-verify on IBKR's market-data pricing page.)* |
| **auth/config** | Remote **IB Gateway** at `IBKR_HOST` / `IBKR_PORT` (this deployment: `<ibkr-gateway-host>:<port>`; standard IBKR ports: 4001 = live Gateway, 4002 = paper, 7497/7496 = TWS paper/live). Needs the Gateway running + logged in; scripts must load `config/.env`. No REST key — socket API. |
| **limits** | Historical-data pacing throttling (avoid bursts). `reqHistoricalNews` **ignores `startDateTime`/`endDateTime`** — always returns the **300 most-recent** articles (verified: 100% overlap across two disjoint windows). `reqTickByTickData` for **options returns Error 10189**. BroadTape streaming = real-time only, no retroactive history. |
| **known_quirks** | Requires a live GUI-less Gateway/TWS session (Xvfb/systemd). News history shallow (~1mo). Options sweep/block detection impossible via API (10189). Generic-tick fundamentals limited vs SEC EDGAR. |
| **best_for** | Real-time price/volume **charting**; live quotes for the cockpit; option chains + Greeks; real-time (Dow Jones-grade) news headlines. Default `realtime` price source in config. |
| **not_good_for** | News/event **backtesting** (shallow history, no date-ranged news); options flow detection; deep fundamental history (use SEC EDGAR / Financial Datasets). |
| **verified_at** | Capability facts 2025-12 (IBKR_GUIDE last test 2025-12-19); pricing 2025-12 (DATA_SUBSCRIPTION_GUIDE). |
| **source_links** | `data_sources/IBKR_GUIDE.md`, `docs/data/DATA_SUBSCRIPTION_GUIDE.md` §市場數據訂閱, `docs/data/IBKR_NEWS_API_LIMITATIONS.md`. External (verify): IBKR market-data pricing page; TWS API `reqMktData` / `reqRealTimeBars` docs. |
| **app_settings_fields** | `ibkr.host` (text), `ibkr.port` (int, default 4001), `ibkr.client_id` (int), `ibkr.enabled` (toggle), **`ibkr.market_data_subscription`** (info + "**Test connection**" button that runs a live `reqMktData` round-trip and reports RT-vs-delayed-vs-snapshot — required before charting is enabled per ProductSpec §5). |

---

## 3. Remaining provider entries

> Same schema as the IBKR exemplar. Pricing/limits carry `verified_at` and are **last-known (source-doc dated), not live-verified** (§0.2).

### 3.1 Polygon (Massive.com)

| Field | Value |
|-------|-------|
| **provider** | Polygon.io — **renamed Massive.com** (docs use both names). |
| **implementation_status** | **live** (free tier) / **optional-live** (paid). |
| **connected_via** | `data_sources/polygon_source.py` (REST). |
| **asset_classes** | US equities, options. |
| **data_types** | OHLCV bars; **news with AI sentiment labels**; options quotes + Greeks (paid); technical indicators (SMA/EMA/RSI). |
| **history_depth** | Prices: **2 yr free / 10–15 yr paid**. **News: 3+ years** — deepest free news archive in the stack. |
| **latency** | **15-minute delayed** on free tier; real-time on paid. |
| **streaming** | `none` on free (15-min delayed); `realtime_quote` on paid. **Not bar-streaming — not charting-grade for our use** (IBKR owns charting). |
| **cost** | Free tier (delayed, rate-limited). Paid ≈ **$29/mo** (real-time options quotes + Greeks + news sentiment + technicals). |
| **auth/config** | `POLYGON_API_KEY`. REST. Wired in `data_preferences.prices` (historical). |
| **limits** | Free ≈ **5 calls/min**; paid 300+ calls/min. |
| **known_quirks** | Free-tier delay makes it historical-only; name split (Polygon/Massive). |
| **best_for** | **Best free news archive** (3+ yr) with AI sentiment; historical price backtests; cheap real-time options ($29). |
| **not_good_for** | Real-time charting on free tier (15-min delay). |
| **verified_at** | 2025-12. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §Polygon, `docs/data/US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS.md`, `data_sources/API_SPECIFICATIONS.md` §Polygon. |
| **app_settings_fields** | `polygon.enabled` (toggle), `polygon.api_key` (secret), `polygon.tier` (free/paid info). |

### 3.2 Finnhub

| Field | Value |
|-------|-------|
| **provider** | Finnhub. |
| **implementation_status** | **live**. |
| **connected_via** | `data_sources/finnhub_source.py` (news/quotes) + `data_sources/finnhub_calendar_client.py` (calendar). REST. |
| **asset_classes** | US equities. |
| **data_types** | Real-time quote; news; **economic / earnings / IPO calendar** (`/calendar/economic` with `actual`/`estimate`/`prev`, UTC-stamped); basic fundamentals (paid). |
| **history_depth** | **News ~7 days in practice** (despite a documented 1-year claim — verified 2025-12-14). Calendar covers upcoming + historical. |
| **latency** | Quote real-time; news near-real-time. |
| **streaming** | `realtime_quote` (quote endpoint is real-time) but **no bar stream** — not charting-grade. |
| **cost** | Free tier (news + calendar + quote). Paid **Fundamental** tiers for deeper financials. |
| **auth/config** | `FINNHUB_API_KEY`. REST. Wired as free news source in `data_preferences`. |
| **limits** | Free ≈ **60 calls/min**. |
| **known_quirks** | ⚠️ **Biggest spec-vs-reality gap in the stack**: free news history is ~7 days, not 1 year — use Polygon for news archive. |
| **best_for** | **Earnings / IPO / economic calendar** (free, well-structured); quick real-time quotes. |
| **not_good_for** | News backtesting / history (~7 days only). |
| **verified_at** | 2025-12. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §Finnhub, `data_sources/DATA_SOURCE_QUIRKS.md`, `docs/design/P1_2_SPEC.md` (calendar), `docs/design/P1_2_PROVIDER_DISCOVERY.md`. |
| **app_settings_fields** | `finnhub.enabled` (toggle), `finnhub.api_key` (secret). |

### 3.3 Tiingo

| Field | Value |
|-------|-------|
| **provider** | Tiingo. |
| **implementation_status** | **live** (price fallback). |
| **connected_via** | `data_sources/tiingo_source.py` (REST). |
| **asset_classes** | US equities (EOD prices). |
| **data_types** | End-of-day OHLCV. |
| **history_depth** | **30+ years EOD** on the free tier. |
| **latency** | EOD (not intraday, not real-time). |
| **streaming** | `none` (EOD only). |
| **cost** | Free tier (30+ yr EOD). Paid **$10+/mo** for fuller access. |
| **auth/config** | `TIINGO_API_KEY`. REST. Config role: `data_preferences.prices.fallback`. |
| **limits** | Free-tier request caps (per Tiingo). |
| **known_quirks** | EOD-only; no intraday on the path used here. |
| **best_for** | **EOD price fallback** with long history for backtests (when IBKR is offline). |
| **not_good_for** | Intraday / real-time / charting. |
| **verified_at** | 2025-12. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §Tiingo, `data_sources/API_SPECIFICATIONS.md` §Tiingo. |
| **app_settings_fields** | `tiingo.enabled` (toggle), `tiingo.api_key` (secret). |

### 3.4 Alpha Vantage

| Field | Value |
|-------|-------|
| **provider** | Alpha Vantage. |
| **implementation_status** | **live**. |
| **connected_via** | `data_sources/alpha_vantage_source.py` (REST). |
| **asset_classes** | US equities, FX, **commodities**. |
| **data_types** | EOD + intraday prices; **news with AI sentiment** (50 articles, title+summary+URL — most detailed but mixed relevance); **commodity series** (WTI/Brent/NatGas/metals/agri). |
| **history_depth** | EOD long; **intraday only ~7 days**. |
| **latency** | Delayed. |
| **streaming** | `none` (delayed). |
| **cost** | Free **25 requests/day** (very restrictive). Paid tiers lift the cap. |
| **auth/config** | `ALPHAVANTAGE_API_KEY`. REST. |
| **limits** | Free **25 req/day** — effectively unusable for bulk; news returns 50 articles/query. |
| **known_quirks** | News is **mixed-relevance** — must post-filter on `relevance_score` (>0.7–0.8); returns all articles mentioning a ticker, not ticker-primary. |
| **best_for** | **Commodity series** mapping 1:1 to IBKR futures (CL/GC/NG/SI/ZC/ZW/ZS/KC/SB/CT); supplementary AI-sentiment news. |
| **not_good_for** | Anything high-volume (25/day); real-time. |
| **verified_at** | 2025-12. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §Alpha Vantage, `data_sources/IBKR_INVESTOR_DATA_VALUE.md` (commodity→futures mapping), `data_sources/API_SPECIFICATIONS.md`. |
| **app_settings_fields** | `alpha_vantage.enabled` (toggle), `alpha_vantage.api_key` (secret). |

### 3.5 EODHD (EOD Historical Data)

| Field | Value |
|-------|-------|
| **provider** | EODHD. |
| **implementation_status** | **optional-live** (paid). |
| **connected_via** | `data_sources/eodhd_source.py` (REST). |
| **asset_classes** | **Global** equities + fundamentals. |
| **data_types** | EOD prices; fundamentals; dividend/split (corporate-actions) calendar; news API. |
| **history_depth** | Long EOD history; broad global symbol coverage. |
| **latency** | EOD. |
| **streaming** | `none`. |
| **cost** | Paid **$19.99–$99/mo** by tier. |
| **auth/config** | `EODHD_API_KEY`. REST. |
| **limits** | Per-tier request caps. |
| **known_quirks** | Value is **breadth** (global markets) rather than US-depth; overlaps Tiingo/Polygon for US EOD. |
| **best_for** | Global EOD + fundamentals breadth; dividend/split calendar. |
| **not_good_for** | Real-time; US-only users may not need it (free options cover US EOD). |
| **verified_at** | 2025-12. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §7 EODHD, `docs/data/US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS.md`. |
| **app_settings_fields** | `eodhd.enabled` (toggle), `eodhd.api_key` (secret). |

### 3.6 SEC EDGAR

| Field | Value |
|-------|-------|
| **provider** | SEC EDGAR (US government). |
| **implementation_status** | **live**. |
| **connected_via** | `data_sources/sec_edgar_financials.py`, `sec_edgar_source.py`, `sec_filings.py`, `sec_insider_trades.py`, `sec_earnings_releases.py` (public REST + `edgartools`). |
| **asset_classes** | US equities (fundamentals + filings). |
| **data_types** | **XBRL structured financials** (Company Facts JSON); filings (10-K / 10-Q / 8-K); insider trades (Form 4); earnings releases. Derives ROE/ROA/D-E/current ratio/margins/revenue+earnings growth/FCF. |
| **history_depth** | **Full filing history** (decades). Quarterly + annual both implemented. |
| **latency** | Filing-driven (as companies file); not a quote feed. |
| **streaming** | `none`. |
| **cost** | **Free** (official SEC API; fair-use rate limits + a User-Agent header). |
| **auth/config** | No key; requires a descriptive `User-Agent`. `edgartools` integration. |
| **limits** | SEC fair-access throttle (~10 req/s); be polite. |
| **known_quirks** | Single-quarter vs cumulative-YTD detection (duration ≤105 days); **no Q4-from-10K** (10-K FY = annual total); scan all us-gaap concepts, not 3 hardcoded. |
| **best_for** | **Authoritative free fundamentals** for all US stocks; the free primary in the fundamentals fallback chain; insider + 8-K event detection. |
| **not_good_for** | Non-US companies; real-time/price data. |
| **verified_at** | 2026-01. |
| **source_links** | `data_sources/API_SPECIFICATIONS.md` §SEC EDGAR, `docs/analysis/FINANCIAL_METRICS_FORMULAS.md` (XBRL field mapping). |
| **app_settings_fields** | `sec_edgar.enabled` (toggle), `sec_edgar.user_agent` (text — required by SEC). |

### 3.7 Financial Datasets

| Field | Value |
|-------|-------|
| **provider** | Financial Datasets (financialdatasets.ai). |
| **implementation_status** | **optional-live** (paid, master-toggle gated). |
| **connected_via** | `data_sources/financial_datasets_client.py` (REST + local cache). |
| **asset_classes** | US equities (fundamentals). |
| **data_types** | Income/balance/cash-flow statements (annual/quarterly/TTM); **Segmented Revenue (unique)**; LLM-optimized response format. |
| **history_depth** | Multi-year statements. |
| **latency** | n/a (statements). |
| **streaming** | `none`. |
| **cost** | Paid ≈ **$30/mo** (Segmented Revenue tier); PAYG usage. Cached locally (DB + file) so repeat reads are free. |
| **auth/config** | `FINANCIAL_DATASETS_API_KEY`. **Master toggle** `data_preferences.paid_sources.financial_datasets.enabled` (false = never call). Cache TTL: annual 180d / quarterly 90d / ttm 30d. |
| **limits** | Per-plan; PAYG cost is the real limiter — gated by `metered_spend` (ProductSpec §4.3). |
| **known_quirks** | The **paid tertiary** in the fundamentals chain (IBKR snapshot → SEC EDGAR free → Financial Datasets paid); zero overhead when disabled. |
| **best_for** | **Segmented Revenue** (no alternative provider); clean LLM-formatted fundamentals fallback when SEC EDGAR is insufficient. |
| **not_good_for** | Anything SEC EDGAR already covers for free; price/real-time. |
| **verified_at** | 2026-01. |
| **source_links** | `data_sources/DATA_SOURCES_EVALUATION.md` §Financial Datasets (2026-01-14), `docs/data/US_STOCKS_OPTIONS_DATA_SUBSCRIPTIONS.md`. |
| **app_settings_fields** | `paid_sources.financial_datasets.enabled` (toggle, default OFF-safe), `financial_datasets.api_key` (secret), cache-TTL info. |

### 3.8 FRED

| Field | Value |
|-------|-------|
| **provider** | FRED (Federal Reserve Bank of St. Louis). |
| **implementation_status** | **live**. |
| **connected_via** | `data_sources/fred_client.py` + `src/macro_calendar/fred_ingestion.py` (REST). |
| **asset_classes** | Macro time-series (rates, CPI, NFP, GDP, etc.). |
| **data_types** | Economic series observations; **ALFRED point-in-time vintages**. |
| **history_depth** | **Decades** (full series history). |
| **latency** | Release-cadence (per series); not intraday. |
| **streaming** | `none`. |
| **cost** | **Free** (API key registration). |
| **auth/config** | `FRED_API_KEY`. REST. |
| **limits** | **2 requests/second** (HTTP 429 above); no documented monthly cap; persistent abuse → temporary block. |
| **known_quirks** | **Anti-lookahead is load-bearing**: `observation date` = date the value *refers to*, NOT the release date. Use ALFRED `realtime_start`/`realtime_end` vintages for point-in-time; naive `decision_date >= release_date` still leaks. |
| **best_for** | Macro context with **correct point-in-time semantics** for backtests; the macro half of the calendar (with Finnhub events). |
| **not_good_for** | Anything intraday or equity-specific. |
| **verified_at** | 2026-04. |
| **source_links** | `docs/design/P1_2_PROVIDER_DISCOVERY.md` §FRED/ALFRED, `docs/design/P1_2_SPEC.md`. |
| **app_settings_fields** | `fred.enabled` (toggle), `fred.api_key` (secret). |

### 3.9 Seeking Alpha (scraped — PROTECTED pipeline) **[FOUNDATION]**

| Field | Value |
|-------|-------|
| **provider** | Seeking Alpha. **NOT an API** — captured via browser extension (Chrome/Firefox) → Native Messaging host → DB. **This pipeline is a PROTECTED runtime surface — do not break it.** |
| **implementation_status** | **protected-pipeline** (foundation tier). |
| **connected_via** | `extension → src/sa_native_host.py → DB`; reader `data_sources/sa_alpha_picks_client.py` + the SA tool layer. |
| **asset_classes** | US equities (curated picks + community + news). |
| **data_types** | **Alpha Picks** (rank/score, open & closed); **comment intelligence** (rule-based community signals, `sql/012`); SA **market news** + article bodies. |
| **history_depth** | Per-capture (whatever has been scraped into the local DB). |
| **latency** | On-demand (user-triggered Quick Refresh / scheduled). |
| **streaming** | `extension_capture` (scraped, not a feed). |
| **cost** | A Seeking Alpha **account/subscription** (user's own); no API key. |
| **auth/config** | Browser login + installed extension + native-host launcher (`~/.local/share/arkscope/native-hosts/...` + `~/.config/arkscope/sa_native_host.json`). |
| **limits** | Scraping cadence; site ToS; capture scope limited to what the extension surfaces. |
| **known_quirks** | Alpha Picks **open/closed dual membership** — same `(symbol, picked_date)` can appear in both tabs; storage preserves tab membership (`sql/014`). Article capture is Markdown-only (no images / no right-rail Factor Grades). |
| **best_for** | **Curated picks + community sentiment** unavailable from any API; differentiated research signal. A foundation source — deepen its coverage first. |
| **not_good_for** | Anything needing an API contract / guaranteed uptime; bulk history. |
| **verified_at** | 2026-05. |
| **source_links** | `docs/design/SA_EXTENSION_ROADMAP.md`, `docs/design/SA_ALPHA_PICKS_CONTENT_CAPTURE.md`, `docs/design/SA_COMMENT_INTELLIGENCE_PLAN.md`, `data_sources/DATA_SOURCE_QUIRKS.md`. |
| **app_settings_fields** | `sa.enabled` (toggle), extension install status (read-only), native-host health (read-only ping), last-refresh timestamp. (No key field — account-gated in-browser.) |

### 3.10 Tavily (web / world search) **[FOUNDATION]**

| Field | Value |
|-------|-------|
| **provider** | Tavily. Surfaced as agent tools `web_search` / `web_fetch` (`src/tools/web_tools.py`); cataloged here as an external source. |
| **implementation_status** | **live** (foundation tier). |
| **connected_via** | `src/tools/web_tools.py` (tool, lazy-init client). |
| **asset_classes** | **Web / world (any topic)** — deliberately **not finance-only**. |
| **data_types** | Keyword web search with AI summary; URL content extraction (paginated). Covers **general world context: politics, international affairs, geopolitics, war** — events that move markets but aren't in financial feeds. |
| **history_depth** | Live web. |
| **latency** | Real-time fetch. |
| **streaming** | `none` (request/response fetch). |
| **cost** | API key; **free 1000 credits/mo**, paid above. Billable → heavy use gated by `metered_spend`; the egress itself gated by `external_web_access` (ProductSpec §4.3). |
| **auth/config** | `TAVILY_API_KEY`. Config flag `tavily: true`. |
| **limits** | Credit-based monthly quota. |
| **known_quirks** | Subject to **`external_web_access`** gate (network egress), distinct from `external_browser_automation`. It is a search/fetch API, **not** browser automation — do not conflate with the deferred CloakBrowser spike or the SA extension. |
| **best_for** | **General world/geopolitical context** + filling gaps local providers can't (breaking news, qualitative context, primary-source lookup). A foundation source — basic, broad situational awareness. |
| **not_good_for** | Structured/authoritative financial data (the providers above are better + cheaper). |
| **verified_at** | 2026-03. |
| **source_links** | `config/user_profile.yaml` (`tavily: true`), `src/tools/web_tools.py`. |
| **app_settings_fields** | `tavily.enabled` (toggle), `tavily.api_key` (secret), quota/credits status (read-only). |

---

## 4. Composition guidance (why the stack has overlap)

The providers are **deliberately layered** for fallback + cross-validation — this drives the agent's source-selection and the Settings "which providers do I need?" UX. **Foundation sources (IBKR, SA, Tavily) are the spine; the rest fill specific gaps:**

- **Prices**: realtime = **IBKR** → fallback = Tiingo (config `data_preferences.prices`).
- **Fundamentals**: local IBKR snapshot → SEC EDGAR (free) → Financial Datasets (paid, cached).
- **News**: **IBKR** (real-time, shallow) + Polygon (deep archive + AI sentiment) + Finnhub (quick, ~7d) — different depth/latency trade-offs.
- **Macro/calendar**: FRED (series) + Finnhub (events).
- **Curated**: **Seeking Alpha** (Alpha Picks + community signal) — unique, not API-replaceable.
- **World context**: **Tavily** (politics / international / geopolitics, beyond finance feeds).

This composition is what lets the agent **prefer provider-native signals** (ProductSpec §3) and pick the right source per question — and it tells the Settings UI which providers are foundational vs optional (§0.4).
