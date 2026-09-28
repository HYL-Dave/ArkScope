"""Durable body jobs use real private capture, tracking and collector stores."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from types import SimpleNamespace

import pytest

from src.sa.company_collector import CompanyCollector
from tests.test_sa_acquisition_authority import activate, call, FIREFOX, CHROME, UNCAPPED
from tests.test_sa_article_acquisition_scope import scope_case, context
from tests.test_sa_article_body_recovery import article, NARRATIVE


@pytest.fixture
def journal_case(scope_case, monkeypatch):
    from src.sa.article_body_recovery_jobs import BodyRecoveryJobs
    from src.sa.article_body_recovery import build_recovery_manifest
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
    capture, profile, conn = scope_case
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(capture))
    for i in range(8):
        article(conn, str(1000 + i), published="2020-01-01")
    conn.commit()
    now = [1790568000.0]
    collector = CompanyCollector(capture.with_name("sa_company_refresh.db"), clock=lambda: now[0])
    activate(collector, UNCAPPED)
    jobs = BodyRecoveryJobs(collector.path, sa_db=capture, profile_db=profile, clock=lambda: now[0])
    preview = build_recovery_manifest(capture, settings=ArticleAcquisitionSettings(), scope_context=context(scope_case))
    def control(operation, **kw):
        return jobs.handle({"protocol_version": 2, "operation": operation, "expected_generation": 1, **kw}, client=FIREFOX)
    def start(request_id="start", **kw):
        return control("start", request_id=request_id, manifest_id=preview["manifest_id"], trigger="manual", **kw)
    def count():
        with sqlite3.connect(collector.path) as db:
            return db.execute("SELECT count(*) FROM sa_body_recovery_jobs").fetchone()[0]
    def begin(job, aid="1000"):
        return call(collector, "begin_task", generation=1, request_id="task-" + aid,
            task_operation="alpha_picks_body_repair", mode="manual", trigger="continuation",
            intent_revision=job["revision"], build="body-v2-test", protocol_version=2,
            body_job_id=job["job_id"], body_job_revision=job["revision"], article_id=aid)
    return SimpleNamespace(jobs=jobs, collector=collector, now=now, conn=conn, capture=capture,
        control=control, start=start, preview=preview, begin=begin,
        job_count=count, navigation_count=lambda: call(collector, "status")["navigation_attempts"])


def test_start_retry_does_not_duplicate_job(journal_case):
    first = journal_case.start(request_id="same-start")
    assert first["status"] == "ok", first
    again = journal_case.start(request_id="same-start")
    assert first["job_id"] == again["job_id"]
    assert first["counts"]["selected"] == 8
    assert journal_case.job_count() == 1
    assert journal_case.navigation_count() == 0


def test_two_concurrent_starts_only_create_one_job(journal_case):
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(journal_case.start, ["one", "two"]))
    assert sum(r["status"] == "ok" for r in replies) == 1
    assert journal_case.job_count() == 1


def test_stale_preview_and_conflicting_retry_are_not_new_intent(journal_case):
    bad = journal_case.control("start", request_id="bad", manifest_id="0" * 64, trigger="manual")
    assert bad["error_code"] == "sa_body_preview_changed"
    first = journal_case.start()
    changed = journal_case.control("start", request_id="start", manifest_id="0" * 64, trigger="manual")
    assert changed["error_code"] == "sa_body_request_conflict"
    assert journal_case.control("state", job_id=first["job_id"])["counts"]["selected"] == 8


def test_native_continuation_is_bound_to_manual_job_and_target(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    assert permit["status"] == "ok", permit
    assert permit["active"]["body_recovery_job_id"] == job["job_id"]
    waiting = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])
    assert waiting["state"] == "running"
    assert waiting.get("target") is None
    assert journal_case.control("checkpoint", job_id=job["job_id"], revision=job["revision"],
        article_id="1000", task_id="0" * 32)["status"] == "error"


def test_save_before_checkpoint_recovers_from_retained_body_and_terminal_receipt(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    journal_case.conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1000'", (NARRATIVE,))
    journal_case.conn.commit()
    reply = call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
                 cleanup_confirmed=True, result={"status": "ok"})
    assert reply["acquisition"]["body_recovery_job_id"] == job["job_id"]
    # Native readback owns the result even if the worker disappears here.
    next_item = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])
    assert next_item["counts"]["saved"] == 1
    assert next_item["target"]["article_id"] == "1001"
    assert journal_case.control("items", job_id=job["job_id"])["items"][0]["state"] == "saved"


def test_cancel_before_navigation_fences_active_task_and_cannot_resurrect(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    cancelled = journal_case.control("cancel", job_id=job["job_id"], revision=job["revision"])
    assert cancelled["state"] == "cancelling"
    nav = call(journal_case.collector, "admit_navigation", token=permit["token"], generation=1,
               navigation_id="never", kind="create", destination_class="article")
    assert nav.get("allowed") is not True
    assert journal_case.navigation_count() == 0
    call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
         cleanup_confirmed=True, result={"status": "cancelled"})
    result = journal_case.control("next", job_id=job["job_id"], revision=cancelled["revision"])
    assert result["state"] == "cancelled"
    assert journal_case.start()["state"] == "cancelled"
    assert journal_case.control("resume", job_id=job["job_id"], revision=cancelled["revision"])["status"] == "error"


def test_cooldown_retains_item_until_native_deadline(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    call(journal_case.collector, "observe_restriction", token=permit["token"], generation=1, reason="rate_limited")
    call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
         cleanup_confirmed=True, result={"status": "error", "error_code": "rate_limited"})
    waiting = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])
    assert waiting["state"] == "waiting"
    assert waiting["counts"]["pending"] == 8
    assert waiting["next_eligible_at"]
    journal_case.now[0] += 6 * 3600
    ready = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])
    assert ready["target"]["article_id"] == "1000"


def test_wrong_owner_and_generation_cannot_mutate_job(journal_case):
    job = journal_case.start()
    assert journal_case.jobs.handle({"protocol_version": 2, "operation": "cancel",
        "job_id": job["job_id"], "revision": job["revision"], "expected_generation": 1}, client=CHROME)["status"] == "error"
    assert journal_case.control("cancel", job_id=job["job_id"], revision=job["revision"], expected_generation=2)["status"] == "error"
    assert journal_case.control("state", job_id=job["job_id"])["state"] == "pending"


def test_read_only_status_does_not_install_journal(journal_case):
    assert journal_case.jobs.public_status()["state"] == "not_started"
    with sqlite3.connect(journal_case.collector.path) as conn:
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'sa_body_recovery_%'").fetchall()


def test_pagination_is_byte_bounded_and_frozen_after_body_save(journal_case):
    from src.sa.article_body_recovery import build_recovery_manifest
    from src.sa.article_acquisition_settings import ArticleAcquisitionSettings
    from src.sa.article_acquisition_scope import read_article_scope_context
    journal_case.conn.execute("UPDATE sa_articles SET title=?", ("\u7814\u7a76" * 15000,))
    journal_case.conn.commit()
    manifest = build_recovery_manifest(journal_case.capture, settings=ArticleAcquisitionSettings(),
        scope_context=read_article_scope_context(sa_db=journal_case.capture, profile_db=journal_case.jobs.profile_db))
    job = journal_case.control("start", request_id="paged", manifest_id=manifest["manifest_id"], trigger="manual")
    journal_case.conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1000'", (NARRATIVE,))
    journal_case.conn.commit()
    cursor, seen = None, []
    while True:
        reply = journal_case.control("items", job_id=job["job_id"], cursor=cursor)
        assert len(json.dumps(reply).encode("utf8")) <= 65536
        seen.extend(r["article_id"] for r in reply["items"])
        cursor = reply["next_cursor"]
        if cursor is None:
            break
    assert seen == [str(1000 + i) for i in range(8)]
    assert journal_case.control("items", job_id=job["job_id"], cursor="garbage")["status"] == "error"


def test_unknown_schema_is_not_reinstalled(journal_case):
    with sqlite3.connect(journal_case.collector.path) as db:
        db.execute("CREATE TABLE sa_body_recovery_items (wrong TEXT)")
    assert journal_case.start()["status"] == "error"
    with sqlite3.connect(journal_case.collector.path) as db:
        assert [r[1] for r in db.execute("PRAGMA table_info(sa_body_recovery_items)")] == ["wrong"]


def test_native_v2_save_requires_admitted_frozen_target(journal_case):
    from src.sa_native_host import handle_message
    job = journal_case.start()
    permit = journal_case.begin(job)
    message = dict(action="save_article_body_recovery", protocol_version=2,
        client=FIREFOX, body_job_id=job["job_id"], task_id=permit["task_id"],
        token=permit["token"], generation=1, article_id="1000",
        expected_body_sha256=journal_case.preview["targets"][0]["body_sha256"], body_markdown=NARRATIVE)
    assert handle_message({**message, "task_id": "0" * 32})["status"] == "error"
    assert handle_message({**message, "article_id": "1001"})["status"] == "error"
    assert handle_message(message)["body_saved"] is True


def test_body_protocol_mismatch_never_saves_or_starts(journal_case):
    from src.sa_native_host import handle_message
    assert handle_message({"action": "preview_article_body_recovery"})["error_code"] == "sa_body_upgrade_required"
    assert handle_message({"action": "save_article_body_recovery", "article_id": "1000",
        "body_markdown": NARRATIVE})["status"] == "error"
    assert journal_case.jobs.handle({"operation": "start"}, client=FIREFOX)["status"] == "error"
    assert journal_case.navigation_count() == 0


def test_public_body_receipt_projects_job_identity_without_secrets(journal_case):
    from src.sa.acquisition_receipt import project_acquisition
    job = journal_case.start()
    permit = journal_case.begin(job)
    receipt = call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
        cleanup_confirmed=True, result={"status": "error"})["acquisition"]
    assert project_acquisition(receipt) == receipt
    assert "token" not in receipt
    assert receipt["body_recovery_job_id"] == job["job_id"]


def test_selected_replacement_owner_can_cancel_but_not_resume_old_intent(journal_case):
    job = journal_case.start()
    call(journal_case.collector, "select", CHROME, expected_generation=1, confirm_schedules=True)
    base = {"protocol_version": 2, "expected_generation": 2, "job_id": job["job_id"], "revision": 1}
    assert journal_case.jobs.handle({**base, "operation": "next"}, client=CHROME)["status"] == "error"
    reply = journal_case.jobs.handle({**base, "operation": "cancel"}, client=CHROME)
    assert reply["state"] == "cancelled"


def test_body_receipt_cannot_claim_success_without_stored_body(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    result = call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
                  cleanup_confirmed=True, result={"status": "ok"})
    assert result["status"] == "error"
    assert result["error_code"] == "sa_company_receipt_unverified"


def test_failed_page_is_visible_and_does_not_block_next_item(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
         cleanup_confirmed=True, result={"status": "error", "error_code": "parser_empty"})
    result = journal_case.control("next", job_id=job["job_id"], revision=1)
    assert result["counts"]["failed"] == 1
    assert result["target"]["article_id"] == "1001"


def test_login_pause_requires_explicit_handling_and_job_resume(journal_case):
    job = journal_case.start()
    permit = journal_case.begin(job)
    call(journal_case.collector, "observe_restriction", token=permit["token"], generation=1, reason="login_required")
    call(journal_case.collector, "finish_task", token=permit["token"], generation=1,
         cleanup_confirmed=True, result={"status": "error", "error_code": "login_required"})
    paused = journal_case.control("next", job_id=job["job_id"], revision=1)
    assert paused["state"] == "paused"
    journal_case.now[0] += 86400
    assert journal_case.control("next", job_id=job["job_id"], revision=1)["state"] == "paused"
    assert journal_case.control("resume", job_id=job["job_id"], revision=1, confirm_handled=True)["status"] == "error"
    call(journal_case.collector, "resume", expected_generation=1, confirm_handled=True)
    assert journal_case.control("next", job_id=job["job_id"], revision=1)["state"] == "paused"
    assert journal_case.control("resume", job_id=job["job_id"], revision=1, confirm_handled=True)["state"] == "pending"
    assert journal_case.control("next", job_id=job["job_id"], revision=1)["target"]["article_id"] == "1000"


def test_count_limit_is_selection_not_hidden_native_batch_size(journal_case):
    from src.profile_state import ProfileStateStore
    from src.sa.article_acquisition_settings import ARTICLE_SETTINGS_KEY
    from src.sa_native_host import handle_message
    store = ProfileStateStore(journal_case.jobs.profile_db)
    store.set_setting(ARTICLE_SETTINGS_KEY, '{"max_articles_per_job":3}')
    preview = handle_message({"action": "preview_article_body_recovery", "protocol_version": 2})
    assert preview["counts"]["targets"] == 8
    job = journal_case.control("start", request_id="limited", manifest_id=preview["manifest_id"], trigger="manual")
    assert job["counts"]["selected"] == 3
    store.set_setting(ARTICLE_SETTINGS_KEY, '{"max_articles_per_job":0}')
    assert journal_case.control("state", job_id=job["job_id"])["counts"]["selected"] == 3


def test_lost_start_response_retry_preserves_job_after_inventory_changes(journal_case):
    job = journal_case.start()
    journal_case.conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1000'", (NARRATIVE,))
    journal_case.conn.commit()
    assert journal_case.start()["job_id"] == job["job_id"]
    assert journal_case.job_count() == 1


def test_single_oversized_target_is_rejected_before_navigation(journal_case):
    job = journal_case.start()
    with sqlite3.connect(journal_case.collector.path) as db:
        payload = json.loads(db.execute("SELECT payload FROM sa_body_recovery_items WHERE article_id='1000'").fetchone()[0])
        payload["target"]["url"] += "x" * 70000
        db.execute("UPDATE sa_body_recovery_items SET payload=? WHERE article_id='1000'", (json.dumps(payload),))
    result = journal_case.control("next", job_id=job["job_id"], revision=1)
    assert result.get("error_code") == "sa_body_target_too_large"
    assert len(json.dumps(result).encode("utf8")) <= 65536
    assert journal_case.navigation_count() == 0


def test_paging_cursor_is_revision_and_job_bound(journal_case):
    job = journal_case.start()
    with sqlite3.connect(journal_case.collector.path) as db:
        rows = db.execute("SELECT article_id,payload FROM sa_body_recovery_items").fetchall()
        for aid, raw in rows:
            item = json.loads(raw)
            item["target"]["url"] += "x" * 10000
            db.execute("UPDATE sa_body_recovery_items SET payload=? WHERE article_id=?", (json.dumps(item), aid))
    first = journal_case.control("items", job_id=job["job_id"])
    assert first["next_cursor"]
    second = journal_case.control("items", job_id=job["job_id"], cursor=first["next_cursor"])
    assert len(first["items"]) + len(second["items"]) == 8
    journal_case.control("cancel", job_id=job["job_id"], revision=1)
    assert journal_case.control("items", job_id=job["job_id"], cursor=first["next_cursor"])["error_code"] == "sa_body_cursor_invalid"
    other = journal_case.start(request_id="other")
    assert journal_case.control("items", job_id=other["job_id"], cursor=first["next_cursor"])["error_code"] == "sa_body_cursor_invalid"
