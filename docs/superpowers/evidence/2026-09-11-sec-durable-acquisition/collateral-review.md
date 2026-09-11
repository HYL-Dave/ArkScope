# Scoped Final Collateral Review

## Verdict

**Approved. No actionable findings in the requested collateral changes.**
The two exact route-count corrections are attributable to the two approved SEC
routes. The subscription launcher failures are attributable to the temporary
offline runner's relative fixture-root classification, not a subscription/auth
product regression. Existing lifecycle contracts and runner session restrictions
are not weakened by these changes.

This is a collateral approval only. The reported initial full run (4 failed,
8430 passed, 12 skipped) and corrected-relative four-test run are parent-supplied
history, not independently re-executed full-suite results. The parent's active
fresh full run and final evidence-sealing gates remain parent-owned.

## Scope And Evidence

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
- HEAD verified: `8070d4fcd94f013fea44cad20965aa293e59e088`.
- Baseline: `737f438d`. Used the specifically supplied `full-review.md` as the
  prior integration review; did not reopen the complete source batch.
- Reviewed current diffs in `tests/test_api.py:169` and
  `tests/test_security_lifecycle_routes.py:465`, temporary `offline_pytest.py:7`
  versus `offline_pytest_initial.py`, supplied `runner_scope_probe.py`, and its
  `runner-initial-red.json` / `runner-fixed-green.json` results.
- No other plan scratch contents, production data/config/tokens, or live
  providers were read. No installation, restart, merge, push, staging, or commit.

## Route Attribution And Contracts

An independent probe evaluated `git show 737f438d:src/api/app.py` in a separate
in-memory namespace and compared its created app with the current factory.
Existing route modules are unchanged outside the approved new SEC owner; the
app diff is exactly its router import and mount. Neither census app entered
lifespan or invoked a route handler.

Both the route-object multiset (including methods, path, endpoint module and
qualified name) and the distinct method/path set excluding HEAD/OPTIONS increased
from **216 to 218**. Exactly these rows were added, once each; none were removed:

| Method | Path | Endpoint |
| --- | --- | --- |
| GET | `/sec-research/{cik}` | `src.api.routes.sec_research.stored_status` |
| POST | `/sec-research/{cik}/refresh` | `src.api.routes.sec_research.refresh` |

`test_api.py` retains exact total equality, all existing named route membership,
the exact two scheduler-owner set, and the exact empty fired-tick assertion. Its
new rows pin the SEC methods, paths, modules, and handler names. The adjacent
network/provider non-use and owner-cleanup test is unchanged and passed freshly.

`test_security_lifecycle_routes.py` retains its existing required lifecycle set,
exact investigation-route set, web-route exclusion, retired mutation exclusion,
and obsolete market-data route disjointness. Its new SEC-prefix equality rejects
extra SEC method/path rows. All five adjacent retired-entry cases passed freshly.
Neither edited test substitutes a lower bound, removes an assertion, or adds a
skip/xfail. The global route-count semantics are unchanged.

## Runner Attribution And Scope

`diff -u offline_pytest_initial.py offline_pytest.py` shows only `.resolve()`
added to WORK. Previously a relative WORK yielded relative FIXTURES, while the
candidate executable was absolute and resolved. `is_relative_to(FIXTURES)` then
rejected genuine fixture launchers. Canonicalizing WORK fixes that mismatch.

Fresh evidence:

- Both unchanged launcher tests pass with the **initial runner and absolute
  workspace**: 2 passed. No product/test repair is needed for that control.
- The corrected runner passes those same two tests in the main focused run.
- Four direct, no-spawn matrix cases exercise initial/corrected runners against
  absolute/relative workspace values: 32 classifications match expectations.
  Initial-relative rejects both fixture names; the other three combinations
  admit them. All combinations reject outside `codex`/`claude`, `..` escape,
  prefix-sibling paths, and bare PATH names for session commands.
- A separate direct probe confirms the corrected runner rejects an in-fixture
  `codex` symlink resolving outside the fixture tree.
- The supplied unmodified `runner_scope_probe.py offline_pytest.py` was also run
  directly with the absolute own workspace: all 5 classifications matched,
  exit 0, with no subprocess spawned by the probe.
- The supplied historical red/green JSON has the same five classifications:
  only the two genuine fixture admissions change. Outside and `..` cases remain
  rejected. Own matrix JSON records fresh relative-path classification evidence;
  it is not represented as a fresh relative launcher-test execution.

The pre-existing `--version` exemption remains. The runner still gates named
`codex`/`claude` session executables, not every conceivable executable/alias; this
review does not claim it is a general adversarial sandbox. No audit rule or
provider-network/production-path restriction was relaxed.

## Commands And Results

All commands ran from the named worktree. The following shell variables/function
express the exact repeated command prefix without duplicating long paths:

```bash
P=.superpowers/sdd/2026-09-11-sec-durable-acquisition
S=/tmp/arkscope-listing-sec-macro-convergence/$P/collateral-review-tests
offline() {
  env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 \
    ARKSCOPE_OFFLINE_TEST_WORKSPACE="$S/fixtures" \
    /home/hyl/.virtualenvs/llm_app/bin/python -B "$@"
}
offline "$S/run_review.py" offline_pytest.py \
  tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes \
  tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes \
  tests/test_subscription_account_usage.py::test_nvm_symlink_launcher_with_env_shebang_passes_exact_version_check \
  tests/test_subscription_account_usage.py::test_app_server_spawn_uses_launcher_path_with_launcher_and_target_dirs_on_path \
  tests/test_api.py::test_local_runtime_gate_rejects_external_network_and_cleans_owners \
  tests/test_security_lifecycle_routes.py::test_actual_app_excludes_unused_lifecycle_http_entry \
  "$S/test_collateral_probes.py" -q --junitxml="$S/scoped.xml"
offline "$S/run_review.py" offline_pytest_initial.py \
  tests/test_subscription_account_usage.py::test_nvm_symlink_launcher_with_env_shebang_passes_exact_version_check \
  tests/test_subscription_account_usage.py::test_app_server_spawn_uses_launcher_path_with_launcher_and_target_dirs_on_path \
  -q --junitxml="$S/initial-absolute.xml"
offline "$P/runner_scope_probe.py" offline_pytest.py
git diff --check HEAD -- tests/test_api.py tests/test_security_lifecycle_routes.py
git diff --exit-code HEAD -- src tests ':!tests/test_api.py' ':!tests/test_security_lifecycle_routes.py' data_sources
git diff --exit-code 737f438d -- src/auth_drivers src/subscription_plan.py src/api/permissions.py src/api/dependencies.py src/api/routes/config_routes.py tests/test_subscription_account_usage.py tests/test_subscription_structured_output.py
git diff --numstat HEAD -- src tests data_sources
```

- Main focused run: **16 passed in 5.15s**, exit 0: the four affected tests,
  six adjacent contract cases, and six independent probes.
- Initial-runner absolute-workspace control: **2 passed in 0.34s**, exit 0.
- Parsed both JUnit files independently: respectively 16 and 2 tests, zero
  failures/errors/skips. These are 18 executions, not 18 unique test identities.
- All three git check/exit-code commands above exited 0. The numstat lists only
  the two reviewed tests, each 5 insertions and 1 deletion. No product delta
  exists versus HEAD. The baseline auth/subscription comparison is empty;
  `app.py` token middleware is unchanged in its exact two-line baseline diff.

The wrapper changes only temporary-file placement before invoking the existing
runner, setting `tempfile.tempdir` and TMPDIR under own scratch so conftest's
session TemporaryDirectory also stays there. Runner HOME, config/cache, database,
token-file and lock overrides remain isolated under the absolute fixture root.
No source/test was modified to obtain any result.

## Changed Paths And Fingerprints

Parent collateral under review: `tests/test_api.py`,
`tests/test_security_lifecycle_routes.py`, and temporary
`.superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py`.
Unrelated parent documentation changes were visible in git status and untouched.

Reviewer writes only: this `collateral-review.md` and
`collateral-review-tests/` containing `run_review.py`,
`test_collateral_probes.py`, `scoped.xml`, `initial-absolute.xml`,
`route-delta.json`, four `scope-*.json` files, and generated `fixtures/` / `tmp/`
state. The original runner, probe, source and repository tests were not edited.

Observed SHA256 fingerprints after verification:

```text
49a9c947bd8fcae6821277fa66511591fb795067db7001c42d69949938495b0a  tests/test_api.py
81774e1f28f5823108601c3b8350e6b14312e9175991b5ce6be5a25e59bf38e0  tests/test_security_lifecycle_routes.py
04afe279c2f3451e7f6a1238259c2b11680747796eb83bbaed0c527678e7b63b  tests/test_subscription_account_usage.py
047900bd47e0c37005bbc9d36c1f07dca252bd8ffd5d2bcb74d234f35745afd6  tests/test_subscription_structured_output.py
faa665ad7b05004d660a4c7d5a8d3cdf922fb210797eacd163d7195be5074311  src/api/app.py
651f50ac0435797366055f965469e423f25aef149d55b0c196312b86624304b3  offline_pytest_initial.py
4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff  offline_pytest.py
```
