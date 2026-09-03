# Codex Spark Content Translation Design

**Status:** Approved for implementation 2026-09-03 after input-bound,
bundled-runtime, entitlement, and code-execution-convergence rulings

## Goal

Make `gpt-5.3-codex-spark` an explicit, optional execution choice for ArkScope's
existing Content Translation task when an eligible ChatGPT Pro subscription is
active.

Spark is admitted here because low latency and a separate subscription quota are
useful for bounded translation. This is a maintenance and quota-allocation
decision, not a claim that Spark is a general replacement for a frontier model.
Its shorter context, text-only input, and speed-oriented behavior make it a poor
default for broad reasoning, tool orchestration, or long-running research.

The implementation treats Spark as a leaf execution adapter for one fixed task.
It does not introduce multi-agent orchestration.

## Product Decision

The only admitted tuple is:

```text
task       = card_translation
provider   = openai
model      = gpt-5.3-codex-spark
auth_mode  = chatgpt_oauth
plan       = pro
harness    = codex_app_server
```

Every dimension is load-bearing:

- Spark is not admitted for `card_synthesis` or `ai_research`.
- Spark is not admitted through `api_key`, `api_key_pool`, or environment-key
  fallback.
- ChatGPT Plus and unknown/missing plan states are not admitted.
- Spark remains optional and does not replace the built-in Content Translation
  default.
- No other task, model, credential, or harness may be selected as a fallback.

As of 2026-09-02, the user reports that the active local ChatGPT account is
Plus, not Pro. A credential label such as `ChatGPT subscription Pro` is display
text and is not entitlement evidence. Offline implementation may proceed, but
ArkScope must not claim a successful live Spark execution until an account that
passes the Pro and exact-model checks is used.

The `card_translation` identifier remains the durable API/DB key. Product copy
continues to use `Content Translation` / `內容翻譯` under the terminology rule in
`docs/design/ARKSCOPE_TERMINOLOGY.md`.

## Verified External Facts

OpenAI's product announcement describes Spark as a ChatGPT Pro research preview
in Codex, with a 128k context window, text-only input, a speed-oriented design,
and a separate usage limit:

- https://openai.com/index/introducing-gpt-5-3-codex-spark/

The announcement also says API access is limited to selected design partners.
ArkScope therefore does not infer general API-key availability and intentionally
forbids API-key execution even if a future local API catalog happens to expose a
similar identifier. Expanding either plan or API-key access requires a new
product decision and tests.

The provider does not publish a general API maximum-output fact for this Spark
surface. The registry must represent that fact as unknown rather than borrowing
the limit of `gpt-5.3-codex` or inventing one. ArkScope does not turn an unknown
provider fact into a guessed character or token limit. The output schema remains
the semantic result contract; separate process-protocol resource guards are not
model capability claims.

## Admission Model

### Static capability policy

The code-reviewed capability record gains closed execution-policy metadata:

- allowed task routes;
- allowed auth modes;
- required subscription plans, when applicable;
- whether model IDs must match exactly rather than inherit prefix variants;
- an adapter identifier for non-provider-native execution;
- an unknown-safe maximum-output representation.

Existing models retain their current behavior through defaults. Spark uses:

```text
allowed_tasks          = (card_translation,)
allowed_auth_modes     = (chatgpt_oauth,)
required_plans         = (pro,)
exact_model_id         = true
execution_adapter      = codex_app_server
provider_max_output    = unknown
```

`model_execution_admission_detail` and task-route admission become task-aware.
A caller that omits task context cannot execute a task-restricted model. This
keeps code generation, calibration, subagents, generic agents, compression,
card synthesis, and AI Research closed to Spark without maintaining a scattered
denylist.

`ModelCapability.max_output` becomes `int | None`; `None` means the provider
maximum is not established, not zero and not an invitation to use a family
default. The following eager consumers must be updated together:

- `src/agents/openai_agent/agent.py` must omit unknown values from
  `_OPENAI_MODEL_MAX_OUTPUT`, and `_get_openai_max_output` must reject a known
  capability whose value is unknown;
- `src/agents/anthropic_agent/agent.py` must apply the same closed behavior to
  `_MODEL_MAX_OUTPUT` and `_get_model_max_output`, even though Spark itself is
  OpenAI-only;
- `src/agents/shared/subagent.py` and every remaining generic execution seam
  must retain its execution-admission check before any output-limit lookup;
- direct helper tests must prove that a known unknown value never enters token
  arithmetic or provider parameters.

Unknown custom models retain their existing provider fallback. A known Spark
record does not: generic execution is rejected by task admission before an
output limit is requested.

### Credential and entitlement policy

Eligibility requires all of the following:

1. The active OpenAI credential is `chatgpt_oauth`.
2. Its token-store record reports the normalized plan `pro`.
3. A successful discovery scope for that exact credential contains the exact
   model ID `gpt-5.3-codex-spark`.
4. The app-server execution session independently reports plan `pro`, lists the
   exact model, and returns the exact requested model from `thread/start`.

Missing plan metadata, stale/missing discovery, a Plus plan, a different auth
mode, or any model mismatch fails closed before a translation turn starts.

Plan admission reads the token-store record populated by ChatGPT login and then
rechecks the live app-server `account/read.planType` value. It never infers a
plan from the credential alias, account label, model name, or rate-limit label.
The two plan values must normalize to the same reviewed `pro` value before a
turn can start.

The effective-model view carries the non-secret plan classification for the
active OAuth credential. It must not persist access tokens or copy plan state
into the model-discovery tables. The token store remains authoritative for the
current plan; the discovery cache remains authoritative for the last observed
model list.

### Picker behavior

Spark appears as a selectable advanced model only in the Content Translation
picker when the active ChatGPT Pro credential has successfully discovered it.
It is not seeded when discovery has not run, and it does not appear as a
candidate for API-key, Plus, card-synthesis, or AI-Research routes.

If a previously saved invalid Spark route exists, the current-route row remains
visible but disabled with a bounded reason. It is never silently removed,
rewritten, or executed through another route.

The account discovery panel may continue to display provider-observed Spark
capabilities. Its `task_route_tasks` value becomes exactly
`["card_translation"]` only for an eligible Pro record; otherwise it is empty.

## Execution Architecture

### One core, one adapter

Content Translation keeps one input contract and one output JSON Schema. The
shared `translate_text` / `translate_card` validation remains authoritative for
shape, locale, NUL rejection, and complete-output requirements while the legacy
generic 16,000-character checks are removed. The Spark work adds a Codex
app-server adapter behind the existing subscription structured-output
dispatcher. It does not fork translation prompts, DTOs, persistence, or output
validation.

Removing the adapter later must leave Content Translation functional through
the existing Anthropic and OpenAI paths.

The dispatcher selects the adapter only for the exact admitted tuple. Other
OpenAI ChatGPT OAuth models continue to use the current raw Responses backend.

### Reviewed runtime contract

Reusable Codex process admission belongs in a shared app-server runtime module,
not in a second copy of the account-usage launcher. Account usage and Spark
translation share:

- the reviewed version allowlist;
- executable and shebang-interpreter checks;
- a clean, allowlisted child environment;
- bounded JSONL stdout/stderr parsing;
- process-group termination and reap behavior;
- JWT account-ID validation and `chatgptAuthTokens` login.

Every ArkScope Codex operation is bundled-only. Account observation and Spark
execution must both resolve `codex_cli_bin`'s bundled binary, verify that the
resolved target remains inside that installed bundle, and probe the exact
allowlisted version. Missing or broken bundle imports and paths are typed
runtime-unavailable failures. No ArkScope path may discover or execute an
external `codex` from `PATH`. This preserves packageability without requiring a
separately installed Codex CLI and matches the bundled-only admission standard
used by the Claude execution runtime.

The approved code-execution-convergence slice removed the old
`src/tools/code_generator.py` Codex backend and its external-CLI/API fallback.
Spark must not recreate that path. Explicit executable injection may remain as
a test seam in the shared app-server runtime; it is not an operator-facing PATH
override.

Account-usage response parsing remains separate from translation event parsing.
The refactor must preserve all existing account-usage tests and behavior.

A checked-in schema projection owns the exact app-server methods and fields the
translation adapter consumes: `initialize`, `account/login/start`,
`account/read`, `model/list`, `thread/start`, `turn/start`, item notifications,
and turn completion. A future `openai-codex` bump remains fail-closed until that
projection and version allowlist are reviewed.

### Isolated single-turn session

Each translation creates a fresh process and temporary directories:

- fresh `CODEX_HOME`, `HOME`, XDG directories, `TMPDIR`, and empty working
  directory, all outside the ArkScope repository;
- no inherited provider keys or application secrets;
- only the reviewed PATH, locale, timezone, proxy, and certificate variables;
- an ephemeral thread;
- empty runtime workspace roots, environments, and dynamic tools;
- `approvalPolicy = never`;
- read-only sandbox with tool-network access disabled;
- `allowProviderModelFallback = false`;
- the exact Spark model and selected effort;
- app-server tool-bearing features disabled at process launch.

The token is sent only through the app-server login request. It is never placed
in the child environment or output. Temporary state is deleted after every
result, error, or timeout.

`thread/start` must echo the exact model, working directory, approval policy,
sandbox policy, empty instruction-source list, and empty workspace roots. Any
mismatch aborts before `turn/start`.

### Turn contract

The existing translation system instruction becomes the thread developer
instruction. The existing translation payload is the sole text input. The
existing translation JSON Schema is passed as `outputSchema`.

Only reasoning/status notifications and exactly one final `agentMessage` for
the requested thread and turn are accepted. The adapter rejects and terminates
the process on any:

- command or shell execution;
- file read/write/change item;
- MCP, app, browser, computer-use, image, dynamic-tool, or subagent item;
- approval, elicitation, auth-refresh, or other server request;
- unknown notification, wrong thread/turn ID, malformed message, output-size
  excess, duplicate final message, missing final message, or non-completed turn.

The final message must be a bare JSON object matching `outputSchema`. It is
parsed and validated with the declared `jsonschema` dependency before being
returned to the existing translation validator. Markdown fences, prose,
additional keys, and malformed JSON are failures.

### Semantic limits and protocol safety

The shared Content Translation contract has no ArkScope-defined character or
token ceiling. It never truncates source text or translated output. In
particular, the existing 16,000-character checks in `translate_text` are not a
provider capability fact and must not constrain the reusable translation core.
An exact provider context rejection is surfaced as a typed, non-retryable
context-limit failure; it is not converted into partial output or retried with a
smaller prompt.

The current lifecycle evidence feature has separate 16,000-character API,
excerpt, translation-cache, and SQLite constraints. Those remain lifecycle
storage/admission rules until that feature is redesigned; they are enforced at
the lifecycle boundary and must never be exposed as a Spark or Content
Translation model limit. Changing those SQLite checks requires its own reviewed
migration and is outside this slice.

The app-server transport still needs bounded-memory protection against a broken
or hostile child process. Request and response JSONL are streamed under a
separately named protocol-resource budget that:

- is large enough not to stand in for a model context or output limit;
- counts encoded protocol bytes rather than characters or tokens;
- terminates and reaps the process on exhaustion;
- reports a typed adapter/protocol failure; and
- never truncates, retries, changes model, or returns a partial translation.

This internal resource guard is not a user-tunable model setting. Settings must
show provider maximum input/output as unknown when it is unknown, rather than
claiming that the guard is a model limit. Account observation retains 64 KiB per
request, 256 KiB aggregate stdout, and 64 KiB stderr. Spark translation uses
2 MiB per request line, 16 MiB aggregate stdout, and 256 KiB stderr; a
600,000-character translation fixture is the positive control. These are
process-protocol budgets, not model limits.

### Deadlines and cleanup

One monotonic deadline covers credential refresh, process startup, login,
entitlement checks, thread creation, turn execution, and cleanup. The adapter
uses the existing fixed-task timeout rather than creating another Settings
value.

Timeout or cancellation terminates and reaps the complete process group. A
timed-out worker must not continue consuming subscription quota after the route
has returned.

## Failure Semantics

Spark has zero retry and zero fallback inside a translation request:

- no alternate effort;
- no alternate model;
- no API key;
- no raw ChatGPT Responses fallback;
- no Anthropic route;
- no second app-server turn.

Credential/plan/visibility failures are non-retryable route or entitlement
failures. Provider rate limits and temporary queueing remain retryable provider
failures. Protocol drift, unexpected tools, malformed output, and model mismatch
are typed adapter failures and never count as successful translation.

An exact provider context rejection gains a closed translation failure code and
localized guidance. Protocol-resource exhaustion remains a distinct adapter
failure because it describes the local harness, not the model. Neither path may
include raw provider text in its public DTO.

The lifecycle translation endpoint continues to expose the existing closed
translation-failure DTO. Harness provenance becomes `codex_app_server` for a
successful Spark translation, while provider and model remain `openai` and
`gpt-5.3-codex-spark`.

No raw provider exception, token, account ID, temporary path, prompt payload, or
internal protocol message is returned to the frontend.

## UI Behavior

- The Content Translation model selector can choose Spark only in the eligible
  ChatGPT Pro/discovered state.
- The provider discovery card offers its existing task-use command only for
  Content Translation.
- The four provider-observed effort choices remain `low`, `medium`, `high`, and
  `xhigh`; the provider-observed default is `medium`.
- Spark is marked as an experimental subscription option, not a built-in
  default or a general recommendation.
- Settings exposes the SDK-observed subscription plan as non-secret account
  state. Plus, missing, and unknown plans show a localized ChatGPT-Pro-required
  reason; display aliases never supply this value.
- Ineligible saved routes show a localized reason and remain editable.
- No visible wording suggests API-key support, image support, AI Research
  support, or automatic multi-agent delegation.

## Persistence and Compatibility

- No database schema migration.
- A selected Spark route uses the existing model-route row and durable task ID.
- Existing routes and historical execution records are unchanged.
- Historical raw model IDs remain displayable even after a future Spark
  retirement.
- Discovery-cache schema is unchanged; only the exact observed model ID is
  stored there.
- Older sidecars that lack the additive capability metadata fail closed for
  Spark rather than synthesizing eligibility.

## RED-First Verification

Implementation starts with failing tests that own these boundaries:

1. Registry tests own the exact model ID, unknown max-output fact, four efforts,
   128k/text-only facts, exact-ID behavior, sole task, sole auth mode, Pro plan,
   and non-default status.
2. Import and helper tests prove no unknown maximum enters either provider's
   eager output map, token arithmetic, or provider parameters.
3. Admission tests prove Spark is rejected for card synthesis, AI Research,
   generic execution without task context, API key, API-key pool, Plus, unknown
   plan, and undiscovered credentials before provider dispatch.
4. Effective-view tests prove only a Pro OAuth discovery places Spark in the
   Content Translation picker; invalid saved routes remain visible and blocked.
5. Discovery tests prove `task_route_tasks` is exactly Content Translation for
   eligible Pro and empty for Plus/unknown plans.
6. Runtime-contract tests bind the reviewed CLI versions to a committed schema
   projection and fail on a missing/changed required method, field, enum, or
   notification shape.
7. Process tests inspect the bundled-only executable, exact launch arguments,
   clean environment, temporary paths, disabled features, no inherited secrets,
   no PATH fallback, and process-group cleanup. Separate owners prove account
   observation and Spark translation use the same bundled authority, and a
   repository tripwire forbids reintroducing an external Codex executable lookup.
8. Protocol tests cover the exact request sequence and reject every command,
   file, tool, MCP, approval, fallback, malformed-message, wrong-ID, duplicate,
   timeout, and non-completed-turn case.
9. Boundary tests prove that source and translated text are never silently
   truncated, that the reusable translator does not reject the former 16,000
   character boundary, that lifecycle-specific storage limits remain at the
   lifecycle boundary, and that protocol-budget exhaustion terminates the child
   without returning partial output. Positive controls must reach each guard.
10. Translation integration tests prove Spark uses the Codex adapter and the
   existing schema/validators, while all other subscription models retain their
   current adapters.
11. Negative call-ledger tests prove failure never builds an API-key client,
   never uses raw Responses, never changes model/effort/credential, and never
   starts a second turn.
12. Frontend tests own task-only visibility, four effort choices, the
    Content-Translation use command, SDK-observed plan display, localized
    blocked reasons, and unchanged defaults.

Every deny-path test includes a positive control showing the harness reached the
guard. Focused backend and frontend suites run before the full backend,
frontend, typecheck, build, and i18n gates.

## Live Validation Boundary

Offline implementation and tests make no provider call. Because the current
local account is reported as Plus, the immediate hand-test expectation is an
honest Pro-required refusal before `turn/start`, not a successful translation.

The first real successful Spark translation requires a separately supplied
eligible Pro credential and is then observed after merge and restart:

1. Sync the ChatGPT Pro model list and confirm the exact Spark model is visible.
2. Confirm Spark appears only under Content Translation with four efforts.
3. Run one bounded model-task test or one short source-text translation.
4. Confirm translated output, latency, provider/model/harness provenance, and
   separate Spark quota movement.
5. Confirm card synthesis and AI Research cannot select Spark.

That observation validates the current account entitlement and live app-server
behavior. It does not widen Spark to API keys, Plus, other tasks, or fallback.

## Non-Goals

- Making Spark a default model.
- Using Spark for card synthesis, AI Research, generic agents, code generation,
  calibration, compression, or tool orchestration.
- Building a general multi-agent scheduler.
- Adding image input.
- Migrating or widening lifecycle evidence/excerpt/translation-cache storage.
- Adding a user-facing character/token limit that pretends to describe a model
  whose provider maximum is unknown.
- Replacing the existing ChatGPT OAuth raw Responses research driver.
- Calling the provider during offline tests.
- Changing Fable 5.1, Claude OAuth, lifecycle automation, provider credentials,
  or `.env` migration policy.
