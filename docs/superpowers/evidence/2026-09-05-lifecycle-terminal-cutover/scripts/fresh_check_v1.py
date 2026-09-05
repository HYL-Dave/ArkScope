"""One attended 19-request evidence check; never approve/apply a disposition."""

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time

import requests

from data_sources.lifecycle_provider_census_transport import (
    EODHD_EXCHANGE_SYMBOL_LIST_URL, MASSIVE_EVENTS_PREFIX, LifecycleProviderCensusTransport,
)
from data_sources.listing_authority_transport import (
    MASSIVE_TICKERS_URL, NASDAQ_LISTED_URL, OTHER_LISTED_URL, ListingAuthorityTransport,
)
from src.active_universe import build_active_universe_snapshot
from src.sa_tracking_memberships import SaTrackingMembershipStore
from src.security_lifecycle_listing_evidence import parse_massive_ticker
from src.security_lifecycle_provider_authority import classify_provider_listing, evidence_dict, terminal_requires_attestation
from src.security_lifecycle_provider_census_credentials import ReadOnlyProviderCredentialStore, resolve_census_credential
from src.security_lifecycle_provider_migration import preflight_provider_upgrade
from src.security_lifecycle_provider_scan import ProviderScanSession
from src.security_lifecycle_provider_store import ProviderCheckStore


TARGETS = ("ARCH", "LTHM", "TA")
LIMITS = {"massive": 15, "eodhd": 2, "nasdaq": 2}
ROOT = Path("/mnt/md0/PycharmProjects/ArkScope")
PROFILE, SA = ROOT / "data/profile_state.db", ROOT / "data/sa_capture.db"


class CheckStopped(BaseException):
    """Do not let provider adapters turn an authorization stop into fallback."""


def require(condition, code):
    if not condition:
        raise CheckStopped(code)


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def write(directory, name, value):
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class MeasuredResponse:
    def __init__(self, response, ledger, row, started):
        self.response, self.ledger, self.row, self.started = response, ledger, row, started
        self.status_code, self.headers = response.status_code, response.headers
        self.digest, self.size, self.complete, self.closed = hashlib.sha256(), 0, False, False

    def iter_content(self, chunk_size):
        for chunk in self.response.iter_content(chunk_size=chunk_size):
            self.digest.update(chunk)
            self.size += len(chunk)
            yield chunk
        self.complete = True

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.response.close()
        finally:
            result = {**self.row, "status_code": self.status_code, "read_bytes": self.size,
                      "body_complete": self.complete, "response_sha256": self.digest.hexdigest() if self.complete else None,
                      "elapsed_ms": round((self.ledger.timer() - self.started) * 1000)}
            self.ledger.outcomes.append(result)
            write(self.ledger.directory, f"request-{self.row['request']:02d}-outcome.json", result)


class RequestLedger:
    def __init__(self, directory, keys, *, session=None, timer=time.monotonic, sleep=time.sleep):
        self.directory, self.keys, self.timer, self.sleep = directory, keys, timer, sleep
        self.session = session if session is not None else requests.Session()
        self.session.trust_env = False
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        self.counts, self.seen, self.outcomes = Counter(), set(), []
        self.case, self.figis, self.successors = None, {}, {}
        self.last_massive, self.halted = None, False
        self.dispatched = 0

    def identify(self, url, params):
        params = params or {}
        if url in {NASDAQ_LISTED_URL, OTHER_LISTED_URL}:
            require(self.case is None and not params, "check_directory_scope")
            return "nasdaq", "directory", url.rsplit("/", 1)[-1]
        if url == EODHD_EXCHANGE_SYMBOL_LIST_URL:
            require(self.case is None and set(params) == {"symbols", "fmt", "delisted", "api_token"}, "check_directory_scope")
            require(params["symbols"] == ",".join(TARGETS) and params["fmt"] == "json"
                    and type(params["delisted"]) is int and params["delisted"] in (0, 1)
                    and params["api_token"] == self.keys["eodhd"], "check_directory_scope")
            return "eodhd", "directory", str(params["delisted"])
        require(self.case in TARGETS, "check_target_scope")
        if url == MASSIVE_TICKERS_URL:
            require(set(params) == {"ticker", "active", "market", "limit", "apiKey"}
                    and params["apiKey"] == self.keys["massive"] and type(params["limit"]) is int
                    and params["limit"] == 2, "check_listing_scope")
            identity = (params["ticker"], params["active"], params["market"])
            allowed = {(self.case, "true", "stocks"), (self.case, "true", "otc"), (self.case, "false", "stocks")}
            allowed.update((value, "true", "stocks") for value in self.successors.get(self.case, ()))
            require(identity in allowed, "check_listing_scope")
            return "massive", "listing", ":".join(identity)
        figi = self.figis.get(self.case)
        require(figi is not None and url == f"{MASSIVE_EVENTS_PREFIX}{figi}/events"
                and params == {"apiKey": self.keys["massive"]}, "check_event_scope")
        return "massive", "events", hashlib.sha256(figi.encode()).hexdigest()

    def get(self, url, **kwargs):
        require(not self.halted, "check_previous_dispatch_stopped")
        require(kwargs.get("allow_redirects") is False and kwargs.get("stream") is True
                and kwargs.get("timeout") in (15, (5, 20)), "check_transport_policy")
        provider, kind, identity = self.identify(url, kwargs.get("params"))
        key = (provider, kind, identity)
        require(key not in self.seen, "check_duplicate_request")
        require(self.counts[provider] < LIMITS[provider] and sum(self.counts.values()) < 19, "check_request_budget")
        row = {"request": sum(self.counts.values()) + 1, "provider": provider, "kind": kind,
               "target": self.case, "identity": identity, "reserved_at": now(), "attempts": 1}
        write(self.directory, f"request-{row['request']:02d}-reserved.json", row)
        self.seen.add(key)
        self.counts[provider] += 1
        if provider == "massive" and self.last_massive is not None:
            self.sleep(max(0.0, 12.5 - (self.timer() - self.last_massive)))
        started = self.timer()
        if provider == "massive":
            row["dispatch_spacing_seconds"] = None if self.last_massive is None else started - self.last_massive
            self.last_massive = started
        self.dispatched += 1
        try:
            response = self.session.get(url, **kwargs)
        except Exception:
            self.halted = True
            result = {**row, "status_code": None, "dispatch_outcome_unknown": True}
            self.outcomes.append(result)
            write(self.directory, f"request-{row['request']:02d}-outcome.json", result)
            raise CheckStopped("check_dispatch_outcome_unknown") from None
        if response.status_code in {401, 403, 429} or 300 <= response.status_code < 400:
            self.halted = True
        return MeasuredResponse(response, self, row, started)

    def close(self):
        self.session.close()


class BoundListingTransport(ListingAuthorityTransport):
    def __init__(self, ledger):
        super().__init__(session=ledger)
        self.ledger = ledger

    def fetch_massive_ticker(self, ticker, *, expected_active, market, api_key, budget):
        payload = super().fetch_massive_ticker(ticker, expected_active=expected_active, market=market, api_key=api_key, budget=budget)
        row = parse_massive_ticker(payload.body, ticker, expected_active=expected_active, market=market,
                                  retrieved_at=payload.retrieved_at, source_url=payload.source_url)
        if ticker == self.ledger.case and not expected_active and row.listing_status == "inactive" and row.composite_figi:
            self.ledger.figis[ticker] = row.composite_figi
        return payload


class BoundEventTransport(LifecycleProviderCensusTransport):
    def __init__(self, ledger):
        super().__init__(session=ledger)
        self.ledger = ledger

    def fetch_massive_ticker_events(self, *, stable_id, api_key, budget):
        result = super().fetch_massive_ticker_events(stable_id=stable_id, api_key=api_key, budget=budget)
        successors = {new for old, new, _ in result.events if old == self.ledger.case}
        if len(successors) == 1:
            self.ledger.successors[self.ledger.case] = successors
        return result


def stopped():
    for port in (8430, 39769):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise CheckStopped("check_app_port_in_use") from None


def source_scope():
    snapshot = build_active_universe_snapshot(profile_db=PROFILE, sa_db=SA)
    require(all(row.available for row in snapshot.source_status.values()), "check_source_unavailable")
    require(len(snapshot.tickers) == 186 and all(snapshot.sources_by_ticker.get(ticker) == ("sa_alpha_picks_former",)
                                               for ticker in TARGETS), "check_target_source_changed")
    return snapshot.sources_by_ticker


def unchanged_state():
    with sqlite3.connect(f"{PROFILE.as_uri()}?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        require(SaTrackingMembershipStore.installed(conn), "check_membership_schema_absent")
        require(conn.execute("SELECT count(*) FROM ticker_identity_transitions").fetchone()[0] == 0, "check_transition_present")
        require(conn.execute("SELECT count(*) FROM portfolio_positions p JOIN portfolio_accounts a ON a.id=p.account_id "
                             "WHERE UPPER(TRIM(p.symbol)) IN ('ARCH','LTHM','TA') AND p.closed_at IS NULL AND a.archived_at IS NULL").fetchone()[0] == 0,
                "check_open_position")
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND ("
                 "name LIKE 'security_lifecycle_%' OR name LIKE 'ticker_identity_%' OR name LIKE 'sa_tracking_%' OR "
                 "name IN ('ticker_meta','watchlists','watchlist_memberships','universe_source_memberships','portfolio_positions','portfolio_accounts')) "
                 "AND name<>'security_lifecycle_provider_checks' ORDER BY name")]
        return {name: hashlib.sha256(encoded(conn.execute('SELECT rowid,* FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall())).hexdigest() for name in names}


def audit(event, args):
    if event in {"subprocess.Popen", "os.system"}:
        raise CheckStopped("check_subprocess_forbidden")
    if event == "socket.getaddrinfo" and args[0] not in {"api.massive.com", "eodhd.com", "www.nasdaqtrader.com"}:
        raise CheckStopped("check_host_forbidden")
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0]))
        if path.name.startswith(".env") or path.name == "auth.json":
            raise CheckStopped("check_ambient_credentials_forbidden")


def run(directory):
    stopped()
    preflight = preflight_provider_upgrade(PROFILE)
    require(preflight["schema_version"] == "v4" and preflight["automation"] == {
        "valid": True, "enabled": False, "apply_profile_transitions": False}, "check_cutover_required")
    scope, state = source_scope(), unchanged_state()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    at = now()
    write(directory, "authorization.json", {"at": at, "targets": TARGETS, "limits": LIMITS, "max_total": 19,
          "minimum_massive_spacing_seconds": 12.5, "retry": False, "fallback": False,
          "terminal_application_authorized": False, "backfill_authorized": False})
    store = ReadOnlyProviderCredentialStore(PROFILE)
    keys = {provider: resolve_census_credential(store, provider) for provider in ("massive", "eodhd")}
    ledger = RequestLedger(directory, keys)
    material, codes = {ticker: () for ticker in TARGETS}, ()
    checks, stopped_code = [], None
    try:
        def session():
            return ProviderScanSession(at=at, massive_key=keys["massive"], eodhd_key=keys["eodhd"],
                listing_transport=BoundListingTransport(ledger), event_transport=BoundEventTransport(ledger))
        directories = session()
        material, codes = directories.directories(TARGETS)
        require(not codes and not ledger.halted, "check_directories_incomplete")
        for ticker in TARGETS:
            ledger.case = ticker
            provider = session()
            rows, failures = provider.exact(ticker)
            checks.append({"ticker": ticker, "at": at, "evidence": [evidence_dict(row) for row in (*material[ticker], *rows)],
                           "blockers": list(failures), "diagnostics": {**provider.diagnostics(),
                           "directory_checked_epoch_s": int(datetime.fromisoformat(at).timestamp()),
                           "exact_checked_epoch_s": int(datetime.fromisoformat(at).timestamp())}})
            require(not any(secret.encode() in encoded(checks[-1]) for secret in keys.values()), "check_secret_in_material")
            write(directory, f"private-{ticker}-evidence.json", checks[-1])
            require(not ledger.halted, "check_provider_stopped")
    except CheckStopped as exc:
        stopped_code = str(exc)
    except Exception:
        stopped_code = "check_unexpected_failure"
    finally:
        ledger.close()
    require(source_scope() == scope and unchanged_state() == state, "check_state_changed_before_publication")
    for check in checks:
        payload = encoded(check)
        require(not any(secret.encode() in payload for secret in keys.values()), "check_secret_in_material")
    write(directory, "private-checks.json", checks)
    require(len(ledger.outcomes) == ledger.dispatched == sum(ledger.counts.values()), "check_request_ledger_incomplete")
    persisted = ProviderCheckStore(PROFILE).record_many(checks) if checks else []
    latest = ProviderCheckStore(PROFILE).latest()
    for check, digest in zip(checks, persisted):
        require(latest[check["ticker"]]["digest"] == digest, "check_publication_mismatch")
    require(source_scope() == scope and unchanged_state() == state, "check_state_changed_after_publication")
    results = []
    for check in checks:
        result = classify_provider_listing(ticker=check["ticker"], evidence=check["evidence"], today=datetime.fromisoformat(at).date())
        results.append({"ticker": check["ticker"], "state": latest[check["ticker"]]["state"], "reasons": result.reasons,
                        "effective_date": result.effective_date, "provider_codes": check["blockers"],
                        "attended_review_available": terminal_requires_attestation(result) and set(check["blockers"]) <= {"massive_not_found"},
                        "evidence_count": len(check["evidence"]), "persisted_sha256": latest[check["ticker"]]["digest"]})
    public = {"at": at, "completed_targets": len(checks), "stopped_code": stopped_code,
              "observed_requests": dict(ledger.counts), "total_requests": ledger.dispatched,
              "minimum_observed_massive_spacing_seconds": min((row["dispatch_spacing_seconds"] for row in ledger.outcomes
                  if row.get("dispatch_spacing_seconds") is not None), default=None),
              "http_status_counts": dict(Counter(str(row["status_code"]) for row in ledger.outcomes)),
              "results": results, "unchanged_domain_tables": len(state), "universe_preserved": 186,
              "terminal_dispositions_applied": 0, "ibkr_requests": 0, "price_writes": 0,
              "app_restarted": False, "automation_enabled": False}
    write(directory, "fresh-check-summary.json", public)
    print(json.dumps(public, sort_keys=True))
    return 0 if len(checks) == 3 and stopped_code is None else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--execute-authorized-19", action="store_true", required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    sys.addaudithook(audit)
    try:
        raise SystemExit(run(args.directory))
    except CheckStopped as exc:
        print(json.dumps({"status": "stopped", "code": str(exc)}))
        raise SystemExit(2) from None
    except Exception:
        print(json.dumps({"status": "stopped", "code": "check_unexpected_failure"}))
        raise SystemExit(2) from None
