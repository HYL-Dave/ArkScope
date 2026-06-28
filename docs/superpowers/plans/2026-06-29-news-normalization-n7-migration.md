# News Normalization N7 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a zero-blocker, evidence-reviewed normalized-news migration plan and a backup-first atomic apply path without changing runtime routing.

**Architecture:** Keep `migration.py` responsible for bounded input scanning, add pure resolution rules in `migration_policy.py`, and isolate writes in `migration_apply.py`. Shared identity/store code enforces source-wide Polygon URL demotion and bounded IBKR-unavailable behavior so N8 inherits the same contracts rather than reimplementing them.

**Tech Stack:** Python 3, SQLite/FTS5, PyArrow Parquet, dataclasses, pytest, existing `market_write_lock` and WAL-safe `backup_market_db`.

---

## File Map

- Modify `src/news_normalized/identity.py`: source-aware identity-key policy; Polygon URLs never become strong keys.
- Modify `src/news_normalized/models.py`: `UNAVAILABLE`, structured error/retry fields, and evidence locator types.
- Modify `src/news_normalized/schema.py`: unavailable fields, cold variants, migration runs, and legacy mapping.
- Modify `src/news_normalized/store.py`: provider-ID aliases, unavailable transitions, retry eligibility, and active/cold body handling.
- Modify `src/news_normalized/writer.py`: honor unavailable and `next_retry_at`; preserve structured error codes.
- Create `src/news_normalized/body_policy.py`: pure body preparation and deterministic active-body ranking.
- Create `src/news_normalized/migration_policy.py`: pure timestamp, URL, weak-rejection, and body-variant resolution.
- Modify `src/news_normalized/migration.py`: row-addressable evidence, resolved preview, rejection evidence, and fingerprints.
- Create `src/news_normalized/migration_apply.py`: transaction-local resolved-plan writer and validators.
- Modify `scripts/migration/preview_news_normalization.py`: print resolved/rejection evidence fields.
- Create `scripts/migration/apply_news_normalization.py`: fingerprint-gated lock/backup/apply orchestration.
- Modify focused tests under `tests/test_news_normalized_*.py` and `tests/test_news_normalization_migration.py`.
- Create `tests/test_news_normalization_apply.py`.
- Modify `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`: record resolved preview and N8 carry-forwards after verification.

### Task 1: Enforce Source-wide Polygon URL Demotion and Provider-ID Aliases

**Files:**
- Modify: `src/news_normalized/identity.py`
- Modify: `src/news_normalized/store.py`
- Test: `tests/test_news_normalized_identity.py`
- Test: `tests/test_news_normalized_store.py`
- Test: `tests/test_news_normalized_provider_adapters.py`

- [ ] **Step 1: Write failing source-policy tests**

```python
def test_polygon_url_is_metadata_not_an_identity_key():
    keys = build_identity_keys(
        source="polygon",
        provider_article_id="poly-1",
        url="https://example.com/reused",
        publisher="Wire",
        title="Title",
        published_at="2026-06-29T10:00:00Z",
    )
    assert [key.kind for key in keys] == [KeyKind.PROVIDER_ID, KeyKind.FALLBACK]


def test_finnhub_url_remains_a_strong_identity_key():
    keys = build_identity_keys(
        source="finnhub",
        provider_article_id="fin-1",
        url="https://example.com/stable",
        publisher="Wire",
        title="Title",
        published_at="2026-06-29T10:00:00Z",
    )
    url_key = next(key for key in keys if key.kind is KeyKind.URL)
    assert url_key.strong is True
```

Add a real adapter assertion that a Polygon candidate with a URL also retains a non-empty
`provider_article_id`; URL demotion is safe only because direct Polygon identity is provider-first.

- [ ] **Step 2: Run the identity tests and verify RED**

Run: `pytest -q tests/test_news_normalized_identity.py tests/test_news_normalized_provider_adapters.py -k "polygon_url or finnhub_url"`

Expected: Polygon still emits `KeyKind.URL`.

- [ ] **Step 3: Implement one shared source policy**

```python
_SOURCES_WITH_NON_IDENTITY_URLS = frozenset({"polygon"})


def url_is_strong_identity(source: str) -> bool:
    return _canonical_source(source) not in _SOURCES_WITH_NON_IDENTITY_URLS


# Inside build_identity_keys:
stable_url = normalize_stable_url(url)
if stable_url and url_is_strong_identity(canonical_source):
    keys.append(ArticleKey(canonical_source, KeyKind.URL, stable_url, True))
```

No audited URL or provider ID may appear in production constants.

- [ ] **Step 4: Write failing provider-alias store tests**

```python
def test_attached_provider_alias_resolves_same_article(conn):
    store = NormalizedNewsStore(conn)
    first = store.upsert(candidate(source="polygon", provider_id="id-a"))
    conn.execute(
        "INSERT INTO news_article_keys(article_id,source,key_kind,key_value,created_at) "
        "VALUES (?,?,?,?,?)",
        (first.article_id, "polygon", "provider_id", "id-b", NOW),
    )
    alias = store.candidate_by_provider_id("polygon", "id-b")
    result = store.upsert(candidate(source="polygon", provider_id="id-b"))
    assert alias is not None
    assert result.article_id == first.article_id
    assert result.quarantined is False
```

- [ ] **Step 5: Run the alias test and verify RED**

Run: `pytest -q tests/test_news_normalized_store.py -k "provider_alias"`

Expected: alias lookup returns `None` or upsert quarantines against the canonical display ID.

- [ ] **Step 6: Resolve provider IDs through the key table**

Add `_article_owns_provider_id(article_id, source, provider_id)` and change both `_resolve` and
`candidate_by_provider_id` to join `news_article_keys` for `key_kind='provider_id'`. Keep
`news_articles.provider_article_id` as the canonical display ID only.

```python
def _article_owns_provider_id(self, article_id, source, provider_id):
    return self.conn.execute(
        "SELECT 1 FROM news_article_keys WHERE article_id=? AND source=? "
        "AND key_kind='provider_id' AND key_value=?",
        (article_id, source.strip().casefold(), provider_id.strip()),
    ).fetchone() is not None
```

- [ ] **Step 7: Run Task 1 tests and commit**

Run: `pytest -q tests/test_news_normalized_identity.py tests/test_news_normalized_store.py tests/test_news_normalized_provider_adapters.py`

Expected: all pass.

```bash
git add src/news_normalized/identity.py src/news_normalized/store.py \
  tests/test_news_normalized_identity.py tests/test_news_normalized_store.py \
  tests/test_news_normalized_provider_adapters.py
git commit -m "fix: enforce normalized news identity policy"
```

### Task 2: Freeze the N7 Schema and Structured Body Model

**Files:**
- Modify: `src/news_normalized/models.py`
- Modify: `src/news_normalized/schema.py`
- Test: `tests/test_news_normalized_schema.py`
- Test: `tests/test_news_normalized_store.py`

- [ ] **Step 1: Write failing model/schema tests**

```python
def test_body_model_exposes_unavailable_and_structured_retry_fields():
    body = BodyCandidate(
        status=BodyStatus.UNAVAILABLE,
        error_code=10172,
        fetch_attempts=3,
        next_retry_at=None,
    )
    assert body.status.value == "unavailable"
    assert body.error_code == 10172


def test_schema_has_variants_and_migration_accountability(conn):
    ensure_news_normalized_schema(conn)
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {
        "news_article_body_variants",
        "news_normalization_runs",
        "news_legacy_migration_map",
    } <= names
    body_cols = {row[1] for row in conn.execute("PRAGMA table_info(news_article_bodies)")}
    assert {"last_error_code", "unavailable_at"} <= body_cols


def test_migration_schema_helper_opens_one_rollbackable_transaction(conn):
    begin_news_normalized_schema_transaction(conn)
    assert conn.in_transaction is True
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 1
    conn.rollback()
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0
```

Also assert `news_legacy_migration_map` has no foreign key to legacy `news` and does have foreign
keys to normalized article/run rows where applicable.

- [ ] **Step 2: Run schema tests and verify RED**

Run: `pytest -q tests/test_news_normalized_schema.py tests/test_news_normalized_store.py -k "unavailable or variants or migration_accountability"`

Expected: enum member and tables/columns are absent.

- [ ] **Step 3: Add the model fields**

```python
class BodyStatus(str, Enum):
    PENDING = "pending"
    FETCHED = "fetched"
    EMPTY = "empty"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"


@dataclass(frozen=True)
class BodyCandidate:
    # existing fields remain
    error_code: Optional[int] = None
    fetch_attempts: int = 0
    next_retry_at: Optional[str] = None
```

- [ ] **Step 4: Add exact additive tables and constraints**

Implement the approved variant schema and:

```sql
CREATE TABLE IF NOT EXISTS news_normalization_runs (
    id                              INTEGER PRIMARY KEY,
    policy_version                  TEXT NOT NULL,
    input_fingerprint               TEXT NOT NULL,
    resolved_fingerprint            TEXT NOT NULL UNIQUE,
    rejection_evidence_fingerprint  TEXT NOT NULL,
    counts_json                     TEXT NOT NULL,
    backup_path                     TEXT NOT NULL,
    applied_at                      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_legacy_migration_map (
    legacy_news_id       INTEGER PRIMARY KEY,
    article_id           INTEGER REFERENCES news_articles(id) ON DELETE RESTRICT,
    resolution_kind      TEXT NOT NULL,
    rejection_reason     TEXT,
    migration_run_id     INTEGER NOT NULL
                         REFERENCES news_normalization_runs(id) ON DELETE RESTRICT,
    migration_fingerprint TEXT NOT NULL,
    CHECK (article_id IS NOT NULL OR rejection_reason IS NOT NULL)
);
```

Add `unavailable` to the body-status check and add `last_error_code` and `unavailable_at`.

Keep `ensure_news_normalized_schema` for ordinary runtime initialization. Add a migration-only
helper because Python `sqlite3.Connection.executescript()` implicitly commits any pending
transaction:

```python
def begin_news_normalized_schema_transaction(conn) -> None:
    if conn.in_transaction:
        raise RuntimeError("migration schema transaction must start from autocommit")
    conn.executescript("BEGIN IMMEDIATE;\n" + ARTICLE_SCHEMA + SEARCH_SCHEMA)
    if not conn.in_transaction:
        raise RuntimeError("migration schema transaction did not remain open")
```

The schema strings contain no `COMMIT`. N7 uses this helper exactly once after backup; all DDL and
rows then share the same caller-controlled transaction.

- [ ] **Step 5: Run Task 2 tests and commit**

Run: `pytest -q tests/test_news_normalized_schema.py tests/test_news_normalized_store.py`

Expected: all pass.

```bash
git add src/news_normalized/models.py src/news_normalized/schema.py \
  tests/test_news_normalized_schema.py tests/test_news_normalized_store.py
git commit -m "feat: freeze normalized news N7 schema"
```

### Task 3: Implement Body Ranking, Variants, and Bounded 10172 State

**Files:**
- Create: `src/news_normalized/body_policy.py`
- Modify: `src/news_normalized/store.py`
- Modify: `src/news_normalized/writer.py`
- Modify: `src/news_normalized/ibkr_adapter.py`
- Test: `tests/test_news_normalized_body_policy.py`
- Test: `tests/test_news_normalized_store.py`
- Test: `tests/test_news_normalized_writer.py`
- Test: `tests/test_news_normalized_ibkr_adapter.py`

- [ ] **Step 1: Write failing pure ranking tests**

```python
def test_active_body_prefers_clean_content_then_length_then_time_then_digest():
    short = evidence("a" * 64, raw="short", clean="short", fetched="2026-01-02T00:00:00Z")
    long = evidence("b" * 64, raw="long complete body", clean="long complete body", fetched=None)
    broken = evidence("c" * 64, raw="x" * 100, clean=None, fetched="2026-06-01T00:00:00Z")
    assert choose_active_body((short, long, broken)).body_sha256 == "b" * 64


def test_active_body_digest_breaks_an_exact_tie():
    left = evidence("a" * 64, raw="same", clean="same", fetched=None)
    right = evidence("b" * 64, raw="same", clean="same", fetched=None)
    assert choose_active_body((right, left)).body_sha256 == "a" * 64
```

- [ ] **Step 2: Run ranking tests and verify RED**

Run: `pytest -q tests/test_news_normalized_body_policy.py`

Expected: module does not exist.

- [ ] **Step 3: Implement a total-order body policy**

```python
@dataclass(frozen=True)
class PreparedBody:
    body_sha256: str
    raw_body: str
    raw_format: Optional[str]
    body_text: Optional[str]
    cleaner_version: Optional[str]
    fetched_at: Optional[str]
    retrieval_method: Optional[str] = None
    retrieval_source: Optional[str] = None
    source_url: Optional[str] = None
    evidence_ref: Optional[str] = None


def body_sort_key(item: PreparedBody) -> tuple:
    normalized_time = normalize_timestamp(item.fetched_at or "")
    return (
        -(1 if item.body_text else 0),
        -len(item.body_text or ""),
        -len(item.raw_body),
        _descending_timestamp_key(normalized_time),
        item.body_sha256,
    )


def choose_active_body(items):
    unique = {item.body_sha256: item for item in items}
    return sorted(unique.values(), key=body_sort_key)[0]
```

`_descending_timestamp_key` must make later valid timestamps sort first and missing/unparseable
timestamps last without using process-local time.

- [ ] **Step 4: Write failing store state/variant tests**

Tests must prove:

```python
def test_third_10172_becomes_terminal_unavailable(store, conn, monkeypatch):
    article = candidate("DJ-N$retry")
    result = store.upsert(article)
    conn.execute(
        "UPDATE news_article_bodies SET body_status='failed',fetch_attempts=2 "
        "WHERE article_id=?", (result.article_id,),
    )
    monkeypatch.setattr("src.news_normalized.store._now", lambda: "2026-06-29T00:00:00Z")
    store.update_body(
        article,
        BodyCandidate(status=BodyStatus.FAILED, error="unavailable", error_code=10172),
    )
    row = conn.execute(
        "SELECT body_status,fetch_attempts,last_error_code,next_retry_at,unavailable_at "
        "FROM news_article_bodies WHERE article_id=?", (result.article_id,),
    ).fetchone()
    assert tuple(row) == (
        "unavailable", 3, 10172, None, "2026-06-29T00:00:00Z"
    )


def test_10172_before_third_attempt_sets_six_hour_retry(store, conn, monkeypatch):
    article = candidate("DJ-N$retry")
    result = store.upsert(article)
    monkeypatch.setattr("src.news_normalized.store._now", lambda: "2026-06-29T00:00:00Z")
    store.update_body(
        article,
        BodyCandidate(status=BodyStatus.FAILED, error="unavailable", error_code=10172),
    )
    row = conn.execute(
        "SELECT body_status,fetch_attempts,next_retry_at FROM news_article_bodies "
        "WHERE article_id=?", (result.article_id,),
    ).fetchone()
    assert tuple(row) == ("failed", 1, "2026-06-29T06:00:00Z")


def test_new_body_variant_indexes_only_selected_active(store, conn):
    article = candidate(
        "DJ-N$variant", body_status=BodyStatus.FETCHED, raw_body="short"
    )
    result = store.upsert(article)
    store.update_body(
        article,
        BodyCandidate(
            status=BodyStatus.FETCHED,
            raw_body="long complete provider body",
            raw_format="text",
            fetched_at="2026-06-29T01:00:00Z",
        ),
    )
    active = conn.execute(
        "SELECT raw_body FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    cold = conn.execute(
        "SELECT raw_body FROM news_article_body_variants WHERE article_id=?",
        (result.article_id,),
    ).fetchall()
    search = conn.execute(
        "SELECT body_text FROM news_search_documents WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    assert active == "long complete provider body"
    assert [row[0] for row in cold] == ["short"]
    assert search == "long complete provider body"
```

Add a writer test with a fake provider and a body row whose `next_retry_at` is one hour in the
future; assert `body_calls == []` and the provider ID remains in continuation. Add an explicit
re-probe test that first asserts normal `UNAVAILABLE -> FETCHED` raises `BodyConflictError`, then
calls `update_body(candidate, fetched_body, allow_terminal_recovery=True)` and asserts fetched
active content.

- [ ] **Step 5: Run state tests and verify RED**

Run: `pytest -q tests/test_news_normalized_store.py tests/test_news_normalized_writer.py tests/test_news_normalized_ibkr_adapter.py -k "10172 or unavailable or variant or next_retry"`

Expected: unavailable, structured code, variant storage, or retry eligibility assertions fail.

- [ ] **Step 6: Implement the state transitions and variant swap**

Set `BodyCandidate(error_code=10172)` in `IBKRNormalizedProvider`. Add `UNAVAILABLE` to writer
terminal states. Before body fetch, skip failed rows whose parsed `next_retry_at` is in the future.

In store failure handling:

```python
if incoming is BodyStatus.FAILED and body.error_code == 10172:
    if attempts >= 3:
        status = BodyStatus.UNAVAILABLE.value
        next_retry_at = None
        unavailable_at = attempted_at
    else:
        status = BodyStatus.FAILED.value
        next_retry_at = iso_add_hours(attempted_at, 6)
        unavailable_at = None
```

Permit `UNAVAILABLE -> FETCHED` only when `update_body(candidate, body,
allow_terminal_recovery=True)` is
explicit. For differing fetched digests, prepare both bodies, keep the winner active, insert the
loser into `news_article_body_variants`, delete any cold duplicate of the winner, and refresh FTS
only from active body text.

- [ ] **Step 7: Run Task 3 tests and commit**

Run: `pytest -q tests/test_news_normalized_body_policy.py tests/test_news_normalized_store.py tests/test_news_normalized_writer.py tests/test_news_normalized_ibkr_adapter.py`

Expected: all pass.

```bash
git add src/news_normalized/body_policy.py src/news_normalized/store.py \
  src/news_normalized/writer.py src/news_normalized/ibkr_adapter.py \
  tests/test_news_normalized_body_policy.py tests/test_news_normalized_store.py \
  tests/test_news_normalized_writer.py tests/test_news_normalized_ibkr_adapter.py
git commit -m "feat: add normalized news body policy"
```

### Task 4: Build Pure Conflict Resolution Without Audited-ID Allowlists

**Files:**
- Create: `src/news_normalized/migration_policy.py`
- Modify: `src/news_normalized/migration.py`
- Test: `tests/test_news_normalization_migration.py`

- [ ] **Step 1: Write synthetic failing policy tests**

Use IDs and URLs that do not occur in live audit data:

```python
def policy_group(
    *, source="polygon", provider_ids=("id",), titles=("Same",),
    urls=("https://example.test/shared",),
    published_at=("2026-06-29T10:00:00Z",), tickers=("AAPL",),
    sentiment_values=(), bodies=(),
):
    return PolicyGroup(
        source=source,
        identity=f"synthetic:{provider_ids[0]}",
        provider_ids=tuple(provider_ids),
        normalized_titles=tuple(normalize_identity_text(item) for item in titles),
        normalized_urls=tuple(normalize_stable_url(item) for item in urls),
        publication_dates=tuple(
            normalize_timestamp(item)[:10] for item in published_at
        ),
        published_at=tuple(published_at),
        tickers=tuple(tickers),
        sentiment_values=tuple(sentiment_values),
        body_refs=bodies,
    )


def legacy_evidence(*, legacy_id, ticker, sentiment):
    return LegacyEvidence(
        legacy_news_id=legacy_id,
        canonical_ticker=ticker,
        sentiment_value=sentiment,
    )


def body_ref(*, digest, clean_length, raw_length):
    return BodyEvidenceRef(
        source_path="synthetic.parquet",
        row_group=0,
        row_index=0,
        body_sha256=digest,
        raw_length=raw_length,
        clean_length=clean_length,
        cleaner_ok=True,
        fetched_at=None,
    )


def test_same_provider_id_title_url_with_different_times_is_timestamp_drift():
    group = policy_group(
        source="finnhub",
        provider_ids=("synthetic-id",),
        titles=("Same title",),
        urls=("https://example.test/story",),
        published_at=("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z"),
    )
    resolved = resolve_timestamp_drift(group)
    assert resolved.canonical_published_at == "2026-01-01T00:00:00Z"
    assert resolved.resolution_kind == "provider_timestamp_drift"


def test_same_polygon_url_title_and_day_merges_provider_groups():
    groups = (
        policy_group(source="polygon", provider_ids=("id-a",), titles=("Same",)),
        policy_group(source="polygon", provider_ids=("id-b",), titles=("Same",)),
    )
    resolved = resolve_polygon_shared_url(groups)
    assert resolved.action == "merge"
    assert resolved.canonical_provider_id == "id-a"
    assert resolved.provider_ids == ("id-a", "id-b")
    assert all(key.kind is not KeyKind.URL for key in resolved.identity_keys)


def test_polygon_shared_url_with_different_metadata_stays_separate():
    groups = (
        policy_group(source="polygon", provider_ids=("id-a",), titles=("First",)),
        policy_group(source="polygon", provider_ids=("id-b",), titles=("Second",)),
    )
    resolved = resolve_polygon_shared_url(groups)
    assert resolved.action == "demote"
    assert len(resolved.groups) == 2
    assert all(
        key.kind is not KeyKind.URL
        for group in resolved.groups
        for key in group.identity_keys
    )


def test_weak_ambiguity_reports_unique_legacy_evidence():
    rejected = reject_weak_legacy(
        legacy_evidence(legacy_id=42, ticker="UNIQUE", sentiment=4.0),
        candidates=(
            policy_group(tickers=("AAPL",), sentiment_values=(3.0,)),
            policy_group(tickers=("MSFT",), sentiment_values=(3.0,)),
        ),
    )
    assert rejected.ticker_unique is True
    assert rejected.sentiment_present is True
    assert rejected.sentiment_unique is True


def test_body_variants_choose_one_active_and_keep_other_digests():
    bodies = (
        body_ref(digest="a" * 64, clean_length=5, raw_length=5),
        body_ref(digest="b" * 64, clean_length=20, raw_length=20),
    )
    active, cold = resolve_body_variants(bodies)
    assert active.body_sha256 == "b" * 64
    assert [item.body_sha256 for item in cold] == ["a" * 64]
```

Also add a source scan test that fails if production policy modules contain any of the 35 audited
provider IDs or 48 audited URLs.

- [ ] **Step 2: Run policy tests and verify RED**

Run: `pytest -q tests/test_news_normalization_migration.py -k "timestamp_drift or shared_url or weak_ambiguity or body_variants or no_audited_allowlist"`

Expected: no resolved policy API exists.

- [ ] **Step 3: Add immutable policy types**

```python
N7_POLICY_VERSION = "news-n7-v1"

@dataclass(frozen=True)
class BodyEvidenceRef:
    source_path: str
    row_group: int
    row_index: int
    body_sha256: str
    raw_length: int
    clean_length: int
    cleaner_ok: bool
    fetched_at: Optional[str]

@dataclass(frozen=True)
class RejectedLegacy:
    legacy_news_id: int
    reason: str
    ticker_unique: bool
    sentiment_present: bool
    sentiment_unique: bool

@dataclass(frozen=True)
class RejectionEvidenceSummary:
    rejected_rows: int
    rows_with_unique_ticker: int
    unique_ticker_relations: int
    rows_with_sentiment: int
    rows_with_unique_sentiment: int
    fingerprint: str


@dataclass(frozen=True)
class LegacyEvidence:
    legacy_news_id: int
    canonical_ticker: str
    sentiment_value: Optional[float]


@dataclass(frozen=True)
class PolicyGroup:
    source: str
    identity: str
    provider_ids: tuple[str, ...]
    normalized_titles: tuple[str, ...]
    normalized_urls: tuple[str, ...]
    publication_dates: tuple[str, ...]
    published_at: tuple[str, ...]
    tickers: tuple[str, ...]
    sentiment_values: tuple[float, ...]
    body_refs: tuple[BodyEvidenceRef, ...]


@dataclass(frozen=True)
class ResolvedArticle:
    source: str
    identity: str
    canonical_provider_id: Optional[str]
    provider_ids: tuple[str, ...]
    canonical_title: str
    publisher: Optional[str]
    url: Optional[str]
    published_at: str
    identity_keys: tuple[ArticleKey, ...]
    ticker_relations: tuple[tuple[str, str], ...]
    titles: tuple[str, ...]
    sentiment_value: Optional[float]
    active_body: Optional[BodyEvidenceRef]
    cold_bodies: tuple[BodyEvidenceRef, ...]
    body_status: BodyStatus
    fetch_attempts: int


@dataclass(frozen=True)
class LegacyResolution:
    legacy_news_id: int
    article_identity: Optional[str]
    resolution_kind: str
    rejection_reason: Optional[str]
```

Define resolved article/group records containing canonical metadata, all strong provider IDs,
eligible identity keys, relations, titles, active body ref, and cold body refs.

- [ ] **Step 4: Make Parquet evidence row-addressable**

Change `iter_parquet_news` to iterate row groups and track `row_group` plus `row_index` within that
group while retaining bounded 2,048-row batches. `BodyEvidenceRef` stores digests/lengths and a
locator, never raw body text. Apply later re-reads exactly that row and verifies its digest.

- [ ] **Step 5: Implement computed policy functions**

```python
def is_timestamp_drift(group) -> bool:
    return (
        bool(group.provider_article_id)
        and len(group.normalized_titles) == 1
        and len(group.normalized_urls) == 1
    )


def polygon_url_action(groups) -> Literal["merge", "demote"]:
    titles = {title for group in groups for title in group.normalized_titles}
    dates = {date for group in groups for date in group.publication_dates}
    return "merge" if len(titles) == 1 and len(dates) == 1 else "demote"
```

Merge canonical provider ID lexicographically, timestamp earliest, and provider-ID keys all. Never
emit Polygon URL keys. Weak ambiguity produces `RejectedLegacy` and computes unique evidence by
comparing the legacy ticker/sentiment against the union of all candidate groups.

- [ ] **Step 6: Run Task 4 tests and commit**

Run: `pytest -q tests/test_news_normalization_migration.py`

Expected: all pass and test fixtures use no audited identifiers.

```bash
git add src/news_normalized/migration_policy.py src/news_normalized/migration.py \
  tests/test_news_normalization_migration.py
git commit -m "feat: resolve normalized news migration conflicts"
```

### Task 5: Produce the Resolved Preview and Rejection Evidence Gate

**Files:**
- Modify: `src/news_normalized/migration.py`
- Modify: `scripts/migration/preview_news_normalization.py`
- Test: `tests/test_news_normalization_migration.py`

- [ ] **Step 1: Write failing resolved-preview tests**

```python
def _resolved_fixture(tmp_path):
    db = tmp_path / "market.db"
    parquet = tmp_path / "raw" / "ibkr" / "2026-06.parquet"
    _legacy_db(db)
    _parquet(parquet)
    return db, [parquet]


def test_resolved_preview_has_all_three_fingerprints(tmp_path):
    db, paths = _resolved_fixture(tmp_path)
    preview = plan_news_normalization(db, paths)
    assert len(preview.input_fingerprint) == 64
    assert preview.policy_version == N7_POLICY_VERSION
    assert len(preview.resolved_fingerprint) == 64
    assert len(preview.rejection_evidence.fingerprint) == 64


def test_rejection_summary_counts_unique_ticker_and_sentiment(tmp_path):
    db, paths = _weak_rejection_fixture(tmp_path)
    summary = plan_news_normalization(db, paths).rejection_evidence
    assert summary.rejected_rows == 2
    assert summary.rows_with_unique_ticker == 1
    assert summary.unique_ticker_relations == 1
    assert summary.rows_with_sentiment == 2
    assert summary.rows_with_unique_sentiment == 1


def test_rejection_fingerprint_changes_with_unique_evidence(tmp_path):
    db, paths = _weak_rejection_fixture(tmp_path)
    first = plan_news_normalization(db, paths).rejection_evidence.fingerprint
    conn = sqlite3.connect(db)
    conn.execute("UPDATE news SET ticker='UNIQUE2' WHERE id=?", (2,))
    conn.commit()
    conn.close()
    second = plan_news_normalization(db, paths).rejection_evidence.fingerprint
    assert second != first


def test_resolved_fingerprint_is_input_order_independent(tmp_path):
    db, paths = _resolved_fixture(tmp_path)
    first = plan_news_normalization(db, paths)
    second = plan_news_normalization(db, list(reversed(paths)))
    assert second.resolved_fingerprint == first.resolved_fingerprint


def test_preview_is_zero_mutation(tmp_path):
    db, paths = _resolved_fixture(tmp_path)
    before = _snapshot_inputs(db, paths)
    plan_news_normalization(db, paths)
    assert _snapshot_inputs(db, paths) == before
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'news_article%'"
    ).fetchone()[0]
    conn.close()
    assert count == 0
```

Define `_weak_rejection_fixture` beside the existing `_legacy_db`/`_parquet` helpers with two
provider groups sharing one fallback and exactly two ambiguous legacy rows: one row reuses a
candidate ticker/sentiment, while the second uses ticker `UNIQUE` and sentiment `4.0` absent from
both groups. Define `_snapshot_inputs` as tuples of resolved path, size, mtime_ns, and inode for DB
and Parquet files. Add a count-drift test by appending a third ambiguous legacy row and assert the
reviewed expected-count validator raises `MigrationPlanDriftError`.

- [ ] **Step 2: Run preview tests and verify RED**

Run: `pytest -q tests/test_news_normalization_migration.py -k "resolved_preview or rejection or order_independent or zero_mutation"`

Expected: preview lacks resolved/rejection fields.

- [ ] **Step 3: Extend the public preview contract**

```python
@dataclass(frozen=True)
class ResolvedMigrationPreview:
    input_fingerprint: str
    policy_version: str
    resolved_fingerprint: str
    rejection_evidence: RejectionEvidenceSummary
    counts: dict[str, int]
    remaining_blockers: tuple[PreviewConflict, ...]
    would_apply: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedMigrationPlan:
    preview: ResolvedMigrationPreview
    articles: tuple[ResolvedArticle, ...]
    legacy_resolutions: tuple[LegacyResolution, ...]


def build_resolved_plan(
    market_db: Path, parquet_paths: Sequence[Path]
) -> ResolvedMigrationPlan:
    """Build immutable apply records plus the body-redacted public preview."""
    scanned = scan_migration_inputs(market_db, parquet_paths)
    return resolve_migration_inputs(scanned, policy_version=N7_POLICY_VERSION)


def plan_news_normalization(
    market_db: Path, parquet_paths: Sequence[Path]
) -> ResolvedMigrationPreview:
    return build_resolved_plan(market_db, parquet_paths).preview
```

Fingerprint records include normalized decisions, legacy mappings/rejections, body digests, and
policy version, but never raw body. `would_apply` requires zero remaining blockers and complete
legacy accountability. The CLI prints all five rejection counts plus its fingerprint.

- [ ] **Step 4: Require explicit rejection-evidence review at apply boundary**

Preview is structurally applyable with reviewed weak-policy rules, but apply must later require
`expected_rejection_evidence_fingerprint` separately from the resolved fingerprint. This prevents
the reviewed rejection cohort from being authorized by count alone. The first real resolved
preview corrected that cohort to 940 rows: 924 IBKR plus 16 Polygon exact-metadata ambiguities
whose provider IDs and URLs remain distinct.

- [ ] **Step 5: Run Task 5 tests and commit**

Run: `pytest -q tests/test_news_normalization_migration.py tests/test_news_normalized_identity.py`

Expected: all pass.

```bash
git add src/news_normalized/migration.py scripts/migration/preview_news_normalization.py \
  tests/test_news_normalization_migration.py
git commit -m "feat: add resolved news migration preview"
```

### Task 6: Write the Transaction-local Apply Engine

**Files:**
- Create: `src/news_normalized/migration_apply.py`
- Create: `tests/test_news_normalization_apply.py`

- [ ] **Step 1: Write failing apply tests**

```python
@pytest.fixture
def temp_inputs(tmp_path):
    db, paths = build_apply_fixture(tmp_path)
    plan = build_resolved_plan(db, paths)
    return db, paths, plan


def test_apply_accounts_for_every_legacy_row(temp_inputs):
    db, paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    result = write_resolved_plan(conn, plan, "backup.db", NOW)
    validate_applied_plan(conn, plan)
    conn.commit()
    mapped = conn.execute("SELECT COUNT(*) FROM news_legacy_migration_map").fetchone()[0]
    legacy = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    assert mapped == legacy
    assert result.resolved_fingerprint == plan.preview.resolved_fingerprint
    conn.close()


def test_apply_keeps_cold_body_out_of_fts(temp_inputs):
    db, paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    write_resolved_plan(conn, plan, "backup.db", NOW)
    conn.commit()
    cold = conn.execute("SELECT raw_body FROM news_article_body_variants").fetchone()[0]
    fts = " ".join(
        row[0]
        for row in conn.execute("SELECT body_text FROM news_search_documents")
    )
    assert cold not in fts
    conn.close()


def test_apply_polygon_aliases_have_no_url_key(temp_inputs):
    db, paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    write_resolved_plan(conn, plan, "backup.db", NOW)
    conn.commit()
    provider_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='provider_id'"
    ).fetchone()[0]
    url_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='url'"
    ).fetchone()[0]
    assert provider_keys == 2
    assert url_keys == 0
    conn.close()


def test_apply_rolls_back_when_validation_raises(temp_inputs):
    db, paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError):
        write_resolved_plan(conn, plan, "backup.db", NOW)
        raise MigrationValidationError("injected")
    conn.rollback()
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0
    conn.close()


def test_body_locator_digest_mismatch_aborts(temp_inputs):
    db, paths, plan = temp_inputs
    bad = replace_first_body_digest(plan, "0" * 64)
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError, match="digest changed"):
        write_resolved_plan(conn, bad, "backup.db", NOW)
    conn.rollback()
    conn.close()
```

`build_apply_fixture` writes one mapped row, one weak-rejected row, one exact Polygon URL merge with
two provider IDs, and one two-body variant group. `replace_first_body_digest` uses
`dataclasses.replace` to alter only the first active `BodyEvidenceRef`. Add a second-call test that
commits once, calls `write_resolved_plan` again with the same plan, and asserts
`already_applied=True` with unchanged counts.

- [ ] **Step 2: Run apply tests and verify RED**

Run: `pytest -q tests/test_news_normalization_apply.py`

Expected: module does not exist.

- [ ] **Step 3: Define apply result and body reader**

```python
@dataclass(frozen=True)
class MigrationApplyResult:
    run_id: int
    resolved_fingerprint: str
    counts: dict[str, int]
    already_applied: bool = False


def read_body_evidence_batch(
    refs: Iterable[BodyEvidenceRef],
) -> dict[BodyEvidenceRef, str]:
    result = {}
    grouped = groupby_sorted(refs, key=lambda ref: (ref.source_path, ref.row_group))
    for (source_path, row_group), group in grouped:
        table = pq.ParquetFile(source_path).read_row_group(
            row_group, columns=["content", "description"]
        )
        for ref in group:
            row = table.slice(ref.row_index, 1).to_pylist()[0]
            raw = str(row.get("content") or row.get("description") or "")
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() != ref.body_sha256:
                raise MigrationValidationError("body evidence digest changed")
            result[ref] = raw
    return result
```

Sort and group every active/cold ref before any insert so each Parquet row group is read at most
once per apply. Tests instrument `ParquetFile.read_row_group` and assert two refs in one group cause
one read; this is an apply performance invariant, not an optional optimization.

- [ ] **Step 4: Implement direct SQL writes under the caller transaction**

`write_resolved_plan(conn, plan, backup_path, applied_at)` must not use nested `with conn:` blocks or
commit. Insert articles in sorted `(source, identity)` order, retain generated IDs in a local map,
then write keys, relations, titles, active/cold bodies, search projection, migration run, and one
legacy map row per input legacy ID.

If the resolved fingerprint already exists, validate its counts and return `already_applied=True`
without writes.

- [ ] **Step 5: Implement transaction-local validators**

`validate_applied_plan` checks quick-check, exact counts, map completeness, key ownership, Polygon
URL-key absence, relation uniqueness, active/cold disjointness, raw-body absence from search
projection, FTS missing/orphans, body-state invariants, and zero unresolved rows.

Tests inject a failure after article insertion and prove no normalized table or row survives the
outer rollback.

- [ ] **Step 6: Run Task 6 tests and commit**

Run: `pytest -q tests/test_news_normalization_apply.py tests/test_news_normalized_schema.py`

Expected: all pass.

```bash
git add src/news_normalized/migration_apply.py tests/test_news_normalization_apply.py
git commit -m "feat: add atomic normalized news migration writer"
```

### Task 7: Add Lock, Backup, Fingerprint, and Post-commit Orchestration

**Files:**
- Create: `scripts/migration/apply_news_normalization.py`
- Modify: `tests/test_news_normalization_apply.py`

- [ ] **Step 1: Write failing orchestration tests**

```python
@pytest.mark.parametrize(
    ("argument", "bad_value"),
    [
        ("expected_input_fingerprint", "bad-input"),
        ("expected_resolved_fingerprint", "bad-resolved"),
        ("expected_rejection_evidence_fingerprint", "bad-rejection"),
    ],
)
def test_orchestrator_refuses_each_fingerprint_before_backup(
    tmp_path, monkeypatch, resolved_plan, argument, bad_value
):
    backup_calls = []
    monkeypatch.setattr(APPLY_MODULE, "build_resolved_plan", lambda *args: resolved_plan)
    monkeypatch.setattr(
        APPLY_MODULE, "backup_market_db", lambda *args, **kwargs: backup_calls.append(args)
    )
    kwargs = approved_arguments(tmp_path, resolved_plan)
    kwargs[argument] = bad_value
    with pytest.raises(MigrationFingerprintMismatch):
        apply_news_normalization(**kwargs)
    assert backup_calls == []


def test_orchestrator_orders_lock_backup_begin_and_postcheck(
    tmp_path, monkeypatch, resolved_plan
):
    events = []
    monkeypatch.setattr(APPLY_MODULE, "market_write_lock", recording_lock(events))
    monkeypatch.setattr(
        APPLY_MODULE,
        "backup_market_db",
        lambda *args, **kwargs: events.append("backup") or str(args[1]),
    )
    monkeypatch.setattr(APPLY_MODULE, "open_apply_connection", fake_connection(events))
    monkeypatch.setattr(
        APPLY_MODULE,
        "validate_reopened_read_only",
        lambda *args: events.append("postcheck"),
    )
    monkeypatch.setattr(
        APPLY_MODULE,
        "require_idempotent_replan",
        lambda *args: events.append("idempotent"),
    )
    apply_news_normalization(**approved_arguments(tmp_path, resolved_plan))
    assert events == [
        "lock-enter", "backup", "begin", "write", "validate", "commit",
        "postcheck", "idempotent", "lock-exit",
    ]


def test_orchestrator_rolls_back_on_validation_failure(
    tmp_path, monkeypatch, resolved_plan
):
    connection, events = failing_validation_connection()
    monkeypatch.setattr(APPLY_MODULE, "open_apply_connection", lambda *args: connection)
    with pytest.raises(MigrationValidationError):
        apply_news_normalization(**approved_arguments(tmp_path, resolved_plan))
    assert events[-1] == "rollback"
    assert "commit" not in events
```

Define `approved_arguments` from the three fingerprints on `resolved_plan.preview`, with a unique
temporary backup path. `recording_lock`, `fake_connection`, and `failing_validation_connection` are test-only
doubles implementing the complete context-manager/connection methods used by the orchestrator;
they record behavior but do not replace planner or policy logic in unit tests.

- [ ] **Step 2: Run orchestration tests and verify RED**

Run: `pytest -q tests/test_news_normalization_apply.py -k "orchestrator"`

Expected: apply CLI/orchestrator does not exist.

- [ ] **Step 3: Implement the hard-gated function**

```python
def apply_news_normalization(
    market_db: Path,
    parquet_root: Path,
    *,
    expected_input_fingerprint: str,
    expected_resolved_fingerprint: str,
    expected_rejection_evidence_fingerprint: str,
    backup_path: Path,
) -> MigrationApplyResult:
    with market_write_lock(timeout=30.0):
        plan = build_resolved_plan(market_db, sorted(parquet_root.rglob("*.parquet")))
        require_expected_fingerprints(
            plan,
            expected_input_fingerprint=expected_input_fingerprint,
            expected_resolved_fingerprint=expected_resolved_fingerprint,
            expected_rejection_evidence_fingerprint=(
                expected_rejection_evidence_fingerprint
            ),
        )
        backup_market_db(str(market_db), str(backup_path), overwrite=False)
        conn = sqlite3.connect(market_db, isolation_level=None)
        try:
            begin_news_normalized_schema_transaction(conn)
            result = write_resolved_plan(conn, plan, str(backup_path), utc_now())
            validate_applied_plan(conn, plan)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        validate_reopened_read_only(market_db, plan)
        require_idempotent_replan(market_db, parquet_root, plan)
        return result
```

Fingerprint checks happen before backup. Backup happens before DDL/transaction writes. The lock is
held until reopened validation and idempotence finish.

- [ ] **Step 4: Add a CLI that cannot infer approvals**

Require explicit `--expected-input-fingerprint`, `--expected-resolved-fingerprint`,
`--expected-rejection-evidence-fingerprint`, and `--backup-path`. Do not provide `--force` or
default fingerprints. JSON output contains counts and paths, never body/title/URL content.

- [ ] **Step 5: Run Task 7 tests and commit**

Run: `pytest -q tests/test_news_normalization_apply.py`

Expected: all pass.

```bash
git add scripts/migration/apply_news_normalization.py tests/test_news_normalization_apply.py
git commit -m "feat: orchestrate normalized news migration apply"
```

### Task 8: Full Offline Verification and Real Resolved Preview Gate

**Files:**
- Modify: `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`
- Read only: `/mnt/md0/PycharmProjects/ArkScope/data/market_data.db`
- Read only: `/mnt/md0/PycharmProjects/ArkScope/data/news/raw/**/*.parquet`

- [ ] **Step 1: Run the full hermetic regression set**

Run:

```bash
pytest -q \
  tests/test_news_normalized_identity.py \
  tests/test_news_normalized_schema.py \
  tests/test_news_normalized_store.py \
  tests/test_news_normalized_body_policy.py \
  tests/test_news_normalized_provider_adapters.py \
  tests/test_news_normalized_ibkr_adapter.py \
  tests/test_news_normalized_writer.py \
  tests/test_news_normalization_migration.py \
  tests/test_news_normalization_apply.py \
  tests/test_ibkr_news.py
```

Expected: all hermetic tests pass; configured live-IBKR tests remain skipped.

- [ ] **Step 2: Compile touched modules**

Run:

```bash
python -m py_compile \
  src/news_normalized/identity.py \
  src/news_normalized/models.py \
  src/news_normalized/schema.py \
  src/news_normalized/body_policy.py \
  src/news_normalized/store.py \
  src/news_normalized/writer.py \
  src/news_normalized/migration_policy.py \
  src/news_normalized/migration.py \
  src/news_normalized/migration_apply.py \
  scripts/migration/preview_news_normalization.py \
  scripts/migration/apply_news_normalization.py
```

Expected: exit 0 and no output.

- [ ] **Step 3: Run real inputs in preview-only mode**

Before running, record size, mtime, inode, normalized-table count, and Parquet snapshots. Run:

```bash
python scripts/migration/preview_news_normalization.py \
  --market-db /mnt/md0/PycharmProjects/ArkScope/data/market_data.db \
  --parquet-root /mnt/md0/PycharmProjects/ArkScope/data/news/raw
```

Expected:

- input fingerprint remains `55aa79c33ebed92658dc8af232d12ae465d4d19c8ef3bf4556f2e0ed6c5442cc`;
- zero unreviewed blockers;
- computed policy counts match the audited classifications without hardcoded IDs;
- rejection evidence reports unique ticker/sentiment counts and a separate fingerprint;
- a new stable resolved fingerprint is emitted;
- main DB size/mtime/inode and normalized-table count remain unchanged.

- [ ] **Step 4: Repeat preview and prove determinism**

Run the identical command again. Expected: resolved and rejection fingerprints match byte-for-byte
and inputs remain unchanged.

- [ ] **Step 5: Update status documentation and commit**

Record the actual resolved/rejection fingerprints and counts in `NEWS_DIRECT_LOCAL_PLAN.md`. State:

- N7 code is review-ready;
- live apply has not run;
- apply requires independent preview reproduction and explicit approval;
- Polygon URL demotion is source-wide and must remain in N8;
- N8 runtime cutover remains blocked on N7 live validation.
- live apply must run in a quiet operator window with the scheduler paused because the write lock
  remains held through the multi-minute post-commit idempotent replan;
- the N8 plan must reconcile scorer-versus-read cutover ordering explicitly before runtime work;
  N7 records the dependency but does not decide it.

```bash
git add docs/design/NEWS_DIRECT_LOCAL_PLAN.md
git commit -m "docs: record normalized news N7 preview gate"
```

- [ ] **Step 6: Stop at the live-apply hard gate**

Report input fingerprint, resolved fingerprint, rejection-evidence fingerprint, all resolution and
unique-evidence counts, test results, and proposed backup path. Do not invoke
`apply_news_normalization.py` until the user independently reviews those values and explicitly
authorizes the live write.
