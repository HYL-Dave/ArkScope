"""Persisted observations, not hand-editable lifecycle decisions or aliases."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from src.security_lifecycle_provider_authority import (
    PROVIDER_OBSERVATION_SOURCE, classify_provider_listing, evidence_dict, validate_provider_material, terminal_requires_attestation,
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("provider_snapshot_time")
    return result.astimezone(timezone.utc)


def _observation(payload, digest):
    ticker, at = payload["ticker"], payload["at"]
    result = classify_provider_listing(ticker=ticker, evidence=payload["evidence"], today=_instant(at).date())
    state = "unresolved" if payload["blockers"] else result.state
    return {
        "ticker": ticker, "cik": None, "issuer_name": ticker,
        "filing_date": _instant(at).date().isoformat(), "source": PROVIDER_OBSERVATION_SOURCE,
        "source_ref": f"listing:{ticker}", "filing_form": "LISTING_STATUS", "filing_items": [],
        "evidence_url": "https://massive.com/docs/rest/stocks/tickers/all-tickers",
        "description": {
            "terminal": "Listing sources confirm delisting; current trading and same-security continuation were checked.",
            "continuation": "A same-security ticker change needs review.",
            "active": "Current listing sources confirm trading continues.",
            "unresolved": "Listing status needs confirmation. Tracking has not been changed.",
        }[state],
        "observed_at": at, "provider_snapshot_sha256": digest,
        "kinds": [{"event_type": "listing_status_review", "effective_date": result.effective_date}],
    }


class ProviderCheckStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def _connection(self, *, write=False):
        conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode={'rw' if write else 'ro'}", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if not write:
                conn.execute("PRAGMA query_only=ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def record(self, *, ticker, at, evidence, diagnostics, blockers=()):
        return self.record_many([dict(ticker=ticker, at=at, evidence=evidence, diagnostics=diagnostics, blockers=blockers)])[0]

    def record_many(self, checks):
        prepared = [self._prepare(**check) for check in checks]
        with self._connection(write=True) as conn:
            conn.executemany("INSERT INTO security_lifecycle_provider_checks VALUES (?,?,?,?,?,?,?,?,?,?) "
                             "ON CONFLICT(ticker,content_sha256) DO NOTHING", prepared)
        return [row[-2] for row in prepared]

    @staticmethod
    def _prepare(*, ticker, at, evidence, diagnostics, blockers=()):
        if not isinstance(ticker, str) or re.fullmatch(r"[A-Z][A-Z0-9. -]{0,15}", ticker) is None:
            raise ValueError("provider_snapshot_ticker")
        instant = _instant(at)
        at = instant.isoformat(timespec="seconds").replace("+00:00", "Z")
        material = [evidence_dict(row) for row in evidence]
        for row in material:
            validate_provider_material(row)
            if row["source_family"] != "listing_authority" or not isinstance(row["excerpt"], str):
                raise ValueError("provider_snapshot_material")
            if hashlib.sha256(row["excerpt"].encode()).hexdigest() != row["content_sha256"]:
                raise ValueError("provider_snapshot_material")
        if any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in diagnostics.items()):
            raise ValueError("provider_snapshot_diagnostics")
        if any(not isinstance(code, str) or re.fullmatch(r"[a-z_]{1,80}", code) is None for code in blockers):
            raise ValueError("provider_snapshot_blockers")
        result = classify_provider_listing(ticker=ticker, evidence=material, today=instant.date())
        payload = {"ticker": ticker, "at": at, "evidence": material, "diagnostics": dict(diagnostics),
                   "blockers": sorted(set(blockers)), "state": "unresolved" if blockers else result.state}
        digest = hashlib.sha256(_json(payload).encode()).hexdigest()
        observation = _observation(payload, digest)
        return (f"slpc_{digest}", ticker, at, _json(observation), _json(material), _json(diagnostics),
                _json(payload["blockers"]), payload["state"], digest, at)

    @staticmethod
    def _read(row):
        payload = {"ticker": row["ticker"], "at": row["observed_at"], "evidence": json.loads(row["evidence_json"]),
                   "diagnostics": json.loads(row["diagnostics_json"]), "blockers": json.loads(row["blockers_json"]), "state": row["state"]}
        digest = hashlib.sha256(_json(payload).encode()).hexdigest()
        if digest != row["content_sha256"] or _observation(payload, digest) != json.loads(row["observation_json"]):
            raise ValueError("provider_snapshot_digest")
        return {**payload, "digest": digest, "observation": json.loads(row["observation_json"])}

    def latest(self):
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT c.* FROM security_lifecycle_provider_checks c WHERE c.rowid=("
                "SELECT r.rowid FROM security_lifecycle_provider_checks r WHERE r.ticker=c.ticker "
                "ORDER BY r.observed_at DESC,r.rowid DESC LIMIT 1) ORDER BY c.ticker"
            ).fetchall()
            return {row["ticker"]: self._read(row) for row in rows}

    @classmethod
    def latest_for_connection(cls, conn, ticker):
        cursor = conn.execute("SELECT * FROM security_lifecycle_provider_checks WHERE ticker=? ORDER BY observed_at DESC,rowid DESC LIMIT 1", (ticker,))
        row = cursor.fetchone()
        return cls._read(dict(zip([item[0] for item in cursor.description], row))) if row is not None else None

    def observations(self):
        latest = self.latest()
        with self._connection() as conn:
            tracked = {row[0] for row in conn.execute("SELECT DISTINCT ticker FROM security_lifecycle_provider_checks WHERE state<>'active'")}
        return [row["observation"] for ticker, row in latest.items() if ticker in tracked]

    def bundle(self, case, *, at):
        from src.security_lifecycle_fact_kernel import AutomationBlocker
        from src.security_lifecycle_automation_worker import LifecycleAutomationEvidenceBundle
        from src.security_lifecycle_investigation import observation_fingerprint
        from src.security_lifecycle_listing_evidence import ListingFact
        row = self.latest().get(case["ticker"])
        if row is None or observation_fingerprint(row["observation"]) != observation_fingerprint(dict(case["observation"])):
            raise ValueError("provider_snapshot_changed")
        now = _instant(at)
        result = classify_provider_listing(ticker=case["ticker"], evidence=row["evidence"], today=now.date())
        incomplete = result.state == "unresolved" or bool(row["blockers"])
        manual_review = terminal_requires_attestation(result) and set(row["blockers"]) <= {"massive_not_found"}
        facts = []
        for item in row["evidence"]:
            locator = item["source_locator"]
            if (item["kind"] == "listing_directory_snapshot" and locator.get("candidate_ticker") == case["ticker"]
                    and locator.get("listing_status") in {"active", "inactive"}):
                if json.loads(item["excerpt"]).get("ticker") != case["ticker"]:
                    raise ValueError("provider_snapshot_fact_binding")
                facts.append(ListingFact(item["evidence_id"], "source_ticker", case["ticker"], 0,
                                         len(item["excerpt"].encode()), item["content_sha256"], "provider_listing.exact_ticker", "1"))
        return LifecycleAutomationEvidenceBundle(
            evidence=tuple(row["evidence"]), facts=tuple(facts),
            blockers=(AutomationBlocker("listing_status_unresolved", not manual_review, {"reasons": list(result.reasons), "provider_codes": row["blockers"], "manual_review_required": manual_review}),) if incomplete else (),
            diagnostics=row["diagnostics"], retry_at=(now + timedelta(days=1)).isoformat() if incomplete and not manual_review else None,
            refreshed_source_families=("listing_authority",),
        )
