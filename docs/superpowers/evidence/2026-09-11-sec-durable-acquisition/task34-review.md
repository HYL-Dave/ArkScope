# Tasks 3 + 4 Service/API Integration Review

## Verdict

No actionable integration findings in the live reviewed source. Tasks 3 + 4
meet the scoped structured-acquisition and explicit-command contract below.
This is not approval of CaptureStore internals, completion of the full SEC
substrate, or a production-readiness claim. Parent-owned CaptureStore R1-R4
remain outside this review; no additional capture change is requested here.

Reviewed in `/tmp/arkscope-listing-sec-macro-convergence` against
`docs/superpowers/plans/2026-09-11-sec-durable-acquisition.md` Tasks 3-4 and
`docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md` storage,
coverage and explicit-command requirements. Read the current implementation,
tests and Task 3 report, not just its reported results.

## Integration Checks

- **Original sources:** `src/sec_research/service.py:133` reads `SecResponse.body`
  after status validation, never `response.json()`. Whole-source parsing precedes
  capture and immutable snapshot publication (`:143`, `:156`). Malformed source
  bytes can be retained without publishing a successful subset of rows. Exact
  numeric precision and original bytes survive reopening real storage.
- **Identity and locators:** `service.py:75` normalizes explicit CIK before side
  effects; `:34` constructs only SEC submissions/companyfacts and same-CIK
  historical URLs. The catalog parser validates payload CIK and declared
  filenames before publication. Both completed and pending persisted locators
  are revalidated before resume (`:91`), including a no-op resume.
- **Durable continuation:** `service.py:109` persists initial intent before
  dispatch; `:169` checkpoints completion and discovered history before the next
  request. Reopening and crash fixtures verify completed-source skipping.
  Failures stay pending. Fresh runs start with new coverage (`:87`), retaining
  but not borrowing previous successful observations.
- **Truthful coverage:** `service.py:53` requires current-run completion for
  success and reports partial when work or gaps remain. Missing history pointers
  remain `historical_files_unobserved` (`:176`), including no-op resume. Explicit
  observed empty sources can be successful; absent/unobserved storage cannot.
- **Separate lease:** `service.py:83` holds the per-issuer refresh lease through
  receipt readback. Real integration fixtures reject same-issuer overlap without
  receipt overwrite and allow a different issuer during provider wait. Provider
  and parser boundary probes acquire the market lock, capture writer lease and
  SQLite write transaction independently, confirming none spans those boundaries.
- **Bounds and cancellation:** `service.py:111` limits distinct source dispatches
  to exact-integer `max_sources` in 1..16, not raw HTTP attempts. Every dispatch
  has preflight and a between-source cancellation check. The existing 16 MiB
  transport metadata default remains intact. An independent real-transport probe
  confirmed one source may perform two HTTP attempts for its single bounded 429
  retry; it still leaves later sources pending and partial.
- **Explicit command ordering:** `src/api/routes/sec_research.py:62` rejects
  coercion and extra request keys. CIK validation and existing `require_db_write`
  precede profile/provider/store/service construction and explicit installation
  (`:70`). Managed SEC identity is validated before store installation (`:77`);
  missing managed identity never falls back to an environment identity.
- **Transport lifetime:** `sec_research.py:92` closes the constructed transport
  on success, no-op resume and failure. Existing tests cover the first two;
  the review probe covers a service exception and closed/redacted HTTP failure.
- **Stored GET:** `sec_research.py:36` resolves the existing market path, verifies
  schema read-only and queries receipt plus SQL snapshot counts. It does not
  construct transport, open profile settings, read capture bodies, materialize
  facts/catalog rows or install schema. Missing DB, unrelated DB and installed
  unobserved DB are unavailable, not empty success. Retained snapshot counts are
  separate from current-receipt coverage.
- **App wiring:** `src/api/app.py:202` imports and `:231` mounts the router. The
  diff adds no startup installation, scheduler, tool registration or UI. An
  independent `TestClient(create_app())` probe exercised mounted GET and denied
  POST without running lifespan or creating SEC storage.

## Fresh Offline Evidence

All execution used the existing offline runner, a cleared environment, clean
PATH, disabled plugin autoload/bytecode writes and unique `review34-tests`
fixture directories. No production data/config/provider access, external network,
agents, source/test edits, installation or commits were performed. Only this
requested report and disposable test outputs were written.

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review34-tests \
  python .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py \
  tests/test_sec_research_service.py tests/test_sec_research_routes.py -q \
  --junitxml=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review34-tests/service-routes.xml
```

Result: **59 passed in 2.64s**, exit 0: 47 service and 12 route tests.

Six additional command-only pytest items were injected through an in-memory
collection plugin, using the same runner with workspace `review34-tests/probes`.
No worktree test file or implementation was modified. Result: **6 passed,
59 deselected in 3.77s**, exit 0; evidence `review34-tests/probes.xml`:

- `test_review34_app_mount_and_permission`
- `test_review34_close_on_service_failure`
- `test_review34_get_installed_empty_no_body_or_install`
- `test_review34_bad_payload_identity_and_history`
- `test_review34_persisted_hostile_locators`
- `test_review34_one_source_allows_one_429_retry`

The hostile-input probes included cross-CIK source bodies, cross-CIK historical
filenames, absolute URLs, traversal and query-suffixed persisted locators. They
confirmed no historical dispatch, no false publication and no receipt mutation
on rejected persisted locators.

## Limits And Handoff

- The existing permission helper is an audit-only structural choke point, not
  implemented interactive permission enforcement. This route correctly uses the
  required existing helper; this review does not claim a new authorization engine.
- Capture publication, snapshot publication and receipt checkpointing are not
  one transaction. A crash after snapshot publication but before its receipt
  checkpoint can reacquire the source. This acknowledged boundary is not an
  exactly-once guarantee and does not permit borrowing completed old-run coverage.
- Cancellation is between source requests, not an in-flight abort or a check
  between the transport's internal retry attempts.
- The six review probes are not permanent regression owners. Persisting owners
  for mounted-app behavior, failure-path closure, installed-empty GET purity and
  source-bound retry semantics would strengthen ongoing regression coverage.
- No full backend suite, application lifespan, production provider validation or
  new inverse mutation was run. The Task 3 report's four caught inverses and
  earlier expanded-suite count remain prior evidence, not fresh review results.
- CaptureStore fixes must receive their own parent validation. No capture-internal
  correctness or recovery conclusion is inferred from these integration passes.

## Reviewed Source Identity

SHA256 values were unchanged between the initial test run and final pre-report
readback for all five scoped files:

```text
f0ef5b8c25cc2572930ea171e8504c50af18354a2bc23e8b819d99dbc8356f36  src/sec_research/service.py
c2c9a9fa592543cf0f0922e9a4f164ba7c3684894a035bbe9019051a65113e55  src/api/routes/sec_research.py
faa665ad7b05004d660a4c7d5a8d3cdf922fb210797eacd163d7195be5074311  src/api/app.py
0bfed3aafa0ae40c4ffb6131f746d56737e8885efa88555396b3ff7c7fdd8d6b  tests/test_sec_research_service.py
cf7473f77766b65e6ea70577d5086d53e629e9bae382570bae6c43c92827e5ac  tests/test_sec_research_routes.py
```
