# Portfolio 1.1 Slice 1 Capture Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: REVIEW-CLEARED — IMPLEMENTATION NOT STARTED, 2026-07-13.**

**Goal:** Start preserving truthful, non-retroactive IBKR account, position, execution, commission, correction, and manual-adjustment facts while retaining the shipped Holdings tables as current-state authority.

**Architecture:** A new append-only `PortfolioObservationStore` shares `profile_state.db` with `PortfolioStore` but owns broker observations and capture-run state. One read-only `PortfolioCaptureService` serializes startup, scheduled, and manual Gateway reads, commits valid observation legs before any separately authorized canonical position update, and exposes a Holdings-owned status/control API; the existing immediate `/portfolio/ibkr/*` routes remain compatible but are no longer the primary UI workflow. The scheduler is a separate lifespan task rather than a Data Sources source, so there is one Portfolio control surface and no duplicate schedule row.

**Tech Stack:** Python 3.11+, SQLite/WAL, FastAPI/Pydantic, `ib_insync` through the existing worker-loop-safe `IBKRDataSource`, React 18, TypeScript 5.5, Vite/Vitest, existing P2.8 UI primitives.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md` is approved and wins over this plan on conflict.
- Existing `portfolio_accounts`, `portfolio_positions`, and `portfolio_position_notes` remain canonical current-state authority; observations never rebuild them.
- Capture begins at feature activation. No backfill, Flex import, performance/TWR claim, tax-lot engine, cash-flow inference, or pre-activation reconstruction belongs in Slice 1.
- Capture cadence is persisted independently: default 15 minutes, accepted range 5-1440, startup catch-up, scheduled runs, and manual runs.
- A configured provider with no explicit settings row means periodic capture is enabled; a missing provider means dormant/blocked with zero IBKR calls.
- Every accepted run uses `IBKRDataSource(readonly=True, client_id=ibkr_client_id_for("portfolio_capture"))`; `portfolio_capture=+70`, `holdings=+60`, and the app-managed base must be 0-29.
- Capture must acquire a dedicated cross-process `portfolio_capture.lock` for
  capture ownership and the shared `ibkr_gateway_lock` for all-IBKR
  serialization; it must not reuse an order/trading client identity.
- `profile_state_write` is checked before any IBKR call. A denied check returns an ephemeral blocked result and creates no row.
- Network reads complete before a short SQLite transaction begins. No DB transaction remains open while waiting on Gateway I/O.
- Account summary, executions/commissions, and positions/portfolio are independent legs. A complete empty position set is not the same as a failed or ambiguous read.
- Observation commit precedes canonical mutation. Observation failure prevents canonical mutation; later canonical failure leaves observations intact and makes the run partial.
- `ibkr_auto` may apply only a complete position leg; `ibkr_review` produces a read-derived preview; `manual` never receives IBKR position mutation.
- Manual position create, financial update, and close must commit their field-level adjustment journal in the same transaction. Notes/thesis/tags alone are not financial activity.
- Stored numeric values must be finite. Blank, parse failure, `NaN`, and positive/negative infinity never become zero.
- All persisted times are UTC. Broker-day gap classification uses `America/New_York`.
- Observation foreign keys are `RESTRICT`/`NO ACTION`, never `CASCADE`; account hard delete is blocked while observations exist.
- Raw broker account ids remain inside the local broker/store boundary. New API DTOs, normal UI, logs, tests, traces, and agent payloads expose local account id, label, and hash only.
- Existing `get_portfolio_holdings` behavior and tool/agent registries remain byte-identical. Slice 1 adds no tool, prompt input, report evidence, or research hydration path.
- Capture ownership must contain zero references to `placeOrder`, `cancelOrder`, `reqGlobalCancel`, order modification methods, `exerciseOption`, or `exerciseOptions`.
- Settings -> Data Sources receives no Portfolio capture row or mutation control. Holdings is the only schedule owner.
- `portfolio_activity_annotations` is deliberately deferred to Slice 3, its first consumer. Do not create an unused table or write API in Slice 1.
- Account overview and rich activity UI remain Slice 2/3. Slice 1 renders only configuration, current/recent run truth, leg outcomes, and the latest derived review diff.
- Spec Section 14.3 is split by its owning consumer: Slice 1 proves the single Holdings schedule owner plus responsive run/review controls; Slice 2 owns every-account visibility, currency-safe/manual subtotals, dual timestamps, and labeled daily P&L; Slice 3 owns fill grouping, unknown-outcome labels, gap markers, and the collapsible activity context panel. Deferred UI clauses are not silently claimed by this plan.
- The existing immediate `/portfolio/ibkr/preview` and `/portfolio/ibkr/apply` API routes remain mounted for compatibility. The new Holdings path uses capture-run observations and must not silently call Gateway again during review/apply.
- One deliberate compatibility-route repair is in scope: a reappearing archived
  IBKR account remains archived and retains user-owned account fields. Legacy
  apply must no longer mistake that account for a new one and silently
  unarchive/reset it; a direct `tests/test_portfolio_ibkr.py` regression pins
  this exception while every other legacy preview/apply contract remains
  unchanged.
- No PostgreSQL import, connection, mirror, or fallback is permitted.
- Implementation stops review-ready. Merge, docs LIVE status, worktree cleanup, and Slice 2 are separate user decisions.

---

## Locked File and Interface Map

| File | Responsibility |
| --- | --- |
| `src/portfolio_capture_types.py` | Immutable capture DTOs, state literals, finite normalization, correction identity, and commission hashing shared by reader/store/service. |
| `src/portfolio_observations.py` | Observation schema, append-only store, settings/runs, account-shell mapping, idempotent inserts, reconciliation, and read projections. |
| `src/portfolio_capture_ibkr.py` | One-connection IBKR adapter. It parses only approved fields and reports independent leg completeness. |
| `src/portfolio_capture.py` | Permission/provider/concurrency orchestration, observation-before-authority ordering, review/apply projection, and in-process due time. |
| `src/portfolio_capture_scheduler.py` | Small async lifespan loop that asks the service to run startup/scheduled work. It has no Data Sources registration. |
| `src/portfolio_state.py` | Existing canonical state plus transactionally inseparable manual financial journals. |
| `src/api/routes/portfolio_capture.py` | Additive run/config/status/review endpoints with redacted DTOs. |
| `src/api/dependencies.py`, `src/api/app.py` | Singleton store/service and lifespan task wiring. |
| `apps/arkscope-web/src/PortfolioCapturePanel.tsx` | Minimum Holdings-owned control/status/review surface. |

### Public Python interfaces

The implementation must use these names and signatures so tasks do not invent
parallel seams. Bodies and exact algorithms are specified in their owning task.

| Owner | Binding signature |
| --- | --- |
| `PortfolioObservationStore` | `__init__(path: str | Path) -> None` |
|  | `get_stored_settings() -> CaptureSettings | None` |
|  | `set_settings(*, enabled: bool, interval_minutes: int) -> CaptureSettings` |
|  | `create_run(*, trigger: CaptureTrigger, effective_client_id: int) -> CaptureRun` |
|  | `record_blocked(*, trigger: CaptureTrigger, effective_client_id: int, error_code: str, error_detail: str | None = None) -> CaptureRun` |
|  | `commit_capture(run_id: int, result: BrokerCaptureResult) -> CaptureCommitResult` |
|  | `finish_run(run_id: int, *, state: CaptureTerminalState, error_code: str | None = None, error_detail: str | None = None) -> CaptureRun` |
|  | `get_run(run_id: int) -> CaptureRun` |
|  | `list_runs(*, limit: int = 20) -> list[CaptureRun]` |
|  | `last_successful_finished_at() -> datetime | None` |
|  | `reconcile_interrupted() -> list[int]` |
|  | `position_snapshot_for_run(run_id: int) -> BrokerSnapshot` |
|  | `latest_reviewable_run_id() -> int | None` |
| `PortfolioCaptureService` | `status() -> PortfolioCaptureStatus` |
|  | `update_settings(*, enabled: bool, interval_minutes: int) -> PortfolioCaptureStatus` |
|  | `trigger(trigger: CaptureTrigger, *, background: bool = True) -> CaptureStart` |
|  | `preview_run(run_id: int) -> CaptureReviewPreview` |
|  | `apply_review_run(run_id: int) -> CaptureReviewPreview` |
|  | `reconcile_startup() -> list[int]` |
|  | `scheduler_tick(*, startup: bool = False, now: datetime | None = None) -> CaptureStart | None` |
| scheduler | `portfolio_capture_scheduler_loop(service: PortfolioCaptureService, *, poll_seconds: float = 15.0) -> None` |

`PortfolioCaptureService.trigger("manual", background=False)` is the
deterministic test/live-probe seam. Production API and scheduler calls use
`background=True`; they return after a durable `running` or terminal `blocked`
result and never hold an HTTP request for the Gateway duration.

---

### Task 0: Reserve the `portfolio_capture=+70` Client-ID Band

**Files:**
- Modify: `data_sources/ibkr_client_id.py`
- Modify: `src/data_provider_config.py`
- Modify: `tests/test_ibkr_client_id.py`
- Modify: `tests/test_data_provider_config.py`

**Interfaces:**
- Produces: `ibkr_client_id_for("portfolio_capture")`; Settings domain metadata with label `持倉擷取`.
- Preserves: every current domain offset and effective id.

- [ ] **Step 1: Strengthen the exact offset and base-bound tests**

Update the existing pins before production code:

```python
def test_domain_ids_pinned_with_default_base(monkeypatch):
    monkeypatch.delenv("IBKR_CLIENT_ID", raising=False)
    assert ibkr_client_id_for("manual") == 1
    assert ibkr_client_id_for("options") == 11
    assert ibkr_client_id_for("prices") == 21
    assert ibkr_client_id_for("news") == 31
    assert ibkr_client_id_for("iv") == 41
    assert ibkr_client_id_for("quotes") == 51
    assert ibkr_client_id_for("holdings") == 61
    assert ibkr_client_id_for("portfolio_capture") == 71


def test_portfolio_capture_band_caps_base_before_legacy_100(monkeypatch):
    monkeypatch.setenv("IBKR_CLIENT_ID", "29")
    assert ibkr_client_id_for("portfolio_capture") == 99
    monkeypatch.setenv("IBKR_CLIENT_ID", "30")
    with pytest.raises(ValueError, match="0 through 29"):
        ibkr_client_id_for("portfolio_capture")
    monkeypatch.setenv("IBKR_CLIENT_ID", "-1")
    with pytest.raises(ValueError, match="0 through 29"):
        ibkr_client_id_for("portfolio_capture")
```

Extend `test_view_exposes_client_id_domains` to expect the eighth domain, offset `70`, effective ids ending at `71`/`77`, label `持倉擷取`, and guard text containing `portfolio_capture=+70` plus `base <= 29`.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_ibkr_client_id.py tests/test_data_provider_config.py::test_view_exposes_client_id_domains -q
```

Expected: failures because the domain is absent and base 30 is still accepted.

- [ ] **Step 3: Add the band and enforce the bound at both entry points**

Use this exact map/label addition and update the module comment so trading is explicitly separate rather than assigned `+70`:

```python
DOMAIN_OFFSETS = {
    "manual": 0,
    "options": 10,
    "prices": 20,
    "news": 30,
    "iv": 40,
    "quotes": 50,
    "holdings": 60,
    "portfolio_capture": 70,
}

DOMAIN_LABELS_ZH = {
    "manual": "基底",
    "options": "選擇權",
    "prices": "股價",
    "news": "新聞",
    "iv": "IV",
    "quotes": "即時股價",
    "holdings": "持倉",
    "portfolio_capture": "持倉擷取",
}
```

After parsing the base in `ibkr_client_id_for`, reject `base < 0` or `base > 29`.
Apply the same `0 <= base <= 29` rule in
`normalize_provider_config_value`; keep the existing integer/canonicalization
behavior. Update `guard_reason` to list `portfolio_capture=+70` and explain
that order placement needs another independently authorized id.

- [ ] **Step 4: Run GREEN and the full provider-config ledger**

Run:

```bash
pytest tests/test_ibkr_client_id.py tests/test_data_provider_config.py -q
```

Expected: all pass; no prior domain id changes.

- [ ] **Step 5: Commit**

```bash
git add data_sources/ibkr_client_id.py src/data_provider_config.py tests/test_ibkr_client_id.py tests/test_data_provider_config.py
git commit -m "feat: reserve portfolio capture client id"
```

---

### Task 1: Add the Append-Only Observation Store

**Files:**
- Create: `src/portfolio_capture_types.py`
- Create: `src/portfolio_observations.py`
- Modify: `src/portfolio_state.py`
- Create: `tests/test_portfolio_observations.py`
- Preserve: `tests/test_portfolio_state.py::test_fresh_schema_does_not_create_deferred_sync_history_tables`

**Interfaces:**
- Consumes: existing `PortfolioStore` account schema and account hash identity.
- Produces: all DTOs and `PortfolioObservationStore` methods listed in the locked interface map.
- Does not produce: `portfolio_activity_annotations`, account-overview queries, or activity-feed APIs.

- [ ] **Step 1: Write the 18 RED store contracts**

Create `tests/test_portfolio_observations.py` with these separately collected tests:

```text
test_fresh_schema_creates_capture_tables_with_no_cascade_foreign_keys
test_settings_write_is_atomic_and_rejects_interval_outside_5_to_1440
test_run_lifecycle_and_recent_order_are_durable
test_startup_reconciles_stale_running_rows_to_interrupted
test_identical_account_values_still_create_one_snapshot_per_run
test_duplicate_execution_is_a_noop
test_changed_duplicate_execution_is_data_conflict_without_overwrite
test_identical_commission_is_a_noop_and_changed_content_is_a_revision
test_correction_family_links_previous_and_reconciliation_uses_latest_revision
test_first_complete_position_capture_is_only_a_baseline
test_complete_same_day_executions_explain_position_change
test_unmatched_position_window_is_idempotent
test_cross_broker_day_window_is_marked_incomplete
test_complete_zero_position_set_differs_from_failed_position_leg
test_non_finite_numeric_input_never_persists_as_zero
test_unknown_account_creates_review_shell_without_raw_id_in_label
test_existing_account_user_fields_and_archive_state_are_not_overwritten
test_observation_rows_block_account_hard_delete
```

Use real SQLite, not mocked SQL. Core fixture shape:

```python
@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "profile_state.db"
    portfolio = PortfolioStore(db)
    observations = PortfolioObservationStore(db)
    return portfolio, observations


def complete_result(*, finished_at: str, account: str = "DU123",
                    quantity: float = 1.0,
                    executions: tuple[ExecutionObservation, ...] = ()) -> BrokerCaptureResult:
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=(BrokerAccountRef(account, "USD"),),
        account_leg=CaptureLegResult("complete"),
        execution_leg=CaptureLegResult("complete"),
        position_leg=CaptureLegResult("complete"),
        account_snapshots=(AccountSnapshotObservation(
            broker_account_id=account,
            as_of_utc=finished_at,
            base_currency="USD",
            net_liquidation=100_000.0,
            total_cash_value=10_000.0,
        ),),
        positions=(PositionObservation(
            broker_account_id=account,
            broker_con_id="265598",
            symbol="AAPL",
            asset_class="stock",
            quantity=quantity,
            avg_cost=100.0,
            currency="USD",
        ),),
        executions=executions,
        commissions=(),
    )
```

The schema test must inspect `PRAGMA foreign_key_list` and assert no observation relation reports `CASCADE`. The conflict test must verify the original immutable row, `data_conflict_count == 1`, and terminal run detail without last-write-wins. The zero-position test must use a run-account mapping with zero position rows and assert it is reviewable; a failed position leg must not be reviewable.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_portfolio_observations.py -q
```

Expected: collection fails because both new modules are absent.

- [ ] **Step 3: Define shared immutable DTOs and validators**

Create `src/portfolio_capture_types.py` with these literal state sets and frozen dataclasses:

```python
CaptureTrigger = Literal["startup", "scheduled", "manual"]
CaptureTerminalState = Literal["succeeded", "partial", "failed", "blocked", "interrupted"]
CaptureRunState = Literal["running", "succeeded", "partial", "failed", "blocked", "interrupted"]
CaptureLegState = Literal["not_attempted", "complete", "partial", "failed"]
ExecutionCoverage = Literal["complete", "incomplete", "gap"]

@dataclass(frozen=True)
class CaptureLegResult:
    state: CaptureLegState
    error_code: str | None = None
    detail: str | None = None

@dataclass(frozen=True)
class BrokerAccountRef:
    broker_account_id: str
    base_currency: str | None = None

@dataclass(frozen=True)
class AccountSnapshotObservation:
    broker_account_id: str
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

@dataclass(frozen=True)
class PositionObservation:
    broker_account_id: str
    broker_con_id: str
    symbol: str
    asset_class: str
    quantity: float
    avg_cost: float | None = None
    currency: str = "USD"
    base_currency: str | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None
    market_value_base: float | None = None
    unrealized_pnl_base: float | None = None
    exchange: str | None = None
    local_symbol: str | None = None
    multiplier: str | None = None

@dataclass(frozen=True)
class ExecutionObservation:
    broker_account_id: str
    exec_id: str
    execution_time_utc: str
    broker_con_id: str
    symbol: str
    asset_class: str
    currency: str
    exchange: str
    side: str
    quantity: float
    price: float
    order_id: int | None = None
    perm_id: int | None = None
    client_id: int | None = None
    order_ref: str | None = None
    liquidation: int | None = None
    cumulative_quantity: float | None = None
    average_price: float | None = None
    origin: Literal["gateway", "flex"] = "gateway"

@dataclass(frozen=True)
class CommissionObservation:
    broker_account_id: str
    exec_id: str
    commission: float | None
    currency: str | None
    realized_pnl: float | None
    yield_value: float | None = None
    yield_redemption_date: int | None = None

@dataclass(frozen=True)
class BrokerCaptureResult:
    finished_at_utc: str
    discovered_accounts: tuple[BrokerAccountRef, ...]
    account_leg: CaptureLegResult
    execution_leg: CaptureLegResult
    position_leg: CaptureLegResult
    account_snapshots: tuple[AccountSnapshotObservation, ...]
    positions: tuple[PositionObservation, ...]
    executions: tuple[ExecutionObservation, ...]
    commissions: tuple[CommissionObservation, ...]

@dataclass(frozen=True)
class CaptureSettings:
    enabled: bool
    interval_minutes: int
    updated_at: str

@dataclass(frozen=True)
class CaptureRun:
    id: int
    trigger: CaptureTrigger
    state: CaptureRunState
    started_at: str
    finished_at: str | None
    account_leg_state: CaptureLegState
    execution_leg_state: CaptureLegState
    position_leg_state: CaptureLegState
    discovered_account_count: int
    new_account_count: int
    archived_activity_count: int
    inserted_execution_count: int
    inserted_commission_count: int
    unmatched_count: int
    data_conflict_count: int
    error_code: str | None
    error_detail: str | None
    effective_client_id: int
    coverage_notes: tuple[str, ...]

@dataclass(frozen=True)
class CaptureCommitResult:
    discovered_account_ids: tuple[int, ...]
    new_account_ids: tuple[int, ...]
    archived_activity_account_ids: tuple[int, ...]
    inserted_execution_count: int
    inserted_commission_count: int
    unmatched_count: int
    data_conflict_count: int

@dataclass(frozen=True)
class ProviderReadiness:
    configured: bool
    code: str | None = None
    status: str | None = None
    provider: str = "ibkr"
    field: str | None = None

class CaptureRunNotReviewable(ValueError):
    """The requested run has no complete broker-position set."""

class CaptureRunSuperseded(ValueError):
    """A newer complete broker-position observation owns the pending diff."""

class PortfolioCaptureBusy(RuntimeError):
    """Capture ownership is active, so review apply cannot take a stable snapshot."""
```

Add `finite_or_none(value, field)`, `correction_family(exec_id)`, and `commission_content_hash(report)` here. `correction_family` strips only a final dot-delimited numeric revision matched by `r"^(.+)\.(\d+)$"`; otherwise the full exec id is its own family. Hash canonical JSON over exactly `exec_id, currency, commission, realized_pnl, yield, yield_redemption_date` after finite decimal normalization.

- [ ] **Step 4: Implement the schema and store**

`PortfolioObservationStore.__init__` first instantiates `PortfolioStore(path)` to guarantee authority tables, then creates these tables and indexes with `PRAGMA foreign_keys=ON`, WAL best effort, and `busy_timeout=5000`:

```text
portfolio_capture_settings              singleton id=1
portfolio_capture_runs                  accepted attempts and five terminal states
portfolio_capture_run_accounts          per-run local account membership, including zero positions
portfolio_account_snapshots             UNIQUE(run_id, account_id)
portfolio_broker_position_observations  UNIQUE(run_id, account_id, broker_con_id)
portfolio_broker_executions             UNIQUE(broker, account_id, exec_id)
portfolio_broker_commission_reports     UNIQUE(broker, account_id, exec_id, content_hash)
portfolio_unmatched_position_changes    UNIQUE(account_id, broker_con_id, from_run_id, to_run_id)
```

The migration is exact rather than prose-driven. Use the following columns,
checks, and relations; implementation may wrap this matrix in one `_SCHEMA`
string but may not rename or omit a field:

| Table | Exact columns and constraints |
| --- | --- |
| `portfolio_capture_settings` | `id INTEGER PRIMARY KEY CHECK(id=1)`, `enabled INTEGER NOT NULL CHECK(enabled IN (0,1))`, `interval_minutes INTEGER NOT NULL CHECK(interval_minutes BETWEEN 5 AND 1440)`, `updated_at TEXT NOT NULL` |
| `portfolio_capture_runs` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `trigger TEXT NOT NULL CHECK(trigger IN ('startup','scheduled','manual'))`, `state TEXT NOT NULL CHECK(state IN ('running','succeeded','partial','failed','blocked','interrupted'))`, `started_at TEXT NOT NULL`, `finished_at TEXT`, `account_leg_state TEXT NOT NULL`, `execution_leg_state TEXT NOT NULL`, `position_leg_state TEXT NOT NULL` with each leg constrained to `not_attempted|complete|partial|failed`; `discovered_account_count`, `new_account_count`, `archived_activity_count`, `inserted_execution_count`, `inserted_commission_count`, `unmatched_count`, and `data_conflict_count` as non-negative `INTEGER NOT NULL DEFAULT 0`; `error_code TEXT`, `error_detail TEXT`, `client_id_domain TEXT NOT NULL CHECK(client_id_domain='portfolio_capture')`, `effective_client_id INTEGER NOT NULL`, `coverage_notes_json TEXT NOT NULL DEFAULT '[]'` |
| `portfolio_capture_run_accounts` | `capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `is_new INTEGER NOT NULL CHECK(is_new IN (0,1))`, `archived_at_capture TEXT`, primary key `(capture_run_id, portfolio_account_id)` |
| `portfolio_account_snapshots` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `as_of_utc TEXT NOT NULL`, `base_currency TEXT`, the ten nullable `REAL` account-value/P&L fields named exactly as `AccountSnapshotObservation`, `source TEXT NOT NULL CHECK(source='ibkr_gateway')`, `as_of_kind TEXT NOT NULL CHECK(as_of_kind='capture_completed')`, unique `(capture_run_id, portfolio_account_id)` |
| `portfolio_broker_position_observations` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `broker TEXT NOT NULL CHECK(broker='ibkr')`, `broker_con_id TEXT NOT NULL`, `symbol TEXT NOT NULL`, `asset_class TEXT NOT NULL`, `quantity REAL NOT NULL`, nullable `avg_cost`, `market_value`, `unrealized_pnl`, `realized_pnl`, `market_value_base`, `unrealized_pnl_base`, `currency TEXT NOT NULL`, nullable `base_currency`, `exchange`, `local_symbol`, `multiplier`, unique `(capture_run_id, portfolio_account_id, broker_con_id)` |
| `portfolio_broker_executions` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `broker TEXT NOT NULL CHECK(broker='ibkr')`, `origin TEXT NOT NULL CHECK(origin IN ('gateway','flex'))`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `first_observed_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `exec_id TEXT NOT NULL`, `first_observed_at_utc TEXT NOT NULL`, `execution_time_utc TEXT NOT NULL`, `broker_con_id TEXT NOT NULL`, `symbol TEXT NOT NULL`, `asset_class TEXT NOT NULL`, `currency TEXT NOT NULL`, `exchange TEXT NOT NULL`, `side TEXT NOT NULL`, `quantity REAL NOT NULL`, `price REAL NOT NULL`, nullable `order_id`, `perm_id`, `client_id`, `order_ref`, `liquidation`, `cumulative_quantity`, `average_price`, `correction_family TEXT NOT NULL`, `corrects_exec_id TEXT`, unique `(broker, portfolio_account_id, exec_id)` |
| `portfolio_broker_commission_reports` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `broker TEXT NOT NULL CHECK(broker='ibkr')`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `first_observed_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `exec_id TEXT NOT NULL`, `first_observed_at_utc TEXT NOT NULL`, nullable `commission`, `currency`, `realized_pnl`, `yield_value`, `yield_redemption_date`, `content_hash TEXT NOT NULL`, composite FK `(broker, portfolio_account_id, exec_id)` to executions with `ON DELETE RESTRICT`, unique `(broker, portfolio_account_id, exec_id, content_hash)` |
| `portfolio_unmatched_position_changes` | `id INTEGER PRIMARY KEY AUTOINCREMENT`, `portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT`, `from_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `to_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT`, `broker_con_id TEXT NOT NULL`, `from_as_of_utc TEXT NOT NULL`, `to_as_of_utc TEXT NOT NULL`, `before_quantity REAL NOT NULL`, `after_quantity REAL NOT NULL`, `expected_quantity REAL NOT NULL`, `residual_quantity REAL NOT NULL`, `execution_coverage TEXT NOT NULL CHECK(execution_coverage IN ('complete','incomplete','gap'))`, `source TEXT NOT NULL CHECK(source='ibkr')`, `reason_code TEXT NOT NULL`, nullable `symbol`, `asset_class`, `currency`, unique `(portfolio_account_id, broker_con_id, from_run_id, to_run_id)` |

Add indexes for run recency, account snapshot recency, account/run positions,
execution correction-family projection, commission lookup by execution, and
unmatched lookup by account/time. Do not add a generic JSON provider-payload
column.

All historical FKs use `ON DELETE RESTRICT`. `portfolio_capture_runs` stores
`trigger`, state, UTC start/finish, three leg states,
discovered/new-account/archived-activity counts, inserted
execution/commission/unmatched/conflict counts, redacted
`error_code/error_detail`, `client_id_domain='portfolio_capture'`, effective
client id, and coverage notes JSON. `portfolio_capture_run_accounts` carries
`is_new` and `archived_at_capture`; it is required so a complete zero-position
account and a reappearing archived account are representable without inventing
a position row.

Within `commit_capture`:

1. Validate every DTO before opening the transaction.
2. Map each raw account id by SHA-256 to an existing `portfolio_accounts` row.
3. Insert an unknown shell as `broker='ibkr'`, label `IBKR · <first 8 hash chars>`, `sync_mode='ibkr_review'`, and never unarchive or rewrite an existing user field.
4. Insert the run-account mapping and all valid leg rows idempotently.
5. For duplicate exec ids, compare every normalized broker/identity field from `ExecutionObservation` plus derived correction family. Preserve the original `first_observed_run_id`/time rather than comparing them to the current run; identical broker facts are a no-op, while any broker-field difference increments `data_conflict_count` without update.
6. Link a newly observed correction to the most recent prior row in the same numeric-suffix family.
7. Insert commission revisions by normalized content hash.
8. Reconcile only accounts with current and previous complete position sets. The first complete set is baseline only.
9. Compute the execution delta as the difference between correction-aware effective execution projections at the two run ids, using `first_observed_run_id`; never sum both an original and its correction.
10. Coverage is `complete` only when the current execution leg is complete and both endpoint captures are on the same ET broker day. A current partial/failed execution leg is `incomplete`; a cross-ET-day window is `gap`. Both states may record a nonzero residual but may not call it unexplained.
11. Use signed BUY/BOT positive and SELL/SLD negative quantities. An unknown side makes coverage `incomplete`, never a fake execution.
12. Insert residuals with the natural unique key and a `1e-9` quantity tolerance; zero residual creates no row.

The unknown-account test asserts `new_account_ids`; the archived-account test
asserts `archived_activity_account_ids` while the existing account remains
archived.

Keep raw account ids only in local `portfolio_accounts`; none of the new observation tables duplicate them. Rename the existing private hash helper to
`portfolio_account_hash(value)` and retain `_account_hash = portfolio_account_hash`
as a local compatibility alias. The observation store imports the public helper
so account identity has one implementation.

- [ ] **Step 5: Run GREEN and SQLite integrity checks**

Run:

```bash
pytest tests/test_portfolio_observations.py tests/test_portfolio_state.py -q
python -m compileall -q src/portfolio_capture_types.py src/portfolio_observations.py
```

Expected: all pass; legacy `portfolio_sync_runs`/`portfolio_sync_diffs` remain absent.

- [ ] **Step 6: Commit**

```bash
git add src/portfolio_capture_types.py src/portfolio_observations.py src/portfolio_state.py tests/test_portfolio_observations.py
git commit -m "feat: add portfolio observation store"
```

---

### Task 2: Journal Manual Financial Mutations Atomically

**Files:**
- Modify: `src/portfolio_state.py`
- Modify: `tests/test_portfolio_state.py`

**Interfaces:**
- Consumes: existing manual create/update/close methods and their current validation.
- Produces: `PortfolioStore.list_manual_adjustments(position_id: int | None = None) -> list[ManualAdjustment]` for audit and later Slice 3 UI.
- Preserves: notes/thesis/tags edits, broker-field ownership, explicit-null behavior, and route payloads.

- [ ] **Step 1: Add eight RED transaction/journal tests**

Add separately collected tests for:

```text
test_manual_create_records_field_level_adjustment
test_manual_update_journals_only_changed_financial_fields
test_manual_avg_cost_clear_records_explicit_null
test_manual_close_records_one_idempotent_adjustment
test_note_only_update_does_not_create_manual_adjustment
test_manual_create_rolls_back_when_journal_insert_fails
test_manual_update_and_note_change_roll_back_when_journal_insert_fails
test_manual_close_rolls_back_when_journal_insert_fails
```

Use a real DB and monkeypatch only `store._record_manual_adjustment` for rollback tests. Assert both the canonical row and adjustment child count before/after; do not accept a test that checks only one side.
The create test also submits `NaN`, positive/negative infinity, zero quantity,
negative average cost, and blank currency in separate assertions; each must
fail before either a position or journal row exists.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_portfolio_state.py -q
```

Expected: journal APIs/tables are absent.

- [ ] **Step 3: Add the manual journal schema and transaction hook**

Append to `_SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS portfolio_manual_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    position_id INTEGER NOT NULL REFERENCES portfolio_positions(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK(action IN ('create','update','close')),
    note TEXT,
    source TEXT NOT NULL CHECK(source='manual'),
    occurred_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_manual_adjustment_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_id INTEGER NOT NULL REFERENCES portfolio_manual_adjustments(id) ON DELETE RESTRICT,
    field TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    UNIQUE(adjustment_id, field)
);
```

Add `_record_manual_adjustment(conn, account_id, position_id, action, changes, now)` and call it inside the same existing `with self._connect() as conn` transaction:

- create records `symbol, asset_class, quantity, avg_cost, currency` from null to stored value;
- update records only changed keys in `_MANUAL_FINANCIAL_FIELDS` after normalization;
- close records `closed_at: null -> timestamp` exactly once;
- user-owned fields are never journaled;
- an exception propagates so SQLite rolls back every mutation in that method.

Before the create insert, run quantity/average-cost through the existing
finite validators and apply the same nonzero/non-negative/currency rules as
manual update. Do not rely on the browser or Pydantic to reject non-finite
values.

Expose frozen `ManualAdjustment`/`ManualAdjustmentChange` read DTOs. Do not add an API route in this slice.

```python
@dataclass(frozen=True)
class ManualAdjustmentChange:
    field: str
    before: Any
    after: Any

@dataclass(frozen=True)
class ManualAdjustment:
    id: int
    account_id: int
    position_id: int
    action: Literal["create", "update", "close"]
    note: str | None
    source: Literal["manual"]
    occurred_at_utc: str
    changes: tuple[ManualAdjustmentChange, ...]
```

- [ ] **Step 4: Run GREEN and route regressions**

Run:

```bash
pytest tests/test_portfolio_state.py tests/test_portfolio_routes.py -q
```

Expected: all tests pass; route request/response shapes remain unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/portfolio_state.py tests/test_portfolio_state.py
git commit -m "feat: journal manual portfolio adjustments"
```

---

### Task 3: Read One Truthful IBKR Capture

**Files:**
- Create: `src/portfolio_capture_ibkr.py`
- Create: `tests/test_portfolio_capture_ibkr.py`
- Modify: `tests/test_ibkr_source_event_loop.py`

**Interfaces:**
- Consumes: Task 0 client id and Task 1 DTOs.
- Produces: `read_ibkr_capture() -> BrokerCaptureResult`.
- Does not own: scheduling, permission checks, DB writes, canonical apply, or Gateway lock acquisition.

- [ ] **Step 1: Write 11 RED adapter tests**

Create tests with a fake `IBKRDataSource` and fake `ib_insync`-shaped session:

```text
test_capture_uses_portfolio_capture_client_id_readonly_and_disconnects
test_connect_false_returns_failed_legs_without_reading_session
test_account_leg_keeps_selected_fields_and_uses_unique_cached_base_currency_hint
test_daily_pnl_subscription_is_bounded_and_missing_values_stay_null
test_execution_leg_uses_connect_synced_fills_without_second_execution_request
test_missing_commission_report_does_not_invent_zero_commission_or_pnl
test_position_leg_joins_positions_and_portfolio_by_account_and_conid
test_successful_empty_position_calls_are_complete
test_one_failed_leg_does_not_discard_other_valid_legs
test_non_finite_provider_value_marks_the_leg_partial_and_never_zero
test_capture_reader_runs_in_an_anyio_worker_thread_without_event_loop_warning
```

Patch the module-level `_source_factory`, not `IBKRDataSource` at a caller module. The worker-thread test calls `read_ibkr_capture` through `anyio.to_thread.run_sync` and asserts no `RuntimeWarning` plus one disconnect.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_portfolio_capture_ibkr.py tests/test_ibkr_source_event_loop.py -q
```

Expected: new module import failure.

- [ ] **Step 3: Implement the one-connection reader**

Create the source before calls and always disconnect:

```python
def read_ibkr_capture() -> BrokerCaptureResult:
    source = _source_factory(
        client_id=ibkr_client_id_for("portfolio_capture"),
        readonly=True,
    )
    try:
        if not source.connect():
            return failed_capture("ibkr_connection_failed")
        ib = getattr(source, "_ib", None)
        if ib is None:
            return failed_capture("ibkr_session_missing")
        return _read_connected_capture(ib)
    finally:
        source.disconnect()
```

`_read_connected_capture` must:

1. Collect visible account ids from `managedAccounts()` and every valid leg row.
2. Read `accountSummary()` and retain only `NetLiquidation`, `TotalCashValue`, `SettledCash`, `GrossPositionValue`, `BuyingPower`, `AvailableFunds`, `InitMarginReq`, and `MaintMarginReq`. Read the already synchronized `accountValues()` cache only for `Currency`/`RealCurrency` base-currency hints; do not persist that payload.
3. Use explicit `BaseCurrency` if present. Otherwise accept a three-letter ISO
   base hint only when the cached account values yield exactly one candidate;
   ambiguous multi-currency candidates stay null. For duplicate summary rows,
   select the row matching the inferred base ISO; otherwise prefer the
   synthetic `BASE` total row. Never sum currencies or guess from a position's
   contract currency.
4. Request `reqPnL(account)` for visible accounts, wait at most two seconds total for finite values, and cancel every started subscription in `finally`; missing/unsupported values and IB's unset max-double sentinel stay null and do not invent zero.
5. Parse `ib.fills()` after the connection completes. The installed
   `ib_insync.IB.connect()` already awaits `reqExecutionsAsync()` during its
   synchronization phase, so capture must not issue a second
   `reqExecutions()` request. Parse each `Fill.execution`, `Fill.contract`, and
   optional `Fill.commissionReport`, preserving `execId`, stable `permId`, and
   session-scoped `orderId`.
6. Call `positions()` and `portfolio()` independently and join by `(account, conId)`. The position leg is complete only when both reads succeed and every nonzero position has one unambiguous matching portfolio item; a missing/duplicate enrichment row makes the leg partial rather than allowing canonical market values to be overwritten with null.
7. Treat both successful empty lists as a complete empty set; an exception, contradictory list, or incomplete join is failed/partial and never an empty account.
8. Mark a leg partial when individual malformed/non-finite rows are skipped, while retaining other valid rows.
9. Return normalized error codes and exception class only; do not emit raw messages or account ids.

The account-leg test includes competing USD/EUR summary rows, no unsupported
fixture-only `BaseCurrency` tag, and one cached `Currency=USD` hint. It proves
the USD account-total row is selected without aggregation; a second arm with
ambiguous cached hints proves base currency remains null rather than guessed.
The execution-leg test makes `reqExecutions` raise if called and supplies the
fills cache populated by the connect fake, so a redundant provider request
cannot pass under a test-shaped seam.

Import `IBKRDataSource` at module import so the existing first-import/event-loop hardening remains active before AnyIO workers execute it.

- [ ] **Step 4: Run GREEN and the event-loop regression family**

Run:

```bash
pytest tests/test_portfolio_capture_ibkr.py tests/test_ibkr_source_event_loop.py tests/test_news_normalized_ibkr_adapter.py -q -W error::pytest.PytestUnraisableExceptionWarning
```

Expected: all pass, zero unraisable warnings.

- [ ] **Step 5: Commit**

```bash
git add src/portfolio_capture_ibkr.py tests/test_portfolio_capture_ibkr.py tests/test_ibkr_source_event_loop.py
git commit -m "feat: read portfolio capture from ibkr"
```

---

### Task 4: Orchestrate Capture, Canonical Apply, and Cadence

**Files:**
- Create: `src/portfolio_capture.py`
- Create: `src/portfolio_capture_scheduler.py`
- Create: `tests/test_portfolio_capture.py`
- Create: `tests/test_portfolio_capture_scheduler.py`
- Modify: `src/portfolio_ibkr.py`
- Modify: `tests/test_portfolio_ibkr.py`

**Interfaces:**
- Consumes: observation store, reader, existing `preview_or_apply_ibkr_snapshot`, `PortfolioStore`, shared `ibkr_gateway_lock`.
- Produces: `PortfolioCaptureService`, status/start/review DTOs, and scheduler loop.
- Preserves: legacy immediate preview is zero-write and legacy apply still
  requires its existing route gate. Deliberate exception: legacy apply now
  recognizes archived broker accounts without unarchiving them or resetting
  their user-owned account fields.

- [ ] **Step 1: Write 14 RED orchestration tests**

`tests/test_portfolio_capture.py` must separately collect:

```text
test_permission_denied_is_ephemeral_blocked_and_calls_no_provider
test_missing_provider_records_blocked_and_calls_no_reader
test_concurrent_trigger_is_already_running_and_opens_no_second_reader
test_gateway_busy_finishes_blocked_without_reader_call
test_observation_commit_happens_before_auto_apply
test_observation_commit_failure_prevents_canonical_apply
test_auto_mode_applies_only_complete_position_leg_and_auto_accounts
test_incomplete_position_leg_never_closes_canonical_positions
test_review_mode_persists_observations_without_canonical_write
test_manual_mode_persists_observations_without_canonical_write
test_canonical_apply_failure_keeps_observations_and_finishes_partial
test_partial_capture_persists_valid_legs
test_review_preview_is_derived_from_run_and_is_zero_write
test_apply_review_requires_latest_complete_run_and_never_rereads_gateway
```

The concurrency test covers both the in-process lock and a fake held
cross-process capture lock. The ordering test uses an event list populated by
fake `commit_capture` and `apply_broker_positions`; it must assert exact order
`['read', 'commit', 'apply', 'finish']`.
The auto-mode test uses one `ibkr_auto` and one `ibkr_review` account in the
same complete capture. It proves only the auto account's broker-owned fields
change. Its auto account is archived, and the test also asserts `archived_at`
remains unchanged.

Add one direct legacy-helper RED regression in `tests/test_portfolio_ibkr.py`:

```text
test_legacy_apply_preserves_archived_account_and_user_owned_fields
```

Seed an `ibkr_auto` account, give it a user label and
`include_in_total=false`, archive it, then apply a snapshot for the same raw
broker account id. The test must assert that the existing local account id,
archive timestamp, label, sync mode, and inclusion setting are unchanged. On
the current code this fails because `list_accounts()` hides the archived row
and `upsert_broker_account()` then clears `archived_at` while resetting
label/sync mode.

- [ ] **Step 2: Write eight RED cadence/scheduler tests**

`tests/test_portfolio_capture_scheduler.py` must separately collect:

```text
test_startup_runs_when_no_success_exists
test_startup_does_not_run_when_last_success_is_inside_interval
test_startup_runs_when_last_success_is_stale
test_partial_or_failed_completion_sets_next_due_from_completion
test_successful_manual_run_resets_next_due
test_already_running_manual_request_does_not_reset_due
test_periodic_disabled_still_allows_manual_trigger
test_scheduler_loop_survives_one_failed_tick_without_tight_retry
```

Use an injected UTC clock and fake sleep; do not use wall-clock sleeps.

- [ ] **Step 3: Run RED**

Run:

```bash
pytest tests/test_portfolio_ibkr.py -q
pytest tests/test_portfolio_capture.py tests/test_portfolio_capture_scheduler.py -q
```

Expected: the new direct legacy regression fails on silent unarchive/reset;
service/scheduler modules are absent.

- [ ] **Step 4: Implement service ordering and redacted projections**

Define these service-level immutable DTOs before the class:

```python
@dataclass(frozen=True)
class CaptureStart:
    accepted: bool
    run: CaptureRun | None
    state: CaptureRunState
    error_code: str | None = None
    error_detail: str | None = None

@dataclass(frozen=True)
class EffectiveCaptureSettings:
    enabled: bool
    interval_minutes: int
    source: Literal["default", "database"]
    provider_configured: bool

@dataclass(frozen=True)
class PortfolioCaptureStatus:
    settings: EffectiveCaptureSettings
    provider_issue: ProviderReadiness | None
    running: bool
    next_due_at: str | None
    latest_run: CaptureRun | None
    recent_runs: tuple[CaptureRun, ...]
    review_run_id: int | None
    review: CaptureReviewPreview | None

@dataclass(frozen=True)
class CaptureReviewChange:
    kind: str
    account_id: int | None
    account_label: str | None
    broker_account_id_hash: str | None
    broker_con_id: str
    symbol: str
    quantity: float
    before: dict[str, Any] | None
    after: dict[str, Any] | None

@dataclass(frozen=True)
class CaptureReviewPreview:
    run_id: int
    changes: tuple[CaptureReviewChange, ...]
    applies: bool
```

Also define one process singleton backed by the existing lock implementation:

```python
PORTFOLIO_CAPTURE_FILE_LOCK = FileLock("portfolio_capture")
```

`PortfolioCaptureService` constructor accepts explicit dependencies:

```python
def __init__(
    self,
    *,
    observations: PortfolioObservationStore,
    portfolio: PortfolioStore,
    reader: Callable[[], BrokerCaptureResult],
    provider_readiness: Callable[[], ProviderReadiness],
    write_allowed: Callable[[str, dict[str, Any]], bool],
    capture_process_lock: FileLock = PORTFOLIO_CAPTURE_FILE_LOCK,
    gateway_lock: Callable[[float], ContextManager[None]] = ibkr_gateway_lock,
    clock: Callable[[], datetime] = utc_now,
) -> None:
```

Use an instance `threading.Lock`, a dedicated
`FileLock("portfolio_capture")`, and the shared file/thread Gateway lock with
`timeout=0`. The capture file lock distinguishes another capture from an
unrelated IBKR job; the Gateway lock continues to serialize every IBKR owner.
`trigger` performs this precedence:

1. own capture lock;
2. write permission;
3. provider readiness;
4. non-blocking cross-process capture file lock;
5. durable running row;
6. background daemon thread or inline `_execute`;
7. Gateway lock;
8. one reader call;
9. observation commit;
10. complete-leg `ibkr_auto` apply only;
11. terminal run update and due-time update;
12. release Gateway, capture-file, and instance locks.

Terminal-state calculation is exact: all three legs complete with zero data
conflicts and zero canonical-apply errors is `succeeded`; at least one valid
complete/partial leg plus any failed/partial leg, conflict, or apply error is
`partial`; no valid observation leg is `failed`; provider/config/concurrency
preconditions use `blocked`; stale process-owned rows use `interrupted`.

Permission denial creates no row and does not reset cadence. `already_running` also does not reset cadence. Provider missing and Gateway busy are permitted durable blocked attempts and set the next in-process due from completion, preventing a retry loop.
If background-thread startup itself fails, finish the already-created run as
failed and release both capture locks synchronously.

Convert observation rows to the existing `BrokerSnapshot` only inside the
service, then partition it by the current local account `sync_mode`. Automatic
post-capture apply passes a snapshot containing only `ibkr_auto` accounts to
`preview_or_apply_ibkr_snapshot(..., apply=True)`; `ibkr_review` and `manual`
accounts are structurally absent from that call. `preview_run(run_id)` obtains
`snapshot = observations.position_snapshot_for_run(run_id)`, filters it to
`ibkr_review`, and calls `preview_or_apply_ibkr_snapshot(portfolio, snapshot,
apply=False)`. Status calls this only for `latest_reviewable_run_id()`; an
arbitrary recent run is history, not another pending proposal.

`apply_review_run(run_id)` first acquires the same instance and cross-process
capture ownership locks without acquiring the Gateway lock. While both are
held, it re-reads `latest_reviewable_run_id()` and requires exact equality with
`run_id`; an older complete run raises `CaptureRunSuperseded`, and active
capture ownership raises `PortfolioCaptureBusy`. It then uses that same
review-only, store-loaded snapshot with `apply=True` before releasing the
locks. This check-and-apply serialization prevents a newer capture from
committing between freshness validation and canonical mutation. Neither review
function calls the reader or silently applies an auto/manual account. Both
public methods convert the
internal `PortfolioSyncPreview` to `CaptureReviewPreview`, which has no raw
account-id field and carries local `account_id`, label, and
`broker_account_id_hash`. Before serialization, derive a safe display label:
if an existing legacy/generated label contains its raw broker account id,
replace only the response label with `IBKR · <first 8 hash chars>`; otherwise
preserve the user's label. Do not mutate the stored user-owned label merely to
pass a response boundary.

In `preview_or_apply_ibkr_snapshot`, build broker-account identity from
`store.list_accounts(include_archived=True)`. This closes the existing path
where a reappearing archived account was mistaken for missing and
`upsert_broker_account` silently cleared `archived_at` and reset user-owned
account fields. This is a deliberate behavior repair on the mounted legacy
compatibility route, not an incidental service-only change. Do not otherwise
change legacy preview/apply behavior.

- [ ] **Step 5: Implement due calculation and scheduler loop**

The service owns `_next_due_at` for its process. On first startup calculation,
use `last_successful_finished_at + interval`; after any accepted terminal
attempt, use that attempt's completion plus the current interval. A manual
success resets it; a rejected concurrent manual request does not.

`reconcile_startup` first checks the instance lock and then tries the dedicated
capture file lock non-blocking. It marks durable `running` rows interrupted
only while that file lock is held. If another sidecar owns the lock, it leaves
those rows alone; a second process must never interrupt a live first process.

Implement the loop exactly as a cheap coordinator:

```python
async def portfolio_capture_scheduler_loop(
    service: PortfolioCaptureService,
    *,
    poll_seconds: float = 15.0,
) -> None:
    first = True
    while True:
        try:
            service.scheduler_tick(startup=first)
        except Exception:
            logger.exception("portfolio capture scheduler tick failed")
        first = False
        await asyncio.sleep(poll_seconds)
```

`scheduler_tick` returns without starting when periodic capture is disabled, provider configuration is absent, a capture is active, or next due is in the future.
Lifespan owns the one startup reconciliation before this loop is created; the
loop must not repeat that repair on every restart/test seam.

`update_settings` delegates the atomic store write, clears `_next_due_at` when
disabled, and when enabled recalculates it from the current time plus the new
interval. It returns a fresh `status()` so API and scheduler share one
effective-settings computation.

- [ ] **Step 6: Run GREEN and legacy sync regressions**

Run:

```bash
pytest tests/test_portfolio_capture.py tests/test_portfolio_capture_scheduler.py tests/test_portfolio_ibkr.py tests/test_portfolio_routes.py -q
```

Expected: all pass; legacy preview still creates zero accounts/positions,
legacy apply still works, and a reappearing archived account remains archived
with its user-owned fields intact.

- [ ] **Step 7: Commit**

```bash
git add src/portfolio_capture.py src/portfolio_capture_scheduler.py src/portfolio_ibkr.py tests/test_portfolio_capture.py tests/test_portfolio_capture_scheduler.py tests/test_portfolio_ibkr.py
git commit -m "feat: orchestrate portfolio capture"
```

---

### Task 5: Add Guarded Capture APIs and Lifespan Wiring

**Files:**
- Create: `src/api/routes/portfolio_capture.py`
- Create: `tests/test_portfolio_capture_routes.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/app.py`
- Modify: `tests/test_provider_config_startup.py`

**Interfaces:**
- Consumes: singleton service from Task 4.
- Produces:
  - `GET /portfolio/capture`
  - `PUT /portfolio/capture/settings`
  - `POST /portfolio/capture/runs`
  - `POST /portfolio/capture/runs/{run_id}/apply`
- Preserves: all current `/portfolio` routes and payloads.

- [ ] **Step 1: Write 10 RED route/lifespan tests**

Create/extend tests with these collected names:

```text
test_portfolio_capture_router_mounts_on_real_app
test_capture_status_defaults_enabled_only_when_ibkr_is_configured
test_capture_status_reports_provider_missing_without_calling_gateway
test_capture_settings_put_requires_gate_and_persists_atomically
test_capture_settings_model_rejects_invalid_interval_without_store_call
test_manual_capture_returns_running_or_terminal_blocked_shape
test_capture_status_recent_runs_contains_no_raw_broker_account_id
test_apply_review_requires_write_gate_and_uses_run_id
test_lifespan_starts_data_and_portfolio_scheduler_tasks
test_disable_scheduler_env_prevents_both_scheduler_tasks
```

Handler-direct tests pass fake service/store dependencies explicitly. The
invalid-interval test constructs `CaptureSettingsBody` and expects Pydantic
`ValidationError`, while a spy proves the store/service was not called; it does
not pretend a direct handler invocation emits an HTTP 422. The mount test uses
`create_app()`, not a nonexistent module-level `app`.
The raw-id test uses the real service/store, seeds a legacy account label
containing the exact fixture account id, and proves the capture response emits
only its safe derived label and hash while the stored label remains unchanged.
The apply test has four arms in the same collected item: an unknown run maps to
404; an incomplete run maps to 409/`capture_run_not_reviewable`; a superseded
complete run maps to 409/`capture_run_superseded`; and active capture ownership
maps to 409/`portfolio_capture_busy`. No arm calls Gateway or mutates canonical
positions. Its success arm proves the exact latest complete run applies once.

- [ ] **Step 2: Run RED**

Run:

```bash
pytest tests/test_portfolio_capture_routes.py tests/test_provider_config_startup.py tests/test_api.py -q
```

Expected: new router paths and dependencies are absent.

- [ ] **Step 3: Add singleton dependencies without route-owned construction**

In `src/api/dependencies.py`, add cached constructors:

```python
@lru_cache(maxsize=1)
def get_portfolio_observation_store() -> PortfolioObservationStore:
    return PortfolioObservationStore(_local_state_db_path())

@lru_cache(maxsize=1)
def get_portfolio_capture_service() -> PortfolioCaptureService:
    return PortfolioCaptureService(
        observations=get_portfolio_observation_store(),
        portfolio=get_portfolio_store(),
        reader=read_ibkr_capture,
        provider_readiness=_ibkr_capture_readiness,
        write_allowed=_portfolio_capture_write_allowed,
    )
```

`_ibkr_capture_readiness` calls
`require_provider_configured('ibkr', get_data_provider_store())` and converts
`ProviderConfigMissing.as_dict()` to the typed readiness result without
changing the existing four-key contract:
`code='provider_config_missing'`, `status='not_configured'`,
`provider='ibkr'`, and the exact missing `field`. The route returns those four
keys in its blocked status/next-action payload. `_portfolio_capture_write_allowed`
invokes `require_profile_state_write` and returns true; tests inject false
directly into the service rather than weakening the project gate.

- [ ] **Step 4: Implement additive redacted routes**

Use these Pydantic bodies:

```python
class CaptureSettingsBody(BaseModel):
    enabled: bool
    interval_minutes: int = Field(ge=5, le=1440)

class CaptureRunBody(BaseModel):
    trigger: Literal["manual"] = "manual"
```

GET returns effective settings with `source: 'default' | 'database'`, provider
readiness, next due, running, latest/recent run summaries, and latest review
diff. PUT gates `portfolio_capture_settings_write` before calling
`service.update_settings`. POST run delegates to
`service.trigger('manual', background=True)`. Apply gates
`portfolio_capture_apply` and delegates by run id, mapping unknown to 404 and
not-reviewable/superseded/busy to distinct normalized 409 envelopes. Serialize only local
ids/labels/hashes; recursively assert the response text contains no raw
fixture account id. The default-status test additionally asserts no settings
row is materialized by GET.

- [ ] **Step 5: Mount the router and lifecycle task**

Include the new router in `create_app()`. After provider env setup succeeds,
obtain the capture service and call `reconcile_startup()` even when
`ARKSCOPE_DISABLE_SCHEDULER=1`. Disabling periodic work must not leave a dead
process's run permanently `running`; setup-only boot skips service construction
because the profile DB is unavailable.

Under the same `provider_config_ready` and `ARKSCOPE_DISABLE_SCHEDULER`
condition as the existing scheduler, create `portfolio_sched_task` beside
`sched_task`:

```python
capture_service = None
portfolio_sched_task = None
if provider_config_ready:
    capture_service = get_portfolio_capture_service()
    capture_service.reconcile_startup()
if provider_config_ready and scheduler_enabled:
    portfolio_sched_task = asyncio.create_task(
        portfolio_capture_scheduler_loop(capture_service),
        name="portfolio-capture-scheduler",
    )
```

Here `scheduler_enabled` is the existing env predicate factored once and shared
by both task creations; do not evaluate two subtly different strings.

Cancel/await both tasks independently during shutdown. Setup-only boot proves
the service is not constructed; scheduler-disabled boot proves reconciliation
occurs but neither scheduler task starts.

- [ ] **Step 6: Run GREEN and real app mount checks**

Run:

```bash
pytest tests/test_portfolio_capture_routes.py tests/test_provider_config_startup.py tests/test_api.py tests/test_portfolio_routes.py -q
```

Expected: all pass; `/portfolio/capture` is present and current routes remain mounted.

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/portfolio_capture.py src/api/dependencies.py src/api/app.py tests/test_portfolio_capture_routes.py tests/test_provider_config_startup.py
git commit -m "feat: expose portfolio capture controls"
```

---

### Task 6: Replace the Holdings Live-Sync Control with Capture Records

**Files:**
- Create: `apps/arkscope-web/src/PortfolioCapturePanel.tsx`
- Create: `apps/arkscope-web/src/PortfolioCapturePanel.test.tsx`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Holdings.tsx`
- Modify: `apps/arkscope-web/src/Holdings.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/styles.css`

**Interfaces:**
- Consumes: Task 5 endpoints and existing Button/StatusBadge/InlineAlert/DataTable primitives.
- Produces: one Holdings-owned `同步紀錄` section with schedule controls, immediate capture, truthful run/leg states, and latest review/apply.
- Does not produce: account overview, activity feed, annotations, placeholder tabs, or a Data Sources scheduler row.

- [ ] **Step 1: Add API DTOs and eight RED panel tests**

Define frontend types matching the redacted API exactly:

```typescript
export type PortfolioCaptureRunState =
  | "running" | "succeeded" | "partial" | "failed" | "blocked" | "interrupted";

export interface PortfolioCaptureRun {
  id: number;
  trigger: "startup" | "scheduled" | "manual";
  state: PortfolioCaptureRunState;
  started_at: string;
  finished_at?: string | null;
  account_leg_state: string;
  execution_leg_state: string;
  position_leg_state: string;
  new_account_count: number;
  archived_activity_count: number;
  error_code?: string | null;
  error_detail?: string | null;
  unmatched_count: number;
  data_conflict_count: number;
}

export interface PortfolioCaptureReviewChange {
  kind: string;
  account_id?: number | null;
  account_label?: string | null;
  broker_account_id_hash?: string | null;
  broker_con_id: string;
  symbol: string;
  quantity: number;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface PortfolioCaptureReview {
  run_id: number;
  changes: PortfolioCaptureReviewChange[];
  applies: boolean;
}

export interface PortfolioCaptureStatus {
  settings: {
    enabled: boolean;
    interval_minutes: number;
    source: "default" | "database";
    provider_configured: boolean;
  };
  provider_issue?: {
    code: "provider_config_missing";
    status: "not_configured";
    provider: "ibkr";
    field: "host" | "port";
  } | null;
  running: boolean;
  next_due_at?: string | null;
  latest_run?: PortfolioCaptureRun | null;
  recent_runs: PortfolioCaptureRun[];
  review?: PortfolioCaptureReview | null;
}

export interface PortfolioCaptureStart {
  accepted: boolean;
  state: PortfolioCaptureRunState;
  run?: PortfolioCaptureRun | null;
  error_code?: string | null;
  error_detail?: string | null;
}
```

Add `getPortfolioCaptureStatus`, `updatePortfolioCaptureSettings`, `triggerPortfolioCapture`, and `applyPortfolioCaptureRun`. Create eight panel tests:

```text
renders_default_schedule_and_latest_component_states
saves_enabled_and_interval_as_one_atomic_payload
rejects_out_of_range_interval_without_fetch
manual_capture_starts_then_polls_until_terminal
renders_partial_blocked_failed_and_interrupted_with_existing_status_badges
shows_next_due_and_recent_runs_without_raw_account_id
renders_latest_review_and_applies_that_capture_run
returns_to_idle_polling_without_repeated_live_announcements_after_terminal
```

Use the existing createRoot/`act`/stubbed-global-fetch house harness. Do not add Testing Library.

- [ ] **Step 2: Run RED**

Run:

```bash
npm --workspace apps/arkscope-web test -- PortfolioCapturePanel.test.tsx
```

Expected: component and API helpers are absent.

- [ ] **Step 3: Implement the bounded panel**

The panel loads once, refreshes every 30 seconds while idle/terminal so a
scheduled capture can appear without navigation, and polls every two seconds
only while the server reports a running capture. A terminal transition returns
to the 30-second cadence; unmount clears either timer. The polling container
has no `aria-live`; only a normalized terminal transition or explicit error may
use the shared status/alert announcement semantics. Controls:

- enabled checkbox;
- numeric interval input with visible `5-1440 分鐘` bound;
- one Save button;
- one `立即同步` button;
- next-due/local-time text;
- latest run plus three leg states;
- `待檢視` notice for `new_account_count > 0` and a separate archived-account
  activity notice for `archived_activity_count > 0` without auto-unarchiving;
- recent run DataTable;
- latest captured review diff and `套用同步` button.

Track the last terminal run id notified to `onPortfolioChanged`; invoke the
callback at most once per run, so 30-second idle refreshes cannot repeatedly
reload canonical holdings.

Map states to shared vocabulary: `succeeded -> ready`; all other names map directly. Disabled periodic capture is muted text, not `interrupted`. Provider missing is `blocked` with exact next-action text `前往設定 > Data Sources > IBKR`; do not render a dead link before the P2.8 shell navigation-target slice exists. Do not render raw exception text beyond the normalized API detail.

Use a finite local interval parser before sending:

```typescript
function parseCaptureInterval(raw: string): number | null {
  const text = raw.trim();
  if (!text) return null;
  const value = Number(text);
  return Number.isInteger(value) && value >= 5 && value <= 1440 ? value : null;
}
```

- [ ] **Step 4: Wire Holdings without a second sync workflow**

Replace the rendered `IBKR 同步` live-preview section in `Holdings.tsx` with `<PortfolioCapturePanel onPortfolioChanged={load} />`. Remove the component's `previewIbkrPortfolioSync`/`applyIbkrPortfolioSync` state and imports; keep the backend compatibility routes untouched. The panel calls `onPortfolioChanged` after a terminal automatic capture or successful explicit review apply.

Evolve the two existing preview/apply UI tests into capture-run tests without deleting their intent, and add:

```text
holdings_renders_one_capture_control_surface_and_no_legacy_live_sync_buttons
```

Add one Settings regression assertion:

```typescript
it("settings_data_sources_does_not_own_portfolio_capture_controls", async () => {
  await renderDataSources();
  expect(host!.textContent).not.toContain("持倉擷取排程");
  expect(host!.querySelector('[data-portfolio-capture-controls]')).toBeNull();
});
```

This is a no-duplicate invariant, not a reason to modify `Settings.tsx`.

- [ ] **Step 5: Add only surface-local responsive CSS**

Use auto-fit grids, existing spacing/radius tokens, and DataTable's own scroll container. Add no `@media` rule, no new chip system, no radius above 8px, and no global shell token. Long normalized errors wrap with `overflow-wrap:anywhere` and cannot cover adjacent run columns.

- [ ] **Step 6: Run GREEN, typecheck, and build**

Run:

```bash
npm --workspace apps/arkscope-web test -- PortfolioCapturePanel.test.tsx Holdings.test.tsx SettingsProviderConfig.test.ts
npm --workspace apps/arkscope-web test
npm --workspace apps/arkscope-web run typecheck
npm --workspace apps/arkscope-web run build
```

Expected: all pass; base `41 files / 366 tests` becomes `42 files / 376 tests` (`+10/-0`), typecheck/build pass, and only the existing chunk warning is permitted.

- [ ] **Step 7: Commit**

```bash
git add apps/arkscope-web/src/PortfolioCapturePanel.tsx apps/arkscope-web/src/PortfolioCapturePanel.test.tsx apps/arkscope-web/src/api.ts apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/styles.css
git commit -m "feat: add holdings capture controls"
```

---

### Task 7: Verify Boundaries, Canonical A/B, and Live Gateway Behavior

**Files:**
- Modify after implementation evidence: `docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md`
- Modify after implementation evidence: `docs/design/PROJECT_PRIORITY_MAP.md`
- Do not change spec status to LIVE before review and merge.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a review-ready branch with exact automated/live evidence.

- [ ] **Step 1: Run the complete focused backend suite**

Run:

```bash
pytest \
  tests/test_ibkr_client_id.py \
  tests/test_data_provider_config.py \
  tests/test_portfolio_state.py \
  tests/test_portfolio_observations.py \
  tests/test_portfolio_capture_ibkr.py \
  tests/test_portfolio_capture.py \
  tests/test_portfolio_capture_scheduler.py \
  tests/test_portfolio_capture_routes.py \
  tests/test_portfolio_ibkr.py \
  tests/test_portfolio_routes.py \
  tests/test_portfolio_holdings_tools.py \
  tests/test_provider_config_startup.py \
  tests/test_api.py -q
```

Expected: all Slice 1 tests pass. The planned backend collect delta is exactly
`+71/-0`: 1 client-id-band, 18 observation-store, 8 manual-journal, 11 reader,
14 service, 8 scheduler, 1 direct legacy archived-account regression, and 10
route/lifespan tests. Any different delta must be reconciled by named test
before review.

- [ ] **Step 2: Run static safety and ownership gates**

Run:

```bash
rg -n "placeOrder|cancelOrder|reqGlobalCancel|modifyOrder|exerciseOptions?" \
  src/portfolio_capture.py src/portfolio_capture_ibkr.py \
  src/portfolio_capture_scheduler.py src/portfolio_observations.py
rg -n "postgres|psycopg|supabase|db_dsn" \
  src/portfolio_capture.py src/portfolio_capture_ibkr.py \
  src/portfolio_capture_scheduler.py src/portfolio_observations.py \
  src/api/routes/portfolio_capture.py
rg -n '\bbroker_account_id\b' apps/arkscope-web/src/PortfolioCapturePanel.tsx
rg -n "portfolio_capture|持倉擷取" apps/arkscope-web/src/Settings.tsx
git diff --exit-code "$(cat /tmp/arkscope-portfolio-1-1-slice-1-base.txt)" -- \
  src/tools src/agents docs/design/ARKSCOPE_TOOL_CATALOG.md
```

Expected: the four `rg` commands produce zero matches and the tool/agent/catalog
boundary diff is empty. The exact-word raw-id gate deliberately permits the
redacted `broker_account_id_hash` identifier. Tests may name banned strings
only to enforce their absence.

Run an AST call-site gate proving `IBKRDataSource` in capture ownership is constructed exactly once, with `readonly=True` and `ibkr_client_id_for('portfolio_capture')`. Run a SQLite schema probe proving every observation FK delete action is `RESTRICT`/`NO ACTION` and no observation table has a DELETE method/route.

- [ ] **Step 3: Run the full frontend and no-PG gates**

Run:

```bash
npm --workspace apps/arkscope-web test
npm --workspace apps/arkscope-web run typecheck
npm --workspace apps/arkscope-web run build
python src/smoke/pg_unreachable_e2e.py
```

Expected: `42 files / 376 tests`, typecheck/build pass, smoke `ok: true`, all checks pass, and `pg_attempts: []`.

- [ ] **Step 4: Run visual/interaction checks**

Start a scheduler-disabled sidecar against a disposable profile DB and Vite on an unused 84xx port. Inspect Holdings at `1440x900`, `1024x768`, `961x768`, `959x768`, and `390x844` using fake/captured run data. Store screenshots under `/tmp`.

Verify:

1. schedule controls, current run, recent runs, and review diff never overlap;
2. long blocked/partial details wrap without covering neighboring cells;
3. financial and run tables own horizontal scrolling on narrow screens;
4. one and only one Portfolio schedule control surface is visible;
5. disabled periodic capture still leaves `立即同步` available;
6. state badges include icon and text, not color alone;
7. no raw broker account id appears in DOM/network response fixtures;
8. 961/959 introduces no new shell breakpoint or layout jump.

- [ ] **Step 5: Run canonical backend A/B with exact accounting**

At implementation-branch creation after plan review, record:

```bash
git rev-parse HEAD > /tmp/arkscope-portfolio-1-1-slice-1-base.txt
```

Compare virgin archives of that exact base and final tip under the same environment, sequential single-process full pytest. Acceptance:

- failure sets identical in both directions;
- pre-existing passed/skipped/warning/error behavior is identical;
- passed/collected delta equals exactly the new test ledger (`+71/-0` backend);
- frontend delta equals `+10/-0`;
- no generated DB/cache/build artifact enters either archive.

If the known TestClient/lifespan hang occurs in the implementation environment, preserve logs and stop short of claiming A/B PASS; reviewer canonical A/B remains mandatory.

- [ ] **Step 6: Run the single-sidecar live Gateway gate**

Shut down every other ArkScope sidecar first. Use the real provider config and profile DB, with one branch sidecar only:

1. record pre-state counts and latest canonical quantities;
2. trigger one manual capture and poll the run to terminal;
3. verify one connection used effective client id `base+70` and readonly mode;
4. verify selected account snapshot fields, complete position observations, current-day executions, and available commission reports were persisted;
5. trigger a second capture and prove executions/commissions are idempotent while run/account snapshots append;
6. verify `ibkr_review` produces a preview with zero canonical writes, then apply it and preserve position notes;
7. if a safe test account is `ibkr_auto`, verify only broker-owned fields update after observation commit; otherwise record the auto leg as test-only evidence rather than changing the user's sync mode;
8. disable periodic capture, prove manual still runs, re-enable at 15 minutes, and verify next due is from completion;
9. restart the sidecar and prove catch-up uses durable last success and stale running rows become interrupted;
10. inspect the new capture API, normal capture logs, capture DOM, agent tool payload, and trace for raw account-id leakage;
11. verify zero order API invocation and zero leftover owned event loop/session.

Do not manufacture a trade, correction, commission revision, or unmatched position change on the user's account. Those remain fake-backed tests unless a naturally occurring event appears.

- [ ] **Step 7: Mark review-ready and stop**

After automated and live gates:

1. Change this plan header/status note to `IMPLEMENTED FOR REVIEW`.
2. Record every RED reason, focused/full counts, static gates, screenshots, A/B evidence, live run ids/counts, and any naturally unverified edge.
3. Add a newest-first map entry with branch/tip and reviewer focus.
4. Commit only review-ready docs.
5. Stop. Do not merge, delete the worktree, mark the spec LIVE, or open Slice 2.

```bash
git add docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/plans/2026-07-13-portfolio-1-1-slice-1-capture-foundation.md
git commit -m "docs: mark portfolio capture review-ready"
```

---

## Stop Conditions

Stop and report rather than widening scope if any of these occurs:

1. IBKR cannot return a complete current position set distinguishable from failure.
2. Daily P&L requires storing an unfiltered account payload or an unbounded subscription.
3. Execution identity cannot be preserved by `execId`, or order grouping requires treating session-scoped `orderId` as stable.
4. Commission arrival requires mutating an execution row rather than appending a revision.
5. Observation persistence requires a DB transaction to remain open during Gateway I/O.
6. A failed/ambiguous position read would be interpreted as zero positions or close canonical rows.
7. `ibkr_review` requires a persisted pending-diff table rather than deriving from a captured run.
8. Manual financial mutation cannot roll back together with its journal event.
9. Capture needs a tool/registry/prompt/research-store import or leaks a raw broker account id.
10. Capture requires an order API, a non-readonly connection, or reuse of `holdings=+60`/future trading identity.
11. The UI needs account overview, performance curves, activity annotations, Flex import, or a second Settings scheduler to become usable.
12. The exact backend/frontend test ledger, no-PG smoke, canonical A/B, or live Gateway idempotence does not close.

## Review Handoff

Reviewer focus should be:

1. schema immutability/non-cascade and complete-zero representation;
2. correction/commission/unmatched idempotency;
3. manual mutation+journal transaction boundaries;
4. permission/provider/concurrency ordering before IBKR spend;
5. one connection, `+70`, readonly, worker-event-loop safety;
6. observation commit before canonical mutation and complete-leg-only apply;
7. derived review with no second Gateway call;
8. startup/manual cadence semantics and no tight retry;
9. redacted additive API and no Data Sources duplicate;
10. deliberate legacy compatibility repair: archived accounts stay archived
    and retain user-owned fields;
11. exact test accounting plus real Gateway evidence.

Implementation may begin only after this plan is reviewed. The recommended execution mode is subagent-driven development with a fresh implementation worktree and one review checkpoint per task; inline execution remains acceptable if the same RED/commit/review boundaries are preserved.
