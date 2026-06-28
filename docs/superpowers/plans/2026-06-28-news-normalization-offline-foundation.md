# News Normalization Offline Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the all-source normalized news identity, schema, cleaner, read-only migration preview, common writer, and provider adapters without Gateway access or live database writes.

**Architecture:** Add a focused `src/news_normalized` package beside the existing legacy news path. N1-N5 operate only on temporary databases, read-only legacy SQLite/Parquet inputs, and fake providers; current scheduler routing and the live `news` table remain unchanged. Strong provider/URL keys are unique, fallback keys are weak candidates, raw bodies are stored once, cleaned text alone feeds FTS, and every ambiguous identity is quarantined rather than silently merged.

**Tech Stack:** Python 3.11, SQLite/FTS5, stdlib `html.parser`, PyArrow Parquet batch readers, pytest, existing `market_write_lock`, `ibkr_gateway_lock`, and provider telemetry helpers.

---

## Scope and hard gates

This plan implements only N1-N5 from
`docs/superpowers/specs/2026-06-28-news-article-normalization-design.md`.

It MUST NOT:

- connect to IBKR, Polygon, Finnhub, PG, or any external provider;
- modify `data/market_data.db` or any live Parquet file;
- route the scheduler to the normalized writer;
- apply the migration preview;
- classify the 321 missing IBKR bodies as `empty` or `expired` by guessing;
- delete the legacy `news` table, Parquet readers/writers, mirror code, or scoring scripts.

N6-N9 require separate plans after the five-article Gateway probe and reviewed N2 preview. In
particular, `score_ibkr_news.py` and `FileBackend` remain active dependencies until normalized
SQLite replacements pass.

## File map

New package:

- `src/news_normalized/models.py` — immutable candidate, key, body, budget, and result types.
- `src/news_normalized/identity.py` — deterministic normalization and strong/weak key generation.
- `src/news_normalized/schema.py` — additive normalized schema, search projection, FTS triggers.
- `src/news_normalized/cleaner.py` — deterministic raw HTML/text to plain body text.
- `src/news_normalized/store.py` — identity resolution, quarantine, article/body/title/ticker upsert.
- `src/news_normalized/migration.py` — streaming legacy/Parquet planner and fingerprint report.
- `src/news_normalized/writer.py` — bounded common writer over injectable providers.
- `src/news_normalized/provider_adapters.py` — Polygon/Finnhub candidate adapters.
- `src/news_normalized/ibkr_adapter.py` — IBKR candidate/body adapter behind the shared lock.
- `src/news_normalized/__init__.py` — public offline-foundation API only.
- `data_sources/ibkr_source.py` — additive strict body-fetch method; legacy swallowing method keeps
  its existing contract.

New scripts:

- `scripts/migration/preview_news_normalization.py` — read-only real-data preview CLI.
- `scripts/diagnostics/probe_ibkr_news_bodies.py` — N6-ready read-only probe; built/tested here but
  not executed in this plan.

Tests:

- `tests/test_news_normalized_identity.py`
- `tests/test_news_normalized_schema.py`
- `tests/test_news_body_cleaner.py`
- `tests/test_news_normalized_store.py`
- `tests/test_news_normalization_migration.py`
- `tests/test_news_normalized_writer.py`
- `tests/test_news_normalized_provider_adapters.py`
- `tests/test_news_normalized_ibkr_adapter.py`
- `tests/fixtures/news_cleaner/*.json` — synthetic/redacted structural fixtures only.

Existing production files are not routed to the new package in N1-N5. `src/news_providers.py`,
`src/news_direct.py`, `src/service/data_scheduler.py`, and live schema helpers stay behaviorally
unchanged.

---

### Task 1: Define normalized article models and identity keys (N1)

**Files:**
- Create: `src/news_normalized/__init__.py`
- Create: `src/news_normalized/models.py`
- Create: `src/news_normalized/identity.py`
- Create: `tests/test_news_normalized_identity.py`

- [ ] **Step 1: Write failing identity tests**

```python
# tests/test_news_normalized_identity.py
from src.news_normalized.identity import build_identity_keys, fallback_identity_hash
from src.news_normalized.models import KeyKind


def test_fallback_excludes_ticker_and_normalizes_text():
    a = fallback_identity_hash(
        source="ibkr", publisher="DJ-N", title="AT&amp;T   Rises",
        published_at="2026-06-27T10:11:12+0000",
    )
    b = fallback_identity_hash(
        source="ibkr", publisher="dj-n", title="at&t rises",
        published_at="2026-06-27T10:11:12Z",
    )
    assert a == b
    assert len(a) == 64


def test_provider_and_url_are_strong_but_fallback_is_weak():
    keys = build_identity_keys(
        source="polygon", provider_article_id="abc-123",
        url="https://example.test/story/?utm_source=x",
        publisher="Reuters", title="Title", published_at="2026-06-27T10:11:12Z",
    )
    assert [(k.kind, k.strong) for k in keys] == [
        (KeyKind.PROVIDER_ID, True),
        (KeyKind.URL, True),
        (KeyKind.FALLBACK, False),
    ]
    assert "utm_source" not in keys[1].value
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q tests/test_news_normalized_identity.py
```

Expected: collection fails because `src.news_normalized` does not exist.

- [ ] **Step 3: Add concrete models**

```python
# src/news_normalized/models.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class KeyKind(str, Enum):
    PROVIDER_ID = "provider_id"
    URL = "url"
    FALLBACK = "fallback"


class BodyStatus(str, Enum):
    PENDING = "pending"
    FETCHED = "fetched"
    EMPTY = "empty"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ArticleKey:
    source: str
    kind: KeyKind
    value: str
    strong: bool


@dataclass(frozen=True)
class BodyCandidate:
    status: BodyStatus = BodyStatus.PENDING
    raw_body: Optional[str] = None
    raw_format: Optional[str] = None
    retrieval_method: Optional[str] = None
    retrieval_source: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ArticleCandidate:
    source: str
    title: str
    published_at: str
    provider_article_id: Optional[str] = None
    publisher: str = ""
    url: str = ""
    primary_ticker: Optional[str] = None
    related_tickers: Tuple[str, ...] = field(default_factory=tuple)
    observed_at: Optional[str] = None
    content_kind: str = "unknown"
    body: BodyCandidate = field(default_factory=BodyCandidate)
```

- [ ] **Step 4: Implement deterministic identity functions**

```python
# src/news_normalized/identity.py
import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import ArticleKey, KeyKind

IDENTITY_VERSION = "news-id-v1"
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_identity_text(value: str) -> str:
    text = html.unescape(value or "")
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def normalize_timestamp(value: str) -> str:
    text = (value or "").strip().replace("+00:00", "Z")
    return text[:-5] + "Z" if text.endswith("+0000") else text


def normalize_stable_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value.strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query)
                             if k.casefold() not in _TRACKING))
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(),
                       parts.path.rstrip("/"), query, ""))


def fallback_identity_hash(*, source: str, publisher: str, title: str,
                           published_at: str) -> str:
    payload = "\0".join((IDENTITY_VERSION, source.casefold(),
                          normalize_identity_text(publisher),
                          normalize_identity_text(title),
                          normalize_timestamp(published_at)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_identity_keys(*, source: str, provider_article_id: str | None,
                        url: str, publisher: str, title: str,
                        published_at: str) -> tuple[ArticleKey, ...]:
    keys = []
    if provider_article_id:
        keys.append(ArticleKey(source, KeyKind.PROVIDER_ID,
                               provider_article_id.strip(), True))
    stable_url = normalize_stable_url(url)
    if stable_url:
        keys.append(ArticleKey(source, KeyKind.URL, stable_url, True))
    keys.append(ArticleKey(
        source, KeyKind.FALLBACK,
        fallback_identity_hash(source=source, publisher=publisher, title=title,
                               published_at=published_at),
        False,
    ))
    return tuple(keys)
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
pytest -q tests/test_news_normalized_identity.py
python -m compileall -q src/news_normalized
```

Expected: all identity tests pass and compile exits 0.

```bash
git add src/news_normalized/__init__.py src/news_normalized/models.py \
  src/news_normalized/identity.py tests/test_news_normalized_identity.py
git commit -m "feat: add normalized news identity model"
```

---

### Task 2: Add additive schema and FTS projection (N1)

**Files:**
- Create: `src/news_normalized/schema.py`
- Create: `tests/test_news_normalized_schema.py`

- [ ] **Step 1: Write failing schema tests**

```python
def test_schema_has_strong_key_uniqueness_but_allows_weak_collisions(conn):
    ensure_news_normalized_schema(conn)
    a = insert_minimal_article(conn, source="ibkr", provider_id=None)
    b = insert_minimal_article(conn, source="ibkr", provider_id=None)
    insert_key(conn, a, "ibkr", "fallback", "same")
    insert_key(conn, b, "ibkr", "fallback", "same")
    insert_key(conn, a, "ibkr", "provider_id", "DJ-N$1")
    with pytest.raises(sqlite3.IntegrityError):
        insert_key(conn, b, "ibkr", "provider_id", "DJ-N$1")


def test_search_projection_triggers_keep_fts_rowids_exact(conn):
    ensure_news_normalized_schema(conn)
    conn.execute("INSERT INTO news_search_documents VALUES (1, 'Alpha', 'clean body')")
    assert conn.execute("SELECT rowid FROM news_articles_fts").fetchall() == [(1,)]
    conn.execute("DELETE FROM news_search_documents WHERE article_id=1")
    assert conn.execute("SELECT rowid FROM news_articles_fts").fetchall() == []
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalized_schema.py`.

Expected: import failure for `ensure_news_normalized_schema`.

- [ ] **Step 3: Implement schema constants and idempotent installer**

`src/news_normalized/schema.py` must define the complete tables from spec sections 5.1-5.7,
including `raw_ref`, plus this search projection:

```python
SEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_search_documents (
    article_id INTEGER PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body_text TEXT NOT NULL DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS news_articles_fts USING fts5(
    title, body_text, content='news_search_documents', content_rowid='article_id',
    tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS news_search_ai AFTER INSERT ON news_search_documents BEGIN
  INSERT INTO news_articles_fts(rowid,title,body_text)
  VALUES(new.article_id,new.title,new.body_text);
END;
CREATE TRIGGER IF NOT EXISTS news_search_ad AFTER DELETE ON news_search_documents BEGIN
  INSERT INTO news_articles_fts(news_articles_fts,rowid,title,body_text)
  VALUES('delete',old.article_id,old.title,old.body_text);
END;
CREATE TRIGGER IF NOT EXISTS news_search_au AFTER UPDATE ON news_search_documents BEGIN
  INSERT INTO news_articles_fts(news_articles_fts,rowid,title,body_text)
  VALUES('delete',old.article_id,old.title,old.body_text);
  INSERT INTO news_articles_fts(rowid,title,body_text)
  VALUES(new.article_id,new.title,new.body_text);
END;
"""


def ensure_news_normalized_schema(conn):
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(ARTICLE_SCHEMA + SEARCH_SCHEMA)
```

The article schema must use the exact CHECK values and partial strong-key index from the spec.
Do not add normalized tables to `_NEWS_SCHEMA`; the legacy bootstrap must stay unchanged.

- [ ] **Step 4: Add idempotency, FK, body-status, and raw-ref tests**

```python
def test_schema_is_idempotent_and_raw_ref_is_reserved(conn):
    ensure_news_normalized_schema(conn)
    ensure_news_normalized_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(news_article_bodies)")}
    assert {"raw_body", "raw_ref", "body_text", "body_sha256"} <= cols


def test_invalid_body_status_rejected(conn):
    article_id = insert_minimal_article(conn, source="ibkr", provider_id="x")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO news_article_bodies(article_id,body_status) VALUES (?,?)",
                     (article_id, "guessed_expired"))
```

- [ ] **Step 5: Verify and commit**

Run `pytest -q tests/test_news_normalized_schema.py`.

Expected: all schema/FTS tests pass.

```bash
git add src/news_normalized/schema.py tests/test_news_normalized_schema.py
git commit -m "feat: add normalized news schema"
```

---

### Task 3: Build deterministic body cleaning (N1)

**Files:**
- Create: `src/news_normalized/cleaner.py`
- Create: `tests/test_news_body_cleaner.py`
- Create: `tests/fixtures/news_cleaner/dj_html.json`
- Create: `tests/fixtures/news_cleaner/table_and_entities.json`
- Create: `tests/fixtures/news_cleaner/plain_alert.json`

- [ ] **Step 1: Add synthetic/redacted golden tests**

```python
@pytest.mark.parametrize("fixture_name", [
    "dj_html.json", "table_and_entities.json", "plain_alert.json",
])
def test_cleaner_golden_fixture(fixture_name):
    case = json.loads((FIXTURES / fixture_name).read_text())
    result = clean_news_body(case["raw"], raw_format=case["format"],
                             source=case["source"])
    assert result.text == case["expected"]
    assert result.version == CLEANER_VERSION


def test_cleaner_never_keeps_script_style_or_markup():
    result = clean_news_body(
        "<style>x</style><h1>Title</h1><script>alert(1)</script><p>Body&nbsp;text</p>",
        raw_format="html", source="ibkr",
    )
    assert result.text == "Title\n\nBody text"
    assert "<" not in result.text
```

Fixtures must contain only synthetic or structurally redacted text, never licensed article bodies.

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_body_cleaner.py`.

Expected: import failure for `clean_news_body`.

- [ ] **Step 3: Implement a stdlib streaming HTML-to-text parser**

```python
# src/news_normalized/cleaner.py
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re

CLEANER_VERSION = "news-clean-v1"
_BLOCKS = {"article", "blockquote", "br", "div", "h1", "h2", "h3", "h4",
           "li", "p", "pre", "table", "tr"}
_DROP = {"script", "style", "noscript", "svg"}


@dataclass(frozen=True)
class CleanBody:
    text: str
    version: str = CLEANER_VERSION


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.drop_depth = [], 0

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if tag in _DROP:
            self.drop_depth += 1
        elif not self.drop_depth and tag in _BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if tag in _DROP and self.drop_depth:
            self.drop_depth -= 1
        elif not self.drop_depth and tag in _BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(data)


def _normalize_blocks(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in unescape(text).splitlines()]
    return "\n\n".join(line for line in lines if line)


def clean_news_body(raw_body: str, *, raw_format: str | None, source: str) -> CleanBody:
    raw = raw_body or ""
    if (raw_format or "").casefold() in {"html", "xml"} or re.search(r"</?[a-z][^>]*>", raw, re.I):
        parser = _TextParser()
        parser.feed(raw)
        raw = "".join(parser.parts)
    return CleanBody(_normalize_blocks(raw))


def looks_like_html(value: str | None) -> bool:
    return bool(value and re.search(r"</?[a-z][^>]*>", value, re.I))
```

Provider boilerplate rules must be explicit line predicates keyed by source/publisher, not broad
substring deletion. Add each rule only with a failing fixture.

- [ ] **Step 4: Add deterministic corpus-invariant test**

Add a test that scans a small locally supplied sample through `clean_news_body` twice and asserts
equal output/hash while printing only counts and hashes. Skip with a clear reason when the local
fixture path is absent; committed tests remain hermetic.

- [ ] **Step 5: Verify and commit**

Run:

```bash
pytest -q tests/test_news_body_cleaner.py
```

Expected: all golden and safety tests pass.

```bash
git add src/news_normalized/cleaner.py tests/test_news_body_cleaner.py \
  tests/fixtures/news_cleaner
git commit -m "feat: add deterministic news body cleaner"
```

---

### Task 4: Implement normalized store and identity quarantine (N1)

**Files:**
- Create: `src/news_normalized/store.py`
- Create: `tests/test_news_normalized_store.py`
- Modify: `src/news_normalized/__init__.py`

- [ ] **Step 1: Write failing store tests for the load-bearing contracts**

```python
def test_fallback_article_acquires_provider_id_without_second_row(store):
    first = candidate(provider_article_id=None, title="Same", raw_body="body")
    second = candidate(provider_article_id="provider-7", title="Same", raw_body="body")
    a = store.upsert(first)
    b = store.upsert(second)
    assert a.article_id == b.article_id
    assert store.count_articles() == 1


def test_cross_ticker_fetch_stores_one_body_and_two_relations(store):
    result = store.upsert(candidate(provider_article_id="p1",
                                    primary_ticker="AAPL",
                                    related_tickers=("AAPL", "MSFT"),
                                    raw_body="<p>body</p>"))
    assert store.count_articles() == 1
    assert store.tickers(result.article_id) == {"AAPL", "MSFT"}
    assert store.body(result.article_id)["raw_body"] == "<p>body</p>"


def test_disagreeing_strong_keys_are_quarantined_without_mutation(store):
    a = store.upsert(candidate(provider_article_id="p1", url="https://x/a"))
    b = store.upsert(candidate(provider_article_id="p2", url="https://x/b"))
    before = store.snapshot_counts()
    conflict = store.upsert(candidate(provider_article_id="p1", url="https://x/b"))
    assert conflict.quarantined is True
    assert store.snapshot_counts()["articles"] == before["articles"]
    assert store.open_conflict_count() == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalized_store.py`.

Expected: import failure for `NormalizedNewsStore`.

- [ ] **Step 3: Implement resolution and transaction boundaries**

```python
class NormalizedNewsStore:
    def __init__(self, conn):
        self.conn = conn
        ensure_news_normalized_schema(conn)

    def upsert(self, candidate: ArticleCandidate) -> UpsertResult:
        keys = build_identity_keys(
            source=candidate.source,
            provider_article_id=candidate.provider_article_id,
            url=candidate.url,
            publisher=candidate.publisher,
            title=candidate.title,
            published_at=candidate.published_at,
        )
        with self.conn:
            resolution = self._resolve(keys, candidate)
            if resolution.conflict:
                return self._quarantine(candidate, resolution)
            article_id = resolution.article_id or self._insert_article(candidate)
            self._attach_keys(article_id, keys)
            self._upsert_title(article_id, candidate)
            self._upsert_tickers(article_id, candidate)
            self._upsert_body(article_id, candidate)
            self._refresh_search_document(article_id)
        return UpsertResult(article_id=article_id, inserted=resolution.article_id is None,
                            quarantined=False)
```

`_resolve` must query strong keys first. It may use one weak candidate only when source,
publisher/title/timestamp match and no stable key/body digest contradicts it. Multiple compatible
weak candidates are quarantined. `_quarantine` inserts deterministic JSON using sorted keys and
never logs payload content.

- [ ] **Step 4: Implement body-state and search invariants**

Add explicit transition validation:

```python
_ALLOWED = {
    BodyStatus.PENDING: {BodyStatus.PENDING, BodyStatus.FETCHED, BodyStatus.EMPTY,
                         BodyStatus.FAILED, BodyStatus.EXPIRED},
    BodyStatus.FAILED: {BodyStatus.FAILED, BodyStatus.FETCHED, BodyStatus.EMPTY,
                        BodyStatus.EXPIRED},
    BodyStatus.FETCHED: {BodyStatus.FETCHED},
    BodyStatus.EMPTY: {BodyStatus.EMPTY},
    BodyStatus.EXPIRED: {BodyStatus.EXPIRED},
}
```

For `FETCHED`, require non-empty `raw_body`, compute `body_sha256`, keep `raw_ref=NULL`, clean the
body, and upsert one search document. `EMPTY`/`EXPIRED` cannot be inferred from age inside the
store. A cleaner failure retains raw content, records `clean_error`, and indexes title with an empty
body rather than changing retrieval status.

- [ ] **Step 5: Verify FTS, title revision, idempotency, and raw isolation**

Run:

```bash
pytest -q tests/test_news_normalized_store.py tests/test_news_normalized_schema.py \
  tests/test_news_body_cleaner.py
```

Expected: all tests pass; tests prove raw HTML terms absent from FTS and a repeated upsert changes
no counts.

- [ ] **Step 6: Commit**

```bash
git add src/news_normalized/store.py src/news_normalized/__init__.py \
  tests/test_news_normalized_store.py
git commit -m "feat: add normalized news store"
```

---

### Task 5: Build streaming migration inputs and read-only inventory (N2)

**Files:**
- Create: `src/news_normalized/migration.py`
- Create: `tests/test_news_normalization_migration.py`

- [ ] **Step 1: Write failing loader tests**

```python
def test_legacy_loader_opens_sqlite_read_only(tmp_path):
    db = make_legacy_news_db(tmp_path)
    before = db.read_bytes()
    rows = list(iter_legacy_news(db, batch_size=2))
    assert len(rows) == 3
    assert db.read_bytes() == before


def test_parquet_loader_streams_only_requested_columns(tmp_path):
    path = make_news_parquet(tmp_path, source="ibkr")
    batches = list(iter_parquet_news([path], batch_size=2))
    assert sum(len(batch) for batch in batches) == 3
    assert batches[0][0].provider_article_id == "DJ-N$1"
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalization_migration.py -k loader`.

Expected: loader imports fail.

- [ ] **Step 3: Implement bounded readers**

```python
import pyarrow.parquet as pq


def iter_legacy_news(path: Path, *, batch_size: int = 2000):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute("SELECT id,ticker,title,description,url,publisher,source,"
                           "published_at,article_hash,sentiment_score,sentiment_source,"
                           "sentiment_scale FROM news ORDER BY id")
        while rows := cur.fetchmany(batch_size):
            yield from rows
    finally:
        conn.close()


def parquet_row_to_candidate(row: dict, path: Path) -> ParquetEvidence:
    source = str(row.get("source_api") or path.parents[1].name).casefold()
    return ParquetEvidence(
        source=source,
        provider_article_id=str(row["article_id"]) if row.get("article_id") else None,
        ticker=str(row.get("ticker") or "").upper(),
        title=str(row.get("title") or ""),
        published_at=str(row.get("published_at") or ""),
        publisher=str(row.get("publisher") or ""),
        url=str(row.get("url") or ""),
        related_tickers=_parse_related_tickers(row.get("related_tickers")),
        raw_body=(row.get("content") or row.get("description") or None),
        content_status=row.get("content_status"),
        collected_at=row.get("collected_at"),
        source_path=str(path),
    )


def _parse_related_tickers(value) -> tuple[str, ...]:
    try:
        items = json.loads(value) if isinstance(value, str) else (value or [])
    except (TypeError, ValueError):
        items = []
    return tuple(sorted({str(t).strip().upper() for t in items if str(t).strip()}))


def iter_parquet_news(paths: Sequence[Path], *, batch_size: int = 2048):
    columns = ["article_id", "ticker", "title", "published_at", "source_api",
               "description", "content", "url", "publisher", "related_tickers",
               "collected_at", "content_status", "content_fetch_attempts",
               "content_fetched_at"]
    for path in sorted(paths):
        parquet = pq.ParquetFile(path)
        available = set(parquet.schema.names)
        for batch in parquet.iter_batches(batch_size=batch_size,
                                          columns=[c for c in columns if c in available]):
            yield [parquet_row_to_candidate(row, path) for row in batch.to_pylist()]
```

Missing optional columns must map to `None`, not fail. Do not load all raw body columns into one
DataFrame.

- [ ] **Step 4: Add inventory aggregation without identity merging**

Implement `inventory_inputs()` to report, by source:

- SQLite row count;
- Parquet row and distinct provider-ID counts;
- rows with non-empty actual content;
- provider-ID body aggregation count;
- SQLite rows enriched from Parquet and SQLite-to-Parquet body-match rate;
- source files, byte sizes, mtimes, and Parquet metadata row counts.

The inventory must reproduce the known IBKR shape on fixture data: flattened empty rows do not make
an article body-missing when another row for the same provider ID has content.

- [ ] **Step 5: Verify and commit**

Run `pytest -q tests/test_news_normalization_migration.py -k 'loader or inventory'`.

Expected: all loader/inventory tests pass with no source file mutation.

```bash
git add src/news_normalized/migration.py tests/test_news_normalization_migration.py
git commit -m "feat: add streaming news migration inputs"
```

---

### Task 6: Implement migration plan, match-rate report, and fingerprint CLI (N2)

**Files:**
- Modify: `src/news_normalized/migration.py`
- Create: `scripts/migration/preview_news_normalization.py`
- Modify: `tests/test_news_normalization_migration.py`

- [ ] **Step 1: Write failing planner/fingerprint tests**

```python
def test_preview_reports_provider_match_and_fallback_blast_radius(fixture_inputs):
    plan = plan_news_normalization(**fixture_inputs)
    assert plan.sources["ibkr"].provider_id_matched == 2
    assert plan.sources["polygon"].fallback_only == 1
    assert plan.cross_ticker_rows_collapsed == 2
    assert len(plan.fingerprint) == 64


def test_fingerprint_is_order_independent_and_content_sensitive(fixture_inputs):
    a = plan_news_normalization(**fixture_inputs)
    b = plan_news_normalization(**reversed_inputs(fixture_inputs))
    c = plan_news_normalization(**changed_body_inputs(fixture_inputs))
    assert a.fingerprint == b.fingerprint
    assert c.fingerprint != a.fingerprint


def test_conflicting_provider_id_blocks_apply_candidate(fixture_inputs):
    plan = plan_news_normalization(**with_reused_provider_id(fixture_inputs))
    assert plan.blocking_conflicts[0].kind == "provider_id_reuse"
    assert plan.would_apply is False
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalization_migration.py -k 'preview or fingerprint or conflict'`.

Expected: planner symbols are missing.

- [ ] **Step 3: Implement deterministic planning**

The planner must:

1. index Parquet evidence by `(source, provider_article_id)`, normalized URL, and fallback key;
2. match legacy rows provider ID first, URL second, compatible fallback third;
3. preserve every title and ticker relation;
4. aggregate body state by provider article, never arbitrary mention row;
5. report non-identical non-empty body variants and distinct sentiment values;
6. count SQLite rows with no recoverable provider ID as `fallback_only` by source;
7. serialize only sorted scalar records/body hashes into the fingerprint, never raw body text.

Use explicit immutable result types:

```python
@dataclass(frozen=True)
class SourcePreview:
    legacy_rows: int
    parquet_rows: int
    planned_articles: int
    provider_id_matched: int
    fallback_only: int
    sqlite_rows_enriched_from_parquet: int
    body_match_count: int
    body_match_rate: float
    body_fetched: int
    body_missing: int


@dataclass(frozen=True)
class MigrationPreview:
    sources: dict[str, SourcePreview]
    planned_ticker_links: int
    planned_titles: int
    cross_ticker_rows_collapsed: int
    blocking_conflicts: tuple[Conflict, ...]
    weak_ambiguities: tuple[Conflict, ...]
    fingerprint: str
    would_apply: bool
```

- [ ] **Step 4: Add a strictly read-only CLI**

```python
def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    before = snapshot_inputs(args.market_db, args.parquet_root)
    preview = plan_news_normalization(
        market_db=Path(args.market_db), parquet_root=Path(args.parquet_root))
    after = snapshot_inputs(args.market_db, args.parquet_root)
    if before != after:
        raise RuntimeError("news normalization preview inputs changed during read")
    print(json.dumps(preview.to_dict(), sort_keys=True, ensure_ascii=True))
    return 0 if preview.would_apply else 2
```

The CLI must reject a SQLite URI without `mode=ro`, never call schema installers, and write only to
stdout unless an explicit report path is supplied.

- [ ] **Step 5: Run the hermetic suite, then the real read-only preview**

Run:

```bash
pytest -q tests/test_news_normalization_migration.py
python scripts/migration/preview_news_normalization.py \
  --market-db data/market_data.db --parquet-root data/news/raw \
  > /tmp/news-normalization-preview.json
```

Expected:

- tests pass;
- CLI reports all three sources;
- `provider_id_matched`, `fallback_only`, body match rate, conflicts, and fingerprint are present;
- `data/market_data.db` size/mtime and every Parquet size/mtime are unchanged;
- no normalized tables appear in the live DB.

Record the exact real counts/fingerprint in the implementation checkpoint; do not hard-code them
into production logic.

- [ ] **Step 6: Commit**

```bash
git add src/news_normalized/migration.py \
  scripts/migration/preview_news_normalization.py \
  tests/test_news_normalization_migration.py
git commit -m "feat: preview normalized news migration"
```

Do not commit `/tmp/news-normalization-preview.json`; it may contain local paths or licensed
metadata. Report only aggregate counts and the fingerprint in the review message.

---

### Task 7: Add bounded common writer with continuation (N3)

**Files:**
- Create: `src/news_normalized/writer.py`
- Create: `tests/test_news_normalized_writer.py`
- Modify: `src/news_normalized/models.py`

- [ ] **Step 1: Write failing writer tests**

```python
def test_writer_stores_metadata_when_body_budget_is_exhausted(tmp_store):
    provider = FakeProvider([candidate("p1"), candidate("p2")])
    result = write_news_batch(tmp_store, provider, tickers=["AAPL"],
                              budget=WriterBudget(max_articles=2, max_body_fetches=1))
    assert result.articles_seen == 2
    assert result.bodies_fetched == 1
    assert result.status == "partial"
    assert result.continuation.deferred_body_ids == ("p2",)
    assert tmp_store.count_articles() == 2


def test_writer_rerun_is_idempotent_and_clears_continuation(tmp_store):
    provider = FakeProvider([candidate("p1")])
    first = write_news_batch(tmp_store, provider, ["AAPL"], WriterBudget(10, 10))
    second = write_news_batch(tmp_store, provider, ["AAPL"], WriterBudget(10, 10))
    assert first.articles_inserted == 1
    assert second.articles_inserted == 0
    assert second.continuation is None
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalized_writer.py`.

Expected: writer imports fail.

- [ ] **Step 3: Add protocol, budget, continuation, and result models**

```python
from contextlib import nullcontext
from typing import Iterable, Protocol


class NewsProvider(Protocol):
    source: str

    def operation(self):
        return nullcontext()

    def fetch_articles(self, ticker: str,
                       since_iso: str | None) -> Iterable[ArticleCandidate]:
        raise NotImplementedError

    def fetch_body(self, candidate: ArticleCandidate) -> BodyCandidate:
        raise NotImplementedError


@dataclass(frozen=True)
class WriterBudget:
    max_articles: int
    max_body_fetches: int


@dataclass(frozen=True)
class WriterContinuation:
    deferred_tickers: tuple[str, ...] = ()
    deferred_body_ids: tuple[str, ...] = ()
    cursor: str | None = None


@dataclass(frozen=True)
class WriterResult:
    status: str
    articles_seen: int
    articles_inserted: int
    bodies_fetched: int
    errors: dict[str, str]
    continuation: WriterContinuation | None
```

Validate non-negative budgets. Continuation JSON must be stable and contain provider IDs rather
than ticker-row hashes.

- [ ] **Step 4: Implement writer orchestration**

```python
from dataclasses import replace


def write_news_batch(store, provider, tickers, budget, *, continuation=None,
                     progress_cb=None) -> WriterResult:
    work_tickers = tuple(continuation.deferred_tickers) if continuation else tuple(tickers)
    deferred_body_ids = list(continuation.deferred_body_ids) if continuation else []
    articles_seen = articles_inserted = bodies_fetched = 0
    errors: dict[str, str] = {}

    with provider.operation():
        # Resume already-persisted body work before fetching new metadata.
        still_deferred = []
        for provider_id in deferred_body_ids:
            if bodies_fetched >= budget.max_body_fetches:
                still_deferred.append(provider_id)
                continue
            candidate = store.candidate_by_provider_id(provider.source, provider_id)
            if candidate is None:
                errors[provider_id] = "deferred article is missing from normalized store"
                continue
            store.update_body(candidate, provider.fetch_body(candidate))
            bodies_fetched += 1

        seen_body_ids: set[str] = set()
        deferred_tickers: list[str] = []
        for ticker_index, ticker in enumerate(work_tickers):
            try:
                since = store.latest_cursor(provider.source, ticker)
                candidates = provider.fetch_articles(ticker, since)
                for candidate in candidates:
                    if articles_seen >= budget.max_articles:
                        deferred_tickers.extend(work_tickers[ticker_index:])
                        break
                    articles_seen += 1
                    pending = replace(candidate, body=BodyCandidate(status=BodyStatus.PENDING))
                    upsert = store.upsert(pending)
                    articles_inserted += int(upsert.inserted)

                    provider_id = candidate.provider_article_id
                    if candidate.body.status is BodyStatus.FETCHED:
                        store.update_body(candidate, candidate.body)
                    elif (candidate.body.status is BodyStatus.PENDING and provider_id
                          and provider_id not in seen_body_ids):
                        seen_body_ids.add(provider_id)
                        if bodies_fetched < budget.max_body_fetches:
                            store.update_body(candidate, provider.fetch_body(candidate))
                            bodies_fetched += 1
                        else:
                            still_deferred.append(provider_id)
                else:
                    if progress_cb:
                        progress_cb(ticker_index + 1, len(work_tickers), ticker)
                    continue
                break
            except Exception as exc:
                errors[ticker] = str(exc)

    continuation_out = None
    if deferred_tickers or still_deferred:
        continuation_out = WriterContinuation(
            deferred_tickers=tuple(dict.fromkeys(deferred_tickers)),
            deferred_body_ids=tuple(dict.fromkeys(still_deferred)),
        )
    status = "partial" if continuation_out or errors else "succeeded"
    return WriterResult(status, articles_seen, articles_inserted, bodies_fetched,
                        errors, continuation_out)
```

Add `latest_cursor(source, ticker)`, `candidate_by_provider_id(source, provider_id)`, and
`update_body(candidate, body)` to `NormalizedNewsStore` with focused tests before using them here.
Use existing provider telemetry helpers with a temporary DB in tests. Per-ticker provider failures
must update `provider_sync_meta`, leave successful tickers committed, and make aggregate status
`partial` when errors exist. N3 returns continuation; scheduler persistence is N8, not this plan.

- [ ] **Step 5: Verify bounded, failure, FTS, and idempotent behavior**

Run:

```bash
pytest -q tests/test_news_normalized_writer.py tests/test_news_normalized_store.py
```

Expected: all tests pass; no network fixtures or live paths are accessed.

- [ ] **Step 6: Commit**

```bash
git add src/news_normalized/writer.py src/news_normalized/models.py \
  tests/test_news_normalized_writer.py
git commit -m "feat: add bounded normalized news writer"
```

---

### Task 8: Add Polygon and Finnhub normalized adapters (N4)

**Files:**
- Create: `src/news_normalized/provider_adapters.py`
- Create: `tests/test_news_normalized_provider_adapters.py`

- [ ] **Step 1: Write failing real-model adapter tests**

```python
def test_polygon_adapter_preserves_provider_id_and_related_tickers():
    article = polygon_article(article_id="poly-1", ticker="AAPL",
                              related_tickers='["AAPL","MSFT"]')
    candidate = collector_article_to_candidate("polygon", article)
    assert candidate.provider_article_id == "poly-1"
    assert candidate.related_tickers == ("AAPL", "MSFT")
    assert candidate.body.raw_body == article.content


def test_finnhub_adapter_does_not_call_parquet_save(monkeypatch):
    collector = FakeFinnhubCollector([finnhub_article(article_id="77")])
    monkeypatch.setattr(collector, "save_articles", Mock(side_effect=AssertionError))
    rows = list(FinnhubNormalizedProvider(collector).fetch_articles("AAPL", None))
    assert rows[0].provider_article_id == "77"
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalized_provider_adapters.py`.

Expected: adapter imports fail.

- [ ] **Step 3: Implement source adapters without routing them**

```python
def collector_article_to_candidate(source: str, article) -> ArticleCandidate:
    related = parse_related_tickers(article.related_tickers)
    raw = article.content or article.description or None
    kind = "full_text" if article.content else ("summary" if article.description else "headline_only")
    return ArticleCandidate(
        source=source,
        provider_article_id=str(article.article_id) if article.article_id else None,
        title=article.title,
        publisher=article.publisher or "",
        url=article.url or "",
        published_at=article.published_at,
        primary_ticker=article.ticker,
        related_tickers=related,
        observed_at=article.collected_at or None,
        content_kind=kind,
        body=BodyCandidate(
            status=BodyStatus.FETCHED if raw else BodyStatus.PENDING,
            raw_body=raw,
            raw_format="html" if looks_like_html(raw) else "text",
            retrieval_method="provider_api",
            retrieval_source=source,
        ),
    )


def parse_related_tickers(value: str | list | None) -> tuple[str, ...]:
    try:
        items = json.loads(value) if isinstance(value, str) else (value or [])
    except (TypeError, ValueError, json.JSONDecodeError):
        items = []
    return tuple(sorted({str(t).strip().upper() for t in items if str(t).strip()}))
```

Provider wrappers call only fetch/parse methods. They must never instantiate or call
`StorageManager`, `save_articles`, `to_parquet`, PG sync, or the legacy writer.
Both REST wrappers implement `operation()` by returning `contextlib.nullcontext()` so the common
writer uses one operation boundary without acquiring the IBKR Gateway lock.

- [ ] **Step 4: Add inclusive-cursor and content-kind tests**

Pin the existing exact-inclusive cursor behavior, provider-ID retention, malformed
`related_tickers` isolation, and `summary` versus `full_text` classification. A malformed one-row
payload must be isolated without aborting other articles.

- [ ] **Step 5: Verify and commit**

Run:

```bash
pytest -q tests/test_news_normalized_provider_adapters.py \
  tests/test_news_providers.py
```

Expected: new and legacy adapter tests pass; legacy runtime behavior is unchanged.

```bash
git add src/news_normalized/provider_adapters.py \
  tests/test_news_normalized_provider_adapters.py
git commit -m "feat: add normalized REST news adapters"
```

---

### Task 9: Add IBKR normalized adapter against a fake Gateway (N5)

**Files:**
- Create: `src/news_normalized/ibkr_adapter.py`
- Create: `tests/test_news_normalized_ibkr_adapter.py`
- Create: `scripts/diagnostics/probe_ibkr_news_bodies.py`
- Modify: `data_sources/ibkr_source.py`

- [ ] **Step 1: Write failing fake-Gateway tests**

```python
def test_ibkr_adapter_fetches_one_body_for_article_seen_through_many_tickers(fake_gateway):
    fake_gateway.headlines = {
        "AAPL": [headline("DJ-N$1", "AAPL")],
        "MSFT": [headline("DJ-N$1", "MSFT")],
    }
    fake_gateway.bodies[("DJ-N", "DJ-N$1")] = "<p>body</p>"
    provider = IBKRNormalizedProvider(fake_gateway)
    result = write_news_batch(temp_store(), provider, ["AAPL", "MSFT"], WriterBudget(10, 10))
    assert fake_gateway.body_calls == [("DJ-N", "DJ-N$1")]
    assert result.articles_inserted == 1


def test_ibkr_failed_body_is_retryable_not_empty_or_expired(fake_gateway):
    fake_gateway.raise_body = TimeoutError("timeout")
    body = IBKRNormalizedProvider(fake_gateway).fetch_body(candidate("DJ-N$2"))
    assert body.status is BodyStatus.FAILED
    assert "timeout" in body.error
```

- [ ] **Step 2: Run tests and verify RED**

Run `pytest -q tests/test_news_normalized_ibkr_adapter.py`.

Expected: adapter imports fail.

- [ ] **Step 3: Implement fakeable Gateway protocol and adapter**

```python
class IBKRNewsGateway(Protocol):
    def fetch_headlines(self, ticker: str, since_iso: str | None):
        raise NotImplementedError

    def fetch_news_article_body(self, provider_code: str,
                                article_id: str) -> str | None:
        raise NotImplementedError


class IBKRNormalizedProvider:
    source = "ibkr"

    def __init__(self, gateway: IBKRNewsGateway):
        self.gateway = gateway
        self._body_cache: dict[str, BodyCandidate] = {}

    def operation(self):
        return ibkr_gateway_lock()

    def fetch_articles(self, ticker: str,
                       since_iso: str | None) -> Iterable[ArticleCandidate]:
        for headline in self.gateway.fetch_headlines(ticker, since_iso):
            yield ArticleCandidate(
                source="ibkr",
                provider_article_id=headline.article_id,
                title=headline.title,
                publisher=headline.provider_code,
                published_at=headline.published_at,
                primary_ticker=ticker,
                related_tickers=(ticker,),
                observed_at=headline.observed_at,
                content_kind="unknown",
                body=BodyCandidate(status=BodyStatus.PENDING),
            )

    def fetch_body(self, candidate: ArticleCandidate) -> BodyCandidate:
        article_id = candidate.provider_article_id
        if article_id in self._body_cache:
            return self._body_cache[article_id]
        provider = article_id.split("$", 1)[0]
        try:
            raw = self.gateway.fetch_news_article_body(provider, article_id)
        except Exception as exc:
            body = BodyCandidate(status=BodyStatus.FAILED, error=str(exc),
                                 retrieval_method="provider_api", retrieval_source="ibkr")
        else:
            body = BodyCandidate(status=BodyStatus.FETCHED if raw else BodyStatus.EMPTY,
                                 raw_body=raw or None,
                                 raw_format="html" if looks_like_html(raw) else "text",
                                 retrieval_method="provider_api", retrieval_source="ibkr")
        self._body_cache[article_id] = body
        return body
```

Add a strict method without changing the existing compatibility method:

```python
# data_sources/ibkr_source.py
def fetch_news_article_body_strict(self, provider_code: str,
                                   article_id: str) -> Optional[str]:
    self._ensure_connected()
    self._rate_limit_wait()
    body = self._ib.reqNewsArticle(provider_code, article_id)
    return body.articleText if body else None


def fetch_news_article_body(self, provider_code: str,
                            article_id: str) -> Optional[str]:
    try:
        return self.fetch_news_article_body_strict(provider_code, article_id)
    except Exception as exc:
        logger.error("Error fetching article body: %s", exc)
        return None
```

The normalized Gateway wrapper calls only the strict method, so `None` means a successful empty
response and exceptions become `FAILED`. The real provider acquires `ibkr_gateway_lock` once around
a bounded provider operation, not once per ticker/body. Tests monkeypatch the context manager and
prove it is acquired exactly once. No real `IBKRDataSource` is constructed in the test suite.

- [ ] **Step 4: Add the N6-ready sanitized probe CLI**

The CLI must default to the five approved IDs, use `client_id` from effective configuration, hold
the shared Gateway lock, perform no DB/Parquet writes, and output only:

```json
{"label":"normal","provider":"DJ-RTA","present":true,"length":1234,
 "html_tags":17,"response_class":"body"}
```

It must never print title, URL, body, snippets, exception payloads containing content, or API
credentials. Add a test that supplies a unique secret phrase in the fake body and asserts the phrase
is absent from stdout/stderr.

- [ ] **Step 5: Verify offline only**

Run:

```bash
pytest -q tests/test_news_normalized_ibkr_adapter.py
```

Expected: all tests pass; fake Gateway call counts prove store-once body behavior; no network socket
is opened. Do not run the diagnostics script against `192.168.0.153` in this plan.

- [ ] **Step 6: Commit**

```bash
git add src/news_normalized/ibkr_adapter.py data_sources/ibkr_source.py \
  scripts/diagnostics/probe_ibkr_news_bodies.py \
  tests/test_news_normalized_ibkr_adapter.py
git commit -m "feat: add normalized IBKR news adapter"
```

---

### Task 10: Run the complete offline gate and record the checkpoint

**Files:**
- Modify: `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md`

- [ ] **Step 1: Run focused tests**

```bash
pytest -q \
  tests/test_news_normalized_identity.py \
  tests/test_news_normalized_schema.py \
  tests/test_news_body_cleaner.py \
  tests/test_news_normalized_store.py \
  tests/test_news_normalization_migration.py \
  tests/test_news_normalized_writer.py \
  tests/test_news_normalized_provider_adapters.py \
  tests/test_news_normalized_ibkr_adapter.py
```

Expected: all focused tests pass.

- [ ] **Step 2: Run legacy regression surfaces**

```bash
pytest -q \
  tests/test_news_providers.py \
  tests/test_news_direct.py \
  tests/test_sqlite_backend.py \
  tests/test_data_scheduler.py
```

Expected: all legacy news/read/scheduler tests pass; current runtime remains unchanged.

- [ ] **Step 3: Verify isolation and static integrity**

```bash
python -m compileall -q src/news_normalized scripts/migration scripts/diagnostics
git diff --check
git status --short
```

Expected:

- compile and diff checks exit 0;
- no tracked changes under `data/`, `config/.env`, `trained_models/`, or
  `config/tickers_core.json` were introduced by this plan;
- no live normalized tables exist in `data/market_data.db`;
- no external request was made.

- [ ] **Step 4: Record exact N1-N5 status without claiming cutover**

Update both design trackers with:

- N1-N5 offline foundation commit IDs;
- real read-only preview aggregate counts and fingerprint;
- blocking/weak conflict counts;
- explicit `N6 probe pending: Gateway handshake unavailable`;
- explicit `N7 apply / N8 cutover / N9 deletion not started`;
- Parquet remains a frozen enrichment source and active legacy dependency, not the new authority.

- [ ] **Step 5: Commit checkpoint docs**

```bash
git add docs/design/NEWS_DIRECT_LOCAL_PLAN.md docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record news normalization offline gate"
```

At this checkpoint, stop for review. Do not proceed to N6, N7, N8, or N9 without their separate
gates and plans.
