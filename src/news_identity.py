"""Canonical identity helpers for local and mirrored news rows."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Mapping


MERGE_FIELDS = (
    "description",
    "url",
    "publisher",
    "sentiment_score",
    "sentiment_source",
    "sentiment_scale",
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


def canonical_article_hash(ticker: str, title: str, published_at: str) -> str:
    """Return the canonical news identity for the stored ticker, title, and UTC date."""
    date10 = (published_at or "")[:10]
    raw = f"{ticker}|{title}|{date10}".encode("utf-8")
    # No [:64]: a SHA-256 hex digest is already exactly 64 characters. This is byte-identical
    # to the existing stored hash contract.
    return hashlib.sha256(raw).hexdigest()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _news_rows(conn: sqlite3.Connection) -> tuple[list[dict], tuple[str, ...]]:
    columns = _table_columns(conn, "news")
    required = ("id", "ticker", "title", "published_at", "article_hash")
    missing = set(required) - columns
    if missing:
        raise sqlite3.OperationalError(f"news table missing identity columns: {sorted(missing)}")
    merge_columns = tuple(field for field in MERGE_FIELDS if field in columns)
    selected = required + merge_columns
    cursor = conn.execute(f"SELECT {','.join(selected)} FROM news ORDER BY id")
    names = tuple(str(item[0]) for item in cursor.description)
    return [dict(zip(names, row)) for row in cursor.fetchall()], merge_columns


def _plan_fingerprint(
    rows_by_id: dict[int, dict],
    merge_columns: tuple[str, ...],
    updates: tuple[NewsIdentityUpdate, ...],
    collisions: tuple[NewsIdentityCollision, ...],
) -> str:
    affected = {item.row_id for item in updates}
    affected.update(item.stale_id for item in collisions)
    affected.update(item.target_id for item in collisions)
    row_fields = ("id", "ticker", "title", "published_at", "article_hash") + merge_columns
    payload = {
        "rows": [
            {field: rows_by_id[row_id].get(field) for field in row_fields}
            for row_id in sorted(affected)
        ],
        "updates": [item.__dict__ for item in updates],
        "collisions": [item.__dict__ for item in collisions],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def plan_news_identity_repair(
    conn: sqlite3.Connection,
    *,
    ticker_overrides: Mapping[int, str] | None = None,
    only_ids: set[int] | None = None,
) -> NewsIdentityPlan:
    """Classify canonical-hash updates and proven identity collisions without writing."""
    rows, merge_columns = _news_rows(conn)
    rows_by_id = {int(row["id"]): row for row in rows}
    overrides = {int(key): value for key, value in (ticker_overrides or {}).items()}
    selected_ids = set(rows_by_id) if only_ids is None else {int(value) for value in only_ids}
    unknown = selected_ids - set(rows_by_id)
    if unknown:
        raise ValueError(f"repair candidate ids not found: {sorted(unknown)}")

    stable_owners: dict[str, int] = {}
    for row_id, row in rows_by_id.items():
        current_hash = canonical_article_hash(row["ticker"], row["title"], row["published_at"])
        if row["article_hash"] == current_hash:
            stable_owners.setdefault(current_hash, row_id)

    candidates: dict[str, list[tuple[int, dict, str]]] = {}
    for row_id in sorted(selected_ids):
        row = rows_by_id[row_id]
        target_ticker = overrides.get(row_id, row["ticker"])
        target_hash = canonical_article_hash(target_ticker, row["title"], row["published_at"])
        if row["article_hash"] != target_hash or row["ticker"] != target_ticker:
            candidates.setdefault(target_hash, []).append((row_id, row, target_ticker))

    updates: list[NewsIdentityUpdate] = []
    collisions: list[NewsIdentityCollision] = []
    for target_hash in sorted(candidates):
        group = sorted(candidates[target_hash], key=lambda item: item[0])
        target_id = stable_owners.get(target_hash)
        if target_id is None:
            row_id, row, target_ticker = group.pop(0)
            target_id = row_id
            updates.append(NewsIdentityUpdate(
                row_id=row_id,
                old_hash=row["article_hash"],
                target_hash=target_hash,
                target_ticker=target_ticker,
            ))
        for stale_id, stale_row, _target_ticker in group:
            collisions.append(NewsIdentityCollision(
                stale_id=stale_id,
                target_id=target_id,
                old_hash=stale_row["article_hash"],
                target_hash=target_hash,
            ))

    updates_tuple = tuple(sorted(updates, key=lambda item: item.row_id))
    collisions_tuple = tuple(sorted(collisions, key=lambda item: item.stale_id))
    fingerprint = _plan_fingerprint(
        rows_by_id, merge_columns, updates_tuple, collisions_tuple)
    return NewsIdentityPlan(
        fingerprint=fingerprint,
        scanned=len(rows),
        updates=updates_tuple,
        collisions=collisions_tuple,
    )


def _is_missing(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _row_dict(conn: sqlite3.Connection, row_id: int, columns: tuple[str, ...]) -> dict:
    cursor = conn.execute(
        f"SELECT {','.join(columns)} FROM news WHERE id = ?", (row_id,))
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"news row disappeared during identity repair: {row_id}")
    names = tuple(str(item[0]) for item in cursor.description)
    return dict(zip(names, row))


def apply_news_identity_plan(
    conn: sqlite3.Connection,
    plan: NewsIdentityPlan,
) -> dict[str, int]:
    """Apply a precomputed plan without owning the surrounding transaction."""
    merge_columns = tuple(
        field for field in MERGE_FIELDS if field in _table_columns(conn, "news"))
    updated = 0
    deleted = 0
    merged_fields = 0

    for item in plan.updates:
        cursor = conn.execute(
            "UPDATE news SET ticker = ?, article_hash = ? "
            "WHERE id = ? AND article_hash IS ?",
            (item.target_ticker, item.target_hash, item.row_id, item.old_hash),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(f"news identity update changed {cursor.rowcount} rows for {item.row_id}")
        updated += 1

    collision_columns = ("id", "article_hash") + merge_columns
    for item in plan.collisions:
        target = _row_dict(conn, item.target_id, collision_columns)
        stale = _row_dict(conn, item.stale_id, collision_columns)
        if target["article_hash"] != item.target_hash:
            raise RuntimeError(
                f"canonical news owner {item.target_id} no longer owns {item.target_hash}")
        if stale["article_hash"] != item.old_hash:
            raise RuntimeError(f"stale news row {item.stale_id} changed after planning")

        fill = {
            field: stale[field]
            for field in merge_columns
            if _is_missing(target[field]) and not _is_missing(stale[field])
        }
        if fill:
            assignments = ", ".join(f"{field} = ?" for field in fill)
            cursor = conn.execute(
                f"UPDATE news SET {assignments} WHERE id = ?",
                (*fill.values(), item.target_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"news identity merge changed {cursor.rowcount} rows for {item.target_id}")
            merged_fields += len(fill)

        cursor = conn.execute(
            "DELETE FROM news WHERE id = ? AND article_hash IS ?",
            (item.stale_id, item.old_hash),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                f"news identity collision delete changed {cursor.rowcount} rows for {item.stale_id}")
        deleted += 1

    return {"updated": updated, "deleted": deleted, "merged_fields": merged_fields}


def validate_news_identity(conn: sqlite3.Connection) -> dict[str, int]:
    """Return global news/hash/FTS integrity counts after reconciliation."""
    rows, _merge_columns = _news_rows(conn)
    mismatches = sum(
        row["article_hash"] != canonical_article_hash(
            row["ticker"], row["title"], row["published_at"])
        for row in rows
    )
    duplicate_hash_groups = int(conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT article_hash FROM news GROUP BY article_hash HAVING COUNT(*) > 1)"
    ).fetchone()[0])
    semantic_duplicate_groups = int(conn.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT source,ticker,title,published_at FROM news "
        "GROUP BY source,ticker,title,published_at HAVING COUNT(*) > 1)"
    ).fetchone()[0])
    news_rows = int(conn.execute("SELECT COUNT(*) FROM news").fetchone()[0])
    fts_rows = int(conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0])
    fts_missing = int(conn.execute(
        "SELECT COUNT(*) FROM news n LEFT JOIN news_fts f ON f.rowid=n.id "
        "WHERE f.rowid IS NULL"
    ).fetchone()[0])
    fts_orphans = int(conn.execute(
        "SELECT COUNT(*) FROM news_fts f LEFT JOIN news n ON n.id=f.rowid "
        "WHERE n.id IS NULL"
    ).fetchone()[0])
    return {
        "news_rows": news_rows,
        "fts_rows": fts_rows,
        "hash_mismatches": int(mismatches),
        "duplicate_hash_groups": duplicate_hash_groups,
        "semantic_duplicate_groups": semantic_duplicate_groups,
        "fts_missing": fts_missing,
        "fts_orphans": fts_orphans,
    }
