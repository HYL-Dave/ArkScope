# IBKR News Long-Catch-Up Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for the audit utility and superpowers:verification-before-completion before claiming the slice is complete. This is an audit-first slice; do not change runtime ingestion behavior unless a reviewed follow-up plan is opened.

**Goal:** Quantify whether normalized IBKR news can miss tail articles after a long quiet window because IBKR historical news returns only the 300 most-recent headlines per ticker, then document the operational boundary and any follow-up decision.

**Architecture:** The current runtime is scheduler -> sanitized `src.news_normalized.ibkr_cli` subprocess -> `IBKRRuntimeGateway.fetch_headlines()` -> `IBKRDataSource.fetch_news()` -> `reqHistoricalNews(..., totalResults=300)`. The normalized writer uses a local latest-cursor per ticker, but IBKR ignores the requested date range, so the provider call is not a true cursor. This slice measures the risk from local SQLite evidence and code-level facts; it does not attempt to page IBKR because there is no supported provider cursor in the existing API.

**Tech Stack:** Python 3, pytest, SQLite read-only URI connections, existing normalized-news tables, local scheduler state.

## Map Check

- This is the only active queue item recorded by the 2026-07-06 dead-code/UI sweep closeout.
- It is a post-PG-exit follow-up. It must not reintroduce PG, PG mirrors, or runtime fallback paths.
- It must not change news ingestion cadence, IBKR Gateway locking, or normalized writer behavior without a separate reviewed implementation plan.
- It is non-blocking: normal scheduled IBKR news cadence is already green; this audit scopes long quiet-window catch-up risk only.

## Current Grounding

- `docs/data/IBKR_NEWS_API_LIMITATIONS.md` records the API-level fact: `reqHistoricalNews` ignores `startDateTime` / `endDateTime` and returns the 300 most-recent articles for the contract.
- `data_sources/ibkr_source.py::_fetch_news_single_query()` calls `reqHistoricalNews(..., 300)` exactly once per ticker.
- `data_sources/ibkr_source.py::fetch_news()` documents that `start_date` / `end_date` are ignored by IBKR and that the maximum is 300 articles per ticker.
- `src/news_normalized/ibkr_runtime.py::IBKRRuntimeGateway.fetch_headlines()` converts `since_iso` to a date and passes it to `fetch_news()`, but the provider does not honor it.
- `src/news_normalized/ibkr_cli.py` has `DEFAULT_MAX_ARTICLES=50_000`; the writer budget is not the live bottleneck for the observed 148-ticker runs.
- Live read-only snapshot on 2026-07-06:
  - `scheduler_state.ibkr_news`: `last_status=succeeded`, `continuation=NULL`, last result `ticker_count=148`, `articles_seen=15068`, `articles_inserted=0`.
  - Recent `provider_sync_runs` for `ibkr/news`: all succeeded; latest runs scanned 148 tickers and added 0 rows after the first post-burst catch-up.
  - Local normalized IBKR articles: 84,381 unique `news_articles` rows; 150 ticker links have IBKR coverage.
  - Last 7 days: max per ticker = 130 (`GOOG`/`GOOGL`), no ticker >= 200, no ticker >= 300.
  - Last 30 days: 6 tickers >= 300, 8 tickers >= 250, 14 tickers >= 200; max = 549 (`MU`).

## Decisions Locked

1. **Audit-first.** This slice produces a reproducible read-only risk report and docs closeout. A runtime fix is out of scope until the report says one is needed.
2. **Do not "fix" by raising writer budgets.** The provider-side 300 cap is the risk; `DEFAULT_MAX_ARTICLES=50_000` is already above observed run size.
3. **No initial live IBKR Gateway probe.** The first pass must be local read-only only. A live Gateway dry-run requires a separate explicit approval because it spends provider/Gateway calls and can be affected by subscriptions/session state.
4. **Normal cadence is distinct from long catch-up.** A 7-day local window currently stays well below the cap; a 30-day quiet window does not. The report must state this distinction instead of labeling IBKR news generally broken.
5. **No fake continuation.** Current sanitized IBKR worker output carries only continuation counts, so the scheduler cannot reconstruct a full `WriterContinuation`; attended-mode also does not auto-resume saved normalized-news partials. Do not add a partial/continue mechanism unless a follow-up plan defines a real provider-side cursor or replacement strategy.

## Stop-Loss Triggers

Stop and report before continuing if any of these happen:

- The audit utility needs to open SQLite without `mode=ro`.
- The implementation attempts to import or instantiate `IBKRDataSource`, `IBKRRuntimeGateway`, or any Gateway client.
- A proposed fix changes runtime ingestion behavior in this audit slice.
- The live read-only report shows inconsistent counts across two immediate runs that cannot be explained by an active writer.
- Tests require touching existing user/training dirty files or profile data.

## Review Gates

1. Static grep proves the audit utility has no IBKR/Gateway imports and no write SQL verbs.
2. Unit tests prove the utility opens SQLite read-only, computes per-window cap risk, and emits stable JSON.
3. A live local read-only audit report is produced twice with the same explicit `--as-of`; core counts are byte-identical or the report records the active-writer explanation. Do not require byte identity across different `--as-of` values because trailing windows intentionally drift by date.
4. The report distinguishes:
   - current cadence safety,
   - long quiet-window cap risk,
   - provider/API limitation,
   - methodology caveats,
   - non-goals.
5. `pytest tests/test_ibkr_news_catchup_audit.py -q` passes.
6. Focused existing tests pass: `pytest tests/test_normalized_ibkr_worker.py tests/test_news_normalized_ibkr_adapter.py tests/test_data_scheduler.py -q`.
7. Full A/B is not mandatory for a read-only script/docs slice, but if any runtime code is touched, full A/B becomes mandatory.
8. `docs/design/PROJECT_PRIORITY_MAP.md` records the audit result and next decision, without reopening PG-exit.

---

## Task 1: Add Read-Only Audit Utility

**Files:**

- Add: `scripts/audit/ibkr_news_catchup_audit.py`
- Add: `tests/test_ibkr_news_catchup_audit.py`

- [ ] **Step 1: Write RED tests for report shape**

Create fixtures with minimal `news_articles`, `news_article_tickers`, `provider_sync_runs`, and `scheduler_state` schemas. The utility should return:

```python
{
    "ok": True,
    "source": "ibkr",
    "windows": {
        "7d": {"max_rows": 130, "tickers_ge_300": 0, ...},
        "30d": {"max_rows": 549, "tickers_ge_300": 6, ...},
    },
    "top_tickers": [...],
    "gap_checks": [
        {
            "label": "observed_quiet_window_2026_06_25_to_2026_07_05",
            "start_date": "2026-06-25",
            "end_date": "2026-07-05",
            "max_rows": 180,
            "tickers_ge_300": 0,
            "assessment": "below_cap",
        }
    ],
    "scheduler_state": {...},
    "provider_runs": [...],
    "caveats": [
        "Local SQLite counts are a lower bound: articles already missed by a prior provider-side 300 cap cannot be counted locally.",
        "A ticker-window below 300 proves only that observed local rows are below the cap, not that no historical tail was ever truncated before this audit.",
        "days_to_300 estimates assume roughly stable article arrival rates and should be treated as planning guidance, not a guarantee.",
    ],
    "risk": {
        "current_cadence": "ok",
        "long_quiet_window": "at_risk",
        "reason": "IBKR reqHistoricalNews returns only the 300 most-recent headlines per ticker",
    },
}
```

Expected: FAIL because the module does not exist.

- [ ] **Step 2: Implement read-only SQLite collectors**

Implementation rules:

- Open `market_data.db` and `profile_state.db` with `sqlite3.connect("file:...?mode=ro", uri=True)`.
- Do not create missing DBs.
- Query only local tables.
- Normalize dates using `substr(published_at, 1, 10)` for the existing mixed `Z` / `+0000` timestamp suffixes.
- Compute at least these windows: 7d, 14d, 30d.
- Compute a named historical `gap_checks` list. The first required gap check is the real quiet window that motivated this audit:
  - label: `observed_quiet_window_2026_06_25_to_2026_07_05`
  - start date: `2026-06-25`
  - end date: `2026-07-05`
  - per-ticker article counts compared against the 300/ticker provider cap
  - top tickers by count and `tickers_ge_300` / `tickers_ge_250`
- Include per-ticker:
  - total IBKR article links,
  - window counts,
  - oldest/newest article timestamps,
  - estimated days-to-300 from 30d rate when possible.
- Include a `caveats` array with the lower-bound / prior-truncation / rate-stability warnings verbatim or semantically equivalent. These caveats are load-bearing: the report must not present local rows as complete provider truth.

- [ ] **Step 3: Add CLI wrapper**

CLI:

```bash
python -m scripts.audit.ibkr_news_catchup_audit \
  --market-db data/market_data.db \
  --profile-db data/profile_state.db \
  --as-of 2026-07-06 \
  --json-out scratchpad/ibkr-news-catchup-audit.json
```

Rules:

- stdout prints sanitized summary only.
- JSON artifact contains no provider secrets.
- `scratchpad/` output is not committed.

## Task 2: Static Runtime Boundary Tests

**Files:**

- Modify: `tests/test_ibkr_news_catchup_audit.py`

- [ ] **Step 1: Prove no Gateway access**

Test that the audit module source does not contain these imports or names:

- `IBKRDataSource`
- `IBKRRuntimeGateway`
- `ib_insync`
- `reqHistoricalNews`

- [ ] **Step 2: Prove writer budget is not the reported bottleneck**

The report should include `writer_budget_note` or equivalent text stating that `DEFAULT_MAX_ARTICLES=50_000` exceeds observed run size and the bottleneck is provider-side 300/ticker, not scheduler budget.

## Task 3: Live Read-Only Audit

**Files:**

- Output only: `scratchpad/ibkr-news-catchup-audit-*.json` (not committed)
- Modify docs only after review: this plan and `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Run report twice**

Run the utility twice against live local DBs. No scheduler shutdown is required for read-only audit, but if a run is active and counts drift, record that and rerun after the source is idle.

Both runs must use the same explicit `--as-of` date. This makes the trailing windows deterministic. Different `--as-of` values are allowed to drift, and that drift is expected.

- [ ] **Step 2: Validate expected current facts**

The report must confirm or update:

- Latest `ibkr_news` durable state.
- Recent `provider_sync_runs` are succeeded, not failed.
- 7d cap risk is below 300 for all tickers.
- 30d cap risk identifies the high-volume tickers.
- The `observed_quiet_window_2026_06_25_to_2026_07_05` gap check is below 300 for all tickers or explicitly lists the tickers that hit/approach the cap.
- The report caveats are present. Reviewer interpretation rule: local counts are evidence for operational risk, not proof of complete provider-side coverage; possible already-missed tail rows remain unknowable without a different data source or live/provider-specific strategy.

- [ ] **Step 3: Decide follow-up**

Choose one:

- `no_runtime_change`: Normal cadence is safe; document "do not leave IBKR news disabled for >N days for high-volume tickers."
- `runbook_only`: Add operator note to Data Sources / docs but no code.
- `implementation_followup`: Open a new plan for one of:
  - higher cadence / catch-up warning,
  - real-time IBKR news subscription capture,
  - cross-provider backfill using Polygon/Finnhub,
  - manual live Gateway probe for the top risk tickers.

## Task 4: Docs Closeout

**Files:**

- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: this plan
- Optionally modify: `docs/data/IBKR_NEWS_API_LIMITATIONS.md`

- [ ] **Step 1: Record live audit result**

Update this plan with:

- artifact path(s),
- key numbers,
- risk classification,
- final follow-up decision.

- [ ] **Step 2: Update map**

Add newest-first §10 entry:

- IBKR news long-catch-up audit completed,
- whether any runtime follow-up was opened,
- queue after this audit.

- [ ] **Step 3: Optional docs/data update**

Only if the audit adds new practical operator guidance, append a short "Post-normalized scheduler note" to `docs/data/IBKR_NEWS_API_LIMITATIONS.md`. Do not rewrite the historical API finding.

## Acceptance Criteria

- Audit utility is read-only and reproducible.
- Live report answers the concrete question: how long can IBKR news be quiet before the 300/ticker cap becomes a real tail-risk for current tickers?
- No runtime code path changes in this slice.
- The map no longer has a vague "IBKR catch-up audit" queue item; it has either a closed audit or a named follow-up.
