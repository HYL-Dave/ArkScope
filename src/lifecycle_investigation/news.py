"""Closed readonly access to locally collected public news, never collector IO."""

from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from uuid import uuid4

from src.lifecycle_public_sources import canonical_source_url, SourceReadError


def _url(value):
    try:
        return canonical_source_url(value)
    except SourceReadError:
        return None


def _metadata(row, kind):
    return {"title": row["title"], "publisher": row["publisher"], "url": _url(row["url"]),
            "published_at": row["published_at"], "coverage": row["coverage"], "corpus": kind}


class LocalNews:
    def __init__(self, market_path, sa_path, *, clock=None):
        self.paths = {key: Path(path) for key, path in (("news", market_path), ("sa_market_news", sa_path)) if path is not None}
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._candidates = {}

    def search(self, *, ticker, issuer_name=None, query=None, since=None, until=None, offset=0, limit=12):
        if (type(ticker) is not str or not ticker or type(offset) is not int or not 0 <= offset <= 1000
                or type(limit) is not int or not 1 <= limit <= 40
                or any(value is not None and (type(value) is not str or len(value) > 240) for value in (issuer_name, query))):
            raise ValueError("local_query_invalid")
        for value in (since, until):
            if value is not None and date.fromisoformat(value).isoformat() != value:
                raise ValueError("local_query_invalid")
        if since and until and since > until:
            raise ValueError("local_query_invalid")
        rows, gaps, available = [], [], 0
        for kind, path in self.paths.items():
            if not path.is_file():
                gaps.append({"corpus": kind, "reason": "local_news_unavailable"})
                continue
            try:
                with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
                    conn.row_factory = sqlite3.Row
                    conn.execute("PRAGMA query_only=ON")
                    found = self._search(conn, kind, ticker, issuer_name, query, since, until, offset + limit + 1)
                available += 1
            except sqlite3.Error:
                gaps.append({"corpus": kind, "reason": "local_news_unavailable"})
                continue
            for row in found:
                identity = "candidate-" + uuid4().hex
                meta = _metadata(row, kind)
                self._candidates[identity] = (kind, row["id"], meta)
                rows.append({"candidate_id": identity, **meta})
        rows.sort(key=lambda row: (row["published_at"] or "", row["title"]), reverse=True)
        return {"status": "unavailable" if not available else "partial" if gaps else "ok",
                "items": rows[offset:offset + limit], "gaps": gaps,
                "next_offset": offset + limit if len(rows) > offset + limit else None,
                "coverage": "available_local_corpora", "observed_at": self.clock()}

    @staticmethod
    def _search(conn, kind, ticker, issuer_name, query, since, until, limit):
        if kind == "news":
            base = ("SELECT a.id,a.canonical_title AS title,a.publisher,a.url,a.published_at,a.content_kind AS coverage "
                    "FROM news_articles a LEFT JOIN news_article_bodies b ON b.article_id=a.id ")
            where = ["a.archived_at IS NULL", "(EXISTS(SELECT 1 FROM news_article_tickers t WHERE t.article_id=a.id AND t.ticker=?)"]
            title, body, published = "a.canonical_title", "COALESCE(b.body_text,'')", "a.published_at"
        else:
            base = ("SELECT a.id,a.title,'Seeking Alpha' AS publisher,a.url,a.published_at,"
                    "CASE WHEN a.body_markdown IS NOT NULL AND a.detail_fetched_at IS NOT NULL THEN 'full_text' "
                    "WHEN a.summary IS NOT NULL THEN 'summary' ELSE 'headline_only' END AS coverage FROM sa_market_news a ")
            where = ["(EXISTS(SELECT 1 FROM sa_market_news_tickers t WHERE t.news_row_id=a.id AND t.ticker=?)"]
            title, body, published = "a.title", "COALESCE(a.body_markdown,a.summary,'')", "a.published_at"
        args = [ticker]
        if issuer_name:
            where[-1] += f" OR instr(lower({title} || ' ' || {body}),lower(?))>0"
            args.append(issuer_name)
        where[-1] += ")"
        if query:
            where.append(f"instr(lower({title} || ' ' || {body}),lower(?))>0")
            args.append(query)
        if since:
            where.append(f"substr({published},1,10)>=?")
            args.append(since)
        if until:
            where.append(f"substr({published},1,10)<=?")
            args.append(until)
        return conn.execute(base + " WHERE " + " AND ".join(where) + f" ORDER BY {published} DESC,a.id DESC LIMIT ?", (*args, limit)).fetchall()

    def read(self, candidate_id):
        if candidate_id not in self._candidates:
            raise ValueError("local_candidate_unknown")
        kind, identity, admitted = self._candidates[candidate_id]
        try:
            with closing(sqlite3.connect(self.paths[kind].resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                if kind == "news":
                    row = conn.execute("SELECT a.canonical_title AS title,a.publisher,a.url,a.published_at,a.content_kind AS coverage,"
                        "b.body_text AS text,b.body_status,b.fetched_at AS captured_at,a.story_group_id "
                        "FROM news_articles a LEFT JOIN news_article_bodies b ON b.article_id=a.id WHERE a.id=? AND a.archived_at IS NULL", (identity,)).fetchone()
                else:
                    row = conn.execute("SELECT title,'Seeking Alpha' AS publisher,url,published_at,"
                        "CASE WHEN body_markdown IS NOT NULL AND detail_fetched_at IS NOT NULL THEN 'full_text' "
                        "WHEN summary IS NOT NULL THEN 'summary' ELSE 'headline_only' END AS coverage,"
                        "COALESCE(body_markdown,summary) AS text,'fetched' AS body_status,"
                        "COALESCE(detail_fetched_at,fetched_at) AS captured_at,NULL AS story_group_id FROM sa_market_news WHERE id=?", (identity,)).fetchone()
        except sqlite3.Error:
            raise ValueError("local_news_unavailable") from None
        if row is None or _metadata(row, kind) != admitted:
            raise ValueError("local_candidate_changed")
        text = row["text"] if row["body_status"] == "fetched" else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError("local_body_unavailable")
        digest = hashlib.sha256(text.encode()).hexdigest()
        group = row["story_group_id"]
        return {**admitted, "text": text, "text_sha256": digest, "captured_at": row["captured_at"],
                "retrieved_at": self.clock(), "syndication_key": None if not group else hashlib.sha256(str(group).encode()).hexdigest()}
