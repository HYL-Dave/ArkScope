# Authorized Read Inventory And Claude OAuth Canary

## Authority

On September 7 the user authorized the previously requested production read-only
schema/case/credential-metadata inventory, and explicitly allowed Claude Code
OAuth for this stage's LLM live testing. This is not permission to install a
production schema, change Settings, apply a finding, restart the App, commit,
merge, push, or call another model provider/billing source.

The earlier `2026-09-07-lifecycle-web-runtime` packet remains immutable. This
packet adds observations; it does not rewrite earlier offline results as live
evidence. `read_inventory.py` uses `mode=ro`, `query_only`, a SQL authorizer and
explicit column allowlists. It does not instantiate an application store,
read token storage, read credential secrets or export source refs. Table schemas
are hashed, not copied with private row data. Cross-file snapshots are not
claimed to be atomic. Normal SA capture need not stop.

## Predeclared Live Envelope

One explicit investigation of the public identity TravelCenters of America Inc.
(`TA`), through the unique active Claude Code OAuth credential and
`claude-sonnet-5`, effort `medium`. The production Research route is OpenAI Luna;
this test uses an explicit temporary selection without changing that route.
Fable 5.1 OAuth admission and all other channels are outside this gate.

- At most two ArkScope model submissions: search, then analysis. No retry,
  replacement model/account, API-key fallback or human confirmation.
- At most four admitted WebSearch uses. The reviewed CLI gets six internal
  turns for search and two for analysis. These are not eight measured HTTP
  requests; native provider-internal requests are not independently observable.
- At most four captured pages, eight source HTTP attempts including redirects,
  two redirects per page, 2 MiB per response, 45 seconds total source retrieval,
  and 180 seconds per model phase. The ordinary source reader is unchanged.
- Fresh private CLI cwd/config and a separate temporary SQLite journal. Only
  selected OAuth token loading is allowed; it remains in memory. The exact
  configured SEC contact field may be read for SEC request identification,
  never supplied to the LLM or evidence output. No `.env` sourcing.
- Any failure/incomplete/unknown stops this attempt without resubmission. A
  local process exit or interrupt acknowledgement is not remote completion.

`claude_canary.py --prepare` binds the current metadata and all 1,070 previously
admitted source hashes without reading the token. Execution requires its exact
plan digest and a new private temporary output directory. The observer subclasses
the actual SDK client and forwards every call/message without replacing transport,
changing hook results, or weakening adapter validation. Real init/result witnesses,
query submissions, source reads and journal terminals are recorded separately.

## Oracles Set Before Dispatch

Protocol success requires literal `apiKeySource="none"`, the selected model on
every phase, real Web search, at least one captured page, a complete structured
analysis and durable readback. No unexpected executable/file/MCP tool, different
credential/model, human assessment or adoption is permitted.

Quality is separate: TA means TravelCenters, not an abbreviation match; an
acquisition announcement alone cannot prove completed delisting; BP must not
be offered as a same-security alias. Insufficient/contradictory/unread material
must withhold an action. A completed request that yields no actionable finding
is not claimed as a successful delisting confirmation.

## Initial Inventory

There are 39 persisted cases: 36 SEC and three listing-authority cases. All 36
market observations and all three expected provider observations have cases;
no case lacks an observation. The Web journal is absent. The three existing
provider checks retain `unresolved` observations; that is not a reclassification
or reversal of earlier attended tracking receipts. No lifecycle conclusion is
drawn from these metadata counts.

Two Claude OAuth credential rows exist, one active. Metadata expiry is not a
live login claim. Runtime preflight still observes SDK 0.2.151 and bundled CLI
2.1.258. No other credential's token, API-key value or stored account label is
included in this inventory.

## Results

**The first canary failed.** The executed plan is `live-plan-r2.json`, approval
digest `a864a9cbb3392d270bc3602dd5dea999ca5446fb047b1f5e224ff0ce89833a0d`.
`live-plan.json` is the unused earlier preparation, not a second dispatch.
The actual SDK and journal each record **one** model submission, at
00:33:15-00:33:36 UTC on September 7. The observer records:

- Init `apiKeySource` is literally `none`; init and every exposed assistant
  message identify `claude-sonnet-5`. Tools are only `StructuredOutput` and
  `WebSearch`, with zero MCP servers.
- Two exposed WebSearch tool-use messages, followed by a successful completed
  ResultMessage with structured output and four internal turns. These are not
  independent counts of native provider HTTP requests.
- Result `model_usage` names **both** `claude-sonnet-5` and
  `claude-haiku-4-5-20251001`. The exact-model guard rejects that result with
  `execution_identity_changed`. No replacement account, API key or ArkScope
  retry was attempted. This is not a passed functional or quality canary.
- No source HTTP request, analysis submission, human assessment or adoption.
  The observed local child is reaped. Credentials were loaded once from the
  selected keyring entry, never copied to the journal or evidence.

The old validation order rejects model usage before recording a valid owned
terminal. The actual saved journal therefore remains `remote_outcome_unknown`
with a null search terminal. It is preserved unchanged in `live-result.json`.
The observer did not retain a session-match boolean for the ResultMessage;
aggregate metrics alone cannot prove that nonce matched. Mixed model usage is
independently sufficient to reject this result. The narrower ownership/terminal
defect is reproduced with controlled matching-session fixtures, not inferred
by rewriting the live row.

The read-only inventories before and after agree on all three schemas, lifecycle
counts/correspondence, routes and allowed credential metadata. Their observation
times differ. This is scoped readback, not a full database-byte equality or
cross-file atomicity claim. The Web journal is still absent from production.

## Helper Model Discovery And Correction

Inspection of the exact installed CLI 2.1.258 finds a WebSearch side-query that
can choose the small/fast model independently of the main loop model. Its model
selector checks `ANTHROPIC_SMALL_FAST_MODEL` first, then resolves the Haiku
default through `ANTHROPIC_DEFAULT_HAIKU_MODEL`. This is a helper-selection path,
not evidence of a failed Sonnet request falling back to Haiku. The observed
mixed usage is consistent with that path; the first witness does not separately
attribute every Haiku token to a specific internal operation.

The same inspected WebSearch implementation sets the hosted tool's `max_uses`
to eight **inside** one admitted CLI WebSearch operation. The four-operation
ArkScope gate is not a four-search-HTTP guarantee. No feature flag, binary or
provider configuration is patched.

The purpose-specific adapter now pins both helper-model overrides to the exact
selected model, while retaining exact-model rejection, `fallback_model=None`,
selected subscription auth and tool restrictions. It also records an owned
remote terminal before validating the result's model usage, turns, tools and
output. Rejected results stay failed and never advance to analysis; missing or
foreign terminals stay unknown. Ordinary Research, Spark and API-key paths are
unchanged. Pinning helpers to Sonnet/Opus may consume more quota or time than the
CLI's native Haiku helper. **The corrected behavior is not yet live verified.**

Primary references consulted, not substitutes for the observed binary:

- [Claude model environment configuration](https://code.claude.com/docs/en/model-config#environment-variables)
  documents the background-model override and the deprecated small/fast setting.
- [SDK cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
  distinguishes per-model usage from a single main response; estimated costs do
  not prove subscription billing amounts.

## Correction Verification

`adapter-correction-red.xml` records seven failures and 24 passing controls
before the product change. `adapter-correction-green.xml` records 112 passes
across the adapter, real-SDK wire, controller, shared models, pipeline and finding
tests. Nine backend nodes are added; none are removed by this correction.
`verify_correction.py` independently removes each helper override, reverses
terminal/acceptance ordering, accepts mixed usage, and accepts a foreign result.
Each mutation runs against the complete existing affected focus in a disposable
copy, followed by restored focus, integration and complete backend verification.
The source-bound campaign passes: **1,928 baseline/restored focus tests**, **2,747
integration tests**, and **6,593 complete-backend passes with 12 skips** (three
existing warnings). All five mutants fail their named owners, with respectively
2/2/5/3/2 failed nodes and no collection errors; every mutant runs the same 1,928
nodes. Full backend adds exactly nine nodes to the previous 6,596-node collection,
removing none. Raw results, source hashes and node deltas are sealed alongside
this report.
The older packet's 23 backend/11 frontend mutations are historical evidence,
not claimed as rerun here. No frontend byte changed in this correction.

Harness preparation failures are retained, not disguised as provider failures.
`harness-rehearsal-red.xml` catches a wrong captured-page field; the misleadingly
named `harness-rehearsal-green.xml` still fails on an incomplete synthetic finding.
The actual pre-live final harness result is `harness-final.xml` (13 passed).
`pre-live-focus.xml` collected no tests because of a nonexistent test filename;
`pre-live-focus-r2.xml` is the actual 70-pass pre-live focus. None dispatched an
LLM. The SDK observer does not weaken the product adapter's admission decisions.

## Remaining Gates

There was no retry after the one failed canary. Another explicitly approved
Claude OAuth attempt must bind the corrected source manifest and record
session-match booleans and per-model token counts, without exporting session
IDs or tokens. The original harness/plan retain their original source identity;
they correctly refuse the now-changed source instead of silently admitting it.
At most two new ArkScope submissions (search, then analysis) would be needed,
with the same stop-on-first-failure envelope and no profile action.

No other channel is live verified by this test. Production installation,
complete-population cutover, merge and restart remain separate authorizations.
