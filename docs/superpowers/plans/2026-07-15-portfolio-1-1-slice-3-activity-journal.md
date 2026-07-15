# Portfolio 1.1 Slice 3 Activity and Journal UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: IMPLEMENTED FOR REVIEW. CODE, AUTOMATED, RESPONSIVE, PRIVACY,
> FRESH-PROFILE, NO-PG, AND CANONICAL A/B GATES PASS. COPIED-PROFILE
> PROVIDER-FREE LIVE GATES PASS; THE FRESH SUCCESSFUL CAPTURE/RERUN SUBGATE IS
> DEFERRED BECAUSE THE EXTERNAL IBKR API HANDSHAKE REMAINED UNAVAILABLE DURING
> AND AFTER THE 2026-07-16 APAC RESET WINDOW.**

## Implementation Ledger

- **Branch / commits:** `codex/portfolio-1-1-activity`; behavioral A/B base
  `c5cd91f`; branch base and plan commit `b657349`; code head `0709bed` before
  this evidence-only closeout. Tasks landed as `8830b9a` (annotation
  foundation), `cce9482` (broker projection), `42706a7` + `3d05600` (complete
  projection and identity/cursor hardening), `54bb484` + `e9b8d65` (API plus
  case-insensitive account-label privacy), `fc7e3a0` + `595c417` (activity UI
  plus truth/focus hardening), and `94c72fa` + `0709bed` (navigation/recent
  integration plus refresh semantics). Merge, spec/map LIVE status, and
  worktree cleanup remain unperformed.
- **Tasks 1-4, backend RED -> GREEN:** Task 1 began with no activity module,
  annotation table, or safe public label helper. Task 2 began with no
  correction-aware broker projection. Task 3 began with no manual/unmatched/
  coverage projection, filters, or cursor. Task 4 began with no mounted
  provider-free activity API. The final focused backend command over activity,
  routes, Portfolio authority, observations, and capture routes reports
  **`115 passed`**. Review fixes additionally pin local/account-scoped marker
  identities, deterministic cursors, case-insensitive legacy raw-label
  redaction, and typed storage failures.
- **Tasks 5-6, frontend RED -> GREEN:** the activity DTO, ET-first formatter,
  activity/recent components, four-tab hierarchy, and contextual layout did
  not exist at RED. The final focused frontend ledger is **`6 files / 83
  tests`**; the full frontend is **`46 files / 450 tests`**. TypeScript
  typecheck and the production build pass, with only the pre-existing Vite
  chunk-size warning. Review fixes pin failed-page cursor truth, commission
  currency display, nested Drawer/ConfirmDialog focus, correction lineage,
  unmatched timestamp domain, synchronous refresh invalidation, and
  note-only refresh exclusion.
- **Static/privacy/fresh gates:** order APIs, PostgreSQL terms, target-file
  `window.confirm`/`@media`, agent/tool registration, and duplicate Settings
  ownership all return zero matches. A fresh temporary profile adds exactly
  `portfolio_activity_annotations`, keeps accounts `0 -> 0`, returns zero
  items, mounts the route, and gives the annotation FK `RESTRICT` rather than
  `CASCADE`. The no-PG smoke reports `ok: true` and `pg_attempts: []`. Focused
  serialization/error/tool/capture probes all keep the real raw broker account
  id absent.
- **Responsive/interaction gate:** a disposable scheduler-disabled sidecar,
  Vite process, and seeded profile passed DOM plus screenshot checks at
  `1440x900`, `1024x768`, `961x768`, `959x768`, and `390x844`. The tab order is
  exactly `持倉 / 活動 / 帳戶明細 / 同步紀錄`, including ArrowRight/ArrowLeft
  keyboard navigation. The activity DataTable owns horizontal overflow while
  the page does not; broker executions show ET first; expanded correction,
  commission, manual, unmatched, and gap rows do not overlap; nested
  ConfirmDialog Escape closes only the top overlay and restores focus before
  the Drawer closes; and the recent panel renders only with real content at
  `961+`, reserving no width at `959` or mobile. Fixture screenshots remain
  disposable under `/tmp/arkscope-p11-s3-*.png`.
- **Canonical backend A/B:** clean detached worktrees, sequential
  single-process pytest, base `c5cd91f` versus code head `0709bed`: collected
  **`4302 -> 4335`**, exactly **`+33/-0`**; passed **`4191 -> 4224`**; both
  sides have **`30 failed / 74 skipped / 18 warnings / 7 errors`**. Parsed
  pytest node IDs show exactly the 33 planned activity tests and no removal;
  parsed JUnit failure and error sets have empty differences in both
  directions. Both temporary A/B worktrees were removed; their only generated
  untracked file was pytest's 73-byte risk-free-rate cache.
- **Copied-profile provider-free live gate:** the normal app/sidecar was
  closed before a scheduler-disabled branch sidecar used an SQLite backup of
  the real profile. Existing captured facts rendered two natural current-day
  broker order groups, unmatched observations, history-start, and explicit
  coverage gaps without a raw account id. A disposable Manual position was
  created, updated, and soft-closed through the real API; the activity feed
  returned exactly `close / update / create`, historical field changes, and
  no execution price, commission, or realized-P&L claim. Saving and clearing
  one intent annotation restored the annotation row count and left SHA-256
  digests of all nine broker/manual fact tables byte-identical.
- **Copied-profile real-data browser gate:** at `1440x900`, the wide recent
  panel showed only real rows and navigated to the full activity surface. The
  activity page rendered 16 real/copied rows, the exact four tabs, ET-first
  broker timestamps, local-first manual/system timestamps, history-start and
  coverage-gap language, no page overflow, and no raw-account-id pattern. The
  only fabricated live-gate entity was the disposable `ZZLIVE` Manual
  position; no broker trade, commission, correction, or second account was
  manufactured.
- **External live subgate deferral:** copied-profile manual capture runs `123`
  and `124` were accepted but failed all three legs with the typed
  `ibkr_connection_failed` result and zero provider rows written. DB and the
  main `config/.env` matched exactly for IBKR host, port, and client-id base;
  TCP connected, but the official `API\0` version handshake returned zero
  bytes until timeout. The first failures occurred during IBKR's published
  APAC reset window (`04:45-06:05 HKT`); isolated handshakes at 06:16 and again
  at 07:24 remained unavailable. No product fix was attempted because failure
  precedes ArkScope client-id, account-summary, execution, or projection logic. The
  still-pending subgate is: after IBKR API service recovers, run two successful
  captures against a fresh copy and prove run history advances while execution
  and logical order cardinality remain unchanged.
- **Cleanup / scope:** disposable Vite and sidecar processes were stopped.
  Product scope did not add Gateway reads, schedulers, Settings controls,
  agents/tools/prompts, PostgreSQL paths, or order APIs. The authority spec and
  priority map deliberately remain pre-LIVE pending independent review and the
  deferred successful-capture subgate.

**Goal:** Complete Portfolio 1.1 with a truthful Holdings activity view over captured broker facts and manual-adjustment journals, user-owned intent annotations, explicit coverage gaps, and a responsive recent-activity summary without changing capture or canonical-position authority.

**Architecture:** Add one focused `PortfolioActivityStore` over the existing `profile_state.db` tables. It derives a bounded correction-aware read model from immutable executions, commission revisions, unmatched changes, capture coverage, and manual journals; only the new annotation table is mutable. Expose the projection through an additive provider-free `/portfolio/activity` API, then render it in the locked second Holdings tab with existing P2.8 primitives and a wide-only contextual summary. No activity read performs Gateway I/O or mutates canonical holdings.

**Tech Stack:** Python 3.10, SQLite/WAL, frozen dataclasses, FastAPI/Pydantic, React 18.3, TypeScript 5.5, Vite/Vitest, `lucide-react`, and the shipped P2.8 `DataTable`, `Drawer`, `ConfirmDialog`, `StatusBadge`, `InlineAlert`, `Button`, and shell-breakpoint primitives.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-13-portfolio-1-1-observation-activity-design.md` wins over this plan on conflict.
- Behavioral A/B base is reviewer-closeout commit `c5cd91f`; `7f005eb` and this plan/status commit are documentation-only.
- `portfolio_accounts`, `portfolio_positions`, and `portfolio_position_notes` remain canonical current-state authority. Activity never rebuilds or mutates them.
- `portfolio_capture_runs`, account/position observations, executions, commission revisions, unmatched changes, and manual adjustments remain their shipped fact authorities. Slice 3 does not duplicate, rewrite, compact, or hard-delete them.
- `portfolio_activity_annotations` is the only new table. It is mutable, user-owned, non-cascading, and cannot be written by an agent.
- Broker activity is correction-aware: one logical execution family displays its latest execution revision while retaining every immutable execution and commission revision in expandable detail.
- Broker fills group only by `(portfolio_account_id, perm_id)` when `perm_id`
  is a positive integer. `order_id` alone never groups fills. A null, zero, or
  negative `perm_id` is treated as absent and remains an independent logical
  execution row; persisted broker facts are not rewritten.
- Activity IDs use local identities only: `order:<local-account-id>:<perm-id>`, `execution:<local-account-id>:<family-root-row-id>`, `unmatched:<local-row-id>`, and `manual:<local-row-id>`. They never contain a raw broker account id.
- Read-only marker IDs are deterministic local keys:
  `gap:<local-account-id-or-global>:<from-run-id-or-0>:<to-run-id>` and
  `history:<local-account-id>:<capture-run-id>`. Marker parsers never accept
  annotation writes.
- Objective facts and confirmed intent stay separate. Objective fields use broker facts plus explicitly labeled deterministic arithmetic; intent is only one of `profit_take`, `stop_loss`, `rebalance`, `thesis_broken`, `cash_need`, or `other` after an explicit user save.
- Gross notional is `sum(abs(quantity * price))`, labeled deterministic arithmetic and never called cash impact. Overflow/non-finite arithmetic returns null, never zero.
- Group commission and realized P&L are returned only when every effective fill has the required latest provider field and one compatible currency. Missing or mixed legs keep the aggregate null; no partial sum is presented as complete.
- Position effect is conservative. It is derived only when two consecutive complete position snapshots bound the first-observed capture window, execution coverage is complete and same-ET-day, the observed after quantity equals before plus effective signed fills, and no other order group for that account/conId shares the window. Otherwise direct fill facts remain visible while position direction/close scope are `unknown`.
- The complete-context result has two axes: `position_direction = increase | reduce | unknown` and `close_scope = none | partial | complete | unknown`. A sign flip remains unknown rather than being narrated as one trade.
- History-start and coverage-gap rows are derived at read time from capture runs; they are not fabricated or persisted as broker events. Empty intervals never claim zero transactions.
- Manual adjustments replay field-level journals so historical symbol display/filtering uses the last symbol value at or before that adjustment, not the position's mutable current symbol. They never claim execution price, commission, or realized P&L.
- Market execution timestamps display ET first and local time second. Capture/manual/system timestamps stay UTC in storage; the activity date filter is explicitly labeled as ET.
- The activity response is bounded: default `limit=100`, maximum `200`, deterministic newest-first order by `(occurred_at_utc, activity_id)`, and an opaque URL-safe cursor carrying exactly that tuple. Invalid cursors fail with a typed 400.
- Each source query reads at most `limit + 1` candidate headers after filters/cursor; details are loaded only for the globally selected page. Do not read unbounded execution or journal history into Python.
- `recent=true` means the current ET date plus the preceding six ET dates. It is the sole definition used by the contextual panel and its unmatched count.
- The final Holdings tab order is exactly `持倉 / 活動 / 帳戶明細 / 同步紀錄`. Activity mounts only while selected; capture polling remains mounted only under `同步紀錄`.
- The recent panel is surface-local, shows real recent rows only, only navigates to `活動`, and collapses without reserving width when empty. At the canonical shell breakpoint (`useShellOverlay`, 960px), it performs no request and renders nothing.
- Domain-to-common UI mapping is fixed: initial read=`loading`, no retained
  activity=`empty`, loaded activity=`ready`, annotation save=`running`, invalid
  or unavailable authority=`blocked`/`failed`, incomplete coverage=`partial`,
  and broker-day gap=`stale`. Financial gain/loss/flat/unknown and confirmed
  intent remain labeled domain facts in plain text; they do not borrow common
  operational status colors. This surface has no genuine `interrupted` state
  and does not synthesize one.
- No second Portfolio scheduler, new Settings control, new global navigation item, provider call, background poller, PostgreSQL path, order API, agent tool, prompt input, raw exception surface, `window.confirm`, ad hoc chip, overlay system, or media-query breakpoint is allowed.
- Existing `/portfolio`, `/portfolio/overview`, `/portfolio/capture`, Holdings row actions, agent payloads, tool ledgers, and capture scheduling remain compatible.
- Implementation stops review-ready. Merge, LIVE COMPLETE status, worktree cleanup, and any Flex/performance/trading follow-up remain separate user decisions.

---

## Locked File and Interface Map

| File | Responsibility |
| --- | --- |
| `src/portfolio_activity.py` | New annotation schema/store plus bounded correction-aware activity projection, filtering, gap markers, stable local IDs, and cursors. |
| `src/portfolio_overview.py` | Export the shipped safe account-label helper for reuse without changing overview output. |
| `src/api/dependencies.py` | Add the cached `PortfolioActivityStore` dependency on the same profile DB. |
| `src/api/routes/portfolio_activity.py` | Add provider-free GET plus guarded annotation PUT/DELETE routes and typed error mapping. |
| `src/api/app.py` | Mount the additive activity router. |
| `tests/test_portfolio_activity.py` | Schema, projection, correction, completeness, filtering, cursor, and annotation contracts. |
| `tests/test_portfolio_activity_routes.py` | Real-app mount, query threading, privacy, zero-provider-read, write-gate, and error-shape contracts. |
| `apps/arkscope-web/src/api.ts` | Add the exact discriminated activity DTO, filter query builder, and annotation helpers. |
| `apps/arkscope-web/src/timeDisplay.ts` | Add ET-first `formatMarketTimestamp` while retaining `formatSystemTimestamp`. |
| `apps/arkscope-web/src/PortfolioActivity.tsx` | Activity filters/table, expandable broker/manual/unmatched/gap detail, and annotation drawer/confirmation. |
| `apps/arkscope-web/src/PortfolioRecentActivity.tsx` | Pure compact recent-activity summary that only requests navigation. |
| `apps/arkscope-web/src/Holdings.tsx` | Insert the final activity tab and conditionally load/render the wide recent panel. |
| `apps/arkscope-web/src/styles.css` | Feature-scoped activity table/filter/detail/two-column layout; no new breakpoint. |
| `apps/arkscope-web/src/PortfolioActivity.test.tsx` | Fifteen activity interaction/state contracts. |
| `apps/arkscope-web/src/PortfolioRecentActivity.test.tsx` | Three compact-summary contracts. |
| `apps/arkscope-web/src/Holdings.test.tsx` | Final tab hierarchy, mount ownership, breakpoint, navigation, and refresh integration. |
| `apps/arkscope-web/src/timeDisplay.test.ts` | One ET-first timestamp contract. |

## Additive API Contract

`GET /portfolio/activity` accepts:

```text
date_from_et=YYYY-MM-DD
date_to_et=YYYY-MM-DD
account_id=<local integer>
symbol=<case-insensitive symbol text>
source=broker|manual|system
state=realized_gain|realized_loss|realized_flat|outcome_unknown|unmatched|manual_adjustment|coverage_gap|history_start
recent=true|false
limit=1..200 (default 100)
cursor=<opaque URL-safe cursor>
```

`recent=true` cannot be combined with explicit dates. `date_from_et` must not
be later than `date_to_et`. The response never contains `broker_account_id`:

```json
{
  "accounts": [
    {
      "id": 2,
      "label": "IBKR · 1a2b3c4d",
      "broker": "ibkr",
      "broker_account_id_hash": "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
      "archived": false
    }
  ],
  "history_started_at_utc": "2026-07-14T05:00:00+00:00",
  "items": [
    {
      "id": "order:2:70001",
      "kind": "order",
      "occurred_at_utc": "2026-07-15T14:31:00+00:00",
      "account": {
        "id": 2,
        "label": "IBKR · 1a2b3c4d",
        "broker": "ibkr",
        "broker_account_id_hash": "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809"
      },
      "symbol": "AAPL",
      "asset_class": "stock",
      "currency": "USD",
      "source": "broker",
      "state": "realized_gain",
      "objective": {
        "side": "sell",
        "quantity": 10.0,
        "average_price": 220.0,
        "gross_notional": 2200.0,
        "gross_notional_kind": "deterministic_arithmetic",
        "commission": 1.0,
        "commission_currency": "USD",
        "realized_pnl": 125.0,
        "realized_outcome": "gain",
        "position_direction": "reduce",
        "close_scope": "partial",
        "position_context": "complete"
      },
      "annotation": {
        "intent_label": "profit_take",
        "note": "trimmed one third",
        "updated_at_utc": "2026-07-15T14:40:00+00:00"
      },
      "fills": [
        {
          "family_root_id": 31,
          "effective_revision_id": 32,
          "revisions": [
            {
              "id": 31,
              "exec_id": "0001",
              "is_effective": false,
              "corrects_exec_id": null,
              "commission_revisions": []
            },
            {
              "id": 32,
              "exec_id": "0001.01",
              "is_effective": true,
              "corrects_exec_id": "0001",
              "commission_revisions": [
                {
                  "id": 90,
                  "commission": 1.0,
                  "currency": "USD",
                  "realized_pnl": 125.0,
                  "is_latest": true
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "summary": {
    "item_count": 1,
    "unmatched_count": 0,
    "recent_window_days": null
  },
  "next_cursor": null
}
```

Kind-specific payloads are discriminated and exact:

- `order` and `execution`: `objective`, `fills`, optional annotation;
- `unmatched`: before/after/expected/residual quantities, from/to UTC,
  coverage and reason, optional annotation;
- `manual_adjustment`: action, field-level `{field,before,after}` changes,
  no objective P&L, optional annotation;
- `coverage_gap`: affected safe account or null, from/to UTC, capture run ids,
  and typed reason; never annotatable; and
- `history_start`: safe account, first successful capture time/run id; never
  annotatable.

Annotation writes are full replacement, not patch semantics:

```http
PUT /portfolio/activity/annotations/{activity_id}
{"intent_label":"profit_take","note":"trimmed one third"}

DELETE /portfolio/activity/annotations/{activity_id}
```

`PUT` requires at least one non-empty user field. Explicit `intent_label:null`
clears that field while preserving the supplied note. Clearing both fields is
done through `DELETE`, which is idempotent. Marker IDs are never valid targets.

## Locked Python Domain Types

The implementation may split declarations within `src/portfolio_activity.py`,
but names and serialized fields remain exact:

```python
@dataclass(frozen=True)
class ActivityAccount:
    id: int
    label: str
    broker: str
    broker_account_id_hash: str | None
    archived: bool

@dataclass(frozen=True)
class ActivityAnnotation:
    intent_label: IntentLabel | None
    note: str
    updated_at_utc: str

@dataclass(frozen=True)
class CommissionRevision:
    id: int
    first_observed_run_id: int
    first_observed_at_utc: str
    commission: float | None
    currency: str | None
    realized_pnl: float | None
    yield_value: float | None
    yield_redemption_date: int | None
    is_latest: bool

@dataclass(frozen=True)
class ExecutionRevision:
    id: int
    exec_id: str
    origin: Literal["gateway", "flex"]
    first_observed_run_id: int
    first_observed_at_utc: str
    execution_time_utc: str
    broker_con_id: str
    symbol: str
    asset_class: str
    currency: str
    exchange: str
    side: str
    quantity: float
    price: float
    order_id: int | None
    perm_id: int | None
    client_id: int | None
    order_ref: str | None
    liquidation: int | None
    cumulative_quantity: float | None
    average_price: float | None
    corrects_exec_id: str | None
    is_effective: bool
    commission_revisions: list[CommissionRevision]

@dataclass(frozen=True)
class ActivityFill:
    family_root_id: int
    effective_revision_id: int
    revisions: list[ExecutionRevision]

@dataclass(frozen=True)
class ProviderTotals:
    commission: float | None
    commission_currency: str | None
    realized_pnl: float | None
    realized_outcome: Literal["gain", "loss", "flat", "unknown"]

@dataclass(frozen=True)
class PositionEffect:
    position_direction: Literal["increase", "reduce", "unknown"]
    close_scope: Literal["none", "partial", "complete", "unknown"]
    position_context: Literal["complete", "unknown"]

@dataclass(frozen=True)
class ActivityObjective:
    side: Literal["buy", "sell", "mixed", "unknown"]
    quantity: float
    average_price: float | None
    gross_notional: float | None
    gross_notional_kind: Literal["deterministic_arithmetic"]
    commission: float | None
    commission_currency: str | None
    realized_pnl: float | None
    realized_outcome: Literal["gain", "loss", "flat", "unknown"]
    position_direction: Literal["increase", "reduce", "unknown"]
    close_scope: Literal["none", "partial", "complete", "unknown"]
    position_context: Literal["complete", "unknown"]

@dataclass(frozen=True)
class BrokerActivityItem:
    id: str
    kind: Literal["order", "execution"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str | None
    asset_class: str | None
    currency: str | None
    source: Literal["broker"]
    state: Literal[
        "realized_gain", "realized_loss", "realized_flat", "outcome_unknown"
    ]
    objective: ActivityObjective
    annotation: ActivityAnnotation | None
    fills: list[ActivityFill]

@dataclass(frozen=True)
class UnmatchedActivityItem:
    id: str
    kind: Literal["unmatched"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str | None
    asset_class: str | None
    currency: str | None
    source: Literal["broker"]
    state: Literal["unmatched"]
    annotation: ActivityAnnotation | None
    from_run_id: int
    to_run_id: int
    from_as_of_utc: str
    to_as_of_utc: str
    before_quantity: float
    after_quantity: float
    expected_quantity: float
    residual_quantity: float
    execution_coverage: Literal["complete", "incomplete", "gap"]
    reason_code: str

@dataclass(frozen=True)
class ActivityFieldChange:
    field: str
    before: Any
    after: Any

@dataclass(frozen=True)
class ManualActivityItem:
    id: str
    kind: Literal["manual_adjustment"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str
    source: Literal["manual"]
    state: Literal["manual_adjustment"]
    annotation: ActivityAnnotation | None
    position_id: int
    action: Literal["create", "update", "close"]
    changes: list[ActivityFieldChange]

@dataclass(frozen=True)
class CoverageGapItem:
    id: str
    kind: Literal["coverage_gap"]
    occurred_at_utc: str
    account: ActivityAccount | None
    source: Literal["system"]
    state: Literal["coverage_gap"]
    from_run_id: int | None
    to_run_id: int
    from_as_of_utc: str | None
    to_as_of_utc: str
    reason_code: Literal["execution_leg_incomplete", "broker_day_gap"]

@dataclass(frozen=True)
class HistoryStartItem:
    id: str
    kind: Literal["history_start"]
    occurred_at_utc: str
    account: ActivityAccount
    source: Literal["system"]
    state: Literal["history_start"]
    capture_run_id: int

PortfolioActivityItem: TypeAlias = (
    BrokerActivityItem | UnmatchedActivityItem | ManualActivityItem
    | CoverageGapItem | HistoryStartItem
)

@dataclass(frozen=True)
class ActivitySummary:
    item_count: int
    unmatched_count: int
    recent_window_days: int | None

@dataclass(frozen=True)
class PortfolioActivityPage:
    accounts: list[ActivityAccount]
    history_started_at_utc: str | None
    items: list[PortfolioActivityItem]
    summary: ActivitySummary
    next_cursor: str | None
```

Manual items deliberately omit `objective`; gap/history items deliberately
omit `annotation`. Frontend types must preserve this discriminated shape rather
than making every field optional on one loose interface.

## Projection Rules

### Effective executions and order groups

1. Partition executions by `(portfolio_account_id, correction_family)`.
2. `family_root_id` is the minimum immutable local execution row id in that
   family; effective revision is the newest `(first_observed_run_id, id)`.
3. Partition effective families with positive `perm_id` by
   `(portfolio_account_id, perm_id)`. Effective families with null/non-positive
   `perm_id` use their `family_root_id` and remain independent even when
   `order_id` matches.
4. Group time is the latest effective execution time; detail preserves every
   fill/revision time.
5. Fill revisions and commission revisions sort oldest-first for audit; the
   activity feed sorts groups newest-first.
6. Group-level symbol, asset class, or currency is returned only when every
   effective fill agrees. A disagreement preserves all fill detail, makes the
   common header field null, and prevents currency-dependent aggregate claims;
   the symbol filter still matches any effective fill in the group.

### Objective result

| Evidence | Projection |
| --- | --- |
| all effective sides are `BUY/BOT` | `side=buy` |
| all effective sides are `SELL/SLD` | `side=sell` |
| known buy and sell both occur | `side=mixed`; position effect unknown |
| any unknown side | `side=unknown`; position effect unknown |
| every effective fill has latest same-currency commission | finite sum |
| any commission missing/mixed/non-finite aggregate | null |
| every effective fill has latest provider `realized_pnl` | finite sum and gain/loss/flat |
| any realized leg missing/non-finite aggregate | null and `outcome_unknown` |
| complete unambiguous position window | derive direction + close scope |
| incomplete/gap/ambiguous/mismatched position window | both unknown |

### Coverage markers

- Per-account history starts at its first terminal run whose account,
  execution, and position legs are all complete and whose state is
  `succeeded` or `partial`. `partial` is included because observation capture
  may be complete before a separate canonical apply failure; blocked, failed,
  interrupted, running, or incomplete-leg runs cannot establish the baseline.
- Top-level `history_started_at_utc` is the earliest per-account history marker
  among accounts admitted by the current account filter; it is null when no
  account has a valid baseline.
- A failed/partial/not-attempted execution leg produces a typed gap marker; a
  run with no discovered-account mapping produces one global marker rather
  than pretending no account was affected.
- An account filter retains a global unknown-account gap marker because the
  run could have affected that account; the UI labels its scope unknown rather
  than hiding it or assigning it to a specific account.
- Consecutive complete execution runs for an account on different ET dates
  produce a cross-broker-day marker.
- Markers are derived from run facts and cursor/filter like other headers, but
  are not inserted into any event table.

## Test Accounting

- Grounded backend baseline at `c5cd91f`: **4302 collected**, with the known
  canonical family `4191 passed / 30 failed / 74 skipped / 18 warnings /
  7 errors`.
- Planned backend delta: **+33 / -0** collected:
  - Task 1 annotations/schema: +8;
  - Task 2 broker projection: +8;
  - Task 3 manual/unmatched/coverage/filtering: +8;
  - Task 4 API/mount/privacy: +9.
- Expected backend head collection: **4335**, expected passed **4224** when the
  pre-existing canonical family remains identical.
- Grounded frontend baseline: **44 files / 426 tests**.
- Planned frontend delta: **+24 / -0** tests and two new test files:
  - Task 5 activity/time surface: +16;
  - Task 6 recent panel/Holdings integration: +8.
- Expected frontend head: **46 files / 450 tests**.
- Replacing the existing `does_not_render_an_unfinished_activity_tab_or_placeholder`
  assertion with the final four-tab contract is a 1:1 evolution and contributes
  zero net tests.

---

### Task 1: User-Owned Activity Annotation Foundation

**Files:**
- Create: `src/portfolio_activity.py`
- Modify: `src/portfolio_overview.py`
- Create: `tests/test_portfolio_activity.py`
- Test: `tests/test_portfolio_overview.py`

**Interfaces:**
- Consumes: existing `PortfolioStore(path)`, `PortfolioObservationStore(path)`, observation/manual-journal tables, and safe account-label behavior.
- Produces: `ActivityFilters`, `ActivityAnnotation`, `PortfolioActivityStore(path)`, `list_activity(filters, *, now_utc=None)`, `put_annotation(activity_id, *, intent_label, note)`, `delete_annotation(activity_id)`, and public `safe_portfolio_account_label(account)`.

- [ ] **Step 1: Write eight collected RED schema/annotation tests**

Create `tests/test_portfolio_activity.py` with local fixtures that seed facts
through public `PortfolioStore` and `PortfolioObservationStore` APIs. Do not
import helpers from another test module. Add these exact collected contracts:

- `test_activity_schema_has_non_cascading_annotation_fk_and_constraints`
- `test_annotation_round_trips_each_supported_target`, parameterized over
  `order`, `execution`, `unmatched`, and `manual_adjustment` (four collected
  cases)
- `test_annotation_replacement_is_user_owned_and_does_not_mutate_facts`
- `test_annotation_rejects_unknown_target_invalid_intent_and_empty_payload`
- `test_annotation_delete_is_idempotent_and_leaves_target_history`

The schema test must inspect `sqlite_master`, `PRAGMA foreign_key_list`, and
`PRAGMA index_list` and prove:

```python
assert "portfolio_activity_annotations" in tables
assert all(row["on_delete"].upper() != "CASCADE" for row in foreign_keys)
assert unique_target_index_exists
with pytest.raises(sqlite3.IntegrityError):
    insert_invalid_intent_directly()
```

The parameterized target test must seed all four real target shapes and verify
the stored identity is local only:

```python
saved = activity.put_annotation(
    target.activity_id,
    intent_label="profit_take",
    note="trimmed exposure",
)
assert saved.intent_label == "profit_take"
assert saved.note == "trimmed exposure"
assert "DU123" not in json.dumps(asdict(saved), sort_keys=True)
```

- [ ] **Step 2: Run the Task 1 tests and verify RED**

Run:

```bash
pytest tests/test_portfolio_activity.py tests/test_portfolio_overview.py -q
```

Expected: collection/import failure because `src.portfolio_activity` and the
public safe-label helper do not exist. Confirm the failure occurs before any
implementation change.

- [ ] **Step 3: Implement the annotation schema and exact identities**

In `src/portfolio_activity.py`, define these constants/types and keep them the
single validation authority for store and route:

```python
ActivityKind = Literal[
    "order", "execution", "unmatched", "manual_adjustment",
    "coverage_gap", "history_start",
]
ActivitySource = Literal["broker", "manual", "system"]
ActivityState = Literal[
    "realized_gain", "realized_loss", "realized_flat", "outcome_unknown",
    "unmatched", "manual_adjustment", "coverage_gap", "history_start",
]
IntentLabel = Literal[
    "profit_take", "stop_loss", "rebalance",
    "thesis_broken", "cash_need", "other",
]
INTENT_LABELS = frozenset(get_args(IntentLabel))
ANNOTATABLE_KINDS = frozenset(
    {"order", "execution", "unmatched", "manual_adjustment"}
)

@dataclass(frozen=True)
class ActivityFilters:
    date_from_et: str | None = None
    date_to_et: str | None = None
    account_id: int | None = None
    symbol: str | None = None
    source: ActivitySource | None = None
    state: ActivityState | None = None
    recent: bool = False
    limit: int = 100
    cursor: str | None = None

@dataclass(frozen=True)
class ParsedActivityId:
    target_kind: Literal["order", "execution", "unmatched", "manual_adjustment"]
    account_id: int | None
    target_ref: str
```

Create only this new table and index. Existing observation/manual tables stay
owned by their shipped modules:

```sql
CREATE TABLE IF NOT EXISTS portfolio_activity_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_kind TEXT NOT NULL CHECK(target_kind IN (
        'order','execution','unmatched','manual_adjustment'
    )),
    portfolio_account_id INTEGER NOT NULL
        REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    target_ref TEXT NOT NULL,
    intent_label TEXT CHECK(intent_label IS NULL OR intent_label IN (
        'profit_take','stop_loss','rebalance','thesis_broken','cash_need','other'
    )),
    note TEXT NOT NULL DEFAULT '',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK(intent_label IS NOT NULL OR length(trim(note)) > 0),
    UNIQUE(target_kind, portfolio_account_id, target_ref)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_activity_annotations_account
ON portfolio_activity_annotations(portfolio_account_id, updated_at_utc DESC, id DESC);
```

`PortfolioActivityStore.__init__` must initialize `PortfolioStore` and
`PortfolioObservationStore` first, then this schema, all on the same path. Its
connection uses the existing `WAL` best effort, `busy_timeout=5000`, and
`foreign_keys=ON` house pattern.

Implement strict local activity-id parsing:

```python
def _parse_annotatable_id(activity_id: str) -> ParsedActivityId:
    # order:<account_id>:<perm_id>
    # execution:<account_id>:<family_root_id>
    # unmatched:<row_id>
    # manual:<row_id>
    # Reject signs, floats, empty segments, non-positive perm ids, markers,
    # and extra segments.
```

Within one `BEGIN IMMEDIATE` transaction, resolve the target against its fact
table, obtain/verify the local account id, then upsert the complete annotation.
For an execution target, `family_root_id` must be the minimum row id for that
account/correction family and its effective revision must have no positive
`perm_id`; a correction row id or a fill already represented by an order group
is not accepted as another logical target. For an order target, at least one
effective execution family with that account/positive perm id must exist.
`unmatched` and `manual` ids resolve their account from their own immutable
rows. Add the grouped-execution rejection to
`test_annotation_rejects_unknown_target_invalid_intent_and_empty_payload` so
the stricter target rule changes no collection accounting.

Normalize `intent_label` against `INTENT_LABELS`; normalize `note` with
`strip()`. Reject a replacement whose normalized intent is null and note is
empty. `delete_annotation` resolves a valid real target, deletes only the
annotation row, and returns whether an annotation existed; a second delete is
therefore `False` without deleting history.

- [ ] **Step 4: Export and reuse the safe account-label helper**

Rename `_safe_label` in `src/portfolio_overview.py` to
`safe_portfolio_account_label`, update its existing call site, and import that
public function from `src/portfolio_activity.py`. Do not change its behavior:

```python
def safe_portfolio_account_label(account: PortfolioAccount) -> str:
    raw_id = account.broker_account_id
    if raw_id and raw_id in account.label:
        if account.broker_account_id_hash:
            return f"{account.broker.upper()} · {account.broker_account_id_hash[:8]}"
        return account.broker.upper()
    return account.label
```

- [ ] **Step 5: Run Task 1 GREEN and commit**

Run:

```bash
pytest tests/test_portfolio_activity.py tests/test_portfolio_overview.py -q
```

Expected: the existing overview tests plus exactly eight collected activity
tests pass. Then commit only Task 1 files:

```bash
git add src/portfolio_activity.py src/portfolio_overview.py tests/test_portfolio_activity.py tests/test_portfolio_overview.py
git commit -m "feat: add portfolio activity annotations"
```

### Task 2: Correction-Aware Broker Activity Projection

**Files:**
- Modify: `src/portfolio_activity.py`
- Modify: `tests/test_portfolio_activity.py`

**Interfaces:**
- Consumes: Task 1 `PortfolioActivityStore`, stable activity targets, existing execution/commission/position/capture rows.
- Produces: `PortfolioActivityStore.list_activity(filters: ActivityFilters, *, now_utc: datetime | None = None) -> PortfolioActivityPage` for broker `order` and `execution` items plus exact revision detail.

- [ ] **Step 1: Add eight RED broker-projection tests**

Add these exact tests; helper `execution(...)` must accept explicit
`perm_id`, `order_id`, `con_id`, `symbol`, `side`, `quantity`, `price`, and
`execution_time` so each test uses real capture input shapes:

- `test_same_account_perm_id_groups_effective_fills_but_never_crosses_accounts`
- `test_missing_perm_id_keeps_same_order_id_as_independent_execution_rows`
- `test_correction_selects_latest_effective_revision_and_preserves_lineage`
- `test_late_commission_revisions_join_exact_execution_without_mutating_it`
- `test_group_totals_require_every_effective_provider_leg_and_one_currency`
- `test_group_arithmetic_returns_null_on_float_overflow_instead_of_zero`
- `test_complete_unambiguous_position_windows_classify_direction_and_close_scope`
- `test_incomplete_ambiguous_or_sign_flip_context_keeps_position_effect_unknown`

The grouping tests must pin account scope and the `order_id` trap, including
both null and zero `perm_id` as independent identities:

```python
assert [item.id for item in page.items if item.kind == "order"] == ["order:2:70001"]
assert len(order.fills) == 2
assert {item.id for item in page.items if item.kind == "execution"} == {
    f"execution:{account_id}:{first_root_id}",
    f"execution:{account_id}:{second_root_id}",
}
```

The correction test must prove the old revision remains expandable but is not
double-counted:

```python
assert [r.exec_id for r in fill.revisions] == ["0001", "0001.01"]
assert [r.is_effective for r in fill.revisions] == [False, True]
assert order.objective.quantity == corrected_quantity
```

The provider-completeness test must cover zero as a valid value, null as
unknown, mixed commission currency as null rather than a partial aggregate,
and conflicting group-level contract/currency fields as null while preserving
every fill.

- [ ] **Step 2: Run the new tests and verify the intended RED reasons**

Run each new test by name, then the file:

```bash
pytest tests/test_portfolio_activity.py -q
```

Expected: Task 1 tests remain green; the eight new tests fail because
`list_activity` has no broker projection. A passing projection test before the
implementation indicates the fixture failed to seed the intended fact.

- [ ] **Step 3: Implement bounded effective-header selection**

Add frozen DTOs for safe accounts, objective result, commission revision,
execution revision, logical fill, annotation, broker item, and page. Build one
SQL CTE that ranks immutable execution revisions without altering the shipped
tables:

```sql
WITH ranked_execution AS (
  SELECT e.*,
         MIN(e.id) OVER (
           PARTITION BY e.portfolio_account_id, e.correction_family
         ) AS family_root_id,
         ROW_NUMBER() OVER (
           PARTITION BY e.portfolio_account_id, e.correction_family
           ORDER BY e.first_observed_run_id DESC, e.id DESC
         ) AS effective_rank
  FROM portfolio_broker_executions e
), effective_execution AS (
  SELECT * FROM ranked_execution WHERE effective_rank=1
)
```

Group headers use non-null `(account_id, perm_id)` and null-perm
`family_root_id` identities. Apply account/symbol/date/source/state/cursor in
SQL and `LIMIT limit + 1`; do not load revision detail until global header
selection chooses the page.

Fetch revisions for only selected correction families and commission rows for
only those revision exec ids. Commission revision ordering is
`(first_observed_run_id, id)`; latest is the final row for that exact exec id.

- [ ] **Step 4: Implement exact objective helpers**

Use small pure helpers with these signatures so tests can exercise every
branch without SQL fixtures:

The helpers have these exact signatures: `_signed_quantity(side: str,
quantity: float) -> float | None`, `_finite_sum(values: Collection[float]) ->
float | None`, `_weighted_average(fills: Collection[EffectiveFill]) -> float |
None`, `_provider_totals(fills: Collection[ActivityFill]) -> ProviderTotals`,
and `_position_effect(*, before_quantity: float, after_quantity: float,
signed_quantity: float, context_complete: bool) -> PositionEffect`.

`_finite_sum` must use `math.fsum`, catch `OverflowError`, and reject a
non-finite result. `_weighted_average` uses absolute fill quantity as weight,
returns null for an empty/zero denominator, and applies `_finite_sum` to both
the denominator and weighted numerator.

`_position_effect` uses an epsilon of `1e-9`, requires
`after == before + signed`, and returns:

```text
before 0 -> nonzero after: increase / none
same sign, abs(after) > abs(before): increase / none
same sign, 0 < abs(after) < abs(before): reduce / partial
nonzero before -> zero after: reduce / complete
sign flip, mismatch, or incomplete evidence: unknown / unknown
```

Before calling it for an item, prove the conservative context conditions in
Global Constraints. If another effective order/execution activity for the same
account/conId shares the capture window, set `context_complete=False`.

- [ ] **Step 5: Run Task 2 GREEN and commit**

Run:

```bash
pytest tests/test_portfolio_activity.py -q
```

Expected: exactly 16 collected tests pass. Commit:

```bash
git add src/portfolio_activity.py tests/test_portfolio_activity.py
git commit -m "feat: project broker portfolio activity"
```

### Task 3: Manual, Unmatched, Coverage, Filters, and Cursor

**Files:**
- Modify: `src/portfolio_activity.py`
- Modify: `tests/test_portfolio_activity.py`

**Interfaces:**
- Consumes: Task 2 broker page candidates and Task 1 annotations.
- Produces: complete `list_activity(filters: ActivityFilters, *, now_utc:
  datetime | None = None) -> PortfolioActivityPage` across all activity kinds,
  exact five-axis filters, recent summary, and opaque cursor pagination.

- [ ] **Step 1: Add eight RED integration tests**

Add:

- `test_manual_adjustment_projection_replays_historical_symbol_and_field_changes`
- `test_manual_adjustment_never_claims_execution_price_commission_or_realized_pnl`
- `test_unmatched_projection_exposes_before_after_expected_residual_window_and_coverage`
- `test_first_successful_complete_capture_creates_history_start_not_a_fake_trade`
- `test_failed_or_incomplete_execution_leg_creates_explicit_gap_marker`
- `test_cross_et_day_complete_runs_create_gap_without_rewriting_empty_activity`
- `test_activity_filters_date_account_symbol_source_and_state_independently`
- `test_activity_cursor_is_deterministic_and_recent_scope_uses_seven_et_dates`

The manual history test must create `AAPL`, rename it to `HAPN`, then change
quantity. It proves older rows remain `AAPL`, later rows filter as `HAPN`, and
the current mutable position name is not blindly joined onto all history.

The gap tests must prove a marker appears even when there are no execution
rows in the interval, and that the API does not insert a marker table row:

```python
assert marker.kind == "coverage_gap"
assert marker.reason_code in {"execution_leg_incomplete", "broker_day_gap"}
assert rows(activity, "SELECT name FROM sqlite_master WHERE name='portfolio_activity_events'") == []
```

The filter test may loop over the five axes inside one collected test, but each
iteration must build a fresh `ActivityFilters` and assert both inclusion and
exclusion. Archive one seeded account after its fact is recorded and prove the
historical item remains readable with `account.archived is True`; account
archive is not history deletion. The cursor test must insert equal timestamps
and prove no duplicate or omission over two pages.

- [ ] **Step 2: Run and confirm RED without regressing broker tests**

```bash
pytest tests/test_portfolio_activity.py -q
```

Expected: 16 Task 1/2 tests pass and the eight new tests fail for missing
manual/unmatched/marker/filter projection.

- [ ] **Step 3: Add bounded source-header queries and historical manual symbol replay**

For manual symbol, query the most recent `symbol` change at or before each
adjustment; use the current position symbol only as a fallback for legacy rows
that predate journaling:

```sql
COALESCE(
  (
    SELECT json_extract(c2.after_json, '$')
    FROM portfolio_manual_adjustments a2
    JOIN portfolio_manual_adjustment_changes c2
      ON c2.adjustment_id=a2.id AND c2.field='symbol'
    WHERE a2.position_id=a.position_id AND a2.id<=a.id
    ORDER BY a2.id DESC LIMIT 1
  ),
  p.symbol
) AS historical_symbol
```

Build separate bounded header queries for manual, unmatched, gap, and
history-start kinds. Each query applies its available filters and returns at
most `limit + 1`; merge headers with Task 2 broker headers, sort by
`(occurred_at_utc, activity_id)` descending, apply cursor, select `limit`, then
load detail only for selected headers.

Build the response account map with
`portfolio.list_accounts(include_archived=True, ensure_manual=False)` so a
historical activity survives archive and a read never creates the Manual shell.
Run every label through `safe_portfolio_account_label` before constructing
`ActivityAccount`.

- [ ] **Step 4: Implement filters, recent scope, and opaque cursor**

`ActivityFilters` validates exact literals, uppercases/strips symbol, parses ET
dates, rejects reversed dates and explicit-date plus `recent=true`, and clamps
nothing silently. `limit` outside 1-200 is an error.

Date filtering uses the ET calendar date of each item's primary time: effective
execution time for broker rows, `to_as_of_utc` for unmatched rows,
`occurred_at_utc` for manual adjustments, and marker time for system rows.
Bounds are inclusive.

Encode the last selected tuple as canonical JSON plus URL-safe base64 without
padding; decode with strict key/type/ISO checks:

```python
payload = {"occurred_at_utc": item.occurred_at_utc, "activity_id": item.id}
cursor = base64.urlsafe_b64encode(
    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
).decode("ascii").rstrip("=")
```

For `recent=true`, compute ET dates from an injected/testable `now_utc` and set
`recent_window_days=7` in the response summary. `unmatched_count` counts rows
within the same effective filter/recent window, not all retained history.
`item_count` is exactly the number of items in the returned page, not an
unbounded total-count query.

- [ ] **Step 5: Run Task 3 GREEN and commit**

```bash
pytest tests/test_portfolio_activity.py -q
```

Expected: exactly 24 collected tests pass. Commit:

```bash
git add src/portfolio_activity.py tests/test_portfolio_activity.py
git commit -m "feat: complete portfolio activity projection"
```

### Task 4: Provider-Free Activity API and Guarded Annotation Routes

**Files:**
- Create: `src/api/routes/portfolio_activity.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/app.py`
- Create: `tests/test_portfolio_activity_routes.py`

**Interfaces:**
- Consumes: Task 3 `PortfolioActivityStore`, `ActivityFilters`, and annotation methods.
- Produces: mounted `GET /portfolio/activity`, `PUT /portfolio/activity/annotations/{activity_id}`, and `DELETE /portfolio/activity/annotations/{activity_id}`.

- [ ] **Step 1: Write nine RED route tests**

Create these exact tests using handler-direct calls for branch logic and one
real `create_app()` mount test:

- `test_portfolio_activity_router_mounts_on_real_app`
- `test_get_activity_fresh_profile_is_empty_zero_authority_write_and_never_calls_gateway`
- `test_get_activity_serializes_exact_shape_without_raw_broker_account_id`
- `test_get_activity_threads_all_filters_recent_limit_and_cursor_to_store`
- `test_get_activity_maps_invalid_date_cursor_and_limit_to_typed_400`
- `test_put_annotation_requires_write_gate_and_uses_full_replacement`
- `test_put_annotation_maps_missing_target_to_404_and_invalid_input_to_400`
- `test_delete_annotation_requires_gate_and_returns_idempotent_deleted_flag`
- `test_activity_storage_failure_is_typed_without_raw_exception_or_account_id`

Construct the store first so schema initialization is outside the assertion.
The fresh-profile test must then compare domain-row/account counts before and
after to prove a GET does not create the Manual shell, fact, or annotation,
and patch any provider/capture seam to raise if called. The privacy test seeds
a legacy account label containing `DU123`,
serializes the complete response, and asserts:

```python
encoded = json.dumps(out, sort_keys=True)
assert "DU123" not in encoded
assert '"broker_account_id"' not in encoded
assert "broker_account_id_hash" in encoded
```

The write tests must pin exact permission calls:

```python
(
  "portfolio_activity_annotation_write",
  {"activity_id": activity_id, "action": "replace"},
)
(
  "portfolio_activity_annotation_write",
  {"activity_id": activity_id, "action": "delete"},
)
```

- [ ] **Step 2: Run route tests and verify RED**

```bash
pytest tests/test_portfolio_activity_routes.py -q
```

Expected: import failure because the route/dependency do not exist.

- [ ] **Step 3: Add cached dependency and router**

Add to `src/api/dependencies.py`:

```python
@lru_cache(maxsize=1)
def get_portfolio_activity_store():
    from src.portfolio_activity import PortfolioActivityStore
    return PortfolioActivityStore(_local_state_db_path())
```

Create an `APIRouter(prefix="/portfolio/activity", tags=["portfolio"])`.
Use FastAPI query validation for literals/integers and `ActivityFilters` for
cross-field/date/cursor validation. The GET route calls only the store.
Serialize frozen dataclasses with `dataclasses.asdict`; do not import the
private `_to_json` helper from the sibling Portfolio router.

Use a full-replacement Pydantic body:

```python
class PortfolioActivityAnnotationBody(BaseModel):
    intent_label: Literal[
        "profit_take", "stop_loss", "rebalance",
        "thesis_broken", "cash_need", "other",
    ] | None = None
    note: str = ""
```

Call `require_profile_state_write` before either mutation. Map controlled
validation to 400, missing target to 404, and SQLite/storage failure to:

```json
{"code":"portfolio_activity_unavailable","action":"retry"}
```

The unexpected storage response is HTTP 503. Do not include `str(exc)` for an
unexpected storage failure. Mount the router in `create_app()` immediately
after the existing portfolio/capture routers.

- [ ] **Step 4: Run Task 4 GREEN and backend focused ledger**

```bash
pytest tests/test_portfolio_activity.py tests/test_portfolio_activity_routes.py tests/test_portfolio_routes.py tests/test_portfolio_observations.py tests/test_portfolio_state.py -q
```

Expected: all focused tests pass; new backend collection is exactly `+33/-0`
relative to `c5cd91f`.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/portfolio_activity.py src/api/dependencies.py src/api/app.py tests/test_portfolio_activity_routes.py
git commit -m "feat: expose portfolio activity API"
```

### Task 5: Activity Client, ET-First Time, and Full Activity Surface

**Files:**
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/timeDisplay.ts`
- Modify: `apps/arkscope-web/src/timeDisplay.test.ts`
- Create: `apps/arkscope-web/src/PortfolioActivity.tsx`
- Create: `apps/arkscope-web/src/PortfolioActivity.test.tsx`
- Modify: `apps/arkscope-web/src/styles.css`

**Interfaces:**
- Consumes: Task 4 exact activity JSON and shipped P2.8 primitives.
- Produces: discriminated `PortfolioActivityItem`, `getPortfolioActivity`, `putPortfolioActivityAnnotation`, `deletePortfolioActivityAnnotation`, `formatMarketTimestamp`, and `<PortfolioActivity />`.

- [ ] **Step 1: Add one RED ET-first formatter test**

```ts
it("formats market activity in ET before local time", () => {
  expect(formatMarketTimestamp(
    "2026-07-15T14:31:00+00:00",
    { localTimeZone: "Asia/Taipei" },
  )).toBe("07-15 10:31 ET · 07-15 22:31 Asia/Taipei");
});
```

Run `npm test -- --run src/timeDisplay.test.ts` from
`apps/arkscope-web`; expect RED because the export does not exist. Implement it
beside, not instead of, `formatSystemTimestamp`.

- [ ] **Step 2: Add fifteen RED component contracts**

Create `PortfolioActivity.test.tsx` with the established `createRoot + act +
vi.stubGlobal("fetch") + DOM query` house harness, not Testing Library. Add:

```text
1. loading then honest empty/history-not-started state
2. broker group renders direct facts separately from confirmed intent
3. row action expands immutable fills, corrections, and commission revisions
4. missing-perm execution rows remain independent
5. pending commission/realized P&L stays unknown, never zero/profit/loss
6. unmatched row exposes before/after/expected/residual/window/coverage
7. manual adjustment exposes field changes and no execution/P&L claim
8. history-start and coverage-gap rows remain visible
9. all five filters plus ET dates produce the exact encoded GET query
10. next_cursor triggers one append request without duplicating rows
11. delayed older filter response cannot clobber a newer response
12. annotation drawer saves the exact full-replacement PUT payload
13. clearing an annotation uses ConfirmDialog then DELETE, never window.confirm
14. market rows show ET first and local second
15. failed read shows cause/next action without raw exception detail
```

Use realistic discriminated fixtures, including a correction and two
commission revisions. The objective/intent test must assert that labels are in
different DOM owners, not merely both present in `textContent`.

- [ ] **Step 3: Run RED and add exact API types/helpers**

Run:

```bash
npm test -- --run src/PortfolioActivity.test.tsx src/timeDisplay.test.ts
```

Expected: missing module/types/helpers. Then define exact discriminated unions
matching the Additive API Contract. The query builder must use
`URLSearchParams`, omit unset/default fields, and never manually concatenate
unescaped symbol/cursor values.

```ts
export function getPortfolioActivity(
  filters: PortfolioActivityFilters = {},
): Promise<PortfolioActivityPage>;
export function putPortfolioActivityAnnotation(
  activityId: string,
  body: { intent_label: PortfolioIntentLabel | null; note: string },
): Promise<PortfolioActivityAnnotation>;
export function deletePortfolioActivityAnnotation(
  activityId: string,
): Promise<{ deleted: boolean; activity_id: string }>;
```

- [ ] **Step 4: Implement `PortfolioActivity` with existing primitives**

The component owns one request generation counter so stale responses cannot
replace newer filter state. After successful annotation PUT/DELETE, update the
matching local item from the typed mutation response (or clear it after a
successful delete) and close the overlay; do not launch a second read whose
failure could obscure a mutation that already committed. On mutation failure,
keep the editor and typed error visible. Render:

- one compact filter band with ET date inputs, account/source/state selects,
  symbol input, and icon-backed refresh/reset commands;
- one history-start statement above the table;
- a `DataTable` with ET time, safe account, symbol/event, source, objective,
  and confirmed-intent columns;
- row actions `查看明細` and, only for annotatable kinds, `編輯註記`;
- an inline expanded detail region for fills/corrections/commissions,
  unmatched arithmetic, or manual field changes;
- one shared `Drawer` for intent/note edit; and
- one shared `ConfirmDialog` for annotation deletion.

Use `StatusBadge` only for the common loading/read/coverage mapping fixed in
Global Constraints; render financial outcome and neutral facts as labeled
text. Do not create a new chip class. Unknown is rendered explicitly as
`未知`, never as an empty numeric cell or zero.

Use this single user-facing intent map in the component (and nowhere else):

```ts
const INTENT_LABELS_ZH: Record<PortfolioIntentLabel, string> = {
  profit_take: "獲利了結",
  stop_loss: "停損",
  rebalance: "再平衡",
  thesis_broken: "投資論點失效",
  cash_need: "資金需求",
  other: "其他",
};
```

Objective realized outcome labels are `已實現獲利 / 已實現虧損 / 已實現損益為零 /
結果未知`; they never reuse the intent wording. `broker / manual / system`
render as `Broker / 手動紀錄 / 系統覆蓋`.

Normal-mode failures use authored copy: read=`活動載入失敗；請重新整理`,
annotation write=`註記未儲存；請重試`, and delete=`註記未清除；請重試`.
Do not render `error.message`, response body, or stack text in this surface.

Add only feature-scoped classes (`portfolio-activity-*`). The table wrapper is
the horizontal scroll owner; numeric cells remain nowrap/tabular. Do not add
`@media`; the full activity tab remains scrollable at mobile widths.

- [ ] **Step 5: Run Task 5 GREEN and commit**

```bash
npm test -- --run src/PortfolioActivity.test.tsx src/timeDisplay.test.ts
npm run typecheck
```

Expected: 16 net-new tests pass and TypeScript passes. Commit:

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/timeDisplay.ts apps/arkscope-web/src/timeDisplay.test.ts apps/arkscope-web/src/PortfolioActivity.tsx apps/arkscope-web/src/PortfolioActivity.test.tsx apps/arkscope-web/src/styles.css
git commit -m "feat: render portfolio activity journal"
```

### Task 6: Final Holdings Tab and Contextual Recent Activity

**Files:**
- Create: `apps/arkscope-web/src/PortfolioRecentActivity.tsx`
- Create: `apps/arkscope-web/src/PortfolioRecentActivity.test.tsx`
- Modify: `apps/arkscope-web/src/Holdings.tsx`
- Modify: `apps/arkscope-web/src/Holdings.test.tsx`
- Modify: `apps/arkscope-web/src/styles.css`

**Interfaces:**
- Consumes: Task 5 activity DTO/component, `getPortfolioActivity({recent:true,limit:5})`, and `useShellOverlay()`.
- Produces: final four-tab Holdings hierarchy and wide-only, zero-empty-width recent summary.

- [ ] **Step 1: Add three RED pure recent-summary tests**

```text
1. renders real compact rows plus recent unmatched count and calls onOpenActivity
2. renders null when both items and unmatched_count are zero
3. never renders broker raw-id-shaped fixture properties or activity detail authority
```

`PortfolioRecentActivity` is presentational: it receives the already-loaded
page and one `onOpenActivity` callback. It must not fetch, poll, mutate, or
render expanded detail.

- [ ] **Step 2: Evolve existing tab tests and add five RED Holdings contracts**

Evolve the existing three-tab/no-placeholder assertions 1:1 to pin exact final
labels and keyboard order:

```ts
expect(tabLabels()).toEqual(["持倉", "活動", "帳戶明細", "同步紀錄"]);
```

Add exactly five tests:

```text
1. PortfolioActivity mounts/fetches only while 活動 is selected
2. at 959px the recent endpoint is not called and no panel/empty width exists
3. at 961px a non-empty recent response renders beside positions
4. clicking the recent summary navigates to 活動 and removes the side panel
5. a successful manual mutation invalidates the wide recent summary once
```

Stub `matchMedia` before render using the shipped shell query; do not fake a
new breakpoint constant.

Before running those tests, evolve the existing `stubFetch` harness rather
than letting the new GET fall through to the generic `/portfolio` handler:

- add `PortfolioActivityPage` to `PortfolioApiResponse`;
- add an optional `recentHandler` argument;
- match `GET /portfolio/activity?...recent=true...` before the generic
  handler; and
- default it to an empty activity page with `unmatched_count=0`.

This is fixture maintenance, not a product behavior test, and changes no test
count. Every pre-existing Holdings test must therefore remain deterministic
without knowing recent-panel internals.

- [ ] **Step 3: Run RED and integrate the final tab**

```bash
npm test -- --run src/PortfolioRecentActivity.test.tsx src/Holdings.test.tsx
```

Expected: missing recent component, only three tabs, and no recent fetch.

Update:

```ts
type PortfolioView = "holdings" | "activity" | "account_details" | "sync_records";
```

Insert `{id:"activity", label:"活動"}` second and add `activity` to the tab
ref map. Mount `<PortfolioActivity />` only in its tabpanel. Capture polling
must remain sync-tab-only.

In `HoldingsView`, use `useShellOverlay()`. Only while the holdings tab is
active and `shellOverlay === false`, request
`getPortfolioActivity({recent:true, limit:5})`. Guard the request with a
generation id and refresh it after successful portfolio mutations. Do not poll.

Render a two-column wrapper only when the response has items or a nonzero
recent unmatched count:

```tsx
<div
  className="portfolio-holdings-layout"
  data-has-recent={String(showRecent)}
>
  <div className="portfolio-holdings-primary">{holdingsContent}</div>
  {showRecent ? (
    <PortfolioRecentActivity
      page={recentActivity}
      onOpenActivity={() => setActiveView("activity")}
    />
  ) : null}
</div>
```

CSS uses the data attribute for `minmax(0,1fr) minmax(260px,320px)` and a
single column otherwise. Because narrow mode never renders the second child,
no new media query or empty rail is needed.

- [ ] **Step 4: Run Task 6 GREEN and frontend full gates**

```bash
npm test -- --run src/PortfolioRecentActivity.test.tsx src/Holdings.test.tsx src/PortfolioActivity.test.tsx
npm test -- --run
npm run typecheck
npm run build
```

Expected: focused tests pass; full frontend is exactly **46 files / 450 tests**;
typecheck passes; production build passes with only the existing chunk-size
warning.

- [ ] **Step 5: Commit**

```bash
git add apps/arkscope-web/src/PortfolioRecentActivity.tsx apps/arkscope-web/src/PortfolioRecentActivity.test.tsx apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx apps/arkscope-web/src/styles.css
git commit -m "feat: complete portfolio activity navigation"
```

### Task 7: Regression, Responsive, Privacy, A/B, and Live Gates

**Files:**
- Modify after evidence only: `docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md`
- Do not mark the authority spec LIVE COMPLETE before review and live approval.

**Interfaces:**
- Consumes: Tasks 1-6 complete implementation.
- Produces: review-ready evidence ledger; no new product behavior.

- [ ] **Step 1: Run exact focused backend and frontend ledgers**

```bash
pytest tests/test_portfolio_activity.py tests/test_portfolio_activity_routes.py tests/test_portfolio_routes.py tests/test_portfolio_observations.py tests/test_portfolio_state.py tests/test_portfolio_capture_routes.py -q
cd apps/arkscope-web
npm test -- --run src/PortfolioActivity.test.tsx src/PortfolioRecentActivity.test.tsx src/Holdings.test.tsx src/PortfolioAccountOverview.test.tsx src/PortfolioCapturePanel.test.tsx src/timeDisplay.test.ts
npm test -- --run
npm run typecheck
npm run build
```

Record exact counts. Stop if backend new collection differs from `+33/-0` or
frontend differs from `+24/-0`; reconcile the ledger before review.

- [ ] **Step 2: Run static authority/privacy ratchets**

All commands must return zero matches unless the command explicitly checks a
required owner:

```bash
rg -n "placeOrder|cancelOrder|reqGlobalCancel|modifyOrder|exerciseOption|exerciseOptions" src/portfolio_activity.py src/api/routes/portfolio_activity.py
rg -n "postgres|psycopg|PG_DSN|DATABASE_URL" src/portfolio_activity.py src/api/routes/portfolio_activity.py tests/test_portfolio_activity.py tests/test_portfolio_activity_routes.py
rg -n "window\.confirm|@media" apps/arkscope-web/src/PortfolioActivity.tsx apps/arkscope-web/src/PortfolioRecentActivity.tsx apps/arkscope-web/src/Holdings.tsx
rg -n "portfolio_activity|PortfolioActivity" src/tools src/agents src/agents/openai_agent src/agents/anthropic_agent
rg -n "portfolio.*capture|portfolio/activity" apps/arkscope-web/src/Settings.tsx
```

Run a serialized privacy probe seeded with a raw broker id and assert that raw
value is absent from GET JSON, route errors, frontend fixtures/DOM snapshots,
generic trace, and `get_portfolio_holdings`; `broker_account_id_hash` is allowed.

Use `git diff --name-only c5cd91f...HEAD` to prove no capture reader/service,
scheduler, agent/tool registry, prompt, Settings, or provider file changed.

- [ ] **Step 3: Run fresh-profile and no-PG gates**

Against a new temporary `ARKSCOPE_PROFILE_DB`, prove:

- activity store migration creates exactly the annotation addition;
- GET returns no items and does not create a Manual account shell;
- all annotation FKs are RESTRICT/non-cascading;
- app router mounts;
- no provider/Gateway call occurs; and
- the existing no-PG smoke reports `ok:true` and `pg_attempts:[]`.

Use the repository's existing smoke command from the Slice 1/2 ledgers; do not
invent a new PG harness.

```bash
python src/smoke/pg_unreachable_e2e.py
```

Expected: `ok: true`, `pg_attempts: []`, and the existing smoke check count
remains green.

- [ ] **Step 4: Run responsive browser verification**

Use one disposable scheduler-disabled sidecar and Vite process with a seeded
temporary profile. Inspect DOM plus screenshots at:

```text
1440x900
1024x768
961x768
959x768
390x844
```

Use ports that do not displace the normal desktop process:

```bash
ARKSCOPE_API_PORT=8421 ARKSCOPE_DISABLE_SCHEDULER=1 ARKSCOPE_PROFILE_DB=/tmp/arkscope-p11-s3-visual.db python -m src.api
```

```bash
cd apps/arkscope-web
VITE_API_BASE=http://127.0.0.1:8421 ARKSCOPE_WEB_DEV_PORT=8432 npm run dev -- --host 127.0.0.1
```

Prove:

- exact four-tab order and keyboard navigation;
- no page-level horizontal overflow; activity DataTable owns its own overflow;
- ET is primary for broker execution rows;
- correction/commission/manual/unmatched expansions do not overlap adjacent rows;
- annotation Drawer and ConfirmDialog retain focus/Escape behavior;
- recent panel appears only with real content at 961+ and reserves zero width
  at 959/mobile/empty;
- no raw account id appears; and
- no disabled placeholder or duplicate activity authority exists.

Use realistic fixtures only for unavailable correction/multi-account shapes;
label screenshot evidence as fixture-backed.

- [ ] **Step 5: Run canonical backend A/B**

Create clean virgin archives/worktrees for `c5cd91f` and implementation head,
run full pytest sequentially in the same environment, and compare parsed test
IDs, not just counts. Required verdict:

```text
base collected 4302
head collected 4335
collect diff +33 / -0
base passed 4191
head passed 4224
failed sets identical 30 = 30, bidirectional diff empty
skipped 74 = 74
warnings 18 = 18
errors 7 = 7
```

If ambient counts differ, authority is same-run base/head set equality plus
exact `+33/-0`; record the observed family honestly. No A/B PASS may be claimed
from a hanging or incomplete side.

- [ ] **Step 6: Run the single-sidecar copied-profile live Gateway gate**

Only after user closes the normal desktop app/sidecar:

1. copy the real `profile_state.db` to a disposable profile and start exactly
   one branch sidecar against the copy, with the real provider config/Gateway;
2. run a manual capture and verify the activity API renders all naturally
   available current-day fills without duplicates or raw account id;
3. rerun immediately and prove execution/order row cardinality is unchanged
   while run history advances;
4. if a real late commission/correction exists, inspect its projection; if not,
   retain the reviewed fake-backed status and do not manufacture a trade;
5. create/edit/close a disposable Manual position in the copied profile and
   prove three journal rows render with historical field changes and no P&L;
6. save and clear one intent annotation and prove broker/manual fact tables are
   byte-identical across that mutation;
7. inspect history-start/gap language and the wide recent panel in real Chrome;
8. compare serialized output against a read-only lookup of the real raw account
   id and prove it is absent; and
9. stop branch Vite/sidecar/Chrome and delete only disposable copied data.

Do not mutate or clean the user's real Portfolio history to create a gate case.

- [ ] **Step 7: Reconcile ledger, mark review-ready, and commit evidence**

Update the plan header to `IMPLEMENTED FOR REVIEW` only after Steps 1-6 that
are feasible before review are complete. Record RED reasons, commit hashes,
exact counts, static results, responsive evidence, A/B verdict, live-backed vs
fake-backed conditions, and any deviation. Do not edit the spec/map to LIVE.

```bash
git add docs/superpowers/plans/2026-07-15-portfolio-1-1-slice-3-activity-journal.md
git commit -m "docs: mark portfolio activity review-ready"
```

## Reviewer Focus

1. Effective correction family is counted once while every revision remains visible.
2. Missing `perm_id` never groups by `order_id`; account scope is always part of order identity.
3. Provider totals are all-legs-or-null; zero remains valid and overflow never becomes zero.
4. Position effect is conservative and cannot narrate ambiguous multi-order windows.
5. Manual historical symbol derives from journal time, not the current mutable position row.
6. Gap/history markers are derived from run truth, not persisted fake activity.
7. Annotation validation occurs in the same write transaction, writes only its table, and requires the profile-state gate.
8. Read routes create no Manual shell, call no Gateway, and expose no raw account id.
9. Recent panel owns no data, polls nothing, navigates only, and reserves zero empty/narrow width.
10. Existing capture, canonical Holdings, Settings scheduler ownership, agents/tools/prompts, and order APIs remain untouched.

## Stop-Loss Conditions

Stop implementation and return for design review if any task requires:

- rebuilding canonical positions from execution/activity history;
- persisting gap/history markers as invented broker events;
- grouping by `order_id` without `perm_id`;
- summing incomplete provider P&L/commission as a complete result;
- inferring user intent or writing it from an agent;
- exposing a raw broker account id to API, DOM, trace, prompt, or tool;
- making an activity GET call IBKR or create profile authority rows;
- adding a scheduler, background poller, Settings control, global nav item, or
  second activity authority;
- introducing any order-side API or reusing capture client identity for
  trading;
- requiring Flex, complete pre-capture history, performance calculations,
  tax lots, manual trade entry, retention/export, or pricing/cost work; or
- changing P2.8 shell primitives/breakpoint rather than consuming them.

## Post-Review Merge Closeout

After independent implementation review, exact canonical A/B, and the user-
approved live gate are GREEN:

1. fast-forward merge the reviewed branch;
2. rerun focused backend, full frontend, typecheck, build, and no-PG smoke on
   merged `master`;
3. change the authority spec header to `PORTFOLIO 1.1 LIVE COMPLETE` while
   preserving future Flex/performance/trading deferrals;
4. change map P2.10 to all three slices LIVE and add newest-first decision-log
   evidence with the actual merge tip;
5. synchronize memory/index status without copying raw broker identity;
6. remove the Slice 3 worktree/branch after proving clean merge state; and
7. restart the normal desktop app so the merged activity surface is the only
   running sidecar.
