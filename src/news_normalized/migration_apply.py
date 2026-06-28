"""Transaction-local writer and validators for the N7 normalized-news plan."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import groupby
import json
from pathlib import Path
import sqlite3
from typing import Iterable

import pyarrow.parquet as pq

from .body_policy import prepare_body
from .cleaner import looks_like_html
from .identity import normalize_identity_text
from .migration import ResolvedMigrationPlan
from .migration_policy import BodyEvidenceRef
from .models import BodyStatus


class MigrationValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MigrationApplyResult:
    run_id: int
    resolved_fingerprint: str
    counts: dict[str, int]
    already_applied: bool = False


def read_body_evidence_batch(
    refs: Iterable[BodyEvidenceRef],
) -> dict[BodyEvidenceRef, str]:
    """Read each referenced Parquet row group once and verify every body digest."""
    ordered = sorted(
        set(refs),
        key=lambda ref: (
            ref.source_path,
            ref.row_group,
            ref.row_index,
            ref.body_sha256,
        ),
    )
    result: dict[BodyEvidenceRef, str] = {}
    parquet_files: dict[str, pq.ParquetFile] = {}
    for (source_path, row_group), grouped in groupby(
        ordered, key=lambda ref: (ref.source_path, ref.row_group)
    ):
        parquet = parquet_files.setdefault(source_path, pq.ParquetFile(source_path))
        available = set(parquet.schema.names)
        columns = [name for name in ("content", "description") if name in available]
        table = parquet.read_row_group(row_group, columns=columns)
        for ref in grouped:
            if ref.row_index < 0 or ref.row_index >= table.num_rows:
                raise MigrationValidationError("body evidence row locator changed")
            row = table.slice(ref.row_index, 1).to_pylist()[0]
            raw = str(row.get("content") or row.get("description") or "")
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if digest != ref.body_sha256:
                raise MigrationValidationError("body evidence digest changed")
            result[ref] = raw
    return result


def _insert_active_body(
    conn: sqlite3.Connection,
    article_id: int,
    source: str,
    status: BodyStatus,
    attempts: int,
    reference: BodyEvidenceRef | None,
    raw_bodies: dict[BodyEvidenceRef, str],
    applied_at: str,
) -> None:
    if reference is None:
        conn.execute(
            "INSERT INTO news_article_bodies "
            "(article_id,body_status,fetch_attempts) VALUES (?,?,?)",
            (article_id, status.value, attempts),
        )
        return
    raw = raw_bodies[reference]
    raw_format = "html" if looks_like_html(raw) else "text"
    prepared = prepare_body(
        raw,
        raw_format=raw_format,
        source=source,
        retrieval_method="parquet_backfill",
        retrieval_source=source,
        fetched_at=reference.fetched_at,
        evidence_ref=(
            f"{reference.source_path}#rg={reference.row_group}&row={reference.row_index}"
        ),
    )
    if (
        len(raw) != reference.raw_length
        or len(prepared.body_text or "") != reference.clean_length
        or (prepared.clean_error is None and bool(prepared.body_text))
        != reference.cleaner_ok
    ):
        raise MigrationValidationError("body evidence cleaning inputs changed")
    conn.execute(
        "INSERT INTO news_article_bodies "
        "(article_id,body_status,raw_body,raw_format,body_text,body_sha256,"
        "cleaner_version,retrieval_method,retrieval_source,fetch_attempts,fetched_at,"
        "cleaned_at,clean_error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            article_id,
            BodyStatus.FETCHED.value,
            prepared.raw_body,
            prepared.raw_format,
            prepared.body_text,
            prepared.body_sha256,
            prepared.cleaner_version,
            prepared.retrieval_method,
            prepared.retrieval_source,
            attempts,
            prepared.fetched_at,
            applied_at if prepared.clean_error is None else None,
            prepared.clean_error,
        ),
    )


def _insert_cold_body(
    conn: sqlite3.Connection,
    article_id: int,
    source: str,
    reference: BodyEvidenceRef,
    raw_bodies: dict[BodyEvidenceRef, str],
    applied_at: str,
) -> None:
    raw = raw_bodies[reference]
    raw_format = "html" if looks_like_html(raw) else "text"
    prepared = prepare_body(
        raw,
        raw_format=raw_format,
        source=source,
        retrieval_method="parquet_backfill",
        retrieval_source=source,
        fetched_at=reference.fetched_at,
        evidence_ref=(
            f"{reference.source_path}#rg={reference.row_group}&row={reference.row_index}"
        ),
    )
    if (
        len(raw) != reference.raw_length
        or len(prepared.body_text or "") != reference.clean_length
        or (prepared.clean_error is None and bool(prepared.body_text))
        != reference.cleaner_ok
    ):
        raise MigrationValidationError("body evidence cleaning inputs changed")
    conn.execute(
        "INSERT INTO news_article_body_variants "
        "(article_id,body_sha256,raw_body,raw_format,body_text,cleaner_version,"
        "retrieval_method,retrieval_source,fetched_at,evidence_ref,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            article_id,
            prepared.body_sha256,
            prepared.raw_body,
            prepared.raw_format,
            prepared.body_text,
            prepared.cleaner_version,
            prepared.retrieval_method,
            prepared.retrieval_source,
            prepared.fetched_at,
            prepared.evidence_ref,
            applied_at,
        ),
    )


def write_resolved_plan(
    conn: sqlite3.Connection,
    plan: ResolvedMigrationPlan,
    backup_path: str,
    applied_at: str,
) -> MigrationApplyResult:
    """Write one reviewed plan inside the caller's open transaction."""
    if not plan.preview.would_apply or plan.preview.remaining_blockers:
        raise MigrationValidationError("resolved plan still has blockers")
    existing = conn.execute(
        "SELECT id,counts_json FROM news_normalization_runs "
        "WHERE resolved_fingerprint=?",
        (plan.preview.resolved_fingerprint,),
    ).fetchone()
    if existing is not None:
        counts = json.loads(existing[1])
        if counts != plan.preview.counts:
            raise MigrationValidationError("existing migration counts differ")
        validate_applied_plan(conn, plan)
        return MigrationApplyResult(
            run_id=int(existing[0]),
            resolved_fingerprint=plan.preview.resolved_fingerprint,
            counts=counts,
            already_applied=True,
        )

    refs = tuple(
        reference
        for article in plan.articles
        for reference in ((article.active_body,) + article.cold_bodies)
        if reference is not None
    )
    raw_bodies = read_body_evidence_batch(refs)
    run = conn.execute(
        "INSERT INTO news_normalization_runs "
        "(policy_version,input_fingerprint,resolved_fingerprint,"
        "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            plan.preview.policy_version,
            plan.preview.input_fingerprint,
            plan.preview.resolved_fingerprint,
            plan.preview.rejection_evidence.fingerprint,
            json.dumps(plan.preview.counts, sort_keys=True, separators=(",", ":")),
            backup_path,
            applied_at,
        ),
    )
    run_id = int(run.lastrowid)
    article_ids: dict[str, int] = {}
    for article in sorted(plan.articles, key=lambda item: (item.source, item.identity)):
        cursor = conn.execute(
            "INSERT INTO news_articles "
            "(source,provider_article_id,canonical_title,publisher,url,published_at,"
            "content_kind,sentiment_score,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                article.source,
                article.canonical_provider_id,
                article.canonical_title,
                article.publisher,
                article.url,
                article.published_at,
                "full_text"
                if article.body_status is BodyStatus.FETCHED
                else "unknown",
                article.sentiment_value,
                applied_at,
                applied_at,
            ),
        )
        article_id = int(cursor.lastrowid)
        article_ids[article.identity] = article_id
        conn.executemany(
            "INSERT INTO news_article_keys "
            "(article_id,source,key_kind,key_value,created_at) VALUES (?,?,?,?,?)",
            [
                (article_id, key.source, key.kind.value, key.value, applied_at)
                for key in article.identity_keys
            ],
        )
        conn.executemany(
            "INSERT INTO news_article_tickers "
            "(article_id,ticker,relation_kind,first_seen_at,last_seen_at) "
            "VALUES (?,?,?,?,?)",
            [
                (article_id, ticker, kind, applied_at, applied_at)
                for ticker, kind in article.ticker_relations
            ],
        )
        conn.executemany(
            "INSERT INTO news_article_titles "
            "(article_id,title,normalized_title,observed_at,observed_with_body) "
            "VALUES (?,?,?,?,?)",
            [
                (
                    article_id,
                    title,
                    normalize_identity_text(title),
                    None,
                    int(
                        article.active_body is not None
                        and title == article.canonical_title
                    ),
                )
                for title in article.titles
            ],
        )
        _insert_active_body(
            conn,
            article_id,
            article.source,
            article.body_status,
            article.fetch_attempts,
            article.active_body,
            raw_bodies,
            applied_at,
        )
        for reference in article.cold_bodies:
            _insert_cold_body(
                conn,
                article_id,
                article.source,
                reference,
                raw_bodies,
                applied_at,
            )
        body_text = conn.execute(
            "SELECT COALESCE(body_text,'') FROM news_article_bodies WHERE article_id=?",
            (article_id,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO news_search_documents(article_id,title,body_text) "
            "VALUES (?,?,?)",
            (article_id, article.canonical_title, body_text),
        )

    for resolution in plan.legacy_resolutions:
        article_id = (
            article_ids[resolution.article_identity]
            if resolution.article_identity is not None
            else None
        )
        conn.execute(
            "INSERT INTO news_legacy_migration_map "
            "(legacy_news_id,article_id,resolution_kind,rejection_reason,"
            "migration_run_id,migration_fingerprint) VALUES (?,?,?,?,?,?)",
            (
                resolution.legacy_news_id,
                article_id,
                resolution.resolution_kind,
                resolution.rejection_reason,
                run_id,
                plan.preview.resolved_fingerprint,
            ),
        )
    return MigrationApplyResult(
        run_id=run_id,
        resolved_fingerprint=plan.preview.resolved_fingerprint,
        counts=dict(plan.preview.counts),
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def validate_applied_plan(
    conn: sqlite3.Connection, plan: ResolvedMigrationPlan
) -> None:
    """Validate all transaction-local postconditions before the caller commits."""
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise MigrationValidationError("SQLite quick_check failed")
    expected = plan.preview.counts
    exact_counts = {
        "articles": _count(conn, "news_articles"),
        "identity_keys": _count(conn, "news_article_keys"),
        "ticker_relations": _count(conn, "news_article_tickers"),
        "titles": _count(conn, "news_article_titles"),
        "legacy_rows": _count(conn, "news_legacy_migration_map"),
        "active_bodies": int(
            conn.execute(
                "SELECT COUNT(*) FROM news_article_bodies "
                "WHERE body_status='fetched'"
            ).fetchone()[0]
        ),
        "body_fetched": int(
            conn.execute(
                "SELECT COUNT(*) FROM news_article_bodies "
                "WHERE body_status='fetched'"
            ).fetchone()[0]
        ),
        "body_failed": int(
            conn.execute(
                "SELECT COUNT(*) FROM news_article_bodies WHERE body_status='failed'"
            ).fetchone()[0]
        ),
        "body_pending": int(
            conn.execute(
                "SELECT COUNT(*) FROM news_article_bodies WHERE body_status='pending'"
            ).fetchone()[0]
        ),
        "body_variant_groups": int(
            conn.execute(
                "SELECT COUNT(DISTINCT article_id) FROM news_article_body_variants"
            ).fetchone()[0]
        ),
        "cold_body_variants": _count(conn, "news_article_body_variants"),
        "fts_documents": _count(conn, "news_search_documents"),
    }
    for key, actual in exact_counts.items():
        if actual != expected[key]:
            raise MigrationValidationError(
                f"applied count mismatch for {key}: {actual} != {expected[key]}"
            )
    if _count(conn, "news_article_bodies") != expected["articles"]:
        raise MigrationValidationError("each article must have one body-state row")
    legacy_count = _count(conn, "news")
    if legacy_count != expected["legacy_rows"]:
        raise MigrationValidationError("not every legacy row is accounted for")
    rejected = conn.execute(
        "SELECT COUNT(*) FROM news_legacy_migration_map WHERE article_id IS NULL"
    ).fetchone()[0]
    if rejected != expected["legacy_rejected"]:
        raise MigrationValidationError("legacy rejection count changed")
    mapped = conn.execute(
        "SELECT COUNT(*) FROM news_legacy_migration_map WHERE article_id IS NOT NULL"
    ).fetchone()[0]
    if mapped != expected["legacy_mapped"]:
        raise MigrationValidationError("legacy mapped count changed")
    run = conn.execute(
        "SELECT COUNT(*) FROM news_normalization_runs WHERE resolved_fingerprint=?",
        (plan.preview.resolved_fingerprint,),
    ).fetchone()[0]
    if run != 1:
        raise MigrationValidationError("migration run fingerprint is missing or duplicated")
    bad_map_fingerprint = conn.execute(
        "SELECT COUNT(*) FROM news_legacy_migration_map "
        "WHERE migration_fingerprint<>?",
        (plan.preview.resolved_fingerprint,),
    ).fetchone()[0]
    if bad_map_fingerprint:
        raise MigrationValidationError("legacy map fingerprint differs from plan")
    if conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='url'"
    ).fetchone()[0]:
        raise MigrationValidationError("Polygon URL remained a strong key")
    if conn.execute(
        "SELECT COUNT(*) FROM news_article_body_variants v "
        "JOIN news_article_bodies b ON b.article_id=v.article_id "
        "WHERE b.body_sha256=v.body_sha256"
    ).fetchone()[0]:
        raise MigrationValidationError("active body also appears as cold variant")
    if conn.execute(
        "SELECT COUNT(*) FROM news_search_documents d "
        "JOIN news_article_bodies b ON b.article_id=d.article_id "
        "WHERE d.body_text<>COALESCE(b.body_text,'')"
    ).fetchone()[0]:
        raise MigrationValidationError("search projection differs from active body")
    missing_fts = conn.execute(
        "SELECT COUNT(*) FROM (SELECT article_id FROM news_search_documents "
        "EXCEPT SELECT rowid FROM news_articles_fts)"
    ).fetchone()[0]
    orphan_fts = conn.execute(
        "SELECT COUNT(*) FROM (SELECT rowid FROM news_articles_fts "
        "EXCEPT SELECT article_id FROM news_search_documents)"
    ).fetchone()[0]
    if missing_fts or orphan_fts:
        raise MigrationValidationError("FTS projection has missing or orphan rows")
    invalid_bodies = conn.execute(
        "SELECT COUNT(*) FROM news_article_bodies WHERE "
        "(body_status='fetched' AND (raw_body IS NULL OR body_sha256 IS NULL)) OR "
        "(body_status<>'fetched' AND (raw_body IS NOT NULL OR body_sha256 IS NOT NULL)) OR "
        "(body_status='pending' AND fetch_attempts<>0) OR "
        "(body_status='failed' AND fetch_attempts=0)"
    ).fetchone()[0]
    if invalid_bodies:
        raise MigrationValidationError("body-state invariants failed")
