"""Check validation precedence without opening an application or installed store."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("suffix,params,expected", [
    ("filings", {"cursor": "!"}, 422),
    ("facts", {"cursor": "!"}, 422),
    ("filings", {"forms": ""}, 422),
    ("facts", {"period": "unknown"}, 422),
    ("filings", {"limit": "1.0"}, 422),
    ("filings", {}, 200),
    ("facts", {}, 200),
])
def test_absent_storage_does_not_bypass_input_validation(tmp_path, monkeypatch, suffix, params, expected):
    from src.api.routes import sec_research as module
    from src.sec_research.paths import SecResearchPaths

    paths = SecResearchPaths.from_market_db(tmp_path / "market.db")
    monkeypatch.setattr(module.SecResearchPaths, "resolve", lambda: paths)

    def forbidden(*args, **kwargs):
        pytest.fail("stored GET constructed a forbidden owner or installed storage")

    for name in ("get_profile_store", "get_data_provider_store", "CaptureStore", "SecTransport"):
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(module.Store, "install", forbidden)
    app = FastAPI()
    app.include_router(module.router)
    with TestClient(app) as client:
        response = client.get("/sec-research/320193/" + suffix, params=params)
    assert not paths.market_db_path.exists()
    assert not paths.capture_root.exists()
    assert response.status_code == expected, response.json()
    if expected == 422:
        assert response.json()["detail"]["code"] in {
            "sec_research_query_invalid", "sec_research_cursor_invalid",
        }
    else:
        assert response.json()["gaps"] == [{"code": "sec_research_not_installed"}]
