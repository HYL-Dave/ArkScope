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

from src.analysis.contracts import AnalysisArtifact, AnalysisRequest, IntegrityResult, RenderedReport
from src.analysis.service import SavedAnalysisReport
from src.api.app import create_app
from src.agents.config import get_agent_config
from src.api.routes.analysis import AnalysisRunRequest, run_analysis


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
        assert data["tools_registered"] == 55
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

class TestNewsFeed:
    def test_feed_route_not_captured_by_ticker_route(self, client):
        # /news/feed is declared BEFORE /news/{ticker} — must return the feed
        # shape, not a ticker-news lookup for ticker="feed".
        r = client.get("/news/feed?days=7&limit=3")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"available", "items", "total", "sources", "days"}
        if data["available"] and data["items"]:
            it = data["items"][0]
            assert {"published_at", "ticker", "title", "source"} <= set(it.keys())

    def test_feed_search_and_filters(self, client):
        r = client.get("/news/feed?q=earnings&ticker=NVDA&days=90&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert all(i["ticker"] == "NVDA" for i in data["items"])


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
        # {points, source_path}: the table is its own request → own provenance
        assert data["source_path"] in ("local", "pg_fallback", "pg", "file", "none")
        assert isinstance(data["points"], list)
        assert len(data["points"]) >= 1
        assert "atm_iv" in data["points"][0]

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


class TestAnalysisEndpoint:
    def test_analysis_run_disabled_by_default(self):
        original = get_agent_config().analysis_pipeline_enabled
        get_agent_config().analysis_pipeline_enabled = False
        try:
            with pytest.raises(Exception) as exc_info:
                run_analysis(AnalysisRunRequest(ticker="NVDA"), dal=object())
        finally:
            get_agent_config().analysis_pipeline_enabled = original
        assert getattr(exc_info.value, "status_code", None) == 503

    def test_analysis_run_enabled(self, monkeypatch):
        artifact = AnalysisArtifact(
            request=AnalysisRequest(ticker="NVDA"),
            context_summary={},
            strategy_results={},
            final_decision={"action": "buy", "summary": "NVDA: BUY bias"},
            report_sections={"executive_summary": "NVDA: BUY bias"},
            degradation_summary=[],
        )

        def _fake_run_analysis_request(request, *, dal=None, render_format="markdown"):
            del request, dal, render_format
            return type(
                "_Output",
                (),
                {
                    "artifact": artifact,
                    "integrity": IntegrityResult(artifact=artifact, status="clean"),
                    "report": RenderedReport(format="markdown", content="# NVDA\n\nNVDA: BUY bias\n"),
                },
            )()

        monkeypatch.setattr(
            "src.api.routes.analysis.run_analysis_request",
            _fake_run_analysis_request,
        )
        monkeypatch.setattr(
            "src.api.routes.analysis.save_analysis_run",
            lambda dal, output, title=None: SavedAnalysisReport(
                id=99,
                file_path="data/reports/nvda.md",
                title=title or "NVDA Phase D Analysis",
                created_at="2026-04-15T00:00:00",
            ),
        )

        original = get_agent_config().analysis_pipeline_enabled
        get_agent_config().analysis_pipeline_enabled = True
        try:
            response = run_analysis(
                AnalysisRunRequest(ticker="NVDA", depth="quick", persist=True),
                dal=object(),
            )
        finally:
            get_agent_config().analysis_pipeline_enabled = original
        assert response.ticker == "NVDA"
        assert response.integrity_status == "clean"
        assert response.action == "buy"
        assert response.report.startswith("# NVDA")
        assert response.saved_report_id == 99
        assert response.saved_report_path == "data/reports/nvda.md"


# ============================================================
# Fundamentals: stored-only mode must NOT trigger a provider fetch
# ============================================================

def test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch(monkeypatch):
    """stored=true is read-only: it may read local financial_cache, but never enters
    the SEC/Financial-Datasets fetch chain and never reads the retired mirror table."""
    from src.api.routes import fundamentals as fr
    from src.tools.schemas import FundamentalsResult

    calls = {"analysis": 0, "dal": 0}

    class _Backend:
        def __init__(self):
            self.rows = {
                "fundamentals_analysis:sec_edgar:AAPL:annual:v1":
                    FundamentalsResult(
                        ticker="AAPL",
                        data_source="sec_edgar",
                        snapshot_date="2025-12-31",
                        roe=0.22,
                    ).model_dump()
            }

        def get_financial_cache(self, cache_key):
            return self.rows.get(cache_key)

    class _FakeDAL:
        backend_type = "LocalMarketDatabaseBackend"

        def __init__(self):
            self._backend = _Backend()

        def get_fundamentals(self, ticker):
            calls["dal"] += 1
            raise AssertionError("stored=true must not read retired fundamentals table")

    def _spy_analysis(dal, ticker):
        calls["analysis"] += 1
        return FundamentalsResult(ticker=ticker.upper(), data_source="sec_edgar")

    monkeypatch.setattr(fr, "get_fundamentals_analysis", _spy_analysis)
    dal = _FakeDAL()

    out = fr.fundamentals("AAPL", stored=True, dal=dal)
    assert calls == {"analysis": 0, "dal": 0}
    assert out["data_source"] == "sec_edgar"
    assert out["snapshot_date"] == "2025-12-31"
    assert out["roe"] == 0.22
    assert out["source_path"] == "local_cache"

    out2 = fr.fundamentals("AAPL", stored=False, dal=dal)
    assert calls["analysis"] == 1
    assert out2["data_source"] == "sec_edgar"


class _FakeDALBT:
    """Minimal DAL stub exposing backend_type for the source_path fallback."""
    def __init__(self, backend_type):
        self.backend_type = backend_type


def test_iv_analysis_source_path_mapping(monkeypatch):
    """/options/{ticker} reports source_path: recorded provenance passes through; when
    nothing is recorded it maps by backend type to pg / file (data) or none (empty)."""
    from src.api.routes import options as opt
    from src.tools.backends import provenance
    from src.tools.schemas import IVAnalysisResult

    monkeypatch.setattr(opt, "get_iv_analysis",
                        lambda dal, ticker: IVAnalysisResult(ticker=ticker, history_days=8, current_iv=0.3))
    monkeypatch.setattr(provenance, "read", lambda d: "local")  # recorded → passes through
    assert opt.iv_analysis("NVDA", dal=_FakeDALBT("LocalMarketDatabaseBackend"))["source_path"] == "local"

    monkeypatch.setattr(provenance, "read", lambda d: None)  # not recorded → by backend type
    assert opt.iv_analysis("NVDA", dal=_FakeDALBT("DatabaseBackend"))["source_path"] == "pg"
    assert opt.iv_analysis("NVDA", dal=_FakeDALBT("FileBackend"))["source_path"] == "file"

    monkeypatch.setattr(opt, "get_iv_analysis",
                        lambda dal, ticker: IVAnalysisResult(ticker=ticker, history_days=0))
    assert opt.iv_analysis("NVDA", dal=_FakeDALBT("DatabaseBackend"))["source_path"] == "none"  # empty


def test_iv_history_source_path_mapping(monkeypatch):
    """/options/{ticker}/history carries its OWN source_path (separate request from
    the summary — the table must never borrow the summary call's provenance)."""
    from src.api.routes import options as opt
    from src.tools.backends import provenance
    from src.tools.schemas import IVHistoryPoint

    pts = [IVHistoryPoint(date="2026-06-01", atm_iv=0.3)]
    monkeypatch.setattr(opt, "get_iv_history_data", lambda dal, ticker: pts)
    monkeypatch.setattr(provenance, "read", lambda d: "local")
    out = opt.iv_history("NVDA", dal=_FakeDALBT("LocalMarketDatabaseBackend"))
    assert out["source_path"] == "local" and out["points"][0]["atm_iv"] == 0.3

    monkeypatch.setattr(provenance, "read", lambda d: None)  # not recorded → by backend type
    assert opt.iv_history("NVDA", dal=_FakeDALBT("FileBackend"))["source_path"] == "file"
    monkeypatch.setattr(opt, "get_iv_history_data", lambda dal, ticker: [])
    out = opt.iv_history("NVDA", dal=_FakeDALBT("DatabaseBackend"))
    assert out["source_path"] == "none" and out["points"] == []


def test_fundamentals_stored_source_path_mapping(monkeypatch):
    """/fundamentals/{ticker}?stored=true reports local_cache or none."""
    from src.api.routes import fundamentals as fr
    from src.tools.schemas import FundamentalsResult

    class _CachedDAL(_FakeDALBT):
        def __init__(self):
            super().__init__("LocalMarketDatabaseBackend")
            self._backend = self

        def get_financial_cache(self, cache_key):
            return FundamentalsResult(
                ticker="AAPL",
                data_source="sec_edgar",
                snapshot_date="2025-12-31",
            ).model_dump()

    out = fr.fundamentals("AAPL", stored=True, dal=_CachedDAL())
    assert out["source_path"] == "local_cache"

    class _EmptyDAL(_FakeDALBT):
        def __init__(self):
            super().__init__("LocalMarketDatabaseBackend")
            self._backend = self

        def get_financial_cache(self, cache_key):
            return None

    out = fr.fundamentals("AAPL", stored=True, dal=_EmptyDAL())
    assert out["source_path"] == "none"
    assert out["data_source"] == "none"
    assert out["snapshot_date"] is None


def test_fundamentals_stored_expired_cache_is_honest_empty(tmp_path):
    """/fundamentals/{ticker}?stored=true must respect financial_cache expiry.

    SqliteBackend.get_financial_cache filters expires_at, so the route should see an
    expired annual-analysis cache row as a miss and return honest empty rather than
    serving stale fundamentals.
    """
    from src.api.routes import fundamentals as fr
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from src.tools.backends.sqlite_backend import SqliteBackend
    from src.tools.schemas import FundamentalsResult

    backend = SqliteBackend(str(tmp_path / "market_data.db"))
    cache_key = fundamentals_analysis_cache_key("AAPL", "annual")
    assert backend.set_financial_cache(
        cache_key,
        "AAPL",
        FundamentalsResult(
            ticker="AAPL",
            data_source="sec_edgar",
            snapshot_date="2025-12-31",
            roe=0.99,
        ).model_dump(),
        source="sec_edgar",
        fetched_at="2000-01-01T00:00:00+00:00",
        expires_at="2000-01-02T00:00:00+00:00",
    )

    class _DAL(_FakeDALBT):
        def __init__(self):
            super().__init__("LocalMarketDatabaseBackend")
            self._backend = backend

    out = fr.fundamentals("AAPL", stored=True, dal=_DAL())

    assert out["source_path"] == "none"
    assert out["data_source"] == "none"
    assert out["snapshot_date"] is None
    assert out["roe"] is None
