# PostgreSQL Runtime Consumer Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** PLAN AUTHORED; INDEPENDENT REVIEW NEXT; IMPLEMENTATION NOT
> AUTHORIZED
>
> **Date:** 2026-08-15
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md`
> at commit `729d8514ac912b447f1892aefd3e897ea8a843b6`, SHA-256
> `e5218b58472891891acdc56fa054b07a30cc98905d71941890ad15a438bf3935`.
>
> **Roles:** Codex authors and executes the docs-only inventory after
> independent plan review. Fable independently reconstructs candidate sets,
> ledgers, partitions, hashes, and review evidence. The user owns batching,
> product dispositions, no-tail implementation, merge, push, live, secret,
> remote-database, and destructive-data rulings.

**Goal:** Produce a complete, mechanically reconstructable, docs-only census
of every remaining PostgreSQL runtime, test, dependency, CLI, environment, and
current-documentation surface, with exactly one reviewed disposition per
surface and exact inputs for a later no-tail implementation plan.

**Architecture:** One canonical `surfaces.jsonl` ledger owns every classified
surface; `candidate_adjudications.jsonl` closes every raw source hit to either
one surface or one narrowly allowed non-surface reason; `candidates.jsonl` and
four named grounding streams preserve independently observed inputs.
Deterministic classification projections and predicted no-tail path sets
derive from those two authorities; grounding streams are regenerated from
their original collectors and joined only at explicit gates.
Static AST/search candidates, dynamic FastAPI route enumeration,
installed-package metadata, test collection, unlocked git-crypt plaintext, and
manual consumer tracing must converge; no one source is treated as complete by
itself.

**Tech Stack:** Git, Python 3.10.12 standard-library `ast`,
`importlib.metadata`, JSON/JSONL, GNU `sha256sum`, `jq`, ripgrep, pytest
collect-only with the pinned EIR-002 reporter, Vitest 4.1.8 list JSON with the
pinned normalizer, and Markdown/TSV authority files.

## Global Constraints

- Exact product grounding base is
  `729d8514ac912b447f1892aefd3e897ea8a843b6`. Task 0 starts from the exact
  independently reviewed plan tip and proves that its delta from this base is
  docs-only. Rebase, merge, or product-byte drift is a stop-and-amend event.
- This line is docs-only. No file outside `docs/` may change in any commit.
- No product/test/dependency/configuration edit, provider call, remote database
  connection, FastAPI lifespan, scheduler start, production SQLite open, or
  archive restore is authorized.
- The private `config/.env` may be checked only for path/key-name presence and
  file metadata. No right-hand-side value, file hash, content excerpt, or copy
  may enter a command transcript or artifact.
- The three git-crypt paths must be inventoried from plaintext in an unlocked
  main tree after proving their tracked blobs equal the implementation base.
  Searching locked ciphertext is rejected absence evidence.
- Every canonical record is UTF-8, globally byte-sorted by its specified key,
  unique, and ends with exactly one newline. Full SHA-256 values are required.
- `surfaces.jsonl` is the only surface/disposition authority;
  `candidate_adjudications.jsonl` is the only raw-candidate resolution
  authority. Every classification projection must rebuild from them
  byte-for-byte; `candidates.jsonl`, full route census, package witness, and
  base node streams are named grounding inputs, not competing classification
  authorities. Manually maintained duplicate truth is forbidden.
- Every surface has exactly one of the six design dispositions. `pending`,
  `unknown`, `cleanup`, `maybe`, and empty dispositions are invalid.
- Inventory may report unresolved evidence only by stopping and amending the
  plan. It may not manufacture certainty or add a seventh disposition.
- Dated plan-author counts below are RED flags for grounding drift, not final
  inventory conclusions. Task 0 must reconstruct them at the reviewed plan
  tip.
- Inventory completion authorizes only a separately reviewed no-tail plan. It
  does not authorize product deletion or compatibility shims.
- The remote three app-record tables, tracked dumps, product SQLite data,
  private `.env`, legacy-agent CLI, and current operator commands remain
  untouched.
- No push is authorized.

---

## 0. Authority, Files, Schemas, and Baselines

### 0.1 Scope of this plan

This plan implements only design section 2, plus the inventory handoff clauses
needed by sections 3 and 4. It does not implement PostgreSQL no-tail, the
legacy-agent CLI census, remote archive deletion, archive restore, or the later
runtime-owner/CSS line.

### 0.2 Tracked file ownership

Create:

```text
docs/design/PG_RUNTIME_CONSUMER_INVENTORY.md
docs/design/pg_runtime_inventory/candidates.jsonl
docs/design/pg_runtime_inventory/candidate_adjudications.jsonl
docs/design/pg_runtime_inventory/candidate_adjudications.tsv
docs/design/pg_runtime_inventory/surfaces.jsonl
docs/design/pg_runtime_inventory/paths.tsv
docs/design/pg_runtime_inventory/symbols.tsv
docs/design/pg_runtime_inventory/routes.tsv
docs/design/pg_runtime_inventory/startup_hooks.tsv
docs/design/pg_runtime_inventory/type_checks.tsv
docs/design/pg_runtime_inventory/dependencies.tsv
docs/design/pg_runtime_inventory/environment_packages.json
docs/design/pg_runtime_inventory/test_nodes.tsv
docs/design/pg_runtime_inventory/cli_entrypoints.tsv
docs/design/pg_runtime_inventory/documentation_claims.tsv
docs/design/pg_runtime_inventory/consumer_methods.tsv
docs/design/pg_runtime_inventory/dispositions.tsv
docs/design/pg_runtime_inventory/no_tail_delete.paths
docs/design/pg_runtime_inventory/no_tail_modify.paths
docs/design/pg_runtime_inventory/no_tail_add.paths
docs/design/pg_runtime_inventory/protected.paths
docs/design/pg_runtime_inventory/backend_base.nodes
docs/design/pg_runtime_inventory/frontend_base.nodes
docs/design/pg_runtime_inventory/pg_focused_base.nodes
docs/design/pg_runtime_inventory/MANIFEST.sha256
docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md
```

Modify only for process/status synchronization:

```text
docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md
docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md
docs/design/PROJECT_PRIORITY_MAP.md
```

Any other tracked path is a stop-and-amend event. Candidate documentation is
classified in the inventory but is not corrected during this line.

### 0.3 Canonical `surfaces.jsonl` schema

Each line is one `json.dumps(record, sort_keys=True, separators=(",", ":"),
ensure_ascii=True)` object. Rows are sorted by UTF-8 bytes of `id`. Required
keys are exact; no extra key is accepted:

The example is pretty-printed only for readability; the tracked record is one
compact JSON line.

```json
{
  "actual_methods": [],
  "candidate_ids": ["dynamic_route:src/api/routes/app_records.py:-:-:route:migration_preview"],
  "cli_class": null,
  "disposition": "retire_pg_only",
  "documentation_status": null,
  "environment_assumptions": [],
  "follow_up_owner": "pg_no_tail",
  "http_methods": ["GET"],
  "id": "route:src/api/routes/app_records.py:migration_preview",
  "kind": "route",
  "line_refs": ["47-61"],
  "local_owner": null,
  "path": "src/api/routes/app_records.py",
  "pg_capabilities": ["migration", "query", "route"],
  "reachability": "api_route",
  "reachability_chain": ["src.api.app.create_app", "app_records.router", "migration_preview"],
  "stop_condition": "A reviewed current product consumer requires migration preview.",
  "symbol": "migration_preview",
  "test_nodes": [{
    "baseline_outcome": "passed",
    "contract_role": "pg_only",
    "environment_assumptions": [],
    "id": "tests/test_app_records_migrate.py::test_route_preview_and_apply",
    "suite": "backend"
  }]
}
```

String arrays are UTF-8 byte-sorted and unique. `test_nodes` objects are sorted
by `(suite, id)` and unique by that pair. `local_owner` is either `null`, an
existing tracked `path:symbol`, or a proposed absent `path:symbol` required by
an exactly measured non-empty method set. A proposed owner is valid only on a
`rewrite_to_local_capability` row and its path is the sole source of the
corresponding `no_tail_add.paths` entry. `symbol` is a non-empty string for
executable, type, dependency, and test surfaces and may be `null` only for
whole-file archive, environment, or documentation rows.

`candidate_ids` is non-empty and maps every classified Task 1 candidate to
exactly one surface. Its union must equal the `classified` IDs in
`candidate_adjudications.jsonl`; duplicates across surfaces are invalid.
`pg_capabilities` is non-empty except for a `legacy-agent` CLI whose sole
disposition is `defer_to_legacy_agent_cli_census`; that exception records the
binding handoff without inventing a PostgreSQL capability.

Closed `kind` values:

```text
archive_asset
cli_entrypoint
dependency
documentation_claim
environment_dependency
inheritance
module_import
route
runtime_config
startup_hook
store_or_backend
test_contract
type_gate
```

Closed `reachability` values:

```text
api_route
archive_only
documentation_only
legacy_agent
operator
product_runtime
scheduler
startup
test_only
unreachable_definition
```

Closed `pg_capabilities` members:

```text
archive
connection
dependency
documentation_claim
inheritance
migration
probe
query
route
runtime_config
test_contract
type_gate
write
```

Closed `disposition` values are copied verbatim from the design:

```text
defer_to_legacy_agent_cli_census
historical_reference
retain_archive_asset
retain_operator_remove_pg_branch
retire_pg_only
rewrite_to_local_capability
```

Closed `follow_up_owner` values:

```text
archive_history
legacy_agent_cli_census
pg_no_tail
runtime_owner_css
```

Disposition/owner compatibility is exact:

```text
retire_pg_only                     -> pg_no_tail
rewrite_to_local_capability        -> pg_no_tail
retain_operator_remove_pg_branch   -> pg_no_tail
retain_archive_asset               -> archive_history
historical_reference               -> archive_history
defer_to_legacy_agent_cli_census   -> legacy_agent_cli_census
```

`runtime_owner_css` is reserved in the schema but must have zero inventory
rows. Discovering a surface that truly requires that owner is a design
stop-and-amend event, not permission to defer PostgreSQL removal.

Closed `cli_class` values are `PG-only`, `mixed`, `operator`, and
`legacy-agent`; the field is non-null exactly when `kind == "cli_entrypoint"`.
Closed `documentation_status` values are `current`, `historical`, and
`archive_instruction`; the field is non-null exactly when
`kind == "documentation_claim"`. `http_methods` is non-empty exactly for route
rows. A route method is an uppercase method from the dynamic route witness.

Closed test suites are `backend` and `frontend`. Closed baseline outcomes are
`passed` and `skipped`. Closed contract roles are:

```text
current_product
historical_compatibility
negative_no_pg
pg_only
```

Package, DSN, scheduler, route, and fixture conditions belong only in
`environment_assumptions`; they are not overloaded into outcome or role.

### 0.4 Candidate ledger, projections, and grounding streams

`candidates.jsonl` is the durable, unclassified source ledger. Each line has
exactly these keys:

```json
{"column":null,"detail":"GET /app-records/migration/preview","id":"dynamic_route:src/api/routes/app_records.py:-:-:route:migration_preview","kind":"route","line":null,"path":"src/api/routes/app_records.py","source_family":"dynamic_route","symbol":"migration_preview"}
```

Candidate rows use the same compact canonical JSON encoding as surfaces and
sort by UTF-8 bytes of `id`. `line` and `column` may be `null` only when the
source has no source coordinate. `kind` uses the section 0.3 closed kind
vocabulary. `path` is repo-relative except for the literal `<environment>`
package witness. `detail` is a string containing bounded identifiers or shape
metadata, never raw secret values or encrypted prose. Closed `source_family`
values are:

```text
archive_manifest
ast
cli_registry
documentation
dynamic_route
environment_metadata
git_crypt_plaintext
package_manifest
test_collection
text_search
```

Multiple candidates may describe one surface, but every candidate ID maps to
exactly one adjudication row.

All source coordinates and `line_refs` refer to the immutable
`CANDIDATE_SOURCE_TIP`, not to later status/evidence line numbers.

`candidate_adjudications.jsonl` contains exactly one compact, ID-sorted row per
candidate:

```json
{"candidate_id":"dynamic_route:src/api/routes/app_records.py:-:-:route:migration_preview","cli_class":null,"evidence":"joins GET route witness and mounted app_records router","exclusion_reason":null,"outcome":"classified","surface_id":"route:src/api/routes/app_records.py:migration_preview"}
```

Closed outcomes are `classified` and `excluded`. A classified row has a
non-null `surface_id` and null `exclusion_reason`; an excluded row has null
`surface_id` and exactly one of:

```text
generated_inventory_authority
cli_handoff_only
lexical_non_surface
```

`evidence` is always a non-empty bounded string with no tabs, newlines, raw
secret, or copied prose.
`cli_class` is non-null exactly for `cli_registry` candidates and uses the
section 0.3 four-value vocabulary. `cli_handoff_only` is valid only for a CLI
with no PostgreSQL capability; it remains in the complete CLI handoff table but
does not receive a fake PostgreSQL disposition. Only `text_search`,
`documentation`, or `git_crypt_plaintext` candidates may use the other two
exclusion reasons. `generated_inventory_authority` is restricted to this plan,
its design, the priority map, and this inventory's evidence path as they exist
at the frozen Task 0 candidate-source tip. `lexical_non_surface` requires an
exact line-level explanation and is invalid for any executable symbol, route,
dependency, environment setting, test contract, CLI, archive asset, or current
product runtime claim. Every other source family must classify to a surface.

The following are classification projections generated from
`surfaces.jsonl` and, where named, `candidate_adjudications.jsonl`:

- `candidate_adjudications.tsv`:
  `candidate_id<TAB>outcome<TAB>surface_id_or_dash<TAB>exclusion_reason_or_dash<TAB>cli_class_or_dash<TAB>evidence`.

- `paths.tsv`: `id<TAB>path<TAB>kind` for every row.
- `symbols.tsv`: `id<TAB>path<TAB>symbol<TAB>kind` for rows with a non-null
  symbol.
- `startup_hooks.tsv`: `id<TAB>path<TAB>symbol<TAB>reachability_chain_json` for
  startup/scheduler hooks.
- `type_checks.tsv`: inheritance and type-gate rows projected as
  `id<TAB>path<TAB>symbol<TAB>kind`.
- `dependencies.tsv`: declared and source-import dependency rows projected as
  `id<TAB>path<TAB>symbol<TAB>disposition`.
- `test_nodes.tsv`: one row per exact node:
  `suite<TAB>node_id<TAB>surface_id<TAB>baseline_outcome<TAB>contract_role<TAB>environment_assumptions_json`.
- `cli_entrypoints.tsv`: one row per entrypoint:
  `entrypoint_id<TAB>path<TAB>symbol<TAB>cli_class<TAB>surface_id_or_dash<TAB>disposition_or_dash`.
  Group all `cli_registry` candidates by `(path, symbol)`, require one class,
  and retain non-PG `cli_handoff_only` rows with dashes in the final two
  columns.
- `documentation_claims.tsv`: one row per claim family:
  `id<TAB>path<TAB>line_refs_json<TAB>documentation_status<TAB>disposition`.
- `consumer_methods.tsv`: one row per consumer-method pair:
  `surface_id<TAB>path<TAB>symbol<TAB>method`, using that consumer surface's
  own `path`/`symbol`; definition-only rows have no method projection.
- `dispositions.tsv`: `id<TAB>disposition<TAB>follow_up_owner` for every
  canonical row.
- path-set files contain one repo-relative path per line and are pairwise
  disjoint. Delete/modify/protected partition every tracked surface path plus
  every `cli_handoff_only` operator path; add contains only absent paths
  projected from reviewed proposed `local_owner` values. A handoff-only CLI
  path is protected unless another PG surface requires that same file to be
  modified, in which case its non-PG command behavior is a named survivor of
  the modify row. A modified path is not also protected.
- `pg_focused_base.nodes` joins canonical test-node objects against the named
  backend/frontend base streams and contains exact normalized node IDs.

The following are independent grounding streams and are never generated from
classification prose:

- `routes.tsv`: all dynamic route rows as
  `methods<TAB>path<TAB>endpoint_module<TAB>endpoint_qualname`;
- `environment_packages.json`: the sanitized package witness from section 0.7;
- `backend_base.nodes`: the pinned reporter's normalized backend collection;
  and
- `frontend_base.nodes`: the pinned normalizer's frontend collection.

Route surfaces must join exactly to `routes.tsv`; dependency/environment rows
must join exactly to `environment_packages.json`; every test object must join
to exactly one matching suite stream. The grounding files are regenerated from
their collectors during review, not trusted because a classification row
mentions them.

Every file is globally UTF-8 byte-sorted with one trailing newline. Empty
ledgers are represented by a zero-byte file and called out explicitly in the
inventory narrative; they must not contain a blank row.

### 0.5 Canonical base identities

Task 0 must freshly reconstruct these at the independently reviewed plan tip:

| Identity | Count | SHA-256 |
|---|---:|---|
| Backend full | 4,394 | `b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb` |
| Frontend full | 1,177 / 101 files | `90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b` |
| Inherited backend native | 4,394 seen | `4,382 passed / 12 skipped / 0 failed`; report `0a58d493ab6b406a2a69fa4cc7b25670373d7a16fd74b85c2b60c9452e07c030` |

The inventory does not execute the native suite. Product bytes are unchanged,
and the prior exact-master native result is dated grounding only. The future
no-tail plan must derive and execute a new canonical target after test
retirement.

Pinned helpers and tracked inputs:

```text
/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
  09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
/tmp/eir006_vitest_list_normalizer.py
  955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
requirements.txt
  23c8fdf89a6eea4ba242c0ce5f23097626d24e91349420778d223bd488ddeb26
package-lock.json
  5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
apps/arkscope-web/package.json
  dbaecc3792419d833af4ef6659cfee42977f6c43e4066c16d3cc8df9b9912ffa
```

Task 0 copies both temporary helpers into its packet. Their `/tmp` paths are
not durable evidence.

### 0.6 Plan-author candidate grounding

These observations were made at
`729d8514ac912b447f1892aefd3e897ea8a843b6` and must be independently
replayed:

```text
Python files importing psycopg2 directly:                 12
  product/data-source files:                              11
  test files:                                              1
Python files importing psycopg directly:                   0
Python files mentioning DatabaseBackend:                  35
  non-tests:                                              18
  tests:                                                  17
Dynamic FastAPI route rows:                              175
Mounted app-record migration routes:                       2
test_db_backend.py nodes:                                 21
  DSN-conditional nodes:                                  17
Frontend migration-route consumers:                        0
```

The 12 direct `psycopg2` importer paths are:

```text
data_sources/financial_datasets_client.py
src/app_records_migrate.py
src/macro_calendar/store.py
src/sa/comment_signal_backfill.py
src/service/data_scheduler.py
src/service/job_runs_store.py
src/service/macro_calendar_health.py
src/smoke/pg_unreachable_e2e.py
src/tools/backends/db_backend.py
src/tools/sa_digest_tools.py
src/tools/sa_tools.py
tests/test_sa_local_readers.py
```

Dynamic route normalization is
`methods<TAB>path<TAB>module<TAB>qualname`, UTF-8 byte-sorted, one final
newline. Its plan-author SHA-256 is
`488231c63e8c9bb0a28a6baf5e972c959c7eeddf9cc5fa10cdffc3330bc95aea`.

### 0.7 Package provenance axis

The repository declares `psycopg[binary]>=3.1`, while current Python source
imports `psycopg2`. At plan-author time the active Python 3.10.12 environment
reported:

```json
{
  "import_providers": {
    "psycopg": [],
    "psycopg2": ["psycopg2-binary"]
  },
  "installed": {
    "news-please": "1.6.15",
    "psycopg2-binary": "2.9.10"
  },
  "observed_reverse_requirements": {
    "psycopg2-binary": ["news-please"]
  },
  "repository_direct_requirements": ["psycopg[binary]>=3.1"]
}
```

This proves the imported v2 module is supplied by an undeclared distribution
in this environment, with installed metadata showing an undeclared
`news-please` reverse-dependent. It does not prove installation history or
whether either distribution was manually installed. The inventory must state
that limit rather than call the relationship a proven installer cause.

`environment_packages.json` records only distribution names, versions,
top-level import mappings, direct requirement strings, and reverse requirement
names. It must not record interpreter path, package install path, user name,
home directory, index URL, environment variables, or full package metadata.

### 0.8 Encrypted-path boundary

Current encrypted paths are exactly:

```text
data_sources/DATA_SOURCES_EVALUATION.md
data_sources/IBKR_INVESTOR_DATA_VALUE.md
data_sources/PAID_SUBSCRIPTION_EVALUATION.md
```

The implementation worktree may contain ciphertext. Before reading plaintext
from the unlocked main tree, compare each path's `git ls-files -s` blob ID at
the implementation base and main `master`. If any blob differs, stop. Do not
copy plaintext into the packet; retain only path, line references for matched
PG claim families, and a bounded paraphrased disposition.

### 0.9 Review gates

Default execution stops after every task for independent review. A later user
batch ruling may replace intermediate waits but cannot relax commits, packets,
or stop conditions. Task 4 is always the combined inventory implementation
review gate. Task 5 requires that review to be GREEN.

---

## 1. Execution Tasks

### Task 0: Re-ground the exact docs-only baseline

**Files:**
- Create: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: exact independently reviewed plan tip, exact product/design base
  `729d8514ac912b447f1892aefd3e897ea8a843b6`, pinned collection helpers,
  current unlocked main tree, and the package/route grounding in sections
  0.5-0.8.
- Produces: immutable Task 0 packet, exact base node streams, sanitized package
  provenance, encrypted-path witness, runtime-isolation/config metadata, and a
  baseline evidence commit used by every later task.

- [ ] **Step 1: Create an isolated implementation worktree**

Use `superpowers:using-git-worktrees`. Branch
`codex/pg-runtime-consumer-inventory` from the exact independently reviewed
plan tip. Prove that
`729d8514ac912b447f1892aefd3e897ea8a843b6..PLAN_TIP` changes docs only and
that the reviewed design blob still has the full SHA-256 pinned in this plan's
header. Stop if master,
the implementation worktree, or the main worktree is dirty, if the merge base
is wrong, or if any product byte differs from the grounding base.

- [ ] **Step 2: Create the Task 0 packet and copy pinned helpers**

Use packet root:

```text
/tmp/pg-runtime-inventory-task0-729d8514
```

Copy the reporter and Vitest normalizer into `tools/` inside that packet, then
verify their full hashes from section 0.5. Record `git status --short`, exact
HEAD, merge-base, Python/pytest/Node/Vitest versions, and the hashes of the
design, requirements, lockfile, and package manifest.

Before any Python or Node command, create and export the isolated paths in the
same controlling shell:

```bash
export PACKET=/tmp/pg-runtime-inventory-task0-729d8514
export SCRATCH_ROOT="$PACKET/runtime"
mkdir -p "$SCRATCH_ROOT/data" "$SCRATCH_ROOT/locks" "$SCRATCH_ROOT/home"
unset DATABASE_URL
export HOME="$SCRATCH_ROOT/home"
export ARKSCOPE_PROFILE_DB="$SCRATCH_ROOT/profile_state.db"
export ARKSCOPE_MARKET_DB="$SCRATCH_ROOT/market_data.db"
export ARKSCOPE_SA_DB="$SCRATCH_ROOT/sa_capture.db"
export ARKSCOPE_MACRO_CALENDAR_DB="$SCRATCH_ROOT/macro_calendar.db"
export ARKSCOPE_CONSENSUS_DB="$SCRATCH_ROOT/consensus.db"
export ARKSCOPE_TOKEN_STORE_PATH="$SCRATCH_ROOT/token_store.json"
export ARKSCOPE_LOCK_DIR="$SCRATCH_ROOT/locks"
```

The worktree's ignored `data/` is an empty real directory. The only permitted
main-tree link is the recorded frontend `node_modules` toolchain link; links to
main `data/`, `config/.env`, or runtime files are forbidden.

- [ ] **Step 3: Recollect backend without running test bodies**

Run from the implementation worktree:

```bash
PYTHONPATH="/tmp/pg-runtime-inventory-task0-729d8514/tools:$PWD" \
PRICE_TRUTH_TIER_REPORT=/tmp/pg-runtime-inventory-task0-729d8514/backend-base.json \
python -m pytest --collect-only -q -p arkscope_eir002_reporter
```

Extract `.collected_node_ids[]` with `jq -r` to `backend_base.nodes`. Verify
sort order, uniqueness, exact count `4,394`, and SHA-256
`b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb`.
The reporter JSON must say zero test bodies executed.

- [ ] **Step 4: Recollect frontend without running test bodies**

Run with an equals-sign output argument so Vitest cannot interpret a test path
as the JSON output file:

```bash
cd apps/arkscope-web
npx vitest list \
  --json=/tmp/pg-runtime-inventory-task0-729d8514/frontend-base.json
python /tmp/pg-runtime-inventory-task0-729d8514/tools/eir006_vitest_list_normalizer.py \
  --input /tmp/pg-runtime-inventory-task0-729d8514/frontend-base.json \
  --web-root "$PWD" \
  --output /tmp/pg-runtime-inventory-task0-729d8514/frontend_base.nodes
```

Verify exact count `1,177`, 101 distinct files (the first TAB field of each
normalized row), and SHA-256
`90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b`.
Any tracked-file rewrite is an immediate stop.

- [ ] **Step 5: Capture sanitized installed-package provenance**

Create a temporary script in the packet using `importlib.metadata` and
`packaging.requirements.Requirement`. It must output exactly the schema in
section 0.7 and omit paths and environment values. Verify the current values
shown there. A changed environment is a stop-and-amend event because the dated
provenance witness must be re-grounded, not silently overwritten.

- [ ] **Step 6: Capture key-name-only and confirm runtime isolation**

For `config/.env`, output only:

```text
{"database_url_key_present":true,"mode":"<octal>","size":<bytes>,"tracked":false}
```

The parser may retain only the substring before the first `=` on each line;
it must discard the remainder immediately and never print it. Record
only the private env file's mode, size, tracked/untracked status, and key-name
presence.

Confirm the exported database/token/lock paths all resolve below
`$SCRATCH_ROOT`, the ignored worktree `data/` and scratch root are real
directories, and neither resolves beneath the main worktree. Record that the
isolated worktree has no link to main `data/` or `config/.env`. Do not stat,
hash, open, or require quiescence of production SQLite files:
Desktop/sidecar may continue legitimate external writes, and their long-lived
metadata is not an inventory admission identity.

- [ ] **Step 7: Prove the git-crypt boundary**

Record the exact three encrypted paths from `git-crypt status -e`; parsing
plain `git-crypt status` by substring is forbidden because `not encrypted:`
contains the same suffix. Accept only lines with the exact encrypted prefix.
For each path, record only its base/main Git blob ID and equality result. Do
not record plaintext or ciphertext bytes. Stop if the set or any blob equality
differs from section 0.8.

- [ ] **Step 8: Write baseline evidence and commit**

Create the evidence file with exact commands, accepted/rejected artifacts,
base identities, package provenance boundary, and explicit statement that no
runtime test, provider, DB, lifespan, scheduler, or product write ran. Add a
newest-first map entry recording Task 0 and the default per-task review rule.

```bash
git add docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: record PostgreSQL inventory baseline"
```

Record that exact commit as `CANDIDATE_SOURCE_TIP`. Every Task 1 source scan
and every later independent candidate reconstruction reads repository blobs
from that tip. Later generated inventory docs therefore cannot recursively
enlarge their own source universe.

Stop for Task 0 review unless the user has issued a recorded batch ruling.

---

### Task 1: Extract the complete candidate universe

**Files:**
- Create: `docs/design/pg_runtime_inventory/candidates.jsonl`
- Modify: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: exact `CANDIDATE_SOURCE_TIP`, Task 0 base streams, and protected
  metadata.
- Produces: a committed unclassified candidate ledger plus raw packet
  artifacts for imports, symbols, routes, startup, dependencies, tests, CLIs,
  docs, encrypted claims, and environment packages. Candidates are evidence,
  not disposition authority.

- [ ] **Step 1: Build a temporary structured Python scanner**

Create a read-only detached worktree at exact `CANDIDATE_SOURCE_TIP`; all
repository-file scanners in this task run there. The implementation branch is
only the destination for the resulting docs ledger and evidence.

Write `/tmp/pg-runtime-inventory-task1-<tip>/tools/scan_python.py`. It must use
`ast.parse` over every `.py` blob tracked at `CANDIDATE_SOURCE_TIP` and emit
candidate objects with the exact section 0.4 schema for:

```text
Import / ImportFrom of psycopg, psycopg2, or PostgreSQL-specific modules
ClassDef bases containing DatabaseBackend or PostgreSQL store classes
Call nodes constructing DatabaseBackend or passing db_dsn
isinstance / issubclass checks naming DatabaseBackend
Attribute calls named _get_conn or connect on PG-class receivers
Name / Attribute / string references to discovered PG classes, re-exports,
  protocols, methods, DATABASE_URL, sslmode, or db_dsn
FastAPI router decorators and include_router calls
if __name__ == "__main__" blocks
argparse / click / typer / fire entrypoint construction
```

Use two AST passes: the first collects definitions/import aliases for PG
classes, stores, migrators, drivers, and config symbols; the second emits every
reference/re-export/call/type gate to that closed discovered symbol set plus
the literal config names above. The scanner emits path, line, column,
candidate kind, enclosing qualname, and
the normalized AST name. It does not import product modules and does not infer
reachability. Its candidate ID is the UTF-8 string
`source_family:path:line:column:kind:symbol`; absent coordinates are the
literal `-`. Reject tabs/newlines in any field before serialization.

The scanner's name resolution and canonical writer must use this shape (the
visitor supplies only matched nodes and their enclosing qualname):

```python
def ast_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = ast_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None

def candidate_id(row: dict[str, object]) -> str:
    coords = [row["line"], row["column"]]
    line, column = ("-" if value is None else str(value) for value in coords)
    return ":".join([
        str(row["source_family"]), str(row["path"]), line, column,
        str(row["kind"]), str(row["symbol"] or "-"),
    ])

def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    by_id = {candidate_id(row): {**row, "id": candidate_id(row)} for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("duplicate candidate id")
    payload = "".join(
        json.dumps(by_id[key], sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True) + "\n"
        for key in sorted(by_id, key=lambda value: value.encode("utf-8"))
    )
    path.write_text(payload, encoding="utf-8", newline="")
```

Keep the script and its full SHA in the Task 1 packet.

- [ ] **Step 2: Run uncapped textual companion searches**

Use `rg` over all tracked plaintext for the closed term set:

```text
DATABASE_URL
DatabaseBackend
PostgreSQL
_get_conn
app_records_migrate
app-records/migration
asyncpg
database backend
database server
db_dsn
db_backend
migration_apply
migration_preview
pg8000
pg_
postgres
postgresql+
psycopg
psycopg2
sqlalchemy.dialects.postgresql
sslmode
use_local_records
```

Use the frozen tip's Git-tracked path list/blobs as input so ignored product
data, `.env`, and later generated inventory files are not searched; remove the
exact section 0.8 encrypted paths from that generic list.
Run one fixed-string, case-insensitive `rg --json -F -i` pass per
listed term under `LC_ALL=C`; normalize the candidate symbol to the listed
lowercase term and use ripgrep's byte offset as `column`. This intentionally
keeps overlapping terms such as `postgres` and `postgresql` as separate source
candidates. Search encrypted plaintext only through the section 0.8 dual-tree
procedure. Parse `rg --json` immediately to
`path<TAB>line<TAB>column<TAB>matched_term`; discard the surrounding line and
all unmatched text before writing the packet. Do not retain or commit raw
encrypted lines, DSN examples, or arbitrary prose.

- [ ] **Step 3: Enumerate the full dynamic FastAPI route surface**

In an isolated process, replace `socket.socket.connect`,
`socket.socket.connect_ex`, and `socket.create_connection` with fail-closed
guards before importing `create_app()`. Do not enter lifespan. Emit all route
rows as:

```text
methods<TAB>path<TAB>endpoint_module<TAB>endpoint_qualname
```

Verify 175 rows, SHA-256
`488231c63e8c9bb0a28a6baf5e972c959c7eeddf9cc5fa10cdffc3330bc95aea`,
and exactly these migration rows:

```text
GET<TAB>/app-records/migration/preview<TAB>src.api.routes.app_records<TAB>migration_preview
POST<TAB>/app-records/migration/apply<TAB>src.api.routes.app_records<TAB>migration_apply
```

Cross-check every dynamic route against static decorator/include candidates.
An unexplained row on either side is a stop.

- [ ] **Step 4: Enumerate dependency, environment, and archive candidates**

Parse requirements, lockfiles, Python packaging metadata, Dockerfiles, and
Compose manifests structurally. Record direct PostgreSQL requirements,
container services/packages, source-import/provider mismatches, top-level
import providers, reverse requirements, and whether each installed
distribution is a declared project dependency. Reproduce section 0.7 without
installation paths.

Independently enumerate every frozen-tip tracked path under `sql/`, `docker/`,
and `data/pg_archive/`, plus every Python migrator/smoke/audit/helper surfaced
by the AST/text union. Emit one `archive_manifest` candidate for each
non-Python archive asset even when it contains no search term. Do not read dump
contents; for tracked manifests/dumps, record only repo path, Git blob ID,
size, and manifest-declared digest/count metadata.

- [ ] **Step 5: Enumerate exact test-node candidates**

Project both base streams by every candidate test path plus every node whose ID
or source body names a candidate symbol, PG DTO, status, copy, or route. Parse
pytest decorators/module fixtures and Vitest source to record
DSN/package/scheduler/route/fixture assumptions. Verify
`tests/test_db_backend.py` has 21 nodes, of which 17 are guarded by
`requires_db`; in the no-`.env` implementation worktree, run that one file and
expect exactly `4 passed / 17 skipped` with no connection attempt. Frontend
nodes remain eligible even when the plan-author migration-route consumer count
is zero. After the candidate test paths close, run the exact backend candidate
files in the Task 0 no-DSN/socket-guarded environment and the exact frontend
candidate files sequentially against the pinned toolchain. Record every
candidate node's `passed`/`skipped` outcome; any unsealed external request or
outcome absent from the collected base streams is a stop.

- [ ] **Step 6: Enumerate CLI and documentation candidates**

CLI candidates are the union of AST entrypoints, `pyproject.toml`/setup entry
points, package.json scripts, executable tracked shell files, and current docs
containing `python -m` or a tracked executable path. Task 1 records candidates
without deciding them; Task 2 assigns each exactly one future class:
`PG-only`, `mixed`, `operator`, or `legacy-agent`.

Documentation candidates include current authorities and historical files.
Record one candidate per path plus claim family, with exact line references.
Do not treat every occurrence of `PG` as a product claim; distinguish machine
identifiers, negative tests, history, archive instructions, and current
runtime assertions explicitly.

- [ ] **Step 7: Prove candidate-union closure and commit evidence**

Normalize and union the structured scanner, textual search, dynamic route,
package, test, CLI, documentation, and encrypted-path candidates into tracked
`candidates.jsonl`. Each raw candidate must have the section 0.4 stable ID and
closed source family. Record per-source and union counts/hashes plus pairwise
differences in evidence. Rebuild the tracked candidate file from packet inputs
with an independently invoked normalization pass and require byte equality. Do
not create `surfaces.jsonl` yet. Manifest and remove the detached candidate
source worktree after proving it clean; the immutable commit remains the
reconstruction authority.

```bash
git add docs/design/pg_runtime_inventory/candidates.jsonl \
  docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: census PostgreSQL runtime candidates"
```

Stop for Task 1 review unless a recorded batch ruling applies.

---

### Task 2: Trace consumers, methods, tests, CLIs, and claims

**Files:**
- Create: `docs/design/pg_runtime_inventory/surfaces.jsonl`
- Create: `docs/design/pg_runtime_inventory/candidate_adjudications.jsonl`
- Create: `docs/design/pg_runtime_inventory/environment_packages.json`
- Modify: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: Task 1 tracked `candidates.jsonl` and its raw-source packet.
- Produces: one adjudication per raw candidate and one fully classified
  canonical row per admitted surface, including exact reachability, measured
  consumer methods, tests/environment, one disposition, follow-up owner, and
  falsifiable stop condition.

- [ ] **Step 1: Adjudicate and trace every candidate**

For each candidate, inspect imports, factories, call sites, registrations,
routes, startup hooks, tests, and current docs. Write exactly one section 0.4
adjudication. Every non-text candidate must classify except the exact
`cli_handoff_only` operator/no-PG case. For classified candidates, record a
concrete surface `reachability_chain`.
`unreachable_definition` requires an uncapped caller census and a named
deletion owner; definition-only occurrence is not enough. For excluded text
candidates, enforce the source-family/path restrictions and write bounded
line-level evidence rather than raw prose.

- [ ] **Step 2: Measure local capability methods**

For every retained consumer that inherits from, constructs, or type-checks a
PostgreSQL class, list the exact methods it calls. Verify calls against the
consumer AST and runtime registration path. Do not include methods merely
implemented by the backend. If no existing neutral local owner exposes exactly
that measured set, record one proposed minimal owner and add-path; do not add
methods beyond the call-site set. If the measured need implies a broader store
or domain redesign, stop and amend rather than designing it here.

- [ ] **Step 3: Classify all CLI entrypoints**

Assign exactly one of `PG-only`, `mixed`, `operator`, or `legacy-agent` based on
current reachable behavior. `PG-only` and `mixed` candidates classify to PG
surfaces. An `operator` with a PG branch classifies to a surface; an operator
with no PG capability uses `cli_handoff_only` and receives no fake disposition.
The interactive agent CLI and any Track-B/skill/Discord-adjacent entrypoint
classify to a surface with `defer_to_legacy_agent_cli_census`; do not recommend
retirement in this task. A mixed command retains only its non-PG product
capability in the future no-tail line.

- [ ] **Step 4: Classify tests without preserving false contracts**

Map each exact node to the surface it owns, one observed baseline outcome, one
contract role, and a sorted environment-assumption set:

```text
baseline_outcome: passed | skipped
contract_role: current_product | historical_compatibility | negative_no_pg | pg_only
environment examples: requires_psycopg2_import | requires_database_url | scheduler_disabled | sealed_fixture
```

Nodes may map to more than one surface through separate `test_nodes.tsv` rows,
and `contract_role` describes that node-to-surface relationship. Each
`(suite, node_id)` has one baseline outcome and one environment-assumption set
across all rows. Every node must exist in exactly one of
`backend_base.nodes` or `frontend_base.nodes`. Tests that only preserve retired
inheritance, empty PG tombstones, or DSN routing are candidate retirements, not
automatic protected coverage.

- [ ] **Step 5: Classify current and historical documentation**

Current runtime claims receive `pg_no_tail` follow-up ownership. Dated plans,
evidence, and closed migration narratives receive `historical_reference`
unless they still function as current instructions. Archive restore docs and
tracked dump manifests receive `retain_archive_asset`. Record the root README
overclaim explicitly rather than silently correcting it.

- [ ] **Step 6: Write both canonical classification authorities**

Write `candidate_adjudications.jsonl` and `surfaces.jsonl`. Use every required
key from sections 0.3-0.4, only closed vocabulary values,
sorted unique arrays, repo-relative tracked paths (except the explicit
`<environment>` dependency row), and one non-empty stop condition per row.
Adjudicate the complete candidate ID set exactly once; map every classified ID
to exactly one surface. Include dependency rows for both the declared but
unavailable v3 family and the imported environment-provided v2 family.
Preserve the installation provenance limit from section 0.7.

- [ ] **Step 7: Validate canonical shape before commit**

A temporary validator must reject:

```text
missing or extra keys
duplicate or unsorted ids
unknown enum values
unsorted or duplicate string arrays or test objects
untracked paths except the explicit environment-dependency row
empty reachability chains for reachable rows
empty stop conditions
candidate IDs absent from candidates.jsonl
candidate IDs with zero or multiple adjudications
non-text candidates excluded from surfaces without the exact
cli_handoff_only/operator/no-PG exception
excluded rows with an unknown reason, forbidden path, or empty evidence
classified candidate IDs mapped by zero or multiple surfaces
CLI candidates with missing/conflicting class or class/disposition mismatch
test node IDs absent from their declared backend/frontend suite stream
one test node assigned conflicting outcome or environment assumptions
cli_class/documentation_status/http_methods populated outside their owning kind
missing cli_class/documentation_status/http_methods on their owning kind
disposition/follow_up_owner pairs outside the exact section 0.3 table
any row using the reserved runtime_owner_css owner
empty pg_capabilities outside the exact deferred legacy-agent exception
more or fewer than one disposition per row
```

Run one negative self-test for each rejection class against a temporary copy;
none may alter the admitted ledger. Retain validator source, self-test source,
transcripts, and full hashes in the Task 2 packet.

- [ ] **Step 8: Commit canonical classification**

```bash
git add docs/design/pg_runtime_inventory/surfaces.jsonl \
  docs/design/pg_runtime_inventory/candidate_adjudications.jsonl \
  docs/design/pg_runtime_inventory/environment_packages.json \
  docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: classify PostgreSQL runtime consumers"
```

Stop for Task 2 review unless a recorded batch ruling applies.

---

### Task 3: Generate projections and close the no-tail handoff

**Files:**
- Create: every remaining path under
  `docs/design/pg_runtime_inventory/` listed in section 0.2
- Create: `docs/design/PG_RUNTIME_CONSUMER_INVENTORY.md`
- Modify: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: Task 2 canonical `surfaces.jsonl`, Task 0 base node streams, and
  Task 1 `candidates.jsonl` plus dynamic route stream.
- Produces: all byte-exact projections, six complete disposition partitions,
  predicted no-tail path sets, focused PG node stream, readable inventory
  authority, and a manifest that the no-tail plan can consume without another
  discovery pass.

- [ ] **Step 1: Generate every projection from canonical JSONL**

Use one temporary structured generator that parses both canonical JSONL files
and writes the exact classification formats in section 0.4. Separately copy
the byte-verified Task
0 backend/frontend streams and Task 1 dynamic route witness into their named
grounding paths. No classification projection or grounding witness may be
manually edited after generation/capture. Retain generator source, invocation,
and full hash in the Task 3 packet.

- [ ] **Step 2: Build the exact PG-focused node stream**

Union every canonical test object, verify each appears exactly once in its
declared backend/frontend base stream, sort exact node IDs by UTF-8 bytes, and
write `pg_focused_base.nodes`. Record per-suite and per-file counts, total
count, and full hash in the narrative. No name-pattern approximation is
accepted.

- [ ] **Step 3: Prove six-way partition algebra**

Project one ID set for each disposition and prove:

```text
pairwise intersections are empty
union of six partitions equals every surfaces.jsonl id
no partition is empty without an explicit narrative explanation
every follow_up_owner is compatible with its disposition
```

`defer_to_legacy_agent_cli_census` must contain actual members or the value is
removed only by a reviewed design amendment; an empty dumping-ground category
is forbidden.

- [ ] **Step 4: Build predicted no-tail path sets**

Create exact delete, modify, add, and protected path sets. Rules:

- delete contains only paths whose retained non-PG consumers are zero;
- modify contains mixed/local-consumer owners that must lose a PG branch,
  inheritance, type gate, DTO, copy, or test contract;
- add contains only absent proposed `local_owner` paths backed by a measured
  non-empty method set; no speculative module or test path;
- protected contains current local/domain/frontend/archive owners whose bytes
  no-tail must preserve, plus every non-PG operator path from
  `cli_handoff_only` that is not already a modify path; and
- all four sets are pairwise disjoint.

If frontend PG DTO/copy consumers are zero, list all current frontend product
paths as a byte-protected boundary and say so explicitly. If any exist, list
their exact bounded modify owners; do not infer byte protection from the
plan-author zero migration-route observation.

- [ ] **Step 5: Write the readable inventory authority**

`PG_RUNTIME_CONSUMER_INVENTORY.md` must include:

1. status/base/authority boundary;
2. candidate-source counts/hashes plus classified/excluded adjudication counts,
   hashes, and exact exclusion evidence;
3. the package v3-declaration/v2-import provenance finding and its limit;
4. complete runtime/startup/route/store/backend maps;
5. exact consumer method table and minimal-capability ceiling;
6. test-node and environment-assumption table;
7. four-way CLI table with no retirement ruling for legacy-agent;
8. current/historical/archive documentation table;
9. six dispositions with counts/hashes;
10. predicted no-tail delete/modify/add/protected tables;
11. canonical backend/frontend/focused identities and recipes;
12. named stop conditions and unresolved facts, which must be empty at
    admission; and
13. explicit exclusions for secrets, remote tables, product DBs, archive
    mutation, and product implementation.

- [ ] **Step 6: Build the tracked manifest**

`MANIFEST.sha256` covers every tracked file in
`docs/design/pg_runtime_inventory/` except itself. Recipe: UTF-8 byte-sort
literal relative paths, run GNU `sha256sum` in that order from repo root, and
write the complete standard-output rows with one final newline. Record the
manifest file's own SHA separately in evidence.

- [ ] **Step 7: Run projection and boundary verification**

Rebuild all classification/adjudication projections into a separate temporary
directory and compare each to the tracked version with `cmp`. Independently
recapture and compare `candidates.jsonl` from `CANDIDATE_SOURCE_TIP`, base node
streams, full dynamic routes, and package witness. Verify six partitions, four
path sets, manifest, design/base hashes, and zero non-doc diff from
`729d8514ac912b447f1892aefd3e897ea8a843b6`.

- [ ] **Step 8: Commit the closed inventory**

```bash
git add docs/design/PG_RUNTIME_CONSUMER_INVENTORY.md \
  docs/design/pg_runtime_inventory \
  docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: close PostgreSQL runtime inventory"
```

Stop for Task 3 review unless a recorded batch ruling applies.

---

### Task 4: Independent reconstruction and inventory admission

**Files:**
- Modify: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: exact Task 3 tip and every tracked inventory ledger.
- Produces: independent admission packet, final docs-only status commit, and a
  review surface from which Fable can reconstruct every set without trusting
  prose.

- [ ] **Step 1: Rebuild from a fresh detached worktree**

Create one detached worktree at exact `CANDIDATE_SOURCE_TIP` for raw candidate
recapture and another at the exact Task 3 tip for authority/projection review.
Copy only the pinned
collection helpers. Write independent review scanner, validator, and projection
tools directly from sections 0.3-0.4; do not copy or import the executor's Task
1-3 tools for the admitted reconstruction. Capture both executor and reviewer
tool hashes so equality cannot be mistaken for independence. Recollect
backend/frontend, rerun static/dynamic/package/encrypted candidate generation,
and rebuild every classification projection from `surfaces.jsonl` into a new
packet root. The executor tools may be rerun as a secondary control only.

- [ ] **Step 2: Compare every artifact byte-for-byte**

Require exact equality for:

```text
backend/frontend/focused node streams
full dynamic route stream
candidate source ledger
candidate adjudication authority
canonical surfaces.jsonl
all projection TSVs
environment package JSON
six disposition partitions
four no-tail path sets
tracked MANIFEST.sha256
candidate-union and projection count/hash reports
```

A prose count match is insufficient.

- [ ] **Step 3: Re-run the safety witnesses**

Verify:

- main and implementation trees are clean;
- no non-doc path changed from
  `729d8514ac912b447f1892aefd3e897ea8a843b6`;
- config key-name/metadata witness is unchanged and contains no RHS value;
- scratch runtime paths remain inside the review packet root, the detached
  worktree has only an empty real `data/` directory, no main `data/`/`.env`
  symlink exists, and no production DB path is reachable;
- no production DB opener, provider request, remote socket connection,
  lifespan, or scheduler process occurred;
- encrypted tracked blobs still match and no plaintext entered artifacts; and
- archive dumps/manifests are byte-identical.

- [ ] **Step 4: Run secret and path leak scans**

Scan every packet/tracked inventory artifact for:

```text
postgres URI credentials
DATABASE_URL values
email addresses
home-directory paths
JWT/API-key patterns
private env lines
encrypted document plaintext excerpts
```

Allowed literal machine operands are only reviewed key names, module names,
repo-relative paths, package names/versions, and bounded paraphrases. A leak is
a stop and packet rejection.

- [ ] **Step 5: Update status without changing authority bytes**

Mark inventory Tasks 0-4 complete, design inventory stage complete, and map
entry `IMPLEMENTATION REVIEW NEXT`. Do not alter canonical inventory rows or
projections during status closeout. Any needed authority edit restarts Task 3
admission.

- [ ] **Step 6: Manifest the admission packet and commit**

Generate packet `SHA256SUMS` using path-byte order, verify every payload, and
record its full hash. Then commit only the four status/evidence docs:

```bash
git add docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: admit PostgreSQL runtime inventory"
```

- [ ] **Step 7: Stop for combined implementation review**

Fable independently rebuilds all candidate sources, exact ledgers, package
provenance, six-way algebra, path sets, and docs-only boundary. No-tail plan
authoring, Task 5 merge, push, product code, `.env` mutation, archive restore,
and remote access remain unauthorized until review GREEN and user ruling.

---

### Task 5: Fast-forward merge and docs-only closeout

**Files:**
- Modify: `docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md`
- Modify: `docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Consumes: Fable GREEN implementation review and explicit user merge
  authorization.
- Produces: exact-master inventory authority and the only allowed handoff to
  PostgreSQL no-tail implementation-plan authoring.

- [ ] **Step 1: Prove linear ancestry and clean boundaries**

Verify `729d8514ac912b447f1892aefd3e897ea8a843b6` is an ancestor of the
reviewed tip, there are no merge
commits, both worktrees are clean, and every changed path is under `docs/`.

- [ ] **Step 2: Fast-forward local master without push**

Use `git merge --ff-only <reviewed-tip>`. Any master drift is a stop and
requires re-grounding; do not force or rebase silently.

- [ ] **Step 3: Rebuild exact-master authority**

In a fresh detached exact-master worktree, rerun Task 4's independent
reconstruction with a new packet name. Every tracked inventory byte, base
stream, projection, partition, path set, and manifest must match the reviewed
tip.

- [ ] **Step 4: Commit docs-only closeout**

Record merged commit, exact-master hashes, packet manifest, review ruling, no
push, and the binding next gate: write the separate PostgreSQL no-tail
implementation plan from this inventory.

```bash
git add docs/superpowers/evidence/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/superpowers/plans/2026-08-15-pg-runtime-consumer-inventory.md \
  docs/superpowers/specs/2026-08-15-pg-runtime-inventory-no-tail-design.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: close PostgreSQL runtime inventory"
```

- [ ] **Step 5: Stop for focused closeout review**

Only after focused closeout GREEN may the inventory branch/worktree be removed
and the no-tail implementation plan begin. No product edit, push, `.env`
cleanup, archive restore, or remote-table action is part of Task 5.

---

## 2. Hard Stop Conditions

Stop immediately and write a bounded docs-only amendment if any condition
occurs:

1. exact base, merge-base, design hash, or product bytes differ;
2. backend or frontend base collection count/hash differs;
3. a tracked path outside `docs/` changes;
4. a test body executes during a collect-only gate;
5. `config/.env` value, hash, excerpt, or RHS enters output/artifacts;
6. a production SQLite path becomes reachable or is opened by an inventory
   process;
7. a provider, remote DB, remote network socket, lifespan, or scheduler is
   started;
8. encrypted paths or blob identities differ from section 0.8;
9. ciphertext search is used as evidence of absence;
10. plaintext from an encrypted document enters the packet;
11. static and dynamic route censuses differ without a classified reason;
12. a candidate from any source is absent from `candidates.jsonl`, has zero or
    multiple adjudications, or a classified candidate ID maps to zero or
    multiple surfaces;
13. a reachable row has no concrete reachability chain;
14. a definition is called unreachable without an uncapped caller census;
15. an actual consumer method is inferred from backend implementation rather
    than measured at call sites;
16. a surface has zero, multiple, or an unknown disposition;
17. any closed partition overlaps another or their union is incomplete;
18. a CLI entrypoint lacks one of the four exact classes;
19. a legacy-agent disposition is turned into a retirement ruling;
20. a current documentation claim is silently edited instead of inventoried;
21. an exact test node is absent from its declared suite stream or has
    conflicting outcome/environment assumptions;
22. frontend byte protection is asserted without completing the frontend
    DTO/status/copy census;
23. predicted delete/modify/add/protected path sets overlap;
24. a predicted added path is not the absent proposed `local_owner` of a
    measured non-empty local capability;
25. a classification projection cannot be regenerated byte-for-byte from
    `surfaces.jsonl` plus `candidate_adjudications.jsonl`, or a named grounding
    stream cannot be independently recaptured;
26. a normalization recipe depends on locale, filesystem order, absolute
    paths, or an omitted trailing-newline rule;
27. the `psycopg2` package source is described as proven manual/transitive
    installation history beyond observable metadata;
28. an archive asset changes or remote archive access occurs;
29. a packet manifest is incomplete or an unmanifested temporary cleanup root
    remains; or
30. implementation proceeds into no-tail, `.env` cleanup, archive restore,
    CLI retirement, merge, or push without its explicit later gate.

## 3. Review Handoff

Independent plan review must reconstruct and judge at least:

1. base backend/frontend streams and pinned helper hashes;
2. 12-importer, 35-DatabaseBackend-path, 175-route, and 21/17-node grounding;
3. sanitized package provenance, including the distinction between observable
   reverse metadata and unknowable installation history;
4. canonical JSONL schema and every closed vocabulary;
5. candidate-source union completeness and closed candidate adjudication;
6. structured route, AST, package, test, CLI, docs, and git-crypt procedures;
7. projection recipes and single-authority discipline;
8. six-way disposition algebra;
9. predicted no-tail path-set rules and frontend decision gate;
10. secret/product/remote/archive safety boundaries; and
11. Task 4 third-party reconstruction and Task 5 merge gates.

Implementation remains blocked until that review is GREEN.
