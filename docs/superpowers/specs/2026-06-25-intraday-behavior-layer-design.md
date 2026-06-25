# Intraday Behavior Layer Design

Date: 2026-06-25
Status: design approved for review

## Purpose

ArkScope currently treats 15 minute bars as the main price freshness surface. That is useful for
coverage diagnostics, but it is not the right long-term data model for every research question.
The user needs a separate concept: whether a stock tends to trade in a choppy, whipsaw, trend,
quiet, or volatile-breakout pattern during the day.

This design adds an Intraday Behavior Layer. It computes deterministic intraday behavior metrics
from fine-grained bars, stores the metrics as the durable asset, and treats raw 1 minute or 5
minute bars as short-retention cache or ephemeral input. The layer is independent from the
market-data health panel and from the existing price_backfill source.

The next scheduler-hardening effort remains separate. This design produces the observations and
operation model that the scheduler can later use for controlled continuation and repair.

## Product Questions

The layer should answer:

1. Does this ticker usually move directionally or chop around intraday?
2. Is today's in-progress session already unusually choppy compared with the same time of day in
   the ticker's own history?
3. Which tickers are currently whipsaw-like, trend-like, quiet, or unusually volatile?
4. Can we compute and keep these signals without permanently storing large volumes of raw 1 minute
   data?

## Non-Goals

- No tick-level data in v1.
- No permanent all-universe 1 minute archive in v1.
- No blind recurring full-universe intraday sweep in v1.
- No provider black-box choppy score as the source of truth.
- No changes to the existing `/market-data/trading-days` coverage panel except future linking.
- No scheduler auto-repair in this spec. Scheduler hardening follows after this design is reviewed.

## Selected Approach

Use a metrics-first design with short-retention raw bars.

Durable:
- native adjusted daily OHLCV, handled by the broader price-tier plan;
- intraday behavior metrics;
- run telemetry and operation provenance.

Short-retention or ephemeral:
- 5 minute raw bars for selected tickers and recent windows;
- 1 minute raw bars only for focus tickers or explicit short probes;
- live bars / forming candles in memory unless the user chooses to cache them.

The first implementation should use 5 minute bars. They are fine enough for choppy and whipsaw
classification, while putting much less pressure on IBKR than 1 minute bars. The 1 minute interval
is an opt-in extension once 5 minute metrics prove useful.

## Alternatives Considered

### A. Persist all 1 minute bars

Pros:
- maximum flexibility for future metrics;
- can recompute any intraday feature later.

Cons:
- large storage footprint;
- high IBKR request pressure;
- hard to keep complete for the full universe;
- makes the desktop app feel like a market-data warehouse.

Rejected for v1.

### B. Provider technical indicators

Pros:
- lower implementation effort;
- some providers expose ATR, RSI, ADX, moving averages, and analytics.

Cons:
- choppy and whipsaw definitions are not standardized;
- provider definitions are harder to explain and backtest;
- not all providers expose the same intraday freshness or entitlement.

Rejected as the core approach. Provider indicators can be supplementary.

### C. Metrics-first with short raw cache

Pros:
- keeps durable data small;
- preserves interpretability;
- supports historical and live-so-far analysis;
- gives the scheduler a clear operation model and request budget.

Selected.

## Metrics

Input bars must be ordered intraday bars for one ticker and one trading session. For v1 the default
input is 5 minute RTH bars. Extended-hours support is explicit and separate.

Core metrics:

```text
returns[t] = log(close[t] / close[t-1])

intraday_abs_move = sum(abs(returns[t]))
intraday_net_move = abs(log(last_close / first_open))
intraday_efficiency = intraday_net_move / max(intraday_abs_move, eps)
intraday_chop_ratio = intraday_abs_move / max(intraday_net_move, eps)
intraday_sign_changes = count(sign(returns[t]) != sign(returns[t-1]))
intraday_realized_vol = sqrt(sum(returns[t]^2))
intraday_range_pct = (session_high - session_low) / first_open
close_location = (last_close - session_low) / max(session_high - session_low, eps)
```

Derived labels:

```text
trend
choppy
quiet
volatile_breakout
whipsaw
insufficient_data
```

The first labeler should be deterministic and rule-based. It should not depend on an LLM. A later
slice can add percentile-based calibration once enough baseline rows exist.

Example first-pass interpretation:

- trend: high net move, high efficiency, low or moderate sign changes;
- choppy: high absolute move, low efficiency, high sign changes;
- quiet: low absolute move and low range;
- volatile_breakout: high range, high net move, high efficiency;
- whipsaw: very high absolute move, very low efficiency, high sign changes;
- insufficient_data: too few bars for the interval/session type.

## Live So-Far Semantics

Intraday live analysis must compare "so far" with historical "same clock window" baselines.
Comparing 10:45 ET to a full trading day is invalid.

For a live probe at 10:45 ET:

```text
today window: 09:30-10:45 ET
baseline windows: prior trading days 09:30-10:45 ET
```

The API should report:

```text
as_of_time_et
session_progress_pct
bars_observed
baseline_sample_days
metric_percentiles
behavior_label_so_far
```

This prevents the UI from calling a normal morning session "incomplete" or comparing it to the
whole day.

## Storage

Use a separate logical domain inside `market_data.db` unless later profiling proves it should move
to a dedicated SQLite file. Keeping it in `market_data.db` is acceptable because the data is
regenerable and market-domain-owned, but the tables must not reuse `provider_sync_runs`.

### intraday_behavior_runs

```sql
CREATE TABLE intraday_behavior_runs (
  run_id              TEXT PRIMARY KEY,
  operation_type      TEXT NOT NULL,  -- live_probe | historical_scan | backfill | scheduled_scan
  source              TEXT NOT NULL,  -- ibkr | polygon | alpha_vantage
  interval            TEXT NOT NULL,  -- 5min first; 1min opt-in
  session             TEXT NOT NULL,  -- rth | extended | live_so_far
  scope               TEXT NOT NULL,  -- explicit ticker list summary or watchlist id
  storage_policy      TEXT NOT NULL,  -- metrics_only | cache_bars | persist_bars
  status              TEXT NOT NULL,  -- running | succeeded | failed | partial
  started_at          TEXT NOT NULL,
  finished_at         TEXT,
  tickers_requested   INTEGER NOT NULL DEFAULT 0,
  tickers_done        INTEGER NOT NULL DEFAULT 0,
  provider_requests   INTEGER NOT NULL DEFAULT 0,
  rows_cached         INTEGER NOT NULL DEFAULT 0,
  metrics_written     INTEGER NOT NULL DEFAULT 0,
  error               TEXT
);
```

`run_id` is independent from `job_runs.id` and `provider_sync_runs.id`. If a scheduler or API route
also creates a `job_runs` row, the job result should reference `intraday_behavior_runs.run_id`.

### intraday_behavior_metrics

```sql
CREATE TABLE intraday_behavior_metrics (
  ticker                TEXT NOT NULL,
  trading_date          TEXT NOT NULL,
  interval              TEXT NOT NULL,
  session               TEXT NOT NULL,
  as_of_time_et         TEXT,
  window_key            TEXT NOT NULL, -- as_of_time_et or 'close'
  run_id                TEXT NOT NULL,
  source                TEXT NOT NULL,
  bars_observed         INTEGER NOT NULL,
  expected_bar_hint     INTEGER,
  data_quality          TEXT NOT NULL, -- complete | partial | thin | live_so_far | insufficient

  abs_move              REAL,
  net_move              REAL,
  efficiency            REAL,
  chop_ratio            REAL,
  sign_changes          INTEGER,
  realized_vol          REAL,
  range_pct             REAL,
  close_location        REAL,
  behavior_label        TEXT NOT NULL,

  computed_at           TEXT NOT NULL,
  PRIMARY KEY (ticker, trading_date, interval, session, window_key)
);
```

`window_key` is deterministic: `as_of_time_et` for live-so-far rows, otherwise `close`.

### intraday_bar_cache

```sql
CREATE TABLE intraday_bar_cache (
  ticker       TEXT NOT NULL,
  datetime    TEXT NOT NULL,
  interval    TEXT NOT NULL,
  source      TEXT NOT NULL,
  open        REAL NOT NULL,
  high        REAL NOT NULL,
  low         REAL NOT NULL,
  close       REAL NOT NULL,
  volume      INTEGER NOT NULL,
  run_id      TEXT NOT NULL,
  expires_at  TEXT NOT NULL,
  PRIMARY KEY (ticker, datetime, interval, source)
);
```

Default storage policy:

- historical scan: `metrics_only`;
- live probe: `metrics_only`;
- user-requested debug/provenance run: `cache_bars` with a short TTL, initially 7 days;
- `persist_bars` disabled in v1 UI.

## Provider Strategy

IBKR is the v1 primary source because it is already integrated and free under the user's session.
It must share the existing IBKR lock so it cannot overlap with price_backfill, IV, news, or other
Gateway-heavy work.

The logical operation ID is independent. The provider client-id namespace should also be distinct
where the code supports it, so behavior scans are not confused with price backfills in logs and
Gateway diagnostics.

Provider fallback:

- IBKR primary for v1;
- Polygon can be a future fallback for historical 5 minute bars if plan entitlement is sufficient;
- Alpha Vantage can be a supplemental source for historical intraday bars or standard indicators,
  but not the source of truth for choppy labels.

## IBKR Request Control

The feature must be request-budgeted from v1.

Initial defaults:

```text
max_concurrent_ibkr_operations = 1
max_tickers_per_run = 20
max_trading_days_per_run = 60 for 5min
max_provider_requests_per_run = 60
request_cooldown_seconds = 2
operation_timeout_seconds = 900
```

If an operation exceeds budget, it finishes as `partial` and records continuation information. It
must not loop indefinitely. A later scheduler-hardening slice can resume from the saved operation
state.

These defaults are profile/env overridable, but the first implementation must ship with bounded
defaults even if no settings UI exists yet.

The first UI should make broad scans explicit. Opening a ticker page may run a small live probe for
that ticker, but it must not trigger an all-universe IBKR sweep.

## API Surface

Proposed routes:

```text
POST /intraday-behavior/runs
GET  /intraday-behavior/runs/{run_id}
GET  /intraday-behavior/ticker/{ticker}
GET  /intraday-behavior/scan/latest
```

`POST /runs` accepts:

```json
{
  "operation_type": "historical_scan",
  "tickers": ["AAPL", "CLS"],
  "interval": "5min",
  "session": "rth",
  "days": 30,
  "storage_policy": "metrics_only"
}
```

Response includes:

```json
{
  "run_id": "...",
  "status": "running",
  "operation_type": "historical_scan",
  "budget": {
    "max_tickers": 20,
    "max_provider_requests": 60
  }
}
```

## UI

Initial UI placement:

- ticker detail page: "Intraday behavior" panel;
- Settings/Data Sources later: provider budget and run history;
- no global dashboard in v1.

Ticker panel should show:

- recent behavior labels by day;
- percentile summary against this ticker's recent baseline;
- today so-far label if a live probe has run;
- latest operation ID and status;
- clear data-quality text: metrics-only, cached bars, or insufficient data.

UI should avoid implying trading advice. Labels describe behavior only.

## Agent Tool Surface

Add a future read-only tool after the metrics table is stable:

```text
get_intraday_behavior(ticker, days=20, interval='5min')
```

It returns deterministic metrics and labels. It should not trigger a provider fetch by default.
An explicit `allow_probe=true` can be considered later, gated by permissions and request budget.

## Implementation Slices

### Slice 1: Pure metric calculator

- Input: ordered OHLCV bars.
- Output: metrics and deterministic behavior label.
- No database, no provider, no scheduler.
- Tests cover trend day, choppy day, whipsaw, quiet, insufficient bars.

### Slice 2: Schema and run store

- Add `intraday_behavior_runs`.
- Add `intraday_behavior_metrics`.
- Add optional `intraday_bar_cache`.
- Add run lifecycle helpers.
- Tests cover independent run_id, partial status, idempotent metric upsert.

### Slice 3: Historical 5 minute scan

- IBKR primary.
- Small explicit ticker list only.
- Shared IBKR lock.
- Metrics-first by default.
- No recurring scheduler.
- Live smoke on 1-2 tickers before any broad run.

### Slice 4: Ticker UI

- Show recent labels and metrics.
- Show latest run_id and data quality.
- No automatic all-universe scan.

### Slice 5: Live so-far probe

- Focus ticker only.
- Compare current window with historical same-time windows.
- Store metrics, not raw bars by default.

## Relation to Scheduler Hardening

Scheduler hardening comes next, but should not be mixed with the first Intraday Behavior Layer
implementation.

This design intentionally gives scheduler hardening these building blocks:

- explicit operation IDs;
- partial run status;
- request budgets;
- resumable scope;
- clear provider errors;
- read-only observation surfaces.

The scheduler hardening design should use the same pattern for price repair: observe gaps first,
run bounded operations second, persist continuation state, and resume safely after app restarts.

## Verification Strategy

Unit tests:

- metric calculator edge cases;
- live so-far window slicing;
- run lifecycle transitions;
- cache TTL behavior;
- no writes during read routes.

Integration tests:

- 5 minute scan with fake provider;
- IBKR lock interaction with existing price_backfill lock;
- operation timeout marks `partial` or `failed`, never leaves `running`.

Live tests:

- one ticker, one recent day, metrics-only;
- two tickers, 5 trading days, metrics-only;
- optional cache_bars run with TTL, then read from cache without provider call.

## Acceptance Criteria

- A user can compute intraday behavior metrics for a small ticker set without permanently storing
  raw 5 minute bars.
- Every operation has an independent `run_id`.
- A failed or interrupted operation is visible as failed or partial, not silently lost.
- IBKR operations are bounded and serialized.
- The ticker UI can explain whether a ticker tends to be trend-like, choppy, whipsaw-like, quiet,
  or volatile-breakout-like.
- The feature does not change the meaning of the existing market-data coverage panel.
