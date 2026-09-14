"""Exercise the current news CLI's real scope resolution without ingestion."""

import sys
from types import SimpleNamespace

import pytest


def assert_news_cli_scope(monkeypatch, expected):
    from src import daily_update, env_keys
    from src.service import data_scheduler

    observed = []

    def collect(source, *, trigger_source, tickers):
        observed.append((source, trigger_source, list(tickers)))
        return {"status": "succeeded"}

    with monkeypatch.context() as patch:
        patch.setattr(sys, "argv", [
            "daily_update", "--massive", "--finnhub", "--scope", "active-universe",
        ])
        patch.setattr(env_keys, "ensure_env_loaded", lambda: None)
        patch.setattr(data_scheduler, "run_source", collect)
        patch.setattr(daily_update, "show_status", lambda: None)
        patch.setattr(daily_update, "_RunTelemetry", lambda **kwargs: SimpleNamespace(
            record=lambda *args, **kwargs: None,
        ))
        with pytest.raises(SystemExit) as stopped:
            daily_update.main()
    assert stopped.value.code == 0
    assert observed == [
        ("polygon_news", "cli", expected), ("finnhub_news", "cli", expected),
    ]
