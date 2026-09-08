"""Opt-in stale-provenance control; run via the no-egress offline_check harness."""

import pytest


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if item.path.name != "test_data_scheduler.py":
        return (yield)

    from src import env_keys

    original = env_keys._loaded_keys
    env_keys._loaded_keys = original | {
        "MASSIVE_API_KEY", "FINNHUB_API_KEY", "IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID",
    }
    try:
        return (yield)
    finally:
        env_keys._loaded_keys = original
