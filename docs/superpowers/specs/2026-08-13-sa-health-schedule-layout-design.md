# SA Health Truth and Schedule Table Layout Design

> **Status:** DRAFT; USER REVIEW REQUIRED; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-13
>
> **Grounding base:** `bea5890f`
>
> **Scope:** correct the Settings SA Extension health semantics and make the
> existing per-source schedule table readable. This unit does not change SA
> capture, repair behavior, provider cadence, or scheduler execution.

## 1. Problem

Two user-visible defects were observed in Settings on 2026-08-12:

1. The SA Extension panel said `鏈路有中斷` while setup, browser registration,
   launcher, native-host ping, sidecar binding, and database readback were all
   healthy. The red row was the latest completed capture outcome, not evidence
   that the browser/native-host chain was broken.
2. Long source descriptions in the schedule table inherited the global
   `.data-table td { white-space: nowrap; }` rule and visually ran into the
   schedule controls in adjacent columns.

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

## 5. Verification contract

Backend tests must prove:

1. a degraded latest capture plus six healthy structural segments produces
   `chain_state="available"` and a warning `capture_degraded` row;
2. each structural fail independently produces `interrupted`;
3. a structural warning with no fail produces `degraded`;
4. capture and repair failures never alter chain state;
5. only the two allowlisted job names cross the API boundary; and
6. no running state is inferred from absent completion data.

Frontend tests must prove:

1. all three chain states render distinct copy and tone;
2. a degraded Alpha Picks row includes its workload, occurrence time, and
   counts without claiming the chain is interrupted;
3. an old repair timestamp cannot be mistaken for current recovery;
4. source descriptions have the dedicated wrapping class; and
5. existing schedule controls and source IDs are unchanged.

Browser verification uses desktop `1322 x 777` and mobile `390 x 844`:

- no source text crosses a cell boundary;
- no control or status text overlaps;
- horizontal scrolling remains available when required;
- the SA panel fits without incoherent clipping; and
- no provider request is triggered by either health read or layout rendering.

## 6. Out of scope

- changing extension capture or repair algorithms;
- linking a failure to a later repair without stored relational evidence;
- adding polling or automatic rechecks;
- changing source schedules or provider configuration; and
- redesigning the complete Settings table system.
