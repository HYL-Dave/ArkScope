# Local-first Financial Research Agent Workbench — Spec

**Date**: 2026-05-02
**Status**: spec phase complete; locks the 9 items below; closes the 7 open questions from the audit; no spec-internal opens. Code does NOT open until reviewer confirms this spec.
**Inputs**:
- `docs/design/PROJECT_PRIORITY_MAP.md` §1 + §10 (newest entry).
- `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md` (factual base).
- `docs/design/CURRENT_PROJECT_CONTEXT.md` (pointer index).
**Non-inputs (intentionally excluded)**:
- `PHASE_A_KNOWLEDGE_GRAPH_SKETCH.md` / `PHASE_D_ANALYSIS_PIPELINE_SKETCH.md` — deferred v2 candidates (knowledge graph, analysis pipeline).
- `PHASE_C_UNIFIED_RUNNER_SPEC.md` — paused; preserved as-is; do not touch in this spec.
- Tool-side memory dirs (`~/.claude/...`, `~/.codex/...`).

---

## 0. What this spec locks vs leaves open

**Locks (9 items)**:
1. Product positioning + 5-layer architecture + non-goals.
2. Deployment-model invariant (one profile dir, web or desktop both read it).
3. Local profile directory contract (path, structure, manifest, lock file).
4. Storage strategy — **two-SQLite split** (`workbench.db` app state + `sa_cache.db` SA ingest, independent writer locks per file) + transient DuckDB on parquet (no persistent DuckDB file in v1) + PG archive/import stance + concrete per-table mapping + SQLite concurrency model.
5. Sync policy (zip-and-go bundle format with **two sanitized export DBs**, manifest schema, single-writer lock per profile, SA evidence sub-class via cross-DB ATTACH, conflict policy).
6. Page IA + bidirectional DTO inventory (8 pages, read + future-write actions + DTO triples).
7. Scheduler storage interface + process interface + deferral trigger (NOT model A/B/C choice).
8. Migration plan (first cut + ordering + mid-stream cross-machine smoke + Phase C resume gate).
9. External ingest clients contract — **storage isolation**: SA native host writes `sa_cache.db` exclusively, NEVER touches `workbench.db`. Future ingest clients each get their own isolated cache DB / inbox file. No direct PG; no hidden second writer to the app DB.

**Decides (7 open questions from audit §11)** — see §10.

**Stays deferred** (named here so deferral is explicit, not silent):
- Scheduler model choice (A embedded / B daemon / C OS cron). Spec locks **storage interface + process interface + deferral trigger** only — model choice waits for the trigger to fire.
- Packaging (PyInstaller / Tauri / launcher). Spec locks only the deployment-model invariant.
- Vector search backend (`sqlite-vec` / LanceDB / Chroma). Out of scope.
- Skill auto-generation (Hermes-style). Out of scope.
- v2 selective sync. Out of scope; sync hooks are designed forward-compatible but not implemented.
- Phase C runner refactor — paused per priority-map resume gate.
- Repo rename Phase 2 — gated on workbench v1 ship.

### 0.1 PG dependence phases (clarification, locked)

The spec uses "v1" with two distinct meanings — disambiguated here so §6.3 (prototype CAN hit PG) does not contradict §8.1 cross-machine smoke (CANNOT hit PG):

- **Pre-v1 prototype phase** (days 2-6 of the migration plan): the read-only UI skeleton (§6.3) is built against the existing `LegacyPostgresBackend` so shape-validation can happen without waiting for migration. PG dependence is **expected and acceptable in this phase**. **No cross-machine smoke runs in this phase.**
- **v1 runtime boundary** (begins when the first migration cut completes — §8.1): once a table is migrated to SQLite, it no longer reads from PG anywhere in the runtime; the UI page consuming it switches to `SQLiteBackend`. **Cross-machine smoke runs here**, but only for the migrated subset. Tables that have not been migrated yet are surfaced in the UI as "available on dev machine only" — the UI does NOT silently fall back to PG on machine B.
- **End-state v1** (when migration plan §8.2 completes): zero PG runtime dependency. `LegacyPostgresBackend` exists only as the import path used by `scripts/migrate_pg_to_local.py --dsn …`.

The phase boundary is the migration cut, not a calendar date. A reader inspecting the spec at any point in time can ask "which tables are on which side of the boundary?" by reading `app.schema_migrations` (SQLite) — if the table appears there, it is past the boundary.

---

## 1. Product Positioning (LOCK #1)

### 1.1 North star (one sentence, locked)

> The agent reads its own accumulated knowledge substrate across sessions and machines; the user sees and edits everything via a research GUI; zipping the profile directory moves a researcher's work between machines.

### 1.2 Five-layer architecture (locked)

| # | Layer | Responsibility | Owns |
|---|-------|---------------|------|
| 1 | Workbench UI | Research workspace surface for the human | Read DTOs from Agent + Data; emit user actions to Agent |
| 2 | Agent Layer | Hermes-capability stack (memory, tools, skills, scheduler, replay, compression, subagents, attachments, prompt-caching) | Reasoning + tool dispatch + memory recall + writing into Profile |
| 3 | Data Layer | Financial ingestion + caches + FTS5 + future vector + cross-source joins | Schema + queries + ingest pipelines; delegates persistence to Profile |
| 4 | Profile Layer | Single local profile directory: SQLite app DB + DuckDB OLAP + raw files + reports + memories + skills + exports | All persistence; one source of truth for the user's research |
| 5 | Portability Layer | Bundle format + lock file + import/export | Cross-machine portability; v2 selective sync surface |

**Dependency direction (top-to-bottom)**: UI consumes Agent + Data; Agent consumes Data and reads/writes Profile; Data lives in Profile; Profile is what Portability bundles. **No upward dependencies allowed.** A Data Layer module must not call Agent functions; an Agent module must not require UI imports.

### 1.3 Hermes capability reference vs product reference (locked)

| Borrow | Don't borrow |
|--------|--------------|
| Filesystem-first profile (`~/.workbench/`-style local dir) | General-purpose agent platform positioning |
| Daemon scheduler shape (single-machine, file-based job definitions) | Hermes' specific RPC tool ABI |
| FTS5 cross-session recall pattern | Their UI choices |
| Skills-as-files convention | Skill auto-generation in v1 (deferred) |

**Differentiation**: financial data layer + investment research workflow. The product is **not** "Hermes for stocks"; it is a research workbench whose agent shares Hermes-grade capabilities.

### 1.4 Non-goals (locked)

The following are explicitly **not** part of the workbench v1 product:
- RL trading model training (paused; existing `training/` code unaffected but not surfaced in UI).
- Backtest framework UI (DuckDB stores backtest results but no v1 UI surface).
- Knowledge graph (Phase A — deferred).
- Vector search (deferred).
- Multi-user collaboration / cloud sync (single-user only).
- Real-time order entry (informational only).
- Live agent collaboration (one user, one machine, one writer at a time).

### 1.5 Repo identity (recap; not re-litigated)

Local repo + code/docs renamed `MindfulRL-Intraday` → `ArkScope` (Phase 2 / P3.2 executed 2026-05-31); remaining lowercase `mindfulrl` (DB name, native host id, addon id, historical docs) intentionally kept. A further *product-brand* rename is still possible if the workbench picks a new name. See `docs/design/CURRENT_PROJECT_CONTEXT.md`.

---

## 2. Deployment Model — invariant, not packaging choice (LOCK #2)

### 2.1 The one invariant

**A web frontend (FastAPI + Jinja2 + HTMX) and a desktop wrapper (any future choice) MUST read the same local profile directory.** This is the only deployment-model claim the spec locks; everything else (PyInstaller / Tauri / launcher / Electron) is deferred.

### 2.2 Implication on code structure

- The web app is the canonical entrypoint in v1 (`python -m src.workbench` or similar; concrete name in §3.4).
- A desktop wrapper, when added, must NOT introduce its own DB or its own config layer — it must point to the same Profile Layer.
- No code may hardcode "the user's home dir is X" — all persistence goes through a single `ProfileLocator` resolver (§3.3).

### 2.3 What's deferred

- Packaging mechanism (PyInstaller single-file / Tauri+sidecar / Python launcher / Electron). Spec only requires that whichever is picked, the invariant above holds.
- Daemon registration (systemd-user / launchd / Windows tray) — deferred with scheduler model choice.
- Auto-update mechanism — deferred until v1.1.

---

## 3. Local Profile Directory Contract (LOCK #3)

### 3.1 Profile location resolver (locked)

Resolution order (first hit wins):

1. `WORKBENCH_PROFILE_DIR` env var (if set; absolute path).
2. Per-OS default:
   - **Linux**: `${XDG_DATA_HOME:-$HOME/.local/share}/workbench` (XDG-compliant).
   - **macOS**: `$HOME/Library/Application Support/Workbench`.
   - **Windows**: `%APPDATA%\Workbench` (i.e. `$HOME/AppData/Roaming/Workbench`).
3. Fallback: `$HOME/.workbench` (when none of the above resolves).

The resolver is implemented by `src/workbench/profile.py:ProfileLocator.resolve()`; all persistence APIs accept an optional `profile_dir` override (for tests + multi-profile experiments) and default to `ProfileLocator.resolve()`.

> Naming note: "Workbench" is a working placeholder. If the eventual product name differs, only `ProfileLocator._APP_NAME` and the dir names change; rest of spec stays valid.

### 3.2 Profile directory structure (locked)

```
<profile_dir>/
├── manifest.json                  ← Profile manifest (§5.3)
├── .workbench.lock                ← Single-writer lock for the app (§5.4); per-profile
├── workbench.db                   ← SQLite: app/user state (§4.1.1) — small, UI/agent-frequent writes
├── workbench.db-{wal,shm}         ← SQLite WAL (transient; excluded from export)
├── sa_cache.db                    ← SQLite: SA raw ingest (§4.1.2) — bulky, SA-native-host-frequent writes; ISOLATED writer lock from workbench.db (per §4.6)
├── sa_cache.db-{wal,shm}          ← SQLite WAL (transient; excluded from export)
├── data/
│   ├── reports/                   ← Markdown research reports (already exists at data/reports/)
│   ├── agent_memory/              ← Markdown agent memories (already exists at data/agent_memory/)
│   ├── chat_history/              ← Per-session JSONL (already exists at data/chat_history/)
│   ├── agent_scratchpad/          ← Per-session scratchpad (device-local, excluded from export)
│   ├── news/                      ← Parquet bulk news (rebuildable; queried via TRANSIENT DuckDB per §4.2)
│   ├── prices/                    ← Parquet bulk prices (rebuildable; transient DuckDB)
│   ├── cache/                     ← TTL caches (rebuildable, excluded from export)
│   └── logs/                      ← Diagnostic logs (device-local, excluded from export)
├── config/
│   ├── user_profile.yaml          ← Watchlist + settings (synced)
│   ├── skills/*.yaml              ← Custom skills (synced)
│   └── .env                       ← API keys (DEVICE-LOCAL; never synced; gitignored upstream)
└── exports/                       ← Bundle outputs land here by default (.zip)

# v2 candidates (NOT in v1; named here so the path layout has room):
#   warehouse.duckdb               ← v2: persistent analytics/cache acceleration (currently transient-only)
#   ingest/sa/*.jsonl              ← v2: append-only SA ingest inbox (compactor → sa_cache.db); upgrade path from v1 sa_cache.db direct-write
#   indexes/                       ← v2: rebuildable FTS5 / vector indexes (currently inline in workbench.db / sa_cache.db)
```

**Filesystem layout invariant**: all paths in DB rows that reference files (e.g. `agent_memories.file_path`) MUST be relative to `<profile_dir>` so the bundle is portable.

### 3.3 ProfileLocator API (locked surface)

```python
# src/workbench/profile.py

class ProfileLocator:
    def resolve(self) -> Path: ...              # current profile dir (cached)
    def db_path(self) -> Path: ...              # <profile>/workbench.db (app state — UI/agent writes)
    def sa_db_path(self) -> Path: ...           # <profile>/sa_cache.db (SA ingest — native host writes ONLY)
    def duckdb_connect(self) -> "duckdb.DuckDBPyConnection": ...
                                                #   Opens a TRANSIENT in-memory DuckDB connection.
                                                #   ATTACHes workbench.db as `app` (read-only) so cross-engine
                                                #   joins work (e.g. news_scores ↔ news parquet). Caller is
                                                #   expected to close. No persistent warehouse.duckdb in v1.
                                                #   v2 may swap this for a persistent path; the helper signature
                                                #   stays stable.
    def data_dir(self, subdir: str) -> Path: ...  # <profile>/data/<subdir>
    def config_path(self, name: str) -> Path: ...
    def manifest_path(self) -> Path: ...        # <profile>/manifest.json
    def lock_path(self) -> Path: ...            # <profile>/.workbench.lock
    def relpath(self, abs_path: Path) -> str: ...

    # Migration helpers (one-shot):
    def migrate_from_repo_data(self, repo_root: Path) -> MigrationReport: ...
```

The first-run experience: app detects no `manifest.json` at the resolved profile dir → invokes **profile bootstrap** (filesystem-only, **NO PG access**): copies `<repo>/data/{reports,agent_memory,chat_history}` + `<repo>/config/{user_profile.yaml,skills}` into the profile dir → creates **two** empty SQLite databases with current schemas (`workbench.db` for app state via `sql/sqlite/app/*.sql`; `sa_cache.db` for SA ingest via `sql/sqlite/sa/*.sql`) → **validates DuckDB extension availability** (no persistent DuckDB file in v1 — see §4.2 transient connection model) and FTS5 trigram availability (per §10.2 fail-fast gate) → writes initial manifest + acquires lock. **First-run does NOT touch PG.** PG → SQLite import is a separate, explicit, opt-in operation via `scripts/migrate_pg_to_local.py --dsn $DATABASE_URL` (DSN provided by the user via flag or env var; the spec does NOT hardcode any host / port / credentials). The user runs this script ONCE per source PG instance, AFTER first-run bootstrap completes.

### 3.4 Module / package conventions (locked)

- New code lives under `src/workbench/` (web app + UI templates + ProfileLocator + new DAL).
- Existing tooling lives where it is (`src/agents/`, `src/tools/`, `src/api/`, `src/service/`).
- `src/api/` (existing FastAPI routes) is reused for HTTP surface; `src/workbench/ui/` adds Jinja2 templates that consume `src/api/` route handlers.

### 3.5 External ingest clients contract (LOCK #9)

> **Why this is its own lock**: a local-first runtime cannot have hidden PG writers leaking outside the main app. The SA Chrome extension (today: `Chrome → Native Messaging → scripts/sa_native_host.py → DataAccessLayer → DatabaseBackend(psycopg2) → PostgreSQL`) is the **first concurrent writer** the workbench will see. If SA keeps writing PG while the main app moves to SQLite, the §0.1 v1 runtime boundary breaks. This lock pulls SA (and any future external writer) into the spec contract — implementation lands at SA migration cut #5 in §8.2; the contract is locked NOW so the cut has clear acceptance criteria.

External ingest clients — today **SA native host** (`scripts/sa_native_host.py`) and future Chrome extensions / third-party tools that write into the workbench — MUST:

1. **Resolve the profile dir via `ProfileLocator`**. No hardcoded paths, no PG DSN env vars, no fallback to "remote PG if local SQLite missing".
2. **Write to ISOLATED storage, never `workbench.db`**. SA native host writes **`sa_cache.db` exclusively** — it must NEVER open `workbench.db` for write. This is the **storage isolation invariant** of LOCK #9: external ingest clients live in a separate DB file so their writer lock cannot block the app's writer lock. Each future ingest client gets its own isolated cache DB / inbox file in the profile directory (e.g. a hypothetical Twitter extension would write `tw_cache.db`, not `workbench.db` and not `sa_cache.db`). Sources: SQLite WAL is per-file single-writer (https://www.sqlite.org/wal.html); DuckDB is single-process write per file (https://duckdb.org/docs/current/connect/concurrency.html) — neither engine offers cheap multi-process write to ONE file, so the only sound design is multiple files. SA native host gets refactored from `psycopg2` to `SQLiteBackend(profile.sa_db_path())` alongside the SA migration cut in §8.2 (cut #5). Until cut #5, SA extension writes to legacy PG in pre-v1 prototype phase ONLY.
3. **Use short transactions** per logical unit. `save_article_with_comments(article, comments)` is one transaction (article + its comments — atomic at the article boundary). `import_batch(80 articles)` is **80 separate transactions**, NOT one. Even with isolation from `workbench.db`, long SA transactions still block other SA writes within `sa_cache.db`.
4. **Coordinate with the profile lock** (`<profile>/.workbench.lock`, §5.4) for **process-existence**, not for write serialization. The lock is per-profile (one app instance per profile); if the main app is running, the native host knows there's a reader on `sa_cache.db` and uses `busy_timeout` (per §4.6) for transient contention. If no app is running, the native host can write `sa_cache.db` independently — it acquires its own lightweight lock on the file via SQLite's built-in file locking.
5. **Be discoverable in the manifest**. `manifest.json` (§5.3) gains an `ingest_clients` field listing external writers that have written to the profile (e.g. `["sa_native_host"]`). Used by `scripts/profile_export.py --include-sa-cache=...` to decide what travels in a bundle.

**Migration timing for SA native host**: rewrite from `DatabaseBackend(psycopg2)` to `SQLiteBackend(ProfileLocator)` lands in cut #5 of the migration plan (§8.2 — `sa_articles` + `sa_article_comments` + FTS5 SQLite migration). Pre-cut-#5: SA extension keeps writing legacy PG (pre-v1 prototype phase only). Post-§8.1 first cut: SA-related UI pages surfaced as "available on dev machine only" until cut #5 lands — same handling as any other not-yet-migrated table per §0.1.

**What this lock does NOT cover**:
- The Chrome extension itself (extension code is upstream of the native host; user-installed; outside the profile).
- Read-only consumers of SA data (those go through DAL like everything else).
- v2 features like remote ingestion / cloud sync — out of scope.

**Embedded-browser prerequisite**: if ArkScope later replaces the external browser extension with an embedded/app-owned browser capture path, the extension code stops being "outside the profile" in practice. That cut must first complete the runtime prerequisite in `SA_EXTENSION_ROADMAP.md`: diagnostics for memory/lifecycle behavior, explicit cleanup of observers/listeners/native ports, capture-core extraction, and a soak-tested session/memory policy.

---

## 4. Storage Strategy (LOCK #4)

### 4.1 SQLite split — `workbench.db` (app state) + `sa_cache.db` (SA ingest)

SQLite splits into **two independent DB files** so the bulky SA-native-host writes do not contend with the small UI/agent writes. Per-file writer-lock semantics (https://www.sqlite.org/wal.html) means two SQLite files = two independent writer locks; bulk writes to `sa_cache.db` do NOT block writes to `workbench.db` and vice versa.

#### 4.1.1 App SQLite (`workbench.db`) — owns user state

Tables under `sql/sqlite/app/0NN_*.sql`:

| App # | Table | Source PG table(s) | Notes |
|-------|-------|-------------------|-------|
| 001 | `research_reports` (+ `referenced_evidence_ids JSON`) | sql/003 | Migration first cut. New JSON column for SA evidence cross-ref (§5.1). |
| 002 | `agent_memories` (+ `referenced_evidence_ids JSON`) + `memory_tickers` + `memory_tags` + `agent_memories_fts` (FTS5) | sql/004 | Junction tables (§10.1); FTS5 trigram (§10.2). |
| 003 | `agent_queries` | sql/001 §agent_queries | Append-only audit log; device-local. |
| 004 | `news_scores` | sql/002 | Joined to news (parquet) via transient DuckDB ATTACH (§4.2). |
| 005 | `financial_data_cache` | sql/005 | TTL rebuildable; device-local. |
| 006 | `job_definitions` (NEW — synced) + `job_runs` (device-local) | sql/011, schema split | Split per audit §1.3 + decision §10.4. |
| 007 | `signals` | sql/001 | Rebuildable. |
| 008 | `fundamentals` | sql/001 | Snapshot blobs; rebuildable. |
| 009 | `cal_economic_events` + revisions + `cal_earnings_events` + revisions + `cal_ipo_events` + revisions + `macro_series` | sql/013 | Macro events. |

#### 4.1.2 SA Cache SQLite (`sa_cache.db`) — owns external ingest

Tables under `sql/sqlite/sa/0NN_*.sql`. **Written by SA native host EXCLUSIVELY** (per §3.5 LOCK #9). The main app reads via `ATTACH DATABASE 'file:<profile>/sa_cache.db?mode=ro' AS sa` — URI form is **required** because SQLite ATTACH defaults to read/write (see §4.1.3 for the full enforcement contract + storage-isolation tests); never writes.

| SA # | Table | Source PG table(s) | Notes |
|------|-------|-------------------|-------|
| 001 | `sa_alpha_picks` + `sa_refresh_meta` | sql/007 | Watchlist-status SA picks. |
| 002 | `sa_articles` (metadata + body) + `sa_article_comments` + `sa_articles_fts` (FTS5) | sql/008 | Body FTS5. |
| 003 | `sa_market_news` (metadata + summary) + `sa_market_news_detail` + `sa_market_news_fts` (FTS5) + `news_tickers` (junction) | sql/009 + sql/010 | FTS5 + tickers via junction. |
| 004 | `sa_comment_signals` + `comment_signal_ticker_mentions` (junction) | sql/012 | Stage 1 rules-based. |

#### 4.1.3 Cross-DB joins (read-only)

When a query needs to join across the two files (e.g. `agent_memories.referenced_evidence_ids` ↔ `sa_articles.id`), use SQLite ATTACH:

```python
# SQLite ATTACH defaults to READ/WRITE — must use URI mode=ro for read-only.
# Connection must be opened with uri=True to enable URI ATTACH.
conn = sqlite3.connect(profile.db_path(), uri=True)
conn.execute(f"ATTACH DATABASE 'file:{profile.sa_db_path()}?mode=ro' AS sa")
conn.execute("""
    SELECT m.title, sa_a.title AS evidence_title
    FROM agent_memories m, json_each(m.referenced_evidence_ids) j
    JOIN sa.sa_articles sa_a ON sa_a.id = json_extract(j.value, '$.id')
    WHERE json_extract(j.value, '$.source') = 'sa_article'
""")
```

**ATTACH read-only enforcement (locked)** — important: SQLite `ATTACH DATABASE` defaults to **read/write**, not read-only. The URI form `file:<path>?mode=ro` is required to make the attached DB read-only at the engine level (and the parent connection must be opened with `uri=True` for URI ATTACH to work). Without `mode=ro`, the main app could accidentally write to `sa.*` tables, breaking the §3.5 LOCK #9 storage isolation invariant. Sources: https://www.sqlite.org/uri.html, https://www.sqlite.org/lang_attach.html.

**Storage-isolation tests (mandatory in `tests/test_storage_isolation.py`)**:
1. Main app opens `workbench.db` with `uri=True`, ATTACHes `sa_cache.db` with `mode=ro`, then attempts `INSERT INTO sa.sa_articles (...)` → must fail with `sqlite3.OperationalError: attempt to write a readonly database` (SQLite returns `SQLITE_READONLY`). Same assertion for `UPDATE` and `DELETE` against any `sa.*` table.
2. Symmetric: SA native host code path is exercised under test; assert it makes no `sqlite3.connect(workbench.db)` call (mock the connect function and fail-fast on any `workbench.db` open).
3. Connection factory contract: `SQLiteBackend._open_connection()` MUST always pass `uri=True`. We deliberately do NOT lock "`uri=False` must fail at URI ATTACH" because SQLite URI handling depends on build / compile-time options (`SQLITE_USE_URI`) that vary across distributions and may change in future SQLite versions. The portable contract is: (a) every production code path opens connections via the factory; (b) the factory always uses `uri=True`; (c) tests (1) and (2) above prove the resulting `mode=ro` ATTACH rejects writes — that is the actual safety property we depend on. Enforcement: a CI lint forbids `sqlite3.connect(...)` outside the factory file (`git ls-files '*.py' | xargs grep -l 'sqlite3.connect' | grep -v 'src/workbench/storage/factory.py'` must produce empty output).

Cross-DB writes are not supported and not needed (SA native host writes only `sa_cache.db`; main app writes only `workbench.db`).

#### 4.1.4 SQLite conventions (apply to BOTH `workbench.db` and `sa_cache.db`)

- Page size: 4096 (default). WAL mode ON.
- All `TIMESTAMPTZ` → `TEXT` (UTC ISO-8601, enforced at DAL boundary).
- All `BIGSERIAL` → `INTEGER PRIMARY KEY AUTOINCREMENT`.
- All `JSONB` → `TEXT` with JSON1 functions; no schema-on-write check beyond JSON validity.
- `TEXT[]` arrays → junction tables (decision §10.1) — never JSON arrays for queryable fields.
- Foreign keys: enforced (`PRAGMA foreign_keys = ON` in DAL bootstrap).
- Schema versioning: each migration file is idempotent (`CREATE TABLE IF NOT EXISTS`); each DB has its own `schema_migrations(version, applied_at)` table — `workbench.db.schema_migrations` for app migrations, `sa_cache.db.schema_migrations` for SA migrations.

### 4.2 DuckDB use pattern — TRANSIENT in v1, no persistent DB file

**v1 does NOT keep a persistent DuckDB file.** DuckDB is used as an **on-the-fly analytical query engine** over the parquet substrate. Each query that needs columnar / OLAP semantics opens a transient connection (`duckdb.connect(":memory:")`), `ATTACH`'s `workbench.db` read-only if a cross-engine join is needed, reads parquet via `read_parquet()`, and closes when done.

**Why no persistent DuckDB file in v1**:
- DuckDB is single-process write per file (https://duckdb.org/docs/current/connect/concurrency.html) — even single-process write locks are coarse. Transient in-memory connections sidestep all the lock-contention concerns.
- No schema versioning needed for DuckDB (no persistent state).
- Bundle and migration become simpler: one less file to sanitize / version / reconcile.
- v1 query volumes (single-user, interactive) make persistence-for-speed unnecessary.

**Use sites in v1** — the workloads `read_parquet()` covers:

| Use site | Backed by | Notes |
|----------|-----------|-------|
| `news` queries (filter by ticker / date / `LIKE` on title) | `data/news/raw/*.parquet` | Cross-join to `app.news_scores` via ATTACH (`mode=ro` per §4.1.3). **No FTS in v1** — DuckDB `fts` extension requires per-table index materialization, and a transient `:memory:` connection rebuilds the index every query, which conflicts with v1 simplicity. Full-text search lives in `sa_cache.db` SA-side FTS5 (`sa_articles_fts`, `sa_market_news_fts` — trigram per §10.2). News headline filtering uses SQL `LIKE '%query%'` (acceptable at single-user scale). v2 candidate: persistent FTS on a `news_fts` table or via `warehouse.duckdb` (§11.1). Source: https://duckdb.org/docs/current/core_extensions/full_text_search.html. |
| `prices` queries (OHLCV by ticker / interval / range) | `data/prices/{15min,hourly}/*.parquet` | Time series scans. |
| `iv_history` queries | `data/options/iv_history/` parquet | Time series scans. |
| `macro_observations` queries | parquet (new path: `data/macro/observations/`) | If observations > 10M rows; otherwise stays in `workbench.db` SQLite. Threshold gated on day-1 measurement. |

**Cross-engine query example** (`news_scores` in SQLite ↔ `news` in parquet):

```python
con = profile.duckdb_connect()  # transient :memory:; auto-ATTACHes app DB
con.execute(f"""
    SELECT n.title, n.published_at, s.sentiment_score
    FROM read_parquet('{profile.data_dir("news/raw")}/*.parquet') n
    LEFT JOIN app.news_scores s ON s.news_id = n.id
    WHERE n.ticker = 'NVDA' AND n.published_at > '2026-01-01'
""")
```

**`warehouse.duckdb`** (persistent analytics cache) is a v2 candidate — see §11. Trigger to introduce it: v1 query latency proves insufficient (measurable: news search > 1s wall time on a typical query) AND the user explicitly requests acceleration. Default v1 position: transient DuckDB is enough.

**Conventions** (apply to every transient DuckDB connection):
- `ATTACH '<profile>/workbench.db' AS app (TYPE sqlite, READ_ONLY);` for app-DB joins.
- `ATTACH '<profile>/sa_cache.db' AS sa (TYPE sqlite, READ_ONLY);` for SA-DB joins (only when needed; many DuckDB queries don't touch SA).
- All write paths go through SQLite (`workbench.db` or `sa_cache.db`) or write parquet files; DuckDB transient connections see new data on next query — DuckDB is **never the write-of-record store**.

### 4.3 Filesystem — owns raw payloads

| Path | Class | Synced? |
|------|-------|---------|
| `data/reports/*.md` | Syncable | Yes (in bundle) |
| `data/agent_memory/*.md` | Syncable | Yes |
| `data/chat_history/*.jsonl` | Syncable | Yes |
| `data/agent_scratchpad/*` | Device-local | No |
| `data/news/raw/*.parquet` | Rebuildable | No |
| `data/prices/{15min,hourly}/*.parquet` | Rebuildable | No |
| `data/cache/*` | Rebuildable | No |
| `data/logs/*` | Device-local | No |

### 4.4 PG archive/import stance (locked)

PG schemas at `sql/0NN_*.sql` (the existing 13 migrations) become **legacy / archive** as of this spec. Stance:

- **No new development** writes against PG. New schema work targets `sql/sqlite/0NN_*.sql` (and DuckDB-readable parquet).
- **One-shot import path** stays usable: `scripts/migrate_pg_to_local.py --dsn $DATABASE_URL` (or `--dsn <PG_DSN>`) reads from a PG instance specified by the user and populates SQLite + DuckDB / parquet. The script does NOT default to any specific host; the spec does not hardcode connection details. Implemented in step 1 of the migration plan (§8).
- **Existing `DatabaseBackend` (psycopg2)** is renamed `LegacyPostgresBackend` and kept import-only; **NOT** registered as a runtime DAL backend in v1.
- **`sql/0NN_*.sql` files**: not deleted (history) but moved to `sql/legacy/` to prevent new development against them.
- **8 psycopg2 source files** (per audit §5.3): `src/tools/backends/db_backend.py` becomes `legacy_db_backend.py`; the others (`src/macro_calendar/store.py`, `src/service/job_runs_store.py`, `src/sa/comment_signal_backfill.py`, `src/tools/sa_tools.py`, `src/tools/sa_digest_tools.py`, `src/service/macro_calendar_health.py`, `src/tools/freshness.py`) are re-pointed at the new `SQLiteBackend` via Protocol — no parallel implementations.

### 4.5 DAL Protocol extension (locked)

Current `src/tools/backends/__init__.py:DataBackend` Protocol is read-only. Spec extends with **typed write methods**, designed bidirectional from day one. Concrete additions (target file: `src/tools/backends/__init__.py`):

```python
@runtime_checkable
class DataBackend(Protocol):
    # ── Read methods (existing — unchanged signatures) ────────────────
    def query_news(...) -> pd.DataFrame: ...
    def query_prices(...) -> pd.DataFrame: ...
    def query_iv_history(...) -> pd.DataFrame: ...
    def query_fundamentals(...) -> dict: ...
    def query_sec_filings(...) -> pd.DataFrame: ...
    def get_available_tickers(...) -> List[str]: ...

    # ── New read methods (audit §4.1 gaps) ────────────────────────────
    def query_memories(*, query: Optional[str], tickers: Optional[List[str]],
                       tags: Optional[List[str]], category: Optional[str],
                       limit: int = 50) -> pd.DataFrame: ...
    def query_reports(*, ticker: Optional[str], days: int = 30,
                      report_type: Optional[str], limit: int = 50) -> pd.DataFrame: ...
    def query_job_runs(*, job_name: Optional[str], status: Optional[str],
                       since: Optional[datetime], limit: int = 100) -> pd.DataFrame: ...
    def query_job_definitions(*, enabled_only: bool = False) -> pd.DataFrame: ...
    def query_chat_history_index(*, days: int = 30) -> pd.DataFrame: ...

    # ── Write methods (new; bidirectional DTO contract) ───────────────
    def upsert_memory(self, input: MemoryCreateInput | MemoryUpdateInput) -> int: ...
    def delete_memory(self, memory_id: int) -> Optional[str]: ...     # returns deleted file_path
    def upsert_report(self, input: ReportCreateInput | ReportUpdateInput) -> int: ...
    def delete_report(self, report_id: int) -> Optional[str]: ...
    def upsert_job_definition(self, input: JobDefinitionCreateInput | JobDefinitionUpdateInput) -> int: ...
    def delete_job_definition(self, job_id: int) -> None: ...
    def upsert_watchlist(self, input: WatchlistUpdateInput) -> None: ...    # writes config/user_profile.yaml
```

Existing `DatabaseBackend` (now `LegacyPostgresBackend`) and the new `SQLiteBackend` both implement this Protocol. v1 runtime registers only `SQLiteBackend` (with optional DuckDB-augmentation for OLAP queries via composition, not Protocol extension).

### 4.6 SQLite concurrency model (locked, sub-lock under #4)

> **Critical clarification**: **SQLite single-writer is per-FILE, not per-app**. Two SQLite files = two **independent** writer locks. With `workbench.db` (app state) and `sa_cache.db` (SA ingest) split per §4.1, bulk SA writes do NOT block UI memory saves at the engine level — they target different files and contend with different locks. This is the structural fix for the SA-vs-UI contention concern that §3.5 LOCK #9 addresses; the mitigations below are for in-engine concurrency *within* each DB file (e.g. UI write vs scheduler write, both in `workbench.db`). Source: https://www.sqlite.org/wal.html.

Within each DB file (multi-reader / single-writer), v1 mitigations are mandatory:

**1. PRAGMAs at every connection open** (`SQLiteBackend._open_connection()`):
- `PRAGMA journal_mode = WAL;` — concurrent reads + non-blocking writes; WAL files (`.db-wal`, `.db-shm`) are device-local and excluded from bundle (§5.1).
- `PRAGMA busy_timeout = 10000;` — wait up to 10 seconds for a lock before raising `SQLITE_BUSY`. v1 default; per-call override allowed for hot loops or batch ingest.
- `PRAGMA foreign_keys = ON;` — enforce FKs (junction tables in §10.1 rely on `ON DELETE CASCADE`).
- `PRAGMA synchronous = NORMAL;` — WAL durability without fsync per commit. Acceptable for single-user research; we are NOT writing financial-orders-grade data.

**2. Transaction discipline** — every write path:
- Uses **short transactions**: one logical unit per `BEGIN ... COMMIT`. Never wraps an HTTP fetch loop or LLM call inside a transaction.
- For SA native host bulk writes: per-article transaction, NOT per-batch. `save_article_with_comments(article, comments)` is one transaction; `import_batch(80 articles)` is 80 separate transactions.
- Scheduler `tick_once`: writes the `job_run` row in a single transaction at end of work; never holds a transaction during job execution.
- Memory / report saves: each save = one transaction (memory row + junction-table inserts).

**3. UI write retry** — DAL retries on `SQLITE_BUSY` up to 3 times with exponential backoff (50ms, 200ms, 800ms). After 3 failures, surfaces "ingest in progress — retry shortly" (or analogous) to the UI; UI does not block waiting on a writer it doesn't control.

**4. Reader cache** — read paths use a separate connection from write paths (WAL allows this without contention). Read connections may set `PRAGMA query_only = ON;` as a safety net.

**5. Validation** — `tests/test_sqlite_concurrency.py` exercises (a) UI write while SA native host bulk-writes 80 articles; (b) scheduler tick during UI write; (c) retry path when `busy_timeout` is exceeded. All three must complete without `SQLITE_BUSY` reaching the UI surface.

---

## 5. Sync Policy (LOCK #5)

### 5.1 Three-class model with SA evidence sub-class (locked)

> Important: NEITHER `workbench.db` NOR `sa_cache.db` is a single sync unit. Tables inside each are classified individually; the bundle uses **two sanitized export DBs** built table-by-table per §5.2, not copies of the live DBs. This means a new device-local table inside `workbench.db` doesn't accidentally leak into the bundle, and `sa_cache.db` (default device-local) only contributes its evidence subset.

- **Device-local** (excluded from bundle): `config/.env`, `data/agent_scratchpad/`, `data/cache/`, `data/logs/`, `data/news/raw/`, `data/prices/`, `agent_queries` (in `workbench.db`), `job_runs` (in `workbench.db`; runtime audit log), `.workbench.lock`, all `*.db-wal` / `*.db-shm` for both DBs, **the entirety of `sa_cache.db` by default** (rebuildable via re-scrape; selective subset travels via the next class), SA refresh meta (extension cookies, last-fetched timestamps).
- **Syncable** (always included in bundle): `manifest.json`, `data/reports/*.md`, `data/agent_memory/*.md`, `data/chat_history/*.jsonl`, `config/user_profile.yaml`, `config/skills/*.yaml`, plus selected tables inside `workbench.db` — `research_reports`, `agent_memories` (+ junction tables `memory_tickers` / `memory_tags`), `news_scores`, `job_definitions`.
- **SA evidence (selectively syncable, default-on)**: rows in `sa_cache.db` (`sa_articles` / `sa_article_comments` / `sa_market_news`) whose IDs are referenced by saved `research_reports.referenced_evidence_ids` or `agent_memories.referenced_evidence_ids`. Computed at export time via cross-DB ATTACH (§5.2 step 5). **Default-included** — the user's research is incomplete without the SA articles their reports / memories actually cite.
- **SA bulk cache (selectively syncable, default-off)**: rest of `sa_cache.db` (rows not referenced by reports/memories) + refresh metadata + cookies. **Default-excluded**. Opt-in via `scripts/profile_export.py --include-sa-cache=all`. Re-scrape on machine B is the alternative.
- **Rebuildable** (excluded from bundle): all parquet caches (`data/news/raw/`, `data/prices/`, `data/options/iv_history/`), all TTL caches (`data/cache/`), no persistent DuckDB file in v1 (transient connections only — see §4.2).

**Schema change required** (lands as part of cut #1 — `research_reports` migration in §8.1, and cut #2 — `agent_memories`): both tables get a `referenced_evidence_ids TEXT NOT NULL DEFAULT '[]'` column (SQLite JSON1 array of objects shaped `{"source": "sa_article" | "sa_market_news" | "sa_comment", "id": <int>}`). Populated at save-time: by the agent when a report cites an article (auto-tracked from tool result chain), or by the user when manually saving a memory tied to an article. The export script joins these to compute the SA evidence subset.

`scripts/profile_export.py --include-sa-cache=evidence-only|all|none`:
- `evidence-only` (default): SA evidence sub-class only.
- `all`: SA evidence + SA bulk cache.
- `none`: skip SA tables entirely (force re-scrape on machine B).

### 5.2 Bundle format with sanitized export DB (locked)

**Filename**: `workbench-profile-v1-<source-machine-hint>-<UTC-timestamp>.zip`

**Layout (zip-internal paths, all relative)**:

```
workbench-profile-v1-<host>-<ts>.zip
├── manifest.json
├── workbench-export.db          ← sanitized app SQLite (built from workbench.db; syncable subset only; per §5.1)
├── workbench-sa-export.db       ← sanitized SA SQLite (built from sa_cache.db; SA evidence subset by default; per §5.1)
├── data/
│   ├── reports/...
│   ├── agent_memory/...
│   └── chat_history/...
└── config/
    ├── user_profile.yaml
    └── skills/
        └── *.yaml
```

**Why two sanitized export DBs and not the live ones**: `workbench.db` mixes syncable and device-local tables; `sa_cache.db` is default-device-local but contributes the SA evidence subset. A naive `VACUUM INTO` or file-copy of either DB would leak the wrong things. Sanitized export DBs carry only the right subset, table-by-table.

**Sanitized DB build process** (in `scripts/profile_export.py`):
1. Acquire read locks on both live `workbench.db` and `sa_cache.db`. If the main app holds the writer lock on either, refuse OR obtain exclusive lock (with explicit user confirmation).
2. Create empty `workbench-export.db`; run app schema migrations 001-N up to the live app DB's current version (read from `app.schema_migrations`).
3. For each **Syncable** app-DB table (per §5.1): `INSERT INTO export.<table> SELECT * FROM live.<table>;`.
4. Skip device-local app-DB tables entirely (no `INSERT` for `agent_queries`, `job_runs`, etc.) — the script's table allowlist enforces this at the table level.
5. **Compute SA evidence reference set** via cross-DB ATTACH (SA DB attached read-only per §4.1.3):
   ```sql
   ATTACH DATABASE 'file:workbench.db?mode=ro' AS app;
   ATTACH DATABASE 'file:sa_cache.db?mode=ro'  AS sa;
   -- (source_id, source) pairs cited by user's saved reports/memories:
   SELECT json_extract(j.value, '$.id')     AS source_id,
          json_extract(j.value, '$.source') AS source
     FROM app.research_reports r, json_each(r.referenced_evidence_ids) j
   UNION
   SELECT json_extract(j.value, '$.id'),
          json_extract(j.value, '$.source')
     FROM app.agent_memories m, json_each(m.referenced_evidence_ids) j;
   ```
   Yields rows where `source ∈ {'sa_article', 'sa_comment', 'sa_market_news'}`. The export script materializes this into a temp table `evidence(source_id INTEGER, source TEXT)` for use in step 7.

6. Create empty `workbench-sa-export.db`; run SA schema migrations 001-N up to the live SA DB's current version. **DO NOT recreate FTS5 virtual tables yet** — they get rebuilt at step 8 from content tables.

7. **Apply per-source export graph** — each evidence source type has its own dependency closure. A single `WHERE id IN <set>` is wrong because SA tables have different keys (comments tied to `article_id`, detail tied to `news_id`, junction tables, FTS virtual tables that must NEVER be raw-copied):

   | Source type | Export graph (what travels with this evidence row) |
   |-------------|--------------|
   | `sa_article` | `sa_articles` row at `id`; **all** `sa_article_comments` for that `article_id` (entire thread = research context); skip `sa_comment_signals` (rebuildable from comments). |
   | `sa_comment` | The parent `sa_articles` row (article context); the specific `sa_article_comments` row at `id`; **other comments in the same thread are NOT auto-included** — the user cited one, so we ship one + parent (keeps bundle small for "I cited one comment from a long thread" cases). |
   | `sa_market_news` | `sa_market_news` row at `id`; `sa_market_news_detail` row at the same `id`; `news_tickers` junction rows for that news id. |

   Implementation: per source type, run a templated SQL block. Example for `sa_article`:
   ```sql
   INSERT INTO sa_export.sa_articles
     SELECT * FROM live_sa.sa_articles
     WHERE id IN (SELECT source_id FROM evidence WHERE source = 'sa_article');
   INSERT INTO sa_export.sa_article_comments
     SELECT * FROM live_sa.sa_article_comments
     WHERE article_id IN (SELECT source_id FROM evidence WHERE source = 'sa_article');
   ```

   `--include-sa-cache=all`: skip the WHERE clauses; copy entire content tables (FTS still gets rebuilt at step 8).
   `--include-sa-cache=none`: skip step 7 entirely; sanitized SA DB ships with empty content tables (FTS step 8 creates empty FTS tables).

8. **Rebuild FTS5 virtual tables in BOTH sanitized DBs** from the now-populated content tables. FTS5 virtual tables MUST NOT be raw-copied — they reference internal rowids and tokenization state that is not portable across DB files.

   For the app sanitized DB (`workbench-export.db`):
   ```sql
   CREATE VIRTUAL TABLE app_export.agent_memories_fts USING fts5(title, content, tokenize='trigram');
   INSERT INTO app_export.agent_memories_fts(rowid, title, content)
     SELECT id, title, content FROM app_export.agent_memories;
   ```

   For the SA sanitized DB (`workbench-sa-export.db`):
   ```sql
   CREATE VIRTUAL TABLE sa_export.sa_articles_fts USING fts5(title, body, tokenize='trigram');
   INSERT INTO sa_export.sa_articles_fts(rowid, title, body)
     SELECT id, title, body FROM sa_export.sa_articles;
   -- analogous for sa_market_news_fts (over title + summary).
   ```

   Each FTS rebuild is a one-time cost at export time; NOT incurred during normal app operation. Note that `agent_memories` content lives in the **app** DB (not SA) — its FTS rebuild reads from `app_export.agent_memories`, not from the SA export DB.

9. Validate: open both sanitized DBs, verify `schema_migrations` match the manifest's `schema_versions`, verify row counts match `contents_summary`, run a sample FTS5 query against each rebuilt FTS table to confirm functional.

10. Bundle BOTH **sanitized** DBs into the zip (NOT the live ones).

**Excluded from bundle entirely** (enforced by allowlist, not denylist):
- `config/.env`, `data/cache/`, `data/news/`, `data/prices/`, `data/logs/`, `data/agent_scratchpad/`, `workbench.db` (live), `sa_cache.db` (live), `*.db-wal`, `*.db-shm`, `.workbench.lock`, `exports/`. **No persistent DuckDB file exists in v1** — `warehouse.duckdb` is a v2 candidate (see §11) and would be excluded as rebuildable when introduced.

**Allowlist semantics**: the export script knows exactly what to include; anything not on the list is implicitly excluded. The sanitized export DB construction makes this enforceable at the table level too — a new device-local table doesn't accidentally get bundled because the script's table allowlist would not include it. **Adding a new table to the syncable allowlist is a deliberate spec-touching change** (review forces a sync-class decision per §5.1).

### 5.3 Manifest schema (locked)

`manifest.json` lives at the profile dir root **and** inside the bundle. Schema:

```json
{
  "bundle_version": 1,
  "created_at": "2026-05-02T10:30:00Z",
  "source_machine_hint": "machine-a",
  "schema_versions": {
    "sqlite_app": "009",
    "sqlite_sa": "004",
    "config": "1"
  },
  "contents_summary": {
    "app_db_size_bytes": 1234567,
    "sa_db_size_bytes": 5678901,
    "files": {
      "reports": 12,
      "agent_memory": 38,
      "chat_history_sessions": 5
    },
    "sa_evidence_rows_included": 17,
    "sa_bulk_cache_included": false
  },
  "ingest_clients": ["sa_native_host"],
  "excludes_explicit": [
    "config/.env",
    "data/cache/**",
    "data/news/**",
    "data/prices/**",
    "data/logs/**",
    "data/agent_scratchpad/**",
    "workbench.db",
    "sa_cache.db",
    "*.db-wal",
    "*.db-shm",
    ".workbench.lock",
    "exports/**"
  ],
  "import_compatibility_min_version": 1
}
```

**Validation on import**:
- `bundle_version` must be `<= current` and `>= import_compatibility_min_version` (= 1 in v1).
- `schema_versions.sqlite_app` must be `<= current app SQLite migration count`. If less, importer runs the missing app migrations on the imported `workbench-export.db` BEFORE merging.
- `schema_versions.sqlite_sa` must be `<= current SA SQLite migration count`. Same rule for `workbench-sa-export.db`. Each DB's migrations are validated independently — a bundle from machine A may have advanced the app schema (newer reports schema) while the SA schema is unchanged, or vice versa.
- `excludes_explicit` is informational (proves the source machine ran the same allowlist).

### 5.4 Single-writer lock (locked)

**Path**: `<profile_dir>/.workbench.lock`

**Format** (JSON):
```json
{
  "machine_hostname": "machine-a",
  "machine_id_short": "...",
  "pid": 12345,
  "started_at": "2026-05-02T10:00:00Z",
  "app_version": "v0.1.0"
}
```

**Behavior**:
- App acquires lock on startup. If lock exists and points at a different `(hostname, pid)`, **app refuses to start** with a clear message + `--force-unlock` override (and a printed warning that force-unlock is destructive if the other instance is genuinely running).
- App releases lock on clean exit (SIGTERM handler + atexit hook).
- App detects stale locks (same hostname, PID not running) and auto-clears.
- Lock file is **excluded from bundle** (per §5.2 exclude list).

**Conflict policy v1**: forbid concurrent two-machine writes. If a user wants to run on machine B while machine A is running, machine B's app refuses to start until either (a) machine A exits cleanly or (b) `--force-unlock` is used (after which the user is responsible for not running both).

**v2 selective sync**: not implemented in v1; the sync policy intentionally has no conflict-merge logic. Selective sync needs CRDT-style or last-writer-wins semantics that would break the "single source of truth" property; defer until evidence shows the v1 zip-and-go pattern is insufficient.

### 5.5 Export / import scripts (locked surface)

```python
# scripts/profile_export.py
def export(profile_dir: Path, output_zip: Path, *,
           dry_run: bool = False) -> ExportReport: ...

# scripts/profile_import.py
def import_bundle(bundle_zip: Path, target_profile_dir: Path, *,
                  merge_strategy: Literal["fail-on-conflict", "force-overwrite"] = "fail-on-conflict",
                  dry_run: bool = False) -> ImportReport: ...
```

`merge_strategy=fail-on-conflict` is v1 default. `force-overwrite` is escape hatch for "I know what I'm doing".

---

## 6. Page IA + bidirectional DTO Inventory (LOCK #6)

### 6.1 Page IA (locked v1 set)

8 pages in v1 read-only prototype. Two new composite endpoints + one new DAL read method (`query_memories`).

| # | Page | Path | Reads from | New routes needed |
|---|------|------|-----------|-------------------|
| 1 | Research home | `/` | watchlist, recent reports, recent anomalies, source health | `GET /research/home` (composite) |
| 2 | Ticker workspace | `/ticker/{ticker}` | news, SA digest, macro slice, signals, fundamentals | (uses existing per-source routes) |
| 3 | Evidence browser | `/evidence` | news + SA + comments + signals + memories (full-text) | `GET /evidence/search` (composite) |
| 4 | Memory / notes browser | `/memory` | `agent_memories` | `GET /memory` (NEW) |
| 5 | Reports browser | `/reports` | `research_reports` | (uses existing `/reports`) |
| 6 | Jobs / scheduler | `/jobs` | `job_definitions`, `job_runs` | (uses existing `/jobs/*`) |
| 7 | Source health + sync status | `/health` | `/sa/market-news/health`, `/macro/health`, sync state | `GET /sync/status` (NEW) |
| 8 | Agent investigation trace | `/trace/{session_id}` | per-session chat_history + replay traces | `GET /trace/{session_id}` (NEW) |

### 6.2 Bidirectional DTO inventory (locked)

For every page that has future write actions, DTOs are defined **now** (in spec) and implemented **now** (in `src/workbench/dtos/`), even if write paths are not wired through UI in v1. The default shape, where resource semantics apply, is the **DTO triple** — `<Resource>DTO` (read) + `<Resource>CreateInput` + `<Resource>UpdateInput`. **Singleton resources** (one-doc-per-profile semantics) skip the Create input because creation is implicit (the doc always exists); they have `<Resource>DTO` + `<Resource>UpdateInput` only. The `n/a` entries in the table below mark these singletons (Watchlist, Profile sync).

| Resource | Read DTO | Create input | Update input | Future write actions (page #) |
|----------|---------|--------------|--------------|-------------------------------|
| Memory | `MemoryDTO` | `MemoryCreateInput` | `MemoryUpdateInput` | edit metadata (4); save to memory (2) |
| Report | `ReportDTO` | `ReportCreateInput` | `ReportUpdateInput` | save report (2); delete (5); promote (5) |
| Watchlist | `WatchlistDTO` | n/a (single doc) | `WatchlistUpdateInput` | edit (1) |
| Investigation note | `InvestigationNoteDTO` | `InvestigationNoteCreateInput` | `InvestigationNoteUpdateInput` | save note (2, 8) |
| Job definition | `JobDefinitionDTO` | `JobDefinitionCreateInput` | `JobDefinitionUpdateInput` | create / pause / delete (6) |
| Skill | `SkillDTO` | `SkillCreateInput` | `SkillUpdateInput` | edit / save (config/skills, page 7) |
| Profile sync | `SyncStatusDTO` | n/a | `SyncTriggerInput` | trigger export / import (7) |

**Implementation note**: DTOs are pydantic v2 `BaseModel` subclasses in `src/workbench/dtos/`. The Update input fields are all `Optional[T] = None` (partial-update semantics); the Create input fields follow construction validity. Read DTO is a superset of both inputs plus derived/system fields (`id`, `created_at`, `file_path`, etc.).

### 6.3 Read-only prototype scope (locked)

> **Phase**: this is the **pre-v1 prototype phase** per §0.1. PG dependence is acceptable here and only here. As soon as §8.1 first migration cut lands, the boundary changes per §0.1 v1 runtime semantics.

**Implements**:
- All 8 pages render against existing PG reads (DAL stays on `LegacyPostgresBackend` for tables that haven't been migrated yet; migrated tables flip to `SQLiteBackend` per §8.1 — this transition begins as the prototype phase ends).
- 4 new routes: `/research/home`, `/evidence/search`, `/memory`, `/sync/status` — though `/sync/status` returns "not yet operational" in read-only phase.
- 1 new DAL Protocol read method: `query_memories`.
- DTO module `src/workbench/dtos/` complete, including create/update inputs (used by route handlers for input parsing only — write methods raise `NotImplementedError` until §8 migration cuts each table).

**Does NOT implement**:
- Any write path UI surface (no "edit memory" button, etc.).
- Bundle export / import UI (CLI only in v1).
- Scheduler page settings UI (status only; no create/pause/delete).

---

## 7. Scheduler — storage interface + process interface + deferral trigger (LOCK #7)

Per audit §7.4 and reviewer correction: spec does NOT pick scheduler model A/B/C. Spec locks **the surfaces that don't depend on the model choice**, so model A/B/C selection later is a small swap.

### 7.1 Storage interface (locked)

Two new SQLite tables (per §4.1 row 010):

```sql
CREATE TABLE job_definitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    job_kind        TEXT NOT NULL,          -- python_module / shell / agent_skill
    spec            TEXT NOT NULL,          -- JSON: payload to dispatch (module path, args, etc.)
    schedule_cron   TEXT,                   -- e.g. "0 18 * * 1-5"  (optional; NULL = manual only)
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- job_runs already exists (sql/011 → migrated to SQLite as sqlite/010).
-- Schema split: job_runs.job_definition_id INTEGER REFERENCES job_definitions(id) ON DELETE SET NULL;
ALTER TABLE job_runs ADD COLUMN job_definition_id INTEGER REFERENCES job_definitions(id);
```

`job_definitions` is **syncable**. `job_runs` is **device-local**. (Per §5.1.)

### 7.2 Process interface (locked)

```python
# src/workbench/scheduler/__init__.py

class SchedulerCore:
    def list_due(self, now_utc: datetime) -> list[JobDefinitionDTO]: ...
    def tick_once(self, now_utc: datetime) -> list[JobRunReport]: ...
    # tick_once is the single entrypoint that any of {Model A asyncio loop,
    # Model B daemon ticker, Model C OS-cron-spawned process} calls.
```

`SchedulerCore` is **storage-bound, process-agnostic**. Whichever model wins the deferred decision, it reduces to "call `tick_once(now_utc)` every N seconds in some host process".

### 7.3 Deferral trigger (locked)

The Model A / B / C choice opens to spec adjustment when **any** of these fires:

1. **First user request** to schedule a job that requires running while UI is closed (overnight market close fetch, daily morning prep job, etc.) — concrete trigger; observed via the workbench UI's `/jobs` create form. **Effect**: spec re-opens to commit to A vs B vs C; until decision lands, scheduling stays disabled.
2. **First v1 user installation on a non-development machine** where the user expects the app to be runnable as a desktop binary — drives packaging, which drives daemon registration semantics. **Effect**: same as (1).
3. **End of v1 stable period (≥ 2 weeks)** with no occurrences of (1) or (2) — at which point the *user* may **manually enable Model A** via a UI toggle ("Enable scheduling — Model A: embedded timer"). The 2-week safety net does **NOT** auto-enable scheduling; it only unblocks the user from doing so without further spec work. Two weeks without (1) or (2) is itself evidence that Model A is sufficient for this user's workflow.

**State machine** (concrete, eliminates ambiguity):

| State | Trigger that exits | Behavior |
|-------|-------------------|----------|
| **Initial** (day 1 onward) | (1), (2), or (3) | Scheduler scaffolding present; embedded timer disabled; `/jobs` page shows "Scheduling not yet enabled — see SCHEDULER decision in priority map §10". |
| **Trigger (1) or (2) fired** | spec re-decision committed | Same as Initial; UI shows "Scheduling pending model decision" until A / B / C is committed in spec. |
| **Trigger (3) fired (day 15+, no 1 or 2)** | user toggles "Enable Model A scheduler" | UI exposes a toggle; **until the user flips it, behavior is identical to Initial**. Once flipped, the embedded timer activates (`tick_once` runs every N seconds; default N=60 mirroring Hermes' gateway tick). |
| **Model A active** | user toggles off OR (1) / (2) fires (which would re-open spec) | Jobs run as scheduled. |

This avoids shipping half-implemented scheduling AND avoids the "default by convention" reading where the timer would silently activate without explicit user intent.

### 7.4 What stays out of scope

- APScheduler / Celery / Dramatiq / Prefect choice — irrelevant until model A/B/C decided.
- systemd unit files / launchd plists / Windows Task Scheduler entries — same.

---

## 8. Migration Plan (LOCK #8)

### 8.1 First migration cut (locked)

**Target**: `research_reports` table (app SQLite #001 — `sql/sqlite/app/001_research_reports.sql` per §4.1.1).

**Why first**: smallest blast radius, already file-backed (`data/reports/*.md`), tiny row count, no FTS dependency, syncable class.

**Acceptance criteria**:
1. New SQLite migration `sql/sqlite/001_research_reports.sql` creates table + indexes (`idx_reports_tickers` via junction `report_tickers`, `idx_reports_date`, `idx_reports_type`).
2. New backend `SQLiteBackend` implements `query_reports`, `upsert_report`, `delete_report` against the new table.
3. One-shot import: `scripts/migrate_pg_to_local.py --dsn $DATABASE_URL --table research_reports` reads from PG `research_reports` (DSN supplied by user via flag or env var) and inserts into SQLite, with `data/reports/*.md` file paths re-rooted relative to `<profile_dir>` (already relative). The `--dsn` argument is **mandatory**; the script never defaults to any host.
4. UI's `/reports` page reads via the new `SQLiteBackend` (the `LegacyPostgresBackend` is unregistered for this table).
5. **Cross-machine smoke**: `scripts/profile_export.py --out /tmp/p1.zip` on machine A → unzip on machine B → app shows the same reports on machine B (read via `SQLiteBackend`, **NOT** PG; per §0.1 v1 runtime boundary). Tables that have not been migrated yet are NOT visible on machine B — the UI surfaces them as "available on dev machine only" rather than silently falling back to a PG instance that may not exist there. The smoke test is what proves the v1 runtime boundary holds for the migrated subset.

**Triggers next migration cut**: only after smoke passes on machine B.

### 8.2 Subsequent ordering (locked)

```
First cut:    research_reports                      (app/001 — sql/sqlite/app/001_research_reports.sql)
Mid-stream:   ── CROSS-MACHINE SMOKE GATE ──
Second cut:   agent_memories + memory_tickers       (app/002 — sql/sqlite/app/002_agent_memories.sql)
              + memory_tags + agent_memories_fts
              ↑ longest pole; FTS5 trigram + junction tables; ~2.5-3 days
Third cut:    job_definitions + job_runs split      (app/006 — sql/sqlite/app/006_jobs.sql;
                                                     stub job_runs lands earlier per §10.4 placeholder;
                                                     same file is updated in-place to add job_definitions)
Fourth cut:   chat_history_index                    (no schema; expose existing JSONL via DAL read)
Fifth cut:    sa_articles + sa_article_comments     (sa/002 — sql/sqlite/sa/002_articles.sql)
              + sa_articles_fts                     SA native host migrates from
                                                    psycopg2 → SQLiteBackend(profile.sa_db_path())
                                                    HERE per §3.5 LOCK #9 cut #5
Sixth cut:    news_scores                           (app/004 — sql/sqlite/app/004_news_scores.sql)
                                                    + transient DuckDB cross-engine ATTACH proof
                                                    (mode=ro per §4.1.3) joining news parquet
Seventh cut:  remaining SA tables                   (sa/001 alpha picks, sa/003 market news + detail,
              + macro + cal_* tables                 sa/004 comment signals, app/009 cal_* + macro_series)
                                                    — bulk migration once shape is settled
```

Each cut: (a) writes the SQLite migration, (b) adds the `SQLiteBackend` methods, (c) re-points existing tools / API routes / UI page from `LegacyPostgresBackend` to `SQLiteBackend`, (d) one-shot import script run, (e) regression test on the page that consumes the table, (f) (only after first cut) cross-machine smoke updated to include the new table.

### 8.3 Cross-machine smoke insertion-point (locked)

**Inserted between cut #1 and cut #2**, not at end. Reasoning: the SQLite-portability claim is the highest-blast-radius unknown. Verifying it after cut #1 = sunk cost is one cut; verifying after cut #7 = sunk cost is seven cuts.

Smoke procedure: see audit §3.4 (already detailed; do not re-spec here).

### 8.4 Phase C resume gate (locked, recap)

Phase C runner refactor resumes only after **all three**:
1. Workbench v1 ships.
2. ≥ 2 weeks stable single-user use (no storage / scheduler / sync regressions).
3. ≥ 1 verified cross-machine migration (zip-and-go smoke passes on a second machine, with reports + memories + chat history visible).

`docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md` is preserved as-is; when the gate fires, commit 1 of Phase C opens against that preserved spec without re-spec'ing.

### 8.5 What is NOT migrated (stays on `LegacyPostgresBackend` import-only)

The agent-runtime data — `news`, `prices`, `iv_history`, `fundamentals` — get migrated to **DuckDB-on-parquet**, not SQLite. Existing parquet files in `data/news/raw/` and `data/prices/{15min,hourly}/` are already the source of truth; the PG copy is redundant. Migration step for these is "stop writing to PG; DuckDB reads parquet directly" — much smaller surface than re-importing.

---

## 9. Effort Reality Check (recap audit §9)

14-day target with locked scope. Tracking against this spec:

| Phase | Effort | Cumulative |
|-------|--------|------------|
| Audit | done | day 0 |
| Spec (this doc) | done | day 1 |
| `ProfileLocator` + manifest + lock file + first migration cut (`research_reports`) | 2 days | day 3 |
| Read-only UI skeleton (8 pages, 4 new routes, DTO module) | 2-3 days | day 6 |
| Cross-machine smoke + bug fixes | 0.5-1 day | day 7 |
| Memory subsystem migration (FTS5 trigram + junction tables + tests) | 2.5-3 days | day 10 |
| `job_definitions` + `job_runs` schema split + scheduler interfaces | 1-1.5 days | day 11.5 |
| 2-3 more migration cuts (chat_history index, news_scores + DuckDB ATTACH proof, sa_articles FTS) | 2-3 days | day 14 |

Token budget ($2000-3000): comfortably within budget; Phase C deferral saves ~$500-1000 of agent time that would have been the 7-commit chain.

---

## 10. Open Question Decisions (LOCK)

All seven open questions from audit §11 are decided here. **No spec-internal opens remain.**

### 10.1 Tickers / tags storage shape — JSON arrays vs junction tables

**Decision**: **junction tables** (`memory_tickers (memory_id INTEGER NOT NULL REFERENCES agent_memories(id) ON DELETE CASCADE, ticker TEXT NOT NULL, PRIMARY KEY (memory_id, ticker))`; analogous `memory_tags`, `news_tickers`, `comment_signal_ticker_mentions`).

**Rationale**: matches GIN array overlap semantics in PG (`tickers && ARRAY['NVDA']` → `EXISTS (SELECT 1 FROM memory_tickers WHERE memory_id = ? AND ticker = 'NVDA')` with proper index). Queryable; fast filter by ticker; `ON DELETE CASCADE` keeps junction clean automatically. Cost is ~50 LoC schema + ~30 LoC DAL helpers per table that has tickers/tags. JSON-array alternative looks simpler but full-table-scans on filter, which hurts the "agent searches its substrate" core flow.

### 10.2 FTS5 tokenizer for Chinese

**Decision**: **`trigram`** tokenizer (FTS5 builtin). Tokenizer config: `tokenize = 'trigram'`. Custom tokenizers (jieba, `simple_tokenizer.so`) deferred to v1.1 if quality is insufficient.

**Rationale**: zero external dependency (FTS5 ships with `trigram` since SQLite 3.34); works for any Unicode text including Chinese / Japanese / Korean without needing per-language segmentation; ranking is "good enough" for `agent_memories` ("find the memory I'm thinking of") and `sa_articles` body search ("find the article that mentioned X"). Custom tokenizer adds installation friction (compiled `.so` must travel with the app) which conflicts with "即開即用" goal. If trigram quality proves insufficient (measurable: false-negative rate on Chinese content searches > 20%), v1.1 swap is a single migration: drop FTS table, re-create with new tokenizer, re-index — no schema change needed.

**Fail-fast environment gate** (locked): on profile bootstrap (`ProfileLocator.bootstrap()`) and on every app startup, run a trigram-availability probe — `CREATE VIRTUAL TABLE temp.fts_check USING fts5(x, tokenize='trigram'); DROP TABLE temp.fts_check;`. If this raises (likely SQLite < 3.34 or `fts5` extension not built), the app refuses to start with a clear error pointing at the SQLite version requirement (≥ 3.34) and instructions to upgrade. Probe cost is negligible (one-time per startup); rationale: a bundled SQLite that silently lacks trigram would degrade FTS to a no-op without a visible error, which is exactly the kind of "silent capability loss across machines" that the local-first pivot is supposed to eliminate.

### 10.3 `news_scores` placement — SQLite or DuckDB

**Decision**: **SQLite**. `news_scores` lives in `workbench.db` (app SQLite #004 — `sql/sqlite/app/004_news_scores.sql`); transient DuckDB ATTACHes `workbench.db` read-only (`mode=ro` per §4.1.3) for the cross-engine join with `news` parquet.

**Rationale**: `news_scores` is small (one row per news × scoring model × effort), write-heavy at scoring time (insert per LLM call), read-light (filter to `WHERE news_id IN (...)` per query). SQLite handles row-wise insert efficiently; DuckDB updates to columnar parquet are batch-friendly but expensive for trickle inserts. The cross-engine join is cheap — DuckDB ATTACH SQLite is well-supported; query pattern: `SELECT n.title, s.sentiment_score FROM news n LEFT JOIN app.news_scores s ON s.news_id = n.id`.

### 10.4 `job_definitions` split timing

**Decision**: **with scheduler interface lock**, on day 11.5 of the migration plan (§9). NOT earlier.

**Rationale**: schema split is cheap once the scheduler interface (`SchedulerCore.tick_once`) is designed. Doing it earlier means designing the schema before knowing what `tick_once` consumes — risk of designing twice. Until then, the existing `job_runs` table stays as-is (read-only via DAL) and the `/jobs` UI page shows the unsplit history. **Placeholder**: a stub migration `sql/sqlite/app/006_jobs.sql` mirroring the current PG `job_runs` schema (without `job_definitions`) lands as part of an earlier cut so read-only UI works on SQLite before the split. The same `app/006_jobs.sql` file is **updated in-place at cut #3** to add `job_definitions` and the `job_definition_id` FK column on `job_runs` — single migration file, two states reflecting the schema's evolution.

### 10.5 Scheduler model deferral trigger — when forced

**Decision**: **any** of three concrete triggers (per §7.3): (1) first user request to schedule a job requiring "runs while UI closed"; (2) first v1 install on non-dev machine where desktop-binary expectation drives packaging; (3) end of v1 stable period (≥ 2 weeks) with neither (1) nor (2) — at which point Model A becomes default by convention.

**Rationale**: explicit triggers prevent the deferral from sliding into "indefinite postponement". Trigger (3) is the safety net so that "indefinitely deferred" cannot happen.

### 10.6 Profile bundle format

**Decision**: zip with relative paths + `manifest.json` at root, allowlist-based export, schema in §5.2 + §5.3 (already locked above).

**Rationale**: zip is universal (no `tar`/`tar.gz` cross-platform pain on Windows); relative paths are portable; allowlist semantics prevent future leaks; `manifest.json` carries schema versions for forward-compatible imports.

### 10.7 Sync conflict policy v1

**Decision**: **forbid concurrent two-machine writes**. Mechanism: `.workbench.lock` file in profile dir + `--force-unlock` escape hatch (§5.4 already locked).

**Rationale**: SQLite WAL files are not safe under concurrent writes from two processes / two machines; the data shape (single user, one workstation at a time) does not need merge semantics; v2 selective sync would require CRDT-style design that costs more than the current product warrants. v1 is "you only run on one machine at a time"; the lock makes that claim enforceable rather than aspirational.

---

## 11. Out of Scope / Deferred / Parked (recap)

- **Phase C runner refactor** — paused; resume gate locked at §8.4. Spec preserved.
- **Knowledge graph (Phase A)** — deferred per priority map P2.2.
- **Vector search backend** — deferred until vector tooling is concretely requested.
- **Skill auto-generation** — deferred to v1.1+.
- **v2 selective sync** — explicitly parked; v1 is zip-and-go only.
- **Packaging** — deferred; spec only locks deployment-model invariant (§2.1).
- **Scheduler model A/B/C** — deferred; spec locks storage + process interface + trigger (§7).
- **Repo rename Phase 2** — gated on workbench v1 ship.
- **README + `CLAUDE.md` content rewrite** — gated on workbench v1 ship; alias mapping in pivot notice covers the immediate need.
- **Multi-user / cloud sync / live order entry / real-time collaboration** — non-goals (§1.4).

### 11.1 Storage-layer v2 candidates (named here so v1 leaves room)

These items live in the directory layout (§3.2) as documented v2 placeholders, NOT v1 deliverables:

- **`warehouse.duckdb` — persistent analytics/cache acceleration**. v1 uses transient DuckDB connections (§4.2) on parquet, which is enough for single-user query volumes. Trigger to introduce: news search > 1s wall time on a typical query AND user explicitly requests acceleration.
- **`ingest/sa/*.jsonl` — append-only ingest inbox + background compactor**. v1 has SA native host writing `sa_cache.db` directly (one transaction per article, per §3.5 LOCK #9). v2 candidate: native host writes append-only JSONL batches, a background compactor reads JSONL → indexes into `sa_cache.db` / DuckDB / FTS / vector index. Removes write-load on `sa_cache.db` during scrape; lets ingest happen while main app is offline. Trigger: SA contention measurable (busy_timeout retries on SA writes > 5% of writes) OR user wants offline scrape with deferred indexing.
- **`indexes/` — out-of-line FTS5 / vector indexes**. v1 has FTS5 inline in `workbench.db` (`agent_memories_fts`) and `sa_cache.db` (`sa_articles_fts`, etc.). v2 candidate: rebuild as standalone files for faster reindex on tokenizer change (§10.2 v1.1 swap path) and to add vector indexes (`sqlite-vec` / LanceDB / Chroma — separate decision). Bundle treats these as rebuildable; never synced.

These are forward-compatible — adopting any of them does NOT require breaking changes to v1 contracts (ProfileLocator API, manifest schema, bundle layout). The directory entries are reserved by spec but unused in v1.

---

## 12. References

- `docs/design/PROJECT_PRIORITY_MAP.md` §1 + §10 — canonical "what's next?" + decision log.
- `docs/design/LOCAL_FIRST_RESEARCH_WORKBENCH_AUDIT.md` — fact base for this spec.
- `docs/design/CURRENT_PROJECT_CONTEXT.md` — pointer index.
- `docs/design/PHASE_C_UNIFIED_RUNNER_SPEC.md` — preserved Phase C spec, paused.
- ARKSCOPE_RENAME_PHASE2.md (removed 2026-06-07; see git history + memory project_rename_arkscope.md) — rename Phase 2 plan, gated on workbench v1.
- Audit §3 sync surface, §4 GUI feasibility, §5 storage blast radius, §6 memory portability, §7 scheduler, §8 Hermes-capability gap — pre-spec inventory.

---

**Next**: open commit 1 of the migration plan (§8.1) — `ProfileLocator` + first manifest + first lock-file + `research_reports` migration cut + cross-machine smoke. **Do NOT** start until reviewer confirms this spec.
