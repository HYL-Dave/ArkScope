"""Read-only, closed projection of repair receipts and actual price coverage."""

from contextlib import closing
from datetime import datetime
from pathlib import Path
import re
import sqlite3

from src import market_data_direct as writer
from src.market_coverage.repair import repair_coverage_available
from src.market_coverage.service import TradingDayCoverageService
from src.price_repair_execution import (
    PriceRepairError, RepairJournal, _digest, load_repair_plan, repair_directory,
)


def _unavailable(repair_id):
    return {"repair_id": repair_id, "state": "unavailable", "reason": "journal_unavailable",
            "scope": None, "requests": None, "coverage": None,
            "resume": {"available": False, "request_limit": 0}}


def _cached_rows_pending(plan, ticker, bars):
    target = next(row for row in plan["preview"]["gaps"] if row["ticker"] == ticker)
    slots = {slot for day in target["missing_dates"] + target["partial_dates"] for slot in plan["slots"][day]}
    timestamps = {row[1] for row in writer._ibkr_bars_to_rows(ticker, bars, "15min") if row[1] in slots}
    if not timestamps:
        return False
    with closing(sqlite3.connect(Path(plan["market_db"]).as_uri() + "?mode=ro", uri=True)) as conn:
        stored = {row[0] for row in conn.execute(
            "SELECT datetime FROM prices WHERE ticker=? AND interval='15min' AND datetime>=? AND datetime<=?",
            (ticker, min(timestamps), max(timestamps)))}
    return bool(timestamps - stored)


def price_repair_status(market_db, repair_id, *, universe, coverage_reader=None):
    """Never dispatch work or infer completion from the number of responses."""
    row = _unavailable(repair_id)
    try:
        directory = repair_directory(market_db, repair_id)
        if directory.parent.is_symlink():
            return row
        plan = load_repair_plan(directory)
        if plan["market_db"] != str(Path(market_db).resolve()):
            return row
        with closing(RepairJournal(directory, plan, readonly=True)) as journal:
            preview = plan["preview"]
            dispatched = {value[0] for value in journal.conn.execute("SELECT request_key FROM dispatches")}
            received = journal.conn.execute("SELECT count(*) FROM responses").fetchone()[0]
            row.update(scope={key: preview[key] for key in ("tickers", "provider", "interval", "as_of_date", "lookback_days")},
                       requests={"planned": len(plan["requests"]), "dispatched": len(dispatched), "received": received,
                                 "unanswered": len(dispatched) - received})
            if not set(preview["tickers"]).issubset(set(universe)):
                row.update(state="blocked", reason="scope_changed")
                return row
            row["reason"] = "coverage_unavailable"
            if coverage_reader is None:
                anchor = datetime.fromisoformat(plan["coverage_at"])
                coverage_reader = TradingDayCoverageService(db_path=market_db, clock=lambda: anchor).get_coverage
            coverage = coverage_reader(universe=preview["tickers"], lookback_days=preview["lookback_days"], interval="15min")
            if (not repair_coverage_available(coverage)
                    or datetime.fromisoformat(coverage.generated_at_et).date().isoformat() != preview["as_of_date"]):
                return row
            gaps = coverage.history_gaps
            row["coverage"] = {"remaining_tickers": sorted(gap.ticker for gap in gaps),
                               "missing_ticker_days": sum(len(gap.missing_dates) for gap in gaps),
                               "partial_ticker_days": sum(len(gap.partial_dates) for gap in gaps)}
            if not gaps:
                row.update(state="complete", reason=None)
                return row
            resumable, request_limit = False, 0
            for gap in gaps:
                try:
                    bars = journal.cached_bars(gap.ticker)
                except PriceRepairError:
                    # Missing responses and failed receipts never authorize a replay.
                    continue
                if bars is None:
                    pending = sum(spec["ticker"] == gap.ticker and _digest(spec) not in dispatched for spec in plan["requests"])
                    resumable |= pending > 0
                    request_limit += pending
                else:
                    resumable |= _cached_rows_pending(plan, gap.ticker, bars)
            reason = ("unconfirmed_requests" if row["requests"]["unanswered"] else
                      None if resumable else "response_incomplete")
            row.update(state="incomplete", reason=reason, resume={"available": resumable, "request_limit": request_limit})
            return row
    except (PriceRepairError, OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        # A corrupt operation must not suppress other operations in the history.
        return row


def list_price_repairs(market_db, *, universe, coverage_reader=None, limit=5, offset=0):
    if type(limit) is not int or not 1 <= limit <= 20 or type(offset) is not int or offset < 0:
        raise ValueError("price_repair_page")
    root = Path(market_db).resolve().parent / "price_repairs"
    if root.is_symlink():
        raise PriceRepairError("price_repair_integrity")
    entries = [] if not root.exists() else [entry for entry in root.iterdir() if re.fullmatch(r"[a-f0-9]{32}", entry.name)]
    entries.sort(key=lambda entry: (entry.lstat().st_mtime_ns, entry.name), reverse=True)
    universe = tuple(universe)
    return {"version": 1, "operations": [price_repair_status(market_db, entry.name, universe=universe, coverage_reader=coverage_reader)
                                          for entry in entries[offset:offset + limit]],
            "total": len(entries), "offset": offset, "has_more": offset + limit < len(entries)}
