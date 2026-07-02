# S-G Scorer Cutover Implementation Plan

Status: plan for review
Branch: `codex/s-g-scorer-cutover-plan`
Date: 2026-07-03

## Map Check

`PROJECT_PRIORITY_MAP.md` names S-G as the next active PG-exit line after the C-1 reconciliation: scorer cutover first, then the rest of the PG-exit remainder. `PG_EXIT_REMAINDER_SCOPING.md` §6 is the detailed authority and classifies `news_scores` as a market-data domain with strategy `cutover`, placed near N8b reads.

This plan keeps S-G scoped to score storage and score reads. It does not redesign the LLM scoring rubric, pick new models, add quality filtering, or change the C-1 SA evidence feed. Those are separate product decisions.

## Current Grounding

The current system has three score realities:

1. PostgreSQL still has `news_scores` with roughly 503k multi-model score rows.
2. Local hard-news reads intentionally downgraded score-dependent results to `NULL` / empty after S3/N8a, as a conscious PG-exit tradeoff.
3. The active scorer script writes scored Parquet columns. `scripts/migrate_to_supabase.py --scores` is the path that imports those Parquet score columns into PG `news_scores`.

The normalized news model is live and local, but it only has `news_articles.sentiment_score`, a nullable single-score vestige. That column is not a valid authority for `news_scores`, because the PG table preserves:

- `score_type` (`sentiment` or `risk`)
- `model`
- `reasoning_effort`
- `score`
- `scored_at`

S-G therefore adds a local multi-model score table instead of collapsing historical scores into `news_articles.sentiment_score`.

## Desired End State

After S-G:

- Historical PG `news_scores` are migrated into local SQLite as `news_article_scores`.
- Runtime score-dependent news reads use local SQLite only.
- `query_news(scored_only=True)`, `query_news_search(scored_only=True)`, and `query_news_stats()` regain sentiment/risk values from local scores.
- Projection-only N8a legacy rows can still find their normalized `article_id`.
- PG `news_scores` is no longer a runtime authority.
- `scripts/migrate_to_supabase.py --scores` is not the active score import path.
- The existing Parquet scorer remains available, but PG score import is replaced by a local score import/cutover path.

S-G does not drop PG tables. Physical PG drops remain N9/S-H cleanup after read and ingest cutovers are complete.

## Core Design Decisions

### D1. Local Score Authority

Add a normalized local table:

```sql
CREATE TABLE IF NOT EXISTS news_article_scores (
    article_id         INTEGER NOT NULL
                       REFERENCES news_articles(id) ON DELETE CASCADE,
    score_type         TEXT NOT NULL
                       CHECK (score_type IN ('sentiment','risk')),
    model              TEXT NOT NULL,
    reasoning_effort   TEXT NOT NULL DEFAULT '',
    score              REAL NOT NULL
                       CHECK (score BETWEEN 1 AND 5),
    scored_at          TEXT NOT NULL,
    source             TEXT NOT NULL DEFAULT 'pg_news_scores_cutover',
    source_legacy_news_id INTEGER,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    PRIMARY KEY (article_id, score_type, model, reasoning_effort)
);

CREATE INDEX IF NOT EXISTS idx_news_article_scores_article
ON news_article_scores(article_id);

CREATE INDEX IF NOT EXISTS idx_news_article_scores_latest
ON news_article_scores(article_id, score_type, scored_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_article_scores_model
ON news_article_scores(score_type, model, reasoning_effort);
```

`reasoning_effort` is stored as an empty string when the PG row has `NULL`, matching the existing uniqueness behavior in `migrate_to_supabase.py`.

### D2. Latest Score Semantics

Default reads use the latest score per `(article_id, score_type)` ordered by:

1. `scored_at DESC`
2. `model DESC`
3. `reasoning_effort DESC`

Model-filtered reads use the latest score per `(article_id, score_type, model)` across reasoning effort. If the caller passes a model name, normalize dashes and dots to underscores the same way existing score column detection does.

The migration preserves every model/effort row. The reader chooses a default latest projection only at query time.

### D3. Legacy Read Bridge

N8a has not cut over every reader to normalized articles yet. Runtime reads still query the legacy `news` projection, so score joins must map a legacy `news.id` to normalized `article_id` through both maps:

```sql
COALESCE(m.article_id, p.article_id) AS article_id
```

where:

- `news_legacy_migration_map m` maps N7 historical rows.
- `news_legacy_projection_map p` maps N8a forward-projected rows.

Using only `news_legacy_migration_map` would miss new post-N8a rows. Using only `news_legacy_projection_map` would miss historical rows. Both are required until N8b removes legacy reads.

### D4. Migration Source

Historical migration reads PG `news_scores` as a read-only source and writes local SQLite. This is acceptable because S-G is a cutover from PG authority to local authority. The command must fail closed if the reviewed fingerprint changes.

The migration maps PG `news_scores.news_id` to normalized `article_id` with `news_legacy_migration_map`. Rejected or unmapped historical rows are counted and included in the proof packet. They are not guessed by title/date.

Projection-only N8a rows do not exist in PG `news_scores` history; they only need read-bridge support for future scores.

### D5. Future Local Imports

The existing Parquet scorer remains a standalone manual tool. S-G adds a local score import path so future scored Parquet can populate `news_article_scores` without PG:

```text
scripts/scoring/score_ibkr_news.py  -> scored parquet columns
python -m src.news_normalized.score_import -> local news_article_scores
```

`scripts/migrate_to_supabase.py --scores` becomes a deprecated PG archive/import path and must not be called by runtime or documented workflows after S-G. It may remain physically present until N9, but the docs and grep gate must prove no runtime path uses it.

## Risk Boundaries

- This slice writes the local market DB during the live apply. It requires a backup and `market_write_lock`.
- This slice reads PG once for historical scores. If PG is unreachable, preview/apply cannot run; runtime after cutover must not require PG.
- This slice does not call OpenAI. It imports existing scores only.
- This slice does not alter the scorer model, prompt, rubric, token budget, or key handling.
- This slice does not drop PG `news_scores`.

## Task 1 — Schema and Hermetic Score Helpers

Files:

- `src/news_normalized/schema.py`
- `src/news_normalized/scores.py` (new)
- `tests/test_news_normalized_schema.py`
- `tests/test_news_normalized_scores.py` (new)

Implement:

1. Add `news_article_scores` DDL to `ARTICLE_SCHEMA`.
2. Add helper functions in `src/news_normalized/scores.py`:

```python
def normalize_score_model(model: str | None) -> str:
    """Return the storage/query model key used by score imports and readers."""

def normalize_reasoning_effort(value: str | None) -> str:
    """Return empty string for NULL/blank effort and stripped lower-case otherwise."""

def score_key(article_id: int, score_type: str, model: str, effort: str | None) -> tuple:
    """Return the canonical upsert key."""
```

3. Add query snippets/helpers for latest score joins. These should return SQL fragments or CTE strings used by `SqliteBackend`, not open connections themselves.

Tests:

- RED: schema creation should include `news_article_scores` and indexes.
- RED: uniqueness is `(article_id, score_type, model, reasoning_effort)`.
- RED: invalid `score_type` and score outside 1-5 fail.
- RED: `normalize_score_model("gpt-5.2") == "gpt_5_2"`.
- RED: `normalize_reasoning_effort(None) == ""`.

Verification:

```bash
pytest tests/test_news_normalized_schema.py tests/test_news_normalized_scores.py -q
```

## Task 2 — Score Migration Planner

Files:

- `src/news_normalized/score_migration.py` (new)
- `tests/test_news_score_migration.py` (new)

Implement pure planner logic with no live DB writes:

```python
@dataclass(frozen=True)
class ScoreSourceRow:
    legacy_news_id: int
    score_type: str
    model: str
    reasoning_effort: str | None
    score: float
    scored_at: str

@dataclass(frozen=True)
class ScoreMigrationRow:
    article_id: int
    legacy_news_id: int
    score_type: str
    model: str
    reasoning_effort: str
    score: float
    scored_at: str

@dataclass(frozen=True)
class ScoreMigrationPlan:
    rows: tuple[ScoreMigrationRow, ...]
    source_rows: int
    mapped_rows: int
    unmapped_rows: int
    duplicate_keys: int
    counts: dict[str, int]
    fingerprint: str
```

Planner rules:

1. Join source rows to `news_legacy_migration_map`.
2. Only rows with non-null `article_id` are migrated.
3. Rows mapping to rejected legacy rows are counted as `unmapped_rows`.
4. Duplicate keys collapse deterministically by latest `scored_at`; ties use lexicographic `(score_type, model, reasoning_effort, legacy_news_id)`.
5. The fingerprint is sorted JSON over normalized migration rows and counts. It must not contain generated timestamps.

Tests:

- A mapped PG score becomes a local score row.
- A rejected/unmapped legacy ID is counted and skipped.
- Duplicate source rows for one upsert key choose deterministic latest.
- Fingerprint is byte-stable for input ordering changes.
- Score type/model/effort normalization matches Task 1 helpers.

Verification:

```bash
pytest tests/test_news_score_migration.py tests/test_news_normalized_scores.py -q
```

## Task 3 — Preview CLI and Proof Packet

Files:

- `scripts/migration/news_scores_cutover.py` (new)
- `tests/test_news_scores_cutover_cli.py` (new)
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md`

Add a CLI:

```bash
python scripts/migration/news_scores_cutover.py preview \
  --market-db data/market_data.db \
  --pg-dsn "$DATABASE_URL" \
  --output /tmp/news-scores-cutover-preview.json
```

Preview behavior:

1. Open SQLite with `file:...?mode=ro` and `PRAGMA query_only=ON`.
2. Open PG read-only if supported by the connection; otherwise never execute writes.
3. Read only `news_scores` and local mapping tables.
4. Emit JSON with:
   - `fingerprint`
   - `pg_score_rows`
   - `mapped_rows`
   - `unmapped_rows`
   - `duplicate_keys`
   - `article_count`
   - `score_type_counts`
   - `model_counts`
   - `reasoning_effort_counts`
   - `latest_scored_at`
   - `would_apply`
5. `would_apply` is true only when:
   - mapped rows are non-zero
   - duplicate resolution is deterministic
   - no malformed score type/score value exists

The proof packet must also report whether any `news_scores.news_id` points to a legacy row rejected by N7. That count is not automatically a blocker, but it must be visible.

Tests:

- Preview creates no normalized score table if it does not already exist.
- Two previews over the same fake data are byte-identical.
- Malformed score rows make `would_apply=false`.
- The output contains no DSN, score text, title, URL, body, or API key value.

Verification:

```bash
pytest tests/test_news_scores_cutover_cli.py tests/test_news_score_migration.py -q
```

Review gate:

- Run preview twice against live data in a quiet window.
- Reviewer independently reproduces the fingerprint and counts.
- No live apply without explicit approval of the reviewed fingerprint.

## Task 4 — Apply CLI

Files:

- `scripts/migration/news_scores_cutover.py`
- `src/news_normalized/score_migration.py`
- `tests/test_news_scores_cutover_apply.py` (new)

Add:

```bash
python scripts/migration/news_scores_cutover.py apply \
  --market-db data/market_data.db \
  --pg-dsn "$DATABASE_URL" \
  --expected-fingerprint <reviewed-fingerprint> \
  --backup data/market_data.db.bak-pre-news-scores-sg-<UTC>.db \
  --confirm-scheduler-paused
```

Apply order:

1. Acquire `market_write_lock(timeout=30.0)`.
2. Re-run preview and compare full report fingerprint and counts.
3. Create backup with `backup_market_db(overwrite=False)`.
4. Open SQLite writable.
5. `BEGIN IMMEDIATE`.
6. Ensure schema.
7. Insert an audit row in a new table:

```sql
CREATE TABLE IF NOT EXISTS news_score_migration_runs (
    id                INTEGER PRIMARY KEY,
    fingerprint       TEXT NOT NULL UNIQUE,
    counts_json       TEXT NOT NULL,
    backup_path       TEXT NOT NULL,
    applied_at        TEXT NOT NULL
);
```

8. Upsert `news_article_scores`.
9. Validate in the same transaction.
10. Commit.
11. Reopen read-only and validate again.
12. Re-run preview/apply planner and assert idempotence.

Validation:

- `news_article_scores` row count equals `mapped_rows - duplicate_keys`.
- No score has an article ID missing from `news_articles`.
- No score has invalid score type or score outside 1-5.
- `news_score_migration_runs.fingerprint` matches the reviewed fingerprint.
- Re-applying with the same fingerprint is a no-op.
- Applying with a different fingerprint raises before backup.

Rollback behavior:

- Any exception before commit rolls back all local score rows and audit rows.
- The backup is retained.
- There is no partial score table population after failure.

Tests:

- Apply writes rows, audit row, and is idempotent.
- Apply refuses fingerprint drift before backup.
- Apply rollback leaves zero score rows after injected failure.
- No-clobber backup path is required.

Verification:

```bash
pytest tests/test_news_scores_cutover_apply.py tests/test_news_scores_cutover_cli.py -q
```

## Task 5 — Local Score Reads for Legacy News Projection

Files:

- `src/tools/backends/sqlite_backend.py`
- `src/tools/backends/local_market_backend.py`
- `tests/test_sqlite_backend.py`

Change `SqliteBackend` news score behavior from "local single sentiment only" to "local normalized multi-model score authority when tables exist".

Implementation shape:

1. Add `_news_score_tables_available()` checking `news_article_scores` and at least one mapping table.
2. Add a score bridge CTE:

```sql
WITH article_bridge AS (
  SELECT n.id AS legacy_news_id,
         COALESCE(m.article_id, p.article_id) AS article_id
  FROM news n
  LEFT JOIN news_legacy_migration_map m ON m.legacy_news_id = n.id
  LEFT JOIN news_legacy_projection_map p ON p.legacy_news_id = n.id
),
latest_sentiment AS (...),
latest_risk AS (...)
```

3. `query_news(scored_only=True)` returns rows with either sentiment or risk.
4. `query_news(model="...")` returns rows with the requested model's scores.
5. `query_news(scored_only=False)` surfaces score columns when present but still returns unscored rows.
6. `query_news_search(scored_only=True)` uses the same bridge.
7. `query_news_stats()` aggregates local normalized scores:
   - `scored_count`: rows with local sentiment or risk
   - `avg_sentiment`: average latest sentiment
   - `avg_risk`: average latest risk
   - bullish/bearish from latest sentiment

Fallback behavior:

- If score tables are absent, keep the current honest-empty scored behavior.
- Never call PG for scored requests.
- Keep existing strict-mode behavior.

Tests:

- Historical row mapped through `news_legacy_migration_map` surfaces sentiment and risk.
- Projection-only row mapped through `news_legacy_projection_map` surfaces sentiment and risk.
- `model="gpt-5.2"` filters to normalized model `gpt_5_2`.
- `scored_only=True` filters to scored rows.
- `scored_only=False` returns scored and unscored rows.
- Search and stats use the same local scores.
- With no score table, the existing retired/honest-empty behavior remains.
- PG poison test proves scored requests do not call `DatabaseBackend`.

Verification:

```bash
pytest tests/test_sqlite_backend.py -q
```

## Task 6 — DataAccess and Tool Parity

Files:

- `src/tools/data_access.py`
- `src/tools/news_tools.py`
- `src/tools/signal_tools.py`
- `tests/test_news_tools.py`
- `tests/test_signal_tools.py`
- `tests/test_local_market_backend.py` if present; otherwise add focused tests to `tests/test_sqlite_backend.py`

Most DAL/tool code should need no behavioral rewrite if Task 5 preserves the existing dataframe shape. This task is a parity gate:

1. `get_news_sentiment_summary` should return non-empty scored summaries when local scores exist.
2. `search_news_advanced` should respect `min_sentiment` and `max_risk`.
3. `detect_anomalies` should no longer report "No scored news" when local score fixtures exist.
4. `get_news_brief` should include non-null sentiment/risk stats.

If any tool currently assumes PG-only score semantics, move the assumption to local score semantics without changing public tool schemas.

Tests:

- Tool-level fixtures use `LocalMarketDatabaseBackend` with PG poisoned.
- Scored news summary works with local `news_article_scores`.
- Risk filter works with local risk scores.
- No PG method is called for score-dependent tool paths.

Verification:

```bash
pytest tests/test_news_tools.py tests/test_signal_tools.py tests/test_sqlite_backend.py -q
```

## Task 7 — Local Score Import for Future Scored Parquet

Files:

- `src/news_normalized/score_import.py` (new)
- `scripts/scoring/import_news_scores_local.py` (thin CLI, new)
- `tests/test_news_score_import.py` (new)
- `tests/test_news_scores.py`

Implement a local replacement for `migrate_to_supabase.py --scores` that imports scored Parquet columns into `news_article_scores`.

Source matching order:

1. If the Parquet row has a legacy `article_hash` and it maps to a local legacy news ID, use `news_legacy_migration_map`.
2. If the Parquet row has provider identity fields compatible with normalized keys, resolve via `news_article_keys`.
3. If neither resolves exactly, skip and count as `unmatched_rows`.

Do not fuzzy-match by title/date in the importer. S-G has a historical PG migration for the existing corpus; future local imports must be exact to avoid score misattachment.

CLI:

```bash
python scripts/scoring/import_news_scores_local.py \
  --market-db data/market_data.db \
  --news-dir data/news \
  --dry-run
```

Rules:

- `--dry-run` emits counts and fingerprint, no write.
- Apply requires `--expected-fingerprint`.
- Apply uses `market_write_lock`, `BEGIN IMMEDIATE`, and idempotent upserts.
- Output never prints article text, body, title, URL, or API keys.

Tests:

- Detect existing score columns exactly as `FileBackend` and `migrate_to_supabase` did.
- Import by legacy article hash.
- Import by normalized provider key.
- Unmatched rows are counted and skipped.
- Re-import is idempotent.
- Output is sanitized.

Verification:

```bash
pytest tests/test_news_score_import.py tests/test_news_scores.py -q
```

## Task 8 — Deprecate PG Score Import Path

Files:

- `scripts/migrate_to_supabase.py`
- `tests/test_news_scores.py`
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- `docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md`

After Tasks 1-7 are implemented and before live apply is marked complete:

1. Update `scripts/migrate_to_supabase.py --scores` help text to state that PG `news_scores` is archived and local score import is the active path.
2. Keep the old function importable for archival tests, but prevent accidental default import-all from importing scores into PG after S-G unless `--scores` is explicitly passed with an archive flag.
3. Add a test that `main()` without flags no longer imports `news_scores` into PG.
4. Update docs to direct operators to `import_news_scores_local.py`.

This is intentionally not a physical deletion. N9 owns deletion of old PG migration paths after the broader PG-exit completion gates pass.

Verification:

```bash
pytest tests/test_news_scores.py tests/test_news_score_import.py -q
```

## Task 9 — Live Preview and Dry-Run Apply on Copy

This task is operational and gated.

1. Run live preview twice in a quiet window:

```bash
python scripts/migration/news_scores_cutover.py preview \
  --market-db /mnt/md0/PycharmProjects/ArkScope/data/market_data.db \
  --pg-dsn "$DATABASE_URL" \
  --output /tmp/news-scores-sg-preview-1.json

python scripts/migration/news_scores_cutover.py preview \
  --market-db /mnt/md0/PycharmProjects/ArkScope/data/market_data.db \
  --pg-dsn "$DATABASE_URL" \
  --output /tmp/news-scores-sg-preview-2.json
```

2. `cmp` the two JSON reports.
3. Reviewer independently reproduces:
   - fingerprint
   - source rows
   - mapped rows
   - unmapped/rejected rows
   - duplicate keys
   - model/type counts
4. Copy the live DB to `/tmp` or `/mnt/md0/tmp` and run full apply against the copy.
5. Verify:
   - live DB byte-identical
   - copy quick_check ok
   - apply succeeds
   - idempotent re-run is no-op
   - local scored read tests pass against the copy

No live write happens in Task 9.

## Task 10 — Live Apply

Prerequisites:

- Task 9 dry-run apply passed.
- Scheduler/manual ingest paused.
- Reviewed fingerprint approved explicitly.
- At least 2x DB size free for backup.

Apply:

```bash
python scripts/migration/news_scores_cutover.py apply \
  --market-db /mnt/md0/PycharmProjects/ArkScope/data/market_data.db \
  --pg-dsn "$DATABASE_URL" \
  --expected-fingerprint <reviewed-fingerprint> \
  --backup /mnt/md0/PycharmProjects/ArkScope/data/market_data.db.bak-pre-news-scores-sg-<UTC>.db \
  --confirm-scheduler-paused
```

Post-apply validation:

- `PRAGMA quick_check` returns `ok`.
- `news_article_scores` count matches reviewed plan.
- Score validation invariants are zero.
- `query_news(scored_only=True)` returns local scored rows with PG poisoned.
- `query_news_search(scored_only=True)` returns local scored rows with PG poisoned.
- `query_news_stats()` has non-zero `scored_count` for known scored tickers.
- Local score import dry-run still works.
- `migrate_to_supabase.py --scores` is not run by any scheduler/runtime path.

Backup is retained through N8b/N9.

## Task 11 — Documentation and Status

Files:

- `PROJECT_PRIORITY_MAP.md`
- `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- `docs/design/DESKTOP_APP_CARRYOVER_ANALYSIS.md`
- `docs/superpowers/specs/2026-06-28-news-article-normalization-design.md`

Update docs only after live apply succeeds:

- Mark S-G done.
- Record live fingerprint and counts.
- State that local scores are the runtime authority.
- State that PG `news_scores` remains archive/drop candidate for N9 only.
- Record any skipped/unmapped score rows with reason counts.

## Review Gates

Before implementation:

- This plan must be reviewed.

Before live apply:

- Preview fingerprint and counts must be independently reproduced.
- Dry-run apply on a DB copy must pass.
- User must explicitly approve the live write.

Before completion claim:

Run:

```bash
pytest tests/test_news_normalized_schema.py \
       tests/test_news_normalized_scores.py \
       tests/test_news_score_migration.py \
       tests/test_news_scores_cutover_cli.py \
       tests/test_news_scores_cutover_apply.py \
       tests/test_news_score_import.py \
       tests/test_news_scores.py \
       tests/test_sqlite_backend.py \
       tests/test_news_tools.py \
       tests/test_signal_tools.py -q
```

Then run the focused app smoke with PG poisoned/unreachable for score-dependent paths.

## Explicit Non-Goals

- No new LLM scoring prompt, rubric, model choice, or cost policy.
- No score quality filtering.
- No SA evidence feed work.
- No PG table drop.
- No N8b normalized read cutover.
- No archive/offload policy.
- No changes to OpenAI API key handling.
