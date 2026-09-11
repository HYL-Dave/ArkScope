"""Read-only, digest-bound accounting before lifecycle population changes.

This manifest is an internal dry-run artifact, not action authority or a public
case DTO. Reading it never approves actions, deletes history, or contacts sources.
"""

from __future__ import annotations

from contextlib import ExitStack
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

from src.security_lifecycle import read_market_observations
from src.security_lifecycle_investigation import (
    LifecycleStoreUnavailable, case_id_for, compose_security_lifecycle_audit, observation_fingerprint,
)
from src.security_lifecycle_provider_authority import classify_provider_listing, evidence_dict, validate_provider_material
from src.security_lifecycle_provider_snapshot import canonical_json, decode_snapshot, instant
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch, MARKET_TABLE_SQL, PROFILE_TABLE_SQL,
    verify_market_connection, verify_profile_connection,
)
from src.ticker_identity_schema import (
    IDENTITY_TABLE_SQL, TickerIdentitySchemaMismatch, identity_schema_present,
    verify_ticker_identity_connection,
)


POLICY_VERSION = "lifecycle_population_v1"
_PREFIX = "security_lifecycle_"


class LifecyclePopulationUnavailable(RuntimeError):
    """A bounded inventory failed; no partial population should be published."""


def _digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _identity(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def _rows(conn, tables):
    # Table names come only from the component's schema authority, never input.
    return {
        table: [dict(row) for row in conn.execute(f'SELECT rowid AS _ordinal,* FROM "{table}" ORDER BY rowid')]
        for table in sorted(tables)
    }


def _schema(conn, tables):
    names = sorted(tables)
    placeholders = ",".join("?" for _ in names)
    return [dict(row) for row in conn.execute(
        f"SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name IN ({placeholders}) ORDER BY type,name",
        names,
    )]


def _capture(market, profile, market_conn, profile_conn):
    identity_tables = {}
    if identity_schema_present(profile_conn):
        verify_ticker_identity_connection(profile_conn)
        identity_tables = _rows(profile_conn, IDENTITY_TABLE_SQL)
    return {
        "market_observations": read_market_observations(str(market), limit=None),
        "profile_tables": _rows(profile_conn, PROFILE_TABLE_SQL),
        "identity_tables": identity_tables,
        "composed_cases": compose_security_lifecycle_audit(str(market), str(profile))["cases"],
        "schemas": {
            "market": _schema(market_conn, MARKET_TABLE_SQL),
            "profile": _schema(profile_conn, (*PROFILE_TABLE_SQL, *identity_tables)),
        },
    }


def read_population_snapshot(market_db_path, profile_db_path, *, at: str) -> dict:
    """Capture stable read bounds without holding a transaction across stores.

    Monitors remain in autocommit: a transaction would pin their data_version.
    Any committed concurrent change invalidates the capture, including WAL writes.
    Writers are not paused, and a failed capture is never retried implicitly.
    """
    try:
        canonical_at = instant(at).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, TypeError):
        raise LifecyclePopulationUnavailable("population_time_invalid") from None
    paths = (Path(market_db_path), Path(profile_db_path))
    try:
        if not all(path.is_file() for path in paths):
            raise LifecyclePopulationUnavailable("population_store_unavailable")
        identities = tuple(_identity(path) for path in paths)
        if identities[0] == identities[1]:
            raise LifecyclePopulationUnavailable("population_store_identity_invalid")
        with ExitStack() as stack:
            connections = []
            for path in paths:
                conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
                stack.callback(conn.close)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA query_only=ON")
                connections.append(conn)
            versions = tuple(conn.execute("PRAGMA data_version").fetchone()[0] for conn in connections)
            verify_market_connection(connections[0])
            verify_profile_connection(connections[1])
            material = _capture(*paths, *connections)
            after = tuple(conn.execute("PRAGMA data_version").fetchone()[0] for conn in connections)
            if versions != after or identities != tuple(_identity(path) for path in paths):
                raise LifecyclePopulationUnavailable("population_snapshot_changed")
    except (LifecycleSchemaMismatch, TickerIdentitySchemaMismatch):
        raise LifecyclePopulationUnavailable("population_schema_invalid") from None
    except (OSError, sqlite3.Error, LifecycleStoreUnavailable):
        raise LifecyclePopulationUnavailable("population_store_unavailable") from None
    except (TypeError, ValueError, KeyError):
        raise LifecyclePopulationUnavailable("population_material_invalid") from None
    unsigned = {"version": 1, "at": canonical_at, "material": material}
    return {**unsigned, "sha256": _digest(unsigned)}


def _key(row):
    return row["source"], row["source_ref"], row["ticker"]


def _case_id(row):
    return case_id_for(*_key(row))


def _reconcile(observations, cases, *, source):
    observed = {_key(row) for row in observations if row["source"] == source}
    persisted = {_key(row) for row in cases if row["source"] == source}
    return {
        "matched": sorted(case_id_for(*key) for key in observed & persisted),
        "observation_only": sorted(case_id_for(*key) for key in observed - persisted),
        "case_only": sorted(case_id_for(*key) for key in persisted - observed),
    }


def _provider_for_case(case, latest):
    row = latest.get(case["ticker"])
    if row is None or _case_id(row["observation"]) != case["case_id"]:
        return None
    return row


def _review(case, provider, *, today):
    result = {
        "review_id": "slpr_" + _digest([POLICY_VERSION, case["case_id"]]),
        "case_ids": [case["case_id"]], "tickers": [case["ticker"]],
        "bucket": "current", "finding": "unresolved", "reason": "provider_confirmation_missing",
        "listing_state": "unresolved", "continuation_state": "unavailable",
        "listing_reasons": [], "continuation_reasons": [], "candidate_tickers": [],
        "listing_end_date": None, "successor_ticker": None, "observed_at": None,
        "action_state": "none", "transition_ids": [], "collection_state": "not_observed",
        "listing_basis": "observation",
    }
    if case["source"] != "listing_authority" or provider is None:
        if case["source_presence"] == "source_missing":
            result["reason"] = "source_missing"
        return result
    decision = classify_provider_listing(
        ticker=case["ticker"], evidence=provider["evidence"], today=today,
        provider_codes=provider["blockers"],
    )
    result.update({
        "listing_state": decision.listing_state, "continuation_state": decision.continuation_state,
        "listing_reasons": list(decision.listing_reasons),
        "continuation_reasons": list(decision.continuation_reasons),
        "candidate_tickers": list(decision.candidate_tickers),
        "listing_end_date": decision.listing_end_date, "successor_ticker": decision.successor_ticker,
        "observed_at": provider["at"],
    })
    if decision.listing_state == "active":
        result.update(bucket="history", finding="active", reason="active_confirmed")
    elif decision.continuation_state == "confirmed":
        result.update(finding="replacement_confirmed", reason="continuation_requires_confirmation")
    elif decision.listing_state == "inactive":
        result.update(finding="old_listing_inactive", reason="removal_requires_confirmation")
    else:
        result["reason"] = "provider_confirmation_incomplete"
    return result


def _listing_identity(evidence, ticker, *, filing_date=None):
    identities = set()
    try:
        for raw in evidence:
            if raw["adapter"] != "massive_reference":
                continue
            row = evidence_dict(raw)
            validate_provider_material(row)
            locator = row["source_locator"]
            if locator.get("candidate_ticker") != ticker or locator.get("listing_status") not in {"active", "inactive"}:
                continue
            fields = tuple(locator.get(key) for key in ("composite_figi", "market", "primary_exchange", "security_type", "issuer_cik"))
            if (locator.get("authority") != "massive" or locator.get("adapter") != "massive_reference"
                    or row["source_family"] != "listing_authority" or locator.get("snapshot_complete") is not True
                    or any(not isinstance(value, str) or not value.strip() for value in fields)):
                return None
            if filing_date is not None:
                # A current ticker lookup cannot identify an arbitrary old filing.
                # Only contemporaneous, observation-bound listing evidence joins it.
                as_of = date.fromisoformat(locator["source_as_of"])
                if not filing_date <= as_of <= filing_date + timedelta(days=3):
                    return None
            identities.add((ticker, *fields))
    except (ValueError, KeyError, TypeError):
        return None
    return next(iter(identities)) if len(identities) == 1 else None


def _matching_run(case, tables):
    observation = case["observation"]
    if not observation:
        return None
    runs = [row for row in tables[_PREFIX + "automation_runs"] if row["case_id"] == case["case_id"]
            and row["observation_fingerprint_sha256"] == observation_fingerprint(observation)]
    if not runs:
        return None
    return max(runs, key=lambda row: (row["created_at"], row["_ordinal"]))


def _bound_sec_identity(case, tables):
    observation = case["observation"]
    run = _matching_run(case, tables)
    if not observation or not observation.get("cik") or run is None or run["status"] != "succeeded":
        return None
    evidence = {row["evidence_id"]: row for row in tables[_PREFIX + "evidence"]
                if row["case_id"] == case["case_id"] and row["automation_run_id"] == run["run_id"]}
    regulator_facts = {}
    for fact in tables[_PREFIX + "automation_facts"]:
        source = evidence.get(fact["evidence_id"])
        if (source is None or source["source_family"] != "regulator" or fact["automation_run_id"] != run["run_id"]
                or fact["case_id"] != case["case_id"]):
            continue
        excerpt = source["excerpt"]
        span = excerpt[fact["source_span_start"]:fact["source_span_end"]]
        if (hashlib.sha256(excerpt.encode()).hexdigest() != source["content_sha256"]
                or hashlib.sha256(span.encode()).hexdigest() != fact["cited_text_sha256"]):
            return None
        locator = json.loads(source["source_locator_json"])
        if locator.get("accession") != observation["source_ref"]:
            continue
        regulator_facts.setdefault(fact["evidence_id"], {}).setdefault(fact["fact_type"], set()).add(
            canonical_json(json.loads(fact["normalized_value_json"])))
    required = {"source_ticker": observation["ticker"], "issuer_cik": observation["cik"], "security_class": "common_stock"}
    if not any(all(facts.get(key) == {canonical_json(value)} for key, value in required.items()) for facts in regulator_facts.values()):
        return None
    key = _listing_identity(list(evidence.values()), case["ticker"], filing_date=date.fromisoformat(observation["filing_date"]))
    if key is None or key[-1] != observation["cik"] or key[-2] != "CS":
        return None
    return key


def _regulator_question(case, tables, *, today):
    observation = case["observation"]
    if any(row["effective_date"] and date.fromisoformat(row["effective_date"]) > today for row in observation["kinds"]):
        return "regulator_event_pending"
    run = _matching_run(case, tables)
    if run is None:
        return None
    regulator_ids = {row["evidence_id"] for row in tables[_PREFIX + "evidence"] if row["source_family"] == "regulator"
                     and row["automation_run_id"] == run["run_id"] and row["case_id"] == case["case_id"]}
    for fact in tables[_PREFIX + "automation_facts"]:
        if fact["automation_run_id"] != run["run_id"] or fact["evidence_id"] not in regulator_ids:
            continue
        value = json.loads(fact["normalized_value_json"])
        if fact["fact_type"] == "effective_date" and date.fromisoformat(value) > today:
            return "regulator_event_pending"
        if (fact["fact_type"] == "successor_ticker" and value != case["ticker"]) or fact["fact_type"] == "destination_venue":
            return "regulator_identity_question"
    return None


def _consolidate(reviews, composed, latest, tables, *, today):
    groups = {}
    for case_id, review in reviews.items():
        case = composed.get(case_id)
        if case is None or case["source"] == "listing_authority":
            ticker = review["tickers"][0]
            provider = latest.get(ticker) if case is None else _provider_for_case(case, latest)
            key = None if provider is None else _listing_identity(provider["evidence"], ticker)
        else:
            key = _bound_sec_identity(case, tables)
        groups.setdefault(("case", case_id) if key is None else ("listing", *key), []).append(case_id)
    merged, by_case, coverage = [], {}, []
    for key, case_ids in groups.items():
        provider_id = next((case_id for case_id in case_ids if case_id not in composed or composed[case_id]["source"] == "listing_authority"), None)
        base = reviews[provider_id or min(case_ids)]
        combined = {**base, "case_ids": sorted(case_ids), "identity_state": "bound" if key[0] == "listing" else "unconfirmed"}
        if key[0] == "listing":
            combined["review_id"] = "slpr_" + _digest([POLICY_VERSION, list(key)])
        if combined["finding"] == "active":
            for case_id in case_ids:
                case = composed.get(case_id)
                if case is not None and case["source"] != "listing_authority":
                    reason = _regulator_question(case, tables, today=today)
                    if reason:
                        combined.update(bucket="current", finding="unresolved", reason=reason)
                        break
        if not set(case_ids).intersection(composed) and combined["finding"] == "active":
            coverage.extend(combined["tickers"])
            continue
        merged.append(combined)
        by_case.update({case_id: combined for case_id in case_ids})
    return sorted(merged, key=lambda row: row["review_id"]), by_case, sorted(coverage)


def _provider_case(row):
    return {**row["observation"], "case_id": _case_id(row["observation"]), "source_presence": "present"}


def _historical_provider_reviews(history, latest, reviews, by_case, coverage, *, today):
    keys = {row["check_id"]: _listing_identity(row["evidence"], row["ticker"]) for row in history}
    historical = {}
    changed = set()
    for row in history:
        key, current_key = keys[row["check_id"]], keys[latest[row["ticker"]]["check_id"]]
        if key is not None and current_key is not None and key != current_key:
            changed.add(row["ticker"])
            if key not in historical or (row["at"], row["ordinal"]) > (historical[key]["at"], historical[key]["ordinal"]):
                historical[key] = row
    for ticker in sorted(changed):
        row = latest[ticker]
        case_id = _case_id(row["observation"])
        if case_id not in by_case:
            view = _review(_provider_case(row), row, today=today)
            view["identity_state"] = "bound"
            view["review_id"] = "slpr_" + _digest([POLICY_VERSION, ["listing", *keys[row["check_id"]]]])
            reviews.append(view)
            by_case[case_id] = view
        by_case[case_id].update(bucket="current", finding="unresolved", reason="listing_identity_changed")
    old_views = {}
    for key, row in historical.items():
        view = _review(_provider_case(row), row, today=instant(row["at"]).date())
        view.update(review_id="slpr_" + _digest([POLICY_VERSION, "historical_listing", list(key)]),
                    bucket="history", reason="superseded_listing_identity", identity_state="bound", historical=True)
        reviews.append(view)
        old_views[key] = view
    check_views = {row["check_id"]: old_views.get(keys[row["check_id"]], by_case.get(_case_id(row["observation"]))) for row in history}
    return check_views, [ticker for ticker in coverage if ticker not in changed]


def _bind_transition_reviews(transitions, reviews, by_case, check_views, composed, history, latest):
    history_by_fingerprint = {observation_fingerprint(row["observation"]): row for row in history}
    unbound = {}
    for transition in transitions:
        case_id = transition["case_id"]
        approved = transition["approved_observation_fingerprint_sha256"]
        observation = composed[case_id]["observation"]
        check = history_by_fingerprint.get(approved)
        target = None
        if check is not None and _case_id(check["observation"]) == case_id:
            old_key = _listing_identity(check["evidence"], check["ticker"])
            current = latest[check["ticker"]]
            proposed = check_views.get(check["check_id"])
            if (check["check_id"] == current["check_id"] or (proposed and proposed.get("historical"))
                    or (old_key is not None and old_key == _listing_identity(current["evidence"], current["ticker"]))):
                target = proposed
        elif observation and observation_fingerprint(observation) == approved:
            target = by_case[case_id]
        if target is None:
            # A receipt with no surviving identity binding is still retained,
            # but cannot describe a different current listing as already removed.
            identity = (case_id, approved)
            if identity not in unbound:
                view = (_review(_provider_case(check), check, today=instant(check["at"]).date()) if check else dict(by_case[case_id]))
                view.update(review_id="slpr_" + _digest([POLICY_VERSION, "historical_action", list(identity)]),
                            case_ids=[case_id], bucket="history", reason="prior_action_history", historical=True)
                reviews.append(view)
                unbound[identity] = view
            target = unbound[identity]
            if check is not None:
                check_views[check["check_id"]] = target
        transition["review_id"] = target["review_id"]


def _transition_inventory(tables, identity_tables, assessments):
    from src.ticker_identity_transition import profile_snapshot_sha256
    proposals = {row["proposal_id"]: row for row in tables[_PREFIX + "action_proposals"]}
    transitions = []
    for row in identity_tables.get("ticker_identity_transitions", []):
        preview = json.loads(row["approved_preview_json"])
        proposal_ids = json.loads(row["proposal_ids_json"])
        assessment = assessments.get(row["assessment_id"])
        if (not isinstance(preview, dict) or preview.get("preview_sha256") != row["approved_preview_sha256"]
                or profile_snapshot_sha256(preview) != row["approved_preview_sha256"]
                or not isinstance(proposal_ids, list) or any(not isinstance(value, str) for value in proposal_ids)
                or assessment is None or assessment["case_id"] != row["case_id"]
                or any(value not in proposals or proposals[value]["assessment_id"] != row["assessment_id"] for value in proposal_ids)):
            raise LifecyclePopulationUnavailable("population_receipt_invalid")
        attempts = [item for item in identity_tables["ticker_identity_transition_attempts"] if item["transition_id"] == row["transition_id"]]
        activity = [item for item in identity_tables["ticker_identity_transition_activity"] if item["transition_id"] == row["transition_id"]]
        if row["status"] in {"applied", "reversed"} and (
                not any(item["status"] == "applied" for item in attempts)
                or not any(item["activity_type"] == "applied" for item in activity)):
            raise LifecyclePopulationUnavailable("population_receipt_incomplete")
        transitions.append({
            **{key: row[key] for key in (
                "transition_id", "case_id", "assessment_id", "kind", "status", "source_ticker", "successor_ticker",
                "execute_on", "approved_at", "applied_at", "updated_at", "approval_authority", "approved_preview_sha256",
                "approved_observation_fingerprint_sha256", "after_snapshot_sha256",
            )},
            "proposal_ids": sorted(proposal_ids), "attempt_ids": sorted(item["attempt_id"] for item in attempts),
            "activity_ids": sorted(item["activity_id"] for item in activity),
        })
    return sorted(transitions, key=lambda row: (row["updated_at"], row["transition_id"]))


def _retain_applied_listing(review, latest, *, today):
    if review["listing_state"] != "unresolved" or set(review["listing_reasons"]) != {"listing_directory_stale"}:
        return
    check = latest.get(review["tickers"][0])
    if check is None or instant(check["at"]).date() > today:
        return
    historical = _review(_provider_case(check), check, today=instant(check["at"]).date())
    if historical["listing_state"] != "inactive":
        return
    # Freshness still gates new actions. An identity-bound, applied receipt can
    # retain the old listing fact; a newer contradictory check cannot be ignored.
    for key in ("listing_state", "continuation_state", "continuation_reasons", "candidate_tickers",
                "listing_end_date", "successor_ticker", "finding"):
        review[key] = historical[key]
    review["listing_basis"] = "applied_receipt"


def _dispositions(reviews, transitions, latest, *, today):
    for review in reviews:
        related = [row for row in transitions if row["review_id"] == review["review_id"]]
        review["transition_ids"] = sorted(row["transition_id"] for row in related)
        if not related:
            continue
        pending = [row for row in related if row["status"] in {"approved", "needs_review"}]
        applied = [row for row in related if row["status"] == "applied"]
        current = (pending or applied or related)[-1]
        review["action_state"] = current["status"]
        if review.get("historical"):
            continue
        if review["reason"] == "source_missing":
            continue
        if pending:
            review["bucket"] = "current"
            review["reason"] = ("action_needs_review" if current["status"] == "needs_review" else
                                "action_scheduled" if date.fromisoformat(current["execute_on"]) > today else "action_pending")
        elif applied:
            _retain_applied_listing(review, latest, today=today)
            if review["listing_state"] == "active":
                review.update(bucket="current", reason="listing_reappeared_after_action")
            elif review["listing_state"] == "unresolved":
                review.update(bucket="current", reason="listing_recheck_required")
            elif current["kind"] == "terminal_delisting":
                if review["continuation_state"] == "not_observed":
                    review.update(bucket="history", reason="removal_applied")
                else:
                    review.update(bucket="current", reason="continuation_followup_pending")
            elif review["continuation_state"] == "confirmed" and review["successor_ticker"] == current["successor_ticker"]:
                review.update(bucket="history", reason="symbol_change_applied")
            else:
                review.update(bucket="current", reason="continuation_followup_pending")


def _retention(tables, identity_tables):
    def rows(name):
        return tables[_PREFIX + name]
    assessments = {row["assessment_id"]: row for row in rows("assessments")}
    evidence = {row["evidence_id"]: row for row in rows("evidence")}
    dependencies = []
    fact_dependencies, translation_dependencies = [], []
    referenced = set()
    for row in rows("assessment_evidence"):
        assessment = assessments.get(row["assessment_id"])
        if assessment is None:
            raise LifecyclePopulationUnavailable("population_dependency_invalid")
        evidence_id = row["evidence_id"]
        if evidence_id is not None:
            target = evidence.get(evidence_id)
            if target is None or target["case_id"] != assessment["case_id"] or target["content_sha256"] != row["cited_content_sha256"]:
                raise LifecyclePopulationUnavailable("population_dependency_invalid")
            referenced.add(evidence_id)
        dependencies.append({
            "assessment_id": row["assessment_id"], "case_id": assessment["case_id"],
            "reference_kind": row["reference_kind"], "evidence_id": evidence_id,
            "content_sha256": row["cited_content_sha256"],
        })
    for row in rows("automation_facts"):
        target = evidence.get(row["evidence_id"])
        if target is None or target["case_id"] != row["case_id"] or target["automation_run_id"] != row["automation_run_id"]:
            raise LifecyclePopulationUnavailable("population_dependency_invalid")
        referenced.add(row["evidence_id"])
        fact_dependencies.append({key: row[key] for key in ("fact_id", "case_id", "evidence_id", "automation_run_id")})
    for row in rows("evidence_translations"):
        target = evidence.get(row["evidence_id"])
        if target is None or target["content_sha256"] != row["evidence_content_sha256"]:
            raise LifecyclePopulationUnavailable("population_dependency_invalid")
        referenced.add(row["evidence_id"])
        translation_dependencies.append({"evidence_id": row["evidence_id"], "content_sha256": row["evidence_content_sha256"], "locale": row["locale"]})
    transitions = _transition_inventory(tables, identity_tables, assessments)
    return {
        "assessment_ids": sorted(assessments), "evidence_ids": sorted(evidence),
        "referenced_evidence_ids": sorted(referenced),
        "unreferenced_evidence_ids": sorted(set(evidence) - referenced),
        "assessment_dependencies": dependencies,
        "fact_dependencies": fact_dependencies, "translation_dependencies": translation_dependencies,
        "proposal_ids": sorted(row["proposal_id"] for row in rows("action_proposals")),
        "transition_ids": sorted(row["transition_id"] for row in transitions),
        "transitions": transitions,
        "table_counts": {name: len(value) for name, value in sorted({**tables, **identity_tables}.items())},
        "deletion_candidates": [],
    }


def build_population_manifest(snapshot: dict) -> dict:
    """Pure classification of a sealed local capture; never an execution plan."""
    try:
        if (set(snapshot) != {"version", "at", "material", "sha256"}
                or type(snapshot["version"]) is not int or snapshot["version"] != 1):
            raise LifecyclePopulationUnavailable("population_snapshot_invalid")
        unsigned = {key: snapshot[key] for key in ("version", "at", "material")}
        if snapshot["sha256"] != _digest(unsigned):
            raise LifecyclePopulationUnavailable("population_snapshot_digest")
        material = snapshot["material"]
        if (not isinstance(material, dict) or set(material) != {
                "market_observations", "profile_tables", "identity_tables", "composed_cases", "schemas"}
                or not isinstance(material["schemas"], dict)
                or set(material["schemas"]) != {"market", "profile"}
                or any(not isinstance(material[key], list) or any(not isinstance(row, dict) for row in material[key])
                       for key in ("market_observations", "composed_cases"))):
            raise LifecyclePopulationUnavailable("population_material_invalid")
        for key, expected in (("profile_tables", set(PROFILE_TABLE_SQL)), ("identity_tables", set(IDENTITY_TABLE_SQL))):
            rows = material[key]
            if (not isinstance(rows, dict) or (set(rows) != expected and not (key == "identity_tables" and not rows))
                    or any(not isinstance(value, list) or any(not isinstance(row, dict) for row in value) for value in rows.values())):
                raise LifecyclePopulationUnavailable("population_material_invalid")
        return _build(snapshot)
    except (KeyError, ValueError, TypeError):
        raise LifecyclePopulationUnavailable("population_material_invalid") from None


def _build(snapshot):
    material = snapshot["material"]
    tables = material["profile_tables"]
    observations = material["market_observations"]
    cases = tables[_PREFIX + "cases"]
    composed = {row["case_id"]: row for row in material["composed_cases"]}
    if any(row["case_id"] != _case_id(row) for row in cases):
        raise LifecyclePopulationUnavailable("population_identity_invalid")
    history = [{**decode_snapshot(row), "check_id": row["check_id"], "ordinal": row["_ordinal"]}
               for row in tables[_PREFIX + "provider_checks"]]
    latest = {}
    for row in sorted(history, key=lambda row: (row["at"], row["ordinal"])):
        latest[row["ticker"]] = row
    tracked = {row["ticker"] for row in history if row["state"] != "active"}
    projected = [latest[ticker]["observation"] for ticker in sorted(tracked)]
    expected = {_case_id(row) for row in (*observations, *projected)} | {row["case_id"] for row in cases}
    if set(composed) != expected:
        raise LifecyclePopulationUnavailable("population_composition_incomplete")
    sec_diff = _reconcile(observations, cases, source="sec_edgar")
    provider_diff = _reconcile(projected, cases, source="listing_authority")
    provider_diff = {
        "virtual": provider_diff["observation_only"], "persisted": provider_diff["matched"],
        "case_only": provider_diff["case_only"],
    }
    today = instant(snapshot["at"]).date()
    reviews = {case_id: _review(row, _provider_for_case(row, latest), today=today) for case_id, row in composed.items()}
    for ticker, row in sorted(latest.items()):
        case_id = _case_id(row["observation"])
        if case_id in reviews:
            continue
        candidate = _review({"case_id": case_id, **row["observation"], "source_presence": "present"}, row, today=today)
        # Even always-active checks can join an existing, identity-bound review.
        reviews[case_id] = candidate
    review_rows, reviews, coverage = _consolidate(reviews, composed, latest, tables, today=today)
    check_views, coverage = _historical_provider_reviews(history, latest, review_rows, reviews, coverage, today=today)
    retention = _retention(tables, material["identity_tables"])
    _bind_transition_reviews(retention["transitions"], review_rows, reviews, check_views, composed, history, latest)
    _dispositions(review_rows, retention["transitions"], latest, today=today)
    mappings = []
    for population, rows in (("market_observation", observations), ("profile_case", cases)):
        for row in rows:
            case_id = _case_id(row)
            review = reviews[case_id]
            mappings.append({
                "population": population, "input_id": str(row["id"]) if population == "market_observation" else case_id,
                "case_id": case_id, "review_id": review["review_id"],
                "destination": review["bucket"], "reason": review["reason"],
            })
    for row in history:
        case_id = _case_id(row["observation"])
        review = check_views[row["check_id"]]
        superseded = row["check_id"] != latest[row["ticker"]]["check_id"]
        mappings.append({
            "population": "provider_check", "input_id": row["check_id"], "case_id": case_id,
            "review_id": review["review_id"] if review else None,
            "destination": "history" if superseded else (review["bucket"] if review else "coverage"),
            "reason": ("superseded_provider_check" if superseded and not (review and review.get("historical"))
                       else review["reason"] if review else "active_confirmed"),
        })
    if len({(row["population"], row["input_id"]) for row in mappings}) != len(observations) + len(cases) + len(history):
        raise LifecyclePopulationUnavailable("population_accounting_incomplete")
    screened = [row for row in composed.values() if (row.get("sec_admission") or {}).get("state") == "screened_out"]
    result = {
        "version": 1, "policy_version": POLICY_VERSION, "observed_at": snapshot["at"],
        "snapshot_sha256": snapshot["sha256"],
        "counts": {
            "market_observations": len(observations), "profile_cases": len(cases), "provider_checks": len(history),
            "provider_latest": len(latest), "provider_projected_observations": len(projected), "composed_cases": len(composed),
            "legacy_visible_cases": sum(row["source_presence"] == "present" and row not in screened for row in composed.values()),
            "legacy_screened_cases": len(screened),
            "current_reviews": sum(row["bucket"] == "current" for row in review_rows),
            "history_reviews": sum(row["bucket"] == "history" for row in review_rows), "coverage_only_tickers": len(coverage),
        },
        "sec_reconciliation": sec_diff, "provider_reconciliation": provider_diff,
        "input_mappings": sorted(mappings, key=lambda row: (row["population"], row["input_id"])),
        "reviews": sorted(review_rows, key=lambda row: row["review_id"]), "coverage_only": coverage,
        "retention": retention,
        "automatic_actions": [], "deletion_authorized": False,
    }
    return {**result, "manifest_sha256": _digest(result)}


def read_population_manifest(market_db_path, profile_db_path, *, at: str) -> dict:
    return build_population_manifest(read_population_snapshot(market_db_path, profile_db_path, at=at))
