# Holdings Row Actions Implementation Plan

> **Status: IMPLEMENTED FOR REVIEW 2026-07-10.** Implements the row-action addendum in
> `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md`. Branch
> `claude/holdings-row-actions`, three TDD commits (store semantics / route contracts /
> inline editor) + this docs commit. Evidence: backend focused 47 passed (+17 new),
> frontend 26 files / 241 tests + typecheck + build, no-hard-delete gate zero matches,
> PG-unreachable smoke `ok:true` `pg_attempts:[]`. Full virgin A/B + user review + live
> verification remain before merge; live mutation waits for explicit merge approval.

**Goal:** Complete the Holdings position lifecycle: every position can edit its
user-owned notes/thesis/tags, manual positions can edit their financial fields and be
soft-closed, closed rows remain inspectable, and IBKR-owned fields stay structurally
read-only.

**Non-goals:** hard delete, restore/reopen controls, tax lots, transaction history,
strategy-bucket/target-allocation UI, broker-position manual close, IBKR financial-field
overrides, order placement, alerts, or changes to the holdings agent tool.

---

## Current Grounding

1. `src/api/routes/portfolio.py::PositionNotesBody` and
   `PATCH /portfolio/positions/{position_id}` already expose notes, thesis, tags,
   strategy bucket, and target allocation. The route is gated by
   `require_profile_state_write`, but the web client has no helper and Holdings has no
   edit affordance.
2. `src/portfolio_state.py::update_position_notes()` updates user-owned fields and IBKR
   sync preserves those fields through the separate `portfolio_position_notes` table.
3. `PortfolioStore.upsert_manual_position()` is insert-only despite its name. No store
   method or route edits manual symbol/asset class/quantity/average cost/currency.
4. `PortfolioStore.close_position()` soft-closes a row, but no route or UI calls it. It
   currently does not reject broker-backed rows.
5. `GET /portfolio/positions` already accepts `include_closed`; the main
   `GET /portfolio` snapshot route and `getPortfolio()` frontend helper do not expose
   that flag.
6. `PortfolioStore.apply_broker_positions()` and the IBKR diff path own broker closure
   and reopening. A manually closed IBKR row would be reopened on the next complete
   snapshot, so the UI must never offer that action.
7. The current Holdings page renders notes but only accepts them during manual creation.
   The frontend has no position PATCH/DELETE helpers or row-action controls.

---

## Decisions Locked

1. **One atomic PATCH:** retain `PATCH /portfolio/positions/{position_id}` as the single
   row-update endpoint. It accepts user-owned fields for every row and manual financial
   fields only for manual rows. Do not split one Save operation across two requests.
2. **User-owned v1 editor:** the UI exposes `notes`, `thesis`, and `tags` for every
   position. `strategy_bucket` and `target_allocation` remain API-only in this slice.
3. **Explicit-null contract:** route parsing uses `model_fields_set`, not truthiness or
   plain optional defaults. Omitted means unchanged. Explicit `null` clears nullable
   fields such as `avg_cost`, `strategy_bucket`, and `target_allocation`. Preserve the
   existing non-null user-field convention: `None` for notes/thesis/tags means no
   change, while `""` clears notes/thesis and `[]` clears tags.
4. **Manual-only financial fields:** `symbol`, `asset_class`, `quantity`, `avg_cost`, and
   `currency` may be changed only when `broker == "manual"`. The server, not merely the
   UI, rejects the same fields on broker-backed rows with HTTP 400 and machine code
   `broker_position_managed_by_sync`. Use a dedicated store exception for this ownership
   violation; do not infer machine codes by matching exception text.
5. **Quantity semantics:** manual quantity may be positive or negative but not zero.
   Closing is an explicit action; quantity zero must not silently mean close.
6. **Soft-close API:** `DELETE /portfolio/positions/{position_id}` means manual-only
   soft-close. It preserves the row and all user-owned fields. Repeating it on an already
   closed manual row is idempotent. Missing rows return 404. IBKR rows return HTTP 400
   `broker_position_managed_by_sync`.
7. **No IBKR close button:** IBKR rows expose Edit user fields only. No disabled or
   decorative close button is rendered.
8. **Closed-row honesty:** `GET /portfolio?include_closed=true` includes closed rows.
   Holdings gets one checkbox for this view; closed rows display a clear status and no
   second close action. Closed manual rows may still correct their historical fields;
   editing does not reopen them. Restore is deferred.
9. **No hard delete:** this slice executes no SQL `DELETE` against portfolio positions or
   notes.
10. **Mutation gate:** PATCH and DELETE call `require_profile_state_write` before any
    mutation. No local write bypass is introduced.
11. **No ledger blast radius:** no agent tool, registry, bridge, prompt, or catalog count
    changes belong in this slice.

### Machine errors

- missing position: `404 {"code":"portfolio_position_not_found", ...}`;
- broker field edit or broker close: `400 {"code":"broker_position_managed_by_sync", ...}`;
- invalid manual payload: `400 {"code":"invalid_portfolio_position", "detail":...}`.

---

## Files

Modify:

- `src/portfolio_state.py`
- `src/api/routes/portfolio.py`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/Holdings.tsx`
- `apps/arkscope-web/src/Holdings.test.tsx`
- `tests/test_portfolio_state.py`
- `tests/test_portfolio_routes.py`
- `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md`
- `docs/superpowers/plans/2026-07-10-holdings-row-actions.md`
- `docs/design/PROJECT_PRIORITY_MAP.md`

No new runtime module or database table is expected.

---

## Stop-Loss Triggers

Stop and report before continuing if:

- an IBKR row can be manually closed or its broker-owned fields can be changed;
- the implementation needs hard delete to satisfy the UI;
- an IBKR sync overwrites notes, thesis, or tags after this change;
- an omitted field is treated as a clear, or an explicit null cannot clear a nullable
  field;
- closing a manual row makes its notes/thesis/tags inaccessible;
- the UI needs a second update request to complete one Save action;
- any mutation route lacks `require_profile_state_write`;
- the work touches order APIs, IBKR connection behavior, tool registry counts, research
  prompts, or profile personalization;
- implementation requires a schema migration rather than using existing columns.

---

## Review Gates

1. **Broker ownership:** a route test must send every manual financial field to an IBKR
   row and receive `broker_position_managed_by_sync`; the stored row is byte-equivalent
   before/after.
2. **No broker close:** store + route tests prove an IBKR row cannot be manually closed.
3. **Explicit null:** tests prove omitted `avg_cost` is preserved and explicit null clears
   it. API-only nullable user fields must follow the same rule.
4. **Sync survival:** edit notes/thesis/tags on an IBKR position, apply a second broker
   snapshot, and assert all user fields survive.
5. **Soft-close visibility:** closing a manual row hides it by default, shows it with
   `include_closed=true`, and preserves user-owned fields.
6. **No hard delete:** static scan over the changed holdings store must show no new SQL
   delete for position/notes tables.
7. **Permission gate:** mutation tests pin `portfolio_position_write` for PATCH and DELETE.
8. **Frontend shape:** IBKR editor has only notes/thesis/tags; manual editor also has the
   five manual financial fields and close action; closed toggle restores visibility.
9. **Frontend gates:** Holdings tests, full Vitest suite, TypeScript, and production build
   all pass.
10. **Backend gates:** focused holdings suites and PG-unreachable smoke pass with
    `pg_attempts=[]`.
11. **Full A/B:** failure sets are identical with zero head-only entries. Passed-count
    delta equals exactly the new backend tests; frontend tests are accounted separately.

---

## Task 1: Store-Level Position Updates And Manual Close

**Purpose:** make broker/user ownership enforceable below the route layer.

**Files:**

- Modify `tests/test_portfolio_state.py`
- Modify `tests/test_portfolio_ibkr.py`
- Modify `src/portfolio_state.py`

### Step 1: Write RED tests

Add these named cases:

```python
def test_update_manual_position_changes_financial_and_user_fields(tmp_path): ...
def test_update_manual_position_explicit_null_clears_avg_cost(tmp_path): ...
def test_update_broker_position_allows_user_fields(tmp_path): ...
def test_update_broker_position_rejects_manual_fields_without_partial_write(tmp_path): ...
def test_manual_soft_close_preserves_user_fields_and_is_visible_when_requested(tmp_path): ...
def test_broker_position_cannot_be_manually_closed(tmp_path): ...
def test_nullable_user_fields_distinguish_omitted_from_explicit_null(tmp_path): ...
```

Required assertions:

- manual symbol is normalized uppercase and currency uppercase;
- positive and negative non-zero quantities work; zero raises `ValueError`;
- omitted `avg_cost` preserves its current value; explicit null clears it;
- notes/thesis/tags update on both manual and IBKR rows;
- any manual financial-field key on an IBKR row raises before any write;
- soft-close sets `closed_at`, keeps notes/thesis/tags, disappears from default reads,
  and appears with `include_closed=True`;
- `close_position()` rejects broker-backed rows;
- omitted `strategy_bucket` / `target_allocation` preserve values while explicit null
  clears them.

Extend the existing IBKR sync-survival test in `tests/test_portfolio_ibkr.py` so notes,
thesis, and tags all survive a subsequent broker snapshot update.

Run:

```bash
pytest tests/test_portfolio_state.py -q
```

Expected RED: no unified update method, nullable clear semantics are missing, and broker
close is currently allowed.

### Step 2: Implement one transactional update method

Add a store method such as:

```python
def update_position(
    self,
    position_id: int,
    *,
    fields: dict[str, Any],
) -> PortfolioPosition:
    ...
```

Add `BrokerPositionManagedBySync(ValueError)` as the typed ownership failure used by
both manual-field updates and manual close attempts.

Implementation rules:

- load the row inside the same SQLite transaction;
- partition keys into user-owned and manual-financial sets;
- reject unknown keys;
- reject any manual-financial key when `broker != "manual"` before updating either
  table;
- validate symbol, quantity, currency, and numeric values;
- require finite non-zero quantity, non-empty normalized symbol/currency/asset class,
  and `avg_cost` either null or a finite non-negative number;
- update `portfolio_positions` and `portfolio_position_notes` atomically;
- use key presence in `fields` as the omitted-vs-explicit-null authority;
- normalize `None` notes/thesis/tags to no-change while preserving empty-string/list
  clears; explicit null remains a real clear for nullable average cost, strategy bucket,
  and target allocation;
- keep `update_position_notes()` as a compatibility wrapper for existing tests/callers,
  preserving its old `None means unchanged` call contract.

Tighten `close_position()`:

- fetch first;
- reject `broker != "manual"`;
- preserve existing note rows;
- return the already-closed row unchanged when called repeatedly.

### Step 3: Verify and commit

```bash
pytest tests/test_portfolio_state.py tests/test_portfolio_ibkr.py -q
python -m compileall -q src/portfolio_state.py
git diff --check
```

Commit:

```bash
git add src/portfolio_state.py tests/test_portfolio_state.py tests/test_portfolio_ibkr.py
git commit -m "feat: add holdings row update semantics"
```

---

## Task 2: Route Contracts For Update, Close, And Closed Visibility

**Purpose:** expose the store contract through guarded, structured API behavior.

**Files:**

- Modify `tests/test_portfolio_routes.py`
- Modify `src/api/routes/portfolio.py`

### Step 1: Write RED route tests

Add these named cases:

```python
def test_patch_position_updates_manual_and_user_fields_atomically(...): ...
def test_patch_position_explicit_null_clears_avg_cost(...): ...
def test_patch_ibkr_position_rejects_manual_fields_without_partial_note_write(...): ...
def test_patch_ibkr_position_updates_user_fields(...): ...
def test_delete_manual_position_soft_closes_and_requires_write_gate(...): ...
def test_delete_ibkr_position_returns_managed_by_sync(...): ...
def test_get_portfolio_include_closed_threads_to_snapshot(...): ...
```

Also preserve the existing missing-position 404 test.

RED must prove:

- `PositionNotesBody` has no manual fields;
- explicit null is currently collapsed into no-change;
- DELETE route does not exist;
- main portfolio snapshot does not accept `include_closed`.

### Step 2: Replace the PATCH body with presence-aware updates

Define `PositionUpdateBody` with:

- user fields: notes, thesis, tags, strategy bucket, target allocation;
- manual fields: symbol, asset class, quantity, average cost, currency.

Add a method returning only explicitly supplied fields:

```python
def updates(self) -> dict[str, Any]:
    return {
        key: value
        for key, value in self.model_dump().items()
        if key in self.model_fields_set
    }
```

The PATCH handler calls `require_profile_state_write` once, then the transactional store
update. Map `KeyError` to 404, `BrokerPositionManagedBySync` to
`broker_position_managed_by_sync`, and ordinary validation `ValueError` to
`invalid_portfolio_position`. Ensure a broker-field rejection cannot still write notes
from the same payload.

### Step 3: Add manual-only soft-close and closed snapshot flag

Add:

```python
@router.delete("/positions/{position_id}")
def close_manual_position(...): ...
```

The route is permission-gated and calls the tightened store method. It never executes a
SQL hard delete.

Extend:

```python
@router.get("")
def get_portfolio(include_closed: bool = False, ...):
    return _to_json(store.snapshot(include_closed=include_closed))
```

### Step 4: Verify and commit

```bash
pytest tests/test_portfolio_routes.py tests/test_portfolio_state.py tests/test_portfolio_ibkr.py -q
python -m compileall -q src/api/routes/portfolio.py src/portfolio_state.py
git diff --check
```

Commit:

```bash
git add src/api/routes/portfolio.py src/portfolio_state.py tests/test_portfolio_routes.py tests/test_portfolio_state.py tests/test_portfolio_ibkr.py
git commit -m "feat: expose holdings row actions"
```

---

## Task 3: Holdings Inline Editor And Closed-Row View

**Purpose:** make the backend capability usable without blurring manual and broker
authority.

**Files:**

- Modify `apps/arkscope-web/src/api.ts`
- Modify `apps/arkscope-web/src/Holdings.tsx`
- Modify `apps/arkscope-web/src/Holdings.test.tsx`

### Step 1: Write RED frontend tests

Use the file's existing `createRoot` / `act` / `stubFetch` harness. Do not introduce
Testing Library or a new UI dependency.

Add these named cases:

```typescript
it("edits notes thesis and tags on an ibkr position without broker fields", async () => { ... });
it("edits manual financial and user fields in one patch", async () => { ... });
it("clears manual average cost with explicit null", async () => { ... });
it("soft closes a manual row after confirmation", async () => { ... });
it("shows closed rows when include closed is enabled", async () => { ... });
it("does not render a close action for ibkr rows", async () => { ... });
```

Required payload assertions:

- IBKR PATCH contains only notes/thesis/tags;
- manual PATCH includes changed manual fields and user fields in one body;
- blank average-cost input serializes as `avg_cost: null`, not omission or zero;
- close uses DELETE only after `window.confirm`;
- include-closed reloads `/portfolio?include_closed=true`;
- IBKR row has no close control in the DOM.

### Step 2: Add API helpers

Extend `PortfolioPosition` with the user-owned fields consumed by the editor, including
`thesis` and `tags`. Define one `PositionUpdate` payload type containing the three UI
user fields plus the five optional manual fields. Widen the Holdings test's
`PortfolioApiResponse` union so PATCH and DELETE response shapes are type-correct.

Add:

```typescript
export function getPortfolio(includeClosed = false): Promise<PortfolioSnapshot>;
export function updatePortfolioPosition(positionId: number, body: PositionUpdate): Promise<PortfolioPosition>;
export function closePortfolioPosition(positionId: number): Promise<PortfolioPosition>;
```

Keep `createManualPosition()` unchanged.

### Step 3: Build the inline row editor

Use one expanded table row below the selected position, not nested cards or a new modal
framework.

- all rows: Notes, Thesis, comma-separated Tags;
- manual rows only: Symbol, Asset Class, Quantity, Avg Cost, Currency;
- Save and Cancel commands;
- manual active rows only: Close command with confirmation;
- IBKR rows: visible broker/synced badge, no manual fields, no close command;
- closed rows: visible `Closed` status; editing remains available, but no close command;
- one include-closed checkbox in the Positions section header.

On successful PATCH/DELETE, reload the snapshot and close the editor. Errors stay on the
existing page error surface. Do not mutate the displayed row optimistically before the
server confirms.

### Step 4: Verify and commit

```bash
cd apps/arkscope-web
npm test -- Holdings.test.tsx
npm test
npm run typecheck
npm run build
```

Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx
git commit -m "feat: add holdings row actions"
```

---

## Task 4: Final Gates, A/B, Live Verification, And Closeout

**Files:**

- Modify `docs/superpowers/plans/2026-07-10-holdings-row-actions.md`
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`
- Optionally update the parent Holdings V1 plan header after its remaining live checks
  are complete

### Step 1: Focused backend and static gates

```bash
pytest tests/test_portfolio_state.py tests/test_portfolio_routes.py \
  tests/test_portfolio_ibkr.py tests/test_portfolio_holdings_tools.py -q
python -m compileall -q src/portfolio_state.py src/api/routes/portfolio.py
rg -n "DELETE FROM portfolio_(positions|position_notes)" src/portfolio_state.py
```

The final `rg` must return no matches.

### Step 2: Frontend gates

```bash
cd apps/arkscope-web
npm test
npm run typecheck
npm run build
```

### Step 3: PG-unreachable smoke

```bash
python src/smoke/pg_unreachable_e2e.py
```

Expected: `ok:true`, `pg_attempts:[]`.

### Step 4: Full virgin A/B

Compare implementation base against final tip. Acceptance:

- failure sets identical;
- zero head-only failures;
- backend passed delta exactly equals new backend tests;
- skips, warnings, and errors are accounted;
- frontend suite remains independently green.

### Step 5: Live UI verification

1. Open Holdings with an applied IBKR account.
2. Edit an IBKR row's note/thesis/tags and save; verify no broker fields or close action
   are present.
3. Preview and apply a second IBKR sync; verify those user fields survive.
4. Add a manual position, edit quantity/average cost/currency and clear average cost once.
5. Close the manual position; verify it disappears from the default view.
6. Enable Include closed; verify the row and user fields reappear with Closed status.
7. Confirm no order API or Gateway write action occurred.

### Step 6: Docs closeout

After review, merge, and live verification:

- mark this plan `LIVE COMPLETE`;
- add implementation commits, test counts, A/B result, and live evidence to the newest
  priority-map entry;
- close the parent Holdings V1 live note if agent holdings trace and the remaining sync
  checks are also complete.

---

## Expected Commit Sequence

1. `feat: add holdings row update semantics`
2. `feat: expose holdings row actions`
3. `feat: add holdings row actions`
4. `docs: close holdings row actions`

Implementation stops review-ready before merge. The reviewer reruns focused suites and
full A/B; live mutation waits until after explicit merge approval.
