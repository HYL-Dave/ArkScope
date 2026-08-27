# Current-Generation Explicit Effort Routing Design

**Status:** Approved 2026-08-27; routing-integrity amendment 2026-08-28

## Goal

Make every user-selectable ArkScope task route name a current-generation model
and the actual provider effort sent on the request. Remove `default`, `none`,
and retired models from task-route controls while preserving provider
capability facts, historical provenance, and compatibility reads.

This slice does not add an LLM to security-lifecycle automation. Lifecycle
decisions remain deterministic: SEC supplies cited regulator facts, IBKR supplies
market-infrastructure corroboration, and unresolved or ambiguous cases remain in
monitoring/review.

## Decision Boundary

`default` and `none` are not equivalent:

- `default` is an ArkScope compatibility sentinel. Depending on runtime and auth
  path it may omit the provider parameter or fall through to an app-level value.
  It is therefore not an honest user-facing effort level.
- `none` is a real OpenAI effort value. ArkScope intentionally excludes it from
  task-route selection because current task routes are quality-sensitive
  synthesis, translation, and research workloads.

The provider/model catalog remains factual. It may continue to report that an
OpenAI model supports `none`; the product policy decides that the value is not
selectable for an ArkScope task route.

## Current Task-Route Lineup

Only these six canonical model IDs are selectable for new task routes:

- Anthropic: `claude-fable-5`, `claude-opus-5`, `claude-sonnet-5`;
- OpenAI: `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`.

The built-in task defaults are complete provider/model/effort tuples:

- card synthesis: `anthropic / claude-opus-5 / high`;
- content translation: `anthropic / claude-sonnet-5 / medium`;
- AI Research: `openai / gpt-5.6-luna / xhigh`.

Fresh installations therefore start with executable explicit routes rather than
an empty effort that becomes `default` or a rejected request. Existing stored
routes are not backfilled into these defaults.

The compatibility resolver has one additional requirement: when an implicit AI
Research request names the provider opposite the configured default route, it
uses that provider's current built-in model with the explicit AI Research effort
`xhigh`. It must not return `None` merely because the configured route belongs to
the other provider. A matching stored legacy route remains incomplete; this
cross-provider fallback must not repair or rewrite it silently.

Generic runtime defaults also move to the current generation: Anthropic uses
Sonnet 5 normally and Opus 5 for its advanced tier; OpenAI uses Luna normally
and Sol for its advanced tier. Active internal runtime hard-codes must be
inventoried and either moved to a current model or explicitly classified as a
low-level diagnostic/compatibility surface. Historical fixtures and provider
capability facts remain unchanged unless their owning behavior changes.

All previously known model IDs remain capability/history facts but are retired
from task routing. This includes GPT-5.4 mini, Claude Haiku 4.5, Claude Sonnet
4.6, and every pre-5 Claude Opus model. Provider discovery must not promote a
known retired model back into a selectable group, and the custom-model escape
hatch must not bypass retirement for a known ID.

The earlier ChatGPT OAuth rejection of `gpt-5.6-luna` is a superseded historical
observation, not a current product restriction. No compatibility fallback to
GPT-5.4 mini remains.

Claude Haiku 4.5 is retired from new routes because ArkScope has no
Traditional-Chinese financial-document translation evaluation proving that it
meets citation, structure, identifier, and numeric-preservation requirements.
This is a product admission decision, not a claim that Haiku cannot translate.

## Model Shapes

### Current model

- Every current model exposes the same selectable set:
  `low`, `medium`, `high`, `xhigh`, and `max`.
- Task-route controls present those values in that canonical ascending order,
  independent of the provider-native capability tuple order.
- A route cannot be saved, tested as a task route, or used to start a new AI
  Research run until one selectable value is chosen.
- Changing provider/model retains the current effort only when the destination
  model supports it. Otherwise selection becomes incomplete.

### Known retired model

- Capability lookup and historical display continue to recognize the model.
- An existing route pin remains visible with a `model_retired` reason and
  requires explicit replacement.
- The model is absent from default, verified, and advanced selection groups even
  when provider discovery reports it.
- New route save, task test, and execution reject it before provider access or
  persistence.

### Unknown/custom model

- Offer the provider's explicit union minus `default` and `none`.
- Require one explicit value. The existing bounded task-model test remains the
  execution check for whether the custom model/account accepts it.
- If the ID resolves to a known retired model, retirement wins over the custom
  escape hatch and the route is rejected.

## Existing Data

- No startup DDL, production migration, or automatic row rewrite.
- Existing route rows containing `default`, `none`, or a retired model remain
  readable.
- A retired model projects as an incomplete route even if its stored effort is
  otherwise valid. A current model with `default` or `none` also projects as
  incomplete.
- Historical runs/messages keep their stored effort unchanged and continue to
  display the raw identifier as provenance.
- A historical successful run whose stored effort is `NULL` or blank is exposed
  as incomplete provenance. The read path must not manufacture the string
  `default`, and the frontend must not replace that missing value with Settings.
- No existing route or historical run is rewritten automatically.

## Backend Admission

Add task-route-specific model and effort validators without weakening the
provider capability validators used by low-level diagnostics:

- model route save: reject retired models and ambiguous/non-selectable effort
  with HTTP 400;
- model route import: skip the route instead of normalizing to `default`;
- task-model test: reject an incomplete route before any provider call;
- AI Research run creation: reject an incomplete explicit or resolved route
  before queueing or persistence;
- raw provider model diagnostics may retain provider-native `none`,
  compatibility `default`, and known legacy model IDs because they are not
  task-route settings.

Card synthesis and translation must not retry an effort rejection with provider
`default`. A task either executes with the recorded explicit effort or fails
through the existing bounded error surface. Low-level provider diagnostics may
retain their separate fallback behavior where explicitly documented.

The catalog response exposes a provider-neutral task-route policy containing the
canonical current and retired model IDs. This policy is separate from discovery
visibility and from provider capability facts. It lets the frontend reject a
known retired ID entered through the custom-model field without treating a
genuinely unknown future ID as retired.

## Frontend Contract

- Settings and AI Research share one selectable-effort helper.
- Effort option labels remain raw provider identifiers.
- No translated speed/cost/quality explanation appears beneath the effort
  selector.
- Incomplete and retired routes show one localized action message and cannot
  save, test, or submit.
- Settings validates completeness before checking whether a draft is unchanged.
  An unchanged legacy `default`, `none`, blank, or retired route therefore still
  blocks Save and its task Test until explicitly replaced.
- Settings save, task-test, route hydration, provider change, model change, and
  custom-model entry preserve a real selected effort or produce an empty required
  selection. None of those paths may coerce an absent value to `default`.
- The model picker presents only the six current models plus a genuinely unknown
  custom ID; a known retired ID never re-enters through discovery or custom
  entry.
- Existing global AI Research selection persistence remains unchanged once a
  complete provider/model/effort tuple is chosen.

## Provenance And Existing Decisions

The Opus 5 registry entry records Anthropic's official
`/about-claude/models/whats-new-opus-5` documentation URL and the date that
ArkScope verified the facts. `verified_at` means documentation verification
time; it is not a live entitlement or execution claim. The distinct Anthropic
effort reference owns the five-value effort ladder.

The user's current live-path ruling, reiterated on 2026-08-28, supersedes the
July ChatGPT OAuth Luna rejection record. Official OpenAI model documentation
independently establishes the Luna model ID and its supported effort values, but
does not serve as evidence for this account's subscription entitlement.
Because `docs/design/PROJECT_PRIORITY_MAP.md` currently contains user-owned
uncommitted work, this slice must not overwrite it. A later authorized
reconciliation can add a dated superseding entry without replacing that work;
until then this approved spec is the newer decision authority.

## Lifecycle Automation

No lifecycle model route or model call is introduced in this slice.

- Deterministic `verified_automatic` outcomes may proceed only through their
  existing SEC, IBKR, date, position, and transition-preview gates.
- Missing/ambiguous IBKR corroboration remains
  `waiting_market_confirmation` or `review_suggested`; the scheduler keeps
  rechecking instead of inventing a conclusion.
- M&A ambiguity remains review work even when an IBKR contract exists.

## Hard Stops

- No provider call.
- No production database read, write, backup, restore, or migration.
- No app restart.
- No merge or push.
