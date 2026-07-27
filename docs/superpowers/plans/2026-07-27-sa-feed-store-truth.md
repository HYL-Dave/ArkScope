# SA Feed Store Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: PLAN REVIEW GREEN - IMPLEMENTATION CLEARED**

**Goal:** Make `GET /sa/feed` distinguish first-run absence, missing storage,
unreadable or incompatible storage, query failure, valid empty results, and
populated results without creating either local database or exposing raw
diagnostics.

**Architecture:** A no-create reader in the existing job-runs owner reports
only `none | present | unknown`. The SA feed owner combines that evidence with
an ordered filesystem, SQLite-open, schema-capability, and query classifier.
The on-disk feed probe and query share one direct SQLite `mode=ro` connection,
so the global first-run behavior of `sa_capture_store.connect` remains
untouched. The News surface consumes a closed reason union and renders no
counts, facets, rows, valid-empty copy, or pagination while unavailable.

**Tech Stack:** Python 3.10, SQLite URI read-only mode, FastAPI, pytest, React
18, TypeScript 5.9, i18next, Vitest 4/jsdom, the existing TypeScript-AST
visible-literal scanner, and Chromium for release evidence.

---

## 1. Authority And Review State

1. Product authority:
   `docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md`.
2. Sequence and follow-up authority:
   `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Small-issue authority:
   `docs/design/ENGINEERING_ISSUE_REGISTER.md`. The Alpha Picks discrepancy is
   a product-contract follow-up in the priority map, not an EIR entry.
4. Behavioral and accounting base:
   `a7806dd95c9d393daa0a4097171fe255921834ab`. Commits after product base
   `5ba126736076238f4bee54e419c4bb24f2f6f017` are docs-only.

If implementation must contradict any authority above, stop and amend the
authority before editing product code.

### 1.1 Independent spec-review resolution

Independent review returned GREEN with zero required changes. Two advisories
were checked against the code and accepted because they close real ambiguity:

1. Both FTS tables are required for every request, including requests without
   `q`. Otherwise the same damaged store could report `available=true` without
   a query and `store_schema_incompatible` with one. Availability is a store
   capability, not a per-filter result.
2. Post-merge verification includes a negative smoke against a unique absent
   temporary `ARKSCOPE_SA_DB` path while retaining the real read-only profile
   history authority. It must not rename, chmod, corrupt, replace, or write the
   production SA store. Both production DBs and the temporary path are checked
   before and after.

The second advisory is a release gate, not permission to manufacture a
production fault.

### 1.2 Independent plan-review resolution

Independent review reproduced all five baselines and returned substantive
GREEN. Two non-design advisories were checked against the code and accepted:

1. The existing route node calls `sa_feed(...)` directly. It proves the
   handler's feature-disabled `503`, but cannot prove that every typed
   unavailable payload remains HTTP `200` through FastAPI transport. One real
   HTTP node is therefore added and loops over every unavailable reason.
2. A `Set<SAFeedEmptyReason>.has(...)` would not make a future union member a
   compile error. The frontend must use one exhaustive `switch` whose default
   passes its value to a `never` helper, following the existing Coverage V2
   pattern. The existing recovery-target node gains the source-level guard;
   the frontend node count does not change.

The HTTP node changes backend accounting by `+1/-0`; all other reviewed
counts remain unchanged.

## 2. Grounded Baseline

All values below were reproduced on clean `a7806dd9` before product edits.
Absolute full-suite pass/fail totals are environment observations; normalized
collection node IDs are the accounting authority.

| Gate | Baseline |
|---|---|
| Backend full collection | `4691` nodes; SHA-256 `ed4b7da05db79204dd847d33d0d9f9bb8f6bbef6c756af48cf218a13f3525acf` |
| Backend focused collection | `77` nodes; SHA-256 `34a30e6d54c108fadfe4e0425d863c9a6fbfaf1b7f10a93ee82f53d380d3eb2a` |
| Backend focused run | `77 passed` |
| Frontend full collection | `96` files / `1072` nodes; SHA-256 `71e4785f75ace3d65e40a479ce823897ffbcae0bd27ff1855aef1504905e429e` |
| Frontend focused collection | `2` files / `25` nodes; SHA-256 `086cce183d540193a966a61148f6e7a9e6c2177a8ebecd49bb71c2c1cfc6d892` |
| Frontend focused run | `25 passed` (`News` 11, resources 14) |
| Per-locale resources | Explore `379`, Settings `704`, total `1782`; Explore `news` subtree `43` |
| Visible-literal scanner, twice | `36 / 20 / 0 / 20`, scope `src/**` |
| Tool surfaces | central `53`, OpenAI `54`, Anthropic `54` |
| no-PG runtime smoke | `23/23`, `ok=true`, `pg_attempts=[]` |
| `src/sa_capture_store.py` blob | `f4eacd5a5746ec96e5f945ecff33cb4c0df1448c` |

### 2.1 Canonical collection recipes

Backend full:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  | sed -n '/^\(tests\|scripts\/testing\)\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/sa-feed-truth-be-full.nodes \
  | sha256sum
wc -l /tmp/sa-feed-truth-be-full.nodes
```

Backend focused:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest --collect-only -q \
  tests/test_job_runs.py tests/test_sa_feed.py \
  | sed -n '/^tests\/.*::/p' \
  | LC_ALL=C sort \
  | tee /tmp/sa-feed-truth-be-focused.nodes \
  | sha256sum
wc -l /tmp/sa-feed-truth-be-focused.nodes
```

Frontend full, from `apps/arkscope-web`:

```bash
npx vitest list --json \
  | jq -r '.[] | [.file,.name] | @tsv' \
  | sed "s#$(pwd)/##" \
  | LC_ALL=C sort \
  | tee /tmp/sa-feed-truth-fe-full.nodes \
  | sha256sum
wc -l /tmp/sa-feed-truth-fe-full.nodes
cut -f1 /tmp/sa-feed-truth-fe-full.nodes | sort -u | wc -l
```

Frontend focused is derived from that full list:

```bash
awk -F '\t' \
  '$1=="src/News.test.tsx" || $1=="src/i18n/resources.test.ts"' \
  /tmp/sa-feed-truth-fe-full.nodes \
  | LC_ALL=C sort \
  | tee /tmp/sa-feed-truth-fe-focused.nodes \
  | sha256sum
wc -l /tmp/sa-feed-truth-fe-focused.nodes
```

Vitest 4 treats the token after `--json` as an optional output filename. Do
not append test paths after `--json`; doing so can overwrite the named source
file. Generate the full JSON stream first and filter the normalized TSV, as
above.

### 2.2 Scanner hashes

The following files remain byte-identical:

```text
migrated-scopes.json              02e335bebcadfba523d502a7af86a5c184d1ac024230cfec9199dd19b4416c13
visible-literal-allowlist.json    3b397a21ab7f8a1cd37819ae55d892e26f1946dc3c791aebf28d2eba2577c212
visible-literal-debt.json         d6eaaf3e70bd344e8c3bd2d89dcc9818081e2735db9191d31dd5757246868cec
visible-literal-scanner.mjs       c22c7e784c6f1c25587a980ca7b441658f58632a004d117985e765cad70fb8da
```

## 3. Exact Accounting

### 3.1 Backend node ledger

No existing backend node ID is removed or renamed. Three current nodes evolve
in place:

```text
tests/test_sa_feed.py::test_feed_empty_window
tests/test_sa_feed.py::test_feed_pg_mode_requires_local
tests/test_sa_feed.py::test_route_handler_happy_and_disabled
```

`tests/test_job_runs.py` adds exactly six nodes:

```text
test_read_job_activity_if_exists_missing_profile_is_none_and_no_create
test_read_job_activity_if_exists_missing_table_is_none_and_no_mutation
test_read_job_activity_if_exists_distinguishes_relevant_and_unrelated_rows
test_read_job_activity_if_exists_unreadable_or_malformed_is_unknown
test_sa_store_activity_job_names_cover_all_current_authorities
test_sa_store_history_contract_has_no_pruning_or_time_cutoff
```

`tests/test_sa_feed.py` adds exactly 24 nodes:

```text
test_missing_store_without_profile_is_not_created_and_creates_nothing
test_missing_store_with_empty_profile_is_not_created_without_mutation
test_missing_store_history_sa_alpha_picks_refresh_is_missing
test_missing_store_history_sa_extension_manual_fetch_is_missing
test_missing_store_history_sa_market_news_refresh_is_missing
test_missing_store_history_sa_market_news_retry_recorded_is_missing
test_missing_store_history_sa_market_news_incident_recovery_is_missing
test_missing_store_history_sa_market_news_repair_is_missing
test_missing_store_history_extract_sa_comment_signals_is_missing
test_missing_store_with_unreadable_history_fails_closed_as_missing
test_backend_unavailable_precedes_store_and_history_checks
test_directory_sa_store_is_unreadable
test_broken_symlink_sa_store_is_unreadable
test_malformed_sa_store_is_unreadable
test_sa_store_open_failure_is_unreadable_and_sanitized
test_missing_required_feed_table_is_schema_incompatible[sa_articles]
test_missing_required_feed_table_is_schema_incompatible[sa_market_news]
test_missing_required_feed_table_is_schema_incompatible[sa_market_news_tickers]
test_missing_required_feed_table_is_schema_incompatible[sa_articles_fts]
test_missing_required_feed_table_is_schema_incompatible[sa_market_news_fts]
test_missing_required_feed_column_is_schema_incompatible
test_extra_feed_schema_remains_compatible
test_post_validation_query_failure_is_typed_sanitized_and_preserves_request
test_route_returns_typed_200_for_every_unavailable_store_reason
```

The seven activity names above are seven separate test functions. They must
not be collapsed into one parametrized node. Each function loops over
`running`, `succeeded`, and `failed` fixtures for its one exact job name, so
both identity and status-independence remain mutation-sensitive.

Final backend accounting:

```text
tests/test_job_runs.py  63 -> 69  (+6/-0)
tests/test_sa_feed.py   14 -> 38  (+24/-0)
focused                77 -> 107 (+30/-0)
full                 4691 -> 4721 (+30/-0)
```

### 3.2 Frontend node ledger

This existing node evolves in place and keeps its ID:

```text
News localization > offers only the reviewed News and Data Sources recovery targets
```

`News.test.tsx` adds exactly two nodes:

```text
News localization > renders typed SA store availability copy in both locales
News localization > hides all feed claims and controls for every unavailable SA reason
```

The resource inventory nodes evolve in place:

```text
bundled i18n resources > contains the exact Explore subtree inventory in both locales
bundled i18n resources > contains the reviewed remaining-surface namespace inventory in both locales
```

Final frontend accounting:

```text
News.test.tsx             11 -> 13 (+2/-0)
resources.test.ts         14 -> 14 (+0/-0, two nodes evolve in place)
focused                   25 -> 27 (+2/-0)
full                    1072 -> 1074 (+2/-0; still 96 files)
```

### 3.3 Resource and non-node ledger

Exactly one leaf is added to each locale:

```text
explore.news.seekingAlphaNotCreated
```

```text
Explore news subtree 43 -> 44
Explore total       379 -> 380
Settings total      704 -> 704
all namespaces     1782 -> 1783
```

There is no key removal, move, plural pair, CSS change, tool-registration
change, route change, schema change, migration, or no-PG inventory change.

## 4. File Ownership

### 4.1 Product files allowed to change

```text
src/service/job_runs_store.py
src/tools/sa_tools.py
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/News.tsx
apps/arkscope-web/src/i18n/resources/en/explore.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts
```

### 4.2 Test files allowed to change

```text
tests/test_job_runs.py
tests/test_sa_feed.py
apps/arkscope-web/src/News.test.tsx
apps/arkscope-web/src/i18n/resources.test.ts
```

### 4.3 Evidence and status files allowed to change

```text
docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md
docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md
docs/superpowers/specs/2026-07-27-sa-feed-store-truth-design.md
docs/design/PROJECT_PRIORITY_MAP.md
```

The spec changes only for review/implementation status or a discovered
authority amendment. It is not rewritten to match an implementation shortcut.

### 4.4 Protected byte-identical families

```text
src/sa_capture_store.py
src/api/routes/seeking_alpha.py
src/sa/extension_run_protocol.py
src/sa/market_news_recovery.py
src/service/jobs.py
src/sa_native_host.py
src/sa_native_manifest.py
extensions/sa_alpha_picks/**
apps/arkscope-web/src/styles.css
apps/arkscope-web/src/primitives.css
apps/arkscope-web/src/shell.css
apps/arkscope-web/src/tokens.css
apps/arkscope-web/scripts/i18n/**
sql/**
```

The authority files in this list are read by tests, not modified by product
code. The implementation must not import `src.service.jobs` at runtime to
discover activity names.

## 5. Implementation Shape

### 5.1 No-create history primitive

Add a module-level primitive to `src/service/job_runs_store.py`:

```python
JobActivityEvidence = Literal["none", "present", "unknown"]


def read_job_activity_if_exists(
    db_path: str | Path,
    job_names: Iterable[str],
) -> JobActivityEvidence:
    path = Path(db_path).expanduser()
    if not os.path.lexists(path):
        return "none"
    if not path.is_file():
        return "unknown"

    names = tuple(sorted({str(name) for name in job_names if str(name)}))
    if not names:
        return "none"

    conn = None
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        table = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='job_runs'"
        ).fetchone()
        if table is None:
            return "none"
        placeholders = ",".join("?" for _ in names)
        row = conn.execute(
            f"SELECT 1 FROM job_runs WHERE job_name IN ({placeholders}) LIMIT 1",
            names,
        ).fetchone()
        return "present" if row is not None else "none"
    except sqlite3.Error:
        return "unknown"
    finally:
        if conn is not None:
            conn.close()
```

The final implementation may improve naming or logging, but these properties
are fixed:

- direct SQLite `mode=ro`;
- no `JobRunsLocalStore` construction;
- no parent creation, schema ensure, WAL, write, row return, or raw error;
- table absence is `none`;
- existing but unqueryable history is `unknown`;
- the SQL filters only exact `job_name`; no status or timestamp predicate.

### 5.2 Activity owner and completeness

`src/tools/sa_tools.py` owns exactly:

```python
SA_STORE_ACTIVITY_JOB_NAMES = frozenset({
    "sa_alpha_picks_refresh",
    "sa_extension:manual_fetch",
    "sa_market_news_refresh",
    "sa_market_news_retry_recorded",
    "sa_market_news_incident_recovery",
    "sa_market_news_repair",
    "extract_sa_comment_signals",
})
```

The test derives the comparison set from:

```python
extension = {
    contract["job_name"]
    for contract in OPERATION_CONTRACTS.values()
}
service = {
    definition.name
    for definition in jobs_module._JOB_DEFINITIONS.values()
    if definition.feature_flag == "sa_enabled"
}
repair = {REPAIR_JOB_NAME}
assert SA_STORE_ACTIVITY_JOB_NAMES == extension | service | repair
assert len(SA_STORE_ACTIVITY_JOB_NAMES) == 7
```

Production `sa_tools.py` receives the immutable set as code. It does not import
the private service registry or derive names dynamically.

### 5.3 Closed response reasons

The backend and TypeScript union are exactly:

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

The generic `error` reason is removed. `_empty_feed` accepts normalized
`days`, normalized `query`, and one closed reason. It never receives
`str(exc)`. Existing fixed, code-owned backend and local-route diagnostics may
remain, but store failures expose only reason codes.

### 5.4 Direct read-only store open and one-connection boundary

Do not call the global `sa_capture_store.connect(read_only=True)` after a
filesystem precheck. A path can disappear between the precheck and that helper;
its intentional missing-file fallback would create an in-memory schema and
could project the race as valid empty.

Instead, `sa_tools.py` opens the known path directly:

```python
def _open_sa_feed_read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        f"{path.expanduser().resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=10.0,
    )
    conn.row_factory = sqlite3.Row
    return conn
```

The ordered owner uses `os.path.lexists` before `Path.is_file()` so a broken
symlink is not confused with fresh absence. A symlink to a readable regular
database may remain valid; a directory or broken target is unreadable.

The connection lifecycle is:

1. open via direct `mode=ro`; open/metadata exceptions are
   `store_unreadable`;
2. inspect required capabilities; missing table/column is
   `store_schema_incompatible`;
3. pass the same connection to `_sa_feed_local_conn`;
4. query exceptions are `store_query_failed`;
5. close in one `finally` block.

### 5.5 Required schema map

Use one immutable map in `sa_tools.py`:

```python
_SA_FEED_REQUIRED_SCHEMA = {
    "sa_articles": frozenset({
        "id", "article_id", "title", "ticker", "published_date", "url",
        "body_markdown", "comments_count",
    }),
    "sa_market_news": frozenset({
        "id", "news_id", "title", "published_at", "url", "summary",
        "body_markdown", "comments_count",
    }),
    "sa_market_news_tickers": frozenset({"news_row_id", "ticker"}),
    "sa_articles_fts": frozenset({"title", "body_markdown"}),
    "sa_market_news_fts": frozenset({"title", "summary"}),
}
```

Probe all five tables for every request. Use `sqlite_master` and
`PRAGMA table_info` against these fixed identifiers. Extra tables, columns,
indexes, triggers, and user-version differences are accepted.

### 5.6 Frontend rendering

`api.ts` introduces a closed `SAFeedEmptyReason` type and applies it to
`SAFeedResponse.empty_reason`.

`News.tsx` derives availability presentation through one exhaustive classifier.
It must cover all nine members of `SAFeedEmptyReason` (including `null`) and
route its default branch through a `never` helper:

```typescript
function unreachableSAFeedReason(value: never): void {
  void value;
}

function classifySAFeedReason(reason: SAFeedEmptyReason): SAFeedReasonPresentation {
  switch (reason) {
    // one explicit case for every closed-union member
    default:
      unreachableSAFeedReason(reason);
      return { copy: "degraded", canOpenDataSources: false };
  }
}
```

The fallback after the `never` call remains a fail-safe for malformed runtime
JSON, but adding a declared union member without a case must fail TypeScript
compilation. A set-based classifier is not accepted. The rendering contract is:

- statistics and facets require `feed?.available`;
- rows and Load More require `feed?.available` even if an adversarial fixture
  supplies items or a positive total;
- valid-empty copy requires `feed?.available && feed.total === 0`;
- `store_not_created` uses the one new neutral leaf;
- `requires_local_sa` retains path-specific copy;
- all other unavailable states use existing degraded copy;
- all path/store states listed above receive the existing Data Sources action;
- `backend_unavailable` stays degraded without claiming a path action.

No CSS change is authorized.

## 6. Stop Conditions

Stop and return to design review if any of these occurs:

1. an eighth activity authority is found outside extension protocol, the
   SA-enabled service definitions, or the repair owner;
2. any relevant job history is pruned, archived away, or time-bounded;
3. a valid feed needs a table or column absent from the reviewed schema map;
4. schema compatibility needs a write, migration, exact user-version pin, FTS
   rebuild, or `quick_check` on every request;
5. no-create history evidence requires `JobRunsLocalStore` construction;
6. the feed cannot avoid the global missing-file in-memory fallback without
   changing `src/sa_capture_store.py`;
7. a public consumer requires raw SQLite/path diagnostics;
8. Alpha Picks, extension, native-host, scheduler, recovery, provider,
   Gateway, PG, or database schema behavior must change;
9. frontend truthfulness requires CSS;
10. node/resource/scanner/tool/no-PG baselines differ before product edits;
11. the implementation introduces a second availability field; or
12. an unavailable fixture can still render any count, facet, row, empty copy,
    or pagination control.

## Task 0: Plan Clearance, Isolated Worktree, And Re-grounding

**Files:**
- Modify `docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md`
- Create `docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md`
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Record independent plan-review clearance.**

  Resolve every review item against source. Commit only plan/spec/priority-map
  corrections on `master`, then record the full commit as
  `PLAN_REVIEW_CLEARANCE_COMMIT`. Product work is forbidden before this commit.

- [ ] **Step 2: Create an isolated worktree.**

  ```bash
  git worktree add /tmp/arkscope-sa-feed-store-truth \
    -b codex/sa-feed-store-truth PLAN_REVIEW_CLEARANCE_COMMIT
  ```

  Do not copy `data/`, `config/.env`, browser profiles, production databases,
  or the untracked `docs/design/SCRIPTS_RETIREMENT_DECISION.md` into it.

- [ ] **Step 3: Reproduce all four collections and hashes.**

  Run Section 2.1 exactly. Expected: backend `4691/77`, frontend
  `96 files / 1072 nodes` and `2 files / 25 focused nodes`, with all four
  baseline hashes exact. Any drift is a stop condition.

- [ ] **Step 4: Reproduce behavior and non-node baselines.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py tests/test_sa_feed.py

  cd apps/arkscope-web
  npx vitest run src/News.test.tsx src/i18n/resources.test.ts
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count

  /home/hyl/.virtualenvs/llm_app/bin/python - <<'PY'
  from src.smoke.pg_unreachable_e2e import REQUIRED_CHECKS
  from src.tools.registry import create_default_registry

  assert len(create_default_registry().list_names()) == 53
  assert len(REQUIRED_CHECKS) == 23
  PY

  python src/smoke/pg_unreachable_e2e.py
  ```

  Expected: focused `77` and `25` green; resources `379/704/1782`;
  tools `53/54/54`; no-PG `23`, `ok=true`, `pg_attempts=[]`; scanner exact.

- [ ] **Step 5: Capture byte baselines.**

  Record `git rev-parse HEAD:<path>` for every protected tracked file and a
  sorted `git ls-tree -r` SHA-256 for protected directory families. Include the
  scanner hashes in Section 2.2.

- [ ] **Step 6: Create the evidence packet.**

  Header:

  ```text
  IMPLEMENTATION IN PROGRESS - NO PRODUCTION WRITE - INDEPENDENT REVIEW PENDING
  ```

  Include clearance commit, collection lists/hashes, focused pass results,
  resource/scanner/tool/no-PG facts, protected byte hashes, and an explicit
  statement that no production file or external service was touched.

- [ ] **Step 7: Commit Task 0 docs only.**

  ```bash
  git add docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md \
    docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: ground SA feed store truth implementation"
  ```

## Task 1: Add The No-Create History Evidence Reader

**Files:**
- Modify `tests/test_job_runs.py`
- Modify `src/service/job_runs_store.py`

- [ ] **Step 1: Write five named RED tests.**

  Add the four `read_job_activity_if_exists` node IDs plus
  `test_sa_store_history_contract_has_no_pruning_or_time_cutoff` from Section
  3.1. The authority-completeness node waits for Task 2, where its immutable
  owner is introduced. Test setup may create disposable SQLite fixtures
  directly, but the production primitive must remain no-create.

  Required assertions:

  - missing nested profile path returns `none` and leaves both parent and file
    absent;
  - existing SQLite file without `job_runs` returns `none` and preserves file
    size, `mtime_ns`, `PRAGMA schema_version`, and `sqlite_master` names;
  - unrelated rows remain `none`, while an exact relevant name is `present`;
  - directory and malformed existing profile targets return `unknown`;
  - runtime `src/**` contains no `DELETE FROM job_runs` or
    `DROP TABLE job_runs`, and the reader source contains no `started_at`,
    `finished_at`, status, limit age, or timestamp predicate.

- [ ] **Step 2: Run RED and verify failure provenance.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py -k \
    'read_job_activity_if_exists or sa_store_history_contract'
  ```

  Correct RED: missing import/symbol or wrong evidence result. A fixture
  exception, permission accident, or accidental real profile access is an
  invalid RED and must be fixed before implementation.

- [ ] **Step 3: Implement `read_job_activity_if_exists`.**

  Follow Section 5.1. Use `sqlite_master` to distinguish absent table from a
  malformed query. Use parameter placeholders for all names. Always close the
  connection.

- [ ] **Step 4: Prove mutation sensitivity.**

  Temporarily replace the reader body with
  `JobRunsLocalStore(db_path); return "none"`. The missing-profile test must
  fail because a parent/file/schema was created. Restore the real helper and
  rerun green.

  Temporarily add `AND status='succeeded'` or a timestamp predicate. Seed the
  relevant-reader test with a non-succeeded row; the relevant/unrelated or
  contract test must fail. Restore and rerun green.

- [ ] **Step 5: Run the complete job-runs suite.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q tests/test_job_runs.py
  ```

  Expected: `68 passed`.

- [ ] **Step 6: Commit Task 1.**

  ```bash
  git add src/service/job_runs_store.py tests/test_job_runs.py
  git commit -m "feat: add no-create SA activity history reader"
  ```

## Task 2: Classify Missing Storage From Ordered Evidence

**Files:**
- Modify `tests/test_job_runs.py`
- Modify `tests/test_sa_feed.py`
- Modify `src/tools/sa_tools.py`

- [ ] **Step 1: Add missing-path and precedence RED tests.**

  Add this one authority-completeness node to `tests/test_job_runs.py` and the
  11 new feed nodes summarized below (their seven exact names are in Section
  3.1):

  ```text
  test_sa_store_activity_job_names_cover_all_current_authorities
  test_missing_store_without_profile_is_not_created_and_creates_nothing
  test_missing_store_with_empty_profile_is_not_created_without_mutation
  seven independently named activity-history nodes
  test_missing_store_with_unreadable_history_fails_closed_as_missing
  test_backend_unavailable_precedes_store_and_history_checks
  ```

  Strengthen `test_feed_pg_mode_requires_local` in place. Monkeypatch the
  history reader to raise if backend-unavailable or requires-local paths call
  it; both earlier states must return before filesystem/history inspection.

  Each activity-name function must loop through `running`, `succeeded`, and
  `failed`, seed only its exact name, and assert `store_missing`. Do not use
  `pytest.mark.parametrize` for the seven names.

  The completeness node imports the three authorities only in test code and
  proves their union equals the immutable seven-name owner. Production code
  must not import the service registry.

- [ ] **Step 2: Run RED.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py tests/test_sa_feed.py -k \
    'sa_store_activity_job_names or missing_store or backend_unavailable or pg_mode_requires_local'
  ```

  Correct RED: current missing path returns
  `available=true/no_items_in_window`, or the new reason is absent. A failure
  caused by writing the real profile path is invalid.

- [ ] **Step 3: Add the immutable activity owner and safe empty projection.**

  Implement `SA_STORE_ACTIVITY_JOB_NAMES`, import only the no-create primitive
  and `resolve_profile_state_db_path`, and evolve `_empty_feed` to preserve
  normalized `days` plus `query`.

- [ ] **Step 4: Add the first four ordered states.**

  After parameter normalization, classify in this exact order:

  1. backend absent/lacks DB interface -> `backend_unavailable`;
  2. backend lacks `_sa_db` -> `requires_local_sa`;
  3. SA path absent plus history `none` -> `store_not_created`;
  4. SA path absent plus history `present|unknown` -> `store_missing`.

  Use `os.path.lexists` to reserve broken symlinks for the unreadable state.
  No missing path may reach `sa_capture_store.connect`.

- [ ] **Step 5: Run GREEN and mutation probes.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py tests/test_sa_feed.py -k \
    'read_job_activity_if_exists or sa_store_activity or missing_store or backend_unavailable or pg_mode_requires_local'
  ```

  Expected at this checkpoint: `tests/test_job_runs.py` `69`,
  `tests/test_sa_feed.py` `25`, total `94`.

  Mutations that must independently turn red:

  - remove any one of the seven strings from the immutable owner;
  - change any one of the seven function fixtures to an unrelated job name;
  - filter history by `status='succeeded'`;
  - construct `JobRunsLocalStore` in the feed path;
  - move missing-store inspection before `requires_local_sa`.

- [ ] **Step 6: Commit Task 2.**

  ```bash
  git add src/tools/sa_tools.py tests/test_job_runs.py tests/test_sa_feed.py
  git commit -m "feat: classify absent SA feed storage honestly"
  ```

## Task 3: Validate The On-Disk Store And Query Through One Read-Only Connection

**Files:**
- Modify `tests/test_sa_feed.py`
- Modify `src/tools/sa_tools.py`

- [ ] **Step 1: Add path/open RED tests.**

  Add:

  ```text
  test_directory_sa_store_is_unreadable
  test_broken_symlink_sa_store_is_unreadable
  test_malformed_sa_store_is_unreadable
  test_sa_store_open_failure_is_unreadable_and_sanitized
  ```

  Responses must preserve normalized `days` and `query`, contain no configured
  path/SQLite prose, and remain `available=false`. The open-failure fixture
  simulates disappearance or access failure after the filesystem check.

- [ ] **Step 2: Add schema-capability RED tests.**

  Add one parametrized function with five explicit IDs, one required-column
  node, and one additive-schema node. The five IDs are counted separately in
  Section 3.1.

  Build disposable databases without mutating production schema code. For the
  missing-table cases, create all reviewed capabilities except the named table.
  For the missing-column case, recreate one ordinary table without one required
  column. For the additive case, add an unknown table and columns and require a
  normal valid-empty result.

- [ ] **Step 3: Add the post-validation query RED test.**

  Inject the failure at `_sa_feed_local_conn`, after successful open and schema
  validation. Use a private marker containing a fake local path and SQLite
  text. Assert:

  ```python
  result["available"] is False
  result["empty_reason"] == "store_query_failed"
  result["days"] == 3650
  result["query"] == "private query"
  marker not in repr(result)
  configured_path not in repr(result)
  ```

  Also add
  `test_route_returns_typed_200_for_every_unavailable_store_reason`. Build a
  minimal FastAPI app with the real Seeking Alpha router, override only
  `get_dal`, and monkeypatch the tool seam to return each closed unavailable
  payload inside one explicit loop. Every response must be HTTP `200` and must
  preserve the exact typed reason. A handler-direct call does not satisfy this
  node.

- [ ] **Step 4: Run RED and confirm each failure class.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_sa_feed.py -k \
    'unreadable or schema_incompatible or extra_feed_schema or post_validation or route_returns'
  ```

  Missing table/column must fail as incompatible, not because fixture SQL is
  invalid. The query test must fail at the injected seam, not during schema
  setup.

- [ ] **Step 5: Implement direct read-only open and schema probe.**

  Follow Sections 5.4 and 5.5. Split `_sa_feed_local` into a connection-owning
  classifier and `_sa_feed_local_conn`. Preserve existing filters, ordering,
  FTS/LIKE routing, facets, snippets, pagination, and item projection.

  Probe both FTS capabilities even when `q is None`. Do not add a request-shape
  exception.

- [ ] **Step 6: Evolve existing valid-empty and route nodes in place.**

  `test_feed_empty_window` additionally proves that valid zero is
  `available=true/no_items_in_window` only after a compatible query.

  `test_route_handler_happy_and_disabled` additionally proves:

  - feature disabled remains HTTP `503`;
  - populated route behavior is unchanged.

  The new real-HTTP node, rather than this handler-direct node, proves every
  unavailable store reason remains a typed HTTP `200` response.

- [ ] **Step 7: Run all feed and job-history tests.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py tests/test_sa_feed.py
  ```

  Expected: `107 passed`.

- [ ] **Step 8: Prove the store/query boundaries by mutation.**

  Independently verify:

  - use global `store.connect(read_only=True)` for the missing/race path -> open
    failure or no-create node turns red;
  - skip either FTS table when `q is None` -> that table's node turns red;
  - count extra columns as incompatible -> additive-schema node turns red;
  - convert post-validation failure to valid empty -> query-failure node turns
    red;
  - pass `str(exc)` to `_empty_feed` -> sanitization node turns red.

- [ ] **Step 9: Commit Task 3.**

  ```bash
  git add src/tools/sa_tools.py tests/test_sa_feed.py
  git commit -m "feat: derive SA feed truth from read-only store capability"
  ```

## Task 4: Render The Closed Availability Contract In News

**Files:**
- Modify `apps/arkscope-web/src/api.ts`
- Modify `apps/arkscope-web/src/News.tsx`
- Modify `apps/arkscope-web/src/News.test.tsx`
- Modify `apps/arkscope-web/src/i18n/resources/en/explore.ts`
- Modify `apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts`
- Modify `apps/arkscope-web/src/i18n/resources.test.ts`

- [ ] **Step 1: Add one resource leaf per locale and evolve counts.**

  Add `explore.news.seekingAlphaNotCreated` with neutral first-run meaning:

  ```text
  en: The local Seeking Alpha store has not been initialized. Run the browser extension once.
  zh-Hant: Seeking Alpha 本地資料庫尚未初始化。請先執行一次瀏覽器擴充功能。
  ```

  Do not name Chrome or Firefox. Evolve the two inventory nodes in place:
  Explore `news 43 -> 44`, Explore `379 -> 380`, total `1782 -> 1783`, Settings
  unchanged at `704`.

- [ ] **Step 2: Add the two mounted RED nodes and evolve recovery coverage.**

  Add the two node IDs in Section 3.2. Use adversarial unavailable fixtures
  with positive totals, nonempty facets, rows, and pagination potential. Loop
  through every unavailable reason inside one named visibility test so it
  remains one node, while asserting each reason label in the failure message.

  The bilingual node proves neutral copy for `store_not_created`, path-specific
  copy for `requires_local_sa`, and generic degraded copy for the other store
  reasons in both `zh-Hant` and `en`.

  Evolve the existing recovery-target node without renaming it. Every
  path/store reason receives Data Sources; `backend_unavailable` and valid empty
  do not claim that action. The same node reads `News.tsx` and requires the
  exhaustive `switch`, the `unreachableSAFeedReason(value: never)` helper, and
  the absence of a set-based availability classifier.

- [ ] **Step 3: Run RED.**

  ```bash
  cd apps/arkscope-web
  npx vitest run src/News.test.tsx src/i18n/resources.test.ts
  ```

  Correct RED includes the current zero/facet block rendering while
  `available=false`, missing closed TypeScript reasons, missing neutral copy,
  and resource count `379/1782`. A test fixture type error unrelated to the
  contract is invalid RED.

- [ ] **Step 4: Implement the closed TypeScript union and rendering gates.**

  Follow Section 5.6. Gate statistics, rows, and Load More at render time with
  `feed.available`; do not merely rely on backend empty arrays. Keep valid
  empty and populated behavior unchanged. Use the required exhaustive switch;
  a `Set.has()` implementation is not contract-equivalent. Do not add CSS.

- [ ] **Step 5: Run focused GREEN and mutation probes.**

  ```bash
  cd apps/arkscope-web
  npx vitest run src/News.test.tsx src/i18n/resources.test.ts
  npm run typecheck
  npm run check:i18n-literals
  npm run check:i18n-literals
  ```

  Expected: `27 passed`; resources `380/704/1783`; scanner twice
  `36/20/0/20`.

  Independently remove each of these gates and require the visibility node to
  turn red:

  - statistics `feed.available` condition;
  - list/row `feed.available` condition;
  - Load More `feed.available` condition;
  - valid-empty `feed.available` condition.

  Restore all mutations before continuing.

- [ ] **Step 6: Commit Task 4.**

  ```bash
  git add apps/arkscope-web/src/api.ts \
    apps/arkscope-web/src/News.tsx \
    apps/arkscope-web/src/News.test.tsx \
    apps/arkscope-web/src/i18n/resources/en/explore.ts \
    apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts \
    apps/arkscope-web/src/i18n/resources.test.ts
  git commit -m "fix: present unavailable SA feed states truthfully"
  ```

## Task 5: Run Isolated Runtime, Full, And Boundary Gates

**Files:**
- Modify `docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md`

- [ ] **Step 1: Run the isolated no-create matrix.**

  Use only temporary paths. Cover:

  ```text
  no SA + no profile              -> store_not_created
  no SA + empty profile           -> store_not_created
  no SA + each activity/status    -> store_missing
  no SA + malformed profile       -> store_missing
  directory/broken/malformed SA   -> store_unreadable
  missing capability              -> store_schema_incompatible
  compatible empty                -> no_items_in_window / available=true
  compatible populated            -> normal result
  injected query failure          -> store_query_failed
  ```

  Record path nonexistence or file size, `mtime_ns`, integrity, FK, schema
  version, table names, and relevant row counts before/after. No absent parent
  or file may appear.

- [ ] **Step 2: Run canonical collections and exact comm.**

  Re-run Section 2.1 against `PLAN_REVIEW_CLEARANCE_COMMIT` and `HEAD`.
  Expected:

  ```text
  backend focused 77 -> 107, +30/-0
  backend full    4691 -> 4721, +30/-0
  frontend focused 25 -> 27, +2/-0
  frontend full   1072 -> 1074, +2/-0, still 96 files
  ```

  Compare node IDs with `comm -13` and `comm -23`, not only counts. The exact
  added names must match Section 3.

- [ ] **Step 3: Run focused and full suites.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_job_runs.py tests/test_sa_feed.py
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q

  cd apps/arkscope-web
  npx vitest run src/News.test.tsx src/i18n/resources.test.ts
  npm test -- --run
  npm run typecheck
  npm run build
  npm run check:i18n-literals
  npm run check:i18n-literals
  cd ../..

  python src/smoke/pg_unreachable_e2e.py
  ```

  Full-suite absolute failures are compared by normalized node-ID set against
  the Task 0 environment baseline. Expected new failures: zero. Focused suites,
  typecheck, build, scanner, and no-PG must be fully green.

- [ ] **Step 4: Run resource/tool/no-PG gates.**

  ```bash
  /home/hyl/.virtualenvs/llm_app/bin/python -m pytest -q \
    tests/test_tools.py::TestRegistry::test_register_all \
    tests/test_agents.py::TestAnthropicToolSchemas::test_tool_count \
    tests/test_agents.py::TestOpenAIToolCreation::test_create_tools_count \
    tests/test_pg_unreachable_e2e.py
  ```

  Expected: tools `53/54/54`; no-PG inventory `23`; no tool/route name change.

- [ ] **Step 5: Prove byte-identical boundaries.**

  ```bash
  git diff --exit-code PLAN_REVIEW_CLEARANCE_COMMIT -- \
    src/sa_capture_store.py \
    src/api/routes/seeking_alpha.py \
    src/sa/extension_run_protocol.py \
    src/sa/market_news_recovery.py \
    src/service/jobs.py \
    src/sa_native_host.py src/sa_native_manifest.py \
    extensions/sa_alpha_picks \
    apps/arkscope-web/src/styles.css \
    apps/arkscope-web/src/primitives.css \
    apps/arkscope-web/src/shell.css \
    apps/arkscope-web/src/tokens.css \
    apps/arkscope-web/scripts/i18n \
    sql
  ```

  Also require no change under DB migration, provider, Gateway, PG, scheduler,
  repair, Alpha Picks, extension, native-host, and CSS ownership.

- [ ] **Step 6: Run isolated bilingual browser evidence.**

  Start only an isolated sidecar/profile/SA fixture. Verify at 390, 960, and
  1440 CSS pixels in both locales:

  - neutral not-created copy and Data Sources action;
  - degraded store reason with no count/facet/row/empty/load-more claim;
  - valid empty copy without recovery action;
  - populated state unchanged;
  - locale switch preserves mode/filter state and makes no data refetch.

  Use semantic locators. No production browser, extension, provider, scheduler,
  or repair action is allowed.

- [ ] **Step 7: Update evidence and run repository hygiene.**

  ```bash
  git diff --check
  git status --short
  git log --oneline --decorate PLAN_REVIEW_CLEARANCE_COMMIT..HEAD
  ```

  Record exact final node lists/hashes, comm, runs, resource/scanner/tool/no-PG
  results, mutation probes, byte gates, browser matrix, and any environment-only
  full-suite failures. Do not call the implementation LIVE or touch production.

- [ ] **Step 8: Commit review-ready evidence.**

  ```bash
  git add docs/superpowers/evidence/2026-07-27-sa-feed-store-truth.md \
    docs/superpowers/plans/2026-07-27-sa-feed-store-truth.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: prepare SA feed store truth review packet"
  ```

## Task 6: Independent Implementation Review

**Files:**
- Modify only review corrections and evidence/status documents authorized by
  this plan

- [ ] **Step 1: Stop product work at review-ready.**

  Do not merge, push, run a production smoke, restart ArkScope, trigger SA
  capture, or edit production databases before independent review.

- [ ] **Step 2: Reviewer reproduces canonical A/B.**

  Required independent checks:

  1. all four baseline/final collections and exact comm;
  2. seven activity names as seven independent nodes, each status-independent;
  3. no-create mutation by substituting `JobRunsLocalStore`;
  4. authority-set completeness against all three current sources;
  5. ordered precedence including backend/requires-local before history;
  6. directory, broken symlink, malformed DB, and open-race classification;
  7. five table and one column omissions plus additive schema acceptance;
  8. both FTS tables checked even without `q`;
  9. post-validation failure preserves normalized request facts and leaks no
     path/prose;
  10. valid empty is reachable only after a successful compatible query;
  11. mounted unavailable fixtures render no count/facet/row/empty/load-more;
  12. both locale states and Data Sources action mapping;
  13. exact resource/scanner/tool/no-PG accounting;
  14. protected byte families and no production writes.

- [ ] **Step 3: Resolve findings with RED-first evidence.**

  Any product correction receives a named failing test before code. Update
  node/resource accounting if and only if the reviewed correction genuinely
  changes it. Re-run all affected and final gates.

- [ ] **Step 4: Record review clearance.**

  Independent GREEN is required before integration. Commit review-only
  evidence corrections, then record the exact reviewed tip.

## 7. Post-Review Integration And Release Protocol

This section is not authorized until Task 6 is GREEN.

1. Confirm `master` still contains `PLAN_REVIEW_CLEARANCE_COMMIT` and has no
   conflicting product changes.
2. Fast-forward only; do not create a merge commit.
3. On the merged tree, rerun backend focused `107`, frontend focused `27`, both
   full collections, exact node comm, resources `380/704/1783`, scanner twice,
   tools `53/54/54`, typecheck/build, no-PG `23`, and protected byte gates.
4. Capture production DB facts using SQLite URI `mode=ro` only:
   path identity, size, `mtime_ns`, `PRAGMA quick_check`, FK count, schema
   version, and relevant row counts for real `sa_capture.db` and
   `profile_state.db`.
5. Positive smoke: merged code reads the real SA store and returns the normal
   populated/valid shape. It triggers no refresh or write.
6. Negative smoke: launch a separate merged-code process with the real
   read-only profile authority and a unique absent path such as
   `/tmp/arkscope-sa-feed-store-truth-<timestamp>/sa_capture.db`. Require
   `available=false`, `empty_reason=store_missing`, normalized request facts,
   no raw path, and absence of both the temporary file and its parent before
   and after. Do not point this process at the real SA store.
7. Re-read both production DB facts and require exact size/mtime/schema/row
   preservation plus integrity `ok` and FK zero. Any mutation stops release.
8. Use a semantic locator to confirm the production News surface still renders
   its normal populated state in both locales. Do not click refresh, recovery,
   extension, provider, scheduler, or repair controls.
9. Update spec, plan, evidence, and priority map to LIVE COMPLETE only after all
   merged and read-only release gates pass. Keep the Alpha Picks availability
   alignment follow-up open.
10. Remove the worktree and delete the branch non-forcibly only after the
    merged tip and closeout commit are confirmed.

## 8. Completion Contract

The slice is complete only when all of the following are independently shown:

1. no missing SA store can return `available=true`;
2. first-run absence, missing-after-evidence, unreadable, incompatible, query
   failure, valid empty, and populated states are mechanically distinct;
3. history evidence is no-create, status-independent, unbounded by time, and
   fail-closed when unreadable;
4. seven names have one immutable owner and complete authority coverage;
5. open/schema/query stages share one direct read-only connection;
6. both FTS tables are capability requirements independent of `q`;
7. normalized request facts survive failures and no raw path/SQLite prose is
   exposed;
8. the frontend closed union matches the backend closed union;
9. unavailable News states render no data or empty-result claims;
10. valid empty and populated behavior remain unchanged;
11. exact node/resource/scanner/tool/no-PG and byte-boundary gates pass;
12. production positive and absent-temp-path negative smokes are read-only and
    leave both real DBs unchanged; and
13. Alpha Picks availability alignment remains separately open.
