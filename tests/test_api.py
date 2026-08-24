"""
API endpoint integration tests.

Uses FastAPI TestClient to test all endpoints against real data.
"""

import sys
import asyncio
import socket
import threading
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.app import create_app
from src.api.dependencies import get_dal
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


def _run_local_runtime_lifespan(monkeypatch, tmp_path):
    from src.api import dependencies
    from src.scheduler_state import SchedulerStateStore
    from src.service import data_scheduler

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    for name, filename in {
        "ARKSCOPE_PROFILE_DB": "profile_state.db",
        "ARKSCOPE_MARKET_DB": "market_data.db",
        "ARKSCOPE_SA_DB": "sa_capture.db",
        "ARKSCOPE_MACRO_CALENDAR_DB": "macro_calendar.db",
        "ARKSCOPE_CONSENSUS_DB": "consensus.db",
        "ARKSCOPE_TOKEN_STORE_PATH": "token_store.json",
    }.items():
        monkeypatch.setenv(name, str(runtime_root / filename))
    monkeypatch.delenv("ARKSCOPE_DISABLE_SCHEDULER", raising=False)

    monkeypatch.setattr(
        "src.data_provider_config.apply_env",
        lambda store: frozenset(),
    )

    class _CaptureService:
        def __init__(self):
            self.events = []

        def reconcile_startup(self):
            self.events.append("reconciled")

        def scheduler_tick(self, *, startup):
            self.events.append(("tick", startup))

    capture_service = _CaptureService()
    monkeypatch.setattr(
        dependencies,
        "get_portfolio_capture_service",
        lambda: capture_service,
    )
    dependencies.get_data_provider_store.cache_clear()
    dependencies.get_dal.cache_clear()

    monkeypatch.setattr(
        data_scheduler,
        "_SCHED_STATE",
        SchedulerStateStore(runtime_root / "profile_state.db"),
    )
    monkeypatch.setattr(data_scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(data_scheduler, "_LAST_RESULT", {})

    tick_seen = threading.Event()
    ticks = []
    provider_calls = []
    real_tick_once = data_scheduler.tick_once

    def _observed_tick():
        fired = real_tick_once(fire=provider_calls.append)
        ticks.append(fired)
        tick_seen.set()
        return fired

    monkeypatch.setattr(data_scheduler, "tick_once", _observed_tick)

    network_attempts = []

    def _blocked_network(*args, **kwargs):
        del args, kwargs
        network_attempts.append("blocked")
        raise OSError("external network denied by local-runtime gate")

    monkeypatch.setattr(socket.socket, "connect", _blocked_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_network)
    monkeypatch.setattr(socket, "create_connection", _blocked_network)

    async def _exercise():
        app = create_app()
        active_owner_names = set()
        async with app.router.lifespan_context(app):
            observed = await asyncio.wait_for(
                asyncio.to_thread(tick_seen.wait, 3.0),
                timeout=4.0,
            )
            assert observed is True
            active_owner_names = {
                task.get_name()
                for task in asyncio.all_tasks()
                if not task.done()
                and task.get_name() in {
                    "data-scheduler",
                    "portfolio-capture-scheduler",
                }
            }
            route_rows = sorted(
                f"{','.join(sorted(getattr(route, 'methods', None) or ())) }\t"
                f"{route.path}\t{route.endpoint.__module__}\t{route.endpoint.__qualname__}"
                for route in app.routes
            )
        await asyncio.sleep(0)
        leaked_owner_names = {
            task.get_name()
            for task in asyncio.all_tasks()
            if not task.done()
            and task.get_name() in {
                "data-scheduler",
                "portfolio-capture-scheduler",
            }
        }
        return route_rows, active_owner_names, leaked_owner_names

    route_rows, active_owner_names, leaked_owner_names = asyncio.run(_exercise())
    dependencies.get_data_provider_store.cache_clear()
    dependencies.get_dal.cache_clear()
    return {
        "routes": route_rows,
        "active_owners": active_owner_names,
        "leaked_owners": leaked_owner_names,
        "ticks": ticks,
        "provider_calls": provider_calls,
        "network_attempts": network_attempts,
        "capture_events": capture_service.events,
    }


def test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes(
    monkeypatch,
    tmp_path,
):
    observed = _run_local_runtime_lifespan(monkeypatch, tmp_path)

    assert len(observed["routes"]) == 184
    assert observed["active_owners"] == {
        "data-scheduler",
        "portfolio-capture-scheduler",
    }
    assert observed["ticks"] == [[]]


def test_local_runtime_gate_rejects_external_network_and_cleans_owners(
    monkeypatch,
    tmp_path,
):
    observed = _run_local_runtime_lifespan(monkeypatch, tmp_path)

    assert observed["network_attempts"] == []
    assert observed["provider_calls"] == []
    assert observed["leaked_owners"] == set()
    assert observed["capture_events"][0] == "reconciled"
    assert ("tick", True) in observed["capture_events"]


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
        "description": "NVIDIA reported stronger earnings.",
    },
    {
        "date": "2026-07-30T13:00:00+0000",
        "ticker": "NVDA",
        "title": "NVIDIA product update",
        "source": "ibkr",
        "url": "https://example.test/nvda-product",
        "publisher": "Example Desk",
        "description": "NVIDIA announced a product update.",
    },
    {
        "date": "2026-07-30T12:00:00+0000",
        "ticker": "AMD",
        "title": "AMD earnings preview",
        "source": "finnhub",
        "url": "https://example.test/amd-earnings",
        "publisher": "Example Wire",
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
    ):
        del days
        frame = pd.DataFrame(_HERMETIC_NEWS_ROWS)
        if ticker:
            frame = frame[frame["ticker"] == ticker.upper()]
        if source not in ("", "auto", None):
            frame = frame[frame["source"] == source]
        return frame.reset_index(drop=True)

    def query_news_search(self, query="", ticker=None, days=30, limit=20):
        frame = self.query_news(ticker=ticker, days=days, source="auto")
        needle = str(query or "").casefold()
        if needle:
            haystack = (
                frame["title"].fillna("").astype(str)
                + "\n"
                + frame["description"].fillna("").astype(str)
            ).str.casefold()
            frame = frame[haystack.str.contains(needle, regex=False)]
        return frame.head(max(0, int(limit))).reset_index(drop=True)

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


def test_retired_sentiment_and_signal_routes_are_absent_while_raw_news_remains_reachable(
    hermetic_market_app,
):
    routes = {
        (getattr(route, "path", None), method)
        for route in hermetic_market_app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    retired_paths = {
        "/news/{ticker}/sentiment",
        "/signals/{ticker}",
        "/signals/{ticker}/anomalies",
        "/signals/{ticker}/event-chains",
        "/signals/factor-rank",
        "/analysis/run",
    }
    assert not {path for path, _method in routes} & retired_paths

    response = _api_get(hermetic_market_app, "/news/NVDA?days=9999")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert set(payload["articles"][0]).isdisjoint({"sentiment_score", "risk_score"})


# ============================================================
# Health
# ============================================================

class TestHealth:
    def test_status(self, hermetic_market_app):
        r = _api_get(hermetic_market_app, "/status")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["tools_registered"] == 50
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
        backend_type = "LocalMarketBackend"

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
            super().__init__("LocalMarketBackend")
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
            super().__init__("LocalMarketBackend")
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
            super().__init__("LocalMarketBackend")
            self._backend = backend

    out = fr.fundamentals("AAPL", stored=True, dal=_DAL())

    assert out["source_path"] == "none"
    assert out["data_source"] == "none"
    assert out["snapshot_date"] is None
    assert out["roe"] is None
