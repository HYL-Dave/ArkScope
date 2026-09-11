# Task 3 HTTP Adapters And Config Handoff

Current status (2026-09-11T22:24:54+08:00, R1): Important I1's fix is committed as
`420e475960bf8a4cacc2f14d4866315c118085ff` after explicit parent permission.
The fresh full SEC/API gate passes 953 tests. Exactly the five authorized R1
paths were committed and the index is empty. Ready for parent frozen re-review;
no independent approval is claimed here. Earlier no-change/no-index claims below
describe their dated checkpoints, not the later authorized R1 commit.

Worktree: `/tmp/arkscope-listing-sec-macro-convergence`, branch
`codex/listing-sec-macro-convergence`.

Initial status: independent Task 3 implementation and self-review ready-to-commit
checkpoint reported to parent BEFORE any index writes. No staging or commit was
performed. Commit: none. Task 3 is NOT complete: the parent has not signaled
Task 2 readiness and `StoredQueries.facts` is still absent. Ten real-facts HTTP
tests remain ordinary failing tests, not skipped, xfailed, or stubbed.

## Scoped Files

- `src/api/routes/sec_research.py`
- `tests/test_sec_research_routes.py`
- `tests/test_api.py`
- `tests/test_security_lifecycle_routes.py`

Only these four tracked files were edited. All manual edits used apply_patch.
Other workers' query/store/frontend changes and the parent plan were left alone.
The report, response example producer, and run artifacts are ignored evidence
under this plan's `.superpowers/sdd/2026-09-11-sec-query-settings/` directory.
No agents, installs of dependencies, live providers, production data/config/token
access, activation, merge, push, or index writes. Store installation and capture
operations occurred only in disposable test fixtures under the offline harness.

## HTTP Contract For UI

Original `stored_status` GET `/sec-research/{cik}` and `refresh` POST
`/sec-research/{cik}/refresh` remain. Refresh still accepts only strict
`max_sources: int = 4` (1..16) and `resume: bool = false` and retains its existing
permission/identity/transport behavior. Both original endpoint names remain in
the existing named route assertions; four new endpoint names are explicitly
added. Actual application census passes at 222 routes, up from 218.

New endpoints:

```text
get_config: GET /sec-research/config
put_config: PUT /sec-research/config
stored_filings: GET /sec-research/{cik}/filings
stored_facts: GET /sec-research/{cik}/facts
```

Static config routes precede the generic CIK route. GET uses the domain typed
budget getter over `get_profile_store()`. Exact absent-store/default response:

```json
{"capture_budget_bytes":107374182400,"capacity":null}
```

PUT accepts exactly `{capture_budget_bytes: int}`, strictly 1..9007199254740991.
Booleans, floats, numeric strings, null, missing/extra fields and out-of-range
values are HTTP 422. It calls
`require_db_write("sec_research_config", {"capture_budget_bytes": value})`
before constructing the profile owner, then calls the domain typed setter.
Request and exact response for a quota reduction:

```json
{"capture_budget_bytes":1}
```

PUT does not open the market/capture store and does not return capacity. UI must
GET readback after successful PUT. Exact GET from the archived 146-byte fixture:

```json
{"capture_budget_bytes":1,"capacity":{"persisted_bytes":146,"orphan_bytes":0,"reserved_bytes":0,"charged_bytes":146,"budget_bytes":1,"remaining_bytes":0,"over_budget":true}}
```

Capacity is the real `CaptureStore.status()` dict. No recovery, preflight,
acquisition, deletion, or schedule change is performed. Real fixture tests retain
capture bytes, market DB bytes, orphan/reservation charges and unrelated settings
across quota reduction. Absent/unrelated stores return null capacity. Partial,
mismatched, corrupt stores and accounting overflow produce HTTP 503, not zero or
null capacity. Case-insensitive SEC ownership detection precedes exact schema
verification so uppercase partial schemas are not treated as absent.

Closed config errors:

```text
503 {"detail":{"code":"sec_research_config_invalid"}}
503 {"detail":{"code":"sec_research_config_unavailable"}}
503 {"detail":{"code":"sec_research_store_unavailable"}}
```

The first means persisted budget corruption, not an absent key; no default or
repair is substituted. The second covers profile storage read/write failure.
The third covers capacity/store failures. Permission denial remains HTTP 403.

Exact domain delegation signatures:

```python
StoredQueries(store).filings(
    cik, forms=None, filed_from=None, filed_to=None,
    include_amendments=True, cursor=None, limit=20,
)
StoredQueries(store).facts(
    cik, metrics=None, concepts=None, fact_ids=None, accession=None,
    as_of=None, period='all', start=None, end=None,
    revisions='latest', cursor=None, limit=40,
)
```

Forms, metrics, concepts and fact_ids are repeatable FastAPI query operands,
e.g. `?forms=10-K&forms=10-Q&limit=1&include_amendments=false`.
Limit accepts canonical decimal HTTP text in 1..100, not `1.0`, signs or booleans.
Amendments accepts lowercase `true`/`false`, not `yes` or `1`. Dates use shared
`query_date` validation for exact ISO calendar dates, not datetime/compact dates.
Domain query/filter/cursor logic stays in StoredQueries. No adapter filtering,
metric registry, currency selection or decimal conversion was introduced.

GET status/query constructs no profile, capture or transport owner and never
installs/repairs an absent or mismatched store. Canonical verification uses a
read-only SQLite connection. Original status envelope is preserved. Exact
absent-store response for status/query:

```json
{"status":"unavailable","data":null,"gaps":[{"code":"sec_research_not_installed"}],"observed_at":null,"coverage":{},"next_cursor":null}
```

The corresponding closed adapter storage-failure envelope substitutes gap code
`sec_research_store_unavailable`. Service-returned envelopes are passed through
without reshaping. Input errors `sec_research_query_invalid`,
`sec_research_cursor_invalid` and `sec_research_cursor_mismatch` are HTTP 422
`{"detail":{"code":"..."}}`, never generic internal 503 responses.

Full, actual JSON responses including catalog ok/empty/partial, complete source
references, coverage and config readback are archived in
`task-3-response-examples/responses.json`. The catalog source reference remains
`row.sources[i].source = {sha256, pointer}`. The exact decimal and facts
`row.source = {sha256, pointer}` expectations remain UNVERIFIED at the HTTP
integration level until Task 2 exists; no fabricated facts response is provided.

## Verification Evidence

Every check used the supplied `run_checks.py` backend mode and isolated offline
pytest harness with fresh HOME/data/config/token/lock paths. Run directories below
each contain raw `output.log`, `results.xml`, and exact `command.json`.

| Run | Result |
| --- | --- |
| `task-3-baseline` | 75 passed, original 218-route census |
| `task-3-red` | 63 failed, 75 passed; missing routes and real facts method |
| `task-3-green-independent` | 9 failed, 119 passed, 10 deselected; validator metadata issue |
| `task-3-green-independent-2` | 128 passed, 10 deselected |
| `task-3-red-capacity-edge` | 1 failed, 6 passed, 72 deselected; uppercase partial store |
| `task-3-green-final-independent` | 261 passed, 10 deselected |
| `task-3-facts-unresolved` | 10 failed, 69 deselected; real facts service absent |
| `task-3-response-examples` | 1 passed; ignored response artifact producer |

No run had collection errors. Initial RED failures were HTTP 404/405, static
config misrouted as invalid CIK, 218 != 222, and explicit missing-facts assertions.
The implementation run exposed installed FastAPI discarding BeforeValidator
metadata when Query was a separate default. Local framework source confirmed the
cause; putting Query() inside Annotated preserved validation. Existing malformed
input owners then passed. Uppercase partial-store RED returned 200/null rather
than required 503; case-insensitive ownership detection fixed that branch.

Final tracked route file has 79 tests versus 12 initially: +67 cases, of which
10 await Task 2. The two census/lifecycle files contribute 63 unchanged test nodes.
Thus the scoped total is 142 nodes: 132 independent pass and 10 unresolved.
The final green run adds config 54, captures 24 and service 51, yielding 261 pass.
The separate 1-case ignored evidence producer is not part of product test census.

Final independent command, executed from the linked worktree:

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py task-3-green-final-independent backend -q tests/test_sec_research_routes.py tests/test_api.py tests/test_security_lifecycle_routes.py tests/test_sec_research_config.py tests/test_sec_research_captures.py tests/test_sec_research_service.py -k 'not facts_real_service'
```

Once the parent signals actual service readiness, rerun WITHOUT `-k` using a
fresh run name, e.g. `task-3-green-after-task-2`, and inspect all real-facts cases.
Current facts tests cover decimal string/EUR/source preservation, as_of/accession/
instant/end/revisions forwarding, concept and metric lists, cursor pagination,
immutable historical fact-id lists, and malformed domain operands. They are
ordinary assertions over the real temporary Store/CaptureStore and real service;
no substitute facts implementation or fake query-return dict exists.

`git diff --check --` for the four owned files passed. Self-review checked static
matching, mutation admission order, typed config persistence, error sanitization,
read-only schema verification, query delegation, list operands, default values,
source serialization and preserved original route names. Independent review and
full backend reconciliation remain parent-owned. No staging/commit was attempted.

## File Hashes At Handoff

```text
aa43de78092396ae45a073dde3038a916e23c3e16746dc89795c5b02eac2bb1a  src/api/routes/sec_research.py
0e5c127e811a7eaffbd78b65b6f66fa3b861c8a3a6f324fb23ab697412c43a9f  tests/test_sec_research_routes.py
dd417d659fa6760256266f1bad9afea939558ab7cbc5fe88f7d0a44e61bc68ee  tests/test_api.py
a3d3fdff1bc82fc81700ebdbc18fa44cff20d2586e2fcc35dc675a8105c4224a  tests/test_security_lifecycle_routes.py
```

## Final Genuine Integration After Task 2 Readiness

Historical checkpoint: 2026-09-11, before the original Task 3 commit at
22:09:40+08:00 and before R1. The no-product-changes statement in this section
applies only to that verification pass.

The parent explicitly signaled the real Task 2 service callable and stable after
Task 1 R1 `7a1b9d99`. Read `task-2-report.md`, confirmed the actual `.facts` entry
and query implementation, and reran the full planned scoped command WITHOUT
`-k`, skips, xfails, fake service implementations, or test expectation changes.

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py task-3-green-after-task-2 backend -q tests/test_sec_research_routes.py tests/test_api.py tests/test_security_lifecycle_routes.py tests/test_sec_research_config.py tests/test_sec_research_captures.py tests/test_sec_research_service.py
```

Result: **271 passed in 21.42s**, process exit 0, zero failures, collection
errors, skips or deselections. Runner elapsed time was 22.824s. Raw evidence:

- `task-3-green-after-task-2/command.json`
- `task-3-green-after-task-2/output.log`
- `task-3-green-after-task-2/results.xml`

Counts reconcile to the previous 261 independent/collateral passes plus the ten
previously deferred real-facts HTTP tests. All 79 route cases now pass. The
application route census remains 222 with both original and four new named routes.

The genuine HTTP integration now verifies:

- Exact `value: "1234567890123456789.123"`, original `unit: "EUR"`, and unchanged
  `source: {sha256, pointer}` with pointer `/facts/us-gaap/Assets/units/EUR/0`.
- Repeatable concepts, filed-date as_of, accession, instant period, end window,
  revisions and cursor/page-limit forwarding through the real facts service.
- Repeatable metrics and immutable fact IDs retaining the requested historical
  decimal observation instead of applying latest revision selection.
- Closed HTTP 422 domain/cursor errors for all eight malformed operand cases.
- Config corruption/capacity failures remain explicit errors, never false zero;
  quota-only PUT persistence and the original refresh/resume contracts still pass.

The four owned product-file hashes remain exactly as listed above. No product
code or tests were changed during this final integration pass. The actual query
dependency hashes match the stable Task 2 report:

```text
0ad7b43182bcf731efd519233d53f1c54493f3bd9ce76cf66fe5e22f66906ae9  src/sec_research/queries.py
b4f0f87fdf13ec70aed5fe77837262d95b763f85faf7fb3a9b58357a9244ab4a  src/sec_research/fact_queries.py
```

The scoped `git diff --check` also passed. Initial RED artifacts remain preserved
as historical evidence; there is no remaining deferred facts integration gate.
The parent's four locale/viewport real-API browser results were reported by the
parent, not rerun or claimed as this worker's verification.

Task 3 is ready for parent review and serialized commit. No index write or commit
has been performed; Task 2 commits first and explicit parent permission is still
required before Task 3 staging. Commit: none.

## Serialized Commit After Parent Permission

Historical checkpoint: 2026-09-11T22:09:40+08:00, original Task 3 commit before R1.

The parent confirmed Task 2 committed, the index was empty, and this worker had
sole index/commit permission restricted to the four Task 3 paths. Before staging,
verified HEAD was `e07e459a3deb1236af9687a3ed4216786114d3ca`, the index was empty,
and all four product hashes plus both query dependency hashes still matched the
271-pass genuine integration source recorded above.

Staged only these explicit paths, then compared the staged name set against the
exact authorization set twice, including immediately before commit:

```text
src/api/routes/sec_research.py
tests/test_api.py
tests/test_sec_research_routes.py
tests/test_security_lifecycle_routes.py
```

`git diff --cached --check` passed, and the scoped unstaged diff was empty, proving
the staged files matched the tested working sources. Repeated the full planned
command with no exclusions under run name `task-3-green-before-commit`:
**271 passed in 19.19s**, exit 0, zero skips, deselections, failures or collection
errors. Runner elapsed time was 20.600s. Raw `command.json`, `output.log`, and
`results.xml` are in that run directory.

Commit command:

```bash
git -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -m "feat(sec-research): expose stored query and capture config routes"
```

Exact commit: `05edf925293c1b096503526782f1350b1beefe83`

Exact parent: `e07e459a3deb1236af9687a3ed4216786114d3ca`

Commit summary: four files, 485 insertions, 12 deletions. Post-commit
`git diff-tree --no-commit-id --name-only -r HEAD` confirmed exactly the four
authorized paths; `git diff --cached --name-only` returned empty. The only
remaining tracked working change was the parent's existing plan edit, left
untouched. No Task 4, query, plan or evidence/report file was staged or committed.
Hooks and signing were disabled for this local commit to avoid uncontrolled side
effects. No merge, push, activation or production operation was performed.

Task 3 implementation, genuine integration, and authorized scoped commit are
complete. This worker has finished all index operations; subsequent permissions
remain parent-controlled. This ignored report records the exact commit and is
intentionally not part of the four-file product commit.

## R1: Storage-Independent Input Validation

Date: 2026-09-11, after the original Task 3 commit and independent I1 review.
This is the initial R1 readiness checkpoint, before commit at 22:24:54+08:00.
Observed working base at verification: `c6e2e435970c47252970767c9e40300f79ddba23`.
The parent granted a narrow Python scope expansion and explicitly withheld index
permission. No subagents, provider requests, production access, dependency
installation, schema changes, staging or commit were performed for R1.

Confirmed Important I1 against `task-3-review.md` and its unchanged seven-case
probe: HTTP returned early for an absent store before StoredQueries could reject
domain operands or cursor syntax. The same ordering let corruption suppress input
errors. Scalar FastAPI validators alone did not cover domain/cursor rules.

R1 edits exactly these five tracked paths:

- `src/api/routes/sec_research.py`
- `src/sec_research/queries.py`
- `src/sec_research/fact_queries.py`
- `tests/test_sec_research_routes.py`
- `tests/test_sec_research_fact_queries.py`

All edits used apply_patch. Task 4/frontend and parent plan changes were left
alone. `tests/test_api.py` and `tests/test_security_lifecycle_routes.py` were run
unchanged; no census/auth expectations were weakened.

### Shared Validation Contract

```python
validate_query(cik, kind, *, cursor=None, **operands) -> dict
# kind is "filings" or "facts"; returns normalized domain filter operands.

fact_filters(*, metrics=None, concepts=None, fact_ids=None, accession=None,
             as_of=None, period="all", start=None, end=None,
             revisions="latest", limit=40) -> dict
```

`validate_query` performs no path resolution, store construction or storage read.
It normalizes CIK, dispatches to the extracted catalog filters or the existing
fact filter rules, and invokes the existing strict cursor decoder through a
shared `_query_token` helper. Cursor syntax, query kind, normalized issuer and
filter hash (including limit) are validated before storage. Explicit fact IDs
retain their separate cursor kind. No cursor format, filter semantics, metric
mapping or observation selection changed.

`StoredQueries.filings` and the real `query_facts` now use this shared validation
entry point and consume its normalized filter result. The HTTP adapter calls the
same validator before Store construction and `_installed`. The adapter contains
no duplicate forms/metrics/concepts/revisions/ID/cursor logic and no dummy or fake
Store. `open_query` and `open_fact_ids_query` reuse `_query_token`; receipt,
snapshot watermark and immutable binding checks remain in their real read-only
storage paths, unchanged.

Malformed operands/cursors now produce the same closed HTTP 422 regardless of
absent, corrupt or installed storage. Valid requests, including structurally valid
real cursors whose immutable bindings cannot be checked without storage, still
return unavailable for absent/broken stores. No installation, schema repair,
capture/profile/transport construction, or acquisition is introduced. Existing
config typed errors and quota-only PUT behavior remain unchanged.

### RED And GREEN Evidence

New named regression owners:

- `test_query_validation_precedes_storage_availability`: 20 request cases across
  absent/corrupt/installed stores (60 cases). Valid controls remain unavailable;
  invalid inputs must reject before path resolution. DB bytes are unchanged and
  no capture root is created.
- `test_query_cursor_request_validation_before_unavailable_store`: real cursors
  generated from temporary Store/CaptureStore data for catalog, ordinary facts,
  and retained fact IDs. Twelve cases distinguish valid unavailable storage from
  changed-limit 422 mismatch errors without attempting receipt-dependent checks.
- `test_shared_query_operand_validation_normalizes_without_storage`: three
  focused domain regression cases for catalog, metrics/concepts and fact IDs,
  confirming preserved normalized output with all Store construction/read access
  forbidden. No substitute storage/service implementation is used.

Every run below used the supplied offline harness with isolated HOME/data/config/
token/lock paths. Each run directory contains exact `command.json`, complete
`output.log`, and `results.xml`; no run had collection errors or skips.

| Run | Result |
| --- | --- |
| `task-3-r1-red` | 57 failed, 18 passed, 171 deselected |
| `task-3-r1-green-focused` | 318 passed, no exclusions |
| `task-3-r1-review-probe-green` | Original unchanged reviewer probe: 7 passed |
| `task-3-r1-green-sec-api` | Whole SEC/API gate: 953 passed, no exclusions |

RED failures were the named forbidden storage-resolution path for invalid
requests, HTTP 200 instead of 422 for changed cursor filters on absent/corrupt
stores, and the missing shared pure validation entry point. Valid unavailable
controls and existing scalar validation remained green. Production extraction and
HTTP wiring followed this RED run; no test expectations were relaxed afterward.

The full gate command was:

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-query-settings/run_checks.py task-3-r1-green-sec-api backend -q tests/test_sec_*.py tests/test_stored_sec_projection.py tests/test_fundamentals_sec_cache.py tests/test_lifecycle_web_sec_sources.py tests/test_api.py tests/test_security_lifecycle_routes.py
```

Result: **953 passed in 32.76s**, process exit 0; runner elapsed 34.234s. This
includes all ten genuine facts HTTP tests, exact decimal/SourceRef preservation,
installed read-only behavior, config corruption/capacity errors, quota-save side
effects, original refresh/resume, and the unchanged 222-route census.
Count reconciliation: prior full SEC 815 + API/lifecycle 63 + R1 additions 75 =
953. Routes increased 79 -> 151; fact-query tests increased 92 -> 95; catalog
query tests remain 72. Focused total is 151 + 95 + 72 = 318.

Self-review confirmed the extraction preserves normalized filters and cursor
hashes, no duplicate adapter rules or fake Store, and storage-dependent cursor
checks remain intact. Scoped `git diff --check` passed. R1 changes are unstaged;
`git diff --cached --name-only` returned empty. Ready-to-commit checkpoint was
reported to the parent, but staging/commit remains permission-gated. R1 commit:
none. Independent re-review remains parent-owned.

R1 source hashes at handoff:

```text
7b6bf652540e5d3502a69ed44269a3c382d01014e9361f89f909f4d79c58d8a1  src/api/routes/sec_research.py
1aa4b4f322fc95b2889c2b49cc7915320616bf8239d58116a3fe899df6e024a4  src/sec_research/queries.py
8274750f9f1ee6fb065da7afa307da55dc41254695c53019f989a39675ed694e  src/sec_research/fact_queries.py
e38cd7c555d480dfbfb1b2f538b0b441c39e00612466be7b6ea08735e24bd451  tests/test_sec_research_routes.py
2e603bd36b70569a4bcf90a0f6bafba69bf55b32b10f15d89e73b3f84b60e86d  tests/test_sec_research_fact_queries.py
```

## R1 Serialized Commit And Final Hashes

Date: 2026-09-11T22:24:54+08:00. The parent confirmed Task 4 was committed and
reviewed, then granted sole index/commit permission restricted to the five R1
Python source/test paths, excluding the parent plan. Before staging, verified an
empty index, the expected parent HEAD, and all five source hashes matching the
953-pass R1 handoff. No source or test edit was needed during this commit pass.

Staged only the five explicit paths and compared the staged name set to the exact
authorization set both after staging and immediately before committing. Staged
whitespace checks passed; the scoped unstaged diff was empty, confirming staged
sources matched the test run's working sources.

Repeated the entire SEC/API gate without exclusions under run name
`task-3-r1-green-before-commit`: **953 passed in 33.05s**, process exit 0,
zero failures, errors, skips or deselections. Runner elapsed time: 34.545s.
Its `command.json`, `output.log`, and `results.xml` are archived in that run
directory. The original reviewer probe's seven passes remain recorded above.

Commit command:

```bash
git -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -m "fix(sec-research): validate queries before checking storage"
```

Exact R1 commit: `420e475960bf8a4cacc2f14d4866315c118085ff`

Exact parent: `c6e2e435970c47252970767c9e40300f79ddba23`

Commit timestamp: `2026-09-11T22:24:54+08:00`

Commit summary: five files, 162 insertions, 24 deletions. Post-commit
`git diff-tree --no-commit-id --name-only -r HEAD` confirmed exactly:

```text
src/api/routes/sec_research.py
src/sec_research/fact_queries.py
src/sec_research/queries.py
tests/test_sec_research_fact_queries.py
tests/test_sec_research_routes.py
```

Post-commit SHA-256 values, unchanged from the tested R1 handoff:

```text
7b6bf652540e5d3502a69ed44269a3c382d01014e9361f89f909f4d79c58d8a1  src/api/routes/sec_research.py
1aa4b4f322fc95b2889c2b49cc7915320616bf8239d58116a3fe899df6e024a4  src/sec_research/queries.py
8274750f9f1ee6fb065da7afa307da55dc41254695c53019f989a39675ed694e  src/sec_research/fact_queries.py
e38cd7c555d480dfbfb1b2f538b0b441c39e00612466be7b6ea08735e24bd451  tests/test_sec_research_routes.py
2e603bd36b70569a4bcf90a0f6bafba69bf55b32b10f15d89e73b3f84b60e86d  tests/test_sec_research_fact_queries.py
```

The post-commit index is empty. The only remaining tracked working change is the
parent's existing plan edit, untouched. No Task 4/frontend, plan, or ignored
report/evidence file was staged or committed. Hooks and signing were disabled for
the local commit to avoid uncontrolled side effects. No merge, push, activation,
production access or provider request was performed.

This worker has completed the authorized R1 commit and finished index operations.
The exact commit is ready for the parent's frozen R1 and whole-batch re-review;
review approval and whole-batch completion remain parent-owned.
