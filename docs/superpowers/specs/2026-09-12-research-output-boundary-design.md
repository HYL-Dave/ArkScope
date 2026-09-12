# Shared Research Output Boundary

## Decision And Scope

The user approved the shared-mechanism option on 2026-09-12. This is an
independent security slice based on `18d46062c30da87b30666b1ba0f290872a28fa7f`.
The uncommitted SEC release Task 2 in the other worktree is parked, including
its four OAuth adapter failures, explicitly blocked on this slice. No SEC
feature wiring or exception list belongs in this change.

The earlier analysis lives at
`/tmp/arkscope-listing-sec-macro-convergence/docs/security/hardening/2026-09-12-tool-output-boundary/`.
Its observations collection digest is
`47fd62991101838a0618cb9545c4a9016fd72d99094912d68252afa0d63db682`.
That analysis describes a dirty feature checkpoint, not this clean base.

## Corrected Findings

`probe_harness.redact` is a deliberately lossy diagnostic safety net. Its
length/shape rules damage ordinary English, exact numbers, URLs and identifiers
when used for successful research content. Independent per-delta replacement
also cannot recognize a credential divided between deltas.

The exposure is not necessarily limited to the live display:
`research_run_manager` appends nonterminal text events through
`research_runs.append_event` into `research_run_events.data_json`. Final answer
redaction cannot retroactively protect these records. This is a source-derived
finding, not a claim that production credentials have leaked. No production
conversations or token stores were read for this decision.

## Authority And Boundaries

1. Auth isolation and exact matching against credentials already captured for
   the execution are primary. Guard state stays in memory, has a safe repr and
   refuses serialization. Do not enumerate stored accounts or ambient secrets.
   Include selected API clients and the OAuth bearer actually used after refresh.
   A child may add only credentials it really captured for that execution;
   concurrent unrelated runs cannot share guard state.
2. The existing heuristic scrubber remains unchanged for diagnostics/probes.
   It must not decide whether a successful research number, word or URL is
   allowed. Errors remain bounded and sanitized before truncation.
3. Known raw credentials and a finite, documented set of common encodings are
   protected. This is not a claim to detect arbitrary transformed or unknown
   secrets. Exact matching is not a semantic proof that a value is private:
   if a known secret coincides with public data, secrecy wins explicitly.
4. Successful tool results have a trusted-code-selected result policy. The
   existing registry has input contracts only, so this slice introduces the
   output owner explicitly. A reviewed public JSON policy may allow dynamic
   mappings; this is not an arbitrary field-name exemption. Domain-specific
   validators can tighten it. Unknown tools/policies and invalid results fail
   with bounded typed codes and no raw rejected value.
5. Validate and check secrets before reducing, previewing, wrapping, or
   persisting tool results. A secret or invalid structure rejects the result;
   never replace an identifier/cursor inside an apparently successful result.
   Deny explicit credential-bearing JSON keys recursively, including mapping
   keys themselves in exact-secret scans. No fallback to arbitrary `str(obj)`.
6. Valid public payloads have equal canonical business data in OpenAI API,
   Anthropic API, ChatGPT OAuth and Claude OAuth. SDK wrappers, call IDs and
   channel-specific size budgets need not have identical wire bytes. Lossless
   admission precedes those existing budgets. New SEC validators and pagination
   integration remain owned by the separate feature task.
7. Prose uses the same exact-secret guard without diagnostic entropy rules.
   A stateful stream matcher holds an undecidable suffix, bounded by the longest
   protected representation minus one, and emits only a safe prefix. Matching
   and emission use raw offsets, not replacement-string offsets. Every split
   position, one-character chunks, overlapping secrets and multiple encodings
   have named tests. Pending partial-secret suffixes are withheld on abnormal
   exit. Normal finish must not emit a partial secret prefix as plaintext.
8. Protection precedes public events, durable event append, scratchpad and
   replay capture. It covers text, thinking text, final answers and tool traces.
   No raw secret in error details or rejected-value repr. Stream state is scoped
   to the execution and closes with the underlying iterator on cancellation.
9. Source captures and citations are immutable. Rejected structured quotations
   are not silently edited; a prose redaction is a display projection and cannot
   be promoted into an exact source citation. No capture rewriting in this slice.

## Compatibility And Resource Policy

Preserve actual model/provider/auth/effort selection, retries, tool allowlists,
timeouts, compressor budgets, SDK session continuity and subprocess isolation.
No live provider, credential read, dependency install, production DB access,
migration, merge, push or application restart. Tests use synthetic credentials
and disposable databases with a closed environment and offline test hooks.

No new service or dependency. Bound guard representations and JSON depth/nodes
explicitly; reject excessive inputs with typed codes. Existing large financial
and news outputs remain positive controls, not assumed malicious by length.
Guard memory does not retain full streamed answers. Domain tools can retain
their existing bounded answer/capture accumulation separately.

## Acceptance

- Existing probe, runtime key-echo, card authority, retry/tracing and subscription
  environment guards remain green, or any changed expectation names its new owner.
- Public words, exact Decimal strings (including exponent form), 12+ digit
  amounts, hashes, accessions, URLs and cursors survive all four adapters.
- Synthetic secrets in any field/key or across any stream split cannot reach
  model tool output, public events, durable replay, scratchpad or final answers.
- Malformed/credential-bearing structured values yield typed failure, with no
  weakened fallback. Unknown fields do not bypass an explicitly closed validator.
- Inverse mutations demonstrate the decisive checks are owned.
- Fresh focused and complete-backend verification, independent task reviews and
  whole-branch review before claiming completion. The parked SEC failures are
  not relabeled as pre-existing baseline failures or hidden by this result.
