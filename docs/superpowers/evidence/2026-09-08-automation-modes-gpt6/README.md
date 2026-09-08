# Automation Modes And GPT-6 Astra

Base: `168a94cd2d93ac8a7dd4f12b6ee5e34e21b24fcd`.
Runtime/test commit: `c1bcc571`.
Branch: `codex/automation-modes-gpt6`.
Worktree: `/tmp/arkscope-tracking-history-provenance`.
Scope approved September 8: simplify the existing controls, remove duplicate
model counts, add GPT-6 without changing selected task defaults, and perform
representative verification instead of testing every model on every channel.

## Product Contract

- Lifecycle automation has Off, Check Only, and Automatic modes. Automatic
  includes existing eligible verified-delisting mutations. It does not add
  automatic rename approval or let an LLM bypass human approval.
- The internal batch bound remains; its selector leaves Settings. The existing
  interval remains adjustable, including persisted non-preset values.
- The boolean API and database schema do not change. Reading settings does not
  normalize or enable them. Selecting a mode saves both booleans atomically.
- Legacy `enabled=false/apply_profile_transitions=true` appears as Off with a
  diagnostic. It cannot authorize unattended mutation. Clicking the already
  selected Off explicitly clears the residual apply flag; interval edits do not.
- Attended approved transitions retain their independently authorized path.
- Provider model chips and the discovery list remain; their duplicate counters
  are removed. Source, observation time, errors and filtering remain visible.
- `gpt-6-astra` is added for the existing four tasks, with low/medium/high/xhigh/max
  efforts. Existing models, current user selections and Luna defaults remain.

## GPT-6 Compatibility

Official facts reviewed on September 8:

- [Model reference](https://developers.openai.com/api/docs/models/gpt-6-astra):
  exact model ID, supported efforts, 1,050,000 context and 128,000 maximum output.
- [Migration guide](https://developers.openai.com/api/docs/guides/latest-model):
  tools require Responses, with no none/minimal effort or sampling parameters.
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling):
  explicit `strict=false` preserves the existing schema's optional fields instead
  of allowing Responses to normalize them into required fields.

Only Astra API-key synthesis/translation switch to Responses. Research already
uses Responses. Existing Chat Completions models and subscription adapters retain
their transport. The new path requests exactly one named output function, disables
parallel calls, uses `store=false`, and retains zero retries/fallback. Existing
fixed-task output budgets remain 8,192 for synthesis and 4,096 for translation;
these are request budgets, not Astra capability limits. Max-effort adequacy is
not claimed from a low-effort live check.

Completed status, returned model, exactly one expected function call and the
requested JSON schema are checked. An unpinned canonical model can return a valid
ISO-dated snapshot of itself; an explicitly requested snapshot must match exactly.
An arbitrary suffix, another model or a different explicit snapshot is rejected.

Review also exposed a preexisting card-translation issue: merging an empty or
partial response into the original card could appear successful. The returned
fields are now validated before merging on both providers. Schema rejection is
typed `translation_output_invalid`, not a retryable generic provider error. No
invalid result is cached. This is the additional shared-behavior change beyond
the three requested UI/catalog changes.

## Representative Live Verification

The planned live canaries dispatched exactly two measured requests; no model-list,
refresh, retry or fallback within those canaries. Both used an explicitly selected
existing profile credential. Only a synthetic sentence was sent. No
profile/token/settings write occurred. **This is not the total network activity
of the turn: an initial mutation-harness failure caused unplanned API activity,
described below.**

| Channel | Requested and observed model | Calls | HTTP | Input/output tokens | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| API key | `gpt-6-astra` | 1 | 200 | 148 / 21 | 3.852 |
| ChatGPT OAuth | `gpt-5.6-luna` | 1 | 200 | 66 / 37 | 3.655 |
| Claude OAuth | Not dispatched | 0 | N/A | N/A | N/A |

Receipts: [API key](live-api-key.json), [ChatGPT OAuth](live-chatgpt-oauth.json).
They retain a closed token-count projection; provider message/request identifiers
and usage-attribution detail are deliberately excluded. The original reports
remain local in `/tmp/arkscope-gpt6-api-canary.json` and
`/tmp/arkscope-gpt6-chatgpt-luna-canary.json`. The measured observed IDs match
exactly, not merely by alias. [Harness](live_canary.py) enforces a one-request
host/path/model budget per invocation and rejects token refresh or writes.

Original receipt SHA-256 values, before the closed archival projection:

```text
42227bbeff6bce675f67e833b39823100cdf42aa5c155dd45e7d0192ebc4cc99  API key
fd1b5ea70d7e1ff551a4a1a9635770827df3a461f0970fd47bb5f61c58d52987  ChatGPT OAuth
```

These calls preceded the final model-receipt/schema hardening. The request shape
did not change afterward; the added rejection paths were verified offline, not
by spending more live requests. This is not live evidence for Astra OAuth,
every task, long inputs, high-effort completion, or translation quality in general.

### Mutation Harness Incident

The first whole-focus translation-shape mutation copied the function's module
globals. This prevented the normal test dependency patches from reaching the
mutated function. The run has three distinct OpenAI `400` failures from unintended
Luna Chat Completions calls; other unexpected paths failed locally for missing
Anthropic authentication. These were synthetic test cards, not production data.
The run did not count HTTP dispatches, so **three is a lower bound on unplanned
OpenAI requests, not a measured total**. The prior claim that the turn contained
only two requests is withdrawn. Extra request usage/billing was not measured.

The failing artifact is retained as
`test-output/mutation-shape-initial-harness.txt`. It is not acceptance evidence.
The harness now uses the real module globals so dependency patches still work.
All final acceptance and mutation runs are additionally inside a new Linux
network namespace with only loopback, an observed `ENETUNREACH` external probe,
and an environment allowlist excluding inherited credentials. This prevents a
mock regression from producing another external request, including from children
or native HTTP implementations. [Offline wrapper](offline_check.py) documents
that boundary; it is not a new product execution sandbox.

The three errors also identify an unresolved compatibility signal in the
unchanged Luna API-key fixed-task path: Chat Completions rejected function tools
combined with reasoning effort. The controlled Luna OAuth canary uses Responses,
so it does not resolve that signal. The [official Luna reference](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
lists endpoints and features separately, not a guarantee of every parameter
combination. The incident did not record exact credential/request selection;
`LUNA-API-FIXED-OUTPUT-COMPATIBILITY` therefore needs a source-bound check before
claiming that route works live. This branch does not silently change its effort,
transport, model or billing source in response to an uninstrumented failure.

## SDK Environment Boundary

The user's current interpreter has Claude Agent SDK `0.2.152`, with bundled CLI
`2.1.259`. Project requirements and the admitted pair remain `0.2.151` / `2.1.258`.
The preexisting version guard correctly rejects the new pair. Initial focused
testing exposed 12 SDK-related failures in this environment. This is version
drift, not evidence that the new binary broke its isolation guarantees.

No pin/allowlist was changed and the shared interpreter was not downgraded. An
isolated, no-dependencies installation of the reviewed SDK was placed under
`/tmp/arkscope-gpt6-reviewed-sdk`. Offline backend runs use:

```sh
PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk /home/hyl/.virtualenvs/llm_app/bin/pytest -q tests --tb=short
```

Those results describe the declared reviewed stack, not live admission of the
user's newer SDK. Claude OAuth live verification was held at zero calls.
`CLAUDE-SDK-0.2.152-READMISSION` is a separate pending work item. No unsupported
PATH binary, auth fallback or unchecked allowlist bump was used to get a pass.
[Version observation](sdk-version-observation.json) records distribution, module,
metadata and the actual bundled binary's credential-free `--version` probe.

## Offline Verification

Final loopback-only full backend: **7,243 passed / 12 skipped / 3 warnings** in
787.44 seconds, exit 0. [Full output](test-output/backend-final-isolated.txt)
starts with the namespace and failed-external-route witness. The three warnings
are existing dependency deprecations. The completed pre-classification checkpoint
was 7,240 passed / 12 skipped; the final three route-level classification owners
are additional tests. The equivalent pre-isolation full run was also green but
is not used to claim absence of egress.

```sh
PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py pytest -q tests --tb=short
```

Collection accounting against the unchanged base checkout: 7,192 -> 7,255 nodes
(+63 net). Exactly two old node names are intentionally replaced:
`test_lifecycle_analysis_and_profile_mutation_are_independent_controls` and
`test_valid_disabled_background_does_not_disable_explicit_mutation_authority`.
Their former disabled-background automatic authority contradicts the approved
Off mode. Replacements own all four legacy flag pairs and both automated/attended
authority, including a real due-transition scheduler consumer. No other existing
backend node is removed; 65 node names are added. This is an explicit contract
change, not lost test coverage.

- Frontend: 124 files / 1,700 tests passed; build, typecheck and literal scanner pass.
- Typed-output focused regression: 164 passed after six observed RED failures.
- Browser: real React components under intercepted fixtures, en/zh-Hant at
  1280x960 and 390x844; five synthetic writes per scenario, zero unexpected
  network, page errors or horizontal overflow. Checks cover all three modes,
  checked-Off normalization, Astra/max save/readback and absent counters.
- The browser fixture contains synthetic coverage warnings. These screenshots
  make no claim about current IBKR data or the user's running App.

[Source hashes](source-files.sha256) cover all 20 changed runtime/test files and
are verified unchanged after the final tests. Requirements, dependency admission
constants and all database schema files remain unchanged from the base.
Captured test output is retained byte-for-byte, including pytest's trailing
spaces and terminal blank lines. Source/document whitespace checks exclude only
`test-output/`; those raw artifacts are checked by their hashes instead.

The first full frontend run caught a dynamic-translation-key scanner failure;
explicit key lookups fixed it without a scanner exemption. Earlier GPT-6 tests
also exposed stale catalog-count expectations, which were updated without
changing runtime defaults. The corrected review RED run had eleven rejection
failures; a separate bare-date model receipt control then failed before its fix.

[Automation RED/GREEN details](automation-tests.md) include the old flag matrix,
real scheduler-consumer positive/negative controls, and native label-click tests.
[Browser harness](browser_check.py) imports only prior fixture declarations, not
their workflow, and never connects to the production sidecar.

## Review And Mutation Evidence

Read-only review found model-receipt overmatching, the preexisting empty/partial
merge, and lost typed output classification. All three are resolved; final narrow
review reported no actionable findings. It did not run provider calls or tests.
That runtime review preceded the mutation-harness incident and is not a sign-off
on the unadmitted SDK or the newly observed Luna API compatibility signal.

Five process-local mutations are exercised against the full relevant backend
focus, with baseline/restored runs. They never edit production source files:

1. Remove the completed-response gate.
2. Remove the model receipt comparison.
3. Remove card-translation validation before merging.
4. Restore disabled-background mutation authority.
5. Break typed invalid-output classification.

[Mutation runner](mutation_check.py) requires pytest's TESTS_FAILED exit code for
a mutation and OK for baseline; crash, collection error or accidental success is
not accepted. Final loopback-only, credential-free full-focus results:

| Stage | Failed | Passed | Expected exit observed |
| --- | ---: | ---: | --- |
| Initial baseline | 0 | 1,044 | Yes |
| Completed-response gate removed | 2 | 1,042 | Yes |
| Model receipt gate removed | 7 | 1,037 | Yes |
| Pre-merge translation validation removed | 6 | 1,038 | Yes |
| Disabled-background mutation authority restored | 4 | 1,040 | Yes |
| Typed invalid-output classification broken | 7 | 1,037 | Yes |
| Restored baseline | 0 | 1,044 | Yes |

The full run, including named failing owners and a namespace witness before each
stage, is [archived](test-output/mutation-campaign-isolated.txt). The existing
pytest warning concerns assertion rewriting after importing `anyio`; it is not
a collection/setup failure. Earlier pre-isolation runs are explicitly labeled
and are not the final mutation acceptance results.

Reproduce a single stage without providers:

```sh
PYTHONPATH=/tmp/arkscope-gpt6-reviewed-sdk /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py mutation model_receipt
```

## Integration And Hand Test

No migration, production write, App restart, merge or push is part of this branch.
The isolated Vite fixture server was stopped after screenshots. The user App has
not consumed these changes yet.

After authorized integration and restart, check mode persistence, interval
preservation, duplicate-count removal and Astra's five efforts/save/readback.
Do not mistake a missing current credential entitlement for global unavailability.
Claude OAuth additionally needs the separately declared SDK admission resolution;
Luna API-key fixed tasks need the compatibility check above. General readiness of
all existing provider paths is not claimed, even if offline regression is green.
