# SA Feed Store Truth Design

> **Status**: USER DESIGN APPROVED - INDEPENDENT REVIEW PENDING
> **Date**: 2026-07-27
> **Grounding commit**: `5ba126736076238f4bee54e419c4bb24f2f6f017`
> **Scope**: `GET /sa/feed`, the `get_sa_feed` tool response, its no-create
> profile-history witness, and the mounted News presentation only

## 1. Purpose

`/sa/feed` currently treats a missing configured `sa_capture.db` as a healthy
empty store. `sa_capture_store.connect(..., read_only=True)` deliberately
creates an in-memory schema when the file is absent, so the feed query succeeds
with zero rows and returns:

```json
{"available": true, "total": 0, "empty_reason": "no_items_in_window"}
```

That response claims the source is available when no source database was read.
The News surface then renders both the zero-count statistics and the valid-empty
copy. This is the same truthfulness class already closed in extension run
outcomes and Coverage v2: unavailable evidence must not be projected as a
complete or empty observation.

This micro-slice makes feed availability a derived, ordered read-time fact. It
does not create, repair, migrate, or write either local database.

## 2. Grounded Current State

The following facts are current at the grounding commit:

1. `src/sa_capture_store.py::connect(read_only=True)` serves an in-memory
   initialized schema when the configured file does not exist. That global
   behavior supports other first-run SA readers and is not changed here.
2. `src/tools/sa_tools.py::get_sa_feed` checks for a backend and `_sa_db`, but
   does not check whether that path names a readable database before calling
   `_sa_feed_local`.
3. Its broad exception handler exposes `str(exc)` and resets `days` to `30`.
   SQLite diagnostics can contain local paths; the fallback response can
   therefore leak a diagnostic and misstate the normalized request.
4. `apps/arkscope-web/src/News.tsx::SAFeedBody` renders total and facet counts
   whenever `feed` exists, even when `available` is false. An unavailable
   response therefore displays `0` and degraded copy at the same time.
5. `requires_local_sa` remains reachable when the backend lacks `_sa_db`, and
   it has a dedicated Data Sources recovery action in the News surface.
6. `JobRunsLocalStore` is not a pure reader: construction creates parent
   directories and ensures the `job_runs` schema. It cannot be used to decide
   whether history exists without changing the evidence being inspected.
7. There is no current `job_runs` deletion, retention, pruning, or vacuum
   policy in the local job-runs owner.
8. A dated production read on 2026-07-27 found rows for five relevant names:
   `sa_market_news_refresh`, `sa_alpha_picks_refresh`,
   `extract_sa_comment_signals`, `sa_extension:manual_fetch`, and
   `sa_market_news_repair`. Counts and timestamps are observations, not
   acceptance constants.
9. `GET /sa/alpha-picks` follows a different missing-store path: it returns an
   empty portfolio with `is_partial=true` and a refresh hint, without a typed
   store-availability reason. That inconsistency is recorded as a separate SA
   contract follow-up and is not absorbed here.

## 3. Scope

### 3.1 In scope

- derive `/sa/feed` availability before the existing feed query;
- perform a no-create, read-only profile-history witness when the SA store path
  is absent;
- define a closed `empty_reason` union for every feed response shape;
- validate the minimum read schema needed by every supported feed request;
- sanitize store failures and preserve normalized request facts;
- distinguish not-yet-created, degraded, and valid-empty presentation;
- suppress counts, facets, and empty-result copy while unavailable;
- retain the existing Data Sources recovery target; and
- add bilingual mounted and backend regression coverage.

### 3.2 Out of scope

- changing the global missing-file behavior of `sa_capture_store.connect`;
- creating or repairing `sa_capture.db` or `profile_state.db`;
- schema migration, schema-version enforcement, integrity repair, or FTS rebuild;
- SA extension, native-host, auto-sync, recovery-window, or popup changes;
- changing `/sa/alpha-picks` behavior;
- changing market NEWS `content_availability`;
- adding a second history database or persistent initialization marker;
- PostgreSQL, Gateway, provider, browser, or network calls; and
- CSS or layout changes.

## 4. Locked Decisions

### LD 1 - Availability is derived in a fixed precedence

The feed evaluates states in the order in section 5. A later healthy condition
cannot overwrite an earlier unavailable condition.

### LD 2 - Missing is never available

`store_not_created`, `store_missing`, `store_unreadable`,
`store_schema_incompatible`, and `store_query_failed` all return
`available=false`. Neutral versus degraded is a presentation distinction, not
a different meaning for the availability boolean.

### LD 3 - Only a real successful query can be empty

`available=true` plus `no_items_in_window` is legal only after opening the
configured on-disk store read-only, validating its required read schema, and
successfully running the requested query to a zero-row result.

### LD 4 - History reports evidence, not an invented past

The history witness distinguishes:

- `none`: the history authority is absent or readable with no relevant rows;
- `present`: at least one relevant activity row exists, regardless of status;
- `unknown`: the history authority exists but cannot be opened or queried.

When the SA store is absent, `none` maps to `store_not_created`; both `present`
and `unknown` map to `store_missing`. User-facing copy may say prior SA activity
was observed. It must not claim that a prior run successfully created the store.

### LD 5 - The history read is no-create

The witness opens an existing `profile_state.db` with SQLite `mode=ro`. It does
not instantiate `JobRunsLocalStore`, create a directory or file, ensure a
schema, enable WAL, or write any marker. An absent profile DB or absent
`job_runs` table returns `none`; an unreadable or unqueryable existing profile
DB returns `unknown`.

### LD 6 - Relevant activity has one explicit owner

One immutable `SA_STORE_ACTIVITY_JOB_NAMES` owner contains exactly the current
seven names:

```text
sa_alpha_picks_refresh
sa_extension:manual_fetch
sa_market_news_refresh
sa_market_news_retry_recorded
sa_market_news_incident_recovery
sa_market_news_repair
extract_sa_comment_signals
```

Its completeness test derives and compares:

- every `job_name` in `src.sa.extension_run_protocol.OPERATION_CONTRACTS`;
- every current service `JobDefinition` with `feature_flag == "sa_enabled"`;
- `src.sa.market_news_recovery.REPAIR_JOB_NAME`.

The test may inspect the service registry even if that registry remains private;
runtime feed code must not import the service job runner merely to discover
names. Adding or renaming an SA store activity in any authority without
updating this owner is a failing change.

### LD 7 - Unpruned history is a protected dependency

The missing-versus-not-created inference depends on relevant `job_runs` history
remaining unpruned. Any future job-runs retention, compaction, archive, or
deletion policy must explicitly revisit this classifier in the same change.
The implementation must not add a time cutoff to the witness.

### LD 8 - The double-loss case is an epistemic boundary

If both `sa_capture.db` and the profile history authority are absent, the system
has no surviving evidence that distinguishes a fresh profile from loss of both
files. It returns `store_not_created`. This is not a claim that historical
capture never occurred; it is the only statement supported by the remaining
evidence.

### LD 9 - Schema compatibility is capability-based

Compatibility requires the tables and columns in section 6. Extra tables,
columns, indexes, triggers, and a newer additive schema remain compatible. An
exact `PRAGMA user_version` match is not required.

### LD 10 - Diagnostics are stable and safe

The API/tool response exposes stable reason codes, never a raw SQLite exception,
configured path, SQL statement, or profile-history diagnostic. Backend logs may
record the exception through the existing logger. All unavailable responses
preserve normalized `days` and `query` rather than resetting them.

### LD 11 - The existing DTO field evolves in place

`empty_reason` remains the field name for compatibility, but becomes a closed
union. Introducing a parallel `availability_reason` during this micro-slice
would create two authorities for the same state.

### LD 12 - Alpha Picks remains separate and visible

The Alpha Picks missing-store inconsistency is a separately owned SA
availability-alignment follow-up in `PROJECT_PRIORITY_MAP.md`. It is neither
silently accepted nor fixed by changing the global store connector in this
slice.

## 5. Ordered Response Contract

Feature-disabled behavior remains outside the feed DTO: it returns the existing
HTTP `503`. Otherwise the first matching row wins:

| Order | Observed condition | `available` | `empty_reason` | Presentation |
|---:|---|---:|---|---|
| 1 | DAL backend absent or lacks the DB interface | false | `backend_unavailable` | degraded |
| 2 | backend has no `_sa_db` route | false | `requires_local_sa` | degraded + Data Sources action |
| 3 | SA path absent; history is `none` | false | `store_not_created` | neutral + Data Sources action |
| 4 | SA path absent; history is `present` or `unknown` | false | `store_missing` | degraded + Data Sources action |
| 5 | configured path exists but is not a readable regular DB target, including a directory or broken symlink | false | `store_unreadable` | degraded + Data Sources action |
| 6 | DB opens, but required read tables or columns are absent | false | `store_schema_incompatible` | degraded + Data Sources action |
| 7 | schema is compatible, but the requested feed query fails | false | `store_query_failed` | degraded + Data Sources action |
| 8 | query succeeds with zero rows | true | `no_items_in_window` | valid empty result |
| 9 | query succeeds with one or more rows | true | `null` | normal feed |

`backend_unavailable` and `requires_local_sa` keep their existing precedence
before any filesystem or history inspection. Any path race that makes open,
schema inspection, or the query fail must end in a false/degraded state; an
exception path may never fall through to the valid-empty row.

The closed frontend/backend reason union is therefore:

```text
backend_unavailable
requires_local_sa
store_not_created
store_missing
store_unreadable
store_schema_incompatible
store_query_failed
no_items_in_window
null
```

The retired generic feed reason is `error`.

## 6. Minimum Feed Read Schema

The compatibility probe checks only what the current feed reader needs:

| Table | Required columns |
|---|---|
| `sa_articles` | `id`, `article_id`, `title`, `ticker`, `published_date`, `url`, `body_markdown`, `comments_count` |
| `sa_market_news` | `id`, `news_id`, `title`, `published_at`, `url`, `summary`, `body_markdown`, `comments_count` |
| `sa_market_news_tickers` | `news_row_id`, `ticker` |
| `sa_articles_fts` | `title`, `body_markdown` |
| `sa_market_news_fts` | `title`, `summary` |

Both FTS tables are required even for a request without `q`, because the
advertised endpoint includes search and must not alternate between apparently
available and structurally unavailable based only on the current filter.

The probe and feed query use one read-only connection. Failure while opening or
reading SQLite metadata is `store_unreadable`; failure after the schema has
validated and query construction begins is `store_query_failed`. Full-database
`quick_check` on every request, writer-trigger validation, and FTS-content
rebuild are deliberately outside this read-path contract.

## 7. Component Boundaries

### 7.1 Job-runs owner

`src/service/job_runs_store.py` receives a small module-level no-create read
primitive. It accepts a profile path and the immutable job-name set and returns
only `none`, `present`, or `unknown`. It never returns rows or raw diagnostics to
the feed layer.

### 7.2 Feed owner

`src/tools/sa_tools.py` owns the ordered classifier, required-schema map, and
safe response projection. The existing query semantics, filters, ordering,
facets, snippets, and pagination remain unchanged after a store reaches the
queryable state.

The implementation may split the current `_sa_feed_local` into an
already-open-connection helper so classification and query share one connection.
It must not change `src/sa_capture_store.py` to make the micro-slice work.

### 7.3 API and agent consumers

`GET /sa/feed`, the registry tool, and both agent bridges continue to consume
the same result object. No route remapping or tool registration count changes.
Stable reason codes are the only diagnostic contract.

### 7.4 News surface

`SAFeedResponse.empty_reason` becomes the exact TypeScript union. Presentation
obeys these rules:

- statistics and facets render only when `feed.available` is true;
- list rows and Load More remain driven by successful feed results;
- valid-empty copy renders only for `available=true` and total `0`;
- `store_not_created` uses neutral first-run copy;
- every other unavailable reason uses existing path-specific or generic
  degraded copy; and
- all path/store unavailable states expose the existing Data Sources action.

No raw reason code or diagnostic is shown to users. No CSS change is expected.

## 8. Copy And Resource Accounting

One new Explore leaf is required per locale:

```text
explore.news.seekingAlphaNotCreated
```

Its meaning is: the local Seeking Alpha store has not been initialized; run the
browser extension once, without naming Chrome or Firefox as the required owner.
The existing `seekingAlphaPathUnavailable`, `seekingAlphaUnavailable`,
`emptySeekingAlpha`, and Data Sources action copy remain.

At the grounded base, the per-locale ledger is:

```text
explore: 379 -> 380
settings: 704 -> 704
total: 1782 -> 1783
```

The existing inventory-count test evolves in place. The visible-literal scanner
must remain `36 / 20 / 0 / 20` with unchanged allowlist and debt manifest.

## 9. RED-First Verification Contract

### 9.1 Backend behavior

Named tests must independently prove:

1. missing SA path plus no profile DB returns `store_not_created` and creates
   neither database nor parent directory;
2. missing SA path plus readable profile DB with no relevant row returns
   `store_not_created` without modifying profile size, mtime, or schema;
3. each of the seven relevant job names independently changes missing-path
   classification to `store_missing`, regardless of run status;
4. unreadable or malformed existing profile history maps missing SA storage to
   `store_missing`, not `store_not_created`;
5. replacing the no-create reader with `JobRunsLocalStore` construction makes a
   file-creation assertion fail;
6. the activity-name owner exactly covers the extension protocol, SA-enabled
   service definitions, and repair owner;
7. `requires_local_sa` remains before filesystem/history checks;
8. a directory, broken symlink, and malformed SQLite file are
   `store_unreadable`;
9. each required table family and at least one required column omission is
   `store_schema_incompatible`;
10. extra tables and columns remain compatible;
11. a valid empty store is the only path to
    `available=true/no_items_in_window`;
12. a compatible populated store preserves existing feed results, facets,
    search, pagination, and snippets;
13. an injected post-validation query failure is `store_query_failed`, keeps
    normalized `days/query`, and exposes no raw path or SQLite prose; and
14. feature-disabled behavior remains HTTP `503` while unavailable store states
    remain HTTP `200` typed responses.

### 9.2 Mounted frontend behavior

Both locales must prove:

- `store_not_created` renders neutral initialization copy and the Data Sources
  action;
- `requires_local_sa` retains its path-specific copy and action;
- `store_missing`, `store_unreadable`, `store_schema_incompatible`, and
  `store_query_failed` render degraded copy and the action;
- every `available=false` fixture renders no total, no facets, no valid-empty
  copy, no rows, and no Load More control;
- valid empty still renders the existing empty-result copy without a recovery
  action; and
- valid populated behavior is unchanged.

Removing the `feed.available` condition from the statistics block must make the
mounted unavailable-state test fail. Adding explanatory text while leaving the
zero/facet block visible does not satisfy the test.

### 9.3 Boundaries

Static and byte gates prove:

- `src/sa_capture_store.py` is byte-identical;
- `extensions/sa_alpha_picks/**` and native-host code are byte-identical;
- no DB schema, migration, PG, provider, Gateway, or write path changed;
- no Alpha Picks product code changed;
- no CSS changed;
- tool registration names and counts are unchanged; and
- scanner/allowlist/debt-manifest files are byte-identical.

## 10. Alpha Picks Follow-Up

The current Alpha Picks reader uses the global in-memory missing-store behavior
and returns `is_partial=true` plus a refresh hint rather than a typed
availability reason. This is a separate contract issue because Alpha Picks has
different freshness, current/closed, and detail semantics.

This spec records the discrepancy and the priority map owns a future bounded
`SA availability alignment` decision. It does not enter the Engineering Issue
Register because it is a product-contract problem, and it does not authorize a
global connector change during this feed slice.

## 11. Runtime And Release Evidence

Implementation review must include an isolated no-create matrix using temporary
SA/profile paths. It must hash or record nonexistence before and after each
case. No production file is renamed, removed, chmodded, corrupted, or replaced
to manufacture a failure.

After merge, production verification is read-only:

- the real readable store still returns the expected valid feed shape;
- production `sa_capture.db` and `profile_state.db` size, mtime, integrity, and
  relevant row counts remain unchanged;
- no extension, provider, scheduler, repair, or browser action is triggered;
- the two-locale News surface displays its normal populated state; and
- the priority map records this micro-slice complete while keeping Alpha Picks
  alignment open.

## 12. Stop Conditions

Stop and return to design review if implementation discovers any of the
following:

- any current activity authority outside the three sources in LD 6;
- relevant job history is pruned, archived, or not durable as grounded;
- a valid feed needs a table or column absent from section 6;
- schema compatibility requires a write, migration, FTS rebuild, or exact
  version pin;
- a no-create history read cannot be implemented without materializing profile
  state;
- fixing the feed requires changing global `sa_capture_store.connect` behavior;
- Alpha Picks, extension, native-host, scheduler, recovery, or provider behavior
  must change;
- raw diagnostics or paths are required by a public consumer;
- frontend truthfulness requires CSS; or
- resource/scanner accounting differs from section 8 before product edits.

## 13. Completion Contract

This micro-slice is complete only when:

1. a missing store can never return `available=true`;
2. first-run absence, missing-after-evidence, unreadable, incompatible, query
   failure, and valid empty are mechanically distinct;
3. the history witness is no-create and fail-closed;
4. unavailable responses expose neither raw diagnostics nor fabricated request
   values;
5. the News surface never displays zero/facet claims beside unavailable copy;
6. valid empty and populated feed behavior remain unchanged;
7. every job-name, schema, response, i18n, and boundary gate is green;
8. production databases remain byte-behaviorally untouched by the release
   verification; and
9. Alpha Picks availability alignment remains explicitly open under its own
   future contract.
