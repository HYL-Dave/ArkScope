from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from data_sources.lifecycle_provider_census_transport import (
    CensusTransportFailure,
    EodhdSymbolSetsResult,
    MassiveListingResult,
    MassiveTickerEventsResult,
    NasdaqDirectoryResult,
)
from src.data_provider_config import ProviderConfigMissing


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    ROOT
    / "docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census"
    / "run_census.py"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("lifecycle_provider_census_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


class RejectingResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, provider: str) -> str:
        self.calls.append(provider)
        raise AssertionError("credential_resolver_called")


class RejectingTransport:
    def __getattr__(self, name: str):
        raise AssertionError(f"transport_accessed:{name}")


class FakeResolver:
    def __init__(self, *, missing: frozenset[str] = frozenset()) -> None:
        self.calls: list[str] = []
        self.missing = missing

    def __call__(self, provider: str) -> str:
        self.calls.append(provider)
        if provider in self.missing:
            raise ProviderConfigMissing(provider, "api_key")
        return f"SENSITIVE_{provider.upper()}_KEY"


class FakeClock:
    def __init__(self) -> None:
        self.value = 1.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class FakeLiveTransport:
    _LISTINGS = {
        "LC": (False, "BBG000000LC", "2025-06-26"),
        "HAPN": (True, "BBG000000LC", None),
        "ARCH": (False, "BBG0000ARCH", "2019-10-01"),
        "CNR": (True, "BBG00000CNR", None),
        "LTHM": (False, "BBG0000LTHM", "2024-01-04"),
        "ALTM": (True, "BBG0000ALTM", None),
        "TA": (False, "BBG000000TA", "2019-12-23"),
        "AAPL": (True, "BBG0000AAPL", None),
        "SMCI": (True, "BBG0000SMCI", None),
    }

    def __init__(
        self,
        *,
        missing_listing: str | None = None,
        eodhd_complete: bool = True,
        failed_listing: str | None = None,
    ) -> None:
        self.calls: list[tuple[str, str]] = []
        self.missing_listing = missing_listing
        self.eodhd_complete = eodhd_complete
        self.failed_listing = failed_listing

    @staticmethod
    def _payload(kind: str, identifier: str) -> bytes:
        return f"{kind}:{identifier}".encode("ascii")

    def fetch_massive_listing(self, ticker, *, expected_active, api_key, budget):
        self.calls.append(("massive_listing", ticker))
        assert api_key == "SENSITIVE_MASSIVE_KEY"
        active, stable_id, delisted_date = self._LISTINGS[ticker]
        assert active is expected_active
        budget.reserve_massive(
            ("listing", ticker, "true" if expected_active else "false")
        )
        if ticker == self.failed_listing:
            raise CensusTransportFailure("massive_rate_limited", status_code=429)
        body = self._payload("listing", ticker)
        budget.record_massive_body(len(body))
        if ticker == self.missing_listing:
            return MassiveListingResult(
                ticker=ticker,
                expected_active=expected_active,
                found=False,
                active=None,
                stable_id=None,
                delisted_date=None,
                source_locator=f"https://api.massive.example/listing/{ticker}",
                response_sha256=hashlib.sha256(body).hexdigest(),
                response_bytes=len(body),
            )
        return MassiveListingResult(
            ticker=ticker,
            expected_active=expected_active,
            found=True,
            active=active,
            stable_id=stable_id,
            delisted_date=delisted_date,
            source_locator=f"https://api.massive.example/listing/{ticker}",
            response_sha256=hashlib.sha256(body).hexdigest(),
            response_bytes=len(body),
        )

    def fetch_massive_ticker_events(self, *, stable_id, api_key, budget):
        self.calls.append(("massive_events", stable_id))
        assert api_key == "SENSITIVE_MASSIVE_KEY"
        budget.reserve_massive(("events", stable_id))
        body = self._payload("events", stable_id)
        budget.record_massive_body(len(body))
        events = (
            (("LC", "HAPN", "2025-06-27"),)
            if stable_id == "BBG000000LC"
            else ()
        )
        return MassiveTickerEventsResult(
            stable_id=stable_id,
            events=events,
            source_locator=f"https://api.massive.example/events/{stable_id}",
            response_sha256=hashlib.sha256(body).hexdigest(),
            response_bytes=len(body),
        )

    def fetch_eodhd_symbol_sets(self, *, symbols, api_key, budget):
        self.calls.append(("eodhd", ",".join(symbols)))
        assert api_key == "SENSITIVE_EODHD_KEY"
        identities = (
            ("exchange-symbol-list", "US", "0", *symbols),
            ("exchange-symbol-list", "US", "1", *symbols),
        )
        budget.require_eodhd_pair_capacity(identities)
        for identity in identities:
            budget.reserve_eodhd(identity)
        active_body = self._payload("eodhd_active", ",".join(symbols))
        delisted_body = self._payload("eodhd_delisted", ",".join(symbols))
        budget.record_eodhd_body(len(active_body))
        budget.record_eodhd_body(len(delisted_body))
        active = tuple(
            symbol
            for symbol in symbols
            if symbol in {"AAPL", "ALTM", "CNR", "HAPN", "SMCI"}
            and (self.eodhd_complete or symbol != "SMCI")
        )
        delisted = tuple(
            symbol for symbol in symbols if symbol in {"ARCH", "LC", "LTHM", "TA"}
        )
        unreported = () if self.eodhd_complete else ("SMCI",)
        return EodhdSymbolSetsResult(
            requested=symbols,
            active=active,
            delisted=delisted,
            unreported=unreported,
            complete=self.eodhd_complete,
            active_source_locator="https://eodhd.example/active",
            delisted_source_locator="https://eodhd.example/delisted",
            active_response_sha256=hashlib.sha256(active_body).hexdigest(),
            delisted_response_sha256=hashlib.sha256(delisted_body).hexdigest(),
            active_response_bytes=len(active_body),
            delisted_response_bytes=len(delisted_body),
        )

    def fetch_nasdaq_directory(self, source_url, *, budget):
        self.calls.append(("nasdaq", source_url))
        budget.reserve_nasdaq(source_url)
        rows = (
            "Symbol|Security Name\n"
            "AAPL|Apple\n"
            "ALTM|Arcadium\n"
            "CNR|Core\n"
            "HAPN|Hapbee\n"
            "SMCI|Super Micro\n"
        )
        body = rows.encode("ascii")
        budget.record_nasdaq_body(len(body))
        return NasdaqDirectoryResult(
            source_locator=source_url,
            body=body,
            response_sha256=hashlib.sha256(body).hexdigest(),
            response_bytes=len(body),
        )

    @staticmethod
    def diagnostics(budget):
        return budget.diagnostics()


def _ack(commit: str = "a" * 40) -> str:
    return runner.live_acknowledgement(
        spec_sha256=runner.spec_sha256(), admitted_commit=commit
    )


def test_dry_run_lists_exact_budget_without_reading_credentials() -> None:
    resolver = RejectingResolver()
    result = runner.run_census(
        mode="dry-run",
        credential_resolver=resolver,
        transport=RejectingTransport(),
    )

    assert result["maximum_http_requests"] == 18
    assert result["request_budget"] == {"massive": 14, "eodhd": 2, "nasdaq": 2}
    assert result["spec_sha256"] == runner.spec_sha256()
    assert resolver.calls == []


def test_fixture_replay_is_deterministic_and_offline() -> None:
    resolver = RejectingResolver()
    first = runner.run_census(
        mode="fixture-replay",
        credential_resolver=resolver,
        transport=RejectingTransport(),
        observation_timestamp="2026-09-04T01:02:03Z",
    )
    second = runner.run_census(
        mode="fixture-replay",
        credential_resolver=resolver,
        transport=RejectingTransport(),
        observation_timestamp="2026-09-04T01:02:03Z",
    )

    assert runner.canonical_json(first) == runner.canonical_json(second)
    assert [row["case_id"] for row in first["oracle"]["results"]] == [
        "AAPL",
        "ARCH",
        "LC",
        "LTHM",
        "SMCI",
        "TA",
    ]
    assert {row["outcome"] for row in first["outcome_samples"]} == set(
        runner.CLOSED_OUTCOMES
    )
    assert all(row["outcome"] == "confirmed" for row in first["oracle"]["results"])
    assert resolver.calls == []


def test_fixture_digest_is_bound_to_normalized_content(tmp_path: Path) -> None:
    payload = json.loads(runner.REPLAY_FIXTURE.read_text(encoding="utf-8"))
    payload["request_observations"][0]["elapsed_ms"] = 1.25
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(runner.CensusRunnerFailure, match="replay_fixture_digest"):
        runner.run_census(
            mode="fixture-replay",
            credential_resolver=RejectingResolver(),
            replay_fixture=altered,
        )


@pytest.mark.parametrize(
    "mode",
    ("", "live", "fixture", "universe"),
)
def test_unknown_modes_fail_before_dependency_access(mode: str) -> None:
    resolver = RejectingResolver()
    with pytest.raises(runner.CensusRunnerFailure, match="census_mode"):
        runner.run_census(
            mode=mode,
            credential_resolver=resolver,
            transport=RejectingTransport(),
        )
    assert resolver.calls == []


def test_universe_manifest_remains_separately_gated() -> None:
    resolver = RejectingResolver()
    with pytest.raises(runner.CensusRunnerFailure, match="universe_manifest_not_authorized"):
        runner.run_census(
            mode="universe-manifest",
            credential_resolver=resolver,
            transport=RejectingTransport(),
        )
    assert resolver.calls == []


@pytest.mark.parametrize(
    "acknowledgement",
    (None, "", "wrong", "SPEC_SHA256=" + "0" * 64),
)
def test_live_mode_requires_exact_digest_budget_and_commit_acknowledgement(
    tmp_path: Path, acknowledgement: str | None
) -> None:
    resolver = RejectingResolver()
    with pytest.raises(runner.CensusRunnerFailure, match="live_acknowledgement"):
        runner.run_census(
            mode="known-case-live",
            credential_resolver=resolver,
            transport=RejectingTransport(),
            acknowledgement=acknowledgement,
            admitted_commit="a" * 40,
            repository_state=runner.RepositoryState("a" * 40, True),
            output_dir=tmp_path,
        )
    assert resolver.calls == []


def test_live_mode_rejects_dirty_or_wrong_repository_before_credentials(tmp_path: Path) -> None:
    for state in (
        runner.RepositoryState("b" * 40, True),
        runner.RepositoryState("a" * 40, False),
    ):
        resolver = RejectingResolver()
        with pytest.raises(runner.CensusRunnerFailure, match="live_repository_state"):
            runner.run_census(
                mode="known-case-live",
                credential_resolver=resolver,
                transport=RejectingTransport(),
                acknowledgement=_ack(),
                admitted_commit="a" * 40,
                repository_state=state,
                output_dir=tmp_path,
            )
        assert resolver.calls == []


def test_live_mode_rejects_production_database_path_before_credentials(
    tmp_path: Path,
) -> None:
    resolver = RejectingResolver()
    with pytest.raises(runner.CensusRunnerFailure, match="production_database_prohibited"):
        runner.run_census(
            mode="known-case-live",
            credential_resolver=resolver,
            transport=RejectingTransport(),
            acknowledgement=_ack(),
            admitted_commit="a" * 40,
            repository_state=runner.RepositoryState("a" * 40, True),
            output_dir=tmp_path,
            production_db_path=tmp_path / "app.db",
        )
    assert resolver.calls == []


def test_known_case_live_executes_exact_budget_and_seals_normalized_packet(
    tmp_path: Path,
) -> None:
    resolver = FakeResolver()
    transport = FakeLiveTransport()
    clock = FakeClock()
    packet = runner.run_census(
        mode="known-case-live",
        credential_resolver=resolver,
        transport=transport,
        acknowledgement=_ack(),
        admitted_commit="a" * 40,
        repository_state=runner.RepositoryState("a" * 40, True),
        output_dir=tmp_path,
        observation_timestamp="2026-09-04T01:02:03Z",
        timer=clock,
        sleeper=clock.sleep,
    )

    assert resolver.calls == ["massive", "eodhd"]
    assert packet["admitted_commit"] == "a" * 40
    assert packet["known_cases_sha256"] == hashlib.sha256(
        runner.KNOWN_CASES_FIXTURE.read_bytes()
    ).hexdigest()
    assert packet["request_accounting"] == {
        "maximum_http_requests": 18,
        "providers": {
            "massive": {"attempts": 14, "body_bytes": 193},
            "eodhd": {"attempts": 2, "body_bytes": 106},
            "nasdaq": {"attempts": 2, "body_bytes": 168},
        },
        "total_attempts": 18,
        "total_body_bytes": 467,
    }
    assert len([call for call in transport.calls if call[0] == "massive_listing"]) == 9
    assert len([call for call in transport.calls if call[0] == "massive_events"]) == 5
    assert len([call for call in transport.calls if call[0] == "eodhd"]) == 1
    assert len([call for call in transport.calls if call[0] == "nasdaq"]) == 2
    assert clock.sleeps == [runner.MASSIVE_MIN_REQUEST_INTERVAL_SECONDS] * 13
    results = {row["case_id"]: row for row in packet["oracle"]["results"]}
    assert set(results) == {"AAPL", "ARCH", "LC", "LTHM", "SMCI", "TA"}
    assert all(row["outcome"] == "confirmed" for row in results.values())
    assert results["LC"]["successor"] == "HAPN"
    assert all(lane["executed"] for lane in packet["lanes"].values())
    summary = (tmp_path / runner.SUMMARY_NAME).read_text(encoding="utf-8")
    assert "SENSITIVE_MASSIVE_KEY" not in summary
    assert "SENSITIVE_EODHD_KEY" not in summary
    assert (tmp_path / runner.SEAL_NAME).is_file()
    runner.verify_seal(output_dir=tmp_path)


def test_missing_eodhd_credential_skips_only_that_lane(tmp_path: Path) -> None:
    resolver = FakeResolver(missing=frozenset({"eodhd"}))
    transport = FakeLiveTransport()
    clock = FakeClock()
    packet = runner.run_census(
        mode="known-case-live",
        credential_resolver=resolver,
        transport=transport,
        acknowledgement=_ack(),
        admitted_commit="a" * 40,
        repository_state=runner.RepositoryState("a" * 40, True),
        output_dir=tmp_path,
        timer=clock,
        sleeper=clock.sleep,
    )

    assert packet["lanes"]["eodhd"] == {
        "executed": False,
        "reason": "credential_unavailable",
    }
    assert packet["request_accounting"]["providers"]["eodhd"]["attempts"] == 0
    skipped = [
        row
        for row in packet["request_observations"]
        if row["provider"] == "eodhd"
    ]
    assert len(skipped) == 1
    assert skipped[0]["result_code"] == "credential_unavailable"
    assert skipped[0]["attempts"] == 0
    assert not any(call[0] == "eodhd" for call in transport.calls)


def test_live_exact_listing_absence_is_not_positive_authority(tmp_path: Path) -> None:
    clock = FakeClock()
    packet = runner.run_census(
        mode="known-case-live",
        credential_resolver=FakeResolver(),
        transport=FakeLiveTransport(missing_listing="CNR"),
        acknowledgement=_ack(),
        admitted_commit="a" * 40,
        repository_state=runner.RepositoryState("a" * 40, True),
        output_dir=tmp_path,
        timer=clock,
        sleeper=clock.sleep,
    )

    observation = next(
        row
        for row in packet["request_observations"]
        if row["provider"] == "massive"
        and row["endpoint_family"] == "all_tickers"
        and row["requested_identifiers"] == ["CNR"]
    )
    assert observation["result_code"] == "coverage_limited"


def test_live_incomplete_eodhd_partition_is_ambiguous(tmp_path: Path) -> None:
    clock = FakeClock()
    packet = runner.run_census(
        mode="known-case-live",
        credential_resolver=FakeResolver(),
        transport=FakeLiveTransport(eodhd_complete=False),
        acknowledgement=_ack(),
        admitted_commit="a" * 40,
        repository_state=runner.RepositoryState("a" * 40, True),
        output_dir=tmp_path,
        timer=clock,
        sleeper=clock.sleep,
    )

    observation = next(
        row
        for row in packet["request_observations"]
        if row["provider"] == "eodhd"
    )
    assert observation["result_code"] == "ambiguous"


def test_live_failure_retains_only_normalized_failure_code(tmp_path: Path) -> None:
    clock = FakeClock()
    packet = runner.run_census(
        mode="known-case-live",
        credential_resolver=FakeResolver(),
        transport=FakeLiveTransport(failed_listing="CNR"),
        acknowledgement=_ack(),
        admitted_commit="a" * 40,
        repository_state=runner.RepositoryState("a" * 40, True),
        output_dir=tmp_path,
        timer=clock,
        sleeper=clock.sleep,
    )

    observation = next(
        row
        for row in packet["request_observations"]
        if row["provider"] == "massive"
        and row["endpoint_family"] == "all_tickers"
        and row["requested_identifiers"] == ["CNR"]
    )
    assert observation["http_status_family"] == "4xx"
    assert observation["result_code"] == "provider_unavailable"
    assert observation["parsed_fields"] == {
        "failure_code": "massive_rate_limited"
    }


def test_unexpected_credential_resolver_failure_is_not_reported_as_missing(
    tmp_path: Path,
) -> None:
    resolver = RejectingResolver()
    with pytest.raises(runner.CensusRunnerFailure, match="credential_resolution_failed"):
        runner.run_census(
            mode="known-case-live",
            credential_resolver=resolver,
            transport=RejectingTransport(),
            acknowledgement=_ack(),
            admitted_commit="a" * 40,
            repository_state=runner.RepositoryState("a" * 40, True),
            output_dir=tmp_path,
        )
    assert resolver.calls == ["massive"]


def test_read_only_profile_store_reads_only_admitted_census_credentials(
    tmp_path: Path,
) -> None:
    path = tmp_path / "profile.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE data_provider_config (
            provider TEXT NOT NULL,
            field TEXT NOT NULL,
            value TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT INTO data_provider_config(provider, field, value) VALUES (?, ?, ?)",
        (
            ("massive", "api_key", "massive-key"),
            ("massive", "unrelated", "massive-unrelated-secret"),
            ("eodhd", "api_key", "eodhd-key"),
            ("openai", "api_key", "openai-secret"),
        ),
    )
    connection.commit()
    connection.close()

    assert runner._ReadOnlyProfileStore(path).get_all() == {
        "massive": {"api_key": "massive-key"},
        "eodhd": {"api_key": "eodhd-key"},
    }


def test_packet_omits_raw_bodies_secrets_and_account_data(tmp_path: Path) -> None:
    packet = runner.run_census(
        mode="fixture-replay",
        credential_resolver=RejectingResolver(),
    )
    path = runner.render_packet(packet, output_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "apiKey" not in text
    assert "api_token" not in text
    assert "authorization" not in text.lower()
    assert "raw_body" not in text
    assert "account_id" not in text.lower()
    assert "user_email" not in text.lower()
    assert "secret" not in text.lower()

    with pytest.raises(runner.CensusRunnerFailure, match="packet_output_exists"):
        runner.render_packet(packet, output_dir=tmp_path)


def test_packet_seal_is_create_only_and_verifies_every_output(tmp_path: Path) -> None:
    packet = runner.run_census(
        mode="fixture-replay",
        credential_resolver=RejectingResolver(),
    )
    packet_path = runner.render_packet(packet, output_dir=tmp_path)
    seal_path = runner.seal_packet(output_dir=tmp_path, files=(packet_path,))
    expected = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    assert seal_path.read_text(encoding="ascii") == f"{expected}  census-summary.json\n"
    runner.verify_seal(output_dir=tmp_path)

    with pytest.raises(runner.CensusRunnerFailure, match="packet_output_exists"):
        runner.seal_packet(output_dir=tmp_path, files=(packet_path,))


def test_fixture_cli_prints_json_without_modifying_live_packet(tmp_path: Path) -> None:
    packet_paths = tuple(
        RUNNER_PATH.parent / name
        for name in (runner.SUMMARY_NAME, runner.SEAL_NAME)
    )
    before = {
        path: path.read_bytes() if path.exists() else None for path in packet_paths
    }
    result = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--mode", "fixture-replay"],
        cwd=tmp_path,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["mode"] == "fixture-replay"
    assert {
        path: path.read_bytes() if path.exists() else None for path in packet_paths
    } == before


def test_readme_states_lane_and_negative_result_contracts() -> None:
    text = (RUNNER_PATH.parent / "README.md").read_text(encoding="utf-8")
    assert "credential_unavailable" in text
    assert "negative oracle result" in text.lower()
    assert "successful experiment outcome" in text.lower()
    for provider in ("Massive", "EODHD", "Nasdaq"):
        assert provider in text
