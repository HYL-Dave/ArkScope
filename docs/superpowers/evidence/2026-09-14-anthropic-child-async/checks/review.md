# Anthropic Child Async Review

## Findings

### P2 / Important: Cancellation can abort response cleanup before stream entry

**Location:** [src/agents/shared/subagent.py:671](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:671), especially the unconditional cancellation for `response is None` at [line 681](/tmp/arkscope-research-output-boundary/src/agents/shared/subagent.py:681).

`response` is assigned only after `stream_ctx.__aenter__()` returns. That does not mean no response exists before then: the installed SDK handles error responses and retries inside that await. In particular, a streamed HTTP 429/5xx response can already be awaiting `response.aclose()` while this helper still has `response = None`.

If the parent is cancelled during that close, `reading.cancel()` interrupts the response finalizer. The owned task then becomes done, so joining it does not finish the aborted cleanup. Stream entry never succeeded, so the context manager's exit does not close it either. `_run_anthropic_subagent` proceeds to client shutdown and can release the invocation scopes without completing the response finalizer. This is the same response-before-client ownership violation addressed for successful streams, but on an uncovered acquisition path. It does not require repeated cancellation; the first cancellation is sufficient.

**Source evidence:**

- [anthropic/lib/streaming/_messages.py:322](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/lib/streaming/_messages.py:322): the manager awaits the entire API request before exposing the stream/response.
- [anthropic/_base_client.py:1878](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:1878): retryable error responses are closed before retry backoff, still inside stream entry. [Line 1891](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/anthropic/_base_client.py:1891) also reads terminal error bodies there.
- [httpx2/_models.py:1058](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/httpx2/_models.py:1058): `is_closed` becomes true before awaiting the body finalizer; an interrupted close cannot be resumed by simply calling `aclose()` again.
- [httpx2/_client.py:2205](/home/hyl/.virtualenvs/llm_app/lib/python3.10/site-packages/httpx2/_client.py:2205): client close shuts down transports/proxies, not the interrupted response coroutine. Transport teardown may recover underlying connections, but that is not completion of the response finalizer.

**Required follow-up:** Account for response cleanup during stream acquisition as well as after entry. Preserve cancellable pending-header I/O and the existing retry policy, while ensuring cancellation remains latched so joining an error response's close cannot start a retry. Add actual-SDK controls with a held error-response finalizer, first and repeated cancellation, response-before-client ordering, retained references/scopes, and no subsequent request. Also cover cancellation while reading a terminal error body before entry.

**Why current evidence misses it:** [tests/test_sec_research_delegated_trace.py:116](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:116) returns HTTP 200, and [line 126](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:126) disables retries. The held-close matrix therefore only sees responses already assigned to the helper. [tests/test_anthropic_child_async.py:81](/tmp/arkscope-research-output-boundary/tests/test_anthropic_child_async.py:81) holds a request before any response is returned, so it does not exercise this intermediate state either.

Confidence: high for the control-flow/cleanup violation from source inspection. No reproduction was executed, as instructed; no socket leak, citation loss, or late request is claimed to have been observed.

## Other Review Results

- The child now awaits actual SDK aggregation for standard and beta streams. Model, effort, thinking, token limits, tool selection, output checks, and citation publication remain in their existing owners.
- Captured API-key auth reaches `RuntimeAuthBinding.api_client(asynchronous=True)` without selecting a replacement credential. Same-provider inheritance, explicit cross-provider capture, output-guard inheritance, and unsupported OAuth fail-closed behavior remain intact. The new read and close tasks inherit those contexts and are explicitly joined.
- Once stream entry succeeds, the `is_closed` branch avoids interrupting normal HTTPX cleanup, repeated cancellation is shield-joined, and client cleanup remains inside the child auth/output scopes. No separate defect was found in observer fencing or completed-reference retention on these inspected paths.
- Both route inventories now include schedule-status; the lifecycle set remains exact, and the lifespan inventory checks the schedule endpoint's method, path, module, and handler.
- The overlapping-invocation test checks separate retained citations and call IDs. Its fixture captures one binding for both runs ([tests/test_sec_research_delegated_trace.py:55](/tmp/arkscope-research-output-boundary/tests/test_sec_research_delegated_trace.py:55)); it does not discriminate concurrent different keys/output secrets, or cancellation of one child while another succeeds. These are additional coverage limits, not independently established defects.

## Evidence And Limits

- Worktree: `/tmp/arkscope-research-output-boundary`; branch: `codex/sec-research-integration`.
- Immutable range: `bf7831b870cd051bd4969abceb647f8b8d195885..e447d3947f31242bf8f5e1ddab558cc208014571`. The supplied short revision and HEAD resolved to the same full commit. The tracked worktree was clean during review.
- Read the complete range's production/test changes, the requirements README, pertinent callers/auth/output owners, and installed Anthropic/HTTPX source. `git diff --check` on the immutable range reported no whitespace errors.
- Read the command receipts and output logs for `route-red`, `child-red`, `cancellation-red`, `close-entry-red`, and `close-entry-green`. They report respectively: 2 route failures; 2 heartbeat failures plus 2 passes; 4 response-join failures; 4 close-entry failures; and 295 focused passes. These are supplied historical results, not reviewer-executed verification.
- No tests, runners, probes, product imports, network calls, production DB/config/credential reads, installs, other agents, source edits, or git writes were performed. Only this review file was written. Complete backend acceptance remains for the controller.
- Native Anthropic ROOT synchronous I/O, new OAuth delegation, and broader SEC/deployment work remain outside this review.

## Verdict

**Request changes / not ready to accept this range.** The async N1 direction and successful-stream ownership are supported by the inspected code and receipts, but error-response cleanup before stream entry still violates the cancellation ownership requirement. Resolve the P2 finding and its missing regression controls before acceptance; the controller's single complete suite remains a separate required gate.
