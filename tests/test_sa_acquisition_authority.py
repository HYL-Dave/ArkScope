"""Durable fencing, capacity and restrictions through the real authority."""

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from uuid import uuid4

import pytest

from src.sa.company_collector import CompanyCollector


FIREFOX = {"client_id": "f" * 32, "browser": "firefox"}
CHROME = {"client_id": "c" * 32, "browser": "chrome"}
POLICY = dict(hour_limit=4, day_limit=8, hour_reserve=2, day_reserve=2)
UNCAPPED = dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0)


def call(obj, operation, client=FIREFOX, **kw):
    return obj.handle(dict(operation=operation, client=client, **kw))


def activate(obj, policy=POLICY):
    configured = call(obj, "configure", policy=policy, financial_gap_seconds=15,
                      confirm_activation=True, expected_generation=0)
    assert configured["status"] == "ok", configured
    selected = call(obj, "select", expected_generation=0, confirm_schedules=True)
    assert selected["generation"] == 1
    return selected


def begin(obj, client=FIREFOX, generation=1, **kw):
    return call(obj, "begin_task", client, generation=generation, request_id=uuid4().hex,
                task_operation="market_news_sync", mode="quick", trigger="manual",
                intent_revision=0, build="test", protocol_version=2, **kw)


def navigation(obj, permit, client=FIREFOX, **kw):
    return call(obj, "admit_navigation", client, token=permit["token"], generation=permit["generation"],
                navigation_id=kw.pop("navigation_id", uuid4().hex), kind="create", destination_class="news", **kw)


@pytest.fixture
def authority(tmp_path):
    clock = [100000.]
    obj = CompanyCollector(tmp_path / "control.db", clock=lambda: clock[0])
    return obj, clock


def test_initialization_is_explicit_and_readers_do_not_create_files(authority):
    obj, _ = authority
    assert call(obj, "status")["owner"] is None
    assert not obj.path.exists()
    assert begin(obj)["status"] == "error"
    assert not obj.path.exists()
    state = activate(obj)
    assert state["prior_traffic_coverage"] == "unknown"
    assert state["managed_since"]
    assert obj.path.with_suffix(".db.identity").read_text().strip() == state["ledger_id"]


@pytest.mark.parametrize("policy", [POLICY, UNCAPPED])
def test_only_one_of_eight_connections_can_reserve(authority, policy):
    obj, clock = authority
    activate(obj, policy)
    with ThreadPoolExecutor(8) as workers:
        results = list(workers.map(lambda _: begin(CompanyCollector(obj.path, clock=lambda: clock[0])), range(8)))
    assert sum(r["status"] == "ok" for r in results) == 1
    assert {r.get("error_code") for r in results if r["status"] != "ok"} == {"sa_company_collector_busy"}


def test_lost_navigation_reply_is_not_a_second_executable_permit(authority):
    obj, _ = authority
    activate(obj)
    permit = begin(obj)
    first = navigation(obj, permit, navigation_id="one")
    replay = navigation(obj, permit, navigation_id="one")
    assert first["allowed"] is True and first["replayed"] is False
    assert replay["allowed"] is False and replay["replayed"] is True
    assert first["attempt_id"] == replay["attempt_id"]
    assert call(obj, "status")["navigation_attempts"] == 1


def test_policy_and_browser_switch_do_not_reset_navigation_budget(authority):
    obj, _ = authority
    activate(obj)
    permit = begin(obj)
    for _ in range(4):
        assert navigation(obj, permit)["allowed"] is True
    assert navigation(obj, permit)["reason"] == "capacity_exhausted"
    call(obj, "finish_task", token=permit["token"], generation=1, cleanup_confirmed=True, result={"status": "ok"})
    selected = call(obj, "select", CHROME, expected_generation=1, confirm_schedules=True)
    assert selected["generation"] == 2
    assert begin(obj, generation=1)["error_code"] == "sa_acquisition_generation_stale"
    assert begin(obj, CHROME, generation=2)["reason"] == "capacity_exhausted"
    other_chrome = {**CHROME, "client_id": "d" * 32}
    assert begin(obj, other_chrome, generation=2)["error_code"] == "sa_company_collector_other_browser"


@pytest.mark.parametrize("policy", [POLICY, UNCAPPED])
def test_login_pause_is_durable_before_cleanup_and_not_cleared_by_selection(authority, policy):
    obj, _ = authority
    activate(obj, policy)
    permit = begin(obj)
    paused = call(obj, "observe_restriction", token=permit["token"], generation=1, reason="login_required")
    assert paused["paused_reason"] == "login_required" and paused["active"] is not None
    assert navigation(obj, permit)["reason"] == "site_paused"
    call(obj, "recover", expected_generation=1, confirm_stopped=True)
    call(obj, "select", CHROME, expected_generation=1, confirm_schedules=True)
    assert begin(obj, CHROME, generation=2)["reason"] == "site_paused"
    assert call(obj, "resume", CHROME, expected_generation=2)["status"] == "error"
    assert call(obj, "resume", CHROME, expected_generation=2, confirm_handled=True)["paused_reason"] is None


@pytest.mark.parametrize("policy", [POLICY, UNCAPPED])
def test_clock_regression_refuses_navigation(authority, policy):
    obj, clock = authority
    activate(obj, policy)
    permit = begin(obj)
    clock[0] -= 1
    assert navigation(obj, permit)["error_code"] == "sa_company_clock_regressed"


def test_uncapped_attempts_survive_reopen_and_count_if_limits_are_enabled(authority):
    obj, clock = authority
    activate(obj, UNCAPPED)
    permit = begin(obj)
    for _ in range(12):
        assert navigation(obj, permit)["allowed"] is True
    reopened = CompanyCollector(obj.path, clock=lambda: clock[0])
    assert call(reopened, "status")["policy"] == UNCAPPED
    assert call(reopened, "status")["navigation_attempts"] == 12
    assert begin(reopened, CHROME)["status"] == "error"
    assert call(reopened, "configure", policy=POLICY, financial_gap_seconds=15,
                expected_generation=1, confirm_activation=True)["status"] == "ok"
    assert navigation(reopened, permit)["reason"] == "capacity_exhausted"
    assert call(reopened, "status")["navigation_attempts"] == 12


@pytest.mark.parametrize("damage", ["database", "marker", "marker_mismatch", "state", "attempts"])
def test_missing_or_corrupt_authority_never_reinitializes(authority, damage):
    obj, _ = authority
    activate(obj)
    permit = begin(obj)
    navigation(obj, permit)
    if damage == "database":
        obj.path.unlink()
    elif damage == "marker":
        obj.path.with_suffix(".db.identity").unlink()
    elif damage == "marker_mismatch":
        obj.path.with_suffix(".db.identity").write_text("0" * 32)
    else:
        with sqlite3.connect(obj.path) as conn:
            conn.execute("DELETE FROM " + ("company_collector" if damage == "state" else "acquisition_navigations"))
    assert call(obj, "status")["status"] == "error"
    assert call(obj, "configure", policy=POLICY, financial_gap_seconds=15,
                confirm_activation=True, expected_generation=1)["status"] == "error"


def test_legacy_action_is_not_an_acquisition_bypass(authority, monkeypatch):
    from src.sa_native_host import handle_message
    monkeypatch.setattr("src.sa.company_collector.CompanyCollector", lambda: authority[0])
    assert handle_message({"action": "company_refresh_control", "operation": "begin", "client": FIREFOX})["status"] == "error"


def test_lowering_policy_during_a_task_preserves_spent_capacity(authority):
    obj, _ = authority
    activate(obj)
    permit = begin(obj)
    navigation(obj, permit)
    navigation(obj, permit)
    smaller = dict(hour_limit=2, day_limit=3, hour_reserve=0, day_reserve=0)
    assert call(obj, "configure", policy=smaller, financial_gap_seconds=15,
                expected_generation=1, confirm_activation=True)["status"] == "ok"
    assert navigation(obj, permit)["reason"] == "capacity_exhausted"
    assert call(obj, "status")["navigation_attempts"] == 2


def test_paywall_pauses_only_the_affected_capability(authority):
    obj, _ = authority
    activate(obj)
    permit = begin(obj)
    call(obj, "observe_restriction", token=permit["token"], generation=1, reason="access_restricted")
    call(obj, "finish_task", token=permit["token"], generation=1, cleanup_confirmed=True, result={"status": "error"})
    assert begin(obj)["reason"] == "site_paused"
    assert call(obj, "begin_task", generation=1, request_id=uuid4().hex,
                task_operation="alpha_picks_sync", mode="quick", trigger="manual",
                intent_revision=0, build="test", protocol_version=2)["status"] == "ok"


@pytest.mark.parametrize("client", [FIREFOX, CHROME])
def test_legacy_upgrade_requires_stopped_ack_and_makes_one_backup(tmp_path, client):
    clock = [100000.]
    obj = CompanyCollector(tmp_path / "legacy.db", clock=lambda: clock[0])
    old = dict(owner=FIREFOX, active=None, paused_reason="login_required", rate_limit_until=None,
               rate_limit_failures=0, next_navigation_at=None, last_seen=99999., failures={})
    with sqlite3.connect(obj.path) as conn:
        conn.execute("CREATE TABLE company_collector (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("CREATE TABLE company_collector_actions (at TEXT, operation TEXT, client_id TEXT, previous_owner TEXT)")
        conn.execute("INSERT INTO company_collector VALUES (1, ?)", (json.dumps(old),))
        conn.execute("PRAGMA user_version=1")
    assert call(obj, "status")["error_code"] == "sa_acquisition_upgrade_required"
    args = dict(policy=POLICY, financial_gap_seconds=60, confirm_activation=True, expected_generation=0)
    assert call(obj, "configure", **args)["error_code"] == "sa_acquisition_upgrade_required"
    upgraded = call(obj, "configure", client, upgrade=True, confirm_stopped=True, **args)
    assert upgraded["status"] == "ok", upgraded
    assert upgraded["paused_reason"] == "login_required"
    assert upgraded["owner"] == FIREFOX
    selected = call(obj, "select", client, expected_generation=0, confirm_schedules=True)
    assert selected["is_owner"] is True and selected["generation"] == 1
    assert selected["paused_reason"] == "login_required"
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as conn:
        assert json.loads(conn.execute("SELECT payload FROM company_collector").fetchone()[0]) == old
    call(obj, "configure", client, **{**args, "expected_generation": 1})
    assert len(list(tmp_path.glob("*.bak"))) == 1


@pytest.mark.parametrize("invalid", ["generation", "clock"])
def test_refused_legacy_upgrade_does_not_leave_a_poisoned_marker(tmp_path, invalid):
    obj = CompanyCollector(tmp_path / "legacy.db", clock=lambda: 100000.)
    old = dict(owner=FIREFOX, active=None, paused_reason=None, rate_limit_until=None,
               rate_limit_failures=0, next_navigation_at=None, last_seen=99999., failures={})
    if invalid == "clock":
        old["last_seen"] = 100001.
    with sqlite3.connect(obj.path) as conn:
        conn.execute("CREATE TABLE company_collector (id INTEGER PRIMARY KEY, payload TEXT)")
        conn.execute("CREATE TABLE company_collector_actions (at TEXT, operation TEXT, client_id TEXT, previous_owner TEXT)")
        conn.execute("INSERT INTO company_collector VALUES (1, ?)", (json.dumps(old),))
        conn.execute("PRAGMA user_version=1")
    result = call(obj, "configure", policy=POLICY, financial_gap_seconds=60, confirm_activation=True,
                  expected_generation=1 if invalid == "generation" else 0, upgrade=True, confirm_stopped=True)
    assert result["status"] == "error"
    assert not obj.marker.exists()
    assert not list(tmp_path.glob("*.bak"))
    assert call(obj, "status")["error_code"] == "sa_acquisition_upgrade_required"


def test_replaying_begin_cannot_reenter_completed_work(authority):
    obj, _ = authority
    activate(obj)
    args = dict(generation=1, request_id="request-one", task_operation="market_news_sync", mode="quick",
                trigger="manual", intent_revision=0, build="test", protocol_version=2)
    first = call(obj, "begin_task", **args)
    assert call(obj, "begin_task", **args)["status"] == "uncertain"
    assert call(obj, "begin_task", **{**args, "mode": "full"})["error_code"] == "sa_acquisition_request_conflict"
    call(obj, "finish_task", token=first["token"], generation=1, cleanup_confirmed=True, result={"status": "ok"})
    assert call(obj, "begin_task", **args)["status"] == "completed"
    assert call(obj, "status")["active"] is None
