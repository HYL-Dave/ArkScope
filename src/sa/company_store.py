"""Bounded, content-addressed company observations in the existing SA store."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3

from src import sa_capture_store
from src.sa.company_data import CompanyDataFailure, canonical_json, digest, normalize_capture, provider_symbol, require


DEFAULT_BUDGET_BYTES = 256 * 1024**2
BUDGET_ENV = "ARKSCOPE_SA_COMPANY_BUDGET_BYTES"


def _budget_bytes():
    raw = os.environ.get(BUDGET_ENV, str(DEFAULT_BUDGET_BYTES))
    require(raw.isascii() and raw.isdigit() and 0 < int(raw) < 2**63, "sa_company_budget_invalid")
    return int(raw)


def save_capture(payload, *, db_path=None):
    observation = normalize_capture(payload)
    budget = _budget_bytes()
    body = observation["body"]
    encoded = canonical_json(body)
    size = len(encoded.encode("utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    try:
        with closing(sa_capture_store.connect(db_path)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            baseline = conn.execute(
                "SELECT observation_id, body_json FROM sa_company_observations WHERE ticker=? AND statement=? "
                "AND period_view=? AND currency=? ORDER BY last_captured_at DESC, observation_id LIMIT 1",
                (body["ticker"], body["statement"], body["view"], body["currency"]),
            ).fetchone()
            if baseline is not None:
                known = json.loads(baseline[1])
                require(digest(known) == baseline[0], "sa_company_observation_invalid")
                # A new extractor revision requires code review; page drift cannot rebaseline itself.
                require(known["layout_id"] != body["layout_id"]
                        or known["structure_sha256"] == body["structure_sha256"], "sa_company_structure_changed")
            previous = conn.execute("SELECT observation_id FROM sa_company_observations WHERE observation_id=?",
                                    (observation["observation_id"],)).fetchone()
            if previous is None:
                used = conn.execute("SELECT COALESCE(SUM(byte_count), 0) FROM sa_company_observations").fetchone()[0]
                require(used + size <= budget, "sa_company_budget_exceeded")
                conn.execute(
                    "INSERT INTO sa_company_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (observation["observation_id"], body["ticker"], body["statement"], body["view"], body["currency"],
                     observation["captured_at"], observation["captured_at"], now, encoded, size),
                )
            else:
                conn.execute(
                    "UPDATE sa_company_observations SET last_captured_at=MAX(last_captured_at, ?) "
                    "WHERE observation_id=?", (observation["captured_at"], observation["observation_id"]),
                )
            conn.commit()
    except (OSError, sqlite3.Error) as exc:
        raise CompanyDataFailure("sa_company_store_unavailable") from exc
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CompanyDataFailure):
            raise
        raise CompanyDataFailure("sa_company_observation_invalid") from exc
    return {"status": "ok", "observation_id": observation["observation_id"], "ticker": body["ticker"],
            "dataset": body.get("dataset", "financials"),
            "statement": body["statement"], "view": body["view"], "currency": body["currency"],
            "deduplicated": previous is not None, "coverage": body["coverage"],
            "structure_sha256": body["structure_sha256"], "budget_bytes": budget}


def read_capture(ticker, statement, view, currency, *, observation_id=None, db_path=None):
    """Never migrate, create a DB, update last-seen state or contact a provider."""
    ticker = provider_symbol(ticker)
    path = Path(db_path or sa_capture_store.resolve_sa_db_path()).expanduser().resolve()
    try:
        if not path.exists():
            return None
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sa_company_observations'").fetchone():
                return None
            ticker_clause = "ticker=?"
            parameters = [ticker]
            if observation_id is not None and ticker == "BRK.B":
                ticker_clause = "ticker IN (?,?)"
                parameters.append("BRK-B")
            sql = f"SELECT * FROM sa_company_observations WHERE {ticker_clause} AND statement=? AND period_view=? AND currency=?"
            parameters.extend([statement, view, currency])
            if observation_id is not None:
                sql += " AND observation_id=?"
                parameters.append(observation_id)
            row = conn.execute(sql + " ORDER BY last_captured_at DESC, observation_id LIMIT 1", parameters).fetchone()
            if row is None:
                return None
            body = json.loads(row["body_json"])
            require(digest(body) == row["observation_id"], "sa_company_observation_invalid")
            require((body["ticker"], body["statement"], body["view"], body["currency"])
                    == (row["ticker"], statement, view, currency), "sa_company_observation_invalid")
            return {"observation_id": row["observation_id"], "first_captured_at": row["captured_at"],
                    "last_captured_at": row["last_captured_at"], "received_at": row["received_at"], **body}
    except (OSError, sqlite3.Error) as exc:
        raise CompanyDataFailure("sa_company_store_unavailable") from exc
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CompanyDataFailure):
            raise
        raise CompanyDataFailure("sa_company_observation_invalid") from exc
