"""Versioned provider receipts, independent of the current decision policy."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit


_V2_DOMAIN = b"arkscope.lifecycle.provider_snapshot.v2\0"
_OBSERVATION_KEYS = frozenset({
    "ticker", "cik", "issuer_name", "filing_date", "source", "source_ref",
    "filing_form", "filing_items", "evidence_url", "description", "observed_at",
    "provider_snapshot_sha256", "kinds",
})
_STATES = frozenset({"active", "terminal", "continuation", "unresolved"})


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def instant(value):
    if not isinstance(value, str):
        raise ValueError("provider_snapshot_time")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("provider_snapshot_time")
    return result.astimezone(timezone.utc)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("provider_snapshot_format")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("provider_snapshot_format")


def _parse(value):
    try:
        return json.loads(value, object_pairs_hook=_object, parse_constant=_invalid_constant)
    except (TypeError, ValueError):
        raise ValueError("provider_snapshot_format") from None


def _validate_payload(payload):
    if (
        not isinstance(payload["ticker"], str)
        or re.fullmatch(r"[A-Z][A-Z0-9. -]{0,15}", payload["ticker"]) is None
        or payload["state"] not in _STATES
        or not isinstance(payload["evidence"], list)
        or any(not isinstance(row, dict) for row in payload["evidence"])
        or not isinstance(payload["diagnostics"], dict)
        or any(type(value) is not int or value < 0 for value in payload["diagnostics"].values())
        or not isinstance(payload["blockers"], list)
        or any(not isinstance(code, str) or re.fullmatch(r"[a-z_]{1,80}", code) is None for code in payload["blockers"])
    ):
        raise ValueError("provider_snapshot_format")
    try:
        canonical_at = instant(payload["at"]).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (TypeError, ValueError):
        raise ValueError("provider_snapshot_format") from None
    if canonical_at != payload["at"] or payload["blockers"] != sorted(set(payload["blockers"])):
        raise ValueError("provider_snapshot_format")


def _validate_observation(payload, observation):
    if not isinstance(observation, dict) or set(observation) != _OBSERVATION_KEYS:
        raise ValueError("provider_snapshot_format")
    ticker, at = payload["ticker"], payload["at"]
    expected = {
        "ticker": ticker, "source": "listing_authority", "source_ref": f"listing:{ticker}",
        "filing_form": "LISTING_STATUS", "filing_date": instant(at).date().isoformat(),
        "filing_items": [], "observed_at": at,
    }
    if any(observation[key] != value for key, value in expected.items()):
        raise ValueError("provider_snapshot_format")
    for key in ("issuer_name", "description", "evidence_url"):
        if not isinstance(observation[key], str) or not observation[key].strip():
            raise ValueError("provider_snapshot_format")
    cik = observation["cik"]
    if cik is not None and (not isinstance(cik, str) or re.fullmatch(r"\d{10}", cik) is None):
        raise ValueError("provider_snapshot_format")
    try:
        url = urlsplit(observation["evidence_url"])
        if url.scheme != "https" or not url.hostname or url.username is not None or url.password is not None:
            raise ValueError("provider_snapshot_format")
    except ValueError:
        raise ValueError("provider_snapshot_format") from None
    kinds = observation["kinds"]
    if (
        not isinstance(kinds, list) or len(kinds) != 1 or not isinstance(kinds[0], dict)
        or set(kinds[0]) != {"event_type", "effective_date"}
        or kinds[0]["event_type"] != "listing_status_review"
    ):
        raise ValueError("provider_snapshot_format")
    effective = kinds[0]["effective_date"]
    if effective is not None:
        try:
            if not isinstance(effective, str) or date.fromisoformat(effective).isoformat() != effective:
                raise ValueError("provider_snapshot_format")
        except ValueError:
            raise ValueError("provider_snapshot_format") from None


def _v2_digest(payload, observation):
    unsigned = {key: value for key, value in observation.items() if key != "provider_snapshot_sha256"}
    return hashlib.sha256(_V2_DOMAIN + canonical_json({
        "snapshot_format": 2, "payload": payload, "observation": unsigned,
    }).encode()).hexdigest()


def encode_snapshot(payload, observation):
    _validate_payload(payload)
    digest = _v2_digest(payload, observation)
    sealed = {**observation, "provider_snapshot_sha256": digest}
    _validate_observation(payload, sealed)
    return digest, canonical_json({"snapshot_format": 2, "observation": sealed})


def decode_snapshot(row):
    try:
        payload = {
            "ticker": row["ticker"], "at": row["observed_at"], "state": row["state"],
            "evidence": _parse(row["evidence_json"]),
            "diagnostics": _parse(row["diagnostics_json"]),
            "blockers": _parse(row["blockers_json"]),
        }
        _validate_payload(payload)
        envelope = _parse(row["observation_json"])
        if not isinstance(envelope, dict):
            raise ValueError("provider_snapshot_format")
        if "snapshot_format" in envelope:
            if (
                type(envelope["snapshot_format"]) is not int or envelope["snapshot_format"] != 2
                or set(envelope) != {"snapshot_format", "observation"}
            ):
                raise ValueError("provider_snapshot_format")
            observation = envelope["observation"]
            _validate_observation(payload, observation)
            digest = _v2_digest(payload, observation)
        else:
            observation = envelope
            if set(observation) != _OBSERVATION_KEYS:
                raise ValueError("provider_snapshot_format")
            digest = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
            if digest != row["content_sha256"] or observation != _v1_observation(payload, digest):
                raise ValueError("provider_snapshot_digest")
        if (
            digest != row["content_sha256"] or observation["provider_snapshot_sha256"] != digest
            or row["check_id"] != f"slpc_{digest}" or row["created_at"] != payload["at"]
        ):
            raise ValueError("provider_snapshot_digest")
    except (KeyError, TypeError):
        raise ValueError("provider_snapshot_format") from None
    return {**payload, "digest": digest, "observation": observation}


# V1 never sealed observation_json. Reconstruct its exact 0b66732b semantics only
# to validate historical receipts; this code must not decide current actions.
_V1_AUTHORITIES = {
    "massive_reference": "massive", "nasdaq_symbol_directory": "nasdaq_trader",
    "eodhd_symbol_directory": "eodhd",
}


def _v1_validate_material(row):
    locator, excerpt = row["source_locator"], row["excerpt"]
    if not isinstance(locator, dict) or not isinstance(excerpt, str) or hashlib.sha256(excerpt.encode()).hexdigest() != row["content_sha256"]:
        raise ValueError("legacy_material")
    content = json.loads(excerpt)
    if not isinstance(content, dict):
        raise ValueError("legacy_material")
    if row["adapter"] == "massive_ticker_events":
        if row["kind"] != "ticker_event_snapshot" or content != locator:
            raise ValueError("legacy_material")
    elif (
        row["kind"] != "listing_directory_snapshot" or type(locator.get("expected_active_state")) is not bool
        or content.get("ticker") != locator.get("candidate_ticker")
        or any(content.get(key) != locator.get(key) for key in (
            "authority", "directory", "listing_status", "market", "primary_exchange", "security_type", "issuer_cik",
            "composite_figi", "expected_active_state", "snapshot_complete", "delisted_utc", "source_as_of", "provider_last_updated_utc",
        )) or row["source_document_sha256"] != locator.get("source_document_sha256")
    ):
        raise ValueError("legacy_material")


def _v1_fields(payload):
    ticker, today = payload["ticker"], instant(payload["at"]).date()
    unresolved = ("unresolved", None)
    rows, events = [], []
    try:
        for row in payload["evidence"]:
            if row.get("source_family") != "listing_authority":
                continue
            _v1_validate_material(row)
            locator = row["source_locator"]
            retrieved = datetime.fromisoformat(str(row["retrieved_at"]).replace("Z", "+00:00"))
            if retrieved.tzinfo is None or not today - timedelta(days=3) <= retrieved.date() <= today or locator.get("snapshot_complete") is not True:
                return unresolved
            if row["adapter"] == "massive_ticker_events":
                if locator.get("candidate_ticker") == ticker:
                    events.append(locator)
                continue
            adapter = row["adapter"]
            if adapter not in _V1_AUTHORITIES or locator.get("adapter") != adapter or locator.get("authority") != _V1_AUTHORITIES[adapter]:
                return unresolved
            if locator.get("listing_status") not in {"active", "inactive", "not_found", "unverified"}:
                return unresolved
            rows.append(locator)
    except (ValueError, TypeError, KeyError):
        return unresolved
    source = [row for row in rows if row.get("candidate_ticker") == ticker]
    active = [row for row in source if row["listing_status"] == "active"]
    inactive = [row for row in source if row["listing_status"] == "inactive"]
    if active:
        return unresolved if inactive else ("active", None)
    massive = [row for row in inactive if row["adapter"] == "massive_reference" and row.get("market") == "stocks" and row.get("expected_active_state") is False]
    if len(massive) != 1:
        return unresolved
    old = massive[0]
    figi = old.get("composite_figi")
    if not isinstance(figi, str) or not figi:
        return unresolved
    try:
        effective = date.fromisoformat(str(old.get("delisted_utc"))[:10])
    except ValueError:
        return unresolved
    if effective > today:
        return unresolved
    missing = False
    for market in ("stocks", "otc"):
        negatives = [row for row in source if row["adapter"] == "massive_reference" and row.get("market") == market and row.get("expected_active_state") is True]
        if len(negatives) != 1 or negatives[0]["listing_status"] != "not_found":
            missing = True
    if not any(row["adapter"] == "eodhd_symbol_directory" for row in inactive):
        missing = True
    directories = {row.get("directory") for row in source if row["adapter"] == "nasdaq_symbol_directory" and row["listing_status"] == "not_found"}
    if directories != {"nasdaq_listed", "other_listed"}:
        missing = True
    unavailable = ("unresolved", effective.isoformat())
    timelines = [row for row in events if row.get("composite_figi") == figi]
    if len(timelines) != 1:
        return unavailable
    timeline = timelines[0]
    relations = timeline.get("events")
    if not isinstance(relations, (tuple, list)) or any(not isinstance(row, (tuple, list)) or len(row) != 3 for row in relations):
        return unresolved
    successors = [row for row in relations if row[0] == ticker]
    if successors:
        if len(successors) != 1:
            return unresolved
        _, successor, changed_on = successors[0]
        confirmed = [row for row in rows if row.get("candidate_ticker") == successor and row.get("adapter") == "massive_reference" and row.get("listing_status") == "active" and row.get("composite_figi") == figi]
        if not confirmed:
            return unresolved
        try:
            change_date = date.fromisoformat(changed_on)
        except (ValueError, TypeError):
            return unresolved
        return unresolved if change_date > today else ("continuation", changed_on)
    if timeline.get("latest_ticker") != ticker:
        return unavailable
    return unresolved if missing else ("terminal", effective.isoformat())


def _v1_observation(payload, digest):
    ticker, at = payload["ticker"], payload["at"]
    state, effective_date = _v1_fields(payload)
    if payload["blockers"]:
        state = "unresolved"
    return {
        "ticker": ticker, "cik": None, "issuer_name": ticker,
        "filing_date": instant(at).date().isoformat(), "source": "listing_authority",
        "source_ref": f"listing:{ticker}", "filing_form": "LISTING_STATUS", "filing_items": [],
        "evidence_url": "https://massive.com/docs/rest/stocks/tickers/all-tickers",
        "description": {
            "terminal": "Listing sources confirm delisting; current trading and same-security continuation were checked.",
            "continuation": "A same-security ticker change needs review.",
            "active": "Current listing sources confirm trading continues.",
            "unresolved": "Listing status needs confirmation. Tracking has not been changed.",
        }[state],
        "observed_at": at, "provider_snapshot_sha256": digest,
        "kinds": [{"event_type": "listing_status_review", "effective_date": effective_date}],
    }
