# Task 2 Fix Round 1 Report

## Delivery

- Commit: `41b9f2b5384881dc0daa04f5c25720b1e9a8660a`.
- Authorized base and exact commit parent: `857359e370d4662fbd4eae036b39636554d0f727`.
- Review consumed: `task-2-review.md`; authority: coordinator fix-round GO and updated spec section 5.
- Final restored focused result: **754 passed, 0 failed, 0 errors, 0 skipped**.
- Both findings have RED owners and targeted GREEN. Three complementary inverses failed decisively and were restored before final GREEN.
- Ready for rereview; no independent-review or whole-backend approval is claimed.

Only these four authorized files were staged and committed:

```text
src/tools/result_policy.py
src/agents/openai_agent/tools.py
tests/test_tool_output_policy.py
tests/test_tool_output_channels.py
```

The commit contains 100 insertions and five deletions, including test additions and the policy docstring correction. The requested report and check artifacts remain plan-local ignored files, not committed. No other manual scratch file was created.

Task 1 core, registry metadata, native Anthropic/OAuth adapters, old sk-ant owner, Task 3 files, coordinator docs/spec/ledger, and SEC feature code were not edited or staged. Task 3's new `output_events.py` and event/lifetime tests remain untracked and untouched by this task. No provider/network call, live credential/token/.env/DB access, install, new tracing exporter, subagent, merge, push, or restart was used.

## Important Finding: Bearer Context

The old context-free Bearer alternative rejected `Bearer shares remain outstanding` as an unknown authentication literal. The minimal production change replaces only that alternative with:

```text
(?i:(?:Proxy-)?Authorization:[ \t]*Bearer)[ \t]+[A-Za-z0-9._~+/-]+=*
```

The existing outer `(?<![A-Za-z0-9_])` boundary and every provider-key alternative are unchanged. The header name, optional Proxy prefix, and Bearer scheme are case-insensitive. A colon is required immediately after the header name, followed by zero or more spaces/tabs; the Bearer scheme requires one or more spaces/tabs before a token. Supported token characters and optional trailing equals padding are unchanged. This is the specified explicit-header literal rule, not a general HTTP header parser or arbitrary unknown-secret detector.

Bare Bearer financial prose and token-looking bare Bearer strings now remain unchanged in declared text, JSON values, and JSON keys. The real four-adapter tests prove financial JSON and text both survive. Explicit Authorization/Proxy-Authorization Bearer literals still reject the whole result as `invalid_value`. Captured bare bearer values still reject through the unchanged exact guard as `known_secret`, without successful rewriting. Provider prefixes, recursive credential-key rejection, JSON bounds, policy lookup, reducers, and wrapper envelopes were not changed in this round.

### Expectation Lineage

The initial Task 2 bare-Bearer rejection expectations were rewritten explicitly under the new ruling, not silently removed:

- `test_narrow_known_auth_syntax_rejects_whole_result_without_rewriting` retains its text/value/key matrix. Its former `bearer` and `lowercase-bearer` cases are now named `authorization-header` and `mixed-case-proxy-header`, with explicit headers, mixed case, tab separators, and the supported token alphabet. The five provider-key cases are unchanged.
- The original bare fixture strings now appear in `test_bare_bearer_without_authorization_header_is_public`, alongside uppercase/lowercase financial prose. Its 12 cases assert exact preservation across declared text, JSON value, and JSON key positions.
- `test_bare_bearer_financial_prose_survives_every_adapter` adds eight real-adapter positives: JSON and text in all four channels.
- `test_authorization_header_bearer_is_rejected_by_every_adapter` adds eight header-context rejection controls without registering the token or using a credential-bearing JSON key.
- `test_captured_bare_bearer_is_still_rejected_by_every_adapter` adds eight JSON/text exact-secret controls across all four adapters.
- The existing `tests/test_claude_code_sdk_driver.py::test_bridge_sk_ant_secret_in_result_is_rejected` was neither edited nor renamed again. It passes in targeted/final runs and while only the Bearer branch is inversed.

No adapter fixture contract was changed in this round. Existing registry policies select the JSON news and text calendar paths used by the new tests.

## Minor Finding: Handled-Error Span

Local SDK inspection confirmed that `agents/tool.py` re-raises before `_on_handled_error` when the failure handler is disabled (lines 661-675), and that the skipped handler previously attached a span error before logging (lines 1862-1901). Public `agents.tracing.get_current_span` delegates to the current provider (`tracing/create.py:84`); public `Span.set_error` stores the supplied error (`tracing/spans.py:373`). No online documentation or provider execution was needed.

The OpenAI `safe_invoke` exception branch now obtains the current span through that public API and, only when a span exists, calls:

```python
span.set_error({"message": "Tool execution failed", "data": None})
```

It then returns the same sanitized error result as before. The fixed annotation contains no tool arguments, exception text, rejected value, or callback output. The SDK's default failure callback/handled-error logger remains disabled. No tracing configuration, processor, exporter, retry classification, or success-path behavior was added to production.

`test_openai_handled_tool_failure_marks_local_span_without_raw_detail` covers tool exceptions and SDK argument-parse failures. It uses a real SDK `function_span` under a local `DefaultTraceProvider` with no processors, reads the in-memory span error, and restores the prior provider in `finally`. Each case first proves a successful tool result leaves its span unmarked, then requires the failing span's complete error payload to equal the fixed content-only annotation. Existing raw-error/argument non-leak and bounded-result checks remain; no span is exported. Existing SDK parse-error and four-adapter diagnostic owners are also included in the targeted span run.

This restores the handled-error signal only. It does not claim to solve the separate Task 3 argument/event/tracing-data boundary.

## RED And GREEN Evidence

All product executions used the approved closed runner. Each run directory below contains its exact `command.json`, `output.log`, and `results.xml`. Counts and JUnit hashes were independently parsed locally using a cleared environment and standard-library XML/JSON only. Every row has zero errors and zero skips; deselected tests are not counted as skips.

| Run | Pass | Fail | Exit |
| --- | ---: | ---: | ---: |
| task2-fix1-red-20260912-01 | 303 | 30 | 1 |
| task2-fix1-bearer-green-20260912-02 | 62 | 0 | 0 |
| task2-fix1-span-green-20260912-03 | 8 | 0 | 0 |
| task2-fix1-focused-green-20260912-04 | 754 | 0 | 0 |
| task2-fix1-inverse-bare-context-20260912-05 | 8 | 20 | 1 |
| task2-fix1-inverse-header-rejection-20260912-06 | 40 | 14 | 1 |
| task2-fix1-inverse-span-20260912-07 | 6 | 2 | 1 |
| task2-fix1-restored-green-20260912-08 | 754 | 0 | 0 |

Run 01 changed only the two test files. Its exact failures were 12 policy bare-Bearer preservation cases, eight real-adapter financial preservation cases, eight captured-bearer cases receiving the old syntax `invalid_value` instead of exact `known_secret`, and two missing span annotations (`None` instead of the fixed payload). Thus the eight captured-bearer RED cases demonstrate the old rejection path/code, not a prior secret leak. There were no collection/import errors. The two production fixes were then applied separately and checked in runs 02 and 03.

Final census: **333 Task 2 tests** (187 policy + 146 channels), up from 295 by 38 focused new cases. The same **421 existing tests** pass: 34 agents, 61 subagent, 12 tool-calling, 13 financial-calculation, 46 ChatGPT OAuth, 51 Claude OAuth, 25 macro-calendar, 141 runtime-binding, 27 probe, and 11 security. Run 08 reports 754 passed in 24.67 seconds. Runs 04 and 08 are repeated verification of the same test set, not additive test counts.

Final command:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task2-fix1-restored-green-20260912-08 backend tests/test_tool_output_policy.py tests/test_tool_output_channels.py tests/test_agents.py tests/test_subagent.py tests/test_tool_calling.py tests/test_financial_calculation_tools.py tests/test_security.py tests/test_chatgpt_oauth_driver.py tests/test_claude_code_sdk_driver.py tests/test_macro_calendar_read.py tests/test_task_runtime_binding.py tests/test_probe_harness.py -q --show-capture=no -rN
```

## Inverses And Restoration

All mutations and restorations used `apply_patch` on an authorized product file only. Each test process completed before its mutation was restored, with restoration in `finally`. No core mutation occurred, and no test was changed during inverse verification.

| Run | Temporary mutation | Decisive outcome |
| --- | --- | --- |
| 05 | Replace the new header-context branch with the old bare-Bearer branch | All 20 bare public preservation cases fail; eight header-rejection controls still pass. |
| 06 | Prefix only the Bearer header alternative with an always-failing `(?!)` assertion | Six policy header cases and eight real-adapter header controls admit forbidden data: 14 failures. Public positives, provider-key cases, and old/new sk-ant owners remain among 40 passes. |
| 07 | Replace only `span.set_error(...)` with `pass` | Both local-span owners fail with `error is None`; six existing diagnostic/parse-error cases still pass. |

Mutated source SHA-256 values:

```text
05 bb33cc7a2444c785453045bbf2be40f5479f065031035e79702063e8c0df11b7  src/tools/result_policy.py
06 60651be60b991adff894e99b12b1a57d9b6646ebf1652b1dfab32b7391ea83da  src/tools/result_policy.py
07 45adac92ca769fb027ba1af338d4bb5683b17c311e6bea49001473c2890e0ee6  src/agents/openai_agent/tools.py
```

Each restoration matched its pre-inverse source hash below. Final GREEN ran after all three restorations; no subsequent product/test edits were made before commit.

```text
52014871ec1120334965c43b21371c568b1a92e9d5c9569ceeab550974a06e6e  src/tools/result_policy.py
b22615874e444fa012d8e30eb4dc78f36d908ea26396df4bb3281630af221244  src/agents/openai_agent/tools.py
954543882ee618e23edd9e4c938c75263f4e3eed768ddc9d3ad0d64061404541  tests/test_tool_output_policy.py
392d454067b15e1efe21969f8589cc161c756a97e1580c90ce89565d02d974e5  tests/test_tool_output_channels.py
```

JUnit SHA-256 values (run suffixes match the table):

```text
01 340f4775c2a2f467b643e7973e048b0d0b79614c518f103734f3baf1114da333
02 58355acb5bba5911eecf33d3b25617af68e94042eb5793b02dbff3c5bffdd871
03 c56e1ae3bc63f817e60baab803dfdb201cdc5675e04a1e1d5ca90993b2038a8c
04 a1c7d9eedf56c6ba358ece65f9a373961f2073bc6faaee24e83df3499b6c8821
05 43559a4668d7c1e7cca41949efba30c109248f0851d478f8d65fece1d49216af
06 6958328a799fb1f7558a606d57ae8f9f0e21b05534b3fe7819e38757ce044c25
07 59f9573affc26a3147f071e3ef8a27cc453eb74297601ede1787becf2aa43818
08 2c7bc1be55269718b3447817ee2a80b690a96fc00f7255110499bfdd4600963b
```

## Handoff

Working and staged `git diff --check` passed. Post-commit verification confirmed the exact four-file scope and authorized parent. The index is empty. A path-scoped diff against the authorized base is empty for Task 1 core, both frozen OAuth drivers, and the existing Claude sk-ant test file.

Only the coordinator's plan/spec changes and Task 3's new output-events source and two test files remain visible outside this commit. They were not staged or altered. This round makes no additional bounds, normalization, registry, reducer, feature, or speculative security changes. Rereview and whole-branch acceptance remain coordinator-owned; the paused SEC integration remains outside this delivery.
