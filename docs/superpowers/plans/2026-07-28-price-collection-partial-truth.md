# Price Collection Partial-Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: DRAFT - INDEPENDENT PLAN REVIEW REQUIRED**

**Goal:** Make direct-local price collection report per-ticker unresolved
completed-day targets as structural partial truth from collector through
Settings, without changing Coverage v2, provider adapters, schemas, request
policy, or production data.

**Architecture:** The existing collector keeps each ticker's original
zero-bar target dates, inserts fetched rows under the existing short write
boundary, and then performs one parameterized day-presence query against those
same identities. One derived issue set owns collector status, provider
telemetry, the sanitized child payload, scheduler durable state, and the
bounded frontend explanation. Three-value audit tables project semantic
partial to `failed`; structured counts and ticker IDs preserve successful
sibling facts.

**Tech Stack:** Python 3.10, SQLite, pytest, subprocess JSON boundaries,
FastAPI scheduler state, React 18, TypeScript 5.9, i18next, Vitest 4/jsdom, and
the existing TypeScript-AST visible-literal scanner.

---

## 1. Authority And Review State

1. Product authority:
   `docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md`.
2. Sequence and follow-up authority:
   `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Small-issue authority:
   `docs/design/ENGINEERING_ISSUE_REGISTER.md`; this contract violation remains
   an active priority-map slice rather than an EIR item.
4. Product base:
   `542776c2e00ae1737d5b424a3b8858b079a63e38`.
5. Reviewed spec tip:
   `1a695141` on isolated branch `codex/price-collection-truth`.

Independent full-document re-review returned GREEN with zero findings. It
verified the local day-presence rule, the three separately named
anti-false-partial shapes, the fixed-26-slot mutation, the local fail-closed
audit projection, and the explicit non-convergence of normalized-news audit
behavior.

Product edits remain unauthorized until an independent plan review records a
clearance commit. If implementation contradicts the spec, changes any
protected boundary, or changes an exact node/resource ledger below, stop and
amend the authority before continuing.

The main worktree's untracked files remain user-owned and out of scope:

```text
docs/data/IBKR_PACING_AND_ERROR_SEMANTICS.md
docs/design/SCRIPTS_RETIREMENT_DECISION.md
```

They must not be copied, edited, staged, or used as implementation authority.

## 2. Grounded Baseline

All collection values below were independently reproduced on clean
`1a695141`; the three docs commits after `542776c2` contain no product code.
Normalized node IDs, not an absolute environment-dependent pass/fail total,
are the accounting authority.

| Gate | Baseline |
|---|---|
| Backend full collection | `4722` nodes; SHA-256 `fcdb1b7dc197c35d43684e7dde846ea82dc975ca6bb688162e88c5f312d43ff0` |
| Backend focused collection | `151` nodes; SHA-256 `3c07d208ced889497521a779ae46dd88403277c34055c00ba9fd74ada08da428` |
| Backend focused composition | direct `63`, worker `4`, scheduler `84` |
| Backend focused run | `151 passed` |
| Frontend full collection | `96` files / `1074` nodes; SHA-256 `e322e7a51e83eedb8b3c7b1fd99e6033f496031968c1a2cb3f59974bfd994f47` |
| Frontend focused collection | `3` files / `86` nodes; SHA-256 `739385b104c147744e7421f030e3fc628b2d99a981406c9c13aeb25c2a70a479` |
| Frontend focused composition | mounted Settings `36`, resources `14`, display `36` |
| Per-locale resources | Settings `704`, Explore `380`, total `1783` |
| Visible-literal scanner, twice | `36 / 20 / 0 / 20`, scope `src/**` |
| Tool surfaces | central `53`, OpenAI `54`, Anthropic `54` |
| no-PG runtime smoke | `23/23`, `ok=true`, `pg_attempts=[]` |

The root `node_modules` symlink and empty ignored `data/` directory are
worktree-only test prerequisites. They are not product input and must never be
replaced with the production `data/` tree. The known backend non-green family
is EIR-002; Task 0 must derive its same-environment node-ID set before product
edits. No historical failure count is an allowlist.

### 2.1 Canonical collection recipes

Backend full:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-be-full.nodes \
  | sha256sum
wc -l /tmp/price-truth-be-full.nodes
```

Backend focused:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_market_data_direct.py \
  tests/test_prices_runtime.py \
  tests/test_data_scheduler.py \
  | sed -n '/^tests\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-be-focused.nodes \
  | sha256sum
wc -l /tmp/price-truth-be-focused.nodes
cut -d: -f1 /tmp/price-truth-be-focused.nodes | sort | uniq -c
```

Frontend full, from `apps/arkscope-web`:

```bash
npx vitest list --json \
  | jq -r '.[] | [.file,.name] | @tsv' \
  | sed "s#$(pwd)/##" \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-fe-full.nodes \
  | sha256sum
wc -l /tmp/price-truth-fe-full.nodes
cut -f1 /tmp/price-truth-fe-full.nodes | sort -u | wc -l
```

Frontend focused is derived from the full normalized stream:

```bash
awk -F '\t' \
  '$1=="src/SettingsProviderConfig.test.ts" || \
   $1=="src/i18n/resources.test.ts" || \
   $1=="src/marketDataDisplay.test.ts"' \
  /tmp/price-truth-fe-full.nodes \
  | LC_ALL=C sort \
  | tee /tmp/price-truth-fe-focused.nodes \
  | sha256sum
wc -l /tmp/price-truth-fe-focused.nodes
cut -f1 /tmp/price-truth-fe-focused.nodes | sort | uniq -c
```

Vitest 4 treats the token after `--json` as an optional output filename. Do
not append test paths after `--json`; generate the full JSON stream first and
filter the normalized TSV.

## 3. Exact Accounting

### 3.1 Backend node ledger

No existing backend node ID is removed or renamed. Add exactly 17 nodes:

| File | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| `tests/test_market_data_direct.py` | 63 | 7 | 0 | 70 |
| `tests/test_prices_runtime.py` | 4 | 4 | 0 | 8 |
| `tests/test_data_scheduler.py` | 84 | 6 | 0 | 90 |
| Focused total | 151 | 17 | 0 | 168 |
| Full repository | 4722 | 17 | 0 | 4739 |

Add these exact direct-collector nodes:

```text
tests/test_market_data_direct.py::test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target
tests/test_market_data_direct.py::test_backfill_failed_when_every_ticker_has_issue
tests/test_market_data_direct.py::test_backfill_resolved_zero_bar_target_stays_succeeded_and_clears_error
tests/test_market_data_direct.py::test_backfill_one_row_low_volume_day_stays_succeeded
tests/test_market_data_direct.py::test_backfill_non_target_rows_do_not_resolve_original_zero_bar_target
tests/test_market_data_direct.py::test_backfill_rechecks_original_target_set_only_once
tests/test_market_data_direct.py::test_backfill_exception_and_unresolved_tickers_share_one_issue_rollup
```

Add these exact worker nodes:

```text
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_partial_json_and_exits_zero
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_failed_result_json_and_exits_nonzero
tests/test_prices_runtime.py::test_prices_worker_rejects_unknown_status_and_malformed_counts
tests/test_prices_runtime.py::test_prices_worker_bounds_sorts_and_sanitizes_ticker_lists
```

Add these exact scheduler nodes:

```text
tests/test_data_scheduler.py::test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers
tests/test_data_scheduler.py::test_prices_worker_stdout_parser_rejects_malformed_partial_payloads
tests/test_data_scheduler.py::test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation
tests/test_data_scheduler.py::test_prices_failed_payload_persists_failed_without_partial
tests/test_data_scheduler.py::test_prices_success_clears_prior_partial_and_preserves_audit_history
tests/test_data_scheduler.py::test_price_partial_projection_does_not_change_normalized_news_audit_status
```

The following existing nodes evolve in place and retain their exact IDs:

```text
tests/test_market_data_direct.py::test_backfill_per_ticker_exception_isolated
tests/test_market_data_direct.py::test_backfill_meta_write_failure_in_error_path_does_not_abort_batch
tests/test_market_data_direct.py::test_backfill_topup_idempotent_on_complete_day
tests/test_market_data_direct.py::test_backfill_ibkr_empty_from_swallowed_request_error_falls_to_polygon
tests/test_market_data_direct.py::test_backfill_fetches_provider_rows_outside_market_write_lock
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_success_json
tests/test_prices_runtime.py::test_prices_worker_prints_sanitized_error_json
tests/test_data_scheduler.py::test_p0c1_ibkr_prices_runs_prices_worker_subprocess
tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync
tests/test_data_scheduler.py::test_price_scope_required
tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure
tests/test_data_scheduler.py::test_prices_worker_stdout_parse_preserves_retryable_and_counts
```

The direct-test fixtures above must use one completed market date where the
test claims a wholly successful result. A fixture that returns one day inside a
multi-day zero-bar window is partial by design and must not be relabeled for
test convenience.

### 3.2 Frontend node and resource ledger

Add exactly two frontend nodes; remove or rename none:

```text
src/marketDataDisplay.test.ts > schedulerStateLabel > renders price unresolved count and bounded ticker list without continuation
src/SettingsProviderConfig.test.ts > Settings provider config authority > renders price partial facts without a Continue control in both locales
```

| File | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| `src/marketDataDisplay.test.ts` | 36 | 1 | 0 | 37 |
| `src/SettingsProviderConfig.test.ts` | 36 | 1 | 0 | 37 |
| `src/i18n/resources.test.ts` | 14 | 0 | 0 | 14 |
| Focused total | 86 | 2 | 0 | 88 |
| Full frontend | 1074 | 2 | 0 | 1076 |
| Frontend files | 96 | 0 | 0 | 96 |

Add exactly two leaves per locale under
`settings.dataSources.schedule.history`:

```text
priceUnresolved_one
priceUnresolved_other
```

The per-locale resource ledger is:

| Subtree | Base | Add | Remove | Final |
|---|---:|---:|---:|---:|
| Settings | 704 | 2 | 0 | 706 |
| Explore | 380 | 0 | 0 | 380 |
| Total | 1783 | 2 | 0 | 1785 |

The existing count node in `src/i18n/resources.test.ts` evolves in place; its
ID does not change.

## 4. File Map

### 4.1 Create

- `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
  records RED, GREEN, mutation, accounting, protected-boundary, and release
  evidence.

### 4.2 Modify

- `src/market_data_direct.py`: post-write target reconciliation, derived batch
  status, and provider telemetry projection.
- `src/prices_runtime.py`: closed sanitized result validator and status-derived
  exit code.
- `src/service/data_scheduler.py`: strict prices payload parser and local
  partial/failed audit projection.
- `tests/test_market_data_direct.py`: seven new nodes and the exact in-place
  evolutions in Section 3.1.
- `tests/test_prices_runtime.py`: four new nodes and two in-place evolutions.
- `tests/test_data_scheduler.py`: six new nodes and five in-place evolutions.
- `apps/arkscope-web/src/api.ts`: scheduler result DTO fields only.
- `apps/arkscope-web/src/marketDataDisplay.ts`: price-specific durable partial
  presentation only.
- `apps/arkscope-web/src/marketDataDisplay.test.ts`: one pure presentation node.
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts`: one bilingual mounted
  node and a bounded fixture mode.
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`: two English plural
  leaves.
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`: two Traditional
  Chinese plural leaves.
- `apps/arkscope-web/src/i18n/resources.test.ts`: count values only, same node
  ID.
- the design spec, this plan, evidence packet, and priority map for lifecycle
  state only.

`apps/arkscope-web/src/settings/DataSourcesSection.tsx` consumes
`schedulerStateLabel` unchanged. It is not an implementation owner unless the
mounted RED proves the existing `needsContinue=false` contract cannot render
correctly; that outcome is a stop condition, not permission to expand scope.

### 4.3 Delete

None.

## 5. Locked Implementation Shape

### 5.1 Collector constants and target query

Add the stable codes next to `_VALID_RUN_STATUSES` and add one private helper
next to `_insert_rows`:

```python
_PRICE_DAY_UNRESOLVED_AFTER_FETCH = "price_day_unresolved_after_fetch"
_PRICE_COLLECTION_PARTIAL = "price_collection_partial"
_PRICE_COLLECTION_FAILED = "price_collection_failed"


def _unresolved_price_target_dates(
    conn,
    *,
    ticker: str,
    interval: str,
    targets: List[date],
) -> List[date]:
    unique_targets = sorted(set(targets))
    if not unique_targets:
        return []
    placeholders = ", ".join("?" for _ in unique_targets)
    target_ids = [target.isoformat() for target in unique_targets]
    rows = conn.execute(
        "SELECT DISTINCT substr(datetime, 1, 10) FROM prices "
        "WHERE ticker = ? AND interval = ? "
        f"AND substr(datetime, 1, 10) IN ({placeholders})",
        (ticker, _INTERVAL_DB.get(interval, interval), *target_ids),
    ).fetchall()
    present = {str(row[0]) for row in rows}
    return [target for target in unique_targets if target.isoformat() not in present]


def _derive_price_collection_status(tickers_scanned: int, issue_count: int) -> str:
    if tickers_scanned <= 0 or issue_count < 0 or issue_count > tickers_scanned:
        raise ValueError("invalid price collection outcome counts")
    if issue_count == 0:
        return "succeeded"
    if issue_count == tickers_scanned:
        return "failed"
    return "partial"
```

The helper receives only `item["gaps"]`, which is the original
`detect_price_gaps()` result captured before provider work. It must not receive
`fetch_days`, call `detect_price_gaps()` itself, count bars, or import Coverage
v2.

### 5.2 Collector write-phase derivation

Initialize the result with the complete semantic envelope:

```python
rollup = {
    "status": "succeeded",
    "provider": provider,
    "tickers_scanned": 0,
    "succeeded_ticker_count": 0,
    "gaps_found": 0,
    "rows_added": 0,
    "errors": {},
    "unresolved_after_fetch_count": 0,
    "unresolved_after_fetch_tickers": [],
}
```

Inside the existing second `market_write_lock`, replace the success path with
this ordered operation. Existing exception recovery remains best-effort and
contributes one issue for that ticker:

```python
rows = item.get("rows")
rows = rows if isinstance(rows, list) else []
targets = item.get("gaps")
targets = targets if isinstance(targets, list) else []
added = _insert_rows(conn, rows)
rollup["rows_added"] += added
last_bar = rows[-1][1] if rows else None
unresolved = _unresolved_price_target_dates(
    conn,
    ticker=canon,
    interval=interval,
    targets=targets,
)
if unresolved:
    rollup["errors"][canon] = _PRICE_DAY_UNRESOLVED_AFTER_FETCH
    rollup["unresolved_after_fetch_tickers"].append(canon)
    _upsert_provider_meta(
        conn,
        provider=provider,
        ticker=canon,
        interval=interval,
        last_bar_datetime=last_bar,
        rows_added=added,
        error=_PRICE_DAY_UNRESOLVED_AFTER_FETCH,
    )
else:
    rollup["succeeded_ticker_count"] += 1
    _upsert_provider_meta(
        conn,
        provider=provider,
        ticker=canon,
        interval=interval,
        last_bar_datetime=last_bar,
        rows_added=added,
        error=None,
    )
```

After all tickers, derive and persist once:

```python
unresolved_tickers = sorted(set(rollup["unresolved_after_fetch_tickers"]))
rollup["unresolved_after_fetch_tickers"] = unresolved_tickers
rollup["unresolved_after_fetch_count"] = len(unresolved_tickers)
issue_count = len(rollup["errors"])
rollup["succeeded_ticker_count"] = rollup["tickers_scanned"] - issue_count
rollup["status"] = _derive_price_collection_status(
    rollup["tickers_scanned"],
    issue_count,
)
run_error = {
    "succeeded": None,
    "partial": _PRICE_COLLECTION_PARTIAL,
    "failed": _PRICE_COLLECTION_FAILED,
}[rollup["status"]]
_finish_provider_run(
    conn,
    run_id,
    status="succeeded" if rollup["status"] == "succeeded" else "failed",
    tickers_scanned=rollup["tickers_scanned"],
    gaps_found=rollup["gaps_found"],
    rows_added=rollup["rows_added"],
    error=run_error,
)
```

Do not add `partial` to `_VALID_RUN_STATUSES` or either SQLite CHECK. Do not
move `_fetch_rows_for_gaps()` under `market_write_lock`.

### 5.3 Worker closed payload

In `src/prices_runtime.py`, add strict helpers. Booleans are invalid integers;
ticker IDs are uppercase ASCII identifiers, sorted/deduplicated, and capped at
the existing 25-item boundary:

```python
import re

_PRICE_RESULT_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICE_COUNT_FIELDS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "unresolved_after_fetch_count",
)
_SAFE_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9 ._-]{0,11}$")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {field}")
    return value


def _ticker_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        raise ValueError(f"invalid {field}")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"invalid {field}")
    result = sorted({item.strip().upper() for item in value})
    if any(not _SAFE_TICKER.fullmatch(item) for item in result):
        raise ValueError(f"invalid {field}")
    return result
```

Replace `sanitize_result()` with validation that cannot manufacture success:

```python
def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    status = result.get("status")
    if status not in _PRICE_RESULT_STATUSES:
        raise ValueError("invalid price collection status")
    provider = result.get("provider")
    if provider not in {"ibkr", "polygon"}:
        raise ValueError("invalid provider")
    counts = {
        field: _nonnegative_int(result.get(field), field)
        for field in _PRICE_COUNT_FIELDS
    }
    errors = result.get("errors")
    if not isinstance(errors, dict):
        raise ValueError("invalid errors")
    error_tickers = _ticker_ids(list(errors), "error_tickers")
    unresolved = _ticker_ids(
        result.get("unresolved_after_fetch_tickers"),
        "unresolved_after_fetch_tickers",
    )
    error_count = len(error_tickers)
    if counts["unresolved_after_fetch_count"] != len(unresolved):
        raise ValueError("invalid unresolved_after_fetch_count")
    if not set(unresolved).issubset(error_tickers):
        raise ValueError("unresolved tickers must be issue tickers")
    scanned = counts["tickers_scanned"]
    if counts["succeeded_ticker_count"] != scanned - error_count:
        raise ValueError("invalid succeeded_ticker_count")
    expected = (
        "succeeded" if error_count == 0
        else "failed" if scanned > 0 and error_count == scanned
        else "partial"
    )
    if scanned <= 0 or status != expected:
        raise ValueError("status does not match price collection facts")
    return {
        "status": status,
        "provider": provider,
        **counts,
        "error_count": error_count,
        "error_tickers": error_tickers[:25],
        "unresolved_after_fetch_tickers": unresolved[:25],
    }
```

Keep the recognized lock-busy exception diagnostic required by retryable-skip
classification. For every other exception, expose only its class and a blank
message:

```python
def sanitize_error(exc: BaseException) -> dict[str, Any]:
    raw = str(exc)
    retryable = _is_retryable_error(raw)
    return {
        "status": "failed",
        "error_class": exc.__class__.__name__,
        "error": raw[:MAX_ERROR_LEN] if retryable else "",
        "retryable": retryable,
    }
```

Derive the process exit from the validated status:

```python
payload = sanitize_result(result)
code = 1 if payload["status"] == "failed" else 0
```

### 5.4 Scheduler strict parser and local projection

Expand `_PRICES_WORKER_COUNT_KEYS` and parse structured result and exception
failure shapes separately:

```python
_PRICES_WORKER_STATUSES = frozenset({"succeeded", "partial", "failed"})
_PRICES_WORKER_COUNT_KEYS = (
    "tickers_scanned",
    "succeeded_ticker_count",
    "gaps_found",
    "rows_added",
    "error_count",
    "unresolved_after_fetch_count",
)


def _parse_price_ticker_ids(value: Any) -> Optional[List[str]]:
    if (
        not isinstance(value, list)
        or len(value) > 25
        or any(not isinstance(item, str) for item in value)
    ):
        return None
    normalized = sorted({item.strip().upper() for item in value})
    if any(
        not item
        or len(item) > 12
        or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-" for ch in item)
        for item in normalized
    ):
        return None
    return normalized
```

`_parse_sanitized_prices_worker_stdout()` must follow this order:

1. reject non-object JSON and unknown status;
2. accept the existing exception envelope only for `status='failed'` when no
   structured count key is present, preserving `error_class`, bounded `error`,
   and `retryable`;
3. otherwise require `provider` to be exactly `ibkr` or `polygon`;
4. require every count as a nonnegative integer, rejecting booleans;
5. require both ticker arrays, reject more than 25 exposed IDs, normalize them,
   and require each normalized length to equal `min(full_count, 25)`;
6. require `succeeded_ticker_count == tickers_scanned - error_count`,
   `unresolved_after_fetch_count <= error_count`, and the status implied by
   `tickers_scanned/error_count`; and
7. return only allowlisted fields.

The structured return shape is:

```python
return {
    "status": status,
    "provider": provider,
    **counts,
    "error_tickers": error_tickers,
    "unresolved_after_fetch_tickers": unresolved_tickers,
    "error_class": "",
    "error": "",
    "retryable": False,
}
```

In `run_source()`, introduce only a price-local semantic flag:

```python
price_partial = False
price_audit_error: Optional[str] = None
```

After the prices child returns, classify payload before return code can imply
success:

```python
price_status = step["payload"]["status"]
if price_status == "partial" and step["returncode"] == 0:
    price_partial = True
    price_audit_error = "price_collection_partial"
elif price_status == "failed":
    reason = _prices_worker_retryable_skip_reason(step["payload"])
    if reason is not None:
        result.update({
            "status": "skipped",
            "reason": reason,
            "skip_kind": "skipped_lock_busy",
        })
    else:
        raise RuntimeError("price_collection_failed")
elif price_status != "succeeded" or step["returncode"] != 0:
    raise RuntimeError(_sanitized_prices_worker_failure_message(step["payload"]))
```

Derive durable status with price partial beside, not inside, normalized-news
continuation logic:

```python
elif ok and (writer_partial or price_partial):
    result["status"] = "partial"
    continuation = writer_continuation if writer_partial else None
    if continuation is not None:
        result["continuation"] = continuation
```

Keep `record_outcome(..., error=error)` unchanged so a completed price partial
has durable status `partial`, `continuation=None`, and structured result without
a fabricated retry control. Project only price partial to failed audit:

```python
audit_failed = (not ok) or price_partial
audit_error = price_audit_error if price_partial else error
store.finish_run(
    run_id,
    status="failed" if audit_failed else "succeeded",
    message=audit_error if audit_failed else None,
    error=audit_error if audit_failed else None,
    result=result,
)
```

This code must leave normalized-news `writer_partial` audit behavior exactly
as it is today.

### 5.5 Frontend DTO, copy, and presentation

Extend only `ScheduleRunResult.collect` in `apps/arkscope-web/src/api.ts`:

```typescript
status?: "succeeded" | "partial" | "failed";
succeeded_ticker_count?: number;
gaps_found?: number;
rows_added?: number;
error_count?: number;
error_tickers?: string[];
unresolved_after_fetch_count?: number;
unresolved_after_fetch_tickers?: string[];
```

Add these exact resources:

```typescript
// en/settings.ts
priceUnresolved_one: "Partially completed ({{count}} ticker remains unresolved after collection: {{tickers}})",
priceUnresolved_other: "Partially completed ({{count}} tickers remain unresolved after collection: {{tickers}})",

// zh-Hant/settings.ts
priceUnresolved_one: "部分完成（抓取後仍有 {{count}} 個標的無法確認：{{tickers}}）",
priceUnresolved_other: "部分完成（抓取後仍有 {{count}} 個標的無法確認：{{tickers}}）",
```

In the `partial` branch of `schedulerStateLabel()`, keep actionable
continuation first, then add this price-specific branch before news
continuation/body facts:

```typescript
const collect = durable?.last_result?.collect;
const unresolved = positiveCount(collect?.unresolved_after_fetch_count);
const unresolvedTickers = Array.isArray(collect?.unresolved_after_fetch_tickers)
  ? collect.unresolved_after_fetch_tickers
    .filter((ticker): ticker is string => typeof ticker === "string" && ticker.length > 0)
    .slice(0, 25)
  : [];
if (
  durable?.last_result?.source === "ibkr_prices"
  && collect?.status === "partial"
  && unresolved > 0
  && unresolvedTickers.length > 0
) {
  const label = unresolved === 1
    ? t(($) => $.dataSources.schedule.history.priceUnresolved_one, {
      count: unresolved,
      tickers: unresolvedTickers.join(", "),
    })
    : t(($) => $.dataSources.schedule.history.priceUnresolved_other, {
      count: unresolved,
      tickers: unresolvedTickers.join(", "),
    });
  return { label, tone: "warn", needsContinue: false };
}
```

Then continue through the existing generic news/count/cursor branches. Do not
change `jobOutcome()`, the generic glyph, `DataSourcesSection.tsx`, provider
health, or any Coverage display.

## 6. Stop Conditions

Stop and amend the reviewed authority before implementation continues if any
of these occurs:

1. a canonical collection hash or composition differs before product edits;
2. the exact final node ledger differs from `+17/-0` backend or `+2/-0`
   frontend;
3. resources cannot close at Settings `706`, Explore `380`, total `1785`;
4. reconciliation requires calling `detect_price_gaps()` after fetch, checking
   all fetch days, requiring 26 slots, or importing `src.market_coverage`;
5. provider fetch would move inside `market_write_lock`;
6. an adapter return type, retry policy, fallback order, request count, client
   ID, Gateway lock, scheduler cadence, or source catalog must change;
7. a SQLite schema, migration, status CHECK, existing price row, or production
   DB must change;
8. implementation requires changing normalized-news audit projection, generic
   job glyphs, provider health, Coverage API/DTO/presentation, or repair logic;
9. raw per-ticker/provider diagnostics or target dates would cross worker
   stdout or frontend DTO;
10. a live provider, Gateway, browser, scheduler, or production write is needed
    for RED/GREEN or review;
11. the base full suite cannot produce a same-environment non-passing node-ID
    set for A/B comparison; or
12. either main-worktree untracked document changes.

## 7. Task 0 - Reground After Plan Clearance

**Files:**
- Create: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Record the clearance identities.**

  Run:

  ```bash
  git status --short --branch
  git rev-parse HEAD
  git merge-base --is-ancestor 542776c2 HEAD
  git diff --name-only 542776c2...HEAD
  ```

  Expected before product edits: branch `codex/price-collection-truth`; product
  base is an ancestor; only the reviewed spec, plan, and priority-map docs
  differ from `542776c2`. Export the exact runtime identity and record its
  output in the evidence packet:

  ```bash
  export PLAN_REVIEW_CLEARANCE_COMMIT="$(git rev-parse HEAD)"
  printf '%s\n' "$PLAN_REVIEW_CLEARANCE_COMMIT"
  ```

- [ ] **Step 2: Prove the worktree is isolated and contains no production data.**

  Run:

  ```bash
  test "$(git rev-parse --show-toplevel)" = "/tmp/arkscope-price-collection-truth"
  test -L node_modules
  test "$(readlink node_modules)" = "/mnt/md0/PycharmProjects/ArkScope/node_modules"
  test -d data
  test -z "$(find data -mindepth 1 -maxdepth 1 -print -quit)"
  git check-ignore -q node_modules
  git check-ignore -q data
  git status --short
  ```

  Expected: the ignored dependency symlink and empty data directory do not
  appear in Git status. Do not copy `data/`, `config/.env`, browser profiles,
  or either main-worktree untracked document into this worktree.

- [ ] **Step 3: Reproduce all four canonical collections.**

  Run Section 2.1 exactly. Expected: backend `4722/151` with composition
  `63/4/84`; frontend `96 files / 1074 nodes` and focused `86` with composition
  `36/14/36`; all four SHA-256 values match Section 2.

- [ ] **Step 4: Reproduce focused and non-node behavior.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py

  cd apps/arkscope-web
  npx vitest run \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts \
    src/marketDataDisplay.test.ts
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count \
    tests/test_pg_unreachable_e2e.py

  /home/hyl/.virtualenvs/llm_app/bin/python src/smoke/pg_unreachable_e2e.py
  ```

  Expected: backend `151 passed`; frontend focused `86 passed`; scanner twice
  `36/20/0/20`; tools `53/54/54`; no-PG `23/23`, `ok=true`, and no PG attempt.

- [ ] **Step 5: Capture the same-environment full non-passing set.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    > /tmp/price-truth-base-full.txt 2>&1
  sed -n 's/^FAILED \([^ ]*::[^ ]*\).*/\1/p; s/^ERROR \([^ ]*::[^ ]*\).*/\1/p' \
    /tmp/price-truth-base-full.txt \
    | LC_ALL=C sort -u \
    | tee /tmp/price-truth-base-nonpassing.nodes \
    | sha256sum
  wc -l /tmp/price-truth-base-nonpassing.nodes
  tail -80 /tmp/price-truth-base-full.txt
  ```

  The command may exit nonzero because EIR-002 is open, but it must terminate
  and produce a normalized set. Record the dated count and hash as an
  observation. If it hangs or cannot produce a complete set, stop under Stop
  Condition 11; do not infer a baseline from partial output.

- [ ] **Step 6: Capture protected-boundary baselines.**

  ```bash
  git rev-parse HEAD:data_sources/ibkr_source.py
  git rev-parse HEAD:data_sources/polygon_source.py
  git rev-parse HEAD:src/service/provider_health.py
  git rev-parse HEAD:src/ibkr_gateway_lock.py
  git rev-parse HEAD:src/api/routes/market_data.py
  git rev-parse HEAD:src/data_provider_config.py
  git rev-parse HEAD:src/provider_config_runtime.py
  git ls-tree -r HEAD src/market_coverage sql scripts \
    | LC_ALL=C sort \
    | sha256sum

  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  import json
  from src.service.data_scheduler import SOURCES

  print(json.dumps({
      key: {
          "default_interval_min": value.default_interval_min,
          "ibkr": value.ibkr,
          "prices_worker": value.prices_worker,
          "provider_fetch": value.provider_fetch,
      }
      for key, value in sorted(SOURCES.items())
  }, sort_keys=True, indent=2))
  PY
  ```

  Store exact output in the evidence packet. The catalog must contain the same
  four active source IDs and intervals before and after.

- [ ] **Step 7: Create the evidence packet with explicit initial state.**

  Create this exact section structure:

  ```markdown
  # Price Collection Partial-Truth Evidence

  > **Status: TASK 0 GROUNDED - RED-FIRST IMPLEMENTATION ACTIVE**
  >
  > **Product base:** `542776c2...`
  > **Plan-review clearance:** recorded from Task 0 Step 1

  ## 1. Scope And Authorities
  ## 2. Canonical Baseline
  ## 3. RED Evidence
  ## 4. GREEN Evidence
  ## 5. Node And Resource Accounting
  ## 6. Mutation Evidence
  ## 7. Protected Boundaries
  ## 8. Full-Suite A/B
  ## 9. Review Resolution
  ## 10. Integration And Read-Only Release Observation
  ```

  Replace the descriptive clearance line with the real full SHA captured in
  Step 1 before saving the file.

- [ ] **Step 8: Record Task 0 and commit docs only.**

  Add a newest-first priority-map entry with exact reproduced hashes and the
  phrase `RED-FIRST IMPLEMENTATION ACTIVE`. Then run:

  ```bash
  git add \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git diff --cached --check
  git commit -m "docs: ground price collection truth task 0"
  ```

## 8. Task 1 - Direct Collector RED And GREEN

**Files:**
- Modify: `tests/test_market_data_direct.py`
- Modify: `src/market_data_direct.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add one-day test helpers without adding nodes.**

  Add beside `_backfill_db`:

  ```python
  _ONE_COMPLETE_DAY_NOW = datetime(2026, 6, 23, 18, 0, tzinfo=timezone.utc)


  def _run_one_complete_day(
      tmp_path, monkeypatch, *, tickers, ibkr, polygon=None, db=None,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = db or _backfill_db(tmp_path)
      result = mdd.backfill_prices_direct(
          tickers_arg=tickers,
          lookback_days=1,
          provider="ibkr",
          db_path=str(db),
          ibkr_src=ibkr,
          polygon_src=polygon or _FakePolygon(),
          now_et=_ONE_COMPLETE_DAY_NOW,
      )
      return db, result
  ```

  At this instant, 2026-06-22 is the sole completed target date and 2026-06-23
  is still in progress.

- [ ] **Step 2: Add the seven exact RED nodes.**

  Use the existing `_FakeIBKR`, `_FakePolygon`, `_bar`, and SQLite helpers. The
  load-bearing assertions are:

  ```python
  def test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      mdd._ensure_provider_sync_tables(conn)
      mdd._upsert_provider_meta(
          conn, provider="ibkr", ticker="LCID", interval="15min",
          last_bar_datetime="2026-06-19T13:30:00+0000", rows_added=0,
          error=None,
      )
      conn.execute(
          "UPDATE provider_sync_meta SET last_success='2000-01-01T00:00:00+00:00' "
          "WHERE provider='ibkr' AND ticker='LCID' AND interval='15min'"
      )
      conn.commit()
      conn.close()
      ibkr = _FakeIBKR({
          "AAPL": [_bar(datetime(2026, 6, 22, 9, 30))],
          "LCID": [],
      })
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="AAPL,LCID", ibkr=ibkr, db=db,
      )
      assert result["status"] == "partial"
      assert result["tickers_scanned"] == 2
      assert result["succeeded_ticker_count"] == 1
      assert result["rows_added"] == 1
      assert result["errors"] == {"LCID": "price_day_unresolved_after_fetch"}
      assert result["unresolved_after_fetch_count"] == 1
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT status, error FROM provider_sync_runs"
      ).fetchone() == ("failed", "price_collection_partial")
      assert conn.execute(
          "SELECT last_success, last_error FROM provider_sync_meta WHERE ticker='LCID'"
      ).fetchone() == (
          "2000-01-01T00:00:00+00:00", "price_day_unresolved_after_fetch",
      )
      assert conn.execute(
          "SELECT COUNT(*) FROM prices WHERE ticker='AAPL'"
      ).fetchone()[0] == 1
      conn.close()


  def test_backfill_failed_when_every_ticker_has_issue(tmp_path, monkeypatch):
      ibkr = _FakeIBKR({"LCID": []}, raises_for=["BAD"])
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="BAD,LCID", ibkr=ibkr,
      )
      assert result["status"] == "failed"
      assert result["succeeded_ticker_count"] == 0
      assert set(result["errors"]) == {"BAD", "LCID"}
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT status, error FROM provider_sync_runs"
      ).fetchone() == ("failed", "price_collection_failed")
      conn.close()


  def test_backfill_resolved_zero_bar_target_stays_succeeded_and_clears_error(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      mdd._ensure_provider_sync_tables(conn)
      mdd._upsert_provider_meta(
          conn, provider="ibkr", ticker="AAPL", interval="15min",
          last_bar_datetime=None, rows_added=0, error="old_error",
      )
      conn.execute(
          "UPDATE provider_sync_meta SET last_success='2000-01-01T00:00:00+00:00' "
          "WHERE provider='ibkr' AND ticker='AAPL' AND interval='15min'"
      )
      conn.commit()
      conn.close()
      result = mdd.backfill_prices_direct(
          tickers_arg="AAPL", lookback_days=1, provider="ibkr",
          db_path=str(db),
          ibkr_src=_FakeIBKR({"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]}),
          polygon_src=_FakePolygon(), now_et=_ONE_COMPLETE_DAY_NOW,
      )
      assert result["status"] == "succeeded"
      assert result["succeeded_ticker_count"] == 1
      assert result["unresolved_after_fetch_count"] == 0
      conn = sqlite3.connect(db)
      last_success, last_error = conn.execute(
          "SELECT last_success, last_error FROM provider_sync_meta "
          "WHERE provider='ibkr' AND ticker='AAPL' AND interval='15min'"
      ).fetchone()
      assert last_success != "2000-01-01T00:00:00+00:00"
      assert last_error is None
      conn.close()


  def test_backfill_one_row_low_volume_day_stays_succeeded(tmp_path, monkeypatch):
      monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
      db = _backfill_db(tmp_path)
      conn = sqlite3.connect(db)
      conn.execute(
          "INSERT INTO prices "
          "(ticker,datetime,interval,open,high,low,close,volume) "
          "VALUES ('LCID','2026-06-22T13:30:00+0000','15min',1,1,1,1,1)"
      )
      conn.commit()
      conn.close()
      result = mdd.backfill_prices_direct(
          tickers_arg="LCID", lookback_days=1, provider="ibkr",
          db_path=str(db), ibkr_src=_FakeIBKR(), polygon_src=_FakePolygon(),
          now_et=_ONE_COMPLETE_DAY_NOW,
      )
      assert result["rows_added"] == 0
      assert result["gaps_found"] == 0
      assert result["status"] == "succeeded"
      assert result["unresolved_after_fetch_count"] == 0


  def test_backfill_non_target_rows_do_not_resolve_original_zero_bar_target(
      tmp_path, monkeypatch,
  ):
      monkeypatch.setattr(
          mdd,
          "_fetch_rows_for_gaps",
          lambda *args, **kwargs: [(
              "LCID", "2026-06-20T13:30:00+0000", "15min",
              1.0, 1.0, 1.0, 1.0, 1,
          )],
      )
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="LCID", ibkr=_FakeIBKR(),
      )
      assert result["rows_added"] == 1
      assert result["status"] == "failed"
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
      conn = sqlite3.connect(db)
      assert conn.execute(
          "SELECT last_bar_datetime, last_success, last_error "
          "FROM provider_sync_meta WHERE ticker='LCID'"
      ).fetchone() == (
          "2026-06-20T13:30:00+0000", None,
          "price_day_unresolved_after_fetch",
      )
      conn.close()


  def test_backfill_rechecks_original_target_set_only_once(tmp_path, monkeypatch):
      calls = []

      def original_targets(*args, **kwargs):
          calls.append(1)
          if len(calls) != 1:
              raise AssertionError("target set was rederived after fetch")
          return {"LCID": [date(2026, 6, 22)]}

      monkeypatch.setattr(mdd, "detect_price_gaps", original_targets)
      db, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="LCID", ibkr=_FakeIBKR(),
      )
      assert db.exists()
      assert calls == [1]
      assert result["status"] == "failed"
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]


  def test_backfill_exception_and_unresolved_tickers_share_one_issue_rollup(
      tmp_path, monkeypatch,
  ):
      ibkr = _FakeIBKR(
          {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))], "LCID": []},
          raises_for=["BAD"],
      )
      _, result = _run_one_complete_day(
          tmp_path, monkeypatch, tickers="AAPL,BAD,LCID", ibkr=ibkr,
      )
      assert result["status"] == "partial"
      assert result["tickers_scanned"] == 3
      assert result["succeeded_ticker_count"] == 1
      assert set(result["errors"]) == {"BAD", "LCID"}
      assert result["unresolved_after_fetch_count"] == 1
      assert result["unresolved_after_fetch_tickers"] == ["LCID"]
  ```

- [ ] **Step 3: Evolve the five existing nodes without renaming them.**

  Make these assertion changes:

  ```python
  # test_backfill_per_ticker_exception_isolated
  ibkr = _FakeIBKR(
      {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]},
      raises_for=["BAD"],
  )
  db, res = _run_one_complete_day(
      tmp_path, monkeypatch, tickers="AAPL,BAD", ibkr=ibkr, db=db,
  )
  assert res["status"] == "partial"
  assert res["succeeded_ticker_count"] == 1
  assert conn.execute(
      "SELECT status, error FROM provider_sync_runs"
  ).fetchone() == ("failed", "price_collection_partial")

  # test_backfill_meta_write_failure_in_error_path_does_not_abort_batch
  ibkr = _FakeIBKR(
      {"AAPL": [_bar(datetime(2026, 6, 22, 9, 30))]},
      raises_for=["BAD"],
  )
  db, res = _run_one_complete_day(
      tmp_path, monkeypatch, tickers="BAD,AAPL", ibkr=ibkr, db=db,
  )
  assert res["status"] == "partial"
  assert res["succeeded_ticker_count"] == 1
  assert conn.execute(
      "SELECT status, error FROM provider_sync_runs"
  ).fetchone() == ("failed", "price_collection_partial")

  # test_backfill_topup_idempotent_on_complete_day
  # use lookback_days=1 and _ONE_COMPLETE_DAY_NOW for both calls
  assert a["status"] == b["status"] == "succeeded"
  assert a["rows_added"] == 1 and b["rows_added"] == 0

  # test_backfill_ibkr_empty_from_swallowed_request_error_falls_to_polygon
  # use lookback_days=1 and _ONE_COMPLETE_DAY_NOW
  assert res["status"] == "succeeded"
  assert res["unresolved_after_fetch_count"] == 0

  # test_backfill_fetches_provider_rows_outside_market_write_lock
  # return a date object from the detect_price_gaps fake and wrap the real
  # _unresolved_price_target_dates helper.
  reconciliation_observed_lock = []
  real_reconcile = mdd._unresolved_price_target_dates
  def checked_reconcile(*args, **kwargs):
      reconciliation_observed_lock.append(in_lock["value"])
      return real_reconcile(*args, **kwargs)
  monkeypatch.setattr(mdd, "_unresolved_price_target_dates", checked_reconcile)
  monkeypatch.setattr(
      mdd, "detect_price_gaps", lambda *a, **k: {"AAPL": [date(2026, 7, 3)]},
  )
  assert fetch_observed_lock == [False]
  assert reconciliation_observed_lock == [True]
  ```

  Also update comments that currently claim per-ticker failures leave the run
  succeeded. Preserve their isolation assertions.

- [ ] **Step 4: Run the direct suite and capture the right RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py
  ```

  Expected before implementation: the seven new contract nodes and evolved
  status assertions fail because no post-write reconciliation/status envelope
  exists. A provider/network call, calendar error, invalid date fixture, or SQL
  setup error is the wrong RED and must be corrected before product edits.

- [ ] **Step 5: Implement Sections 5.1 and 5.2 exactly.**

  Keep fetch in the first unlocked phase. Reconcile only `item["gaps"]` after
  `_insert_rows()` in the second write phase. Keep the existing outer fatal
  failure finalizer and best-effort per-ticker meta recovery.

- [ ] **Step 6: Run direct GREEN and exact collection.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_market_data_direct.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-direct-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-direct-tip.nodes
  ```

  Expected: `70 passed`, exactly `+7/-0`; all existing direct node IDs survive.

- [ ] **Step 7: Commit collector truth.**

  ```bash
  git add src/market_data_direct.py tests/test_market_data_direct.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: derive price collection partial truth"
  ```

## 9. Task 2 - Worker RED And GREEN

**Files:**
- Modify: `tests/test_prices_runtime.py`
- Modify: `src/prices_runtime.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add a valid result factory and four exact RED nodes.**

  Add this non-test helper:

  ```python
  def _collector_result(*, status="succeeded", scanned=2, errors=None, unresolved=None):
      errors = errors or {}
      unresolved = unresolved or []
      return {
          "status": status,
          "provider": "ibkr",
          "tickers_scanned": scanned,
          "succeeded_ticker_count": scanned - len(errors),
          "gaps_found": len(unresolved),
          "rows_added": 26 if status == "succeeded" else 1,
          "errors": errors,
          "unresolved_after_fetch_count": len(unresolved),
          "unresolved_after_fetch_tickers": unresolved,
      }
  ```

  Add these tests:

  ```python
  def test_prices_worker_prints_sanitized_partial_json_and_exits_zero(monkeypatch, capsys):
      from src import prices_runtime as worker
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: _collector_result(
              status="partial", errors={"LCID": "PRIVATE_PROVIDER_TEXT"},
              unresolved=["LCID"],
          ),
      )
      assert worker.main(["--tickers", "AAPL,LCID"]) == 0
      payload = json.loads(capsys.readouterr().out)
      assert payload == {
          "status": "partial", "provider": "ibkr", "tickers_scanned": 2,
          "succeeded_ticker_count": 1, "gaps_found": 1, "rows_added": 1,
          "error_count": 1, "error_tickers": ["LCID"],
          "unresolved_after_fetch_count": 1,
          "unresolved_after_fetch_tickers": ["LCID"],
      }
      assert "PRIVATE_PROVIDER_TEXT" not in json.dumps(payload)


  def test_prices_worker_prints_sanitized_failed_result_json_and_exits_nonzero(
      monkeypatch, capsys,
  ):
      from src import prices_runtime as worker
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: _collector_result(
              status="failed", scanned=2,
              errors={"BAD": "PRIVATE_A", "LCID": "PRIVATE_B"},
              unresolved=["LCID"],
          ),
      )
      assert worker.main(["--tickers", "BAD,LCID"]) == 1
      payload = json.loads(capsys.readouterr().out)
      assert payload["status"] == "failed"
      assert payload["error_count"] == 2
      assert payload["succeeded_ticker_count"] == 0
      assert payload["error_tickers"] == ["BAD", "LCID"]
      assert "PRIVATE_" not in json.dumps(payload)


  def test_prices_worker_rejects_unknown_status_and_malformed_counts(monkeypatch, capsys):
      from src import prices_runtime as worker
      invalid = _collector_result()
      invalid["status"] = "complete"
      with pytest.raises(ValueError, match="status"):
          worker.sanitize_result(invalid)
      for value in (-1, 1.5, True, "2"):
          invalid = _collector_result()
          invalid["rows_added"] = value
          with pytest.raises(ValueError, match="rows_added"):
              worker.sanitize_result(invalid)
      monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
      monkeypatch.setattr(
          worker, "_run_worker",
          lambda **kwargs: {**_collector_result(), "status": "PRIVATE_STATUS"},
      )
      assert worker.main(["--tickers", "AAPL,NVDA"]) == 1
      payload = json.loads(capsys.readouterr().out)
      assert payload["status"] == "failed"
      assert payload["error_class"] == "ValueError"
      assert "PRIVATE_STATUS" not in json.dumps(payload)


  def test_prices_worker_bounds_sorts_and_sanitizes_ticker_lists():
      from src import prices_runtime as worker
      tickers = [f"T{i:02d}" for i in range(30)]
      result = _collector_result(
          status="failed", scanned=30,
          errors={ticker: "PRIVATE" for ticker in reversed(tickers)},
          unresolved=list(reversed(tickers)),
      )
      payload = worker.sanitize_result(result)
      assert payload["error_count"] == 30
      assert payload["unresolved_after_fetch_count"] == 30
      assert payload["error_tickers"] == tickers[:25]
      assert payload["unresolved_after_fetch_tickers"] == tickers[:25]
      for malformed_ids in (["AAPL\nPRIVATE"], [123]):
          malformed = {
              **result,
              "unresolved_after_fetch_tickers": malformed_ids,
              "unresolved_after_fetch_count": len(malformed_ids),
          }
          with pytest.raises(ValueError, match="unresolved_after_fetch_tickers"):
              worker.sanitize_result(malformed)
  ```

- [ ] **Step 2: Evolve the two existing worker nodes in place.**

  `test_prices_worker_prints_sanitized_success_json` must return
  `_collector_result(status="succeeded", errors={}, unresolved=[])`, require
  every new count field, and require no raw error. Keep its node ID.

  `test_prices_worker_prints_sanitized_error_json` keeps the exact retryable
  lock-busy message and exit `1`, then adds one non-retryable exception case
  whose planted message is absent and whose class remains present. Keep both
  cases inside the same existing node.

- [ ] **Step 3: Run worker RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_prices_runtime.py
  ```

  Expected before implementation: partial is hard-coded to succeeded, failed
  result exits zero, malformed counts are coerced, and new fields are absent.
  All failures must be contract assertions, not argparse or fixture failures.

- [ ] **Step 4: Implement Section 5.3 exactly.**

  Keep `_run_worker()` and provider arguments unchanged. Validate all facts
  before serializing; strip per-ticker error values; preserve only the stable
  lock-busy diagnostic needed by scheduler skip classification.

- [ ] **Step 5: Run worker and direct GREEN.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_prices_runtime.py \
    tests/test_market_data_direct.py
  ```

  Expected: `78 passed` (`8 + 70`).

- [ ] **Step 6: Commit the worker boundary.**

  ```bash
  git add src/prices_runtime.py tests/test_prices_runtime.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: preserve price worker outcome truth"
  ```

## 10. Task 3 - Scheduler RED And GREEN

**Files:**
- Modify: `tests/test_data_scheduler.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add scheduler price-payload and audit helpers.**

  Add near the existing prices-worker tests:

  ```python
  def _scheduled_price_payload(
      *, status="succeeded", scanned=2, errors=0, unresolved=0,
  ):
      unresolved_tickers = ["LCID"][:unresolved]
      error_order = ["LCID", "BAD"] if unresolved else ["BAD", "LCID"]
      error_tickers = sorted(error_order[:errors])
      return {
          "status": status,
          "provider": "ibkr",
          "tickers_scanned": scanned,
          "succeeded_ticker_count": scanned - errors,
          "gaps_found": unresolved,
          "rows_added": 26 if status == "succeeded" else 1,
          "error_count": errors,
          "error_tickers": error_tickers,
          "unresolved_after_fetch_count": unresolved,
          "unresolved_after_fetch_tickers": unresolved_tickers,
          "error_class": "",
          "error": "",
          "retryable": False,
      }


  class _RecordingJobStore:
      def __init__(self):
          self.created = []
          self.finished = []

      def create_run(self, name, **kwargs):
          self.created.append((name, kwargs))
          return len(self.created)

      def finish_run(self, run_id, **kwargs):
          self.finished.append((run_id, kwargs))
          return True


  def _install_recording_job_store(monkeypatch):
      store = _RecordingJobStore()
      monkeypatch.setattr(
          "src.service.job_runs_store.JobRunsLocalStore",
          lambda profile_db: store,
      )
      return store
  ```

- [ ] **Step 2: Add the two strict parser RED nodes.**

  ```python
  def test_prices_worker_stdout_parser_preserves_partial_truth_and_bounded_tickers():
      raw = _scheduled_price_payload(
          status="partial", scanned=30, errors=1, unresolved=1,
      )
      raw["succeeded_ticker_count"] = 29
      raw["error_tickers"] = ["LCID"]
      raw["unresolved_after_fetch_tickers"] = ["LCID"]
      parsed = ds._parse_sanitized_prices_worker_stdout(json.dumps(raw))
      assert parsed == raw


  def test_prices_worker_stdout_parser_rejects_malformed_partial_payloads():
      valid = _scheduled_price_payload(status="partial", errors=1, unresolved=1)
      invalid = [
          {**valid, "status": "complete"},
          {**valid, "provider": "PRIVATE_PROVIDER"},
          {**valid, "rows_added": -1},
          {**valid, "error_count": True},
          {**valid, "succeeded_ticker_count": 2},
          {**valid, "unresolved_after_fetch_count": 2},
          {**valid, "error_tickers": "LCID"},
          {**valid, "error_tickers": ["LCID"] * 26},
          {**valid, "error_tickers": [123]},
          {**valid, "unresolved_after_fetch_tickers": ["LCID\nPRIVATE"]},
      ]
      for payload in invalid:
          assert ds._parse_sanitized_prices_worker_stdout(json.dumps(payload)) is None
  ```

  The first node uses one exposed ticker and full count one. The separate
  30-item cap is already owned by the worker node; scheduler owns validation
  and preservation of a bounded payload, not a second independent truncation
  policy.

- [ ] **Step 3: Add the four scheduler outcome RED nodes.**

  ```python
  def test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation(
      monkeypatch,
  ):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess",
          lambda argv: {
              "returncode": 0,
              "payload": _scheduled_price_payload(
                  status="partial", errors=1, unresolved=1,
              ),
          },
      )
      result = ds.run_source("ibkr_prices", trigger_source="api")
      assert result["status"] == "partial"
      assert result["collect"]["succeeded_ticker_count"] == 1
      assert result["collect"]["unresolved_after_fetch_tickers"] == ["LCID"]
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "partial"
      assert durable["last_error"] is None
      assert durable["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "failed"
      assert finished["error"] == "price_collection_partial"
      assert finished["message"] == "price_collection_partial"
      assert finished["result"]["status"] == "partial"


  def test_prices_failed_payload_persists_failed_without_partial(monkeypatch):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["BAD", "LCID"])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess",
          lambda argv: {
              "returncode": 1,
              "payload": _scheduled_price_payload(
                  status="failed", errors=2, unresolved=1,
              ),
          },
      )
      result = ds.run_source("ibkr_prices", trigger_source="api")
      assert result["status"] == "failed"
      assert result["collect"]["status"] == "failed"
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "failed"
      assert durable["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "failed"
      assert finished["error"] == "price_collection_failed"


  def test_prices_success_clears_prior_partial_and_preserves_audit_history(monkeypatch):
      store = _install_recording_job_store(monkeypatch)
      monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "LCID"])
      steps = iter([
          {
              "returncode": 0,
              "payload": _scheduled_price_payload(
                  status="partial", errors=1, unresolved=1,
              ),
          },
          {
              "returncode": 0,
              "payload": _scheduled_price_payload(status="succeeded"),
          },
      ])
      monkeypatch.setattr(
          ds, "_run_sanitized_prices_worker_subprocess", lambda argv: next(steps),
      )
      assert ds.run_source("ibkr_prices")["status"] == "partial"
      assert ds.run_source("ibkr_prices")["status"] == "succeeded"
      durable = ds._state_store().get("ibkr_prices")
      assert durable["last_status"] == "succeeded"
      assert durable["last_error"] is None
      assert durable["continuation"] is None
      assert [kwargs["status"] for _, kwargs in store.finished] == [
          "failed", "succeeded",
      ]
      assert store.finished[0][1]["error"] == "price_collection_partial"
      assert store.finished[1][1]["error"] is None


  def test_price_partial_projection_does_not_change_normalized_news_audit_status(
      monkeypatch,
  ):
      import src.news_normalized.routing as routing
      store = _install_recording_job_store(monkeypatch)
      _patch_news_write_route(monkeypatch, routing.NewsWriteMode.NORMALIZED)
      monkeypatch.setattr(
          ds, "_run_normalized_news_writer",
          lambda *args, **kwargs: {"status": "partial", "continuation": None},
      )
      result = ds.run_source("polygon_news", trigger_source="api")
      assert result["status"] == "partial"
      assert ds._state_store().get("polygon_news")["continuation"] is None
      _, finished = store.finished[-1]
      assert finished["status"] == "succeeded"
      assert finished["error"] is None
  ```

- [ ] **Step 4: Evolve the five existing scheduler nodes in place.**

  Use a fully valid `_scheduled_price_payload()` in both subprocess-launch
  nodes and in `test_price_scope_required`. Extend
  `test_prices_worker_stdout_parse_preserves_retryable_and_counts` to require
  all new fields and closed status while retaining the exception lock-busy
  case. Keep
  `test_prices_worker_retryable_lock_busy_is_skip_not_failure` unchanged except
  for any parser-required exception-envelope field. No node may be renamed.

- [ ] **Step 5: Run scheduler RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_data_scheduler.py
  ```

  Expected before implementation: strict parser cases fail; return-code-zero
  partial becomes succeeded; the audit projection is succeeded; a later
  success/history sequence lacks the required first failed audit. Normalized
  news must remain green.

- [ ] **Step 6: Implement Section 5.4 exactly.**

  Preserve the exception envelope and lock-busy skip. Treat payload status as
  semantic truth. Keep `price_partial` local to the prices branch and use a
  separate audit error so durable partial has no fabricated continuation or
  raw diagnostic.

- [ ] **Step 7: Run all backend focused tests and collect exact nodes.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py \
    | sed -n '/^tests\/.*::/p' \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-be-focused-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-be-focused-tip.nodes
  comm -13 /tmp/price-truth-be-focused.nodes /tmp/price-truth-be-focused-tip.nodes
  comm -23 /tmp/price-truth-be-focused.nodes /tmp/price-truth-be-focused-tip.nodes
  ```

  Expected: `168 passed`; hash
  `9faa90281df39dddccf7bedf3ad2ad7304341560c00dea8ff8b9dd887f5e55a3`;
  exact `+17/-0` with only Section 3.1 additions.

- [ ] **Step 8: Commit scheduler projection.**

  ```bash
  git add src/service/data_scheduler.py tests/test_data_scheduler.py \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "fix: project price partial through scheduler"
  ```

## 11. Task 4 - Frontend RED And GREEN

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`

- [ ] **Step 1: Add the pure display RED node.**

  Add inside `describe("schedulerStateLabel", ...)`:

  ```typescript
  it("renders price unresolved count and bounded ticker list without continuation", () => {
    const durable = {
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_prices",
        status: "partial",
        collect: {
          status: "partial" as const,
          tickers_scanned: 150,
          succeeded_ticker_count: 149,
          unresolved_after_fetch_count: 1,
          unresolved_after_fetch_tickers: ["LCID"],
        },
      },
    };
    expect(localizedSchedulerStateLabel(durable, zhT)).toEqual({
      label: "部分完成（抓取後仍有 1 個標的無法確認：LCID）",
      tone: "warn",
      needsContinue: false,
    });
    expect(localizedSchedulerStateLabel(durable, settingsT("en"))).toEqual({
      label: "Partially completed (1 ticker remains unresolved after collection: LCID)",
      tone: "warn",
      needsContinue: false,
    });
    const nonPrice = {
      ...durable,
      last_result: { ...durable.last_result, source: "polygon_news" },
    };
    expect(localizedSchedulerStateLabel(nonPrice, zhT).label).toBe("部分完成");
  });
  ```

- [ ] **Step 2: Add the mounted bilingual RED node and bounded fixture mode.**

  Place the fixture changes and new node inside the existing
  `describe("Settings provider config authority", ...)` block; the exact node
  ID in Section 3.2 includes that prefix.

  Add to `mocked`:

  ```typescript
  priceScheduleMode: "blank" as "blank" | "partial",
  ```

  In the `ibkr_prices` schedule fixture, derive `last_result` and
  `durable_state` from that mode:

  ```typescript
  last_result: mocked.priceScheduleMode === "partial" ? {
    source: "ibkr_prices",
    status: "partial",
    collect: {
      status: "partial",
      tickers_scanned: 150,
      succeeded_ticker_count: 149,
      gaps_found: 150,
      rows_added: 3874,
      error_count: 1,
      error_tickers: ["LCID"],
      unresolved_after_fetch_count: 1,
      unresolved_after_fetch_tickers: ["LCID"],
    },
  } : null,
  durable_state: mocked.priceScheduleMode === "partial" ? {
    last_status: "partial",
    last_error: null,
    continuation: null,
    last_result: {
      source: "ibkr_prices",
      status: "partial",
      collect: {
        status: "partial",
        tickers_scanned: 150,
        succeeded_ticker_count: 149,
        gaps_found: 150,
        rows_added: 3874,
        error_count: 1,
        error_tickers: ["LCID"],
        unresolved_after_fetch_count: 1,
        unresolved_after_fetch_tickers: ["LCID"],
      },
    },
    last_attempt: "2026-07-28T00:19:00Z",
    updated_at: "2026-07-28T00:22:00Z",
  } : null,
  ```

  Reset `mocked.priceScheduleMode = "blank"` in `afterEach`. Add the exact node:

  ```typescript
  it("renders price partial facts without a Continue control in both locales", async () => {
    mocked.priceScheduleMode = "partial";
    const jobs = health.jobs as Record<string, {
      status: string; finished_at: string; error: string;
    }>;
    jobs["collect.ibkr_prices"] = {
      status: "failed",
      finished_at: "2026-07-28T00:22:00Z",
      error: "price_collection_partial",
    };
    try {
      await renderDataSources();
      const row = () => Array.from(host!.querySelectorAll("tr")).find((node) =>
        node.textContent?.includes(
          i18n.language === "en" ? "IBKR Prices" : "IBKR 股價",
        ));
      expect(row()?.textContent).toContain("✗");
      expect(row()?.textContent)
        .toContain("部分完成（抓取後仍有 1 個標的無法確認：LCID）");
      expect(Array.from(row()!.querySelectorAll("button")).some((button) =>
        button.textContent?.trim() === "補抓")).toBe(false);

      await act(async () => { await i18n.changeLanguage("en"); });
      expect(row()?.textContent).toContain("✗");
      expect(row()?.textContent).toContain(
        "Partially completed (1 ticker remains unresolved after collection: LCID)",
      );
      expect(Array.from(row()!.querySelectorAll("button")).some((button) =>
        button.textContent?.trim() === "Continue")).toBe(false);
    } finally {
      delete jobs["collect.ibkr_prices"];
    }
  });
  ```

- [ ] **Step 3: Evolve the resource count node without renaming it.**

  Change only these expected values:

  ```typescript
  settings: 706,
  // ...
  expect(total, `${locale}.total`).toBe(1785);
  ```

  Explore stays `380`; every other subtree count stays exact.

- [ ] **Step 4: Run frontend RED.**

  ```bash
  cd apps/arkscope-web
  npx vitest run \
    src/marketDataDisplay.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts
  ```

  Expected before implementation: the two new nodes fail on the generic
  partial label and missing DTO/resources; the evolved resource count fails by
  exactly two leaves per locale.

- [ ] **Step 5: Implement Section 5.5 exactly.**

  Keep `DataSourcesSection.tsx` byte-identical. The dedicated branch must be
  source-exact (`ibkr_prices`), status-exact (`partial`), require a positive
  count plus at least one bounded ticker, and return `needsContinue=false`.

- [ ] **Step 6: Run focused frontend GREEN and inventory.**

  ```bash
  cd apps/arkscope-web
  npx vitest run \
    src/marketDataDisplay.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/i18n/resources.test.ts
  npx vitest list --json \
    | jq -r '.[] | [.file,.name] | @tsv' \
    | sed "s#$(pwd)/##" \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-fe-full-tip.nodes \
    | sha256sum
  awk -F '\t' \
    '$1=="src/SettingsProviderConfig.test.ts" || \
     $1=="src/i18n/resources.test.ts" || \
     $1=="src/marketDataDisplay.test.ts"' \
    /tmp/price-truth-fe-full-tip.nodes \
    | LC_ALL=C sort \
    | tee /tmp/price-truth-fe-focused-tip.nodes \
    | sha256sum
  wc -l /tmp/price-truth-fe-focused-tip.nodes
  cd ../..
  ```

  Expected: `88 passed`; full `1076` hash
  `de48671aa1d3f70cb87166e3f5b026804e206ac31f8e29fe7e74b38cde9448d5`;
  focused hash
  `b6f01cae4038c5c94f51da05ad920e52b723c387c6f48938f7dce6a13b028e4f`;
  exact `+2/-0`; Settings `706`, Explore `380`, total `1785`.

- [ ] **Step 7: Run frontend static gates.**

  ```bash
  cd apps/arkscope-web
  npm run check:i18n-literals
  npm run check:i18n-literals
  npm run typecheck
  npm run build
  cd ../..
  ```

  Expected: scanner twice `36/20/0/20`; typecheck and build exit zero.

- [ ] **Step 8: Commit frontend truth.**

  ```bash
  git add \
    apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/marketDataDisplay.ts \
    apps/arkscope-web/src/marketDataDisplay.test.ts \
    apps/arkscope-web/src/SettingsProviderConfig.test.ts \
    apps/arkscope-web/src/i18n/resources/en/settings.ts \
    apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts \
    apps/arkscope-web/src/i18n/resources.test.ts \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md
  git diff --cached --check
  git commit -m "feat: show unresolved price collection facts"
  ```

## 12. Task 5 - Mutation, Boundary, And Full Verification

**Files:**
- Modify: `docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md`
- Modify: `docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Run the eight independent mutation probes.**

  Apply one mutation at a time with `apply_patch`, run only its owning node,
  reverse that exact patch with `apply_patch`, and verify the product-file blob
  returns to its pre-mutation SHA. Record command, RED node, and restored blob.

  | Mutation | Required RED owner |
  |---|---|
  | Return `[]` without executing `_unresolved_price_target_dates` | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
| Force a zero-row ticker to bypass target reconciliation and imply success | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
  | Change day presence to require 26 stored rows | `test_backfill_one_row_low_volume_day_stays_succeeded` |
  | Pass `error=None` for an unresolved ticker | `test_backfill_partial_preserves_healthy_rows_and_marks_unresolved_target` |
  | Hard-code worker status to `succeeded` | `test_prices_worker_prints_sanitized_partial_json_and_exits_zero` |
  | Ignore payload partial when return code is zero | `test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation` |
  | Persist price partial audit as succeeded | `test_prices_partial_persists_durable_partial_failed_audit_and_no_continuation` |
  | Remove the frontend price-unresolved branch | both new frontend nodes |

  The 26-row mutation must affect the target/day-presence predicate, not merely
  add a dead condition after an empty target set. The one-row node must turn
  RED for the semantic reason. Preserve the exact temporary diff for this
  mutation in the evidence packet so review can prove that target
  classification, rather than only `_unresolved_price_target_dates()` on an
  already-empty target set, was changed.

- [ ] **Step 2: Reproduce exact final collections and comms.**

  Run Section 2.1, writing `*-tip.nodes`, then:

  ```bash
  comm -13 /tmp/price-truth-be-full.nodes /tmp/price-truth-be-full-tip.nodes
  comm -23 /tmp/price-truth-be-full.nodes /tmp/price-truth-be-full-tip.nodes
  comm -13 /tmp/price-truth-fe-full.nodes /tmp/price-truth-fe-full-tip.nodes
  comm -23 /tmp/price-truth-fe-full.nodes /tmp/price-truth-fe-full-tip.nodes
  ```

  Expected backend: `4739`, hash
  `a72bbd36dfad3d36aee2e6630e6024ec9fb4e910bebaf1363d44df8a1aa204dd`,
  exact `+17/-0`. Expected frontend: `96/1076`, hash
  `de48671aa1d3f70cb87166e3f5b026804e206ac31f8e29fe7e74b38cde9448d5`,
  exact `+2/-0`.

- [ ] **Step 3: Run focused and full test gates.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py \
    tests/test_prices_runtime.py \
    tests/test_data_scheduler.py

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    > /tmp/price-truth-tip-full.txt 2>&1
  sed -n 's/^FAILED \([^ ]*::[^ ]*\).*/\1/p; s/^ERROR \([^ ]*::[^ ]*\).*/\1/p' \
    /tmp/price-truth-tip-full.txt \
    | LC_ALL=C sort -u \
    | tee /tmp/price-truth-tip-nonpassing.nodes \
    | sha256sum
  comm -13 \
    /tmp/price-truth-base-nonpassing.nodes \
    /tmp/price-truth-tip-nonpassing.nodes
  ```

  Expected focused: `168 passed`. Expected new full-suite non-passing IDs:
  none. Any disappeared EIR-002 node is recorded as an environment observation,
  not claimed as this slice's fix unless the changed files causally own it.

- [ ] **Step 4: Run frontend full and non-node gates.**

  ```bash
  cd apps/arkscope-web
  npm test -- --run
  npm run typecheck
  npm run build
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count \
    tests/test_pg_unreachable_e2e.py

  /home/hyl/.virtualenvs/llm_app/bin/python src/smoke/pg_unreachable_e2e.py
  ```

  Expected: frontend `96/1076` all green; scanner twice `36/20/0/20`;
  typecheck/build zero; tools `53/54/54`; no-PG `23/23`, `ok=true`,
  `pg_attempts=[]`.

- [ ] **Step 5: Prove byte-identical protected files and trees.**

  ```bash
  git diff --exit-code "$PLAN_REVIEW_CLEARANCE_COMMIT" -- \
    data_sources/ibkr_source.py \
    data_sources/polygon_source.py \
    src/market_coverage \
    src/service/provider_health.py \
    src/ibkr_gateway_lock.py \
    src/api/routes/market_data.py \
    src/data_provider_config.py \
    src/provider_config_runtime.py \
    sql \
    scripts \
    apps/arkscope-web/src/settings/DataSourcesSection.tsx
  ```

  Set `PLAN_REVIEW_CLEARANCE_COMMIT` to the full recorded SHA from Task 0 before
  running the command. Re-run the catalog script from Task 0 and compare exact
  JSON. Run the existing schema,
  coverage, provider-health, Gateway-lock, source-catalog, and interval tests:

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_market_data_direct.py::test_provider_sync_runs_status_check_enforced_at_schema \
    tests/test_market_data_direct.py::test_provider_run_status_constrained_to_valid_set \
    tests/test_market_coverage_boundaries.py \
    tests/test_market_coverage_observations.py \
    tests/test_provider_health.py \
    tests/test_ibkr_gateway_lock.py \
    tests/test_data_scheduler.py::test_defaults_everything_disabled \
    tests/test_data_scheduler.py::test_scheduler_source_defs_have_no_legacy_collector_plumbing \
    tests/test_data_scheduler.py::test_is_due_matrix
  ```

- [ ] **Step 6: Prove shared frontend files changed only in allowed sections.**

  Review:

  ```bash
  git diff -U3 "$PLAN_REVIEW_CLEARANCE_COMMIT" -- \
    apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/marketDataDisplay.ts
  ```

  Require:

  ```text
  api.ts: only ScheduleRunResult.collect fields change
  marketDataDisplay.ts: only scheduler partial presentation changes
  coverage enums/functions/copy: byte-identical
  provider-health functions/copy: byte-identical
  ```

  In addition, run all existing Coverage V2 frontend nodes in
  `src/marketDataDisplay.test.ts`; they must remain green in the full focused
  file run.

- [ ] **Step 7: Complete the evidence packet and mark review-ready.**

  Record:

  1. every baseline and final node hash;
  2. exact backend `+17/-0` and frontend `+2/-0` comms;
  3. all 17 backend and two frontend additions by ID;
  4. all in-place evolved IDs;
  5. Settings `706`, Explore `380`, total `1785` with `+2/-0` keys;
  6. eight mutation commands and RED owners;
  7. full A/B non-passing node sets;
  8. scanner/tool/no-PG/typecheck/build results;
  9. protected blob/tree/catalog checks;
  10. explicit confirmation of zero provider, Gateway, scheduler, browser, and
      production-data interaction; and
  11. product tip full SHA.

  Update lifecycle headers to `IMPLEMENTATION REVIEW-READY - INDEPENDENT REVIEW
  NEXT` and add a newest-first priority-map entry with the exact final numbers.

- [ ] **Step 8: Commit review evidence.**

  ```bash
  git add \
    docs/superpowers/specs/2026-07-28-price-collection-partial-truth-design.md \
    docs/superpowers/plans/2026-07-28-price-collection-partial-truth.md \
    docs/superpowers/evidence/2026-07-28-price-collection-partial-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git diff --cached --check
  git commit -m "docs: record price collection truth evidence"
  git status --short
  ```

## 13. Task 6 - Independent Review And Integration Gate

**Files:**
- Modify only when resolving verified findings in files already owned by this plan.

- [ ] **Step 1: Request independent implementation review.**

  Provide the spec, plan, evidence packet, product base, clearance commit,
  product tip, exact node lists, and mutation records. Ask the reviewer to
  verify:

  ```text
  original target identity is not rederived
  provider fetch remains outside market_write_lock
  one-row low-volume does not become unresolved
  direct status is derived from distinct issue tickers
  unresolved meta preserves prior success and stable error
  worker/parser reject malformed status and counts
  scheduler reads payload status and keeps price continuation null
  price partial audit is failed while normalized-news audit is unchanged
  frontend count/list is source-exact, bilingual, and has no Continue
  exact node/resource/boundary ledgers close
  ```

- [ ] **Step 2: Resolve findings RED-first.**

  For each verified finding, add or evolve a named test that fails for that
  finding, record its node-ledger effect, implement the minimum correction,
  rerun all gates, and request focused re-review. Do not absorb unrelated
  provider scheduling, extended-hours, pacing, structured adapter-outcome,
  EIR-002, or scripts-retirement work.

- [ ] **Step 3: Integrate only after GREEN and explicit user approval.**

  Use `superpowers:finishing-a-development-branch`. Verify master has not moved
  incompatibly, fast-forward merge the exact reviewed tip, and rerun canonical
  focused collections/tests plus frontend typecheck/build/scanner. Do not push
  unless separately requested.

## 14. Task 7 - Post-Merge Read-Only Observation

**Files:**
- Modify: lifecycle docs only after observed evidence is complete.

- [ ] **Step 1: Restart merged ArkScope without triggering collection.**

  Restart only after merge. Confirm the desktop/sidecar loads merged code. Do
  not press Run, change cadence, or start a provider probe.

- [ ] **Step 2: Capture read-only pre-run facts.**

  With both SQLite databases in `mode=ro`, record latest
  `collect.ibkr_prices`, LCID `provider_sync_meta`, LCID latest stored bar,
  2026-07-27 Coverage row, file size/mtime, `PRAGMA integrity_check`, and
  `PRAGMA foreign_key_check`. This is observation, not repair.

- [ ] **Step 3: Obtain explicit approval before any manual provider action.**

  The ordinary enabled scheduler cycle may occur naturally. A manual Run,
  provider/Gateway probe, cadence change, retry experiment, or LCID repair
  requires a fresh user approval immediately before execution.

- [ ] **Step 4: Accept either truthful terminal outcome.**

  ```text
  Resolved:
    LCID gains at least one 2026-07-27 row; current provider error clears;
    collection succeeds; Coverage may be complete or partial by slot truth.

  Still unresolved:
    LCID remains zero-row; last_success does not advance; current error is
    price_day_unresolved_after_fetch; collector/scheduler are partial with
    unresolved count 1; audit rows are failed; Coverage remains indeterminate.
  ```

  Neither outcome may claim which provider, pacing rule, halt, entitlement, or
  no-trade condition caused it.

- [ ] **Step 5: Close lifecycle docs only after bounded observation.**

  Record merged SHA, read-only before/after facts, the actual natural-run
  outcome, and unchanged non-target DB integrity. Mark the slice LIVE only when
  merged verification and this observation are complete. The next sequence
  remains EIR-002 and then root scripts retirement according to the priority
  map's current explicit decision. Calendar-aware price scheduling and
  extended-hours capture remain separate candidate slices until explicitly
  reprioritized.

## 15. Plan Self-Review Checklist

- [x] Every spec requirement in Sections 3, 5, 6, 7, 8, 9, and 10 maps to a
  task and a named test or boundary gate.
- [x] The backend ledger is exactly `+17/-0`; the frontend ledger is exactly
  `+2/-0`; resource leaves are exactly `+2/-0` per locale.
- [x] Items 3, 4, and 6 of spec Section 9.1 are separately named and cannot
  hide one another.
- [x] The fixed-26 mutation turns the one-row low-volume node RED.
- [x] Normalized-news audit behavior is explicitly tested unchanged.
- [x] No adapter, Coverage, schema, provider-health, scheduler-cadence, source
  catalog, Gateway lock, scripts, production DB, or repair work entered scope.
- [x] No plan step contains an unresolved implementation choice or an
  ungrounded external-market acceptance constant.
