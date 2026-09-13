# Anthropic Pre-Stream Cleanup Re-Review

## Findings And Verdict

**No new actionable findings in the scoped follow-up. The prior P2 is addressed.**

**Ready to proceed to the controller's single complete backend acceptance run.** This is a scoped code-review clearance, not a claim that the full backend suite has passed or that broader release/deployment work is complete.

Reviewed immutable range: `e447d3947f31242bf8f5e1ddab558cc208014571..24c10280df6d3320fa59afe7188fb064c6cd13dd`.

HEAD resolved to `24c10280df6d3320fa59afe7188fb064c6cd13dd`, commit `Own Anthropic pre-stream error response cleanup`, on `codex/sec-research-integration` in `/tmp/arkscope-research-output-boundary`. Review was limited to this six-file delta, the named P2, and its immediate SDK/cancellation regression surface.

## P2 Disposition

The original defect was cancellation interrupting an error response's cleanup inside SDK stream entry, before the prior helper could obtain `stream.response`.

- [anthropic_response_cleanup.py:41](/tmp/arkscope-research-output-boundary/src/agents/shared/anthropic_response_cleanup.py:41) now retains the HTTP response and wraps its byte-stream finalizer before the SDK performs retry/error processing. The middleware does not consume the body or implement an alternative parser/retry policy.
- [anthropic_response_cleanup.py:17](/tmp/arkscope-research-output-boundary/src/agents/shared/anthropic_response_cleanup.py:17) creates one owned finalizer task, shields and joins it through cancellation, retrieves its outcome, then re-raises cancellation. HTTPX setting `is_closed` before awaiting the finalizer no longer allows that finalizer to be abandoned at this boundary.
- [subagent.py:670](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:670) finalizes observed responses even when stream entry fails or a terminal error body is cancelled. [AnthropicResponseCleanup.close:48](/tmp/arkscope-research-output-boundary/src/agents/shared/anthropic_response_cleanup.py:48) clears the per-turn inventory and joins all response closes before propagating an error.
- [subagent.py:688](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:688) cancels model I/O once and joins it through subsequent cancellation. A cancelled retry-response close finishes cleanup and raises cancellation before the SDK reaches retry backoff or another attempt. Outer client cleanup remains shield-joined inside the child invocation scopes at [line 659](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:659).

These changes directly cover both original failure modes: interrupted 429/500/400 response cleanup and a cancelled 400 body that never entered the stream context manager.

## SDK And Regression Checks

- Installed source reports Anthropic `1.4.0`. [AsyncAnthropic.with_middleware:944](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_client.py:944) calls `copy`; [copy:906](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_client.py:906) reuses the HTTP client, and [line 926](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_client.py:926) carries forward the API key, auth token, base URL, timeout, retry budget, headers, and query options. Closing the middleware client therefore closes the same transport owner rather than a newly selected client's pool.
- [SDK middleware dispatch:1908](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:1908), [raw-response preparation:2524](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:2524), and [response construction:2078](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:2078) confirm that the observer receives the response before body parsing/error handling. [Retry processing:1854](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:1854) remains SDK-owned after the observer returns.
- [HTTPX response close:1058](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/httpx2/_models.py:1058) dispatches to the replaced stream's async finalizer. Standard and beta SDK stream managers both await aggregation and response close; neither is replaced by this patch.
- [subagent.py:556](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:556) creates a response owner per child. No global response inventory, auth selection, citation observer, output policy, model/effort policy, or task owner is introduced or changed. The four unit-client fixture edits only preserve their existing assertions across the middleware-copy call.
- [tests/test_sec_research_delegated_trace.py:250](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:250) expands real-SDK cancellation coverage to 429/500 close and 400 body/close for both parents and successful/failing cleanup. Assertions retain response-before-client ordering, repeated-cancel joins, the research-operation hold, no subsequent model request, cancelled terminal state, and reopenable citations.
- [Retry controls:374](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:374) independently check one 400 attempt and three 429/500 attempts with a two-retry budget for both parents, without cancellation. The dependency floor now matches the inspected `1.4.0` middleware interface; no installation was performed.

## Evidence And Limits

Read the controller's command receipts and output logs, not just its summary:

- `error-entry-red`: 16 failed, 37 deselected. Close cases report client cleanup overtaking response cleanup; 400 body cases time out waiting for response cleanup to start.
- `error-entry-green`: 145 passed, exit code 0.
- `retry-and-authority`: 317 passed, exit code 0.

These are inspected historical results, not reviewer-executed tests. The real SDK is exercised against controlled HTTPX transports; this review makes no live-network or exhaustive lower-level transport-shutdown claim. The error-status cancellation matrix uses the standard stream path; the beta path was checked against installed source, with its existing focused coverage retained. No additional blocking test omission was identified for this P2.

`git diff --check` on the immutable range reported no whitespace errors. The tracked worktree remained clean. No tests, runners, probes, product imports, network calls, production DB/config/credential reads, installs, other agents, source edits, or git writes were performed. Only this `rereview.md` was written.

The earlier `review.md` is unchanged; its SHA-256 before and after inspection was `afc71999fbed5ad32b2a87eaa2566bbc51b112eda491cc8897b208a03f96740d`. Its original verdict remains historical for the prior range; this report updates only the P2 disposition for the new HEAD. Native Anthropic ROOT sync I/O, OAuth delegation expansion, and broader SEC/deployment scope were not reopened.
