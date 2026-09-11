"""Immutable structured SEC observations and append-only refresh receipts."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3

from src.market_data_direct import market_write_lock

from . import schema
from .catalog import CatalogSnapshot
from .common import normalize_cik
from .facts import FactsSnapshot
from .paths import SecResearchPaths


MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_ROWS = 100000


def _json(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError):
        raise ValueError("sec_research_payload_invalid") from None


def _bounded_json(value) -> str:
    encoded = _json(value)
    try:
        size = len(encoded.encode("utf-8"))
    except UnicodeError:
        raise ValueError("sec_research_payload_invalid") from None
    if size > MAX_SNAPSHOT_BYTES:
        raise ValueError("sec_research_snapshot_bytes_exceeded")
    return encoded


def _timestamp(value) -> str:
    if not isinstance(value, str):
        raise ValueError("sec_research_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise ValueError("sec_research_timestamp_invalid") from None


def _receipt_fields(cik, status, completed, pending, gaps):
    def locators(value):
        return isinstance(value, list) and all(
            isinstance(item, str) and (item in ("submissions", "companyfacts")
            or re.fullmatch(r"CIK" + cik + r"-submissions-[0-9]+\.json", item))
            for item in value)
    if (status not in ("ok", "partial", "unavailable") or not locators(completed)
            or not locators(pending) or not isinstance(gaps, list)
            or len(set(completed)) != len(completed) or len(set(pending)) != len(pending)
            or set(completed) & set(pending)
            or any(not isinstance(gap, dict) for gap in gaps)):
        raise ValueError("sec_research_receipt_invalid")


def _receipt(row) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    try:
        if (type(result["receipt_id"]) is not int or not 1 <= result["receipt_id"] <= 2**63 - 1
                or normalize_cik(result["cik"]) != result["cik"]):
            raise ValueError
        for key in ("completed", "pending", "gaps", "source_snapshots"):
            if not isinstance(result[key], str):
                raise ValueError
            result[key] = json.loads(result[key])
        _receipt_fields(result["cik"], result["status"], result["completed"], result["pending"], result["gaps"])
        for key in ("observed_at", "recorded_at"):
            _timestamp(result[key])
        bindings = result["source_snapshots"]
        if (not isinstance(bindings, dict)
                or bindings and set(bindings) != set(result["completed"])):
            raise ValueError
        for binding in bindings.values():
            _binding_shape(binding)
    except (ValueError, RecursionError):
        raise ValueError("sec_research_receipt_binding_invalid") from None
    return result


def _snapshot(row):
    if row is None:
        return None
    result = dict(row)
    result["historical_files"] = json.loads(result["historical_files"])
    result["historical_files_observed"] = bool(result["historical_files_observed"])
    return result


def _binding_shape(binding):
    if (not isinstance(binding, dict) or set(binding) != {"snapshot_id", "observed_at"}
            or not isinstance(binding["snapshot_id"], str)
            or re.fullmatch(r"secsnapshot_[0-9a-f]{64}", binding["snapshot_id"]) is None):
        raise ValueError("sec_research_receipt_binding_invalid")
    try:
        return {"snapshot_id": binding["snapshot_id"], "observed_at": _timestamp(binding["observed_at"])}
    except ValueError:
        raise ValueError("sec_research_receipt_binding_invalid") from None


def _bound_snapshot(conn, cik, locator, binding):
    row = conn.execute("SELECT * FROM sec_research_snapshots WHERE snapshot_id=? AND cik=?",
                       (binding["snapshot_id"], cik)).fetchone()
    kind = "facts" if locator == "companyfacts" else "catalog"
    historical_name = None if locator in ("submissions", "companyfacts") else locator
    if row is None or row["kind"] != kind or row["historical_name"] != historical_name:
        raise ValueError("sec_research_receipt_binding_invalid")
    return _snapshot(row)


class Store:
    def __init__(self, paths: SecResearchPaths):
        self.paths = paths

    @contextmanager
    def connect(self, readonly=False):
        """Yield a caller-committed connection and always explicitly close it."""
        path = self.paths.market_db_path
        conn = sqlite3.connect(
            path.as_uri() + "?mode=ro" if readonly else str(path),
            uri=readonly, isolation_level=None,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            if readonly:
                conn.execute("PRAGMA query_only=ON")
            yield conn
        finally:
            conn.close()

    def install(self):
        with market_write_lock():
            self.paths.market_db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as conn:
                schema.install(conn)

    @contextmanager
    def _write(self):
        with market_write_lock(), self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                schema.verify(conn)
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def publish(self, snapshot, *, object_sha256, observed_at, source_url):
        if not isinstance(snapshot, (CatalogSnapshot, FactsSnapshot)):
            raise ValueError("sec_research_snapshot_invalid")
        kind = "catalog" if isinstance(snapshot, CatalogSnapshot) else "facts"
        rows = snapshot.filings if kind == "catalog" else snapshot.facts
        history = snapshot.historical_files if kind == "catalog" else ()
        if len(rows) + len(history) > MAX_SNAPSHOT_ROWS:
            raise ValueError("sec_research_snapshot_rows_exceeded")
        if (not isinstance(object_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", object_sha256) is None
                or object_sha256 != snapshot.sha256
                or any(row.source.sha256 != object_sha256 for row in (*rows, *history))):
            raise ValueError("sec_research_object_hash_mismatch")
        cik = normalize_cik(snapshot.cik)
        if cik != snapshot.cik or any(row.cik != cik for row in rows):
            raise ValueError("sec_research_snapshot_invalid")
        if kind == "facts" and any(type(row.value) is not str for row in rows):
            raise ValueError("sec_research_snapshot_invalid")
        observed_at = _timestamp(observed_at)
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("sec_research_source_url_invalid")
        payload = asdict(snapshot)
        _bounded_json({"snapshot": payload, "observed_at": observed_at, "source_url": source_url})
        historical_name = snapshot.historical_name if kind == "catalog" else None
        identity = _json([cik, kind, historical_name, object_sha256])
        snapshot_id = "secsnapshot_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        historical_files = _json(payload.get("historical_files", []))
        normalized_rows = payload["filings" if kind == "catalog" else "facts"]
        with self._write() as conn:
            obj = conn.execute("SELECT * FROM sec_research_objects WHERE sha256=?", (object_sha256,)).fetchone()
            if obj is None:
                raise ValueError("sec_research_object_missing")
            if type(obj["size_bytes"]) is not int or obj["size_bytes"] < 0:
                raise ValueError("sec_research_object_invalid")
            try:
                self.paths.object_path(obj["object_key"])
            except ValueError:
                raise ValueError("sec_research_object_invalid") from None
            if conn.execute("SELECT 1 FROM sec_research_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone():
                return snapshot_id
            conn.execute("""INSERT INTO sec_research_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                         (snapshot_id, cik, kind, object_sha256, observed_at, source_url,
                          historical_name, int(getattr(snapshot, "historical_files_observed", False)),
                          historical_files, len(rows)))
            table = "sec_research_filings" if kind == "catalog" else "sec_research_facts"
            for ordinal, row in enumerate(normalized_rows):
                source = row.pop("source")
                values = {"snapshot_id": snapshot_id, "ordinal": ordinal, **row,
                          "source_sha256": source["sha256"], "source_pointer": source["pointer"]}
                columns = ", ".join(values)
                placeholders = ", ".join("?" for _ in values)
                conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
        return snapshot_id

    def snapshots(self, cik, kind):
        cik = normalize_cik(cik)
        if kind not in ("catalog", "facts"):
            raise ValueError("sec_research_kind_invalid")
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            result = [_snapshot(row) for row in conn.execute(
                "SELECT * FROM sec_research_snapshots WHERE cik=? AND kind=? ORDER BY rowid", (cik, kind))]
        return result

    def snapshot(self, cik, snapshot_id):
        """Reopen one immutable snapshot for this issuer, never a latest substitute."""
        cik = normalize_cik(cik)
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            return _snapshot(conn.execute(
                "SELECT * FROM sec_research_snapshots WHERE cik=? AND snapshot_id=?",
                (cik, snapshot_id)).fetchone())

    def bound_snapshot(self, cik, locator, binding):
        """Validate a receipt binding and reopen its exact source metadata."""
        cik = normalize_cik(cik)
        binding = _binding_shape(binding)
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            return _bound_snapshot(conn, cik, locator, binding)

    def snapshot_observations(self, cik, snapshot_id):
        """Read only the named snapshot's rows; missing/foreign snapshots have no rows."""
        snapshot = self.snapshot(cik, snapshot_id)
        if snapshot is None:
            return []
        table = "sec_research_filings" if snapshot["kind"] == "catalog" else "sec_research_facts"
        return self._observations(cik, table, snapshot_id=snapshot_id)

    def iter_snapshot_observations(self, cik, snapshot_id):
        """Stream immutable rows from one issuer-scoped snapshot; close on early stop."""
        cik = normalize_cik(cik)
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            snapshot = conn.execute(
                "SELECT kind FROM sec_research_snapshots WHERE cik=? AND snapshot_id=?",
                (cik, snapshot_id)).fetchone()
            if snapshot is None:
                return
            table = "sec_research_filings" if snapshot["kind"] == "catalog" else "sec_research_facts"
            for record in conn.execute(f"""
                SELECT o.*, s.observed_at, s.source_url, s.object_sha256
                FROM {table} o JOIN sec_research_snapshots s USING(snapshot_id)
                WHERE o.cik=? AND o.snapshot_id=? ORDER BY o.ordinal""", (cik, snapshot_id)):
                row = dict(record)
                row.pop("ordinal")
                row["source"] = {"sha256": row.pop("source_sha256"), "pointer": row.pop("source_pointer")}
                yield row

    def _observations(self, cik, table, *, snapshot_id=None):
        cik = normalize_cik(cik)
        selection = " AND o.snapshot_id=?" if snapshot_id is not None else ""
        parameters = (cik, snapshot_id) if snapshot_id is not None else (cik,)
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            result = [dict(row) for row in conn.execute(f"""
                SELECT o.*, s.observed_at, s.source_url, s.object_sha256
                FROM {table} o JOIN sec_research_snapshots s USING(snapshot_id)
                WHERE o.cik=?{selection} ORDER BY s.rowid, o.ordinal""", parameters)]
        for row in result:
            row.pop("ordinal")
            row["source"] = {"sha256": row.pop("source_sha256"), "pointer": row.pop("source_pointer")}
        return result

    def catalog(self, cik):
        return self._observations(cik, "sec_research_filings")

    def facts(self, cik):
        return self._observations(cik, "sec_research_facts")

    def record_receipt(self, cik, *, status, completed, pending, gaps, observed_at,
                       source_snapshots=None):
        """Append coverage; omitted bindings are explicitly unbound, not query authority."""
        cik = normalize_cik(cik)
        _receipt_fields(cik, status, completed, pending, gaps)
        if len(completed) + len(pending) + len(gaps) > MAX_SNAPSHOT_ROWS:
            raise ValueError("sec_research_snapshot_rows_exceeded")
        observed_at = _timestamp(observed_at)
        if source_snapshots is None:
            bindings = {}
        else:
            if not isinstance(source_snapshots, dict) or set(source_snapshots) != set(completed):
                raise ValueError("sec_research_receipt_binding_invalid")
            bindings = {locator: _binding_shape(binding) for locator, binding in source_snapshots.items()}
        _bounded_json([cik, status, completed, pending, gaps, observed_at, bindings])
        encoded = [_json(value) for value in (completed, pending, gaps)]
        with self._write() as conn:
            for locator, binding in bindings.items():
                _bound_snapshot(conn, cik, locator, binding)
            recorded_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
            cursor = conn.execute("""INSERT INTO sec_research_receipts
                (cik, status, completed, pending, gaps, observed_at, recorded_at, source_snapshots)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (cik, status, *encoded, observed_at, recorded_at, _json(bindings)))
            result = _receipt(conn.execute("SELECT * FROM sec_research_receipts WHERE receipt_id=?", (cursor.lastrowid,)).fetchone())
        return result

    def receipt(self, cik, receipt_id):
        """Reopen a committed receipt belonging to this issuer."""
        cik = normalize_cik(cik)
        if type(receipt_id) is not int or not 1 <= receipt_id <= 2**63 - 1:
            raise ValueError("sec_research_receipt_invalid")
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            return _receipt(conn.execute(
                "SELECT * FROM sec_research_receipts WHERE cik=? AND receipt_id=?",
                (cik, receipt_id)).fetchone())

    def latest_receipt(self, cik):
        """Return the last durable append; timestamps are diagnostic metadata."""
        cik = normalize_cik(cik)
        with self.connect(readonly=True) as conn:
            schema.verify(conn)
            return _receipt(conn.execute("""SELECT * FROM sec_research_receipts WHERE cik=?
                ORDER BY receipt_id DESC LIMIT 1""", (cik,)).fetchone())
