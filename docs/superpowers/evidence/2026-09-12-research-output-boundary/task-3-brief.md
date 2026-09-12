## Task 3: Execution Lifetimes, Prose, Events And Durable Traces

**Files:** Modify `src/auth_drivers/runtime_binding.py`, both OAuth drivers,
`src/agents/openai_agent/agent.py`, `src/agents/anthropic_agent/agent.py`;
create `src/agents/shared/output_events.py`, `tests/test_research_output_events.py`,
`tests/test_research_output_lifetimes.py`. Modify managed/legacy route boundaries
and shared scratchpad/capture consumers only where necessary to protect actual
pre-persistence sinks. Enumerate additional exact paths in the ledger before editing.

The source inventory additionally owns `src/agents/shared/subagent.py`,
`src/research_run_manager.py`, `src/api/routes/query.py` and, only if required,
`src/auth_drivers/live_resolver.py`. Guard complete producer values before
scratchpad/replay/preview truncation. Activate the retained OutputGuard around
each upstream iterator advance/close and reset before public yields; do not
leave a ContextVar token installed in the consumer across generator yields.
Tool arguments must be admitted before handler execution, including write
tools, not repaired after they may have persisted a secret.

**Consumes:** Task 1 scope/matcher and Task 2 result admission. Produces common
event protection prior to emission, with selected-client and refreshed-bearer
registration before any response is consumed. Helpers never recapture credentials.

- [ ] Add real-adapter synthetic text/thinking/final-answer split tests and disposable managed-run replay tests; final-only redaction must fail the durable-event assertion.
- [ ] Test parent/child, refresh, cancellation, completion and exception lifetime, direct API-key entry without ambient runtime binding, plus SDK trace/scratchpad guards.
- [ ] Run RED; expected failures are damaged public prose, reconstructed fake secrets or unsafe durable event data, not provider/network/setup failures.
- [ ] Wire common output scopes across async iteration and tool callbacks. Register captured client secrets/OAuth bearers, sanitize before public/durable yields, redact full values before preview truncation. Always close upstream on cancellation; no retry/session changes.
- [ ] Verify existing owners including `test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors`, runtime binding, card execution authority, retry/tracing, OAuth cancellation/environment and session continuity.
- [ ] Inverse: replace matcher by per-fragment replace; skip active client capture; move protection after durable append. Each has a named RED owner; restore GREEN.
- [ ] Commit and independent task review.

