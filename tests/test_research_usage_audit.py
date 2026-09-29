"""Historical usage counts must not manufacture calls or successful data reads."""

import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("research_usage_audit", ROOT / "tests/support/research_usage.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def corpus(events):
    return {
        "research_threads": [{"id": "t", "created_at": "2026-01-01"}],
        "research_messages": [dict(id=1, thread_id="t", role="user", content="private question",
            created_at="2026-01-01", tool_calls_json=None, run_id=None, provider=None, model=None)],
        "research_runs": [dict(id="r", thread_id="t", status="succeeded", provider="openai",
            auth_mode="api_key", created_at="2026-01-01", question="private question")],
        "research_run_events": [dict(run_id="r", seq=i, type=kind, data_json=data, created_at="2026-01-01")
                                for i, (kind, data) in enumerate(events)],
    }


def summarize(events):
    return audit.summarize(corpus(events), {"by_message_id": {"1": "test"}}, ["get_data"])


def test_header_and_saved_message_are_not_additional_invocations():
    data = corpus([
        ("tool_end", {"tool": "tool_get_data"}),
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "summary": "private result", "is_error": False}),
    ])
    message = dict(data["research_messages"][0], id=2, role="assistant", provider="openai",
                   content="private answer", tool_calls_json=[{"name": "get_data", "input": {}, "result_preview": "private result"}])
    data["research_messages"].append(message)
    result = audit.summarize(data, {"by_message_id": {"1": "test"}}, ["get_data"])
    row = result["tools"][0]
    assert row["starts"] == row["reported_success"] == row["header_only_ends"] == row["message_records"] == 1
    assert row["channels"] == row["header_channels"] == {"openai_api_key": 1}
    assert row["message_channels"] == {"unobserved": 1}, "provider is not auth mode"
    assert "private" not in json.dumps(result)


def test_ambiguous_same_name_overlap_is_not_guessed():
    result = summarize([
        ("tool_start", {"tool": "get_data", "input": {"n": 1}}),
        ("tool_start", {"tool": "get_data", "input": {"n": 2}}),
        ("tool_end", {"tool": "get_data", "is_error": False}),
        ("tool_end", {"tool": "get_data", "is_error": True}),
    ])
    row = result["tools"][0]
    assert row["starts"] == row["unknown"] == row["ambiguous_starts"] == 2
    assert row["flagged_completion_success_percent"] is None


def test_unavailable_preview_is_not_success_and_missing_flag_is_unknown():
    result = summarize([
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "summary": '{"status":"unavailable"}', "is_error": False}),
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "summary": "no explicit outcome"}),
    ])
    row = result["tools"][0]
    assert row["reported_unavailable"] == row["unknown"] == 1
    assert row["reported_success"] == 0 and row["flagged_completion_success_percent"] is None


def test_repeated_complete_attempts_are_not_deduplicated_by_same_arguments():
    result = summarize([
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "is_error": True}),
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "is_error": False}),
    ])
    row = result["tools"][0]
    assert row["starts"] == 2 and row["flagged_completion_success_percent"] == 50


def test_orphan_and_incomplete_records_remain_visible():
    result = summarize([
        ("tool_end", {"tool": "get_data", "is_error": False}),
        ("tool_start", {"tool": "get_data", "input": {}}),
    ])
    row = result["tools"][0]
    assert row["starts"] == row["unknown"] == row["unpaired_ends"] == row["incomplete_starts"] == 1


def test_snapshot_labels_and_event_identities_are_checked():
    data = corpus([("tool_start", {"tool": "get_data", "input": {}})])
    with pytest.raises(ValueError, match="topic labels"):
        audit.summarize(data, {"by_message_id": {}}, [])
    data["research_run_events"].append(data["research_run_events"][0])
    with pytest.raises(ValueError, match="duplicate event"):
        audit.summarize(data, {"by_message_id": {"1": "test"}}, [])


def test_readonly_verification_does_not_create_or_modify_databases(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        audit.readonly_tables(missing)
    assert not missing.exists()
    path = tmp_path / "profile.db"
    data = corpus([])
    with sqlite3.connect(path) as conn:
        for table, columns in audit.COLUMNS.items():
            conn.execute("CREATE TABLE " + table + " (" + ",".join(columns) + ")")
            for row in data[table]:
                conn.execute("INSERT INTO " + table + " VALUES (" + ",".join("?" for _ in columns) + ")",
                             [row[key] for key in columns])
        conn.execute("CREATE TABLE private_credentials (secret TEXT)")
        conn.execute("INSERT INTO private_credentials VALUES ('must not be read')")
    before = path.read_bytes()
    assert audit.fingerprint(audit.readonly_tables(path)) == audit.fingerprint(data)
    assert path.read_bytes() == before


def test_summary_totals_match_a_synthetic_inventory():
    data = corpus([
        ("tool_start", {"tool": "get_data", "input": {}}),
        ("tool_end", {"tool": "get_data", "is_error": False}),
        ("tool_start", {"tool": "retired_tool", "input": {}}),
        ("tool_end", {"tool": "retired_tool", "is_error": True}),
    ])
    data["research_messages"].append(dict(data["research_messages"][0], id=2,
        role="assistant", content="synthetic answer", run_id="r",
        tool_calls_json=[{"name": "get_data", "input": {}, "result_preview": "synthetic result"}]))
    result = audit.summarize(data, {"by_message_id": {"1": "synthetic topic"}}, ["get_data", "unseen_tool"])
    assert {row["tool"] for row in result["tools"] if row["registered"]} == {"get_data", "unseen_tool"}
    assert sum(row["messages"] for row in result["topics"]) == result["counts"]["user_messages"] == 1
    assert sum(row["starts"] for row in result["tools"]) == result["event_types"]["tool_start"] == 2
    assert sum(row["message_records"] for row in result["tools"]) == 1
    assert result["unobserved_registered_tools"] == ["unseen_tool"]
    for row in result["tools"]:
        assert sum(row[key] for key in ("reported_success", "reported_error", "reported_unavailable", "reported_partial", "unknown")) == row["starts"]
