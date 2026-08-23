# Ticker Identity Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely apply an explicitly approved terminal-delisting or simple `A -> B` ticker continuation without losing tracking intent or rewriting provider-owned history.

**Architecture:** A dedicated profile-side identity-transition component derives a canonical preview from the current accepted lifecycle assessment and active-universe state. Approval persists that exact preview; a provider-free scheduler revalidates it and applies all user-owned changes in one SQLite transaction, with append-only attempts, lineage, and fingerprint-gated reversal.

**Tech Stack:** Python 3, stdlib `sqlite3`, FastAPI/Pydantic, React/TypeScript, Vitest/Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-ticker-identity-continuation-design.md`

**Implementation status (2026-08-23):** Tasks 0-7 and both bounded
independent-review repair rounds are implemented on the isolated branch through
`936747b9`. Second-round RED was exact (`6 failed / 24 passed`); fresh GREEN is
Task 7 focused `231 passed`, full backend `4295 passed / 12 skipped`
(collection `4307`), frontend `104 files / 1220 passed`, typecheck, literal
scan, production build, `185` routes, and the ten-screenshot bilingual browser
matrix. Independent review of this new tip is still required, so these results
are self-admission rather than live or merge clearance. No provider call,
production database target, live migration, merge, or push was used. Fresh
production preflight, backup, restore probe, and cutover remain separately
gated after an independent GREEN.

## Global Constraints

- No provider/network call is allowed in Tasks 0-7 implementation or admission.
- No production database write or migration is authorized by this plan.
- Existing `security_lifecycle_%` schema and migrated rows stay byte-compatible.
- `ticker_aliases`, portfolio positions, SA capture rows, notes, research, and historical market rows are never rewritten.
- Only `user` and `legacy` tags may copy to a successor.
- Acquisition and `symbol_or_venue_changed` outcomes never enter the executor.
- Every mutation is RED-first and uses scratch databases.
- Production preflight, backup, and migration remain separately approved live
  operations after Task 7 implementation review.

---

## File Map

- `src/ticker_identity_schema.py`: closed vocabulary, additive DDL, exact component verification.
- `src/ticker_identity_transition.py`: canonical snapshots/previews and atomic transition store.
- `src/ticker_identity_service.py`: lifecycle/active-universe composition, approval, due execution, lineage reads.
- `src/ticker_identity_migration.py`: read-only preflight, backup, additive live migration, restore probe.
- `src/api/routes/ticker_identity.py`: typed preview/approve/cancel/retry/reverse routes.
- `src/api/dependencies.py`: request-owned transition service dependency.
- `src/api/app.py`: route registration only.
- `src/service/ticker_identity_scheduler.py`: bounded provider-free due runner.
- `src/service/data_scheduler.py`: one scheduler-tick handoff to the due runner.
- `src/api/routes/profile.py`: add lineage to ticker-state read model.
- `apps/arkscope-web/src/api.ts`: DTOs and commands.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`: transition preview and lifecycle commands.
- `apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.ts`: exhaustive status/effect/blocker copy selection.
- `apps/arkscope-web/src/TickerDetail.tsx`: predecessor/successor history links.
- `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/explore.ts`: bilingual product copy.
- `docs/design/PROJECT_PRIORITY_MAP.md`: implementation/live-cutover status and deferred provider work.

---

### Task 0: Isolated Baseline and Ownership Census

**Files:**
- Modify: `docs/superpowers/plans/2026-08-23-ticker-identity-continuation.md`
- Create: `/tmp/ticker-identity-continuation-baseline/*` (untracked evidence only)

**Interfaces:**
- Consumes: clean `master` with backend collection `4229` and frontend `1207/1207`.
- Produces: an isolated worktree and exact baseline receipts used by every later task.

- [x] **Step 1: Create the isolated worktree**

Run:

```bash
git worktree add /tmp/arkscope-ticker-identity -b ticker-identity-continuation master
```

Expected: the new worktree points at the plan-authority commit and `git status --short` is empty.

- [x] **Step 2: Record product ownership before edits**

Run:

```bash
mkdir -p /tmp/ticker-identity-continuation-baseline
git -C /tmp/arkscope-ticker-identity rev-parse HEAD > /tmp/ticker-identity-continuation-baseline/base.txt
rg -l "remap_symbol|archive_manual_memberships|hide_from_active_universe|symbol_or_venue_changed|ticker_aliases" /tmp/arkscope-ticker-identity/src /tmp/arkscope-ticker-identity/tests /tmp/arkscope-ticker-identity/apps/arkscope-web/src | sort > /tmp/ticker-identity-continuation-baseline/owners.txt
```

Expected: every future edit is either in the File Map or is added to the plan through a docs-only amendment before product code changes.

- [x] **Step 3: Reproduce the baseline**

Run:

```bash
cd /tmp/arkscope-ticker-identity
python -m pytest --collect-only -q
python -m pytest tests/test_security_lifecycle_investigation.py tests/test_security_lifecycle_routes.py tests/test_profile_state.py tests/test_data_scheduler.py -q
cd apps/arkscope-web
npm test -- --run
```

Expected: collection is `4229`; focused backend and all `1207` frontend tests pass.

- [x] **Step 4: Commit the authority docs on master before product work**

Run from the main worktree:

```bash
git add docs/superpowers/specs/2026-08-23-ticker-identity-continuation-design.md docs/superpowers/plans/2026-08-23-ticker-identity-continuation.md
git commit -m "docs: design ticker identity continuation"
```

Then fast-forward the branch to that docs-only commit before Task 1.

```bash
git -C /tmp/arkscope-ticker-identity merge --ff-only master
```

---

### Task 1: Additive Identity Schema

**Files:**
- Create: `src/ticker_identity_schema.py`
- Create: `tests/test_ticker_identity_schema.py`

**Interfaces:**
- Produces: `create_ticker_identity_schema(conn) -> None`, `verify_ticker_identity_connection(conn) -> None`, `identity_schema_present(conn) -> bool`, and closed status constants.
- Consumes: a caller-owned `sqlite3.Connection`; never opens a path itself.

- [x] **Step 1: Write schema RED tests**

Add tests that assert exact tables, columns, checks, indexes, and no implicit creation:

```python
def test_identity_schema_is_additive_exact_and_foreign_key_clean(tmp_path):
    conn = sqlite3.connect(tmp_path / "profile.db")
    create_profile_schema(conn)
    create_ticker_identity_schema(conn)
    verify_ticker_identity_connection(conn)
    assert _tables(conn) == {
        "ticker_identity_transitions",
        "ticker_identity_transition_attempts",
        "ticker_identity_links",
    }
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_identity_verifier_rejects_missing_extended_or_changed_schema(tmp_path):
    conn = sqlite3.connect(tmp_path / "profile.db")
    create_profile_schema(conn)
    assert identity_schema_present(conn) is False
    with pytest.raises(TickerIdentitySchemaMismatch):
        verify_ticker_identity_connection(conn)
```

- [x] **Step 2: Run RED**

Run:

```bash
python -m pytest tests/test_ticker_identity_schema.py -q
```

Expected: collection/import fails because `src.ticker_identity_schema` does not exist.

- [x] **Step 3: Implement exact DDL**

Define:

```python
TRANSITION_KINDS = frozenset({"symbol_continuation", "terminal_delisting"})
TRANSITION_STATUSES = frozenset(
    {"approved", "needs_review", "applied", "cancelled", "reversed"}
)
ATTEMPT_TRIGGERS = frozenset({"attended_user", "scheduler"})
ATTEMPT_STATUSES = frozenset(
    {"blocked", "applied", "already_applied", "reversed"}
)
PRIORITY_RESOLUTIONS = frozenset({"source", "successor"})
```

Create the three tables from Spec §8. Use closed CHECK constraints, bounded JSON lengths, terminal-state timestamp coherence, foreign keys to lifecycle case/assessment tables, and indexes for `(status, execute_on)` plus both lineage directions. `verify_ticker_identity_connection` must compare normalized SQL and exact table/index sets prefixed with `ticker_identity_`.

- [x] **Step 4: Run GREEN and schema mutation checks**

Run:

```bash
python -m pytest tests/test_ticker_identity_schema.py tests/test_security_lifecycle_schema.py -q
```

Expected: all pass; existing lifecycle schema tests remain unchanged.

- [x] **Step 5: Commit**

```bash
git add src/ticker_identity_schema.py tests/test_ticker_identity_schema.py
git commit -m "feat(lifecycle): add ticker transition schema"
```

---

### Task 2: Canonical Preview and Eligibility Kernel

**Files:**
- Create: `src/ticker_identity_transition.py`
- Create: `tests/test_ticker_identity_transition.py`
- Modify: `src/security_lifecycle_investigation.py`
- Modify: `tests/test_security_lifecycle_investigation.py`

**Interfaces:**
- Produces: `TransitionOptions`, `build_transition_preview(conn, *, case, assessment, proposals, observation_fingerprint_sha256, sources, options) -> dict`, `profile_snapshot_sha256(preview) -> str`.
- Consumes: current lifecycle rows and literal source names; performs no write and no network call.

- [x] **Step 1: Write eligibility RED tests**

Cover each closed decision:

```python
@pytest.mark.parametrize(
    ("outcomes", "successor", "eligible_kind"),
    [
        (("symbol_changed",), "NEW", "symbol_continuation"),
        (("symbol_changed", "venue_transfer"), "NEW", "symbol_continuation"),
        (("venue_transfer",), None, None),
        (("symbol_or_venue_changed",), "NEW", None),
        (("acquisition_stock",), "NEW", None),
    ],
)
def test_preview_uses_the_closed_transition_eligibility_matrix(...):
    preview = build_transition_preview(...)
    assert preview["transition_kind"] == eligible_kind


def test_terminal_delisting_is_blocked_by_open_portfolio(...):
    preview = build_transition_preview(..., sources=("manual_lists", "portfolio_open"))
    assert preview["block_reasons"] == ["portfolio_position_open"]
```

Add independent tests for differing priority, hidden successor, missing date,
stale assessment, missing observation citation, successor equal to source, and
no active source.

- [x] **Step 2: Write profile-effect RED tests**

Seed scratch rows for `A` and `B`, then assert the preview lists exact adds,
reactivations, archives, copied editable tags, untouched provider tags, priority
resolution, suppression behavior, and caveats. Include `B` already active,
archived, and absent.

- [x] **Step 3: Run RED**

```bash
python -m pytest tests/test_ticker_identity_transition.py tests/test_security_lifecycle_investigation.py -q
```

Expected: new tests fail because the preview kernel is absent; the evolved
portfolio test fails until proposal generation no longer suppresses safe
successor tracking.

- [x] **Step 4: Implement canonical preview**

Use immutable options:

```python
@dataclass(frozen=True)
class TransitionOptions:
    execute_on: str
    priority_resolution: str | None = None
    unhide_successor: bool = False
```

Return a canonical dictionary containing `transition_kind`, `eligible`, sorted
`block_reasons`, exact effects/caveats, all authority fingerprints, and
`preview_sha256`. JSON serialization must use sorted keys, compact separators,
and UTF-8.

Change proposal generation so:

- `symbol_changed` with a distinct successor can emit `remap_symbol` even when
  `portfolio_open` exists;
- `portfolio_open` also emits `review_portfolio_position` with its blocker;
- `venue_transfer` without a distinct successor emits no remap;
- acquisition outcomes emit no executable remap;
- ambiguous legacy outcomes emit no remap.

- [x] **Step 5: Run GREEN**

```bash
python -m pytest tests/test_ticker_identity_transition.py tests/test_security_lifecycle_investigation.py -q
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/ticker_identity_transition.py src/security_lifecycle_investigation.py tests/test_ticker_identity_transition.py tests/test_security_lifecycle_investigation.py
git commit -m "feat(lifecycle): derive safe ticker transition previews"
```

---

### Task 3: Approval, Atomic Execution, and Reversal

**Files:**
- Modify: `src/ticker_identity_transition.py`
- Modify: `tests/test_ticker_identity_transition.py`

**Interfaces:**
- Produces: `TickerIdentityTransitionStore` with `approve`, `get`, `list_due`, `apply`, `cancel`, `reverse`, and `lineage_for_ticker`.
- Consumes: a verified caller-owned profile connection and a current preview supplied by the service.

- [x] **Step 1: Write approval and idempotency RED tests**

Use deterministic IDs and clock:

```python
store = TickerIdentityTransitionStore(
    conn,
    id_factory=lambda prefix: f"{prefix}_1",
    clock=lambda: "2026-08-24T01:00:00Z",
)
transition = store.approve(preview=preview, approved_preview_sha256=preview["preview_sha256"])
assert transition["status"] == "approved"
assert store.approve(...)["transition_id"] == transition["transition_id"]
```

Assert a mismatched preview digest, ineligible preview, or unresolved conflict
writes zero rows.

- [x] **Step 2: Write atomic-apply RED tests**

For `A -> B`, assert final rows and operation order. Inject failures after each
logical mutation through a test-only callable seam:

```python
for fail_after in range(1, 9):
    before = snapshot_all_owned_rows(conn)
    with pytest.raises(RuntimeError, match="injected_failure"):
        store.apply(
            transition_id,
            current_preview=preview,
            trigger="scheduler",
            fail_after_step=fail_after,
        )
    assert snapshot_all_owned_rows(conn) == before
```

The production signature must not expose `fail_after_step`; inject a private
step hook in the store constructor and pass it only in tests.

- [x] **Step 3: Write source-ownership RED tests**

Before/after-digest all protected tables and assert:

- portfolio rows unchanged;
- notes and research rows unchanged;
- provider-owned tags unchanged and not copied;
- lifecycle assessments/evidence unchanged;
- `ticker_aliases` is never opened;
- an old broker position leaves `A` unsuppressed while `B` tracking is active.

- [x] **Step 4: Write reversal RED tests**

Assert exact restore succeeds immediately, while a user edit after application
causes `reverse_state_changed` and zero mutation. Assert a later active
`B -> C` link blocks reversing `A -> B`.

- [x] **Step 5: Run RED**

```bash
python -m pytest tests/test_ticker_identity_transition.py -q
```

Expected: store methods are missing.

- [x] **Step 6: Implement one-transaction writes**

`apply` must execute `BEGIN IMMEDIATE`, re-read profile-owned rows, compare the
current digest, and either:

```python
return {"status": "blocked", "block_reasons": ["preview_changed"]}
```

without profile mutation, or commit memberships, editable tags, priority,
suppression, link, transition status, and attempt together. Re-entry after
commit records/returns `already_applied` without changing profile rows.

- [x] **Step 7: Run GREEN**

```bash
python -m pytest tests/test_ticker_identity_transition.py tests/test_profile_state.py -q
```

Expected: all pass.

- [x] **Step 8: Commit**

```bash
git add src/ticker_identity_transition.py tests/test_ticker_identity_transition.py
git commit -m "feat(lifecycle): apply atomic ticker transitions"
```

---

### Task 4: Cross-Store Service and Typed API

**Files:**
- Create: `src/ticker_identity_service.py`
- Create: `src/api/routes/ticker_identity.py`
- Create: `tests/test_ticker_identity_routes.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/app.py`
- Modify: `src/api/routes/profile.py`
- Modify: `tests/test_security_lifecycle_routes.py`
- Modify: `tests/test_profile_state.py`

**Interfaces:**
- Produces: `TickerIdentityService.preview_case`, `approve_case`, `execute_transition`, `cancel_transition`, `reverse_transition`, `lineage_for_ticker`.
- Produces routes from Spec §9 and `lineage` in the ticker-state DTO.
- Consumes current lifecycle composition and `build_active_universe_snapshot`.

- [x] **Step 1: Write route RED tests**

Create a scratch app with dependency overrides. Assert:

```python
preview = client.get(f"/security-lifecycle/cases/{case_id}/transition-preview")
assert preview.status_code == 200
digest = preview.json()["preview_sha256"]
approved = client.post(
    f"/security-lifecycle/cases/{case_id}/approve-transition",
    json={"execute_on": "2026-08-25", "preview_sha256": digest},
)
assert approved.status_code == 200
assert approved.json()["status"] == "approved"
```

Assert malformed input is rejected before permission invocation; writes call
`profile_state_write`, not `db_write`; stale digest returns 409; missing schema
returns typed 503; ineligible cases return 422; read preview opens no network.

- [x] **Step 2: Write lineage route RED tests**

Extend ticker state expectations:

```python
assert payload["lineage"] == {
    "predecessors": [{"ticker": "OLD", "transition_id": "slt_1"}],
    "successors": [],
}
```

Assert the read is empty when identity schema is absent rather than creating
tables; a malformed present schema returns typed unavailable.

- [x] **Step 3: Run RED**

```bash
python -m pytest tests/test_ticker_identity_routes.py tests/test_profile_state.py tests/test_security_lifecycle_routes.py -q
```

Expected: new imports/routes fail.

- [x] **Step 4: Implement service composition**

The service opens `market_data.db` read-only and `profile_state.db` read/write
only for commands. It obtains the case through the existing lifecycle read
service, maps current proposals/assessment into the preview kernel, and never
uses old proposal snapshots as current truth.

Expose a request-owned dependency:

```python
def get_ticker_identity_service():
    return TickerIdentityService(
        market_db_path=resolve_market_db_path(),
        profile_db_path=_local_state_db_path(),
    )
```

- [x] **Step 5: Implement routes and permissions**

Pydantic request models use `extra="forbid"`, canonical dates, closed priority
choices, and bounded ticker values. Call `require_profile_state_write` only
after request validation and service preflight, immediately before mutation.

- [x] **Step 6: Run GREEN and route inventory**

```bash
python -m pytest tests/test_ticker_identity_routes.py tests/test_profile_state.py tests/test_security_lifecycle_routes.py -q
python -c 'from src.api.app import create_app; print(len(create_app().routes))'
```

Expected: all pass and exactly five routes are added.

- [x] **Step 7: Commit**

```bash
git add src/ticker_identity_service.py src/api/routes/ticker_identity.py src/api/dependencies.py src/api/app.py src/api/routes/profile.py tests/test_ticker_identity_routes.py tests/test_profile_state.py tests/test_security_lifecycle_routes.py
git commit -m "feat(lifecycle): expose reviewed ticker transitions"
```

---

### Task 5: Provider-Free Due Scheduler

**Files:**
- Create: `src/service/ticker_identity_scheduler.py`
- Create: `tests/test_ticker_identity_scheduler.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

**Interfaces:**
- Produces: `run_due_ticker_identity_transitions(*, limit: int = 10, now: datetime | None = None) -> dict`.
- Consumes: approved transition rows and the shared service; performs no provider call.

- [x] **Step 1: Write scheduler RED tests**

Assert:

- future plans are not selected;
- due plans run in `America/New_York` date semantics;
- at most ten plans run per tick;
- one blocked plan does not prevent later plans;
- concurrent calls apply once;
- scheduler trigger is recorded;
- no SEC/IBKR/SA/Tavily/LLM adapter is imported or called;
- no plan means no write and no database creation.

Use a socket-denial fixture around the full due runner.

- [x] **Step 2: Run RED**

```bash
python -m pytest tests/test_ticker_identity_scheduler.py tests/test_data_scheduler.py -q
```

Expected: scheduler module/handoff is absent.

- [x] **Step 3: Implement bounded runner**

Return a stable summary:

```python
{
    "due": 2,
    "applied": 1,
    "needs_review": 1,
    "already_applied": 0,
    "transition_ids": ["slt_1", "slt_2"],
}
```

The data scheduler calls this once per tick after interrupted-run
reconciliation and before provider source dispatch. Failures are logged with
sanitized codes and never stop provider scheduling.

- [x] **Step 4: Run GREEN**

```bash
python -m pytest tests/test_ticker_identity_scheduler.py tests/test_data_scheduler.py -q
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/service/ticker_identity_scheduler.py src/service/data_scheduler.py tests/test_ticker_identity_scheduler.py tests/test_data_scheduler.py
git commit -m "feat(lifecycle): run approved ticker transitions"
```

---

### Task 6: Bilingual Transition UI and Historical Links

**Files:**
- Create: `apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.ts`
- Create: `apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.test.ts`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/TickerDetail.tsx`
- Modify: `apps/arkscope-web/src/TickerDetail.test.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

**Interfaces:**
- Produces exhaustive TypeScript DTO/status/blocker maps and attended commands.
- Consumes the Task 4 routes; does not recompute hashes or transition effects.

- [x] **Step 1: Write presentation RED tests**

Use `Record<TransitionStatus, string>` and `Record<TransitionBlockReason, string>`
so a missing backend enum is a TypeScript error. Assert distinct copy for:

- approved/waiting;
- needs review;
- tracking moved while old broker position remains;
- terminal delisting applied;
- cancelled;
- reversed;
- explicit unknown value.

- [x] **Step 2: Write workflow RED tests**

Render a real transition-preview shape. Assert the modal displays `A -> B`,
date, list effects, tags, priority conflict control, broker caveat, and the
historical-data non-rewrite statement. Assert approval sends the server-provided
`preview_sha256`; no client hash exists.

Add tests for ineligible proposals, cancellation, changed-preview 409, reversal
blocked by later edits, and action buttons disabled while a command is pending.

- [x] **Step 3: Write lineage RED tests**

Render ticker `B` with predecessor `A`; clicking it invokes the existing ticker
navigation rather than rewriting notes into `B`.

- [x] **Step 4: Run RED**

```bash
cd apps/arkscope-web
npm test -- --run src/lifecycle/tickerIdentityPresentation.test.ts src/lifecycle/LifecycleView.test.tsx src/TickerDetail.test.tsx src/i18n/resources.test.ts
```

Expected: new types/components are absent.

- [x] **Step 5: Implement DTOs, copy, and controls**

Use existing compact lifecycle sections and modal patterns. Do not create nested
cards or a new landing surface. All visible copy lives in locale resources.
Conflict choices use a segmented/radio control; commands use existing button
styles and familiar icons where available.

- [x] **Step 6: Run frontend gates**

```bash
npm test -- --run
npm run typecheck
npm run check:i18n-literals
npm run build
```

Expected: all tests pass, TypeScript is clean, visible-literal scan is clean,
and production build succeeds.

- [x] **Step 7: Browser verification**

Run the app against scratch migrated fixtures and capture `1440x900` and
`390x844` screenshots for:

- symbol continuation with an open broker position;
- terminal delisting;
- priority conflict;
- applied transition plus predecessor link.

Assert no overlap, truncation, raw enum leakage, or provider/network request.

- [x] **Step 8: Commit**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.ts apps/arkscope-web/src/lifecycle/tickerIdentityPresentation.test.ts apps/arkscope-web/src/lifecycle/LifecycleView.tsx apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx apps/arkscope-web/src/TickerDetail.tsx apps/arkscope-web/src/TickerDetail.test.tsx apps/arkscope-web/src/i18n/resources/en/explore.ts apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts apps/arkscope-web/src/i18n/resources.test.ts
git commit -m "feat(lifecycle): review ticker transition effects"
```

---

### Task 7: Migration Utility, Admission, and Separately Authorized Live Cutover

**Files:**
- Create: `src/ticker_identity_migration.py`
- Create: `tests/test_ticker_identity_migration.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_data_provider_config.py`
- Modify: `src/ticker_identity_service.py`
- Modify: `src/ticker_identity_transition.py`
- Modify: `src/ticker_identity_schema.py`
- Modify: `src/tools/security_lifecycle_tools.py`
- Modify: `tests/test_ticker_identity_schema.py`
- Modify: `tests/test_ticker_identity_transition.py`
- Modify: `tests/test_ticker_identity_routes.py`
- Modify: `tests/test_ticker_identity_migration.py`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.tsx`
- Modify: `apps/arkscope-web/src/lifecycle/LifecycleView.test.tsx`
- Modify: `apps/arkscope-web/src/i18n/resources/{en,zh-Hant}/explore.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/specs/2026-08-23-ticker-identity-continuation-design.md`
- Modify: `docs/superpowers/plans/2026-08-23-ticker-identity-continuation.md`

**Interfaces:**
- Produces: `preflight_ticker_identity_migration`, `create_profile_backup`, `migrate_ticker_identity_schema`, and `restore_profile_backup`.
- Consumes: an explicit profile path, clock, backup directory, and approval digest; no default production path.

- [x] **Step 1: Write migration RED tests**

Assert read-only preflight creates nothing; additive migration preserves every
existing table schema/row digest; interruption rolls back all three new tables;
re-run is idempotent; malformed pre-existing identity tables stop; restore
requires a verified backup and never targets the backup itself.

- [x] **Step 2: Implement explicit migration functions**

All public functions require keyword-only paths with no production defaults.
Preflight returns exact existing schema/integrity digests, identity-table
presence, lifecycle counts, and an approval SHA-256. Migration checks that SHA
immediately before `BEGIN IMMEDIATE` and creates only the three approved tables
and indexes.

- [x] **Step 3: Run focused and full admission**

The five Task 4 routes evolve the exact local-runtime inventory from `180` to
`185`; update that existing count owner. Full-suite RED also proved that the
simulated unavailable-profile startup in `tests/test_api.py` can leave the
process-global `provider_config_setup_required` state set for later modules.
Extend the existing hermetic fixture in `tests/test_data_provider_config.py` to
clear that process-global state before and after each test. This is test
isolation only; do not weaken the production fail-closed state or its routes.

```bash
python -m pytest tests/test_ticker_identity_schema.py tests/test_ticker_identity_transition.py tests/test_ticker_identity_routes.py tests/test_ticker_identity_scheduler.py tests/test_ticker_identity_migration.py tests/test_security_lifecycle_investigation.py tests/test_profile_state.py tests/test_data_scheduler.py -q
python -m pytest -q
cd apps/arkscope-web
npm test -- --run
npm run typecheck
npm run check:i18n-literals
npm run build
```

Expected: zero failures, backend collection equals baseline plus reviewed
additions, and frontend equals baseline plus reviewed additions.

- [x] **Step 4: Prove protected boundaries**

On scratch copies, compare before/after schema and row digests for lifecycle
observations, evidence, assessments, portfolio, notes, research, SA, market
history, and aliases. Run with sockets denied. Expected: only the three identity
tables/indexes and explicitly exercised profile rows differ.

- [x] **Step 5: Update status docs and request independent review**

Record exact commits, counts, route inventory, mutation/rollback evidence,
browser fixtures, and zero-network proof. Do not claim production migration.

- [x] **Step 6: Repair independent-review findings RED-first**

The repair must prove all of the following before repeating admission:

1. A broker position opened after service recomposition but before
   `BEGIN IMMEDIATE` changes the lock-time dependency digest, records a blocked
   attempt, moves the transition to `needs_review`, and performs no profile
   suppression or membership archive.
2. A stale scheduled preview reaches the store's durable blocked-attempt path
   instead of raising in the service while leaving the plan `approved`.
   Client-supplied approval digests remain fail-closed before execution.
3. Exact schema verification rejects every unapproved trigger, view, or index
   attached to an identity table, including objects without the expected name
   prefix; SQLite-owned autoindexes remain permitted.
4. Case detail returns the bounded stored approved preview, and approved,
   `needs_review`, and applied UI states retain the exact approved effects and
   caveats after the editable preview closes.
5. Restore never replaces an existing profile database. It installs a
   reverified backup only at an absent target using a same-directory atomic
   no-clobber operation; an operator must first stop writers and move the old
   target aside.

Market/SEC/SA inputs are sampled before the profile transaction and cannot be
made atomically current by this profile-only executor. A change observed before
apply must produce `needs_review`; a provider change after that sample is a new
observation for the next reconciliation cycle. The implementation and docs may
not claim cross-database linearizability.

Repair evidence at `42820905`: exact RED was `8 failed / 21 passed` backend and
`1 failed / 25 passed` frontend. GREEN was `65 passed` for the repair-focused
backend set, `224 passed` for the cumulative Task 7 backend command,
`4288 passed / 12 skipped` for the full backend (collection `4300`), and
`104 files / 1220 passed` for the frontend. Typecheck, literal scan, production
build, and `185`-route inventory passed. The `1440x900` English and `390x844`
Traditional Chinese browser matrix produced ten screenshots, mechanically
asserted retained approved caveats, and recorded zero writes, external requests,
console errors, page errors, or horizontal overflow.

- [ ] **Step 7: Repeat full admission and independent review**

Run every Task 7 gate from a clean repaired tip and obtain an independent
review with the five repair regressions in scope. Historical GREEN counts do
not authorize the repaired tip. Self-admission is complete at `42820905` with
the evidence recorded above, but re-review at `2118f0ab` returned RED.

The second repair is bounded as follows:

1. If the provider observation changes or disappears so the accepted
   assessment is no longer current, execution must still pass an honest
   unavailable/current-mismatch signal into the store. The store appends a
   blocked attempt, moves the approved plan to `needs_review`, and performs no
   profile effect.
2. `store.apply` receives the request's expected approved-preview digest and
   compares it again after `BEGIN IMMEDIATE`. A concurrent re-approval makes the
   stale request a typed `transition_preview_changed` conflict; it cannot apply
   the new plan and does not invalidate that newly approved plan.
3. Exact object verification covers both `sqlite_master` and
   `sqlite_temp_master`: TEMP triggers attached to identity tables and any TEMP
   object in the reserved identity namespace are rejected. A differently named,
   read-only view that merely selects from an identity table is an external
   consumer, not an owned schema object, and is not rejected or parsed by this
   component.
4. Restore fsyncs the verified copy before publication, rechecks target and
   sidecars immediately before install, atomically links at an absent target,
   and fsyncs the parent directory before success. External writer quiescence
   remains an operator prerequisite rather than a claim of automatic detection.

All four changes are RED-first. The complete Task 7 admission and independent
review restart from the resulting clean tip; no earlier GREEN is inherited.

Second-round evidence at `936747b9`: exact RED was `6 failed / 24 passed`; the
new minimal GREEN was `30 passed`, the complete ticker transition set was
`72 passed`, and the cumulative Task 7 backend gate was `231 passed`. Full
backend passed `4295 / 12 skipped` (collection `4307`), while frontend remained
`104 files / 1220 passed`. Typecheck, literal scan, production build, and the
`185`-route runtime owner passed. The repeated `1440x900` English and `390x844`
Traditional Chinese browser matrix produced ten screenshots with explicit
approved-caveat assertions and zero writes, external requests, console errors,
page errors, or horizontal overflow. Independent re-review remains pending.

- [ ] **Step 8: Stop for live authorization**

Only after implementation review GREEN, run a fresh read-only production
preflight and present its approval digest, backup path/digest, schema delta, and
restore-probe result. Production migration, merge, and provider calls remain
separate user decisions.
