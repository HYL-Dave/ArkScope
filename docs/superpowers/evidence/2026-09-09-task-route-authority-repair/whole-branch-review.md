# Final Whole-Branch Review: Four-Task Route Authority

**Ready to merge? No.** Two Important findings: one P1 and one P2. No additional
Critical or Minor findings. Most route, receipt and refresh requirements are
implemented, but the secret-free failure contract and the specified
current-conversation override lifetime still have gaps.

## Findings

### P1: Structured Refusal Metadata Bypasses Selected-Key Redaction

Locations: [query.py:562](/tmp/arkscope-task-route-authority/src/api/routes/query.py:562),
[research_run_manager.py:170](/tmp/arkscope-task-route-authority/src/research_run_manager.py:170),
and the earlier sink in [agent.py:468](/tmp/arkscope-task-route-authority/src/agents/anthropic_agent/agent.py:468).

An admitted Anthropic API-key Research execution returning HTTP 200 with
`stop_reason="refusal"` does not enter the new sanitized exception handler.
`AnthropicRefusalError` retains provider-controlled `stop_details`, incorporates
its category in the error string, and the native agent logs that string before
yielding the raw details. The new legacy-stream sanitizer processes only
`error`, `message` and `detail`, leaving `stop_details` unchanged. Managed
Research similarly sanitizes the main error string, then copies `stop_details`
unchanged through `_typed_error_event_data` into `append_event`.

Consequently, a provider echo of the selected key in a refusal category reaches
logs; an echo in the explanation alone reaches SSE and durable/public Research
event data. The actual persistence sink serializes that dictionary at
[research_runs.py:733](/tmp/arkscope-task-route-authority/src/research_runs.py:733),
and [_event_dict:111](/tmp/arkscope-task-route-authority/src/api/routes/research.py:111)
returns it without removing refusal details. Redacting only the main error
string cannot repair these earlier or nested disclosures.

The new offline diagnostic below confirms this with the real Anthropic SDK and
a synthetic transport. Each case makes exactly one mocked request and remains
an error, with no fallback. A benign refusal is the positive control. Existing
key-echo tests exercise raised HTTP errors and flat error events, not this
HTTP-200 semantic-failure branch. This is an unclosed binding requirement in
the repaired failure surface, not a claim that every underlying sink was newly
introduced by this branch.

Required correction: sanitize or reduce structured refusal details using the
captured binding before the native log/event, and enforce the same closed safe
shape at both Research event boundaries. Preserve the `model_refusal` code and
safe useful refusal metadata. Add category/explanation key-echo controls for
logs, legacy SSE and managed SQLite event replay.

### P2: Same-Conversation Overrides Are Lost on Ordinary App Navigation

Location: [Research.tsx:280](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:280).
The changed `rememberUserSelection` stores the override only in component-local
state, initialized to null at line 222. The shell renders Research and other
pages as mutually exclusive component branches at
[App.tsx:160](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/App.tsx:160).
Navigating to Home or Settings therefore unmounts that state. Returning reloads
the same active thread from session storage at
[Research.tsx:380](/tmp/arkscope-task-route-authority/apps/arkscope-web/src/Research.tsx:380),
but the explicit tuple is gone and `resolveResearchSelection` selects Settings.

Concrete workflow: in thread T, explicitly choose Sol/low while Settings says
Luna/xhigh; visit another App page and return to T without choosing another/new
conversation. The next turn sends Luna/xhigh. This contradicts the plan's
instruction to clear the override only on actual new/open-another-conversation
actions. The existing same-conversation and first-ID tests keep Research
mounted, so they do not cover this shell lifecycle. This finding is a static
caller/state-lifetime trace, not a newly executed UI test.

Required correction: retain the transient current-conversation tuple above the
page-unmount boundary, keyed to the current conversation, and clear it on the
specified new/other/delete actions. Do not restore global historical
localStorage preferences or derive authority from stored message tuples. Add a
Research -> Home/Settings -> same-thread navigation control alongside the
existing open-other reset control.

## Scope and Method

- Worktree: `/tmp/arkscope-task-route-authority`.
- Immutable base: `fb12f27e92c182ae5ff425595a4e9d2f947d601d`.
- Immutable head: `090a72258e76f84367c886da0e41ae79e181d2c0`.
- Package SHA-256: `828abd1b322da4f5cc935c524c9807bfff6db6b586f1b88ce7f7973263e8000b`.
- Compared the package's diff body byte-for-byte with `git diff --unified=10`
  for the immutable range. It matches; the package also contains its commit
  list and stat preamble. Reviewed all changed runtime/frontend modules and
  behavioral test changes, with surrounding callers, SDK source and storage
  paths for reachability. Used the requesting-code-review rubric directly,
  without subagents or inherited agent state.
- Read the approved plan, canonical implementation/review reports, integration
  correction, ledger, mutation/browser records and hand-test guide. Concurrent
  controller documentation assembly is distinguished from the immutable code.

## Strengths and Contract Checks

| Area | Independent code assessment |
| --- | --- |
| Four-task admission | Task IDs, capability registry, retirement, exact Spark task/auth/plan admission and Fable OAuth exclusion are unchanged. `_db_route` raises a bounded typed failure for all four tasks; genuinely missing rows still reach documented defaults. |
| Research handoff | HTTP capture precedes persistence and scheduling; the manager checks provider/auth/credential identity and refuses missing bindings. API-key snapshots and controlled original-ID OAuth refresh prevent active-credential reselection across the managed/legacy streaming paths. |
| Native and child clients | Main and child OpenAI Agents use explicit per-agent `OpenAIResponsesModel` clients, not the global default. The installed SDK runs synchronous function tools through context-preserving `asyncio.to_thread`; native Anthropic delegation executes within the active context. Same-provider children inherit the parent, deliberate cross-provider children create a separate boundary, and unsupported direct-SDK OAuth remains rejected. Subscription Research's read-only tool allowlists do not expose that delegation tool. |
| Error and trace controls | Captured-key redaction precedes truncation and exception logging on the ordinary repaired paths. All four OpenAI Runner sites explicitly disable sensitive trace payloads while retaining ordinary metadata/usage. Finding P1 identifies the remaining structured-refusal exception to the confidentiality contract. |
| Fixed-task execution | Card APIs capture complete model/effort/auth selections before gathering or dispatch and pass them through synthesis, translation and the direct evidence-translation caller. Explicit provider overrides retain the documented defaults; selected failures do not introduce a new provider/effort/auth retry. |
| Persistence | Additive receipt/version tables preserve old result JSON. New output and receipt writes commit together; translation uses `BEGIN IMMEDIATE` for cross-instance read/merge/write serialization. Read transactions keep cache and receipt snapshots consistent. A legacy cache is archived with unknown metadata before its first successful refresh. |
| API and card UI | The four-field receipt excludes credentials, preserves historical provider/model, and leaves missing metadata unknown. The frontend rejects malformed present receipts, keeps timeout arguments, distinguishes no-op, and does not borrow Settings for history. Cache reads do not dispatch; explicit refresh failures retain old output/receipt; successful earlier versions remain stored. |
| Research UI | Settings replaces fixed/default/history/global-preference authority; current mounted-conversation overrides survive acknowledgment and later turns, and new/other conversations reset them. Finding P2 covers the missing shell-unmount case. |
| Lifecycle | Existing preflight/start digest checks bind route, effort, runtime and credential generation; controller dispatch resolves the original ID and rejects generation mismatch. Previous-run source and next-run confirmation now display distinct full tuples. |
| Head test correction | `test_events.py` asserts the literal custom Anthropic model, medium effort and exactly one stream call. The supported-model control is retained; the separate real-registry Haiku no-effort control remains direct-agent coverage, not a relaxation of task admission. No runtime rollback, skip or registry mutation was used. |

## Verification and Limitations

- Supplied final backend completion: **7,537 passed, 12 skipped, exit 0**,
  818.88 seconds, three disclosed edgar deprecation warnings. Independently
  read `backend-final.xml`: 7,549 total, 12 skipped, zero failures/errors.
  This is inspected controller-run evidence, not a reviewer rerun.
- Supplied final frontend completion: **1,739 passed**. Independently read the
  final JUnit root: 1,739 tests, zero failures/errors. Typecheck/build success
  remains attributed to the supplied evidence; no duplicate full suites ran.
- Inspected the six restored mutation records, exact changed lines, named
  failing owners and restoration evidence against the 1,415-backend/149-UI
  focused baselines. The additional cache-mutation teardown error is not a
  separate owner. These mutations do not exercise either finding above.
- Read the synthetic browser harness and its 64-scene record. Independently
  viewed the Traditional Chinese mobile saved-card refresh-failure screenshot
  and English desktop next-run confirmation screenshot; prior content/source
  and next-run details are readable and distinct. No new browser run or server
  was started. The browser evidence is synthetic, not live provider acceptance.
- `git diff --check` for the immutable branch range is clean. Runtime, tests
  and frontend remain unchanged against Head; the index remains untouched.
- The eventkit import-order error is supported by the supplied original-base
  reproduction and does not fail the final full suite. The zero-argument
  OpenAI compaction constructor is pre-existing, caught and disabled, not newly
  enabled here. Treat both as separate follow-ups, along with the existing
  Vite chunk warning and edgar deprecations; none accounts for these findings.
- No provider/account/live-auth validation, production migration, private
  configuration or credential-store inspection was performed. Merge, push and
  App restart remain unperformed and unauthorized. The sole authored file is
  this report, written with `apply_patch`.

## Assessment

**Ready to merge: No.** Fix the reproduced confidentiality gap and the
same-conversation override-lifetime gap, add their missing behavioral controls,
and obtain focused re-review. The broad passing suites support the rest of the
implementation but do not override these concrete contract failures.

## New Offline Diagnostic

This report-local doctest exercises the native Anthropic stream with a real SDK
and synthetic HTTP transport, then the managed Research error-event builder.
Configuration, scratchpad, context management, tools and prompt construction
are replaced in memory. It reads no credentials or production stores and makes
no external requests. The string used as a key is a synthetic fixture only.

Executed from the review worktree using:

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q --noconftest -p no:cacheprovider --doctest-glob=final-review.md .superpowers/sdd/2026-09-09-task-route-authority-repair/final-review.md --tb=short
```

Final diagnostic result: **1 passed in 2.08 seconds, exit 0**. The wrapper
reported only loopback, `external_probe: ENETUNREACH`, and no inherited
credentials. This doctest deliberately asserts the observed vulnerable output;
its pass confirms the finding, not remediation. Its tuple records mocked
request count, terminal type, and key presence in log, native SSE, managed
error-event payload and sanitized main error text, respectively. The first
two-case run also passed (2.09 seconds); the final run adds the
explanation-only control without changing implementation.

```pycon
>>> import asyncio, io, json, logging
>>> from contextlib import ExitStack
>>> from unittest.mock import MagicMock, patch
>>> import httpx2
>>> from anthropic import Anthropic
>>> from src.agents import config as cfg
>>> from src.agents.anthropic_agent import agent as aa
>>> from src.auth_drivers import live_resolver as live
>>> from src.auth_drivers.runtime_binding import RuntimeAuthBinding, activate_runtime_auth
>>> from src.research_errors import classify_research_failure
>>> from src.research_run_manager import _typed_error_event_data
>>> def inspect_refusal(category, explanation=None):
...     secret = "fixture-refusal-alpha"
...     model = "claude-fable-5-1"
...     requests = []
...     def response(request):
...         requests.append(request)
...         frames = [
...             {"type": "message_start", "message": {"id": "msg_fixture", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0}}},
...             {"type": "message_delta", "delta": {"stop_reason": "refusal", "stop_sequence": None, "stop_details": {"type": "refusal", "category": category, "explanation": explanation or category}}, "usage": {"output_tokens": 0}},
...             {"type": "message_stop"},
...         ]
...         body = "".join("event: " + frame["type"] + "\ndata: " + json.dumps(frame) + "\n\n" for frame in frames)
...         return httpx2.Response(200, text=body, headers={"content-type": "text/event-stream"})
...     log = io.StringIO()
...     handler = logging.StreamHandler(log)
...     aa.logger.addHandler(handler)
...     binding = RuntimeAuthBinding("anthropic", "db_api_key", "api_key", "local:1", secret)
...     try:
...         with ExitStack() as stack:
...             client = stack.enter_context(Anthropic(api_key=secret, http_client=httpx2.Client(transport=httpx2.MockTransport(response))))
...             for target, name, value in [
...                 (aa, "get_agent_config", cfg.AgentConfig()),
...                 (aa, "_build_anthropic_tools_list", []),
...                 (aa, "Scratchpad", MagicMock()),
...                 (aa, "ContextManager", MagicMock()),
...                 (aa, "is_capture_enabled", False),
...                 (live, "live_anthropic_client", client),
...             ]:
...                 _ = stack.enter_context(patch.object(target, name, return_value=value))
...             _ = stack.enter_context(patch("src.agents.shared.prompts.build_system_prompt", return_value="offline"))
...             _ = stack.enter_context(activate_runtime_auth(binding))
...             async def collect():
...                 return [event async for event in aa.run_query_stream("offline", model=model, effort="high", dal=object())]
...             terminal = asyncio.run(collect())[-1]
...             failure = classify_research_failure(terminal.data["error"], explicit_code=terminal.data["code"])
...             replay = _typed_error_event_data(terminal.data, failure)
...             return (len(requests), terminal.type.value, secret in log.getvalue(), secret in terminal.to_sse(), secret in json.dumps(replay), secret in failure.detail)
...     finally:
...         aa.logger.removeHandler(handler)
>>> inspect_refusal("fixture-refusal-alpha")
(1, 'error', True, True, True, False)
>>> inspect_refusal("policy", "fixture-refusal-alpha")
(1, 'error', False, True, True, False)
>>> inspect_refusal("policy")
(1, 'error', False, False, False, False)

```
