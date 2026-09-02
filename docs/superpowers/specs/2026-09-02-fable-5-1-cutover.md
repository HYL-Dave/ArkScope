# Claude Fable 5.1 Cutover Specification

> **Status:** User-approved on 2026-09-02. API-key live canary is authorized;
> Claude OAuth live verification is explicitly deferred because the current
> subscription does not expose Claude Fable 5.1.

## Product Decision

- `claude-fable-5-1` is the sole current Fable model in ArkScope.
- `claude-fable-5` is product-retired immediately. Existing records retain the
  exact historical model and effort, but every new execution and continuation
  must fail closed with `model_retired` until the route is corrected.
- This cutover reduces choice and maintenance cost. It is not a claim that
  Fable 5.1 wins every capability comparison, and the current model may change
  again as provider releases evolve.
- Existing built-in task defaults remain unchanged: Opus 5 for card synthesis,
  Sonnet 5 for Content translation, and Luna for AI Research.

## Authentication Boundary

- The Anthropic API-key path is eligible for Fable 5.1 and will receive a
  bounded live canary after all offline gates pass.
- The current Claude OAuth subscription does not expose Fable 5.1. ArkScope
  must label this exact model/authentication pair as not live-verified and
  reject it before a provider call. This is not a permanent provider-wide
  incompatibility claim.
- A future subscription upgrade does not require an architectural rewrite. A
  successful OAuth canary can remove the model/authentication admission block.
- No OAuth live call is authorized in this slice and no OAuth support may be
  claimed from seed-only discovery.

## Fable 5.1 Request Compatibility

- For Anthropic API-key card synthesis and Content translation only, Fable 5.1
  uses `tool_choice={"type":"auto"}` and a single tool definition with
  top-level `strict: true`.
- The prompt requires exactly one named tool call. A text-only response or a
  response without that tool remains an explicit failure; it is never accepted
  as structured output and never falls back to another model or effort.
- Other Anthropic models retain their existing forced named-tool request shape.
- Claude OAuth structured-output adapters are not changed by this request-shape
  migration because Fable 5.1 is rejected for that auth mode in this slice.

## Compaction Boundary

- ArkScope client-side compaction is not enabled for Fable 5.1 in this slice.
  The combination fails closed before a provider call with guidance to disable
  client-side compaction or choose another model.
- Fable 5.1 without ArkScope client-side compaction remains executable.
- Fable 5's existing client-side compaction capability fact is not rewritten;
  its new executions are independently blocked by product retirement.
- Provider-side Anthropic `context_management` compaction remains a separate
  capability and is not disabled or rewritten here.
- This slice does not delete, rewrite, or selectively strip thinking blocks.

## Product Language And History

- The product term is **Content translation** / **內容翻譯**. The durable task
  identifier remains `card_translation`; invisible search aliases may retain
  the former wording.
- Historical `claude-fable-5` research runs and messages must still round-trip
  and display their exact provider, model, effort, and generated content.
- Retired model IDs remain in the registry for provenance and admission. They
  are not discovery seeds or default picker entries.

## Live Canary

After offline backend, frontend, type, build, and terminology gates pass, run
exactly two direct Anthropic API-key calls with the configured credential named
`TD_MRL`:

1. one minimal card-synthesis request;
2. one minimal Content-translation request.

Both calls use `claude-fable-5-1`, `effort=low`, bounded timeouts, zero SDK
retries, no fallback, and the production structured-output seams. Do not print
or retain the credential, prompt, or response content. Record only the outcome,
latency, schema/tool-call validation, model, effort, and timestamp. Stop after a
credential, authorization, quota, or request-contract failure instead of
trying another credential.

## Out Of Scope

- Upgrading the user's Claude subscription.
- Claiming Claude OAuth support for Fable 5.1.
- Removing or rewriting signed thinking blocks.
- Changing the three built-in task defaults.
- Adding GPT-5.3 Codex Spark to Content translation; that remains a separate
  adapter slice after this cutover.
- Merge or push without separate user authorization.
