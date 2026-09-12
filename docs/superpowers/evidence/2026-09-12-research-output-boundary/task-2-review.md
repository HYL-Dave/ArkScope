## Spec Compliance

- Verdict: Issues found. One Important Task2 public-content admission issue is reproduced below. The remaining reviewed Task2 requirements are satisfied; the separate Minor finding concerns SDK error observability.
- Scope: immutable `a81e4d92b5b9649dafbab6dbf7dee8ded181aa41..3e73d2aa8e1fb5925b388178f02e623e291a12df`, using `task-2-review.diff`. The later docs-only checkpoint, coordinator plan/census, and two Task3 test files are outside this review.
- Check: all eight brief-listed product/new-test files have corresponding hunks; the three additional existing-test files retain their owners with explicit policies or named replacements (`task-2-brief.md:3`, `task-2-report.md:78`).
- Not verified here: execution-wide credential capture, events/replay/scratchpad, argument protection, iterator lifetime, and whole-backend acceptance are pending Task3/coordinator work, not Task2 failures (`docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:67`, `task-2-report.md:175`). Approved core concurrency/marker behavior was not reopened.

## Strengths

- Trusted metadata fails closed and cannot be chosen by result content; all 54 registrations declare policies, with a separate explicit bridge-only delegation contract (`src/tools/registry.py:39`, `src/tools/registry.py:187`, `src/tools/result_policy.py:176`, `src/tools/result_policy.py:215`, `tests/test_tool_output_policy.py:123`).
- The shared admission path normalizes the closed native type set, scans values/keys and emitted numeric spellings, and enforces progressive depth/node/byte budgets without arbitrary object coercion (`src/tools/result_policy.py:81`, `src/tools/result_policy.py:105`, `src/tools/result_policy.py:195`, `tests/test_tool_output_policy.py:394`).
- Closed validators require literal True, receive detached normalized data, suppress exception details, and cannot change the returned encoding (`src/tools/result_policy.py:197`, `tests/test_tool_output_policy.py:325`, `tests/test_tool_output_policy.py:356`, `tests/test_tool_output_policy.py:376`).
- Real four-adapter tests establish canonical public-data equality; OAuth admission precedes the unchanged 12,000-character reducer, and both native macro paths now use admission (`tests/test_tool_output_channels.py:186`, `tests/test_tool_output_channels.py:351`, `tests/test_tool_output_channels.py:419`, `tests/test_tool_output_channels.py:430`). Different API/bridge inventories and post-reduction sizes are intentional; no SEC special case is required or introduced.
- Existing unknown sk-ant safety coverage now checks rejection with an admitted public control; wrapper-tag, unnamed-policy, schema, timeout, and preview owners remain present (`tests/test_claude_code_sdk_driver.py:790`, `tests/test_security.py:64`, `tests/test_chatgpt_oauth_driver.py:123`, `tests/test_claude_code_sdk_driver.py:769`).

## Issues

### Critical

- None identified in the scoped diff.

### Important

- `src/tools/result_policy.py:50`: the context-free Bearer alternative accepts case-insensitive `Bearer` at the start of a string or after any character outside `[A-Za-z0-9_]`, followed by spaces/tabs and `[A-Za-z0-9._~+/-]+` with optional trailing `=` characters; no right boundary or authentication context is required. Consequently ordinary financial prose such as `Bearer shares remain outstanding` matches `Bearer shares` and rejects the entire text or enclosing JSON result at `src/tools/result_policy.py:89`, despite no captured secret. The focused run reproduced both failures. This is a Task2 common-policy restriction, not pending Task3 work. It is not an entropy heuristic, but literal/prose ambiguity is unavoidable with this bare-substring rule; a zero-false-positive claim is not justified. Reconcile lossless public content with explicit-authentication rejection (`docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:39`, `docs/superpowers/specs/2026-09-12-research-output-boundary-design.md:57`): narrow the Bearer branch to explicit authentication context, or obtain an explicit specification decision accepting this exact restriction. Keep the provider-key branches and `tests/test_claude_code_sdk_driver.py:790` intact. Add legitimate financial-prose controls next to `tests/test_tool_output_policy.py:276`.

### Minor

- `src/agents/openai_agent/tools.py:48`: disabling the SDK failure handler and converting the propagated exception into a normal string also drops its previous handled-error span annotation. The installed SDK re-raises at `/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/agents/tool.py:671` before the callback at line 674; that callback previously attached the error at line 1893. The outer wrapper adds no sanitized replacement. Callers still receive a safe failure result, so this is a Minor observability regression, not a demonstrated runtime-retry failure or pending argument/capture protection. Retain a content-free/sanitized error-span signal and add a focused failed-tool tracing assertion without restoring raw exception/argument logging. This finding is source-traced, not independently executed.

## Checks And Evidence

- Read the supplied diff once in contiguous sections; no changed product file was read separately, no git commands were run, and no product/index/HEAD mutation was used to prove a finding. Only this requested report is manually edited.
- Named outside-diff check: native SDK failure-handler/logging and diagnostic truncation risk. Inspected `/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/agents/tool.py:661`, its handled-error/parse helpers at lines 1862/1918, its invocation path at line 2704, and `src/auth_drivers/runtime_binding.py:98`. The None failure callback bypasses handled-error logging; diagnostic sanitization precedes its 500-character truncation. Runtime retry classification is unchanged by this diff. SDK raw argument debug logging is argument-boundary/Task3 scope, not a newly reported Task2 result leak.
- Existing evidence: inspected `task2-final-green-20260912-17/output.log:12`, which reports 716 passed in 25.19s with no warning summary; read the six inverse groups and restoration limitations in `task-2-report.md:125`. The coordinator already independently parsed JUnit; no broad suite or inverse rerun was performed here.
- Focused named risk: legitimate public financial prose colliding with Bearer syntax. The following report-local doctest specifies the expected lossless behavior for text and a JSON field; it does not modify the implementation or execute a data tool.

```pycon
>>> from src.tools.result_policy import PUBLIC_JSON, PUBLIC_TEXT, admit_tool_result
>>> public = "Bearer shares remain outstanding"
>>> admit_tool_result(public, policy=PUBLIC_TEXT) == public
True
>>> import json
>>> json.loads(admit_tool_result({"note": public}, policy=PUBLIC_JSON)) == {"note": public}
True

```

## Assessment

- Focused check completed: `task2-review-bearer-prose-20260912-01/output.log:14` and `task2-review-bearer-prose-20260912-01/output.log:35` show `invalid_value` for both public examples. Result: one failing doctest containing both examples, one passing existing sk-ant control, exit 1, no warnings (`task2-review-bearer-prose-20260912-01/output.log:53`). This is expected reproduction RED, not a production mutation or broad-suite rerun.
- Exact runner command (recorded with JUnit in the same plan-local run directory): `/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-research-output-boundary/run_checks.py task2-review-bearer-prose-20260912-01 backend --doctest-glob=task-2-review.md --doctest-continue-on-failure .superpowers/sdd/2026-09-12-research-output-boundary/task-2-review.md tests/test_claude_code_sdk_driver.py::test_bridge_sk_ant_secret_in_result_is_rejected -q --show-capture=no -rN`.
- Task quality: Needs fixes.
- Reasoning: The centralized boundary and retained adapter owners are well structured; the bare-Bearer content restriction needs a narrower rule or an explicit authority decision before Task2 approval. No product fix, Task3 completion, or whole-branch approval is claimed.
