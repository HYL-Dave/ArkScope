"""Project normalized news rows into the legacy local news compatibility table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
import re
import sqlite3
from typing import Any

from src.news_direct import _norm_published
from src.news_identity import canonical_article_hash

from .cleaner import clean_news_body, looks_like_html


@dataclass(frozen=True)
class ProjectionResult:
    inserted: int = 0
    updated: int = 0
    skipped_no_ticker: int = 0


class LegacyProjectionConflict(RuntimeError):
    pass


_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_NOISE_RE = re.compile(r"[*_`>#~]+")


def project_article_uncommitted(conn: sqlite3.Connection, article_id: int) -> ProjectionResult:
    """Project one normalized article into legacy ``news`` rows.

    This helper is transaction-neutral: callers own transaction boundaries, and legacy
    ``news_fts`` synchronization is left to the existing ``news`` triggers.
    """
    article = _read_article(conn, article_id)
    tickers = _read_tickers(conn, article_id)
    if not tickers:
        return ProjectionResult(skipped_no_ticker=1)

    published_at = _norm_published(article["published_at"])
    if published_at is None:
        raise ValueError(f"normalized article {article_id} has unparseable published_at")

    description = _clean_snippet(article["body_text"] or "", source=article["source"])
    inserted = 0
    updated = 0
    for ticker in tickers:
        row = _legacy_values(article, ticker, published_at, description)
        mapped = _mapped_legacy_id(conn, article_id, ticker)
        if mapped is not None:
            if _update_mapped_row(conn, mapped, row):
                _touch_map(conn, article_id, ticker, mapped)
                updated += 1
            continue

        existing = _legacy_row_by_hash(conn, row["article_hash"])
        if existing is not None:
            if _adopt_existing_row(conn, article_id, ticker, existing, row):
                updated += 1
            continue

        legacy_id = _insert_legacy_row(conn, row)
        _insert_map(conn, article_id, ticker, legacy_id)
        inserted += 1

    return ProjectionResult(inserted=inserted, updated=updated)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _dict_from_row(cursor: sqlite3.Cursor, row: Any) -> dict[str, Any]:
    names = tuple(str(item[0]) for item in cursor.description)
    return dict(zip(names, row))


def _read_article(conn: sqlite3.Connection, article_id: int) -> dict[str, Any]:
    cursor = conn.execute(
        "SELECT a.id,a.source,a.canonical_title,a.publisher,a.url,a.published_at,"
        "COALESCE(b.body_text,'') AS body_text "
        "FROM news_articles a LEFT JOIN news_article_bodies b ON b.article_id=a.id "
        "WHERE a.id=?",
        (article_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise KeyError(f"normalized article not found: {article_id}")
    return _dict_from_row(cursor, row)


def _read_tickers(conn: sqlite3.Connection, article_id: int) -> list[str]:
    return [
        str(row[0])
        for row in conn.execute(
            "SELECT ticker FROM news_article_tickers WHERE article_id=? ORDER BY ticker",
            (article_id,),
        ).fetchall()
    ]


def _clean_snippet(value: str, *, source: str) -> str:
    text = value or ""
    if looks_like_html(text):
        text = clean_news_body(text, raw_format="html", source=source).text
    text = unescape(text)
    text = _MARKDOWN_LINK_RE.sub(r"\1", text)
    text = _MARKDOWN_NOISE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500].rstrip()


def _legacy_values(
    article: dict[str, Any],
    ticker: str,
    published_at: str,
    description: str,
) -> dict[str, Any]:
    title = article["canonical_title"]
    return {
        "ticker": ticker,
        "title": title,
        "description": description,
        "url": article["url"] or "",
        "publisher": article["publisher"] or "",
        "source": article["source"],
        "published_at": published_at,
        "article_hash": canonical_article_hash(
            ticker, title, article["published_at"]
        ),
    }


def _mapped_legacy_id(
    conn: sqlite3.Connection, article_id: int, ticker: str
) -> int | None:
    row = conn.execute(
        "SELECT legacy_news_id FROM news_legacy_projection_map "
        "WHERE article_id=? AND ticker=?",
        (article_id, ticker),
    ).fetchone()
    return int(row[0]) if row else None


def _legacy_row_by_id(conn: sqlite3.Connection, legacy_id: int) -> dict[str, Any] | None:
    cursor = conn.execute(
        "SELECT id,ticker,title,description,url,publisher,source,published_at,article_hash "
        "FROM news WHERE id=?",
        (legacy_id,),
    )
    row = cursor.fetchone()
    return _dict_from_row(cursor, row) if row else None


def _legacy_row_by_hash(
    conn: sqlite3.Connection, article_hash: str
) -> dict[str, Any] | None:
    cursor = conn.execute(
        "SELECT id,ticker,title,description,url,publisher,source,published_at,article_hash "
        "FROM news WHERE article_hash=?",
        (article_hash,),
    )
    row = cursor.fetchone()
    return _dict_from_row(cursor, row) if row else None


def _mapped_owner(
    conn: sqlite3.Connection, legacy_id: int
) -> tuple[int, str] | None:
    row = conn.execute(
        "SELECT article_id,ticker FROM news_legacy_projection_map "
        "WHERE legacy_news_id=?",
        (legacy_id,),
    ).fetchone()
    return (int(row[0]), str(row[1])) if row else None


def _update_mapped_row(
    conn: sqlite3.Connection, legacy_id: int, row: dict[str, Any]
) -> bool:
    current = _legacy_row_by_id(conn, legacy_id)
    if current is None:
        raise LegacyProjectionConflict(
            f"mapped legacy news row is missing: {legacy_id}"
        )
    competing = _legacy_row_by_hash(conn, row["article_hash"])
    if competing is not None and int(competing["id"]) != legacy_id:
        raise LegacyProjectionConflict(
            "canonical legacy hash is already owned by another news row"
        )
    if _legacy_row_matches(current, row):
        return False
    _write_legacy_row(conn, legacy_id, row)
    return True


def _adopt_existing_row(
    conn: sqlite3.Connection,
    article_id: int,
    ticker: str,
    existing: dict[str, Any],
    row: dict[str, Any],
) -> bool:
    if existing["ticker"] != ticker:
        raise LegacyProjectionConflict(
            "canonical legacy hash is owned by incompatible ticker/source"
        )
    if existing["source"] != row["source"]:
        # Legacy news rows are unique by ticker/title/date hash, not by source. If
        # another provider already projected the same syndicated article, preserve
        # that compatibility row and treat this source as represented.
        return False
    legacy_id = int(existing["id"])
    owner = _mapped_owner(conn, legacy_id)
    if owner is not None and owner != (article_id, ticker):
        raise LegacyProjectionConflict(
            "legacy news row is already mapped to another projection"
        )
    changed = not _legacy_row_matches(existing, row)
    if changed:
        _write_legacy_row(conn, legacy_id, row)
    _insert_map(conn, article_id, ticker, legacy_id)
    return changed


def _insert_legacy_row(conn: sqlite3.Connection, row: dict[str, Any]) -> int:
    cursor = conn.execute(
        "INSERT INTO news "
        "(ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?)",
        _row_tuple(row),
    )
    return int(cursor.lastrowid)


def _write_legacy_row(
    conn: sqlite3.Connection, legacy_id: int, row: dict[str, Any]
) -> None:
    cursor = conn.execute(
        "UPDATE news SET ticker=?,title=?,description=?,url=?,publisher=?,source=?,"
        "published_at=?,article_hash=? WHERE id=?",
        (*_row_tuple(row), legacy_id),
    )
    if cursor.rowcount != 1:
        raise LegacyProjectionConflict(
            f"legacy news update changed {cursor.rowcount} rows for {legacy_id}"
        )


def _insert_map(conn: sqlite3.Connection, article_id: int, ticker: str, legacy_id: int) -> None:
    conn.execute(
        "INSERT INTO news_legacy_projection_map "
        "(article_id,ticker,legacy_news_id,projected_at) VALUES (?,?,?,?)",
        (article_id, ticker, legacy_id, _now()),
    )


def _touch_map(conn: sqlite3.Connection, article_id: int, ticker: str, legacy_id: int) -> None:
    cursor = conn.execute(
        "UPDATE news_legacy_projection_map SET projected_at=? "
        "WHERE article_id=? AND ticker=? AND legacy_news_id=?",
        (_now(), article_id, ticker, legacy_id),
    )
    if cursor.rowcount != 1:
        raise LegacyProjectionConflict(
            "projection map changed while updating legacy row"
        )


def _row_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["ticker"],
        row["title"],
        row["description"],
        row["url"],
        row["publisher"],
        row["source"],
        row["published_at"],
        row["article_hash"],
    )


def _legacy_row_matches(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    return all(existing[key] == desired[key] for key in desired)
