"""
API endpoint integration tests.

Uses FastAPI TestClient to test all endpoints against real data.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


# ============================================================
# Health
# ============================================================

class TestHealth:
    def test_status(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["tools_registered"] == 33
        assert data["data_sources"]["price_tickers"] > 50


# ============================================================
# News
# ============================================================

class TestNewsEndpoints:
    def test_get_news(self, client):
        r = client.get("/news/NVDA?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] > 0
        assert len(data["articles"]) > 0

    def test_get_news_sentiment(self, client):
        r = client.get("/news/NVDA/sentiment?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["scored_count"] > 0
        assert 1 <= data["sentiment_mean"] <= 5

    def test_search_news(self, client):
        r = client.get("/news/search/keyword?keyword=earnings&days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0


# ============================================================
# Prices
# ============================================================

class TestPriceEndpoints:
    def test_get_prices(self, client):
        r = client.get("/prices/NVDA?interval=15min&days=7")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] > 0
        assert len(data["bars"]) > 0

    def test_price_change(self, client):
        r = client.get("/prices/NVDA/change?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert "change_pct" in data
        assert data["bar_count"] > 0

    def test_sector_performance(self, client):
        r = client.get("/prices/sector/AI_CHIPS?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["sector"] == "AI_CHIPS"
        assert data["ticker_count"] > 0
        assert "avg_change_pct" in data


# ============================================================
# Options
# ============================================================

class TestOptionsEndpoints:
    def test_iv_analysis(self, client):
        r = client.get("/options/AMD")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "AMD"
        assert data["current_iv"] is not None

    def test_iv_history(self, client):
        r = client.get("/options/AMD/history")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "atm_iv" in data[0]

    def test_greeks(self, client):
        r = client.get("/options/greeks/calculate?S=150&K=155&T=0.25&sigma=0.30")
        assert r.status_code == 200
        data = r.json()
        assert "delta" in data
        assert "gamma" in data
        assert 0 <= data["delta"] <= 1


# ============================================================
# Signals
# ============================================================

class TestSignalEndpoints:
    def test_synthesize_signal(self, client):
        r = client.get("/signals/NVDA?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["action"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_anomalies(self, client):
        r = client.get("/signals/NVDA/anomalies?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"

    def test_event_chains(self, client):
        r = client.get("/signals/NVDA/event-chains?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


# ============================================================
# Scan
# ============================================================

class TestScanEndpoints:
    def test_mispricing_scan(self, client):
        r = client.get("/scan/mispricing?tickers=AMD,NVDA")
        assert r.status_code == 200
        data = r.json()
        # Empty without cached quotes, but should not error
        assert isinstance(data, list)


# ============================================================
# Fundamentals
# ============================================================

class TestFundamentalsEndpoints:
    def test_fundamentals(self, client):
        r = client.get("/fundamentals/NVDA")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["market_cap"] is not None

    def test_sec_filings(self, client):
        r = client.get("/sec/NVDA")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


# ============================================================
# Config
# ============================================================

class TestConfigEndpoints:
    def test_watchlist(self, client):
        r = client.get("/config/watchlist")
        assert r.status_code == 200
        data = r.json()
        assert len(data["tickers"]) > 0
        assert "NVDA" in data["tickers"]

    def test_sectors(self, client):
        r = client.get("/config/sectors")
        assert r.status_code == 200
        data = r.json()
        assert "AI_CHIPS" in data

    def test_strategy(self, client):
        r = client.get("/config/strategy?strategy=momentum")
        assert r.status_code == 200
        data = r.json()
        assert "price_trend" in data

    def test_overview(self, client):
        r = client.get("/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker_count"] > 0

    def test_morning_brief(self, client):
        r = client.get("/morning-brief")
        assert r.status_code == 200
        data = r.json()
        assert "date" in data
        assert "holdings" in data