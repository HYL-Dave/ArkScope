# DB-Derived Universe and `tickers_core.json` Retirement Design

> **Status:** ADOPTED DESIGN; WRITTEN REVIEW PENDING. Implementation is
> deliberately deferred until after P2.8 Slice 3.

## 1. Purpose

Make local databases the runtime authority for ArkScope's active ticker
universe, automatically include current Alpha Picks as one derived source, and
retire `config/tickers_core.json` from both runtime reads and extension writes.
Retain an explicit, deterministic, on-demand compatibility export.

This design retires `tickers_core.json`; it does not claim to retire every
ticker-bearing legacy setting in `config/user_profile.yaml`.

## 2. Ground Truth

### 2.1 Alpha Picks facts already live in SQLite

Every successful Alpha Picks current/closed refresh writes pick facts to
`data/sa_capture.db`. On current-refresh success, the native host separately
calls `sync_tickers_to_collection()` and rewrites
`tier3_user_watchlist.sa_alpha_picks_auto` in `config/tickers_core.json`.

The extension's `Auto-sync Alpha Picks` control only schedules Chrome alarms.
Turning it off stops future automatic refreshes; it does not delete captured
facts or revoke ticker eligibility. Browser extension uninstall has no cleanup
hook for ArkScope's DB or universe.

### 2.2 Runtime authority is currently fragmented

Direct code inspection found three live production read surfaces, one dormant
compatibility reader, and one writer, not ten direct readers:

1. `/profile/universe` unions `active_universe_tickers()` from JSON with local
   profile membership and the legacy overview;
2. profile import derives legacy category/provenance tags from JSON;
3. symbol-catalog offline seed calls `all_universe_tickers()`; and
4. the compatibility `DataAccessLayer.get_tier_tickers()` can read JSON, but no
   current production caller was found.

The writer is `sa_native_host._try_ticker_sync()`. Maintained news collectors,
the scheduler, and `daily_update` already resolve their ticker scope through
`src.universe_scope.resolve_active_universe()`, which reads
`profile_state.db`; they no longer use JSON as their default.

The writer also checks legacy key `tier2_extended`, while the tracked file and
current loader use `tier2_expanded`. Flattened set parity, rather than trusting
that writer's category-level dedupe, is therefore the migration authority. The
writer is retired after cutover instead of receiving a separate cleanup slice.

The exact migration inventory, rather than a remembered reader count, is the
review/ratchet authority.

### 2.3 Existing DB sources do not exactly equal the JSON snapshot

A read-only 2026-07-17 comparison found `152` active JSON tickers versus `151`
in the union of active local lists, open holdings, and current non-stale Alpha
Picks. The diff was two JSON-only symbols and one DB-only symbol. This is not a
reason to choose one side silently; it proves the need for an explicit preview,
import, and strict post-migration parity gate.

The working tree also currently contains an uncommitted Alpha-Picks-style
addition to `config/tickers_core.json`. Implementation must preserve and
preview the live file; it must never overwrite or discard that edit during
migration.

## 3. Locked Product Decisions

1. **Capture is unconditional once a refresh runs.** Current/closed picks and
   article facts always enter `sa_capture.db`; there is no "record this feed"
   switch.
2. **The existing extension Auto-sync switch controls cadence only.** It does
   not control persistence or universe membership.
3. **V1 current-pick eligibility is automatic.** Every current, non-stale Alpha
   Picks symbol contributes source `sa_alpha_picks_current`; no second
   default-on universe toggle is added.
4. **Membership is a union of sources.** Removing an Alpha Pick withdraws only
   that source. A ticker retained by an active list, open holding, or another
   source remains active.
5. **View contraction never deletes history.** A ticker leaving every active
   source disappears from the derived universe but its prices, news, research,
   picks, articles, notes, and capture history remain.
6. **Feed retirement is a named deferral.** If the user later ends the Alpha
   Picks feed, add a visible per-source `enabled` control that withdraws only
   derived eligibility. Do not delete captured facts and do not infer retirement
   from age. Until that feature exists, stopped capture freezes the last current
   set and exposes its last-success time.
7. **JSON is export, never authority.** Manual edits after cutover have no
   runtime effect. User additions go through DB-owned list/universe actions.
8. **One accessor owns resolution.** Runtime readers consume the same structured
   active-universe snapshot; no consumer assembles its own union.

## 4. Source and Accessor Model

### 4.1 Code-reviewed source registry

The registry defines source keys and read adapters:

| Source | Authority | Active membership |
|---|---|---|
| `manual_lists` | `profile_state.db` | membership and parent list both unarchived |
| `portfolio_open` | `profile_state.db` | position open and account unarchived |
| `sa_alpha_picks_current` | `sa_capture.db` | `portfolio_status='current' AND is_stale=0` |
| `legacy_config_seed` | `profile_state.db` | one-time imported active JSON membership not otherwise represented |

The registry contains no V1 `enabled` flag for Alpha Picks. It may reserve an
additive source-policy interface for the named retirement follow-up, but must
not ship a hidden environment flag or dead UI branch.

The one-time JSON importer stores tier/category metadata only for compatibility
round-tripping; tier does not regain product priority semantics. Existing
classification tags remain on their independent facet/source axis and do not
qualify a ticker by themselves.

Persisted compatibility membership uses a normalized profile-state shape:

```text
universe_source_memberships
  source_key
  ticker
  created_at
  archived_at
  PRIMARY KEY (source_key, ticker)

universe_source_annotations
  source_key
  ticker
  annotation_key        legacy_tier | legacy_category
  annotation_value
  PRIMARY KEY (source_key, ticker, annotation_key, annotation_value)
```

Only `legacy_config_seed` needs these rows in V1. Manual lists, open portfolio
positions, and current Alpha Picks remain direct derived reads from their
existing authorities. The one-to-many annotation table prevents round-trip
metadata from being collapsed to one arbitrary category.

### 4.2 Structured snapshot

The single accessor returns more than a bare list:

```text
ActiveUniverseSnapshot
  tickers[]                 sorted canonical symbols
  sources_by_ticker{}       ticker -> sorted source keys
  source_status{}           available, last_success_at, optional warning
  unavailable_sources[]
  generated_at
```

`resolve_active_universe()` remains a thin compatibility adapter over
`snapshot.tickers` while callers migrate. New readers use the structured
snapshot so UI/export can explain why a symbol is present.

`ticker_meta.hidden_at` remains the final explicit user veto over the union.
An archived list member is not active merely because the current resolver used
to select every membership row without archive predicates.

### 4.3 Cross-database failure behavior

The accessor reads databases in read-only mode and never copies Alpha Picks or
portfolio facts into a second membership table. If a registered DB source is
unavailable:

- scheduler/collector callers fail closed rather than silently collect an
  incomplete universe;
- UI callers may render the last accepted snapshot only when its stale/source
  warning is explicit; and
- an unavailable source is not reported as an observed empty set.

Age may drive a warning but never automatic source removal. Last-success time
is evidence of freshness, not evidence that a subscription ended.

## 5. Readers-First Migration

Migration proceeds in this order:

1. introduce the source registry, structured accessor, and deterministic
   fixtures without changing any reader;
2. preview active JSON against the other DB-derived sources, then import only
   user-approved JSON-only entries into `legacy_config_seed`, preserving the
   live working-file contents and legacy category metadata without giving
   already-represented Alpha Picks a duplicate permanent source;
3. migrate `/profile/universe` and profile import/tag bootstrap;
4. migrate the symbol-catalog local seed;
5. replace or remove the currently unused DAL tier compatibility method;
6. generate a reviewed transition snapshot from the accessor so DB-only symbols
   are added to JSON and JSON-only symbols already imported remain present;
7. verify every runtime reader uses the accessor and current JSON/accessor sets
   are exactly equal at the reviewed cutover snapshot;
8. stop `sa_native_host` and `SAAlphaPicksClient` from writing JSON; then
9. remove runtime JSON loaders and retire the tracked file.

Writer-last is mandatory. Stopping the extension writer before readers and
import are complete can strand current Alpha Picks; leaving it active after
cutover recreates background git noise and dual authority.

Static acceptance includes zero runtime `tickers_core.json` reads/writes after
the exporter/importer compatibility module is excluded from the search.

## 6. Strict Parity and Cutover Safety

During the dual-path transition, parity means strict set equality:

```text
flatten(active JSON tiers) == new accessor tickers
```

It is never a subset/superset assertion. A mismatch is either an unimported
legacy membership, a missing DB source, an archive/hidden-policy discrepancy,
or a real bug that requires an explicit decision.

The implementation plan must provide:

- deterministic fixture parity tests for every source and overlap;
- a read-only live preview listing JSON-only and DB-only symbols;
- an explicit, gated import of JSON-only active membership;
- a generated transition snapshot that includes DB-only membership after user
  review, followed by an exact current-JSON/accessor comparison;
- source/database fingerprints rechecked immediately before writer cutover; and
- a stop condition if the file or source DBs change during the cutover window.

Cross-database data need not be transactionally copied. The cutover is a
bounded maintenance operation with the extension idle, fingerprints on every
input, and no silent last-writer-wins behavior.

## 7. On-Demand Compatibility Export

The app owns export after cutover. Extension code never writes the file.

The exporter:

- reads one accepted `ActiveUniverseSnapshot`;
- emits deterministic sorted JSON with atomic file replacement or a browser
  download;
- is invoked only on demand;
- includes source-derived groups needed by legacy consumers;
- preserves imported legacy tier/category metadata for round-trip
  compatibility; and
- never mutates DB state.

Because JSON has no comments, its generated warning is a top-level metadata
object:

```json
{
  "_generated": {
    "authority": "profile_state.db + sa_capture.db via active_universe",
    "warning": "Generated compatibility snapshot; manual edits have no runtime effect",
    "generated_at": "..."
  }
}
```

The flattened active ticker set of an export must exactly equal the accessor
snapshot used to create it. Export age is harmless because no runtime reader
uses it.

Terminal git policy is:

- remove the tracked `config/tickers_core.json` after successful cutover;
- ignore that path so an explicitly requested legacy export cannot become
  routine git churn; and
- never delete/replace the current dirty file until its content has appeared in
  migration preview and the user has approved the cutover.

## 8. Catalog Supersession

This design supersedes the standing `ARKSCOPE_TOOL_CATALOG.md` promise that the
UI must opt into/follow Alpha Picks through a new gated action. V1 is automatic
derived eligibility with no second switch. A future explicit source-retirement
control is additive and withdraws eligibility without deleting facts.

The catalog wording changes in the same commit as this adopted design so the
two authorities never describe contradictory product behavior.

## 9. Alternatives Rejected

### 9.1 Keep JSON as an automatically maintained cache

Rejected because runtime readers can silently recouple to it, background writes
dirty the repository, and DB/JSON become competing authorities again.

### 9.2 Copy Alpha Picks into watchlist membership rows

Rejected because provider facts already have an authority. Copying them creates
sync/delete semantics and makes a removed pick indistinguishable from a user
list decision.

### 9.3 Add a default-on source switch now

Rejected for V1 because the extension already controls update cadence and the
user actively wants current picks included. The real unsupported case is feed
retirement, retained as the named additive follow-up in §3.6.

### 9.4 Expire Alpha Picks membership by age

Rejected because staleness is not proof of cancellation. The UI may warn; it
must not silently remove or delete.

## 10. Non-Goals

- retiring ticker-bearing sections of `config/user_profile.yaml`;
- deleting historical ticker data;
- automatically enabling/disabling provider sources by subscription inference;
- changing Alpha Picks capture cadence;
- implementing Alpha Picks article matching;
- making exported JSON editable authority; or
- combining this migration with P2.8 Slice 3.

## 11. Verification Contract

The future implementation plan must prove:

1. source sets union deterministically and retain all source provenance;
2. an Alpha Pick removal withdraws only `sa_alpha_picks_current`;
3. holdings/list overlap keeps a removed Alpha Picks ticker active;
4. archived list/account/position state follows the locked predicates;
5. stopped/stale Alpha Picks capture warns but does not age-expire membership;
6. unavailable source DBs fail closed and never masquerade as empty;
7. JSON-only live entries survive the gated import;
8. strict parity is exact before writer cutover;
9. all readers migrate before the native-host writer is removed;
10. the off/retirement path remains absent in V1 rather than existing untested;
11. export is deterministic, generated-labelled, and exact-set equivalent;
12. manual changes to an exported file have no runtime effect;
13. runtime static scans find no JSON reader/writer outside explicit
    import/export compatibility code; and
14. the current uncommitted JSON edit is preserved through preview and is not
    staged, overwritten, or reverted by implementation setup.

## 12. Sequence

Written review may refine this design now. Implementation begins only after
P2.8 Slice 3, in a separate branch and plan from Alpha Picks article
reconciliation.
