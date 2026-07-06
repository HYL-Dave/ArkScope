# News Identity Repair (S3.0a) Implementation Plan

> **Status: COMPLETED — historical implementation record; closeout entry in `PROJECT_PRIORITY_MAP.md` §10.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make news identity canonical across direct ingest, PG migration, ticker renames, and the existing local database without losing richer article content.

**Architecture:** `src/news_identity.py` becomes the single production owner of the SHA-256 identity and the low-level SQLite reconciliation algorithm. `market_data_admin.py` delegates only news aliases to that identity-aware reconciler; other domains keep the existing generic ticker update. `src/news_identity_repair.py` provides read-only preview and guarded live apply orchestration with fingerprint comparison, WAL-safe backup, market write lock, one transaction, and post-condition validation.

**Tech Stack:** Python 3, `sqlite3`, dataclasses, `hashlib`, pytest, SQLite FTS5 triggers and backup API.

---

## File Map

- Create `src/news_identity.py`: canonical hash, deterministic repair plan, collision merge, low-level apply and validation.
- Create `src/news_identity_repair.py`: DB-path preview/apply orchestration, lock, backup and transaction boundary.
- Create `tests/test_news_identity.py`: pure hash and SQLite reconciliation behavior.
- Create `tests/test_news_identity_repair.py`: preview/apply safety, backup, rollback and idempotency.
- Modify `src/news_providers.py`: import the shared hash helper; remove the duplicate formula and stale module documentation.
- Modify `scripts/migrate_to_supabase.py`: expose the shared helper as the existing `article_hash` compatibility name.
- Modify `src/news_direct.py`: correct stale MD5 documentation.
- Modify `src/market_data_admin.py`: news-only alias-aware canonicalization; other tables unchanged.
- Modify `src/market_data_direct.py`: make WAL-safe backup support refusal to overwrite.
- Modify `tests/test_news_providers.py`: assert both paths use the shared helper.
- Modify `tests/test_market_data_admin.py`: pin rename/hash/merge/FTS behavior and non-news compatibility.
- Modify `tests/test_market_data_direct.py`: pin no-overwrite backup behavior.
- Modify `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`: record S3.0a status and corrected S3.1 telemetry requirement.

## Task 1: Establish One Production Hash Helper

**Files:**
- Create: `src/news_identity.py`
- Modify: `src/news_providers.py`
- Modify: `scripts/migrate_to_supabase.py`
- Modify: `src/news_direct.py`
- Test: `tests/test_news_identity.py`
- Test: `tests/test_news_providers.py`

- [ ] **Step 1: Write failing shared-identity tests**

Add tests that define the public contract and require both existing callers to reference it:

```python
import hashlib

from src.news_identity import canonical_article_hash


def test_canonical_article_hash_uses_verbatim_ticker_title_and_date10():
    assert canonical_article_hash(
        "HAPN", "Title With Case ", "2026-06-27T23:59:59+0000"
    ) == hashlib.sha256(b"HAPN|Title With Case |2026-06-27").hexdigest()


def test_direct_and_migration_share_the_same_hash_function():
    import src.news_providers as providers
    from scripts import migrate_to_supabase as migration

    assert providers.canonical_article_hash is canonical_article_hash
    assert migration.article_hash is canonical_article_hash
```

Update the existing `_article_to_raw` assertion to compare against `canonical_article_hash` rather
than importing an independently implemented migration formula.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
pytest -q tests/test_news_identity.py tests/test_news_providers.py
```

Expected: FAIL because `src.news_identity` does not exist and the two callers do not share one
function object.

- [ ] **Step 3: Implement the minimal shared helper**

Create `src/news_identity.py`:

```python
from __future__ import annotations

import hashlib


def canonical_article_hash(ticker: str, title: str, published_at: str) -> str:
    date10 = (published_at or "")[:10]
    raw = f"{ticker}|{title}|{date10}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

In `src/news_providers.py`, import this function and remove `_canonical_article_hash` plus its local
`hashlib` import. In `_article_to_raw`, call `canonical_article_hash(article.ticker,
article.title, article.published_at)`.

In `scripts/migrate_to_supabase.py`, remove its private implementation and preserve compatibility:

```python
from src.news_identity import canonical_article_hash

article_hash = canonical_article_hash
```

Correct the module-level documentation in `src/news_providers.py` and `src/news_direct.py` to say
canonical SHA-256 rather than collector MD5/`dedup_hash`.

- [ ] **Step 4: Verify GREEN and regressions**

Run:

```bash
pytest -q tests/test_news_identity.py tests/test_news_providers.py tests/test_news_direct.py
```

Expected: PASS; existing direct/mirror coexistence test remains green.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/news_identity.py src/news_providers.py src/news_direct.py \
  scripts/migrate_to_supabase.py tests/test_news_identity.py tests/test_news_providers.py
git commit -m "refactor(news): centralize canonical article identity"
```

## Task 2: Build the Deterministic SQLite Repair Engine

**Files:**
- Modify: `src/news_identity.py`
- Test: `tests/test_news_identity.py`

- [ ] **Step 1: Write failing planner tests**

Use an in-memory SQLite fixture with the production `news` columns. Add these exact cases:

- `test_plan_classifies_unowned_stale_hash_as_update`: insert id 1 with ticker `HAPN`, title `T`,
  date `2026-06-01`, and the hash calculated for ticker `LC`; assert one update for id 1, target
  ticker `HAPN`, and no collision.
- `test_plan_classifies_stale_hash_with_canonical_owner_as_collision`: add id 2 with the same
  HAPN/title/date and canonical HAPN hash; assert id 1 is the only collision and targets id 2.
- `test_plan_groups_two_stale_rows_with_same_target_deterministically`: insert ids 7 and 3 with the
  same HAPN/title/date but two distinct arbitrary stale hashes and no canonical owner; assert id 3
  is the update owner and id 7 is a collision targeting id 3.
- `test_plan_fingerprint_changes_when_merge_content_changes`: plan a collision, update only the
  stale row description, re-plan, and assert the fingerprints differ while counts stay equal.

The planner must read all current hashes to find owners even when `only_ids` limits which rows may
be changed. Otherwise a canonical owner outside `only_ids` would be missed by runtime alias repair.

- [ ] **Step 2: Run planner tests and verify RED**

Run:

```bash
pytest -q tests/test_news_identity.py -k plan
```

Expected: FAIL because repair dataclasses and planner do not exist.

- [ ] **Step 3: Implement immutable repair-plan types and classifier**

Add these public shapes to `src/news_identity.py`:

```python
from dataclasses import dataclass
from typing import Mapping


MERGE_FIELDS = (
    "description", "url", "publisher",
    "sentiment_score", "sentiment_source", "sentiment_scale",
)


@dataclass(frozen=True)
class NewsIdentityUpdate:
    row_id: int
    old_hash: str | None
    target_hash: str
    target_ticker: str


@dataclass(frozen=True)
class NewsIdentityCollision:
    stale_id: int
    target_id: int
    old_hash: str | None
    target_hash: str


@dataclass(frozen=True)
class NewsIdentityPlan:
    fingerprint: str
    scanned: int
    updates: tuple[NewsIdentityUpdate, ...]
    collisions: tuple[NewsIdentityCollision, ...]
```

Implement `plan_news_identity_repair(conn, *, ticker_overrides=None, only_ids=None) ->
NewsIdentityPlan`. `only_ids` restricts change candidates but must not restrict the owner index: the
function first reads every news row, builds canonical/stored-hash ownership from all rows, then
classifies only selected candidates.

Classifier requirements:

- Read `id,ticker,title,published_at,article_hash` plus existing merge columns discovered through
  `PRAGMA table_info(news)`.
- Compute each desired hash from the override ticker or current ticker.
- Prefer an already-canonical owner (`stored_hash == desired_hash`).
- Otherwise choose the lowest row ID in each desired-hash group as one update owner.
- Classify remaining members as collisions targeting that owner.
- Fingerprint sorted identity rows and merge-field values using SHA-256 so preview/apply detects
  relevant content changes, not only count changes.

- [ ] **Step 4: Write failing apply/merge tests**

Add these exact tests:

- `test_apply_updates_hash_without_deleting_noncollision`: apply the id-1 LC-hash fixture and assert
  row count remains one, id remains 1, and stored hash equals the HAPN hash.
- `test_apply_keeps_canonical_id_and_fills_missing_description`: stale id 1 has description `rich`;
  canonical id 2 has an empty description. Assert only id 2 remains and has `rich`.
- `test_apply_never_overwrites_nonempty_canonical_fields`: stale/canonical descriptions are
  `stale`/`canonical`; assert `canonical` survives.
- `test_apply_merges_missing_sentiment_fields`: canonical sentiment fields are null and stale fields
  are `(4.0, 'local', '1-5')`; assert all three values transfer to the retained row.
- `test_apply_preserves_canonical_source_and_published_at`: stale and canonical source/time differ;
  assert retained source/time remain byte-identical to the canonical row.
- `test_apply_is_zero_change_on_second_plan`: after apply, re-plan and assert empty update/collision
  tuples.

- [ ] **Step 5: Run apply tests and verify RED**

Run:

```bash
pytest -q tests/test_news_identity.py -k "apply or second_plan"
```

Expected: FAIL because the apply function does not exist.

- [ ] **Step 6: Implement minimal low-level apply and validator**

Implement `apply_news_identity_plan(conn, plan) -> dict[str, int]` and
`validate_news_identity(conn) -> dict[str, int]` as transaction-neutral functions: neither commits,
rolls back, opens another connection, or writes FTS directly.

Apply updates before collisions so a deterministic owner selected from a stale group owns the
target hash before other rows merge into it. For each collision, fill only target values satisfying
`value is None` or `isinstance(value, str) and not value.strip()`. Never merge `source`, `ticker`,
`title`, or `published_at`. Require every `UPDATE`/`DELETE` to affect exactly one expected row;
otherwise raise and let the caller rollback.

Validator must report and require zero for:

- hash mismatch or null hash;
- duplicate stored hash groups;
- duplicate `(source,ticker,title,published_at)` groups;
- FTS missing rowids and orphan rowids.

It must also report equal `news_rows` and `fts_rows`.

- [ ] **Step 7: Verify Task 2 GREEN**

Run:

```bash
pytest -q tests/test_news_identity.py
```

Expected: PASS, including the same-batch target collision case rather than relying only on UNIQUE
rollback.

- [ ] **Step 8: Commit Task 2**

```bash
git add src/news_identity.py tests/test_news_identity.py
git commit -m "feat(news): add deterministic identity reconciliation"
```

## Task 3: Make Future News Ticker Renames Identity-Aware

**Files:**
- Modify: `src/market_data_admin.py`
- Modify: `tests/test_market_data_admin.py`

- [ ] **Step 1: Write failing alias regression tests**

Add three news tests using `_NEWS_SCHEMA`, `_ensure_news_hash_unique`,
`_ensure_news_fts_triggers`, and a seeded `LC -> HAPN` alias:

- Alias-only: one row still has ticker `LC` and LC hash. After canonicalization assert the same ID
  has ticker `HAPN` and HAPN hash.
- Collision/merge: stale id 1 is LC-hashed with description `rich`; canonical id 2 is HAPN-hashed
  with an empty description. Assert only id 2 survives with description `rich`.
- FTS: in the collision fixture, assert `MATCH 'rich'` returns retained id 2, stale id 1 is absent,
  and FTS/news row counts match.

Keep the existing price collision test and assert it still passes unchanged; do not create a new
price implementation path.

- [ ] **Step 2: Run alias tests and verify RED**

Run:

```bash
pytest -q tests/test_market_data_admin.py -k "canonicalize_news or canonicalize_prices"
```

Expected: new news tests FAIL because the generic path changes ticker only; the existing prices
test remains PASS.

- [ ] **Step 3: Implement the news-only specialized branch**

Add `_canonicalize_news_tickers(conn, aliases)` to `market_data_admin.py`:

```python
def _canonicalize_news_tickers(conn, aliases) -> int:
    overrides = {}
    spellings = set()
    for alias, canonical in aliases:
        if alias == canonical:
            continue
        ids = conn.execute("SELECT id FROM news WHERE ticker = ?", (alias,)).fetchall()
        if ids:
            spellings.add(alias)
            overrides.update({int(row[0]): canonical for row in ids})
    if overrides:
        plan = plan_news_identity_repair(
            conn, ticker_overrides=overrides, only_ids=set(overrides)
        )
        apply_news_identity_plan(conn, plan)
    return len(spellings)
```

In `_canonicalize_table_tickers`, dispatch `table == "news"` to this handler and retain the exact
existing generic SQL for prices, IV, and fundamentals. Keep the existing commit/return contract.

- [ ] **Step 4: Verify GREEN and mirror/bootstrap regressions**

Run:

```bash
pytest -q tests/test_market_data_admin.py tests/test_news_direct.py
```

Expected: PASS; bootstrap, incremental mirror, alias tests, FTS tests and direct writer remain green.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/market_data_admin.py tests/test_market_data_admin.py
git commit -m "fix(news): preserve identity across ticker aliases"
```

## Task 4: Add Guarded Preview and Atomic Live Apply

**Files:**
- Create: `src/news_identity_repair.py`
- Modify: `src/market_data_direct.py`
- Create: `tests/test_news_identity_repair.py`
- Modify: `tests/test_market_data_direct.py`

- [ ] **Step 1: Write failing preview safety tests**

Add these preview tests:

- Existing DB: snapshot the file size, mtime, schema SQL and rows before preview; assert all remain
  identical afterward.
- Missing DB: preview returns `exists=False` and the path is still absent.
- Stable result: two previews without intervening writes return identical fingerprints and counts;
  the LC-hash/HAPN fixture reports one update and zero collisions.

- [ ] **Step 2: Run preview tests and verify RED**

Run:

```bash
pytest -q tests/test_news_identity_repair.py -k preview
```

Expected: FAIL because `preview_news_identity_repair` does not exist.

- [ ] **Step 3: Implement read-only preview**

Create `src/news_identity_repair.py` with:

```python
def preview_news_identity_repair(db_path: str | None = None) -> dict[str, object]:
    path = Path(db_path or resolve_market_db_path())
    if not path.exists():
        return {"exists": False, "path": str(path), "updates": 0, "collisions": 0}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        plan = plan_news_identity_repair(conn)
        return {
            "exists": True,
            "path": str(path),
            "fingerprint": plan.fingerprint,
            "scanned": plan.scanned,
            "updates": len(plan.updates),
            "collisions": len(plan.collisions),
        }
    finally:
        conn.close()
```

- [ ] **Step 4: Write failing backup/apply tests**

Add these apply tests with explicit assertions:

- Existing backup destination raises `FileExistsError` and its bytes are unchanged.
- Wrong reviewed fingerprint raises before backup creation and before any DB mutation.
- Successful apply returns a backup path whose read-only contents equal the pre-apply fixture.
- Monkeypatched post-validator failure after low-level writes raises and leaves every source row and
  hash equal to the pre-apply snapshot.
- Successful collision apply returns one deletion, preserves richer text, and leaves news/FTS
  counts and rowids equal.
- A second apply using the second preview fingerprint reports zero changes and `backup_path=None`;
  the backup directory gains no file.

- [ ] **Step 5: Run apply tests and verify RED**

Run:

```bash
pytest -q tests/test_news_identity_repair.py tests/test_market_data_direct.py -k "backup or apply"
```

Expected: FAIL on overwrite refusal and missing apply orchestration.

- [ ] **Step 6: Add no-overwrite support to WAL-safe backup**

Change the existing helper compatibly:

```python
def backup_market_db(src_path: str, dest_path: str, *, overwrite: bool = True) -> str | None:
    if not Path(src_path).exists():
        return None
    dest = Path(dest_path)
    if dest.exists() and not overwrite:
        raise FileExistsError(dest)
    if overwrite:
        dest.unlink(missing_ok=True)
    src = sqlite3.connect(src_path, timeout=10.0)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return str(dest)
```

Existing callers retain `overwrite=True`; S3.0a passes `overwrite=False`.

- [ ] **Step 7: Implement guarded apply**

Implement `apply_news_identity_repair(*, expected_fingerprint, db_path=None,
backup_path=None) -> dict[str, object]` with the exact order below.

Required order:

1. Resolve the real path and reject a missing DB.
2. Acquire `market_write_lock()`.
3. Open SQLite, compute the locked plan, and compare its fingerprint to the reviewed fingerprint.
4. Return a zero-change result without a backup when there are no updates/collisions.
5. Generate a microsecond UTC backup name if none was supplied; refuse an existing path.
6. Call `backup_market_db(str(path), str(destination), overwrite=False)` while holding the lock.
7. Execute `BEGIN IMMEDIATE`.
8. Re-plan and require the same fingerprint.
9. Apply the plan and run `validate_news_identity` before commit.
10. Commit only on success; on any exception call `rollback()` and re-raise.
11. Reopen read-only after commit and require a zero-change plan plus clean validator output.

Do not create schema, rebuild FTS, or manually write `news_fts`.

- [ ] **Step 8: Verify Task 4 GREEN**

Run:

```bash
pytest -q tests/test_news_identity_repair.py tests/test_market_data_direct.py
```

Expected: PASS, including rollback and no-clobber behavior.

- [ ] **Step 9: Commit Task 4**

```bash
git add src/news_identity_repair.py src/market_data_direct.py \
  tests/test_news_identity_repair.py tests/test_market_data_direct.py
git commit -m "feat(news): add guarded identity repair"
```

## Task 5: Documentation and Full Code Verification Gate

**Files:**
- Modify: `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`

- [ ] **Step 1: Update the plan status and S3.1 contract**

Record:

- S3.0 hash unification code and smoke cleanup are complete.
- S3.0a is code-complete only after Tasks 1-4 pass; live-complete only after Task 6.
- S3.1 combines run-level `provider_sync_runs` with current per-ticker errors from
  `provider_sync_meta`; it must not infer health solely from failed aggregate runs.
- S3.2 default-on remains blocked until S3.0a live validation and S3.1 are complete.

- [ ] **Step 2: Run focused and broad regression suites**

Run:

```bash
pytest -q \
  tests/test_news_identity.py \
  tests/test_news_identity_repair.py \
  tests/test_news_providers.py \
  tests/test_news_direct.py \
  tests/test_market_data_admin.py \
  tests/test_market_data_direct.py \
  tests/test_data_scheduler.py
python -m compileall -q src/news_identity.py src/news_identity_repair.py \
  src/news_providers.py src/news_direct.py src/market_data_admin.py
git diff --check
```

Expected: all tests pass, compilation succeeds, and diff check emits no output.

- [ ] **Step 3: Review the code-only diff before any live write**

Confirm:

- no change to `config/tickers_core.json` or `trained_models/` is staged;
- no PG write or provider fetch was introduced;
- no fuzzy dedup logic exists;
- no live DB path is opened during tests;
- non-news canonicalization remains byte-for-byte equivalent apart from dispatch structure.

- [ ] **Step 4: Commit Task 5**

```bash
git add docs/design/NEWS_DIRECT_LOCAL_PLAN.md
git commit -m "docs(news): gate Step 3 on identity repair"
```

## Task 6: Gated Live Preview, Apply, and Verification

**Files:**
- Live state only: `data/market_data.db` and a timestamped gitignored backup.

- [ ] **Step 1: Run the read-only live preview**

Invoke `preview_news_identity_repair()` against the resolved production DB and report only path,
fingerprint, scanned rows, updates and collisions. Do not print article titles or content.

Expected from the audited snapshot: `updates=1047`, `collisions=101`; current data is authoritative.

- [ ] **Step 2: Stop at the live-write gate**

Present the preview fingerprint, counts, free disk space and proposed unique backup path. Obtain the
user's explicit approval before continuing.

- [ ] **Step 3: Apply with the reviewed fingerprint**

Call `apply_news_identity_repair(expected_fingerprint=reviewed_fingerprint)`. The function itself
acquires the market write lock, creates the WAL-safe backup, starts the transaction, validates and
commits.

Expected from the audited snapshot: 1,047 updates, 101 merged/deleted collisions, no provider or PG
traffic.

- [ ] **Step 4: Verify live invariants independently**

Open the DB read-only and confirm:

- expected-hash mismatch/null count = 0;
- exact hash duplicate groups = 0;
- exact `(source,ticker,title,published_at)` duplicate groups = 0;
- `news == news_fts`;
- FTS missing/orphan rowids = 0/0;
- HAPN and BRK B stale-hash counts = 0;
- the 93 formerly missing canonical descriptions are populated;
- preview now reports updates=0 and collisions=0;
- the backup exists and can be opened read-only.

- [ ] **Step 5: Record live completion without committing DB state**

Update `NEWS_DIRECT_LOCAL_PLAN.md` with the actual counts, backup name, timestamp and verification
result. Commit documentation only:

```bash
git add docs/design/NEWS_DIRECT_LOCAL_PLAN.md
git commit -m "docs(news): record S3.0a live identity repair"
```

Do not delete the backup until normal application reads and one subsequent news ingestion have been
verified.
