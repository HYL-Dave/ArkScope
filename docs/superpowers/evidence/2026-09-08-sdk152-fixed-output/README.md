# SDK Readmission and OpenAI Fixed-Output Repair

Base: `d97ff291` on the isolated `codex/sdk152-openai-fixed-output` branch.
The parent contains the still-unmerged automation controls and GPT-6 change.
No migration, production setting/token write, App restart, merge, or push.
SEC work in this packet is an assessment only, not a feature change.

## Scope and evidence strength

The earlier mutation-harness incident observed three Luna 400 errors for
Chat Completions function tools with reasoning effort. That was not a controlled
request-selection test; its unmeasured totals and failed artifact remain in
the immutable parent packet. This repair does not rewrite that history.

The two affected API-key product call sites are `_synthesize_openai` and
`_translate_openai` in `src/card_synthesis.py`. They now use the existing
Responses helper for reviewed GPT-5.6 Luna/Terra/Sol and the official `gpt-5.6`
alias, retaining GPT-6 Astra's Responses path. Effort, selected model/credential,
output schema, task timeout, and output-size limits are preserved. There is
no retry after rejection and no model, credential, effort, or transport fallback.

`uses_responses_for_tools` is deliberately a reviewed ArkScope transport choice,
not a claim that every Chat Completions combination is prohibited by OpenAI.
The Luna failing combination was observed; Sol/Terra were not live-tested for
that failure. Official model pages document Responses support for all three.
Using their supported interface avoids another model-specific exception without
asserting unmeasured provider behavior.

Other Chat Completions callers are the simple model-access probe (no tools) and
the investment-profile JSON-mode calibration (no tools). They do not contain
this triggering combination and are unchanged, not newly live-certified.
AI Research and lifecycle investigation already use Responses. ChatGPT OAuth
is intercepted before construction of the API-key client; Spark retains its
separate exact-ID subscription adapter. No defaults or task eligibility change.

Response model matching now accepts a reviewed official alias resolving to its
canonical model, or an allowed canonical dated snapshot. An explicitly pinned
snapshot cannot change, and a sibling/unknown suffix cannot pass as a receipt.

Sources checked September 8:

- https://developers.openai.com/api/docs/models/gpt-5.6-luna
- https://developers.openai.com/api/docs/models/gpt-5.6-terra
- https://developers.openai.com/api/docs/models/gpt-5.6-sol
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/docs/guides/latest-model

## Measured live verification

| Channel | Measured invocation | Result |
| --- | --- | --- |
| OpenAI API key | One HTTP POST to official `/v1/responses`, selected profile credential, Luna `low` | HTTP 200; exact `gpt-5.6-luna`; valid translation; 141 input / 21 output tokens; 2.746 seconds |
| Claude OAuth | Two SDK `query()` sessions, at most two turns each | Both passed; three observed model turns total; exact Sonnet 5; literal `apiKeySource="none"`; 1,737 input / 219 output tokens |
| ChatGPT OAuth | No new invocation | Existing parent receipt is not presented as proof of the changed API-key path |
| Anthropic API key | No invocation | Unchanged path, not newly live-tested |

OpenAI's transport counts dispatch before sending, permits exactly one selected
request, and disables SDK and HTTP retries. Its create-only artifact prevents
accidental replay to the same receipt. The harness has five offline owners,
including 400/429/500 and a deliberately attempted second dispatch.

Claude session/model-turn counts are not HTTP request counts: internal CLI HTTP
retry behavior is not observed. The gate records zero ArkScope session retries
and no configured or observed model fallback. The positive MCP tool executes
exactly once; the negative session exposes no tools/servers. Correctly placed
synthetic project/config traps produce no tool startup, write, or instruction
observation. These fixtures are not App dependencies and are not an OS sandbox.
The SDK version, binary hash, literal auth source, inventories, and observed
models are retained in `live-sdk152.json`, not raw messages or credentials.
`live-source-files.sha256` binds the unchanged execution source and SDK pin
used for these runs. The live host is Linux; no Windows/macOS canary is claimed.

`claude-sdk-offline-admission.md` is the implementer's pre-live checkpoint;
its pending items are closed by the subsequent live receipt and this summary.
The installed SDK/CLI pair passed four-way identity checks. The official SDK
release comparison changes version metadata and the bundled CLI, not Python
transport/types. No new upstream tool or permission surface is enabled.

## Offline verification

All backend tests and mutations execute with no external network interfaces and
no inherited credentials through the existing namespace wrapper. The wrapper's
loopback-only / `ENETUNREACH` witness appears in retained logs.

- Original Astra baseline: 49 passed.
- New 5.6 RED: 71 failed / 8 passed before repair; expected old request path and
  absent alias-aware receipt behavior. GREEN with Astra: 128 passed.
- Combined OpenAI/task focus: 322 passed (`focused-openai.txt`).
- Live API harness: five passed (`harness.txt`).
- SDK/auth pre-live focus: 101 passed (`sdk-gate-prelive.txt`); implementer's
  broader auth focus: 144 passed, recorded in its report.
- Return 5.6 to old transport: 71 failed / 251 passed across the 322-node focus.
- Remove model receipt rejection: 11 failed / 311 passed across that same focus.

The old two-node Luna Chat Completions preservation test is deliberately
replaced by custom-model legacy-transport controls. The new 5.6 matrix owns the
changed contract; no legacy current-model transport assumption is hidden in a
green test.

Final canonical backend: **7,331 passed / 12 skipped / three existing edgar
deprecation warnings**, 770.04 seconds, using the newly admitted installed SDK.
Collection is 7,343 nodes: parent 7,255 plus 79 compatibility cases, five live
API harness cases and four SDK model-receipt cases. The runtime version test
has an explicitly versioned replacement name, not a dropped owner. Restored
combined focus is **430 passed** (`focused-restored.txt`).

Independent review reports no findings, 543 broader focused tests passed, and
its own complete 7,331 passed / 12 skipped run. See `review.md` for scope and
remaining validation limitations. No frontend source changed in this follow-up;
the parent packet retains its 1,700-test frontend/build/browser verification.

An initial incorrect invocation
of pytest at repository root collected archived diagnostic scripts and stopped
with five collection errors. `backend-full.txt` preserves that invocation;
the canonical `pytest tests` run is `backend-tests.txt`. No test exclusion,
archived artifact change, or provider access was used to correct the command.

Publication scanning first flagged two parameter IDs in `collection.txt`.
Both are exact preexisting literals in `test_redact_scrubs_token_shapes`, not
credentials obtained by these tests. The seal permits only those two digests
at that exact node/file and verifies their presence in the source fixture;
every other credential-shaped match still fails. Generated logs are retained
byte-for-byte, including the initial incorrect pytest invocation.

## Hand-test scope after integration

1. Select OpenAI API key and Luna with an explicit effort. Generate an AI card,
   then run Content Translation; neither should hit the former 400 combination.
2. Select Claude OAuth and Sonnet 5. Test one chosen function to confirm the App
   uses the newly admitted installed runtime. Fable 5.1 OAuth remains a separate
   policy decision, not enabled by this SDK bump.
3. The parent automation controls/GPT-6 changes remain part of the pending
   integration. Their prior hand-test checklist still applies; no need to test
   every model/auth/task combination as live calls.

See `SEC-surface-audit.md` for the proposed retirement of the obsolete SEC event
schedule and reuse of the existing financials core. No new financial-report
collector or filing library is claimed implemented here.
