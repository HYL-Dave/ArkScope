import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("relative", [
    "data_sources/sec_filings.py",
    "data_sources/sec_earnings_releases.py",
    "src/security_lifecycle_news_evidence.py",
    "src/news_identity_repair.py",
])
def test_abandoned_leaf_is_physically_absent(relative):
    assert not (ROOT / relative).exists(), f"abandoned leaf remains: {relative}"


def test_factory_has_no_placeholder_class_or_export():
    tree = ast.parse((ROOT / "src/auth_drivers/factory.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ClassDef) and node.name == "NotImplementedDriver"
        for node in ast.walk(tree)
    ), "obsolete auth factory placeholder remains"
    exported = (ROOT / "src/auth_drivers/__init__.py").read_text(encoding="utf-8")
    assert "NotImplementedDriver" not in exported
