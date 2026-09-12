# Task 3 Integration Inventory

Base source paths read, no production I/O:
- OpenAI `run_query` async and `run_query_stream`: `_build_agent` owns selected
  SDK client; `_extract_tool_info` writes tool args and truncated tool outputs
  into scratchpad/replay before public yields; final answer saved before done.
- Anthropic `run_query_stream` owns selected client; sync run_query collects it.
  Thinking saved/truncated early; raw tool_input passed into compressor and
  scratchpad/replay. Guard all complete values before truncation/sinks.
- ChatGPT `_managed_stream` manages client cleanup; `_stream` loads then refreshes
  bearer, consumes SSE and emits text; final answer may come from output_items
  rather than deltas. Keep cleanup/retry/model selection intact.
- Claude `_stream` loads bearer then builds MCP callbacks; `_map` emits text,
  thinking, tool inputs/results and done; `_tool_end_event` currently redacts
  after preview slicing (must reorder). Preserve SDK authentication-source
  checks and isolated CLI config teardown.
- `research_run_manager.execute_research_run` appends ALL nonterminal events
  directly, including text. `query_agent_stream` yields and saves traces. Both
  need a guard before the append/yield even with injected stream_factory tests.
- `src/agents/shared/subagent.py` captures child auth and restores parent before
  returning answer. Shared execution guard must retain captured child secrets
  for late parent result serialization. Same-provider children inherit auth.
- `src/agents/shared/scratchpad.py` and `replay.py` are downstream sinks. Prefer
  protecting complete values at producers, including tool args before execution,
  not adding silent altered-success JSON deep inside persistence helpers.
- `src/auth_drivers/live_resolver.py` creates selected SDK clients but is used by
  other tasks too. Register only the returned client key into an already active
  guard; never recapture or add ambient keys. Mocked clients require producer-side
  registration immediately after actual client construction as well.

Scope additions approved by coordinator before edits: src/agents/shared/subagent.py,
src/auth_drivers/live_resolver.py (only if necessary), src/research_run_manager.py,
src/api/routes/query.py. Shared scratchpad/replay changes require a concrete
pre-persistence path owner; do not turn all persisted artifacts into heuristically
redacted debug dumps.

Full-GO scope additionally includes src/agents/openai_agent/tools.py and
src/agents/anthropic_agent/tools.py for pre-handler argument admission only.
OpenAI's SDK dispatches tools before _extract_tool_info sees the resulting run
items; checking there cannot prevent a write or SDK argument logging. Its
on_invoke_tool boundary must check arguments before invoking the SDK callback.
The Anthropic dispatch boundary gives the matching direct-handler owner.
These files are Task2-owned until that review completes; the current narrow
new-output_events.py GO does not authorize editing them.

Async generators: holding a ContextVar token across a public yield can leak into
the consumer or fail on out-of-order generator interleaving. Prefer a wrapper
that retains an OutputGuard instance, enters activate_output_guard(guard) around
EACH upstream __anext__/aclose, and resets BEFORE yielding admitted events. Use
an async-generator decorator/wrapper to minimize indentation/refactors, but test
interleaved generators and actual closure. Native async nonstream function can
use an execution scope normally.

ResultPolicy admission owns structured tool outputs. Event metadata is a separate
closed event projection: preserve safe typed counters/IDs, reject invalid/secret
metadata or inputs with a typed output error rather than corrupting call IDs.
Prose fields get stateful/full-value projection. Unknown text-bearing event keys
must not become unscanned extra payload. Already admitted wrapper data can be
checked without destructive regex passes. Terminal answer never contains pending
raw secret, and partial tail is never flushed in plaintext on error/cancellation.

Avoid double buffering: use a trusted `ProtectedEventStream` async-iterator
type and an idempotent `protect_events(stream, *, guard=None)` factory. When the
producer already returned that EXACT type with the same active guard, manager
and route reuse it. A raw injected stream still goes through protection. Do not
trust payload booleans/subclasses claiming they were protected; mismatched guard
identity is a typed boundary failure, not silent adoption of another execution.
Native async-generator entry decorators may return this iterator while keeping
their public signature via wraps; sync Anthropic collector can consume it. OAuth
stream_llm returns it around existing cleanup-owning raw generators. The wrapper
activates its retained guard per upstream advance/close and never across yield.
Implement aclose, terminal closure, non-reentrant advancement, and per-wrapper
text/thinking matcher ownership. Closing one borrowed wrapper must not abort
other streams belonging to the shared parent guard. No payload-selected bypass.

Measured coordinator synthetic cost: 2,051-char fake bearer, 10,400-char public
answer, 3-char deltas -> 0.9406s matcher CPU and first emission after 2,736 input
chars. No live token/provider. Therefore do not add a second equal rolling tail
at manager/route. Bound is content-length latency, not a claimed wall-clock SLA.
This is an observation of current primitive, not a timing assertion in tests.

Pre-provider exact-secret checks on tool input protect write-capable tools,
scratchpad and compressor input persistence. Do not forward invalid credential-
bearing arguments to a handler and then hope output redaction repairs the write.
Preserve ordinary public URL/search inputs (no diagnostic entropy filter).

Diagnostic sanitizer remains for real exceptions. Provider text and tooling
names in log formatting also must not carry captured key before slicing.
Use static codes/type-only info where safe representation is unavailable.

Required inverse owners: stateless stream replacement, missing direct-client
registration, and missing pre-append guard against injected stream_factory.
Existing runtime echo/retry/tracing/card auth tests are positive controls.
