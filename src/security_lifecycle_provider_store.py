"""Persisted observations, not hand-editable lifecycle decisions or aliases."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from src.security_lifecycle_provider_authority import (
    PROVIDER_OBSERVATION_SOURCE, classify_provider_listing, evidence_dict, validate_provider_material,
)
from src.security_lifecycle_provider_snapshot import (
    canonical_json as _json, decode_snapshot, encode_snapshot, instant as _instant,
)


def _observation(payload, result):
    ticker, at = payload["ticker"], payload["at"]
    state = result.state
    description = {
        "terminal": "Listing sources confirm that the old listing stopped trading.",
        "continuation": "Listing sources confirm a same-security ticker change.",
        "active": "Current listing sources confirm trading continues.",
        "unresolved": "Listing status needs confirmation. Tracking has not been changed.",
    }[state]
    if state == "terminal":
        description += {
            "unavailable": " Continuation could not be checked; this does not prove that no successor exists.",
            "candidate": " A replacement candidate needs confirmation: " + ", ".join(result.candidate_tickers) + ".",
            "ambiguous": " Continuation evidence is ambiguous and needs review.",
            "not_observed": " No continuation was observed in the retrieved timeline.",
        }[result.continuation_state]
    return {
        "ticker": ticker, "cik": None, "issuer_name": ticker,
        "filing_date": _instant(at).date().isoformat(), "source": PROVIDER_OBSERVATION_SOURCE,
        "source_ref": f"listing:{ticker}", "filing_form": "LISTING_STATUS", "filing_items": [],
        "evidence_url": "https://massive.com/docs/rest/stocks/tickers/all-tickers",
        "description": description,
        "observed_at": at,
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
        blockers = tuple(blockers)
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
        result = classify_provider_listing(ticker=ticker, evidence=material, today=instant.date(), provider_codes=blockers)
        payload = {"ticker": ticker, "at": at, "evidence": material, "diagnostics": dict(diagnostics),
                   "blockers": sorted(set(blockers)), "state": result.state}
        digest, envelope = encode_snapshot(payload, _observation(payload, result))
        return (f"slpc_{digest}", ticker, at, envelope, _json(material), _json(diagnostics),
                _json(payload["blockers"]), payload["state"], digest, at)

    @staticmethod
    def _read(row):
        return decode_snapshot(row)

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

    @classmethod
    def current_material(cls, conn, row, *, at):
        """Include independently observed successor listings, without a provider call."""
        material = [evidence_dict(item) for item in row["evidence"]]
        codes = set(row["blockers"])
        targets = set()
        for item in material:
            locator = item["source_locator"]
            if item["adapter"] != "massive_ticker_events" or locator.get("candidate_ticker") != row["ticker"]:
                continue
            relations = locator.get("events")
            if not isinstance(relations, (tuple, list)):
                continue
            for relation in relations:
                if (isinstance(relation, (tuple, list)) and len(relation) == 3 and relation[0] == row["ticker"]
                        and isinstance(relation[1], str) and re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", relation[1])
                        and relation[1] != row["ticker"]):
                    targets.add(relation[1])

        def channel(item):
            locator = item["source_locator"]
            return (item["adapter"], locator.get("candidate_ticker"), locator.get("directory"), locator.get("market"),
                    locator.get("expected_active_state") if item["adapter"] == "massive_reference" else None)

        now = _instant(at)
        unrecovered = set(targets)
        for ticker in sorted(targets):
            current = cls.latest_for_connection(conn, ticker)
            if current is None or not now - timedelta(days=3) <= _instant(current["at"]) <= now:
                continue
            failed = any(not code.startswith(("massive_timeline_", "massive_successor_", "successor_listing_"))
                         for code in current["blockers"])
            if failed:
                codes.add("successor_listing_provider_error")
            for incoming in current["evidence"]:
                if (incoming["kind"] != "listing_directory_snapshot"
                        or incoming["source_locator"].get("candidate_ticker") != ticker):
                    continue
                matches = [item for item in material if channel(item) == channel(incoming)]
                observed = _instant(incoming["retrieved_at"])
                if (not failed and now - timedelta(days=3) <= observed <= now
                        and incoming["source_locator"].get("snapshot_complete") is True):
                    unrecovered.discard(ticker)
                if any(_instant(item["retrieved_at"]) > observed for item in matches):
                    continue
                # A newer observation replaces its own lookup, not other sources.
                # Equally timed contradictions remain visible to the classifier.
                material = [item for item in material if channel(item) != channel(incoming)
                            or (_instant(item["retrieved_at"]) == observed
                                and item["content_sha256"] != incoming["content_sha256"])]
                material.append(incoming)
        if targets and not unrecovered:
            codes.discard("successor_listing_provider_error")
        return tuple(material), tuple(sorted(codes))

    def material(self, *, ticker, evidence, blockers, at):
        with self._connection() as conn:
            return self.current_material(conn, dict(ticker=ticker, evidence=evidence, blockers=blockers), at=at)

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
        with self._connection() as conn:
            row = self.latest_for_connection(conn, case["ticker"])
            if row is None or observation_fingerprint(row["observation"]) != observation_fingerprint(dict(case["observation"])):
                raise ValueError("provider_snapshot_changed")
            material, codes = self.current_material(conn, row, at=at)
        now = _instant(at)
        result = classify_provider_listing(ticker=case["ticker"], evidence=material, today=now.date(), provider_codes=codes)
        incomplete = result.state == "unresolved"
        facts = []
        for item in material:
            locator = item["source_locator"]
            if (item["kind"] == "listing_directory_snapshot" and locator.get("candidate_ticker") == case["ticker"]
                    and locator.get("listing_status") in {"active", "inactive"}):
                if json.loads(item["excerpt"]).get("ticker") != case["ticker"]:
                    raise ValueError("provider_snapshot_fact_binding")
                facts.append(ListingFact(item["evidence_id"], "source_ticker", case["ticker"], 0,
                                         len(item["excerpt"].encode()), item["content_sha256"], "provider_listing.exact_ticker", "1"))
        return LifecycleAutomationEvidenceBundle(
            evidence=material, facts=tuple(facts), provider_codes=codes,
            blockers=(AutomationBlocker("listing_status_unresolved", True, {"reasons": list(result.reasons), "provider_codes": list(codes), "manual_review_required": False}),) if incomplete else (),
            diagnostics=row["diagnostics"], retry_at=(now + timedelta(days=1)).isoformat() if incomplete else None,
            refreshed_source_families=("listing_authority",),
        )
