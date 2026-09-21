# Selected Financial Data Sources

## Decision And Scope

The September 21 clarification prioritizes working source selection before more
event-aware freshness logic. The user has no paid Finnhub subscription. Do not
infer endpoint entitlement from a key, require a Finnhub upgrade, or make its
calendar a prerequisite for financial reuse. Provider capability, user selection,
subscription evidence, billing permission and data age are separate facts.

ArkScope remains a research workbench with collection capability. Letting a model
choose a source is an explicit request within operator-selected sources, not a
way around configuration or paid admission. Raw provider/MCP exposure and a new
external MCP server are not prerequisites for this bounded repair.

This slice completes Settings -> stored policy -> actual tool dispatch -> result
provenance for three existing paths:

| Dataset | Current implemented providers | Consumers |
| --- | --- | --- |
| `fundamentals_analysis` | SEC EDGAR, Financial Datasets | `get_fundamentals_analysis`, four existing research channels |
| `detailed_financials` | SEC EDGAR | `get_detailed_financials` and its existing callers |
| `earnings_supplements` | Finnhub | Earnings history/upcoming components of `get_detailed_financials` |

Selections are ordered eligible sources, not a command to buy every source.
Automatic reads try eligible local observations before permitted acquisitions.
An explicit provider request never silently switches providers. Comparing two
providers requires separate explicit reads and keeps their stored observations
separate. An empty selected set means disabled, not restore defaults. Defaults
preserve the current paths until the operator makes a choice; FD paid admission
still refuses unconfigured limits. Selection does not certify data correctness.

The narrower detailed-financials implementation cannot silently use FD merely
because fundamental analysis can. SA/Massive financial adapters are not wired;
their subscriptions cannot make an absent adapter usable. News collection,
current quotes, macro jobs and other Finnhub tools retain their own owners and
are not governed by these three rows. Do not label this a provider-wide kill
switch or claim all 56 tools have migrated.

## Implementation Contract

- One policy catalog and strict parser own source eligibility and order. Persist
  each dataset under the existing profile settings table, without new schema or
  YAML writes. Tool reads are read-only, including absent-profile first use.
  Invalid stored policy fails closed; no network or fallback through another
  provider may hide the failure. Updates apply to subsequent tool invocations,
  not an advertised cancellation of in-flight work.
- Settings GET exposes implemented choices, effective ordered selection and
  whether it is default or saved. PUT validates all input before one setting
  write. Loading/saving this surface makes no provider request and returns no key.
- Fundamental analysis gains `source=auto|sec_edgar|financial_datasets` through
  registry, native OpenAI/Anthropic and both existing OAuth channels. Explicit
  source must be selected; return a typed refusal otherwise. Keep existing
  freshness controls and local observations' original acquisition timestamps.
- Disabling SEC detailed financials suppresses its acquisition. Disabling Finnhub
  supplements suppresses that read/acquisition independently; SEC metrics may
  remain available. Route receipts distinguish chosen source from allowed set.
- Settings owns an optional FD policy override: enabled, daily attempt limit,
  rolling-minute limit. Existing YAML remains a default when no saved override
  exists. Turning paid acquisition on requires positive limits and explicit UI
  confirmation; this is not a dollar cap or proof of the provider's plan limits.
  Stored observations do not require paid activation. Server governor remains
  authoritative; source selection cannot bypass it.
- Reuse existing Settings navigation guards, read cache and localized controls.
  Show unsupported adapters as unavailable, not an enabled source switch. Do not
  duplicate credentials or confuse a route selection with subscription purchase.

## Verification

- [x] RED-first source exclusion, explicit routing, invalid policy and stored-only tests (21 initial failures).
- [x] Shared policy, API and live-read runtime wiring (621 related checks pass; two existing live skips).
- [x] Four-channel source argument and provenance checks; existing allowlists unchanged.
- [x] Settings source selection and paid-budget controls, with save/failure/navigation tests (18 focused UI checks).
- [x] Browser checks across desktop/mobile and a narrow desktop container on isolated state; no external requests.
- [ ] Related and standalone full regression, frontend/typecheck/build, main-tree verification.
- [ ] Update the root acquisition contract; commit/merge/owned-branch cleanup, no push.

Pre-freeze checks: frontend 1,886 tests / 125 files; typecheck/build, localized
literal scanner and eight desktop checks pass. The root acquisition contract is
updated. Standalone full backend acceptance and main-tree verification remain.

The first full backend run at `bb688e0f` was intentionally interrupted before a
UI correction, not accepted as a completed regression. Unconfigured or invalid
paid policies can now be explicitly saved as disabled without inventing limits;
the two added UI cases and isolated browser check pass. A new frozen revision
must run the full backend again.

No production-store mutation, provider calls, subscription activation, purchases,
App restart, SA scraping, formula repair or event-aware financial expiry is
authorized as part of offline verification. The root
[Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md) remains
the durable current-behavior contract and must be updated with this delivery.
