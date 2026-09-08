"""Prepare, never execute, the separately authorized recent-price operation."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.market_coverage.models import CoverageDayV2, CoverageHistoryGapV2
from src.price_repair_execution import build_repair_plan


def require(condition):
    if not condition:
        raise ValueError("recent_price_manifest_mismatch")


def prepare(inventory, summary, market_db, expected_preview_sha256):
    observed = inventory["coverage"]["current_15"]
    expected = summary["coverage"]["current_15"]
    require(summary["status"] == "readonly_inventory_complete_no_execution")
    at = datetime.fromisoformat(summary["at"])
    require(at.tzinfo is not None)
    require(expected["lookback_days"] == 15 and expected["as_of_date"] == "2026-09-05")
    require(expected["observation_health"] == expected["calendar_health"] == "ok")
    require(expected["preview_sha256"] == observed["preview"]["preview_sha256"] == expected_preview_sha256)
    gaps = [CoverageHistoryGapV2.model_validate(row) for row in observed["history_gaps"]]
    days = [CoverageDayV2.model_validate(row) for row in observed["days"]]
    require(len({row.date for row in days}) == len(days))
    dates = {day for row in gaps for day in row.missing_dates + row.partial_dates}
    require(dates and all("2026-08-21" <= day <= "2026-08-28" for day in dates))
    require(set(observed["preview"]["tickers"]) <= set(inventory["sources_by_ticker"]))
    coverage = SimpleNamespace(
        generated_at_et=at.astimezone(ZoneInfo("America/New_York")).isoformat(),
        interval="15min", lookback_days=15, days=days, history_gaps=gaps,
        observation_health=SimpleNamespace(status="ok"), calendar_health=SimpleNamespace(status="ok"),
    )
    plan = build_repair_plan(coverage, market_db)
    require(plan["preview"] == observed["preview"])
    require(len(plan["preview"]["tickers"]) == expected["repair_tickers"])
    require(sum(len(row.missing_dates) for row in gaps) == expected["missing_ticker_days"])
    require(sum(len(row.partial_dates) for row in gaps) == expected["partial_ticker_days"])
    windows = Counter((row["start"], row["end"]) for row in plan["windows"].values())
    public = {
        "status": "prepared_not_authorized_for_execution", "plan_sha256": plan["plan_sha256"],
        "preview_sha256": plan["preview"]["preview_sha256"], "inventory_at": summary["at"],
        "ticker_count": len(plan["preview"]["tickers"]),
        "missing_ticker_days": expected["missing_ticker_days"], "partial_ticker_days": expected["partial_ticker_days"],
        "date_counts": dict(sorted(Counter(day for row in gaps for day in row.missing_dates + row.partial_dates).items())),
        "windows": [{"start": start, "end": end, "tickers": count} for (start, end), count in sorted(windows.items())],
        "max_insertable_slots": sum(len(plan["slots"][day]) for row in gaps for day in row.missing_dates + row.partial_dates),
        "request_budget": plan["request_budget"], "gateway_connection_attempts_per_execution": 1,
        "pacing_seconds": plan["pacing_seconds"], "retry": False, "fallback": False,
        "unknown_dispatch_may_repeat": False, "received_results_reusable": True,
        "production_reads": 0, "production_writes": 0, "provider_requests": 0,
        "scope_source": "previously_authorized_immutable_post_disposition_inventory",
    }
    return plan, public


def private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--market-db", required=True, type=Path)
    parser.add_argument("--expected-preview-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inventory, summary = args.inventory.read_bytes(), args.summary.read_bytes()
    plan, public = prepare(json.loads(inventory), json.loads(summary), args.market_db, args.expected_preview_sha256)
    public["inventory_sha256"] = hashlib.sha256(inventory).hexdigest()
    public["summary_sha256"] = hashlib.sha256(summary).hexdigest()
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    private_write(args.output / "plan.json", plan)
    private_write(args.output / "summary.json", public)
    print(json.dumps(public, sort_keys=True))


if __name__ == "__main__":
    main()
