"""Contracts for the fingerprinted legacy-universe retirement gate."""

from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import sa_capture_store
from src.active_universe import build_active_universe_snapshot
from src.portfolio_state import PortfolioStore
from src.profile_state import ProfileStateStore
from src.universe_compat import flatten_generated_active_tickers


FIXTURE = Path(__file__).parent / "fixtures" / "universe" / "tickers_core_legacy.json"
NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-07-19T12:00:00+00:00"
FINGERPRINT_KEYS = {
    "legacy_json_sha256",
    "profile_sources_sha256",
    "sa_sources_sha256",
    "legacy_overview_sha256",
}

_REAL_SQLITE_CONNECT = sqlite3.connect
_REAL_OPEN = builtins.open
_REAL_PATH_OPEN = Path.open
_REAL_OS_REPLACE = os.replace


def _audit():
    return importlib.import_module("src.audit.universe_retirement")


def _insert_pick(
    path: Path,
    symbol: str,
    *,
    picked_date: str = "2026-07-01",
) -> None:
    symbol_key = symbol.strip().upper()
    with _REAL_SQLITE_CONNECT(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sa_pick_lineages "
            "(symbol_key, picked_date, created_at) VALUES (?, ?, ?)",
            (symbol_key, picked_date, NOW_TEXT),
        )
        lineage_id = conn.execute(
            "SELECT lineage_id FROM sa_pick_lineages "
            "WHERE symbol_key=? AND picked_date=?",
            (symbol_key, picked_date),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO sa_alpha_picks "
            "(lineage_id, symbol, company, picked_date, portfolio_status, is_stale) "
            "VALUES (?, ?, ?, ?, 'current', 0)",
            (lineage_id, symbol, f"{symbol_key} Inc", picked_date),
        )


def _set_current_refresh(path: Path, *, row_count: int = 1) -> None:
    with _REAL_SQLITE_CONNECT(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sa_refresh_meta "
            "(scope, last_attempt_at, last_success_at, snapshot_ts, row_count, ok, "
            "last_error, updated_at) VALUES ('current', ?, ?, ?, ?, 1, NULL, ?)",
            (NOW_TEXT, NOW_TEXT, NOW_TEXT, row_count, NOW_TEXT),
        )


def _make_sources(root: Path) -> SimpleNamespace:
    root.mkdir(parents=True)
    profile_path = root / "profile_state.db"
    sa_path = root / "sa_capture.db"
    legacy_json = root / "tickers_core.json"
    legacy_json.write_bytes(FIXTURE.read_bytes())

    profile = ProfileStateStore(profile_path)
    portfolio = PortfolioStore(profile_path)
    profile.import_lists([{"name": "Core", "tickers": ["AAPL"]}])
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(
        account_id=account.id,
        symbol="HAPN",
        quantity=1,
    )
    profile.set_universe_hidden("ATGE", True)
    profile.set_universe_hidden("BRK.B", True)

    sa_capture_store.connect(str(sa_path)).close()
    _insert_pick(sa_path, "BTSG")
    _insert_pick(sa_path, "BRK.B")
    _set_current_refresh(sa_path, row_count=2)
    return SimpleNamespace(
        profile_path=profile_path,
        sa_path=sa_path,
        legacy_json=legacy_json,
        profile=profile,
        portfolio=portfolio,
        overview=("AAPL", "BTSG", "HAPN"),
    )


@pytest.fixture()
def sources(tmp_path):
    return _make_sources(tmp_path / "sources")


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: (
            {"__bytes__": bytes(item).hex()}
            if isinstance(item, (bytes, bytearray, memoryview))
            else repr(item)
        ),
    ).encode("utf-8")


def _sqlite_semantic_digest(path: Path) -> str:
    payload: list[dict[str, object]] = []
    with _REAL_SQLITE_CONNECT(path) as conn:
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' ORDER BY name"
        ).fetchall()
        for table in tables:
            name = table["name"]
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
            ]
            rows = [
                list(row)
                for row in conn.execute(f"SELECT * FROM {quoted}").fetchall()
            ]
            rows.sort(key=lambda row: _json_bytes(row))
            payload.append(
                {
                    "name": name,
                    "sql": table["sql"],
                    "columns": columns,
                    "rows": rows,
                }
            )
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _sqlite_backup(source: Path, target: Path) -> None:
    with _REAL_SQLITE_CONNECT(source) as source_conn:
        with _REAL_SQLITE_CONNECT(target) as target_conn:
            source_conn.backup(target_conn)


def _break_writer_schema(path: Path, finding: str) -> None:
    with _REAL_SQLITE_CONNECT(path) as conn:
        if finding == "membership_created_at":
            conn.execute("DROP TABLE universe_source_memberships")
            conn.execute(
                "CREATE TABLE universe_source_memberships ("
                "source_key TEXT NOT NULL, ticker TEXT NOT NULL, archived_at TEXT, "
                "PRIMARY KEY (source_key, ticker))"
            )
        elif finding == "membership_conflict_shape":
            conn.execute("DROP TABLE universe_source_memberships")
            conn.execute(
                "CREATE TABLE universe_source_memberships ("
                "source_key TEXT NOT NULL, ticker TEXT NOT NULL, "
                "created_at TEXT NOT NULL, archived_at TEXT)"
            )
        else:
            conn.execute("DROP TABLE universe_source_annotations")
            conn.execute(
                "CREATE TABLE universe_source_annotations ("
                "source_key TEXT NOT NULL, ticker TEXT NOT NULL, "
                "annotation_key TEXT NOT NULL, annotation_value TEXT NOT NULL)"
            )


def _legacy_rows(path: Path) -> dict[str, list[list[object]]]:
    with _REAL_SQLITE_CONNECT(path) as conn:
        memberships = [
            list(row)
            for row in conn.execute(
                "SELECT source_key, ticker, created_at, archived_at "
                "FROM universe_source_memberships ORDER BY source_key, ticker"
            )
        ]
        annotations = [
            list(row)
            for row in conn.execute(
                "SELECT source_key, ticker, annotation_key, annotation_value "
                "FROM universe_source_annotations "
                "ORDER BY source_key, ticker, annotation_key, annotation_value"
            )
        ]
    return {"memberships": memberships, "annotations": annotations}


_MUTATING_SQLITE_ACTIONS = {
    getattr(sqlite3, name)
    for name in (
        "SQLITE_ALTER_TABLE",
        "SQLITE_ATTACH",
        "SQLITE_CREATE_INDEX",
        "SQLITE_CREATE_TABLE",
        "SQLITE_CREATE_TEMP_INDEX",
        "SQLITE_CREATE_TEMP_TABLE",
        "SQLITE_CREATE_TEMP_TRIGGER",
        "SQLITE_CREATE_TEMP_VIEW",
        "SQLITE_CREATE_TRIGGER",
        "SQLITE_CREATE_VIEW",
        "SQLITE_DELETE",
        "SQLITE_DETACH",
        "SQLITE_DROP_INDEX",
        "SQLITE_DROP_TABLE",
        "SQLITE_DROP_TEMP_INDEX",
        "SQLITE_DROP_TEMP_TABLE",
        "SQLITE_DROP_TEMP_TRIGGER",
        "SQLITE_DROP_TEMP_VIEW",
        "SQLITE_DROP_TRIGGER",
        "SQLITE_DROP_VIEW",
        "SQLITE_INSERT",
        "SQLITE_REINDEX",
        "SQLITE_UPDATE",
    )
}


def _install_sqlite_read_guard(monkeypatch, audit, sources):
    traces: list[str] = []
    denied: list[tuple[int, str | None, str | None]] = []
    opens: list[str] = []
    names = {sources.profile_path.name, sources.sa_path.name}

    def guarded_connect(database, *args, **kwargs):
        rendered = os.fspath(database)
        connection = _REAL_SQLITE_CONNECT(database, *args, **kwargs)
        if any(name in rendered for name in names):
            opens.append(rendered)
            assert kwargs.get("uri") is True
            assert "mode=ro" in rendered

            def authorize(action, first, second, _database, _trigger):
                if action in _MUTATING_SQLITE_ACTIONS:
                    denied.append((action, first, second))
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            connection.set_authorizer(authorize)
            connection.set_trace_callback(traces.append)
        return connection

    monkeypatch.setattr(audit.sqlite3, "connect", guarded_connect)
    return traces, denied, opens


def _path(value: object) -> Path | None:
    if isinstance(value, int):
        return None
    try:
        return Path(os.fspath(value)).resolve()
    except (TypeError, ValueError, OSError):
        return None


def _alias_path(root: Path, source: Path, alias_kind: str, label: str) -> Path:
    if alias_kind == "direct":
        return source
    alias = root / f"{label}-{alias_kind}"
    if alias_kind == "symlink":
        alias.symlink_to(source)
    else:
        os.link(source, alias)
    return alias


def _install_source_write_guard(monkeypatch, audit, source: Path):
    source = source.resolve()
    open_modes: list[str] = []
    replacements: list[tuple[Path | None, Path | None]] = []

    def guarded_open(file, mode="r", *args, **kwargs):
        if _path(file) == source:
            open_modes.append(mode)
            assert not ({"w", "a", "x", "+"} & set(mode))
        return _REAL_OPEN(file, mode, *args, **kwargs)

    def guarded_path_open(self, mode="r", buffering=-1, encoding=None, errors=None,
                          newline=None):
        if self.resolve() == source:
            open_modes.append(mode)
            assert not ({"w", "a", "x", "+"} & set(mode))
        return _REAL_PATH_OPEN(
            self,
            mode,
            buffering,
            encoding,
            errors,
            newline,
        )

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "open", guarded_path_open)

    for method_name in ("write_bytes", "write_text", "touch", "unlink", "rename", "replace"):
        original = getattr(Path, method_name)

        def guarded_path_operation(self, *args, _original=original,
                                   _method_name=method_name, **kwargs):
            destination = _path(args[0]) if args and _method_name in {"rename", "replace"} else None
            if self.resolve() == source or destination == source:
                raise AssertionError(f"source JSON {_method_name} is forbidden")
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(Path, method_name, guarded_path_operation)

    def guarded_replace(source_path, destination_path):
        pair = (_path(source_path), _path(destination_path))
        replacements.append(pair)
        assert source not in pair
        return _REAL_OS_REPLACE(source_path, destination_path)

    monkeypatch.setattr(audit.os, "replace", guarded_replace)
    return open_modes, replacements


def _preview(audit, sources, *, overview=None):
    return audit.build_preview_report(
        profile_db=sources.profile_path,
        sa_db=sources.sa_path,
        legacy_json=sources.legacy_json,
        legacy_overview_tickers=sources.overview if overview is None else overview,
        now=NOW,
    )


def _apply(
    audit,
    sources,
    report,
    output: Path,
    *,
    overview=None,
    approvals=None,
    preview_report_path=None,
):
    optional = (
        {"preview_report_path": preview_report_path}
        if preview_report_path is not None
        else {}
    )
    return audit.apply_reviewed_preview(
        profile_db=sources.profile_path,
        sa_db=sources.sa_path,
        legacy_json=sources.legacy_json,
        legacy_overview_tickers=sources.overview if overview is None else overview,
        preview_report=report,
        approved_json_only=(
            report["requires_approval"] if approvals is None else approvals
        ),
        transition_out=output,
        now=NOW,
        **optional,
    )


def test_preview_is_read_only_and_emits_semantic_source_fingerprints(
    sources, tmp_path, monkeypatch
):
    audit = _audit()
    profile_before = _sqlite_semantic_digest(sources.profile_path)
    sa_before = _sqlite_semantic_digest(sources.sa_path)
    json_before = sources.legacy_json.read_bytes()
    traces, denied, database_opens = _install_sqlite_read_guard(
        monkeypatch, audit, sources
    )
    source_modes, replacements = _install_source_write_guard(
        monkeypatch, audit, sources.legacy_json
    )

    report = _preview(audit, sources)

    assert set(report) == {
        "fingerprints",
        "counts",
        "rows",
        "overview_missing",
        "requires_approval",
    }
    assert set(report["fingerprints"]) == FINGERPRINT_KEYS
    assert audit.InputFingerprints(**report["fingerprints"])
    assert report["fingerprints"]["legacy_json_sha256"] == hashlib.sha256(
        json_before
    ).hexdigest()
    assert all(len(value) == 64 for value in report["fingerprints"].values())
    assert report["counts"] == {"json_active": 5, "snapshot_active": 3}
    assert report["overview_missing"] == []
    assert report["requires_approval"] == ["OKTA"]
    assert [(row["ticker"], row["classification"]) for row in report["rows"]] == [
        ("AAPL", "overlap"),
        ("ATGE", "hidden"),
        ("BRK.B", "hidden"),
        ("BTSG", "overlap"),
        ("HAPN", "db_only"),
        ("LC", "superseded_by_rename"),
        ("OKTA", "json_only"),
    ]
    by_ticker = {row["ticker"]: row for row in report["rows"]}
    assert by_ticker["BRK.B"]["sources"] == ["sa_alpha_picks_current"]
    assert by_ticker["BRK.B"]["category_paths"] == []
    assert denied == []
    assert database_opens
    assert traces
    assert not any(
        statement.lstrip().split(maxsplit=1)[0].upper()
        in {"ALTER", "CREATE", "DELETE", "DROP", "INSERT", "REPLACE", "UPDATE", "VACUUM"}
        for statement in traces
        if statement.strip()
    )
    assert source_modes and set(source_modes) <= {"r", "rb"}
    assert replacements == []
    assert _sqlite_semantic_digest(sources.profile_path) == profile_before
    assert _sqlite_semantic_digest(sources.sa_path) == sa_before
    assert sources.legacy_json.read_bytes() == json_before
    rendered = json.dumps(report, sort_keys=True)
    assert str(tmp_path) not in rendered
    assert "OperationalError" not in rendered

    with _REAL_SQLITE_CONNECT(sources.profile_path) as conn:
        conn.execute("CREATE TABLE audit_irrelevant_profile (value TEXT)")
        conn.execute("INSERT INTO audit_irrelevant_profile VALUES ('ignored')")
    with _REAL_SQLITE_CONNECT(sources.sa_path) as conn:
        conn.execute("CREATE TABLE audit_irrelevant_sa (value TEXT)")
        conn.execute("INSERT INTO audit_irrelevant_sa VALUES ('ignored')")
    repeated = _preview(audit, sources)
    assert repeated["fingerprints"] == report["fingerprints"]

    missing_schema = tmp_path / "missing-required-schema.db"
    _REAL_SQLITE_CONNECT(missing_schema).close()
    with pytest.raises(audit.RequiredSchemaMissing) as exc_info:
        audit.build_preview_report(
            profile_db=missing_schema,
            sa_db=sources.sa_path,
            legacy_json=sources.legacy_json,
            legacy_overview_tickers=sources.overview,
            now=NOW,
        )
    assert exc_info.value.code == "required_schema_missing"
    assert exc_info.value.source == "profile"
    assert str(missing_schema) not in str(exc_info.value)

    writer_schema_cases = (
        (
            "membership_created_at",
            "universe_source_memberships.created_at",
        ),
        (
            "membership_conflict_shape",
            "universe_source_memberships.unique(source_key,ticker)",
        ),
        (
            "annotation_conflict_shape",
            "universe_source_annotations.unique(source_key,ticker,annotation_key,annotation_value)",
        ),
    )
    for index, (finding, required_shape) in enumerate(writer_schema_cases):
        malformed = tmp_path / f"malformed-writer-{index}.db"
        _sqlite_backup(sources.profile_path, malformed)
        _break_writer_schema(malformed, finding)

        with pytest.raises(audit.RequiredSchemaMissing) as malformed_exc:
            audit.build_preview_report(
                profile_db=malformed,
                sa_db=sources.sa_path,
                legacy_json=sources.legacy_json,
                legacy_overview_tickers=sources.overview,
                now=NOW,
            )

        assert required_shape in malformed_exc.value.missing
        assert str(malformed) not in str(malformed_exc.value)


def test_preview_proves_legacy_overview_subset_or_stops(sources, tmp_path):
    audit = _audit()
    represented = _preview(audit, sources, overview=(" aapl ", "BTSG"))
    missing = _preview(
        audit,
        sources,
        overview=("AAPL", "BTSG", "not-represented"),
    )

    assert represented["overview_missing"] == []
    assert missing["overview_missing"] == ["NOT-REPRESENTED"]
    profile_before = _sqlite_semantic_digest(sources.profile_path)
    transition = tmp_path / "blocked-overview.json"
    with pytest.raises(audit.OverviewCoverageError) as exc_info:
        _apply(
            audit,
            sources,
            missing,
            transition,
            overview=("AAPL", "BTSG", "not-represented"),
        )
    assert exc_info.value.missing == ("NOT-REPRESENTED",)
    assert _sqlite_semantic_digest(sources.profile_path) == profile_before
    assert not transition.exists()


def test_apply_rejects_changed_json_or_database_fingerprint_before_write(
    tmp_path, monkeypatch
):
    audit = _audit()
    cases = (
        "legacy_json_sha256",
        "profile_sources_sha256",
        "sa_sources_sha256",
        "legacy_overview_sha256",
    )

    for index, changed_key in enumerate(cases):
        case = _make_sources(tmp_path / f"case-{index}")
        report = _preview(audit, case)
        overview = case.overview
        if changed_key == "legacy_json_sha256":
            case.legacy_json.write_bytes(case.legacy_json.read_bytes() + b"\n")
        elif changed_key == "profile_sources_sha256":
            case.profile.import_lists([{"name": "Changed", "tickers": ["NEW"]}])
        elif changed_key == "sa_sources_sha256":
            _insert_pick(case.sa_path, "NEW", picked_date="2026-07-02")
        else:
            overview = (*case.overview, "NEW")

        profile_before = _sqlite_semantic_digest(case.profile_path)
        transition = tmp_path / f"rejected-{index}.json"
        with pytest.raises(audit.FingerprintMismatch) as exc_info:
            _apply(
                audit,
                case,
                report,
                transition,
                overview=overview,
            )
        assert exc_info.value.changed == (changed_key,)
        assert _sqlite_semantic_digest(case.profile_path) == profile_before
        assert not transition.exists()

    for index, changed_key in enumerate(cases):
        case = _make_sources(tmp_path / f"hook-case-{index}")
        overview = list(case.overview)
        report = _preview(audit, case, overview=overview)
        legacy_before = _legacy_rows(case.profile_path)
        accepted_row_tickers: list[str] = []
        original_build = audit.build_reviewed_import

        def build_then_mutate(rows, approvals):
            reviewed = original_build(rows, approvals)
            accepted_row_tickers.extend(row.ticker for row in rows)
            if changed_key == "legacy_json_sha256":
                document = json.loads(case.legacy_json.read_text(encoding="utf-8"))
                document["tier2_expanded"]["identity_access"]["tickers"].append(
                    "RACE"
                )
                case.legacy_json.write_text(
                    json.dumps(document, sort_keys=True),
                    encoding="utf-8",
                )
            elif changed_key == "profile_sources_sha256":
                case.profile.import_lists(
                    [{"name": "Concurrent", "tickers": ["RACE"]}]
                )
            elif changed_key == "sa_sources_sha256":
                _insert_pick(case.sa_path, "RACE", picked_date="2026-07-03")
            else:
                overview.append("RACE")
            return reviewed

        def forbid_profile_transaction(_path):
            raise AssertionError("profile transaction reached after source changed")

        transition = tmp_path / f"hook-rejected-{index}.json"
        with monkeypatch.context() as scoped:
            scoped.setattr(audit, "build_reviewed_import", build_then_mutate)
            scoped.setattr(
                audit,
                "_profile_store_for_existing_schema",
                forbid_profile_transaction,
            )
            with pytest.raises(audit.FingerprintMismatch) as hook_exc:
                _apply(
                    audit,
                    case,
                    report,
                    transition,
                    overview=overview,
                )

        assert hook_exc.value.changed == (changed_key,)
        assert _legacy_rows(case.profile_path) == legacy_before
        assert "RACE" not in accepted_row_tickers
        assert not transition.exists()


def test_apply_requires_explicit_approval_for_every_visible_json_only_symbol(
    sources, tmp_path
):
    audit = _audit()
    report = _preview(audit, sources)
    assert report["requires_approval"] == ["OKTA"]

    profile_before = _sqlite_semantic_digest(sources.profile_path)
    for index, blank in enumerate(("", " ", "\t\n")):
        blank_output = tmp_path / f"blank-approval-{index}.json"
        with pytest.raises(audit.InvalidApproval):
            _apply(
                audit,
                sources,
                report,
                blank_output,
                approvals=(blank,),
            )
        assert not blank_output.exists()

    missing_output = tmp_path / "missing-approval.json"
    with pytest.raises(audit.ApprovalMismatch) as missing_exc:
        _apply(audit, sources, report, missing_output, approvals=())
    assert missing_exc.value.missing == ("OKTA",)
    assert missing_exc.value.extra == ()

    extra_output = tmp_path / "extra-approval.json"
    with pytest.raises(audit.ApprovalMismatch) as extra_exc:
        _apply(
            audit,
            sources,
            report,
            extra_output,
            approvals=("OKTA", "AAPL"),
        )
    assert extra_exc.value.missing == ()
    assert extra_exc.value.extra == ("AAPL",)
    assert _sqlite_semantic_digest(sources.profile_path) == profile_before
    assert not missing_output.exists()
    assert not extra_output.exists()

    apply_argv = [
        "apply",
        "--profile-db",
        "profile.db",
        "--sa-db",
        "sa.db",
        "--legacy-json",
        "legacy.json",
        "--preview-report",
        "preview.json",
        "--transition-out",
        "transition.json",
    ]
    parser = audit._build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(apply_argv)
    approve_none = parser.parse_args([*apply_argv, "--approve-none"])
    assert approve_none.approve_none is True
    assert approve_none.approve_json_only is None
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                *apply_argv,
                "--approve-json-only",
                "OKTA",
                "--approve-none",
            ]
        )


def test_apply_and_transition_export_are_exact_and_idempotent_after_fresh_preview(
    sources, tmp_path, monkeypatch
):
    audit = _audit()
    first_preview = _preview(audit, sources)
    first_transition = tmp_path / "transition-first.json"

    _apply(audit, sources, first_preview, first_transition)

    first_document = json.loads(first_transition.read_text(encoding="utf-8"))
    first_snapshot = build_active_universe_snapshot(
        profile_db=sources.profile_path,
        sa_db=sources.sa_path,
        now=NOW,
    )
    assert flatten_generated_active_tickers(first_document) == set(
        first_snapshot.tickers
    ) == {"AAPL", "BTSG", "HAPN", "OKTA"}
    memberships = _legacy_rows(sources.profile_path)["memberships"]
    assert len(memberships) == 1
    assert memberships[0][:2] == ["legacy_config_seed", "OKTA"]
    assert memberships[0][2]
    assert memberships[0][3] is None

    after_first = _sqlite_semantic_digest(sources.profile_path)
    stale_output = tmp_path / "stale-preview.json"
    with pytest.raises(audit.FingerprintMismatch) as stale_exc:
        _apply(audit, sources, first_preview, stale_output)
    assert stale_exc.value.changed == ("profile_sources_sha256",)
    assert _sqlite_semantic_digest(sources.profile_path) == after_first
    assert not stale_output.exists()

    fresh_preview = _preview(audit, sources)
    assert fresh_preview["requires_approval"] == []
    rows_before = _legacy_rows(sources.profile_path)
    bytes_before = first_transition.read_bytes()
    second_transition = tmp_path / "transition-second.json"

    _apply(
        audit,
        sources,
        fresh_preview,
        second_transition,
        approvals=(),
    )

    assert _legacy_rows(sources.profile_path) == rows_before
    assert second_transition.read_bytes() == bytes_before

    exported = tmp_path / "transition-export.json"
    audit.export_transition_snapshot(
        profile_db=sources.profile_path,
        sa_db=sources.sa_path,
        output=exported,
        now=NOW,
    )
    assert exported.read_bytes() == bytes_before

    failure_cases = (
        ("post_commit_verification", "build_compat_export", ValueError),
        ("transition_write", "write_compat_export", OSError),
    )
    for index, (stage, patched_name, failure_type) in enumerate(failure_cases):
        case = _make_sources(tmp_path / f"post-commit-{index}")
        preview = _preview(audit, case)
        backup = tmp_path / f"profile-backup-{index}.db"
        _sqlite_backup(case.profile_path, backup)
        backup_digest = _sqlite_semantic_digest(backup)
        transition = tmp_path / f"post-commit-{index}.json"
        original_transition = b""
        if stage == "transition_write":
            original_transition = b"existing transition\n"
            transition.write_bytes(original_transition)

        def fail_after_commit(*_args, **_kwargs):
            raise failure_type("synthetic post-commit failure")

        with monkeypatch.context() as scoped:
            scoped.setattr(audit, patched_name, fail_after_commit)
            with pytest.raises(audit.RestoreRequired) as restore_exc:
                _apply(audit, case, preview, transition)

        assert restore_exc.value.stage == stage
        assert restore_exc.value.as_dict() == {
            "code": "restore_required",
            "stage": stage,
        }
        assert _legacy_rows(case.profile_path)["memberships"]
        assert _sqlite_semantic_digest(case.profile_path) != backup_digest
        assert _sqlite_semantic_digest(backup) == backup_digest
        assert _legacy_rows(backup) == {"memberships": [], "annotations": []}
        if stage == "transition_write":
            assert transition.read_bytes() == original_transition
        else:
            assert not transition.exists()


def test_audit_never_opens_or_replaces_the_source_json_for_write(
    sources, tmp_path, monkeypatch
):
    audit = _audit()
    report = _preview(audit, sources)
    preview_report_path = tmp_path / "preview-report.json"
    preview_report_path.write_text(json.dumps(report), encoding="utf-8")
    source_before = sources.legacy_json.read_bytes()
    source_mode = sources.legacy_json.stat().st_mode
    profile_before = _sqlite_semantic_digest(sources.profile_path)
    sa_before = _sqlite_semantic_digest(sources.sa_path)
    preview_report_before = preview_report_path.read_bytes()
    open_modes, replacements = _install_source_write_guard(
        monkeypatch,
        audit,
        sources.legacy_json,
    )

    def invoke_with_output(operation: str, output: Path) -> None:
        if operation == "preview":
            audit.write_preview_report(
                profile_db=sources.profile_path,
                sa_db=sources.sa_path,
                legacy_json=sources.legacy_json,
                legacy_overview_tickers=sources.overview,
                report_out=output,
                now=NOW,
            )
        elif operation == "apply":
            _apply(
                audit,
                sources,
                report,
                output,
                preview_report_path=preview_report_path,
            )
        else:
            audit.export_transition_snapshot(
                profile_db=sources.profile_path,
                sa_db=sources.sa_path,
                output=output,
                now=NOW,
            )

    protected_outputs = (
        ("preview", "profile", sources.profile_path),
        ("preview", "sa", sources.sa_path),
        ("preview", "legacy", sources.legacy_json),
        ("apply", "profile", sources.profile_path),
        ("apply", "sa", sources.sa_path),
        ("apply", "legacy", sources.legacy_json),
        ("apply", "report", preview_report_path),
        ("export", "profile", sources.profile_path),
        ("export", "sa", sources.sa_path),
    )
    alias_root = tmp_path / "aliases"
    alias_root.mkdir()
    for operation, label, protected in protected_outputs:
        for alias_kind in ("direct", "symlink", "hardlink"):
            alias = _alias_path(
                alias_root,
                protected,
                alias_kind,
                f"{operation}-{label}",
            )
            try:
                with pytest.raises(audit.OutputPathConflict):
                    invoke_with_output(operation, alias)
            finally:
                if alias_kind != "direct" and os.path.lexists(alias):
                    os.unlink(alias)

    assert _sqlite_semantic_digest(sources.profile_path) == profile_before
    assert _sqlite_semantic_digest(sources.sa_path) == sa_before
    assert sources.legacy_json.read_bytes() == source_before
    assert preview_report_path.read_bytes() == preview_report_before
    assert replacements == []

    preflight_cases = (
        "missing_parent",
        "directory_target",
        "parent_not_directory",
        "symlink_target",
        "symlink_loop",
        "unwritable_parent",
    )
    for index, shape in enumerate(preflight_cases):
        case = _make_sources(tmp_path / f"preflight-{index}")
        case_report = _preview(audit, case)
        legacy_before = _legacy_rows(case.profile_path)
        if shape == "missing_parent":
            output = tmp_path / f"absent-{index}" / "transition.json"
        elif shape == "directory_target":
            output = tmp_path / f"directory-target-{index}"
            output.mkdir()
        elif shape == "parent_not_directory":
            parent = tmp_path / f"parent-file-{index}"
            parent.write_text("not a directory", encoding="utf-8")
            output = parent / "transition.json"
        elif shape == "symlink_target":
            target = tmp_path / f"unrelated-target-{index}.json"
            target.write_text("unrelated", encoding="utf-8")
            output = tmp_path / f"unrelated-link-{index}.json"
            output.symlink_to(target)
        elif shape == "symlink_loop":
            output = tmp_path / f"loop-link-{index}.json"
            output.symlink_to(output.name)
        else:
            parent = tmp_path / f"unwritable-{index}"
            parent.mkdir()
            parent.chmod(0o500)
            output = parent / "transition.json"
        try:
            with pytest.raises(audit.OutputPreflightError):
                _apply(audit, case, case_report, output)
        finally:
            if shape == "unwritable_parent":
                output.parent.chmod(0o700)
        assert _legacy_rows(case.profile_path) == legacy_before

    transition = tmp_path / "allowed-transition.json"

    _apply(
        audit,
        sources,
        report,
        transition,
        preview_report_path=preview_report_path,
    )

    assert open_modes and set(open_modes) <= {"r", "rb"}
    assert replacements
    assert {destination for _source, destination in replacements} == {
        transition.resolve()
    }
    assert sources.legacy_json.read_bytes() == source_before
    assert sources.legacy_json.stat().st_mode == source_mode
    assert transition.exists()
