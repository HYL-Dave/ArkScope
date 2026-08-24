from __future__ import annotations

import hashlib
import inspect
import sqlite3

import pytest


_AT = "2026-08-24T00:00:00Z"


def _create_profile(path):
    from src.security_lifecycle_schema import create_v1_profile_schema

    connection = sqlite3.connect(path)
    create_v1_profile_schema(connection)
    connection.execute(
        "INSERT INTO security_lifecycle_cases "
        "(case_id,source,source_ref,ticker,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        ("slc_retirement", "sec_edgar", "accession", "RET", _AT, _AT),
    )
    connection.commit()
    connection.close()


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preflight_requires_explicit_existing_profile_path_and_never_creates(tmp_path):
    from src.security_lifecycle_retirement import (
        TavilyRetirementUnavailable,
        preflight_tavily_retirement,
    )

    parameter = inspect.signature(preflight_tavily_retirement).parameters[
        "profile_path"
    ]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty

    missing = tmp_path / "missing" / "profile_state.db"
    with pytest.raises(TavilyRetirementUnavailable) as caught:
        preflight_tavily_retirement(profile_path=missing)
    assert caught.value.code == "tavily_retirement_preflight_unavailable"
    assert not missing.exists()
    assert not missing.parent.exists()


def test_preflight_accepts_empty_legacy_storage_without_writes(tmp_path):
    from src.security_lifecycle_retirement import preflight_tavily_retirement

    path = tmp_path / "profile_state.db"
    _create_profile(path)
    before = path.stat()
    digest = _sha256(path)

    report = preflight_tavily_retirement(profile_path=path)

    after = path.stat()
    assert report.profile_path == str(path.resolve())
    assert report.tavily_run_count == 0
    assert report.tavily_evidence_count == 0
    assert report.storage_empty is True
    assert _sha256(path) == digest
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )


def test_preflight_rejects_stored_tavily_runs_with_exact_counts(tmp_path):
    from src.security_lifecycle_retirement import (
        TavilyRetirementBlocked,
        preflight_tavily_retirement,
    )

    path = tmp_path / "profile_state.db"
    _create_profile(path)
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO security_lifecycle_investigation_runs "
        "(run_id,case_id,trigger,adapter,status,query_plan_json,query_count,"
        "result_count,fetch_count,usage_json,started_at,finished_at,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "run_tavily",
            "slc_retirement",
            "attended_user",
            "tavily",
            "succeeded",
            "[]",
            0,
            0,
            0,
            "{}",
            _AT,
            _AT,
            _AT,
        ),
    )
    connection.commit()
    connection.close()

    with pytest.raises(TavilyRetirementBlocked) as caught:
        preflight_tavily_retirement(profile_path=path)
    assert caught.value.code == "stored_tavily_rows_present"
    assert caught.value.run_count == 1
    assert caught.value.evidence_count == 0


def test_preflight_rejects_stored_tavily_evidence_with_exact_counts(tmp_path):
    from src.security_lifecycle_retirement import (
        TavilyRetirementBlocked,
        preflight_tavily_retirement,
    )

    path = tmp_path / "profile_state.db"
    _create_profile(path)
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO security_lifecycle_evidence "
        "(evidence_id,case_id,run_id,kind,source_url,title,publisher,domain,"
        "source_published_at,retrieved_at,adapter,excerpt,content_sha256,"
        "mime_type,document_status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "ev_tavily",
            "slc_retirement",
            None,
            "web_search_result",
            "https://example.com/source",
            "Source",
            "Publisher",
            "example.com",
            None,
            _AT,
            "tavily",
            "Stored excerpt that must block retirement migration.",
            "a" * 64,
            "text/plain",
            None,
            _AT,
        ),
    )
    connection.commit()
    connection.close()

    with pytest.raises(TavilyRetirementBlocked) as caught:
        preflight_tavily_retirement(profile_path=path)
    assert caught.value.code == "stored_tavily_rows_present"
    assert caught.value.run_count == 0
    assert caught.value.evidence_count == 1
