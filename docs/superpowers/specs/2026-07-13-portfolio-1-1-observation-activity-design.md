# Portfolio 1.1 Account Observation and Activity Design

> **Status: APPROVED DESIGN; SLICE 1 MERGED / LIVE 2026-07-14 (`fa052dc`); SLICE 2 IMPLEMENTATION PLAN OPEN / REVIEW PENDING 2026-07-14; SLICE 3 PENDING.**
> This document extends, but does not replace,
> `docs/superpowers/specs/2026-07-08-holdings-portfolio-design.md` and its
> shipped implementation. Holdings V1 remains the authority for local
> accounts, canonical positions, notes, row ownership, and
> `manual | ibkr_review | ibkr_auto` sync semantics. This specification owns
> Portfolio 1.1 broker observations, capture cadence, account-value display,
> activity history, and manual-adjustment journaling.

## 1. Decision

Portfolio 1.1 adopts a dual-layer model:

1. the existing portfolio tables remain the current-state authority; and
2. a new append-only observation layer records what IBKR reported and what
   manual financial mutations occurred from feature activation onward.

Capture records broker facts regardless of whether an IBKR-backed account is
in review or automatic sync mode. Sync mode controls only whether a complete
broker position observation may mutate canonical broker-owned position fields.

The observation layer never rebuilds, replaces, or claims to be the complete
source of canonical holdings. Event sourcing is explicitly rejected because
IB Gateway execution history is incomplete by construction: capture begins
after prior activity has already occurred, and Gateway execution queries have
a bounded current-day window. Reconstructing positions from that incomplete
event stream would conflict with the broker snapshot and the shipped Holdings
authority model.

## 2. Product Outcomes

Portfolio 1.1 should let a user answer four questions without inventing data:

1. What does each broker account report now for net liquidation, cash,
   buying power, margin, and today's profit/loss?
2. What canonical positions has ArkScope accepted locally, and when were they
   last synchronized or approved?
3. What fills, commissions, corrections, manual financial changes, and
   unexplained position changes have ArkScope observed since capture began?
4. Did a sale realize a broker-reported gain or loss, and what objective
   position effect did it have?

Portfolio 1.1 must not silently answer different questions:

- it does not claim complete pre-activation history;
- it does not call a reduction a profit-taking sale or stop-loss without user
  confirmation;
- it does not derive realized P&L when IBKR did not report it;
- it does not call IBKR account value plus manual holdings one combined net
  worth; and
- it does not place, modify, cancel, or exercise orders.

The last rule is scoped to the Portfolio 1.1 capture path. ArkScope may later
support order placement through a separately designed trading subsystem with
its own permissions, client-id domain, previews, confirmations, audit ledger,
and kill switch.

## 3. Grounded Current State

### 3.1 Shipped local authority

`src/portfolio_state.py` currently owns:

- `portfolio_accounts`;
- `portfolio_positions`; and
- `portfolio_position_notes`.

Canonical position identity for IBKR-backed holdings is local account scope
plus IBKR `conId`; symbol is display metadata. Broker-owned financial fields
are separated from user-owned notes, thesis, tags, strategy bucket, target
allocation, alert preferences, and research links.

The shipped sync modes are exactly:

- `manual`;
- `ibkr_review`; and
- `ibkr_auto`.

Manual accounts are constrained to `manual` mode. Preview is read-only;
applying a broker snapshot is separately write-gated. Broker rows cannot be
manually edited or closed, while manual rows may update financial fields and
soft-close. Existing position notes survive subsequent broker syncs.

### 3.2 Shipped IBKR read surface

`src/portfolio_ibkr.py` currently reads one read-only snapshot through the
`holdings=+60` client-id domain. It calls:

- `ib.positions()`;
- `ib.portfolio()`; and
- `ib.accountSummary()`.

The current adapter keeps position quantity, average cost, market value, and
unrealized P&L, but retains only `BaseCurrency` from account summary. It does
not preserve the other account-value tags, `PortfolioItem.realizedPNL`, broker
executions, fills, or commission reports.

The repository has no current execution/fill ledger. This is a new broker API
surface, not a UI projection over an existing table.

### 3.3 External history boundary

IB Gateway execution requests expose executions for the current broker day;
TWS can expose a longer recent window only when its Trade Log setting is
configured. Portfolio 1.1 therefore treats Gateway execution coverage as
current-day and never promises recovery of a missed prior day. See the
[official TWS API documentation](https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/).

IBKR Flex can later provide activity-statement or trade-confirmation imports,
but it has separate Client Portal credentials/query identifiers and different
freshness semantics. It is a future provenance source, not a hidden fallback
inside Gateway capture. See the
[official Flex Web Service documentation](https://ibkrcampus.com/campus/ibkr-api-page/flex-web-service/).

## 4. Authority and Observation Boundaries

### 4.1 Current-state authority

The existing account, position, and position-note tables remain the only
canonical Holdings authority consumed by the shipped Holdings UI and
`get_portfolio_holdings` tool.

Portfolio 1.1 does not derive canonical positions from executions. Broker
position snapshots are evidence about broker state; they are not an event
stream from which Holdings is rebuilt.

### 4.2 Append-only observation layer

The observation layer lives beside portfolio state in `profile_state.db`, not
in `market_data.db`. It records:

- capture attempts and component coverage;
- per-account value snapshots;
- complete broker position observations;
- executions and commission reports;
- broker corrections;
- unmatched position changes;
- manual financial adjustments; and
- user-owned activity annotations.

Every broker observation carries:

- a local `portfolio_account_id`;
- source/provenance;
- capture-run linkage;
- observation or provider `as_of` time in UTC;
- currency for every monetary value; and
- enough contract identity to interpret the observation without using symbol
  as a stable key.

### 4.3 No cascading historical deletion

Observation-table foreign keys use `RESTRICT` or `NO ACTION`, never
`ON DELETE CASCADE`. Accounts with observations cannot be hard-deleted. They
must be archived. Positions with manual-adjustment history remain soft-closed.

Any future privacy-driven hard-delete design must explicitly preserve or
anonymize the historical observation. Silent cascading deletion is forbidden.

### 4.4 Derived review differences

For `ibkr_review`, the pending difference is a derived-at-read view between the
latest complete broker position observation and canonical positions. It is not
stored as a mutable pending-diff row.

This preserves the shipped preview contract: reading or scheduling capture
does not silently approve a position change. Applying a derived preview remains
an explicit, write-gated user action.

### 4.5 Distinct timestamps

Broker account summaries and broker positions each expose their observation
time. Canonical positions expose their last sync or approval time. The two may
differ legitimately. The UI must show both instead of presenting the newer
broker account observation as proof that local positions were also applied.

## 5. Capture Service

### 5.1 One service per configured Gateway

`PortfolioCaptureService` owns account-value, position, and execution capture.
V1.1 uses the existing S-J IBKR provider configuration as its only connection
authority. It does not introduce `broker_connections`.

One configured Gateway capture discovers every account visible to that
session. Multiple Gateways or multiple broker providers require a later
connection model and are out of scope.

### 5.2 Trigger and cadence

Capture supports three triggers:

- `startup` catch-up;
- `scheduled`; and
- `manual`.

The persisted interval defaults to 15 minutes and accepts values from 5 to
1440 minutes. If IBKR provider configuration is complete and there is no
explicit override, periodic capture is enabled. If provider configuration is
missing, the schedule is dormant/blocked and performs no connection attempt.

At startup, capture runs when no successful capture exists or the last
successful run is older than the configured interval. The durable source for
this decision is the most recent successful `capture_run.finished_at`, not an
in-process timer.

Any accepted startup, scheduled, or manual run computes the next in-process due
time from completion, including a partial or failed attempt, so failure cannot
create a tight retry loop. A manual request rejected as already running does
not create a second connection or reset the cadence. On a later App restart,
the catch-up decision still uses the durable last-success time as ruled above.

### 5.3 Client-id isolation

Client-id bands become:

```text
quotes            +50  ad hoc current quote
holdings          +60  immediate Holdings preview/apply read
portfolio_capture +70  startup/scheduled/manual Portfolio capture
```

`portfolio_capture=+70` is read-only. The Settings domain hint, provider guard
reason, module comments, domain labels, and spacing tests must change together.
With `+70` as the high app-managed band, the base client id must remain at or
below 29 to stay below the documented legacy 100+ collision zone.

Future order placement must receive a different domain and offset. It may not
reuse `holdings` or `portfolio_capture`.

### 5.4 Concurrency

Only one Portfolio capture may be active for a Gateway. The capture service
also reuses the existing Gateway serialization and worker-loop-safe
`IBKRDataSource` connection boundary.

A concurrent trigger returns `blocked` with `already_running`. It is not a
provider failure and never opens another IBKR session.

### 5.5 Write permission before spending

Automatic observation writes require `profile_state_write`. The permission
check occurs before connecting to IBKR. A denied write returns `blocked` and
performs zero provider calls.

The ordinary Holdings preview route remains read-only and can still inspect a
snapshot without persisting observations. This specification does not weaken
that contract.

### 5.6 Capture pipeline

One accepted run performs these stages:

1. create a short-lived `running` capture-run record;
2. connect through `IBKRDataSource(readonly=True, client_id=+70)`;
3. read account summary;
4. read executions/fills and commission reports;
5. read positions and portfolio items;
6. disconnect from the Gateway;
7. validate each component independently;
8. open a short SQLite transaction and persist every valid observation; and
9. after observation commit, separately attempt any authorized canonical
   position mutation.

No SQLite transaction remains open while waiting for IBKR.

### 5.7 Component completeness

Account summary, executions/commissions, and positions/portfolio are separate
capture legs. A run may persist a valid account snapshot even if the execution
leg failed. Such a run is `partial`.

A position leg is complete only when the adapter can distinguish a successful
empty position set from a failed read. Only a complete position set can:

- produce a review diff;
- participate in unmatched reconciliation; or
- update canonical positions in `ibkr_auto` mode.

A failed or ambiguous position read never becomes an empty snapshot and never
closes every canonical position.

### 5.8 Newly discovered accounts

An observation requires a local account identity. When capture discovers an
unknown IBKR account, the final observation transaction creates a minimal,
write-gated `portfolio_accounts` shell:

- broker = `ibkr`;
- sync mode = `ibkr_review`;
- no canonical positions; and
- a local display label plus broker id/hash according to the existing account
  boundary.

Capture never overwrites an existing account's user-owned label, sync mode,
`include_in_total`, or archive state. Base currency remains present on the
observation itself even if the account shell is not changed.

A newly discovered account is shown as `待檢視`. An archived account that
reappears remains archived but surfaces a new-activity notice; capture does not
silently unarchive it.

## 6. Storage Contract

Exact migrations belong to each implementation plan, but the following table
names, identities, and invariants are design authority.

### 6.1 `portfolio_capture_settings`

Singleton configuration:

- `enabled`;
- `interval_minutes`;
- `updated_at`.

Validation is atomic. An invalid interval does not partially update `enabled`.
Disabling periodic capture does not disable a separately requested manual run.

### 6.2 `portfolio_capture_runs`

Each accepted attempt records:

- stable run id;
- trigger;
- transient `running` state;
- terminal state;
- `started_at` / `finished_at` UTC;
- account-summary, execution, and position leg states;
- discovered account count;
- normalized error code and redacted detail;
- client-id domain/effective id; and
- coverage notes.

A blocked attempt is persisted only when profile writes are permitted. A
permission-denied attempt is returned ephemerally because the same permission
that forbids observations also forbids manufacturing a durable run row.

Terminal states are exactly:

- `succeeded`;
- `partial`;
- `failed`;
- `blocked`; and
- `interrupted`.

On startup, any stale `running` row from a terminated process is reconciled to
`interrupted`. It is not left permanently active and is not rewritten as a
provider failure.

### 6.3 `portfolio_account_snapshots`

One row per successful account-summary leg and local account in a run:

- `capture_run_id`;
- `portfolio_account_id`;
- `as_of_utc`;
- `base_currency`;
- `net_liquidation`;
- `total_cash_value`;
- `settled_cash`;
- `gross_position_value`;
- `buying_power`;
- `available_funds`;
- `initial_margin_requirement`;
- `maintenance_margin_requirement`;
- `daily_realized_pnl`;
- `daily_unrealized_pnl`; and
- normalized source metadata that excludes the raw unfiltered account-summary
  payload.

The unique key is `(capture_run_id, portfolio_account_id)`. Each successful
run stores a fresh snapshot even when the values equal the previous run. The
capture-run table separately proves that a check occurred.

`daily_total_pnl` may be exposed as a labeled deterministic sum of broker
realized plus unrealized values. It is not stored as an independently reported
provider fact unless IBKR supplies an explicit tag for it.

### 6.4 `portfolio_broker_position_observations`

One row per position in each complete broker position set:

- capture and local account ids;
- broker and `conId`;
- symbol and asset class;
- quantity and average cost;
- instrument and base currencies;
- market value;
- unrealized P&L;
- broker-reported realized P&L when present;
- base-currency values when provided; and
- selected contract metadata needed to interpret the row.

The unique key is
`(capture_run_id, portfolio_account_id, broker_con_id)`.

A complete zero-position set is represented by the position-leg completeness
on the capture run plus zero rows. Zero rows without a complete leg never mean
that the account was empty.

### 6.5 `portfolio_broker_executions`

Execution rows are immutable broker facts. Stored fields include:

- broker/source (`ibkr`, with origin `gateway | flex`);
- local account id;
- `exec_id`;
- first-observed capture run and time;
- execution time UTC;
- `conId`, symbol, asset class, currency, exchange;
- side, shares/contracts, price;
- `order_id` and `perm_id`;
- client id, order reference, liquidation flag;
- cumulative quantity and broker average price when present;
- correction family and `corrects_exec_id`; and
- normalized provider fields required for future display.

The unique key is `(broker, portfolio_account_id, exec_id)`.

`perm_id` is the primary stable grouping identity for the activity view.
`order_id` is retained as broker fact but is client-session scoped and is not a
cross-session identity. If `perm_id` is absent, the UI does not invent an order
group and renders the fill independently.

Every stored execution field is immutable. Re-reading the same `exec_id` with
any different stored value is `data_conflict`; last-write-wins is forbidden.

### 6.6 `portfolio_broker_commission_reports`

Commission reports are separate observations linked to the exact execution id.
They retain:

- `exec_id` and local account relation;
- commission and currency;
- broker-reported realized P&L;
- yield and yield-redemption date when present;
- first-observed run/time; and
- normalized content hash.

The content hash covers normalized
`exec_id, currency, commission, realized_pnl, yield, yield_redemption_date`.
Equivalent values normalize identically, so formatting differences do not
create false revisions.

An identical report is a no-op. A later different report becomes a new
revision; prior revisions remain. The effective activity projection joins the
latest valid report without mutating the immutable execution row.

The revision unique key is
`(broker, portfolio_account_id, exec_id, content_hash)`.

### 6.7 `portfolio_unmatched_position_changes`

An unmatched observation stores:

- local account and `conId`;
- from/to capture-run ids and UTC window;
- before and after quantities;
- expected quantity and residual;
- execution-coverage state;
- source and reason code; and
- selected display metadata.

The natural unique key is:

```text
(portfolio_account_id, broker_con_id, from_run_id, to_run_id)
```

Recomputing the same window is idempotent.

### 6.8 `portfolio_manual_adjustments`

Manual financial mutations are not executions. An adjustment event stores:

- event id;
- local manual account and position ids;
- action (`create | update | close`);
- optional user note;
- UTC timestamp; and
- source = `manual`.

Field-level child rows live in `portfolio_manual_adjustment_changes` and store:

```text
{ field, before, after }
```

Only manual financial fields and close state are journaled here. Ordinary
notes/thesis/tags edits remain position-note behavior, not fake market
activity. Manual adjustment rows never calculate realized P&L because no
provider execution price exists.

### 6.9 `portfolio_activity_annotations`

Broker facts and user interpretation remain separate. A mutable user-owned
annotation may target:

- a broker order group `(portfolio_account_id, perm_id)`;
- an ungrouped execution;
- an unmatched position change; or
- a manual adjustment.

It may store a confirmed intent label, free-form note, and updated time. V1.1
does not let an agent write this table. Any future agent suggestion is a
proposal requiring explicit user confirmation.

### 6.10 Numeric and time discipline

All persisted numeric values must be finite. `NaN`, positive/negative infinity,
blank strings, and parse failures do not become zero. The affected component is
invalid or partial, with a normalized diagnostic.

Provider times and observations are stored in UTC. Market-facing execution
display is anchored to US Eastern time; local time may be shown secondarily.
The user-facing meaning of `今日` for broker daily P&L is anchored to IBKR's
US Eastern broker/market day, not the viewer's local calendar date, and the UI
must label that timezone context.
When IBKR supplies no source timestamp for account summary, `as_of_utc` is the
completed observation time and is labeled as such.

## 7. Idempotency, Corrections, and Reconciliation

### 7.1 Repeated current-day reads

Every 15-minute run may receive the same current-day executions. Unique
execution identity turns duplicates into no-ops. A repeated run still creates
a new capture run and account snapshot, proving that the broker was checked
again.

### 7.2 Late commissions

An execution may arrive before its commission report. The execution remains
valid with pending commission/realized-P&L fields. A later commission
observation enriches the read projection without rewriting the execution.

Missing commission or realized P&L stays null. The UI does not infer either
from quantity, prices, or position cost.

### 7.3 Broker corrections

IBKR corrections use a new execution id related to the original execution
family. The corrected execution is inserted as another immutable row with
`corrects_exec_id`. The activity projection selects the latest correction for
normal display while keeping prior revisions expandable.

The old execution is not overwritten or deleted. Commission reports remain
attached to their exact execution revision.

### 7.4 Position reconciliation

For two consecutive complete broker position observations, per account and
`conId`:

```text
expected quantity = previous broker quantity
                  + change in effective signed executions over the window

residual = current broker quantity - expected quantity
```

The execution term compares the effective correction-aware execution
projection as of the two capture runs. It is not a raw sum of every newly
inserted correction row.

If the residual is non-zero, Portfolio records an
`unmatched_position_change`. It never fabricates an execution, price,
commission, or P&L.

The first complete capture establishes a baseline only. With no earlier
complete broker snapshot, no unmatched change is produced.

### 7.5 Coverage states

The application may call a residual unexplained only when:

- both endpoint position sets are complete; and
- execution coverage for the interval is complete enough to support that
  claim.

If an execution leg failed, the App was offline across a broker-day boundary,
or Gateway history could not cover the interval, the unmatched row carries an
incomplete/gap coverage state. It says that fills may be missing, not that the
broker changed positions without a transaction.

Later same-day captures may observe fills missed by an earlier failed leg. New
windows then reconcile from their own evidence. Earlier incomplete
observations remain append-only; V1.1 does not rewrite history to hide the gap.

### 7.6 Objective outcome versus intent

Objective facts may be calculated only from broker facts and complete position
context:

- buy or sell;
- increase or reduce;
- partial or complete close;
- fill quantity and price;
- provider commission;
- provider-reported realized gain, loss, or unknown; and
- gross notional `abs(quantity x price)`, explicitly labeled as deterministic
  arithmetic rather than account cash impact.

When position context is incomplete, the UI keeps direct execution facts but
labels the position effect as unknown.

`profit_take`, `stop_loss`, `rebalance`, `thesis_broken`, cash need, and other
intent labels are user interpretation. They are never inferred as confirmed
facts. A later agent may propose an intent, but only explicit user approval may
write it.

## 8. Canonical Position Mutation

### 8.1 Observation commit precedes authority mutation

After all network reads finish, the service commits valid observations in a
short transaction. Canonical position mutation is a separate step.

If observation commit fails, canonical apply does not run. If observation
commit succeeds but canonical apply fails, broker facts remain and the capture
run is `partial`.

This asymmetry is deliberate: machine observations preserve every valid fact
obtained, while authority updates remain separately controlled.

### 8.2 Sync modes

- `ibkr_auto`: a complete broker position observation may update canonical
  broker-owned fields and close/reopen broker positions.
- `ibkr_review`: canonical positions are unchanged; the latest complete
  observation feeds a derived preview.
- `manual`: IBKR never mutates canonical positions.

All three modes may retain account snapshots, executions, commission reports,
and unmatched observations.

### 8.3 Manual mutation atomicity

A manual position create, financial update, or close and its
`manual_adjustment` event execute in the same SQLite transaction. If journal
creation fails, the position mutation rolls back. There is no state in which a
manual financial mutation succeeded but its audit event is missing.

## 9. Holdings User Experience

### 9.1 Chosen hierarchy

The user selected the Holdings-first, tabbed layout. Account summary remains
visible at the top; canonical holdings remain the primary work surface.

The four tabs are:

1. `持倉`;
2. `活動`;
3. `帳戶明細`; and
4. `同步紀錄`.

Portfolio 1.1 adds no new global navigation item.

### 9.2 Account summary

Each visible IBKR account receives its own compact summary row with:

- Net Liquidation;
- Total Cash;
- Buying Power;
- daily realized P&L;
- daily unrealized P&L;
- a labeled deterministic daily total;
- base currency;
- broker observation time; and
- local position sync/approval time.

All accounts remain visible rather than being hidden behind one selector.

Manual accounts do not claim broker account-value data. Their complementary
display is `手動帳戶持倉小計`, calculated with the shipped `PortfolioTotals`
currency, open-position, and `include_in_total` rules.

Manual subtotals never include IBKR positions and are never added to IBKR Net
Liquidation. The UI never labels those separate numbers as overall net worth.

IBKR account aggregation is optional and conservative:

- primary display remains per account;
- excluded accounts do not participate;
- same-currency accounts may expose a labeled IBKR subtotal; and
- mixed currencies remain separate under the existing currency-basis
  discipline.

### 9.3 `持倉`

The default tab retains:

- canonical positions;
- account filters;
- financial columns;
- existing row actions;
- closed-position view; and
- user-owned notes.

It shows canonical authority time separately from broker observation time.

For `ibkr_review`, an unapplied derived preview appears with the existing
review/apply semantics. Reading the preview remains zero-write.

### 9.4 `活動`

The activity view combines projections over distinct event types without
merging their storage identity:

- broker order/fill activity;
- commission revisions and corrections;
- unmatched position changes; and
- manual adjustments.

It groups broker fills by `(portfolio_account_id, perm_id)`. Each order row can
expand to immutable fills, exact commission revisions, and corrections. If
`perm_id` is absent, the fill remains independent; `order_id` alone is not used
as a cross-session grouping key.

Filters include date, account, symbol, source, and state. Objective outcome and
confirmed user intent are visually separate. Unmatched changes expose before,
after, residual, window, and coverage state.

The page always states that history begins with the first successful capture.
Coverage gaps render as explicit markers. An empty interval never implies
there were no broker transactions when capture was unavailable.

### 9.5 `帳戶明細`

This tab exposes the complete latest account-snapshot fields per account. It
does not show a performance curve in V1.1. Historical snapshots are retained
for a later qualified use.

### 9.6 `同步紀錄`

This tab is the single product authority for Portfolio capture controls:

- periodic enabled/disabled state;
- 5-1440 minute interval;
- next expected capture;
- manual `立即同步`;
- latest and recent run states;
- component-level results;
- coverage gaps, conflicts, and unmatched counts; and
- newly discovered or archived-but-active account notices.

Settings -> Data Sources does not render a second Portfolio scheduler row. It
may retain ordinary IBKR provider configuration/health and may link to this
tab, but it does not duplicate mutation controls.

### 9.7 Contextual recent-activity panel

On wide Holdings layouts, the positions tab may show a surface-local recent
activity summary and unmatched count. It only navigates to full activity; it
does not become another data authority.

This is not the global placeholder rail retired by P2.8. It has real local
content and collapses completely when no actionable/recent content exists. It
also disappears below the canonical 960px shell breakpoint, with all content
remaining available in tabs and badges.

### 9.8 Responsive and state behavior

- Financial tables own horizontal scrolling rather than shrinking text.
- Layout must be checked on both sides of the canonical breakpoint, at 961px
  and 959px, plus desktop and mobile widths.
- Shared P2.8 buttons, status, alerts, DataTable, and confirmation primitives
  are reused.
- No new ad hoc chip or overlay system is introduced.
- General mode shows cause and next action; raw exception detail is available
  only in Developer Mode.

Market executions are displayed primarily in ET, with local time available as
secondary context. Capture/system times display in local time while remaining
stored as UTC.

## 10. Run States and Error Semantics

### 10.1 State mapping

The capture surface maps domain states to the canonical UI vocabulary:

| Capture fact | Common state |
| --- | --- |
| Accepted and in flight | `running` |
| Complete persisted run | `ready` / terminal `succeeded` |
| Some valid observations persisted | `partial` |
| Provider/config/permission prevents start | `blocked` |
| Provider, validation, or persistence failure with no valid observation | `failed` |
| Process shutdown or explicit cancellation | `interrupted` |

`blocked`, `failed`, and `interrupted` are not interchangeable.

### 10.2 Failure rules

- Missing IBKR provider configuration returns `provider_config_missing`, makes
  zero provider calls, and links to the exact Settings section.
- A connection failure does not persist an empty snapshot.
- A DB observation-write failure prevents canonical apply.
- A canonical-apply failure after observation commit produces `partial`.
- A concurrent run produces `blocked/already_running`.
- There is no tight retry loop. The next normal schedule or manual action
  retries.
- App startup reconciles orphan `running` rows to `interrupted` before deciding
  whether catch-up is due.

## 11. Read-Only, Privacy, and Research Boundaries

### 11.1 Read-only capture

The capture connection is always constructed with `readonly=True`. Capture
modules must not reference or call order-side APIs, including:

- `placeOrder`;
- `cancelOrder`;
- `reqGlobalCancel`;
- order-modification paths; and
- `exerciseOption` / `exerciseOptions`.

Implementation plans must include a static source gate for these names in the
capture ownership boundary.

The user's Gateway itself need not be globally read-only. Future ArkScope
trading remains possible, but only through a separately authorized trading
line that does not reuse capture code or client identity.

### 11.2 Account identity privacy

Raw broker account ids remain inside the local broker/account boundary. Normal
UI/API responses use local account id, user label, and redacted hash where
possible. Raw account ids must not appear in:

- agent payloads;
- prompts;
- ordinary trace metadata;
- generic error details; or
- capture logs intended for normal UI.

### 11.3 Data minimization

Portfolio capture stores normalized fields required by this specification. It
does not persist the unfiltered raw `accountSummary` payload and does not store
provider tokens or credentials.

### 11.4 Research isolation

V1.1 does not inject account snapshots, executions, manual adjustments, or
unmatched changes into AI Research. `get_portfolio_holdings` continues to read
canonical holdings only and continues to redact raw account identity.

A future activity-analysis capability requires a separately named read-only
tool, an explicit minimal schema, full tool-registration ledger updates, and a
new prompt/data-boundary review.

## 12. Retention and Future Performance Analysis

Observation data is retained by default. V1.1 does not expose hard-delete,
retention, compaction, or export controls for broker activity.

Any future retention design must preserve:

- correction lineage;
- commission revisions;
- coverage gaps;
- manual adjustment audit; and
- account snapshot times.

Account-value snapshots are sufficient to draw a future nominal NAV curve,
but not to claim investment return. Time-weighted or money-weighted performance
requires cash-flow events such as deposits, withdrawals, dividends, interest,
tax, and FX treatment. Gateway capture does not provide a clean complete flow
ledger. Flex or another import path must supply that evidence before ArkScope
claims portfolio performance.

## 13. Implementation Sequence

Portfolio 1.1 is a three-slice line. Each slice receives its own implementation
plan, TDD sequence, implementation review, canonical A/B comparison, and live
gate.

### Slice 1: observation and capture foundation

Deliver:

- observation schema and stores;
- idempotency, corrections, late commissions, and unmatched reconciliation;
- manual-adjustment atomic journal;
- `portfolio_capture=+70` and client-id ledger changes;
- startup/scheduled/manual capture;
- run/config APIs; and
- the minimum Holdings sync-record control/status surface.

This slice starts preserving non-retroactive broker facts immediately. It does
not wait for the richer account/activity UI.

### Slice 2: account overview

Deliver:

- per-account summary rows;
- full account-detail tab;
- broker/canonical dual timestamps;
- manual subtotal separation;
- multi-account/currency behavior; and
- responsive overview verification.

### Slice 3: activity and journal UI

Deliver:

- grouped order/fill activity;
- commissions, corrections, and unmatched detail;
- manual-adjustment display;
- user-confirmed intent annotations;
- filters and coverage markers; and
- contextual recent-activity summary.

Portfolio 1.1 becomes `LIVE COMPLETE` only after Slice 3's live gate.

## 14. Verification Contract

### 14.1 Store and schema tests

Plans must cover at least:

- all observation FKs are non-cascading;
- hard-delete is blocked while observations exist;
- every unique/idempotency key in Section 6;
- first complete position capture creates no unmatched row;
- exact duplicate execution is a no-op;
- conflicting same-exec facts produce `data_conflict`;
- late commission joins without execution mutation;
- changed commission content creates one revision;
- execution correction preserves old and selects new effective revision;
- complete empty position set differs from failed position read;
- unmatched recomputation is idempotent;
- NaN/Inf/parse failures never become zero;
- manual mutation and journal roll back together; and
- account discovery preserves user-owned account fields.

### 14.2 Capture and scheduler tests

Plans must prove:

- profile-state permission denial makes zero IBKR calls;
- provider-config missing makes zero IBKR calls;
- worker-thread/event-loop connection uses the existing safe boundary;
- `connect() == False` never reads an empty session;
- one accepted run opens one capture connection;
- concurrent trigger returns `blocked/already_running`;
- startup catch-up reads durable last-success time;
- stale `running` becomes `interrupted`;
- successful manual capture resets next due time;
- account, execution, and position legs can produce truthful `partial`;
- incomplete positions never mutate canonical holdings;
- `ibkr_review` writes observations but not canonical positions;
- `ibkr_auto` mutates only broker-owned fields after observation commit; and
- all order-API static gates are empty.

### 14.3 UI tests

Plans must prove:

- every IBKR account is visible;
- mixed currencies do not produce a fake grand total;
- manual subtotal excludes IBKR positions and is not added to NLV;
- broker and canonical timestamps are both visible;
- daily total P&L is labeled realized + unrealized arithmetic;
- unknown outcome does not become a fabricated close/profit/loss label;
- absent `perm_id` yields independent fill rows;
- coverage gaps remain visible when an interval has no events;
- Data Sources contains no second Portfolio scheduler control;
- the contextual side panel collapses when empty and below 960px; and
- 961px, 959px, desktop, and mobile layouts have no overlap or clipped
  financial text.

### 14.4 Regression and environment gates

Each slice plan includes:

- focused backend tests;
- focused and full frontend tests for touched UI slices;
- TypeScript and production build gates;
- no-PG smoke with `pg_attempts:[]`;
- static raw-account-id and order-API boundaries;
- full canonical base/head A/B, with identical pre-existing failure sets and
  exact new-test accounting; and
- a clean fresh-profile SQLite migration test.

### 14.5 Live Gateway gate

With one sidecar and the user's real Gateway:

1. run one manual capture and verify account snapshots, position observations,
   and current-day fills persist;
2. rerun immediately and prove executions do not duplicate while run/snapshot
   history advances;
3. verify a late commission can appear in the effective activity projection;
4. trigger a second request while one is active and receive
   `blocked/already_running`;
5. prove `ibkr_review` leaves canonical positions unchanged while the derived
   preview changes;
6. perform a manual financial edit and prove an adjustment is journaled; and
7. inspect normal API/trace/tool output for raw account-id leakage.

Unavailable live conditions, such as a real correction or multiple visible
accounts, are covered by realistic fakes and explicitly marked runtime-unproven
rather than fabricated during the gate.

## 15. Non-Goals

Portfolio 1.1 does not implement:

- complete history before activation;
- Flex import;
- TWR/MWR or a performance curve;
- tax lots or tax reporting;
- self-calculated realized P&L;
- deposit/withdrawal/dividend/interest/tax/FX reconciliation;
- complete manual trade entry;
- agent-authored confirmed intent;
- a new agent activity tool;
- Research prompt injection;
- order placement or automated trading;
- multiple simultaneous Gateway connections;
- another broker provider;
- retention, compaction, or export UI; or
- a second Portfolio scheduler in Settings.

These are deferred, not permanent rejections. Order placement in particular is
expected to become a separate future product line and may consume the broker
facts accumulated here without converting capture into a write path.

## 16. Stop-Loss Conditions

Implementation stops for design review if any slice requires:

- rebuilding canonical positions from observations or executions;
- persisting a pending review diff instead of deriving it at read time;
- writing canonical positions from an incomplete position leg;
- holding a SQLite transaction during Gateway I/O;
- reusing `holdings=+60` or `portfolio_capture=+70` for order placement;
- introducing any order API into capture ownership;
- storing unfiltered account-summary payloads;
- exposing raw broker account ids to an agent or generic trace;
- claiming complete history across a coverage gap;
- inferring realized P&L or subjective trade intent;
- combining manual subtotal with IBKR NLV as overall net worth;
- adding a second Gateway/connection authority; or
- making Flex, performance analytics, or trading a green condition for
  Portfolio 1.1.

## 17. Authority and Follow-Up

Authority order after written review:

1. this spec owns Portfolio 1.1 observations, capture, account-value, and
   activity behavior;
2. the Holdings V1 design owns canonical account/position/note semantics;
3. the P2.8 canonical shell spec owns shared UI primitives, breakpoint, and
   interaction behavior;
4. S-J provider configuration remains the IBKR connection authority; and
5. each reviewed implementation plan owns exact file/commit order without
   weakening this contract.

After written-spec approval, Slice 1 alone is promoted to implementation-plan
design. Slices 2 and 3 remain planned dependencies and receive their own plan
only after the preceding slice is review-cleared.
