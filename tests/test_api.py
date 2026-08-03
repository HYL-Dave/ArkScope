"""
API endpoint integration tests.

Uses FastAPI TestClient to test all endpoints against real data.
"""

import sys
import asyncio
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.contracts import AnalysisArtifact, AnalysisRequest, IntegrityResult, RenderedReport
from src.analysis.service import SavedAnalysisReport
from src.api.app import create_app
from src.api.dependencies import get_dal
from src.agents.config import get_agent_config
from src.api.routes.analysis import AnalysisRunRequest, run_analysis
from src.tools.data_access import DataAccessLayer


def test_fixed_task_runtime_routes_mount_on_real_app():
    try:
        asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    routes = {
        (getattr(route, "path", None), method)
        for route in create_app().routes
        for method in (getattr(route, "methods", None) or set())
    }
    assert ("/config/fixed-task-runtime", "PUT") in routes
    assert ("/config/fixed-task-runtime", "DELETE") in routes


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


_HERMETIC_NEWS_ROWS = [
    {
        "date": "2026-07-30T14:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA earnings beat expectations",
        "source": "polygon",
        "url": "https://example.test/nvda-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 5.0,
        "risk_score": 2.0,
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "sentiment_score": 3.0,
        "risk_score": 3.0,
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
        "sentiment_score": 2.0,
        "risk_score": 4.0,
        "description": "Analysts preview AMD earnings.",
    },
]

_HERMETIC_PRICE_ROWS = {
    ("NVDA", "15min"): [
        ("2026-07-30T13:30:00+0000", 100.0, 102.0, 99.0, 101.0, 100),
        ("2026-07-30T13:45:00+0000", 101.0, 106.0, 100.0, 105.0, 120),
    ],
    ("NVDA", "1d"): [
        ("2026-07-29T00:00:00+0000", 100.0, 106.0, 99.0, 105.0, 1000),
        ("2026-07-30T00:00:00+0000", 105.0, 112.0, 104.0, 110.0, 1200),
    ],
    ("AMD", "15min"): [
        ("2026-07-30T13:30:00+0000", 50.0, 52.0, 49.0, 51.0, 200),
        ("2026-07-30T13:45:00+0000", 51.0, 53.0, 50.0, 52.0, 220),
    ],
    ("AMD", "1d"): [
        ("2026-07-29T00:00:00+0000", 50.0, 53.0, 49.0, 52.0, 2000),
        ("2026-07-30T00:00:00+0000", 52.0, 53.0, 50.0, 51.0, 2200),
    ],
}

_PRICE_COLUMNS = ["datetime", "open", "high", "low", "close", "volume"]


class _HermeticMarketBackend:
    def query_news(
        self,
        ticker=None,
        days=30,
        source="auto",
        scored_only=True,
        model=None,
    ):
        del days, model
        frame = pd.DataFrame(_HERMETIC_NEWS_ROWS)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        if scored_only:
            frame = frame[frame["sentiment_score"].notna()]
        return frame.reset_index(drop=True)

    def query_prices(self, ticker, interval="15min", days=30):
        del days
        rows = _HERMETIC_PRICE_ROWS.get((ticker.upper(), interval), [])
        return pd.DataFrame(rows, columns=_PRICE_COLUMNS)

    def query_fundamentals(self, ticker):
        if ticker.upper() != "NVDA":
            return {}
        return {
            "collected_at": "2026-07-30T00:00:00+0000",
            "snapshot": {
                "market_cap": 1_500_000_000_000.0,
                "pe_ratio": 30.0,
                "price_to_sales": 15.0,
                "price_to_book": 25.0,
            },
        }

    def get_financial_cache(self, cache_key):
        from src.tools.schemas import FundamentalsResult

        if cache_key != "fundamentals_analysis:sec_edgar:NVDA:annual:v1":
            return None
        return FundamentalsResult(
            ticker="NVDA",
            snapshot_date="2025-12-31",
            data_source="sec_edgar",
            roe=0.31,
            revenue_growth=0.25,
            free_cash_flow=500_000.0,
        ).model_dump()

    def get_available_tickers(self, data_type):
        return {
            "news": ["AMD", "NVDA"],
            "prices": ["AMD", "NVDA"],
            "fundamentals": ["NVDA"],
        }.get(data_type, [])


@pytest.fixture()
def hermetic_market_app():
    app = create_app()
    dal = DataAccessLayer(
        base_path=project_root,
        backend=_HermeticMarketBackend(),
    )
    app.dependency_overrides[get_dal] = lambda: dal
    try:
        yield app
    finally:
        app.dependency_overrides.pop(get_dal, None)


def _api_get(app, path):
    async def _request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(_request())


def _install_fundamentals_provider_spies(monkeypatch):
    calls = []

    def _record_sec(*args, **kwargs):
        del args, kwargs
        calls.append("sec_edgar")
        raise RuntimeError("SEC provider fallback reached")

    def _record_fd(*args, **kwargs):
        del args, kwargs
        calls.append("financial_datasets")
        return False

    monkeypatch.setattr(
        "data_sources.sec_edgar_financials.SECEdgarFinancials",
        _record_sec,
    )
    monkeypatch.setattr(
        "src.tools.analysis_tools._is_fd_enabled",
        _record_fd,
    )
    return calls


# ============================================================
# Health
# ============================================================

class TestHealth:
    def test_status(self, hermetic_market_app):
        r = _api_get(hermetic_market_app, "/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["tools_registered"] == 53
        assert data["data_sources"] == {
            "news_tickers": 2,
            "price_tickers": 2,
            "fundamentals_tickers": 1,
        }


# ============================================================
# News
# ============================================================

class TestNewsEndpoints:
    def test_get_news(self, hermetic_market_app):
        r = _api_get(hermetic_market_app, "/news/NVDA?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] == 2
        assert data["source_breakdown"] == {"polygon": 1, "ibkr": 1}

    def test_get_news_sentiment(self, hermetic_market_app):
        r = _api_get(hermetic_market_app, "/news/NVDA/sentiment?days=9999")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["article_count"] == 2
        assert data["scored_count"] == 2
        assert data["sentiment_mean"] == 4.0
        assert data["bullish_ratio"] == 0.5

    def test_search_news(self, hermetic_market_app):
        r = _api_get(
            hermetic_market_app,
            "/news/search/keyword?keyword=earnings&days=9999",
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert {article["ticker"] for article in data["articles"]} == {"NVDA", "AMD"}


# ============================================================
# Prices
# ============================================================

class TestPriceEndpoints:
    def test_get_prices(self, hermetic_market_app):
        r = _api_get(
            hermetic_market_app,
            "/prices/NVDA?interval=15min&days=7",
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["count"] == 2
        assert [bar["close"] for bar in data["bars"]] == [101.0, 105.0]

    def test_price_change(self, hermetic_market_app):
        r = _api_get(hermetic_market_app, "/prices/NVDA/change?days=30")
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["bar_count"] == 2
        assert data["change_pct"] == 10.0
        assert data["period_high"] == 112.0
        assert data["period_low"] == 99.0

    def test_sector_performance(self, hermetic_market_app):
        r = _api_get(
            hermetic_market_app,
            "/prices/sector/AI_CHIPS?days=30",
        )
        assert r.status_code == 200
        data = r.json()
        assert data["sector"] == "AI_CHIPS"
        assert data["ticker_count"] == 2
        assert data["avg_change_pct"] == 6.0
        assert data["best_ticker"] == "NVDA"
        assert data["worst_ticker"] == "AMD"


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
        assert set(data.keys()) == {
            "available",
            "items",
            "total",
            "sources",
            "days",
            "content_counts",
        }
        if data["available"] and data["items"]:
            it = data["items"][0]
            assert {
                "published_at",
                "ticker",
                "title",
                "source",
                "content_availability",
                "content_recovery",
            } <= set(it.keys())

    def test_feed_search_and_filters(self, client):
        r = client.get("/news/feed?q=earnings&ticker=NVDA&days=90&limit=5")
        assert r.status_code == 200
        data = r.json()
        assert all(i["ticker"] == "NVDA" for i in data["items"])

    def test_feed_rejects_invalid_content(self, client):
        r = client.get("/news/feed?content=body_or_guess")

        assert r.status_code == 422


class TestOptionsEndpoints:
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
# Fundamentals
# ============================================================

class TestFundamentalsEndpoints:
    def test_fundamentals(self, hermetic_market_app, monkeypatch):
        provider_calls = _install_fundamentals_provider_spies(monkeypatch)
        r = _api_get(hermetic_market_app, "/fundamentals/NVDA")
        assert r.status_code == 200
        assert provider_calls == []
        data = r.json()
        assert data["ticker"] == "NVDA"
        assert data["data_source"] == "sec_edgar"
        assert data["snapshot_date"] == "2025-12-31"
        assert data["roe"] == 0.31
        assert data["revenue_growth"] == 0.25
        assert data["market_cap"] is None
        assert data["pe_ratio"] is None

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


def test_retired_market_admin_and_iv_routes_are_absent_while_greeks_remains_reachable(
    client,
):
    paths = client.app.openapi()["paths"]
    assert "/options/{ticker}" not in paths
    assert "/options/{ticker}/history" not in paths
    assert "/scan/mispricing" not in paths
    assert "/market-data/jobs/{job_id}" not in paths
    assert "/options/greeks/calculate" in paths

    response = client.get(
        "/options/greeks/calculate",
        params={
            "S": 150,
            "K": 155,
            "T": 0.25,
            "sigma": 0.30,
            "option_type": "C",
            "model": "american",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert {"delta", "gamma", "theta", "vega", "rho"} <= set(data)
    assert 0 <= data["delta"] <= 1


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
