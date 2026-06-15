# Local Storage Topology

> **Doc type:** Decision record / deferred architecture note
> **Status:** DRAFT — principle is agreed; implementation is deferred, but this is an active storage-scalability risk to revisit as provider count and write concurrency grow.
> **Created:** 2026-06-13
> **Scope:** How ArkScope thinks about multiple SQLite files, source-specific capture stores, canonical read models, and why this is not an immediate implementation slice.

---

## 1. Product stance

ArkScope is a research, analysis, and alerting workbench. It is **not** a trading terminal and should not optimize the whole storage architecture around tick-by-tick monitoring.

The storage priorities are:

1. Do not lose captured data.
2. Keep source, timestamps, freshness, and provenance explicit.
3. Make data queryable by the app, AI cards, and agents.
4. Support backfill / replay / repair.
5. Keep UI reads stable.
6. Accept reasonable latency when the source is healthy, and show stale/disconnected state when it is not.

If the user has TWS / IBKR app open, that remains the better realtime trading surface. ArkScope should be close enough for research context and alerts, but it does not need to become a low-latency execution UI.

---

## 2. The real SQLite problem

The issue is not "SQLite cannot handle this data." The issue is **multiple independent writer processes**.

SQLite WAL handles many readers and one writer. It can serialize writes, but ArkScope should not assume it is safe or pleasant for all of these to write the same DB directly:

- Electron/FastAPI sidecar
- scheduler jobs
- CLI backfill scripts
- Chrome native host
- Firefox native host
- future embedded browser capture path
- agent-triggered writes

That topology risks `database is locked`, latency spikes, skipped writes, and split-brain behavior. It does not necessarily corrupt data, but it makes correctness and operator reasoning harder.

**Principle:** local SQLite is acceptable when write authority is explicit. Multiple processes may request writes; they should not all become direct writers to the same canonical DB.

This is a real architecture issue, not just a future optimization. As ArkScope adds more providers, the chance of concurrent writes rises. The project should treat source-specific DBs or an app-owned write service as the natural next step once write concurrency becomes visible, not as a last-resort rescue.

### Lock safety rule

SQLite lock waiting is safe only under all of these conditions:

1. The write is inside a bounded transaction.
2. The writer uses WAL + `busy_timeout` or an explicit file/process lock.
3. A timeout/skip is recorded in telemetry and surfaced as stale/failed state.
4. The job is idempotent or retryable.
5. No paid/provider response is discarded without a secondary cache or retry path.

If any of those are false, "the DB was locked" is a correctness problem, not just latency. In that case ArkScope should add a source DB, a local write queue, or a single app-owned writer instead of asking independent processes to keep retrying.

---

## 3. Source DBs vs canonical DBs

Splitting by data source is a valid tool, but it should not become the product's main query shape.

Recommended mental model:

```text
source / raw capture DBs            canonical read DBs
------------------------            ------------------
sa_capture.db              ┐
ibkr_capture.db ?          ├──>     market_data.db
polygon_capture.db ?       │        prices / news / IV / fundamentals
finnhub_capture.db ?       ┘        used by UI, AI cards, agents

profile_state.db                    user state / settings / credentials / cards
```

Source DBs isolate ingestion and writer ownership. Canonical DBs serve app queries.

### Good reasons to add a source DB

- A source is written by an independent process outside the sidecar.
- A source has high write frequency or bursty capture behavior.
- A source needs independent rebuild / repair / replay.
- A source can fail without blocking the main app.
- Raw provider payloads need to be preserved separately from normalized records.
- A new provider would otherwise write directly into `market_data.db` from a separate process.

### Bad reasons to add a source DB

- Avoiding a small amount of app-side query complexity.
- Prematurely optimizing for realtime behavior that the product does not require.
- Making every provider its own runtime query target.
- Letting UI / agent flows perform cross-DB joins by default.

### Provider-growth rule

When adding a new provider or a new scheduled collector, the design review must answer one question:

> Does this source write through the app-owned scheduler/write path, or does it need its own source DB/inbox?

Default decisions:

| Writer shape | Default storage decision |
|---|---|
| In-process scheduler job, low-frequency, idempotent writes | May write canonical local DB directly if the lock-safety rule holds. |
| Independent process (browser native host, standalone collector, external helper) | Prefer a source DB or inbox; canonical DB is updated by app-owned normalization. |
| High-frequency stream or bursty capture | Source DB/inbox first; canonical read model updates in batches. |
| Paid-provider response | Must have a secondary cache or durable local write before returning success. |

This keeps the app from slowly recreating a PG-style central write bottleneck inside one SQLite file.

---

## 4. Query model

UI, AI-card evidence, and agents should primarily read from canonical DBs:

- `profile_state.db` for user state.
- `market_data.db` for prices/news/IV/fundamentals and other normalized market evidence.
- `sa_capture.db` for the protected Seeking Alpha capture domain, until a later consolidation rule says otherwise.

`ATTACH` across SQLite DBs is acceptable for operator tools, repair scripts, or bounded read paths. It should not become the default runtime model for dense UI screens, FTS search, pagination, or evidence gathering. Cross-source ranking, dedupe, freshness, and traceability belong in the canonical read model.

---

## 5. Realtime / persistence tiers

Realtime needs are layered:

| Tier | Purpose | Persistence stance |
|---|---|---|
| **Realtime display** | Current quote / forming candle / temporary UI alert context | In memory or short-lived buffer; OK to reconnect and rebuild |
| **Persisted snapshots** | Research-quality intraday history, chart context, alert audit | Store at configured frequency; tolerate small delay |
| **Research archive** | News, SA capture, fundamentals, IV, daily/15m history | Durable, queryable, provenance-rich |

The app can later support IBKR streaming or frequent polling, but that should not force the whole storage system into a trading-terminal architecture.

---

## 6. Current decision

Do **not** start a broad source-DB split now.

This does **not** defer PostgreSQL runtime retirement. These are separate decisions:

- **PG retirement is required:** normal app/runtime reads and writes should end in local stores; PG becomes archive/import/legacy.
- **More source DBs are conditional:** add `ibkr_capture.db`, `polygon_capture.db`, `finnhub_capture.db`, etc. only if writer contention, replay needs, or raw-capture isolation justify them.

The current split (`profile_state.db`, `market_data.db`, `sa_capture.db`) is enough to continue removing PG as long as the lock-safety rule above holds. If it stops holding, the answer is not to keep PG as the safety valve; the answer is to introduce the next local isolation boundary.

So the immediate stance is:

1. Continue PG runtime retirement.
2. Require every new provider/collector to pass the provider-growth rule.
3. Promote source DBs from "deferred" to implementation when lock telemetry, writer shape, or stream requirements justify it.

Current priorities stay:

1. Finish SA cutover follow-ups, especially `extract_sa_comment_signals` port to SQLite.
2. Keep `sa_capture.db` hard-cutover stable through soak.
3. Continue building app-visible query surfaces and agent-accessible data paths.
4. Revisit storage topology when one of the triggers in §7 happens.

The accepted principle is:

> Use SQLite for local-first storage, but keep write ownership explicit. Add source DBs only when they reduce real writer contention or capture risk. Keep app reads on canonical DBs.

---

## 7. Revisit triggers

Reopen this design when one or more is true:

- We observe real `SQLITE_BUSY` / lock contention in production-like use.
- IBKR streaming or high-frequency persisted snapshots become active scope.
- A source needs an independent crash-safe raw ingest buffer.
- Embedded browser / CloakBrowser / app-owned capture replaces external browser extensions.
- CLI and extension writers are consolidated behind an app-owned write service.
- Cross-process write paths become hard to reason about despite file locks.

Until then, this remains a decision record and review checklist, not a broad immediate implementation slice.

---

## 8. Related docs

- `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` — active storage migration and collection plan.
- `SA_CUTOVER_3D_RUNBOOK.md` — Seeking Alpha hard cutover to `sa_capture.db`.
- `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` — storage architecture authority.
- `ARKSCOPE_PROVIDER_CATALOG.md` — provider facts, streaming modes, cost/latency.
