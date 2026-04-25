#!/home/hyl/.virtualenvs/llm_app/bin/python3
"""
Native Messaging host for SA Alpha Picks Chrome extension.

Chrome launches this script via stdin/stdout pipe when the extension calls
chrome.runtime.sendNativeMessage(). Each invocation is a fresh process.

Message format: 4-byte little-endian length prefix + UTF-8 JSON body.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone

# Fix cwd — Chrome starts native hosts with unpredictable cwd.
# DAL and config use relative paths (data/cache/seeking_alpha/, config/user_profile.yaml).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

# Ensure log directory exists BEFORE configuring logging
_log_dir = os.path.join(PROJECT_ROOT, "data", "logs")
os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(_log_dir, "sa_native_host.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def read_message():
    """Read a Native Messaging message from stdin."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    length = struct.unpack("=I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data)


def write_message(msg):
    """Write a Native Messaging message to stdout."""
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def handle_message(msg):
    """Process a message from the extension."""
    from src.tools.data_access import DataAccessLayer

    action = msg.get("action")
    scope = msg.get("scope")

    # batch_ts from extension (shared across scopes), fallback to now()
    batch_ts_str = msg.get("batch_ts")
    if batch_ts_str:
        # JS Date.toISOString() outputs trailing Z; Python 3.10 fromisoformat can't parse Z
        attempt_ts = datetime.fromisoformat(batch_ts_str.replace("Z", "+00:00"))
    else:
        attempt_ts = datetime.now(tz=timezone.utc)

    dal = DataAccessLayer(db_dsn="auto")

    if action == "refresh":
        return _handle_refresh(dal, scope, msg.get("picks", []), attempt_ts)

    elif action == "refresh_failure":
        return _handle_failure(dal, scope, attempt_ts, msg.get("error", "unknown"))

    elif action == "check_detail_cache":
        return _handle_check_detail_cache(
            dal, msg.get("picks", []), msg.get("articles", [])
        )

    elif action == "save_detail":
        return _handle_save_detail(dal, msg)

    elif action == "save_detail_by_symbol":
        return _handle_save_detail_by_symbol(dal, msg)

    elif action == "save_articles_meta":
        return _handle_save_articles_meta(dal, msg)

    elif action == "save_market_news":
        return _handle_save_market_news(dal, msg)

    elif action == "get_market_news_recent_ids":
        return _handle_get_market_news_recent_ids(dal, msg)

    elif action == "save_market_news_detail":
        return _handle_save_market_news_detail(dal, msg)

    elif action == "save_article_content":
        return _handle_save_article_content(dal, msg)

    elif action == "save_comments_only":
        return _handle_save_comments_only(dal, msg)

    elif action == "audit_unresolved":
        return _handle_audit_unresolved(dal)

    elif action == "record_extension_job":
        return _handle_record_extension_job(dal, msg)

    elif action == "ping":
        return {"status": "ok", "project_root": PROJECT_ROOT}

    return {"status": "error", "error": f"unknown action: {action}"}


def _handle_refresh(dal, scope, picks, attempt_ts):
    """Persist scraped picks via DAL."""
    # Add portfolio_status and is_stale (extension doesn't set these)
    for pick in picks:
        pick["portfolio_status"] = scope
        pick["is_stale"] = False

    snapshot_ts = datetime.now(tz=timezone.utc)
    try:
        count = dal.apply_sa_refresh(
            scope=scope,
            picks=picks,
            attempt_ts=attempt_ts,
            snapshot_ts=snapshot_ts,
        )
        logger.info("Refresh %s: %d picks saved", scope, count)

        # Ticker sync: only on current scope success
        if scope == "current" and picks:
            _try_ticker_sync(dal, picks)

        return {"status": "ok", "scope": scope, "count": count}

    except Exception as e:
        logger.error("Refresh %s failed: %s", scope, e)
        try:
            dal.record_sa_refresh_failure(scope, attempt_ts, str(e))
        except Exception:
            pass
        return {"status": "error", "scope": scope, "error": str(e)}


def _handle_failure(dal, scope, attempt_ts, error):
    """Record a refresh failure (session expired, paywall, etc.)."""
    try:
        dal.record_sa_refresh_failure(scope, attempt_ts, error)
        logger.warning("Recorded failure for %s: %s", scope, error)
    except Exception as e:
        logger.error("Failed to record failure for %s: %s", scope, e)
    return {"status": "ok", "scope": scope, "recorded_failure": True}


def _handle_check_detail_cache(dal, picks, articles=None):
    """Return list of picks that need detail fetching (null or expired).

    If articles list is provided (from articles page scrape), matches
    articles to picks by ticker symbol and returns article_url for each.
    """
    try:
        from src.agents.config import get_agent_config

        config = get_agent_config()
        detail_cache_days = getattr(config, "sa_detail_cache_days", 7)
    except Exception:
        detail_cache_days = 7

    # Build ticker → article URL mapping (most recent per ticker)
    # Also build prefix index for cross-exchange matching (KGC → KGCK)
    article_map = {}
    if articles:
        for a in articles:
            ticker = a.get("ticker", "").upper()
            if ticker and ticker not in article_map:
                article_map[ticker] = a.get("url", "")

    need_detail = []
    no_article = []  # Picks needing detail but no matching article found
    now = datetime.now(tz=timezone.utc)
    for p in picks:
        symbol = p.get("symbol", "").upper()
        picked_date = p.get("picked_date")

        cached = dal.get_sa_pick_detail(symbol, picked_date)
        if cached and cached.get("detail_report"):
            # Check expiry
            fetched_at = cached.get("detail_fetched_at")
            if fetched_at:
                if isinstance(fetched_at, str):
                    fetched_at = datetime.fromisoformat(
                        fetched_at.replace("Z", "+00:00")
                    )
                age_days = (now - fetched_at).days
                if age_days <= detail_cache_days:
                    continue  # Has detail and not expired → skip

        # Find matching article URL (exact match, then prefix match for cross-exchange)
        article_url = article_map.get(symbol)
        if not article_url:
            # Prefix match: KGC→KGCK, CLS→CLSCLS, SSRM→SSRMSSRM (US+CA doubled)
            for art_ticker, art_url in article_map.items():
                if art_ticker.startswith(symbol) and len(art_ticker) <= len(symbol) * 2:
                    article_url = art_url
                    break
        if not article_url:
            no_article.append(symbol)
            continue  # No article available for this pick

        need_detail.append({
            "symbol": symbol,
            "picked_date": picked_date,
            "article_url": article_url,
        })

    logger.info(
        "check_detail_cache: %d/%d need detail, %d no article (%d articles available)",
        len(need_detail), len(picks), len(no_article), len(article_map),
    )
    result = {"status": "ok", "need_detail": need_detail}
    if no_article:
        result["no_article"] = no_article
    return result


def _handle_save_detail(dal, msg):
    """Save detail report for a pick."""
    symbol = msg.get("symbol", "")
    picked_date = msg.get("picked_date", "")
    report = msg.get("detail_report", "")
    try:
        ok = dal.save_sa_pick_detail(symbol, picked_date, report)
        if ok:
            logger.info(
                "Detail saved for %s/%s (%d chars)", symbol, picked_date, len(report)
            )
            return {"status": "ok", "symbol": symbol}
        else:
            logger.warning("Detail save returned False for %s/%s", symbol, picked_date)
            return {"status": "error", "symbol": symbol, "error": "DB row not found"}
    except Exception as e:
        logger.error("Detail save failed for %s/%s: %s", symbol, picked_date, e)
        return {"status": "error", "symbol": symbol, "error": str(e)}


def _handle_save_detail_by_symbol(dal, msg):
    """Save detail report, resolving picked_date from DB by symbol."""
    symbol = msg.get("symbol", "").upper()
    report = msg.get("detail_report", "")
    try:
        # Find the pick's picked_date from DB
        cached = dal.get_sa_pick_detail(symbol)
        if not cached:
            return {"status": "error", "symbol": symbol, "error": "Pick not found in DB"}
        picked_date = cached.get("picked_date")
        if not picked_date:
            return {"status": "error", "symbol": symbol, "error": "No picked_date found"}
        # Convert date object to string if needed
        if hasattr(picked_date, "isoformat"):
            picked_date = picked_date.isoformat()

        ok = dal.save_sa_pick_detail(symbol, picked_date, report)
        if ok:
            logger.info("Manual detail saved for %s/%s (%d chars)", symbol, picked_date, len(report))
            return {"status": "ok", "symbol": symbol}
        else:
            return {"status": "error", "symbol": symbol, "error": "DB row not found"}
    except Exception as e:
        logger.error("Manual detail save failed for %s: %s", symbol, e)
        return {"status": "error", "symbol": symbol, "error": str(e)}


def _parse_sa_date(date_str):
    """Parse SA date → 'YYYY-MM-DD'. Accepts 'Mar. 16, 2026', 'Mar 16, 2026', or ISO 'YYYY-MM-DD'."""
    if not date_str:
        return None
    date_str = date_str.strip()
    try:
        # ISO format (from <time datetime>): "2026-03-16" or "2026-03-16T..."
        if len(date_str) >= 10 and date_str[4] == "-" and date_str[7] == "-":
            return date_str[:10]
        from datetime import datetime as _dt
        for fmt in ("%b. %d, %Y", "%b %d, %Y"):
            try:
                return _dt.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    except Exception:
        return None


def _handle_save_market_news(dal, msg):
    """Persist recent Seeking Alpha market-news metadata."""
    items = msg.get("items", [])
    detail_current_limit = msg.get("detail_current_limit")
    detail_backfill_limit = msg.get("detail_backfill_limit", 0)
    try:
        result = dal.save_sa_market_news(
            items,
            detail_current_limit=detail_current_limit,
            detail_backfill_limit=detail_backfill_limit,
        )
        logger.info(
            "save_market_news: saved=%s items=%s current_limit=%s backfill_limit=%s need_detail=%s",
            result.get("saved"),
            len(items),
            detail_current_limit,
            detail_backfill_limit,
            len(result.get("need_detail") or []),
        )
        return result
    except Exception as e:
        logger.error("save_market_news failed: %s", e)
        return {"status": "error", "error": str(e)}


def _handle_get_market_news_recent_ids(dal, msg):
    """Return recent stored market-news IDs for duplicate-aware scrolling."""
    limit = msg.get("limit", 200)
    try:
        ids = dal.get_sa_market_news_recent_ids(limit=limit)
        logger.info("get_market_news_recent_ids: count=%s limit=%s", len(ids), limit)
        return {"status": "ok", "news_ids": ids}
    except Exception as e:
        logger.error("get_market_news_recent_ids failed: %s", e)
        return {"status": "error", "error": str(e), "news_ids": []}


def _handle_save_market_news_detail(dal, msg):
    """Persist a single market-news body payload."""
    news_id = msg.get("news_id", "")
    body_markdown = msg.get("body_markdown", "")
    try:
        ok = dal.save_sa_market_news_detail(news_id, body_markdown)
        logger.info(
            "save_market_news_detail: %s (%d chars, ok=%s)",
            news_id, len(body_markdown), ok,
        )
        return {"status": "ok" if ok else "error", "news_id": news_id, "ok": ok}
    except Exception as e:
        logger.error("save_market_news_detail failed for %s: %s", news_id, e)
        return {"status": "error", "news_id": news_id, "error": str(e)}


def _handle_save_articles_meta(dal, msg):
    """Batch upsert article metadata, return need_content + unresolved."""
    mode = msg.get("mode", "quick")
    articles = msg.get("articles", [])
    # Map scraper fields to DB fields
    for a in articles:
        if "date" in a and "published_date" not in a:
            a["published_date"] = _parse_sa_date(a.pop("date"))
    try:
        result = dal.save_sa_articles_meta(articles, mode=mode)
        logger.info(
            "save_articles_meta: saved=%s need_content=%s need_comments=%s unresolved=%s auto_upgrade=%s",
            result.get("saved"), len(result.get("need_content", [])),
            len(result.get("need_comments", [])),
            len(result.get("unresolved_symbols", [])),
            result.get("auto_upgrade"),
        )
        return result
    except Exception as e:
        logger.error("save_articles_meta failed: %s", e)
        return {"status": "error", "error": str(e)}


_COMMENT_SPACE_RE = re.compile(r"\s+")


def _normalize_comment_value(value):
    return _COMMENT_SPACE_RE.sub(" ", (value or "")).strip()


def _canonical_comment_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    else:
        return str(value)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()


def _comment_identity_key(comment):
    return (
        _normalize_comment_value(comment.get("commenter")).lower(),
        _normalize_comment_value(comment.get("comment_text")).lower(),
    )


def _merge_comment_bucket(bucket):
    merged = dict(bucket[0])
    merged["comment_date"] = _canonical_comment_date(merged.get("comment_date"))
    merged["_source_ids"] = [c.get("comment_id") for c in bucket if c.get("comment_id")]

    for item in bucket[1:]:
        item_date = _canonical_comment_date(item.get("comment_date"))
        if not merged.get("commenter") and item.get("commenter"):
            merged["commenter"] = item.get("commenter")
        if len(_normalize_comment_value(item.get("comment_text"))) > len(
            _normalize_comment_value(merged.get("comment_text"))
        ):
            merged["comment_text"] = item.get("comment_text")
        merged["upvotes"] = max(
            int(merged.get("upvotes") or 0),
            int(item.get("upvotes") or 0),
        )
        if not merged.get("comment_date") and item_date:
            merged["comment_date"] = item_date
        if not merged.get("parent_comment_id") and item.get("parent_comment_id"):
            merged["parent_comment_id"] = item.get("parent_comment_id")
        if item.get("comment_id"):
            merged["_source_ids"].append(item.get("comment_id"))

    return merged


def _dedupe_comments(comments):
    grouped = defaultdict(list)
    group_order = []
    for comment in comments:
        item = dict(comment)
        item["comment_date"] = _canonical_comment_date(item.get("comment_date"))
        key = _comment_identity_key(item)
        if key not in grouped:
            group_order.append(key)
        grouped[key].append(item)

    deduped = []
    for key in group_order:
        dated_groups = defaultdict(list)
        dated_order = []
        null_dated = []
        for item in grouped[key]:
            date_key = item.get("comment_date")
            if date_key:
                if date_key not in dated_groups:
                    dated_order.append(date_key)
                dated_groups[date_key].append(item)
            else:
                null_dated.append(item)

        if len(dated_groups) == 1:
            only_date_key = dated_order[0]
            deduped.append(_merge_comment_bucket(dated_groups[only_date_key] + null_dated))
            continue

        if not dated_groups:
            deduped.append(_merge_comment_bucket(null_dated))
            continue

        for date_key in dated_order:
            deduped.append(_merge_comment_bucket(dated_groups[date_key]))
        if null_dated:
            deduped.append(_merge_comment_bucket(null_dated))

    return deduped


def _normalize_comment_ids(article_id, comments):
    """Ensure stable comment IDs and collapse obvious duplicate comment payloads."""
    deduped = _dedupe_comments(comments)

    id_map = {}
    for comment in deduped:
        source_ids = comment.pop("_source_ids", [])
        comment_date = _canonical_comment_date(comment.get("comment_date"))
        comment["comment_date"] = comment_date

        old_id = comment.get("comment_id", "")
        if not old_id or old_id.startswith("syn_"):
            if comment_date:
                raw = "{}:{}:{}:{}".format(
                    article_id,
                    comment.get("commenter", ""),
                    comment_date,
                    (comment.get("comment_text", "") or "")[:100],
                )
            else:
                raw = "{}:{}:{}".format(
                    article_id,
                    comment.get("commenter", ""),
                    (comment.get("comment_text", "") or "")[:100],
                )
            comment["comment_id"] = hashlib.sha256(raw.encode()).hexdigest()[:20]

        for source_id in source_ids:
            id_map[source_id] = comment["comment_id"]

    for comment in deduped:
        parent = comment.get("parent_comment_id")
        if parent and parent in id_map:
            comment["parent_comment_id"] = id_map[parent]
        if comment.get("parent_comment_id") == comment.get("comment_id"):
            comment["parent_comment_id"] = None

    return deduped


def _handle_save_article_content(dal, msg):
    """Compound atomic write: article body + comments + pick sync."""
    article_id = msg.get("article_id", "")
    body_markdown = msg.get("body_markdown", "")
    comments = _normalize_comment_ids(article_id, msg.get("comments", []))
    try:
        result = dal.save_sa_article_with_comments(article_id, body_markdown, comments)
        logger.info(
            "save_article_content: %s (%d chars, prepared=%d net_new=%d stored_total=%d synced=%s)",
            article_id, len(body_markdown),
            result.get("prepared_comments", 0),
            result.get("net_new_comments", 0),
            result.get("stored_comments_total", 0),
            result.get("synced_picks", 0),
        )
        return {"status": "ok", "article_id": article_id, **result}
    except Exception as e:
        logger.error("save_article_content failed for %s: %s", article_id, e)
        return {"status": "error", "article_id": article_id, "error": str(e)}


def _handle_save_comments_only(dal, msg):
    """Comments-only update for TTL refresh."""
    article_id = msg.get("article_id", "")
    comments = _normalize_comment_ids(article_id, msg.get("comments", []))
    try:
        stats = dal.save_sa_comments_only(article_id, comments)
        logger.info(
            "save_comments_only: %s (prepared=%d net_new=%d stored_total=%d)",
            article_id,
            stats.get("prepared_comments", 0),
            stats.get("net_new_comments", 0),
            stats.get("stored_comments_total", 0),
        )
        return {
            "status": "ok",
            "article_id": article_id,
            "comments_count": stats.get("prepared_comments", 0),
            **stats,
        }
    except Exception as e:
        logger.error("save_comments_only failed for %s: %s", article_id, e)
        return {"status": "error", "article_id": article_id, "error": str(e)}


def _handle_audit_unresolved(dal):
    """Final audit: full-text fallback for unresolved current picks."""
    try:
        result = dal.audit_sa_unresolved_symbols()
        logger.info(
            "audit_unresolved: %d unresolved, %d resolved by fulltext",
            len(result.get("unresolved_symbols", [])),
            result.get("resolved_by_fulltext", 0),
        )
        return {"status": "ok", **result}
    except Exception as e:
        logger.error("audit_unresolved failed: %s", e)
        return {"status": "error", "error": str(e)}


def _handle_record_extension_job(dal, msg):
    """Persist an extension-managed sync into job_runs (P0.4 commit 2).

    The extension only contacts native messaging *after* a sync flow
    finishes, so we land directly in the terminal state with the
    extension's own start/finish timestamps. Best-effort: any DB error
    is logged but never raised back to the extension.
    """
    job_name = msg.get("job_name") or ""
    status = msg.get("status") or ""
    if status not in ("succeeded", "failed"):
        return {"status": "error", "error": f"invalid job status: {status!r}"}
    if not job_name:
        return {"status": "error", "error": "job_name required"}

    started_at = _parse_iso_dt(msg.get("started_at"))
    if started_at is None:
        return {"status": "error", "error": "valid started_at required"}
    finished_at = _parse_iso_dt(msg.get("finished_at"))

    payload = msg.get("payload") or {}
    result = msg.get("result")
    message_text = msg.get("message")
    error_text = msg.get("error")
    duration_ms = msg.get("duration_ms")
    if duration_ms is not None:
        try:
            duration_ms = int(duration_ms)
        except (TypeError, ValueError):
            duration_ms = None
    trigger_source = msg.get("trigger_source") or "extension"

    try:
        from src.service.job_runs_store import JobRunsStore
        store = JobRunsStore(dal)
        run_id = store.record_completed_run(
            job_name,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            trigger_source=trigger_source,
            payload=payload if isinstance(payload, dict) else {"value": payload},
            result=result if isinstance(result, dict) else None,
            message=message_text,
            error=error_text,
            duration_ms=duration_ms,
        )
        logger.info(
            "record_extension_job: name=%s status=%s run_id=%s duration_ms=%s",
            job_name, status, run_id, duration_ms,
        )
        return {"status": "ok", "run_id": run_id, "persisted": run_id is not None}
    except Exception as e:
        logger.error("record_extension_job failed: %s", e)
        return {"status": "error", "error": str(e)}


def _parse_iso_dt(value):
    """Accept extension-supplied ISO 8601 strings (with trailing Z)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _try_ticker_sync(dal, picks):
    """Best-effort ticker sync to tickers_core.json."""
    try:
        from data_sources.sa_alpha_picks_client import SAAlphaPicksClient
        client = SAAlphaPicksClient(dal=dal)
        client.sync_tickers_to_collection(picks)
        logger.info("Ticker sync completed")
    except Exception as e:
        logger.warning("Ticker sync failed (best-effort): %s", e)


def main():
    try:
        msg = read_message()
        if msg is None:
            return

        logger.info("Received: action=%s scope=%s", msg.get("action"), msg.get("scope"))
        result = handle_message(msg)
        write_message(result)
        logger.info("Sent: %s", json.dumps(result)[:200])

    except Exception as e:
        logger.exception("Native host error")
        try:
            write_message({"status": "error", "error": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    main()
