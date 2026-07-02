# PG-Exit Remainder Scoping (design skeleton v0)

- **Date:** 2026-07-01
- **Status:** DRAFT / survey v1 — local/runtime audit + provider survey folded; S-A1 demonstrator implemented; still not an implementation plan
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
| `data_scheduler.py:827` | `python -m src.news_normalized.ibkr_cli` | news | **converted in S-A1**; old script retained as compatibility wrapper |
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

- **Provider clients stay in `data_sources/` unless deliberately migrated.** That is the existing
  provider layer (`data_sources/ibkr_source.py`, `sec_edgar_financials.py`,
  `financial_datasets_client.py`, `polygon_source.py`, ...). Runtime orchestration / domain logic
  moves into `src/<domain>/...` modules (`src/news_normalized/`, `src/iv/`,
  `src/fundamentals/`, ...). Do **not** accidentally create a second provider layer under
  `src/providers/`.
- **Runtime imports `src/` only.** Subprocess isolation may stay, but its **target becomes `python -m src.<module>`, never `scripts/*.py`**.
- **Retirement = definition-of-done of each domain's cutover**, riding along that domain's migration. **Not** a standalone mega-refactor (avoid stalling PG-exit momentum).
- **First conversion candidate = the N8a IBKR news worker:** `scripts/collection/collect_ibkr_news_normalized.py`
  is **not** a trivial shell. `src/news_normalized/ibkr_runtime.py` holds the Gateway adapter, but
  the script still owns worker orchestration, DB/write locking, provider config injection,
  `stderr` suppression, sanitized stdout JSON, sanitized error classes, and continuation-count
  redaction. S-A1 must move this whole worker boundary into `src/news_normalized/ibkr_cli.py` and
  repoint the scheduler to `python -m src.news_normalized.ibkr_cli` while preserving the
  sanitization contract.

---

## 6. Slice breakdown (each own spec/plan/gate, TDD)

1. **S-A | scripts/ retirement rule + coupling baseline** — §4/§5 landed as a contract; S-A1 converted the IBKR news worker runtime boundary to `python -m src.news_normalized.ibkr_cli`. Remaining S-A work applies the same definition-of-done per domain.
2. **S-B | fundamentals refetch/cache** — *fast win, may run first / in parallel with the survey.* Stop the PG mirror for the fundamentals domain, retire the frozen `fundamentals` table as an authority, make `stored=true` read only local positive SEC annual-analysis `financial_cache` rows (`fundamentals_analysis:sec_edgar:{TICKER}:annual:v1`) and otherwise return honest empty, keep default analysis on SEC EDGAR / Financial Datasets fallback, reuse the existing TTL semantics, **check for non-US tickers** (EDGAR is US-only). Extract `src/fundamentals/`.
3. **S-C | IV provider survey** (decision axes in §7) → outputs a selection recommendation, no implementation.
4. **S-D | IV local schema reboot** (contract in §7): raw-retain + versioned-derive schema, provider-abstraction interface; no scheduling yet.
5. **S-E | IV IBKR small-scope computed-IV prototype** (10–30 tickers, near-month/ATM, fixed DTE-or-delta bucket, append-only, no gap-fill). Extract `src/iv/`.
6. **S-F | (optional) IV bulk provider backend** — only if the survey finds a fit; plugs into the same schema.
7. **S-G | scorer (news_scores) cutover** — place near N8b reads.
8. **S-H | orphan/audit + app-state relocation** — drop-orphan PG `news`/`sa_*` (confirm no reader first); decide app-state homes; audit macro/cal.
9. **S-I | N9 real drop** (§8).
10. **S-J | provider-config authority hardening (DB-first, fail-closed)** — orthogonal to the domain slices (provider *config*, not market data). Kill the two silent `config/.env` fallbacks (per-field overlay + whole-store startup degrade), surface per-field provenance with an explicit import affordance, then flip strict-by-default behind a tri-state. Contract in §13. **Phase 0–1 must land before S-E** so new IV provider keys are DB-native from day one.

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
- **Independent:** S-G (scorer), S-H (orphan/app-state audit), S-J (provider-config hardening — but its Phase 0–1 must land before S-E, §13.6).
- **Endgame:** S-I (N9), after each domain is localised and confirmed reader-free.

---

## 10. Open questions / decisions needed

1. **IV forward strategy:** historical options backfill now looks plausible in principle, but only the proof packet can decide if it is usable. It must verify historical IV/greeks completeness/reliability, provider rate limits, tier/pricing gates, and timestamp/input comparability before switching from forward-only to "one-time backfill + forward".
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
- IBKR news: S-A1 moved the normalized worker boundary into
  `src/news_normalized/ibkr_cli.py` and scheduler now launches it with
  `python -m src.news_normalized.ibkr_cli`; the old
  `scripts/collection/collect_ibkr_news_normalized.py` file is only a compatibility
  wrapper until N9/scripts cleanup.
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
| News scores | PG table and `migrate_to_supabase --scores` still exist, but local runtime code marks `news_scores` retired/deferred and score-dependent local reads do not fall back to PG | not a PG-exit blocker; treat as separate scoring/enrichment project or verified-dead PG drop, not part of IV/fundamentals work. Conscious tradeoff: hard-local news currently degrades multi-model sentiment/risk to `NULL`/`0` until a future scoring project exists |
| SA | local `sa_capture.db` is populated and SA tools prefer hard-local backend; a few health paths still use `job_runs` best-effort | PG `sa_*` is a likely orphan; grep-gate before drop; job telemetry belongs to app-state/ops, not SA market data |
| Fundamentals | S-B retires the frozen `fundamentals` mirror table as an authority; `stored=true` reads only local positive SEC annual-analysis `financial_cache` rows (`fundamentals_analysis:sec_edgar:{TICKER}:annual:v1`) and otherwise returns honest empty; live cache may initially be cold; default analysis remains SEC EDGAR / Financial Datasets refetch with local cache | PG-free after S-B; old `fundamentals` table is an N9 drop-orphan |
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

1. set stored-only fundamentals reads to local `financial_cache` only (no PG fallback, no provider fetch),
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
| Polygon / Massive Options | chain snapshot endpoint returns chain-level pricing details, greeks, IV, quotes/trades, open interest, and underlying asset data; historical quotes endpoint provides bid/ask records with precise timestamps but is plan-gated. | Best raw/bulk-style candidate if plan/history access is acceptable; supports own computation from raw snapshots. Proof packet must verify current product naming/plan boundaries ("Polygon" vs "Massive") and historical endpoint tier gates |
| Alpha Vantage | realtime US options can return full chains; `require_greeks=true` enables greeks/IV; historical options accept dates back to 2008-01-01 and can return a whole chain or a contract. | Strong cheap/accessible candidate for historical chain backfill, but proof packet must test whether historical IV/greeks are populated/reliable and whether low-tier rate limits make multi-ticker backfill impractical |
| EODHD / Unicorn options | marketplace product advertises US options EOD + historical data for 6,000+ symbols, two-year history, bid/ask/trade, volume, OI, IV (`volatility`), greeks, theoretical, DTE, midpoint. | Cheap EOD-history candidate; likely better for daily research snapshots than intraday raw reconstruction. Proof packet must verify product name, current availability, actual historical IV/greeks population, and cost/tier gates |
| Tradier | chain endpoint is per underlying + expiration and can include greeks/IV courtesy of ORATS. | Useful live broker-style source; less suitable as the historical raw backbone unless account terms fit. Its greeks/IV are ORATS-derived, so Tradier is not an independent cross-check against ORATS |
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
- **Proof-packet blockers:** a provider cannot be selected until the packet quantifies:
  historical IV/greeks non-null coverage, request limits for the desired
  `tickers × dates × expiries` backfill, exact tier/pricing gates, and whether any
  vendor-derived greeks are independent or just ORATS-derived.

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

Do not wait for the IV provider survey to do fundamentals. S-A1 is now complete and
serves as the scripts-retirement demonstrator.
Recommended next order:

1. **S-B fundamentals refetch/cache:** local-cache stored reads + provider fallback retained. **Status: implemented** once the S-B code commit lands.
2. **S-C IV provider proof packet:** compare Polygon/Massive, Alpha Vantage, EODHD,
   Tradier, ORATS, and IBKR against the raw-retain/versioned-derive contract.
3. **S-D IV schema design:** provider-neutral schema and status model.
4. **S-E IV IBKR prototype:** small scope only (10-30 tickers), fixed snapshot time,
   no gap-fill, honest failures.

---

## 13. Provider-config authority hardening design contract (core of S-J) — decisions locked 2026-07-02

**Problem.** The desktop premise is DB-first, but provider config today is
"DB-overlays-.env". `apply_env` (`src/data_provider_config.py:162`) first loads
`config/.env` (`env_keys.ensure_env_loaded()`), then overwrites per-field with
app-stored values. Two silent-fallback modes result:

- **per-field:** a managed field with no DB row silently serves the `config/.env`
  value — no prompt, no provenance shown at the point of use;
- **whole-store:** sidecar startup wraps `apply_env` in try/except-warning
  (`src/api/app.py:43`) — an unreadable profile DB silently degrades the whole
  process tree to pure-.env mode.

Both violate the desktop model (DB required; missing config = visible
"not configured", never a silent substitute). The **real shell env > app**
precedence is a deliberate operator escape hatch and does **not** change.

**Why convergence is cheap.** `.env` ingestion has a single choke point
(`src/env_keys.py`: `ensure_env_loaded` / `keys_loaded_from_file` /
`reload_var_from_file`); per-var provenance already exists
(`effective_source()` → `app | env | config/.env | missing`); the sidecar is the
parent of every collector subprocess, so one injection covers the tree; the S-A1
worker already applies DB config explicitly
(`src/news_normalized/ibkr_cli.py:125`).

### 13.1 Consumer classes (hardening applies to the first class only)

| Class | Examples | Rule |
|---|---|---|
| sidecar process tree | FastAPI app, scheduler, collector subprocesses | DB-first, fail-closed; provider keys enter ONLY via `apply_env` |
| spawned workers (standalone-capable) | `python -m src.news_normalized.ibkr_cli` | must call `apply_env(DataProviderConfigStore())` at startup (S-A1 precedent) |
| CLI + `scripts/` (retiring) | `src/agents/cli.py::_load_env()`, `scripts/*` | no investment; legacy `.env` behavior until retirement |

**Out of scope:** LLM credentials (auth-driver/token-store thread — deliberately a
different design); `DATABASE_URL`/PG DSN (`src/tools/data_access.py:381` — it IS
the PG-exit retirement target; stays .env-transitional until PG-exit completes);
OS keyring (existing backlog item); unit tests (they keep fake backends —
fail-closed is a runtime policy, not a test-fixture requirement).

### 13.2 Phase 0 — audit (output = a classification table appended here)

Inventory every provider env var and classify:

- **managed** (already in FieldDefs): `POLYGON_API_KEY`, `FINNHUB_API_KEY`,
  `FRED_API_KEY`, `FINANCIAL_DATASETS_API_KEY`, `IBKR_HOST` / `IBKR_PORT` /
  `IBKR_CLIENT_ID`;
- **`legacy_env_only`** (known candidates: `SEC_CONTACT_EMAIL` /
  `ARKSCOPE_SEC_USER_AGENT` (UA contract — attach to the existing `sec_edgar`
  provider); alpha_vantage / tiingo / eodhd api_keys (live readers exist — this
  absorbs the old "Slice A optional" FieldDefs list, incl. its
  `_TESTABLE`/connection-test decision); Discord ops token; `REDDIT_*`/FMP have
  no live reader → defer/retire) → each is either promoted to FieldDefs or
  recorded as `legacy_env_only`-with-reason. Under strict these keep working
  with a rendered warning — never blocked; no runtime `getenv()` interception
  sweep;
- **retiring consumer** (CLI/scripts) → listed, not fixed.

Grep surface: `_load_env|load_dotenv|config/\.env|os\.environ` (provider-key
reads) + FieldDefs registry. Read-only; no code change in Phase 0.

### 13.3 Phase 1 — visibility + hard startup (no default-behavior flip yet)

1. **Startup fail-closed = needs-setup mode, not process death:** unreadable
   profile DB at sidecar startup → boot into a setup-only state (replaces the
   `app.py:43` warn-and-continue): Settings/status surfaces stay up, but the
   scheduler loop is not started and provider fetch / collector subprocesses
   are disabled. The one forbidden outcome is today's behavior — silently
   continuing to collect on pure-.env config.
2. **Provenance surfaced:** status/Settings show `effective_source` per managed
   field; `config/.env` renders as "from config/.env — import suggested" with a
   **per-field** one-click import (Settings PUT exists; the 2026-06-27 .env→DB
   migration was one-shot, so this adds a first-class import affordance). No
   blind bulk import — any later batch action must be preview + selected-import.
3. **FieldDefs growth:** promote `SEC_CONTACT_EMAIL` / `ARKSCOPE_SEC_USER_AGENT`
   onto the existing `sec_edgar` provider (preserve the canonical-var-first
   precedence); promote the `legacy_env_only` candidates that pass the Phase-0
   promote/keep call.
4. **`IBKR_CLIENT_ID` seed + change guard** (already a FieldDef since Slice A —
   only the value was never seeded): if the DB row is missing, seed the explicit
   default `1`; Settings renders it app-managed (defaulted). Edits get a change
   guard (changing it disturbs IB Gateway sessions; the stored value is a *base*
   — `option_chain_tools` applies a +10 offset). The legacy `.env` name
   `IBKR_CLIENT` (never read by code) is not auto-ingested — explicit user
   import only.
5. **New-provider rule (effective immediately):** any provider added from now on
   (e.g. the S-F IV bulk backend) is DB-native only — no `.env` fallback is ever
   added for new keys.

### 13.4 Phase 2 — strict default (tri-state, news-S3.2 pattern)

- New setting `provider_env_fallback` (profile setting + env override),
  tri-state: **unset → strict** — FieldDefs-managed fields read DB-injected
  values only; a missing field is a structured
  `{code: "provider_config_missing", status: "not_configured", provider, field}`
  shared by provider-health, API routes, and agent tools (display layers may
  re-render it into their vocabulary, but consumers assert on the machine
  `code`, never on message text), and never a silent `.env` read.
  `legacy_env_only` vars keep working under strict with a rendered warning.
  Explicit `true` → legacy per-field fallback (migration/rescue). Explicit
  `false` → strict, pinned.
- Rollback = explicit `true`, mirroring the news S3.2 default-ON tri-state
  discipline (default is the new world; the old world needs an explicit flag).
- `config/.env` thereafter = import/export + migration material; real shell env
  remains the operator escape hatch (precedence unchanged).

### 13.5 Gates / tests

- strict + DB value present → the file loader is not consulted for that var
  (assert via `keys_loaded_from_file` bookkeeping / monkeypatched loader).
- strict + missing → `provider_config_missing` at all three surfaces
  (provider-health, API route, agent tool), asserted on the machine `code` — no
  exception, no silent empty.
- explicit `true` → legacy fallback restored (rollback path proven).
- unreadable profile DB → boots needs-setup: Settings/status reachable,
  scheduler not started, collector subprocess launch refused (lifespan test).
- `IBKR_CLIENT_ID`: missing row → seeded `1`; edit → change guard; legacy
  `IBKR_CLIENT` env name never auto-ingested.
- `legacy_env_only` var under strict → still works + warning rendered, not
  blocked.
- worker entrypoints apply DB config before provider construction (extend the
  S-A1 worker tests).
- §11 generic gate applies; the only persistent-state growth is additive
  FieldDefs rows in `profile_state.db` (no live market-DB step in this slice).

### 13.6 Sequencing

- Does not block S-C (survey is doc work; run in parallel).
- **Phase 0–1 land before S-E**, so the IV prototype's provider wiring is born
  DB-first and never grows a `.env` dependency.
- Phase 2 flips only after Phase 1 has soaked: Settings shows no remaining
  "from config/.env" managed fields on the primary machine (or each is a
  conscious keep), then default-strict is turned on.

### 13.7 Decisions (locked at review, 2026-07-02)

1. **Strict scope:** FieldDefs-managed vars only. No runtime interception sweep
   of all `getenv()` (that becomes a house-cleaning project). Unmanaged provider
   keys are listed in the Phase-0 table as `legacy_env_only`; under strict they
   warn but never block. New providers never gain `.env` fallback.
2. **`not_configured` shape:** shared structured error —
   `code: "provider_config_missing"` / `status: "not_configured"` — one shape
   for provider-health, routes, and tools; display layers may re-render it, but
   the machine `code` is the contract (never a text-only status).
3. **Import affordance:** Phase 1 ships per-field import only. No blind bulk
   import as a mainline flow (it would re-bless `.env` as an authority); any
   later batch action must be preview + selected-import.
4. **`IBKR_CLIENT_ID`:** becomes managed-with-value, guarded: Phase 1 seeds the
   explicit default `1` when the DB row is missing, Settings shows
   app-managed/defaulted, edits warn (IB Gateway session impact), and the legacy
   `IBKR_CLIENT` `.env` name is imported only on explicit user action.
5. **Startup semantics (correction):** fail-closed means *boot to setup-only* —
   Settings/needs-setup surfaces stay available while the scheduler, provider
   fetch, and collector subprocesses are disabled. It does not mean the sidecar
   dies; it does mean no silent pure-.env collection.
