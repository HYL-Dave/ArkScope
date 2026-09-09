# Research Cache Hints: Findings, Not An Implemented Feature

Observed 2026-09-09 using public official documentation and local source only.
The user requested a warning for model changes or long conversation gaps.
The bounded presentation still needs approval; this note does not authorize
cache settings, provider calls, cache warming, pricing estimates or the deferred
global usage ledger. The separately approved cold-restoration repair continues.

## Official Contracts

- OpenAI's current GPT-5.6+ API cache uses a default/minimum 30-minute lifetime
  after write/reuse. Earlier-model retention varies: in-memory is usually
  5-10 idle minutes, up to an hour; extended retention can reach 24 hours.
  Model and organization policy matter. Matching prefixes and routing remain
  necessary, so time alone cannot guarantee a hit. Responses reports reads
  and writes under `input_tokens_details`.
  [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
- Claude API defaults to five minutes, with an explicitly selected one-hour
  option at a higher write price. Lifetime starts at request start, not response
  completion. Hits refresh it. Cache markers cover the prefix ending at the
  marked block; changing thinking/effort can invalidate that prefix.
  [Claude prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).
- Claude Agent SDK documents a separate subscription policy: main turns within
  included plan usage request one hour; usage-credit billing drops them to five
  minutes. Auxiliary requests have a separate policy. Its USD figures are
  client-side estimates, not authoritative bills.
  [Claude SDK cost and usage](https://code.claude.com/docs/en/agent-sdk/cost-tracking).
- Claude Code also documents model-specific effort behavior and cache prefixes
  influenced by the working environment. A documented TTL is not a measured
  per-call cache state.
  [Claude Code caching](https://code.claude.com/docs/en/prompt-caching).
- The API guides do not establish ChatGPT subscription cache retention or the
  conversion from tokens to either account's subscription quota. Cache misses
  change processing/cost, not the logical context-window size.

## Current ArkScope Boundaries

- `src/agents/anthropic_agent/agent.py::_prepare_cached_system` and
  `_prepare_cached_tools` mark system/tools with `ephemeral` and no explicit TTL.
  The Research request does not mark the complete conversation as cached.
  `src/agents/shared/subagent.py` reuses these helpers. Do not advertise a
  conversation-wide guarantee from these markers.
- `src/agents/openai_agent/agent.py` and the OpenAI child agent's `ModelSettings`
  do not explicitly select a retention policy. An omitted parameter is not
  evidence of a known organization policy or a guaranteed cache expiry time.
- Static consumer mismatch: `TokenTracker.record_openai_result` reads
  `usage.prompt_tokens_details`; the installed Agents SDK `Usage` and its
  Responses conversion use `input_tokens_details`, including `cached_tokens`
  and `cache_write_tokens`. Existing tracker cache tests use the former mock
  shape. A real-SDK-object RED owner is needed before repairing this reader.
  This is not a measured production charge or a completed fix.
- Research's evidence drawer already renders persisted usage counters when
  supplied. Tracker/driver summaries sometimes omit zero or absent counters;
  absence must not be presented as a measured zero or a guaranteed miss.
  Reuse this display instead of creating a second usage authority.
- Claude Research supplies a custom system prompt and a fresh neutral directory
  per SDK invocation. The official description of directory-dependent prefixes
  is a reason to verify this adapter's actual cache reuse before claiming that
  one-hour retention makes consecutive ArkScope turns cheap. It is not proof
  that every invocation misses. Do not weaken isolation to improve caching.
- The prior `RESEARCH-SDK-USAGE-SCOPE` follow-up in Priority Map P2.9 separately
  records Claude SDK per-model counter scope. Neither that issue nor the
  OpenAI reader mismatch is repaired by the route-authority branch.

## Proposed Small Surface

Use a nonblocking hint beside Research submission for a changed execution
selection or a resumed conversation with a meaningful elapsed interval. State
that previous cache reuse may be unavailable; do not promise a hit, a definite
miss, a token amount or a dollar charge. Preserve the intended conversation and
the user's selection; never switch models, discard context, or warm a cache.

Only show a time-policy interpretation when the exact model/channel and actual
request policy support it. Otherwise show the observed interval and unknown
cache state, not an invented expiry countdown. UI completion timestamps alone
cannot establish the last provider cache write/read during a multi-call run.
Account/channel changes and prefix/effort changes also matter; same model plus
a short gap is not sufficient evidence of a hit. Switching back to a model
does not prove that model's earlier cache was erased.

After a response, show actual provider-reported cache reads/writes only after
the reader contract above is covered. Preserve missing/unknown and legacy
records. API pricing and subscription usage must remain distinct.

No runtime or cache-control change has been made for this proposal.
