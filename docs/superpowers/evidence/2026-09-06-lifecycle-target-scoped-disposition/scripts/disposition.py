"""Three attended retirements; unrelated capture is not an approval dependency."""

from collections import Counter
from contextlib import contextmanager, ExitStack, closing
import argparse
import importlib.util
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import time


V1 = Path(__file__).resolve().parents[2] / "2026-09-05-lifecycle-tracking-first-disposition"
spec = importlib.util.spec_from_file_location("target_disposition_v1", V1 / "scripts/disposition.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
DispositionStopped = base.DispositionStopped
require = base.require
digest = base.digest
timestamp = base.timestamp
readonly = base.readonly
file_digest = base.file_digest
database_digest = base.database_digest
runtime_hashes = base.runtime_hashes
write = base.write
scope = base.scope
TARGET_DATES = base.TARGET_DATES
TARGETS = base.TARGETS
VERSION = "target-scoped-disposition-v2"
_CONNECT = sqlite3.connect
WRITES = base.WRITES - {"sa_tracking_bindings"}


def script_hashes():
    return {str(path.relative_to(base.ROOT)): file_digest(path) for path in (
        Path(__file__), V1 / "scripts/disposition.py", base.READONLY / "scripts/inventory.py")}


def protected_rows(conn, target):
    """Taken inside each writer transaction, so independent commits are not vetoes."""
    from src.security_lifecycle_investigation import case_id_for
    members = target["input_effects"]["sa_tracking_memberships"]
    require(len(members) == 1, "disposition_membership_scope")
    params = {"ticker": target["ticker"], "case": case_id_for("listing_authority", f"listing:{target['ticker']}", target["ticker"]),
              "member": members[0]["membership_id"]}
    own_case = "case_id=:case"
    own_transition = "transition_id IN (SELECT transition_id FROM ticker_identity_transitions WHERE case_id=:case)"
    own_assessment = "assessment_id IN (SELECT assessment_id FROM security_lifecycle_assessments WHERE case_id=:case)"
    own_member = "membership_id=:member"
    own_ticker = "ticker=:ticker"
    ownership = {
        "security_lifecycle_cases": own_case + " AND " + own_ticker,
        "security_lifecycle_assessments": own_case,
        "security_lifecycle_assessment_outcomes": own_assessment,
        "security_lifecycle_assessment_evidence": own_assessment,
        "security_lifecycle_action_proposals": own_case,
        "ticker_identity_transitions": own_case + " AND source_ticker=:ticker AND kind='terminal_delisting' AND successor_ticker IS NULL AND approval_authority='attended_user'",
        "ticker_identity_transition_attempts": own_transition,
        "ticker_identity_transition_activity": own_transition + " AND source_ticker=:ticker AND successor_ticker IS NULL",
        "sa_tracking_memberships": own_member + " AND " + own_ticker,
        "sa_tracking_events": own_member,
        "ticker_meta": own_ticker,
    }
    return {table: digest([tuple(row) for row in conn.execute(
        f'SELECT * FROM "{table}" WHERE ({condition}) IS NOT 1 ORDER BY rowid', params)])
        for table, condition in ownership.items()}


class ScopedConnection(sqlite3.Connection):
    target = None
    protected_before = None
    finishing = False

    def execute(self, sql, parameters=()):
        result = super().execute(sql, parameters)
        if sql.strip().upper() in {"BEGIN", "BEGIN IMMEDIATE"} and self.target is not None:
            self.protected_before = protected_rows(self, self.target)
        return result

    def __enter__(self):
        require(not self.in_transaction, "disposition_nested_transaction")
        self.execute("BEGIN IMMEDIATE")
        return self

    def commit(self):
        try:
            if self.in_transaction and self.target is not None:
                require(self.protected_before is not None and protected_rows(self, self.target) == self.protected_before,
                        "disposition_row_scope")
            self.finishing = True
            super().commit()
        except BaseException:
            self.rollback()
            raise
        finally:
            self.finishing = False
            self.protected_before = None

    def rollback(self):
        self.finishing = True
        try:
            super().rollback()
        finally:
            self.finishing = False
            self.protected_before = None

    def __exit__(self, error_type, error, traceback):
        if error_type is not None:
            self.rollback()
        else:
            self.commit()
        return False

    def executescript(self, sql):
        raise DispositionStopped("disposition_script_forbidden")


@contextmanager
def connections(paths, *, target=None):
    original = sqlite3.connect
    known = {value: role for role, path in paths.items() for value in (
        str(path.resolve()), path.resolve().as_uri() + "?mode=ro", path.resolve().as_uri() + "?mode=rw",
        f"file:{path.resolve()}?mode=ro", f"file:{path.resolve()}?mode=rw")}
    denied = []

    def connect(database, *args, **kwargs):
        role = known.get(os.fsdecode(database))
        require(role is not None, "disposition_database_scope")
        writable = role == "profile" and target is not None and not os.fsdecode(database).endswith("?mode=ro")
        if writable:
            require("factory" not in kwargs, "disposition_connection_factory")
            kwargs = {**kwargs, "factory": ScopedConnection, "cached_statements": 0}
        conn = original(database, *args, **kwargs)
        try:
            if writable:
                conn.target = target
            else:
                conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("SELECT name FROM pragma_table_info('sqlite_master') LIMIT 0").fetchall()

            def authorize(action, first, second, database_name, source):
                ok = False
                if action == sqlite3.SQLITE_READ:
                    ok = base.allowed_read(role, first, second)
                elif action == sqlite3.SQLITE_SELECT:
                    ok = True
                elif action == sqlite3.SQLITE_TRANSACTION:
                    ok = not writable or first == "BEGIN" or conn.finishing
                elif action == sqlite3.SQLITE_FUNCTION:
                    ok = second != "load_extension"
                elif action == sqlite3.SQLITE_PRAGMA:
                    ok = first in {"table_info", "index_info", "index_list", "index_xinfo", "foreign_key_list", "data_version",
                                   "integrity_check", "foreign_key_check"} or (
                        first in {"foreign_keys", "query_only"} and second in {None, "ON", "1"})
                elif action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE}:
                    ok = writable and conn.protected_before is not None and database_name == "main" and first in WRITES
                    if first == "sa_tracking_memberships":
                        ok = ok and action == sqlite3.SQLITE_UPDATE and second in {"removed_at", "current_tracking", "reason", "updated_at"}
                    if first == "sa_tracking_events":
                        ok = ok and action == sqlite3.SQLITE_INSERT
                    if first == "ticker_meta" and action == sqlite3.SQLITE_UPDATE:
                        ok = ok and second in {"hidden_at", "updated_at"}
                if not ok:
                    denied.append((role, action, first, second))
                return sqlite3.SQLITE_OK if ok else sqlite3.SQLITE_DENY
            conn.set_authorizer(authorize)
            return conn
        except BaseException:
            conn.close()
            raise

    sqlite3.connect = connect
    try:
        yield denied
    finally:
        sqlite3.connect = original


@contextmanager
def reserve(paths, roles):
    with ExitStack() as stack:
        for role in roles:
            conn = stack.enter_context(closing(_CONNECT(paths[role].as_uri() + "?mode=rw", uri=True, timeout=2)))
            conn.execute("BEGIN IMMEDIATE")
            stack.callback(conn.rollback)
        yield


@contextmanager
def pinned_snapshots(paths):
    with ExitStack() as stack:
        readers = {}
        # Reserve only while the read snapshots are pinned, not while copying or rehearsing.
        with reserve(paths, ("profile", "market", "sa")):
            for role, path in paths.items():
                conn = stack.enter_context(closing(readonly(path)))
                require(conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal", "disposition_wal_required")
                conn.execute("BEGIN")
                conn.execute("SELECT rootpage FROM sqlite_master LIMIT 1").fetchall()
                readers[role] = conn
        yield readers


def backup_snapshot(source, destination, *, progress=None):
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(destination)) as dst:
        source.backup(dst, pages=1024, progress=progress)
        require(dst.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "disposition_backup_integrity")
    return database_digest(destination)


def _target_context(conn, ticker, observations):
    from src.sa_tracking_memberships import tracking_identity_context, _digest
    from src.ticker_identity_transition import _profile_dependency_snapshot
    links, relations = tracking_identity_context(conn)
    connected = {ticker}
    while True:
        expanded = connected | {value for pair in links.items() for value in pair if connected.intersection(pair)}
        if expanded == connected:
            break
        connected = expanded
    dependency = _profile_dependency_snapshot(conn, source_ticker=ticker, successor_ticker=None)
    cursor = conn.execute("SELECT * FROM sa_tracking_bindings ORDER BY lineage_id")
    bindings = [dict(zip((column[0] for column in cursor.description), row)) for row in cursor]
    member_ids = {row["membership_id"] for row in dependency["sa_tracking_memberships"]}
    relevant = [row for row in bindings if row["ticker"] in connected or row["membership_id"] in member_ids]
    by_id = {row["lineage_id"]: row for row in observations}
    for binding in relevant:
        row = by_id.get(binding["lineage_id"])
        require(row is not None and _digest({**row, "observed_at": binding["observed_at"]}) == binding["observation_sha256"],
                "disposition_target_sa_material_changed")
    lineage_ids = {row["lineage_id"] for row in relevant}
    require(bool(relevant), "disposition_target_binding_absent")
    selected = [row for row in observations if row["ticker"] in connected or row["lineage_id"] in lineage_ids]
    require(all(row["lineage_id"] in lineage_ids and not row["current_observed"] for row in selected),
            "disposition_target_sa_unbound_or_current")
    return {
        "profile_dependency": dependency,
        "bindings": [{key: row[key] for key in ("lineage_id", "membership_id", "ticker", "picked_date")} for row in relevant],
        "sa_material": [{key: value for key, value in row.items() if key != "observed_at"} for row in selected],
        "identity_links": sorted(pair for pair in links.items() if connected.intersection(pair)),
        "related_securities": sorted(pair for pair in relations if connected.intersection(pair)),
    }


def observe(paths, *, at):
    from src.sa_tracking_memberships import read_sa_tracking_observations
    from src.security_lifecycle_schema import verify_profile_connection
    from src.security_lifecycle_investigation import case_id_for
    sources = scope(paths)
    observations = read_sa_tracking_observations(paths["sa"])
    targets, effects = [], []
    with closing(readonly(paths["profile"])) as conn:
        conn.execute("BEGIN")
        verify_profile_connection(conn)
        base.automation_off(conn)
        for ticker in TARGETS:
            row, effect = base.inventory.target_inventory(conn, ticker, sources, now=base.instant(at))
            require(row["ready_for_new_attended_preview"] and row["listing_end_date"] == TARGET_DATES[ticker]
                    and row["sources"] == ["sa_alpha_picks_former"] and row["evidence_records"] == 6
                    and row["sa_memberships_to_suppress"] == 1 and row["sa_current_sources_to_stop"] == 0
                    and row["watchlist_archives"] == row["legacy_archives"] == 0 and not row["already_hidden"],
                    "disposition_target_changed")
            age = base.instant(at) - base.instant(row["observed_at"])
            require(0 <= age.total_seconds() <= 72 * 3600, "disposition_evidence_expired")
            case_id = case_id_for("listing_authority", f"listing:{ticker}", ticker)
            require(conn.execute("SELECT count(*) FROM security_lifecycle_assessments WHERE case_id=?", (case_id,)).fetchone()[0] == 0,
                    "disposition_existing_assessment")
            targets.append({**row, "input_effects": effect["effects"], "context": _target_context(conn, ticker, observations)})
            effects.append(effect)
    return {"universe_before": len(sources), "effects_sha256": digest(effects), "targets": targets}


def require_seed(actual, expected):
    require([row["ticker"] for row in actual["targets"]] == list(TARGETS), "disposition_target_scope")
    require(actual["effects_sha256"] == expected["effects_sha256"], "disposition_target_effects_changed")
    require({row["ticker"]: row["provider_check_sha256"] for row in actual["targets"]}
            == {row["ticker"]: row["provider_check_sha256"] for row in expected["targets"]}, "disposition_evidence_changed")


def require_current(actual, expected):
    require_seed(actual, expected)
    require(digest([row["context"] for row in actual["targets"]]) == digest([row["context"] for row in expected["targets"]]),
            "disposition_target_context_changed")


def before_write(paths, target, *, at):
    from src.sa_tracking_memberships import read_sa_tracking_observations
    from src.security_lifecycle_provider_store import ProviderCheckStore
    observations = read_sa_tracking_observations(paths["sa"])
    with closing(readonly(paths["profile"])) as conn:
        conn.execute("BEGIN")
        base.automation_off(conn)
        check = ProviderCheckStore.latest_for_connection(conn, target["ticker"])
        require(check is not None and check["digest"] == target["provider_check_sha256"], "disposition_evidence_changed")
        age = base.instant(at) - base.instant(check["at"])
        require(0 <= age.total_seconds() <= 72 * 3600, "disposition_evidence_expired")
        require(digest(_target_context(conn, target["ticker"], observations)) == digest(target["context"]),
                "disposition_target_context_changed")


def perform(paths, observed, directory, *, seed, clock, expected_previews=None):
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.ticker_identity_service import TickerIdentityService
    from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
    directory.mkdir(mode=0o700, exist_ok=False)
    previews, results, reservation_ms = {}, [], []
    for target in observed["targets"]:
        ticker = target["ticker"]
        counters = Counter()
        def identifier(prefix):
            counters[prefix] += 1
            return base.command_id(seed, ticker, prefix, counters[prefix])
        def recheck():
            before_write(paths, target, at=clock())
        with connections(paths, target=target) as denials:
            recheck()
            with closing(sqlite3.connect(paths["profile"].as_uri() + "?mode=rw", uri=True)) as conn:
                store = SecurityLifecycleInvestigationStore(conn, id_factory=lambda prefix, ordinal: base.command_id(seed, ticker, prefix, ordinal))
                check = ProviderCheckStore.latest_for_connection(conn, ticker)
                fingerprint = observation_fingerprint(check["observation"])
                at = clock()
                case_id = store.ensure_case(source="listing_authority", source_ref=f"listing:{ticker}", ticker=ticker, at=at)
                assessment = store.create_assessment(case_id=case_id, relevance="direct_tracked_security", confidence="high", author="human",
                    conclusion="User-authorized attended retirement after review of explicit old-listing inactivity. Continuation remains unavailable; no acquirer alias is authorized.",
                    impact_summary="Stop current price/news collection for this old listing; retain historical data and durable removal intent.",
                    outcomes=("listing_ended",), citations=[{"reference_kind": "observation", "cited_content_sha256": fingerprint}],
                    observation_fingerprint_sha256=fingerprint, effective_date=target["listing_end_date"], at=at)
                store.accept_assessment(assessment, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=at)
                store.generate_action_proposals(case_id=case_id, observation_fingerprint_sha256=fingerprint, sources_by_ticker=scope(paths), at=at)
            service = TickerIdentityService(market_db_path=str(paths["market"]), profile_db_path=str(paths["profile"]),
                source_loader=lambda: scope(paths), clock=clock, id_factory=identifier)
            options = TransitionOptions(execute_on=target["listing_end_date"])
            preview = service.preview_case(case_id, options=options)
            base.require_effects(preview, target)
            if expected_previews is not None:
                require(preview == expected_previews[ticker], "disposition_rehearsal_preview_changed")
            previews[ticker] = preview
            write(directory, f"{ticker}-intent.json", {"preview": preview, "transition_id": base.command_id(seed, ticker, "tit", 1)})
            # SA is reserved only across each actual validation/commit boundary.
            with reserve(paths, ("sa",)):
                started = time.monotonic()
                approved = service.approve_case(case_id, options=options, preview_sha256=preview["preview_sha256"], before_write=recheck)
                reservation_ms.append(round((time.monotonic() - started) * 1000, 3))
            write(directory, f"{ticker}-approved.json", approved)
            with reserve(paths, ("sa",)):
                started = time.monotonic()
                applied = service.execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=recheck)
                reservation_ms.append(round((time.monotonic() - started) * 1000, 3))
            require(applied["status"] == "applied", "disposition_not_applied")
            write(directory, f"{ticker}-applied.json", applied)
            require(not denials, "disposition_sql_scope_denied")
        results.append({"ticker": ticker, "transition_id": approved["transition_id"], "preview_sha256": preview["preview_sha256"],
                        "listing_end_date": target["listing_end_date"], "status": applied["status"]})
        with connections(paths):
            require(ticker not in scope(paths), "disposition_target_still_tracked")
    with connections(paths), closing(readonly(paths["profile"])) as conn:
        store = TickerIdentityTransitionStore(conn, clock=clock)
        reverse = {row["ticker"]: store.reverse_readiness(row["transition_id"])["reversible"] for row in results}
        require(all(reverse.values()), "disposition_reverse_state_changed")
        actual = conn.execute("SELECT source_ticker,kind,status,successor_ticker,approval_authority FROM ticker_identity_transitions WHERE source_ticker IN (?,?,?) ORDER BY source_ticker", TARGETS).fetchall()
        require(actual == [(ticker, "terminal_delisting", "applied", None, "attended_user") for ticker in TARGETS], "disposition_receipt_scope")
        remaining = scope(paths)
        require(not set(TARGETS).intersection(remaining), "disposition_target_still_tracked")
        sync = SaTrackingMembershipStore(paths["profile"]).synchronization_status(read_sa_tracking_observations(paths["sa"]))
    return {"previews": previews, "receipts": results, "applied": len(results), "universe_after": len(remaining), "sa_sync_status": sync,
            "all_reverse_ready": all(reverse.values()), "no_alias": True, "provider_requests": 0, "price_writes": 0,
            "sa_reconciliation_performed": False, "write_scope": list(TARGETS), "sa_commit_reservation_ms": reservation_ms}


def rehearsal_sync_control(paths, directory, *, clock):
    from src.sa_tracking_memberships import reconcile_sa_tracking
    test_paths = {**paths, "profile": directory / "profile.sync-control.db"}
    base.backup(paths["profile"], test_paths["profile"])
    # This copy is disposable. Production never runs full-source reconciliation here.
    require(reconcile_sa_tracking(profile_db=test_paths["profile"], sa_db=test_paths["sa"], at=clock()), "disposition_sa_unavailable")
    with connections(test_paths):
        require(not set(TARGETS).intersection(scope(test_paths)), "disposition_sa_resurrection")
    return True


def prepare(paths, expected, directory, *, clock=timestamp):
    require(not directory.exists(), "disposition_directory_exists")
    code_before, scripts_before = runtime_hashes(), script_hashes()
    with connections(paths):
        initial = observe(paths, at=clock())
        require_seed(initial, expected)
    backups, hashes = {}, {}
    with pinned_snapshots(paths) as readers:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        for role, conn in readers.items():
            backups[role] = directory / f"{role}.before.db"
            hashes[role] = backup_snapshot(conn, backups[role])
    rehearsal = {**backups, "profile": directory / "profile.rehearsal.db"}
    base.backup(backups["profile"], rehearsal["profile"])
    with connections(backups):
        current = observe(backups, at=clock())
        require_current(current, initial)
    seed = digest({"observed": current, "created_at": clock()})
    performed = perform(rehearsal, current, directory / "rehearsal", seed=seed, clock=clock)
    survived = rehearsal_sync_control(rehearsal, directory, clock=clock)
    with connections(paths):
        require_current(observe(paths, at=clock()), current)
    require(runtime_hashes() == code_before and script_hashes() == scripts_before, "disposition_runtime_changed_during_rehearsal")
    plan = {"version": VERSION, "at": clock(), "seed": seed, "observed": current, "backup_hashes": hashes,
            "previews": performed["previews"], "script_hashes": scripts_before,
            "database_paths": {role: str(path.resolve()) for role, path in paths.items()}, "runtime_hashes": code_before,
            "rehearsal_passed": True, "rehearsal_survives_sa_reconciliation": survived}
    write(directory, "private-plan.json", plan)
    result = {"version": VERSION, "at": plan["at"], "plan_sha256": digest(plan), "rehearsal_applied": performed["applied"],
              "rehearsal_universe_after": performed["universe_after"], "no_alias": True,
              "targets": [{key: value for key, value in row.items() if key != "transition_id"} for row in performed["receipts"]],
              "rehearsal_survives_sa_reconciliation": survived, "production_dispositions": 0, "provider_requests": 0, "price_writes": 0}
    write(directory, "prepare-summary.json", result)
    return result


def apply(paths, directory, *, approved_sha256, clock=timestamp):
    require(not (directory / "apply-started.json").exists(), "disposition_already_started")
    plan = json.loads((directory / "private-plan.json").read_text())
    require(digest(plan) == approved_sha256 and plan["version"] == VERSION and plan["rehearsal_passed"] is True,
            "disposition_approval_mismatch")
    require(script_hashes() == plan["script_hashes"], "disposition_code_changed")
    require(runtime_hashes() == plan["runtime_hashes"], "disposition_runtime_changed")
    require({role: str(path.resolve()) for role, path in paths.items()} == plan["database_paths"], "disposition_database_paths_changed")
    for role, expected in plan["backup_hashes"].items():
        require(database_digest(directory / f"{role}.before.db") == expected, "disposition_backup_changed")
    with connections(paths):
        current = observe(paths, at=clock())
        require_current(current, plan["observed"])
    write(directory, "apply-started.json", {"at": clock(), "approved_sha256": approved_sha256})
    performed = perform(paths, current, directory / "production", seed=plan["seed"], clock=clock, expected_previews=plan["previews"])
    result = {key: value for key, value in performed.items() if key not in {"previews", "receipts"}}
    result.update({"at": clock(), "plan_sha256": approved_sha256,
                   "targets": [{k: v for k, v in row.items() if k != "transition_id"} for row in performed["receipts"]]})
    write(directory, "apply-summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--expected-inventory", type=Path)
    parser.add_argument("--approved-sha256")
    for role in ("profile", "market", "sa"):
        parser.add_argument("--" + role, type=Path, required=True)
    args = parser.parse_args()
    paths = {role: getattr(args, role).resolve(strict=True) for role in ("profile", "market", "sa")}
    require(len(set(paths.values())) == 3, "disposition_database_roles_overlap")
    sys.addaudithook(base.audit_for(paths, args.directory))
    logging.disable(logging.CRITICAL)
    base.stopped()
    try:
        if args.phase == "prepare":
            require(args.expected_inventory is not None, "disposition_inventory_required")
            result = prepare(paths, json.loads(args.expected_inventory.read_text()), args.directory)
        else:
            require(args.approved_sha256 is not None, "disposition_approval_required")
            result = apply(paths, args.directory, approved_sha256=args.approved_sha256)
    except Exception as exc:
        failure = {"status": "stopped", "phase": args.phase, "at": timestamp(),
                   "code": str(exc) if isinstance(exc, DispositionStopped) else "disposition_unexpected_failure",
                   "exception_type": type(exc).__name__}
        try:
            failure["readback"] = base.recorded_status(paths)
        except Exception:
            failure["readback_unavailable"] = True
        if args.directory.is_dir():
            write(args.directory, f"stopped-{args.phase}-{os.getpid()}.json", failure)
        print(json.dumps(failure, sort_keys=True))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        code = str(exc) if isinstance(exc, DispositionStopped) else "disposition_unexpected_failure"
        print(json.dumps({"status": "stopped", "code": code, "exception_type": type(exc).__name__}))
        raise SystemExit(2) from None
