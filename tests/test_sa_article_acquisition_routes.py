"""Settings reads are local and writes never change a frozen acquisition job."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api.dependencies import get_data_provider_store
from src.api.routes import seeking_alpha
from src.data_provider_config import DataProviderConfigStore
from src.sa.article_acquisition_settings import ARTICLE_SETTINGS_KEY, ArticleAcquisitionSettings
from tests.test_sa_body_recovery_jobs import journal_case, scope_case


DEFAULTS = ArticleAcquisitionSettings().model_dump()
ENDPOINT = "/sa/article-acquisition-settings"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "capture.db"))
    app = FastAPI()
    app.include_router(seeking_alpha.router)
    app.dependency_overrides[get_data_provider_store] = lambda: DataProviderConfigStore(tmp_path / "profile.db")
    with TestClient(app) as client:
        yield client


def test_empty_reads_never_create_stores_or_spawn_native(client, tmp_path, monkeypatch):
    forbidden = Mock(side_effect=AssertionError("not a local read"))
    monkeypatch.setattr("subprocess.Popen", forbidden)
    before = set(tmp_path.iterdir())
    response = client.get(ENDPOINT)
    assert response.status_code == 200
    assert response.json() == {"values": DEFAULTS, "defaults": DEFAULTS, "setting_source": "default", "error_code": None}
    assert client.get("/sa/body-recovery-status").json()["state"] == "not_started"
    assert set(tmp_path.iterdir()) == before
    forbidden.assert_not_called()


@pytest.mark.parametrize("limit,days", [(0, 0), (128, 3650), (2**53 - 1, 2**53 - 1)])
def test_round_trip_policy_preserves_other_settings(client, tmp_path, limit, days):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    store.set_setting("financial.sentinel", "unchanged")
    values = {**DEFAULTS, "max_articles_per_job": limit, "body_lookback_days": days,
              "body_scope": "current", "comment_scope": "tracked"}
    response = client.put(ENDPOINT, json=values)
    assert response.status_code == 200, response.text
    assert response.json()["values"] == values
    assert client.get(ENDPOINT).json() == response.json()
    assert store.get_setting("financial.sentinel") == "unchanged"


@pytest.mark.parametrize("change", [{"max_articles_per_job": -1}, {"body_lookback_days": True},
    {"max_articles_per_job": "5"}, {"max_articles_per_job": 2**53}, {"body_lookback_days": 1.5},
    {"body_scope": "deleted"}, {"comment_scope": "all"}, {"paid": True}])
def test_invalid_update_is_atomic(client, tmp_path, change):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    raw = json.dumps(DEFAULTS)
    store.set_setting(ARTICLE_SETTINGS_KEY, raw)
    assert client.put(ENDPOINT, json={**DEFAULTS, **change}).status_code == 422
    assert store.get_setting(ARTICLE_SETTINGS_KEY) == raw


def test_invalid_saved_policy_and_unreadable_store_are_not_defaults(client, tmp_path):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    store.set_setting(ARTICLE_SETTINGS_KEY, "{")
    response = client.get(ENDPOINT).json()
    assert response["values"] is None
    assert response["error_code"] == "sa_article_settings_invalid"
    assert client.put(ENDPOINT, json=DEFAULTS).status_code == 200
    with sqlite3.connect(tmp_path / "profile.db") as conn:
        conn.execute("DROP TABLE profile_settings")
    assert client.get(ENDPOINT).status_code == 503


def test_write_permission_and_write_error_leave_policy_unchanged(client, tmp_path, monkeypatch):
    store = DataProviderConfigStore(tmp_path / "profile.db")
    permission = Mock(side_effect=HTTPException(403, "blocked"))
    monkeypatch.setattr(seeking_alpha, "require_profile_state_write", permission)
    assert client.put(ENDPOINT, json=DEFAULTS).status_code == 403
    assert store.get_setting(ARTICLE_SETTINGS_KEY) is None
    permission.side_effect = None
    broken = Mock()
    broken.set_setting.side_effect = OSError("private path not exposed")
    client.app.dependency_overrides[get_data_provider_store] = lambda: broken
    response = client.put(ENDPOINT, json=DEFAULTS)
    assert response.status_code == 503
    assert "private path" not in response.text


def test_settings_change_keeps_body_job_and_former_content_frozen(journal_case):
    case = journal_case
    job = case.start()
    before = case.conn.execute("SELECT * FROM sa_articles ORDER BY article_id").fetchall()
    app = FastAPI()
    app.include_router(seeking_alpha.router)
    app.dependency_overrides[get_data_provider_store] = lambda: DataProviderConfigStore(case.jobs.profile_db)
    with TestClient(app) as client:
        snapshot = client.get("/sa/body-recovery-status")
        assert snapshot.status_code == 200
        assert snapshot.json()["counts"]["selected"] == 8
        assert not any(secret in snapshot.text for secret in ("client_id", "token", "capture_path", "ledger_id"))
        saved = client.put(ENDPOINT, json={**DEFAULTS, "body_scope": "current", "max_articles_per_job": 1})
        assert saved.status_code == 200
        assert client.get(ENDPOINT).json() == saved.json()
        assert client.get("/sa/body-recovery-status").json() == snapshot.json()
        assert snapshot.json()["job_id"] == job["job_id"]
    assert case.conn.execute("SELECT * FROM sa_articles ORDER BY article_id").fetchall() == before
    assert case.navigation_count() == 0


def test_broken_journal_is_an_error_not_no_work(client, tmp_path):
    with sqlite3.connect(tmp_path / "sa_company_refresh.db") as conn:
        conn.execute("CREATE TABLE unrelated(value)")
    response = client.get("/sa/body-recovery-status")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "sa_body_journal_unavailable"
