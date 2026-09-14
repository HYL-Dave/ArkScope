"""Physical boundaries for the user-approved retirement of old news CLIs."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("leaf", ["__init__.py", "polygon_news.py", "finnhub_news.py"])
def test_old_collector_modules_are_physically_absent(leaf):
    assert not (ROOT / "src" / "collectors" / leaf).exists()


@pytest.mark.parametrize("source", ["polygon_news", "finnhub_news"])
def test_news_source_has_no_retired_adapter_target(source):
    from src.service.data_scheduler import SOURCES

    entry = SOURCES[source]
    assert entry.adapter is None
    assert entry.news_direct_source == source.removesuffix("_news")
    assert entry.universe_tickers and entry.writes_market_db
    assert SOURCES["sec_research_filings"].adapter == (
        "src.sec_research.scheduled", "run_incremental",
    )


def test_current_cli_does_not_advertise_old_collection_entrypoint():
    text = (ROOT / "src" / "daily_update.py").read_text()
    assert "src.collectors." not in text
    assert "data/news/raw" not in text
    assert "News data is up to date!" not in text


def test_current_cli_has_no_obsolete_step_wrapper_or_config_path():
    from src import daily_update

    assert not hasattr(daily_update._RunTelemetry, "timed")
    assert not hasattr(daily_update, "CONFIG_DIR")
