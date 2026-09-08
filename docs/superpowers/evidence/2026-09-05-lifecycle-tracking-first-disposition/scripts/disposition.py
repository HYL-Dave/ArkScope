"""One explicitly authorized three-target disposition, with independent rehearsal."""

from collections import Counter
from contextlib import contextmanager, ExitStack, closing
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[5]
READONLY = Path(__file__).resolve().parents[2] / "2026-09-05-lifecycle-tracking-first-readonly"
spec = importlib.util.spec_from_file_location("disposition_inventory", READONLY / "scripts/inventory.py")
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)
TARGET_DATES = {"ARCH": "2025-01-15", "LTHM": "2024-01-05", "TA": "2023-05-16"}
TARGETS = tuple(TARGET_DATES)
WRITES = {
    "security_lifecycle_cases", "security_lifecycle_assessments",
    "security_lifecycle_assessment_outcomes", "security_lifecycle_assessment_evidence",
    "security_lifecycle_action_proposals", "ticker_identity_transitions",
    "ticker_identity_transition_attempts", "ticker_identity_transition_activity",
    "sa_tracking_bindings", "sa_tracking_memberships", "sa_tracking_events", "ticker_meta",
}
PROFILE_INPUTS = {"watchlists", "watchlist_memberships", "universe_source_memberships", "ticker_tags", "ticker_meta",
                  "portfolio_positions", "portfolio_accounts", "profile_settings"}
PORTFOLIO_COLUMNS = {
    "portfolio_positions": "id,account_id,symbol,asset_class,closed_at",
    "portfolio_accounts": "id,archived_at",
}


class DispositionStopped(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise DispositionStopped(code)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() is not None, "disposition_timestamp")
    return parsed


def encoded(value):
    return inventory.encoded(value)


def digest(value):
    return inventory.digest(value)


def file_digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(part)
    return result.hexdigest()


def database_digest(path):
    sidecars = {suffix: path.with_name(path.name + suffix) for suffix in ("-wal", "-journal")}
    return digest({"main": file_digest(path), **{suffix: file_digest(value) if value.exists() and value.stat().st_size else None
                                              for suffix, value in sidecars.items()}})


def runtime_hashes():
    import src
    root = Path(src.__file__).resolve().parent.parent
    files = sorted([*root.joinpath("src").rglob("*.py"), *root.joinpath("data_sources").rglob("*.py")])
    require(bool(files), "disposition_runtime_files_absent")
    return {str(path.relative_to(root)): file_digest(path) for path in files}


def write(directory, name, value):
    inventory.private_write(directory, name, value)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def readonly(path):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def automation_off(conn):
    from src.service.security_lifecycle_automation_config import SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS, parse_security_lifecycle_automation_config
    keys = SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS
    rows = dict(conn.execute(f"SELECT key,value FROM profile_settings WHERE key IN ({','.join('?' for _ in keys)})", keys))
    state = parse_security_lifecycle_automation_config(rows)
    require(state.valid and state.config is not None and not state.config.enabled
            and not state.config.apply_profile_transitions, "disposition_automation_not_disabled")
    return rows


def allowed_read(role, table, column):
    if table in inventory._METADATA:
        return True
    if role == "profile":
        if table in PORTFOLIO_COLUMNS:
            return not column or column in PORTFOLIO_COLUMNS[table].split(",")
        return table.startswith(("security_lifecycle_", "ticker_identity_", "sa_tracking_")) or table in PROFILE_INPUTS
    if role == "market":
        return table.startswith("security_lifecycle_") or table in {"prices", "provider_sync_meta", "ticker_aliases"}
    return table in inventory.SCOPES["sa"]


@contextmanager
def connections(paths, *, writable_profile=False):
    original = sqlite3.connect
    known = {value: role for role, path in paths.items() for value in (
        str(path.resolve()), path.resolve().as_uri() + "?mode=ro", path.resolve().as_uri() + "?mode=rw",
        f"file:{path.resolve()}?mode=ro", f"file:{path.resolve()}?mode=rw")}
    denied = []

    def connect(database, *args, **kwargs):
        role = known.get(os.fsdecode(database))
        require(role is not None, "disposition_database_scope")
        conn = original(database, *args, **kwargs)
        writable = role == "profile" and writable_profile
        if not writable:
            conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("SELECT name FROM pragma_table_info('sqlite_master') LIMIT 0").fetchall()

        def authorize(action, first, second, database_name, source):
            ok = False
            if action == sqlite3.SQLITE_READ:
                ok = allowed_read(role, first, second)
            elif action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}:
                ok = True
            elif action == sqlite3.SQLITE_FUNCTION:
                ok = second != "load_extension"
            elif action == sqlite3.SQLITE_PRAGMA:
                ok = first in {"table_info", "index_info", "index_list", "index_xinfo", "foreign_key_list", "data_version",
                               "integrity_check", "foreign_key_check"} or (
                    first in {"foreign_keys", "query_only"} and second in {None, "ON", "1"})
            elif action in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE}:
                ok = writable and first in WRITES
            if not ok:
                denied.append((role, action, first, second))
            return sqlite3.SQLITE_OK if ok else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorize)
        return conn

    sqlite3.connect = connect
    try:
        yield denied
    finally:
        sqlite3.connect = original


@contextmanager
def reserve_sources(paths, *, roles=("profile", "market", "sa")):
    with ExitStack() as stack:
        for role in roles:
            conn = stack.enter_context(closing(sqlite3.connect(paths[role].as_uri() + "?mode=rw", uri=True, timeout=2)))
            conn.execute("BEGIN IMMEDIATE")
            stack.callback(conn.rollback)
        yield


def scope(paths):
    from src.active_universe import build_active_universe_snapshot
    value = build_active_universe_snapshot(profile_db=paths["profile"], sa_db=paths["sa"])
    require(all(row.available for row in value.source_status.values()), "disposition_source_unavailable")
    return {key: list(row) for key, row in value.sources_by_ticker.items()}


def domain_state(profile, *, protected=False):
    from src.security_lifecycle_investigation import case_id_for
    case_ids = [case_id_for("listing_authority", f"listing:{ticker}", ticker) for ticker in TARGETS]
    with closing(readonly(profile)) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                 if row[0].startswith(("security_lifecycle_", "ticker_identity_", "sa_tracking_")) or row[0] in PROFILE_INPUTS]
        result = {}
        for name in names:
            if name == "profile_settings":
                result[name] = digest(automation_off(conn))
                continue
            where, params = "", ()
            columns = PORTFOLIO_COLUMNS.get(name, "*")
            if protected:
                if name == "sa_tracking_bindings":
                    columns = "lineage_id,membership_id,ticker,picked_date"
                elif name in {"sa_tracking_memberships", "ticker_meta"}:
                    where, params = " WHERE ticker NOT IN (?,?,?)", TARGETS
                elif name == "sa_tracking_events":
                    where, params = " WHERE membership_id NOT IN (SELECT membership_id FROM sa_tracking_memberships WHERE ticker IN (?,?,?))", TARGETS
                elif name in {"security_lifecycle_cases", "security_lifecycle_assessments", "security_lifecycle_action_proposals"}:
                    where, params = " WHERE case_id NOT IN (?,?,?)", case_ids
                elif name in {"security_lifecycle_assessment_outcomes", "security_lifecycle_assessment_evidence"}:
                    where, params = " WHERE assessment_id NOT IN (SELECT assessment_id FROM security_lifecycle_assessments WHERE case_id IN (?,?,?))", case_ids
                elif name == "ticker_identity_transitions":
                    where, params = " WHERE source_ticker NOT IN (?,?,?)", TARGETS
                elif name in {"ticker_identity_transition_attempts", "ticker_identity_transition_activity"}:
                    where, params = " WHERE transition_id NOT IN (SELECT transition_id FROM ticker_identity_transitions WHERE source_ticker IN (?,?,?))", TARGETS
            rows = [tuple(row) for row in conn.execute(f'SELECT {columns} FROM "{name}"{where} ORDER BY rowid', params)]
            result[name] = digest(rows)
        return result


def observe(paths, *, at):
    from src.sa_tracking_memberships import read_sa_tracking_observations
    from src.security_lifecycle_schema import verify_profile_connection
    from src.security_lifecycle_investigation import case_id_for
    sources = scope(paths)
    observations = read_sa_tracking_observations(paths["sa"])
    targets, effects = [], []
    with closing(readonly(paths["profile"])) as conn:
        verify_profile_connection(conn)
        automation_off(conn)
        for ticker in TARGETS:
            row, effect = inventory.target_inventory(conn, ticker, sources, now=instant(at))
            require(row["ready_for_new_attended_preview"] and row["listing_end_date"] == TARGET_DATES[ticker]
                    and row["sources"] == ["sa_alpha_picks_former"] and row["evidence_records"] == 6
                    and row["sa_memberships_to_suppress"] == 1 and row["sa_current_sources_to_stop"] == 0
                    and row["watchlist_archives"] == row["legacy_archives"] == 0 and not row["already_hidden"],
                    "disposition_target_changed")
            age = instant(at) - instant(row["observed_at"])
            require(0 <= age.total_seconds() <= 72 * 3600, "disposition_evidence_expired")
            case_id = case_id_for("listing_authority", f"listing:{ticker}", ticker)
            require(conn.execute("SELECT count(*) FROM security_lifecycle_assessments WHERE case_id=?", (case_id,)).fetchone()[0] == 0,
                    "disposition_existing_assessment")
            targets.append({**row, "input_effects": effect["effects"]})
            effects.append(effect)
    return {"universe_before": len(sources), "universe_sha256": digest(sources), "sources": sources,
            "sa_observations_sha256": digest(observations), "effects_sha256": digest(effects), "targets": targets}


def require_expected(actual, expected):
    require(all(actual[key] == expected[key] for key in ("universe_before", "universe_sha256", "sa_observations_sha256", "effects_sha256")),
            "disposition_inputs_changed")
    require([row["ticker"] for row in actual["targets"]] == list(TARGETS), "disposition_target_scope")
    require({row["ticker"]: row["provider_check_sha256"] for row in actual["targets"]}
            == {row["ticker"]: row["provider_check_sha256"] for row in expected["targets"]}, "disposition_evidence_changed")


def backup(source, destination):
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with closing(readonly(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        require(dst.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "disposition_backup_integrity")
    return database_digest(destination)


def command_id(seed, ticker, prefix, ordinal):
    return prefix + "_" + digest([seed, ticker, prefix, ordinal])[:32]


def require_effects(preview, target):
    require(preview["eligible"] is True and preview["source_ticker"] == target["ticker"]
            and preview["transition_kind"] == "terminal_delisting" and preview["successor_ticker"] is None
            and preview["execute_on"] == target["listing_end_date"] and preview["outcomes"] == ["listing_ended"]
            and preview["active_sources"] == ["sa_alpha_picks_former"], "disposition_preview_scope")
    effects = preview["effects"]
    require(all(effects[key] == target["input_effects"][key] for key in ("watchlists", "legacy_config_seed", "sa_tracking_memberships"))
            and not effects["editable_tags_to_copy"] and not effects["priority"]["write_successor"]
            and effects["suppression"]["hide_source"] is True and not effects["suppression"]["unhide_successor"],
            "disposition_effects_changed")


def perform(paths, observed, directory, *, seed, clock, expected_previews=None):
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations, reconcile_sa_tracking
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.ticker_identity_service import TickerIdentityService
    from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
    directory.mkdir(mode=0o700, exist_ok=False)
    protected = domain_state(paths["profile"], protected=True)
    provider_before = domain_state(paths["profile"])["security_lifecycle_provider_checks"]
    observations = read_sa_tracking_observations(paths["sa"])
    require(digest(observations) == observed["sa_observations_sha256"], "disposition_sa_changed")
    with closing(readonly(paths["profile"])) as conn:
        members_before = conn.execute("SELECT * FROM sa_tracking_memberships ORDER BY membership_id").fetchall()
        events_before = conn.execute("SELECT * FROM sa_tracking_events ORDER BY event_id").fetchall()
    require(reconcile_sa_tracking(profile_db=paths["profile"], sa_db=paths["sa"], at=clock()), "disposition_sa_unavailable")
    with closing(readonly(paths["profile"])) as conn:
        require(conn.execute("SELECT * FROM sa_tracking_memberships ORDER BY membership_id").fetchall() == members_before
                and conn.execute("SELECT * FROM sa_tracking_events ORDER BY event_id").fetchall() == events_before,
                "disposition_sync_changed_intent")
    require(scope(paths) == observed["sources"], "disposition_sync_changed_sources")
    previews, results = {}, []
    for target in observed["targets"]:
        ticker = target["ticker"]
        counters = Counter()
        def identifier(prefix):
            counters[prefix] += 1
            return command_id(seed, ticker, prefix, counters[prefix])
        def before_write():
            with closing(readonly(paths["profile"])) as conn:
                automation_off(conn)
                check = ProviderCheckStore.latest_for_connection(conn, ticker)
                require(check is not None and check["digest"] == target["provider_check_sha256"], "disposition_evidence_changed")
            require(domain_state(paths["profile"], protected=True) == protected, "disposition_unrelated_state_changed")
            require(digest(read_sa_tracking_observations(paths["sa"])) == observed["sa_observations_sha256"], "disposition_sa_changed")
        before_write()
        with closing(sqlite3.connect(paths["profile"].as_uri() + "?mode=rw", uri=True)) as conn:
            store = SecurityLifecycleInvestigationStore(conn, id_factory=lambda prefix, ordinal: command_id(seed, ticker, prefix, ordinal))
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
        require_effects(preview, target)
        if expected_previews is not None:
            require(preview == expected_previews[ticker], "disposition_rehearsal_preview_changed")
        previews[ticker] = preview
        write(directory, f"{ticker}-intent.json", {"preview": preview, "transition_id": command_id(seed, ticker, "tit", 1)})
        approved = service.approve_case(case_id, options=options, preview_sha256=preview["preview_sha256"], before_write=before_write)
        write(directory, f"{ticker}-approved.json", approved)
        applied = service.execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=before_write)
        require(applied["status"] == "applied", "disposition_not_applied")
        write(directory, f"{ticker}-applied.json", applied)
        results.append({"ticker": ticker, "transition_id": approved["transition_id"], "preview_sha256": preview["preview_sha256"],
                        "listing_end_date": target["listing_end_date"], "status": applied["status"]})
        require(scope(paths) == {key: value for key, value in observed["sources"].items() if key not in {row["ticker"] for row in results}},
                "disposition_post_scope_changed")
    before_reconcile = domain_state(paths["profile"])
    require(reconcile_sa_tracking(profile_db=paths["profile"], sa_db=paths["sa"], at=clock()), "disposition_sa_unavailable")
    require(domain_state(paths["profile"]) == before_reconcile, "disposition_sa_resurrection_or_receipt_change")
    require(domain_state(paths["profile"], protected=True) == protected, "disposition_unrelated_state_changed")
    require(domain_state(paths["profile"])["security_lifecycle_provider_checks"] == provider_before, "disposition_old_snapshots_changed")
    with closing(readonly(paths["profile"])) as conn:
        store = TickerIdentityTransitionStore(conn, clock=clock)
        reverse = {row["ticker"]: store.reverse_readiness(row["transition_id"])["reversible"] for row in results}
        require(all(reverse.values()), "disposition_reverse_state_changed")
        require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)] and not conn.execute("PRAGMA foreign_key_check").fetchall(),
                "disposition_integrity")
        actual = conn.execute("SELECT source_ticker,kind,status,successor_ticker,approval_authority FROM ticker_identity_transitions WHERE source_ticker IN (?,?,?) ORDER BY source_ticker", TARGETS).fetchall()
        require(actual == [(ticker, "terminal_delisting", "applied", None, "attended_user") for ticker in TARGETS], "disposition_receipt_scope")
    sync = SaTrackingMembershipStore(paths["profile"]).synchronization_status(observations)
    require(sync == "current", "disposition_sync_incomplete")
    return {"previews": previews, "receipts": results, "applied": len(results), "universe_after": len(scope(paths)), "sa_sync_status": sync,
            "survives_sa_reconciliation": True, "old_provider_snapshots_unchanged": True, "all_reverse_ready": all(reverse.values()),
            "protected_state_sha256": digest(protected), "no_alias": True, "provider_requests": 0, "price_writes": 0}


def prepare(paths, expected, directory, *, clock=timestamp):
    require(not directory.exists(), "disposition_directory_exists")
    code_before = runtime_hashes()
    script_before = file_digest(Path(__file__))
    with reserve_sources(paths):
        with connections(paths):
            current = observe(paths, at=clock())
            require_expected(current, expected)
            before = domain_state(paths["profile"])
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        backups, hashes = {}, {}
        for role, path in paths.items():
            backups[role] = directory / f"{role}.before.db"
            hashes[role] = backup(path, backups[role])
        rehearsal = {**backups, "profile": directory / "profile.rehearsal.db"}
        backup(backups["profile"], rehearsal["profile"])
        with connections(backups):
            require_expected(observe(backups, at=clock()), current)
            require(domain_state(backups["profile"]) == before, "disposition_backup_changed")
        seed = digest({"observed": current, "domain": before, "created_at": clock()})
        with connections(rehearsal, writable_profile=True) as denials:
            performed = perform(rehearsal, current, directory / "rehearsal", seed=seed, clock=clock)
            require(not denials, "disposition_sql_scope_denied")
        with connections(paths):
            require_expected(observe(paths, at=clock()), current)
            require(domain_state(paths["profile"]) == before, "disposition_production_changed_during_prepare")
        require(runtime_hashes() == code_before and file_digest(Path(__file__)) == script_before, "disposition_runtime_changed_during_rehearsal")
        plan = {"at": clock(), "seed": seed, "observed": current, "domain_before": before, "backup_hashes": hashes,
                "previews": performed["previews"], "script_sha256": script_before,
                "database_paths": {role: str(path.resolve()) for role, path in paths.items()}, "runtime_hashes": code_before,
                "rehearsal_passed": True, "rehearsal_summary": {k: v for k, v in performed.items() if k not in {"previews", "receipts"}}}
        write(directory, "private-plan.json", plan)
        result = {"at": plan["at"], "plan_sha256": digest(plan), "rehearsal_applied": performed["applied"],
                  "rehearsal_universe_after": performed["universe_after"], "no_alias": True,
                  "targets": [{key: value for key, value in row.items() if key != "transition_id"} for row in performed["receipts"]],
                  "production_dispositions": 0, "provider_requests": 0, "price_writes": 0}
        write(directory, "prepare-summary.json", result)
        return result


def apply(paths, directory, *, approved_sha256, clock=timestamp):
    require(not (directory / "apply-started.json").exists(), "disposition_already_started")
    plan = json.loads((directory / "private-plan.json").read_text())
    require(digest(plan) == approved_sha256 and plan["rehearsal_passed"] is True, "disposition_approval_mismatch")
    require(file_digest(Path(__file__)) == plan["script_sha256"], "disposition_code_changed")
    require(runtime_hashes() == plan["runtime_hashes"], "disposition_runtime_changed")
    require({role: str(path.resolve()) for role, path in paths.items()} == plan["database_paths"], "disposition_database_paths_changed")
    for role, expected in plan["backup_hashes"].items():
        require(database_digest(directory / f"{role}.before.db") == expected, "disposition_backup_changed")
    with reserve_sources(paths, roles=("market", "sa")):
        histories_before = {role: database_digest(paths[role]) for role in ("market", "sa")}
        with connections(paths):
            current = observe(paths, at=clock())
            require_expected(current, plan["observed"])
            require(domain_state(paths["profile"]) == plan["domain_before"], "disposition_production_changed")
        write(directory, "apply-started.json", {"at": clock(), "approved_sha256": approved_sha256})
        with connections(paths, writable_profile=True) as denials:
            performed = perform(paths, current, directory / "production", seed=plan["seed"], clock=clock, expected_previews=plan["previews"])
            require(not denials, "disposition_sql_scope_denied")
        require({role: database_digest(paths[role]) for role in ("market", "sa")} == histories_before, "disposition_history_changed")
        result = {key: value for key, value in performed.items() if key not in {"previews", "receipts"}}
        result.update({"at": clock(), "plan_sha256": approved_sha256, "history_databases_unchanged": True,
                       "targets": [{k: v for k, v in row.items() if k != "transition_id"} for row in performed["receipts"]]})
        write(directory, "apply-summary.json", result)
        return result


def audit_for(paths, directory):
    databases = {str(path.resolve()) for path in paths.values()}
    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise DispositionStopped("disposition_external_execution_forbidden")
        if event == "sqlite3.connect":
            name = os.fsdecode(args[0])
            candidate = name.removeprefix("file:").split("?", 1)[0]
            path = Path(candidate).resolve()
            require(str(path) in databases or (path.parent == directory.resolve() and path.suffix == ".db"), "disposition_database_scope")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            require(not path.name.startswith(".env") and path.name not in {"auth.json", "credentials.json"}, "disposition_ambient_auth_forbidden")
    return audit


def recorded_status(paths):
    with connections(paths), closing(readonly(paths["profile"])) as conn:
        rows = conn.execute("SELECT source_ticker,status FROM ticker_identity_transitions WHERE source_ticker IN (?,?,?) ORDER BY source_ticker", TARGETS).fetchall()
    return {"recorded_applied": sum(row[1] == "applied" for row in rows),
            "recorded_approved": sum(row[1] == "approved" for row in rows),
            "targets": [{"ticker": row[0], "status": row[1]} for row in rows]}


def stopped():
    for port in (8430, 39769):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise DispositionStopped("disposition_app_port_in_use") from None


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
    sys.addaudithook(audit_for(paths, args.directory))
    logging.disable(logging.CRITICAL)
    stopped()
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
            failure["readback"] = recorded_status(paths)
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
