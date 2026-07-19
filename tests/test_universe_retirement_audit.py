"""Contracts for the fingerprinted legacy-universe retirement gate."""

from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import os
import sqlite3
from contextlib import contextmanager
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

    sa_capture_store.connect(str(sa_path)).close()
    _insert_pick(sa_path, "BTSG")
    _set_current_refresh(sa_path)
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


def _apply(audit, sources, report, output: Path, *, overview=None, approvals=None):
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
        ("BTSG", "overlap"),
        ("HAPN", "db_only"),
        ("LC", "superseded_by_rename"),
        ("OKTA", "json_only"),
    ]
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


def test_apply_rejects_changed_json_or_database_fingerprint_before_write(tmp_path):
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


def test_apply_requires_explicit_approval_for_every_visible_json_only_symbol(
    sources, tmp_path
):
    audit = _audit()
    report = _preview(audit, sources)
    assert report["requires_approval"] == ["OKTA"]

    profile_before = _sqlite_semantic_digest(sources.profile_path)
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


def test_apply_and_transition_export_are_exact_and_idempotent_after_fresh_preview(
    sources, tmp_path
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


def test_audit_never_opens_or_replaces_the_source_json_for_write(
    sources, tmp_path, monkeypatch
):
    audit = _audit()
    report = _preview(audit, sources)
    source_before = sources.legacy_json.read_bytes()
    source_mode = sources.legacy_json.stat().st_mode
    open_modes, replacements = _install_source_write_guard(
        monkeypatch,
        audit,
        sources.legacy_json,
    )
    transition = tmp_path / "allowed-transition.json"

    _apply(audit, sources, report, transition)

    assert open_modes and set(open_modes) <= {"r", "rb"}
    assert replacements
    assert {destination for _source, destination in replacements} == {
        transition.resolve()
    }
    assert sources.legacy_json.read_bytes() == source_before
    assert sources.legacy_json.stat().st_mode == source_mode
    assert transition.exists()
