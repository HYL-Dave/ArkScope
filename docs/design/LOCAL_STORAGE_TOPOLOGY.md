# Local Storage Topology

> **Doc type:** Decision record / deferred architecture note
> **Status:** DRAFT — principle is agreed; implementation is deferred until a concrete writer-collision or streaming requirement appears.
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

### Bad reasons to add a source DB

- Avoiding a small amount of app-side query complexity.
- Prematurely optimizing for realtime behavior that the product does not require.
- Making every provider its own runtime query target.
- Letting UI / agent flows perform cross-DB joins by default.

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

Do **not** start a source-DB split now.

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

Until then, this remains a decision record, not an implementation backlog item.

---

## 8. Related docs

- `DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md` — active storage migration and collection plan.
- `SA_CUTOVER_3D_RUNBOOK.md` — Seeking Alpha hard cutover to `sa_capture.db`.
- `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` — storage architecture authority.
- `ARKSCOPE_PROVIDER_CATALOG.md` — provider facts, streaming modes, cost/latency.
