# Task 2 Report

## Delivery

- Commit: `3e73d2aa8e1fb5925b388178f02e623e291a12df`.
- Recorded pre-dispatch/product base and exact commit parent: `a81e4d92b5b9649dafbab6dbf7dee8ded181aa41`.
- Approved core consumed without changes: `5f22762d747743185b808c7c21cf19d25077c312`, approved in `task-1-rereview.md`.
- Workspace: `/tmp/arkscope-research-output-boundary`.
- Final focused verification: **716 passed, 0 failed, 0 errors, 0 skipped**.
- Initial 288-test suite reached GREEN; the final two new files contain 295 tests after seven cases for confirmed gaps.
- Six deliberate inverses were caught, restored, and followed by full focused GREEN.
- Ready for coordinator freeze and independent review. No independent-review or whole-backend pass is claimed.

Only the following 11 files were staged and committed:

```text
src/tools/result_policy.py
src/tools/registry.py
src/agents/openai_agent/tools.py
src/agents/anthropic_agent/tools.py
src/auth_drivers/chatgpt_oauth_driver.py
src/auth_drivers/claude_code_sdk_driver.py
tests/test_tool_output_policy.py
tests/test_tool_output_channels.py
tests/test_chatgpt_oauth_driver.py
tests/test_claude_code_sdk_driver.py
tests/test_security.py
```

This requested report and the runner artifacts are plan-local ignored files, not committed, following the Task 1 report convention. No other scratch artifact was authored. The coordinator's modified plan and Task 3's untracked event/lifetime tests were left untouched. Core source/tests, diagnostic heuristic implementation, docs/ledger, source captures, citations, SEC feature code, and Task 3 product files were not edited or staged. There was no subdelegation, provider/network use, live credential/token/.env/DB access, install, merge, push, or restart.

## Result Contract

```python
ResultPolicy(kind: Literal["json", "text"], validator: Callable | None = None)
ToolDefinition.result_policy: ResultPolicy | None = None
admit_tool_result(result, *, policy, guard=None) -> str
serialize_tool_result(result, *, tool_name) -> str
```

The source-only `inventory-results.json` and `task-2-contract.md` determine all 54 explicit registration policies: 50 `PUBLIC_JSON`, and `PUBLIC_TEXT` for `check_data_freshness`, `scan_alerts`, `get_economic_calendar`, and `get_macro_value`. API-only `delegate_to_subagent` has one explicit JSON contract. Unknown/unnamed tools and missing/invalid policy metadata fail closed; output content cannot select a policy. Native API policy lookup lazily constructs the existing registry without DAL access. No SEC import, field exemption, reducer exception, or domain schema was introduced.

JSON admits exact built-in JSON types, plus explicitly normalized native Pydantic models, date/datetime ISO strings, and finite Decimal strings. Compact sorted-key UTF-8 JSON is canonical. Decimal spelling, including exponent form, stays exact. Raw strings under JSON policy, nonfinite values, foreign objects/duck `model_dump`, nonstring keys, invalid Unicode, cycles, and unsupported types fail without arbitrary repr/string coercion. Text policy requires an exact string and never auto-parses JSON-looking text. Shared acyclic references are allowed.

Pydantic fields are visited progressively rather than dumped recursively before budgeting. Field exclusions and allowed extras are honored; custom model/field serializers and computed fields fail closed and require the tool to prepare explicit supported data. Source inspection and the coordinator's checkpoint found no current `src/tools` custom serializers/computed fields, and the coordinator confirmed portfolio numpy metrics already become explicit floats. No extra normalization accommodation was added for those non-gaps.

The existing `OutputBoundaryError` is reused: `invalid_value` for policy/shape/credential-syntax/validator rejection, `known_secret` for exact protected representations, and `value_limit` for boundary budgets. No new core code or interface was needed. Validators receive detached normalized data, must return literal `True`, and cannot change the immutable pre-callback encoding unnoticed. Callback exceptions, including an attempted unrelated core error code, become `invalid_value`; rejected values and callback reprs are not returned.

Budgets are progressive: depth 64 with root at zero, 1,000,000 nodes including containers/keys/values, and 32 MiB encoded output including JSON punctuation/escaping. String byte accounting uses 64 Ki-character chunks. Overlimit mapping keys are rejected before allocating whole-key canonicalization copies. These limits do not enlarge the existing channel reducers or claim provider acquisition limits. Python's own oversized-integer conversion refusal also fails closed.

Exact-secret checks cover both normalized values/keys and the final emitted canonical spelling, including numeric coincidences. OAuth callbacks add only their already-captured bearer to the current/new guard. They do not enumerate credentials or read a store. Execution credential capture/lifetime integration outside these callbacks remains Task 3 ownership.

## Credential Syntax

Credential-name comparison uses ASCII lowercase and removes only `_`, `-`, space, tab, CR, and LF. The denied names after normalization are `authorization`, `proxyauthorization`, `xapikey`, `apikey`, `accesstoken`, `refreshtoken`, `idtoken`, `clientsecret`, `password`, and `privatekey`. Values and nested mapping keys are checked. `token_count` and `token_usage` are not credential exemptions or denied credential names; they remain public data.

Unknown authentication literals reject the whole result using these exact supported forms:

```text
(?<![A-Za-z0-9_])(?:
  (?i:Bearer)[ \t]+[A-Za-z0-9._~+/-]+=* |
  sk-(?:ant-(?:api03|oat01)-|proj-)[A-Za-z0-9_-]{20,} |
  sk-[A-Za-z0-9]{32,} |
  gh[pousr]_[A-Za-z0-9]{36,}
)
```

The displayed whitespace/newlines are explanatory; the source compiles the concatenated pattern. Bearer alone is case-insensitive; key prefixes are case-sensitive. The left boundary forbids a preceding ASCII letter, digit, or underscore; no right boundary is required. This is not an entropy, generic long-token, PII, or mixed-case detector. Arbitrary unknown secrets or transforms outside the core's finite known-secret representations are not covered. Successful words, numbers, email, hashes, accessions, URLs, and full cursors are not rewritten.

## Adapter Differences

- Native OpenAI and Anthropic retain their existing `<tool_output>` tags. The two former OpenAI macro direct returns now also enter admission and receive the established tags. Native list-of-dict Python repr output becomes canonical JSON, and whitespace changes from default JSON spacing to compact encoding are intentional.
- OAuth output envelopes remain unchanged; no native tags were added. Both callbacks admit the complete value before their existing 12,000-character reducer and downstream previews. Successful output no longer passes through lossy diagnostic heuristics. Large pages may still be reduced under those unchanged budgets, so equivalence is asserted before independent reduction, not for all wire bytes after it.
- Native function exceptions are sanitized before the Anthropic error logger and before the OpenAI SDK's handled-error logger/default failure callback can format them. OpenAI uses a guarded callable, disables that SDK default failure handler, and returns safe errors through its outer invocation wrapper, including SDK argument-parse errors. Invalid `holdings_json` no longer echoes raw input. This intentionally changes default SDK error wording while preserving error-as-result behavior.
- Exception detail uses exact scoped-secret projection and the unchanged runtime diagnostic sanitizer before its existing truncation. Typed admission failures contain only safe codes. Runtime retry classification was not changed.
- Unknown-name rejection does not echo an untrusted tool name: Anthropic returns an error plus `invalid_value`; OAuth retains failure flags and allowlist/registration reasons with bounded `invalid_value` text. Existing allowlists and timeout/executor behavior are unchanged. In particular, `get_macro_value` remains vetoed in OAuth.

## Existing Test Changes And Owners

No original safety owner was deleted. The first existing-suite run exposed eight failures: four serialization-contract expectations and four fake-result fixtures lacking explicit policies. Corrections were confined to these files:

- `tests/test_chatgpt_oauth_driver.py`: `_ToolDef`, `_VerboseToolDef`, and `_SlowNewsBriefToolDef` now declare JSON. Existing successful continuation, full model result versus 200-character UI preview, and timeout tests remain unchanged positive/behavior owners. No production fallback was added for these fixtures.
- `tests/test_claude_code_sdk_driver.py`: `_FakeToolDef` defaults to `None`; `_full_fake_registry` explicitly supplies JSON or calendar text. The calendar's default fixture now actually returns text. The existing happy-invoke test is parameterized over JSON and text (one additional case), and the existing oversized-result/reducer owner is retained. Direct timeout and input-schema fixtures declare the corresponding policy while retaining their original timing/schema assertions; the off-allowlist fake remains unclassified.
- The existing Claude `test_bridge_sk_ant_secret_in_result_is_redacted` owner is renamed `test_bridge_sk_ant_secret_in_result_is_rejected`, not removed. It first proves the same tool/policy accepts a public result, then requires the secret case to return `is_error=True` and exactly `invalid_value`, while retaining the non-leak assertion. The auth-syntax inverse makes this owner fail, so it is not passing merely because a fixture lacks a policy.
- `tests/test_security.py`: both with-tool-name tests retain opening/closing tag assertions and compare parsed canonical business data instead of JSON spaces. Both without-tool-name tests now require typed `invalid_value` because an unnamed result has no trusted policy. Additional direct-serializer unknown/unnamed tests and registry policy tests own that fail-closed contract. All other prompt/wrapper coverage remains.

New adapter tests invoke the actual OpenAI SDK `on_invoke_tool`, Anthropic `execute_tool`, ChatGPT `_invoke_tool`, and Claude `_invoke_bridged_tool` paths with synthetic registered results and a DAL that refuses access. They cover equal public data, full cursors/long words/numbers/URLs, canonical lists, native types, trusted-policy positive/negative pairs, malformed/credential rejection, validators, macro bypasses, diagnostic errors, captured OAuth bearers, and admission before reducer/preview. They do not invoke providers or real data tools.

## Verification Evidence

All product tests used the closed plan runner. Each run below has `command.json`, `output.log`, and `results.xml` under its named plan-local directory. Counts and hashes were checked with a cleared-environment standard-library XML/JSON reader, without importing product code. Every row has zero errors and zero skips.

| Run | Pass | Fail | Exit |
| --- | ---: | ---: | ---: |
| task2-red-initial-20260912-01 | 7 | 266 | 1 |
| task2-red-ready-20260912-02 | 9 | 279 | 1 |
| task2-green-first-20260912-03 | 288 | 0 | 0 |
| task2-existing-first-20260912-04 | 244 | 8 | 1 |
| task2-extra-red-20260912-05 | 0 | 3 | 1 |
| task2-green-and-regressions-20260912-06 | 711 | 0 | 0 |
| task2-fixture-positives-20260912-07 | 3 | 0 | 0 |
| task2-inverse-policy-20260912-08 | 2 | 6 | 1 |
| task2-inverse-exact-secret-20260912-09 | 0 | 26 | 1 |
| task2-inverse-credential-key-20260912-10 | 0 | 25 | 1 |
| task2-inverse-byte-limit-20260912-11 | 0 | 1 | 1 |
| task2-inverse-node-limit-20260912-12 | 0 | 1 | 1 |
| task2-inverse-auth-syntax-20260912-13 | 0 | 26 | 1 |
| task2-key-budget-red-20260912-14 | 0 | 1 | 1 |
| task2-restored-full-20260912-15 | 713 | 0 | 0 |
| task2-unknown-name-red-20260912-16 | 0 | 3 | 1 |
| task2-final-green-20260912-17 | 716 | 0 | 0 |

Initial RED was completed before product GO. Run 01 included a mistaken expectation that OAuth exposed `get_macro_value`; source-confirmed allowlist veto tests replaced that assumption during RED preparation, before implementation. Run 02 is the final 288-case initial RED evidence, not a collection/import failure. Its nine passing cases already exercised existing behavior. Run 04's fixture/format failures are explained above rather than relabeled as baseline failures. Run 07 selected three positive/negative fixture owners with 48 deselected, not skipped.

Only confirmed subsequent gaps added cases: run 05 proved raw holdings-input echo, SDK parse-error logging, and validator-selected unrelated error code (three RED cases); run 14 proved the overlimit-key canonicalization made 67,119,420 bytes of temporary allocation before its limit (one RED case); run 16 proved three unknown-name branches echoed a synthetic secret and oversized name (three RED cases). Each received its narrow fix. The key test now bounds peak incremental allocation below 8 MiB; it does not change the specified 32 MiB output limit. No core marker tests were duplicated.

Final command:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task2-final-green-20260912-17 backend tests/test_tool_output_policy.py tests/test_tool_output_channels.py tests/test_agents.py tests/test_subagent.py tests/test_tool_calling.py tests/test_financial_calculation_tools.py tests/test_security.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_macro_calendar_read.py tests/test_task_runtime_binding.py tests/test_probe_harness.py -q --show-capture=no -rN
```

Final census: 175 policy + 120 channel tests, plus 421 existing tests: 120 agents/subagent/tool/financial-calculation, 97 OAuth-driver, 25 macro-calendar, 141 runtime-binding, 27 probe, and 11 security tests. Pytest reported 716 passed in 25.19 seconds; runner exit was zero. The coordinator's separately verified 120/308 baselines are not added to these fresh totals.

## Inverses And Restoration

All six inverses were temporary `apply_patch` mutations of **only** `src/tools/result_policy.py`; each was restored before the next mutation. Core was never mutated. The test commands, selected nodes, failure assertions, and exit codes are retained in each run's artifacts; the deliberate changes are recorded below.

| Run | Deliberate bypass | Decisive failures |
| --- | --- | --- |
| 08 | Default missing policy to PUBLIC_JSON | Two policy-unit owners and all four real-adapter missing-policy owners admit forbidden data: 6 failures; 2 other invalid-policy controls still pass. |
| 09 | Disable normalized AND encoded guard.check | Protected value/key representations, emitted numeric spellings, macro outputs, and captured OAuth bearers: 26 failures. |
| 10 | Disable recursive credential-name rejection | Normalized credential key spellings plus all four real adapters: 25 failures. |
| 11 | Disable encoded byte-budget rejection | `test_text_32_mib_limit_counts_encoded_bytes_not_unicode_characters`: DID NOT RAISE. Core's character limit cannot mask this owner. |
| 12 | Disable node-budget rejection | `test_node_budget_stops_before_coercing_an_over_budget_foreign_value`: wrong invalid_value instead of early value_limit. |
| 13 | Disable narrow authentication-literal rejection | Syntax/key-position units, all four unknown-sk-ant adapter cases, and the retained existing Claude sk-ant owner: 26 failures. |

The policy source was restored byte-for-byte to its pre-inverse SHA-256 `b94e25c9a580d86c79abdbdf64588bde7c29c5c46713d25c953c2ea1193cc555`. The later confirmed key-budget ordering and unknown-name fixes followed that inverse sequence. The six inverses were not rerun after those narrow fixes; their unchanged owners and all focused regressions pass in final run 17. Runs 15 and 17 are full restored GREEN, not only inverse-node reruns.

Selected JUnit SHA-256 evidence:

```text
02 f00e03dccc7021311ac644c7a035d3367a3090698c9b026c9826b915b3bb0d2f
08 1f688ca9c6051fb321277af263d531db140d06116536a339721180cd25ec1088
09 7ffe0bf7c853296dbf62bfccd5ff3ba4ed0c5a111db1030a354b593c3a4a6ce7
10 ac843659c3acf70ecc92497a3953573f06ef27ef4618282af38433341c005c98
11 46662a7499f359fc38290314aea7d0a54529f22f6690a234df5c4aa7578a2043
12 49dde62c439a3ed0e438a6842b2e422dec5abfcdd24029af300875cde3db352d
13 ea85348a30f5748aa19ddf276171683459d920a337c6f3760883a7c6260789f1
14 24c496f6112c98840eace7f1bd68b412cbce96dc9b57b3dcb8a495924a0e45c7
15 2b36aa8f231cf554cd30aec5ca9507c696edfe804ce24801a88b3a075a435272
16 44baf048244098087b79a0af972b62a2d44892d8d8e8cdca21b67c9dc3fa9cf2
17 5d865bd7b428e596d86a39b6b28152c44de9a276848d656634fa21d3ae0e23f0
```

Committed Task 2 source/test SHA-256:

```text
62285c99affe064eb681761df002cc6b47d21ab00f991b7d8518e1983bd8f69e  src/tools/result_policy.py
db6549ac6105f7f8fa2036a0437e1c067c8cb4d3d4feeb1c382a92c8b58e475a  tests/test_tool_output_policy.py
fc0c078efd3409799df1f37896fdddc852b9cbed8e04a8336265da7772bc92e0  tests/test_tool_output_channels.py
```

Unchanged approved core SHA-256 (also an empty path-scoped diff against `5f22762d`):

```text
975563ed82d3edcc9e3b0832e942ab756711dd2946fe32dd475df267d3bdb9a1  src/agents/shared/output_boundary.py
3f0cc160d482c94a2a21e3c6080b481592dfc7284d3c868739ef18d9ffa3a6d6  tests/test_output_boundary.py
```

## Review Handoff

`git diff --check` and the staged diff check passed. The commit's exact file list and parent were verified after commit; the index is empty. The only remaining visible changes are the coordinator's plan and Task 3's two untracked test files.

No known failing focused Task 2 test remains. Whole-backend/whole-branch verification and independent Task 2 review remain coordinator work; Task 3 owns event/replay/scratchpad protection and execution-wide credential/iterator lifetimes. These are not claimed by the four-adapter tests.

The separate paused SEC feature's four OAuth adapter failures remain parked as recorded by the tracked spec and original feature checkpoint. They were not executed as this branch's tests, hidden, relabeled as baseline failures, or claimed fixed; their feature integration and large-page pagination/reduction ownership remain outside Task 2.

Residual contract limits are explicit: reviewed generic public JSON is not a per-domain schema; arbitrary unknown secrets/transforms are not detected; supported native normalization is deliberately closed; valid admitted output can still be reduced under the original channel budgets; and credentials must be captured before use for exact guard protection. No generic policy fallback or silent successful credential rewriting was added.
