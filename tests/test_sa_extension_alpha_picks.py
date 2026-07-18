"""Structural regression tests for the SA Alpha Picks extension flow."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = ROOT / "extensions" / "sa_alpha_picks" / "background.js"
SCRAPER = ROOT / "extensions" / "sa_alpha_picks" / "scrape.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_alpha_picks_flow_waits_for_dom_readiness_not_tab_complete():
    text = _read(BACKGROUND)
    assert "waitForAlphaPicksTableReady" in text
    assert "ALPHA_PICKS_PAGE_TIMEOUT_MS" in text
    assert "waitForTabLoad(tabId, 30000, expectedPathFromUrl(SA_CURRENT_URL))" not in text
    assert "waitForTabLoad(tabId, 30000, expectedPathFromUrl(SA_CLOSED_URL))" not in text


def test_alpha_picks_timeout_reports_actionable_page_diagnostics():
    text = _read(BACKGROUND)
    for marker in (
        "selectorCounts",
        "documentReadyState",
        "bodySnippet",
        "formatAlphaPicksReadinessTimeout",
    ):
        assert marker in text


def test_alpha_picks_scraper_supports_non_table_row_fallback():
    text = _read(SCRAPER)
    assert "collectCandidateRows" in text
    assert "role=\"row\"" in text
    assert "role=\"gridcell\"" in text
    background = _read(BACKGROUND)
    compact = " ".join(background.split())
    assert 'files: ["article_identity.js", "scrape_articles_list.js"]' in compact
    assert 'files: ["article_identity.js", "scrape_detail.js"]' in compact
