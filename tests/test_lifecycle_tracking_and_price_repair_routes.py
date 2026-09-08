import sqlite3
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api.routes import market_data, profile
from src.api.dependencies import get_profile_store
from src.profile_state import ProfileStateStore
from src.sa_tracking_memberships import SaTrackingMembershipStore
from tests.test_price_coverage_repair import coverage


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src import sa_capture_store
    monkeypatch.setattr(sa_capture_store, "resolve_sa_db_path", lambda: tmp_path / "sa.db")
    store = ProfileStateStore(tmp_path / "profile.db")
    monkeypatch.setattr(market_data, "resolve_market_db_path", lambda: str(tmp_path / "market.db"))
    app = FastAPI()
    app.include_router(profile.router)
    app.include_router(market_data.router)
    app.dependency_overrides[get_profile_store] = lambda: store
    with TestClient(app) as http:
        yield http, store


def test_former_routes_are_source_scoped_gated_and_get_is_pure(client, monkeypatch):
    http, profile_store = client
    path = profile_store.db_path
    before = open(path, "rb").read()
    assert http.get("/profile/alpha-picks-tracking").json() == {"available": False, "memberships": []}
    assert open(path, "rb").read() == before
    with sqlite3.connect(path) as conn:
        SaTrackingMembershipStore.install(conn)
    tracking = SaTrackingMembershipStore(path)
    row = {"lineage_id": 1, "ticker": "OLD", "picked_date": "2025-01-01", "portfolio_status": "closed", "observed_at": "2026-09-05T01:00:00Z"}
    tracking.reconcile([row], at=row["observed_at"], bootstrap_actor="attended_user")
    from src import sa_tracking_memberships
    assert http.get("/profile/alpha-picks-tracking").json()["sync_status"] == "unavailable"
    monkeypatch.setattr(sa_tracking_memberships, "read_sa_tracking_observations", lambda path: [row])
    before = open(path, "rb").read()
    assert http.get("/profile/alpha-picks-tracking").json()["sync_status"] == "current"
    assert open(path, "rb").read() == before
    member_id = http.get("/profile/alpha-picks-tracking").json()["memberships"][0]["membership_id"]
    def deny(*args):
        raise HTTPException(403, {"code": "permission_denied"})
    monkeypatch.setattr(profile, "require_profile_state_write", deny)
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "remove"}).status_code == 403
    assert tracking.list_memberships()[0]["state"] == "tracking"
    monkeypatch.setattr(profile, "require_profile_state_write", lambda *args: None)
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "remove"}).status_code == 200
    tracking.reconcile([row], at=row["observed_at"], bootstrap_actor="attended_user")
    assert http.get("/profile/alpha-picks-tracking").json()["memberships"][0]["state"] == "removed"
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "restore"}).status_code == 200
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "erase"}).status_code == 422
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "remove", "ticker": "LIVE"}).status_code == 422


def test_dual_source_route_keeps_current_visible_after_former_removal(client, monkeypatch):
    http, profile_store = client
    with sqlite3.connect(profile_store.db_path) as conn:
        SaTrackingMembershipStore.install(conn)
    tracking = SaTrackingMembershipStore(profile_store.db_path)
    row = {"lineage_id": 1, "ticker": "BOTH", "picked_date": "2025-01-01", "portfolio_status": "closed",
           "current_observed": True, "observed_at": "2026-09-05T01:00:00Z"}
    tracking.reconcile((row,), at=row["observed_at"])
    monkeypatch.setattr(profile, "require_profile_state_write", lambda *args: None)
    before = http.get("/profile/alpha-picks-tracking").json()["memberships"]
    assert {(item["portfolio_status"], item["state"]) for item in before} == {
        ("current", "tracking"), ("closed", "tracking"),
    }
    member_id = next(item["membership_id"] for item in before if item["portfolio_status"] == "closed")
    assert http.post(f"/profile/alpha-picks-tracking/{member_id}", json={"action": "remove"}).status_code == 200
    after = http.get("/profile/alpha-picks-tracking").json()["memberships"]
    assert {(item["portfolio_status"], item["state"]) for item in after} == {
        ("current", "tracking"), ("closed", "removed"),
    }
    current = next(item for item in after if item["portfolio_status"] == "current")
    assert current["removed_at"] is None
    assert current["reason"] == "current_observed"
    assert tracking.active_sources() == {"sa_alpha_picks_current": {"BOTH"}}


def test_repair_route_requires_fresh_preview_and_both_permissions_before_dispatch(client, monkeypatch):
    http, _ = client
    current = [coverage()]
    monkeypatch.setattr(market_data, "market_data_trading_days", lambda **kwargs: current[0])
    dispatched = []
    class Thread:
        def __init__(self, **kwargs):
            dispatched.append(kwargs)
        def start(self):
            pass
    monkeypatch.setattr(threading, "Thread", Thread)
    preview = http.get("/market-data/price-repair/preview?lookback_days=15").json()
    assert dispatched == []
    body = {"lookback_days": 15, "preview_sha256": preview["preview_sha256"]}
    for permission in ("require_db_write", "require_profile_state_write"):
        monkeypatch.setattr(market_data, "require_db_write", lambda *args: None)
        monkeypatch.setattr(market_data, "require_profile_state_write", lambda *args: None)
        def deny(*args):
            raise HTTPException(403, {"code": "permission_denied"})
        monkeypatch.setattr(market_data, permission, deny)
        assert http.post("/market-data/price-repair", json=body).status_code == 403
        assert dispatched == []
    monkeypatch.setattr(market_data, "require_profile_state_write", lambda *args: None)
    current[0] = coverage(tickers=("CHANGED",))
    assert http.post("/market-data/price-repair", json=body).json()["detail"]["code"] == "price_repair_preview_changed"
    assert dispatched == []
    current[0] = coverage()
    response = http.post("/market-data/price-repair", json=body)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert dispatched[0]["kwargs"]["tickers"] == ["NEW"]
    assert dispatched[0]["kwargs"]["price_repair_id"] == response.json()["repair_id"]
