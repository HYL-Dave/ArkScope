"""Closed current-review reads. Population accounting is not action authority."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from src.active_universe import SOURCE_KEYS
from src.security_lifecycle_disposition import current_automation_run, next_lifecycle_recheck_at
from src.security_lifecycle_investigation import observation_fingerprint
from src.security_lifecycle_population import (
    LifecyclePopulationUnavailable, _dispositions, build_population_manifest, read_population_snapshot,
)
from src.security_lifecycle_provider_authority import classify_provider_listing, evidence_dict
from src.security_lifecycle_provider_diagnostics import listing_operator_detail
from src.security_lifecycle_provider_snapshot import decode_snapshot, instant
from src.security_lifecycle_review import confirmation_for
from src.service.security_lifecycle_automation_config import (
    SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS, parse_security_lifecycle_automation_config,
)
from src.ticker_identity_transition import TickerIdentityTransitionStore


_SOURCE_HOSTS = frozenset({"api.massive.com", "api.polygon.io", "eodhd.com", "www.nasdaqtrader.com", "ftp.nasdaqtrader.com", "www.sec.gov"})
_PROVIDERS = {"massive_reference": "massive", "massive_ticker_events": "massive",
              "eodhd_symbol_directory": "eodhd", "nasdaq_symbol_directory": "nasdaq"}
CURRENT_REVIEW_REASONS = frozenset({
    "provider_confirmation_missing", "source_missing", "active_confirmed", "continuation_requires_confirmation",
    "removal_requires_confirmation", "provider_confirmation_incomplete", "regulator_event_pending", "regulator_identity_question",
    "listing_identity_changed", "superseded_listing_identity", "prior_action_history", "action_needs_review", "action_scheduled",
    "action_pending", "listing_reappeared_after_action", "listing_recheck_required", "removal_applied",
    "continuation_followup_pending", "symbol_change_applied", "applied_state_changed",
})
CURRENT_ACTION_STATES = frozenset({
    "not_prepared", "approved", "scheduled", "applied", "blocked", "cancelled", "reversed", "applied_state_changed",
})


def _sources(value):
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise LifecyclePopulationUnavailable("current_sources_invalid")
    result = {}
    for ticker, sources in value.items():
        if (not isinstance(ticker, str) or not ticker or ticker != ticker.strip().upper()
                or not isinstance(sources, (tuple, list, set, frozenset)) or not sources
                or any(not isinstance(source, str) or source not in SOURCE_KEYS for source in sources)):
            raise LifecyclePopulationUnavailable("current_sources_invalid")
        result[ticker] = sorted(set(sources))
    return result


def _source_url(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or url.hostname not in _SOURCE_HOSTS
                or url.username is not None or url.password is not None or url.port not in {None, 80, 443}):
            return None
        # Source checks carry the market/filter separately; queries must not
        # export credentials or turn the audit link into an API request recipe.
        return urlunsplit(("https", url.hostname, url.path, "", ""))
    except ValueError:
        return None


def _source_checks(check):
    result = []
    for raw in check["evidence"] if check else ():
        row = evidence_dict(raw)
        locator = row["source_locator"]
        provider = _PROVIDERS.get(row["adapter"])
        if provider is None:
            raise LifecyclePopulationUnavailable("current_source_check_invalid")
        if row["kind"] == "ticker_event_snapshot":
            name, status = "continuation", "observed" if locator.get("events") else "not_observed"
        elif provider == "massive":
            name = "delisting" if locator.get("expected_active_state") is False else locator.get("market")
            status = locator.get("listing_status")
        else:
            name, status = provider, locator.get("listing_status")
        if name not in {"delisting", "stocks", "otc", "eodhd", "nasdaq", "continuation"} or status not in {
                "active", "inactive", "not_found", "observed", "not_observed"}:
            raise LifecyclePopulationUnavailable("current_source_check_invalid")
        directory = locator.get("directory") if provider == "nasdaq" else None
        if provider == "nasdaq" and directory not in {"nasdaq_listed", "other_listed"}:
            raise LifecyclePopulationUnavailable("current_source_check_invalid")
        result.append({"provider": provider, "check": name, "directory": directory, "status": status,
                       "ticker": locator.get("candidate_ticker", check["ticker"]),
                       "observed_at": row["retrieved_at"], "url": _source_url(row["source_url"])})
    return sorted(result, key=lambda row: (row["provider"], row["check"], row["directory"] or "", row["ticker"], row["url"] or ""))


def _enabled(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='profile_settings'").fetchone():
        return False
    placeholders = ",".join("?" for _ in SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS)
    values = dict(conn.execute(f"SELECT key,value FROM profile_settings WHERE key IN ({placeholders})", SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS))
    return parse_security_lifecycle_automation_config(values).effective_background_enabled


def _assessment(case):
    rows = case.get("assessment_history", []) if case else []
    if not rows or not case.get("observation"):
        return None
    latest = max(rows, key=lambda row: row["revision"])
    if latest["observation_fingerprint_sha256"] != observation_fingerprint(case["observation"]):
        return None
    return latest


def _current_action_transitions(transitions, material):
    from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION

    applied = [row for row in transitions if row["status"] == "applied"]
    if not applied:
        return transitions
    receipts = {row["transition_id"]: row for row in material["identity_tables"]["ticker_identity_transitions"]}
    assessments = {row["assessment_id"]: row for row in material["profile_tables"]["security_lifecycle_assessments"]}
    event_fields = ("review_id", "case_id", "kind", "source_ticker", "successor_ticker", "execute_on")

    def superseded(row):
        if (row["status"] not in {"approved", "needs_review"} or row["approval_authority"] != "automation_policy"
                or receipts[row["transition_id"]]["automation_policy_version"] == AUTOMATION_POLICY_VERSION):
            return False
        assessment = assessments[row["assessment_id"]]
        # Assessment revision orders decisions even when a stale attempt updates
        # its receipt after the replacement applied. Keep both receipts in history.
        return any(
            all(replacement[key] == row[key] for key in event_fields)
            and assessments[replacement["assessment_id"]]["effective_date"] == assessment["effective_date"]
            and assessments[replacement["assessment_id"]]["revision"] > assessment["revision"]
            for replacement in applied
        )

    return [row for row in transitions if not superseded(row)]


def _action(review, cases, transitions, store, *, today):
    candidates = [row for row in cases if row["source"] == "listing_authority" and row["source_presence"] == "present"]
    case = candidates[0] if len(candidates) == 1 else (cases[0] if cases else None)
    assessment = _assessment(case) if case and case["source"] == "listing_authority" else None
    kind = "recheck" if review["bucket"] == "current" else "none"
    if review["bucket"] == "current" and assessment:
        if review["finding"] == "replacement_confirmed":
            kind = "review_symbol_change"
        elif review["finding"] == "old_listing_inactive":
            kind = "review_removal"
    result = {"kind": kind, "state": "not_prepared", "case_id": case["case_id"] if case else review["case_ids"][0],
              "assessment_id": assessment["assessment_id"] if assessment else None, "transition_id": None,
              "preview_sha256": None, "transition_kind": None, "execute_on": None, "current_effects_match": None,
              "can_reverse": False, "block_reasons": []}
    related = [row for row in transitions if row["review_id"] == review["review_id"]]
    if not related:
        return result, case, assessment
    pending = [row for row in related if row["status"] in {"approved", "needs_review"}]
    transition = store.get((pending or related)[-1]["transition_id"])
    if "review_confirmation" in transition["approved_preview"]:
        confirmation_for(transition)
    status = transition["status"]
    result.update(state=status, case_id=transition["case_id"], assessment_id=transition["assessment_id"],
                  transition_id=transition["transition_id"], preview_sha256=transition["approved_preview_sha256"],
                  execute_on=transition["execute_on"], transition_kind=transition["kind"])
    if status == "applied":
        readiness = store.reverse_readiness(transition["transition_id"])
        result["current_effects_match"] = readiness["expected_state_sha256"] == readiness["observed_state_sha256"]
        result["can_reverse"] = readiness["reversible"]
        result["block_reasons"] = readiness["block_reasons"]
        if not result["current_effects_match"]:
            result["state"] = "applied_state_changed"
        result["kind"] = "recheck" if review["bucket"] == "current" else "none"
    elif status == "approved":
        result["state"] = "scheduled" if transition["execute_on"] > today else "approved"
        result["kind"] = "none" if result["state"] == "scheduled" else "resume"
    elif status == "needs_review":
        row = store.conn.execute("SELECT block_reasons_json FROM ticker_identity_transition_attempts WHERE transition_id=? ORDER BY rowid DESC LIMIT 1",
                                 (transition["transition_id"],)).fetchone()
        blockers = json.loads(row[0]) if row else ["review_changed"]
        if not isinstance(blockers, list) or any(not isinstance(code, str) for code in blockers):
            raise LifecyclePopulationUnavailable("current_receipt_invalid")
        result.update(state="blocked", kind="recheck", block_reasons=blockers)
    else:
        result["kind"] = "recheck" if review["bucket"] == "current" else "none"
    if review.get("historical"):
        result["kind"] = "none"
    return result, case, assessment


def _project(snapshot, manifest, sources, conn):
    material = snapshot["material"]
    cases = {case["case_id"]: case for case in material["composed_cases"]}
    providers, latest, by_review = {}, {}, {}
    for raw in material["profile_tables"]["security_lifecycle_provider_checks"]:
        row = {**decode_snapshot(raw), "check_id": raw["check_id"], "ordinal": raw["_ordinal"]}
        providers[row["check_id"]] = row
        if row["ticker"] not in latest or (row["at"], row["ordinal"]) > (latest[row["ticker"]]["at"], latest[row["ticker"]]["ordinal"]):
            latest[row["ticker"]] = row
    for mapping in manifest["input_mappings"]:
        if mapping["population"] == "provider_check" and mapping["review_id"] is not None:
            row = providers[mapping["input_id"]]
            previous = by_review.get(mapping["review_id"])
            if previous is None or (row["at"], row["ordinal"]) > (previous["at"], previous["ordinal"]):
                by_review[mapping["review_id"]] = row
    transitions = manifest["retention"]["transitions"]
    store = TickerIdentityTransitionStore(conn) if transitions else None
    enabled = _enabled(conn)
    today = instant(snapshot["at"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    current_transitions = _current_action_transitions(transitions, material)
    reviews = manifest["reviews"]
    if len(current_transitions) != len(transitions):
        reviews = [dict(review) for review in reviews]
        _dispositions(reviews, current_transitions, latest, today=today)
    items = []
    for review in reviews:
        if len(review["tickers"]) != 1:
            raise LifecyclePopulationUnavailable("current_review_identity_invalid")
        ticker = review["tickers"][0]
        members = [cases[key] for key in review["case_ids"] if key in cases]
        names = {case["observation"]["issuer_name"] for case in members if case.get("observation") and case["source"] == "sec_edgar"}
        check = by_review.get(review["review_id"])
        action, action_case, assessment = _action(review, members, current_transitions, store, today=today)
        reason = review["reason"]
        bucket = "attention" if review["bucket"] == "current" else "history"
        if action["state"] == "applied_state_changed" and not review.get("historical"):
            reason, bucket = "applied_state_changed", "attention"
            action["kind"] = "recheck"
        elif action["state"] in {"scheduled", "approved"} and not review.get("historical"):
            reason = "action_scheduled" if action["state"] == "scheduled" else "action_pending"
        if reason not in CURRENT_REVIEW_REASONS or action["state"] not in CURRENT_ACTION_STATES:
            raise LifecyclePopulationUnavailable("current_vocabulary_invalid")
        current_sources = [] if sources is None or review.get("historical") else sources.get(ticker, [])
        collection_state = ("historical" if review.get("historical") else "unavailable" if sources is None
                            else "tracking" if current_sources else "not_tracking")
        diagnostics = listing_operator_detail({"reasons": review["listing_reasons"] + review["continuation_reasons"],
            "provider_codes": check["blockers"] if check else [], "manual_review_required": review["listing_state"] == "unresolved"})
        next_check = None
        if enabled and bucket == "attention" and action_case:
            next_check = next_lifecycle_recheck_at(current_automation_run(action_case), assessment)
        observed_at = review["observed_at"]
        if observed_at is None and check is None:
            times = [case["observation"]["last_observed_at"] for case in members if case.get("observation")]
            observed_at = max(times, key=instant) if times else None
        items.append({
            "review_id": review["review_id"], "case_ids": list(review["case_ids"]), "ticker": ticker,
            "issuer_name": next(iter(names)) if len(names) == 1 else None, "bucket": bucket,
            "finding": review["finding"], "reason": reason,
            "collection": {"state": collection_state, "sources": list(current_sources)},
            "listing": {"state": review["listing_state"], "basis": review["listing_basis"], "ended_on": review["listing_end_date"]},
            "continuation": {"state": review["continuation_state"], "successor_ticker": review["successor_ticker"],
                             "candidate_tickers": list(review["candidate_tickers"])},
            "observed_at": observed_at, "next_check_at": next_check,
            "diagnostics": diagnostics, "next_action": action, "source_checks": _source_checks(check),
            "source_notices": [{"form": case["observation"]["filing_form"], "filed_on": case["observation"]["filing_date"],
                                "text": case["observation"]["description"] or None, "url": _source_url(case["observation"]["evidence_url"])}
                               for case in members if case["source"] == "sec_edgar" and case.get("observation")],
        })
    active = {ticker for ticker, row in latest.items() if classify_provider_listing(
        ticker=ticker, evidence=row["evidence"], today=instant(snapshot["at"]).date(), provider_codes=row["blockers"]).listing_state == "active"}
    tracked_count = len(sources) if sources is not None else None
    active_count = len(active.intersection(sources)) if sources is not None else None
    return {"version": 1, "as_of": snapshot["at"], "source_context": "unavailable" if sources is None else "available",
            "coverage": {"tracked": tracked_count, "confirmed_active": active_count,
                         "unconfirmed": tracked_count - active_count if tracked_count is not None else None},
            "counts": {"attention": sum(row["bucket"] == "attention" for row in items), "history": sum(row["bucket"] == "history" for row in items)},
            "items": sorted(items, key=lambda row: (row["ticker"], row["review_id"]))}


def _read(service, *, at, web_review_id=None):
    at = at if at is not None else datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    paths = (Path(service.market_db_path), Path(service.profile_db_path))
    try:
        identities = [(path.stat().st_dev, path.stat().st_ino) for path in paths]
        with ExitStack() as stack:
            connections = []
            for path in paths:
                conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
                stack.callback(conn.close)
                conn.execute("PRAGMA query_only=ON")
                connections.append(conn)
            versions = [conn.execute("PRAGMA data_version").fetchone()[0] for conn in connections]
            sources = _sources(service.sources_by_ticker())
            snapshot = read_population_snapshot(*paths, at=at)
            manifest = build_population_manifest(snapshot)
            result = _project(snapshot, manifest, sources, connections[1])
            if web_review_id is not None:
                from src.lifecycle_web_projection import latest_web_runs
                from src.lifecycle_web_schema import WebJournalError
                review = next((row for row in result["items"] if row["review_id"] == web_review_id), None)
                try:
                    result["web_runs"] = latest_web_runs(connections[1], review["case_ids"] if review else [], at=at)
                except WebJournalError:
                    raise LifecyclePopulationUnavailable("current_web_journal_unavailable") from None
            if (sources != _sources(service.sources_by_ticker())
                    or versions != [conn.execute("PRAGMA data_version").fetchone()[0] for conn in connections]
                    or identities != [(path.stat().st_dev, path.stat().st_ino) for path in paths]):
                raise LifecyclePopulationUnavailable("current_snapshot_changed")
            return result
    except (OSError, sqlite3.Error):
        raise LifecyclePopulationUnavailable("current_store_unavailable") from None
    except (KeyError, TypeError, ValueError):
        raise LifecyclePopulationUnavailable("current_material_invalid") from None


def list_current_reviews(service, *, at=None, view="attention", ticker=None, case_id=None, limit=50, offset=0):
    if view not in {"attention", "history"} or type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
        raise ValueError("current_review_filter")
    if ticker is not None and not isinstance(ticker, str):
        raise ValueError("ticker")
    if case_id is not None and (not isinstance(case_id, str) or not case_id.strip()):
        raise ValueError("case_id")
    result = _read(service, at=at)
    prefix = (ticker or "").strip().upper()
    # Existing case links resolve across both views, independently of the
    # operator's current page. The normal list keeps its selected view/filter.
    rows = [row for row in result["items"] if (case_id in row["case_ids"] if case_id is not None
            else row["bucket"] == view and row["ticker"].startswith(prefix))]
    return {**result, "items": rows[offset:offset + limit], "page": {"offset": offset, "limit": limit, "total": len(rows)}}


def get_current_review(service, review_id, *, at=None):
    result = _read(service, at=at, web_review_id=review_id)
    row = next((row for row in result["items"] if row["review_id"] == review_id), None)
    if row is None:
        raise KeyError("current_review_not_found")
    return {"version": 1, "as_of": result["as_of"], "item": row, "web_runs": result["web_runs"]}
