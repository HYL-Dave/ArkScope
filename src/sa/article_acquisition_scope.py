"""Read-only article eligibility; historical closure is not a security exclusion."""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Literal

from src.active_universe import _read_identity_links, _IdentityLinksInvalid
from src.sa.article_body_recovery import _cohorts, _memberships, _provider_identity, _read_inventory
from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
from src.sa_tracking_memberships import SaTrackingMembershipStore, _identity
from src.tools.retained_read_results import content_id


def read_article_scope_context(*, sa_db: str | Path, profile_db: str | Path) -> dict:
    try:
        inventory = _read_inventory(sa_db)
        articles, lineages, picks, links = inventory
        with closing(sqlite3.connect(Path(profile_db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            if not SaTrackingMembershipStore.installed(conn):
                raise ValueError("tracking_schema_absent")
            identities = _read_identity_links(conn)
            tracked = {r["membership_id"]: dict(r) for r in conn.execute(
                "SELECT * FROM sa_tracking_memberships ORDER BY membership_id")}
            bindings = {r["lineage_id"]: dict(r) for r in conn.execute(
                "SELECT * FROM sa_tracking_bindings ORDER BY lineage_id")}
        # Fail closed if the capture changed between its snapshot and authority read.
        check = _read_inventory(sa_db)
        if content_id(inventory) != content_id(check):
            raise ValueError("source_changed")
        result = _context(articles, lineages, picks, links, tracked, bindings, identities)
        result["inventory_id"] = content_id(inventory)
        return result
    except (sqlite3.Error, OSError, ValueError, _IdentityLinksInvalid):
        return {"status": "unavailable", "error_code": "sa_article_scope_unavailable",
                "context_id": None, "articles": {}, "cohorts": {}, "securities": {}, "exclusions": []}


def _context(articles, lineages, picks, links, tracked, bindings, identities):
    cohorts = _cohorts(lineages, picks, links)
    securities = defaultdict(list)
    exclusions = []
    for lid, cohort in cohorts.items():
        binding = bindings.get(lid, {})
        member = tracked.get(binding.get("membership_id"), {})
        security = _identity(cohort["symbol"], identities)
        cohort["security"] = security
        reason = member.get("reason")
        if member and (binding["ticker"], binding["picked_date"]) != (cohort["symbol"], cohort["picked_date"]):
            raise ValueError("tracking_binding_conflict")
        state = "unknown"
        if reason == "terminal_delisting":
            state = "terminal"
        elif member.get("removed_at") and not member.get("current_tracking"):
            state = "removed"
        elif member.get("accepted_at") and reason not in {"identity_ambiguous", "related_security"}:
            if member.get("current_tracking"):
                state = "current"
            elif member.get("portfolio_status") == "closed":
                state = "former"
            # A newer capture may await writer-side tracking reconciliation. Do not
            # resurrect a stale Current or infer an exit from an unapplied snapshot.
            observed = cohort.get("latest_snapshot_at")
            if observed and observed > binding.get("observed_at", ""):
                expected = "current" if cohort["membership_status"] == "current" else "former"
                if cohort["membership_status"] == "unknown" or state != expected:
                    state = "unknown"
        cohort["effective_membership"] = state
        if state in {"terminal", "removed"}:
            exclusions.append({"lineage_id": lid, "security": security, "reason": state})
        securities[security].append(lid)
    by_article = defaultdict(list)
    for link in links:
        by_article[link["article_id"]].append(link)
    decisions = {}
    for article in articles:
        memberships, conflicts = _memberships(article, cohorts, by_article[article["article_id"]])
        direct = {m["lineage_id"] for m in memberships if m["basis"] in {"accepted_link", "canonical_id"}}
        provider, _ = _provider_identity(article)
        if not direct and provider:
            identity = _identity(provider, identities)
            direct = set(securities.get(identity, []))
        candidate_only = not direct
        if not direct:
            direct = {m["lineage_id"] for m in memberships if m["basis"] == "entry_candidate"}
        states = {cohorts[lid]["effective_membership"] for lid in direct}
        if not by_article[article["article_id"]] and "terminal" in states and "current" in states:
            conflicts.append("reused_symbol_without_article_binding")
        # Only expand ordinary retained cohorts to current cohorts of the same
        # established identity. An old terminal/removal cannot be undone by reuse.
        ordinary = {lid for lid in direct if cohorts[lid]["effective_membership"] in {"current", "former"}}
        current = any(cohorts[other]["effective_membership"] == "current"
                      for lid in ordinary for other in securities[cohorts[lid]["security"]])
        state = ("current" if current else "former" if "former" in states else
                 "terminal" if "terminal" in states else "removed" if "removed" in states else "unknown")
        decisions[article["article_id"]] = {
            "effective_membership": state, "conflict": bool(conflicts),
            "candidate_only": candidate_only,
            "lineage_ids": sorted(direct),
        }
    result = {"status": "ok", "articles": decisions, "cohorts": cohorts,
              "securities": dict(securities), "exclusions": exclusions}
    # Internal sets used for candidate recognition are not JSON provenance.
    result["cohorts"] = {lid: {k: v for k, v in c.items() if not k.startswith("_")}
                         for lid, c in cohorts.items()}
    result["context_id"] = content_id(result)
    return result


def decide_article_acquisition(article_id: str, *, operation: Literal["body", "comments"],
                               settings: ArticleAcquisitionSettings, context: dict) -> dict:
    result = {"allowed": False, "reason_code": None, "effective_membership": "unknown",
              "context_id": context.get("context_id")}
    if operation not in {"body", "comments"}:
        return result | {"reason_code": "sa_article_operation_invalid"}
    if context.get("status") != "ok":
        return result | {"reason_code": "sa_article_scope_unavailable"}
    item = context.get("articles", {}).get(article_id)
    if item is None:
        return result | {"reason_code": "sa_article_not_retained"}
    state = item["effective_membership"]
    result["effective_membership"] = state
    if item.get("conflict"):
        return result | {"reason_code": "sa_article_identity_conflict"}
    if state in {"terminal", "removed"}:
        return result | {"reason_code": "sa_article_permanently_excluded" if state == "terminal" else "sa_article_membership_removed"}
    if operation == "comments" and item.get("candidate_only"):
        return result | {"reason_code": "sa_article_membership_unresolved"}
    allowed = (state == "current" or operation == "body" and settings.body_scope == "all_retained"
               or operation == "comments" and settings.comment_scope == "tracked" and state == "former")
    return result | {"allowed": allowed, "reason_code": None if allowed else
                     "sa_article_former_out_of_scope" if state == "former" else "sa_article_membership_unresolved"}
