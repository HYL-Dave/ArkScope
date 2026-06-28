"""Additive schema for the normalized all-source news store."""

ARTICLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_articles (
    id                  INTEGER PRIMARY KEY,
    source              TEXT NOT NULL,
    provider_article_id TEXT,
    canonical_title     TEXT NOT NULL,
    publisher           TEXT,
    url                 TEXT,
    published_at        TEXT NOT NULL,
    content_kind        TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (content_kind IN (
                            'full_text','summary','brief','headline_only','unknown'
                        )),
    language            TEXT,
    story_group_id      TEXT,
    archived_at         TEXT,
    sentiment_score     REAL CHECK (
                            sentiment_score IS NULL OR sentiment_score BETWEEN 1 AND 5
                        ),
    sentiment_source    TEXT,
    sentiment_scale     TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_articles_provider_id
ON news_articles(source, provider_article_id)
WHERE provider_article_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_news_articles_source_pub
ON news_articles(source, published_at);

CREATE TABLE IF NOT EXISTS news_article_keys (
    id          INTEGER PRIMARY KEY,
    article_id  INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    key_kind    TEXT NOT NULL CHECK (key_kind IN ('provider_id','url','fallback')),
    key_value   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (article_id, key_kind, key_value)
);
CREATE INDEX IF NOT EXISTS idx_news_article_keys_article
ON news_article_keys(article_id);
CREATE INDEX IF NOT EXISTS idx_news_article_keys_lookup
ON news_article_keys(source, key_kind, key_value);
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_article_keys_strong
ON news_article_keys(source, key_kind, key_value)
WHERE key_kind IN ('provider_id','url');

CREATE TABLE IF NOT EXISTS news_article_tickers (
    article_id     INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    ticker         TEXT NOT NULL,
    relation_kind  TEXT NOT NULL DEFAULT 'related'
                   CHECK (relation_kind IN ('primary','related','observed_via')),
    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL,
    PRIMARY KEY (article_id, ticker)
);
CREATE INDEX IF NOT EXISTS idx_news_article_tickers_ticker
ON news_article_tickers(ticker, article_id);

CREATE TABLE IF NOT EXISTS news_article_titles (
    id                  INTEGER PRIMARY KEY,
    article_id          INTEGER NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    normalized_title    TEXT NOT NULL,
    observed_at         TEXT,
    observed_with_body  INTEGER NOT NULL DEFAULT 0
                        CHECK (observed_with_body IN (0,1)),
    UNIQUE (article_id, title)
);

CREATE TABLE IF NOT EXISTS news_article_bodies (
    article_id        INTEGER PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE,
    body_status       TEXT NOT NULL CHECK (
                          body_status IN ('pending','fetched','empty','failed','expired')
                      ),
    raw_body          TEXT,
    raw_ref           TEXT,
    raw_format        TEXT,
    body_text         TEXT,
    body_sha256       TEXT,
    cleaner_version   TEXT,
    retrieval_method  TEXT,
    retrieval_source  TEXT,
    source_url        TEXT,
    fetch_attempts    INTEGER NOT NULL DEFAULT 0 CHECK (fetch_attempts >= 0),
    last_attempt_at   TEXT,
    next_retry_at     TEXT,
    fetched_at        TEXT,
    last_error        TEXT,
    cleaned_at        TEXT,
    clean_error       TEXT
);

CREATE TABLE IF NOT EXISTS news_ingest_conflicts (
    id                         INTEGER PRIMARY KEY,
    source                     TEXT NOT NULL,
    conflict_kind              TEXT NOT NULL,
    candidate_fingerprint      TEXT NOT NULL,
    candidate_payload_json     TEXT NOT NULL,
    existing_article_ids_json  TEXT,
    status                     TEXT NOT NULL DEFAULT 'open'
                               CHECK (status IN ('open','resolved','ignored')),
    created_at                 TEXT NOT NULL,
    resolved_at                TEXT,
    resolution                 TEXT,
    UNIQUE (source, conflict_kind, candidate_fingerprint)
);
"""

SEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS news_search_documents (
    article_id  INTEGER PRIMARY KEY REFERENCES news_articles(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body_text   TEXT NOT NULL DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS news_articles_fts USING fts5(
    title, body_text,
    content='news_search_documents', content_rowid='article_id',
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


def ensure_news_normalized_schema(conn) -> None:
    """Create the normalized schema without touching the legacy ``news`` tables."""
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(ARTICLE_SCHEMA + SEARCH_SCHEMA)
