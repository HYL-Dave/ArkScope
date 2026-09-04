"""Detached lifecycle-provider authority census.

Offline modes never resolve credentials, open application databases, or create
network clients. The live mode exists only behind a digest-, budget-, and
commit-bound acknowledgement and writes create-only normalized evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping


PACKET_DIR = Path(__file__).resolve().parent
ROOT = PACKET_DIR.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_sources.lifecycle_provider_census_transport import (  # noqa: E402
    CensusRequestBudget,
    CensusTransportFailure,
    LifecycleProviderCensusTransport,
    MassiveListingResult,
    MassiveTickerEventsResult,
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
)
from src.security_lifecycle_provider_census import (  # noqa: E402
    CENSUS_OUTCOMES,
    CensusObservation,
    classify_known_case,
    render_census_summary,
)
from src.data_provider_config import ProviderConfigMissing  # noqa: E402
from src.active_universe import (  # noqa: E402
    SOURCE_KEYS,
    ActiveUniverseUnavailable,
    build_active_universe_snapshot,
)


SPEC = (
    ROOT
    / "docs/superpowers/specs/2026-09-04-lifecycle-provider-authority-shadow-census-design.md"
)
KNOWN_CASES_FIXTURE = ROOT / "tests/fixtures/lifecycle_provider_census/known_cases.json"
REPLAY_FIXTURE = ROOT / "tests/fixtures/lifecycle_provider_census/normalized_replay.json"
ATTEMPT_2_DIR = PACKET_DIR / "attempt-2"
MODES = (
    "dry-run",
    "fixture-replay",
    "known-case-live",
    "ticker-event-revalidation",
    "universe-manifest",
)
CLOSED_OUTCOMES = tuple(sorted(CENSUS_OUTCOMES))
REQUEST_BUDGET = {"massive": 14, "eodhd": 2, "nasdaq": 2}
MAXIMUM_HTTP_REQUESTS = sum(REQUEST_BUDGET.values())
EVENT_REVALIDATION_REQUEST_BUDGET = {"massive": 1, "eodhd": 0, "nasdaq": 0}
EVENT_REVALIDATION_MAXIMUM_HTTP_REQUESTS = 1
LC_HAPN_REVALIDATION_RELATION = ("LC", "HAPN", "2026-06-22")
MASSIVE_MIN_REQUEST_INTERVAL_SECONDS = 12.5
SUMMARY_NAME = "census-summary.json"
SEAL_NAME = "SHA256SUMS"
UNIVERSE_MANIFEST_NAME = "universe-manifest.json"
UNIVERSE_ATTESTATION_NAME = "universe-manifest-attestation.json"
PRIVATE_UNIVERSE_MANIFEST_DIRNAME = "lifecycle-provider-authority-universe-manifest"

_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID = re.compile(r"^BBG[A-Z0-9_]{8,29}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_PROVIDER_TICKER = re.compile(r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*$")
_MASSIVE_TICKER_OVERRIDES = {"BRK B": "BRK.B"}
_FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "apikey",
        "api_key",
        "api_token",
        "authorization",
        "raw_body",
        "account_id",
        "user_email",
        "credential",
        "secret",
        "token",
    }
)
_LISTING_REQUESTS = (
    ("LC", False),
    ("HAPN", True),
    ("ARCH", False),
    ("CNR", True),
    ("LTHM", False),
    ("ALTM", True),
    ("TA", False),
    ("AAPL", True),
    ("SMCI", True),
)
_EVENT_CASES = ("LC", "ARCH", "LTHM", "TA", "AAPL")
_ORACLE_CASES = ("AAPL", "ARCH", "LC", "LTHM", "SMCI", "TA")


class CensusRunnerFailure(RuntimeError):
    """Closed runner failure without provider- or credential-controlled text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RepositoryState:
    head: str
    clean: bool

    def __post_init__(self) -> None:
        if _COMMIT.fullmatch(self.head) is None or type(self.clean) is not bool:
            raise ValueError("repository_state")


class _MassiveRequestPacer:
    def __init__(
        self,
        *,
        timer: Callable[[], float],
        sleeper: Callable[[float], None],
    ) -> None:
        self._timer = timer
        self._sleeper = sleeper
        self._previous_start: float | None = None

    def wait(self) -> None:
        now = self._timer()
        if self._previous_start is not None:
            target = self._previous_start + MASSIVE_MIN_REQUEST_INTERVAL_SECONDS
            if now < target:
                self._sleeper(target - now)
                now = self._timer()
            if now + 0.001 < target:
                raise CensusRunnerFailure("massive_request_pacing")
        self._previous_start = now


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def spec_sha256() -> str:
    return hashlib.sha256(SPEC.read_bytes()).hexdigest()


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _timestamp(value: str | None) -> str:
    normalized = value or _now()
    if not isinstance(normalized, str) or _UTC_TIMESTAMP.fullmatch(normalized) is None:
        raise CensusRunnerFailure("observation_timestamp")
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        raise CensusRunnerFailure("observation_timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise CensusRunnerFailure("observation_timestamp")
    return normalized


def _json_object(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise CensusRunnerFailure(code) from None
    if not isinstance(value, dict):
        raise CensusRunnerFailure(code)
    return value


def _content_digest(value: Mapping[str, object]) -> str:
    material = dict(value)
    material.pop("normalized_content_sha256", None)
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _known_cases() -> tuple[dict[str, object], ...]:
    payload = _json_object(KNOWN_CASES_FIXTURE, code="known_cases_fixture")
    if set(payload) != {"version", "cases"} or payload.get("version") != 1:
        raise CensusRunnerFailure("known_cases_fixture")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 6:
        raise CensusRunnerFailure("known_cases_fixture")
    expected_ids = {"LC", "ARCH", "LTHM", "TA", "AAPL", "SMCI"}
    if {
        row.get("case_id") for row in cases if isinstance(row, dict)
    } != expected_ids or any(
        not isinstance(row, dict)
        or set(row) != {"case_id", "source", "successor", "terminal"}
        or row["case_id"] != row["source"]
        or type(row["terminal"]) is not bool
        for row in cases
    ):
        raise CensusRunnerFailure("known_cases_fixture")
    return tuple(cases)


def _validated_replay(path: Path) -> dict[str, Any]:
    payload = _json_object(path, code="replay_fixture")
    required = {
        "version",
        "fixture_kind",
        "observation_timestamp",
        "known_cases_sha256",
        "normalized_content_sha256",
        "request_budget",
        "request_observations",
        "oracle_observations",
        "outcome_samples",
    }
    if set(payload) != required or payload.get("version") != 1:
        raise CensusRunnerFailure("replay_fixture")
    if payload.get("fixture_kind") != "closed_synthetic_normalized":
        raise CensusRunnerFailure("replay_fixture")
    expected_known_digest = hashlib.sha256(KNOWN_CASES_FIXTURE.read_bytes()).hexdigest()
    if payload.get("known_cases_sha256") != expected_known_digest:
        raise CensusRunnerFailure("known_cases_fixture_digest")
    expected_content_digest = payload.get("normalized_content_sha256")
    if (
        not isinstance(expected_content_digest, str)
        or _SHA256.fullmatch(expected_content_digest) is None
        or expected_content_digest != _content_digest(payload)
    ):
        raise CensusRunnerFailure("replay_fixture_digest")
    if payload.get("request_budget") != REQUEST_BUDGET:
        raise CensusRunnerFailure("replay_fixture_budget")
    _timestamp(payload.get("observation_timestamp"))
    return payload


def _closed_request_observations(rows: object) -> tuple[dict[str, object], ...]:
    allowed = {
        "provider",
        "endpoint_family",
        "requested_identifiers",
        "expected_state",
        "attempts",
        "body_bytes",
        "http_status_family",
        "elapsed_ms",
        "response_sha256s",
        "parsed_fields",
        "result_code",
    }
    if not isinstance(rows, list):
        raise CensusRunnerFailure("replay_request_observations")
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != allowed:
            raise CensusRunnerFailure("replay_request_observations")
        if row.get("provider") not in REQUEST_BUDGET:
            raise CensusRunnerFailure("replay_request_observations")
        if row.get("result_code") not in CENSUS_OUTCOMES:
            raise CensusRunnerFailure("replay_request_observations")
        attempts = row.get("attempts")
        body_bytes = row.get("body_bytes")
        elapsed = row.get("elapsed_ms")
        digests = row.get("response_sha256s")
        if (
            type(attempts) is not int
            or attempts < 0
            or type(body_bytes) is not int
            or body_bytes < 0
            or not isinstance(elapsed, (int, float))
            or elapsed < 0
            or not isinstance(digests, list)
            or any(
                not isinstance(item, str) or _SHA256.fullmatch(item) is None
                for item in digests
            )
            or not isinstance(row.get("parsed_fields"), dict)
        ):
            raise CensusRunnerFailure("replay_request_observations")
        normalized.append(dict(row))
    return tuple(normalized)


def _oracle_results(observation_rows: object) -> list[dict[str, object]]:
    if not isinstance(observation_rows, list):
        raise CensusRunnerFailure("replay_oracle_observations")
    try:
        observations = tuple(CensusObservation(**row) for row in observation_rows)
        results = tuple(classify_known_case(case_id, observations) for case_id in _ORACLE_CASES)
    except (TypeError, ValueError):
        raise CensusRunnerFailure("replay_oracle_observations") from None
    return json.loads(render_census_summary(results))["results"]


def _outcome_samples(rows: object) -> tuple[dict[str, str], ...]:
    if not isinstance(rows, list):
        raise CensusRunnerFailure("replay_outcome_samples")
    normalized: list[dict[str, str]] = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"sample_id", "result_code", "reason"}
            or row.get("result_code") not in CENSUS_OUTCOMES
            or any(not isinstance(value, str) or not value for value in row.values())
        ):
            raise CensusRunnerFailure("replay_outcome_samples")
        normalized.append(
            {
                "sample_id": row["sample_id"],
                "outcome": row["result_code"],
                "reason": row["reason"],
            }
        )
    if {row["outcome"] for row in normalized} != set(CENSUS_OUTCOMES):
        raise CensusRunnerFailure("replay_outcome_samples")
    return tuple(sorted(normalized, key=lambda row: row["sample_id"]))


def _request_accounting(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    by_provider = {
        provider: {"attempts": 0, "body_bytes": 0}
        for provider in sorted(REQUEST_BUDGET)
    }
    for row in rows:
        provider = str(row["provider"])
        by_provider[provider]["attempts"] += int(row["attempts"])
        by_provider[provider]["body_bytes"] += int(row["body_bytes"])
    if any(
        values["attempts"] > REQUEST_BUDGET[provider]
        for provider, values in by_provider.items()
    ):
        raise CensusRunnerFailure("request_accounting")
    return {
        "maximum_http_requests": MAXIMUM_HTTP_REQUESTS,
        "providers": by_provider,
        "total_attempts": sum(row["attempts"] for row in by_provider.values()),
        "total_body_bytes": sum(row["body_bytes"] for row in by_provider.values()),
    }


def _dry_run(timestamp: str) -> dict[str, object]:
    return {
        "version": 1,
        "mode": "dry-run",
        "observation_timestamp": timestamp,
        "spec_sha256": spec_sha256(),
        "request_budget": dict(REQUEST_BUDGET),
        "maximum_http_requests": MAXIMUM_HTTP_REQUESTS,
        "known_cases": [row["case_id"] for row in _known_cases()],
        "lanes": {
            provider: {"executed": False, "reason": "dry_run"}
            for provider in sorted(REQUEST_BUDGET)
        },
    }


def _fixture_replay(path: Path, timestamp: str) -> dict[str, object]:
    fixture = _validated_replay(path)
    requests = _closed_request_observations(fixture["request_observations"])
    results = _oracle_results(fixture["oracle_observations"])
    cases = {str(row["case_id"]): row for row in _known_cases()}
    for result in results:
        expected = cases[str(result["case_id"])]
        if result["outcome"] != "confirmed" or result["successor"] != expected["successor"]:
            raise CensusRunnerFailure("replay_oracle_mismatch")
    return {
        "version": 1,
        "mode": "fixture-replay",
        "observation_timestamp": timestamp,
        "spec_sha256": spec_sha256(),
        "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "request_budget": dict(REQUEST_BUDGET),
        "maximum_http_requests": MAXIMUM_HTTP_REQUESTS,
        "request_accounting": _request_accounting(requests),
        "lanes": {
            provider: {"executed": True, "reason": "synthetic_fixture_replay"}
            for provider in sorted(REQUEST_BUDGET)
        },
        "request_observations": list(requests),
        "oracle": json.loads(render_census_summary(
            [
                classify_known_case(
                    case_id,
                    tuple(CensusObservation(**row) for row in fixture["oracle_observations"]),
                )
                for case_id in _ORACLE_CASES
            ]
        )),
        "outcome_samples": list(_outcome_samples(fixture["outcome_samples"])),
    }


def live_acknowledgement(*, spec_sha256: str, admitted_commit: str) -> str:
    if _SHA256.fullmatch(spec_sha256) is None or _COMMIT.fullmatch(admitted_commit) is None:
        raise ValueError("live_acknowledgement")
    return (
        f"SPEC_SHA256={spec_sha256};"
        "BUDGET=massive:14,eodhd:2,nasdaq:2;"
        f"ADMITTED_COMMIT={admitted_commit}"
    )


def attempt_2_summary_sha256() -> str:
    verify_seal(output_dir=ATTEMPT_2_DIR)
    return hashlib.sha256((ATTEMPT_2_DIR / SUMMARY_NAME).read_bytes()).hexdigest()


def event_revalidation_acknowledgement(
    *, spec_sha256: str, source_sha256: str, admitted_commit: str
) -> str:
    if (
        _SHA256.fullmatch(spec_sha256) is None
        or _SHA256.fullmatch(source_sha256) is None
        or _COMMIT.fullmatch(admitted_commit) is None
    ):
        raise ValueError("event_revalidation_acknowledgement")
    return (
        f"SPEC_SHA256={spec_sha256};"
        "BUDGET=massive:1,eodhd:0,nasdaq:0;"
        f"SOURCE_SHA256={source_sha256};"
        f"ADMITTED_COMMIT={admitted_commit}"
    )


def universe_manifest_acknowledgement(*, spec_sha256: str, admitted_commit: str) -> str:
    if (
        _SHA256.fullmatch(spec_sha256) is None
        or _COMMIT.fullmatch(admitted_commit) is None
    ):
        raise ValueError("universe_manifest_acknowledgement")
    return (
        f"SPEC_SHA256={spec_sha256};"
        "MODE=universe-manifest;NETWORK=0;"
        f"ADMITTED_COMMIT={admitted_commit}"
    )


def inspect_repository_state(root: Path = ROOT) -> RepositoryState:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        raise CensusRunnerFailure("live_repository_state") from None
    try:
        return RepositoryState(head=head, clean=not bool(status.strip()))
    except ValueError:
        raise CensusRunnerFailure("live_repository_state") from None


def _assert_live_admission(
    *,
    mode: str,
    acknowledgement: str | None,
    admitted_commit: str | None,
    repository_state: RepositoryState | None,
    output_dir: Path,
    production_db_path: Path | None,
) -> None:
    if not isinstance(admitted_commit, str) or _COMMIT.fullmatch(admitted_commit) is None:
        raise CensusRunnerFailure("live_acknowledgement")
    if mode == "known-case-live":
        expected = live_acknowledgement(
            spec_sha256=spec_sha256(), admitted_commit=admitted_commit
        )
    elif mode == "ticker-event-revalidation":
        expected = event_revalidation_acknowledgement(
            spec_sha256=spec_sha256(),
            source_sha256=attempt_2_summary_sha256(),
            admitted_commit=admitted_commit,
        )
    else:
        raise CensusRunnerFailure("census_mode")
    if acknowledgement != expected:
        raise CensusRunnerFailure("live_acknowledgement")
    state = repository_state or inspect_repository_state()
    if state.head != admitted_commit or not state.clean:
        raise CensusRunnerFailure("live_repository_state")
    if production_db_path is not None:
        raise CensusRunnerFailure("production_database_prohibited")
    for name in (SUMMARY_NAME, SEAL_NAME):
        if (output_dir / name).exists():
            raise CensusRunnerFailure("packet_output_exists")


def _assert_universe_manifest_admission(
    *,
    acknowledgement: str | None,
    admitted_commit: str | None,
    repository_state: RepositoryState | None,
    profile_db_path: Path | None,
    sa_db_path: Path | None,
    private_output_dir: Path | None,
    public_output_dir: Path,
) -> tuple[Path, Path, Path]:
    if (
        not isinstance(admitted_commit, str)
        or _COMMIT.fullmatch(admitted_commit) is None
    ):
        raise CensusRunnerFailure("live_acknowledgement")
    expected = universe_manifest_acknowledgement(
        spec_sha256=spec_sha256(), admitted_commit=admitted_commit
    )
    if acknowledgement != expected:
        raise CensusRunnerFailure("live_acknowledgement")
    state = repository_state or inspect_repository_state()
    if state.head != admitted_commit or not state.clean:
        raise CensusRunnerFailure("live_repository_state")
    if profile_db_path is None or sa_db_path is None or private_output_dir is None:
        raise CensusRunnerFailure("universe_manifest_paths_required")

    profile = profile_db_path.resolve()
    sa = sa_db_path.resolve()
    private = private_output_dir.resolve()
    public = public_output_dir.resolve()
    if not profile.is_file() or not sa.is_file():
        raise CensusRunnerFailure("universe_manifest_database_unavailable")
    expected_private = (
        profile.parent / "private_evidence" / PRIVATE_UNIVERSE_MANIFEST_DIRNAME
    ).resolve()
    if private != expected_private:
        raise CensusRunnerFailure("universe_manifest_private_path")
    if (
        private == public
        or private in public.parents
        or public in private.parents
        or private.exists()
        or public.exists()
    ):
        raise CensusRunnerFailure("packet_output_exists")
    return profile, sa, private


def _failure_outcome(error: CensusTransportFailure) -> str:
    code = error.code
    if not isinstance(code, str) or _FAILURE_CODE.fullmatch(code) is None:
        raise CensusRunnerFailure("transport_failure_code")
    if code.endswith("_unauthorized"):
        return "not_entitled"
    if code.endswith("_not_found"):
        return "coverage_limited"
    if any(
        marker in code
        for marker in (
            "ambiguous",
            "mismatch",
            "invalid",
            "duplicate",
            "unsupported",
        )
    ):
        return "ambiguous"
    return "provider_unavailable"


def _elapsed_ms(start: float, timer: Callable[[], float]) -> float:
    return round(max(0.0, (timer() - start) * 1000.0), 3)


def _success_request(
    *,
    provider: str,
    endpoint_family: str,
    requested: tuple[str, ...],
    expected: str,
    attempts: int,
    body_bytes: int,
    response_sha256s: tuple[str, ...],
    parsed_fields: Mapping[str, object],
    elapsed_ms: float,
    result_code: str = "confirmed",
) -> dict[str, object]:
    if result_code not in CENSUS_OUTCOMES:
        raise CensusRunnerFailure("request_result_code")
    return {
        "provider": provider,
        "endpoint_family": endpoint_family,
        "requested_identifiers": list(requested),
        "expected_state": expected,
        "attempts": attempts,
        "body_bytes": body_bytes,
        "http_status_family": "2xx",
        "elapsed_ms": elapsed_ms,
        "response_sha256s": list(response_sha256s),
        "parsed_fields": dict(parsed_fields),
        "result_code": result_code,
    }


def _failed_request(
    *,
    provider: str,
    endpoint_family: str,
    requested: tuple[str, ...],
    expected: str,
    attempts: int,
    error: CensusTransportFailure,
    elapsed_ms: float,
) -> dict[str, object]:
    family = None
    if error.status_code is not None:
        family = f"{error.status_code // 100}xx"
    return {
        "provider": provider,
        "endpoint_family": endpoint_family,
        "requested_identifiers": list(requested),
        "expected_state": expected,
        "attempts": attempts,
        "body_bytes": 0,
        "http_status_family": family,
        "elapsed_ms": elapsed_ms,
        "response_sha256s": [],
        "parsed_fields": {"failure_code": error.code},
        "result_code": _failure_outcome(error),
    }


def _nasdaq_symbols(body: bytes, requested: set[str]) -> list[str]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CensusRunnerFailure("nasdaq_directory_invalid") from None
    matched: set[str] = set()
    for index, line in enumerate(text.splitlines()):
        if index == 0 or not line or line.startswith("File Creation Time:"):
            continue
        ticker = line.split("|", 1)[0]
        if ticker in requested:
            matched.add(ticker)
    return sorted(matched)


def _attempt_2_lc_stable_id() -> str:
    verify_seal(output_dir=ATTEMPT_2_DIR)
    packet = _json_object(ATTEMPT_2_DIR / SUMMARY_NAME, code="attempt_2_packet")
    if packet.get("mode") != "known-case-live":
        raise CensusRunnerFailure("attempt_2_packet")
    rows = packet.get("request_observations")
    if not isinstance(rows, list):
        raise CensusRunnerFailure("attempt_2_packet")

    stable_ids: list[str] = []
    for ticker, active in (("LC", False), ("HAPN", True)):
        matches = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("provider") == "massive"
            and row.get("endpoint_family") == "all_tickers"
            and row.get("requested_identifiers") == [ticker]
            and row.get("attempts") == 1
            and row.get("result_code") == "confirmed"
        ]
        if len(matches) != 1:
            raise CensusRunnerFailure("attempt_2_identity")
        parsed = matches[0].get("parsed_fields")
        if (
            not isinstance(parsed, dict)
            or parsed.get("ticker") != ticker
            or parsed.get("found") is not True
            or parsed.get("active") is not active
        ):
            raise CensusRunnerFailure("attempt_2_identity")
        stable_id = parsed.get("stable_id")
        if not isinstance(stable_id, str) or _STABLE_ID.fullmatch(stable_id) is None:
            raise CensusRunnerFailure("attempt_2_identity")
        stable_ids.append(stable_id)
    if len(set(stable_ids)) != 1:
        raise CensusRunnerFailure("attempt_2_identity")
    return stable_ids[0]


def _run_event_revalidation(
    *,
    credential_resolver: Callable[[str], str],
    transport: LifecycleProviderCensusTransport,
    timestamp: str,
    admitted_commit: str,
    timer: Callable[[], float],
) -> dict[str, object]:
    stable_id = _attempt_2_lc_stable_id()
    source_digest = attempt_2_summary_sha256()
    budget = CensusRequestBudget(max_massive_requests=1)
    expected_relation = LC_HAPN_REVALIDATION_RELATION
    expected_state = "exact_lc_to_hapn"
    requests: list[dict[str, object]] = []
    lane_reason = "executed"

    try:
        massive_key = credential_resolver("massive")
    except ProviderConfigMissing:
        massive_key = None
        lane_reason = "credential_unavailable"
    except Exception:
        raise CensusRunnerFailure("credential_resolution_failed") from None

    outcome = "credential_unavailable"
    if massive_key is None:
        requests.append(
            {
                "provider": "massive",
                "endpoint_family": "ticker_events",
                "requested_identifiers": [stable_id],
                "expected_state": expected_state,
                "attempts": 0,
                "body_bytes": 0,
                "http_status_family": None,
                "elapsed_ms": 0.0,
                "response_sha256s": [],
                "parsed_fields": {},
                "result_code": outcome,
            }
        )
    else:
        before = budget.massive_requests
        started = timer()
        try:
            result = transport.fetch_massive_ticker_events(
                stable_id=stable_id,
                api_key=massive_key,
                budget=budget,
            )
        except CensusTransportFailure as error:
            failed = _failed_request(
                provider="massive",
                endpoint_family="ticker_events",
                requested=(stable_id,),
                expected=expected_state,
                attempts=budget.massive_requests - before,
                error=error,
                elapsed_ms=_elapsed_ms(started, timer),
            )
            requests.append(failed)
            outcome = str(failed["result_code"])
        else:
            source_relations = tuple(
                event for event in result.events if event[0] == "LC"
            )
            if expected_relation in result.events and source_relations == (
                expected_relation,
            ):
                outcome = "confirmed"
            elif source_relations:
                outcome = "contradicted"
            else:
                outcome = "ambiguous"
            requests.append(
                _success_request(
                    provider="massive",
                    endpoint_family="ticker_events",
                    requested=(stable_id,),
                    expected=expected_state,
                    attempts=budget.massive_requests - before,
                    body_bytes=result.response_bytes,
                    response_sha256s=(result.response_sha256,),
                    parsed_fields={
                        "stable_id": result.stable_id,
                        "events": [list(event) for event in result.events],
                    },
                    elapsed_ms=_elapsed_ms(started, timer),
                    result_code=outcome,
                )
            )

    diagnostics = dict(transport.diagnostics(budget))
    if (
        diagnostics.get("massive_requests", 0) > 1
        or diagnostics.get("eodhd_requests", 0) != 0
        or diagnostics.get("nasdaq_requests", 0) != 0
    ):
        raise CensusRunnerFailure("request_accounting")
    providers = {
        provider: {
            "attempts": diagnostics.get(f"{provider}_requests", 0),
            "body_bytes": diagnostics.get(f"{provider}_body_bytes", 0),
        }
        for provider in sorted(EVENT_REVALIDATION_REQUEST_BUDGET)
    }
    return {
        "version": 1,
        "mode": "ticker-event-revalidation",
        "observation_timestamp": timestamp,
        "spec_sha256": spec_sha256(),
        "source_packet_sha256": source_digest,
        "admitted_commit": admitted_commit,
        "request_budget": dict(EVENT_REVALIDATION_REQUEST_BUDGET),
        "maximum_http_requests": EVENT_REVALIDATION_MAXIMUM_HTTP_REQUESTS,
        "request_accounting": {
            "maximum_http_requests": EVENT_REVALIDATION_MAXIMUM_HTTP_REQUESTS,
            "providers": providers,
            "total_attempts": sum(row["attempts"] for row in providers.values()),
            "total_body_bytes": sum(row["body_bytes"] for row in providers.values()),
        },
        "lanes": {
            "massive": {
                "executed": lane_reason == "executed",
                "reason": lane_reason,
            },
            "eodhd": {"executed": False, "reason": "not_in_manifest"},
            "nasdaq": {"executed": False, "reason": "not_in_manifest"},
        },
        "request_observations": requests,
        "relation": {
            "source_ticker": expected_relation[0],
            "successor_ticker": expected_relation[1],
            "effective_date": expected_relation[2],
            "outcome": outcome,
        },
    }


def _run_known_case_live(
    *,
    credential_resolver: Callable[[str], str],
    transport: LifecycleProviderCensusTransport,
    timestamp: str,
    admitted_commit: str,
    timer: Callable[[], float],
    sleeper: Callable[[float], None],
) -> dict[str, object]:
    budget = CensusRequestBudget()
    massive_pacer = _MassiveRequestPacer(timer=timer, sleeper=sleeper)
    requests: list[dict[str, object]] = []
    oracle_observations: list[CensusObservation] = []
    listings: dict[str, MassiveListingResult] = {}
    lane_reasons: dict[str, str] = {}

    try:
        massive_key = credential_resolver("massive")
    except ProviderConfigMissing:
        massive_key = None
        lane_reasons["massive"] = "credential_unavailable"
    except Exception:
        raise CensusRunnerFailure("credential_resolution_failed") from None
    if massive_key is not None:
        lane_reasons["massive"] = "executed"
        for ticker, expected_active in _LISTING_REQUESTS:
            massive_pacer.wait()
            before = budget.massive_requests
            started = timer()
            try:
                result = transport.fetch_massive_listing(
                    ticker,
                    expected_active=expected_active,
                    api_key=massive_key,
                    budget=budget,
                )
            except CensusTransportFailure as error:
                requests.append(
                    _failed_request(
                        provider="massive",
                        endpoint_family="all_tickers",
                        requested=(ticker,),
                        expected="active" if expected_active else "inactive",
                        attempts=budget.massive_requests - before,
                        error=error,
                        elapsed_ms=_elapsed_ms(started, timer),
                    )
                )
                oracle_observations.append(
                    CensusObservation(
                        provider="massive",
                        axis="listing_state",
                        source_ticker=ticker,
                        successor_ticker=None,
                        active=None,
                        stable_id=None,
                        effective_date=None,
                        complete=False,
                    )
                )
                continue
            listings[ticker] = result
            requests.append(
                _success_request(
                    provider="massive",
                    endpoint_family="all_tickers",
                    requested=(ticker,),
                    expected="active" if expected_active else "inactive",
                    attempts=budget.massive_requests - before,
                    body_bytes=result.response_bytes,
                    response_sha256s=(result.response_sha256,),
                    parsed_fields={
                        "ticker": result.ticker,
                        "found": result.found,
                        "active": result.active,
                        "stable_id": result.stable_id,
                        "delisted_date": result.delisted_date,
                    },
                    elapsed_ms=_elapsed_ms(started, timer),
                    result_code="confirmed" if result.found else "coverage_limited",
                )
            )
            oracle_observations.append(
                CensusObservation(
                    provider="massive",
                    axis="listing_state",
                    source_ticker=ticker,
                    successor_ticker=None,
                    active=result.active,
                    stable_id=result.stable_id,
                    effective_date=None,
                    complete=result.found and result.active is not None,
                )
            )

        for ticker in _EVENT_CASES:
            listing = listings.get(ticker)
            if listing is None or listing.stable_id is None:
                requests.append(
                    {
                        "provider": "massive",
                        "endpoint_family": "ticker_events",
                        "requested_identifiers": [ticker],
                        "expected_state": "exact_ticker_change_contract",
                        "attempts": 0,
                        "body_bytes": 0,
                        "http_status_family": None,
                        "elapsed_ms": 0.0,
                        "response_sha256s": [],
                        "parsed_fields": {},
                        "result_code": "ambiguous",
                    }
                )
                continue
            massive_pacer.wait()
            before = budget.massive_requests
            started = timer()
            try:
                event_result = transport.fetch_massive_ticker_events(
                    stable_id=listing.stable_id,
                    api_key=massive_key,
                    budget=budget,
                )
            except CensusTransportFailure as error:
                requests.append(
                    _failed_request(
                        provider="massive",
                        endpoint_family="ticker_events",
                        requested=(listing.stable_id,),
                        expected="exact_ticker_change_contract",
                        attempts=budget.massive_requests - before,
                        error=error,
                        elapsed_ms=_elapsed_ms(started, timer),
                    )
                )
                continue
            requests.append(
                _success_request(
                    provider="massive",
                    endpoint_family="ticker_events",
                    requested=(listing.stable_id,),
                    expected="exact_ticker_change_contract",
                    attempts=budget.massive_requests - before,
                    body_bytes=event_result.response_bytes,
                    response_sha256s=(event_result.response_sha256,),
                    parsed_fields={
                        "stable_id": event_result.stable_id,
                        "events": [list(event) for event in event_result.events],
                    },
                    elapsed_ms=_elapsed_ms(started, timer),
                )
            )
            for source, successor, effective_date in event_result.events:
                oracle_observations.append(
                    CensusObservation(
                        provider="massive",
                        axis="ticker_change",
                        source_ticker=source,
                        successor_ticker=successor,
                        active=None,
                        stable_id=event_result.stable_id,
                        effective_date=effective_date,
                        complete=True,
                    )
                )
    else:
        for ticker, expected_active in _LISTING_REQUESTS:
            requests.append(
                {
                    "provider": "massive",
                    "endpoint_family": "all_tickers",
                    "requested_identifiers": [ticker],
                    "expected_state": "active" if expected_active else "inactive",
                    "attempts": 0,
                    "body_bytes": 0,
                    "http_status_family": None,
                    "elapsed_ms": 0.0,
                    "response_sha256s": [],
                    "parsed_fields": {},
                    "result_code": "credential_unavailable",
                }
            )

    manifest = tuple(sorted(ticker for ticker, _ in _LISTING_REQUESTS))
    try:
        eodhd_key = credential_resolver("eodhd")
    except ProviderConfigMissing:
        eodhd_key = None
        lane_reasons["eodhd"] = "credential_unavailable"
    except Exception:
        raise CensusRunnerFailure("credential_resolution_failed") from None
    if eodhd_key is not None:
        lane_reasons["eodhd"] = "executed"
        before = budget.eodhd_requests
        started = timer()
        try:
            result = transport.fetch_eodhd_symbol_sets(
                symbols=manifest, api_key=eodhd_key, budget=budget
            )
        except CensusTransportFailure as error:
            requests.append(
                _failed_request(
                    provider="eodhd",
                    endpoint_family="exchange_symbol_list",
                    requested=manifest,
                    expected="active_and_delisted_partition",
                    attempts=budget.eodhd_requests - before,
                    error=error,
                    elapsed_ms=_elapsed_ms(started, timer),
                )
            )
        else:
            requests.append(
                _success_request(
                    provider="eodhd",
                    endpoint_family="exchange_symbol_list",
                    requested=manifest,
                    expected="active_and_delisted_partition",
                    attempts=budget.eodhd_requests - before,
                    body_bytes=result.active_response_bytes + result.delisted_response_bytes,
                    response_sha256s=(
                        result.active_response_sha256,
                        result.delisted_response_sha256,
                    ),
                    parsed_fields={
                        "active": list(result.active),
                        "delisted": list(result.delisted),
                        "unreported": list(result.unreported),
                        "complete": result.complete,
                    },
                    elapsed_ms=_elapsed_ms(started, timer),
                    result_code="confirmed" if result.complete else "ambiguous",
                )
            )
    else:
        requests.append(
            {
                "provider": "eodhd",
                "endpoint_family": "exchange_symbol_list",
                "requested_identifiers": list(manifest),
                "expected_state": "active_and_delisted_partition",
                "attempts": 0,
                "body_bytes": 0,
                "http_status_family": None,
                "elapsed_ms": 0.0,
                "response_sha256s": [],
                "parsed_fields": {},
                "result_code": "credential_unavailable",
            }
        )

    lane_reasons["nasdaq"] = "executed"
    requested_set = set(manifest)
    for url, family in (
        (NASDAQ_LISTED_URL, "nasdaq_listed"),
        (OTHER_LISTED_URL, "other_listed"),
    ):
        before = budget.nasdaq_requests
        started = timer()
        try:
            result = transport.fetch_nasdaq_directory(url, budget=budget)
        except CensusTransportFailure as error:
            requests.append(
                _failed_request(
                    provider="nasdaq",
                    endpoint_family=family,
                    requested=manifest,
                    expected="current_directory",
                    attempts=budget.nasdaq_requests - before,
                    error=error,
                    elapsed_ms=_elapsed_ms(started, timer),
                )
            )
        else:
            requests.append(
                _success_request(
                    provider="nasdaq",
                    endpoint_family=family,
                    requested=manifest,
                    expected="current_directory",
                    attempts=budget.nasdaq_requests - before,
                    body_bytes=result.response_bytes,
                    response_sha256s=(result.response_sha256,),
                    parsed_fields={"matched": _nasdaq_symbols(result.body, requested_set)},
                    elapsed_ms=_elapsed_ms(started, timer),
                )
            )

    oracle = [
        classify_known_case(case_id, oracle_observations) for case_id in _ORACLE_CASES
    ]
    diagnostics = dict(transport.diagnostics(budget))
    if (
        diagnostics.get("massive_requests", 0) > REQUEST_BUDGET["massive"]
        or diagnostics.get("eodhd_requests", 0) > REQUEST_BUDGET["eodhd"]
        or diagnostics.get("nasdaq_requests", 0) > REQUEST_BUDGET["nasdaq"]
    ):
        raise CensusRunnerFailure("request_accounting")
    return {
        "version": 1,
        "mode": "known-case-live",
        "observation_timestamp": timestamp,
        "spec_sha256": spec_sha256(),
        "admitted_commit": admitted_commit,
        "known_cases_sha256": hashlib.sha256(KNOWN_CASES_FIXTURE.read_bytes()).hexdigest(),
        "request_budget": dict(REQUEST_BUDGET),
        "maximum_http_requests": MAXIMUM_HTTP_REQUESTS,
        "request_accounting": {
            "maximum_http_requests": MAXIMUM_HTTP_REQUESTS,
            "providers": {
                "massive": {
                    "attempts": diagnostics.get("massive_requests", 0),
                    "body_bytes": diagnostics.get("massive_body_bytes", 0),
                },
                "eodhd": {
                    "attempts": diagnostics.get("eodhd_requests", 0),
                    "body_bytes": diagnostics.get("eodhd_body_bytes", 0),
                },
                "nasdaq": {
                    "attempts": diagnostics.get("nasdaq_requests", 0),
                    "body_bytes": diagnostics.get("nasdaq_body_bytes", 0),
                },
            },
            "total_attempts": sum(
                diagnostics.get(name, 0)
                for name in ("massive_requests", "eodhd_requests", "nasdaq_requests")
            ),
            "total_body_bytes": sum(
                diagnostics.get(name, 0)
                for name in (
                    "massive_body_bytes",
                    "eodhd_body_bytes",
                    "nasdaq_body_bytes",
                )
            ),
        },
        "lanes": {
            provider: {
                "executed": lane_reasons.get(provider) == "executed",
                "reason": lane_reasons.get(provider, "provider_unavailable"),
            }
            for provider in sorted(REQUEST_BUDGET)
        },
        "request_observations": requests,
        "oracle": json.loads(render_census_summary(oracle)),
        "outcome_samples": [],
    }


def digest_tickers(tickers: tuple[str, ...]) -> str:
    if (
        not isinstance(tickers, tuple)
        or not tickers
        or any(not isinstance(ticker, str) or not ticker for ticker in tickers)
        or tuple(sorted(set(tickers))) != tickers
    ):
        raise CensusRunnerFailure("universe_manifest_tickers_invalid")
    return hashlib.sha256(canonical_json(list(tickers)).encode("utf-8")).hexdigest()


def build_universe_manifest(
    rows: Iterable[tuple[str, tuple[str, ...]]],
    *,
    observation_timestamp: str,
    admitted_commit: str,
) -> dict[str, object]:
    timestamp = _timestamp(observation_timestamp)
    if _COMMIT.fullmatch(admitted_commit) is None:
        raise CensusRunnerFailure("universe_manifest_commit")

    seen: set[str] = set()
    normalized_rows: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise CensusRunnerFailure("universe_manifest_row_invalid")
        ticker, sources = row
        if not isinstance(ticker, str):
            raise CensusRunnerFailure("universe_manifest_ticker_invalid")
        normalized_ticker = ticker.strip().upper()
        if normalized_ticker in seen:
            raise CensusRunnerFailure("universe_manifest_ticker_duplicate")
        seen.add(normalized_ticker)
        massive_ticker = _MASSIVE_TICKER_OVERRIDES.get(normalized_ticker)
        if massive_ticker is None and _PROVIDER_TICKER.fullmatch(normalized_ticker):
            massive_ticker = normalized_ticker
        if (
            ticker != normalized_ticker
            or massive_ticker is None
            or _PROVIDER_TICKER.fullmatch(massive_ticker) is None
        ):
            raise CensusRunnerFailure("universe_manifest_ticker_invalid")
        if (
            not isinstance(sources, tuple)
            or not sources
            or any(source not in SOURCE_KEYS for source in sources)
            or len(sources) != len(set(sources))
        ):
            raise CensusRunnerFailure("universe_manifest_sources_invalid")
        normalized_rows.append(
            {
                "ticker": normalized_ticker,
                "massive_ticker": massive_ticker,
                "sources": sorted(sources),
            }
        )

    normalized_rows.sort(key=lambda item: str(item["ticker"]))
    if not normalized_rows:
        raise CensusRunnerFailure("universe_manifest_empty")
    tickers = tuple(str(row["ticker"]) for row in normalized_rows)
    rows_digest = hashlib.sha256(
        canonical_json(normalized_rows).encode("utf-8")
    ).hexdigest()
    count = len(normalized_rows)
    return {
        "version": 1,
        "mode": "universe-manifest",
        "observation_timestamp": timestamp,
        "spec_sha256": spec_sha256(),
        "admitted_commit": admitted_commit,
        "count": count,
        "tickers": list(tickers),
        "tickers_sha256": digest_tickers(tickers),
        "rows": normalized_rows,
        "rows_sha256": rows_digest,
        "active_pass_request_budget": {
            "massive": count,
            "eodhd": 2,
            "nasdaq": 2,
            "exact_http_requests": count + 4,
        },
        "active_pass_status": "not_authorized",
    }


def _source_warning_counts(snapshot: object) -> dict[str, int]:
    statuses = getattr(snapshot, "source_status", None)
    if not isinstance(statuses, dict) or set(statuses) != set(SOURCE_KEYS):
        raise CensusRunnerFailure("universe_manifest_source_status_invalid")
    counts: Counter[str] = Counter()
    for status in statuses.values():
        warnings = getattr(status, "warnings", None)
        if not isinstance(warnings, tuple) or any(
            not isinstance(warning, str)
            or not warning
            or len(warning) > 128
            or not warning.isprintable()
            for warning in warnings
        ):
            raise CensusRunnerFailure("universe_manifest_source_status_invalid")
        counts.update(warnings)
    return dict(sorted(counts.items()))


def _universe_manifest_attestation(
    packet: Mapping[str, object], *, source_warning_counts: Mapping[str, int]
) -> dict[str, object]:
    rows = packet.get("rows")
    if not isinstance(rows, list):
        raise CensusRunnerFailure("universe_manifest_row_invalid")
    source_counts = {source: 0 for source in SOURCE_KEYS}
    override_count = 0
    for row in rows:
        if not isinstance(row, dict):
            raise CensusRunnerFailure("universe_manifest_row_invalid")
        ticker = row.get("ticker")
        massive_ticker = row.get("massive_ticker")
        sources = row.get("sources")
        if not isinstance(ticker, str) or not isinstance(massive_ticker, str):
            raise CensusRunnerFailure("universe_manifest_row_invalid")
        if ticker != massive_ticker:
            override_count += 1
        if not isinstance(sources, list):
            raise CensusRunnerFailure("universe_manifest_row_invalid")
        for source in sources:
            if source not in source_counts:
                raise CensusRunnerFailure("universe_manifest_sources_invalid")
            source_counts[source] += 1
    if any(
        type(count) is not int or count < 0 for count in source_warning_counts.values()
    ):
        raise CensusRunnerFailure("universe_manifest_source_status_invalid")

    private_digest = hashlib.sha256(
        canonical_json(dict(packet)).encode("utf-8")
    ).hexdigest()
    return {
        "version": 1,
        "mode": "universe-manifest-attestation",
        "observation_timestamp": packet["observation_timestamp"],
        "spec_sha256": packet["spec_sha256"],
        "admitted_commit": packet["admitted_commit"],
        "count": packet["count"],
        "tickers_sha256": packet["tickers_sha256"],
        "rows_sha256": packet["rows_sha256"],
        "private_manifest_sha256": private_digest,
        "source_membership_counts": source_counts,
        "source_warning_counts": dict(sorted(source_warning_counts.items())),
        "massive_identifier_override_count": override_count,
        "active_pass_request_budget": packet["active_pass_request_budget"],
        "active_pass_status": packet["active_pass_status"],
    }


def _snapshot_rows(
    snapshot: object, *, observation_timestamp: str
) -> tuple[tuple[tuple[str, tuple[str, ...]], ...], dict[str, int]]:
    tickers = getattr(snapshot, "tickers", None)
    sources_by_ticker = getattr(snapshot, "sources_by_ticker", None)
    unavailable = getattr(snapshot, "unavailable_sources", None)
    generated_at = getattr(snapshot, "generated_at", None)
    if (
        not isinstance(tickers, tuple)
        or not isinstance(sources_by_ticker, dict)
        or unavailable != ()
        or tuple(sorted(sources_by_ticker)) != tickers
    ):
        raise CensusRunnerFailure("universe_manifest_snapshot_invalid")
    try:
        generated = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        observed = datetime.fromisoformat(observation_timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise CensusRunnerFailure("universe_manifest_snapshot_invalid") from None
    if generated != observed:
        raise CensusRunnerFailure("universe_manifest_snapshot_invalid")
    return tuple(sources_by_ticker.items()), _source_warning_counts(snapshot)


def _write_private_manifest(packet: Mapping[str, object], *, output_dir: Path) -> None:
    _assert_packet_safe(packet)
    try:
        output_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(output_dir, 0o700)
        manifest_path = output_dir / UNIVERSE_MANIFEST_NAME
        manifest_bytes = canonical_json(dict(packet)).encode("utf-8")
        descriptor = os.open(
            manifest_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(manifest_bytes)
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        seal_bytes = f"{digest}  {UNIVERSE_MANIFEST_NAME}\n".encode("ascii")
        descriptor = os.open(
            output_dir / SEAL_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(seal_bytes)
    except FileExistsError:
        raise CensusRunnerFailure("packet_output_exists") from None
    except OSError:
        raise CensusRunnerFailure("universe_manifest_output_failed") from None
    verify_seal(output_dir=output_dir)


def _write_universe_attestation(
    attestation: Mapping[str, object], *, output_dir: Path
) -> None:
    _assert_packet_safe(attestation)
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
        path = output_dir / UNIVERSE_ATTESTATION_NAME
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(dict(attestation)))
    except FileExistsError:
        raise CensusRunnerFailure("packet_output_exists") from None
    except OSError:
        raise CensusRunnerFailure("universe_manifest_output_failed") from None
    seal_packet(output_dir=output_dir, files=(path,))
    verify_seal(output_dir=output_dir)


def _assert_packet_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in _FORBIDDEN_PACKET_KEYS:
                raise CensusRunnerFailure("packet_forbidden_field")
            _assert_packet_safe(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_packet_safe(item)


def render_packet(
    packet: Mapping[str, object], *, output_dir: Path, filename: str = SUMMARY_NAME
) -> Path:
    if not isinstance(packet, Mapping) or filename != SUMMARY_NAME:
        raise CensusRunnerFailure("packet_shape")
    _assert_packet_safe(packet)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(dict(packet)))
    except FileExistsError:
        raise CensusRunnerFailure("packet_output_exists") from None
    return path


def seal_packet(*, output_dir: Path, files: tuple[Path, ...]) -> Path:
    if not files:
        raise CensusRunnerFailure("packet_shape")
    root = output_dir.resolve()
    lines: list[str] = []
    seen: set[str] = set()
    for path in sorted(files, key=lambda item: item.name):
        resolved = path.resolve()
        if resolved.parent != root or not resolved.is_file() or path.name in seen:
            raise CensusRunnerFailure("packet_shape")
        seen.add(path.name)
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    seal = output_dir / SEAL_NAME
    try:
        with seal.open("x", encoding="ascii", newline="\n") as handle:
            handle.writelines(lines)
    except FileExistsError:
        raise CensusRunnerFailure("packet_output_exists") from None
    return seal


def verify_seal(*, output_dir: Path) -> None:
    seal = output_dir / SEAL_NAME
    try:
        lines = seal.read_text(encoding="ascii").splitlines()
    except OSError:
        raise CensusRunnerFailure("packet_seal") from None
    if not lines:
        raise CensusRunnerFailure("packet_seal")
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2 or _SHA256.fullmatch(parts[0]) is None:
            raise CensusRunnerFailure("packet_seal")
        name = parts[1]
        if Path(name).name != name or name == SEAL_NAME:
            raise CensusRunnerFailure("packet_seal")
        path = output_dir / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != parts[0]:
            raise CensusRunnerFailure("packet_seal")


def run_census(
    *,
    mode: str,
    credential_resolver: Callable[[str], str],
    transport: LifecycleProviderCensusTransport | None = None,
    observation_timestamp: str | None = None,
    replay_fixture: Path = REPLAY_FIXTURE,
    acknowledgement: str | None = None,
    admitted_commit: str | None = None,
    repository_state: RepositoryState | None = None,
    output_dir: Path = PACKET_DIR,
    production_db_path: Path | None = None,
    profile_db_path: Path | None = None,
    sa_db_path: Path | None = None,
    private_output_dir: Path | None = None,
    timer: Callable[[], float] = time.perf_counter,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    if mode not in MODES:
        raise CensusRunnerFailure("census_mode")
    timestamp = _timestamp(observation_timestamp)
    if mode == "dry-run":
        return _dry_run(timestamp)
    if mode == "fixture-replay":
        return _fixture_replay(replay_fixture, timestamp)
    if mode == "universe-manifest":
        if production_db_path is not None:
            raise CensusRunnerFailure("production_database_argument_invalid")
        profile, sa, private = _assert_universe_manifest_admission(
            acknowledgement=acknowledgement,
            admitted_commit=admitted_commit,
            repository_state=repository_state,
            profile_db_path=profile_db_path,
            sa_db_path=sa_db_path,
            private_output_dir=private_output_dir,
            public_output_dir=output_dir,
        )
        try:
            snapshot = build_active_universe_snapshot(
                profile_db=profile,
                sa_db=sa,
                now=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
            )
        except ActiveUniverseUnavailable:
            raise CensusRunnerFailure("universe_manifest_source_unavailable") from None
        except (OSError, sqlite3.Error, ValueError):
            raise CensusRunnerFailure("universe_manifest_read_failed") from None
        rows, warning_counts = _snapshot_rows(snapshot, observation_timestamp=timestamp)
        private_packet = build_universe_manifest(
            rows,
            observation_timestamp=timestamp,
            admitted_commit=admitted_commit,
        )
        attestation = _universe_manifest_attestation(
            private_packet, source_warning_counts=warning_counts
        )
        _write_private_manifest(private_packet, output_dir=private)
        _write_universe_attestation(attestation, output_dir=output_dir)
        return attestation

    _assert_live_admission(
        mode=mode,
        acknowledgement=acknowledgement,
        admitted_commit=admitted_commit,
        repository_state=repository_state,
        output_dir=output_dir,
        production_db_path=production_db_path,
    )
    if transport is None:
        raise CensusRunnerFailure("live_transport_required")
    if mode == "ticker-event-revalidation":
        packet = _run_event_revalidation(
            credential_resolver=credential_resolver,
            transport=transport,
            timestamp=timestamp,
            admitted_commit=admitted_commit,
            timer=timer,
        )
    else:
        packet = _run_known_case_live(
            credential_resolver=credential_resolver,
            transport=transport,
            timestamp=timestamp,
            admitted_commit=admitted_commit,
            timer=timer,
            sleeper=sleeper,
        )
    summary = render_packet(packet, output_dir=output_dir)
    seal_packet(output_dir=output_dir, files=(summary,))
    verify_seal(output_dir=output_dir)
    return packet


class _ReadOnlyProfileStore:
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()

    def get_all(self) -> dict[str, dict[str, str]]:
        uri = f"file:{self._path.as_posix()}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                """
                SELECT provider, field, value
                FROM data_provider_config
                WHERE provider IN (?, ?) AND field = ?
                """,
                ("massive", "eodhd", "api_key"),
            ).fetchall()
        except sqlite3.Error:
            raise CensusRunnerFailure("profile_credential_store_unavailable") from None
        finally:
            if "connection" in locals():
                connection.close()
        result: dict[str, dict[str, str]] = {}
        for provider, field, value in rows:
            result.setdefault(str(provider), {})[str(field)] = str(value)
        return result


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--acknowledgement")
    parser.add_argument("--admitted-commit")
    parser.add_argument("--profile-db", type=Path)
    parser.add_argument("--sa-db", type=Path)
    parser.add_argument("--private-output-dir", type=Path)
    parser.add_argument("--production-db", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    output_dir = args.output_dir or (
        PACKET_DIR / "universe-manifest"
        if args.mode == "universe-manifest"
        else PACKET_DIR
    )

    if args.mode in {"dry-run", "fixture-replay"}:
        resolver = lambda provider: (_ for _ in ()).throw(  # noqa: E731
            AssertionError(f"offline_credential_access:{provider}")
        )
        packet = run_census(mode=args.mode, credential_resolver=resolver)
        sys.stdout.write(canonical_json(packet))
        return 0

    if args.mode == "universe-manifest":
        resolver = lambda provider: (_ for _ in ()).throw(  # noqa: E731
            AssertionError(f"manifest_credential_access:{provider}")
        )
        packet = run_census(
            mode=args.mode,
            credential_resolver=resolver,
            acknowledgement=args.acknowledgement,
            admitted_commit=args.admitted_commit,
            profile_db_path=args.profile_db,
            sa_db_path=args.sa_db,
            private_output_dir=args.private_output_dir,
            output_dir=output_dir,
            production_db_path=args.production_db,
        )
        sys.stdout.write(canonical_json(packet))
        return 0

    if args.profile_db is None:
        raise CensusRunnerFailure("profile_credential_store_required")
    from functools import partial
    import requests
    from src.security_lifecycle_provider_census_credentials import (
        resolve_census_credential,
    )

    store = _ReadOnlyProfileStore(args.profile_db)
    transport = LifecycleProviderCensusTransport(session=requests.Session())
    try:
        packet = run_census(
            mode=args.mode,
            credential_resolver=partial(resolve_census_credential, store),
            transport=transport,
            acknowledgement=args.acknowledgement,
            admitted_commit=args.admitted_commit,
            output_dir=output_dir,
            production_db_path=args.production_db,
        )
    finally:
        transport.close()
    sys.stdout.write(canonical_json(packet))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except CensusRunnerFailure as error:
        print(error.code, file=sys.stderr)
        raise SystemExit(2) from None
