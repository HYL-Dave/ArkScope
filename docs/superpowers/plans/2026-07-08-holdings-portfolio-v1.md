# Holdings + Portfolio V1 Implementation Plan

> **Status: PLAN FOR REVIEW 2026-07-08.** Implements
> `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:test-driven-development` and either
> `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
> Implement task-by-task, one commit per task, and stop at every stop-loss.

**Goal:** Add a first-class local portfolio/holdings model with manual positions,
read-only IBKR position sync, a desktop Holdings page, and one agent-readable local
holdings tool. Holdings is profile state, not market data, and lives in
`profile_state.db`.

**Non-goals:** order placement, trading automation, alerts, research-note linking,
advanced options risk modeling, multiple Gateway connection profiles, CSV import,
and automatic profile/stance changes from holdings.

---

## Design Decisions Locked By This Plan

1. **Storage authority:** holdings live in local `profile_state.db`. Remote PG and
   market-data SQLite files are never holdings authorities.
2. **IBKR connection authority:** v1 uses existing S-J provider config
   (`ibkr.host`, `ibkr.port`, guarded `ibkr.client_id`). Do not create a
   `broker_connections` table in this slice.
3. **Account model:** `portfolio_accounts` are local app objects. Fresh profiles get
   a Manual account. IBKR accounts discovered from Gateway become local accounts.
4. **Sync identity:** IBKR-backed positions are keyed by
   `(account_id, broker, broker_account_id_hash, broker_con_id)`, not symbol.
   Symbol is display metadata only. Manual positions use local ids until explicitly
   linked to a broker contract.
5. **Sync modes:** account-level `manual`, `ibkr_review`, `ibkr_auto`. Review mode
   creates inert diffs/proposals; auto mode writes broker-owned fields only.
6. **User-owned fields:** notes, thesis, tags, strategy bucket, target allocation,
   alert preferences, and research links are never overwritten by IBKR sync.
7. **Currency honesty:** totals must expose currency basis. Broker base-currency
   values may drive aggregate totals when IBKR supplies them; otherwise API/UI show
   per-currency subtotals instead of silently mixing currencies.
8. **Read-only IBKR:** holdings uses its own client-id domain and
   `IBKRDataSource(..., readonly=True)`. This slice must not call order APIs.
9. **Tool ledger discipline:** adding one holdings tool changes live registry
   count from 55 to 56 and bridge count from 56 to 57. Tool catalog and every
   ledger assertion must change in the same task.
10. **Frontend surface:** the existing `Holdings` nav key becomes enabled and
    renders a real page. Do not bury holdings under Settings.

---

## Files

Create:

- `src/portfolio_state.py`
- `src/portfolio_ibkr.py`
- `src/api/routes/portfolio.py`
- `src/tools/portfolio_holdings_tools.py`
- `apps/arkscope-web/src/Holdings.tsx`
- `apps/arkscope-web/src/Holdings.test.tsx`
- `tests/test_portfolio_state.py`
- `tests/test_portfolio_ibkr.py`
- `tests/test_portfolio_routes.py`
- `tests/test_portfolio_holdings_tools.py`

Modify:

- `data_sources/ibkr_client_id.py`
- `src/data_provider_config.py`
- `src/api/dependencies.py`
- `src/api/app.py`
- `src/tools/registry.py`
- `src/agents/openai/tools.py`
- `src/agents/anthropic/tools.py`
- `docs/design/ARKSCOPE_TOOL_CATALOG.md`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/App.tsx`
- `docs/design/PROJECT_PRIORITY_MAP.md`
- `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md`

Likely tests to update because one tool is added:

- `tests/test_api.py`
- `tests/test_tools.py`
- `tests/test_agents.py`
- `tests/test_subagent.py`
- `tests/test_memory_tools.py`
- `tests/test_sec_tools.py`
- `tests/test_portfolio_tools.py`
- `tests/test_analyst_tools.py`
- `tests/test_sa_tools.py`
- any new catalog parity test output if the registry/catalog gate reports drift.

---

## Stop-Loss Triggers

Stop and report before continuing if any of these happen:

- Any holdings code needs to call `placeOrder`, `cancelOrder`, `modifyOrder`,
  `exerciseOption`, `reqGlobalCancel`, or any order/execution API.
- IBKR position sync requires write-enabled Gateway assumptions.
- A proposed schema keys IBKR-backed positions by symbol only.
- A sync path overwrites user-owned fields.
- A route mutates holdings without `require_profile_state_write`.
- Provider-config missing is handled by falling back to `.env` or by guessing
  defaults outside the S-J runtime contract.
- Tool integration requires changing tool permission classes outside one
  read-only local holdings primitive.
- Frontend implementation needs a marketing/landing page instead of the actual
  Holdings work surface.

---

## Review Gates

Run these before asking for review:

1. **No order API:**
   `rg -n "\\.(placeOrder|cancelOrder|modifyOrder|exerciseOption)|reqGlobalCancel|bracketOrder|whatIfOrder" src/portfolio_state.py src/portfolio_ibkr.py src/api/routes/portfolio.py src/tools/portfolio_holdings_tools.py`
   must return no matches.
2. **No PG holdings authority:**
   `rg -n "psycopg2|postgres|DATABASE_URL|db_dsn" src/portfolio_state.py src/portfolio_ibkr.py src/api/routes/portfolio.py src/tools/portfolio_holdings_tools.py`
   must return no matches.
3. **No symbol-keyed IBKR identity:** route/store tests must prove an IBKR rename
   updates the same `broker_con_id` row rather than creating a delete+add diff.
4. **Provider-config missing:** route tests must assert the S-J shaped
   `provider_config_missing` refusal when IBKR host/port/client id are not
   configured.
5. **Tool catalog parity:** construct `create_default_registry().list_names()` and
   compare to backtick tool names in `ARKSCOPE_TOOL_CATALOG.md`; missing/extra
   names must be zero.
6. **Client-id band:** Settings provider-config tests must include `holdings=+60`
   and updated guard reason text; UI hint must show the new derived id.
7. **Fresh-profile smoke:** `python src/smoke/pg_unreachable_e2e.py` must stay
   green with `pg_attempts=[]`.
8. **Full A/B:** failure set identical. Passed-count delta must equal the new
   tests minus any intentionally removed tests. No head-only failures.

---

## Task 0: IBKR Client-ID Domain And Spec Status

**Purpose:** reserve a read-only IBKR connection identity before any sync code exists,
and remove stale Settings guard text.

**Files:**

- `data_sources/ibkr_client_id.py`
- `src/data_provider_config.py`
- `tests/test_data_provider_config.py`
- `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md`

- [ ] Step 1: Write/update failing tests.

Update `tests/test_data_provider_config.py::test_view_exposes_client_id_domains` so
it expects:

```python
assert [d["domain"] for d in doms] == [
    "manual", "options", "prices", "news", "iv", "quotes", "holdings",
]
assert [d["offset"] for d in doms] == [0, 10, 20, 30, 40, 50, 60]
assert [d["effective_client_id"] for d in doms] == [1, 11, 21, 31, 41, 51, 61]
assert doms[-1]["label"] == "持倉"
```

For the env-base variant, expect `[7, 17, 27, 37, 47, 57, 67]`.

Add a guard-reason assertion that the IBKR guarded field text mentions both
`quotes=+50` and `holdings=+60`.

Expected RED: holdings domain missing and guard reason stale.

- [ ] Step 2: Implement smallest domain change.

In `data_sources/ibkr_client_id.py`, add:

```python
"holdings": 60,  # read-only portfolio/position snapshots
```

and:

```python
"holdings": "持倉",
```

Update the module comment to record band pressure:

```text
quotes=+50, holdings=+60; if future trading/execution reserves +70, the app-managed
base must stay <= 29 to avoid the archived 100-999 legacy band.
```

In `src/data_provider_config.py`, update `guard_reason` to mention
`quotes=+50` and `holdings=+60`.

- [ ] Step 3: Verify.

Run:

```bash
pytest tests/test_data_provider_config.py
```

Commit:

```bash
git add data_sources/ibkr_client_id.py src/data_provider_config.py tests/test_data_provider_config.py docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md
git commit -m "feat: reserve ibkr holdings client id"
```

---

## Task 1: Local Portfolio Store

**Purpose:** create the durable local holdings authority with manual account support,
multi-account shape, conId identity, broker/user field separation, and honest currency
totals.

**Files:**

- `src/portfolio_state.py`
- `src/api/dependencies.py`
- `tests/test_portfolio_state.py`

- [ ] Step 1: Write failing store tests.

Create `tests/test_portfolio_state.py` with these required cases:

```python
def test_fresh_store_creates_manual_account(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    accounts = store.list_accounts()
    assert [a.label for a in accounts] == ["Manual"]
    assert accounts[0].broker == "manual"
    assert accounts[0].sync_mode == "manual"


def test_manual_position_round_trip_and_totals(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.ensure_manual_account()
    store.upsert_manual_position(
        account_id=account.id,
        symbol="NVDA",
        asset_class="stock",
        quantity=3,
        avg_cost=100,
        currency="USD",
        notes="long-term core",
    )
    snapshot = store.snapshot()
    assert snapshot.positions[0].symbol == "NVDA"
    assert snapshot.positions[0].notes == "long-term core"
    assert snapshot.totals.currency_basis == "per_currency"
    assert snapshot.totals.per_currency["USD"].quantity_positions == 1


def test_ibkr_position_identity_uses_conid_not_symbol(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account(
        broker="ibkr",
        broker_account_id="DU123",
        label="IBKR DU123",
        sync_mode="ibkr_auto",
        base_currency="USD",
    )
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1001, symbol="LC", quantity=5)],
        source="test",
    )
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=1001, symbol="HAPN", quantity=5)],
        source="test",
    )
    positions = store.list_positions(account_id=account.id)
    assert len(positions) == 1
    assert positions[0].broker_con_id == "1001"
    assert positions[0].symbol == "HAPN"


def test_broker_sync_does_not_overwrite_user_fields(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123")
    first = store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=2002, symbol="AAPL", quantity=1)],
        source="test",
    )[0]
    store.update_position_notes(first.id, notes="my thesis", tags=["core"])
    store.apply_broker_positions(
        account_id=account.id,
        positions=[broker_pos(con_id=2002, symbol="AAPL", quantity=2)],
        source="test",
    )
    row = store.get_position(first.id)
    assert row.quantity == 2
    assert row.notes == "my thesis"
    assert row.tags == ["core"]
```

Expected RED: module missing.

- [ ] Step 2: Implement schema and store.

Create `src/portfolio_state.py` with:

- `_SCHEMA` appended into the same SQLite file as profile state.
- Tables:
  - `portfolio_accounts`
  - `portfolio_positions`
  - `portfolio_position_notes`
  - `portfolio_sync_runs`
  - `portfolio_sync_diffs`
- Dataclasses:
  - `PortfolioAccount`
  - `PortfolioPosition`
  - `BrokerPosition`
  - `PortfolioTotals`
  - `PortfolioSnapshot`
  - `PortfolioSyncRun`
  - `PortfolioSyncDiff`
- Store:
  - `PortfolioStore(path)`
  - `ensure_manual_account()`
  - `list_accounts(include_archived=False)`
  - `upsert_broker_account(...)`
  - `list_positions(account_id=None, include_closed=False)`
  - `upsert_manual_position(...)`
  - `update_position_notes(...)`
  - `apply_broker_positions(account_id, positions, source)`
  - `preview_broker_positions(account_id, positions)`
  - `snapshot(account_id=None)`

Implementation constraints:

- Use a local generated id for every row.
- For IBKR-backed rows, enforce uniqueness on `(account_id, broker, broker_con_id)`.
- Store raw broker account id only if already visible in UI; also store a stable hash
  for joins/logging where account id should not be repeated.
- User-owned fields live in `portfolio_position_notes`, joined at read time.
- `PortfolioTotals.currency_basis` is `"broker_base"` only when every included
  broker position has compatible broker-supplied base-currency values; otherwise it
  is `"per_currency"`.

Add to `src/api/dependencies.py`:

```python
@lru_cache(maxsize=1)
def get_portfolio_store():
    from src.portfolio_state import PortfolioStore
    return PortfolioStore(_local_state_db_path())
```

- [ ] Step 3: Verify.

Run:

```bash
pytest tests/test_portfolio_state.py
python -m compileall src/portfolio_state.py
```

Commit:

```bash
git add src/portfolio_state.py src/api/dependencies.py tests/test_portfolio_state.py
git commit -m "feat: add local portfolio store"
```

---

## Task 2: Read-Only IBKR Snapshot And Sync Diff

**Purpose:** read positions/accounts from IBKR without order capability, convert them to
store-neutral broker snapshots, and support review/auto sync modes.

**Files:**

- `src/portfolio_ibkr.py`
- `tests/test_portfolio_ibkr.py`

- [ ] Step 1: Write failing adapter/sync tests.

Create `tests/test_portfolio_ibkr.py`:

```python
def test_reader_uses_holdings_client_id_and_readonly(monkeypatch):
    captured = {}

    class FakeSource:
        def __init__(self, *, client_id, readonly):
            captured["client_id"] = client_id
            captured["readonly"] = readonly
        def connect(self): captured["connected"] = True
        def disconnect(self): captured["disconnected"] = True

    monkeypatch.setenv("IBKR_CLIENT_ID", "1")
    monkeypatch.setattr(portfolio_ibkr, "IBKRDataSource", FakeSource)
    monkeypatch.setattr(portfolio_ibkr, "_read_connected_ibkr", lambda source: BrokerSnapshot(accounts=[], positions=[]))

    read_ibkr_portfolio_snapshot()
    assert captured == {
        "client_id": 61,
        "readonly": True,
        "connected": True,
        "disconnected": True,
    }


def test_review_mode_returns_diff_without_writing(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123", sync_mode="ibkr_review")
    diff = preview_or_apply_ibkr_snapshot(store, snapshot_with_pos(account="DU123", con_id=1), apply=False)
    assert diff.changes[0].kind == "add"
    assert store.list_positions(account_id=account.id) == []


def test_auto_mode_applies_broker_owned_fields_only(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    account = store.upsert_broker_account("ibkr", "DU123", "IBKR DU123", sync_mode="ibkr_auto")
    preview_or_apply_ibkr_snapshot(store, snapshot_with_pos(account="DU123", con_id=1, quantity=1), apply=True)
    row = store.list_positions(account_id=account.id)[0]
    store.update_position_notes(row.id, notes="do not touch")
    preview_or_apply_ibkr_snapshot(store, snapshot_with_pos(account="DU123", con_id=1, quantity=2), apply=True)
    row = store.get_position(row.id)
    assert row.quantity == 2
    assert row.notes == "do not touch"
```

Expected RED: module missing.

- [ ] Step 2: Implement adapter seam.

Create `src/portfolio_ibkr.py`:

- `BrokerAccountSnapshot`
- `BrokerPositionSnapshot`
- `BrokerSnapshot`
- `read_ibkr_portfolio_snapshot()`
- `_read_connected_ibkr(source)`
- `preview_or_apply_ibkr_snapshot(store, snapshot, *, apply: bool)`

`read_ibkr_portfolio_snapshot()` must mirror current-quote discipline:

```python
source = IBKRDataSource(client_id=ibkr_client_id_for("holdings"), readonly=True)
try:
    source.connect()
    return _read_connected_ibkr(source)
finally:
    source.disconnect()
```

The connected reader may use the underlying ib_insync session to call:

- `positions()`
- `portfolio()`
- `accountSummary()`

Do not call any order methods. If exact ib_insync row shapes are awkward, normalize
through small private helpers and pin them with fake object tests.

Provider-config behavior:

- If S-J runtime marks provider setup required, route layer returns
  `provider_config_missing`; the adapter should not invent fallback config.
- The adapter itself may raise a structured `IBKRHoldingsUnavailable` for connection
  failures; routes convert it to `503`.

- [ ] Step 3: Static no-order gate.

Run:

```bash
rg -n "\\.(placeOrder|cancelOrder|modifyOrder|exerciseOption)|reqGlobalCancel|bracketOrder|whatIfOrder" src/portfolio_ibkr.py
```

Expected: no output.

- [ ] Step 4: Verify.

Run:

```bash
pytest tests/test_portfolio_ibkr.py
python -m compileall src/portfolio_ibkr.py
```

Commit:

```bash
git add src/portfolio_ibkr.py tests/test_portfolio_ibkr.py
git commit -m "feat: add read-only ibkr portfolio sync"
```

---

## Task 3: Portfolio API Routes

**Purpose:** expose holdings to the desktop app and make all mutations explicit
profile-state writes.

**Files:**

- `src/api/routes/portfolio.py`
- `src/api/app.py`
- `tests/test_portfolio_routes.py`

- [ ] Step 1: Write failing route tests.

Create `tests/test_portfolio_routes.py` using handler-direct tests plus one real app
mount test:

```python
def test_portfolio_router_mounts_on_real_app():
    from src.api.app import create_app
    paths = {getattr(route, "path", None) for route in create_app().routes}
    assert "/portfolio" in paths
    assert "/portfolio/positions" in paths
    assert "/portfolio/ibkr/preview" in paths


def test_get_portfolio_returns_manual_account_for_fresh_profile(tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    out = routes.get_portfolio(store=store)
    assert out["accounts"][0]["label"] == "Manual"
    assert out["totals"]["currency_basis"] == "per_currency"


def test_manual_position_mutation_requires_profile_state_write(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail)))
    store = PortfolioStore(tmp_path / "profile_state.db")
    body = routes.ManualPositionBody(account_id=store.ensure_manual_account().id, symbol="NVDA", quantity=1)
    routes.upsert_manual_position(body, store=store)
    assert calls == [("portfolio_position_write", {"source": "manual"})]


def test_ibkr_preview_does_not_write(monkeypatch, tmp_path):
    store = PortfolioStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(routes, "read_ibkr_portfolio_snapshot", lambda: snapshot_with_pos())
    out = routes.preview_ibkr_sync(store=store)
    assert out["changes"]
    assert store.list_positions() == []


def test_ibkr_apply_requires_profile_state_write(monkeypatch, tmp_path):
    calls = []
    store = PortfolioStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(routes, "read_ibkr_portfolio_snapshot", lambda: snapshot_with_pos())
    monkeypatch.setattr(routes, "require_profile_state_write", lambda action, detail=None: calls.append((action, detail)))
    routes.apply_ibkr_sync(store=store)
    assert calls == [("portfolio_ibkr_sync", {"mode": "apply"})]
```

Add a provider-config missing test that monkeypatches the same runtime predicate used
by other provider routes and expects:

```python
assert exc.value.status_code == 503
assert exc.value.detail["code"] == "provider_config_missing"
```

- [ ] Step 2: Implement routes.

Create `src/api/routes/portfolio.py`:

- `router = APIRouter(prefix="/portfolio", tags=["portfolio"])`
- `GET /portfolio`
- `GET /portfolio/accounts`
- `POST /portfolio/accounts`
- `PATCH /portfolio/accounts/{account_id}`
- `GET /portfolio/positions`
- `POST /portfolio/positions`
- `PATCH /portfolio/positions/{position_id}`
- `POST /portfolio/ibkr/preview`
- `POST /portfolio/ibkr/apply`

Rules:

- Use `Depends(get_portfolio_store)`.
- Mutations call `require_profile_state_write`.
- IBKR preview never writes.
- IBKR apply calls write gate once before store mutation.
- Do not expose account hashes as the primary display label.
- All responses include `currency_basis`.

In `src/api/app.py`, include the router.

- [ ] Step 3: Verify.

Run:

```bash
pytest tests/test_portfolio_routes.py
python -m compileall src/api/routes/portfolio.py
```

Commit:

```bash
git add src/api/routes/portfolio.py src/api/app.py tests/test_portfolio_routes.py
git commit -m "feat: add portfolio api routes"
```

---

## Task 4: Desktop Holdings Page

**Purpose:** turn the existing disabled `Holdings` nav item into the actual portfolio
surface.

**Files:**

- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/App.tsx`
- `apps/arkscope-web/src/Holdings.tsx`
- `apps/arkscope-web/src/Holdings.test.tsx`

- [ ] Step 1: Write failing frontend tests.

Create `apps/arkscope-web/src/Holdings.test.tsx`:

```tsx
it("renders accounts, positions, and currency basis", async () => {
  stubFetch({
    accounts: [{ id: 1, label: "Manual", broker: "manual", sync_mode: "manual", base_currency: "USD" }],
    positions: [{ id: 10, account_id: 1, symbol: "NVDA", asset_class: "stock", quantity: 3, currency: "USD", notes: "core" }],
    totals: { currency_basis: "per_currency", per_currency: { USD: { market_value: null, position_count: 1 } } },
  });
  const host = render(<HoldingsView />);
  await screen.findByText("Manual");
  expect(host.textContent).toContain("NVDA");
  expect(host.textContent).toContain("per-currency");
});

it("can add a manual holding", async () => {
  const calls: unknown[] = [];
  stubFetchWithPostCapture(calls);
  render(<HoldingsView />);
  await user.type(screen.getByLabelText("Ticker"), "AAPL");
  await user.type(screen.getByLabelText("Quantity"), "2");
  await user.click(screen.getByRole("button", { name: "新增持倉" }));
  expect(calls).toContainEqual(expect.objectContaining({ symbol: "AAPL", quantity: 2 }));
});

it("shows ibkr preview as review before applying", async () => {
  stubFetchWithIbkrPreview({ changes: [{ kind: "add", symbol: "MSFT", quantity: 1 }] });
  render(<HoldingsView />);
  await user.click(screen.getByRole("button", { name: "預覽 IBKR 同步" }));
  expect(await screen.findByText("MSFT")).toBeTruthy();
  expect(screen.getByRole("button", { name: "套用同步" })).toBeTruthy();
});
```

Add an `App.tsx` test or update an existing one so `Holdings` is enabled and renders
`HoldingsView`.

Expected RED: API helpers/component missing and nav disabled.

- [ ] Step 2: Implement API helpers and UI.

In `api.ts`, add DTOs and helpers:

- `PortfolioAccount`
- `PortfolioPosition`
- `PortfolioTotals`
- `PortfolioSnapshot`
- `PortfolioSyncPreview`
- `getPortfolio()`
- `createManualPosition()`
- `updateManualPosition()`
- `previewIbkrPortfolioSync()`
- `applyIbkrPortfolioSync()`

Create `Holdings.tsx`:

- Dense workbench page, not a landing page.
- Account filter/segmented control.
- Positions table with asset class, quantity, cost/market value when present,
  P&L when present, currency, source/sync status, and notes.
- Manual add/edit form.
- IBKR preview/apply controls with explicit review state.
- Currency basis banner when totals are per-currency or broker-base.
- Empty state for fresh profile: Manual account + no positions.

In `App.tsx`:

- import `HoldingsView`;
- add `Holdings` to `ENABLED`;
- render `HoldingsView` for `view === "Holdings"`.

- [ ] Step 3: Verify.

Run:

```bash
cd apps/arkscope-web
npm test -- Holdings.test.tsx
npm run typecheck
npm run build
```

Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/App.tsx apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx
git commit -m "feat: add holdings desktop page"
```

---

## Task 5: Agent Tool And Catalog Ledger

**Purpose:** give agents a controlled local holdings read primitive without letting
them mutate holdings or call broker APIs.

**Files:**

- `src/tools/portfolio_holdings_tools.py`
- `src/tools/registry.py`
- `src/agents/openai/tools.py`
- `src/agents/anthropic/tools.py`
- `docs/design/ARKSCOPE_TOOL_CATALOG.md`
- tests listed in the ledger section.

- [ ] Step 1: Write failing tool tests.

Create `tests/test_portfolio_holdings_tools.py`:

```python
def test_get_portfolio_holdings_reads_local_store(tmp_path, monkeypatch):
    db = tmp_path / "profile_state.db"
    store = PortfolioStore(db)
    account = store.ensure_manual_account()
    store.upsert_manual_position(account_id=account.id, symbol="NVDA", quantity=2, currency="USD")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db))

    out = get_portfolio_holdings()

    assert out["accounts"][0]["label"] == "Manual"
    assert out["positions"][0]["symbol"] == "NVDA"
    assert out["totals"]["currency_basis"] == "per_currency"


def test_get_portfolio_holdings_never_touches_ibkr(monkeypatch):
    monkeypatch.setattr("src.portfolio_ibkr.read_ibkr_portfolio_snapshot", lambda: (_ for _ in ()).throw(AssertionError("IBKR touched")))
    out = get_portfolio_holdings()
    assert out["source"] == "local_profile"
```

Update registry tests so `get_portfolio_holdings` is present.

Expected RED: tool missing and counts stale.

- [ ] Step 2: Implement read-only tool.

Create `src/tools/portfolio_holdings_tools.py`:

```python
def get_portfolio_holdings(account_id: int | None = None, include_closed: bool = False) -> dict:
    """Read local portfolio holdings from profile_state.db.

    Does not call IBKR, does not sync, and does not mutate local state.
    """
```

It should open `PortfolioStore` using `ARKSCOPE_PROFILE_DB` or the same default path as
`_local_state_db_path()` without importing API dependencies.

Register it in `ToolRegistry` under the portfolio category.

Bridge/catalog discipline:

- `ToolRegistry` count: 55 -> 56.
- Agent bridge count including `delegate_to_subagent`: 56 -> 57.
- Update Anthropic/OpenAI tool schemas.
- Update `docs/design/ARKSCOPE_TOOL_CATALOG.md`:
  - count 55 -> 56;
  - bridge count 56 -> 57;
  - add a row for `get_portfolio_holdings`;
  - update roll-up total.

Ledger tests to update/run:

```bash
pytest tests/test_tools.py tests/test_api.py tests/test_agents.py tests/test_subagent.py \
  tests/test_memory_tools.py tests/test_sec_tools.py tests/test_portfolio_tools.py \
  tests/test_analyst_tools.py tests/test_sa_tools.py tests/test_portfolio_holdings_tools.py
```

Before committing, run:

```bash
python - <<'PY'
import re
from pathlib import Path
from src.tools.registry import create_default_registry
names = set(create_default_registry().list_names())
catalog = Path("docs/design/ARKSCOPE_TOOL_CATALOG.md").read_text()
catalog_names = set(re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", catalog))
missing = sorted(names - catalog_names)
print("missing", missing)
assert not missing
PY
```

- [ ] Step 3: Verify no accidental broker access.

Run:

```bash
rg -n "IBKRDataSource|read_ibkr_portfolio_snapshot|placeOrder|cancelOrder|modifyOrder|exerciseOption" src/tools/portfolio_holdings_tools.py
```

Expected: no output.

Commit:

```bash
git add src/tools/portfolio_holdings_tools.py src/tools/registry.py src/agents/openai/tools.py src/agents/anthropic/tools.py docs/design/ARKSCOPE_TOOL_CATALOG.md tests/test_*.py
git commit -m "feat: expose local portfolio holdings tool"
```

---

## Task 6: Final Gates, Smoke, Docs Closeout

**Purpose:** prove the slice is safe in fresh profiles, PG-unreachable environments,
desktop frontend, and tool ledger.

- [ ] Step 1: Focused backend.

Run:

```bash
pytest tests/test_data_provider_config.py tests/test_portfolio_state.py tests/test_portfolio_ibkr.py \
  tests/test_portfolio_routes.py tests/test_portfolio_holdings_tools.py tests/test_tools.py \
  tests/test_api.py tests/test_agents.py tests/test_subagent.py tests/test_memory_tools.py \
  tests/test_sec_tools.py tests/test_portfolio_tools.py tests/test_analyst_tools.py tests/test_sa_tools.py
```

- [ ] Step 2: Frontend.

Run:

```bash
cd apps/arkscope-web
npm test -- Holdings.test.tsx
npm run typecheck
npm run build
```

- [ ] Step 3: Static gates.

Run:

```bash
rg -n "\\.(placeOrder|cancelOrder|modifyOrder|exerciseOption)|reqGlobalCancel|bracketOrder|whatIfOrder" src/portfolio_state.py src/portfolio_ibkr.py src/api/routes/portfolio.py src/tools/portfolio_holdings_tools.py
rg -n "psycopg2|postgres|DATABASE_URL|db_dsn" src/portfolio_state.py src/portfolio_ibkr.py src/api/routes/portfolio.py src/tools/portfolio_holdings_tools.py
python src/smoke/pg_unreachable_e2e.py
```

First two commands must print no matches. Smoke must report `ok:true` and
`pg_attempts:[]`.

- [ ] Step 4: Full A/B.

Use virgin worktrees. Acceptance:

- failure set identical;
- no head-only failures;
- passed delta equals the net new tests;
- skips/errors/warnings explained if changed.

- [ ] Step 5: Docs closeout.

Update:

- this plan header to `IMPLEMENTED FOR REVIEW` or `LIVE COMPLETE` depending on live
  verification state;
- `docs/design/PROJECT_PRIORITY_MAP.md` §10 newest entry with implementation evidence;
- spec status line if live complete;
- any memory/status docs used by this repo's normal closeout flow.

Commit:

```bash
git add docs/superpowers/plans/2026-07-08-holdings-portfolio-v1.md docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md
git commit -m "docs: close holdings portfolio v1"
```

---

## Live Verification After Merge

Do this only after review/merge and after restarting the sidecar so the new routes/tools
are loaded:

1. Open the app and navigate to `持倉`.
2. Fresh profile shows Manual account and empty holdings.
3. Add a manual NVDA or AAPL holding; refresh page; row persists.
4. With IBKR Gateway running, run IBKR preview; verify discovered accounts/positions
   are shown as review changes.
5. Apply only after explicitly approving; user notes survive a second sync.
6. Ask the agent for local holdings summary; trace shows `get_portfolio_holdings`, not
   `get_portfolio_analysis` with ad hoc JSON and not IBKR access.

