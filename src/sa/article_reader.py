"""Read bounded article/comment evidence from one consistent local snapshot."""

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from src.sa.comment_scope import read_policy

from src.tools.retained_read_results import (
    RetainedReadFailure, bounded_result, canonical_json, page_integer, require,
    valid_snapshot_id,
)


_ARTICLE_COLUMNS = (
    "article_id, url, title, ticker, author, published_date, article_type, body_markdown, "
    "detail_fetched_at, comments_fetched_at, comments_count, comments_count_observed_at, "
    "provider_comments_count_at_last_scan, comment_recovery_state, "
    "comment_recovery_last_terminal_reason"
)
_OPTIONAL_SCAN_COLUMNS = ("comment_backfill_pending", "comment_scan_attempted_at", "comment_scan_stop_reason", "comment_scan_policy")
_COMMENT_COLUMNS = (
    "comment_id, parent_comment_id, commenter, comment_text, upvotes, comment_date, fetched_at"
)
_COMMENT_ORDER = "(comment_date IS NULL), comment_date, comment_id"


def article_unavailable(code):
    return {"status": "unavailable", "error_code": code,
            "provider": "seeking_alpha", "retrieval": "stored"}


def read_article(
    db_path, article_id, *, body_offset=0, body_limit=4000,
    comment_offset=0, comment_limit=2, comment_id=None,
    comment_text_offset=0, comment_text_limit=500, snapshot_id=None,
):
    try:
        require(type(article_id) is str and 0 < len(article_id) <= 256, "sa_article_id_invalid")
        require(comment_id is None or (type(comment_id) is str and 0 < len(comment_id) <= 256),
                "sa_article_comment_id_invalid")
        require(all(page_integer(v) for v in (body_offset, body_limit, comment_offset, comment_limit, comment_text_offset))
                and page_integer(comment_text_limit, minimum=1), "sa_article_pagination_invalid")
        require(valid_snapshot_id(snapshot_id), "sa_article_snapshot_id_invalid")
        require(not (body_offset or comment_offset or comment_text_offset) or snapshot_id is not None,
                "sa_article_snapshot_required")
        require(comment_id is not None or comment_text_offset == 0, "sa_article_comment_id_required")
        require(comment_id is None or (comment_offset == 0 and comment_limit > 0), "sa_article_pagination_invalid")
        require(body_limit > 0 or comment_limit > 0, "sa_article_pagination_invalid")
        path = Path(db_path)
        if not path.is_file():
            return article_unavailable("sa_article_capture_missing")
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sa_articles)")}
            scan_columns = ", ".join(
                column if column in columns else f"NULL AS {column}"
                for column in _OPTIONAL_SCAN_COLUMNS
            )
            row = conn.execute(f"SELECT {_ARTICLE_COLUMNS}, {scan_columns} FROM sa_articles WHERE article_id=?", (article_id,)).fetchone()
            if row is None:
                return article_unavailable("sa_article_not_found")
            article = dict(row)
            # Hash all served fields, not row counts or acquisition timestamps alone:
            # comment edits and upvote changes also invalidate continuation pages.
            hasher = hashlib.sha256(canonical_json({"version": 1, "article": article}).encode("utf-8"))
            count = 0
            for comment in conn.execute(
                f"SELECT {_COMMENT_COLUMNS} FROM sa_article_comments WHERE article_id=? ORDER BY {_COMMENT_ORDER}",
                (article_id,),
            ):
                hasher.update(b"\n" + canonical_json(dict(comment)).encode("utf-8"))
                count += 1
            current_id = hasher.hexdigest()
            require(snapshot_id is None or snapshot_id == current_id, "sa_article_snapshot_changed")
            body = article.pop("body_markdown") or ""
            require(body_offset <= len(body) and comment_offset <= count, "sa_article_offset_out_of_range")
            selected = " AND comment_id=?" if comment_id is not None else ""
            params = (article_id, comment_id) if comment_id is not None else (article_id,)
            rows = conn.execute(
                f"SELECT {_COMMENT_COLUMNS} FROM sa_article_comments WHERE article_id=?{selected} "
                f"ORDER BY {_COMMENT_ORDER} LIMIT ? OFFSET ?",
                params + ((1 if comment_id is not None else comment_limit), comment_offset),
            ).fetchall()
            require(comment_id is None or bool(rows), "sa_article_comment_not_found")
            comments = []
            for row in rows:
                comment = dict(row)
                text = comment["comment_text"]
                require(comment_text_offset <= len(text), "sa_article_offset_out_of_range")
                end = min(len(text), comment_text_offset + comment_text_limit)
                parent = comment["parent_comment_id"]
                comment.update(
                    comment_text=text[comment_text_offset:end], text_offset=comment_text_offset,
                    total_characters=len(text), next_text_offset=end if end < len(text) else None,
                    text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    parent_in_store=bool(conn.execute(
                        "SELECT 1 FROM sa_article_comments WHERE article_id=? AND comment_id=?", (article_id, parent),
                    ).fetchone()) if parent else None,
                )
                comments.append(comment)
            coverage = _coverage(article, body, count)
            result = {
                **article, "status": "ok", "provider": "seeking_alpha", "retrieval": "stored",
                "snapshot_id": current_id, "body_markdown": body[body_offset:body_offset + body_limit],
                "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                "comments": comments, "coverage": coverage,
                "pagination": {
                    "text_offset_unit": "unicode_codepoint", "body_offset": body_offset,
                    "body_characters": min(body_limit, len(body) - body_offset),
                    "total_body_characters": len(body),
                    "next_body_offset": body_offset + body_limit if body_limit and body_offset + body_limit < len(body) else None,
                    "comment_offset": comment_offset, "comment_count": len(comments), "total_comments": count,
                    "next_comment_offset": comment_offset + len(comments) if comment_id is None and comments and comment_offset + len(comments) < count else None,
                    "selected_comment_id": comment_id,
                },
                "source_ref": {"provider": "seeking_alpha", "article_id": article_id,
                               "url": article["url"], "snapshot_id": current_id},
                "limitations": ["retained_capture_not_live", "comments_are_unverified_opinions",
                                "snapshot_id_detects_changes_not_historical_archive"],
            }
            return bounded_result("get_sa_article_detail", result)
    except RetainedReadFailure as exc:
        return article_unavailable(exc.code)
    except (sqlite3.Error, OSError):
        return article_unavailable("sa_article_store_unavailable")


def _coverage(article, body, count):
    reasons = []
    state = article["comment_recovery_state"]
    if article.get("comment_backfill_pending"):
        reasons.append("comment_backfill_pending")
    if state != "repaired":
        reasons.append("comment_recovery_" + state)
    if not article["comments_fetched_at"]:
        reasons.append("comment_scan_time_unknown")
    observed = article["provider_comments_count_at_last_scan"]
    listed = article["comments_count"]
    if any(type(value) is int and value > count for value in (observed, listed)):
        reasons.append("provider_count_exceeds_stored")
    if count:
        status = "partial" if reasons else "captured"
    elif reasons:
        status = "not_captured" if not article["comments_fetched_at"] and not listed else "partial"
    else:
        status = "observed_empty" if observed == 0 else "unknown"
    return {
        "body": {"status": "available" if body.strip() else "not_captured",
                 "fetched_at": article["detail_fetched_at"]},
        "comments": {"status": status, "stored_count": count, "complete": None,
                     "backfill_pending": bool(article.get("comment_backfill_pending")),
                     "scan_attempted_at": article.get("comment_scan_attempted_at"),
                     "scan_stop_reason": article.get("comment_scan_stop_reason"),
                     "scan_policy": read_policy(article.get("comment_scan_policy")),
                     "fetched_at": article["comments_fetched_at"], "gap_reasons": reasons,
                     "completeness_basis": "provider_counts_and_capture_times_do_not_prove_exhaustion"},
    }
