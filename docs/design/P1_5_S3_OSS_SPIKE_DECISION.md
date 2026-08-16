# P1.5 S3 Admin Dashboard — OSS Spike Decision

> **Scope**: 1-day strict spike. Output = THIS doc. No integration.
> **Date**: 2026-05-02.
> **Predecessor**: `PROJECT_PRIORITY_MAP.md` §3 P1.5; decision-log entry 2026-05-02 (selected sequence: P1.5 spike → Phase C spec → Phase C code).

---

## 1. What the dashboard is for

Operational visibility, not analytical exploration. The user
audience is "me, checking that the system is alive." Concretely:

- **Jobs**: name, last run time, status, error if any, recent history
- **Freshness**: SA Market News / SA Alpha Picks / Macro calendar / Reports — last successful update, staleness warnings
- **Errors**: where they cluster (which job, which ticker, which feed)
- **Reports**: list + view recent research reports saved by the agent

It is **NOT** for:
- CRUD over tables (no editing rows by hand)
- BI / chart exploration over time series
- Real-time agent telemetry (separate concern)
- Trade execution or order management

This framing matters because most "admin dashboard" OSS tools assume
CRUD or BI. Our use case is closer to a status console.

## 2. Constraints (the kill criteria)

The spike's first job is to apply these to each candidate. A
candidate that fails any non-negotiable constraint is rejected.

### 2.1 Non-negotiable

1. **No ORM adoption for the dashboard.** ArkScope uses explicit local stores
   and query capabilities. Adding a parallel model layer just to drive a status
   screen would duplicate working read contracts and expand the maintenance area.
2. **JSON API surface already exists** for every read concern the
   dashboard needs (`/jobs/status`, `/jobs/history`,
   `/sa/market-news/health`, `/macro/health`, `/reports`). A tool
   that bypasses this surface and queries the DB directly forks
   the truth source.
3. **Single-process deployment preferred.** API runs in `uvicorn
   src.api.app:create_app --factory`. Adding a separate service
   (its own image / port / metadata DB / cache) is overhead the
   audience-of-one does not benefit from.
4. **Read-only is the default.** Any tool that exposes write
   surfaces by default needs explicit gating; CRUD-default tools
   work against the use case.

### 2.2 Nice-to-have

5. Auth: existing API has no auth gate. Dashboard auth is itself a
   separate decision (basic auth / IP allowlist / nothing on
   localhost) — but the chosen tool should not make auth WORSE
   than the API.
6. Reuses existing pydantic response models so contract drift is a
   single-edit problem.

## 3. Candidate evaluation

### 3.1 sqladmin (`aminalaee/sqladmin`)

- **Shape**: SQLAlchemy ORM-only. Mounts a CRUD admin under a
  FastAPI app for ORM-mapped tables.
- **Verdict**: REJECTED. Fails constraint #1 (no SQLAlchemy in
  repo). Even if we accepted the ORM cost, fails framing — its
  primary affordance is CRUD, which is explicitly not what the use
  case asks for. Read-only mode exists but the tool's value
  proposition collapses without CRUD.
- **Cost to integrate hypothetically**: ~14 ORM models (200-500
  LoC), parallel session/engine management, retest of every
  existing read path that touches the same tables. Days of work
  for a tool we'd then strip features off.

### 3.2 FastAPI Admin (`fastapi-admin/fastapi-admin`)

- **Shape**: Tortoise ORM (or SQLAlchemy via fork). Built around
  CRUD with role-based perms. Heavier than sqladmin.
- **Verdict**: REJECTED. Same ORM gap as sqladmin (Tortoise just
  swaps which ORM is missing). CRUD-default + perms model is
  overspec for "me checking my own system."

### 3.3 Apache Superset

- **Shape**: BI tool. Connects to supported SQL sources through its own
  model layer and lets you build charts / dashboards
  over arbitrary SQL. Has its own metadata DB + Redis +
  Celery worker for caching.
- **Verdict**: REJECTED. Fails constraint #3 (separate service,
  ~400MB image, additional deps). Wrong shape — Superset is for
  exploring data, not "is the system alive". Setting up alerts
  for "job hasn't run in 24h" via Superset is possible but
  fights the tool's grain.
- **Niche where it would win**: if our core need was time-series
  analysis over `news_scores` / `news_sentiment` / RL model
  outputs — but that's a different tool's job (P3.1 RL
  productionization, P2.2 Knowledge Graph). Not this one.

### 3.4 RQ Dashboard / Prefect UI / Hatchet

- **Shape**: Job-queue UIs. Show queued / running / failed tasks
  for their respective queue backends.
- **Verdict**: REJECTED. We don't have a job queue. `src/service/
  jobs.py` is an in-process scheduler with local run telemetry.
  Migrating to RQ / Prefect is
  a separate, larger decision (covered briefly in §6 of priority
  map under "future job queue if S2 outgrows in-process
  scheduler"). Out of scope for P1.5.

### 3.5 Minimal custom (FastAPI + Jinja2 or HTMX)

- **Shape**: New routes under `src/api/routes/admin.py` (or new
  `src/api/admin/` package) that render server-side HTML using
  Jinja2 templates, calling the SAME pydantic-typed read functions
  the existing JSON endpoints use. Optional HTMX sprinkles for
  in-place refresh / partial updates.
- **Verdict**: ✅ RECOMMENDED.
  - Passes all four non-negotiables: no ORM, single process, reuses
    JSON-equivalent read paths via the same dependencies, read-only
    by default.
  - Auth shape is whatever we want (basic auth on `/admin/*`, or
    nothing while behind localhost — explicit decision in
    integration cycle, not now).
  - Footprint: estimated ~300-500 LoC total for v1 covering jobs
    status, jobs history, freshness layers, recent reports list.
    Includes Jinja2 templates + a thin route module + reused
    response models.
  - HTMX is optional and additive; v1 can be plain Jinja2 with
    `?refresh=N` query for periodic reload, HTMX added in v2 if
    the page reload pattern proves annoying.
- **Trade-offs accepted**:
  - We write ~200 lines of HTML/CSS we'd otherwise inherit.
  - We don't get free CRUD — but we explicitly don't want it.
  - We don't get free auth — same explicit decision needed.
- **Why this is leverage-positive**: every existing read endpoint
  already knows how to produce the data; the dashboard is a thin
  presentational shell over JSON, not a parallel data-access layer.

## 4. Recommendation

**Build minimal custom** under `src/api/admin/` (NEW package or
single route module — defer that decision to integration).

Phase-wise scope for the integration cycle (NOT this spike):

- **v1** (1-2 days): Jobs status + history, freshness for SA Market
  News / Alpha Picks / Macro / Reports, recent reports list.
  Server-rendered Jinja2, no JS framework. Auth = decided at
  integration time (likely basic auth gated on env flag).
- **v1.1** (optional, +0.5 day): HTMX for partial refresh on
  long-polling-style status.
- **v2 deferred**: alerts / notifications (already covered by
  `src/monitor/` — dashboard just SHOWS them, doesn't fire);
  per-ticker drill-downs (defer until use signals demand);
  user-customisable views (out of scope for audience-of-one).

## 5. Why not "just curl + jq"

The user already mentioned this implicitly with the smoke endpoints.
For 80% of "is this alive?" questions, four `curl | jq` aliases work.
The dashboard is incremental value when:

- One page summarises 4-5 health surfaces at once (curl loses
  cross-context aggregation)
- Recent runs / errors need scanning, not single-shot lookup
- Mobile / browser browsing is more convenient than terminal
- Sharing a URL with future-self in a note

If the user finds none of those compelling on reflection, the
correct call is to skip integration entirely and stop at this doc.
The spike isn't a commitment to build.

## 6. Out of scope (explicit)

- Job queue migration (RQ / Dramatiq / Prefect): separate decision,
  larger blast radius, only triggered when in-process scheduler
  outgrows current load.
- BI / analytical views: when needed, evaluate Superset / Metabase
  on its own merits, not bundled with this dashboard.
- Multi-user / role-based perms: audience-of-one assumption.
- Real-time websockets / streaming: out of P1.5 scope; current
  pull-with-refresh suffices.

## 7. Decision summary

| Candidate | Verdict | Primary reason |
|---|---|---|
| sqladmin | ❌ | SQLAlchemy gap + CRUD shape |
| FastAPI Admin | ❌ | SQLAlchemy/Tortoise gap + CRUD shape |
| Apache Superset | ❌ | Separate service overhead + BI shape |
| RQ Dashboard / Prefect UI | ❌ | Out of scope (no job queue) |
| Custom minimal (FastAPI + Jinja2) | ✅ | Zero ORM, single process, reuses existing API |

## 8. Next step

Integration is **NOT** the next mainline task — Phase C spec is
(per priority map decision log 2026-05-02). When P1.5 integration
is scheduled, this doc is the input.

This spike is now closed. No code changes from P1.5 land in this
cycle. Phase C spec begins immediately.
