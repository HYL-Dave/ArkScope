# Final Whole-Plan Integration Review

## Verdict

**No actionable findings. Approved for the scoped durable structured-acquisition
integration, subject to the parent's outstanding full-suite and evidence-sealing
gates.** No source/test change or source-freeze invalidation is requested.

This is a source/integration approval, not a completed release gate, an exhaustive
security audit, production activation approval, or completion of the full SEC
research feature. The parent-owned full backend execution was still incomplete
when checked for this report. Its final result is not inferred from collection,
the earlier 200-case run, or this review's focused passes.

## Scope And Identity

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base: `737f438dbec232443f7c4bdb15a2158495fdd233`.
- HEAD: `562e105b64ceaaed43bdf8b6448afeb2f1a463e4`, plus the current
  intent-to-add working diff, not HEAD alone.
- Reviewed all 12 changed source/test paths, **2,583 added lines**, plus the
  durable-acquisition plan, issue-register addition and cleanup-audit addition.
  The complete base comparison contained 15 paths and 2,812 added lines.
- Read the linked `2026-09-10-sec-research-substrate-design.md` for the approved
  storage, provenance, coverage, capacity and explicit-command boundaries.
  Historical `30bb31c7..737f438d` implementation was not re-reviewed wholesale.
  Unchanged dependencies were inspected only to establish current contracts.
- Source/test/data_sources patch SHA256:
  `452c30f1111a28a29457ef646578a8680ffeb1487e5cb6c69434c3fb80e8030c`.
  All **794** paths in `source-before.json` matched before and after verification;
  the patch digest matched too. No existing source/test path was changed here.
- Parent edits to plan completion checkboxes occurred during review. The plan's
  implementation boundary was unchanged; documentation is not claimed frozen
  by the source manifest. Final publication wording remains parent-owned.

The original Task 1 review/report including its fix append, Task 2 review/fix
report/re-review, and Task 3/4 review plus stored-route addendum were inspected.
The GET addendum is now approved, not still in progress. Their conclusions were
used as evidence and checked against live source, not reflexively repeated as
new findings or treated as substitutes for this integration review.

## Cross-Module Checks

| Boundary | Counterexample Checked And Result |
| --- | --- |
| Schema/store/capture ownership | Capture SQL consumes exactly the three canonical shared tables. Explicit installation verifies owned definitions transactionally without altering unrelated tables. Snapshot and observation publication requires registered, matching source hashes. Shape mismatch is not silently repaired. |
| Original bytes and exact facts | Service consumes `SecResponse.body`, parses the whole source, retains bytes through CaptureStore, then publishes immutable normalized rows. Real-store tests retain decimal TEXT, amendments and old snapshots. A malformed source cannot become a smaller successful snapshot. |
| Capacity and durable continuation | A new quota-blocked attempt after an old successful run remains unavailable/pending, even when the recording clock moves backward. Increasing capacity permits explicit resume; identical bodies do not acquire duplicate capture charges or snapshots. A fresh probe exercised this combined path. |
| Partial writes and recovery | A real two-byte partial stage followed by injected ENOSPC produces a closed service gap and no catalog snapshot. On resume, preflight converts the abandoned reservation to its actual orphan charge before dispatch. Exact successful bodies reopen and the failed-stage charge remains. |
| Concurrency and commit order | The issuer lease encloses latest-receipt selection and checkpointing; same-CIK requests cannot interleave receipts. Other issuers remain eligible. Provider and parser execution do not hold the capture writer or SQLite/market writer. `latest_receipt` and its index use receipt ID, not adjustable wall time. |
| Filesystem and lease authority | Create-only stages, no-replace links, regular-file/hash validation and descriptor-relative directory access remain in place. Parent-directory fsync precedes registration. Writer/issuer coordination uses the trusted external lock namespace; replacing legacy capture-root lock names does not reclaim live work. |
| Provider authority | Explicit normalized CIK and validated same-CIK history names produce fixed SEC URLs. No HTTP request accepts an arbitrary caller URL. Existing transport host/identity validation, disabled redirects, governor and 16 MiB metadata bound remain unchanged. No float-decoded legacy response path is reused. |
| Application admission | The router is actually mounted by `create_app`. A fresh mounted-app probe confirmed missing API token rejects GET/POST before construction, and authenticated POST still reaches the existing permission choke point before profile/provider/storage construction. This does not turn the audit-only permission helper into an interactive authorization engine. |
| Stored GET | GET consumes `ResearchService.stored`, uses read-only metadata/receipt queries and exposes current-receipt coverage separately from retained snapshot counts. No refresh, profile access, transport, capture construction/body read, fact/catalog materialization or installation occurs. Missing/unobserved storage stays unavailable. |
| Application preservation | Outside the new owner and tests, the only backend modification is the two router import/mount lines. No scheduler, tool registration, lifecycle mutation, financial-cache mutation, startup installer, dependency or configuration override was added. Existing SEC tools remain in place. |

Important locations: `src/sec_research/service.py:83`, `:109`, `:156`, `:182`;
`src/sec_research/store.py:108`, `:187`, `:213`;
`src/sec_research/captures.py:49`, `:61`, `:132`;
`src/sec_research/capture_lock.py:27`, `:143`;
`src/api/routes/sec_research.py:47`, `:70`; `src/api/app.py:202`, `:231`.

The GET cleanup intentionally materializes snapshot metadata, including decoded
historical-file metadata, rather than issuing the old direct SQL count query.
Its zero-valued kind counters and this metadata-only cost are acknowledged in
the approved addendum; no fact/body-read regression or false current coverage
was found.

## Fresh Verification

All executions used the existing offline runner, an empty environment, explicit
interpreter/PATH, disabled pytest plugin autoload and bytecode writes, and the
unique `final-review-tests` fixture workspace. No external/provider request,
production DB/config/token access, new agent, source/test edit, stage, commit,
installation, restart, merge or push was performed. No source mutation was used.
This report is the only manually authored file; pytest produced disposable
fixture state and XML within the requested review workspace.

```text
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1
ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/final-review-tests
/home/hyl/.virtualenvs/llm_app/bin/python -B
.superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py
tests/test_sec_research_store.py tests/test_sec_research_capture_lock.py
tests/test_sec_research_captures.py tests/test_sec_research_service.py
tests/test_sec_research_routes.py -q
--junitxml=.superpowers/sdd/2026-09-11-sec-durable-acquisition/final-review-tests/integration.xml
```

The displayed command is line-wrapped for readability. Actual result: **142
passed in 5.03s**, exit 0: 48 store, 11 lock, 24 capture, 47 service and 12 route
cases. XML node identities exactly equal all 142 added nodes in the supplied
base/final collection difference, not merely the same count.

Three additional command-only pytest functions were injected with
`pytest.Function.from_parent` after the runner installed its fixture environment
and audit fence. The fixture workspace was `final-review-tests/probes`; no test
file was authored or altered. **3 passed in 3.58s**, exit 0, recorded in
`final-review-tests/probes.xml`:

- `test_final_review_clock_rollback_capacity_resume`: old success, reduced
  budget and backward recording clock, unavailable stored coverage, pinned
  reads, explicit resumed dispatch and unchanged deduplicated charge/counts.
- `test_final_review_partial_stage_failure_receipt_and_resume`: actual partial
  staging, ENOSPC, closed receipt gap, no successful smaller catalog, recovered
  two-byte orphan charge before dispatch and successful resumed exact captures.
- `test_final_review_mounted_auth_and_permission`: actual `create_app` mounting,
  token rejection, authenticated stored GET and denied POST with forbidden
  profile/provider constructors; no lifespan or storage installation.

Also verified `git diff --check 737f438d --` exits 0. Inspected, but did not claim
as a fresh execution, `integration-reviewed.xml`: 200 cases, no failures, errors
or skips. Historical RED/inverse results remain the named task evidence; this
review did not revert source to reproduce them.

## Census And Release Gates

The actual `final-nodes.txt` contains **8,446 unique collected nodes**, compared
with **8,304** baseline nodes: **142 added, zero removed**. Collection is not an
executed full-suite result. Parent must still reconcile the completed full-run
XML against every collected identity, verify unchanged skips and source hashes,
and archive the final evidence before claiming the full release gate passed.

Inspected `census-final.json.gz` and the preceding sealed source-core census.
Every hashed file in the final census manifest still matched its recorded bytes.
The supplied final comparison has no coverage reduction, dependency-metadata
change or new untracked path:

- Exactly two new candidates are the mounted GET/POST SEC HTTP routes without
  frontend consumers. They are intentional application commands pending the
  later UI integration, not dead endpoints authorized for removal.
- The four prior test-only candidates, catalog/config/facts/paths, disappear
  because the service and route now consume those foundations.
- **30 new SQL uncertainties, not 31**, remain in the final artifact: seven
  dynamic SQL, eighteen prepare failures and five unmodeled statements, all in
  schema/store/captures. The seven dynamic sites use owned DDL or fixed
  dataclass/table choices, not user-selected SQL identifiers. Live canonical
  fixture execution supplies evidence for the actual SQL contracts; it does
  not repair or waive the census model's existing `CENSUS-SQL-001` limitation.
- The 100 locale-leaf candidates have a named `CENSUS-I18N-001` cleanup owner
  without turning the count into deletion authority. `EIR-001` and
  `CENSUS-SQL-001` remain intact. Final priority/spec/evidence status publication
  belongs to the parent; older status prose is not proof of feature completion.

## Accepted Limits And Residual Gaps

- POSIX descriptor I/O is the admitted platform; unsupported platforms fail
  closed. All cooperating processes must share the trusted `ARKSCOPE_LOCK_DIR`
  authority, which must not be replaced while live. Offline relocation tests
  do not authorize live root relocation or adversarial replacement of all
  coordination authorities.
- Capture budget is not a whole-market-DB/WAL/export budget. The normalized
  64 MiB/100000-row admission bound and 256 MiB free-space margin are not a
  hardware reservation or a measured peak-memory/whole-disk guarantee.
- Original capture, normalized source publication and receipt checkpointing
  are separate commits. A crash in the acknowledged checkpoint window may
  reacquire a pending source. Exactly-once acquisition is not claimed.
- Request bounds count source dispatches, not internal HTTP attempts. Existing
  bounded 429 retry remains; cancellation is between source requests, not
  in-flight transport interruption.
- Large retained-store recovery duration and GET metadata-list memory/latency
  have not been measured. Fault-injection/fsync-order and process-death tests
  are not hardware power-cut validation. The three new review probes are not
  permanent regression owners. These are reasonable residual test boundaries,
  not demonstrated blockers for this explicit pre-activation slice.
- No live provider validation, application lifespan/activation, export or
  production schema operation was performed. Documents/citations, issuer
  resolution, filtered query policy/cursors, three tools/four transports,
  export, scheduling/UI, C11/C12 and old actual-schema disposition remain open.
  The complete SEC first release is not ready for a hand-testing claim.

## Source Fingerprints

```text
faa665ad7b05004d660a4c7d5a8d3cdf922fb210797eacd163d7195be5074311  src/api/app.py
83e5f786d565e9964d8447e7d24e6648be4fd602fdc580fd92e0f0250caf53cd  src/api/routes/sec_research.py
17aba0183ebad1bbaef1f8be8b21e95850db74a15c58f8d196c05414c1d69b5a  src/sec_research/capture_lock.py
7429b7e12cc1df9645fa2a97d97c0a043f5c80aff7f21f556e5fb136f1981793  src/sec_research/captures.py
a51a61c18dd49dfba8853a619ed6e747e1638eef4dd74c74f3c26bf76d081e7c  src/sec_research/schema.py
f0ef5b8c25cc2572930ea171e8504c50af18354a2bc23e8b819d99dbc8356f36  src/sec_research/service.py
b38f3466883611f9822eba62179d6870af953dab27991542b6ba72f2513d5c80  src/sec_research/store.py
ce86211168a75089bd0fdb064bc372ab67b6dcbaeac182dd01a060b47e2f06dc  tests/test_sec_research_capture_lock.py
51151fbb436f0e15d566d948608928ead020f8ead1c784ba22f5936c281d3a6a  tests/test_sec_research_captures.py
cf7473f77766b65e6ea70577d5086d53e629e9bae382570bae6c43c92827e5ac  tests/test_sec_research_routes.py
0bfed3aafa0ae40c4ffb6131f746d56737e8885efa88555396b3ff7c7fdd8d6b  tests/test_sec_research_service.py
27ae01a2cf490e4b7cba835aacc5d7f338c7184ce5940dd7da1cc63ebf502525  tests/test_sec_research_store.py
```
