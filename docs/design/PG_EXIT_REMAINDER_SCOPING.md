# PG-Exit Remainder Scoping (design skeleton v0)

- **Date:** 2026-07-01
- **Status:** DRAFT / scoping skeleton — to be fleshed into per-slice specs
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
