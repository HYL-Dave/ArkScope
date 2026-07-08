# Holdings + Portfolio Design

> **Status: ADOPTED DESIGN — implementation branch review-ready 2026-07-08.**
> Drafted 2026-07-08 after Investor Profile Track A.5. This document defines
> ArkScope's first-class holdings model and its IBKR sync boundary. Runtime
> changes are authorized only by the linked implementation plan; live completion
> waits for review, full A/B, merge, and IBKR verification.

## 1. Problem

ArkScope can analyze a caller-supplied `holdings` object through
`get_portfolio_analysis()`, and Watchlists can label lists as holdings-like, but the app
does not yet own a durable portfolio model. That makes later features brittle:

- alerts cannot know what the user actually owns;
- research notes cannot distinguish owned positions from watchlist interest;
- investor-profile risk checks have no portfolio context;
- agents must accept ad hoc holdings JSON instead of reading a controlled local source;
- IBKR users cannot use their broker positions as the app's portfolio basis.

The first holdings slice should make holdings a local-first profile feature, not a tool
argument convention.

## 2. Product Ruling

ArkScope supports a hybrid model:

- users can maintain holdings manually;
- users can sync positions from IBKR;
- the local profile remains the durable app authority;
- sync behavior is configurable per portfolio account;
- manual holdings, IBKR holdings, and future imported holdings can coexist.

This is not a trading feature. Holdings v1 is read-only with respect to IBKR and never
places, modifies, or cancels orders.

## 3. Conceptual Model

### 3.1 Broker connection

A broker connection is the external API session used to discover/read broker data. For
IBKR, this is the Gateway/TWS host, port, base client id, and account visibility returned
by the API.

V1 does not create a new `broker_connections` table. The only IBKR connection authority is
the existing S-J provider configuration (`ibkr.host`, `ibkr.port`, guarded
`ibkr.client_id`, enabled/config state). Holdings uses that connection to discover broker
accounts and positions. A physical `broker_connections` table should be introduced only
if ArkScope later supports multiple simultaneous Gateway endpoints or multiple broker
providers that need independently stored connection profiles.

Important properties:

- one IBKR Gateway connection may expose one account, multiple accounts, only a subaccount,
  or a managed-account view;
- account visibility does not imply trading permission;
- order-placement capability must never be inferred during holdings sync;
- the same Gateway may later be reused by a separate trading/execution feature, but
  holdings v1 must not call order APIs.

### 3.2 Portfolio account

A portfolio account is ArkScope's local grouping for positions. Examples:

- `Manual`;
- `IBKR Uxxxx`;
- `IBKR DUxxxx`;
- `IBKR subaccount`;
- future `CSV import` account.

Portfolio accounts are app objects in the profile database. IBKR discovery can create or
update IBKR-backed portfolio accounts, but manual accounts are first-class too.

### 3.3 Position

A position belongs to one portfolio account. Positions carry both broker-owned and
user-owned fields.

For IBKR-backed positions, the sync identity is IBKR `conId` plus account scope, not the
display symbol. Symbols can change across renames and corporate actions; a symbol-keyed
diff would misclassify a rename as one deleted position plus one new position. Symbol is
display metadata. Manual positions may use a local generated id until linked to a broker
contract.

Broker-owned fields may be refreshed from IBKR:

- symbol / contract identifier (`conId` for IBKR-backed positions);
- asset class;
- quantity;
- average cost;
- currency;
- market value;
- unrealized P&L;
- last broker snapshot metadata.

User-owned fields are never overwritten by IBKR:

- notes;
- thesis;
- tags;
- strategy bucket;
- target allocation;
- alert preferences;
- research-note links.

## 4. Sync Modes

Sync mode is primarily account-level, with optional position-level exceptions later.

### `manual`

The account is fully user-maintained. IBKR may show differences in a future diagnostics
view, but it does not mutate positions.

### `ibkr_review`

ArkScope reads IBKR positions and shows a diff. The user approves before broker-owned
fields are written to local positions.

This mirrors the Investor Profile calibration proposal pattern: external inference can
propose; user confirmation writes.

### `ibkr_auto`

ArkScope reads IBKR positions and automatically applies broker-owned field changes for
that account. User-owned fields remain untouched.

This is intended for users whose actual investing happens through IBKR and who want the
app portfolio to follow broker reality with minimal friction.

## 5. Multi-Account Requirement

Multi-account support is a v1 data-model requirement, not a future migration.

Rationale: IBKR may expose original accounts, subaccounts, managed accounts, or only the
account visible to the current Gateway login. A single-account schema would make later
IBKR support and aggregation ambiguous.

V1 UI may stay simple:

- default view = aggregate all included accounts;
- account filter available;
- account-level sync status visible;
- positions grouped or filterable by account;
- accounts can be included/excluded from aggregate totals.

## 6. Asset Coverage

V1 should display every IBKR position ArkScope can read, including stocks, ETFs, cash, and
options.

### Stocks and ETFs

Stocks/ETFs are fully supported for v1 portfolio metrics when price data is available:

- market value;
- unrealized P&L;
- weight;
- concentration;
- sector exposure where data exists;
- beta/correlation reuse where current tools support it.

### Cash

Cash should be visible as a separate cash section or row. It can participate in total
portfolio value, but it should not be treated as an equity position.

### Options

Options must be visible, not hidden. V1 supports broker-provided basics:

- contract;
- expiry;
- strike;
- right;
- quantity;
- average cost if provided;
- market value if provided;
- unrealized P&L if provided.

If IBKR provides market value/P&L, those values may be included in total market value and
total P&L. But advanced derivatives risk is out of v1:

- no full Greeks model;
- no scenario P&L;
- no assignment-risk engine;
- no option-notional concentration mixed into equity concentration as if it were stock
  market value.

Options should have a separate derivatives section so ArkScope is honest about what it
does and does not model.

## 7. IBKR Boundary

Holdings v1 may use the same IBKR Gateway that other read features use. It does not
require Gateway read-only mode, but ArkScope's holdings code must be read-only:

- allowed: managed accounts, positions, account summary, market data required for
  portfolio display;
- forbidden: place order, cancel order, modify order, exercise option, or any order-like
  side effect.

Future automated trading, if opened, must be a separate product line with:

- explicit permission gates;
- order preview;
- confirmation;
- audit log;
- kill switch;
- execution-specific client-id domain;
- order correlation ids;
- no reuse of holdings sync paths for writes.

## 8. Client-Id Isolation

Existing IBKR client ids are domain-partitioned by `data_sources/ibkr_client_id.py`
(`manual`, `options`, `prices`, `news`, `iv`, `quotes`). Holdings should add its own
read-only domain, for example `holdings`, in a future implementation plan.

Client-id bands are finite because old scripts already occupied awkward ranges:
`collect_ibkr_fundamentals.py` hardcoded `103`, and archived scan/IV scripts used random
`100-999` ids. The current highest domain offset is `quotes=50`. A future `holdings=60`
band implies the base client id must stay low enough that derived ids avoid the legacy
range; a future trading/execution band would make that tighter. The implementation plan
must update `data_sources/ibkr_client_id.py` comments/tests and the Settings domain hint
contracts together.

Future trading/execution must not reuse the holdings read id. It needs independent ids:

- an execution client-id domain such as `orders` or `trading`;
- an ArkScope order-intent id;
- a broker order correlation id;
- an audit-log id.

This keeps read sync, quote snapshots, price/news workers, options tools, and any future
execution channel diagnosable and separable in Gateway logs.

## 9. Local Storage Direction

Recommended v1 tables in `profile_state.db`:

- `portfolio_accounts`
  - account id, display label, type, broker, broker account id/hash, sync mode, base
    currency, include-in-total, archived status, timestamps;
- `portfolio_positions`
  - account id, local position id, broker contract id (`conId` for IBKR), symbol, contract
    metadata, asset class, quantity, average cost, currency, broker market value/P&L,
    source, sync status, timestamps;
- `portfolio_position_notes`
  - user-owned notes/thesis/tags/strategy bucket/target allocation/links;
- `portfolio_sync_snapshots`
  - raw-ish broker snapshot metadata sufficient for diff/provenance, with secrets and
    account PII redacted;
- `portfolio_sync_events`
  - review/auto/manual write events and row counts.

Exact schema belongs in the implementation plan. The design requirement is that broker
fields and user fields are separable.

Mixed-currency totals must be honest. V1 may use broker-provided base-currency market
value/P&L where IBKR supplies it; otherwise it should show per-currency subtotals rather
than silently summing unlike currencies. The UI/API must state which currency basis an
aggregate uses.

## 10. UI Shape

V1 should be functional, not decorative:

- table-first holdings view;
- account filter and aggregate/all-accounts toggle;
- source/sync badges per account and position;
- manual add/edit flow;
- IBKR sync button;
- diff review surface for `ibkr_review`;
- clear warning when options are displayed but advanced option risk is not modeled;
- visible "read-only holdings sync; no trading" copy near IBKR sync setup.

Cards are appropriate for account summaries. Positions themselves should stay dense and
scannable.

## 11. Agent and Tool Access

Agents should read holdings through a controlled local accessor, not by asking the user to
paste holdings JSON.

V1 agent/tool policy:

- default tool reads aggregate included accounts;
- tool can optionally filter by account id/display label;
- tool response must report which accounts were included;
- raw broker account ids should not be injected into prompts; use display labels or
  redacted ids;
- tool should distinguish stocks/ETFs, cash, and options in output;
- tool must not expose order placement or execution affordances.

This can replace or wrap the current `get_portfolio_analysis(holdings=...)` pattern for
workbench use. The legacy ad hoc holdings argument can remain for CLI/dev compatibility
until a later cleanup.

## 12. V1 Cut Line

In scope:

- local portfolio accounts and positions;
- manual account and manual positions;
- multi-account schema;
- account-level sync mode;
- IBKR read-only discovery/snapshot/import path;
- stocks/ETFs/cash/options display;
- broker-provided market value/P&L display;
- basic aggregate totals;
- tool/read API for local holdings;
- UI diff/approval for review mode;
- auto-apply for broker-owned fields in auto mode.

Out of scope:

- order placement or trading automation;
- advanced options risk engine;
- tax lots;
- wash-sale/tax reporting;
- margin requirement modeling;
- rebalancing execution;
- multi-broker sync beyond schema compatibility;
- cloud sync.

## 13. Acceptance Criteria

- A fresh profile has a Manual account available for user-entered holdings.
- IBKR sync can discover one or multiple accounts without assuming trading permission.
- `ibkr_review` produces a human-readable diff and does not write until approval.
- `ibkr_auto` updates only broker-owned fields.
- Manual/user-owned fields survive every sync mode.
- Stocks/ETFs/cash/options are visible; unsupported advanced option analytics are labeled
  honestly.
- Aggregate totals state which accounts and asset classes are included.
- Agent/tool reads use the local holdings store and record account scope in trace/output.
- No code path in this slice calls IBKR order APIs.
- IBKR client-id usage is domain-separated from quotes/prices/news/options, and future
  trading ids are reserved as separate from holdings.

## 14. Open Questions for the Implementation Plan

1. What exact IBKR API surface should the first live snapshot use: `positions`,
   `portfolio`, `accountSummary`, or a combination?
2. How much of IBKR contract metadata should be normalized into columns vs kept as a
   JSON metadata payload?
3. Should `ibkr_auto` run only on explicit user sync in v1, or also on app startup?
4. Should options be grouped by underlying, expiry, or account-first in the v1 table?
5. Should local holdings feed current quote lookup automatically, or keep quote fetch as
   an explicit enrichment step?
