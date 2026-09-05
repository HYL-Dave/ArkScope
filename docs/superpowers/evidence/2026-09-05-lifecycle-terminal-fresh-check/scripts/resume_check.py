"""Replay the four saved directory responses, then spend only unused Massive reads."""

from collections import Counter
from datetime import datetime, timedelta
import argparse
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import stat
import sys

from src.security_lifecycle_listing_evidence import parse_nasdaq_directories


BASE_PATH = Path(__file__).resolve().parents[2] / "2026-09-05-lifecycle-terminal-cutover/scripts/fresh_check_v2.py"
spec = importlib.util.spec_from_file_location("terminal_fresh_check_v2", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
require, CheckStopped = base.require, base.CheckStopped
EXPECTED = (
    ("nasdaq", "nasdaqlisted.txt", "text/plain"),
    ("nasdaq", "otherlisted.txt", "text/plain"),
    ("eodhd", "0", "application/json"),
    ("eodhd", "1", "application/json"),
)


def private_bytes(path, *, maximum=65_536):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and info.st_mode & 0o077 == 0 and 0 < info.st_size <= maximum, "resume_private_file_invalid")
        body = stream.read(maximum + 1)
    require(len(body) == info.st_size, "resume_private_file_changed")
    return body


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "resume_timestamp_invalid")
    return parsed


class ReplayResponse:
    def __init__(self, body, content_type):
        self.body = body
        self.status_code = 200
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        pass


class DirectoryReplay:
    """No socket or requests.Session exists in the replay transport."""

    def __init__(self, bodies):
        self.bodies, self.calls = bodies, 0

    def get(self, url, **kwargs):
        expected = (
            (base.NASDAQ_LISTED_URL, {}), (base.OTHER_LISTED_URL, {}),
            (base.EODHD_EXCHANGE_SYMBOL_LIST_URL,
             {"symbols": ",".join(base.TARGETS), "fmt": "json", "delisted": 0, "api_token": "offline-replay"}),
            (base.EODHD_EXCHANGE_SYMBOL_LIST_URL,
             {"symbols": ",".join(base.TARGETS), "fmt": "json", "delisted": 1, "api_token": "offline-replay"}),
        )
        require(self.calls < 4 and (url, kwargs.get("params") or {}) == expected[self.calls], "resume_replay_request_mismatch")
        require(kwargs.get("stream") is True and kwargs.get("allow_redirects") is False, "resume_replay_transport_policy")
        result = ReplayResponse(self.bodies[self.calls], EXPECTED[self.calls][2])
        self.calls += 1
        return result

    def close(self):
        pass


def load_directory_replay(source, *, at):
    info = source.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and info.st_mode & 0o077 == 0, "resume_private_directory_invalid")
    auth_bytes = private_bytes(source / "authorization.json")
    summary_bytes = private_bytes(source / "fresh-check-summary.json")
    authorization, summary = json.loads(auth_bytes), json.loads(summary_bytes)
    require(authorization["targets"] == list(base.TARGETS) and authorization["limits"] == base.LIMITS
            and authorization["max_total"] == 19 and authorization["retry"] is False
            and authorization["fallback"] is False and authorization["terminal_application_authorized"] is False
            and authorization["backfill_authorized"] is False, "resume_authorization_mismatch")
    require(summary["at"] == authorization["at"] and summary["completed_targets"] == 0
            and summary["stopped_code"] == "check_directories_incomplete"
            and summary["observed_requests"] == {"nasdaq": 2, "eodhd": 2}
            and summary["total_requests"] == 4 and summary["http_status_counts"] == {"200": 4}
            and summary["results"] == [], "resume_remainder_not_unused")
    observed = instant(authorization["at"])
    require(timedelta(0) <= instant(at) - observed <= timedelta(hours=24), "resume_directory_expired")
    expected_reservations = {f"request-{i:02d}-reserved.json" for i in range(1, 5)}
    expected_outcomes = {f"request-{i:02d}-outcome.json" for i in range(1, 5)}
    require({p.name for p in source.glob("request-*-reserved.json")} == expected_reservations
            and {p.name for p in source.glob("request-*-outcome.json")} == expected_outcomes, "resume_request_ledger_mismatch")
    bindings = {"authorization.json": hashlib.sha256(auth_bytes).hexdigest(),
                "fresh-check-summary.json": hashlib.sha256(summary_bytes).hexdigest()}
    bodies = []
    for i, (provider, identity, content_type) in enumerate(EXPECTED, 1):
        name = f"request-{i:02d}"
        reserved_bytes = private_bytes(source / f"{name}-reserved.json")
        outcome_bytes = private_bytes(source / f"{name}-outcome.json")
        reserved, outcome = json.loads(reserved_bytes), json.loads(outcome_bytes)
        require(reserved["request"] == i and reserved["provider"] == provider and reserved["kind"] == "directory"
                and reserved["target"] is None and reserved["identity"] == identity
                and type(reserved["attempts"]) is int and reserved["attempts"] == 1
                and observed <= instant(reserved["reserved_at"]) <= instant(at), "resume_request_identity_mismatch")
        require(all(outcome.get(key) == value for key, value in reserved.items())
                and outcome["status_code"] == 200 and outcome["body_complete"] is True
                and not outcome.get("dispatch_outcome_unknown") and outcome["content_type"] == content_type,
                "resume_response_incomplete")
        body = private_bytes(source / f"private-{name}.body", maximum=(8 if provider == "nasdaq" else 1) * 1024 * 1024)
        require(hashlib.sha256(body).hexdigest() == outcome["response_sha256"]
                and type(outcome["read_bytes"]) is int and len(body) == outcome["read_bytes"], "resume_response_digest_mismatch")
        bindings[f"{name}-reserved.json"] = hashlib.sha256(reserved_bytes).hexdigest()
        bindings[f"{name}-outcome.json"] = hashlib.sha256(outcome_bytes).hexdigest()
        bindings[f"private-{name}.body"] = outcome["response_sha256"]
        bodies.append(body)

    # Revalidate timeliness now, but preserve the original observation time in evidence.
    parse_nasdaq_directories(nasdaq_bytes=bodies[0], other_bytes=bodies[1], retrieved_at=at)
    replay = DirectoryReplay(bodies)
    scanner = base.ProviderScanSession(
        at=authorization["at"], massive_key=None, eodhd_key="offline-replay",
        listing_transport=base.ListingAuthorityTransport(session=replay, now=lambda: observed),
        event_transport=base.LifecycleProviderCensusTransport(session=replay))
    material, codes = scanner.directories(base.TARGETS)
    require(not codes and replay.calls == 4, "resume_directory_replay_incomplete")
    return {"at": authorization["at"], "material": material, "bindings": bindings,
            "source_sha256": hashlib.sha256(base.encoded(bindings)).hexdigest()}


class MassiveRemainderLedger(base.RequestLedger):
    def identify(self, url, params):
        require(url == base.MASSIVE_TICKERS_URL or url.startswith(base.MASSIVE_EVENTS_PREFIX), "resume_directory_network_forbidden")
        provider, kind, identity = super().identify(url, params)
        require(provider == "massive", "resume_provider_forbidden")
        return provider, kind, identity


def claim_remainder(source, destination, *, replay, at):
    try:
        base.write(source, "massive-remainder-claim.json", {
            "at": at, "destination": str(destination), "source_sha256": replay["source_sha256"],
            "max_new_massive_requests": 15, "max_new_directory_requests": 0,
        })
    except FileExistsError:
        raise CheckStopped("resume_remainder_already_claimed") from None


def preflight():
    base.stopped()
    result = base.preflight_provider_upgrade(base.PROFILE)
    require(result["schema_version"] == "v4" and result["automation"] == {
        "valid": True, "enabled": False, "apply_profile_transitions": False}, "check_cutover_required")
    return base.source_scope(), base.unchanged_state()


def run(source, destination):
    before = preflight()
    at = base.now()
    replay = load_directory_replay(source, at=at)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    base.write(destination, "replay-binding.json", {key: replay[key] for key in ("at", "bindings", "source_sha256")})
    base.write(destination, "private-directory-material.json", {
        ticker: [base.evidence_dict(row) for row in rows] for ticker, rows in replay["material"].items()})
    # One atomic claim binds the remaining budget to one destination, before credentials.
    claim_remainder(source, destination, replay=replay, at=at)
    key = base.resolve_census_credential(base.ReadOnlyProviderCredentialStore(base.PROFILE), "massive")
    ledger = MassiveRemainderLedger(destination, {"massive": key})
    checks, stopped_code = [], None
    try:
        for ticker in base.TARGETS:
            ledger.case = ticker
            scanner = base.ProviderScanSession(
                at=at, massive_key=key, eodhd_key=None,
                listing_transport=base.BoundListingTransport(ledger), event_transport=base.BoundEventTransport(ledger))
            material, codes = scanner.exact(ticker)
            check = {"ticker": ticker, "at": at,
                     "evidence": [base.evidence_dict(row) for row in (*replay["material"][ticker], *material)],
                     "blockers": list(codes), "diagnostics": {
                         **scanner.diagnostics(), "directory_replayed_responses": 4,
                         "directory_checked_epoch_s": int(instant(replay["at"]).timestamp()),
                         "exact_checked_epoch_s": int(instant(at).timestamp()),
                     }}
            require(key.encode() not in base.encoded(check), "check_secret_in_material")
            checks.append(check)
            base.write(destination, f"private-{ticker}-evidence.json", check)
            require(not ledger.halted, "check_provider_stopped")
    except CheckStopped as exc:
        stopped_code = str(exc)
    except Exception:
        stopped_code = "check_unexpected_failure"
    finally:
        ledger.close()
    require(preflight() == before, "check_state_changed_before_publication")
    require(len(ledger.outcomes) == ledger.dispatched == sum(ledger.counts.values()), "check_request_ledger_incomplete")
    require(set(ledger.counts) <= {"massive"} and ledger.dispatched <= 15, "resume_request_budget")
    base.write(destination, "private-checks.json", checks)
    store = base.ProviderCheckStore(base.PROFILE)
    digests = store.record_many(checks) if checks else []
    latest = store.latest()
    results = []
    for check, digest in zip(checks, digests):
        ticker = check["ticker"]
        require(latest[ticker]["digest"] == digest, "check_publication_mismatch")
        decision = base.classify_provider_listing(ticker=ticker, evidence=check["evidence"], today=instant(at).date())
        results.append({"ticker": ticker, "state": latest[ticker]["state"], "reasons": decision.reasons,
                        "effective_date": decision.effective_date, "provider_codes": check["blockers"],
                        "attended_review_available": base.terminal_requires_attestation(decision)
                        and set(check["blockers"]) <= {"massive_not_found"},
                        "evidence_count": len(check["evidence"]), "persisted_sha256": digest})
    require(preflight() == before, "check_state_changed_after_publication")
    summary = {"at": at, "directory_observed_at": replay["at"], "replay_source_sha256": replay["source_sha256"],
               "completed_targets": len(checks), "stopped_code": stopped_code, "results": results,
               "observed_new_requests": dict(ledger.counts), "new_http_requests": ledger.dispatched,
               "reused_directory_responses": {"nasdaq": 2, "eodhd": 2},
               "authorization_requests_including_saved_directories": ledger.dispatched + 4,
               "http_status_counts": dict(Counter(str(row["status_code"]) for row in ledger.outcomes)),
               "minimum_observed_massive_spacing_seconds": min((row["dispatch_spacing_seconds"] for row in ledger.outcomes
                   if row.get("dispatch_spacing_seconds") is not None), default=None),
               "unchanged_domain_tables": len(before[1]), "universe_preserved": len(before[0]),
               "terminal_dispositions_applied": 0, "ibkr_requests": 0, "price_writes": 0,
               "app_restarted": False, "automation_enabled": False}
    base.write(destination, "fresh-check-summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if len(checks) == 3 and stopped_code is None else 2


def audit(event, args):
    base.audit(event, args)
    if event == "socket.getaddrinfo":
        require(args[0] == "api.massive.com", "resume_host_forbidden")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--execute-unused-massive-15", required=True, action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    sys.addaudithook(audit)
    try:
        raise SystemExit(run(args.source, args.directory))
    except CheckStopped as exc:
        print(json.dumps({"status": "stopped", "code": str(exc)}))
        raise SystemExit(2) from None
    except Exception:
        print(json.dumps({"status": "stopped", "code": "resume_unexpected_failure"}))
        raise SystemExit(2) from None
