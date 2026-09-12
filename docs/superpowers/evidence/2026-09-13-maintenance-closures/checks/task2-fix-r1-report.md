# Task2 R1 Fix Handoff

Worktree `/tmp/arkscope-research-output-boundary`, branch
`codex/sec-research-integration`, base `a4bf0a739fabba418138829f3ce501edc6dab5f8`.
Only `src/service/provider_health.py` and `tests/test_provider_health.py` changed
in product/tests. R1 and the controller's existence-probe ordering refinement
are implemented; scoped re-review and frozen integration acceptance remain
controller-owned.

## Root Cause And Final Fix

Health retained the legacy `news` slice after assigning legacy sync data if a
later acquisition raised. Its broad handler added a note without retiring that
slice. The initial fix cleared news before the current reader; the controller's
refinement identified the earlier `Path(db_path).exists()` failure window.
The final order clears only provisional news before either operation can fail:

```python
sync = overlay_price_authority(read_sync_meta(db_path))
sync = dict(sync)
# Legacy news cannot survive a failed path probe or current read.
sync["news"] = None
db_exists = Path(db_path).exists()
direct_news = read_news_sync_status(db_path)
sync["news"] = direct_news
```

The existing exception note, non-news data, provider/key semantics and IBKR
calculation are unchanged. A failed existence probe retains the existing
`db_exists=False` behavior; a successful probe before a failed query stays True.
No errors were suppressed or expected current statuses relaxed.

## Regression Controls

- The two corrupted-current-table nodes use actual disposable SQLite stores:
  real `market_sync_meta` price telemetry, optional legacy news timestamp/error/
  counters, malformed `provider_sync_runs`, actual articles and prices, and
  `SqliteBackend`. The real legacy reader locally replaces the autouse empty
  stub; the failing current query is not mocked. Assertions preserve the error
  note, price telemetry/authority, fundamentals, article visibility without
  provider success fallback, IBKR success, source rows and unchanged DB bytes.
- The additional existence-failure unit control also uses a real legacy store
  and reader. Only health's module-local `Path` probe raises `PermissionError`;
  the legacy reader's own path check is unaffected. It checks the response note,
  False existence result, retained prices, no publication fallback, unchanged
  DB bytes and no legacy news. The real corrupted-table controls remain intact.

## Commands And Receipts

All runs used the unchanged offline runner, sequentially, from the worktree:

```bash
W=.superpowers/sdd/2026-09-13-maintenance-closures
H=tests/test_provider_health.py
C="$H::test_health_clears_legacy_news_when_current_telemetry_read_fails"
E="$H::test_health_clears_legacy_news_when_db_exists_check_fails"
O=(tests/test_news_settings_route.py tests/test_news_providers.py
   tests/test_news_normalized_routing.py tests/test_news_sync_status.py
   tests/test_provider_health.py tests/test_data_coverage_tools.py
   tests/test_stored_sec_projection.py tests/test_market_data_admin.py
   tests/test_data_scheduler.py tests/test_security_lifecycle_routes.py
   tests/test_news_routing_cleanup.py tests/test_api.py)
/home/hyl/.virtualenvs/llm_app/bin/python -B "$W/run_checks.py" RUN MODE ARGS
```

Each RUN below is prefixed `task2-fix-r1-`. Its directory contains the expanded
`command.json` with environment/exit, `output.log`, and `results.xml` for test
runs. Counts are separate receipts, not additive totals. P/F mean passed/failed.

| RUN Suffix | MODE ARGS | Result | Exit |
| --- | --- | --- | --- |
| baseline | `backend -q "$H"` | 24P | 0 |
| red | `backend -q "$C"` | 1F, 1P | 1 |
| focused-green | `backend -q "$H"` | 26P | 0 |
| collect | `collect "${O[@]}"` | 331 collected | 0 |
| owned-green | `backend -q "${O[@]}"` | 331P | 0 |
| inverse | `backend -q "$C"` | 1F, 1P | 1 |
| restored | `backend -q "${O[@]}"` | 331P | 0 |
| exists-red | `backend -q "$E"` | 1F | 1 |
| exists-health-green | `backend -q "$H"` | 27P | 0 |
| final-inverse | `backend -q "$C" "$E"` | 2F, 1P | 1 |
| final-health-restored | `backend -q "$H"` | 27P | 0 |
| final-collect | `collect "${O[@]}"` | 332 collected | 0 |
| final-owned-restored | `backend -q "${O[@]}"` | 332P | 0 |

All test runs had zero skips and collection/setup errors. The four nonzero test
receipts are intentional defect RED/inverse results: each failure is the final
`sync["news"] is None` assertion exposing the seeded legacy row; preceding
preservation assertions pass. The absent-legacy control passes throughout.
`exists-red` specifically fails against the intermediate fix before reordering.
No fixture correction or regression-assertion-only RED occurred in R1; these
receipts do not reclassify the earlier Task2 RED history. Earlier 331P receipts
predate the existence refinement and are not final acceptance for these bytes.

## Exact Node Delta

Compared preserved `task2-collect-after/output.log` with
`task2-fix-r1-final-collect/output.log` using sorted `^tests/.+::` node IDs and
both directions of `comm`: **329 unchanged, 3 added, 0 removed; 332 current**.
Health changes from 24 to 27 nodes. Exact additions:

```text
tests/test_provider_health.py::test_health_clears_legacy_news_when_current_telemetry_read_fails[legacy-news-absent]
tests/test_provider_health.py::test_health_clears_legacy_news_when_current_telemetry_read_fails[legacy-news-present]
tests/test_provider_health.py::test_health_clears_legacy_news_when_db_exists_check_fails
```

## Restoration And Handoff

The final inverse restored the original product bytes exactly:
`git diff --exit-code a4bf0a739fabba418138829f3ce501edc6dab5f8 -- src/service/provider_health.py`
returned 0. Tests and all three runner files kept identical hashes through the
inverse. The refined bytes were then restored before both final test runs.

| File / State | SHA256 |
| --- | --- |
| provider_health.py, base and inverses | `23e7abf4b72e634dff9b39c275cd2339153e44e0400133e07ed16c07d9b022ce` |
| provider_health.py, intermediate fix | `1e94ef2aa93ce15a05e2da98bc1a1567476b36a8f4fbdc4284bfa74bee491cfd` |
| provider_health.py, final restored | `e01866ee0d3060b2ad33bdf9f775e0088a2937a0372ab52852df2988f37b550e` |
| test_provider_health.py, final | `2bf1b078f2e39446844f458b9d019c2f0176a1c7c98a4eea113a676257072df6` |

`task2-fix-r1-final.sha256` records the final product/test and unchanged
`run_checks.py`, `offline_pytest.py`, `offline_node.cjs` hashes. `sha256sum -c`
returned 0 with all five OK after restoration and again after the final scoped
run. `task2-fix-r1-reviewed.sha256` is preserved unchanged as the intermediate
fix receipt, not the current manifest. All prior reports/receipts remain intact.

Final diff: 2 files, 146 insertions, 1 deletion (product +3/-1, tests +143/-0).
`git diff --check` returned 0; staged diff is empty. Controller docs were left
untouched. No full backend/frontend/build/typecheck run was added in this
Python-only fix round; no agents, providers, private DB/config, App, dependency
or runner edits, staging or commits. Offline guards remain audit hooks, not an
OS sandbox. All owned test processes exited; the final process query found no
runner (expected `pgrep` exit 1). No servers were started. Ready for controller
freeze and scoped re-review; no further product edits or tests running.
