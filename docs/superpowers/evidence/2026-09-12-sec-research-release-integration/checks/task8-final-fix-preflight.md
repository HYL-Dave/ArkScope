# Task8 Final Fix Preflight

Base: `a77a7c2e7cb1bb1b8d2b92cd4cfb129f299f6687`.
Worktree: `/tmp/arkscope-research-output-boundary`.
Recorded before any product source edit. Tests and generated receipts only have
changed so far; controller pending documents/evidence remain unstaged.

## Mechanism And Callers

Use one canonical shared async dispatcher and async child loops in
`src/agents/shared/subagent.py`. Retain synchronous dispatch/runner entrypoints
as bridges to those same loops, without cloning a runner. Anthropic child tool
calls await `execute_tool_async`; OpenAI child execution awaits `Runner.run`.
The existing synchronous Anthropic SDK stream phases remain unchanged.

Immediate async callers are Anthropic `execute_tool_async` in
`src/agents/anthropic_agent/tools.py` and the OpenAI decorated
`tool_delegate_to_subagent` in `src/agents/openai_agent/tools.py`. The latter
must be async to avoid the SDK's unowned synchronous-tool executor path.
Anthropic `execute_tool` and public `dispatch_subagent` remain synchronous.

## Ownership And Cancellation

Keep delegation awaited inside inherited output and captured child auth scopes.
No new delegation thread or detached child task. Cancellation propagates to
`invoke_sec_tool`, whose existing owned worker requests stop and joins through
repeated cancellation before returning control. Parent operation protection
therefore remains held while SEC cleanup is in flight. Each child runner owns
its constructed client and closes it before leaving child scopes. Async OpenAI
client cleanup follows the existing shield-and-join finalizer pattern and must
settle even after repeated parent cancellation.

Keep provider/model/auth/effort, defaults, required SEC and optional tool
filtering, output policy, operation locking and SEC worker implementation
unchanged. No nested-loop workaround or new model admission policy.

## Scope And Evidence

Product files: the three files named above only. Tests: new
`tests/test_sec_research_delegated_dispatch.py`, necessary existing subagent
mock updates, and M1's acquisition-entry counter/assertions in the existing
release workflow. No full framework matrix, subagents or full suites.

`task8-final-fix-red-01` reproduced all three real native parent/child failures
at the complete-envelope assertion, receiving the running-event-loop error.
`red-02` also exposed a cancellation-fixture parent model not admitted by the
managed Research route; that one failure is fixture error, not ownership proof.
The fixture now uses a locally admitted parent model; `red-03` reaches the
actual delegation failure. No product admission change is proposed or needed.

Use unchanged isolated runners and unique `task8-final-fix-*` receipts. Preserve
all failed attempts, one behavioral inverse with immutable original/mutant
artifacts, restored GREEN and focused covering verification. Source/tests only
will be committed; this preflight and the final report remain outside the commit.
All brief prohibitions remain in force. No broad change or unresolved design
ambiguity currently blocks this mechanism; escalate before any scope growth.

## Delegated Trace Interface Question

After the initial source edit, the controller asked whether child SEC citations
reach the parent's retained Research trace. Static readback: they do not. Both
child loops return answer/tools_used/token_usage only; shared dispatch adds
subagent/model/provider/error. Anthropic parent citation extraction receives
`delegate_to_subagent`, not the child's SEC tool names. `sec_citations_from_result`
returns no references for that name, and `validate_citation_event_fields` rejects
SEC citation metadata attached to a non-SEC tool. OpenAI child dispatch installs
no child trace hook either. Durable projection copies existing event citation
fields; it cannot recover references omitted by the child.

This is distinct from cancellation: the await chain can own SEC work, client
cleanup, output/auth and parent operation protection without forwarding durable
child references. If the retained-reference spec includes delegated SEC calls,
that is a load-bearing acceptance conflict. Controller ruling was requested on
blocking this wave versus separately owned follow-up. No nested trace event,
result contract or citation validation redesign is included in this repair.

## Proposed Bounded Citation Extension (Awaiting Controller Ruling)

Controller ruled the missing delegated references load-bearing, not optional.
Full delegated acceptance and final handoff are held; no citation extension has
been implemented. Proposed interface, matching the controller's unchanged-code
read:

- Shared subagent owner: invocation-local, code-installed observer of actual
  admitted SEC completions. Use the Anthropic child's real completion site and
  OpenAI RunHooks.on_tool_end. Project complete results with unchanged
  citation_event_fields before preview slicing. Emit ordinary flat tool_end
  events with actual SEC tool names and collision-isolated child call IDs.
  Keep delegate answer/result JSON unchanged; never trust citations claimed in it.
- OpenAI parent producer: connect observer to existing ToolEvents.publish,
  queue and ready signal. Keep its failure/cancellation drain, active gate and
  join of the exact runner task before releasing execution protection.
- Anthropic parent producer: invocation-local collector around awaited
  delegation; drain admitted child completions before delegate completion on
  success or before propagating failure/cancellation. Disable admission as the
  invocation ends; do not detach work or yield during GeneratorExit cleanup.
- No changes to citation validation, accepted tool names, AgentEvent field
  schema, durable trace projection, storage, UI or model/auth policy. Existing
  persistence retains the flat SEC completion events under the parent's run.

New product scope beyond current I1 files: only
src/agents/anthropic_agent/agent.py and src/agents/openai_agent/agent.py.
The shared subagent module is already owned. Extend focused regression/trace
tests with actual retention/reopening and completed-before-failure/cancel
controls; no nested trace framework or full framework matrix.

Supported combinations: native API-key Anthropic/OpenAI parents, each with
Anthropic/OpenAI children (four combinations). OAuth parents do not currently
expose delegation; OAuth-selected child SDK paths remain fail-closed. Standalone
sync callers keep their return contract without acquiring a Research sink.

Separately, self-review of new client cleanup reproduced cancellation being
masked by a close exception. Two RED receipts preserve it. Local cleanup now
joins while preserving prior cancellation; the focused I1/M1 run has 85 passes.
This did not change any trace/citation interface or extend product-file scope.

## Approved Extension And SDK Ownership Reconciliation

The controller appended the approved Delegated Citation Retention ruling to the
original brief. The proposal above is now implemented in the same five product
files, with `tests/test_sec_research_delegated_trace.py` as the focused retention
owner. The citation validator, event schema, durable projection, delegate JSON,
OAuth inventories and auth/model/storage/UI owners are unchanged.

`red-citations-02` recorded 16 behavioral failures for lost retained completions
and four passing forged-delegate controls. `red-citations-03` also reached the
missing completion assertion for malformed-result gaps and foreign-secret
rejection. The preceding `red-citations-01` had fixture setup errors only.

Actual SDK cancellation tests then exposed an additional immediate ownership
limit: installed OpenAI SDK function-tool cancellation cancels its invocation
tasks but attaches background callbacks instead of awaiting their cleanup
(`agents/run_internal/tool_execution.py`, `_cancel_pending_tasks_for_parent_cancellation`).
Thus joining Runner.run alone did not join a delegated client's cleanup, or a
child's SEC worker. `red-citation-lifetime-01` and `-02` preserve these behavioral
failures. They are not citation-schema problems or a basis for an SDK redesign.

The bounded correction remains in shared/subagent.py and its two already-owned
parent call sites: an async invocation-local observer scope retains actual
delegated-call tasks; the OpenAI child retains actual SEC invocation tasks by
wrapping only its selected SEC tool callables. No new task or worker is created
for delegation. On exit, admission stops, remaining owned tasks are cancelled
and shield-joined, then the child client closes. Existing SEC stop/worker logic
is unchanged. The Anthropic collector still drains after awaited cleanup and
never yields during GeneratorExit. OpenAI still publishes/drains through its
existing ToolEvents queue and active gate. Both task sets are invocation-local,
not a global buffer or nested tracing system.

`green-citation-lifetime-02`: five focused lifetime controls passed, including
actual task cancellation, repeated cancellation during held cleanup, late valid
and secret callbacks, and explicit close with admitted completions pending.
The preceding `green-citation-lifetime-01` was a missed `async` declaration and
collection error, not a behavioral RED; its receipt remains preserved.

Current phase: combined focused verification, then final-source inverse,
covering, self-review and scoped source/test commit. No design ruling is pending.
Final handoff will include a machine-readable inventory of every final-fix
command.json hash, exit status and disposition, plus immutable inverse paths and
hashes. Controller artifacts remain outside the index.

## Final Cleanup Ruling And Handoff

The appended private-owner cleanup ruling supersedes the initial intention to
retain private sync runner bridges. They were test-only and are now removed.
Public dispatch_subagent remains synchronous; each original private runner name
now denotes its single async implementation. Direct helper tests and the named
test_fable_5_1_runtime.py collateral call that async owner with all assertions
retained. No replacement facade was added.

Final commit: 911d69a28a2a633c82335ef378d0784875757000, ten scoped source/test files
only. The final private-owner/auth/sync focused run passed 258 tests. All three
inverses were rebound to final revision-04 source and killed behaviorally; exact
restore passed cmp, then restored focused verification passed 194 tests and
final scoped covering passed 1349 tests. All runner sessions completed.

Handoff evidence: task8-final-fix-report.md, task8-final-fix-receipt-inventory.json
(all 36 exact command receipts/dispositions), and task8-final-fix-inverse-proof.json
(eight inverse invocations, 20 immutable artifacts, exact hashes/restores).
No active runner or mutant remains; controller documents/evidence are unstaged
and the index is empty. No further design ruling is pending in this fix wave.
