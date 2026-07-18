"""SQLite persistence and projections for Alpha Picks article reconciliation."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection, Sequence
from typing import Any

from . import sa_capture_store as capture_store
from .sa_article_reconciliation import (
    ArticleEvidence,
    CandidateEvaluation,
    PickEvent,
    decide_reconciliation,
    evaluate_candidate,
    normalize_symbol,
)


MAX_EVENTS_PER_RECONCILIATION = 100
MAX_CANDIDATES_PER_EVENT = 20


def resolve_lineage(conn: sqlite3.Connection, *, symbol: str, picked_date: str) -> int:
    symbol_key = normalize_symbol(symbol)
    canonical_date = capture_store.canon_date(picked_date)
    if not symbol_key or not canonical_date:
        raise ValueError("symbol and picked_date are required for Alpha Picks lineage")
    conn.execute(
        "INSERT OR IGNORE INTO sa_pick_lineages(symbol_key, picked_date, created_at) "
        "VALUES (?, ?, ?)",
        (symbol_key, canonical_date, capture_store.now_ts()),
    )
    row = conn.execute(
        "SELECT lineage_id FROM sa_pick_lineages WHERE symbol_key=? AND picked_date=?",
        (symbol_key, canonical_date),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to resolve Alpha Picks lineage")
    return int(row[0])


def _lineage_ids_clause(lineage_ids: Collection[int] | None) -> tuple[str, list[int]]:
    if lineage_ids is None:
        return "", []
    normalized = sorted({int(value) for value in lineage_ids if int(value) > 0})
    if not normalized:
        return " AND 0", []
    return f" AND l.lineage_id IN ({','.join('?' for _ in normalized)})", normalized


def list_events(
    conn: sqlite3.Connection,
    *,
    lineage_ids: Collection[int] | None = None,
) -> list[dict[str, Any]]:
    lineage_clause, params = _lineage_ids_clause(lineage_ids)
    rows = conn.execute(
        "SELECT l.lineage_id, l.symbol_key, l.picked_date, "
        "COALESCE((SELECT p.company FROM sa_alpha_picks p "
        " WHERE p.lineage_id=l.lineage_id "
        " ORDER BY p.is_stale ASC, (p.portfolio_status='current') DESC, p.id DESC LIMIT 1), '') "
        "AS company "
        "FROM sa_pick_lineages l WHERE EXISTS ("
        " SELECT 1 FROM sa_alpha_picks p WHERE p.lineage_id=l.lineage_id)"
        + lineage_clause
        + " ORDER BY l.symbol_key, l.picked_date, l.lineage_id",
        tuple(params),
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "lineage_id": int(row["lineage_id"]),
            "symbol": row["symbol_key"],
            "company": row["company"],
        }
        events.append({
            **base,
            "role": "entry",
            "event_anchor_date": row["picked_date"],
            "reason_code": None,
        })
        closed_rows = conn.execute(
            "SELECT DISTINCT closed_date FROM sa_alpha_picks "
            "WHERE lineage_id=? AND portfolio_status='closed' "
            "ORDER BY (closed_date IS NULL), closed_date",
            (row["lineage_id"],),
        ).fetchall()
        for closed_row in closed_rows:
            anchor = capture_store.canon_date(closed_row["closed_date"])
            events.append({
                **base,
                "role": "exit",
                "event_anchor_date": anchor,
                "reason_code": None if anchor else "missing_event_anchor",
            })
    return events


def _find_event(
    conn: sqlite3.Connection,
    *,
    lineage_id: int,
    role: str,
    event_anchor_date: str | None,
) -> dict[str, Any]:
    canonical_anchor = capture_store.canon_date(event_anchor_date)
    matches = [
        event
        for event in list_events(conn, lineage_ids=[lineage_id])
        if event["role"] == role and event["event_anchor_date"] == canonical_anchor
    ]
    if len(matches) != 1:
        raise ValueError("reconciliation event not found or ambiguous")
    return matches[0]


def _current_link(
    conn: sqlite3.Connection,
    *,
    lineage_id: int,
    role: str,
    event_anchor_date: str | None,
) -> sqlite3.Row | None:
    if role == "entry":
        return conn.execute(
            "SELECT * FROM sa_pick_article_links "
            "WHERE lineage_id=? AND role='entry' AND revoked_at IS NULL",
            (lineage_id,),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM sa_pick_article_links "
        "WHERE lineage_id=? AND role='exit' AND event_anchor_date=? "
        "AND revoked_at IS NULL",
        (lineage_id, event_anchor_date),
    ).fetchone()


def _article_evidence(row: sqlite3.Row) -> ArticleEvidence:
    return ArticleEvidence(
        article_id=str(row["article_id"]),
        published_date=row["published_date"],
        title=row["title"] or "",
        body_markdown=row["body_markdown"],
        article_type=row["article_type"],
        list_ticker=row["list_ticker"],
        detail_ticker=row["detail_ticker"],
        has_content=bool(row["body_markdown"]),
    )


def _pick_event(event: dict[str, Any]) -> PickEvent:
    return PickEvent(
        lineage_id=int(event["lineage_id"]),
        symbol_key=str(event["symbol"]),
        company=str(event["company"] or ""),
        role=event["role"],
        event_anchor_date=event["event_anchor_date"],
    )


def _candidate_rows(
    conn: sqlite3.Connection,
    event: dict[str, Any],
    *,
    article_ids: Collection[str] | None = None,
    limit: int = MAX_CANDIDATES_PER_EVENT,
) -> list[sqlite3.Row]:
    anchor = event["event_anchor_date"]
    if not anchor:
        return []
    params: list[Any] = []
    predicates: list[str] = []
    if article_ids is not None:
        normalized_ids = sorted({str(value) for value in article_ids if str(value)})
        if not normalized_ids:
            return []
        predicates.append(f"a.article_id IN ({','.join('?' for _ in normalized_ids)})")
        params.extend(normalized_ids)
    predicates.append(
        "(ABS(julianday(a.published_date) - julianday(?)) <= 3 "
        " OR a.article_id IN (SELECT canonical_article_id FROM sa_alpha_picks "
        " WHERE lineage_id=? AND canonical_article_id IS NOT NULL))"
    )
    params.extend((anchor, event["lineage_id"]))
    params.append(max(1, min(int(limit), MAX_CANDIDATES_PER_EVENT)))
    return conn.execute(
        "SELECT a.* FROM sa_articles a WHERE "
        + " AND ".join(predicates)
        + " ORDER BY (a.published_date IS NULL), a.published_date DESC, a.article_id DESC "
        "LIMIT ?",
        tuple(params),
    ).fetchall()


def _rejected_ids(conn: sqlite3.Connection, event: dict[str, Any]) -> set[str]:
    if not event["event_anchor_date"]:
        return set()
    rows = conn.execute(
        "SELECT article_id FROM sa_pick_article_decisions "
        "WHERE lineage_id=? AND role=? AND event_anchor_date=? AND decision='rejected'",
        (event["lineage_id"], event["role"], event["event_anchor_date"]),
    ).fetchall()
    return {str(row[0]) for row in rows}


def _evaluation_for_article(
    conn: sqlite3.Connection,
    event: dict[str, Any],
    article_id: str,
) -> tuple[sqlite3.Row, CandidateEvaluation]:
    article = conn.execute(
        "SELECT * FROM sa_articles WHERE article_id=?", (article_id,)
    ).fetchone()
    if article is None:
        raise ValueError("article not found")
    return article, evaluate_candidate(_pick_event(event), _article_evidence(article))


def accept_link(
    conn: sqlite3.Connection,
    *,
    lineage_id: int,
    role: str,
    event_anchor_date: str,
    article_id: str,
    link_source: str,
    evidence_codes: Sequence[str],
    replace_link_id: int | None = None,
) -> dict[str, Any]:
    if role not in ("entry", "exit") or link_source not in ("auto", "user"):
        raise ValueError("invalid reconciliation link role or source")
    conn.execute("BEGIN IMMEDIATE")
    try:
        event = _find_event(
            conn,
            lineage_id=int(lineage_id),
            role=role,
            event_anchor_date=event_anchor_date,
        )
        if not event["event_anchor_date"]:
            raise ValueError("missing event anchor cannot be accepted")
        article, evaluation = _evaluation_for_article(conn, event, str(article_id))
        if link_source == "auto" and not evaluation.auto_eligible:
            raise ValueError("automatic link is not eligible")

        current = _current_link(
            conn,
            lineage_id=int(lineage_id),
            role=role,
            event_anchor_date=event["event_anchor_date"],
        )
        if current is not None and str(current["article_id"]) == str(article_id):
            conn.commit()
            return {
                "status": "ok",
                "link_id": int(current["link_id"]),
                "article_id": str(article_id),
                "idempotent": True,
                "warnings": [] if evaluation.auto_eligible else [evaluation.reason_code],
            }
        supersedes_link_id = None
        if current is not None:
            current_id = int(current["link_id"])
            if replace_link_id != current_id:
                raise ValueError("replace_link_id must match the active link")
            supersedes_link_id = current_id
            conn.execute(
                "UPDATE sa_pick_article_links SET revoked_at=? WHERE link_id=?",
                (capture_store.now_ts(), current_id),
            )

        reviewed_codes = tuple(str(value) for value in evidence_codes if str(value))
        if not reviewed_codes:
            reviewed_codes = evaluation.evidence_codes
        linked_at = capture_store.now_ts()
        cur = conn.execute(
            "INSERT INTO sa_pick_article_links "
            "(lineage_id, article_id, role, event_anchor_date, link_source, "
            "evidence_codes, supersedes_link_id, linked_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(lineage_id),
                str(article_id),
                role,
                event["event_anchor_date"],
                link_source,
                json.dumps(reviewed_codes),
                supersedes_link_id,
                linked_at,
            ),
        )
        link_id = int(cur.lastrowid)
        if role == "entry":
            if article["body_markdown"]:
                conn.execute(
                    "UPDATE sa_alpha_picks SET canonical_article_id=?, detail_report=?, "
                    "detail_fetched_at=?, updated_at=? WHERE lineage_id=?",
                    (
                        str(article_id),
                        article["body_markdown"],
                        article["detail_fetched_at"],
                        linked_at,
                        int(lineage_id),
                    ),
                )
            else:
                conn.execute(
                    "UPDATE sa_alpha_picks SET canonical_article_id=?, updated_at=? "
                    "WHERE lineage_id=?",
                    (str(article_id), linked_at, int(lineage_id)),
                )
        conn.commit()
        return {
            "status": "ok",
            "link_id": link_id,
            "article_id": str(article_id),
            "idempotent": False,
            "warnings": [] if evaluation.auto_eligible else [evaluation.reason_code],
        }
    except Exception:
        conn.rollback()
        raise


def reject_candidate(
    conn: sqlite3.Connection,
    *,
    lineage_id: int,
    role: str,
    event_anchor_date: str,
    article_id: str,
    reason_code: str,
) -> dict[str, Any]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        event = _find_event(
            conn,
            lineage_id=int(lineage_id),
            role=role,
            event_anchor_date=event_anchor_date,
        )
        if not event["event_anchor_date"]:
            raise ValueError("missing event anchor cannot be rejected")
        if conn.execute(
            "SELECT 1 FROM sa_articles WHERE article_id=?", (str(article_id),)
        ).fetchone() is None:
            raise ValueError("article not found")
        conn.execute(
            "INSERT OR IGNORE INTO sa_pick_article_decisions "
            "(lineage_id, article_id, role, event_anchor_date, decision, reason_code, decided_at) "
            "VALUES (?, ?, ?, ?, 'rejected', ?, ?)",
            (
                int(lineage_id),
                str(article_id),
                role,
                event["event_anchor_date"],
                str(reason_code),
                capture_store.now_ts(),
            ),
        )
        decision_id = conn.execute(
            "SELECT decision_id FROM sa_pick_article_decisions "
            "WHERE lineage_id=? AND article_id=? AND role=? AND event_anchor_date=?",
            (int(lineage_id), str(article_id), role, event["event_anchor_date"]),
        ).fetchone()[0]
        conn.commit()
        return {"status": "ok", "decision_id": int(decision_id), "idempotent": True}
    except Exception:
        conn.rollback()
        raise


def _decision(
    conn: sqlite3.Connection,
    event: dict[str, Any],
    *,
    article_ids: Collection[str] | None = None,
) -> tuple[Any, list[sqlite3.Row]]:
    rows = _candidate_rows(conn, event, article_ids=article_ids)
    rejected = _rejected_ids(conn, event)
    decision = decide_reconciliation(
        _pick_event(event),
        [_article_evidence(row) for row in rows],
        rejected_article_ids=rejected,
    )
    return decision, rows


def reconcile_events(
    conn: sqlite3.Connection,
    *,
    lineage_ids: Collection[int] | None,
    article_ids: Collection[str] | None,
    max_events: int,
    enrichment_limit: int,
) -> dict[str, Any]:
    event_limit = max(1, min(int(max_events), MAX_EVENTS_PER_RECONCILIATION))
    events = list_events(conn, lineage_ids=lineage_ids)
    selected: list[tuple[dict[str, Any], Any, list[sqlite3.Row]]] = []
    for event in events:
        if len(selected) >= event_limit:
            break
        if _current_link(
            conn,
            lineage_id=event["lineage_id"],
            role=event["role"],
            event_anchor_date=event["event_anchor_date"],
        ) is not None:
            continue
        decision, rows = _decision(conn, event, article_ids=article_ids)
        if article_ids is not None and not rows:
            continue
        selected.append((event, decision, rows))

    auto_linked = 0
    review_required = 0
    enrichment_rows: dict[str, tuple[str, str | None]] = {}
    for event, decision, rows in selected:
        by_id = {str(row["article_id"]): row for row in rows}
        if decision.accepted_article_id is not None:
            winner = next(
                row for row in decision.candidates
                if row.article_id == decision.accepted_article_id
            )
            accept_link(
                conn,
                lineage_id=event["lineage_id"],
                role=event["role"],
                event_anchor_date=event["event_anchor_date"],
                article_id=winner.article_id,
                link_source="auto",
                evidence_codes=winner.evidence_codes,
            )
            auto_linked += 1
        else:
            review_required += 1
        for candidate in decision.candidates:
            if candidate.needs_enrichment and candidate.article_id in by_id:
                row = by_id[candidate.article_id]
                enrichment_rows[candidate.article_id] = (
                    str(row["url"]),
                    row["published_date"],
                )

    ordered_enrichment = sorted(
        enrichment_rows.items(),
        key=lambda item: (item[1][1] or "", item[0]),
        reverse=True,
    )[:max(0, int(enrichment_limit))]
    return {
        "status": "ok",
        "events_scanned": len(selected),
        "auto_linked": auto_linked,
        "review_required": review_required,
        "enrichment": [
            {"article_id": article_id, "url": values[0]}
            for article_id, values in ordered_enrichment
        ],
    }


def _candidate_projection(
    row: sqlite3.Row,
    evaluation: CandidateEvaluation,
    *,
    current_link: sqlite3.Row | None,
) -> dict[str, Any]:
    return {
        "article_id": str(row["article_id"]),
        "url": str(row["url"]),
        "published_date": row["published_date"],
        "title": row["title"],
        "evidence_codes": list(evaluation.evidence_codes),
        "reason_code": evaluation.reason_code,
        "content_state": "complete" if row["body_markdown"] else "missing",
        "requires_confirmation": (
            not evaluation.auto_eligible
            or (
                current_link is not None
                and str(current_link["article_id"]) != str(row["article_id"])
            )
        ),
    }


def list_review_queue(conn: sqlite3.Connection, *, limit: int) -> dict[str, Any]:
    projected: list[dict[str, Any]] = []
    for event in list_events(conn):
        current = _current_link(
            conn,
            lineage_id=event["lineage_id"],
            role=event["role"],
            event_anchor_date=event["event_anchor_date"],
        )
        if current is not None:
            continue
        decision, rows = _decision(conn, event)
        by_id = {str(row["article_id"]): row for row in rows}
        candidates = [
            _candidate_projection(by_id[item.article_id], item, current_link=current)
            for item in decision.candidates
            if item.article_id in by_id
        ]
        reason_code = event["reason_code"] or decision.reason_code or "review_required"
        projected.append({
            "lineage_id": event["lineage_id"],
            "symbol": event["symbol"],
            "company": event["company"],
            "role": event["role"],
            "event_anchor_date": event["event_anchor_date"],
            "reason_code": reason_code,
            "current_link": None,
            "candidates": candidates,
        })
    total = len(projected)
    return {"events": projected[:max(0, int(limit))], "total": total}


def resolve_event(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    role: str,
    event_anchor_date: str,
) -> dict[str, Any]:
    symbol_key = normalize_symbol(symbol)
    anchor = capture_store.canon_date(event_anchor_date)
    if not symbol_key or role not in ("entry", "exit") or not anchor:
        return {"status": "event_not_found"}
    if role == "entry":
        rows = conn.execute(
            "SELECT lineage_id FROM sa_pick_lineages WHERE symbol_key=? AND picked_date=?",
            (symbol_key, anchor),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT l.lineage_id FROM sa_pick_lineages l "
            "JOIN sa_alpha_picks p ON p.lineage_id=l.lineage_id "
            "WHERE l.symbol_key=? AND p.portfolio_status='closed' AND p.closed_date=?",
            (symbol_key, anchor),
        ).fetchall()
    if not rows:
        return {"status": "event_not_found"}
    if len(rows) != 1:
        return {"status": "ambiguous_event"}
    return {
        "status": "ok",
        "lineage_id": int(rows[0][0]),
        "symbol": symbol_key,
        "role": role,
        "event_anchor_date": anchor,
    }


def preview_legacy_links(conn: sqlite3.Connection, *, limit: int) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT DISTINCT l.lineage_id, l.symbol_key, l.picked_date, "
        "p.canonical_article_id, a.* "
        "FROM sa_pick_lineages l "
        "JOIN sa_alpha_picks p ON p.lineage_id=l.lineage_id "
        "JOIN sa_articles a ON a.article_id=p.canonical_article_id "
        "WHERE p.canonical_article_id IS NOT NULL "
        "ORDER BY l.symbol_key, l.picked_date, a.article_id"
    ).fetchall()
    items = []
    for row in rows:
        company_row = conn.execute(
            "SELECT company FROM sa_alpha_picks WHERE lineage_id=? ORDER BY id DESC LIMIT 1",
            (row["lineage_id"],),
        ).fetchone()
        event = PickEvent(
            int(row["lineage_id"]),
            row["symbol_key"],
            company_row[0] if company_row else "",
            "entry",
            row["picked_date"],
        )
        evaluation = evaluate_candidate(event, _article_evidence(row))
        items.append({
            "lineage_id": int(row["lineage_id"]),
            "symbol": row["symbol_key"],
            "event_anchor_date": row["picked_date"],
            "article_id": str(row["canonical_article_id"]),
            "evidence_codes": list(evaluation.evidence_codes),
            "reason_code": evaluation.reason_code,
        })
    return {"items": items[:max(0, int(limit))], "total": len(items)}
