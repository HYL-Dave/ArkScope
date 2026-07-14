# Portfolio 1.1 Slice 2 Account Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: REVIEW-CLEARED, 2026-07-14. IMPLEMENTATION AUTHORIZED BUT NOT STARTED.**

**Goal:** Add a truthful Holdings account overview that shows every visible IBKR account's latest captured values, keeps manual-account holdings separate, exposes broker and canonical timestamps, and moves the shipped capture controls into the final Holdings tab hierarchy without implementing Slice 3 activity.

**Architecture:** Add one provider-free read projection over the shipped `PortfolioStore` authority and `PortfolioObservationStore` observations, exposed through an additive `GET /portfolio/overview` route. The projection joins each non-archived account to its latest captured account snapshot and canonical position-sync time, reuses the existing Portfolio totals algorithm for included manual accounts, derives daily total P&L only when both provider legs exist, and never calls IBKR; it retains the pre-existing fresh-profile `ensure_manual_account` initialization already used by `GET /portfolio` rather than inventing a second initialization policy. The React Holdings surface loads `/portfolio` first and then the failure-isolated overview, avoiding a new concurrent fresh-profile Manual-shell race while keeping canonical positions usable when the additive overview is unavailable; it renders summary/details from one DTO and exposes only the three completed tabs, with Slice 3 inserting `活動` later at its locked position.

**Tech Stack:** Python, SQLite/WAL, FastAPI, frozen dataclasses, React 18, TypeScript 5.5, Vite/Vitest, existing P2.8 `DataTable`, `StatusBadge`, `InlineAlert`, `Button`, and `PageHeader` primitives.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md` wins over this plan on conflict.
- Implementation baseline for behavioral A/B is `a0daf69`; later plan/status documentation is non-behavioral.
- Existing `portfolio_accounts`, `portfolio_positions`, and `portfolio_position_notes` remain canonical current-state authority. Account observations never rewrite or reconstruct them.
- Slice 2 adds no new write route, write gate, broker call, scheduler, or background task. The overview retains one existing V1 first-read behavior: a fresh profile may create the Manual account shell through `list_accounts()` / `ensure_manual_account`; it creates no broker shell, observation, position, or review/apply mutation.
- `GET /portfolio/overview` is additive. Existing `/portfolio`, `/portfolio/accounts`, `/portfolio/capture`, tool schemas, research hydration, and capture payloads remain compatible.
- Every non-archived account remains visible. An IBKR account with no captured snapshot renders an explicit no-data state; a manual account renders no broker-value claim.
- IBKR values are displayed per account. Slice 2 deliberately does **not** implement the optional cross-account IBKR subtotal, so mixed currencies can never create a fake grand total.
- The only manual aggregate is labeled `手動帳戶持倉小計`. Its members are non-archived manual accounts with `include_in_total=true`; it reuses the shipped open-position/currency-basis totals calculation, excludes every IBKR position, and is never added to Net Liquidation or labeled net worth.
- `daily_total_pnl` is labeled `已實現 + 未實現`. It is returned only when both provider-reported daily legs are finite/non-null; a missing leg keeps the total null rather than treating the missing value as zero.
- Broker observation time is the latest snapshot `as_of_utc`. Canonical position sync/approval time is the maximum persisted `last_sync_at` for that account across open **and closed** canonical rows, so a complete liquidation does not erase the authority timestamp.
- Snapshot/capture times use `formatSystemTimestamp` (local time plus ET). `今日` P&L labels explicitly say `ET`.
- The new overview response never exposes `broker_account_id`. If a legacy label embeds the raw id, the projection replaces it with `IBKR · <hash-prefix>` before serialization. The local id, user-safe label, and hash remain available.
- The final tab order remains `持倉 / 活動 / 帳戶明細 / 同步紀錄`, but unfinished controls are not rendered. Slice 2 renders `持倉 / 帳戶明細 / 同步紀錄`; Slice 3 inserts `活動` between the first and second rendered tabs. No disabled or empty activity placeholder is allowed.
- Account summary remains above the tablist and visible for every completed tab. The existing manual-position editor and canonical positions stay under `持倉`; canonical position rows gain an account column and an all/account filter using the overview's safe label; `PortfolioCapturePanel` moves under `同步紀錄`; complete latest snapshot fields live under `帳戶明細`.
- `PortfolioAccountSummary` replaces the existing Accounts card/status-grid block completely. The old per-account cards, duplicate `納入總計` controls, mixed-account `Currency basis` metric, and `currencySummary()` helper must be removed rather than left beside or outside the new tab hierarchy.
- A new frontend plus an old/stale sidecar must not make canonical positions unusable. Overview failure renders a scoped alert while `/portfolio` data remains interactive. The frontend loads `/portfolio` before `/portfolio/overview`; do not issue the two first-read requests concurrently because both retain V1 Manual-shell initialization.
- Financial tables own horizontal scrolling and do not shrink numeric text. Visual verification is mandatory at `1440x900`, `1024x768`, `961x768`, `959x768`, and `390x844`.
- No new `@media` query, shell breakpoint, ad hoc badge/chip, raw exception surface, `window.confirm`, PostgreSQL path, order API, agent tool, prompt input, or Data Sources scheduler control is allowed.
- Slice 3 owns activity/order grouping, fills, commissions, corrections, unmatched detail, annotations, filters, gap markers, and the contextual recent-activity panel. None may be prebuilt here.
- Implementation stops review-ready. Merge, LIVE status, worktree cleanup, and Slice 3 planning remain separate user decisions.

---

## Locked File and Interface Map

| File | Responsibility |
| --- | --- |
| `src/portfolio_capture_types.py` | Add the immutable persisted latest-account-snapshot read DTO; no storage/input contract changes. |
| `src/portfolio_observations.py` | Select exactly one latest snapshot per requested local account with deterministic SQL ordering. |
| `src/portfolio_state.py` | Expose read-only canonical sync-time and exact-account totals helpers while keeping `_totals` the single calculation authority. |
| `src/portfolio_overview.py` | New pure join/projection: safe labels, per-account broker values, null-safe deterministic daily total, and manual subtotal. |
| `src/api/routes/portfolio.py` | Add `GET /portfolio/overview` using existing dependency seams and `_to_json`. |
| `apps/arkscope-web/src/api.ts` | Add the exact additive overview DTO and `getPortfolioOverview()`. |
| `apps/arkscope-web/src/PortfolioAccountOverview.tsx` | Render always-visible account summary and complete account-details table from one DTO. |
| `apps/arkscope-web/src/Holdings.tsx` | Fetch authority/overview independently, add the three completed tabs, retain positions, and move capture controls. |
| `apps/arkscope-web/src/styles.css` | Feature-scoped account-row/tab/detail-table layout only; shared tokens/primitives remain authoritative. |

## Additive API Contract

`GET /portfolio/overview` returns no raw broker id and performs no provider I/O:

```json
{
  "accounts": [
    {
      "id": 2,
      "label": "IBKR · 1a2b3c4d",
      "broker": "ibkr",
      "broker_account_id_hash": "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
      "sync_mode": "ibkr_review",
      "base_currency": "USD",
      "include_in_total": true,
      "canonical_last_sync_at": "2026-07-14T05:01:00+00:00",
      "latest_snapshot": {
        "capture_run_id": 50,
        "as_of_utc": "2026-07-14T05:00:02+00:00",
        "as_of_kind": "capture_completed",
        "source": "ibkr_gateway",
        "base_currency": "USD",
        "net_liquidation": 100000.0,
        "total_cash_value": 10000.0,
        "settled_cash": null,
        "gross_position_value": 90000.0,
        "buying_power": 25000.0,
        "available_funds": 20000.0,
        "initial_margin_requirement": 15000.0,
        "maintenance_margin_requirement": 12000.0,
        "daily_realized_pnl": 125.0,
        "daily_unrealized_pnl": -25.0,
        "daily_total_pnl": 100.0
      }
    }
  ],
  "manual_subtotal": {
    "included_account_ids": [1],
    "totals": {
      "currency_basis": "per_currency",
      "per_currency": {},
      "broker_base": null
    }
  }
}
```

---

### Task 1: Latest Account-Snapshot Read Projection

**Files:**
- Modify: `src/portfolio_capture_types.py`
- Modify: `src/portfolio_observations.py`
- Test: `tests/test_portfolio_observations.py`

**Interfaces:**
- Consumes: existing `portfolio_account_snapshots` rows and local `portfolio_account_id` relations.
- Produces: `AccountSnapshotRecord` and `PortfolioObservationStore.latest_account_snapshots(account_ids: Collection[int] | None = None) -> dict[int, AccountSnapshotRecord]`.

- [ ] **Step 1: Add three RED store tests**

Append tests with these exact contracts:

```python
def test_latest_account_snapshots_returns_one_newest_full_record_per_account(stores):
    portfolio, observations = stores
    first = complete_result(finished_at="2026-07-14T05:00:00+00:00")
    commit(observations, first)
    latest_result = replace(
        first,
        finished_at_utc="2026-07-14T05:15:00+00:00",
        account_snapshots=(AccountSnapshotObservation(
            broker_account_id="DU123",
            as_of_utc="2026-07-14T05:15:00+00:00",
            base_currency="USD",
            net_liquidation=101_000,
            total_cash_value=11_000,
            settled_cash=9_000,
            gross_position_value=90_000,
            buying_power=25_000,
            available_funds=20_000,
            initial_margin_requirement=15_000,
            maintenance_margin_requirement=12_000,
            daily_realized_pnl=125,
            daily_unrealized_pnl=-25,
        ),),
    )
    latest_run_id, _ = commit(observations, latest_result)
    account = next(a for a in portfolio.list_accounts() if a.broker == "ibkr")

    records = observations.latest_account_snapshots()

    assert records[account.id] == AccountSnapshotRecord(
        capture_run_id=latest_run_id,
        portfolio_account_id=account.id,
        as_of_utc="2026-07-14T05:15:00+00:00",
        base_currency="USD",
        net_liquidation=101_000,
        total_cash_value=11_000,
        settled_cash=9_000,
        gross_position_value=90_000,
        buying_power=25_000,
        available_funds=20_000,
        initial_margin_requirement=15_000,
        maintenance_margin_requirement=12_000,
        daily_realized_pnl=125,
        daily_unrealized_pnl=-25,
        source="ibkr_gateway",
        as_of_kind="capture_completed",
    )


def test_latest_account_snapshots_filters_local_ids_and_breaks_time_ties_by_run(stores):
    portfolio, observations = stores
    same_time = "2026-07-14T06:00:00+00:00"
    first_id, _ = commit(observations, complete_result(finished_at=same_time))
    second = complete_result(finished_at=same_time)
    second = replace(
        second,
        account_snapshots=(replace(second.account_snapshots[0], net_liquidation=222_000),),
    )
    second_id, _ = commit(observations, second)
    account = next(a for a in portfolio.list_accounts() if a.broker == "ibkr")

    records = observations.latest_account_snapshots({account.id})

    assert first_id < second_id
    assert records[account.id].capture_run_id == second_id
    assert records[account.id].net_liquidation == 222_000


def test_latest_account_snapshots_empty_filter_returns_empty(stores):
    _, observations = stores
    assert observations.latest_account_snapshots(set()) == {}
```

Add `AccountSnapshotRecord` to the test imports. `replace` is already imported.

- [ ] **Step 2: Run the three tests and verify the intended RED**

Run:

```bash
pytest tests/test_portfolio_observations.py -k latest_account_snapshots -q
```

Expected: three failures because `AccountSnapshotRecord` and `latest_account_snapshots` do not exist; no schema or fixture failure may precede that reason.

- [ ] **Step 3: Add the immutable read DTO**

In `src/portfolio_capture_types.py`, after `AccountSnapshotObservation`, add:

```python
@dataclass(frozen=True)
class AccountSnapshotRecord:
    capture_run_id: int
    portfolio_account_id: int
    as_of_utc: str
    base_currency: str | None = None
    net_liquidation: float | None = None
    total_cash_value: float | None = None
    settled_cash: float | None = None
    gross_position_value: float | None = None
    buying_power: float | None = None
    available_funds: float | None = None
    initial_margin_requirement: float | None = None
    maintenance_margin_requirement: float | None = None
    daily_realized_pnl: float | None = None
    daily_unrealized_pnl: float | None = None
    source: Literal["ibkr_gateway"] = "ibkr_gateway"
    as_of_kind: Literal["capture_completed"] = "capture_completed"
```

This is a read shape only. Do not change `AccountSnapshotObservation`, schema CHECK clauses, or capture writes.

- [ ] **Step 4: Implement one bounded SQL latest-row query**

Import `Collection` from `collections.abc` and `AccountSnapshotRecord`. Add this public method near `list_runs`:

```python
def latest_account_snapshots(
    self,
    account_ids: Collection[int] | None = None,
) -> dict[int, AccountSnapshotRecord]:
    ids = None if account_ids is None else sorted({int(value) for value in account_ids})
    if ids == []:
        return {}
    where = ""
    params: tuple[int, ...] = ()
    if ids is not None:
        placeholders = ",".join("?" for _ in ids)
        where = f"WHERE portfolio_account_id IN ({placeholders})"
        params = tuple(ids)
    with self._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM (
                SELECT s.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY s.portfolio_account_id
                           ORDER BY s.as_of_utc DESC, s.capture_run_id DESC, s.id DESC
                       ) AS latest_rank
                FROM portfolio_account_snapshots s
                {where}
            )
            WHERE latest_rank=1
            ORDER BY portfolio_account_id
            """,
            params,
        ).fetchall()
    return {
        int(row["portfolio_account_id"]): self._account_snapshot_record(row)
        for row in rows
    }
```

Add the exact mapper, listing every persisted field rather than serializing `row` wholesale:

```python
@staticmethod
def _account_snapshot_record(row: sqlite3.Row) -> AccountSnapshotRecord:
    return AccountSnapshotRecord(
        capture_run_id=int(row["capture_run_id"]),
        portfolio_account_id=int(row["portfolio_account_id"]),
        as_of_utc=row["as_of_utc"],
        base_currency=row["base_currency"],
        net_liquidation=row["net_liquidation"],
        total_cash_value=row["total_cash_value"],
        settled_cash=row["settled_cash"],
        gross_position_value=row["gross_position_value"],
        buying_power=row["buying_power"],
        available_funds=row["available_funds"],
        initial_margin_requirement=row["initial_margin_requirement"],
        maintenance_margin_requirement=row["maintenance_margin_requirement"],
        daily_realized_pnl=row["daily_realized_pnl"],
        daily_unrealized_pnl=row["daily_unrealized_pnl"],
        source=row["source"],
        as_of_kind=row["as_of_kind"],
    )
```

- [ ] **Step 5: Run focused tests**

```bash
pytest tests/test_portfolio_observations.py -q
```

Expected: `21 passed` (`18 + 3`), with no observation schema change.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/portfolio_capture_types.py src/portfolio_observations.py tests/test_portfolio_observations.py
git commit -m "feat: expose latest portfolio account snapshots"
```

---

### Task 2: Canonical Sync-Time and Exact-Account Totals Helpers

**Files:**
- Modify: `src/portfolio_state.py`
- Test: `tests/test_portfolio_state.py`

**Interfaces:**
- Consumes: existing canonical position rows and `_totals(positions)`.
- Produces: `PortfolioStore.last_position_sync_at_by_account(account_ids: Collection[int] | None = None) -> dict[int, str]` and `PortfolioStore.totals_for_accounts(account_ids: Collection[int]) -> PortfolioTotals`.

- [ ] **Step 1: Add three RED authority-read tests**

```python
def test_last_position_sync_time_survives_complete_liquidation(monkeypatch, tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR", base_currency="USD")
    monkeypatch.setattr("src.portfolio_state._now", lambda: "2026-07-14T05:00:00+00:00")
    store.apply_broker_positions(
        account_id=account.id,
        positions=[BrokerPosition("ibkr", "DU123", "1", "AAPL", "stock", 1)],
        source="capture",
    )
    monkeypatch.setattr("src.portfolio_state._now", lambda: "2026-07-14T06:00:00+00:00")
    store.apply_broker_positions(account_id=account.id, positions=[], source="capture")

    assert store.list_positions(account_id=account.id) == []
    assert store.last_position_sync_at_by_account({account.id}) == {
        account.id: "2026-07-14T06:00:00+00:00"
    }


def test_totals_for_accounts_reuses_open_position_currency_rules_and_exact_ids(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    manual = store.ensure_manual_account()
    included = store.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    excluded_account = store.upsert_broker_account("ibkr", "DU123", "IBKR")
    store.apply_broker_positions(
        account_id=excluded_account.id,
        positions=[BrokerPosition(
            "ibkr", "DU123", "1", "MSFT", "stock", 1,
            currency="USD", market_value=999,
        )],
        source="capture",
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=250 WHERE id=?",
            (included.id,),
        )

    totals = store.totals_for_accounts({manual.id})

    assert totals.currency_basis == "per_currency"
    assert totals.per_currency["USD"].position_count == 1
    assert totals.per_currency["USD"].market_value == 250


def test_totals_for_accounts_empty_set_never_falls_back_to_all_positions(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    manual = store.ensure_manual_account()
    store.upsert_manual_position(account_id=manual.id, symbol="AAPL", quantity=1)

    totals = store.totals_for_accounts(set())

    assert totals.per_currency == {}
    assert totals.broker_base is None
```

- [ ] **Step 2: Verify RED**

```bash
pytest tests/test_portfolio_state.py -k "last_position_sync_time or totals_for_accounts" -q
```

Expected: three failures because both public read helpers are absent.

- [ ] **Step 3: Implement the helpers without duplicating totals math**

Import `Collection` from `collections.abc`. Add:

```python
def last_position_sync_at_by_account(
    self,
    account_ids: Collection[int] | None = None,
) -> dict[int, str]:
    ids = None if account_ids is None else sorted({int(value) for value in account_ids})
    if ids == []:
        return {}
    where = "WHERE last_sync_at IS NOT NULL"
    params: tuple[int, ...] = ()
    if ids is not None:
        placeholders = ",".join("?" for _ in ids)
        where += f" AND account_id IN ({placeholders})"
        params = tuple(ids)
    with self._connect() as conn:
        rows = conn.execute(
            f"""
            SELECT account_id, MAX(last_sync_at) AS last_sync_at
            FROM portfolio_positions
            {where}
            GROUP BY account_id
            """,
            params,
        ).fetchall()
    return {int(row["account_id"]): row["last_sync_at"] for row in rows}


def totals_for_accounts(self, account_ids: Collection[int]) -> PortfolioTotals:
    ids = {int(value) for value in account_ids}
    if not ids:
        return _totals([])
    positions = [
        position
        for position in self.list_positions(include_closed=False)
        if position.account_id in ids
    ]
    return _totals(positions)
```

Do not make `_totals` public, copy its arithmetic, or count closed rows.

- [ ] **Step 4: Run the authority suite**

```bash
pytest tests/test_portfolio_state.py -q
```

Expected: `29 passed` (`26 + 3`).

- [ ] **Step 5: Commit Task 2**

```bash
git add src/portfolio_state.py tests/test_portfolio_state.py
git commit -m "feat: expose portfolio overview authority reads"
```

---

### Task 3: Pure Account Overview Projection

**Files:**
- Create: `src/portfolio_overview.py`
- Create: `tests/test_portfolio_overview.py`

**Interfaces:**
- Consumes: `PortfolioStore.list_accounts`, `totals_for_accounts`, `last_position_sync_at_by_account`, and `PortfolioObservationStore.latest_account_snapshots`.
- Produces: `build_portfolio_overview(portfolio: PortfolioStore, observations: PortfolioObservationStore) -> PortfolioOverview` plus frozen JSON-safe DTOs.

- [ ] **Step 1: Create seven RED projection tests**

Create `tests/test_portfolio_overview.py` with the real stores and exact broker-capture seam:

```python
from __future__ import annotations

from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_overview import build_portfolio_overview
from src.portfolio_state import BrokerPosition, PortfolioStore


def captured_account(
    *,
    account: str = "DU123",
    as_of: str = "2026-07-14T05:00:00+00:00",
    realized: float | None = 125,
    unrealized: float | None = -25,
) -> BrokerCaptureResult:
    return BrokerCaptureResult(
        finished_at_utc=as_of,
        discovered_accounts=(BrokerAccountRef(account, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult("complete"),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(AccountSnapshotObservation(
            broker_account_id=account,
            as_of_utc=as_of,
            base_currency="USD",
            net_liquidation=100_000,
            total_cash_value=10_000,
            settled_cash=9_000,
            gross_position_value=90_000,
            buying_power=25_000,
            available_funds=20_000,
            initial_margin_requirement=15_000,
            maintenance_margin_requirement=12_000,
            daily_realized_pnl=realized,
            daily_unrealized_pnl=unrealized,
        ),),
        positions=(),
        executions=(),
        commissions=(),
    )


def commit_snapshot(observations: PortfolioObservationStore, result: BrokerCaptureResult) -> int:
    run = observations.create_run(trigger="manual", effective_client_id=71)
    observations.commit_capture(run.id, result)
    observations.finish_run(run.id, state="succeeded")
    return run.id


def stores(tmp_path):
    path = tmp_path / "profile_state.db"
    return PortfolioStore(path), PortfolioObservationStore(path)


def test_overview_keeps_every_visible_account_and_marks_missing_snapshots(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    ibkr = portfolio.upsert_broker_account("ibkr", "DU123", "Primary")

    overview = build_portfolio_overview(portfolio, observations)
    rows = {row.id: row for row in overview.accounts}

    assert set(rows) == {manual.id, ibkr.id}
    assert rows[manual.id].latest_snapshot is None
    assert rows[ibkr.id].latest_snapshot is None


def test_overview_joins_latest_values_and_distinct_broker_canonical_times(
    monkeypatch, tmp_path,
):
    portfolio, observations = stores(tmp_path)
    run_id = commit_snapshot(observations, captured_account())
    ibkr = next(account for account in portfolio.list_accounts() if account.broker == "ibkr")
    monkeypatch.setattr("src.portfolio_state._now", lambda: "2026-07-14T05:01:00+00:00")
    portfolio.apply_broker_positions(
        account_id=ibkr.id,
        positions=[BrokerPosition("ibkr", "DU123", "1", "AAPL", "stock", 1)],
        source="capture",
    )

    overview = build_portfolio_overview(portfolio, observations)
    row = next(item for item in overview.accounts if item.id == ibkr.id)

    assert row.canonical_last_sync_at == "2026-07-14T05:01:00+00:00"
    assert row.latest_snapshot is not None
    assert row.latest_snapshot.capture_run_id == run_id
    assert row.latest_snapshot.as_of_utc == "2026-07-14T05:00:00+00:00"
    assert row.latest_snapshot.net_liquidation == 100_000
    assert row.latest_snapshot.daily_total_pnl == 100


def test_overview_daily_total_requires_both_finite_provider_legs(tmp_path):
    portfolio, observations = stores(tmp_path)
    commit_snapshot(observations, captured_account(realized=125, unrealized=None))

    row = next(
        item for item in build_portfolio_overview(portfolio, observations).accounts
        if item.broker == "ibkr"
    )

    assert row.latest_snapshot is not None
    assert row.latest_snapshot.daily_realized_pnl == 125
    assert row.latest_snapshot.daily_unrealized_pnl is None
    assert row.latest_snapshot.daily_total_pnl is None

    commit_snapshot(observations, captured_account(
        as_of="2026-07-14T05:15:00+00:00",
        realized=1e308,
        unrealized=1e308,
    ))
    overflow_row = next(
        item for item in build_portfolio_overview(portfolio, observations).accounts
        if item.broker == "ibkr"
    )
    assert overflow_row.latest_snapshot is not None
    assert overflow_row.latest_snapshot.daily_total_pnl is None


def test_overview_manual_subtotal_uses_only_included_manual_accounts(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    position = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    with portfolio._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=500, unrealized_pnl=25 WHERE id=?",
            (position.id,),
        )

    included = build_portfolio_overview(portfolio, observations).manual_subtotal
    portfolio.update_account(manual.id, include_in_total=False)
    excluded = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert included.included_account_ids == [manual.id]
    assert included.totals.per_currency["USD"].market_value == 500
    assert excluded.included_account_ids == []
    assert excluded.totals.per_currency == {}


def test_overview_manual_subtotal_never_contains_ibkr_positions(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    manual_position = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=2, currency="USD"
    )
    ibkr = portfolio.upsert_broker_account("ibkr", "DU123", "Primary")
    portfolio.apply_broker_positions(
        account_id=ibkr.id,
        positions=[BrokerPosition(
            "ibkr", "DU123", "1", "MSFT", "stock", 1,
            currency="USD", market_value=999,
        )],
        source="capture",
    )
    with portfolio._connect() as conn:
        conn.execute(
            "UPDATE portfolio_positions SET market_value=500 WHERE id=?",
            (manual_position.id,),
        )

    subtotal = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert subtotal.included_account_ids == [manual.id]
    assert subtotal.totals.per_currency["USD"].position_count == 1
    assert subtotal.totals.per_currency["USD"].market_value == 500


def test_overview_mixed_manual_currencies_remain_per_currency_without_grand_total(tmp_path):
    portfolio, observations = stores(tmp_path)
    manual = portfolio.ensure_manual_account()
    usd = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="AAPL", quantity=1, currency="USD"
    )
    twd = portfolio.upsert_manual_position(
        account_id=manual.id, symbol="2330", quantity=10, currency="TWD"
    )
    with portfolio._connect() as conn:
        conn.execute("UPDATE portfolio_positions SET market_value=100 WHERE id=?", (usd.id,))
        conn.execute("UPDATE portfolio_positions SET market_value=10000 WHERE id=?", (twd.id,))

    subtotal = build_portfolio_overview(portfolio, observations).manual_subtotal

    assert subtotal.totals.currency_basis == "per_currency"
    assert set(subtotal.totals.per_currency) == {"USD", "TWD"}
    assert subtotal.totals.broker_base is None


def test_overview_redacts_legacy_label_that_contains_raw_broker_id(tmp_path):
    portfolio, observations = stores(tmp_path)
    account = portfolio.upsert_broker_account("ibkr", "DU123", "IBKR DU123")

    row = next(
        item for item in build_portfolio_overview(portfolio, observations).accounts
        if item.id == account.id
    )

    assert row.label == f"IBKR · {account.broker_account_id_hash[:8]}"
    assert "DU123" not in repr(row)
```

- [ ] **Step 2: Verify RED imports**

```bash
pytest tests/test_portfolio_overview.py -q
```

Expected: collection fails only because `src.portfolio_overview` does not exist.

- [ ] **Step 3: Define the exact frozen projection DTOs**

Create `src/portfolio_overview.py` with:

```python
from __future__ import annotations

import math
from dataclasses import dataclass

from src.portfolio_capture_types import AccountSnapshotRecord
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioAccount, PortfolioStore, PortfolioTotals


@dataclass(frozen=True)
class AccountValueOverview:
    capture_run_id: int
    as_of_utc: str
    base_currency: str | None
    net_liquidation: float | None
    total_cash_value: float | None
    settled_cash: float | None
    gross_position_value: float | None
    buying_power: float | None
    available_funds: float | None
    initial_margin_requirement: float | None
    maintenance_margin_requirement: float | None
    daily_realized_pnl: float | None
    daily_unrealized_pnl: float | None
    daily_total_pnl: float | None
    source: str
    as_of_kind: str


@dataclass(frozen=True)
class PortfolioAccountOverviewRow:
    id: int
    label: str
    broker: str
    broker_account_id_hash: str | None
    sync_mode: str
    base_currency: str | None
    include_in_total: bool
    canonical_last_sync_at: str | None
    latest_snapshot: AccountValueOverview | None


@dataclass(frozen=True)
class ManualPortfolioSubtotal:
    included_account_ids: list[int]
    totals: PortfolioTotals


@dataclass(frozen=True)
class PortfolioOverview:
    accounts: list[PortfolioAccountOverviewRow]
    manual_subtotal: ManualPortfolioSubtotal
```

- [ ] **Step 4: Implement the pure join and privacy rule**

```python
def build_portfolio_overview(
    portfolio: PortfolioStore,
    observations: PortfolioObservationStore,
) -> PortfolioOverview:
    accounts = portfolio.list_accounts()
    broker_ids = {account.id for account in accounts if account.broker != "manual"}
    snapshots = observations.latest_account_snapshots(broker_ids)
    canonical_times = portfolio.last_position_sync_at_by_account(broker_ids)
    manual_ids = sorted(
        account.id
        for account in accounts
        if account.broker == "manual" and account.include_in_total
    )
    rows = [
        PortfolioAccountOverviewRow(
            id=account.id,
            label=_safe_label(account),
            broker=account.broker,
            broker_account_id_hash=account.broker_account_id_hash,
            sync_mode=account.sync_mode,
            base_currency=account.base_currency,
            include_in_total=account.include_in_total,
            canonical_last_sync_at=canonical_times.get(account.id),
            latest_snapshot=_values(snapshots.get(account.id)),
        )
        for account in accounts
    ]
    return PortfolioOverview(
        accounts=rows,
        manual_subtotal=ManualPortfolioSubtotal(
            included_account_ids=manual_ids,
            totals=portfolio.totals_for_accounts(manual_ids),
        ),
    )


def _safe_label(account: PortfolioAccount) -> str:
    raw_id = account.broker_account_id
    if raw_id and raw_id in account.label:
        if account.broker_account_id_hash:
            return f"{account.broker.upper()} · {account.broker_account_id_hash[:8]}"
        return account.broker.upper()
    return account.label


def _values(record: AccountSnapshotRecord | None) -> AccountValueOverview | None:
    if record is None:
        return None
    total = None
    if record.daily_realized_pnl is not None and record.daily_unrealized_pnl is not None:
        candidate = record.daily_realized_pnl + record.daily_unrealized_pnl
        total = candidate if math.isfinite(candidate) else None
    return AccountValueOverview(
        capture_run_id=record.capture_run_id,
        as_of_utc=record.as_of_utc,
        base_currency=record.base_currency,
        net_liquidation=record.net_liquidation,
        total_cash_value=record.total_cash_value,
        settled_cash=record.settled_cash,
        gross_position_value=record.gross_position_value,
        buying_power=record.buying_power,
        available_funds=record.available_funds,
        initial_margin_requirement=record.initial_margin_requirement,
        maintenance_margin_requirement=record.maintenance_margin_requirement,
        daily_realized_pnl=record.daily_realized_pnl,
        daily_unrealized_pnl=record.daily_unrealized_pnl,
        daily_total_pnl=total,
        source=record.source,
        as_of_kind=record.as_of_kind,
    )
```

Do not expose `broker_account_id`, optional IBKR aggregation, or historical snapshot arrays.

- [ ] **Step 5: Run projection and neighboring store suites**

```bash
pytest tests/test_portfolio_overview.py tests/test_portfolio_observations.py tests/test_portfolio_state.py -q
```

Expected: `57 passed` (`7 + 21 + 29`).

- [ ] **Step 6: Commit Task 3**

```bash
git add src/portfolio_overview.py tests/test_portfolio_overview.py
git commit -m "feat: project portfolio account overview"
```

---

### Task 4: Additive Overview Route

**Files:**
- Modify: `src/api/routes/portfolio.py`
- Modify: `tests/test_portfolio_routes.py`

**Interfaces:**
- Consumes: `build_portfolio_overview`, `get_portfolio_store`, and `get_portfolio_observation_store`.
- Produces: mounted provider-free `GET /portfolio/overview` with the JSON contract above and the existing fresh-profile Manual-shell initialization only.

- [ ] **Step 1: Add four RED route tests**

Add imports for `json`, `PortfolioObservationStore`, and the observation dependency. Add these tests:

```python
def test_portfolio_overview_router_mounts_on_real_app():
    from src.api.app import create_app
    paths = {getattr(route, "path", None) for route in create_app().routes}
    assert "/portfolio/overview" in paths


def test_get_portfolio_overview_fresh_profile_is_truthful(tmp_path):
    path = tmp_path / "profile_state.db"
    out = routes.get_portfolio_overview(
        store=PortfolioStore(path),
        observations=PortfolioObservationStore(path),
    )
    assert out["accounts"] == [{
        "id": 1,
        "label": "Manual",
        "broker": "manual",
        "broker_account_id_hash": None,
        "sync_mode": "manual",
        "base_currency": "USD",
        "include_in_total": True,
        "canonical_last_sync_at": None,
        "latest_snapshot": None,
    }]
    assert out["manual_subtotal"]["totals"]["per_currency"] == {}


def test_get_portfolio_overview_never_serializes_raw_broker_id(tmp_path):
    path = tmp_path / "profile_state.db"
    store = PortfolioStore(path)
    store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    out = routes.get_portfolio_overview(
        store=store,
        observations=PortfolioObservationStore(path),
    )
    encoded = json.dumps(out, sort_keys=True)
    assert all("broker_account_id" not in account for account in out["accounts"])
    assert "DU123" not in encoded
    assert "broker_account_id_hash" in out["accounts"][1]


def test_get_portfolio_overview_never_calls_gateway_or_checks_write_permission(
    monkeypatch, tmp_path,
):
    monkeypatch.setattr(
        routes,
        "require_profile_state_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("write gate called")),
    )
    monkeypatch.setattr(
        routes,
        "_read_ibkr_snapshot_or_503",
        lambda: (_ for _ in ()).throw(AssertionError("IBKR read called")),
    )
    path = tmp_path / "profile_state.db"
    out = routes.get_portfolio_overview(
        store=PortfolioStore(path),
        observations=PortfolioObservationStore(path),
    )
    assert out["accounts"][0]["broker"] == "manual"
```

- [ ] **Step 2: Verify RED**

```bash
pytest tests/test_portfolio_routes.py -k portfolio_overview -q
```

Expected: failures because the route handler/path do not exist.

- [ ] **Step 3: Mount the read-only route**

Update imports:

```python
from src.api.dependencies import (
    get_data_provider_store,
    get_portfolio_observation_store,
    get_portfolio_store,
)
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_overview import build_portfolio_overview
```

Place the static route before position/account mutation routes:

```python
@router.get("/overview")
def get_portfolio_overview(
    store: PortfolioStore = Depends(get_portfolio_store),
    observations: PortfolioObservationStore = Depends(get_portfolio_observation_store),
) -> dict[str, Any]:
    return _to_json(build_portfolio_overview(store, observations))
```

No exception wrapper, provider readiness check, permission gate, or capture-service dependency belongs here. The existing Manual shell may be initialized by `list_accounts()`; do not describe that as a new mutation capability or broaden it to broker accounts.

- [ ] **Step 4: Run route/focused backend gates**

```bash
pytest tests/test_portfolio_routes.py tests/test_portfolio_overview.py tests/test_portfolio_observations.py tests/test_portfolio_state.py -q
```

Expected: `81 passed`, exactly `64 + 17` over the grounded focused baseline.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/api/routes/portfolio.py tests/test_portfolio_routes.py
git commit -m "feat: add portfolio overview api"
```

---

### Task 5: Frontend Overview DTO and Presenters

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Create: `apps/arkscope-web/src/PortfolioAccountOverview.tsx`
- Create: `apps/arkscope-web/src/PortfolioAccountOverview.test.tsx`

**Interfaces:**
- Consumes: additive `/portfolio/overview`, `PortfolioTotals`, `DataTable`, `StatusBadge`, and `formatSystemTimestamp`.
- Produces: `PortfolioOverview`, `getPortfolioOverview()`, `PortfolioAccountSummary`, and `PortfolioAccountDetails`.

- [ ] **Step 1: Add ten RED component tests using the house `createRoot` harness**

Create the test file with these exact cases:

```text
renders_every_visible_account_even_without_snapshot
renders_broker_values_and_both_timestamps
labels_daily_total_as_realized_plus_unrealized
does_not_invent_daily_total_when_one_provider_leg_is_missing
renders_manual_subtotal_by_currency_without_overall_net_worth
keeps_manual_subtotal_separate_from_ibkr_net_liquidation
renders_all_latest_snapshot_fields_in_account_details
keeps_account_details_inside_the_data_table_scroll_owner
emits_include_toggle_for_each_account
never_renders_an_unexpected_raw_broker_account_id_property
```

Use `createRoot`, `act`, a local `overview()` fixture, and DOM queries; do not add Testing Library. The representative fixture must contain:

```typescript
const overview = (over: Partial<PortfolioOverview> = {}): PortfolioOverview => ({
  accounts: [{
    id: 1,
    label: "Manual",
    broker: "manual",
    broker_account_id_hash: null,
    sync_mode: "manual",
    base_currency: "USD",
    include_in_total: true,
    canonical_last_sync_at: null,
    latest_snapshot: null,
  }, {
    id: 2,
    label: "IBKR · hash-one",
    broker: "ibkr",
    broker_account_id_hash: "hash-one",
    sync_mode: "ibkr_review",
    base_currency: "USD",
    include_in_total: true,
    canonical_last_sync_at: "2026-07-14T05:01:00+00:00",
    latest_snapshot: {
      capture_run_id: 50,
      as_of_utc: "2026-07-14T05:00:00+00:00",
      as_of_kind: "capture_completed",
      source: "ibkr_gateway",
      base_currency: "USD",
      net_liquidation: 100_000,
      total_cash_value: 10_000,
      settled_cash: 9_000,
      gross_position_value: 90_000,
      buying_power: 25_000,
      available_funds: 20_000,
      initial_margin_requirement: 15_000,
      maintenance_margin_requirement: 12_000,
      daily_realized_pnl: 125,
      daily_unrealized_pnl: -25,
      daily_total_pnl: 100,
    },
  }],
  manual_subtotal: {
    included_account_ids: [1],
    totals: {
      currency_basis: "per_currency",
      per_currency: {
        USD: { position_count: 1, market_value: 500, unrealized_pnl: 25 },
        TWD: { position_count: 1, market_value: 10_000, unrealized_pnl: -500 },
      },
      broker_base: null,
    },
  },
  ...over,
});
```

Pin exact visible labels including `今日損益合計（已實現 + 未實現，ET）`, `Broker 觀察`, `本地持倉核准 / 同步`, `手動帳戶持倉小計`, and `無帳戶價值資料`. Assert `整體淨值` is absent.

- [ ] **Step 2: Verify RED**

```bash
npm test -- --run src/PortfolioAccountOverview.test.tsx
```

Expected: collection/import failure because the DTO and component do not exist.

- [ ] **Step 3: Add the exact frontend API types**

In `api.ts`, after `PortfolioSnapshot`, add:

```typescript
export interface PortfolioAccountValueSnapshot {
  capture_run_id: number;
  as_of_utc: string;
  as_of_kind: "capture_completed" | string;
  source: "ibkr_gateway" | string;
  base_currency: string | null;
  net_liquidation: number | null;
  total_cash_value: number | null;
  settled_cash: number | null;
  gross_position_value: number | null;
  buying_power: number | null;
  available_funds: number | null;
  initial_margin_requirement: number | null;
  maintenance_margin_requirement: number | null;
  daily_realized_pnl: number | null;
  daily_unrealized_pnl: number | null;
  daily_total_pnl: number | null;
}

export interface PortfolioOverviewAccount {
  id: number;
  label: string;
  broker: string;
  broker_account_id_hash: string | null;
  sync_mode: "manual" | "ibkr_review" | "ibkr_auto" | string;
  base_currency: string | null;
  include_in_total: boolean;
  canonical_last_sync_at: string | null;
  latest_snapshot: PortfolioAccountValueSnapshot | null;
}

export interface PortfolioOverview {
  accounts: PortfolioOverviewAccount[];
  manual_subtotal: {
    included_account_ids: number[];
    totals: PortfolioTotals;
  };
}

export function getPortfolioOverview(): Promise<PortfolioOverview> {
  return getJSON<PortfolioOverview>("/portfolio/overview");
}
```

Do not add `broker_account_id` to any new interface.

- [ ] **Step 4: Implement the summary and detail presenters**

Create `PortfolioAccountOverview.tsx` with this complete shape (formatting may be split into private functions, but field membership and labels are fixed):

```tsx
import type { ReactNode } from "react";

import type {
  PortfolioAccountValueSnapshot,
  PortfolioOverview,
  PortfolioOverviewAccount,
  PortfolioTotals,
} from "./api";
import { formatSystemTimestamp } from "./timeDisplay";
import { DataTable, StatusBadge, type DataTableColumn } from "./ui";


export function PortfolioAccountSummary({
  overview,
  busyAccountId,
  onToggleAggregate,
}: {
  overview: PortfolioOverview;
  busyAccountId: number | null;
  onToggleAggregate: (accountId: number, include: boolean) => void;
}) {
  const manualRows = currencyRows(overview.manual_subtotal.totals);
  return (
    <section className="ui-section-band portfolio-account-summary" aria-label="帳戶總覽">
      <div className="ui-section-head">
        <h2>帳戶總覽</h2>
      </div>
      {overview.accounts.map((account) => {
        const snapshot = account.latest_snapshot;
        const currency = snapshot?.base_currency ?? account.base_currency;
        return (
          <article className="portfolio-account-row" key={account.id}>
            <div className="ui-section-head">
              <div>
                <h3>{account.label}</h3>
                <span className="muted tiny">
                  {account.broker === "manual" ? "手動帳戶" : account.sync_mode}
                </span>
              </div>
              {account.broker === "manual" ? (
                <span className="muted tiny">無帳戶價值資料</span>
              ) : snapshot ? (
                <StatusBadge state="ready" label="已取得帳戶快照" />
              ) : (
                <StatusBadge state="empty" label="尚無帳戶快照" />
              )}
            </div>

            {account.broker !== "manual" ? (
              <div className="portfolio-account-values">
                <Metric label="Net Liquidation">
                  {formatAmount(snapshot?.net_liquidation, currency)}
                </Metric>
                <Metric label="Total Cash">
                  {formatAmount(snapshot?.total_cash_value, currency)}
                </Metric>
                <Metric label="Buying Power">
                  {formatAmount(snapshot?.buying_power, currency)}
                </Metric>
                <Metric label="今日已實現損益（ET）">
                  {formatAmount(snapshot?.daily_realized_pnl, currency)}
                </Metric>
                <Metric label="今日未實現損益（ET）">
                  {formatAmount(snapshot?.daily_unrealized_pnl, currency)}
                </Metric>
                <Metric label="今日損益合計（已實現 + 未實現，ET）">
                  {formatAmount(snapshot?.daily_total_pnl, currency)}
                </Metric>
              </div>
            ) : null}

            <div className="portfolio-account-times">
              <span className="muted tiny">
                Broker 觀察：{formatSystemTimestamp(snapshot?.as_of_utc)}
              </span>
              <span className="muted tiny">
                本地持倉核准 / 同步：{formatSystemTimestamp(account.canonical_last_sync_at)}
              </span>
            </div>
            <label className="muted tiny">
              <input
                type="checkbox"
                aria-label={`${account.label} 納入總計`}
                checked={account.include_in_total}
                disabled={busyAccountId === account.id}
                onChange={(event) => onToggleAggregate(account.id, event.currentTarget.checked)}
              />
              納入總計
            </label>
          </article>
        );
      })}

      <section className="portfolio-manual-subtotal" aria-label="手動帳戶持倉小計">
        <div className="ui-section-head">
          <div>
            <h3>手動帳戶持倉小計</h3>
            <span className="muted tiny">
              只包含已勾選且未關閉的手動帳戶持倉；不與 IBKR Net Liquidation 相加。
            </span>
          </div>
        </div>
        {manualRows.length === 0 ? (
          <p className="muted">尚無納入總計的手動持倉。</p>
        ) : (
          <div className="portfolio-account-values">
            {manualRows.map(([currency, row]) => (
              <div className="ui-metric" key={currency}>
                <span className="ui-metric-label">{currency}</span>
                <strong>{formatAmount(row.market_value, currency)}</strong>
                <span className="muted tiny">
                  {row.position_count} 筆 · 未實現 {formatAmount(row.unrealized_pnl, currency)}
                </span>
              </div>
            ))}
            {overview.manual_subtotal.totals.broker_base ? (
              <div className="ui-metric">
                <span className="ui-metric-label">手動帳戶 broker-base 小計</span>
                <strong>
                  {formatAmount(
                    overview.manual_subtotal.totals.broker_base.market_value,
                    null,
                  )}
                </strong>
                <span className="muted tiny">
                  未實現 {formatAmount(
                    overview.manual_subtotal.totals.broker_base.unrealized_pnl,
                    null,
                  )}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </section>
    </section>
  );
}


export function PortfolioAccountDetails({ overview }: { overview: PortfolioOverview }) {
  const columns: DataTableColumn<PortfolioOverviewAccount>[] = [
    {
      id: "account",
      header: "帳戶",
      render: (account) => (
        <>
          <strong>{account.label}</strong>
          <br />
          <span className="muted tiny">{account.broker}</span>
        </>
      ),
    },
    {
      id: "run",
      header: "Capture Run",
      align: "right",
      render: (account) => account.latest_snapshot?.capture_run_id ?? "—",
    },
    {
      id: "currency",
      header: "Base Currency",
      render: (account) => account.latest_snapshot?.base_currency ?? account.base_currency ?? "—",
    },
    ...moneyColumns,
    {
      id: "source",
      header: "來源",
      render: (account) => account.latest_snapshot
        ? `${account.latest_snapshot.source} · ${account.latest_snapshot.as_of_kind}`
        : account.broker === "manual" ? "無帳戶價值資料" : "尚無帳戶快照",
    },
    {
      id: "broker-time",
      header: "Broker 觀察",
      render: (account) => formatSystemTimestamp(account.latest_snapshot?.as_of_utc),
    },
    {
      id: "canonical-time",
      header: "本地持倉核准 / 同步",
      render: (account) => formatSystemTimestamp(account.canonical_last_sync_at),
    },
  ];
  return (
    <section className="ui-section-band portfolio-account-details">
      <div className="ui-section-head">
        <div>
          <h2>帳戶明細</h2>
          <p className="muted">
            最新觀察值，不是績效曲線；空值表示 provider 未回報。
          </p>
        </div>
      </div>
      <DataTable<PortfolioOverviewAccount>
        ariaLabel="帳戶最新快照明細"
        rows={overview.accounts}
        columns={columns}
        rowKey={(account) => account.id}
        rowLabel={(account) => account.label}
        emptyText="尚無帳戶"
      />
    </section>
  );
}


type MoneyField = keyof Pick<
  PortfolioAccountValueSnapshot,
  | "net_liquidation"
  | "total_cash_value"
  | "settled_cash"
  | "gross_position_value"
  | "buying_power"
  | "available_funds"
  | "initial_margin_requirement"
  | "maintenance_margin_requirement"
  | "daily_realized_pnl"
  | "daily_unrealized_pnl"
  | "daily_total_pnl"
>;

const moneyColumnSpecs: Array<[string, string, MoneyField]> = [
  ["net-liquidation", "Net Liquidation", "net_liquidation"],
  ["total-cash", "Total Cash", "total_cash_value"],
  ["settled-cash", "Settled Cash", "settled_cash"],
  ["gross-position", "Gross Position Value", "gross_position_value"],
  ["buying-power", "Buying Power", "buying_power"],
  ["available-funds", "Available Funds", "available_funds"],
  ["initial-margin", "Initial Margin", "initial_margin_requirement"],
  ["maintenance-margin", "Maintenance Margin", "maintenance_margin_requirement"],
  ["daily-realized", "今日已實現（ET）", "daily_realized_pnl"],
  ["daily-unrealized", "今日未實現（ET）", "daily_unrealized_pnl"],
  ["daily-total", "今日合計（已實現 + 未實現，ET）", "daily_total_pnl"],
];

const moneyColumns: DataTableColumn<PortfolioOverviewAccount>[] = moneyColumnSpecs
  .map(([id, header, field]) => ({
  id,
  header,
  align: "right" as const,
  render: (account: PortfolioOverviewAccount) => {
    const snapshot = account.latest_snapshot;
    const currency = snapshot?.base_currency ?? account.base_currency;
    return formatAmount(snapshot?.[field], currency);
  },
}));


function Metric({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="ui-metric">
      <span className="ui-metric-label">{label}</span>
      <strong>{children}</strong>
    </div>
  );
}


function formatAmount(value: number | null | undefined, currency: string | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  if (!currency) return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value)} ${currency}`;
  }
}


function currencyRows(totals: PortfolioTotals) {
  return Object.entries(totals.per_currency)
    .sort(([left], [right]) => left.localeCompare(right));
}
```

The summary must not recompute `daily_total_pnl`; it displays the backend field. The details table includes every normalized latest-snapshot field plus the canonical timestamp. `broker_base`, when present, remains explicitly scoped to the manual subtotal and is never merged with IBKR values.

- [ ] **Step 5: Run component tests and typecheck**

```bash
npm test -- --run src/PortfolioAccountOverview.test.tsx
npm run typecheck
```

Expected: `10 passed`; typecheck passes.

- [ ] **Step 6: Commit Task 5**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/PortfolioAccountOverview.tsx apps/arkscope-web/src/PortfolioAccountOverview.test.tsx
git commit -m "feat: render portfolio account overview"
```

---

### Task 6: Holdings Tabs, Degraded Overview, and Responsive Ownership

**Files:**
- Modify: `apps/arkscope-web/src/Holdings.tsx`
- Modify: `apps/arkscope-web/src/Holdings.test.tsx`
- Modify: `apps/arkscope-web/src/PortfolioCaptureCss.test.ts`
- Modify: `apps/arkscope-web/src/styles.css`

**Interfaces:**
- Consumes: `getPortfolioOverview`, `PortfolioAccountSummary`, `PortfolioAccountDetails`, and existing `PortfolioCapturePanel`.
- Produces: account summary above three completed tabs, resilient dual fetch, and stable horizontal-scroll ownership.

- [ ] **Step 1: Extend the house fetch harness and add six RED integration tests**

Add `PortfolioOverview` to `PortfolioApiResponse`, provide a default `overview()` fixture, and route `GET /portfolio/overview` to it rather than returning `PortfolioSnapshot` accidentally.

Add these six tests:

```text
keeps_canonical_positions_usable_when_the_additive_overview_fails
keeps_account_summary_visible_above_every_completed_tab
switches_between_holdings_account_details_and_sync_records
does_not_render_an_unfinished_activity_tab_or_placeholder
mounts_capture_polling_only_while_sync_records_is_active
supports_arrow_home_and_end_keyboard_navigation_between_tabs
```

Evolve, without deleting, the existing capture/apply tests:

- `holdings_renders_one_capture_control_surface_and_no_legacy_live_sync_buttons` first clicks `同步紀錄`, then asserts one capture surface.
- `clears captured review_and_shows_persisted_positions_after_applying` first enters `同步紀錄`, applies, and asserts both `/portfolio` and `/portfolio/overview` were fetched again before returning to `持倉`.
- The account aggregate-toggle test continues to assert the exact PATCH body, now through `PortfolioAccountSummary`.
- In that same aggregate-toggle test, assert `Currency basis` is absent and the fixture's Manual account has exactly one `Manual 納入總計` checkbox. This is a 1:1 strengthening of the existing test, not a new collected test.
- `renders accounts, positions, and currency basis` becomes `renders account-labelled positions and filters by account`: seed two accounts with one position each, assert the Account column uses overview-safe labels, select one account, and assert only that account's row remains. This is a 1:1 intent-strengthening rename, not a new collected test.

For degraded loading, return a rejected overview promise and a successful snapshot. Assert `NVDA` and row actions still render, while a scoped alert says `帳戶總覽無法載入；持倉仍可使用`.
In the same test, assert the first two GET calls are ordered `/portfolio` then `/portfolio/overview`; this pins the fresh-profile Manual-shell race guard without adding another collected test.

- [ ] **Step 2: Add two RED CSS contract assertions**

Append to `PortfolioCaptureCss.test.ts`:

```typescript
it("keeps_account_detail_financial_columns_inside_one_scroll_owner", () => {
  expect(rule(".portfolio-account-details .ui-data-table")).toMatch(/min-width:\s*1800px/);
  expect(rule('.portfolio-account-details .ui-data-table [data-align="right"]')).toMatch(
    /white-space:\s*nowrap/,
  );
});

it("lets_the_completed_portfolio_tabs_wrap_without_a_new_breakpoint", () => {
  expect(rule(".portfolio-view-tabs")).toMatch(/flex-wrap:\s*wrap/);
  expect(rule(".portfolio-view-tab")).toMatch(/min-height:\s*var\(--control-height-default\)/);
});
```

- [ ] **Step 3: Verify the intended RED**

```bash
npm test -- --run src/Holdings.test.tsx src/PortfolioCaptureCss.test.ts
```

Expected: failures for missing tabs, independent overview state, and CSS selectors; existing position behavior remains green after harness routing is corrected.

- [ ] **Step 4: Wire independent authority/overview loading**

Add state and imports:

```typescript
type PortfolioView = "holdings" | "account_details" | "sync_records";

const [overview, setOverview] = useState<PortfolioOverview | null>(null);
const [overviewErr, setOverviewErr] = useState<string | null>(null);
const [activeView, setActiveView] = useState<PortfolioView>("holdings");
const [positionAccountId, setPositionAccountId] = useState<number | "all">("all");
```

Replace `load` with a sequential, failure-isolated boundary:

```typescript
const load = useCallback(async () => {
  setLoading(true);
  setErr(null);
  setOverviewErr(null);
  setOverview(null);
  try {
    setSnapshot(await getPortfolio(includeClosed));
    try {
      setOverview(await getPortfolioOverview());
    } catch (overviewError) {
      setOverviewErr(overviewError instanceof Error
        ? overviewError.message
        : String(overviewError));
    }
  } catch (portfolioError) {
    setErr(portfolioError instanceof Error
      ? portfolioError.message
      : String(portfolioError));
  } finally {
    setLoading(false);
  }
}, [includeClosed]);
```

The overview alert must show a user action, not the raw exception. Keep raw detail out of normal mode:

```tsx
{overviewErr ? (
  <InlineAlert state="partial" title="帳戶總覽無法載入；持倉仍可使用">
    請重新整理；若剛更新版本，請重啟應用程式後再試。
  </InlineAlert>
) : null}
```

- [ ] **Step 5: Render the completed tab contract**

Define a constant in final-order-relative form:

```typescript
const PORTFOLIO_VIEWS: Array<{ id: PortfolioView; label: string }> = [
  { id: "holdings", label: "持倉" },
  // Slice 3 inserts the activity view here.
  { id: "account_details", label: "帳戶明細" },
  { id: "sync_records", label: "同步紀錄" },
];
```

Import `type KeyboardEvent as ReactKeyboardEvent`, create refs for the three completed controls, and use this exact keyboard boundary:

```tsx
const tabRefs = useRef<Record<PortfolioView, HTMLButtonElement | null>>({
  holdings: null,
  account_details: null,
  sync_records: null,
});

function onTabKeyDown(
  event: ReactKeyboardEvent<HTMLButtonElement>,
  current: PortfolioView,
) {
  const currentIndex = PORTFOLIO_VIEWS.findIndex((view) => view.id === current);
  let nextIndex: number | null = null;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % PORTFOLIO_VIEWS.length;
  if (event.key === "ArrowLeft") {
    nextIndex = (currentIndex - 1 + PORTFOLIO_VIEWS.length) % PORTFOLIO_VIEWS.length;
  }
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = PORTFOLIO_VIEWS.length - 1;
  if (nextIndex == null) return;
  event.preventDefault();
  const next = PORTFOLIO_VIEWS[nextIndex].id;
  setActiveView(next);
  tabRefs.current[next]?.focus();
}
```

Render `PortfolioAccountSummary` immediately below errors and before the tablist:

```tsx
{overview ? (
  <PortfolioAccountSummary
    overview={overview}
    busyAccountId={busy?.startsWith("account-") ? Number(busy.slice(8)) : null}
    onToggleAggregate={(accountId, include) => {
      void onToggleAggregate(accountId, include);
    }}
  />
) : null}

<div className="portfolio-view-tabs" role="tablist" aria-label="持倉檢視">
  {PORTFOLIO_VIEWS.map((view) => (
    <button
      key={view.id}
      ref={(node) => { tabRefs.current[view.id] = node; }}
      id={`portfolio-tab-${view.id}`}
      className="portfolio-view-tab"
      type="button"
      role="tab"
      tabIndex={activeView === view.id ? 0 : -1}
      aria-selected={activeView === view.id}
      aria-controls={`portfolio-panel-${view.id}`}
      onClick={() => setActiveView(view.id)}
      onKeyDown={(event) => onTabKeyDown(event, view.id)}
    >
      {view.label}
    </button>
  ))}
</div>
```

Before wrapping the three completed panels, delete the existing Accounts `ui-section-band` in its
entirety: the per-account `ui-status-grid` cards, their old aggregate toggles, and the mixed-account
`Currency basis` metric. Remove the now-unused `currencySummary()` helper as part of the same
replacement. No legacy Accounts summary may remain above, below, or outside the tab hierarchy;
`PortfolioAccountSummary` is the sole account-summary and aggregate-toggle surface.

Each panel uses `role="tabpanel"`, `aria-labelledby`, and is mounted only when active. Wrap the existing contiguous manual-add, Positions, Options, editor, and ConfirmDialog JSX in `portfolio-panel-holdings` without changing those nodes. The two new panel wrappers are exact:

```tsx
{activeView === "account_details" ? (
  <div
    id="portfolio-panel-account_details"
    role="tabpanel"
    aria-labelledby="portfolio-tab-account_details"
  >
    {overview ? <PortfolioAccountDetails overview={overview} /> : null}
  </div>
) : null}
{activeView === "sync_records" ? (
  <div
    id="portfolio-panel-sync_records"
    role="tabpanel"
    aria-labelledby="portfolio-tab-sync_records"
  >
    <PortfolioCapturePanel onPortfolioChanged={load} />
  </div>
) : null}
```

Move existing sections without changing their bodies:

- `持倉`: manual add, standard positions, options, editor, close dialog.
- `帳戶明細`: `<PortfolioAccountDetails overview={overview} />`; if no overview, show the scoped loading/empty state, not fake values.
- `同步紀錄`: `<PortfolioCapturePanel onPortfolioChanged={load} />`.

Do not render the word/button `活動` anywhere in production Slice 2 DOM.

Build account labels from the redacted overview first, with the shipped authority label only as old-sidecar fallback, and filter before splitting standard/options:

```typescript
const accountLabels = useMemo(() => {
  const safe = new Map((overview?.accounts ?? []).map((account) => [account.id, account.label]));
  return new Map(
    (snapshot?.accounts ?? []).map((account) => [
      account.id,
      safe.get(account.id) ?? account.label,
    ]),
  );
}, [overview, snapshot]);

const filteredPositions = positionAccountId === "all"
  ? positions
  : positions.filter((position) => position.account_id === positionAccountId);
const standardPositions = filteredPositions.filter(
  (position) => position.asset_class !== "option",
);
const optionPositions = filteredPositions.filter(
  (position) => position.asset_class === "option",
);
```

Add this control beside the closed-row filter:

```tsx
<label className="muted tiny">
  <span>帳戶</span>
  <select
    aria-label="持倉帳戶篩選"
    value={positionAccountId}
    onChange={(event) => {
      setPositionAccountId(event.currentTarget.value === "all"
        ? "all"
        : Number(event.currentTarget.value));
    }}
  >
    <option value="all">全部帳戶</option>
    {accounts.map((account) => (
      <option key={account.id} value={account.id}>
        {accountLabels.get(account.id) ?? account.label}
      </option>
    ))}
  </select>
</label>
```

Pass `accountLabels` into both `PositionsTable` calls and prepend this column:

```typescript
{
  id: "account",
  header: "Account",
  render: (position) => accountLabels.get(position.account_id) ?? `#${position.account_id}`,
},
```

If a refresh removes the selected account, reset it rather than leaving an empty table selected against a missing option:

```typescript
useEffect(() => {
  if (positionAccountId !== "all" && !accounts.some((account) => account.id === positionAccountId)) {
    setPositionAccountId("all");
  }
}, [accounts, positionAccountId]);
```

- [ ] **Step 6: Add only feature-scoped CSS**

```css
.portfolio-view-tabs {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border);
}
.portfolio-view-tab {
  min-height: var(--control-height-default);
  padding: 5px 10px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--muted);
  font: inherit;
  cursor: pointer;
}
.portfolio-view-tab[aria-selected="true"] {
  border-bottom-color: var(--accent);
  color: var(--fg);
}
.portfolio-view-tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.portfolio-account-summary {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
}
.portfolio-account-row {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3) 0;
  border-top: 1px solid var(--border);
}
.portfolio-account-row h3,
.portfolio-manual-subtotal h3 {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0;
}
.portfolio-account-values {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: var(--space-2);
}
.portfolio-account-times {
  display: flex;
  gap: var(--space-2) var(--space-4);
  flex-wrap: wrap;
  min-width: 0;
}
.portfolio-manual-subtotal {
  display: grid;
  gap: var(--space-2);
  min-width: 0;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border);
}
.portfolio-account-details .ui-data-table { min-width: 1800px; }
.portfolio-account-details .ui-data-table [data-align="right"] {
  white-space: nowrap;
  overflow-wrap: normal;
}
```

Do not add a new `@media`; the grid, wrapping tablist, and existing `DataTable` scroll owner cover the required widths.

- [ ] **Step 7: Run focused and full frontend gates**

```bash
npm test -- --run src/PortfolioAccountOverview.test.tsx src/Holdings.test.tsx src/PortfolioCapturePanel.test.tsx src/PortfolioCaptureCss.test.ts
npm test
npm run typecheck
npm run build
```

Expected full result: `44 files / 412 tests`, exactly one new file and `+18/-0` tests over `43 / 394`; typecheck/build pass with only the existing chunk-size warning.

- [ ] **Step 8: Commit Task 6**

```bash
git add apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx apps/arkscope-web/src/PortfolioCaptureCss.test.ts apps/arkscope-web/src/styles.css
git commit -m "feat: add holdings account overview tabs"
```

---

### Task 7: Boundaries, Fresh-Profile/Responsive/Live Gates, and Review Handoff

**Files:**
- Modify after evidence exists: `docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md`
- Must not modify product behavior in this task.

**Interfaces:**
- Consumes: final Tasks 1-6 implementation.
- Produces: review-ready evidence only. No merge or LIVE claim.

- [ ] **Step 1: Run the exact focused backend ledger**

```bash
pytest tests/test_portfolio_observations.py tests/test_portfolio_state.py tests/test_portfolio_overview.py tests/test_portfolio_routes.py -q
```

Expected: `81 passed`, exactly `64 + 17`.

- [ ] **Step 2: Run fresh-profile migration and real-app mount checks**

```bash
pytest tests/test_portfolio_observations.py::test_fresh_schema_creates_capture_tables_with_no_cascade_foreign_keys tests/test_portfolio_routes.py::test_portfolio_overview_router_mounts_on_real_app tests/test_portfolio_routes.py::test_get_portfolio_overview_fresh_profile_is_truthful -q
```

Expected: `3 passed`; no migration script, destructive rewrite, or default raw account appears.

- [ ] **Step 3: Run static boundary ratchets**

All commands must return zero matches unless an exact positive assertion is stated:

```bash
rg -n "placeOrder|cancelOrder|reqGlobalCancel|modifyOrder|exerciseOption|exerciseOptions" src/portfolio_overview.py src/api/routes/portfolio.py
rg -n "psycopg|postgres|PG_DSN|DATABASE_URL" src/portfolio_overview.py src/api/routes/portfolio.py
rg -n "get_portfolio_holdings|ToolRegistry|research|prompt" src/portfolio_overview.py
rg -n "window\.confirm|@media" apps/arkscope-web/src/PortfolioAccountOverview.tsx apps/arkscope-web/src/Holdings.tsx
rg -n "活動" apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/PortfolioAccountOverview.tsx
```

The last command is allowed exactly one source comment documenting Slice 3 insertion and zero rendered string literals; prefer replacing the comment with `activity` in English if the gate would otherwise be ambiguous.

Prove out-of-scope owners stayed byte-identical:

```bash
git diff --exit-code a0daf69 -- src/portfolio_capture.py src/portfolio_capture_ibkr.py src/portfolio_capture_scheduler.py src/tools apps/arkscope-web/src/Settings.tsx
```

- [ ] **Step 4: Run full frontend and no-PG gates**

```bash
cd apps/arkscope-web
npm test
npm run typecheck
npm run build
cd ../..
python src/smoke/pg_unreachable_e2e.py
```

Expected: `44 files / 412 tests`; typecheck/build pass; smoke prints `ok: true` and `pg_attempts: []`.

- [ ] **Step 5: Run visual/interaction verification at all required widths**

Start a scheduler-disabled sidecar against a disposable profile DB and Vite on an unused port:

```bash
ARKSCOPE_DISABLE_SCHEDULER=1 ARKSCOPE_PROFILE_DB=/tmp/arkscope-p11-s2-visual.db python -m src.api
```

```bash
cd apps/arkscope-web
ARKSCOPE_WEB_DEV_PORT=8431 npm run dev -- --host 127.0.0.1
```

Use captured/fake local snapshot data containing two IBKR accounts in different base currencies, one IBKR account with no snapshot, and USD/TWD manual subtotal rows. Inspect `1440x900`, `1024x768`, `961x768`, `959x768`, and `390x844`; store disposable screenshots under `/tmp`. At every width prove:

1. all accounts remain visible;
2. no fake IBKR/overall total appears;
3. both timestamps are readable;
4. detail financial columns scroll within the table owner and never create page-level horizontal overflow;
5. tab labels do not overlap;
6. summary remains above each tab;
7. capture controls exist only under `同步紀錄`; and
8. no `活動` placeholder appears.

- [ ] **Step 6: Run one-sidecar live Gateway gate**

With only the normal desktop/branch sidecar using the real profile DB and Gateway:

1. trigger one manual capture through the shipped `同步紀錄` control;
2. call `GET /portfolio/overview` and verify every visible IBKR account has either one latest snapshot or an explicit null, with no raw account id in JSON/log/DOM;
3. compare broker observation time with canonical sync/approval time and confirm they are independently sourced;
4. verify all provider-present NLV/cash/buying-power/margin/P&L fields render and provider-absent Settled Cash stays `—`;
5. verify the manual subtotal is separate and no overall net-worth line exists;
6. switch all three completed tabs and apply a review diff if one naturally exists; confirm apply refreshes authority and overview without a second live Gateway read; and
7. record multi-account/mixed-currency behavior as fake-backed if the user's live Gateway exposes only one account. Do not manufacture a second broker account or transaction.

- [ ] **Step 7: Run canonical full base/head A/B**

Use clean virgin archives of base `a0daf69` and final code head under identical environment isolation. Run sequential single-process full pytest. Acceptance:

- bidirectional pre-existing failure-set diff is empty;
- skip/warning/error families are identical;
- full collection is `4258 -> 4275`, exactly `+17/-0`;
- passed delta is exactly `+17`; and
- frontend collection is `43/394 -> 44/412`, exactly `+1 file / +18 tests`.

If this environment reproduces the known `TestClient`/lifespan hang, record it without claiming PASS and stop for reviewer canonical A/B. Do not replace the authority with a weaker partial run.

- [ ] **Step 8: Reconcile the implementation ledger and stop review-ready**

Add an `Implementation Ledger` beneath the plan header containing:

- branch/base/head commits;
- each task's RED reason and GREEN command;
- focused/full test counts and exact collect delta;
- static gate outputs;
- fresh-profile, responsive screenshots, and live evidence;
- naturally unverified live conditions; and
- every deliberate deviation from this reviewed plan.

Then change the plan status to `IMPLEMENTED FOR REVIEW`; change the spec/map only to `SLICE 2 IMPLEMENTED FOR REVIEW` (not LIVE), commit the docs, and stop:

```bash
git add docs/superpowers/plans/2026-07-14-portfolio-1-1-slice-2-account-overview.md docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark portfolio overview review-ready"
```

---

## Exact Test Ledger

### Backend

| File | Baseline | Added | Final |
| --- | ---: | ---: | ---: |
| `tests/test_portfolio_observations.py` | 18 | 3 | 21 |
| `tests/test_portfolio_state.py` | 26 | 3 | 29 |
| `tests/test_portfolio_overview.py` | 0 | 7 | 7 |
| `tests/test_portfolio_routes.py` | 20 | 4 | 24 |
| **Focused total** | **64** | **17** | **81** |
| **Full collection** | **4258** | **17** | **4275** |

### Frontend

| Owner | Added tests |
| --- | ---: |
| `PortfolioAccountOverview.test.tsx` | 10 |
| `Holdings.test.tsx` | 6 |
| `PortfolioCaptureCss.test.ts` | 2 |
| **Total** | **18** |

Full frontend contract: `43 files / 394 tests -> 44 files / 412 tests`; no test removal or renamed-away intent.

## Stop-Loss Conditions

Stop and report rather than widening scope if any of these occurs:

1. Latest account values require a fresh Gateway call instead of reading Slice 1 observations.
2. Manual subtotal cannot reuse the existing `_totals` algorithm without changing shipped totals semantics.
3. The projection would need to expose raw broker account ids to identify rows.
4. Account values require reconstructing historical performance, cash flows, or positions from executions.
5. A useful account overview requires activity/fill/annotation work owned by Slice 3.
6. The old `/portfolio` response must be changed incompatibly rather than adding `/portfolio/overview`.
7. An account-value write path beyond the existing fresh-profile Manual shell, background scheduler, Data Sources control, tool/prompt registration, or order API becomes necessary.
8. A second shell breakpoint, new generic UI primitive, or global layout rewrite becomes necessary.
9. Live Gateway returns a materially different account-snapshot shape not represented by the normalized Slice 1 schema.
10. Any existing model/research/tool/capture behavior changes beyond the explicitly listed overview read and UI relocation.

## Reviewer Focus

1. `latest_account_snapshots` is SQL-bounded and deterministic, not an unbounded read-all-then-first loop.
2. Canonical sync time includes closed rows and does not use account `updated_at` as a misleading substitute.
3. Manual subtotal uses exactly included manual accounts and existing `_totals`; no IBKR value or position can enter it.
4. Daily total never treats a missing provider leg as zero.
5. Legacy raw-id labels are redacted before the additive API/DOM while user-owned safe labels survive unchanged.
6. Overview failure does not take canonical positions or row actions down.
7. Account summary is persistent above tabs and fully replaces the old Accounts/Currency-basis block; every account has exactly one aggregate toggle; canonical positions identify/filter accounts with safe labels; capture polling is mounted only in `同步紀錄`; no unfinished activity control is rendered.
8. Account details expose every normalized latest-snapshot field and both timestamps without page overflow.
9. Optional IBKR aggregation, performance claims, and Slice 3 activity have not leaked into the implementation.
10. Backend `+17/-0`, frontend `+18/-0`, no-PG, privacy/order/static boundaries, responsive matrix, and one-sidecar live evidence all reconcile exactly before merge consideration.
