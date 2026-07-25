from __future__ import annotations

import importlib
import json
from datetime import date, datetime
from importlib import metadata
from pathlib import Path
from zoneinfo import ZoneInfo

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS_PATH = ROOT / "requirements.txt"
FIXTURE_PATH = (
    ROOT / "src" / "market_coverage" / "official_nyse_sessions_v1.json"
)
EASTERN = ZoneInfo("America/New_York")

REVIEWED_SOLUTION = {
    "exchange-calendars": "4.13.2",
    "numpy": "1.26.4",
    "pandas": "2.3.1",
    "pyluach": "2.3.0",
    "toolz": "1.1.0",
    "tzdata": "2025.2",
    "korean-lunar-calendar": "0.4.0",
    "python-dateutil": "2.9.0.post0",
    "pytz": "2025.2",
    "six": "1.17.0",
}
EXPECTED_ORDINARY_SESSION = {
    "date": "2026-07-24",
    "open_et": "09:30",
    "close_et": "16:00",
}
EXPECTED_EARLY_CLOSES = [
    {"date": "2025-07-03", "close_et": "13:00"},
    {"date": "2025-11-28", "close_et": "13:00"},
    {"date": "2025-12-24", "close_et": "13:00"},
    {"date": "2026-11-27", "close_et": "13:00"},
    {"date": "2026-12-24", "close_et": "13:00"},
    {"date": "2027-11-26", "close_et": "13:00"},
]
EXPECTED_EXTRAORDINARY_CLOSURES = ["2025-01-09"]
EXPECTED_SOURCE_URLS = [
    "https://www.nyse.com/trade/hours-calendars",
    "https://www.nyse.com/publicdocs/ICE_NYSE_2025_Yearly_Trading_Calendar.pdf",
    "https://www.nyse.com/publicdocs/nyse/markets/american-options/"
    "rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf",
]


def _requirements() -> list[Requirement]:
    requirements = []
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.partition("#")[0].strip()
        if line:
            requirements.append(Requirement(line))
    return requirements


def _manifest() -> dict:
    assert FIXTURE_PATH.is_file(), f"official fixture manifest missing: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _xnys(manifest: dict):
    exchange_calendars = importlib.import_module("exchange_calendars")
    return exchange_calendars.get_calendar(
        manifest["calendar"],
        start=manifest["reviewed_from"],
        end=manifest["reviewed_through"],
    )


def _time_et(package_timestamp: object) -> str:
    value = package_timestamp.to_pydatetime()
    assert isinstance(value, datetime)
    assert value.tzinfo is not None
    return value.astimezone(EASTERN).strftime("%H:%M")


def test_reviewed_python_dependency_solution_is_exact():
    requirements = _requirements()

    for distribution, expected_version in REVIEWED_SOLUTION.items():
        declarations = [
            requirement
            for requirement in requirements
            if canonicalize_name(requirement.name) == canonicalize_name(distribution)
        ]
        assert len(declarations) == 1, (
            f"expected one requirement for {distribution}, found {declarations}"
        )
        assert str(declarations[0]) == f"{distribution}=={expected_version}"
        assert metadata.version(distribution) == expected_version


def test_exchange_calendar_imports_on_supported_python():
    exchange_calendars = importlib.import_module("exchange_calendars")

    assert callable(exchange_calendars.get_calendar)


def test_xnys_matches_reviewed_full_session_fixture():
    manifest = _manifest()
    assert manifest["ordinary_session"] == EXPECTED_ORDINARY_SESSION
    calendar = _xnys(manifest)
    session = manifest["ordinary_session"]

    assert calendar.is_session(session["date"])
    assert _time_et(calendar.session_open(session["date"])) == session["open_et"]
    assert _time_et(calendar.session_close(session["date"])) == session["close_et"]


def test_xnys_matches_every_reviewed_early_close_fixture():
    manifest = _manifest()
    assert manifest["early_closes"] == EXPECTED_EARLY_CLOSES
    calendar = _xnys(manifest)

    for early_close in manifest["early_closes"]:
        session_date = early_close["date"]
        assert calendar.is_session(session_date)
        assert _time_et(calendar.session_close(session_date)) == early_close["close_et"]


def test_xnys_matches_extraordinary_closure_fixture():
    manifest = _manifest()
    assert manifest["extraordinary_closures"] == EXPECTED_EXTRAORDINARY_CLOSURES
    calendar = _xnys(manifest)

    for closure_date in manifest["extraordinary_closures"]:
        assert not calendar.is_session(closure_date)


def test_fixture_release_horizon_covers_twelve_calendar_months():
    manifest = _manifest()
    source_urls = [source["url"] for source in manifest["metadata"]["sources"]]

    assert manifest["schema_version"] == 1
    assert manifest["calendar"] == "XNYS"
    assert manifest["reviewed_from"] == "2025-01-01"
    assert manifest["reviewed_through"] == "2027-12-31"
    assert source_urls == EXPECTED_SOURCE_URLS

    reviewed_evidence_date = date(2026, 7, 26)
    twelve_month_horizon = reviewed_evidence_date.replace(
        year=reviewed_evidence_date.year + 1
    )
    assert date.fromisoformat(manifest["reviewed_through"]) >= twelve_month_horizon
