# Lifecycle Web Usage Calibration

Offline amendment after the attended-write concurrency checkpoint. This is not
a renewed live canary, a billing audit or completion of production cutover.
No application provider/LLM call, production credential/database read or write,
migration, App restart, commit, merge or push occurs in this amendment.

## Correction

The immutable Sonnet canary's main-loop 4 / 1,036 input/output counters differ
from its `model_usage` aggregate 29,706 / 3,228. [Anthropic's SDK documentation](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
distinguishes main-loop from nested-work totals. Web uses the selected-model
aggregate and records cache creation/read and WebSearch counts separately.
Absent fields are unknown, not zero or the smaller main-loop count. A present
malformed value remains a typed error. JSON-safe integers are a representation
constraint, not a model context/output budget.

Accepted phase counters are bound to exact journal call, remote ID and completed
terminal. Ordinary source/analysis failure retains already accepted reports;
a missing or rejected second report yields a partial subtotal, not zero use.
The existing final JSON receipt carries this data without DDL changes. Both UI
and Research consume a closed projection without remote IDs, SDK objects or
native cost estimates. Old records explicitly lack counter provenance. The
usage section is collapsed and does not change the finding or human approval.

These are reported counters, not subscription charging. A hard process crash or
failed final journal write can lose in-memory phase reports; recovery remains
unknown. This is not a per-token crash-durable ledger. Other transports retain
their counter semantics. The independent ordinary Research SDK camelCase/scope
defect is recorded as RESEARCH-SDK-USAGE-SCOPE in the priority map, not fixed by
this lifecycle amendment.

## Verification

| Surface | Measured Result |
| --- | --- |
| Entire affected backend focus, baseline/restored | 2,195 passed |
| Integration | 3,014 passed |
| Complete backend | 6,860 passed / 12 skipped / 3 existing warnings |
| Entire frontend, baseline/restored | 1,604 passed |
| Product mutations | 16 backend + 8 frontend, named owners fail |
| Unique node changes | +62 backend / +26 frontend, no removals |
| Browser | 54 cases, 108 screenshots; two locales, 1440/390/320 widths |
| New canary harness | 9 offline cases, 3 named-owned mutations |

The SDK wire replay, four-channel temporary controller, failure/reopen/shared
projection tests, malformed persisted JSON, cross-session and duplicate receipt
controls own the correction. Every product mutation runs the entire backend
focus or entire frontend suite, not only its containing test file. The real
TypeScript reader also parses DTOs produced from temporary persisted Python rows.

Two additional disk-backed maximum-source runs use real controllers, a shared
temporary profile, heartbeats, source storage and attended human writers. Each
job stores four 128 MiB decoded sources; both jobs succeed for removal and
same-security rename. Confirmation is 22.534 / 21.033 seconds, four measured
human write transactions are 0.524 / 0.395 / 0.492 / 0.349 seconds, and maximum
child `ru_maxrss` is 1,909,673,984 bytes. The separate supervisor's 4 GiB RSS
guard does not fire. This does not guarantee instant UI, a whole-App 4 GiB cap
or that a model accepts every retained byte. Source/model work here is synthetic.

`seal.py` re-derives counts and unique nodes from XML/JSON, verifies each named
mutation, checks both maximum-source runs and all screenshot pixels/geometry,
reruns typecheck/build/literal-i18n checks, scans secret-shaped data, validates
source hashes and publishes create-only evidence. Four schemas and the ordinary
Research, Spark translation, dispatch and capability files match the previous
checkpoint. Earlier seals are hash-verified and left immutable.

## Retained Failures

The initial unit and journal REDs remain historical. The first journal fixture
needed an explicit remote-ID binding before its corrected RED. The first full
frontend campaign found two exact i18n leaf-count assertions needing the +21
new labels; the first backend campaign was intentionally interrupted, restored
and retained. Both complete final campaigns were repeated after that update.

The canary runner is a new preparation artifact, not an edit to sealed live
evidence. Its first nine-case green run did not exercise populated HTTP
observations. A subsequent owner exposed a wrong observation field name; the
corrected final suite and reverse mutation cover this path. These intermediate
results are not substituted for the final admission.

## Remaining Gates

The user's offer of preauthorization still needs confirmation of the exact
single-TA / Sonnet 5 / Claude Code OAuth envelope in the calibration plan. The
new runner permits at most one search and one analysis SDK submission and reads
only the exact selected credential/token and SEC contact if authorized. It does
not prepare a production-bound plan or dispatch just because its offline tests
pass. No existing canary authorization is reused.

After that: renewed live validation, the remaining channel gates, explicit Web
journal installation and complete-population cutover, then authorized merge,
restart and hand testing. Protocol completion and a useful action-ready finding
remain separate; no canary finding is automatically accepted or applied.
