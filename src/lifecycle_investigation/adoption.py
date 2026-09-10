"""Adapt real target investigations to the existing attended transition writer.

Only confirmation creates a source anchor. No legacy case or fabricated filing
is needed to investigate, read a finding, or preview the effects.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from src.lifecycle_investigation.findings import Finding, validate_finding
from src.lifecycle_investigation.schema import verify_journal
from src.lifecycle_investigation.store import InvestigationStore
from src.lifecycle_investigation.target import Target, target_snapshot
from src.lifecycle_journal_codec import digest_json
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, case_id_for
from src.security_lifecycle_review import _FINDING_FIELDS, _proposal_vetoes, now, packet_digest
from src.security_lifecycle_web_contract import ExecutionSelection
from src.ticker_identity_transition import build_transition_effects, _execution_date


def is_target_run(run_id):
    return isinstance(run_id, str) and run_id.startswith("li_")


def binding_on_connection(conn, run_id):
    conn.row_factory = sqlite3.Row
    verify_journal(conn)
    row, _ = InvestigationStore.row(conn, run_id)
    saved = conn.execute("SELECT payload_sha256 FROM lifecycle_investigation_results WHERE run_id=?", (run_id,)).fetchone()
    sources = tuple(tuple(item) for item in conn.execute("SELECT source_id,payload_sha256 FROM lifecycle_investigation_sources WHERE run_id=? ORDER BY source_id", (run_id,)))
    return (row["header_sha256"], row["status"], None if saved is None else saved[0], sources,
            conn.execute("PRAGMA schema_version").fetchone()[0])


def as_adoption(row):
    result = row["result"]
    if row["status"] != "succeeded" or not result or result.get("validated") is None:
        raise ValueError("web_finding_not_complete")
    target = Target.model_validate(row["binding"]["target"])
    requests = [step["payload"] for step in row["steps"] if step["kind"] == "model_request"]
    outputs = [step["payload"] for step in row["steps"] if step["kind"] == "model_result"]
    if not requests or not outputs:
        raise ValueError("investigation_integrity")
    last = outputs[-1]
    actual = last["output"]
    if (last.get("output_error") is not None or type(actual) is not dict or actual.get("action") != "conclude"
            or Finding.model_validate(actual.get("finding")).model_dump() != result["validated"]["finding"]
            or last["call_id"] != requests[-1]["call_id"]
            or not any(call["call_id"] == last["call_id"] and call["remote_id"] == last["remote_id"] and call["terminal"] == "completed" for call in row["calls"])):
        raise ValueError("investigation_integrity")
    checked = validate_finding(target, result["validated"]["finding"], row["sources"], set(requests[-1]["supplied_passages"]))
    if checked != result["validated"]:
        raise ValueError("investigation_integrity")
    source = {"source": "lifecycle_investigation", "source_ref": row["run_id"], "ticker": target.ticker}
    observation_sha = digest_json({**source, "target": target.model_dump()})
    case = {"case_id": case_id_for(**source), **source}
    return {**row, "case_id": case["case_id"], "target_case": case,
        "observation_sha256": observation_sha, "request": target, "selection": ExecutionSelection(**row["binding"]["selection"]),
        "finding": SimpleNamespace(finding=Finding.model_validate(checked["finding"]), action=checked["action"],
            block_reasons=tuple(checked["block_reasons"]), passages=checked["passages"]),
        "pages": {key: SimpleNamespace(retrieved_at=value["retrieved_at"]) for key, value in row["sources"].items()},
        "source_gaps": [{"url": gap["url"], "reason": gap["reason"]} for gap in result["gaps"]]}


@dataclass(frozen=True)
class ValidatedInvestigationRead:
    path: Path
    run_id: str
    binding: tuple
    material: dict

    def on_connection(self, conn, run_id):
        database = next((row[2] for row in conn.execute("PRAGMA database_list") if row[1] == "main"), None)
        if (not conn.in_transaction or run_id != self.run_id or not database or Path(database).resolve() != self.path
                or binding_on_connection(conn, run_id) != self.binding):
            raise ValueError("investigation_integrity")
        return self.material


def validated_read(path, run_id):
    store = InvestigationStore(path)
    with store.connection() as conn:
        binding = binding_on_connection(conn, run_id)
        row = InvestigationStore.read_on_connection(conn, run_id)
    # Large source parsing is outside the mutable profile transaction.
    read = ValidatedInvestigationRead(store.path, run_id, binding, as_adoption(row))
    with store.connection() as conn:
        read.on_connection(conn, run_id)
    return read


def read_on_connection(conn, run_id, *, validated=None):
    if validated is not None:
        if type(validated) is not ValidatedInvestigationRead:
            raise ValueError("investigation_integrity")
        return validated.on_connection(conn, run_id)
    verify_journal(conn)
    return as_adoption(InvestigationStore.read_on_connection(conn, run_id))


def prepare_on_connection(service, conn, *, run_id, options, web_read=None):
    from src.lifecycle_web_review import assessment_id_for, acceptance_for, _adoption_values, _provider_veto, _freshness
    run = read_on_connection(conn, run_id, validated=web_read)
    case = run["target_case"]
    store = SecurityLifecycleInvestigationStore(conn)
    at = now(service)
    blockers = list(run["finding"].block_reasons) + list(_freshness(run, at))
    sources = service._read_service.sources_by_ticker()
    active = None if sources is None else tuple(sources.get(case["ticker"], ()))
    # The source's identity is immutable; a changed current stable identifier is a conflict, not a new alias.
    try:
        current = target_snapshot(service, case["ticker"], conn=conn)
        for field in ("issuer_cik", "composite_figi", "security_class", "venue"):
            old, new = getattr(run["request"], field), getattr(current, field)
            if old is not None and new is not None and old != new:
                blockers.append("web_security_identity_conflict")
        if current.identity_status == "conflicting":
            blockers.append("web_security_identity_conflict")
    except ValueError as exc:
        blockers.append(str(exc))
    if run["finding"].action is None:
        blockers.append("web_finding_not_actionable")
    identity = assessment_id_for(run_id)
    prior = conn.execute("SELECT assessment_id FROM security_lifecycle_assessments WHERE case_id=? AND assessment_id<>? ORDER BY revision DESC LIMIT 1", (case["case_id"], identity)).fetchone()
    previous = store.get_assessment(prior[0]) if prior else None
    evidence_sha = store._evidence_set_sha256(case["case_id"])
    expected = _adoption_values(run, evidence_sha256=evidence_sha, revision=1 if previous is None else previous["revision"] + 1)
    expected["conclusion"] = "Attended adoption of the cited target investigation."
    expected["impact_summary"] = " ".join([run["finding"].finding.summary, *run["finding"].finding.limitations])
    existing = conn.execute("SELECT 1 FROM security_lifecycle_assessments WHERE assessment_id=?", (identity,)).fetchone()
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
    packet = {"version": 1, "lane": "investigation", "case_id": case["case_id"], "assessment_id": identity,
        "source_ticker": case["ticker"], "action": run["finding"].action, "execute_on": execute_on,
        "options": asdict(options), "finding": {key: expected[key] for key in _FINDING_FIELDS}, "assessment_material": expected,
        "prior_assessment": None if previous is None else {key: previous[key] for key in (*_FINDING_FIELDS, "assessment_id", "revision")},
        "observation_fingerprint_sha256": run["observation_sha256"], "evidence_set_sha256": evidence_sha,
        "provider_check_sha256": provider_digest, "provider_observed_at": None, "source_references": [],
        "active_sources": effects["active_sources"], "effects": effects["effects"], "source_gaps": run["source_gaps"],
        "profile_state_sha256": effects["profile_state_sha256"], "caveats": effects["caveats"],
        "web": {"run_id": run_id, "result_sha256": run["result_sha256"], "header_sha256": run["header_sha256"],
            "execution": {key: getattr(run["selection"], key) for key in ("provider", "auth_mode", "model")},
            "passages_sha256": digest_json(run["finding"].passages)}, "ready": not blockers, "block_reasons": sorted(set(blockers))}
    packet["packet_sha256"] = packet_digest(packet)
    return packet, case, assessment
