# Final Collateral Review

## Findings

None within the requested test-only collateral scope. The corrected expectations follow the already-approved Task 2 product replacement; they do not hide a source regression or weaken the existing guards. No product change is proposed.

## Bound Patch

- Repository: `/tmp/arkscope-research-output-boundary`; branch: `codex/sec-research-integration`.
- Base: `885c2a2d19065e37bfba492c0e6b75b17f30ed06`.
- Head, verified before and after the focused run: `ae2055e3a6750edd0322f2c405964cbb0e5ad741`.
- Exact `git diff --no-ext-diff --no-textconv 885c2a2d..ae2055e3 --` SHA-256: `d2f3944f668820eb1d23f34c42be88eb4a8431a82d41498963c35286a89fd921`.
- Only changed files: `tests/test_security_lifecycle_routes.py`, `tests/test_security_lifecycle_tools.py`, and `docs/superpowers/plans/2026-09-12-sec-research-release-integration.md`.

## Source And Guard Checks

**Route test:** Reviewed the complete body of [test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes](/tmp/arkscope-research-output-boundary/tests/test_security_lifecycle_routes.py:431), its real `create_app().routes` fixture, and the complete patch. The fixture still enumerates distinct method/path pairs, excluding HEAD/OPTIONS. The expected lifecycle membership, exact eight-entry SEC route set, exact investigation route set, and retired-route exclusions are unchanged. Only strict count `224` becomes `223`, with a new explicit rejection of `("GET", "/sec/{ticker}")`.

The base plan already requires removal of that route and forbids an alias/redirect/stub. Path-limited history identifies `3fef138daae0a5c357b385156738d34107a04956` as removing its sole GET registration from `src/api/routes/fundamentals.py`. Current [app mounts](/tmp/arkscope-research-output-boundary/src/api/app.py:174), [SEC registrations](/tmp/arkscope-research-output-boundary/src/api/routes/sec_research.py:63), and lifecycle/investigation router definitions agree with the retained assertions. This explains the one-row decrease without removing another expected route from the test. Reintroducing the old GET route would now fail explicitly, even if a compensating deletion kept the total at 223.

**Allowlist test:** Reviewed the complete body of [test_lifecycle_tools_are_in_both_research_driver_allowlists](/tmp/arkscope-research-output-boundary/tests/test_security_lifecycle_tools.py:1022). Both original lifecycle names remain required in both drivers. The required set adds `list_sec_filings`, `get_sec_financial_facts`, and `read_sec_filing`; both drivers must exclude `get_sec_filings` and have exactly 17 names. There is no skipped/xfail assertion, mock replacement, or conversion of strict counts to a permissive bound.

The actual hardcoded frozensets in [ChatGPT](/tmp/arkscope-research-output-boundary/src/auth_drivers/chatgpt_oauth_driver.py:52) and [Claude](/tmp/arkscope-research-output-boundary/src/auth_drivers/claude_code_sdk_driver.py:121) contain the same 17 names. Line-limited history independently shows that `3fef138d` replaced exactly the old SEC name with those three names in each, preserving every other member: `15 - 1 + 3 = 17`. Dropping a required lifecycle/new SEC name or restoring the old SEC name fails even with a compensating substitution that preserves cardinality.

**Plan rows:** The three new [Task 2 counter rows](/tmp/arkscope-research-output-boundary/docs/superpowers/plans/2026-09-12-sec-research-release-integration.md:333) correctly distinguish one app-route count and two OAuth counts. The shared-policy inventory row states `56 = 49 + 3 + 4` and explicitly retains no SEC redaction exception; it does not change the policy or its tests in this patch. This review does not independently certify shared-policy behavior or the other Task 2 progress receipts.

## Commands And Results

All commands below ran in the repository above.

```bash
git rev-parse HEAD 885c2a2d ae2055e3
git branch --show-current
git diff --no-ext-diff --no-textconv 885c2a2d..ae2055e3 --
git diff --no-ext-diff --no-textconv 885c2a2d..ae2055e3 -- | sha256sum
git log -1 --format=short -p -G '/sec/\{ticker\}' 885c2a2d -- src/api/routes/fundamentals.py
git log -1 --format=short -L 52,72:src/auth_drivers/chatgpt_oauth_driver.py 885c2a2d
git log -1 --format=short -L 121,141:src/auth_drivers/claude_code_sdk_driver.py 885c2a2d
git show 885c2a2d:docs/superpowers/plans/2026-09-12-sec-research-release-integration.md | sed -n '257,291p'
```

All exited 0; identity, patch scope, and prior-product provenance are recorded above. Read-only `sed`/`rg` inspections covered the test bodies, relevant definitions, current plan, existing runner/audit hook, and receipt files. One initial allowlist search assumed an unannotated assignment and returned no matches (exit 1); the corrected anchored search found both annotated definitions.

Inspected existing `command.json` and `output.log` receipts, without rerunning them:

- `integration-last-collateral-red`: exit 1, exactly 2 failed in 3.69s. Failures are route `223 == 224` and OpenAI allowlist `17 == 15`. The latter stops before the old Anthropic count assertion, so this receipt alone is not proof that both count assertions executed.
- `integration-last-collateral-green`: exit 0, 126 passed in 17.14s across the two lifecycle files, `tests/test_api.py`, and `tests/test_sec_research_tool_adapters.py`.

Fresh independent execution, using the unchanged current-plan runner:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py final-collateral-review-ae2055e3-20260913-01 backend -q tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes tests/test_security_lifecycle_tools.py::test_lifecycle_tools_are_in_both_research_driver_allowlists
```

Result: exit 0; **2 passed in 3.54s**. JUnit independently records 2 tests, 0 failures, 0 errors, 0 skips, with both exact node names. Both drivers' assertions execute in this fresh passing run. [Receipt folder](/tmp/arkscope-research-output-boundary/.superpowers/sdd/2026-09-12-sec-research-release-integration/final-collateral-review-ae2055e3-20260913-01) contains `command.json`, `output.log`, `results.xml`, and isolated generated runtime files. The runner uses its closed child environment, existing offline audit hook, isolated HOME/store/temp paths, disabled bytecode, and disabled pytest cache.

Before and after execution, this command exited 0 with no differences:

```bash
git diff --exit-code --no-ext-diff --no-textconv ae2055e3 -- tests/test_security_lifecycle_routes.py tests/test_security_lifecycle_tools.py src/api/app.py src/api/routes/fundamentals.py src/api/routes/sec_research.py src/api/routes/security_lifecycle.py src/api/routes/lifecycle_investigation.py src/auth_drivers/chatgpt_oauth_driver.py src/auth_drivers/claude_code_sdk_driver.py docs/superpowers/plans/2026-09-12-sec-research-release-integration.md
```

## Limits And Handoff

These remain inventory guards, not a full exact-name allowlist specification or proof of runtime authorization/dispatch. Unrelated equal-cardinality substitutions outside required members are a pre-existing coverage limitation, not introduced by this patch. Counterexamples above were assessed from assertions; no mutation experiment was run.

The earlier full-backend `10277P/2F/12S` total is controller-provided context, not a new independent result. No complete backend rerun, census, node-accounting/sealing operation, agent, provider call, private-config/production-DB access, install/restart, other-worktree operation, or source/test/index mutation was performed for this review. Writes are limited to this report via `apply_patch` and the named generated receipt folder.

All commands/sessions started by this reviewer have finished. The controller's separate full-backend run was left untouched. No repository-wide security, release-readiness, or full-suite success claim is made.
