# PG-Exit Remainder Scoping (design skeleton v0)

- **Date:** 2026-07-01
- **Status:** DRAFT / survey v1 — local/runtime audit + provider survey folded; still not an implementation plan
- **Context:** news-domain PG exit is LIVE-complete (`news_pg_exit_runs` id=1 completed, fail-closed). **Overall ArkScope PG exit is NOT complete.**
- **Purpose of this doc:** scope the *remainder* of the PG exit — enumerate residual PG domains, assign a destination strategy per domain, define the `scripts/` retirement rule with a runtime-coupling inventory as its gating input, produce the N9 drop list, and sequence the remaining slices. **This document implements nothing.**

Companion docs: `docs/design/PG_EXIT_COMPLETION_PLAN.md`, `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`.

---

## 1. Goals & non-goals

**Goals**
- Enumerate every residual PG domain and assign a destination strategy.
- Define the `scripts/` retirement rule, gated on the current runtime→`scripts/` coupling inventory (§4).
- Produce the N9 real drop list.
- Sequence the remaining slices with dependencies.

**Non-goals**
- No IV collector implementation, no prices migration, no code committed from this doc.
- No paid-provider selection (that is the survey slice, §6 S-C).

---

## 2. Classification framework (two cuts)

- **Cut A — domain nature:** `market-data` (prices / iv / fundamentals / news_scores / macro / cal) vs `app-state` (agent_queries / research_reports / agent_memories / job_runs / signals). **Destinations differ:** market-data follows Cut B; app-state → a local state store or retirement, **never into `market_data.db`**.
- **Cut B — market-data strategy:** `re-fetchable? × volume × in-use?` →
  - not re-fetchable + large + core → **migrate**
  - re-fetchable + small / on-demand → **refetch/cache**
  - already localised / no longer read → **drop-orphan**
  - not re-fetchable but abandoned → **drop + forward-only rebuild**

---

## 3. PG domain inventory + destination

`reltuples` estimates from `pg_class` (2026-07-01). `?` = to be confirmed in the audit slice.

| PG table | ~rows | Cut A | Strategy | Notes |
|---|---|---|---|---|
| `prices` | 2.25M | market | **migrate** | re-fetchable but large; N7-style migration; own slice |
| `news_scores` | 503k | market | **cutover (scorer)** | scorer still on PG; place near N8b reads |
| `news` (PG) | 343k | market | **drop-orphan** | not read by app post-N8a → N9 drop |
| `sa_*` (comments/signals/market_news/articles/alpha_picks) | ~95k | market | **drop-orphan?** | SA already local (`sa_capture.db`); confirm no reader before drop |
| `fundamentals` | 130 | market | **refetch/cache** | EDGAR base + paid supplement; period-aware TTL |
| `iv_history` | ~24 | market | **drop + forward reboot** | abandon old data; rebuild capability |
| `macro_*` / `cal_*` | ? | market | **audit** | local `macro_calendar.db` exists → confirm which are already local |
| `financial_data_cache` | ? | market (cache) | **drop / local cache** | it is a cache by definition |
| `job_runs` | 13k | app-state | **relocate/retire** | operational log |
| `agent_queries` / `research_reports` / `agent_memories` / `signals` | ? | app-state | **relocate/retire** | local state store, NOT `market_data.db` |

---

## 4. `scripts/ → src/` runtime coupling inventory (gating input for retirement)

> Hard fact: **`scripts/` IS the current ingest runtime.** Retirement = extracting these into `src/` one domain at a time, not a cleanup pass.

### A. In-process imports (runtime imports `scripts/` directly)

| Caller | `scripts/` target | Domain |
|---|---|---|
| `src/news_providers.py:132/136` | `collect_polygon_news` / `collect_finnhub_news` | news |
| `src/service/data_scheduler.py:115/122/272/284` | `collect_polygon_news` / `collect_finnhub_news` (`run_incremental`) | news |

### B. Subprocess launches (`_COLLECT_DIR = scripts/collection`)

| Location | Target | Domain | State |
|---|---|---|---|
| `data_scheduler.py:827` | `collect_ibkr_news_normalized.py` | news | **active (shipped in N8a)** |
| `data_scheduler.py:128` → 938 | `collect_ibkr_news.py` | news | **likely dead** (post-exit routing never selects legacy) → confirm, then retire |
| `data_scheduler.py:135` → 938 | `collect_ibkr_prices.py` | prices | active |
| `data_scheduler.py:141` → 938 | `collect_iv_history.py` | iv | idle (collection stopped) |
| `data_scheduler.py:958` | `migrate_to_supabase.py <sync_flag>` (`_MIGRATE`) | PG sync | retires per-domain as each leaves PG; fully gone at N9 |

### C. Parallel CLI path

`scripts/collection/daily_update.py` shares `run_source` with the scheduler; `job_runs` uses `daily_update.*` step aliases. → collapse into a thin `src/` entrypoint or retire.

### D. Docstring mentions only (not couplings; low priority)

`market_data_admin.py:22` (migrate_market_to_sqlite), `db_config.py:5` (migrate_to_supabase), `auth_drivers/chatgpt_oauth_probe.py:5`, `agents/shared/replay.py:4` (replay_run.py = companion CLI). → wording/classification only, non-blocking.

---

## 5. `scripts/` retirement rule (principle)

- **Logic lives in `src/` domain modules** (`src/providers/`, `src/iv/`, `src/fundamentals/`, …). `scripts/` either disappears or remains only as **one-time migration** tooling.
- **Runtime imports `src/` only.** Subprocess isolation may stay, but its **target becomes `python -m src.<module>`, never `scripts/*.py`**.
- **Retirement = definition-of-done of each domain's cutover**, riding along that domain's migration. **Not** a standalone mega-refactor (avoid stalling PG-exit momentum).
- **First conversion candidate = the N8a IBKR news worker:** its logic already lives in `src/news_normalized/ibkr_runtime.py`; `scripts/collection/collect_ibkr_news_normalized.py` is a thin shell → repoint the subprocess to `python -m src.news_normalized.ibkr_cli` to decouple (small change, demonstrates the pattern).

---

## 6. Slice breakdown (each own spec/plan/gate, TDD)

1. **S-A | scripts/ retirement rule + coupling baseline** — land §4/§5 as a contract + first demonstrator conversion (IBKR news worker → `python -m src`).
2. **S-B | fundamentals refetch/cache** — *fast win, may run first / in parallel with the survey.* Stop the PG mirror for the fundamentals domain, route reads to the local cache + EDGAR fallback, reuse the period-aware TTL, warm the active universe on cold start, **check for non-US tickers** (EDGAR is US-only). Extract `src/fundamentals/`.
3. **S-C | IV provider survey** (decision axes in §7) → outputs a selection recommendation, no implementation.
4. **S-D | IV local schema reboot** (contract in §7): raw-retain + versioned-derive schema, provider-abstraction interface; no scheduling yet.
5. **S-E | IV IBKR small-scope computed-IV prototype** (10–30 tickers, near-month/ATM, fixed DTE-or-delta bucket, append-only, no gap-fill). Extract `src/iv/`.
6. **S-F | (optional) IV bulk provider backend** — only if the survey finds a fit; plugs into the same schema.
7. **S-G | scorer (news_scores) cutover** — place near N8b reads.
8. **S-H | orphan/audit + app-state relocation** — drop-orphan PG `news`/`sa_*` (confirm no reader first); decide app-state homes; audit macro/cal.
9. **S-I | N9 real drop** (§8).

---

## 7. IV reboot design contract (core of S-C/S-D)

- **Two layers:**
  - `iv raw/snapshot layer`: input-complete enough to **recompute** — quotes, greeks, open interest, **`snapshot_at` (fixed time-of-day)**, underlying price, rate/dividend assumptions, strike/DTE selection rule, `num_quotes`, spread, confidence, provider, method.
  - `iv research-metric layer`: ArkScope-computed (ATM IV / term structure / VRP / event IV), **method-versioned (`iv_method_version`)**, a deterministic function of the raw layer; improving the method **recomputes from stored raw, no re-fetch** (same pattern as news `cleaner_version`).
- **Build/buy line (driven by the "own the computation" value):**
  - **Buy RAW bulk** (Polygon-style chain/greeks/quotes/OI + historical) → feed your own compute; solves the IBKR rate-limit; does not compromise research autonomy.
  - **Pre-derived (ORATS surface / ex-earnings vol)** = reference only, or for metrics you won't build — not the backbone.
  - **Cross-check precondition:** comparing your IV vs a provider's is only meaningful when **inputs are comparable** (same time, quotes, assumptions); otherwise treat as two independent series, not validation.
- **Constraints:** no interpolation (a gap is a gap, marked explicitly); the series is **sparse/irregular**, so the research layer must not assume daily continuity; per-ticker failures must be attributable (attempted-no-data vs not-attempted, reusing the news honest-status discipline).
- **Monitoring (make-or-break for the reboot):** scheduling must be monitored — a missed day must alert. The old collector **died silently in March and went unnoticed for ~4 months**; a forward-only series is only as good as collector uptime.

---

## 8. N9 real drop list (draft — grep-confirm "no training/report/migrate/other script still reads" before each drop)

- PG `news` (343k, orphaned)
- PG `sa_*` (SA already local)
- PG `iv_history` (old 24 rows)
- PG `fundamentals` (130, after refetch)
- the news/fundamentals/iv `--sync` paths in `migrate_to_supabase.py`
- **Retain:** `prices` (pending migration slice), `news_scores` (pending scorer cutover), any incomplete domain.

---

## 9. Sequencing & dependencies

- **Parallel / can-go-first:** S-A (demonstrator conversion), S-B (fundamentals fast win), S-C (survey).
- **Dependency chain:** S-C → S-D → S-E → (optional) S-F → wire scheduler/UI/tool.
- **Independent:** S-G (scorer), S-H (orphan/app-state audit).
- **Endgame:** S-I (N9), after each domain is localised and confirmed reader-free.

---

## 10. Open questions / decisions needed

1. **IV forward strategy:** accept forward-only, or — if the survey finds an affordable historical IV / option-chain vendor — switch to "one-time backfill + forward"? (The only finding that overturns the "not re-fetchable" premise.)
2. **app-state homes:** `agent_queries` / `research_reports` / `agent_memories` / `signals` / `job_runs` → which local store (`profile_state.db`? a new `ops.db`?) or retire?
3. **macro/cal:** is `macro_calendar.db` already the local authority? Are PG `macro_*` / `cal_*` orphans or still authoritative?
4. **scorer timing:** cutover `news_scores` *before* or *with* N8b reads?
5. **prices:** confirm migrate (not refetch); when to schedule.
6. **legacy `collect_ibkr_news.py`:** confirm it is dead post-exit → can it be retired directly?

---

## 11. Per-slice generic gate (reuse proven discipline)

- For slices that touch the live DB: preview (`mode=ro`) → fingerprint → backup (`O_EXCL`) → single txn → validate → rollback-able → reopen-RO verify; no `--force`.
- Before any retirement / drop: grep-confirm no runtime/script reader remains.
- Each slice: TDD + green offline gate + independent review (plus an independent re-check when touching the live DB).

---

## 12. Survey v1 evidence (2026-07-01)

This section records the first concrete survey pass. It is intentionally scoped to
evidence and ordering; it does not authorize any live schema change or code cutover.

### 12.1 Local stores already present

Read-only SQLite checks (`PRAGMA quick_check`) all passed:

| Local DB | Relevant tables / counts | Survey conclusion |
|---|---:|---|
| `data/market_data.db` | `prices=2,312,165`, `news=377,650`, `news_articles=290,241`, `iv_history=24`, `fundamentals=130`, `news_legacy_migration_map=371,575`, `news_legacy_projection_map=43,603` | news-domain cutover is represented locally; prices are large enough to migrate; IV/fundamentals local rows are tiny legacy snapshots |
| `data/sa_capture.db` | `sa_articles=394`, `sa_market_news=21,747`, `sa_alpha_picks=111` | SA data is local; PG `sa_*` should be treated as a drop-orphan candidate after reader grep |
| `data/profile_state.db` | `agent_queries=2`, `research_reports=2`, `agent_memories=1`, plus `scheduler_state`, `data_provider_config`, research thread tables | app-records already have a local app-state home; future app-state should not go into `market_data.db` |
| `data/macro_calendar.db` | `macro_*` / `cal_*` tables present | macro/cal likely already have a local authority; confirm no PG authority remains before drop |

### 12.2 Runtime couplings that are still real

The `scripts/` retirement rule in §5 is not optional hygiene. Current runtime still
uses `scripts/` in these ways:

- Polygon/Finnhub news: `src/news_providers.py` and `src/service/data_scheduler.py`
  still lazily import `scripts.collection.collect_polygon_news` and
  `scripts.collection.collect_finnhub_news`.
- IBKR news: N8a's normalized worker is launched as
  `scripts/collection/collect_ibkr_news_normalized.py`, even though the real logic
  lives in `src/news_normalized/ibkr_runtime.py`.
- IBKR prices and IV: scheduler subprocesses still target
  `scripts/collection/collect_ibkr_prices.py` and `scripts/collection/collect_iv_history.py`.
- PG sync: `scripts/migrate_to_supabase.py` remains the domain sync target for
  unfinished domains (`--prices`, `--iv`, `--fundamentals`, and opt-in `--scores`).
- `scripts/collection/daily_update.py` remains a parallel CLI runtime path and writes
  `daily_update.*` job aliases that scheduler state still recognizes.

Therefore "scripts retirement" must be a per-domain definition-of-done:

1. extract runtime logic into a `src/<domain>/...` module,
2. keep subprocess isolation where it is technically valuable,
3. launch subprocesses with `python -m src.<domain>.<entrypoint>`, and
4. leave `scripts/` only for one-shot migration/backfill tools until they are retired.

### 12.3 Domain disposition after survey

| Domain | Current survey finding | Disposition |
|---|---|---|
| News | hard-local reads and normalized local writes are live; PG news is no longer the app authority | N9 drop candidate after final reader grep; keep legacy local projection until N8b/N9 |
| News scores | PG table and `migrate_to_supabase --scores` still exist, but local runtime code marks `news_scores` retired/deferred and score-dependent local reads do not fall back to PG | not a PG-exit blocker; treat as separate scoring/enrichment project or verified-dead PG drop, not part of IV/fundamentals work |
| SA | local `sa_capture.db` is populated and SA tools prefer hard-local backend; a few health paths still use `job_runs` best-effort | PG `sa_*` is a likely orphan; grep-gate before drop; job telemetry belongs to app-state/ops, not SA market data |
| Fundamentals | local table has only 130 stored snapshots; default analysis already does stored → SEC EDGAR → Financial Datasets; stored-only UI path can still PG-fallback unless strict | fast win: stop fundamentals mirror/sync, make stored path local-only with honest empty, rely on local financial cache + SEC/paid fallback |
| IV | only 24 local rows; scheduler still routes `iv_history` through IBKR script → PG → mirror; tools/UI read local with PG fallback on miss | abandon old 24 rows as experimental; preserve capability via rebooted local schema + provider abstraction |
| Prices | local table has 2.3M rows and price data is core | migrate/direct-local slice; do not refetch 2.3M by default |
| Macro/cal | local `macro_calendar.db` exists | audit readers and PG tables; likely local authority already |
| App state / ops | profile app-records are local, but `job_runs` remains PG-backed telemetry | decide `job_runs` home (`scheduler_state` / `profile_state.db` / new `ops.db`) separately from market data |

### 12.4 Fundamentals survey

The fundamentals direction is unchanged: refetch/cache, not PG migration.

- SEC EDGAR is the primary free source for US public-company filings and extracted
  XBRL; the SEC's developer guidance explicitly exposes data APIs and requires fair
  access discipline, currently no more than 10 requests per second across machines.
- Existing code already caches SEC-derived fundamentals into `financial_cache`, and
  negative SEC misses are short-cached to avoid hammering uncovered tickers.
- EODHD is a reasonable paid/global supplement candidate: its docs cover fundamentals
  for stocks/ETFs/funds/indices across US and non-US exchanges, with broad historical
  coverage and versioned fundamentals endpoint guidance.

Slice implication: fundamentals should be a small PG-exit slice, not an N7-style
migration. Required gates:

1. set stored-only fundamentals reads to local-only under PG-exit (no PG fallback),
2. preserve default `get_fundamentals_analysis` provider fallback,
3. keep/verify SEC User-Agent + backoff/rate limit,
4. scan active universe for non-US / EDGAR-uncovered symbols,
5. optionally pre-warm active-universe fundamentals into local `financial_cache`, and
6. retire `migrate_to_supabase --fundamentals` only after the local-only smoke passes.

### 12.5 IV provider survey

The IV decision is not "keep old rows vs drop old rows"; the old rows are too small
and stale to matter. The real decision is how to build a forward research-grade IV
dataset without making IBKR rate limits the backbone.

| Provider | What official docs indicate | Fit for ArkScope |
|---|---|---|
| IBKR TWS/Gateway | `reqContractDetails` can enumerate option chains but complete chains are throttled and not recommended for all strikes/rights/expiries; `reqSecDefOptParams` improves chain definition discovery but returns expirations/strikes, not all market quotes. Greeks/IV arrive through option market data subscriptions and tick computations. | Good for a small-scope computed-IV prototype and live cross-checks; poor as the 148-ticker daily backbone |
| Polygon / Massive Options | chain snapshot endpoint returns chain-level pricing details, greeks, IV, quotes/trades, open interest, and underlying asset data; historical quotes endpoint provides bid/ask records with precise timestamps but is plan-gated. | Best raw/bulk-style candidate if plan/history access is acceptable; supports own computation from raw snapshots |
| Alpha Vantage | realtime US options can return full chains; `require_greeks=true` enables greeks/IV; historical options accept dates back to 2008-01-01 and can return a whole chain or a contract. | Strong cheap/accessible candidate for historical chain backfill; needs payload/time semantics verification before choosing |
| EODHD / Unicorn options | marketplace product advertises US options EOD + historical data for 6,000+ symbols, two-year history, bid/ask/trade, volume, OI, IV (`volatility`), greeks, theoretical, DTE, midpoint. | Cheap EOD-history candidate; likely better for daily research snapshots than intraday raw reconstruction |
| Tradier | chain endpoint is per underlying + expiration and can include greeks/IV courtesy of ORATS. | Useful live broker-style source; less suitable as the historical raw backbone unless account terms fit |
| ORATS | API focuses on volatility summarizations, smoothed parameterized curves, derived IV/earnings/volatility metrics, live/1-minute/snapshot APIs. | Excellent reference/specialist data; not the backbone if ArkScope wants to own derived IV computation |

Survey recommendation:

- **Backbone preference:** buy/access raw or near-raw chain/quote/OI snapshots and compute
  ArkScope metrics from retained inputs.
- **IBKR role:** keep as bounded prototype/cross-check, not full-universe daily collector.
- **Pre-derived role:** ORATS/vendor surfaces are reference/enrichment, not the canonical
  research dataset unless a future product decision explicitly chooses vendor-derived IV.
- **Next IV slice output:** a provider proof packet, not production code: sample payload
  fields, timestamp semantics, history depth, cost/rate constraints, and whether the same
  raw snapshot is sufficient to recompute ATM IV / term structure / VRP.

### 12.6 IV reboot schema implications

The reboot schema should be designed before choosing the provider. It must support both
IBKR prototype and bulk provider backends:

- raw snapshot table: provider, snapshot_at, underlying price, contract identity, strike,
  expiry, call/put, bid/ask/last/mid, bid/ask sizes, volume, OI, quote/trade timestamps,
  provider greeks/IV if supplied, rate/dividend assumptions if available, raw payload
  hash/ref, and confidence inputs such as spread and `num_quotes`;
- derived metrics table: deterministic ArkScope outputs (`atm_iv`, term buckets, VRP,
  event-vol fields), `iv_method_version`, source snapshot id(s), selection rule, and
  confidence;
- status table: attempted/no-data/error/not-attempted per ticker/date/provider, so gaps
  are visible and never silently interpolated.

### 12.7 Immediate slice recommendation

Do not wait for the IV provider survey to do fundamentals or the scripts demonstrator.
Recommended next order:

1. **S-A1 scripts demonstrator:** repoint N8a IBKR news worker from
   `scripts/collection/collect_ibkr_news_normalized.py` to `python -m src.news_normalized...`.
   This proves the retirement rule without changing behavior.
2. **S-B fundamentals refetch/cache:** local-only stored reads + provider fallback retained.
3. **S-C IV provider proof packet:** compare Polygon/Massive, Alpha Vantage, EODHD,
   Tradier, ORATS, and IBKR against the raw-retain/versioned-derive contract.
4. **S-D IV schema design:** provider-neutral schema and status model.
5. **S-E IV IBKR prototype:** small scope only (10-30 tickers), fixed snapshot time,
   no gap-fill, honest failures.
