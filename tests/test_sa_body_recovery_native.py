"""Exercise the real native entry, including read-only preview and write bounds."""

import hashlib
import json
from pathlib import Path
import selectors
import sqlite3
import struct
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from src import sa_capture_store as store
from src.sa_native_host import handle_message as native_handle_message
from src.tools.backends.sa_capture_backend import SACaptureBackend


BAD = "Analyst's Disclosure: no positions.\n\nSeeking Alpha's Disclosure: investing involves risk."
GOOD = "Demand and free cash flow improved following the company's cost reduction program."
handle_message = native_handle_message


@pytest.fixture(autouse=True)
def admitted_messages(monkeypatch):
    auth = {}
    monkeypatch.setattr(sys.modules[__name__], "handle_message", lambda message: native_handle_message(
        {"protocol_version": 2, **auth, **message}))
    return auth


@pytest.fixture
def db(tmp_path, monkeypatch, admitted_messages):
    from src.profile_state import ProfileStateStore
    from src.sa_tracking_memberships import SaTrackingMembershipStore
    from src.sa.article_acquisition_settings import ARTICLE_SETTINGS_KEY
    from src.sa.company_collector import CompanyCollector
    from tests.test_sa_acquisition_authority import activate, call, FIREFOX, UNCAPPED

    path = tmp_path / "sa.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(path))
    profile = tmp_path / "profile.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    ProfileStateStore(profile).set_setting(ARTICLE_SETTINGS_KEY, '{"body_lookback_days":365}')
    with sqlite3.connect(profile) as conn:
        SaTrackingMembershipStore.install(conn)
    backend = SACaptureBackend(sa_db=str(path), market_db=str(tmp_path / "market.db"))
    today = datetime.now(timezone.utc).date().isoformat()
    backend.upsert_sa_articles_meta([{
        "article_id": "123", "title": "Portfolio update", "published_date": today,
        "url": "https://seekingalpha.com/alpha-picks/articles/123-update",
    }, {
        "article_id": "456", "title": "Closed pick update", "published_date": "2020-01-01",
        "url": "https://seekingalpha.com/alpha-picks/articles/456-update",
    }])
    with store.connect(str(path)) as conn:
        conn.execute("UPDATE sa_articles SET body_markdown=?", (BAD,))
    collector = CompanyCollector(path.with_name("sa_company_refresh.db"))
    activate(collector, UNCAPPED)
    preview = handle_message({"action": "preview_article_body_recovery"})
    job = handle_message({"action": "article_body_recovery_control", "operation": "start", "client": FIREFOX,
                          "request_id": "native-test", "manifest_id": preview["manifest_id"],
                          "expected_generation": 1, "trigger": "manual"})
    permit = call(collector, "begin_task", generation=1, request_id="body-task", task_operation="alpha_picks_body_repair",
                  mode="manual", trigger="manual", intent_revision=job["revision"], build="test", protocol_version=2,
                  body_job_id=job["job_id"], body_job_revision=job["revision"], article_id="123")
    assert permit["status"] == "ok", permit
    admitted_messages.update(client=FIREFOX, token=permit["token"], generation=1, task_id=permit["task_id"], body_job_id=job["job_id"])
    return path


def test_native_preview_is_readonly_and_has_no_network_or_dal_initialization(db, monkeypatch):
    import src.tools.data_access as data_access
    monkeypatch.setattr(data_access, "DataAccessLayer", lambda: pytest.fail("preview instantiated DAL"))
    before = db.read_bytes()
    result = handle_message({"action": "preview_article_body_recovery"})
    assert result["status"] == "ok"
    assert [target["article_id"] for target in result["targets"]] == ["123"]
    assert db.read_bytes() == before


def test_native_preview_missing_store_does_not_create_it(tmp_path, monkeypatch):
    path = tmp_path / "missing" / "sa.db"
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(path))
    result = handle_message({"action": "preview_article_body_recovery"})
    assert result["status"] == "unavailable"
    assert not path.parent.exists()


def test_preview_bounds_native_payload_but_preserves_total_count(db):
    with store.connect(str(db)) as conn:
        date = datetime.now(timezone.utc).date().isoformat()
        conn.executemany("INSERT INTO sa_articles(article_id,url,title,published_date) VALUES (?,?,?,?)", [
            (str(i), f"https://seekingalpha.com/alpha-picks/articles/{i}-update", "Portfolio update", date)
            for i in range(1000, 1020)
        ])
    result = handle_message({"action": "preview_article_body_recovery"})
    assert len(result["targets"]) == 21
    assert len(json.dumps(result).encode("utf8")) <= 65536
    assert result["counts"]["targets"] == 21
    assert "held" not in result
    assert "excluded" not in result


def test_native_repair_revalidates_scope_and_then_skips_already_saved_body(db):
    digest = hashlib.sha256(BAD.encode()).hexdigest()
    base = {"article_id": "123", "body_sha256": digest}
    checked = handle_message({"action": "check_article_body_recovery_target", **base})
    assert checked["status"] == "ok"
    result = handle_message({"action": "save_article_body_recovery", "article_id": "123",
                             "expected_body_sha256": digest, "body_markdown": GOOD})
    assert result["status"] == "ok"
    assert result["body_saved"] is True
    assert handle_message({"action": "check_article_body_recovery_target", **base})["reason"] == "already_present"
    assert handle_message({"action": "preview_article_body_recovery"})["targets"] == []


@pytest.mark.parametrize("article_id,digest,reason", [
    ("456", hashlib.sha256(BAD.encode()).hexdigest(), "sa_body_target_invalid"),
    ("123", "0" * 64, "source_changed"),
])
def test_native_save_cannot_expand_frozen_scope_or_overwrite_changed_input(db, article_id, digest, reason):
    before = db.read_bytes()
    result = handle_message({"action": "save_article_body_recovery", "article_id": article_id,
                             "expected_body_sha256": digest, "body_markdown": GOOD})
    assert result["status"] == ("error" if article_id == "456" else "skipped")
    assert result.get("reason", result.get("error_code")) == reason
    assert not result.get("body_saved")
    assert db.read_bytes() == before


def test_native_save_rejects_bad_capture_and_preserves_raw_evidence(db):
    result = handle_message({"action": "save_article_body_recovery", "article_id": "123",
                             "expected_body_sha256": hashlib.sha256(BAD.encode()).hexdigest(),
                             "body_markdown": BAD})
    assert result["status"] == "error"
    assert result["error_code"] == "sa_article_body_disclosure_only"
    with sqlite3.connect(str(db)) as conn:
        assert conn.execute("SELECT body_markdown FROM sa_articles WHERE article_id='123'").fetchone()[0] == BAD


def test_native_repair_preserves_body_bound_reference_counts(db):
    from src.sa.article_reader import read_article

    capture = {"schema_version": 1, "extractor_version": 2, "links": {"observed": 0, "retained": 0},
               "images": {"observed": 1, "retained": 1}, "unsupported_embeds": 0}
    body = GOOD + "\n\n![Outlook](<https://images.example/chart.png>)"
    message = {"action": "save_article_body_recovery", "article_id": "123",
               "expected_body_sha256": hashlib.sha256(BAD.encode()).hexdigest(), "body_markdown": body}
    rejected = handle_message({**message, "body_capture": {**capture, "extractor_version": 999}})
    assert rejected["status"] == "error" and rejected["body_saved"] is False
    with sqlite3.connect(str(db)) as conn:
        assert conn.execute("SELECT body_markdown FROM sa_articles WHERE article_id='123'").fetchone()[0] == BAD
    result = handle_message({**message, "body_capture": capture})
    assert result["body_saved"] is True
    assert result["body_references"]["images"] == {"observed": 1, "retained": 1}
    assert read_article(db, "123")["coverage"]["references"] == result["body_references"]


def test_native_host_handles_a_port_until_eof(monkeypatch):
    from src import sa_native_host as host

    inputs = iter([{"action": "ping"}, {"action": "get_extension_action_limits"}, None])
    seen, replies, initialized = [], [], []
    monkeypatch.setattr(host, "_init_script_runtime", lambda: initialized.append(True))
    monkeypatch.setattr(host, "read_message", lambda: next(inputs))
    monkeypatch.setattr(host, "handle_message", lambda message: seen.append(message) or {"status": "ok"})
    monkeypatch.setattr(host, "write_message", replies.append)
    host.main()
    assert initialized == [True]
    assert seen == [{"action": "ping"}, {"action": "get_extension_action_limits"}]
    assert replies == [{"status": "ok"}, {"status": "ok"}]


def test_native_host_framed_port_stays_alive_and_exits_on_disconnect(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = f"""
import sys
sys.path.insert(0, {str(root)!r})
from src import sa_native_host as host
host.PROJECT_ROOT = {str(tmp_path)!r}
host._resolve_sidecar_target = lambda: ('http://127.0.0.1:1', '', 'offline_test')
host.main()
"""
    process = subprocess.Popen([sys.executable, "-B", "-c", code], cwd=tmp_path,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            for _ in range(2):
                message = json.dumps({"action": "ping"}).encode()
                process.stdin.write(struct.pack("=I", len(message)) + message)
                process.stdin.flush()
                assert selector.select(10), "native port did not reply"
                header = process.stdout.read(4)
                assert len(header) == 4, "native host closed a persistent channel"
                reply = json.loads(process.stdout.read(struct.unpack("=I", header)[0]))
                assert reply["status"] == "ok"
                assert reply["project_root"] == str(tmp_path)
                assert process.poll() is None
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        assert not list(tmp_path.rglob("*.db")), "holding a native port must not initialize data stores"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close()
