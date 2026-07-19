# DB-Derived Universe and `tickers_core.json` Retirement Design

> **Status:** APPROVED; WRITTEN REVIEW GREEN; IMPLEMENTATION PLAN REVIEW GREEN.
> P2.8 Slice 3 and the Alpha Picks reconciliation line are live. The cleared
> RED-first implementation plan is at
> `docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md`;
> implementation may proceed in an isolated worktree while the user's dirty
> JSON remains protected.

## 1. Purpose

Make local databases the runtime authority for ArkScope's active ticker
universe, automatically include current Alpha Picks as one derived source, and
retire `config/tickers_core.json` from both runtime reads and
native-host/fallback writes. Retain an explicit, deterministic, on-demand
compatibility export.

This design retires `tickers_core.json`; it does not claim to retire every
ticker-bearing legacy setting in `config/user_profile.yaml`.

## 2. Ground Truth

### 2.1 Alpha Picks facts already live in SQLite

Every successful Alpha Picks current/closed refresh writes pick facts to
schema-v2 `data/sa_capture.db`. On current-refresh success, the native host
separately calls `sync_tickers_to_collection()` and rewrites
`tier3_user_watchlist.sa_alpha_picks_auto` in `config/tickers_core.json`.
The v2 lineage/link/decision tables are orthogonal to universe membership;
current eligibility still comes from `sa_alpha_picks` itself.

The extension's `Auto-sync Alpha Picks` control only schedules browser alarms
through the Chrome-compatible extension API used by both shipped builds.
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

The sole write implementation is
`SAAlphaPicksClient.sync_tickers_to_collection()`. It is reached both from
`sa_native_host._try_ticker_sync()` after a successful current refresh and from
the optional `refresh_portfolio(sync_tickers=True)` fallback. Both call paths
retire in this slice. Maintained news collectors, the scheduler,
`daily_update`, the market-data coverage route, and direct market-data helpers
already call `src.universe_scope.resolve_active_universe()` rather than JSON.

That resolver is not yet the target authority: it selects every distinct
`watchlist_memberships.ticker`, does not join the parent list or filter either
archive column, does not include open portfolio positions or current Alpha
Picks, and returns `[]` for both a valid empty universe and an unavailable DB.
The new structured accessor replaces those semantics; this is not a cosmetic
refactor of the existing query.

The writer also checks legacy key `tier2_extended`, while the tracked file and
current loader use `tier2_expanded`. Flattened set parity, rather than trusting
that writer's category-level dedupe, is therefore the migration authority. The
writer is retired after cutover instead of receiving a separate cleanup slice.

The exact migration inventory, rather than a remembered reader count, is the
review/ratchet authority.

### 2.3 Fresh read-only parity snapshot

A fresh read-only probe at `2026-07-19T11:48:38+08:00`, against production
schema v2 and the live dirty JSON file, produced:

| Set | Distinct symbols |
|---|---:|
| active JSON tiers | 152 |
| active manual-list membership | 148 |
| open positions under unarchived accounts | 10 |
| current, non-stale Alpha Picks | 44 |
| raw union of the three DB-derived sources | 151 |
| DB-derived union after the explicit hidden veto | 150 |

All 10 current open-position rows have `asset_class='stock'`. That is snapshot
evidence, not the future membership predicate; §4.1 explicitly covers ETF,
option-underlying, and unsupported-class behavior.

The raw diff is exact: JSON-only `ATGE` and `LC`; DB-only `HAPN`. The profile
also hides `ATGE` and `BRK.B`; `BRK.B` is still a real Alpha Picks source fact,
but the explicit veto removes it from the effective universe. Therefore the
migration preview must classify at least three different cases instead of
calling all JSON-only rows missing data:

- hidden JSON-only `ATGE` is not imported as active membership;
- visible JSON-only `LC` is classified `superseded_by_rename`, because commit
  `7150ba7` and the migrated market/profile state establish `LC -> HAPN`; its
  default action is **do not import** unless the user explicitly overrides that
  known rename; and
- DB-only `HAPN` enters the generated transition snapshot from its DB source.

The working tree's one-line uncommitted addition is `BTSG` under
`sa_alpha_picks_auto`. It is already represented by the current Alpha Picks DB
source, so it must survive preview without becoming a duplicate permanent
`legacy_config_seed` membership. Implementation must preserve and preview the
live file; it must never stage, overwrite, revert, or silently replace that
edit during setup.

These counts are evidence snapshots, not migration constants. The cutover gate
recomputes every set and fingerprint immediately before it writes anything.

### 2.4 Other legacy inputs are not hidden membership sources

`config/user_profile.yaml` currently contributes 17 tickers to the legacy
overview, and all 17 are already represented by active manual-list membership.
After migration, that overview may enrich rows and its theme groups may still
seed classification tags, but it does not independently qualify active
membership. Cutover must prove its current ticker set is a subset of the
accepted accessor or stop for an explicit import decision.

`all_universe_tickers()` also exposes 46 `legacy_reference`-only symbols to the
offline symbol-catalog seed. They are not active membership. The current SEC
cache already carries 43 of them; `ANSS`, `SGEN`, and `WBA` are absent from that
cache and from every active source. This slice deliberately does not import the
46 as active or compatibility membership. The symbol catalog continues to use
the active snapshot as its guaranteed local seed and the existing SEC cache as
its broad reference authority; retiring stale `legacy_reference` may narrow
cache-less offline autocomplete, but may not enlarge the active universe.

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
9. **Universe identity is exact after trim/uppercase.** The accessor does not
   apply market-data alias collapse. `BRK.B` and `BRK B` remain distinct source
   keys so hiding the duplicate `BRK.B` cannot accidentally suppress canonical
   `BRK B`; downstream market reads keep their independent alias resolver.
10. **Legacy reference is not membership.** `legacy_reference` is neither
    imported nor exported as active universe state.
11. **Legacy overview is enrichment, not qualification.** Ticker-bearing
    `user_profile.yaml` fields remain outside this retirement slice, but no
    longer enter `/profile/universe` through an independent union leg.

## 4. Source and Accessor Model

### 4.1 Code-reviewed source registry

The registry defines source keys and read adapters:

| Source | Authority | Active membership |
|---|---|---|
| `manual_lists` | `profile_state.db` | membership and parent list both have `archived_at IS NULL` |
| `portfolio_open` | `profile_state.db` | `position.closed_at IS NULL`, account `archived_at IS NULL`, and normalized `asset_class` is one of `stock`, `etf`, or `option`; an IBKR option row contributes its stored underlying `symbol`; `include_in_total` is irrelevant to membership |
| `sa_alpha_picks_current` | `sa_capture.db` | distinct exact symbols where `portfolio_status='current' AND is_stale=0` |
| `legacy_config_seed` | `profile_state.db` | user-approved active JSON-only membership with `archived_at IS NULL` |

The registry contains no V1 `enabled` flag for Alpha Picks. It may reserve an
additive source-policy interface for the named retirement follow-up, but must
not ship a hidden environment flag or dead UI branch.

Portfolio rows with `cash`, futures, FX, bonds, or any unknown/unsupported
asset class do not enter this equity/news universe. Their exclusion is exposed
as a `portfolio_open` source warning rather than silently treating an unknown
class as an equity ticker. This deliberately retains ETF holdings and the
underlying symbol of option holdings while refusing to inject non-equity
contract keys.

The one-time JSON importer stores annotations for every reviewed active JSON
entry, even when another DB source already qualifies that ticker. It creates a
`legacy_config_seed` membership only for user-approved JSON-only entries.
Therefore category round-tripping does not require duplicating Alpha Picks,
portfolio, or manual-list membership. Tier does not regain product priority
semantics. Existing classification tags remain on their independent
facet/source axis and do not qualify a ticker by themselves.

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

Only `legacy_config_seed` writes `universe_source_memberships` in V1. The
annotation table may contain rows for any reviewed active JSON ticker and has
no membership authority; it must not have a foreign key that requires a
matching membership row. Manual lists, open portfolio positions, and current
Alpha Picks remain direct derived reads from their existing authorities. The
one-to-many annotation table prevents round-trip metadata from being collapsed
to one arbitrary category.

### 4.2 Structured snapshot

The single accessor returns more than a bare list:

```text
ActiveUniverseSnapshot
  tickers[]                 sorted exact normalized symbols
  sources_by_ticker{}       ticker -> sorted source keys
  source_status{}           available, optional last_success_at, optional warning
  unavailable_sources[]
  generated_at
```

`resolve_active_universe()` remains a thin compatibility adapter over
`snapshot.tickers` while callers migrate. It returns a list only from a complete
accepted snapshot; source failure raises a typed `ActiveUniverseUnavailable`
rather than returning the same `[]` used by a valid empty universe. New readers
use the structured snapshot so UI/export can explain why a symbol is present.

The typed failure has one sanitized boundary shape: stable code
`active_universe_unavailable`, sorted `unavailable_sources`, and safe
source-level reason codes. It never carries raw SQLite exceptions, file paths,
provider credentials, or source rows.

All source symbols use the same trim-and-uppercase normalization. Alias
canonicalization is intentionally absent at this layer. Source provenance is
collected before `ticker_meta.hidden_at` applies its exact-key final veto.

`ticker_meta.hidden_at` remains the final explicit user veto over the union.
An archived list member is not active merely because the current resolver used
to select every membership row without archive predicates.

### 4.3 Cross-database failure behavior

The accessor opens short read-only transactions against `profile_state.db` and
`sa_capture.db` and never copies Alpha Picks or portfolio facts into a second
membership table. `source_status.available` means the source DB and required
schema were readable, not that the provider's latest refresh succeeded. For
Alpha Picks, `sa_refresh_meta(scope='current')` supplies the optional
`last_success_at` and warning: a failed latest refresh preserves the last
successful current set and reports a warning instead of withdrawing it. Local
list, portfolio, and legacy-seed sources do not invent a provider-success
timestamp.

If any registered source required for a complete snapshot is unavailable:

- scheduler/collector callers fail closed rather than silently collect an
  incomplete universe;
- V1 UI/API callers return a typed unavailable response rather than inventing
  an empty or partial universe; and
- an unavailable source is not reported as an observed empty set.

Every current compatibility caller has an explicit landing contract:

| Caller | Required unavailable-source behavior |
|---|---|
| `service.data_scheduler` | `run_source()` records a durable `failed` outcome before any provider/subprocess call and returns normally so the scheduler loop survives |
| `collectors.finnhub_news` | abort scope resolution before provider construction/fetch; the CLI exits non-zero with a sanitized universe error |
| `collectors.polygon_news` | abort scope resolution before provider construction/fetch; the CLI exits non-zero with a sanitized universe error |
| `daily_update` | catch the typed failure once before its per-source loop, log the stable code, and exit non-zero without running any source |
| `market_data_direct` | propagate the typed failure before constructing or calling IBKR/Polygon providers |
| `api.routes.market_data` coverage route | return HTTP 503 with the sanitized typed envelope; do not return a fabricated zero-coverage result |

A complete but genuinely empty snapshot remains a distinct value. Each caller
may apply its existing empty-work policy, but tests must prove it is not
reported as `active_universe_unavailable`.

V1 adds no second persisted last-snapshot cache. A future cache may be additive
only if it carries explicit source staleness and never masquerades as a fresh
read.

Age may drive a warning but never automatic source removal. Last-success time
is evidence of freshness, not evidence that a subscription ended.

## 5. Readers-First Migration

Migration proceeds in this order:

1. introduce the source registry, structured accessor, and deterministic
   fixtures without changing any reader;
2. preview the exact live active JSON set against DB-derived sources and the
   hidden veto, categorizing hidden, JSON-only, DB-only, and overlapping rows;
3. persist reviewed annotations for all active JSON entries, but create
   `legacy_config_seed` membership only for user-approved visible JSON-only
   entries; separately prove every current `user_profile.yaml` overview ticker
   is already represented or stop for an explicit import decision;
4. migrate `/profile/universe` and profile import/tag bootstrap so the overview
   enriches accepted rows but no longer contributes an independent membership
   union leg;
5. migrate the symbol-catalog guaranteed local seed to the accepted active
   snapshot while retaining the SEC cache as its broad reference authority;
6. replace or remove the currently unused DAL tier compatibility method;
7. generate a reviewed transition snapshot from the accessor so DB-only symbols
   are added, approved legacy membership remains present, and hidden symbols
   plus `legacy_reference` are absent;
8. verify every runtime reader uses the accessor and the generated transition
   snapshot/accessor sets are exactly equal;
9. remove both callers and the implementation of
   `sync_tickers_to_collection()`; then
10. remove runtime JSON loaders and retire the tracked file.

Writer-last is mandatory. Stopping the native-host/fallback writer before
readers and import are complete can strand current Alpha Picks; leaving it
active after cutover recreates background git noise and dual authority.

Static acceptance includes zero runtime `tickers_core.json` reads/writes after
the exporter/importer compatibility module is excluded from the search.

## 6. Strict Parity and Cutover Safety

The dirty input file is preview evidence, not the final parity target. Its raw
active set currently includes hidden symbols. After user decisions and import,
the app generates a transition snapshot whose active tiers contain exactly the
effective accessor set:

```text
flatten(generated transition JSON active tiers) == accepted snapshot.tickers
```

It is never a subset/superset assertion. A mismatch is either an unimported
legacy membership, a missing DB source, an archive/hidden-policy discrepancy,
an exact-key normalization error, or a real bug that requires an explicit
decision. Hidden input rows remain visible in preview but are absent from both
sides of the final equality.

The implementation plan must provide:

- deterministic fixture parity tests for every source and overlap;
- a read-only live preview listing JSON-only, DB-only, hidden, and overlapping
  symbols with their exact source/category provenance;
- an explicit, gated import of JSON-only active membership;
- a current `user_profile.yaml`-ticker subset proof;
- a generated transition snapshot that includes DB-only membership after user
  review, followed by an exact generated-JSON/accessor comparison;
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
- reconstructs reviewed legacy tier/category groups from annotations and puts
  otherwise ungrouped active source members in deterministic generated groups;
- preserves imported legacy tier/category metadata for round-trip
  compatibility; and
- omits the retired top-level `settings` block (`default_tier`, tier-inclusion,
  capacity, request-size, and news-lookback keys), because fresh static review
  found no runtime reader and export is not a round-trip authority; and
- never mutates DB state.

It filters every group through the accepted effective snapshot. Hidden symbols
and the old `legacy_reference` block are never exported as active entries.

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

The catalog wording changed with the adopted design; fresh review confirms it
still describes automatic eligibility and the writer-last transition rather
than the retired opt-in proposal.

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
- implementing P2.8 Slice 4 Settings changes in the same branch.

## 11. Verification Contract

The future implementation plan must prove:

1. source sets union deterministically and retain all source provenance;
2. an Alpha Pick removal withdraws only `sa_alpha_picks_current`;
3. holdings/list overlap keeps a removed Alpha Picks ticker active;
4. archived lists/memberships/accounts and closed positions follow the exact
   locked predicates, `include_in_total=false` does not withdraw a holding,
   `stock`/`etf`/`option` contribute the reviewed equity symbol, and every other
   or unknown asset class is excluded with a source warning;
5. stopped/stale Alpha Picks capture warns but does not age-expire membership;
6. an accessible Alpha Picks DB with failed latest refresh remains available
   with warning and preserved membership;
7. unavailable source DBs raise typed failure and never masquerade as empty;
8. every one of the six current compatibility callers exercises its explicit
   fail-closed landing: scheduler survival with durable failure, two collector
   non-zero exits, pre-loop `daily_update` abort, pre-provider direct-market
   abort, and sanitized HTTP 503 coverage response;
9. exact normalization preserves `BRK.B` and `BRK B` as distinct keys, so the
   existing `BRK.B` veto does not hide `BRK B`;
10. annotations for already-represented JSON tickers do not create duplicate
   permanent membership;
11. approved JSON-only live entries survive the gated import, hidden JSON-only
    entries do not become active, and known rename predecessor `LC` is previewed
    as `superseded_by_rename` with default action `do_not_import`;
12. all current legacy-overview tickers are represented before that union leg
    is removed;
13. `legacy_reference` never enters active membership or active export;
14. strict hidden-aware parity is exact before writer cutover;
15. all readers migrate before both native-host/fallback writer paths and the
    shared writer implementation are removed;
16. the off/retirement path remains absent in V1 rather than existing untested;
17. export is deterministic, generated-labelled, exact-set equivalent, and
    omits the retired settings block;
18. manual changes to an exported file have no runtime effect;
19. runtime static scans find no JSON reader/writer outside explicit
    import/export compatibility code; and
20. the current uncommitted JSON edit is preserved through preview and is not
    staged, overwritten, or reverted by implementation setup.

## 12. Sequence

P2.8 Slice 3 and Alpha Picks reconciliation are live, so the former sequencing
block is satisfied. Independent written review is GREEN. The separate RED-first
implementation plan may now open; product implementation remains blocked until
that plan receives independent review. P2.8 Slice 4 remains next after this
bounded authority retirement rather than sharing its branch or A/B baseline.
