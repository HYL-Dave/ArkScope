# Fixed AI Task Runtime Limits Design

> **Status: ADOPTED DESIGN, 2026-07-12; implementation plan pending.**
> This design covers fixed, single-result AI tasks. AI Research keeps its
> existing independent runtime authority. The first implementation scope is
> card synthesis and card translation.

## 1. Problem

ArkScope currently has two incompatible timeout models:

- AI Research has app-managed runtime settings in `profile_state.db`, including
  `session_timeout_s` (default 900 seconds).
- Card synthesis and translation use hard-coded subscription deadlines and
  hard-coded browser request deadlines.

Live validation exposed the consequence. The same MU EvidencePacket completed
with Claude Sonnet 5 at `low` effort in 31.6 seconds, while `max` effort exceeded
both 90 seconds and 210 seconds. A tiny task-test completed in about five seconds.
Therefore a short canary cannot determine a suitable production timeout, and one
global constant cannot represent different fixed tasks or future models.

## 2. Scope

V1 manages model-execution limits for:

- `card_synthesis`;
- `card_translation`.

The schema and API are task-keyed so later fixed tasks such as note assistance or
summary generation can join without another storage redesign.

AI Research is explicitly out of scope. It continues to use
`research_runtime_config.session_timeout_s`, max turns, and per-tool timeout.
Task-test canaries and SDK subprocess cleanup are also out of scope for user
configuration: canaries remain short, and cleanup remains a system safety bound.

## 3. Product Decisions

### 3.1 Per-task authority

Each fixed task owns one `model_timeout_s`. V1 defaults are:

| Task | Default |
|---|---:|
| Card synthesis | 900 seconds |
| Card translation | 900 seconds |

Valid values are 60 through 3600 seconds. Zero/unlimited is not accepted for
fixed tasks: a hung provider must eventually return control to the app.

The timeout does not vary automatically by provider, credential, model, or
effort. A user choosing `max` may increase the task limit, but ArkScope never
silently lowers effort, changes model, switches provider, or borrows another
billing path.

### 3.2 Meaning of the limit

`model_timeout_s` bounds the provider/model execution phase. It does not claim to
bound local evidence gathering, request queueing, database persistence, or SDK
cleanup. The UI labels it **模型執行上限** rather than a generic request timeout.

The effective value applies to both API-key and subscription execution:

- subscription structured-output calls receive the effective deadline;
- OpenAI and Anthropic API-key requests receive the equivalent per-request SDK
  timeout;
- unsupported auth modes remain fail-closed.

### 3.3 One server authority, derived client wait

The backend timeout is authoritative. The web client derives its request budget
from the effective task timeout plus 60 seconds for evidence gathering, response
serialization, and bounded SDK cleanup. The UI never asks the user to maintain a
second timeout value.

If runtime settings cannot be loaded, the backend uses the built-in 900-second
default and returns a warning. A new frontend talking to an old sidecar uses the
same 900-second compatibility fallback.

## 4. Storage And Resolution

Add a task-keyed table to `profile_state.db`:

```sql
CREATE TABLE IF NOT EXISTS fixed_task_runtime_config (
    task            TEXT PRIMARY KEY,
    model_timeout_s REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
```

Only recognized fixed tasks may be stored. The resolver returns, per task:

- `task`;
- `model_timeout_s`;
- `source`: `env | db | default`;
- `db_saved`;
- `warning`.

Resolution order is real operator environment override, then DB, then built-in
default. Initial environment keys are:

- `ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S`;
- `ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S`.

Environment values are operator overrides, not imported into the DB. Invalid env
values are ignored with a surfaced warning; an invalid DB write is rejected.

## 5. API Contract

`GET /config/runtime` gains an additive `fixed_task_runtime` object keyed by task.

Add:

- `PUT /config/fixed-task-runtime` with
  `{ "tasks": { "card_synthesis": { "model_timeout_s": 900 }, "card_translation": { "model_timeout_s": 900 } } }`;
- `DELETE /config/fixed-task-runtime` to reset all fixed-task DB overrides.

PUT is atomic: every supplied task/value is validated before any row is written.
Unknown tasks and values outside 60-3600 return HTTP 400. PUT and DELETE pass
through `require_profile_state_write`; GET is read-only.

Model routes remain provider/model/effort only. Runtime limits do not enter
`model_route`, because changing a timeout must not rewrite routing provenance.

## 6. Execution Flow

For card generation:

1. The route resolves `card_synthesis` runtime settings.
2. Evidence gathering runs under its existing contracts.
3. The effective `model_timeout_s` is passed explicitly into synthesis.
4. The selected provider/credential/model/effort executes unchanged.
5. Timeout returns a redacted 502 containing task, provider, model, effort, and
   effective seconds; no partial card is stored.

Translation follows the same flow for `card_translation`. A failed translation
does not populate the translation cache.

Task-test continues to use its short dedicated bound and must not inherit the
production task timeout. It tests connectivity and compatibility, not worst-case
production latency.

## 7. Settings UX

Add a **固定 AI 任務執行限制** panel near the existing Models routing controls.
It contains one numeric field per registered fixed task and shows each field's
effective source.

Initial labels:

- `AI 卡片生成 - 模型執行上限（秒）`;
- `卡片翻譯 - 模型執行上限（秒）`.

The panel explains that higher effort may take materially longer and that the
limit does not change model quality settings. Save writes all edited values
atomically; Reset deletes DB overrides. An env-owned value remains visible as an
override even if a DB value is saved underneath it.

The existing **AI 研究執行限制** panel remains separate and is relabeled only if
needed to make its Research-only scope unmistakable.

## 8. Error And Lifecycle Rules

- Timeout is an explicit failure, never an empty success.
- No provider/model/effort/credential fallback is permitted.
- No partial card, translation, or run trace is persisted on timeout.
- Provider subprocess cleanup remains bounded and exact-PID scoped; users cannot
  weaken it through Settings.
- Leaving the page does not promise server cancellation. Server-owned fixed-task
  runs and cancellation are a separate future slice.

## 9. Verification

The implementation plan must include:

- store tests for defaults, DB persistence, env precedence, invalid values,
  unknown tasks, reset, and atomic multi-task validation;
- route tests for additive runtime shape, profile-state write gates, and 400
  errors;
- synthesis and translation tests proving the resolved timeout reaches all four
  API-key/subscription provider paths;
- regressions proving task-test deadlines and AI Research runtime are unchanged;
- timeout tests proving no partial card/translation persistence;
- frontend tests for rendering, save/reset, source badges, validation, and the
  derived `model_timeout_s + 60s` request budget;
- subprocess cleanup regression and host-level zero-zombie smoke;
- frontend full suite/typecheck/build, no-PG smoke, and canonical full A/B.

## 10. Non-Goals

- automatic timeout prediction from model or effort;
- automatic retry with lower effort;
- unlimited fixed-task execution;
- moving AI Research settings into this table;
- server-owned card job queues, background continuation, or cancellation;
- changing provider, credential, model, effort, or billing selection.
