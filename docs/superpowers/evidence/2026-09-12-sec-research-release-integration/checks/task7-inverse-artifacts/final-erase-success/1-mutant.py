"""SEC-owned append-only batch checkpoints; reads never install or acquire."""

import json
import math
import re

from . import schema
from .capture_lock import store_operation
from .common import normalize_cik
from .store import _bounded_json, _timestamp


FORMS = ("10-K", "10-Q", "20-F", "40-F")
MAX_MEMBERS = 100000
_KEYS = set("batch_id status started_at finished_at acquired_at universe_tickers universe_status rotation scope forms attempted_ciks confirmed_ciks failed_ciks deferred_ciks unresolved outcomes request_count filing_count fact_count gaps stop_reason elapsed_seconds issuer_map_observation_id".split())


def _require(condition):
    if not condition:
        raise ValueError("sec_schedule_batch_invalid")


def normalize_member(value):
    """Bound observed universe text without applying SEC identifier admission."""
    _require(isinstance(value, str))
    value = value.strip().upper()
    _require(1 <= len(value) <= 256 and value.isprintable())
    return value


def receipt_counts(store, receipt):
    counts = dict(filing_count=0, fact_count=0)
    forms = (*FORMS, *(form + "/A" for form in FORMS))
    with store.connect(readonly=True) as conn:
        for source, binding in receipt["source_snapshots"].items():
            store.bound_snapshot(receipt["cik"], source, binding)
            table, key = (("sec_research_facts", "fact_count") if source == "companyfacts"
                          else ("sec_research_filings", "filing_count"))
            counts[key] += conn.execute(f"""SELECT COUNT(*) FROM {table}
                WHERE snapshot_id=? AND form IN (?,?,?,?,?,?,?,?)""",
                (binding["snapshot_id"], *forms)).fetchone()[0]
    return counts


def validate_batch(batch, store=None, *, cache=None):
    """Validate bounded shape and, when reading, JSON-hidden receipt/map edges."""
    try:
        _require(type(batch) is dict and set(batch) == _KEYS)
        _require(isinstance(batch["batch_id"], str) and re.fullmatch(r"[a-f0-9]{32}", batch["batch_id"]))
        _require(batch["scope"] == "recent" and batch["forms"] == list(FORMS))
        _require(batch["status"] in ("running", "succeeded", "partial", "failed"))
        _require(batch["universe_status"] in ("unknown", "available", "unavailable"))
        _timestamp(batch["started_at"])
        for key in ("finished_at", "acquired_at"):
            if batch[key] is not None:
                _timestamp(batch[key])
        _require((batch["finished_at"] is None) == (batch["status"] == "running"))
        for key, maximum in (("request_count", 1001), ("filing_count", 50000000), ("fact_count", 50000000)):
            _require(type(batch[key]) is int and 0 <= batch[key] <= maximum)
        elapsed = batch["elapsed_seconds"]
        _require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0)
        _require(batch["stop_reason"] in (None, "issuer_limit", "request_limit", "deadline", "cancelled",
            "capture_budget_exceeded", "storage_space_insufficient", "capture_store_write_failed"))
        for key in ("universe_tickers", "rotation", "deferred_ciks", "unresolved", "gaps"):
            _require(type(batch[key]) is list and len(batch[key]) <= MAX_MEMBERS + 1001)
        members = batch["universe_tickers"]
        _require(len(set(members)) == len(members))
        for member in members:
            _require(member == normalize_member(member))
        for key in ("attempted_ciks", "confirmed_ciks", "failed_ciks", "deferred_ciks"):
            values = batch[key]
            _require(type(values) is list and len(values) <= (MAX_MEMBERS if key == "deferred_ciks" else 500))
            _require(len(set(values)) == len(values) and all(normalize_cik(cik) == cik for cik in values))
        attempted, confirmed, failed, deferred = (set(batch[key]) for key in
            ("attempted_ciks", "confirmed_ciks", "failed_ciks", "deferred_ciks"))
        _require(not confirmed & failed and not attempted & deferred and confirmed | failed <= attempted)
        rotation = batch["rotation"]
        _require(all(type(row) is dict and set(row) == {"cik", "tickers"} for row in rotation))
        _require(len({row["cik"] for row in rotation}) == len(rotation))
        for row in rotation:
            _require(normalize_cik(row["cik"]) == row["cik"] and type(row["tickers"]) is list
                     and 1 <= len(row["tickers"]) <= MAX_MEMBERS)
            _require(all(ticker == normalize_member(ticker) for ticker in row["tickers"]))
            if batch["universe_status"] == "available":
                _require(set(row["tickers"]) <= set(members))
        for row in batch["unresolved"]:
            _require(type(row) is dict and set(row) == {"ticker", "candidates", "code"}
                     and row["ticker"] in members and type(row["candidates"]) is list
                     and len(row["candidates"]) <= MAX_MEMBERS and isinstance(row["code"], str)
                     and re.fullmatch(r"[a-z_]{1,80}", row["code"]))
            _require(all(normalize_cik(cik) == cik for cik in row["candidates"]))
        for gap in batch["gaps"]:
            _require(type(gap) is dict and {"code"} <= set(gap) <= {"code", "cik", "source"}
                     and isinstance(gap["code"], str) and re.fullmatch(r"[a-z_]{1,80}", gap["code"]))
            if "cik" in gap:
                _require(gap["cik"] in attempted)
            if "source" in gap:
                _require(gap["source"] in ("submissions", "companyfacts"))
        outcomes = batch["outcomes"]
        _require(type(outcomes) is list and len(outcomes) <= 500)
        _require(len({row["cik"] for row in outcomes}) == len(outcomes))
        cache = {} if cache is None else cache
        for row in outcomes:
            _require(set(row) == {"cik", "receipt_id", "status", "completed_sources", "filing_count", "fact_count"}
                     and row["cik"] in attempted and row["status"] in ("ok", "partial", "unavailable"))
            for key, maximum in (("completed_sources", 2), ("filing_count", 100000), ("fact_count", 100000)):
                _require(type(row[key]) is int and 0 <= row[key] <= maximum)
            if row["receipt_id"] is None:
                _require(row["status"] == "unavailable" and row["completed_sources"] == 0
                         and row["filing_count"] == row["fact_count"] == 0
                         and any(gap.get("cik") == row["cik"] for gap in batch["gaps"]))
            else:
                _require(type(row["receipt_id"]) is int and 1 <= row["receipt_id"] <= 2**63 - 1)
            if store is not None and row["receipt_id"] is not None:
                identity = (row["cik"], row["receipt_id"])
                if identity not in cache:
                    receipt = store.receipt(*identity)
                    _require(receipt is not None and receipt["scope"] == "recent")
                    cache[identity] = (receipt, receipt_counts(store, receipt))
                receipt, counts = cache[identity]
                _require(row["status"] == receipt["status"] and row["completed_sources"] == len(receipt["completed"])
                         and all(row[key] == counts[key] for key in counts))
        _require(all(batch[key] == sum(row[key] for row in outcomes) for key in ("filing_count", "fact_count")))
        _require(confirmed == {row["cik"] for row in outcomes if row["status"] == "ok"})
        _require(failed == {row["cik"] for row in outcomes if row["status"] != "ok"})
        _require(bool(confirmed) == (batch["acquired_at"] is not None))
        _require(2 * len(confirmed) <= batch["request_count"] <= 1 + 2 * len(attempted))
        if batch["status"] != "running":
            _require(attempted == confirmed | failed)
            _require(batch["status"] != "succeeded" or batch["universe_status"] == "available")
            incomplete = bool(failed or deferred or batch["unresolved"] or batch["gaps"] or batch["stop_reason"])
            acquired = any(row["completed_sources"] for row in outcomes)
            _require(batch["status"] == (("partial" if acquired else "failed") if incomplete else "succeeded"))
        observation_id = batch["issuer_map_observation_id"]
        if observation_id is not None:
            _require(type(observation_id) is int and 1 <= observation_id <= 2**63 - 1)
            if store is not None:
                with store.connect(readonly=True) as conn:
                    _require(conn.execute("SELECT 1 FROM sec_research_issuer_maps WHERE observation_id=?", (observation_id,)).fetchone())
    except (KeyError, TypeError, ValueError, RecursionError):
        raise ValueError("sec_schedule_batch_invalid") from None
    return batch


class ScheduleStore:
    def __init__(self, store):
        self.store = store
        self.paths = store.paths

    def record(self, batch):
        validate_batch(batch)
        payload = _bounded_json(batch)
        with self.store._write() as conn:
            conn.execute("""INSERT INTO sec_research_schedule_batches
                (batch_id,status,acquired_at,payload) VALUES (?,?,?,?)""",
                (batch["batch_id"], batch["status"], batch["acquired_at"], payload))
        return json.loads(payload)

    def _read_row(self, row):
        try:
            batch = validate_batch(json.loads(row["payload"]), self.store)
            _require(all(row[key] == batch[key] for key in ("batch_id", "status", "acquired_at")))
            return batch
        except (ValueError, TypeError, KeyError, RecursionError):
            raise ValueError("sec_schedule_batch_invalid") from None

    @store_operation
    def status(self):
        result = {"last_attempt": None, "last_acquisition_at": None, "last_completed_batch": None}
        if not self.paths.market_db_path.exists():
            return result
        with self.store.connect(readonly=True) as conn:
            if not schema._owned(conn):
                return result
            schema.verify(conn)
            row = conn.execute("SELECT * FROM sec_research_schedule_batches ORDER BY checkpoint_id DESC LIMIT 1").fetchone()
            if row:
                result["last_attempt"] = self._read_row(row)
            row = conn.execute("""SELECT * FROM sec_research_schedule_batches
                ORDER BY checkpoint_id DESC LIMIT 1""").fetchone()
            if row:
                result["last_acquisition_at"] = self._read_row(row)["acquired_at"]
            row = conn.execute("""SELECT * FROM sec_research_schedule_batches
                WHERE status='succeeded' ORDER BY checkpoint_id DESC LIMIT 1""").fetchone()
            if row:
                result["last_completed_batch"] = self._read_row(row)
        return result
