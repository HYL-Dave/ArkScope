"""Action-bound attended review over existing assessment and approval records.

Preparation grants no authority. Only the confirmation command writes the
versioned review material into an attended transition's approval receipt.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Mapping

from src.security_lifecycle_decision_policy import AUTOMATION_POLICY_VERSION, RULE_VERSIONS
from src.security_lifecycle_investigation import (
    SecurityLifecycleInvestigationStore, assessment_fingerprint, case_id_for, observation_fingerprint,
)
from src.security_lifecycle_provider_authority import provider_transition_guard
from src.security_lifecycle_provider_store import ProviderCheckStore, _instant
from src.ticker_identity_transition import (
    TransitionOptions, _canonical_json, _execution_date, _sha256, _ticker,
    build_transition_effects, build_transition_preview, profile_snapshot_sha256,
)


REVIEW_VERSION = 1
_FINDING_FIELDS = (
    "conclusion", "impact_summary", "relevance", "confidence", "outcomes", "successor_ticker",
    "destination_venue", "effective_date", "counterparty_name", "counterparty_ticker", "counterparty_cik",
    "consideration_currency", "cash_per_security_decimal", "exchange_ratio_decimal",
)
_PROVENANCE_FIELDS = (
    "assessment_id", "revision", "author", "created_at", "automation_method", "automation_run_id",
    "rule_id", "rule_version", "decision_provenance_sha256", "citations",
)
_SOURCE_FIELDS = (
    "evidence_id", "kind", "source_family", "adapter", "source_url", "title", "publisher", "domain",
    "source_published_at", "retrieved_at", "mime_type", "document_status",
)
_PUBLIC_PACKET_FIELDS = (
    "version", "case_id", "assessment_id", "packet_sha256", "source_ticker", "action", "execute_on",
    "provider_observed_at", "active_sources", "caveats", "ready", "block_reasons",
)


def now(service) -> str:
    return service._clock() if service._clock else datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def packet_digest(packet: Mapping) -> str:
    return hashlib.sha256(_canonical_json({key: value for key, value in packet.items() if key != "packet_sha256"}).encode()).hexdigest()


def _citation_material(store, assessment):
    references = []
    for citation in assessment["citations"]:
        if citation["reference_kind"] == "observation":
            continue
        try:
            row = store.get_evidence(citation["evidence_id"])
        except KeyError:
            raise ValueError("review_citation_invalid") from None
        digest = hashlib.sha256(row["excerpt"].encode("utf-8")).hexdigest()
        if (row["case_id"] != assessment["case_id"] or digest != row["content_sha256"]
                or digest != citation["cited_content_sha256"]):
            raise ValueError("review_citation_invalid")
        references.append({**{key: row[key] for key in _SOURCE_FIELDS}, "content_sha256": digest,
            "source_document_sha256": row["source_document_sha256"], "source_locator_json": row["source_locator_json"]})
    return references


def project_packet(packet):
    """Project the reviewed action without exporting the internal binding material."""
    effects = packet["effects"]
    projected_effects = {
        "watchlists": {action: [{key: row[key] for key in ("list_name", "ticker")} for row in effects["watchlists"][action]]
                       for action in ("add", "archive", "reactivate", "unchanged")},
        "legacy_config_seed": {action: [{key: row[key] for key in ("source_key", "ticker")} for row in effects["legacy_config_seed"][action]]
                               for action in ("add", "archive", "reactivate", "unchanged")},
        "editable_tags_to_copy": [{key: row[key] for key in ("facet", "value", "source", "ticker")} for row in effects["editable_tags_to_copy"]],
        "priority": {key: effects["priority"][key] for key in ("resolution", "result_value", "source_value", "successor_value", "write_successor")},
        "suppression": {key: effects["suppression"][key] for key in ("hide_source", "source_hidden", "successor_hidden", "unhide_successor")},
    }
    if "sa_tracking_memberships" in effects:
        projected_effects["sa_tracking_memberships"] = [
            {"ticker": row["ticker"], "picked_date": row["picked_date"], "portfolio_status": row["portfolio_status"],
             "current_tracking": bool(row["current_tracking"]), "removed": row["removed_at"] is not None}
            for row in effects["sa_tracking_memberships"]]
    return {**{key: packet[key] for key in _PUBLIC_PACKET_FIELDS}, "effects": projected_effects,
            **({"source_gaps": [{key: gap[key] for key in ("url", "reason")} for gap in packet["source_gaps"]]}
               if "source_gaps" in packet else {}),
            "finding": {key: packet["finding"][key] for key in _FINDING_FIELDS},
            "options": {key: packet["options"][key] for key in ("execute_on", "priority_resolution", "unhide_successor")},
            "source_references": [{key: row[key] for key in _SOURCE_FIELDS} for row in packet["source_references"]]}


def _proposal_vetoes(store, *, case, assessment, kind):
    if kind is None:
        return ()
    rows = [row for row in store.list_proposals(case["case_id"])
            if row["assessment_id"] == assessment["assessment_id"] and row["source_ticker"] == case["ticker"]]
    fingerprint = assessment_fingerprint(assessment)
    if any(row["status"] == "proposed" and row["assessment_fingerprint_sha256"] != fingerprint for row in rows):
        return ("stale_assessment",)
    required_action = "notify" if kind == "terminal_delisting" else "remap_symbol"
    replacement = None if kind == "terminal_delisting" else assessment["successor_ticker"]
    required = [row for row in rows if row["action_type"] == required_action and row["replacement_ticker"] == replacement]
    # Missing recommendations are staged on confirmation; an existing dismissal
    # must not look available now and then fail only after the user confirms.
    if required and not any(row["status"] == "proposed" and row["block_reason"] is None for row in required):
        return ("proposal_missing" if kind == "terminal_delisting" else "remap_proposal_missing",)
    return ()


def prepare_on_connection(service, conn, *, case_id, assessment_id, options, web_read=None):
    store = SecurityLifecycleInvestigationStore(conn)
    case = store.get_case_identity(case_id)
    assessment = store.get_assessment(assessment_id)
    if assessment["case_id"] != case_id:
        raise ValueError("assessment_case_mismatch")
    from src.lifecycle_web_review import acceptance_for, prepare_on_connection as prepare_web
    adoption = acceptance_for(conn, assessment_id)
    if adoption is not None:
        return prepare_web(service, conn, run_id=adoption["run_id"], options=options, web_read=web_read)
    at = now(service)
    sources = service._read_service.sources_by_ticker()
    active_sources = None if sources is None else tuple(sources.get(case["ticker"], ()))
    blockers = []
    latest = conn.execute("SELECT assessment_id,revision FROM security_lifecycle_assessments WHERE case_id=? ORDER BY revision DESC LIMIT 1",
                          (case_id,)).fetchone()
    if latest["assessment_id"] != assessment_id:
        blockers.append("assessment_superseded")
    references = _citation_material(store, assessment)
    # Web findings require their own validated persisted provenance. This entry
    # does not promote SEC, manual evidence, or a prior accepted row to that lane.
    check = ProviderCheckStore.latest_for_connection(conn, case["ticker"])
    observation = None if check is None else check["observation"]
    if (case["source"] != "listing_authority" or observation is None
            or case_id_for(observation["source"], observation["source_ref"], observation["ticker"]) != case_id):
        blockers.append("listing_authority_required")
        observation = None
    fingerprint = None if observation is None else observation_fingerprint(observation)
    if fingerprint is not None:
        try:
            store.validate_assessment_acceptance(assessment_id, observation_fingerprint_sha256=fingerprint,
                acceptance_authority="human", at=at, allow_accepted=True)
        except ValueError as exc:
            blockers.append(str(exc))
    else:
        blockers.append("source_observation_missing")
    source = _ticker(case["ticker"])
    successor = _ticker(assessment.get("successor_ticker"))
    outcomes = frozenset(assessment["outcomes"])
    kind = None
    if outcomes == {"listing_ended"} and successor is None:
        kind = "terminal_delisting"
    elif "symbol_changed" in outcomes and outcomes <= {"symbol_changed", "venue_transfer"} and successor and successor != source:
        kind = "symbol_continuation"
    else:
        blockers.append("outcome_not_executable")
    blockers.extend(_proposal_vetoes(store, case=case, assessment=assessment, kind=kind))
    if assessment["relevance"] != "direct_tracked_security":
        blockers.append("assessment_not_direct")
    execute_on, date_blocker = _execution_date(options, assessment)
    if date_blocker:
        blockers.append(date_blocker)
    if fingerprint and kind:
        blockers.extend(provider_transition_guard(conn, ticker=source, observation_fingerprint_sha256=fingerprint,
            transition_kind=kind, successor_ticker=successor, effective_date=assessment["effective_date"], at=at,
            human_accepted=True))
    effects = build_transition_effects(conn, source_ticker=source, successor_ticker=successor,
        transition_kind=kind, sources=active_sources, options=options)
    blockers.extend(effects["block_reasons"])
    packet = {
        "version": REVIEW_VERSION,
        "case_id": case_id,
        "assessment_id": assessment_id,
        "latest_assessment": {"assessment_id": latest["assessment_id"], "revision": latest["revision"]},
        "source_ticker": source,
        "action": kind,
        "options": asdict(options),
        "execute_on": execute_on,
        "finding": {key: assessment.get(key) for key in _FINDING_FIELDS},
        "provenance": {key: assessment.get(key) for key in _PROVENANCE_FIELDS},
        "source_references": references,
        "observation_fingerprint_sha256": fingerprint,
        "evidence_set_sha256": assessment["evidence_set_sha256"],
        "provider_check_sha256": check["digest"] if observation else None,
        "provider_observed_at": check["at"] if observation else None,
        "policy_version": AUTOMATION_POLICY_VERSION,
        "provider_rule_version": RULE_VERSIONS["lifecycle.provider_listing_status"],
        "active_sources": effects["active_sources"],
        "effects": effects["effects"],
        "profile_state_sha256": effects["profile_state_sha256"],
        "caveats": effects["caveats"],
        "ready": kind is not None and not blockers,
        "block_reasons": sorted(set(blockers)),
    }
    packet["packet_sha256"] = packet_digest(packet)
    return packet, case, assessment


def confirmation_for(transition):
    preview = transition["approved_preview"]
    value = preview.get("review_confirmation")
    if not isinstance(value, dict) or set(value) != {"version", "packet_sha256", "actor", "action", "confirmed_at", "packet"}:
        raise ValueError("review_confirmation_invalid")
    try:
        if _instant(value["confirmed_at"]) > _instant(transition["approved_at"]):
            raise ValueError("review_confirmation_invalid")
    except (AttributeError, TypeError, ValueError):
        raise ValueError("review_confirmation_invalid") from None
    packet = value["packet"]
    if (type(value["version"]) is not int or value["version"] != REVIEW_VERSION or value["actor"] != "attended_user"
            or transition["approval_authority"] != "attended_user" or not isinstance(packet, dict)
            or packet_digest(packet) != value["packet_sha256"] or packet.get("packet_sha256") != value["packet_sha256"]
            or type(packet.get("version")) is not int or packet["version"] != REVIEW_VERSION
            or packet.get("ready") is not True or packet.get("block_reasons")
            or packet.get("case_id") != transition["case_id"] or packet.get("assessment_id") != transition["assessment_id"]
            or packet.get("action") != transition["kind"] or value["action"] != transition["kind"]
            or packet.get("effects") != preview.get("effects") or packet.get("execute_on") != transition["execute_on"]
            or profile_snapshot_sha256(preview) != transition["approved_preview_sha256"]):
        raise ValueError("review_confirmation_invalid")
    return value


def approved_preview(conn, *, packet, case, assessment, confirmation, at, web_read=None):
    store = SecurityLifecycleInvestigationStore(conn)
    preview = build_transition_preview(conn, case=case, assessment=assessment,
        proposals=store.project_proposals(case["case_id"], observation_fingerprint_sha256=packet["observation_fingerprint_sha256"]),
        observation_fingerprint_sha256=packet["observation_fingerprint_sha256"], sources=packet["active_sources"],
        options=TransitionOptions(**packet["options"]), at=at, web_read=web_read)
    if preview["effects"] != packet["effects"] or preview["profile_state_sha256"] != packet["profile_state_sha256"]:
        raise ValueError("review_changed")
    preview["review_confirmation"] = confirmation
    preview["preview_sha256"] = profile_snapshot_sha256(preview)
    return preview


def prepare(service, case_id, *, assessment_id, options):
    from src.lifecycle_web_review import validated_adoption_read
    web_read = validated_adoption_read(service, assessment_id=assessment_id)
    with service._profile_connection(write=False) as conn:
        conn.execute("BEGIN")
        return prepare_on_connection(service, conn, case_id=case_id, assessment_id=assessment_id, options=options, web_read=web_read)[0]


def _matching_transition(store, *, case_id, assessment_id, action, packet_sha256, options):
    cursor = store.conn.execute("SELECT transition_id FROM ticker_identity_transitions WHERE case_id=? AND assessment_id=? AND kind=?",
                                (case_id, assessment_id, action))
    row = cursor.fetchone()
    if row is None:
        return None
    transition = store.get(str(row[0]))
    if "review_confirmation" not in transition["approved_preview"]:
        return None
    confirmation = confirmation_for(transition)
    if confirmation["packet_sha256"] != packet_sha256 or confirmation["packet"]["options"] != asdict(options):
        return None
    return transition


def _result(service, transition_id, *, repeated=False):
    with service._profile_connection(write=False) as conn:
        conn.execute("BEGIN")
        store = service._store(conn)
        transition = store.get(transition_id)
        confirmation = confirmation_for(transition)
        status = transition["status"]
        matches = None
        blockers = []
        if status == "applied":
            readiness = store.reverse_readiness(transition_id)
            matches = readiness["expected_state_sha256"] == readiness["observed_state_sha256"]
            status = ("already_applied" if repeated else "applied") if matches else "applied_state_changed"
        elif status == "approved":
            status = "scheduled" if transition["execute_on"] > service._new_york_date() else "approved"
        elif status == "needs_review":
            row = conn.execute("SELECT block_reasons_json FROM ticker_identity_transition_attempts WHERE transition_id=? ORDER BY rowid DESC LIMIT 1",
                               (transition_id,)).fetchone()
            blockers = json.loads(row[0]) if row else ["review_changed"]
            status = "blocked"
        return {"version": REVIEW_VERSION, "status": status, "transition_id": transition_id,
                "case_id": transition["case_id"], "packet_sha256": confirmation["packet_sha256"],
                "action": transition["kind"], "source_ticker": transition["source_ticker"],
                "successor_ticker": transition["successor_ticker"], "execute_on": transition["execute_on"],
                "applied_at": transition["applied_at"], "current_effects_match": matches, "block_reasons": blockers}


def execute(service, transition_id, *, before_write, trigger="attended_user", web_read=None):
    before_write()
    with service._profile_connection(write=True) as conn:
        store = service._store(conn)
        if web_read is None:
            from src.lifecycle_web_review import validated_adoption_read
            web_read = validated_adoption_read(service, conn=conn, assessment_id=store.get(transition_id)["assessment_id"])
        if web_read is not None:
            before_write()
        conn.execute("BEGIN IMMEDIATE")
        transition = store.get(transition_id)
        confirmation = confirmation_for(transition)
        if transition["status"] != "approved" or transition["execute_on"] > service._new_york_date():
            conn.rollback()
            return _result(service, transition_id, repeated=transition["status"] == "applied")
        try:
            packet, case, assessment = prepare_on_connection(service, conn, case_id=transition["case_id"],
                assessment_id=transition["assessment_id"], options=TransitionOptions(**confirmation["packet"]["options"]), web_read=web_read)
            current = None
            if packet["ready"] and packet["packet_sha256"] == confirmation["packet_sha256"]:
                current = approved_preview(conn, packet=packet, case=case, assessment=assessment, confirmation=confirmation, at=now(service), web_read=web_read)
            before_write()
            store.apply(transition_id, current_preview=current, expected_preview_sha256=transition["approved_preview_sha256"],
                        trigger=trigger, _caller_transaction=True, web_read=web_read)
            service._review_step("application_staged")
            before_write()
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    service._review_step("application_committed")
    return _result(service, transition_id)


def confirm(service, case_id, *, assessment_id, packet_sha256, action, options, before_write):
    from src.ticker_identity_service import TickerIdentityConflict

    _sha256("review_digest", packet_sha256)
    if action not in {"terminal_delisting", "symbol_continuation"}:
        raise ValueError("review_action")
    before_write()
    with service._profile_connection(write=True) as conn:
        from src.lifecycle_web_review import validated_adoption_read
        web_read = validated_adoption_read(service, conn=conn, assessment_id=assessment_id)
        if web_read is not None:
            before_write()
        conn.execute("BEGIN IMMEDIATE")
        store = service._store(conn)
        try:
            existing = _matching_transition(store, case_id=case_id, assessment_id=assessment_id, action=action,
                                            packet_sha256=packet_sha256, options=options)
            if existing is not None:
                transition_id = existing["transition_id"]
                conn.rollback()
            else:
                packet, case, assessment = prepare_on_connection(service, conn, case_id=case_id, assessment_id=assessment_id, options=options, web_read=web_read)
                if packet["packet_sha256"] != packet_sha256 or packet["action"] != action:
                    raise TickerIdentityConflict("review_changed")
                if not packet["ready"]:
                    raise ValueError("review_ineligible")
                at = now(service)
                investigation = SecurityLifecycleInvestigationStore(conn)
                before_write()
                if assessment["status"] == "draft":
                    assessment = investigation.accept_assessment(assessment_id,
                        observation_fingerprint_sha256=packet["observation_fingerprint_sha256"], acceptance_authority="human", at=at,
                        _caller_transaction=True)
                service._review_step("assessment_accepted")
                investigation.generate_action_proposals(case_id=case_id, observation_fingerprint_sha256=packet["observation_fingerprint_sha256"],
                    sources_by_ticker={case["ticker"]: packet["active_sources"]}, at=at, _caller_transaction=True)
                service._review_step("proposals_created")
                confirmation = {"version": REVIEW_VERSION, "packet_sha256": packet_sha256, "actor": "attended_user",
                                "action": action, "confirmed_at": at, "packet": packet}
                preview = approved_preview(conn, packet=packet, case=case, assessment=assessment, confirmation=confirmation, at=at, web_read=web_read)
                transition = store._approve(preview=preview, approved_preview_sha256=preview["preview_sha256"],
                                            automation=False, _caller_transaction=True, web_read=web_read)
                transition_id = transition["transition_id"]
                service._review_step("approval_created")
                before_write()
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
    service._review_step("approval_committed")
    return execute(service, transition_id, before_write=before_write, web_read=web_read)
