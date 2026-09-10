"""Spent operator entrypoints must not return to the runtime source tree."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPENT_MODULES = (
    "src/audit/sa_article_reconciliation.py",
    "src/audit/universe_retirement.py",
    "src/audit/ibkr_news_catchup_audit.py",
    "src/monitor/scheduler.py",
)


@pytest.mark.parametrize("relative", SPENT_MODULES)
def test_spent_module_is_absent(relative):
    assert not (ROOT / relative).exists()
