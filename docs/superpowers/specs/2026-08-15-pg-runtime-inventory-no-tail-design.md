# PostgreSQL Runtime Inventory and No-Tail Program Design

> **Status:** USER-APPROVED SECTIONS 1-4; WHOLE-DOCUMENT REVIEW NEXT;
> DESIGN ONLY; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-15
>
> **Grounding base:** `360fff3815ffc2fee71664e7a8954fb2717c92e6`

## 1. Decision and Product Direction

### 1.1 Problem

ArkScope completed the product-data move from PostgreSQL to local SQLite, and
the remote PostgreSQL instance was stopped in July 2026. The repository still
contains executable PostgreSQL surfaces, however:

- normal application construction can still inspect `DATABASE_URL` and create
  a `DatabaseBackend`;
- the production FastAPI app still mounts PostgreSQL migration preview/apply
  routes;
- local backends still inherit PostgreSQL classes to satisfy historical
  `isinstance(DatabaseBackend)` gates;
- scheduler startup probes PostgreSQL before reading a store that is already
  local;
- PostgreSQL store classes, connection helpers, mixed local/PG branches, and a
  Python dependency remain importable; and
- the current no-PG smoke disables the scheduler and checks a hand-written
  route list, so its GREEN result does not cover these surfaces.

This is a runtime ownership problem, not a data-migration problem. Local stores
already own current product data. Frozen PostgreSQL dumps own archive history.
Keeping an executable Python PostgreSQL compatibility layer between those two
authorities creates no product capability and continues to burden startup,
tests, dependencies, documentation, and future architecture work.

The project's early CLI-first direction is no longer a preservation
constraint. The primary product is the desktop research workbench. A command
survives only when it still owns a current operator capability, not merely
because it is a CLI or because historical callers once existed.

### 1.2 Selected program

The approved sequence is binding:

1. **PostgreSQL consumer inventory** - a docs-only, mechanically
   reconstructable census of every remaining runtime, test, dependency,
   command, and documentation surface.
2. **PostgreSQL runtime no-tail** - remove all Python PostgreSQL executable
   surfaces and route every retained product consumer through measured local
   capabilities.
3. **Legacy-agent CLI census** - inventory and classify the old interactive
   agent CLI immediately after no-tail. The census completes even if the user
   is not yet ready to decide its retirement.
4. **Runtime-owner and CSS boundary work** - follow with the already queued
   ownership cleanup, including EIR-001 dead CSS and the schedule-read test
   hardening debt.

No ordinary feature line may be inserted between these stages. A genuine P0
incident may interrupt the sequence under the existing stop-the-line policy.

The legacy-agent CLI retirement plan is separately gated by a user product
ruling because its behavior may overlap the unstarted Investment Skills Track
B and possible skill/Discord integration. Inventory does not force that
ruling. Insufficient information after the census is an explicit completed
handoff state, not evidence that the CLI must be kept or removed.

### 1.3 End-state architecture

Normal runtime:

```text
Desktop / FastAPI / scheduler / retained operator command
                           |
                           v
                  DAL and domain services
                           |
                           v
              measured local capability contracts
                           |
                           v
        profile_state.db / market_data.db / sa_capture.db /
                       macro_calendar.db
```

Archive inspection:

```text
tracked dump + manifest
          |
          v
pg_restore into an isolated scratch PostgreSQL database
          |
          v
psql verification / inspection
          |
          v
drop the scratch database
```

These flows do not share Python code, runtime configuration, dependencies, or
credentials. The archive surface consists only of:

- `docker/` scratch-restore infrastructure;
- `sql/` schema lineage needed by archive restore;
- tracked dumps and manifests under `data/pg_archive/`; and
- concise operating and historical documentation.

There is no retained Python archive CLI, `DatabaseBackend`, PostgreSQL store,
runtime probe, migration API, or importable compatibility shim. Git history is
the source for recovering retired implementation if a future reviewed design
needs it.

### 1.4 Grounded current facts

The following observations are dated grounding for the inventory. They are
not substitutes for its final ledgers:

1. Root `README.md` says the runtime needs no database server, while live code
   still contains reachable PostgreSQL construction and migration routes. The
   product outcome is directionally true; the runtime-code claim is too broad.
2. `src/api/app.py` mounts `src/api/routes/app_records.py`, whose migration
   preview/apply routes reach the PostgreSQL migrator.
3. `src/api/dependencies.py` constructs `DataAccessLayer(db_dsn="auto")`.
   That mode can inspect `DATABASE_URL` and instantiate a PostgreSQL backend.
4. Local backends inherit PostgreSQL-backed classes to pass historical type
   checks. These inheritance relationships are compatibility debt, not local
   capabilities.
5. Scheduler startup calls a PostgreSQL reachability probe before consulting
   `get_job_runs_store()`, although that factory returns the local
   `JobRunsLocalStore`. With the remote instance stopped, the probe suppresses
   an otherwise usable local job-history supplement and can make a source run
   one interval early after restart.
6. PostgreSQL `JobRunsStore` and `MacroCalendarStore` classes remain even
   though normal factories select their local replacements.
7. Mixed SA, fundamentals, freshness, and tool modules contain PostgreSQL
   branches that require consumer-by-consumer classification.
8. `requirements.txt` still declares a PostgreSQL driver while current source
   imports use a different driver family. The inventory must measure both
   dependency declarations and imports instead of assuming either is
   authoritative.
9. `tests/test_db_backend.py` currently carries a substantial PostgreSQL-only
   node family, including tests conditional on a local `.env` DSN. Removing
   those tests changes canonical collection identity and retires the temporary
   `.env` symlink dance used by prior native admissions.
10. The current `pg_unreachable_e2e` smoke sets
    `ARKSCOPE_DISABLE_SCHEDULER=1` and checks a manually selected route list.
    It therefore does not prove the intended final runtime property.
11. The app-record archive
    `data/pg_archive/app_records_20260706T121127Z/app_records.dump` is paired
    with a manifest whose recorded SHA-256 is
    `486f6fae01519794405d88b7180188b615e5dfb7c094bf6071f0853e11ab0e92`.
    Its reviewed row counts are `agent_queries=2`, `research_reports=2`, and
    `agent_memories=1`.
12. `docker/README.md` already documents a two-stage scratch restore with
    standard PostgreSQL tools. The no-tail line verifies this path instead of
    adding a custom Python reader.
13. The private `config/.env` currently has a PostgreSQL DSN key. Its value is
    outside repository evidence and must never be printed, copied, hashed into
    an artifact, or committed.

### 1.5 Scope boundaries

This program does not:

- migrate current product data between SQLite databases;
- change product records, the 491,808 historical score-row research decision,
  or any other production table;
- call a provider or remote PostgreSQL service;
- physically delete the three remote app-record archive tables;
- delete or rewrite tracked archive dumps;
- add a Python archive inspection utility;
- redesign all DAL/domain interfaces;
- retire the legacy-agent CLI before its separate census and user ruling;
- remove current operator commands merely because they are command-line
  programs; or
- implement the later runtime-owner/CSS work.

Physical deletion of the three remote archive tables remains a separate,
explicitly approved operation. The remote instance may need to be started for
that operation; this design grants no such access.

## 2. PostgreSQL Consumer Inventory

### 2.1 Purpose and authority

The inventory is the first implementation slice and is docs-only. It creates
the authoritative input for the later no-tail plan. It neither edits product
code nor presumes that a symbol is dead because a quick search found no caller.

Every final set, count, and digest must be reconstructable from literal rows
in the committed inventory. Dated counts in this design and older PG-exit
documents are grounding clues only and cannot be used for admission.

### 2.2 Required row schema

Each discovered surface receives one row with these fields:

| Field | Meaning |
|---|---|
| Path and symbol | Exact tracked path plus class, function, route, command, dependency, test node, or claim |
| Reachability | How current runtime, startup, a route, scheduler, test, or operator reaches it; `none` must be evidenced |
| PostgreSQL capability | Connection, query, write, probe, migration, inheritance, type gate, dependency, or documentation claim |
| Local replacement | Existing local owner, or `none` when the capability retires |
| Actual methods used | Consumer-observed method set; this is the only input to a minimal local capability interface |
| Tests and environment | Exact owning node IDs plus DSN, package, scheduler, route, or fixture assumptions |
| Disposition | Exactly one closed value from section 2.3 |
| Follow-up owner | No-tail, legacy-agent census, archive/history, or a named future slice |
| Stop condition | Concrete fact that would invalidate the disposition |

A row cannot use vague values such as `maybe`, `probably dead`, `cleanup`, or
`future`. An unresolved reachability question is a stop-and-amend event, not a
seventh disposition.

### 2.3 Closed disposition vocabulary

The only admitted disposition values are:

1. `retire_pg_only` - the capability exists only to reach PostgreSQL and has no
   current product owner.
2. `rewrite_to_local_capability` - a current product consumer remains, but its
   PostgreSQL construction, inheritance, or type gate is replaced by the
   measured local capability it actually uses.
3. `retain_operator_remove_pg_branch` - the current operator command remains,
   while its PostgreSQL-only branch and configuration retire.
4. `retain_archive_asset` - non-Python dump, manifest, SQL lineage, Docker
   restore infrastructure, or archive operating documentation remains.
5. `historical_reference` - a dated statement remains only as history and must
   not be read as current runtime authority.
6. `defer_to_legacy_agent_cli_census` - the surface belongs to the later
   legacy-agent product census and cannot be retired in no-tail.

`pg_unreachable_e2e` uses
`retain_operator_remove_pg_branch`. Its row names the no-tail slice as owner
and records its transformation into a new no-PG admission gate. No additional
disposition is needed.

### 2.4 Mandatory census surface

The inventory must cover all of the following from an unlocked, clean tree:

1. Every `psycopg`, `psycopg2`, SQLAlchemy PostgreSQL, and equivalent driver
   import or optional import.
2. Every PostgreSQL package declaration, lockfile entry, container dependency,
   and test-only dependency.
3. Every `DatabaseBackend` constructor, subclass, re-export, protocol use,
   `isinstance`/`issubclass` check, and method reference.
4. Every `_get_conn`, `db_dsn`, `DATABASE_URL`, SSL option, reachability probe,
   and PG-specific environment setting.
5. Every FastAPI route, lifespan hook, dependency, scheduler path, factory, and
   startup branch that can reach a PostgreSQL surface.
6. Every PostgreSQL store, migrator, smoke, audit, archive helper, SQL file,
   dump, and manifest.
7. Every test node that is PostgreSQL-only, conditionally activated by a DSN,
   or asserts historical PG fallback or inheritance behavior.
8. Every command-line entrypoint, classified independently as `PG-only`,
   `mixed`, `operator`, or `legacy-agent`.
9. Every product document that claims PostgreSQL is absent, available,
   required, a fallback, or archive-only. At minimum, this includes the root
   README and current PG-exit authority documents.
10. Every frontend DTO, status projection, copy branch, and test that still
    represents PostgreSQL availability, fallback, migration, or exit state.
11. The exact methods current consumers invoke on PostgreSQL-derived classes.
    That measured set, not speculative architecture, defines the maximum
    allowed local capability extraction in no-tail.

Repository searches must be uncapped and include dynamically imported and
string-registered surfaces. Text search over locked git-crypt ciphertext is
never evidence of absence. The inventory must verify tracked encrypted blobs
against the implementation base, then read their plaintext from an unlocked
main tree where applicable.

### 2.5 Required mechanical ledgers

The committed inventory includes literal, globally UTF-8 byte-sorted ledgers
for:

- all in-scope paths;
- all PostgreSQL symbols and imports;
- all executable routes and startup hooks;
- all inheritance and runtime type checks;
- all dependency declarations;
- all exact test node IDs and their current pass/skip/conditional state;
- all CLI entrypoints and four-way labels;
- all current product documentation claims;
- all measured consumer method sets;
- each of the six disposition partitions;
- predicted no-tail deletion, modification, addition, and protected sets; and
- canonical backend, frontend, and focused collection identities at the exact
  inventory base.

Each ledger records count, full SHA-256, normalization recipe, and one trailing
newline rule. Aggregate hashes must include a literal command or an equivalent
byte-exact recipe. A reviewer must be able to rebuild every identity without
guessing line order, path prefixes, separators, or whether a hash is over
content or filenames.

### 2.6 Safety boundary

Inventory work is read-only with respect to product state:

- no source, test, dependency, runtime configuration, or product code changes;
- no provider or remote database connection;
- no production SQLite write;
- no secret value read or artifact capture;
- private `.env` evidence is limited to path existence, key-name presence, file
  metadata, and a non-secret tracked/untracked classification;
- no `git-crypt` ciphertext search used as an absence claim; and
- no old GREEN smoke or collection report promoted to final no-tail evidence.

### 2.7 Inventory completion gate

The inventory is complete when a third party can reconstruct every set and
digest from the committed document, every row has exactly one disposition,
all partitions are closed and disjoint, every current consumer method is
accounted for, and no executable surface remains classified by assumption.

Completion of the inventory authorizes writing the no-tail implementation
plan. It does not authorize product deletion by itself.

## 3. PostgreSQL Runtime No-Tail Design

### 3.1 Minimal local capability rule

No-tail may introduce a capability interface only when the inventory proves a
retained consumer currently relies on methods inherited from or gated by a
PostgreSQL class. The interface contains exactly the observed methods required
to remove that dependency. It must not redesign a domain store, merge stores,
invent future methods, or normalize unrelated ownership.

If the measured method set implies a larger architectural redesign, execution
stops. That work belongs to the later runtime-owner line; no-tail retains only
the smallest bridge needed to remove PostgreSQL cleanly.

### 3.2 Runtime construction

After no-tail:

- normal DAL construction is local-only;
- `DATABASE_URL` cannot influence backend selection;
- no ignored DSN parameter remains on local constructors;
- no local class inherits a PostgreSQL class;
- no product code performs `isinstance(DatabaseBackend)` or equivalent type
  routing;
- no compatibility alias, tombstone class, or re-export preserves the old
  import surface; and
- local missing/corrupt state follows each domain's reviewed honest-empty or
  typed-unavailable contract, never a PostgreSQL or generic file fallback.

Historical callers are not a reason to keep ignored parameters or aliases.
Any unmeasured current caller is a stop-and-amend event.

### 3.3 Executable surface retirement

No-tail removes:

1. the mounted app-record migration preview/apply routes;
2. the PostgreSQL migrator and its PG-only tests;
3. `DatabaseBackend` and PostgreSQL-derived store classes after all consumers
   have moved to measured local capabilities;
4. PG-only connection helpers, DSN loading, SSL options, probes, factories,
   inheritance, type gates, and re-exports;
5. dead PG branches from retained mixed/operator modules;
6. PostgreSQL Python dependencies and their lockfile entries when the final
   import census reaches zero; and
7. product documentation that presents executable PG fallback, migration, or
   runtime archive access as current behavior.

Pure helpers embedded in a retiring module may move to a neutral local module
only when the inventory proves a retained consumer. Copying an entire class or
module to preserve hypothetical reuse is forbidden.

### 3.4 Scheduler restart continuity

The PostgreSQL reachability probe in scheduler seeding retires. Restart state
is derived in this order:

1. read durable local `scheduler_state`;
2. for any source still missing state, consult local `JobRunsLocalStore`
   unconditionally;
3. derive the admitted last-attempt/last-result facts from local history; and
4. leave the source due only when neither local authority provides a value.

There is no network probe. A dedicated RED-first owner must prove that a source
with no `scheduler_state` row but a qualifying local job-history row is seeded
from that history and does not fire one interval early. Removing that local
supplement must be caught by mutation.

### 3.5 New no-PG admission gate

The transformed no-PG gate must run in an isolated environment where no
PostgreSQL Python driver is installed or importable. It must:

1. import the real application and execute the real FastAPI lifespan;
2. start the real scheduler without `ARKSCOPE_DISABLE_SCHEDULER=1`;
3. use sealed provider fakes and scratch local SQLite stores;
4. enumerate the real `app.routes` dynamically rather than compare a
   hand-written allowlist;
5. prove the migration preview/apply routes are absent;
6. complete startup seeding and at least one provider-free scheduler tick;
7. fail if any PostgreSQL package import, DSN read, socket probe, backend
   construction, or fallback occurs; and
8. leave no process, file descriptor, temporary database, environment link, or
   runtime directory behind.

A static repository census accompanies the runtime gate. Its only exclusions
are named archive assets and named historical documents from the inventory.
Pattern-wide exclusions such as all `docker/`, all `docs/`, or all `sql/` are
not accepted unless every excluded path is enumerated and classified.

### 3.6 Error behavior

Deleting PostgreSQL must not turn availability errors into false success.
Retained local domains preserve their existing reviewed contracts:

- missing optional data remains honest empty only where that domain already
  defines empty as valid;
- missing, corrupt, locked, or incompatible local state remains a typed local
  failure where required;
- no PostgreSQL retry or fallback is attempted;
- no `FileBackend` or generic fallback substitutes a different authority; and
- broad exception swallowing is not introduced to keep old tests GREEN.

### 3.7 Archive capability proof

No-tail preserves archive access through standard tooling and proves it before
closeout:

1. verify the tracked app-record manifest and dump SHA before restore;
2. start an isolated scratch PostgreSQL instance with archive-only
   credentials, distinct from any app runtime configuration;
3. restore
   `data/pg_archive/app_records_20260706T121127Z/app_records.dump`;
4. query the restored tables with `psql` and verify exactly
   `agent_queries=2`, `research_reports=2`, and `agent_memories=1`;
5. record schema/table sanity without exposing row contents or credentials;
6. drop the scratch database and stop/remove the scratch instance; and
7. prove no archive process, volume created for the proof, credential file, or
   port remains.

The no-tail evidence pins the final commit that still contains the Python
PostgreSQL executable surface. This makes historical source recovery explicit
without retaining importable code. The hash is measured at cutover and must
not be guessed in this design.

### 3.8 Configuration and destructive boundaries

After merged closeout, the user may remove the `DATABASE_URL` entry from the
private `config/.env`. This is an operator step, not a tracked commit. The
procedure checks only that the key is absent afterward, never prints or
records its value, and reminds the user to restart the desktop app/sidecar.

Archive scratch credentials remain local to the Docker restore workflow and
must not reuse application runtime configuration.

Deletion of the three remote archive tables is excluded. It requires a
separate manifest, explicit user authorization, remote-instance lifecycle
handling, and its own pre/post verification.

## 4. Execution, Verification, and Handoff

### 4.1 Phase ordering

The no-tail implementation plan must preserve this dependency order:

1. **Cut retained consumers to measured local capabilities.** PostgreSQL
   classes may temporarily remain on disk, but no product path may reach them.
2. **Retire executable routes and branches.** Remove migration APIs, migrators,
   probes, and PG-only branches; land the scheduler local-history fix.
3. **Delete PostgreSQL foundations.** Remove classes, connection helpers,
   dependencies, re-exports, PG-only tests, and compatibility inheritance only
   after they are dead.
4. **Transform admission and documentation.** Replace the old smoke, prove the
   archive restore, correct current runtime claims, pin the last PG-surface
   commit, and close the line.

This ordering keeps each deletion reviewable and ensures later removals are
dead-code removal. Phase 1's temporary presence of unreachable PostgreSQL
classes is an admitted intermediate state, not the final architecture.

### 4.2 RED-first and evidence discipline

Each phase starts with exact owner tests that fail for the intended missing
contract, then lands product and evidence commits separately. Commits are not
squashed. Every stage records:

- exact before/after collection streams and full SHA-256 values;
- retired, added, evolved, protected, and survivor ledgers;
- focused and collateral runtime transcripts;
- source and generated-artifact manifests;
- rejected attempts labelled as rejected rather than folded into GREEN; and
- product owner pre/post hashes for mutation restoration.

Any unlisted consumer, route, test node, dependency, documentation authority,
or product path is a stop-and-amend event. Deleting code to force a planned
count or weakening a test to preserve an old identity is forbidden.

The no-tail implementation plan must recompute the canonical backend identity
after the inventory. It must account explicitly for the large retirement of
PG-only tests, including the current conditional `test_db_backend.py` family.
Frontend behavior is expected to remain unchanged, but byte identity is not
asserted before inventory closes: any live PostgreSQL DTO, status, copy, or
test contract must be listed and assigned an exact bounded delta. If inventory
finds no such required consumer, the frontend tree becomes byte-protected.
Any frontend change outside that post-inventory ledger is a stop event.

### 4.3 Required mutation families

At minimum, the final tree must kill these independently restored mutations:

1. restore `DATABASE_URL`-driven backend selection;
2. remount either app-record migration route;
3. restore a local class's PostgreSQL inheritance or runtime type gate;
4. restore the scheduler PostgreSQL reachability probe;
5. restore a PostgreSQL package import or dependency;
6. restore a PostgreSQL branch in a retained mixed/operator command;
7. make product `src/` import archive-only tooling; and
8. remove the local job-history supplement from scheduler restart seeding.

Each mutation changes active semantics, names its owning node, makes that owner
RED, starts from a clean exact tip, and restores the complete owner file
byte-for-byte. A mutation in dead text or an owner that stays GREEN is rejected
evidence.

### 4.4 Final admission

No-tail admission requires all of the following on a fresh exact-tip worktree:

1. final backend collection identity and native pass/skip/fail counts match the
   implementation plan's post-inventory ledger;
2. all retained domain, scheduler, API, DAL, operator, and no-PG focused suites
   pass;
3. frontend collection and product bytes match the post-inventory contract:
   byte-identical when no live PG contract exists, otherwise exactly the
   reviewed bounded ledger;
4. no PostgreSQL Python driver is installed in the no-PG gate environment;
5. no product Python import, dependency, constructor, route, probe,
   inheritance, type gate, DSN branch, or fallback survives;
6. the real FastAPI lifespan and scheduler start and complete the bounded local
   gate without a PG-disable flag;
7. dynamic route census contains no migration route;
8. scheduler restart continuity uses local history when scheduler state is
   absent;
9. scratch product databases and sealed provider fakes prove zero provider,
   remote database, and production-data contact;
10. the real app-record archive restore and exact count proof in section 3.7
    succeeds; and
11. all temporary environments, links, processes, databases, ports, and
    artifacts are manifested and cleaned.

The old native `.env` symlink procedure is not part of final admission. A
remaining need for it means PostgreSQL test/runtime behavior survived and the
gate fails.

### 4.5 Documentation truth

No-tail updates current product authority to state the precise end state:

- normal application runtime is local-only and has no PostgreSQL Python
  dependency or executable fallback;
- PostgreSQL exists only as an external scratch tool for inspecting tracked
  archives;
- migration preview/apply is no longer a product route;
- current operator commands are listed by actual supported capability; and
- historical documents remain historical and cannot be read as current
  instructions.

The inventory decides which old documents are corrected, retained as dated
history, or retired. Documentation edits do not silently rewrite historical
execution evidence.

### 4.6 Legacy-agent CLI handoff

Immediately after the no-tail closeout, a docs-only legacy-agent CLI census
starts from the exact merged master. It receives the inventory's four-way
entrypoint map and records:

- each command and subcommand;
- every current product, operator, test, documentation, skill, or Discord
  consumer;
- overlap with the desktop workbench and future Track B;
- unique capability that would be lost by retirement;
- dependency and maintenance cost; and
- a recommendation with explicit uncertainty.

The census itself is required and does not need a Track B decision. Writing or
executing a retirement plan requires a later user ruling. If the evidence is
insufficient, the census closes with that explicit result and the sequence may
continue.

### 4.7 Later runtime-owner/CSS line

After the CLI census handoff, the queued runtime-owner/CSS line may begin. It
owns broader runtime composition, operator ownership, EIR-001 dead CSS, and
the known load-sensitive shared schedule-read test. Those concerns must not be
pulled backward into PG no-tail unless they are strictly necessary to remove a
measured PostgreSQL dependency.

## 5. Acceptance

This design is satisfied only when:

1. the inventory is independently reconstructable, docs-only, and closed over
   every executable, test, dependency, CLI, and current documentation surface;
2. the no-tail implementation leaves no Python PostgreSQL runtime or archive
   executable surface;
3. every retained product consumer uses only measured local capabilities;
4. real app startup and scheduler execution succeed with no PostgreSQL package,
   DSN, probe, route, fallback, or disable flag;
5. scheduler restart continuity is proven against local job history;
6. standard `pg_restore`/`psql` tooling restores and verifies the tracked
   app-record archive in an isolated scratch environment;
7. product and archive credentials remain separate and secret values never
   enter evidence;
8. remote archive-table deletion remains unexecuted and separately gated;
9. the legacy-agent CLI census begins as the binding next product-analysis
   slice, with retirement still gated by user ruling; and
10. the runtime-owner/CSS line remains the next ordinary implementation line
    after that handoff.

## 6. Supersession and Authorization

This design narrows and supersedes older statements that accepted importable
PostgreSQL compatibility classes, migration routes, DSN-driven construction,
or a Python PG archive layer after product data became local. It does not
invalidate historical migration evidence, tracked dumps, SQL lineage, or
already reviewed local-store contracts.

Approval of this design authorizes only:

1. committing this docs-only design and its priority-map status entry;
2. independent whole-document review; and, after that review is GREEN,
3. writing and executing the docs-only PostgreSQL consumer inventory under its
   own exact plan and stop conditions.

It does not authorize no-tail product edits, merge, push, provider traffic,
remote PostgreSQL access, production database mutation, private `.env`
mutation, remote archive-table deletion, legacy-agent CLI retirement, or the
runtime-owner/CSS implementation.
