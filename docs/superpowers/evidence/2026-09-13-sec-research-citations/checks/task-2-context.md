# Source-Verified Event Context

Inspected locally, no network/provider access:
`/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/agents/lifecycle.py`
RunHooksBase.on_tool_start(context, agent, tool) and
on_tool_end(context, agent, tool, result) are async. The function-tool context is
ToolContext with tool_call_id, tool_name, tool_arguments. Actual invocation is in
agents/run_internal/tool_execution.py (on_tool_start around2033/end2169).
The old agents/_run_impl.py path does not exist in this installed version.
Local source SHA256s: lifecycle.py
5bbf13d8390ddad8a2678351919068230b8cdfb943001e387f894500cf94d4bd;
tool_context.py bfc613da331f13f9fd58b7dd84c7098bec43d6227e856bedf935f5be680a1303;
run_internal/tool_execution.py
86b91c62df0779e896143e5bc841a962d436099d79365497377dd9a233b02946.
The end hook runs with final_result after the SDK creates/commits its output
item (same module2145-2175), before returning that function result to the runner.

OpenAI stream currently awaits Runner.run, extracts result and emits name-only
tool_end afterward. Existing retry loop admits only "No tool output found", twice;
keep retry/tracing/selected-auth behavior. Hook queue belongs to a single running
attempt; end emission must reach the consumer before a later error/cancel. Close
and await the same runner on cancellation/aclose; disable hook publication before
waiting on an abandoned worker. Preserve completed tool refs already emitted.
Do not duplicate hook-observed calls when extracting raw_responses afterward.
Explicitly account for provider call-ID reuse across retry attempts so distinct
executions cannot overwrite citations.

Anthropic stream checks result with check_output_value before ctx.compress_tool_result;
derive citations between those operations. ToolUseBlock.id is already available.
ChatGPT OAuth has call['call_id'] and whole reduced result before summary slicing.
Claude maps ToolUseBlock.id -> name in a per-request dict; _tool_end_event receives
tool_use_id and actual ToolResultBlock.content (MCP content may be text blocks).
Its success content is admitted by check_output_value with token-derived guard
before conversion to preview text. Retain that order. Do not parse repr strings.

output_events.py is a closed vocabulary: tool_end currently allows only tool,
summary,chars,is_error,call_id. Add only the planned optional input,sec_citations,
sec_citation_gaps; validate using the citation module's closed types. Run the
existing output-event security owners; never weaken exact-secret guard or allow
arbitrary metadata. Typed malformed SEC reference must not become missing evidence.

ResearchRunStore._terminalize_error_on_connection currently passes tool_calls=None
when restart/no-task cancellation calls it. Recovery should derive complete durable
events inside the same transaction rather than use the public 500-event page API.
The public paginated event route remains bounded; do not change it to dump all rows.
