# DB-Derived Universe and `tickers_core.json` Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** CLEARED FOR IMPLEMENTATION; IMPLEMENTATION NOT STARTED.
> Independent plan review is GREEN with exact raw accounting `+54/-6`. The
> user's unstaged `config/tickers_core.json` edit remains outside this plan
> commit and must remain protected through the reviewed cutover gate.

**Goal:** Make one complete, explainable SQLite-derived snapshot the runtime
authority for ArkScope's active ticker universe, migrate every reader to it,
preserve reviewed legacy metadata through explicit compatibility import/export,
and retire both automatic `tickers_core.json` writers plus the tracked file.

**Architecture:** `src/active_universe.py` owns the four-source registry,
read-only cross-database snapshot, exact-key hidden veto, source health, and a
sanitized typed unavailable error. `src/universe_compat.py` owns explicit legacy
JSON parsing, preview decisions, annotation projection, and deterministic export;
`src/audit/universe_retirement.py` owns copied-DB/live maintenance commands and
fingerprint gates but is never imported by runtime readers. Profile-state stores
only reviewed compatibility membership/annotations; list, portfolio, and Alpha
Picks facts remain direct reads from their existing authorities. Readers migrate
first, then the legacy native-host/client writer and JSON loader retire together.

**Tech Stack:** Python 3.11, stdlib SQLite/WAL and dataclasses, FastAPI, pytest,
the existing local `profile_state.db` and `sa_capture.db` authorities, and Git
worktree/virgin-archive A/B verification. The React app and browser extension
JavaScript are byte-protected in this slice.

---

## Global Constraints

1. The design authority is
   `docs/superpowers/specs/2026-07-17-db-derived-universe-tickers-core-retirement-design.md`.
   This plan may make implementation details concrete but may not weaken its
   source union, exact identity, hidden veto, typed failure, readers-first,
   writer-last, strict parity, or history-preservation decisions.
2. The runtime source keys are exactly `manual_lists`, `portfolio_open`,
   `sa_alpha_picks_current`, and `legacy_config_seed`. Do not add a V1 source
   enable flag, age-expiry rule, fallback JSON source, or cached second authority.
3. A complete snapshot requires every registered source schema to be readable.
   Missing files/tables and corrupt/unreadable databases are typed unavailable;
   they are never converted to an observed empty set. Accessor reads use SQLite
   URI `mode=ro`, `PRAGMA query_only=ON`, and short read transactions. They never
   create a file or run schema migration.
4. Profile schema creation remains an explicit store/startup or maintenance
   action. The accessor may assume the reviewed profile/portfolio tables exist;
   if they do not, it reports safe source reason codes. Do not add DB work to
   `/healthz` or otherwise violate the API's cheap-readiness contract.
5. Universe identity is `trim().upper()` only. Never call the market alias
   resolver here. `BRK.B` and `BRK B` remain distinct, and the existing exact
   `BRK.B` hidden veto must not suppress `BRK B`.
6. `portfolio_open` accepts normalized `stock`, `etf`, and `option`. An option
   contributes the stored underlying `portfolio_positions.symbol`. Cash, FX,
   futures, bonds, blank symbols, and unknown classes are excluded and produce
   safe count-only warnings; raw contract IDs/classes are not returned.
7. `include_in_total` is an accounting preference, not membership. Closed
   positions and positions under archived accounts are excluded.
8. Alpha Picks membership is current, non-stale provider fact. A failed latest
   refresh or a last success older than the existing reviewed SA health horizon
   of 48 hours adds warnings but does not withdraw captured membership. No age
   condition appears in the membership SQL.
9. A hidden ticker is removed after source provenance is assembled. Hidden
   source facts remain observable in migration preview but do not enter runtime
   snapshot/export.
10. Archived manual-list history remains visible in `/profile/universe` only
    when `include_archived=true`, but it is not an active source, export member,
    scheduler scope, or `tracked=true` symbol-search result. A ticker active via
    another source is not marked archived merely because all of its list rows
    are archived.
11. `user_profile.yaml` overview rows enrich accepted/archived UI rows but never
    qualify a ticker. The live cutover must prove the current overview set is a
    subset of the accepted active snapshot or stop.
12. Compatibility annotations use `source_key='legacy_config_seed'` without a
    membership foreign key. `legacy_tier` stores the raw active tier key;
    `legacy_category` stores the paired path `<tier>/<category>`. The paired
    encoding prevents the exporter from creating a false tier/category Cartesian
    product for symbols appearing in more than one group.
13. A compatibility import writes annotations for every reviewed active JSON
    row. It writes active `legacy_config_seed` membership only for explicitly
    approved visible generic JSON-only rows. Hidden rows, overlap rows, and known
    rename predecessor `LC` receive no active compatibility membership.
14. `LC -> HAPN` is the only reviewed V1 rename decision. Preview labels `LC`
    `superseded_by_rename` and defaults to `do_not_import`. Do not build a broad
    alias engine into this slice.
15. The exporter omits `_description` inputs, `legacy_reference`, hidden symbols,
    and the retired top-level `settings` object. Its flattened active set must be
    exactly the snapshot used to produce it. A mismatch raises; it is never
    relaxed to subset/superset parity.
16. The user's main-checkout `config/tickers_core.json` currently contains an
    unstaged `BTSG` addition. Task setup may inspect/hash/diff it read-only, but
    may not copy it into the implementation worktree, stage it, restore it,
    rewrite it, or include it in an implementation commit. Its only destructive
    transition occurs after copied-DB live preview, retained backup, explicit
    user approval, independent implementation GREEN, and stopped-service merge.
17. Browser extension JavaScript, `apps/arkscope-web`, market/news schemas,
    capture cadence, Alpha Picks article reconciliation, provider configuration,
    and P2.8 Slice 4 Settings are out of scope.
18. Existing raw provider/database exceptions and filesystem paths must not cross
    API/CLI/scheduler boundaries. The typed envelope contains only allowlisted
    source keys and reason codes.
19. No task may silently change test accounting. Any node addition, removal, or
    rename outside the reviewed ledger is a stop-and-review condition.

---

## Authority, Base, and Exact Accounting

- Canonical behavior/A-B base: `5d8748f` (`fix: include reconciliation UI in
  Firefox build`). Commits `cb6b6c9` and `0fb872d` are documentation-only and
  therefore do not change behavior.
- Plan-authoring tip: `0fb872d` (`docs: close DB universe written review`).
- Implementation branch point: the exact docs tip receiving independent plan
  review GREEN. Record it as `PLAN_REVIEW_CLEARANCE_COMMIT` in the execution
  ledger before Task 0. It must descend from `0fb872d`; do not branch directly
  from the behavior base and omit the reviewed plan.
- Current full collection is exactly `4514 tests collected`. The last canonical
  family plus the merged Firefox regression gives the expected baseline:

  ```text
  4403 passed / 30 failed / 74 skipped / 7 errors / 18 warnings
  ```

  Task 0 must reproduce collection and record any environment-only difference
  before RED. Canonical completion compares virgin archives sequentially and
  requires identical pre-existing failure/error node identities, not just counts.
- Focused baseline command:

  ```bash
  pytest --collect-only -q \
    tests/test_profile_state.py \
    tests/test_symbol_catalog.py \
    tests/test_data_access.py \
    tests/test_collector_adapters.py \
    tests/test_data_scheduler.py \
    tests/test_daily_update_wrapper.py \
    tests/test_market_data_direct.py \
    tests/test_trading_day_coverage.py \
    tests/test_sa_tools.py \
    tests/test_sa_reconciliation_native_host.py
  ```

  Expected: `388 tests collected`.
- Frontend baseline is fresh and byte-protected: `60 files / 572 tests`, plus
  typecheck and production build.
- Reviewed raw node accounting is `+54/-6`, semantic net `+48`:

  | Test owner | Added | Removed | Net |
  |---|---:|---:|---:|
  | `tests/test_active_universe_profile_store.py` | 6 | 0 | +6 |
  | `tests/test_active_universe.py` | 14 | 0 | +14 |
  | `tests/test_universe_compat.py` | 12 | 0 | +12 |
  | `tests/test_universe_retirement_audit.py` | 6 | 0 | +6 |
  | `tests/test_profile_state.py` | 5 | 2 | +3 |
  | `tests/test_symbol_catalog.py` | 3 | 0 | +3 |
  | six caller landing tests in existing files | 6 | 0 | +6 |
  | writer-retirement tests in `tests/test_sa_tools.py` | 2 | 3 | -1 |
  | dormant DAL tier-reader removal in `tests/test_data_access.py` | 0 | 1 | -1 |
  | **Total** | **54** | **6** | **+48** |

- The six intentionally removed nodes are:

  ```text
  tests/test_profile_state.py::test_config_tag_seeds_structure
  tests/test_profile_state.py::test_active_universe_excludes_legacy_reference
  tests/test_data_access.py::TestConfigAccess::test_get_tier_tickers
  tests/test_sa_tools.py::TestTickerSync::test_current_picks_synced_to_tickers_core
  tests/test_sa_tools.py::TestTickerSync::test_closed_picks_not_synced
  tests/test_sa_tools.py::TestTickerSync::test_stale_picks_not_synced
  ```

  Each is replaced by stronger DB-authority/import/export/writer-absence tests;
  no product intent is discarded.
- Reviewed targets are focused `388 -> 436`, canonical collection
  `4514 -> 4562`, and (with unchanged known families) passed `4403 -> 4451`.
- Any different `git diff` node ledger is a stop condition. Parameterized tests
  must be counted by collected node ID, not Python function count.

---

## File Map

### Create

- `src/active_universe.py` - source registry, read-only source adapters,
  structured snapshot, source health/warnings, exact hidden veto, and sanitized
  `ActiveUniverseUnavailable`.
- `src/universe_compat.py` - explicit legacy JSON parser, preview classifier,
  reviewed import decisions, annotation-to-tag projection, deterministic
  generated export, exact parity assertion, and optional atomic file writer.
- `src/audit/universe_retirement.py` - explicit preview/apply/export CLI,
  semantic fingerprints, legacy-overview subset gate, and maintenance reports;
  never imported by runtime modules.
- `tests/fixtures/universe/tickers_core_legacy.json` - small sanitized legacy
  fixture containing overlap, hidden, rename, duplicate-group, reference, and
  retired-settings cases.
- `tests/test_active_universe_profile_store.py` - six schema/transaction/history
  contracts.
- `tests/test_active_universe.py` - fourteen source/snapshot/failure contracts.
- `tests/test_universe_compat.py` - twelve parser/preview/import/export contracts.
- `tests/test_universe_retirement_audit.py` - six read-only/fingerprint/apply
  contracts.

### Modify

- `src/profile_state.py` - compatibility tables, validated atomic import,
  annotation projection, active source reads, and archived-list history query.
- `src/universe_scope.py` - thin list compatibility adapter over the complete
  structured snapshot; no SQLite query and no JSON reference.
- `src/api/routes/profile.py` - accepted snapshot inventory, archived-history
  compatibility, source provenance/status, typed 503, annotation-backed tag
  import, no overview qualification, and on-demand export endpoint.
- `src/api/routes/symbols.py` - `tracked` from the accepted snapshot and typed
  unavailable response instead of every historical membership row.
- `src/api/routes/market_data.py` - sanitized 503 landing for coverage.
- `src/symbol_catalog.py` - accepted snapshot as guaranteed local seed; SEC
  remains the broad reference authority and unavailable active state is not
  fabricated.
- `src/tools/sa_tools.py` - remove the stale JSON-writer guarantee sentence;
  tool behavior and registry remain unchanged.
- `src/tools/data_access.py` - remove dormant `get_tickers_config()` and
  `get_tier_tickers()` compatibility readers; update module documentation.
- `src/service/data_scheduler.py` - preserve loop survival/durable failure while
  recognizing typed unavailable scope before provider/subprocess work.
- `src/collectors/finnhub_news.py` and `src/collectors/polygon_news.py` - typed
  scope landing, provider construction ordering, and current DB-derived copy.
- `src/daily_update.py` - one pre-loop typed catch and stable non-zero exit.
- `src/market_data_direct.py` - typed failure before provider construction.
- `src/sa_native_host.py` - remove post-current-refresh `_try_ticker_sync()` call
  and implementation only after every reader/cutover gate is ready.
- `data_sources/sa_alpha_picks_client.py` - remove `sync_tickers` fallback
  parameter, filesystem writer method, and now-unused JSON/path imports.
- `.gitignore` - ignore `/config/tickers_core.json` after tracked retirement.
- The ten existing test files in the focused baseline - add/evolve the exact
  contracts and remove only the six reviewed obsolete nodes.
- `docs/superpowers/specs/2026-07-17-db-derived-universe-tickers-core-retirement-design.md`
  and `docs/design/PROJECT_PRIORITY_MAP.md` - status/ledger updates only.

### Delete, Writer-Last

- `src/universe_config.py` - only after runtime imports and stored-annotation
  replacement are proven.
- `config/tickers_core.json` - branch deletes the clean tracked version only in
  the final product task. Main's dirty file remains untouched until the explicit
  stopped-service closeout checkpoint described below.

### Must Not Modify

- `apps/arkscope-web/**`
- `extensions/sa_alpha_picks/**`
- `src/sa_capture_store.py` and Alpha Picks reconciliation schemas
- market/news/portfolio schemas except the additive profile-state compatibility
  tables in `src/profile_state.py`
- provider routing/configuration and scheduler cadence

---

## Locked Runtime Interfaces

The implementation must use these names and shapes so later tasks and tests do
not invent parallel contracts:

```python
# src/active_universe.py
SOURCE_KEYS = (
    "manual_lists",
    "portfolio_open",
    "sa_alpha_picks_current",
    "legacy_config_seed",
)
EQUITY_ASSET_CLASSES = frozenset({"stock", "etf", "option"})
SA_STALE_AFTER_HOURS = 48

@dataclass(frozen=True)
class SourceStatus:
    available: bool
    last_success_at: str | None = None
    warnings: tuple = ()  # immutable, sorted strings

@dataclass(frozen=True)
class ActiveUniverseSnapshot:
    tickers: tuple
    sources_by_ticker: dict[str, tuple]
    source_status: dict[str, SourceStatus]
    unavailable_sources: tuple
    generated_at: str

class ActiveUniverseUnavailable(RuntimeError):
    code = "active_universe_unavailable"

    def __init__(self, source_reasons: Mapping[str, str]):
        allowed_reasons = {
            "source_db_missing",
            "source_db_unreadable",
            "required_schema_missing",
        }
        normalized = {
            key: (
                source_reasons[key]
                if source_reasons[key] in allowed_reasons
                else "source_db_unreadable"
            )
            for key in SOURCE_KEYS
            if key in source_reasons
        }
        self.source_reasons = normalized
        self.unavailable_sources = tuple(normalized)
        super().__init__(
            f"{self.code}: {','.join(self.unavailable_sources)}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "status": "unavailable",
            "unavailable_sources": list(self.unavailable_sources),
            "source_reasons": dict(self.source_reasons),
        }
```

Accessor signature (implemented in Task 2):

```text
build_active_universe_snapshot(*, profile_db: str | Path | None = None,
                               sa_db: str | Path | None = None,
                               now: datetime | None = None)
    -> ActiveUniverseSnapshot
```

The typed boundary is exact and sanitized:

```json
{
  "code": "active_universe_unavailable",
  "status": "unavailable",
  "unavailable_sources": ["sa_alpha_picks_current"],
  "source_reasons": {
    "sa_alpha_picks_current": "source_db_missing"
  }
}
```

Allowlisted reason codes are:

```text
source_db_missing
source_db_unreadable
required_schema_missing
```

Do not add raw exception text. All dict/list ordering is deterministic.

The profile-store compatibility methods are:

```python
@dataclass(frozen=True)
class UniverseSourceAnnotation:
    source_key: str
    ticker: str
    annotation_key: str
    annotation_value: str

replace_legacy_config_import(*, approved_memberships: Iterable[str],
                             annotations: Iterable[UniverseSourceAnnotation])
    -> dict[str, int]
list_active_universe_source_memberships(source_key="legacy_config_seed")
    -> list[str]
list_universe_source_annotations(source_key="legacy_config_seed")
    -> list[UniverseSourceAnnotation]
legacy_annotation_tag_groups() -> list[dict]
archived_list_tickers() -> list[str]
```

The compatibility layer uses paired category paths:

```python
@dataclass(frozen=True)
class LegacyUniverseEntry:
    ticker: str
    tier: str
    category_path: str  # e.g. tier3_user_watchlist/sa_alpha_picks_auto

@dataclass(frozen=True)
class LegacyPreviewRow:
    ticker: str
    classification: Literal[
        "hidden", "overlap", "json_only", "db_only", "superseded_by_rename"
    ]
    default_action: Literal["annotate_only", "requires_approval", "do_not_import"]
    sources: tuple
    category_paths: tuple
    superseded_by: str | None = None
```

`src/audit/universe_retirement.py` may call compatibility/store interfaces but
no runtime module may import from `src.audit`.

---

## Task 0: Isolated Worktree, Boundary Proof, and Baselines

**Files:**
- Modify later: plan ledger only
- Protect: main checkout `config/tickers_core.json`

- [x] **Step 1: Record the independently reviewed branch point**

After plan review GREEN, record:

```text
PLAN_REVIEW_CLEARANCE_COMMIT=<exact full hash>
BEHAVIOR_AB_BASE=5d8748f
MAIN_CHECKOUT=/mnt/md0/PycharmProjects/ArkScope
```

Expected: clearance descends from `0fb872d`; its product diff from `0fb872d` is
empty.

- [x] **Step 2: Create an isolated implementation worktree**

Use `superpowers:using-git-worktrees`. Preferred branch/path:

```bash
git worktree add /tmp/arkscope-db-universe -b codex/db-derived-universe \
  "$PLAN_REVIEW_CLEARANCE_COMMIT"
```

If linked-worktree git-crypt metadata requires the established `--no-checkout`
flow, copy only Git metadata/key material, then populate with `git read-tree`.
Never copy a working-tree file from main.

- [x] **Step 3: Prove the main dirty-file boundary before any RED**

Run from main:

```bash
git status --short
git diff -- config/tickers_core.json
sha256sum config/tickers_core.json
```

Expected: only the user-owned JSON modification is present, with the one-line
`BTSG` addition. Record the SHA-256 and diff in the plan ledger. Run from the
implementation worktree:

```bash
git status --short
git diff -- config/tickers_core.json
```

Expected: clean worktree and no copied user edit.

- [x] **Step 4: Reproduce baseline collections**

Run the focused collection command from the accounting section and:

```bash
pytest --collect-only -q
```

Expected: focused `388`, full `4514`. A different baseline must be explained
before tests are authored.

- [x] **Step 5: Reproduce byte-protected frontend baseline**

```bash
cd apps/arkscope-web
npm test -- --run
npm run typecheck
npm run build
```

Expected: `60 files / 572 tests`, clean typecheck, build with at most the known
chunk-size warning.

- [x] **Step 6: Commit only the execution-ledger update**

```bash
git add docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md
git commit -m "docs: open DB universe implementation ledger"
```

---

## Task 1: Profile-State Compatibility Tables and Atomic Import

**Files:**
- Modify: `src/profile_state.py`
- Create: `tests/test_active_universe_profile_store.py`

- [ ] **Step 1: Write the six RED schema/store tests**

Create exactly these nodes:

```text
test_universe_source_tables_have_reviewed_shape_without_annotation_fk
test_replace_legacy_config_import_validates_every_row_before_begin
test_replace_legacy_config_import_is_atomic_on_sql_failure
test_replace_legacy_config_import_archives_reactivates_and_is_idempotent
test_annotation_tag_groups_preserve_paired_paths_without_membership
test_archived_list_history_query_never_qualifies_membership
```

The first test must inspect `PRAGMA table_info`, index/PK shape, and
`PRAGMA foreign_key_list(universe_source_annotations)` and assert zero FK to
membership. The validation test supplies one valid and one blank/invalid row,
then asserts no transaction mutation. The SQL-failure test installs a temporary
trigger that aborts the second mutation and proves both membership and
annotations roll back. The idempotency test exercises archive, reactivation,
and exact repeat. The paired-path test uses one ticker in two categories and
asserts no Cartesian expansion. The archive test covers parent-list archive,
membership archive, and a ticker with another active list.

- [ ] **Step 2: Run RED for reviewed reasons**

```bash
pytest -q tests/test_active_universe_profile_store.py
```

Expected: collection succeeds and all six fail because the schema/types/methods
do not exist. A failure caused by importing `universe_config` is the wrong seam.

- [ ] **Step 3: Add the exact additive schema**

Append to `_SCHEMA` in `src/profile_state.py`:

```sql
CREATE TABLE IF NOT EXISTS universe_source_memberships (
    source_key  TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    archived_at TEXT,
    PRIMARY KEY (source_key, ticker)
);
CREATE INDEX IF NOT EXISTS idx_universe_source_memberships_active
ON universe_source_memberships(source_key, ticker)
WHERE archived_at IS NULL;

CREATE TABLE IF NOT EXISTS universe_source_annotations (
    source_key       TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    annotation_key   TEXT NOT NULL,
    annotation_value TEXT NOT NULL,
    PRIMARY KEY (source_key, ticker, annotation_key, annotation_value)
);
CREATE INDEX IF NOT EXISTS idx_universe_source_annotations_ticker
ON universe_source_annotations(ticker, source_key);
```

Do not add a user-version migration or FK. Existing `_ensure_schema()` is the
idempotent profile schema owner.

- [ ] **Step 4: Add validated data types and normalization**

Add the dataclass and constants:

```python
_LEGACY_SOURCE_KEY = "legacy_config_seed"
_LEGACY_ANNOTATION_KEYS = frozenset({"legacy_tier", "legacy_category"})

@dataclass(frozen=True)
class UniverseSourceAnnotation:
    source_key: str
    ticker: str
    annotation_key: str
    annotation_value: str
```

Validation occurs before opening the write transaction. Require exact source
key, nonblank normalized ticker/value, allowlisted key, and for
`legacy_category` exactly one `/` separating nonblank tier/category. Deduplicate
the fully normalized input deterministically.

- [ ] **Step 5: Implement one short atomic replacement transaction**

Use this transaction order under `self._write_lock`:

```python
conn.execute("BEGIN IMMEDIATE")
# archive active legacy memberships absent from approved set
# insert/reactivate every approved membership
# delete only legacy_config_seed annotation rows
# insert the complete reviewed annotation set
conn.commit()
```

On every exception call `rollback()` and re-raise. Never delete historical
membership rows; withdrawal sets `archived_at`. Return deterministic counts:

```python
{
    "memberships_active": len(approved),
    "memberships_archived": archived_count,
    "annotations": len(normalized_annotations),
}
```

- [ ] **Step 6: Implement read projections**

`list_active_universe_source_memberships()` filters `archived_at IS NULL` and
sorts. `list_universe_source_annotations()` sorts all four columns.
`archived_list_tickers()` returns distinct exact tickers for which list history
exists but no active `(watchlist, membership)` pair exists. It does not apply
the hidden veto; the route does that once.

`legacy_annotation_tag_groups()` derives existing tag semantics from the
category component of paired paths:

```text
sa_alpha_picks_auto       -> provenance / Alpha Picks
seeking_picks_<sector>    -> provenance / Seeking Alpha
                              + category / prettified <sector>
all other categories      -> category / prettified category key
```

Tier annotations never become tags or priority.

- [ ] **Step 7: Run GREEN and relevant existing profile tests**

```bash
pytest -q tests/test_active_universe_profile_store.py tests/test_profile_state.py
```

Expected: six new nodes pass; existing tests remain at baseline for now.

- [ ] **Step 8: Commit**

```bash
git add src/profile_state.py tests/test_active_universe_profile_store.py
git commit -m "feat: add universe compatibility state"
```

---

## Task 2: Structured Active-Universe Snapshot and Typed Failure

**Files:**
- Create: `src/active_universe.py`
- Modify: `src/universe_scope.py`
- Create: `tests/test_active_universe.py`

- [ ] **Step 1: Write the fourteen RED snapshot tests**

Create exactly these nodes:

```text
test_snapshot_unions_all_four_sources_and_retains_sorted_provenance
test_manual_lists_require_active_parent_and_membership
test_portfolio_open_requires_open_account_and_position_but_ignores_include_total
test_portfolio_equity_classes_include_stock_etf_option_and_warn_on_others
test_alpha_picks_current_excludes_stale_and_closed
test_alpha_latest_refresh_failure_warns_without_withdrawing_facts
test_alpha_age_warning_uses_48_hours_without_expiring_membership
test_exact_hidden_veto_distinguishes_brk_dot_b_from_brk_space_b
test_legacy_config_seed_is_a_direct_source_not_an_annotation
test_complete_empty_sources_return_an_empty_snapshot
test_missing_profile_db_reports_three_profile_sources_without_paths
test_missing_sa_db_reports_only_alpha_source_without_fake_empty
test_read_paths_use_mode_ro_query_only_and_create_no_files
test_resolve_active_universe_is_a_thin_complete_snapshot_adapter
```

Use real temp SQLite schemas by constructing `ProfileStateStore`,
`PortfolioStore`, and `sa_capture_store.connect()`. Do not hand-write reduced
production schemas except in the explicit missing-schema arms. For malformed
asset classes and exceptions use hostile values containing a temp path/token and
assert neither appears in `as_dict()` or `str(exc)`.

- [ ] **Step 2: Run RED for reviewed reasons**

```bash
pytest -q tests/test_active_universe.py
```

Expected: fourteen failures because `src.active_universe` does not exist.

- [ ] **Step 3: Implement read-only connection and typed error primitives**

Use one helper:

```python
def _open_read_only(path: str | Path) -> sqlite3.Connection:
    candidate = Path(path)
    if not candidate.is_file():
        raise FileNotFoundError
    conn = sqlite3.connect(f"{candidate.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    return conn
```

Map file absence, `sqlite3.DatabaseError`, and missing reviewed tables only to
the three allowlisted reason codes. `ActiveUniverseUnavailable` sorts/filter
source keys against `SOURCE_KEYS` and emits no raw cause. Preserve the cause
internally by raising the sanitized exception with the original exception as
its cause only at construction boundaries; do not serialize that cause.

- [ ] **Step 4: Implement the profile source adapter in one read transaction**

Use these predicates, not post-filter approximations:

```sql
SELECT DISTINCT m.ticker
FROM watchlist_memberships m
JOIN watchlists w ON w.id = m.list_id
WHERE m.archived_at IS NULL AND w.archived_at IS NULL;

SELECT p.symbol, LOWER(TRIM(p.asset_class)) AS asset_class
FROM portfolio_positions p
JOIN portfolio_accounts a ON a.id = p.account_id
WHERE p.closed_at IS NULL AND a.archived_at IS NULL;

SELECT ticker
FROM universe_source_memberships
WHERE source_key='legacy_config_seed' AND archived_at IS NULL;

SELECT ticker FROM ticker_meta WHERE hidden_at IS NOT NULL;
```

Normalize symbols after read. Include stock/ETF/option; skip others. Emit only
safe warnings such as `unsupported_asset_class_count=2` and
`invalid_symbol_count=1`.

- [ ] **Step 5: Implement the Alpha Picks source adapter**

In one SA read transaction query:

```sql
SELECT DISTINCT symbol
FROM sa_alpha_picks
WHERE portfolio_status='current' AND is_stale=0;

SELECT last_attempt_at, last_success_at, ok
FROM sa_refresh_meta WHERE scope='current';
```

No meta row means available with warning `never_refreshed`. `ok=0` means
`latest_refresh_failed`. A parseable `last_success_at` older than 48 hours means
`stale_refresh`. These warnings may coexist. They never change membership.

- [ ] **Step 6: Assemble provenance, apply the exact hidden veto, and finalize**

Build `ticker -> set(source_key)` before removing every exact hidden key. Sort
tickers, each source tuple, status keys, warning tuples, and unavailable keys.
Inject `now` in tests and serialize UTC seconds. If any source is unavailable,
raise one combined `ActiveUniverseUnavailable`; never return a partial snapshot.
Resolve default paths without FastAPI dependencies: `ARKSCOPE_PROFILE_DB` or
`<repo>/data/profile_state.db`, and `sa_capture_store.resolve_sa_db_path()` for
SA.

- [ ] **Step 7: Reduce `universe_scope.py` to the compatibility adapter**

Its entire behavior becomes:

```python
from src.active_universe import build_active_universe_snapshot

def resolve_active_universe() -> list[str]:
    return list(build_active_universe_snapshot().tickers)
```

Retain the public function name only. Remove its SQLite/path/logger code and all
`tickers_core.json` commentary.

- [ ] **Step 8: Run GREEN and no-create probes**

```bash
pytest -q tests/test_active_universe.py tests/test_active_universe_profile_store.py
```

Also run a temp-path probe that calls the accessor with two absent paths and
asserts neither path exists afterward.

- [ ] **Step 9: Commit**

```bash
git add src/active_universe.py src/universe_scope.py \
  tests/test_active_universe.py
git commit -m "feat: derive the active universe from SQLite"
```

---

## Task 3: Explicit Legacy Preview, Import Decisions, and Exact Export

**Files:**
- Create: `src/universe_compat.py`
- Create: `tests/fixtures/universe/tickers_core_legacy.json`
- Create: `tests/test_universe_compat.py`

- [ ] **Step 1: Add the sanitized legacy fixture**

The fixture must include:

```text
tier1_core: AAPL, LC, ATGE
tier2_expanded: OKTA
tier3_user_watchlist/sa_alpha_picks_auto: BTSG, OKTA
tier3_user_watchlist/seeking_picks_tech: BTSG
legacy_reference: WBA
settings: every retired settings key
```

Use synthetic descriptions only. Do not copy licensed Alpha Picks article data
or user profile content.

- [ ] **Step 2: Write the twelve RED compatibility tests**

Create exactly:

```text
test_parse_active_json_preserves_paired_paths_and_ignores_reference_settings
test_preview_classifies_hidden_overlap_json_only_and_db_only
test_preview_classifies_lc_as_superseded_by_hapn_default_no_import
test_preview_treats_dirty_btsg_as_alpha_overlap_not_seed_membership
test_import_requires_explicit_visible_json_only_approval
test_import_writes_all_annotations_but_membership_only_for_approved_rows
test_export_preserves_category_paths_without_cartesian_pairs
test_export_places_unannotated_db_symbols_in_generated_group
test_export_filters_hidden_reference_and_retired_settings
test_export_is_generated_deterministic_exact_and_manual_edits_are_inert
test_export_rejects_annotation_snapshot_mismatch_instead_of_relaxed_parity
test_atomic_export_failure_preserves_the_existing_target
```

The `BTSG` test uses a snapshot source of `sa_alpha_picks_current` and asserts
`annotate_only`. The LC test requires HAPN in the snapshot and asserts
`superseded_by='HAPN'`, `do_not_import`. The inert-edit test writes an export,
modifies it, then rebuilds a snapshot and proves no runtime read touches it.

- [ ] **Step 3: Run RED**

```bash
pytest -q tests/test_universe_compat.py
```

Expected: twelve failures because the compatibility module is absent.

- [ ] **Step 4: Implement parser and preview classification**

Use exact constants:

```python
ACTIVE_TIERS = ("tier1_core", "tier2_expanded", "tier3_user_watchlist")
KNOWN_RENAMES = {"LC": "HAPN"}
GENERATED_TIER = "tier3_user_watchlist"
GENERATED_CATEGORY = "db_derived_active"
```

Parsing accepts only dict categories with a list-valued `tickers` field or a
legacy bare list. It ignores keys beginning `_`, top-level settings, unknown
tiers, and `legacy_reference`. Every output entry stores
`category_path=f"{tier}/{category}"`.

Preview precedence is:

```text
hidden -> superseded_by_rename -> overlap -> json_only
snapshot-only -> db_only
```

Rows sort by ticker/classification. Categories and sources sort and dedupe.

- [ ] **Step 5: Implement explicit import materialization**

`build_reviewed_import(preview, approved_json_only)` must reject approval names
not present as visible generic `json_only`. It returns:

```python
ReviewedLegacyImport(
    approved_memberships=("ACME",),
    annotations=(
        UniverseSourceAnnotation(
            source_key="legacy_config_seed",
            ticker="ACME",
            annotation_key="legacy_category",
            annotation_value="tier3_user_watchlist/manual_review",
        ),
    ),
)
```

Emit `legacy_tier` and paired `legacy_category` annotations for every active
input row regardless of membership action. Hidden, overlap, and superseded rows
remain annotate-only/no-membership.

- [ ] **Step 6: Implement deterministic export and exact flattening**

The returned dict starts with:

```python
{
    "_generated": {
        "authority": "profile_state.db + sa_capture.db via active_universe",
        "warning": "Generated compatibility snapshot; manual edits have no runtime effect",
        "generated_at": snapshot.generated_at,
    },
    "tier1_core": {},
    "tier2_expanded": {},
    "tier3_user_watchlist": {},
}
```

For each active ticker, place it in every valid paired annotated category. If it
has no valid paired category, place it once in
`tier3_user_watchlist/db_derived_active`. Filter every group through
`snapshot.tickers`, sort object keys and ticker arrays, and assert:

```python
flatten_generated_active_tickers(document) == set(snapshot.tickers)
```

Do not emit `settings` or `legacy_reference`.

- [ ] **Step 7: Implement optional atomic file replacement**

`write_compat_export(path, document)` writes UTF-8 JSON to a sibling temp file,
flushes and `os.fsync()`s it, sets mode `0600`, and calls `os.replace()`. Clean
the temp file on failure and preserve any existing target. Runtime code does not
call this writer; the API returns a browser-downloadable JSON body.

- [ ] **Step 8: Run GREEN**

```bash
pytest -q tests/test_universe_compat.py
```

Expected: twelve pass.

- [ ] **Step 9: Commit**

```bash
git add src/universe_compat.py tests/fixtures/universe/tickers_core_legacy.json \
  tests/test_universe_compat.py
git commit -m "feat: add reviewed universe compatibility bridge"
```

---

## Task 4: Migrate Profile, Symbol, and Dormant Tier Read Surfaces

**Files:**
- Modify: `src/api/routes/profile.py`
- Modify: `src/api/routes/symbols.py`
- Modify: `src/symbol_catalog.py`
- Modify: `src/tools/data_access.py`
- Modify: `tests/test_profile_state.py`
- Modify: `tests/test_symbol_catalog.py`
- Modify: `tests/test_data_access.py`

- [ ] **Step 1: Add five RED profile-route nodes**

Add exactly:

```text
test_universe_route_uses_snapshot_and_keeps_archived_history_non_active
test_universe_route_returns_sanitized_503_for_unavailable_source
test_legacy_overview_enriches_but_never_qualifies_universe
test_import_universe_uses_annotations_without_opening_json
test_universe_export_route_is_deterministic_read_only_and_omits_settings
```

Use real temp profile/portfolio/SA schemas. The first test includes a ticker
active only via SA, one ticker with only archived list history, and one ticker
with archived list history plus an active holding. Assert archived-only is shown
only when requested and never appears in `sources_by_ticker`/export. The
unavailable fixture includes path-like error text and asserts it is absent.

- [ ] **Step 2: Add three RED symbol tests and strengthen the existing route node**

Add:

```text
test_local_seed_uses_accepted_snapshot_without_legacy_reference
test_local_seed_unavailable_keeps_sec_catalog_without_fake_active_seed
test_symbol_search_unavailable_returns_sanitized_503
```

Strengthen `test_route_flags_tracked` in place: an Alpha-Picks-only ticker is
tracked, archived-list-only is not, and `BRK.B` hidden does not affect `BRK B`.

- [ ] **Step 3: Run the route/symbol RED set**

```bash
pytest -q tests/test_profile_state.py tests/test_symbol_catalog.py
```

Expected: new nodes fail because routes still use JSON/all historical
memberships; existing nodes may fail only where their old authority is being
intentionally evolved.

- [ ] **Step 4: Migrate `/profile/universe` without deleting archive UX**

Build the snapshot with `profile_db=store.db_path`. On
`ActiveUniverseUnavailable`, raise `HTTPException(status_code=503,
detail=exc.as_dict())`.

Compute UI inventory as:

```python
active = set(snapshot.tickers)
archived_only = (set(store.archived_list_tickers()) - active) - store.get_hidden_tickers()
inventory = active | archived_only
visible = inventory if include_archived else active
```

Overview rows enrich only symbols already in `inventory`; never union overview
keys. A row is `archived = ticker not in active`. Add sorted `sources` per row and
top-level serialized `source_status`; preserve existing response fields and
batch summary behavior.

- [ ] **Step 5: Replace config tag seeding with stored annotation projection**

Remove `src.universe_config` imports. Keep `ImportBody.include_tiers` for API
compatibility, but document it as the persisted reviewed legacy-category
projection. When true, call `store.legacy_annotation_tag_groups()`. It must not
open the retired file. Theme overview import remains best-effort enrichment.

- [ ] **Step 6: Add the on-demand export route**

Add `GET /profile/universe/export`. It builds one accepted snapshot, loads
stored annotations, calls `build_compat_export()`, and returns the dict. It does
not write a server file or mutate DB state. Unavailable returns the same typed
503.

- [ ] **Step 7: Migrate symbol catalog and search tracking**

`symbol_catalog.search()` and `load_catalog()` gain an optional
`active_tickers` argument. Without it they build one structured snapshot; on
typed unavailable they log only the stable code and use no active seed while SEC
cache/network still supplies the broad catalog. Track `_cache_seed_key` so a
changed accepted set invalidates the merged catalog immediately instead of
waiting for the SEC TTL.

`symbols_search()` builds one accepted snapshot, passes the same
`snapshot.tickers` into `symbol_catalog.search` as `active_tickers`, and uses
that tuple for `tracked`. It returns typed 503 on unavailable rather than marking
every hit false. This avoids two cross-database reads per keystroke and keeps
autocomplete reference availability distinct from universe truth.

- [ ] **Step 8: Remove the dormant DAL tier reader and obsolete JSON tests**

Delete `DataAccessLayer.get_tickers_config()` and `get_tier_tickers()`, update
the module docstring, and remove only
`TestConfigAccess::test_get_tier_tickers`. Remove only the two reviewed
`universe_config` tests from `tests/test_profile_state.py`; their stronger
replacement nodes already exist.

- [ ] **Step 9: Run GREEN and account removals**

```bash
pytest -q tests/test_profile_state.py tests/test_symbol_catalog.py tests/test_data_access.py
pytest --collect-only -q \
  tests/test_profile_state.py tests/test_symbol_catalog.py tests/test_data_access.py
```

Record added/removed node IDs. At this point raw accounting must reflect Task 4
`+8/-3` and no other removal.

- [ ] **Step 10: Commit**

```bash
git add src/api/routes/profile.py src/api/routes/symbols.py \
  src/symbol_catalog.py src/tools/data_access.py \
  tests/test_profile_state.py tests/test_symbol_catalog.py tests/test_data_access.py
git commit -m "refactor: migrate universe read surfaces to SQLite"
```

---

## Task 5: Explicit Fail-Closed Landings for Six Compatibility Callers

**Files:**
- Modify: `src/service/data_scheduler.py`
- Modify: `src/collectors/finnhub_news.py`
- Modify: `src/collectors/polygon_news.py`
- Modify: `src/daily_update.py`
- Modify: `src/market_data_direct.py`
- Modify: `src/api/routes/market_data.py`
- Modify: `tests/test_data_scheduler.py`
- Modify: `tests/test_collector_adapters.py`
- Modify: `tests/test_daily_update_wrapper.py`
- Modify: `tests/test_market_data_direct.py`
- Modify: `tests/test_trading_day_coverage.py`

- [ ] **Step 1: Strengthen scheduler and shared-scope tests in place**

Evolve, without renaming:

```text
tests/test_data_scheduler.py::test_adapter_universe_unavailable_fails_loud
tests/test_collector_adapters.py::test_load_tickers_active_universe
```

The scheduler node raises a real `ActiveUniverseUnavailable`, asserts no
provider/writer/subprocess call, `run_source()` returns `failed` rather than
raising, and durable scheduler state stores only the stable code/safe source
names. The collector node loops over Finnhub and Polygon, proving typed
unavailable is not confused with valid empty.

- [ ] **Step 2: Add exactly six caller landing nodes**

```text
# tests/test_collector_adapters.py
test_finnhub_unavailable_scope_exits_before_provider_construction
test_polygon_unavailable_scope_exits_before_provider_construction

# tests/test_daily_update_wrapper.py
test_daily_update_unavailable_scope_exits_before_any_source

# tests/test_market_data_direct.py
test_backfill_unavailable_scope_raises_before_provider_construction

# tests/test_trading_day_coverage.py
test_route_unavailable_returns_sanitized_503
test_route_complete_empty_is_not_unavailable
```

Each zero-call assertion uses constructor/call counters, not only output text.
The CLI subprocess fixture must initialize full profile/portfolio/SA schemas and
pass both `ARKSCOPE_PROFILE_DB` and `ARKSCOPE_SA_DB`; the unavailable arm points
only the SA path to a missing file.

- [ ] **Step 3: Run RED**

```bash
pytest -q \
  tests/test_data_scheduler.py::test_adapter_universe_unavailable_fails_loud \
  tests/test_collector_adapters.py \
  tests/test_daily_update_wrapper.py \
  tests/test_market_data_direct.py::test_backfill_unavailable_scope_raises_before_provider_construction \
  tests/test_trading_day_coverage.py
```

Expected: new typed paths fail; no test should contact a provider.

- [ ] **Step 4: Preserve scheduler loop survival and safe durable failure**

No second catch layer is needed around `scheduler_loop()`: `run_source()` already
owns generic failure persistence. Ensure `_resolve_price_scope()` lets the typed
error reach that catch before any provider/subprocess work. Since
`ActiveUniverseUnavailable.__str__()` is sanitized, the existing truncated
durable error remains safe. Do not convert it to `[]`.

- [ ] **Step 5: Reorder collector scope resolution before provider construction**

Finnhub already resolves scope before `collect_news`; retain that. In Polygon
`run_incremental`, move `load_tickers()` before `load_env()` and
`PolygonNewsCollector(api_key, config)`. Both CLIs catch the typed subclass of
`RuntimeError`, log only its stable sanitized string, and exit `1`.

Valid complete empty retains the existing explicit empty-scope error; it is not
serialized as `active_universe_unavailable`.

- [ ] **Step 6: Add one pre-loop daily-update catch**

Wrap only active-universe resolution:

```python
try:
    tickers = resolve_active_universe()
except ActiveUniverseUnavailable as exc:
    logger.error("%s: %s", exc.code, ",".join(exc.unavailable_sources))
    sys.exit(1)
```

This occurs before `ensure_env_loaded`, source loop construction/execution, DB
telemetry, or provider work. Existing explicit `--tickers` bypasses it.

- [ ] **Step 7: Keep direct-market and coverage boundaries typed**

`backfill_prices_direct()` resolves scope before `_default_ibkr_src()` or
`_default_polygon_src()` and lets typed unavailable propagate. It retains its
existing valid-empty `RuntimeError`.

`market_data_trading_days()` catches only `ActiveUniverseUnavailable` and raises
HTTP 503 with `exc.as_dict()`. A complete empty list reaches the existing
coverage summarizer and returns a zero-universe result.

- [ ] **Step 8: Run GREEN**

```bash
pytest -q \
  tests/test_data_scheduler.py \
  tests/test_collector_adapters.py \
  tests/test_daily_update_wrapper.py \
  tests/test_market_data_direct.py \
  tests/test_trading_day_coverage.py
```

Expected: six added nodes pass, strengthened nodes retain names, no provider or
PG access occurs.

- [ ] **Step 9: Commit**

```bash
git add src/service/data_scheduler.py src/collectors/finnhub_news.py \
  src/collectors/polygon_news.py src/daily_update.py \
  src/market_data_direct.py src/api/routes/market_data.py \
  tests/test_data_scheduler.py tests/test_collector_adapters.py \
  tests/test_daily_update_wrapper.py tests/test_market_data_direct.py \
  tests/test_trading_day_coverage.py
git commit -m "fix: fail closed when universe sources are unavailable"
```

---

## Task 6: Read-Only Preview, Fingerprinted Apply, and Transition Audit

**Files:**
- Create: `src/audit/universe_retirement.py`
- Create: `tests/test_universe_retirement_audit.py`

- [ ] **Step 1: Write the six RED maintenance tests**

Create exactly:

```text
test_preview_is_read_only_and_emits_semantic_source_fingerprints
test_preview_proves_legacy_overview_subset_or_stops
test_apply_rejects_changed_json_or_database_fingerprint_before_write
test_apply_requires_explicit_approval_for_every_visible_json_only_symbol
test_apply_and_transition_export_are_exact_and_idempotent_after_fresh_preview
test_audit_never_opens_or_replaces_the_source_json_for_write
```

Use SQLite authorizer/trace hooks and monkeypatched `open`/`Path` operations to
prove preview/source-file read-only behavior. The changed-input test mutates one
source at a time after preview and asserts the profile DB digest is unchanged.
The overview test uses both represented and missing symbols. The idempotency
test runs apply, creates a fresh post-apply preview/fingerprint, applies that
fresh report, and compares rows/export bytes. Reusing a stale pre-apply report
must fail its fingerprint check rather than pretending to be idempotent.

- [ ] **Step 2: Run RED**

```bash
pytest -q tests/test_universe_retirement_audit.py
```

Expected: six failures because the audit module is absent.

- [ ] **Step 3: Implement canonical semantic fingerprints**

Define `InputFingerprints` over canonical JSON encodings of:

```text
legacy_json_sha256       raw source-file bytes
profile_sources_sha256   active list rows, open portfolio rows, hidden rows,
                         legacy membership, and annotations
sa_sources_sha256        current/non-stale picks plus current refresh meta
legacy_overview_sha256   sorted normalized overview ticker set
```

Fingerprint queries are read-only and sort every row/field. Do not use raw DB
file hashes: WAL/checkpoint layout is not semantic state. Missing required
schema is a typed failure, not an empty fingerprint.

- [ ] **Step 4: Implement preview as a pure read**

`build_preview_report` accepts explicit profile/SA/JSON paths and an
injected overview ticker set for tests. The CLI obtains production overview via
the existing local DAL `get_watchlist_overview()` path and fails closed if that
read is unavailable. It returns:

```python
{
    "fingerprints": fingerprint_map,
    "counts": {"json_active": 0, "snapshot_active": 0},
    "rows": [],
    "overview_missing": [],
    "requires_approval": [],
}
```

No raw DB path or exception is written to the report. `overview_missing` must be
empty before apply.

- [ ] **Step 5: Implement fingerprinted explicit apply**

`apply_reviewed_preview()` performs this order:

```text
1. recompute all four fingerprints;
2. exact-compare to the preview report;
3. reject missing overview coverage;
4. reject missing/extra explicit JSON-only approvals;
5. build ReviewedLegacyImport;
6. call the one ProfileStateStore transaction;
7. rebuild the accepted snapshot;
8. build transition export and assert exact parity;
9. atomically write only the caller-supplied transition-output path.
```

It never writes/replaces the source JSON. If any post-write parity check fails,
the caller's production procedure restores the pre-write online backup; the
unit test uses a copy and asserts the failure is loud.

- [ ] **Step 6: Add an explicit CLI without hidden defaults**

Support:

```bash
python -m src.audit.universe_retirement preview \
  --profile-db PATH --sa-db PATH --legacy-json PATH --report-out PATH

python -m src.audit.universe_retirement apply \
  --profile-db PATH --sa-db PATH --legacy-json PATH \
  --preview-report PATH --transition-out PATH \
  --approve-json-only SYMBOL

python -m src.audit.universe_retirement export \
  --profile-db PATH --sa-db PATH --output PATH
```

No implicit repository JSON path is allowed. `apply` requires the preview report
and exact approval list, even when empty (use `--approve-none`). Make
`--approve-json-only` repeatable and make `--approve-none` mutually exclusive
with it.

- [ ] **Step 7: Run GREEN and the no-PG smoke**

```bash
pytest -q tests/test_universe_retirement_audit.py tests/test_universe_compat.py
python -m src.smoke.pg_unreachable_e2e
```

Expected: twelve compatibility plus six audit nodes pass; no-PG reports
`ok:true` and `pg_attempts:[]`.

- [ ] **Step 8: Commit**

```bash
git add src/audit/universe_retirement.py tests/test_universe_retirement_audit.py
git commit -m "feat: add fingerprinted universe retirement audit"
```

---

## Task 7: Writer-Last Retirement and Tracked JSON Tombstone

**Files:**
- Modify: `src/sa_native_host.py`
- Modify: `data_sources/sa_alpha_picks_client.py`
- Modify: `src/tools/sa_tools.py`
- Delete: `src/universe_config.py`
- Delete: `config/tickers_core.json` in the implementation branch only
- Modify: `.gitignore`
- Modify: `tests/test_sa_tools.py`
- Modify: `tests/test_sa_reconciliation_native_host.py`
- Modify any existing native-host test that patches `_try_ticker_sync` in place

- [ ] **Step 1: Prove all readers are already migrated before touching writers**

Run:

```bash
rg -n 'src\.universe_config|active_universe_tickers|all_universe_tickers|config_tag_seeds|get_tier_tickers|get_tickers_config' \
  src data_sources --glob '*.py'
rg -n 'tickers_core\.json' src data_sources --glob '*.py'
```

Expected before writer removal: only explicit compatibility/audit references,
legacy writer code, and stale copy/comments in files this task will edit. Any
runtime reader outside `src/universe_compat.py`/`src/audit/universe_retirement.py`
is a stop condition.

- [ ] **Step 2: Replace three obsolete writer-policy tests with two RED absence tests**

Remove exactly the three `TestTickerSync` nodes and add:

```text
test_current_refresh_never_calls_or_writes_tickers_core
test_refresh_portfolio_signature_has_no_sync_tickers_escape_hatch
```

The first runs `_handle_refresh()` with a fake DAL, patches filesystem write/
replace calls to fail, and asserts capture plus reconciliation still occur. The
second uses `inspect.signature()` and source/static checks to prove both the
parameter and writer method are absent. Remove `_try_ticker_sync` monkeypatches
from existing tests without changing their node names.

- [ ] **Step 3: Run RED**

```bash
pytest -q tests/test_sa_tools.py tests/test_sa_reconciliation_native_host.py
```

Expected: new tests fail because both writer paths still exist.

- [ ] **Step 4: Remove native-host and fallback writer paths**

In `_handle_refresh`, remove only:

```python
if scope == "current" and picks:
    _try_ticker_sync(dal, picks)
```

Delete `_try_ticker_sync`. In `SAAlphaPicksClient`, change
`refresh_portfolio(self, sync_tickers: bool = False)` to
`refresh_portfolio(self)`, delete the fallback block and
`sync_tickers_to_collection()`, then remove unused `json`, `os`, `Path`, and
typing imports. Capture, refresh status, and reconciliation ordering stay byte-
semantically unchanged.

- [ ] **Step 5: Delete the loader and branch copy of the tracked file**

Delete `src/universe_config.py`. Add this anchored ignore rule:

```gitignore
# Retired runtime authority; explicit compatibility exports are local artifacts.
/config/tickers_core.json
```

Use `git rm config/tickers_core.json` only in the isolated implementation
worktree, whose file is the clean committed base. Before/after, prove main's
dirty path SHA and diff are unchanged.

- [ ] **Step 6: Run writer/static GREEN**

```bash
pytest -q tests/test_sa_tools.py tests/test_sa_reconciliation_native_host.py

rg -n 'sync_tickers_to_collection|_try_ticker_sync|sync_tickers' \
  src data_sources --glob '*.py'

rg -n 'tickers_core\.json' src data_sources --glob '*.py' \
  --glob '!src/universe_compat.py' \
  --glob '!src/audit/universe_retirement.py'
```

Expected: production writer symbols zero; runtime Python path references zero
(comments/docstrings included, to prevent future recoupling). Tests may refer to
the retired name only inside explicit negative/static assertions.

- [ ] **Step 7: Prove browser/web byte boundaries**

```bash
git diff --exit-code "$BEHAVIOR_AB_BASE" -- apps/arkscope-web extensions/sa_alpha_picks
```

Expected: empty.

- [ ] **Step 8: Commit**

```bash
git add src/sa_native_host.py data_sources/sa_alpha_picks_client.py \
  src/tools/sa_tools.py \
  src/universe_config.py config/tickers_core.json .gitignore \
  tests/test_sa_tools.py tests/test_sa_reconciliation_native_host.py
git commit -m "refactor: retire tickers core runtime authority"
```

Do not merge yet. Main's user edit must still be present and unstaged.

---

## Task 8: Full Verification, Copied-DB Gate, and Review Handoff

**Files:**
- Modify: this plan ledger
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Do not modify production DBs in the pre-review phase

- [ ] **Step 1: Run exact focused and full accounting**

Run the focused command with the four new files appended:

```bash
pytest -q \
  tests/test_active_universe_profile_store.py \
  tests/test_active_universe.py \
  tests/test_universe_compat.py \
  tests/test_universe_retirement_audit.py \
  tests/test_profile_state.py \
  tests/test_symbol_catalog.py \
  tests/test_data_access.py \
  tests/test_collector_adapters.py \
  tests/test_data_scheduler.py \
  tests/test_daily_update_wrapper.py \
  tests/test_market_data_direct.py \
  tests/test_trading_day_coverage.py \
  tests/test_sa_tools.py \
  tests/test_sa_reconciliation_native_host.py
```

Expected: `436 passed`. Then:

```bash
pytest --collect-only -q
```

Expected: `4562 tests collected`. Generate exact added/removed node sets against
`5d8748f`; require `+54/-6` with the six reviewed removals and no other loss.

- [ ] **Step 2: Run canonical virgin-archive A/B**

Create separate virgin archives for `5d8748f` and product tip. Supply the same
installed Python/Node dependencies to both without copying source or DB state.
Run full pytest sequentially. Require:

```text
existing failure/error identity diff: empty in both directions
30 failed / 74 skipped / 7 errors / 18 warnings: unchanged
collect: 4514 -> 4562 (raw +54/-6, semantic +48)
passed: 4403 -> 4451
```

If environment-only node-module/import behavior differs, document and prove it
with the same dependency mount on both sides; never hide a product failure as an
environment exception.

- [ ] **Step 3: Run frontend, static, and no-PG gates**

```bash
git diff --exit-code "$BEHAVIOR_AB_BASE" -- apps/arkscope-web extensions/sa_alpha_picks

cd apps/arkscope-web
npm test -- --run
npm run typecheck
npm run build

cd ../..
python -m src.smoke.pg_unreachable_e2e
git diff --check
```

Expected: frontend exact `60/572`, no-PG `ok:true / pg_attempts:[]`, and no
whitespace errors.

- [ ] **Step 4: Run structural ratchets**

Prove:

```text
all six resolve_active_universe callers remain explicit and tested
no runtime JSON loader/writer outside compatibility/audit
no automatic source enabled/off switch
no age predicate in Alpha Picks membership SQL
no alias resolver import in active_universe.py
no annotation -> membership FK
no runtime import from src.audit
no frontend/extension product diff
no raw DB/path/error fields in typed envelope
```

Use AST/import inspection where a plain string scan would confuse tests/docs.

- [ ] **Step 5: Run a read-only live preview against online-backup copies**

Do not close or mutate production yet. Create mode-0600 online backups of
`profile_state.db` and `sa_capture.db` in `/tmp`, initialize only the additive
profile schema on the profile copy, and run branch audit `preview` against:

```text
profile copy
SA copy
main checkout's live dirty config/tickers_core.json (read-only explicit path)
real local legacy overview
```

Expected classifications include:

```text
ATGE -> hidden / no membership
LC -> superseded_by_rename(HAPN) / do_not_import
BTSG -> overlap(sa_alpha_picks_current) / annotate_only
overview_missing -> []
```

Counts are observations, not constants. Record source fingerprints and confirm
main JSON SHA/diff remain exactly Task 0 values.

- [ ] **Step 6: Replay apply/export on the copies**

Apply with `--approve-none`, because current known JSON-only rows are hidden or
superseded. Require:

```text
legacy_config_seed active memberships: 0 unless fresh preview exposes a new
  visible generic JSON-only row (then STOP for user decision)
annotations: all reviewed active JSON entries
flatten(transition export): exact snapshot.tickers
hidden/reference/settings: absent
second apply/export: row and byte idempotent except caller-supplied generated_at
integrity_check: ok
foreign_key_check: empty
```

Modify one fingerprinted input on a third disposable copy and prove apply stops
before any write.

- [ ] **Step 7: Request independent implementation review**

Use `superpowers:requesting-code-review`. Reviewer focus:

1. source predicates and read-only/no-create behavior;
2. complete-empty versus unavailable distinction;
3. six fail-closed caller landings and zero provider calls;
4. exact BRK key handling and hidden veto order;
5. paired annotations/no Cartesian export;
6. LC/HAPN and dirty BTSG decisions;
7. archive UI compatibility without archive membership;
8. writer-last/static retirement proof;
9. `+54/-6` exact node ledger and canonical A/B;
10. copied-DB fingerprint/apply/parity evidence and main dirty-file preservation.

Do not merge or touch production state before independent GREEN and user merge
approval.

- [ ] **Step 8: Record review-ready evidence and commit docs only**

```bash
git add docs/superpowers/plans/2026-07-19-db-derived-universe-tickers-core-retirement.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: record DB universe implementation evidence"
```

---

## Post-Review Merge and Production Cutover

These steps execute only after independent implementation GREEN and explicit
user approval. Use `superpowers:finishing-a-development-branch`.

- [ ] **Close every writer before the destructive path transition**

Ask the user to close ArkScope and browsers/disable extension auto-sync. Prove
no sidecar, native host, extension browser, Vite/Electron, or scheduled writer
process remains. The IB Gateway may stay open; it does not write this JSON/DB.

- [ ] **Create retained mode-0600 backups before touching main's dirty file**

Create timestamped SQLite online backups for production `profile_state.db` and
`sa_capture.db`, plus an exact byte copy and patch of main's dirty JSON under
`data/backups/` (gitignored). Record SHA-256 and permissions. Re-run preview from
the reviewed product tip against those exact inputs and show the user the
classification/approval set.

- [ ] **Obtain explicit user approval for the cutover**

If a fresh visible generic JSON-only ticker appears, stop and ask whether to
import it. Hidden and `LC` keep their reviewed defaults; BTSG remains overlap.
Approval must explicitly cover preserving the dirty file in backup, removing
the working path, and proceeding with DB import/merge.

- [ ] **Make main mergeable without losing the user artifact**

Only after approval and verified backup, restore main's tracked JSON path to its
current committed `HEAD` bytes so the reviewed fast-forward deletion can apply.
Record that this is the sole authorized handling of the user edit. If merge does
not complete, immediately restore the dirty file from the retained backup.

- [ ] **Fast-forward merge and keep services stopped**

```bash
git merge --ff-only codex/db-derived-universe
```

Do not restart yet. Verify merged product tip and absence/ignore status of
`config/tickers_core.json`.

- [ ] **Initialize additive profile schema, recheck fingerprints, and apply**

Using merged code only, instantiate `ProfileStateStore` once to create the
additive tables. Run audit preview against production DBs and the retained JSON
backup. Require semantic fingerprints and decisions to equal the stopped-window
preview. Run `apply` with the user-approved exact list and write a retained
transition export under `data/backups/`, never at the retired config path.

- [ ] **Verify production truth before restart**

Require:

```text
PRAGMA integrity_check = ok on both DBs
PRAGMA foreign_key_check = empty
accepted snapshot available
source provenance contains manual/portfolio/Alpha Picks as observed
transition export exact-set parity
ATGE and BRK.B hidden; BRK B unaffected
LC absent; HAPN present when still sourced
BTSG present through Alpha Picks when still current
no runtime config/tickers_core.json path
```

Compare unaffected table multiset digests to backups. If any gate fails, keep
all services stopped, restore DB backups, and restore the JSON backup before
deciding how to repair; do not let old writer code reopen migrated state.

- [ ] **Restart merged desktop/browser components and run live smoke**

Restart ArkScope from merged `master`; browser extension needs no reload because
its bytes did not change. Verify `/profile/universe`, symbol search, Data Sources
scheduler scope, and one no-provider dry run. Do not force a paid/provider run.

- [ ] **Close documentation and remove the worktree**

Update spec to LIVE, plan ledger to COMPLETE, priority map with merge/cutover
hashes and retained backup paths, and memory terminology. Remove the
implementation worktree/branch only after production verification. Retain the
pre-retirement JSON/DB backups until a later explicit cleanup decision.

---

## Stop Conditions

Stop and return to review/design if any of the following occurs:

1. A fresh preview finds a visible generic JSON-only symbol beyond the reviewed
   hidden ATGE / superseded LC / overlap BTSG cases.
2. Any current `user_profile.yaml` overview ticker is absent from the accepted
   snapshot.
3. A runtime reader still opens/parses/writes `tickers_core.json` after Task 7.
4. A complete-empty source is indistinguishable from unavailable.
5. The accessor must create/migrate a DB to complete a read.
6. An unsupported portfolio class needs product membership rather than warning.
7. Exact export parity cannot be achieved without subset/superset relaxation.
8. A source fingerprint changes during a cutover window.
9. Main's dirty JSON diff/SHA changes before the explicit closeout checkpoint.
10. Any frontend/extension byte changes appear.
11. Test accounting differs from `+54/-6` without a reviewed node ledger.
12. Production migration would require v1/old writer code to reopen state after
    the tracked file is removed.

---

## Execution Ledger

Record evidence here during implementation; do not pre-fill passing claims:

```text
PLAN_REVIEW_CLEARANCE_COMMIT: c526783ff19b9de2de1502acf5e2b520e01af65a
BEHAVIOR_AB_BASE: 5d8748f
IMPLEMENTATION_BRANCH: codex/db-derived-universe
IMPLEMENTATION_WORKTREE: /tmp/arkscope-db-universe
WORKTREE_MATERIALIZATION: initial checkout stopped at the expected linked-worktree git-crypt smudge boundary; retry used --no-checkout, copied only .git/git-crypt/keys/default into linked Git metadata, then git read-tree -mu HEAD; final status clean
MAIN_DIRTY_JSON_SHA256: 00d197cf9cc04bf1cb83a877aea0a647ee25c958ba122607bd33e45be325964f (one unstaged BTSG line, main checkout only)
FOCUSED_BASELINE: 388 tests collected
FULL_COLLECT_BASELINE: 4514 tests collected
FRONTEND_BASELINE: 60 files / 572 tests; typecheck clean; production build clean except reviewed chunk-size warning
RED COMMITS:
GREEN COMMITS:
RAW NODE DELTA:
CANONICAL A/B:
NO-PG:
STATIC RATCHETS:
COPIED-DB PREVIEW:
COPIED-DB APPLY/PARITY:
INDEPENDENT REVIEW:
MERGE COMMIT:
PRODUCTION BACKUPS:
PRODUCTION CUTOVER:
PROCESS CLEANUP:
```
