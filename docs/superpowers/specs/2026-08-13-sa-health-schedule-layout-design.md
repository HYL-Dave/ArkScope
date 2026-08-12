# SA Health Truth and Schedule Table Layout Design

> **Status:** BASE DESIGN USER-APPROVED; FAILURE-DIAGNOSTICS AMENDMENT REVIEW REQUIRED; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-13
>
> **Grounding base:** `bea5890f`; diagnostics amendment grounded at `bdd8fc30`
>
> **Scope:** correct the Settings SA Extension health semantics, preserve
> bounded failure evidence for later diagnosis, and make the existing
> per-source schedule table readable. This unit does not change SA capture or
> repair algorithms, provider cadence, retry policy, or scheduler execution.

## 1. Problem

Two user-visible defects were observed in Settings on 2026-08-12:

1. The SA Extension panel said `鏈路有中斷` while setup, browser registration,
   launcher, native-host ping, sidecar binding, and database readback were all
   healthy. The red row was the latest completed capture outcome, not evidence
   that the browser/native-host chain was broken.
2. Long source descriptions in the schedule table inherited the global
   `.data-table td { white-space: nowrap; }` rule and visually ran into the
   schedule controls in adjacent columns.
3. A completed Alpha Picks run exposed only `detail_save_failed`. The stored
   row did not say whether the failure happened in browser navigation, access
   validation, extraction, native-host transport, or SQLite persistence. That
   makes a real failure visible but not diagnosable.

The supplied screenshots are the visual authority for these symptoms:

| Screenshot | Size | SHA-256 |
|---|---:|---|
| `Screenshot from 2026-08-12 23-33-43.png` | 1111 x 407 | `97854f75eb481d49334e2ce82cc3b2b6a20304510d18d70d2f313d065f9dd4d0` |
| `Screenshot from 2026-08-12 23-34-28.png` | 1121 x 372 | `f2d567b4e56e7461c25b51bb20b377adaf3cdb065395db5dda87d4411aff07d6` |

## 2. Grounded facts

### 2.1 The red SA row was operational history, not a broken chain

`src/service/sa_extension_health.py::_telemetry_last_segment()` selects the
latest **completed** structured extension attempt. It has no running-row
signal. The response then computes its top-level `ok` value by requiring every
segment, including historical capture and repair rows, to be non-failing.

At the screenshot time:

- the latest completed Alpha Picks run had a degraded result: three phases
  completed and one phase failed with `detail_save_failed`;
- a Market News run was active, but it had not yet produced the completed row
  consumed by this endpoint;
- `sa_capture.db` was receiving Market News rows at the same time; and
- the green `market_news_repair` row referred to an older 2026-08-02 repair. It
  was not a claim that the current Alpha Picks failure had been repaired.

The current API therefore collapses two independent facts:

- **chain health:** can the extension, browser registration, launcher,
  native host, sidecar binding, and local capture store communicate; and
- **capture outcome:** what happened in the latest completed Alpha Picks or
  Market News operation.

The UI also omits the capture job name and occurrence time even though a safe
timestamp is already present in the backend segment.

### 2.2 The schedule collision is deterministic CSS behavior

`styles.css` applies `white-space: nowrap` to every `.data-table` cell. The
schedule table uses `table-layout: fixed`, gives its source column 22 percent,
and does not opt the source cell into the existing wrapping class. The source
description therefore paints past the cell instead of wrapping within it.

This is not a translation-length problem. Shortening one Chinese sentence
would leave the same defect for English, future provider names, or narrower
windows.

### 2.3 The 2026-08-12 failure occurred before local persistence

Production read-only evidence for `job_runs.id=20308` records a degraded
`sa_alpha_picks_refresh` attempt from `2026-08-12T15:04:05Z` through
`2026-08-12T15:06:46Z`. Its failed phase is `article_details`, with the generic
reason `detail_save_failed`; `payload` contains only the extension event
identity and `error` is null.

The native-host log provides a narrower, non-speculative boundary:

- metadata save completed with 60 articles and requested comments for three;
- exactly one `save_comments_only` request then reached the native host;
- that request committed successfully for article `6323722`; and
- no native-host save request exists for the other two targets before the
  terminal extension telemetry row was recorded.

The two missing operations therefore did not fail in the SQLite transaction.
They stopped somewhere in the browser-owned path: navigation/load, access or
login readiness, script injection, scrolling/parsing, or an extension
exception. Existing code increments `failed` at each of those branches but
does not retain the branch or target. `buildAlphaPicksProtocolResult()` then
collapses the count to `detail_save_failed`, and `protocolProjection()` drops
all non-canonical fields before persistence.

The extension/native save contract itself is valid: a successful local save
returns `ok=true` through the backend and native-host envelope, and the
extension checks that field. This design must not replace that working
contract based on the generic stored reason.

## 3. Alternatives

### A. Change only the copy

Rename `鏈路有中斷` to a softer phrase and shorten source descriptions.

Rejected. The response would still model a capture failure as a broken chain,
and nowrap content could overlap again as soon as copy changes.

### B. Split chain truth from operation truth and bound the source column

Make chain state an explicit backend projection over structural segments only.
Keep the latest operation as a separate, named and timestamped row. Give the
source cell its own wrapping contract and rebalance table columns.

Selected. This fixes the ownership errors without changing capture or
scheduler behavior.

### C. Add a full SA run-history and incident-resolution model

Track running attempts, unresolved failures, repair linkage, and recovery
status as a new history surface.

Deferred. That could be useful, but current storage does not provide a reviewed
failure-to-repair relation. Inferring one from timestamps would invent truth.

### D. Persist raw browser/native logs or exception text

Rejected. Raw logs can contain URLs, page text, account identifiers, provider
responses, or implementation details; they are also too large and unstable to
be a product contract. Persist a closed diagnostic projection at the failure
site instead.

## 4. Locked decisions

### LD 1 - Chain state has one explicit owner

Replace the ambiguous top-level `ok` field with:

```text
chain_state: "available" | "degraded" | "interrupted"
```

The backend derives it from these structural segments only:

- `config`
- `manifests`
- `launcher`
- `host_ping`
- `telemetry_binding`
- `capture_readback`

Any structural `fail` yields `interrupted`; otherwise any structural `warn`
yields `degraded`; otherwise the result is `available`. `telemetry_last` and
`market_news_repair` never alter chain state.

All in-repo consumers move atomically to `chain_state`; no legacy parallel
boolean remains.

### LD 2 - Completed capture truth remains visible and typed

The latest completed capture segment uses the recorded `derived_outcome`:

| Outcome | Segment state | Stable code |
|---|---|---|
| `complete` | `ok` | `capture_complete` |
| `skipped` | `warn` | `capture_skipped` |
| `degraded` | `warn` | `capture_degraded` |
| `failed` or invalid terminal result | `fail` | `capture_failed` |

Retryable item counts remain counts; they do not turn a structurally healthy
chain into `interrupted`. A degraded run is not relabeled complete.

The segment adds a closed, allowlisted `job_name` for exactly
`sa_alpha_picks_refresh` and `sa_market_news_refresh`. Arbitrary job names or
backend prose do not enter the DTO.

### LD 3 - The UI states what the row actually represents

The panel header renders one of:

- `鏈路可用`
- `鏈路尚未完整驗證`
- `鏈路有中斷`

The telemetry row names the workload (`Alpha Picks` or `市場新聞`), states the
typed outcome, shows safe counts when present, and displays `occurred_at`.
The repair row also displays its occurrence time and is described as the most
recent historical repair, not as resolution of a newer failure.

No UI path invents a `running` state. A future running indicator requires a
separate authoritative source and design.

Traditional Chinese UI copy uses `擷取`; this unit does not introduce
`攝入`. English copy uses `capture` or `fetch` according to the existing
surface.

### LD 4 - Schedule source text owns wrapping

The source cell receives a dedicated class with:

- `white-space: normal`;
- `overflow-wrap: anywhere`;
- top alignment for multi-line source rows; and
- a stable line height for the label and description.

The table remains horizontally scrollable on narrow screens. Controls,
timestamps, and status badges retain bounded no-wrap behavior.

The fixed column allocation becomes approximately `30 / 11 / 12 / 12 / 35`
percent for source, schedule, interval, run-now, and last-result. Exact values
may move by at most two percentage points during browser verification, but the
source and last-result columns must remain the two widest columns and total
100 percent.

No provider label, description, source ID, cadence, enable flag, or execution
behavior changes in this unit.

### LD 5 - Canonical outcome and diagnostic evidence have separate owners

The existing extension run protocol remains the sole authority for terminal
outcome, phase states, counts, and retryability. Add a sibling
`extension_diagnostics` envelope to the telemetry request; diagnostics may
explain an outcome but can never change it.

The request shape is closed:

```text
extension_diagnostics:
  schema_version: 1
  entries: [diagnostic entry, ...]
  omitted_count: integer >= 0
```

Each admitted diagnostic entry has exactly these fields:

```text
occurred_at: aware UTC ISO-8601 failure-observation timestamp
stage: closed enum
reason_code: closed enum
target_kind: "article_detail" | "article_comments" |
             "market_news_detail" | "phase"
target_ref: optional bounded opaque provider identifier
retryable: boolean
attempt_count: integer in [1, 1000]
message: optional sanitized text, at most 240 characters
```

`occurred_at` must fall within the parent run's `started_at`/`finished_at`
interval. `target_ref`, when present, matches `[A-Za-z0-9._:-]{1,128}`.
`omitted_count` is bounded to `[0, 10000]`; it reports entries dropped only
because the 32-entry cap was reached, never entries rejected for invalid data.

The initial closed `stage` vocabulary is:

- `tab_navigation`
- `page_readiness`
- `script_injection`
- `content_parse`
- `native_transport`
- `local_persistence`
- `reconciliation`
- `extension_runtime`

`reason_code` reuses the existing extension protocol's failure-capable
`REASON_CODES` wherever one already describes the observed fact. Diagnostics
must not create a near-synonym for existing codes such as `login_required`,
`access_restricted`, `navigation_timeout`, `detail_timeout`, `dom_not_ready`,
`parser_empty`, `native_host_unavailable`, or `reconciliation_failed`.

The initial diagnostics-only additions are closed to:

- `tab_closed`
- `browser_api_failed`
- `script_injection_failed`
- `comment_scan_unusable`
- `native_response_invalid`
- `database_busy`
- `database_integrity_failed`
- `database_write_failed`
- `extension_runtime_error`

Unknown values are rejected rather than persisted as free-form categories.
`target_ref` is an opaque article/news identifier, never a URL or title.

Diagnostics validation is isolated from result validation. A malformed or
secret-bearing diagnostics envelope is discarded as a whole, while the valid
terminal outcome is still persisted with a typed
`diagnostics_status="rejected"` and
`diagnostics_error_code="invalid_extension_diagnostics"` marker. A malformed
diagnostic must never make a completed run disappear. Valid new-client events
record `diagnostics_status="recorded"`, including an empty entry list on
success; legacy events without the sibling field record `"absent"`.

### LD 6 - The failing layer classifies the failure before incrementing counts

Every extension branch that increments a failed detail count must first append
one typed diagnostic. Browser code owns browser stages; the native host owns
transport-envelope validation; and the local backend owns SQLite error
classification. A caller must not relabel an unknown browser failure as a
database write failure.

Native save failures return a stable `error_code` plus a bounded sanitized
diagnostic. Raw `str(exception)`, stack traces, SQL text, and filesystem paths
are not telemetry authorities. An unrecognized exception maps to the owning
stage's generic stable code, not to an invented provider cause.

The diagnostic envelope participates in the immutable extension-event hash.
A retry with different admitted evidence is therefore not silently deduplicated
against the earlier event. For a rejected envelope, only the canonical
rejection marker participates in the hash; rejected raw bytes are never
retained or hashed into durable state.

### LD 7 - Durable tracking reuses `job_runs` without creating a parallel log

`JobRunsLocalStore.record_extension_event_once()` persists the validated
envelope, or its rejection/absence marker, under
`job_runs.payload.extension_diagnostics`. The terminal result continues to live
in `job_runs.result`; no second outcome table or raw-log table is introduced.

The health service may read at most the latest 20 completed allowlisted SA
extension rows to derive a bounded recurrence summary by `(job_name, stage,
reason_code)`. It exposes:

- diagnostics from the latest completed run;
- the latest occurrence time for each repeated typed cause; and
- the number of affected runs in that bounded window.

This is an operational history, not failure-to-repair linkage. Rows written by
older extension versions remain valid and render `原因未記錄（舊版資料）` when
the terminal outcome is degraded or failed without diagnostics.

### LD 8 - Normal and developer UI expose different diagnostic depth

The normal SA health row renders the precise stable cause when available, for
example an article page readiness timeout versus a local database write
failure. It does not show raw exception text.

The UI may name a network cause only when the browser supplies a reviewed,
stable signal for it. A generic navigation/load timeout remains a browser page
readiness failure and explicitly says that stored evidence cannot distinguish
network, provider-page, and browser causes. The product must not guess a more
specific root cause from elapsed time or a missing native-host call.

Developer mode may additionally show run ID, stage, reason code, target
reference, occurrence time, retryability, attempt count, sanitized message,
and recurrence count. This evidence joins the existing Settings developer
diagnostics surface; it is not rendered as an always-open raw-log panel.

`重新檢查` remains a local GET-only action. It re-reads stored health and
diagnostics and never retries provider work.

### LD 9 - Diagnostic storage is bounded and secret-safe

One event admits at most 32 entries plus an `omitted_count`; the canonical
diagnostic JSON is capped at 32 KiB. Invalid entries are rejected atomically
rather than partially transformed into plausible evidence.

The envelope must never contain URL/query text, title, body, comments, HTML,
cookie, authorization header, token, email address, full filesystem path, SQL,
or stack trace. Tests use sentinels for each prohibited class and prove they do
not cross the extension request, native-host payload, database row, API DTO, or
rendered developer surface.

## 5. Verification contract

Backend tests must prove:

1. a degraded latest capture plus six healthy structural segments produces
   `chain_state="available"` and a warning `capture_degraded` row;
2. each structural fail independently produces `interrupted`;
3. a structural warning with no fail produces `degraded`;
4. capture and repair failures never alter chain state;
5. only the two allowlisted job names cross the API boundary; and
6. no running state is inferred from absent completion data.
7. valid diagnostic envelopes round-trip into `job_runs.payload` and alter the
   immutable event hash;
8. malformed enums, timestamps, identifiers, oversized envelopes, and secret
   sentinels never persist, while the canonical terminal outcome does persist
   with the typed diagnostics-rejected marker;
9. browser-, transport-, and SQLite-owned failures retain distinct stable
   codes while unknown exceptions remain generic to their owning stage;
10. a latest degraded row with no diagnostic renders the typed legacy-absence
    state rather than an inferred cause; and
11. the 20-run recurrence projection is bounded, deterministic, and read-only.

Frontend tests must prove:

1. all three chain states render distinct copy and tone;
2. a degraded Alpha Picks row includes its workload, occurrence time, and
   counts without claiming the chain is interrupted;
3. an old repair timestamp cannot be mistaken for current recovery;
4. source descriptions have the dedicated wrapping class; and
5. existing schedule controls and source IDs are unchanged.
6. normal mode distinguishes browser readiness, native transport, and local
   persistence failures without raw details;
7. developer mode renders only the admitted diagnostic fields and recurrence
   count; and
8. `重新檢查` performs local GETs only and cannot trigger extension/provider
   work.

Extension tests must prove each existing `failed++` branch emits exactly one
typed entry before terminal protocol construction, successful saves emit none,
and a multi-target attempt reports the correct target without retaining page
content or URL data.

Browser verification uses desktop `1322 x 777` and mobile `390 x 844`:

- no source text crosses a cell boundary;
- no control or status text overlaps;
- horizontal scrolling remains available when required;
- the SA panel fits without incoherent clipping; and
- no provider request is triggered by either health read or layout rendering.

## 6. Out of scope

- changing extension capture or repair algorithms;
- changing retry counts, backoff, page-navigation windows, or provider traffic;
- linking a failure to a later repair without stored relational evidence;
- persisting raw browser/native logs or adding a generic log viewer;
- adding polling or automatic rechecks;
- changing source schedules or provider configuration; and
- redesigning the complete Settings table system.
