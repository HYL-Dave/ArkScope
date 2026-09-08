# Claude Analysis JSON Amendment

## Measured Reason

R1 and D1 failed because native StructuredOutput arguments used literal generic
tool-template fields. Adding the exact schema to the analysis system prompt let
R2 produce valid native output, but ArkScope incorrectly rejected its final
completion turn. The corrected counting guard preserves native tool budgets.
The renewed R3 full run then reproduced the template failure despite the schema
prompt. The prompt amendment alone is therefore not a reliable remedy.

[SDK structured outputs](https://code.claude.com/docs/en/agent-sdk/structured-outputs)
are validated after generation and may be re-prompted inside the CLI. The
[firsthand upstream issue](https://github.com/anthropics/claude-code/issues/87234)
reports the same placeholder symptom; it is not vendor confirmation of a cause.
Do not patch the bundled binary, enable hidden feature flags, add unrelated
tools merely to change model behavior, or keep retrying until one run passes.

## Narrow Transport Change

Only Claude OAuth lifecycle **analysis** uses final-message JSON instead of the
native StructuredOutput tool. Search retains its existing native structured
output and bounded WebSearch tool. The shared ModelReply/finding schema, other
auth adapters, source selection, exact-quote checks and human-adoption guards
do not change.

The analysis request declares this output mode before dispatch. It is not a
fallback after a rejected native output. Disable native output_format and every
tool for this phase. The existing fresh directory, reviewed binary, selected
subscription/model, helper pins, stop/reap logic and no-API-fallback policy stay.

The owned, successful ResultMessage.result is the only JSON input. The SDK
[Python result contract](https://code.claude.com/docs/en/agent-sdk/python#resultmessage)
defines it as final assistant text. Reject absent/non-string results, native
structured output on this explicitly different mode, tool activity, trailing
prose, Markdown fences, repeated JSON keys, NaN/Infinity, extra objects and any
schema mismatch. No extraction, wrapper unwrapping, coercion or repair. A failed
or interrupted terminal never becomes accepted output. The same downstream
finding validator still determines whether the conclusion is actionable.

## Verification And Remaining Authority

RED-first tests cover valid JSON, malformed/ambiguous JSON, phase isolation,
empty tool surface, foreign session, incomplete terminal, source identity,
remote terminal ownership and one submission only. Run real wire parsing and
the entire focus against named reverse mutations, then the full backend.
Changing the declared transport is a deliberate contract update; do not remove
old safety owners merely because their synthetic messages need a new shape.

The original public-source HTTP budget is exhausted: R1 used four, R3 four
including one redirect. Necessary additional Sonnet 5 submissions are authorized,
but subsequent diagnostics must replay immutable public captures with zero
source retrieval. Two separate single-submission analysis checks may use R3 and
R1's different sealed source sets. This checks both prior failure inputs, not a
retry-until-success loop. A replay is not a fresh end-to-end retrieval canary. Record
each real SDK submission, literal auth source, model, native terminal, accepted
output, validation gaps and cleanup. No production installation, adoption,
credential mutation, restart, commit, merge or push is authorized here.
