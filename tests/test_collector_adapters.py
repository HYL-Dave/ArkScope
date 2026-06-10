"""Tests for the import-safe collector modules (in-process provider adapters).

The news collectors are imported by the sidecar and called in-process by the
scheduler — these tests pin the import-safety contract and the run_incremental
fast paths WITHOUT any network/API access.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytest

import scripts.collection.collect_finnhub_news as cfn
import scripts.collection.collect_polygon_news as cpn


def test_import_is_side_effect_free():
    # Importing must not reconfigure root logging (the old module-level
    # basicConfig added a cwd-relative FileHandler at import) — pin that the
    # config now lives behind _setup_cli_logging(), called only by main().
    for mod in (cpn, cfn):
        assert callable(mod.run_incremental)
        assert callable(mod._setup_cli_logging)
        src = open(mod.__file__).read()
        head = src.split("def _setup_cli_logging")[0]
        assert "basicConfig" not in head, f"{mod.__name__}: basicConfig at import time"


def test_paths_are_repo_anchored():
    # cwd-independence: the sidecar calls these from an arbitrary cwd.
    assert cpn.CollectionConfig().data_dir.is_absolute()
    assert cpn.CollectionConfig().checkpoint_dir.is_absolute()
    assert cfn.FinnhubConfig().data_dir.is_absolute()
    assert str(cpn.CollectionConfig().data_dir).endswith("data/news/raw/polygon")
    assert str(cfn.FinnhubConfig().data_dir).endswith("data/news/raw/finnhub")


def test_polygon_up_to_date_short_circuit(monkeypatch):
    # latest article in the future → up_to_date, NO collector construction,
    # no API key needed, no network.
    monkeypatch.setattr(cpn.StorageManager, "get_latest_timestamp",
                        lambda self: datetime.now() + timedelta(seconds=30))
    monkeypatch.setattr(cpn, "PolygonNewsCollector",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("collector constructed")))
    out = cpn.run_incremental()
    assert out == {"mode": "up_to_date", "new_articles": 0}


def test_polygon_missing_key_raises(monkeypatch):
    monkeypatch.setattr(cpn.StorageManager, "get_latest_timestamp",
                        lambda self: datetime.now() - timedelta(hours=6))
    monkeypatch.setattr(cpn, "load_env", lambda: "")
    with pytest.raises(RuntimeError, match="POLYGON_API_KEY"):
        cpn.run_incremental()


def test_finnhub_up_to_date_short_circuit(monkeypatch):
    monkeypatch.setattr(cfn.StorageManager, "get_latest_timestamp",
                        lambda self: datetime.now() + timedelta(seconds=30))
    monkeypatch.setattr(cfn, "collect_news",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("collect_news called")))
    out = cfn.run_incremental()
    assert out == {"mode": "up_to_date", "new_articles": 0}


def test_finnhub_missing_key_raises(monkeypatch):
    monkeypatch.setattr(cfn.StorageManager, "get_latest_timestamp",
                        lambda self: datetime.now() - timedelta(days=2))
    monkeypatch.setattr(cfn, "load_env", lambda: "")
    with pytest.raises(RuntimeError, match="FINNHUB_API_KEY"):
        cfn.run_incremental()


def test_finnhub_incremental_window_capped_at_7_days(monkeypatch):
    # 30 days behind → window capped at 7 (Finnhub free-tier history limit)
    seen = {}

    def _fake_collect(tickers, start_date, end_date):
        seen["window_days"] = (end_date - start_date).days
        return {"total_articles": 5}

    monkeypatch.setattr(cfn.StorageManager, "get_latest_timestamp",
                        lambda self: datetime.now() - timedelta(days=30))
    monkeypatch.setattr(cfn, "collect_news", _fake_collect)
    monkeypatch.setattr(cfn, "load_tickers", lambda arg=None: ["AAPL"])
    monkeypatch.setattr(cfn, "_save_collection_stats", lambda *a, **k: "/dev/null")
    out = cfn.run_incremental()
    assert out == {"mode": "incremental", "new_articles": 5}
    assert seen["window_days"] == 7
