"""Structural regression tests for the SA Alpha Picks extension flow."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = ROOT / "extensions" / "sa_alpha_picks" / "background.js"
SCRAPER = ROOT / "extensions" / "sa_alpha_picks" / "scrape.js"
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_fixture.mjs"
FIXTURES = ROOT / "tests" / "fixtures" / "sa_alpha_picks"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_scraper(fixture: Path, url: str, *, check: bool = True):
    env = os.environ.copy()
    env["ARKSCOPE_FIXTURE_URL"] = url
    completed = subprocess.run(
        ["node", str(RUNNER), str(fixture), str(SCRAPER)],
        cwd=ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout) if check else completed


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


def test_alpha_picks_scraper_parses_live_company_column_shape():
    current = _run_scraper(
        FIXTURES / "current_portfolio_company_column.html",
        "https://seekingalpha.com/alpha-picks/picks/current",
    )
    removed = _run_scraper(
        FIXTURES / "removed_portfolio_company_column.html",
        "https://seekingalpha.com/alpha-picks/picks/removed",
    )

    assert current == [
        {
            "company": "",
            "symbol": "ACME",
            "picked_date": "2026-07-15",
            "return_pct": 3.12,
            "sector": "Health Care",
            "sa_rating": "STRONG BUY",
            "holding_pct": 0.38,
            "detail_url": "https://seekingalpha.com/alpha-picks/acme-analysis",
            "raw_data": {
                "cells": [
                    "",
                    "ACME",
                    "07/15/2026",
                    "3.12%",
                    "Health Care",
                    "STRONG BUY",
                    "0.38%",
                    "Open",
                ],
                "detail_url": "https://seekingalpha.com/alpha-picks/acme-analysis",
            },
        }
    ]
    assert removed == [
        {
            "company": "",
            "symbol": "EXIT",
            "picked_date": "2024-10-15",
            "closed_date": "2026-07-17",
            "return_pct": 356.94,
            "sector": "Industrials",
            "sa_rating": "HOLD",
            "holding_pct": None,
            "detail_url": "https://seekingalpha.com/alpha-picks/exit-analysis",
            "raw_data": {
                "cells": [
                    "",
                    "EXIT",
                    "10/15/2024",
                    "07/17/2026",
                    "356.94%",
                    "Industrials",
                    "HOLD",
                    "Open",
                ],
                "detail_url": "https://seekingalpha.com/alpha-picks/exit-analysis",
            },
        },
        {
            "company": "",
            "symbol": "SMCI*",
            "picked_date": "2022-11-15",
            "closed_date": "2024-10-30",
            "return_pct": 301.41,
            "sector": "Information Technology",
            "sa_rating": "HOLD",
            "holding_pct": None,
            "detail_url": "https://seekingalpha.com/alpha-picks/smci-exit-analysis",
            "raw_data": {
                "cells": [
                    "",
                    "SMCI*",
                    "11/15/2022",
                    "10/30/2024",
                    "301.41%",
                    "Information Technology",
                    "HOLD",
                    "Open",
                ],
                "detail_url": "https://seekingalpha.com/alpha-picks/smci-exit-analysis",
            },
        },
    ]


def test_alpha_picks_scraper_fails_closed_when_visible_rows_parse_to_zero(tmp_path):
    fixture = tmp_path / "unparseable-portfolio.html"
    fixture.write_text(
        """<table><tbody><tr>
        <td></td><td>not a ticker</td><td>not a date</td>
        <td>n/a</td><td>Unknown</td><td>n/a</td>
        </tr></tbody></table>""",
        encoding="utf-8",
    )

    completed = _run_scraper(
        fixture,
        "https://seekingalpha.com/alpha-picks/picks/current",
        check=False,
    )

    assert completed.returncode != 0
    assert "rows were present but none could be parsed" in completed.stderr
