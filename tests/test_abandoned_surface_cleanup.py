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
