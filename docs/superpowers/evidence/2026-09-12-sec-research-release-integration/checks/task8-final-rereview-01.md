# Task8 Final Scoped Re-Review

## Verdict

**NEEDS FIXES.** The three named findings are **ADDRESSED**, but the fix introduces one **Important** regression in the immediate OpenAI-parent/Anthropic-child composition. Open findings: **0 Critical, 1 Important, 0 Minor**. This is a source-review verdict, not merge, deployment, or SQLite-activation approval.

- Worktree: `/tmp/arkscope-research-output-boundary`.
- W: `.superpowers/sdd/2026-09-12-sec-research-release-integration`, the plan workspace containing the supplied brief/package and this report.
- BASE: `a77a7c2e7cb1bb1b8d2b92cd4cfb129f299f6687`.
- HEAD: `911d69a28a2a633c82335ef378d0784875757000`; read back during this review.
- Immutable package: `W/task8-final-rereview-01.diff`, SHA256 `28c82e5e77e93e342a9aab1fe27aa34680394a7628afc3e147e2d64ab4089842`.
- Complete package read: ten files, five product and five test files, 1222 insertions and 155 deletions. The comparison was not regenerated.

## Named Findings

### I1: ADDRESSED

The named nested-loop failure is repaired. [Anthropic async tool dispatch:1307](/tmp/arkscope-research-output-boundary/src/agents/anthropic_agent/tools.py:1307) now treats delegation as an awaited path and calls `dispatch_subagent_async` at line 1330. [Shared dispatch:494](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:494) awaits the selected child inside inherited output and captured-auth scopes. The [Anthropic child:638](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:638) awaits `execute_tool_async`, which awaits `invoke_sec_tool`. That composition no longer reaches the synchronous SEC `asyncio.run` bridge on the parent's loop.

The [new dispatch owner:98](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_dispatch.py:98) retains real native parent/child SDK loops, tool dispatch and generated SEC services. Its next-turn assertion compares the child's received content to the entire expected successful envelope, rather than accepting a final answer or inventory membership. It checks all three SEC tools, the exact decimal `1234567890123456789.123`, filing continuation identity, document identity/text, unchanged acquisition/transport counts, selected model/provider, captured key despite replacement, inherited guard and client closure. It also covers public sync dispatch, the live synchronous Anthropic tool bridge and the OpenAI tool callable. The original RED receipt contains three envelope failures with `asyncio.run() cannot be called from a running event loop`, not import/setup failures.

Public [synchronous dispatch:421](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:421) remains a bridge for callers outside an event loop; [the synchronous tool mapping:1551](/tmp/arkscope-research-output-boundary/src/agents/anthropic_agent/tools.py:1551) remains live. The private runner names now each denote their single async implementation. Existing direct-owner assertions were adapted, including [the Fable pre-client rejection:72](/tmp/arkscope-research-output-boundary/tests/test_fable_5_1_runtime.py:72), rather than retaining test-only compatibility wrappers.

For cancellation while delegated SEC work is actually in flight, [the managed-run test:176](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_dispatch.py:176) holds generated acquisition cleanup, repeats cancellation, checks that the run stays running and exclusive operation admission stays busy, and verifies worker completion before client closure and terminal cancellation. It covers client-close failure without replacing cancellation. [OpenAI child close controls:298](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_dispatch.py:298) cover held close and model cancellation with close errors. These are supported by the existing SEC stop/join owner at `src/sec_research/tool_execution.py:70` and the new finalizers, not by removing operation protection.

The report's claims about configured choices and foreign-credential rejection are supported by unchanged selection/filtering code, the captured scopes at `subagent.py:494`, [foreign-secret dispatch coverage:269](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_dispatch.py:269), and the retained auth owners. This verdict is for I1's named execution and in-flight SEC lifetime defect; it does not excuse the distinct changed-caller regression N1 below.

### M1: ADDRESSED

[The acquisition factory:87](/tmp/arkscope-research-output-boundary/tests/test_sec_research_release_workflow.py:87) now increments `f.acquisitions` on entry. [The interrupted workflow:252](/tmp/arkscope-research-output-boundary/tests/test_sec_research_release_workflow.py:252) snapshots that count after the failed refresh and asserts no increase after retained-reference reopening and the stored-only facts call; line 285 repeats the assertion after cleanup and another reopening.

The original controls remain: transport equality, unavailable/empty stored response, exact retained values and references, staged bytes, reservation/orphan accounting, exact cleanup candidates, exclusion of pinned objects, freed-byte accounting and durable readback. `reopen_saved` at line 149 reads the pinned citations through the retained reader. This closes the factory-entry observation gap without claiming a previously demonstrated production acquisition defect.

### Delegated Citation Interface: ADDRESSED

[The host-owned observer:72](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:72) accepts only actual SEC names, checks the entire result and arguments before projecting with unchanged `citation_event_fields`, then creates an ordinary `tool_end` with a bounded preview. The [child completion adapter:107](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:107) isolates child call IDs with a fresh invocation namespace. Actual completion sites are the Anthropic tool return at line 639 and the OpenAI `RunHooks.on_tool_end` at line 728. No delegate-answer JSON field supplies citation authority; the dispatcher return fields at line 505 remain unchanged.

[Anthropic's parent collector:550](/tmp/arkscope-research-output-boundary/src/agents/anthropic_agent/agent.py:550) is scoped around awaited delegation and drains admitted child completions before the delegate completion or propagated exception/cancellation. `GeneratorExit` is deliberately outside its yielding exception handler. [OpenAI's parent wrapper:721](/tmp/arkscope-research-output-boundary/src/agents/openai_agent/agent.py:721) connects the observer to the existing `ToolEvents` queue/ready signal and active gate. Its existing finite cancellation drain and exact worker join remain in place at lines 749 and 761.

The SDK ownership correction is substantive and necessary. In the installed `agents/run_internal/tool_execution.py`, `_cancel_pending_tasks_for_parent_cancellation` at line 1777 cancels tasks and attaches callbacks without awaiting them; invocation work has its own task at line 2041, with further cancellation handling at line 2179. Therefore merely awaiting/joining `Runner.run` is not sufficient evidence that child cleanup finished. [The new task owner:35](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:35) records the actual current invocation task, excludes its own enclosing task, stops further tracking, cancels pending tasks and shield-joins them through repeated cancellation. Dispatch tracks delegated calls at line 453. The OpenAI child wraps only selected SEC callables at line 709, so its separate owner tracks the SDK task executing the real SEC work. It closes admission before joining those tasks and then closing the child client at line 774. The parent observer similarly closes admission before joining at line 100. No delegation worker or detached replacement task is created.

The following retained tests exercise those contracts on final source:

- [Native terminal/readback:179](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:179): all four native parent/child provider combinations, all three tools, success/failure/cancel, complete child envelopes, reopening both event and assistant-message references, unique completion IDs, and direct retained-reference reads. Success also checks SEC completions precede the delegate completion and verifies the exact delegate JSON field set.
- [Invocation isolation:220](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:220), forged delegate metadata at line 236, malformed-result typed gaps at line 249, and foreign-secret rejection at line 273.
- [Real task cancellation:292](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:292): the `Runner.run` observer calls the saved real SDK runner; cancellation, held async client cleanup, repeated cancellation, late valid/secret hooks and operation exclusion are checked for both native parents. This is not just a direct mocked dispatch result.
- [Explicit stream close:380](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:380) checks no remaining event is yielded on close. [The OpenAI-child SEC-worker test:403](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:403) holds the actual SEC worker, checks captured scope and operation exclusion, and requires worker finish before client/parent release.

The unchanged validators and projection still provide the final public/durable boundary: `src/sec_research/citations.py:362` and `:384`, `src/agents/shared/output_events.py:239`, and `src/research_tool_trace.py:25`. The latter can retain a completion-only identified call, keeps its real SEC name/input, and copies citations to the durable row. `src/research_run_manager.py:94` holds the parent operation lease around execution/persistence, including cancellation terminalization. The unchanged [OAuth-child fail-closed test:582](/tmp/arkscope-research-output-boundary/tests/test_task_runtime_binding.py:582) remains in the final covering run. This patch neither adds OAuth-parent delegation nor changes their inventories.

## New Breakage

### Important N1: OpenAI Delegation Now Runs Blocking Anthropic SDK I/O On The Parent Event Loop

**Primary changed location:** [src/agents/openai_agent/tools.py:654](/tmp/arkscope-research-output-boundary/src/agents/openai_agent/tools.py:654). Blocking callee: [src/agents/shared/subagent.py:610](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:610). **Confidence: high, static source evidence; no new runtime reproduction claimed.**

The decorator change from `def tool_delegate_to_subagent` to `async def` changes execution placement, not just return type. The installed SDK detects coroutine functions at [agents/tool.py:2687](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/agents/tool.py:2687). Its [invocation branch:2730](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/agents/tool.py:2730) directly awaits async functions, but runs synchronous functions through `asyncio.to_thread` at lines 2737/2739. The immutable BASE side had the synchronous delegate, so an Anthropic child performed its synchronous SDK work off the OpenAI parent's loop.

At HEAD, the OpenAI SDK directly awaits the new delegate, which awaits shared dispatch and then `_run_anthropic_subagent` on that same loop. That runner still constructs the explicitly synchronous `live_anthropic_client` (`src/auth_drivers/live_resolver.py:107`) and uses `with stream_ctx` plus `stream.get_final_message()` without any async I/O or worker boundary. Creating the parent runner task at `src/agents/openai_agent/agent.py:730` does not move it to another thread. Managed Research itself is scheduled on the application's loop at `src/research_run_manager.py:305`.

**Trigger and impact:** an otherwise admitted native OpenAI parent delegates to an Anthropic child, including the tested `deep_researcher` override. While that child's model stream waits for network data, the parent loop cannot run its cancellation handling, queue drain, timers or other tasks sharing that loop. A slow child model can therefore stall concurrent Research/API work for the duration of synchronous stream consumption. The new task-join sets only act once execution reaches a cancellation/await boundary; they cannot make this blocking phase cooperative. This is an availability/responsiveness regression, not evidence of credential disclosure, corrupt SEC results, premature operation-lock release, or failure of OpenAI-to-OpenAI delegation.

**Why this is new and in scope:** the report explicitly acknowledges preserving synchronous Anthropic SDK phases. That accurately describes the child body, but does not preserve their previous off-loop placement under the OpenAI SDK's synchronous-tool adapter. The review brief explicitly includes immediate changed caller composition. I am not reopening the pre-existing synchronous network behavior of native Anthropic parents; N1 is the newly affected OpenAI root caused by this diff.

**Why the covering run does not settle it:** the Anthropic fake transport in `tests/test_sec_research_delegated_trace.py:98` returns its response immediately. Its synthetic cancellation originates within that response path, not from a concurrently scheduled cancellation while an Anthropic stream is blocked. The held model/close tests use an OpenAI child; the Anthropic-child held-work test cancels at the SEC await. Consequently the successful four-provider-combination matrix establishes results/retention but not event-loop progress during the changed synchronous phase.

**Required repair/verification:** preserve nonblocking parent-loop execution for the Anthropic child's SDK phases while retaining captured auth, observer isolation and owned cancellation/join. A genuinely awaitable Anthropic client path or an explicitly owned, context-propagating blocking-work boundary needs a controller scope decision; merely reverting to an unowned SDK executor would undo the ownership repair. The bounded missing regression control is an actual OpenAI-parent/Anthropic-child composition with a held fake Anthropic stream and an independent event-loop heartbeat/cancellation request, plus the existing scope/join controls. Coordinate that probe with the controller before running it. No such probe or product edit was performed by this reviewer.

## Out-Of-Scope Observations

No additional out-of-scope finding is promoted. Pre-existing synchronous Anthropic-parent model I/O, unchanged OAuth delegation exclusions and unsupported external callers of private runner helpers are not new findings here. The private-helper coroutine change was explicitly directed by the controller, with public sync callers retained. Controller-owned evidence/census/frontend readback and the frozen full-backend gate remain independent; this report does not replace them.

## Verified Evidence

The brief was read first, followed by the final-fix brief/rulings, original I1/M1 report, the full final-fix report, and preflight including its SDK-ownership and private-owner amendments. All 1982 lines of the supplied immutable ten-file package were read. Unchanged source reads were limited to the named citation/auth/operation boundaries and the immediate SDK/caller composition described above; there was no second repository-wide review.

Current SHA256 values for all ten source/test files match the final-fix report and receipt inventory. HEAD matches the supplied commit, and tracked source/tests are clean. The index was read back empty. The three existing controller document changes were left alone. Runner source hashes also match the report: `run_checks.py` is `2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f`, and `offline_pytest.py` is `4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff`.

I inspected the 36-entry receipt inventory's dispositions, then checked selected receipt bytes and actual output/JUnit data, rather than treating the report's pass totals as proof. The following are **preserved runs, not reviewer reruns**:

| Receipt Suffix (`task8-final-fix-`) | Verified Result | What It Establishes |
| --- | --- | --- |
| `red-01` | 3 failures; no JUnit errors/skips; exit 1 | Original nested-loop error at all three complete-envelope assertions; warnings retained. |
| `red-citations-02` | 16 failures, 4 passes; exit 1 | Twelve terminal-combination and four isolation failures; forged-output controls already pass. |
| `red-citation-lifetime-02` | 2 failures, 1 pass; exit 1 | Actual SDK early parent release and abandoned SEC-worker cleanup, with a passing Anthropic-parent client control. |
| `green-private-owners-01` | 258 passes; exit 0 | Public sync/private async, Fable, auth, delegation and trace controls. |
| `restored-04` | 194 passes; exit 0 | Combined focused verification after final-source restoration. |
| `covering-03` | 1349 passes; exit 0 | Nineteen selected files; includes all 48 new delegation cases and both release workflows. |

The three final GREEN JUnit files independently contain respectively 258, 194 and 1349 test cases with zero failures, errors or skips. Actual command receipts specify the unchanged isolated `offline_pytest.py`, exact worktree and selected files; output summaries agree. I did not sum overlapping runs into an inflated coverage total.

All three final inverse artifacts were compared to `subagent.original-04.py`, and their source/test/command/log/JUnit hashes were checked against the manifests. These are single behavioral changes, not syntax/import failures:

| Boundary | Final Artifact SHA256 | Actual Kill |
| --- | --- | --- |
| Async client close shield | `ce93761306336ba1b52767e7d2b215c0c08c8442f9851cf1ea183bc58fa06bb7` | `inverse-close-04`: one failure, unfinished client-close assertion. |
| Child completion fence | `e591260a53c7ea02d15b8bfd03cf943e6caf704e762ca5ad53bb0a166f7b894a` | `inverse-citation-fence-02`: one failure; a late callback reaches `known_secret` during held cleanup. |
| Actual SDK invocation-task join | `09cd276413f545a8abeea6eac021af6fa88f4136c3ba3fde0b6a47dca4576ea9` | `inverse-sdk-join-02`: two lifetime failures and one passing control. |

The original SHA256 is `0d04e48041a66f3b1acd875f4c9fc4eba60283d165b79ff6e4242f0731576e83`. A fresh read-only `cmp` of the current shared source against that final original returned 0. Both final test snapshots match their current test files. The report properly distinguishes fixture errors, intermediate cleanup/SDK regressions and its collection SyntaxError from behavioral RED/inverse evidence. I checked selected material receipts, not every historical log or the controller's complete evidence census.

Installed SDK source read for the two material interfaces was not executed or modified: `agents/tool.py` SHA256 `304cce5a1e53d410d6c1ccf2c91ae07ad364a71e586ade6d6af3674b0cfb0150`; `agents/run_internal/tool_execution.py` SHA256 `86b91c62df0779e896143e5bc841a962d436099d79365497377dd9a233b02946`.

Reviewer actions were read-only file/Git/hash comparisons and standard-library JSON/XML receipt analysis, plus writing this report. No product import/execution, test collection/suite/probe, provider/model/CLI call, network call, production config/token/database access, install, restart, actual-store action, subagent, index/branch write, merge or push occurred. Initial absent-path lookups and oversized output reads were resolved with bounded reads; none was a test attempt. No reviewer-owned runner was launched or remains active.

## Overall Assessment

**Recommendation/workflow: revise.** Close I1, M1 and the delegated-citation gap separately, but do not accept this fix wave while N1 remains. The patch's successful retention and SDK-cleanup controls materially support those named repairs; they do not cover the newly blocking OpenAI caller. A targeted correction and coordinated focused verification are needed in addition to the controller's independent final gates. No deployment or SQLite-activation conclusion follows from this source-only review.
