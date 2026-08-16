"""Backfill / incremental extraction job for SA comment signals.

Reads ``sa_article_comments``, applies ``CommentSignalExtractor``, writes
to ``sa_comment_signals``. Default mode extracts only the
pending tail (comments without a signal row at the current rule-set
version), so incremental runs are cheap.

Universe = watchlist tickers (from user_profile.yaml via DAL) ∪ all
Alpha Picks symbols (current and closed). Symbols outside this universe
become ``candidate_mentions`` rather than ``ticker_mentions``.

Wired into ``src/service/jobs.py`` as the ``extract_sa_comment_signals``
job so each run lands in the local ``job_runs`` store for observability.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

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
    if backend is not None:
        try:
            from src import sa_capture_store as store

            conn = store.connect(backend._sa_db, read_only=True)
            try:
                rows = conn.execute(
                    "SELECT DISTINCT symbol FROM sa_alpha_picks WHERE symbol IS NOT NULL"
                ).fetchall()
            finally:
                conn.close()
            for row in rows:
                if row[0]:
                    universe.add(row[0].upper())
        except Exception as exc:
            logger.warning("build_ticker_universe: local Alpha Picks read failed: %s", exc)

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
        dal: DataAccessLayer backed by the current local capability.
        batch_size: rows per local transaction.
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
    if backend is None:
        return {
            "error": "SA capture local backend unavailable",
            "extracted_count": 0,
            "total_pending": 0,
            "universe_size": 0,
            "rule_set_version": rule_set_version,
            "batch_count": 0,
        }

    try:
        sa_db = backend._sa_db
    except AttributeError:
        return {
            "error": "SA capture local backend unavailable",
            "extracted_count": 0,
            "total_pending": 0,
            "universe_size": 0,
            "rule_set_version": rule_set_version,
            "batch_count": 0,
        }
    return _run_backfill_sqlite(
        dal,
        sa_db,
        batch_size=batch_size,
        max_extracted=max_extracted,
        rule_set_version=rule_set_version,
    )


# ---------------------------------------------------------------------------
# Extract into sa_capture.db through the store choke point
# ---------------------------------------------------------------------------


def _run_backfill_sqlite(
    dal: Any,
    sa_db: str,
    *,
    batch_size: int,
    max_extracted: Optional[int],
    rule_set_version: str,
) -> Dict[str, Any]:
    """Read and write comment signals through the local capture store.

    The loop
    sa_capture.db through the sa_capture_store signal API. Each batch is one
    transaction (``with conn:``) so scalar + junction writes commit together;
    a crash rolls back the whole batch (re-extracted on rerun), never a
    half-updated comment.
    """
    from src import sa_capture_store as store

    universe = build_ticker_universe(dal)
    extractor = CommentSignalExtractor(
        universe=universe, rule_set_version=rule_set_version,
    )
    conn = store.connect(sa_db)
    try:
        total_pending = store.count_pending_signals(conn, rule_set_version)
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
        cap_reached = False

        while not cap_reached:
            rows = store.fetch_pending_comments(
                conn, last_id=last_id, limit=batch_size,
                rule_set_version=rule_set_version,
            )
            if not rows:
                break

            with conn:  # batch-atomic (refinement #3)
                for row in rows:
                    row_id, article_id, comment_id, text, upvotes = row
                    signals = extractor.extract(text or "", upvotes=upvotes or 0)
                    store.upsert_comment_signal(
                        conn, row_id=row_id, article_id=article_id,
                        comment_id=comment_id, signals=signals,
                    )
                    extracted += 1
                    sample_high_score = max(sample_high_score, signals.high_value_score)
                    last_id = max(last_id, row_id)
                    if max_extracted is not None and extracted >= max_extracted:
                        cap_reached = True
                        break

            batch_count += 1

        return {
            "extracted_count": extracted,
            "total_pending": total_pending,
            "universe_size": len(universe),
            "rule_set_version": rule_set_version,
            "batch_count": batch_count,
            "sample_high_score": sample_high_score,
        }
    finally:
        conn.close()
