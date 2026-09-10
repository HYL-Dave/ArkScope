"""Human adoption of a model-authored finding through the governed writer.

Preparing a packet never invents an accepted assessment. The eventual human
decision and the immutable model/source journal have different authorship.
"""

from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import sqlite3

from src.lifecycle_web_schema import WebJournalError, verify_web_journal
from src.lifecycle_journal_codec import canonical_json, digest_json
from src.lifecycle_web_store import LifecycleWebStore
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.security_lifecycle_provider_authority import evidence_dict, validate_provider_material
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_review import (
    _FINDING_FIELDS, _proposal_vetoes, _matching_transition, approved_preview, execute, now, packet_digest,
)
from src.ticker_identity_transition import TransitionOptions, _execution_date, _sha256, build_transition_effects


def assessment_id_for(run_id):
    return "sla_web_" + hashlib.sha256(run_id.encode()).hexdigest()[:32]


def acceptance_for(conn, assessment_id):
    row = None
    for table in ("lifecycle_web_acceptances", "lifecycle_investigation_acceptances"):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            continue
        row = conn.execute(f"SELECT * FROM {table} WHERE assessment_id=?", (assessment_id,)).fetchone()
        if row is not None:
            if table == "lifecycle_web_acceptances":
                verify_web_journal(conn)
            else:
                from src.lifecycle_investigation.schema import verify_journal
                verify_journal(conn)
            break
    if row is None:
        return None
    value = dict(row)
    packet = json.loads(value["packet_json"])
    if (packet_digest(packet) != value["packet_sha256"] or packet.get("packet_sha256") != value["packet_sha256"]
            or packet.get("assessment_id") != assessment_id or packet.get("lane") not in {"web", "investigation"}
            or packet.get("web", {}).get("run_id") != value["run_id"] or value["actor"] != "attended_user"):
        raise ValueError("web_acceptance_invalid")
    return {**value, "packet": packet}


def _adoption_values(run, *, evidence_sha256, revision):
    finding = run["finding"].finding
    kind = run["finding"].action
    values = {key: None for key in _FINDING_FIELDS}
    values.update(conclusion="Attended adoption of the cited Web investigation.", impact_summary=finding.summary,
                  relevance="direct_tracked_security", confidence="high", outcomes=[
                      "listing_ended" if kind == "terminal_delisting" else "symbol_changed" if kind == "symbol_continuation" else "undetermined"],
                  successor_ticker=finding.successor_ticker, effective_date=finding.effective_date)
    values.update(assessment_id=assessment_id_for(run["run_id"]), case_id=run["case_id"], revision=revision, author="human",
                  observation_fingerprint_sha256=run["observation_sha256"], evidence_set_sha256=evidence_sha256)
    return values


def _provider_veto(conn, run, *, at):
    """A failed lookup is not a veto; positive contrary identity/trading is."""
    check = ProviderCheckStore.latest_for_connection(conn, run["request"].ticker)
    if check is None:
        return (), None
    rows, blockers = [], set()
    request, finding = run["request"], run["finding"].finding
    for raw in check["evidence"]:
        item = evidence_dict(raw)
        validate_provider_material(item)
        if item["kind"] != "listing_directory_snapshot":
            continue
        locator = item["source_locator"]
        if locator.get("snapshot_complete") is True:
            rows.append((locator, instant(item["retrieved_at"])))
    source = [(row, observed) for row, observed in rows if row.get("candidate_ticker") == request.ticker]
    for field in ("issuer_cik", "composite_figi"):
        known = {row[field] for row, _ in source if row.get(field)}
        expected = getattr(request, field)
        if len(known) > 1 or (expected is not None and known and known != {expected}):
            blockers.add("web_security_identity_conflict")
    if finding.timing == "completed":
        for row, observed in source:
            if (row.get("listing_status") == "active" and instant(at) - timedelta(days=3) <= observed <= instant(at)
                    and (finding.effective_date is None or observed.date().isoformat() >= finding.effective_date)):
                blockers.add("web_active_listing_conflict")
    if finding.event_kind == "symbol_continuation":
        old_ids = {row["composite_figi"] for row, _ in source if row.get("composite_figi")}
        new_ids = {row["composite_figi"] for row, _ in rows if row.get("candidate_ticker") == finding.successor_ticker and row.get("composite_figi")}
        if old_ids and new_ids and (len(old_ids | new_ids) != 1):
            blockers.add("web_security_identity_conflict")
    return tuple(sorted(blockers)), check["digest"]


def _freshness(run, at):
    when = instant(at)
    times = [instant(run["finished_at"]), *(instant(page.retrieved_at) for page in run["pages"].values())]
    return () if times and all(when - timedelta(days=3) <= observed <= when for observed in times) else ("web_finding_stale",)


def prepare_on_connection(service, conn, *, run_id, options, web_read=None):
    from src.lifecycle_investigation.adoption import is_target_run, prepare_on_connection as prepare_target
    if is_target_run(run_id):
        return prepare_target(service, conn, run_id=run_id, options=options, web_read=web_read)
    conn.row_factory = sqlite3.Row
    run = LifecycleWebStore.read_on_connection(conn, run_id, validated=web_read)
    if run["status"] != "succeeded" or run["finding"] is None:
        raise ValueError("web_finding_not_complete")
    store = SecurityLifecycleInvestigationStore(conn)
    case = store.get_case_identity(run["case_id"])
    current = service._read_service.get_case(run["case_id"])
    current_fingerprint = current.get("observation_fingerprint_sha256")
    sources = service._read_service.sources_by_ticker()
    active = None if sources is None else tuple(sources.get(case["ticker"], ()))
    at = now(service)
    blockers = list(run["finding"].block_reasons) + list(_freshness(run, at))
    if current_fingerprint != run["observation_sha256"] or case["ticker"] != run["request"].ticker:
        blockers.append("web_observation_changed")
    if run["finding"].action is None:
        blockers.append("web_finding_not_actionable")
    identity = assessment_id_for(run_id)
    prior = conn.execute("SELECT assessment_id FROM security_lifecycle_assessments WHERE case_id=? AND assessment_id<>? ORDER BY revision DESC LIMIT 1",
                         (case["case_id"], identity)).fetchone()
    previous = store.get_assessment(prior[0]) if prior else None
    revision = 1 if previous is None else previous["revision"] + 1
    evidence_sha = store._evidence_set_sha256(case["case_id"])
    expected = _adoption_values(run, evidence_sha256=evidence_sha, revision=revision)
    existing = conn.execute("SELECT assessment_id FROM security_lifecycle_assessments WHERE assessment_id=?", (identity,)).fetchone()
    assessment = store.get_assessment(identity) if existing else expected
    if existing:
        if any(assessment.get(key) != value for key, value in expected.items()):
            blockers.append("web_adoption_changed")
        if acceptance_for(conn, identity) is None or assessment["status"] != "accepted" or assessment["acceptance_authority"] != "human":
            blockers.append("web_acceptance_required")
        blockers.extend(_proposal_vetoes(store, case=case, assessment=assessment, kind=run["finding"].action))
    vetoes, provider_digest = _provider_veto(conn, run, at=at)
    blockers.extend(vetoes)
    execute_on, date_blocker = _execution_date(options, expected)
    if date_blocker:
        blockers.append(date_blocker)
    effects = build_transition_effects(conn, source_ticker=case["ticker"], successor_ticker=expected["successor_ticker"],
        transition_kind=run["finding"].action, sources=active, options=options)
    blockers.extend(effects["block_reasons"])
    packet = {
        "version": 1, "lane": "web", "case_id": case["case_id"], "assessment_id": identity,
        "source_ticker": case["ticker"], "action": run["finding"].action, "execute_on": execute_on,
        "options": asdict(options), "finding": {key: expected[key] for key in _FINDING_FIELDS},
        "assessment_material": expected,
        "prior_assessment": None if previous is None else {key: previous[key] for key in (*_FINDING_FIELDS, "assessment_id", "revision")},
        "observation_fingerprint_sha256": run["observation_sha256"], "evidence_set_sha256": evidence_sha,
        "provider_check_sha256": provider_digest, "provider_observed_at": None,
        "source_references": [], "active_sources": effects["active_sources"], "effects": effects["effects"],
        "source_gaps": run["source_gaps"],
        "profile_state_sha256": effects["profile_state_sha256"], "caveats": effects["caveats"],
        "web": {"run_id": run_id, "result_sha256": run["result_sha256"], "header_sha256": run["header_sha256"],
                "execution": {key: getattr(run["selection"], key) for key in ("provider", "auth_mode", "model")},
                "passages_sha256": digest_json([asdict(passage) for passage in run["finding"].passages])},
        "ready": not blockers, "block_reasons": sorted(set(blockers)),
    }
    packet["packet_sha256"] = packet_digest(packet)
    return packet, case, assessment


def prepare(service, run_id, *, options):
    web_read = LifecycleWebStore(service.profile_db_path).validated_read(run_id)
    with service._profile_connection(write=False) as conn:
        conn.execute("BEGIN")
        return prepare_on_connection(service, conn, run_id=run_id, options=options, web_read=web_read)[0]


def validated_adoption_read(service, *, assessment_id, conn=None):
    if conn is None:
        with service._profile_connection(write=False) as owned:
            return validated_adoption_read(service, assessment_id=assessment_id, conn=owned)
    if conn.in_transaction:
        raise RuntimeError("caller_transaction_open")
    conn.row_factory = sqlite3.Row
    accepted = acceptance_for(conn, assessment_id)
    return (None if accepted is None else
            LifecycleWebStore(service.profile_db_path).validated_read(accepted["run_id"]))


def web_transition_guard(conn, *, assessment, observation_sha256, transition_kind, successor_ticker, at,
                         automation=False, confirmation=None, require_confirmation=False, web_read=None):
    """None means the ordinary lane. A Web adoption never falls through to it."""
    identity = assessment["assessment_id"]
    accepted = acceptance_for(conn, identity)
    if accepted is None:
        return ("web_acceptance_required",) if identity.startswith("sla_web_") else None
    packet = accepted["packet"]
    run = LifecycleWebStore.read_on_connection(conn, accepted["run_id"], validated=web_read)
    expected = packet["assessment_material"]
    blockers = []
    if require_confirmation and not isinstance(confirmation, dict):
        blockers.append("web_acceptance_required")
    if (automation or assessment.get("acceptance_authority") != "human" or assessment.get("status") != "accepted"
            or any(assessment.get(key) != value for key, value in expected.items())
            or packet["ready"] is not True or packet["block_reasons"] or packet["action"] != transition_kind
            or packet["finding"]["successor_ticker"] != successor_ticker
            or packet.get("source_gaps", []) != run["source_gaps"]
            or packet["observation_fingerprint_sha256"] != observation_sha256
            or identity != assessment_id_for(run["run_id"]) or run["finding"].action != transition_kind
            or run["result_sha256"] != packet["web"]["result_sha256"] or run["header_sha256"] != packet["web"]["header_sha256"]):
        blockers.append("web_acceptance_invalid")
    if confirmation is not None and (confirmation.get("packet_sha256") != accepted["packet_sha256"]
                                      or confirmation.get("actor") != "attended_user"):
        blockers.append("web_acceptance_invalid")
    current = SecurityLifecycleInvestigationStore(conn)
    if current._evidence_set_sha256(run["case_id"]) != packet["evidence_set_sha256"]:
        blockers.append("web_evidence_changed")
    latest = conn.execute("SELECT assessment_id FROM security_lifecycle_assessments WHERE case_id=? ORDER BY revision DESC LIMIT 1", (run["case_id"],)).fetchone()
    if latest[0] != identity:
        blockers.append("assessment_superseded")
    vetoes, provider_digest = _provider_veto(conn, run, at=at)
    blockers.extend(vetoes)
    if provider_digest != packet["provider_check_sha256"]:
        blockers.append("web_observation_changed")
    blockers.extend(_freshness(run, at))
    return tuple(sorted(set(blockers)))


def confirm(service, run_id, *, packet_sha256, action, options, before_write, acknowledge_source_gaps=False):
    from src.ticker_identity_service import TickerIdentityConflict

    _sha256("review_digest", packet_sha256)
    if action not in {"terminal_delisting", "symbol_continuation"}:
        raise ValueError("review_action")
    before_write()
    web_read = LifecycleWebStore(service.profile_db_path).validated_read(run_id)
    before_write()
    with service._profile_connection(write=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN IMMEDIATE")
        try:
            run = LifecycleWebStore.read_on_connection(conn, run_id, validated=web_read)
            if run.get("source_gaps") and acknowledge_source_gaps is not True:
                raise WebJournalError("web_source_gaps_not_acknowledged")
            store = service._store(conn)
            identity = assessment_id_for(run_id)
            existing = _matching_transition(store, case_id=run["case_id"], assessment_id=identity, action=action,
                                            packet_sha256=packet_sha256, options=options)
            if existing is not None:
                transition_id = existing["transition_id"]
                conn.rollback()
            else:
                packet, case, _ = prepare_on_connection(service, conn, run_id=run_id, options=options, web_read=web_read)
                if packet["packet_sha256"] != packet_sha256 or packet["action"] != action:
                    raise TickerIdentityConflict("review_changed")
                if not packet["ready"]:
                    raise ValueError("web_review_ineligible")
                if acceptance_for(conn, identity) is not None:
                    raise ValueError("web_acceptance_already_recorded")
                at = now(service)
                values = packet["assessment_material"]
                investigation = SecurityLifecycleInvestigationStore(conn, id_factory=lambda prefix, ordinal: identity if prefix == "sla" else f"{prefix}_{hashlib.sha256(f'{run_id}:{prefix}:{ordinal}'.encode()).hexdigest()[:32]}")
                before_write()
                if packet["lane"] == "investigation":
                    # A real attended-source anchor, inside this same rollback boundary.
                    investigation._upsert_case_row(case["case_id"], (case["source"], case["source_ref"], case["ticker"]), at=at)
                investigation.create_assessment(
                    **{key: values[key] for key in (*_FINDING_FIELDS, "case_id", "author", "observation_fingerprint_sha256")},
                    citations=[{"reference_kind": "observation", "cited_content_sha256": packet["observation_fingerprint_sha256"]}],
                    at=at, _caller_transaction=True,
                )
                assessment = investigation.accept_assessment(identity, observation_fingerprint_sha256=packet["observation_fingerprint_sha256"],
                    acceptance_authority="human", at=at, _caller_transaction=True)
                acceptance_table = "lifecycle_investigation_acceptances" if packet["lane"] == "investigation" else "lifecycle_web_acceptances"
                conn.execute(f"INSERT INTO {acceptance_table} VALUES (?,?,?,?,?,?)",
                             (identity, run_id, canonical_json(packet), packet_sha256, "attended_user", at))
                investigation.generate_action_proposals(case_id=case["case_id"], observation_fingerprint_sha256=packet["observation_fingerprint_sha256"],
                    sources_by_ticker={case["ticker"]: packet["active_sources"]}, at=at, _caller_transaction=True)
                confirmation = {"version": 1, "packet_sha256": packet_sha256, "actor": "attended_user", "action": action, "confirmed_at": at, "packet": packet}
                preview = approved_preview(conn, packet=packet, case=case, assessment=assessment, confirmation=confirmation, at=at, web_read=web_read)
                transition = store._approve(preview=preview, approved_preview_sha256=preview["preview_sha256"], automation=False,
                    _caller_transaction=True, web_read=web_read)
                transition_id = transition["transition_id"]
                before_write()
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return execute(service, transition_id, before_write=before_write, web_read=web_read)
