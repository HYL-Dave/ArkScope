"""Read-only article identity and event projections over retained SA evidence."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Collection

from src.sqlite_id_sets import text_ids_query
from src.tools.retained_read_results import RetainedReadFailure, page_integer, require


# A provider's primary ticker is not an exclusive subject: an accepted event
# may associate a multi-company article with another pick. Never rewrite either.
ASSOCIATIONS_CTE = """
WITH accepted_article_associations AS (
    SELECT k.article_id, UPPER(TRIM(l.symbol_key)) AS symbol,
           CASE WHEN k.role IN ('entry', 'exit') THEN k.role ELSE 'related' END AS role,
           k.link_source, k.evidence_codes, l.picked_date, k.event_anchor_date, k.link_id
    FROM sa_pick_article_links k
    JOIN sa_pick_lineages l ON l.lineage_id = k.lineage_id
    JOIN sa_articles a ON a.article_id = k.article_id
    WHERE k.revoked_at IS NULL
), provider_article_identity AS (
    SELECT article_id, NULLIF(UPPER(TRIM(ticker)), '') AS legacy_ticker,
           NULLIF(UPPER(TRIM(list_ticker)), '') AS listed,
           NULLIF(UPPER(TRIM(detail_ticker)), '') AS detail
    FROM sa_articles
), provider_article_associations AS (
    SELECT article_id, COALESCE(listed, detail, legacy_ticker) AS symbol,
           'related' AS role,
           CASE WHEN listed IS NOT NULL OR detail IS NOT NULL THEN 'provider' ELSE 'legacy' END AS link_source,
           CASE WHEN listed IS NOT NULL AND detail IS NOT NULL THEN '["ticker_list_exact","ticker_detail_exact"]'
                WHEN listed IS NOT NULL THEN '["ticker_list_exact"]'
                WHEN detail IS NOT NULL THEN '["ticker_detail_exact"]'
                ELSE '["legacy_ticker_projection"]' END AS evidence_codes,
           NULL AS picked_date, NULL AS event_anchor_date, NULL AS link_id
    FROM provider_article_identity
    WHERE (listed IS NULL OR detail IS NULL OR listed = detail)
      AND COALESCE(listed, detail, legacy_ticker) IS NOT NULL
), article_associations AS (
    SELECT * FROM accepted_article_associations
    UNION ALL
    SELECT p.* FROM provider_article_associations p
    WHERE NOT EXISTS (
        SELECT 1 FROM accepted_article_associations k
        WHERE k.article_id = p.article_id AND k.symbol = p.symbol
    )
)
"""

ARTICLE_TICKER_FILTER = (
    "sa_articles.article_id IN "
    "(SELECT article_id FROM article_associations WHERE symbol = ?)"
)


def associations_by_article(conn: sqlite3.Connection, article_ids: Collection[str]) -> dict:
    if not article_ids:
        return {}
    ids_query, params = text_ids_query(conn, article_ids)
    try:
        rows = conn.execute(
            ASSOCIATIONS_CTE + "SELECT * FROM article_associations "
            f"WHERE article_id IN ({ids_query}) ORDER BY article_id, symbol, role, picked_date, event_anchor_date, link_id",
            params,
        )
        result: dict = {}
        for row in rows:
            association = dict(row)
            article_id = association.pop("article_id")
            association["evidence_codes"] = json.loads(association["evidence_codes"])
            result.setdefault(article_id, []).append(association)
        return result
    except sqlite3.Error as exc:
        raise RetainedReadFailure("sa_article_associations_unavailable") from exc


def attach_associations(conn: sqlite3.Connection, articles: list[dict]) -> list[dict]:
    associations = associations_by_article(conn, [a["article_id"] for a in articles])
    for article in articles:
        article["associations"] = associations.get(article["article_id"], [])
        article["tickers"] = sorted({a["symbol"] for a in article["associations"]})
    return articles


def known_query_symbol(conn: sqlite3.Connection, query: str | None) -> str | None:
    """Only an entire retained symbol is a ticker query, never a body mention."""
    candidate = (query or "").strip().removeprefix("$").upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,19}", candidate):
        return None
    row = conn.execute(
        ASSOCIATIONS_CTE + "SELECT 1 FROM ("
        "SELECT symbol FROM article_associations UNION ALL "
        "SELECT UPPER(TRIM(symbol_key)) FROM sa_pick_lineages UNION ALL "
        "SELECT UPPER(TRIM(ticker)) FROM sa_market_news_tickers"
        ") WHERE symbol = ? LIMIT 1", (candidate,),
    ).fetchone()
    return candidate if row else None


def pick_articles(conn: sqlite3.Connection, lineage_id: int, symbol: str, *, related_offset: int = 0) -> dict:
    """Entry/exit are tied to the selected investment, not just its symbol."""
    require(page_integer(related_offset), "sa_pick_related_offset_invalid")
    symbol = symbol.strip().upper()
    picked = conn.execute(
        "SELECT picked_date FROM sa_pick_lineages WHERE lineage_id=?", (lineage_id,),
    ).fetchone()
    page = {"offset": related_offset, "limit": 20, "total": 0, "next_offset": None}
    result: dict = {"entry": [], "exit": [], "related": [], "related_pagination": page}
    if picked is None:
        return result
    select = ASSOCIATIONS_CTE + (
        "SELECT article_id, url, title, published_date, COALESCE(body_markdown, '') != '' AS has_content "
        "FROM sa_articles WHERE article_id IN (SELECT article_id FROM article_associations "
        "WHERE symbol=? AND "
    )
    order = " ORDER BY published_date DESC, article_id DESC"
    events = conn.execute(
        select + "role IN ('entry', 'exit') AND picked_date=?)" + order, (symbol, picked[0]),
    ).fetchall()
    related = conn.execute(
        select + "role='related')" + order + " LIMIT ? OFFSET ?", (symbol, page["limit"], related_offset),
    ).fetchall()
    page["total"] = conn.execute(
        ASSOCIATIONS_CTE + "SELECT COUNT(DISTINCT article_id) FROM article_associations "
        "WHERE symbol=? AND role='related'", (symbol,),
    ).fetchone()[0]
    if related_offset + len(related) < page["total"]:
        page["next_offset"] = related_offset + len(related)
    rows = list({row["article_id"]: dict(row) for row in [*events, *related]}.values())
    related_ids = {row["article_id"] for row in related}
    attach_associations(conn, rows)
    for row in rows:
        row["has_content"] = bool(row["has_content"])
        for role in ("entry", "exit", "related"):
            if role == "related" and row["article_id"] not in related_ids:
                continue
            matching = [a for a in row["associations"] if a["symbol"] == symbol
                        and a["role"] == role
                        and (role == "related" or a["picked_date"] == picked[0])]
            if matching:
                result[role].append({**row, "matching_link_ids": [a["link_id"] for a in matching if a["link_id"] is not None]})
    return result
