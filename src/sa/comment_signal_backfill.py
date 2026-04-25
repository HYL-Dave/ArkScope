"""Backfill / incremental extraction job for SA comment signals.

Reads ``sa_article_comments``, applies ``CommentSignalExtractor``, writes
to ``sa_comment_signals`` (sql/012). Default mode extracts only the
pending tail (comments without a signal row at the current rule-set
version), so incremental runs are cheap.

Universe = watchlist tickers (from user_profile.yaml via DAL) ∪ all
Alpha Picks symbols (current and closed). Symbols outside this universe
become ``candidate_mentions`` rather than ``ticker_mentions``.

Wired into ``src/service/jobs.py`` as the ``extract_sa_comment_signals``
job so each run lands in ``job_runs`` (sql/011) for observability.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

import psycopg2
import psycopg2.extras

from src.sa.comment_signals import (
    RULE_SET_VERSION,
    CommentSignalExtractor,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------


def build_ticker_universe(dal: Any) -> Set[str]:
    """Combine watchlist + all-time Alpha Picks symbols into one set.

    Empty set is acceptable — extractor degrades to all candidates being
    ``candidate_mentions``. Failures in any source are logged, not raised.
    """
    universe: Set[str] = set()

    try:
        wl = dal.get_watchlist(include_sectors=False)
        for t in getattr(wl, "tickers", []) or []:
            if t:
                universe.add(t.upper())
    except Exception as exc:
        logger.warning("build_ticker_universe: watchlist read failed: %s", exc)

    backend = getattr(dal, "_backend", None)
    if backend is not None and hasattr(backend, "_get_conn"):
        try:
            conn = backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT symbol FROM sa_alpha_picks WHERE symbol IS NOT NULL"
                )
                rows = cur.fetchall()
            for row in rows:
                if row[0]:
                    universe.add(row[0].upper())
        except Exception as exc:
            logger.warning("build_ticker_universe: alpha picks read failed: %s", exc)

    return universe


# ---------------------------------------------------------------------------
# Backfill / incremental extraction
# ---------------------------------------------------------------------------


def run_backfill(
    dal: Any,
    *,
    batch_size: int = 500,
    max_extracted: Optional[int] = None,
    rule_set_version: str = RULE_SET_VERSION,
) -> Dict[str, Any]:
    """Extract signals for all pending comments and upsert into the table.

    Args:
        dal: DataAccessLayer; must be backed by a DatabaseBackend.
        batch_size: rows per fetch loop. 500 is a sweet spot for psycopg2
            on the remote DB (low memory, low round-trip count).
        max_extracted: optional cap so an ad-hoc CLI run can short-circuit
            after N rows for testing.
        rule_set_version: pins the run; pending = comments without a row
            at this version.

    Returns:
        Dict with extracted_count, total_pending, universe_size,
        rule_set_version, batch_count, sample_high_score (highest score
        seen this run, for sanity checking).
    """
    backend = getattr(dal, "_backend", None)
    if backend is None or not hasattr(backend, "_get_conn"):
        return {
            "error": "DB unavailable (DAL is not on DatabaseBackend)",
            "extracted_count": 0,
            "total_pending": 0,
            "universe_size": 0,
            "rule_set_version": rule_set_version,
            "batch_count": 0,
        }

    universe = build_ticker_universe(dal)
    extractor = CommentSignalExtractor(
        universe=universe, rule_set_version=rule_set_version,
    )

    conn = backend._get_conn()
    total_pending = _count_pending(conn, rule_set_version)
    if total_pending == 0:
        return {
            "extracted_count": 0,
            "total_pending": 0,
            "universe_size": len(universe),
            "rule_set_version": rule_set_version,
            "batch_count": 0,
            "sample_high_score": 0.0,
        }

    extracted = 0
    batch_count = 0
    sample_high_score = 0.0
    last_id = 0

    while True:
        rows = _fetch_pending_batch(
            conn, last_id=last_id, limit=batch_size,
            rule_set_version=rule_set_version,
        )
        if not rows:
            break

        for row in rows:
            row_id, article_id, comment_id, text, upvotes = row
            signals = extractor.extract(text or "", upvotes=upvotes or 0)
            _upsert_signal(
                conn,
                row_id=row_id,
                article_id=article_id,
                comment_id=comment_id,
                signals=signals,
            )
            extracted += 1
            sample_high_score = max(sample_high_score, signals.high_value_score)
            last_id = max(last_id, row_id)

        batch_count += 1
        if max_extracted is not None and extracted >= max_extracted:
            logger.info("run_backfill: max_extracted=%d reached", max_extracted)
            break

    return {
        "extracted_count": extracted,
        "total_pending": total_pending,
        "universe_size": len(universe),
        "rule_set_version": rule_set_version,
        "batch_count": batch_count,
        "sample_high_score": sample_high_score,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _count_pending(conn, rule_set_version: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM sa_article_comments c
            WHERE NOT EXISTS (
                SELECT 1 FROM sa_comment_signals s
                WHERE s.comment_row_id = c.id
                  AND s.rule_set_version = %s
            )
            """,
            (rule_set_version,),
        )
        return int(cur.fetchone()[0])


def _fetch_pending_batch(conn, *, last_id: int, limit: int, rule_set_version: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.article_id, c.comment_id, c.comment_text, c.upvotes
            FROM sa_article_comments c
            WHERE c.id > %s
              AND NOT EXISTS (
                  SELECT 1 FROM sa_comment_signals s
                  WHERE s.comment_row_id = c.id
                    AND s.rule_set_version = %s
              )
            ORDER BY c.id
            LIMIT %s
            """,
            (last_id, rule_set_version, limit),
        )
        return cur.fetchall()


def _upsert_signal(
    conn,
    *,
    row_id: int,
    article_id: str,
    comment_id: str,
    signals,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sa_comment_signals (
                comment_row_id, article_id, comment_id,
                ticker_mentions, candidate_mentions, keyword_buckets,
                high_value_score, needs_verification, rule_set_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (comment_row_id) DO UPDATE SET
                ticker_mentions    = EXCLUDED.ticker_mentions,
                candidate_mentions = EXCLUDED.candidate_mentions,
                keyword_buckets    = EXCLUDED.keyword_buckets,
                high_value_score   = EXCLUDED.high_value_score,
                needs_verification = EXCLUDED.needs_verification,
                rule_set_version   = EXCLUDED.rule_set_version,
                extracted_at       = NOW()
            """,
            (
                row_id, article_id, comment_id,
                signals.ticker_mentions,
                signals.candidate_mentions,
                psycopg2.extras.Json(signals.keyword_buckets),
                float(signals.high_value_score),
                bool(signals.needs_verification),
                signals.rule_set_version,
            ),
        )