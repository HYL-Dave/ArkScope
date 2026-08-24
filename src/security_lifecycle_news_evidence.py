"""Read bounded lifecycle evidence from caller-owned local news databases."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping
from urllib.parse import urlsplit

from src.security_lifecycle_sec_evidence import IdentityContext


_NORMALIZED_SCHEMA = {
    "news_articles": {
        "id",
        "source",
        "canonical_title",
        "publisher",
        "url",
        "published_at",
    },
    "news_article_tickers": {"article_id", "ticker"},
    "news_article_bodies": {
        "article_id",
        "body_status",
        "body_text",
        "body_sha256",
        "source_url",
    },
}
_SA_SCHEMA = {
    "sa_market_news": {
        "id",
        "news_id",
        "url",
        "title",
        "published_at",
        "summary",
        "body_markdown",
    },
    "sa_market_news_tickers": {"news_row_id", "ticker"},
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PublisherEvidence:
    evidence_id: str
    source_family: str
    adapter: str
    kind: str
    source_url: str | None
    title: str
    publisher: str
    domain: str | None
    source_published_at: str
    retrieved_at: str
    excerpt: str
    content_sha256: str
    source_document_sha256: str | None
    source_locator: Mapping[str, Any]
    evidence_dedupe_key: str


@dataclass(frozen=True)
class LocalPublisherEvidenceResult:
    evidence: tuple[PublisherEvidence, ...]
    blockers: tuple[str, ...]
    source_families: tuple[str, ...]
    corroboration_family_count: int
    truncated: bool


class _SchemaMismatch(RuntimeError):
    pass


def _date(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(name) from exc
    if parsed.isoformat() != normalized:
        raise ValueError(name)
    return normalized


def _timestamp(value: str) -> str:
    normalized = str(value or "").strip()
    parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError("retrieved_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at")
    return normalized


def _verify_schema(conn: sqlite3.Connection, expected: Mapping[str, set[str]]) -> None:
    for table, required_columns in expected.items():
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        columns = {str(row[1]) for row in rows}
        if not required_columns.issubset(columns):
            raise _SchemaMismatch(table)


def _bounded_utf8(value: object, limit: int) -> str:
    normalized = str(value or "").strip()
    encoded = normalized.encode("utf-8")
    if len(encoded) <= limit:
        return normalized
    return encoded[:limit].decode("utf-8", errors="ignore")


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    return urlsplit(url).hostname


def _normalized_rows(
    conn: sqlite3.Connection,
    *,
    aliases: tuple[str, ...],
    start_date: str,
    end_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in aliases)
    rows = conn.execute(
        "SELECT a.id,a.source,a.canonical_title,a.publisher,a.url,a.published_at,"
        "b.body_status,b.body_text,b.body_sha256,b.source_url,"
        "group_concat(DISTINCT t.ticker) AS matched_tickers "
        "FROM news_articles a "
        "JOIN news_article_tickers t ON t.article_id=a.id "
        "LEFT JOIN news_article_bodies b ON b.article_id=a.id "
        f"WHERE t.ticker IN ({placeholders}) "
        "AND substr(a.published_at,1,10) BETWEEN ? AND ? "
        "GROUP BY a.id ORDER BY a.published_at DESC,a.id DESC LIMIT ?",
        (*aliases, start_date, end_date, limit),
    ).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "table": "news_articles",
                "row_id": int(row[0]),
                "provider_source": str(row[1]),
                "title": str(row[2]),
                "publisher": str(row[3] or row[1]),
                "url": str(row[4]) if row[4] else (str(row[9]) if row[9] else None),
                "published_at": str(row[5]),
                "body_status": str(row[6] or "unknown"),
                "body": str(row[7] or row[2]),
                "body_sha256": str(row[8]) if row[8] else None,
                "matched_tickers": tuple(
                    sorted({item for item in str(row[10] or "").split(",") if item})
                ),
            }
        )
    return result


def _sa_rows(
    conn: sqlite3.Connection,
    *,
    aliases: tuple[str, ...],
    start_date: str,
    end_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in aliases)
    rows = conn.execute(
        "SELECT n.id,n.news_id,n.url,n.title,n.published_at,n.summary,n.body_markdown,"
        "group_concat(DISTINCT t.ticker) AS matched_tickers "
        "FROM sa_market_news n "
        "JOIN sa_market_news_tickers t ON t.news_row_id=n.id "
        f"WHERE t.ticker IN ({placeholders}) "
        "AND substr(n.published_at,1,10) BETWEEN ? AND ? "
        "GROUP BY n.id ORDER BY n.published_at DESC,n.id DESC LIMIT ?",
        (*aliases, start_date, end_date, limit),
    ).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "table": "sa_market_news",
                "row_id": int(row[0]),
                "provider_source": "seeking_alpha",
                "provider_article_id": str(row[1]),
                "url": str(row[2]),
                "title": str(row[3]),
                "published_at": str(row[4]),
                "publisher": "Seeking Alpha",
                "body_status": "stored",
                "body": str(row[6] or row[5] or row[3]),
                "body_sha256": None,
                "matched_tickers": tuple(
                    sorted({item for item in str(row[7] or "").split(",") if item})
                ),
            }
        )
    return result


def _evidence(
    row: Mapping[str, Any], *, retrieved_at: str, max_excerpt_bytes: int
) -> PublisherEvidence:
    excerpt = _bounded_utf8(row["body"], max_excerpt_bytes)
    content_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    body_digest = str(row.get("body_sha256") or "").lower()
    document_digest = body_digest if _SHA256.fullmatch(body_digest) else None
    dedupe_material = (
        f'{row["table"]}\0{row["row_id"]}\0{content_digest}'
    )
    dedupe_digest = hashlib.sha256(dedupe_material.encode("utf-8")).hexdigest()
    return PublisherEvidence(
        evidence_id="sle_" + dedupe_digest[:32],
        source_family="publisher",
        adapter="internal_news",
        kind="publisher_excerpt",
        source_url=row.get("url"),
        title=_bounded_utf8(row["title"], 500),
        publisher=_bounded_utf8(row["publisher"], 240),
        domain=_domain(row.get("url")),
        source_published_at=str(row["published_at"]),
        retrieved_at=retrieved_at,
        excerpt=excerpt,
        content_sha256=content_digest,
        source_document_sha256=document_digest,
        source_locator={
            "table": row["table"],
            "row_id": row["row_id"],
            "provider_source": row["provider_source"],
            "matched_tickers": row["matched_tickers"],
            "body_status": row["body_status"],
        },
        evidence_dedupe_key=f"internal_news:{dedupe_digest}",
    )


def read_local_publisher_evidence(
    *,
    normalized_conn: sqlite3.Connection,
    sa_conn: sqlite3.Connection,
    context: IdentityContext,
    start_date: str,
    end_date: str,
    retrieved_at: str,
    max_rows: int = 20,
    max_excerpt_bytes: int = 2000,
) -> LocalPublisherEvidenceResult:
    """Read only from two explicit borrowed connections; never create schema."""
    start = _date("start_date", start_date)
    end = _date("end_date", end_date)
    if start > end:
        raise ValueError("date_range")
    at = _timestamp(retrieved_at)
    if type(max_rows) is not int or not 1 <= max_rows <= 100:
        raise ValueError("max_rows")
    if type(max_excerpt_bytes) is not int or not 64 <= max_excerpt_bytes <= 16_000:
        raise ValueError("max_excerpt_bytes")

    try:
        _verify_schema(normalized_conn, _NORMALIZED_SCHEMA)
        _verify_schema(sa_conn, _SA_SCHEMA)
    except _SchemaMismatch:
        return LocalPublisherEvidenceResult(
            (), ("internal_news_schema_mismatch",), (), 0, False
        )
    except sqlite3.Error:
        return LocalPublisherEvidenceResult(
            (), ("internal_news_unavailable",), (), 0, False
        )

    read_limit = max_rows + 1
    try:
        rows = _normalized_rows(
            normalized_conn,
            aliases=context.ticker_aliases,
            start_date=start,
            end_date=end,
            limit=read_limit,
        )
        rows.extend(
            _sa_rows(
                sa_conn,
                aliases=context.ticker_aliases,
                start_date=start,
                end_date=end,
                limit=read_limit,
            )
        )
    except sqlite3.Error:
        return LocalPublisherEvidenceResult(
            (), ("internal_news_unavailable",), (), 0, False
        )

    deduped = {
        (str(row["table"]), int(row["row_id"])): row
        for row in rows
    }
    ordered = sorted(
        deduped.values(),
        key=lambda row: (str(row["published_at"]), str(row["table"]), int(row["row_id"])),
        reverse=True,
    )
    truncated = len(ordered) > max_rows
    evidence = tuple(
        _evidence(row, retrieved_at=at, max_excerpt_bytes=max_excerpt_bytes)
        for row in ordered[:max_rows]
    )
    families = ("publisher",) if evidence else ()
    return LocalPublisherEvidenceResult(
        evidence=evidence,
        blockers=(),
        source_families=families,
        corroboration_family_count=len(families),
        truncated=truncated,
    )
