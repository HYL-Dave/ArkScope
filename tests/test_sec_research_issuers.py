"""Issuer-map observations over disposable canonical stores and raw SEC bytes."""

import hashlib
import importlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from data_sources.sec_transport import SecResponse
from src.sec_research.captures import CaptureStore
from src.sec_research.paths import SecResearchPaths
from src.sec_research.store import Store


NOW = "2026-09-12T12:00:00Z"
MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def owner(name):
    assert importlib.util.find_spec("src.sec_research." + name), f"missing Task 1 {name} contract"
    return importlib.import_module("src.sec_research." + name)


def map_body(*rows):
    return json.dumps({str(i): {"cik_str": cik, "ticker": ticker, "title": "Fixture issuer"}
                       for i, (ticker, cik) in enumerate(rows)}).encode()


class Transport:
    def __init__(self, responses):
        self.responses, self.calls = responses, []
        self.before = None

    def get(self, url):
        self.calls.append(url)
        if self.before:
            self.before(url)
        result = self.responses[url]
        if isinstance(result, BaseException):
            raise result
        return result if isinstance(result, SecResponse) else SecResponse(200, result)


@pytest.fixture
def issuer_fixture(tmp_path):
    issuer_type = owner("issuer_store").IssuerStore
    store = Store(SecResearchPaths(tmp_path / "market.db"))
    store.install()
    captures = CaptureStore(store, budget=lambda: 1024**2, free_bytes=lambda _: 1024**3)
    transport = Transport({MAP_URL: map_body(("DUP", 1), ("DUP", 2))})
    issuers = issuer_type(store)
    return SimpleNamespace(store=store, captures=captures, transport=transport, issuers=issuers)


def test_ambiguous_map_never_selects_last_cik(tmp_path):
    f = issuer_fixture.__wrapped__(tmp_path)
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    result = f.issuers.resolve("dup")
    assert result["status"] == "unavailable"
    assert result["cik"] is None
    assert result["candidates"] == ["0000000001", "0000000002"]
    assert result["source"] == {"url": MAP_URL, "sha256": hashlib.sha256(f.transport.responses[MAP_URL]).hexdigest()}
    assert result["observed_at"] == NOW
    assert f.captures.read(result["source"]["sha256"]) == f.transport.responses[MAP_URL]


@pytest.mark.parametrize("value,expected", [
    (" cik:320193 ", ("cik", "0000320193")), ("1", ("cik", "0000000001")),
    ("brk.b", ("ticker", "BRK.B")), ("BRK-B", ("ticker", "BRK-B")),
    ("123A", ("ticker", "123A")),
])
def test_issuer_normalization(value, expected):
    assert owner("issuers").parse_issuer(value) == expected


@pytest.mark.parametrize("value", [None, True, 123, "", "0", "CIK:AAPL", "１２３", "https://sec.gov", "-A", "A" * 21])
def test_invalid_issuer(value):
    with pytest.raises(ValueError):
        owner("issuers").parse_issuer(value)


@pytest.mark.parametrize("body", [b"[]", b'{"0":{}}', b'{"0":{},"0":{}}',
    map_body(("aapl", 1)), map_body(("AAPL", True)), map_body(("AAPL", 0)),
    b'{"0":{"cik_str":1,"ticker":"A","title":null}}'])
def test_invalid_map_is_not_smaller_success(body):
    parser = owner("issuers").parse_ticker_map
    with pytest.raises(ValueError):
        parser(body)


def test_map_failure_is_latest_and_retains_invalid_body(issuer_fixture):
    f = issuer_fixture
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    f.transport.responses[MAP_URL] = b'{"invalid":"PRIVATE"}'
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    result = f.issuers.resolve("DUP")
    assert result["cik"] is None and result["candidates"] == []
    assert result["gaps"] == [{"code": "issuer_map_invalid"}]
    assert f.captures.read(result["source"]["sha256"]) == b'{"invalid":"PRIVATE"}'
    assert "PRIVATE" not in json.dumps(result)


def test_map_intent_blocks_old_success_during_dispatch(issuer_fixture):
    f = issuer_fixture
    f.transport.responses[MAP_URL] = map_body(("A", 1))
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    observations = []
    f.transport.before = lambda _: observations.append(f.issuers.resolve("A"))
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    assert observations[0]["status"] == "unavailable"
    assert observations[0]["cik"] is None
    assert f.issuers.resolve("A")["cik"] == "0000000001"


def test_explicit_cik_never_opens_storage(tmp_path):
    store = Store(SecResearchPaths(tmp_path / "absent" / "market.db"))
    result = owner("issuer_store").IssuerStore(store).resolve("CIK:1")
    assert result["cik"] == "0000000001" and result["status"] == "ok"
    assert list(tmp_path.iterdir()) == []


def test_uninstalled_map_resolution_is_stored_unavailable_without_creation(tmp_path):
    store = Store(SecResearchPaths(tmp_path / "absent" / "market.db"))
    try:
        result = owner("issuer_store").IssuerStore(store).resolve("AAPL")
    except sqlite3.Error:
        result = None
    assert result is not None, "missing map storage must return an unavailable observation"
    assert result["status"] == "unavailable" and result["cik"] is None
    assert result["gaps"] == [{"code": "issuer_map_unobserved"}]
    assert list(tmp_path.iterdir()) == []


def test_symbols_do_not_guess_dot_hyphen_aliases(issuer_fixture):
    f = issuer_fixture
    f.transport.responses[MAP_URL] = map_body(("BRK-B", 1))
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    assert f.issuers.resolve("BRK.B")["cik"] is None
    assert f.issuers.resolve("BRK-B")["cik"] == "0000000001"


def test_map_lease_is_separate_and_does_not_hold_market_transaction(issuer_fixture):
    f = issuer_fixture
    nested = []
    def during_request(_):
        with f.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
        with pytest.raises(ValueError, match="issuer_map_busy"):
            f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
        nested.append(True)
    f.transport.before = during_request
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    assert nested == [True] and f.transport.calls == [MAP_URL]


def test_map_records_are_immutable_and_quota_charged(issuer_fixture):
    f = issuer_fixture
    f.issuers.refresh(f.transport, f.captures, clock=lambda: NOW, check=None)
    charged = f.captures.status()["charged_bytes"]
    assert charged == len(f.transport.responses[MAP_URL])
    with f.store.connect() as conn:
        for sql in ("UPDATE sec_research_issuer_maps SET status='unavailable'",
                    "DELETE FROM sec_research_issuer_maps",
                    "INSERT OR REPLACE INTO sec_research_issuer_maps SELECT * FROM sec_research_issuer_maps"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                conn.execute(sql)
