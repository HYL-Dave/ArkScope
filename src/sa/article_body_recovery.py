"""Build a deterministic, read-only preview of retained SA body recovery work.

This module neither navigates nor writes. An available body is preserved, not
certified complete. Membership is the retained snapshot, not a reconstruction
of the portfolio at ``as_of``; stale observations do not establish closure.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from src.sa.article_body_quality import assess_body
from src.tools.retained_read_results import content_id


_RECENT_DAYS = 365
_ENTRY_CANDIDATE_DAYS = 3
_PREFIX = "sa_article_body_recovery_"
_REQUIRED_COLUMNS = {
    "sa_articles": {
        "article_id", "url", "title", "published_date", "body_markdown",
        "ticker", "list_ticker", "detail_ticker",
    },
    "sa_pick_lineages": {"lineage_id", "symbol_key", "picked_date"},
    "sa_alpha_picks": {
        "id", "lineage_id", "symbol", "company", "picked_date", "closed_date",
        "portfolio_status", "is_stale", "canonical_article_id",
    },
    "sa_pick_article_links": {
        "link_id", "lineage_id", "article_id", "role", "event_anchor_date",
        "link_source", "evidence_codes", "revoked_at",
    },
}


def _unavailable(reason: str) -> dict:
    return {"status": "unavailable", "error_code": _PREFIX + reason,
            "provider": "seeking_alpha", "retrieval": "stored",
            "targets": []}


def _as_of_date(value) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value)
    raise ValueError("date required")


def _published_date(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return date.fromisoformat(value)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed).date()
    except ValueError:
        return None


def _safe_url(url, article_id: str) -> str | None:
    if not isinstance(url, str) or re.search(r"[\x00-\x20\x7f\s\\%]", url):
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if (parsed.scheme != "https" or parsed.netloc != "seekingalpha.com"
            or parsed.query or parsed.fragment or "?" in url or "#" in url):
        return None
    match = re.fullmatch(
        r"/(?:article|alpha-picks/articles)/([0-9]+)(?:-[A-Za-z0-9_-]+)?/?",
        parsed.path,
    )
    return url if match and match[1] == article_id else None


def _symbol(value) -> str | None:
    if isinstance(value, str):
        return value.strip().upper() or None
    return None


def _provider_identity(article: dict) -> tuple[str | None, list[str]]:
    listed, detail, legacy = (_symbol(article[k]) for k in ("list_ticker", "detail_ticker", "ticker"))
    if listed and detail and listed != detail:
        return None, ["ticker_metadata_conflict"]
    codes = (["ticker_list_exact"] if listed else []) + (["ticker_detail_exact"] if detail else [])
    if not codes and legacy:
        codes = ["legacy_ticker_projection"]
    return listed or detail or legacy, codes


def _title_identity(title: str, symbol: str, companies: list[str]) -> list[str]:
    # Bare short/common words are not ticker evidence. Dollar, exchange,
    # parenthesized, or leading-colon forms explicitly identify a symbol.
    token = re.escape(symbol)
    explicit = rf"(?<![\w.$-])(?:\${token}|(?:NYSE|NASDAQ|AMEX):\s*{token})(?![\w.-])"
    if (re.search(explicit, title)
            or re.search(rf"\({token}\)", title)
            or re.match(rf"{token}\s*:", title)):
        return ["title_symbol_explicit"]
    if len(symbol) >= 3 and re.search(rf"(?<![\w.$-]){token}(?![\w.-])", title):
        return ["title_symbol_exact"]
    normalized = " ".join(title.split())
    for company in companies:
        company = " ".join(company.split())
        if (len(company) >= 4 and company.upper() != symbol
                and re.search(rf"(?<![\w.-]){re.escape(company)}(?![\w.-])", normalized, re.I)):
            return ["title_company_exact"]
    return []


def _latest_snapshot(rows: list[dict]) -> str | None:
    timestamps = []
    for row in rows:
        value = row["last_seen_snapshot"]
        if not isinstance(value, str):
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                timestamps.append(parsed.astimezone(timezone.utc))
        except ValueError:
            continue
    return max(timestamps).isoformat(timespec="seconds") if timestamps else None


def _cohorts(lineages: list[dict], picks: list[dict], links: list[dict]) -> dict[int, dict]:
    observations = defaultdict(list)
    entries = defaultdict(set)
    for pick in picks:
        observations[pick["lineage_id"]].append(pick)
    for link in links:
        if link["role"] == "entry":
            entries[link["lineage_id"]].add(link["article_id"])
    cohorts = {}
    for lineage in lineages:
        lid = lineage["lineage_id"]
        rows = observations[lid]
        current = [p for p in rows if p["is_stale"] == 0 and p["portfolio_status"] == "current"]
        closed = [p for p in rows if p["is_stale"] == 0 and p["portfolio_status"] == "closed"]
        status = "current" if current else "closed" if closed else "unknown"
        selected = current or closed or rows
        canonical = sorted({p["canonical_article_id"] for p in selected if p["canonical_article_id"]})
        cohorts[lid] = {
            "lineage_id": lid, "symbol": lineage["symbol_key"],
            "picked_date": lineage["picked_date"], "membership_status": status,
            "latest_snapshot_at": _latest_snapshot(rows),
            "membership_reasons": ["nonstale_current_observation" if current else
                                   "nonstale_closed_observation" if closed else
                                   "stale_or_missing_membership_observation"],
            "observations": [
                {"pick_id": p["id"], "portfolio_status": p["portfolio_status"],
                 "is_stale": bool(p["is_stale"]), "closed_date": p["closed_date"],
                 "last_seen_snapshot": p["last_seen_snapshot"]}
                for p in rows
            ],
            "accepted_entry_article_ids": sorted(entries[lid]),
            "canonical_article_ids": canonical,
            "_entry_ids": entries[lid] or set(canonical),
            "_companies": sorted({p["company"] for p in selected if p["company"]}),
        }
    return cohorts


def _membership(cohort: dict, basis: str, *, role=None, link_id=None,
                evidence_codes=(), **extra) -> dict:
    return {key: cohort[key] for key in
            ("lineage_id", "symbol", "picked_date", "membership_status", "latest_snapshot_at")} | {
        "basis": basis, "role": role, "link_id": link_id,
        "evidence_codes": sorted(set(evidence_codes)), **extra,
    }


def _link_evidence(value) -> tuple[list[str], str]:
    try:
        evidence = json.loads(value)
    except (TypeError, ValueError, RecursionError):
        return [], "unknown"
    if not isinstance(evidence, list):
        return [], "unknown"
    # Codes are identifiers, never retained prose or arbitrary JSON keys.
    codes = [c for c in evidence if isinstance(c, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", c)]
    return codes, "recorded" if len(codes) == len(evidence) else "unknown"


def _memberships(article: dict, cohorts: dict, links: list[dict]) -> tuple[list[dict], list[str]]:
    aid = article["article_id"]
    published = _published_date(article["published_date"])
    provider, provider_codes = _provider_identity(article)
    members = []
    for link in links:
        cohort = cohorts[link["lineage_id"]]
        evidence, evidence_status = _link_evidence(link["evidence_codes"])
        members.append(_membership(
            cohort, "accepted_link", role=link["role"], link_id=link["link_id"],
            evidence_codes=evidence, link_source=link["link_source"],
            evidence_status=evidence_status,
            event_anchor_date=link["event_anchor_date"],
        ))
    for cohort in cohorts.values():
        if not cohort["accepted_entry_article_ids"] and aid in cohort["canonical_article_ids"]:
            members.append(_membership(cohort, "canonical_id", role="entry",
                                       evidence_codes=["legacy_canonical_article_id"]))
        if provider == cohort["symbol"]:
            members.append(_membership(cohort, "provider_identity", evidence_codes=provider_codes))
        if cohort["membership_status"] != "current" or cohort["_entry_ids"]:
            continue
        picked = _published_date(cohort["picked_date"])
        distance = abs((published - picked).days) if published and picked else None
        if distance is None or distance > _ENTRY_CANDIDATE_DAYS:
            continue
        identity = (provider_codes if provider == cohort["symbol"] else []
                    if provider or "ticker_metadata_conflict" in provider_codes else
                    _title_identity(article["title"], cohort["symbol"], cohort["_companies"]))
        if identity:
            members.append(_membership(
                cohort, "entry_candidate", evidence_codes=[*identity, "date_exact" if distance == 0 else "date_near"],
                date_distance_days=distance,
            ))
    members.sort(key=lambda m: (m["symbol"], m["picked_date"], m["lineage_id"],
                                m["basis"], m["role"] or "", m["link_id"] or 0))
    return members, ["ticker_metadata_conflict"] if "ticker_metadata_conflict" in provider_codes else []


def _item(article: dict, cohorts: dict, links: list[dict], as_of: date, cutoff: date) -> dict:
    body = article["body_markdown"]
    assessment = assess_body(body, title=article["title"])
    members, reasons = _memberships(article, cohorts, links)
    published = _published_date(article["published_date"])
    current = [m for m in members if m["membership_status"] == "current"]
    entries = [m for m in current if m["role"] == "entry"
               and m["basis"] in {"accepted_link", "canonical_id"}]
    candidates = [m for m in current if m["basis"] == "entry_candidate"]
    followups = [m for m in current if published and
                 (picked := _published_date(m["picked_date"])) and picked <= published]
    priority = None
    if published and published > as_of:
        reasons.append("published_after_as_of")
    elif entries:
        priority = 1
        reasons.extend("current_cohort_accepted_entry" if m["basis"] == "accepted_link"
                       else "current_cohort_canonical_entry" for m in entries)
    elif candidates:
        priority = 1
        reasons.append("current_cohort_entry_candidate")
    elif published and cutoff <= published <= as_of:
        priority = 2 if followups else 3
        reasons.append("recent_current_pick_followup" if followups else "recent_article")
    elif published is None:
        reasons.append("published_date_unknown")
    else:
        reasons.append("older_article_outside_recovery_scope")
    url = _safe_url(article["url"], article["article_id"])
    reason_code = None
    if assessment["status"] == "available":
        reasons.append("body_available")
    if url is None:
        disposition = "exclude"
        reason_code = _PREFIX + "url_invalid"
        reasons.append(reason_code)
    elif assessment["status"] == "available":
        disposition = "exclude"
    else:
        disposition = "recover" if priority else "hold"
        reason_code = assessment["reason_code"]
    return {
        "article_id": article["article_id"], "url": url, "title": article["title"],
        "published_date": article["published_date"],
        "body_sha256": hashlib.sha256((body or "").encode("utf-8")).hexdigest(),
        "body_is_null": body is None, "body_assessment": assessment,
        "priority": priority, "disposition": disposition, "reason_code": reason_code,
        "reasons": sorted(set(reasons)), "cohort_memberships": members,
    }


def _manifest(articles: list[dict], lineages: list[dict], picks: list[dict],
              links: list[dict], as_of: date) -> dict:
    cutoff = as_of - timedelta(days=_RECENT_DAYS)
    cohorts = _cohorts(lineages, picks, links)
    by_article = defaultdict(list)
    for link in links:
        by_article[link["article_id"]].append(link)
    items = [_item(article, cohorts, by_article[article["article_id"]], as_of, cutoff)
             for article in articles]
    targets = sorted((i for i in items if i["disposition"] == "recover"),
                     key=lambda i: (i["priority"],
                                    "current_cohort_entry_candidate" in i["reasons"],
                                    -(_published_date(i["published_date"]) or date.min).toordinal(),
                                    i["article_id"]))
    held = [i for i in items if i["disposition"] == "hold"]
    excluded = [i for i in items if i["disposition"] == "exclude"]
    priorities = Counter(str(i["priority"]) for i in targets)
    statuses = Counter(i["body_assessment"]["status"] for i in items)
    result = {
        "status": "ok", "schema_version": 1, "provider": "seeking_alpha", "retrieval": "stored",
        "as_of": as_of.isoformat(), "cutoff": cutoff.isoformat(),
        "scope": {
            "mode": "preview_only", "recent_days": _RECENT_DAYS,
            "entry_candidate_days": _ENTRY_CANDIDATE_DAYS,
            "recent_bounds": "inclusive", "current_entry_age_limit": None,
            "membership_basis": "retained_snapshot_not_historical_reconstruction",
            "available_bodies": "preserve", "older_unrelated_bodies": "hold",
        },
        "body_hash_algorithm": "sha256", "body_hash_version": 1,
        "body_hash_encoding": "utf8_null_as_empty",
        "targets": targets, "held": held, "excluded": excluded,
        "cohorts": [{k: v for k, v in cohort.items() if not k.startswith("_")}
                    for cohort in sorted(cohorts.values(), key=lambda c: (c["symbol"], c["picked_date"], c["lineage_id"]))],
        "counts": {
            "articles": len(items), "targets": len(targets), "held": len(held), "excluded": len(excluded),
            "by_priority": {p: priorities[p] for p in ("1", "2", "3")},
            "by_body_status": {s: statuses[s] for s in ("available", "not_captured", "unusable")},
            "invalid_urls": sum(i["url"] is None for i in items),
        },
    }
    result["manifest_id"] = content_id(result)
    return result


def build_recovery_manifest(db_path, *, as_of=None) -> dict:
    """Return a source-prose-free preview; unavailable stores are never created.

    ``as_of`` is a date or YYYY-MM-DD (default: today's UTC date). The hash
    includes the complete manifest except itself, using canonical JSON. Bodies
    are hashed as retained UTF-8, with NULL treated as empty, before assessment.
    Priority 1 is a current entry or explicitly unproven entry candidate, 2 a
    recent current-pick follow-up, 3 any other recent invalid article. Only
    ``targets`` are recovery candidates; ``held`` and ``excluded`` are retained.
    """
    try:
        day = _as_of_date(as_of)
        day - timedelta(days=_RECENT_DAYS)
    except (ValueError, OverflowError):
        return _unavailable("as_of_invalid")
    try:
        path = Path(db_path)
        if not path.is_file():
            return _unavailable("capture_missing")
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            snapshot_column = "NULL AS last_seen_snapshot"
            for table, required in _REQUIRED_COLUMNS.items():
                columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if not required <= columns:
                    return _unavailable("schema_unavailable")
                if table == "sa_alpha_picks" and "last_seen_snapshot" in columns:
                    snapshot_column = "last_seen_snapshot"
            articles = [dict(row) for row in conn.execute(
                "SELECT article_id, url, title, published_date, body_markdown, ticker, list_ticker, detail_ticker "
                "FROM sa_articles ORDER BY article_id")]
            lineages = [dict(row) for row in conn.execute(
                "SELECT lineage_id, symbol_key, picked_date FROM sa_pick_lineages ORDER BY lineage_id")]
            picks = [dict(row) for row in conn.execute(
                "SELECT id, lineage_id, symbol, company, picked_date, closed_date, portfolio_status, "
                f"is_stale, canonical_article_id, {snapshot_column} FROM sa_alpha_picks ORDER BY id")]
            links = [dict(row) for row in conn.execute(
                "SELECT k.link_id, k.lineage_id, k.article_id, k.role, k.event_anchor_date, "
                "k.link_source, k.evidence_codes FROM sa_pick_article_links k "
                "JOIN sa_pick_lineages l ON l.lineage_id=k.lineage_id "
                "JOIN sa_articles a ON a.article_id=k.article_id "
                "WHERE k.revoked_at IS NULL ORDER BY k.link_id")]
        return _manifest(articles, lineages, picks, links, day)
    except (sqlite3.Error, OSError):
        return _unavailable("store_unavailable")
