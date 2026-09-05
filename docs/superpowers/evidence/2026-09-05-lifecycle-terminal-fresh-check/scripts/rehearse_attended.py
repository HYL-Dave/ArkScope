"""Exercise attended disposition only on a private SQLite backup, with no network."""

import argparse
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.ticker_identity_service import TickerIdentityService
from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore


spec = importlib.util.spec_from_file_location("resume_check", Path(__file__).with_name("resume_check.py"))
resume = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)
base, require = resume.base, resume.require
MARKET = base.ROOT / "data/market_data.db"


def audit_for(copy):
    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
            raise base.CheckStopped("rehearsal_external_effect_forbidden")
        if event == "sqlite3.connect":
            name = os.fsdecode(args[0])
            if name == str(copy) or name in {f"{copy.as_uri()}?mode=ro", f"{copy.as_uri()}?mode=rw",
                                              f"file:{copy}?mode=ro", f"file:{copy}?mode=rw"}:
                return
            readonly = {form for path in (base.PROFILE, base.SA, MARKET)
                        for form in (f"{path.as_uri()}?mode=ro", f"file:{path}?mode=ro")}
            require(name in readonly, "rehearsal_production_write_forbidden")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            require(not path.name.startswith(".env") and path.name != "auth.json", "rehearsal_ambient_credentials_forbidden")
    return audit


def copied_state(copy, names):
    with sqlite3.connect(copy) as conn:
        return {name: hashlib.sha256(base.encoded(conn.execute(
            'SELECT rowid,* FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall())).hexdigest()
            for name in names}


def run(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    copy = directory / "profile-rehearsal.db"
    sys.addaudithook(audit_for(copy))
    before = resume.preflight()
    now = base.now()
    fd = os.open(copy, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(f"{base.PROFILE.as_uri()}?mode=ro", uri=True) as source:
        source.execute("PRAGMA query_only=ON")
        with sqlite3.connect(copy) as destination:
            source.backup(destination)
    require(copied_state(copy, before[1]) == before[1], "rehearsal_backup_changed")
    checks = base.ProviderCheckStore(copy).latest()
    require(set(checks) == set(base.TARGETS), "rehearsal_check_scope")
    def scope():
        return base.build_active_universe_snapshot(profile_db=copy, sa_db=base.SA).sources_by_ticker
    service = TickerIdentityService(market_db_path=str(MARKET), profile_db_path=str(copy), source_loader=scope, clock=lambda: now)
    steps = []
    for ticker in base.TARGETS:
        check = checks[ticker]
        decision = base.classify_provider_listing(ticker=ticker, evidence=check["evidence"], today=resume.instant(now).date())
        require(base.terminal_requires_attestation(decision) and check["blockers"] == ["massive_not_found"], "rehearsal_attestation_shape")
        with sqlite3.connect(copy) as conn:
            store = SecurityLifecycleInvestigationStore(conn)
            case_id = store.ensure_case(source="listing_authority", source_ref=f"listing:{ticker}", ticker=ticker, at=now)
            fingerprint = observation_fingerprint(check["observation"])
            assessment_id = store.create_assessment(
                case_id=case_id, relevance="direct_tracked_security", confidence="high", author="human",
                conclusion="Rehearsal only: explicit historical delisting reviewed; no acquirer alias authorized.",
                impact_summary="Rehearsal only: stop collection and preserve source history.", outcomes=("listing_ended",),
                citations=[{"reference_kind": "observation", "cited_content_sha256": fingerprint}],
                observation_fingerprint_sha256=fingerprint, effective_date=decision.effective_date, at=now)
            store.accept_assessment(assessment_id, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=now)
            store.generate_action_proposals(case_id=case_id, observation_fingerprint_sha256=fingerprint, sources_by_ticker=scope(), at=now)
        options = TransitionOptions(execute_on=decision.effective_date)
        preview = service.preview_case(case_id, options=options)
        require(preview["eligible"], "rehearsal_preview_ineligible")
        approved = service.approve_case(case_id, options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
        applied = service.execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)
        require(applied["status"] == "applied", "rehearsal_application_failed")
        base.write(directory, f"private-{ticker}-receipt.json", {"preview": preview, "approval": approved, "application": applied})
        steps.append({"ticker": ticker, "transition_id": approved["transition_id"], "effective_date": decision.effective_date,
                      "provider_check_sha256": check["digest"], "status": applied["status"]})
    after = scope()
    require(after == {ticker: sources for ticker, sources in before[0].items() if ticker not in base.TARGETS}, "rehearsal_unexpected_scope_change")
    observations = read_sa_tracking_observations(base.SA)
    SaTrackingMembershipStore(copy).reconcile(observations, at=now, bootstrap_actor="attended_user")
    require(scope() == after, "rehearsal_sa_resurrection")
    with sqlite3.connect(copy) as conn:
        require(conn.execute("SELECT count(*) FROM ticker_identity_links").fetchone()[0] == 0, "rehearsal_acquirer_alias_created")
        store = TickerIdentityTransitionStore(conn, clock=lambda: now)
        reversible = {row["ticker"]: store.reverse_readiness(row["transition_id"])["reversible"] for row in steps}
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        require(integrity == "ok" and not conn.execute("PRAGMA foreign_key_check").fetchall(), "rehearsal_integrity_failed")
    require(resume.preflight() == before, "rehearsal_production_changed")
    result = {"at": now, "rehearsal_only": True, "source_profile_opened_read_only": True,
              "provider_calls": 0, "production_dispositions": 0, "production_price_writes": 0,
              "universe_before": len(before[0]), "rehearsal_universe_after": len(after),
              "exact_other_source_edges_preserved": True, "survives_sa_reconciliation": True,
              "acquirer_aliases_created": 0, "reverse_readiness_after_reconciliation": reversible,
              "results": [{key: value for key, value in row.items() if key != "transition_id"} for row in steps],
              "integrity": integrity}
    base.write(directory, "rehearsal-summary.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        run(args.directory)
    except base.CheckStopped as exc:
        print(json.dumps({"status": "stopped", "code": str(exc)}))
        raise SystemExit(2) from None
    except Exception as exc:
        print(json.dumps({"status": "stopped", "code": "rehearsal_unexpected_failure", "exception_type": type(exc).__name__}))
        raise SystemExit(2) from None
