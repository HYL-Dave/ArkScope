"""Shared local authority for browser-driven financial acquisition."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import importlib

import pytest


NOW = datetime(2026, 9, 23, tzinfo=timezone.utc).timestamp()
FIREFOX = {"client_id": "f" * 32, "browser": "firefox"}
CHROME = {"client_id": "c" * 32, "browser": "chrome"}
SCOPE = {"ticker": "AMD", "statement": "income_statement", "view": "annual"}


def module():
    return importlib.import_module("src.sa.company_collector")


@pytest.fixture
def control(tmp_path):
    clock = [NOW]
    obj = module().CompanyCollector(tmp_path / "control.db", clock=lambda: clock[0])
    return obj, clock


def call(obj, operation, client=FIREFOX, **kwargs):
    return obj.handle({"operation": operation, "client": client, **kwargs})


def begin(obj, client=FIREFOX, **kwargs):
    return call(obj, "begin", client, scope=SCOPE, interval_days=7, force=False, **kwargs)


def test_status_and_watchlist_on_missing_databases_never_install_anything(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "sa.db"))
    obj = module().CompanyCollector(tmp_path / "nested" / "control.db")
    assert call(obj, "status")["owner"] is None
    result = module().watchlist_targets()
    assert result["error_code"] == "active_universe_unavailable"
    assert list(tmp_path.iterdir()) == []


def test_watchlist_preserves_complete_membership_and_exposes_unsupported(monkeypatch):
    from src.active_universe import ActiveUniverseSnapshot, SourceStatus

    tickers = tuple(f"T{i}" for i in range(183)) + ("BRK B",)
    snapshot = ActiveUniverseSnapshot(tickers, {s: ("manual_lists",) for s in tickers},
                                      {"manual_lists": SourceStatus(True)}, (), "2026-09-23T00:00:00Z")
    monkeypatch.setattr("src.active_universe.build_active_universe_snapshot", lambda: snapshot)
    result = module().watchlist_targets()
    assert result["status"] == "ok"
    assert result["total_count"] == 184
    assert len(result["tickers"]) == 183
    assert result["unsupported"] == [{"ticker": "BRK B", "reason": "sa_company_symbol_unmapped"}]
    assert result["sources_by_ticker"] == {s: ["manual_lists"] for s in tickers}
    assert result["source_status"]["manual_lists"] == asdict(SourceStatus(True))


def test_unselected_or_other_browser_cannot_acquire(control):
    obj, _ = control
    assert begin(obj)["error_code"] == "sa_company_collector_unselected"
    assert call(obj, "select")["is_owner"] is True
    assert call(obj, "status", CHROME)["is_owner"] is False
    assert begin(obj, CHROME)["error_code"] == "sa_company_collector_other_browser"
    assert begin(obj)["status"] == "ok"


def test_single_reservation_wins_across_independent_native_instances(control):
    obj, _ = control
    call(obj, "select")
    with ThreadPoolExecutor(8) as workers:
        results = list(workers.map(lambda _: begin(module().CompanyCollector(obj.path, clock=lambda: NOW)), range(8)))
    assert sum(r["status"] == "ok" for r in results) == 1
    assert {r.get("error_code") for r in results if r["status"] != "ok"} == {"sa_company_collector_busy"}


def test_owner_switch_does_not_expire_or_steal_active_reservation(control):
    obj, clock = control
    call(obj, "select")
    permit = begin(obj)
    clock[0] += 86400 * 100
    assert call(obj, "select", CHROME)["error_code"] == "sa_company_collector_busy"
    assert call(obj, "recover", CHROME)["error_code"] == "sa_company_recovery_confirmation_required"
    assert call(obj, "recover", CHROME, confirm_stopped=True)["active"] is None
    assert call(obj, "select", CHROME)["is_owner"] is True
    assert call(obj, "finish", token=permit["token"], result={"status": "cancelled"})["error_code"] == "sa_company_reservation_invalid"


def test_failure_is_durable_before_cleanup_and_transfer_cannot_bypass_cooldown(control):
    obj, clock = control
    call(obj, "select")
    permit = begin(obj)
    error = {"status": "error", "error_code": "sa_company_rate_limited"}
    result = call(obj, "report_failure", token=permit["token"], result=error)
    assert result["rate_limited"] is True
    assert result["active"] is not None
    # An explicit recovery does not forgive the rate limit or increment it twice.
    call(obj, "recover", confirm_stopped=True)
    call(obj, "select", CHROME)
    blocked = call(obj, "begin", CHROME, scope=SCOPE, interval_days=7, force=True)
    assert blocked["error_code"] == "sa_company_rate_limited"
    assert call(obj, "status")["rate_limit_until"] == result["rate_limit_until"]
    clock[0] += 6 * 3600 + 1
    assert begin(obj, CHROME)["status"] == "ok"


def test_challenge_pause_survives_recovery_and_needs_owner_resume(control):
    obj, _ = control
    call(obj, "select")
    permit = begin(obj)
    error = {"status": "error", "error_code": "sa_company_human_verification_required"}
    call(obj, "finish", token=permit["token"], result=error)
    call(obj, "select", CHROME)
    assert begin(obj, CHROME)["error_code"] == "sa_company_human_verification_required"
    assert call(obj, "resume")["error_code"] == "sa_company_collector_other_browser"
    assert call(obj, "resume", CHROME)["paused_reason"] is None


def test_unpersisted_success_is_not_a_freshness_checkpoint(control):
    obj, _ = control
    call(obj, "select")
    permit = begin(obj)
    result = call(obj, "finish", token=permit["token"], result={"status": "ok", "observation_id": "a" * 64})
    assert result["error_code"] == "sa_company_receipt_unverified"
    assert call(obj, "status")["active"] is not None


def test_saved_observation_is_reused_without_advancing_capture_time(control, monkeypatch):
    obj, clock = control
    observed = {"observation_id": "a" * 64, "last_captured_at": "2026-09-22T00:00:00+00:00"}
    monkeypatch.setattr("src.sa.company_store.read_capture", lambda *a, **k: observed)
    call(obj, "select")
    first = begin(obj)
    assert first["status"] == "reused"
    assert first["last_success_at"] == observed["last_captured_at"]
    clock[0] += 86400
    call(obj, "select", CHROME)
    second = begin(obj, CHROME)
    assert second["status"] == "reused"
    assert second["last_success_at"] == first["last_success_at"]
    assert call(obj, "status")["active"] is None


def test_corrupt_control_database_fails_closed(control):
    obj, _ = control
    obj.path.write_bytes(b"not sqlite")
    assert call(obj, "select")["error_code"] == "sa_company_collector_unavailable"
    assert obj.path.read_bytes() == b"not sqlite"


def test_native_control_routes_do_not_construct_dal(control, monkeypatch):
    from src.sa_native_host import handle_message

    def forbidden(*args, **kwargs):
        raise AssertionError("DAL must not be constructed")

    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", forbidden)
    monkeypatch.setattr(module(), "CompanyCollector", lambda: control[0])
    assert handle_message({"action": "company_refresh_control", "operation": "status", "client": FIREFOX})["status"] == "ok"


def test_recovery_revokes_the_old_collectors_pre_navigation_check(control):
    obj, _ = control
    call(obj, "select")
    permit = begin(obj)
    assert call(obj, "validate", token=permit["token"])["status"] == "ok"
    call(obj, "recover", confirm_stopped=True)
    assert call(obj, "validate", token=permit["token"])["error_code"] == "sa_company_reservation_invalid"


def test_native_begin_cannot_reuse_a_disabled_source(control, monkeypatch):
    from src.sa_native_host import handle_message
    from src.data_source_routing import DataSourcePolicyFailure

    class DisabledRoute:
        def candidates(self, provider):
            raise DataSourcePolicyFailure("data_source_not_selected")

    monkeypatch.setattr(module(), "CompanyCollector", lambda: control[0])
    monkeypatch.setattr("src.data_source_routing.load_route", lambda _: DisabledRoute())
    call(control[0], "select")
    result = handle_message({"action": "company_refresh_control", "operation": "begin", "client": FIREFOX,
                             "scope": SCOPE, "force": False, "interval_days": 7})
    assert result["error_code"] == "data_source_not_selected"
    assert call(control[0], "status")["active"] is None


def test_real_persisted_receipt_and_page_pacing(control, monkeypatch, tmp_path):
    from tests.test_sa_company_data import capture
    from src.sa.company_store import save_capture

    obj, clock = control
    clock[0] = datetime.now(timezone.utc).timestamp() - 1000
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "sa.db"))
    call(obj, "select")
    permit = begin(obj)
    clock[0] += 1
    payload = capture()
    payload["captured_at"] = datetime.fromtimestamp(clock[0], timezone.utc).isoformat()
    receipt = save_capture(payload)
    clock[0] += 1
    assert call(obj, "finish", token=permit["token"], result=receipt)["active"] is None
    assert begin(obj)["status"] == "reused"
    forced = call(obj, "begin", scope=SCOPE, interval_days=7, force=True)
    assert forced["status"] == "deferred" and forced["error_code"] == "sa_company_pacing"
    clock[0] += 60
    permit = call(obj, "begin", scope=SCOPE, interval_days=7, force=True)
    assert permit["status"] == "ok"
    # An old but real receipt cannot certify this second acquisition.
    assert call(obj, "finish", token=permit["token"], result=receipt)["error_code"] == "sa_company_receipt_unverified"


def test_manual_request_already_satisfied_before_crash_is_not_reacquired(control, monkeypatch):
    obj, clock = control
    request_at = datetime.fromtimestamp(clock[0] - 10, timezone.utc).isoformat()
    observation = {"observation_id": "b" * 64, "last_captured_at": datetime.fromtimestamp(clock[0] - 5, timezone.utc).isoformat()}
    monkeypatch.setattr("src.sa.company_store.read_capture", lambda *a, **k: observation)
    call(obj, "select")
    result = call(obj, "begin", scope=SCOPE, interval_days=7, force=True, requested_at=request_at)
    assert result["status"] == "reused"
    assert result["last_success_at"] == observation["last_captured_at"]
    assert call(obj, "status")["active"] is None


@pytest.mark.parametrize("completion", ["finish", "recover"])
def test_delayed_navigation_keeps_a_gap_after_completion(control, monkeypatch, completion):
    obj, clock = control
    call(obj, "select")
    permit = begin(obj)
    # The worker suspended between reservation and page navigation.
    clock[0] += 3600
    observation = {"observation_id": "b" * 64, "last_captured_at": datetime.fromtimestamp(clock[0], timezone.utc).isoformat()}
    monkeypatch.setattr("src.sa.company_store.read_capture", lambda *a, **k: observation)
    if completion == "finish":
        call(obj, "finish", token=permit["token"], result={"status": "ok", "observation_id": observation["observation_id"]})
    else:
        call(obj, "recover", confirm_stopped=True)
    clock[0] += 20
    result = call(obj, "begin", scope=SCOPE, interval_days=7, force=True)
    assert result["status"] == "deferred" and result["error_code"] == "sa_company_pacing"
