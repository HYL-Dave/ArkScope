# Spec Compliance

**Verdict: Issues found.** The captured OpenAI key is not authoritative over SDK ambient authentication headers (`src/auth_drivers/runtime_binding.py:52`). The explicit no-secret-diagnostics requirement also remains unmet at the model-test error boundary (`src/model_credentials.py:1291`) and native Research error sinks.

**Cannot verify from this diff:** End-to-end route-read failure propagation in the other task consumers and the complete unchanged Spark entitlement/admission implementation remain controller checks. This task retains the four task IDs and calls the existing Research admission gates; it does not modify the model catalog or introduce Fable OAuth admission. Tasks 2-4 and controller-owned uncommitted documents were not reviewed.

# Strengths

- `src/agents/config.py:487`: Store failure becomes a bounded `ModelRouteUnavailable`; genuine row absence remains distinct from failure.
- `src/api/routes/research.py:389`, `src/research_run_manager.py:119`, `src/auth_drivers/runtime_binding.py:66`: Capture precedes persistence, queued execution validates binding identity, and activation covers stream iteration with context restoration. API-key repr suppression and detached OAuth ID metadata are appropriately separated from execution records.
- `src/agents/openai_agent/agent.py:350`, `src/agents/shared/subagent.py:559`: Main and child Agents SDK models receive explicit clients; deliberate cross-provider delegation has a separate capture boundary.
- `src/model_credentials.py:1273`, `src/api/routes/config_routes.py:1092`, `src/agents/anthropic_agent/agent.py:366`: The Anthropic access probe disables SDK retries and no longer substitutes default effort; invalid explicit test effort is rejected, and admitted custom Research effort reaches the messages parameters.

# Issues

## Critical

None identified within this task's scope.

## Important

1. **P1: Bind or reject ambient authorization overrides before SDK construction.** `src/auth_drivers/runtime_binding.py:52` passes only `api_key` to the SDK after capture. The installed OpenAI SDK subsequently reads `OPENAI_CUSTOM_HEADERS`; an `Authorization` entry overrides the generated header, even while `client.api_key` still equals the captured key. A header introduced between capture and dispatch can therefore send the request under another credential while Research records the original credential ID. Pin the effective authorization header, or fail closed on an incompatible ambient override, and cover this at the actual request boundary. SDK evidence: `openai/_client.py:312`, `openai/_client.py:637`, and `openai/_base_client.py:475` in the review virtualenv. The async constructor has the same ambient-header behavior at `openai/_client.py:1060`.

2. **P1: Sanitize selected-execution failures before any diagnostic or public sink.** `src/model_credentials.py:1291` still returns `str(exc)` directly in the model-test result, whose schema has no redaction validator (`src/model_credentials.py:113`). A provider error that echoes the selected key therefore exposes it through the Settings response. Native Research has the same unmet requirement: `src/agents/anthropic_agent/agent.py:612` logs the raw exception, and `src/agents/openai_agent/agent.py:855` passes it to the scratchpad; both emit raw exception text as error-event data (`src/agents/anthropic_agent/agent.py:626`, `src/agents/openai_agent/agent.py:862`). `src/api/routes/query.py:571` forwards the legacy stream event without a sanitizing boundary. Server-owned Research's later classifier cannot undo an earlier log or legacy SSE disclosure. Use bounded, sanitized failure data before logging, scratchpad writes, model-test serialization, and legacy SSE emission; add a synthetic key-echo rejection case. These are pre-existing sinks left open by a task that explicitly requires secret-free failures, not a claim that this commit introduced each sink. This finding is static; the single permitted focused execution was used for Finding 1.

## Minor

None separately reported.

# Assessment

**Task quality: Needs fixes.** The main route/auth lifetime repair is well scoped and the supplied tests exercise real stores and SDK transports, but a remaining SDK auth override defeats the binding guarantee and error sinks do not meet the stated secrecy contract.

# Review Checks

- Reviewed the supplied immutable package `8512d3aa..f788ef280c245baf0d8a5f55681564603f75dfb5` once, in three non-overlapping reads. No git commands, subagents, provider calls, production stores/credentials, branch changes, App restart, merge, or push.
- The package has bounded context and cuts off functions. Focused completions/checks were limited to named risks: shared dispatch admission/auth selection (`src/api/routes/query.py:201`); detached OAuth metadata compatibility (`src/auth_drivers/factory.py:158`, `src/auth_drivers/chatgpt_oauth_driver.py:305`, `src/auth_drivers/claude_code_sdk_driver.py:477`); SDK ambient auth precedence (Finding 1); raw-error propagation (`src/research_errors.py:46`, `src/agents/shared/scratchpad.py:180`, and Finding 2).
- Checked the changed global-client contract's existing compaction consumer (`src/agents/openai_agent/agent.py:92`, installed `agents/memory/openai_responses_compaction_session.py:92`). Its argument-less construction already fails against this SDK and is caught; this is not a newly reachable auth regression, so no task finding. Checked the OpenAI child tool's direct dispatch at `src/agents/openai_agent/tools.py:630`; no extra thread boundary was introduced there.
- The implementer reports 789 passing tests with no warnings. Those suites were not rerun. Exactly one new focused SDK-header check was executed below: one expected contract failure, confirming Finding 1.
- The only authored file is this report. The focused check is embedded as a doctest so it does not require creating or modifying any test/source file. It supplies a synthetic in-memory credential row, patches the SDK transport, and never constructs a production credential store.

## Focused SDK Header Check

Expected contract: one mock request, the selected key retained in the client, the selected key on the wire, and no alternate key on the wire. Only booleans and a request count are emitted.

```pycon
>>> import sys
>>> sys.dont_write_bytecode = True
>>> import os
>>> from types import SimpleNamespace
>>> from unittest.mock import patch
>>> import httpx2
>>> from openai import OpenAI as SDKOpenAI
>>> from src.auth_drivers.runtime_binding import capture_runtime_auth
>>> selected_key = "synthetic-selected-review-key"
>>> alternate_key = "synthetic-alternate-review-key"
>>> row = SimpleNamespace(provider="openai", auth_type="api_key", id=1, active=True, secret=selected_key)
>>> binding = capture_runtime_auth("openai", store=SimpleNamespace(list=lambda provider: [row]))
>>> requests = []
>>> def reply(request):
...     requests.append(request)
...     return httpx2.Response(200, json={"id": "resp_review", "object": "response", "created_at": 1, "model": "gpt-5.6-luna", "status": "completed", "output": []})
>>> def sdk_client(**kwargs):
...     return SDKOpenAI(**kwargs, max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
>>> with patch.dict(os.environ, {"OPENAI_CUSTOM_HEADERS": f"Authorization: Bearer {alternate_key}"}, clear=True), patch("openai.OpenAI", side_effect=sdk_client):
...     with binding.api_client() as client:
...         selected_in_client = client.api_key == selected_key
...         response = client.responses.create(model="gpt-5.6-luna", input="OK", max_output_tokens=16)
>>> (len(requests), selected_in_client, requests[0].headers.get("authorization") == f"Bearer {selected_key}", requests[0].headers.get("authorization") == f"Bearer {alternate_key}")
(1, True, True, False)

```

Command (worktree cwd, no reported suite rerun):

```bash
env -u PYTHONPATH /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q --noconftest --assert=plain -p no:cacheprovider --doctest-glob=task-1-review.md .superpowers/sdd/2026-09-09-task-route-authority-repair/task-1-review.md --tb=short
```

Result: **1 failed in 0.95s**, exit 1, no warnings. Expected `(1, True, True, False)`; observed `(1, True, False, True)`. The mock transport received exactly one request authenticated with the alternate ambient key, despite the SDK client retaining the captured key. The wrapper reported `interfaces: [lo]`, `external_probe: ENETUNREACH`, and `inherited_credentials: false`. The doctest expectation is intentionally left as the required contract; no second execution or implementation mutation was performed.
