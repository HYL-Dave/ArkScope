from __future__ import annotations

import ast
import builtins
import fcntl
import json
import threading
from pathlib import Path

import pytest


class _Clock:
    def __init__(self, value: float = 1_787_500_000.0):
        self.value = value
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class _Response:
    def __init__(
        self,
        status_code: int = 200,
        body: bytes = b"{}",
        *,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        self._chunks = chunks if chunks is not None else [body]
        self.closed = False

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, responses=None, *, on_get=None):
        self.responses = list(responses or [_Response()])
        self.on_get = on_get
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.on_get is not None:
            self.on_get()
        return self.responses.pop(0)


def _transport(tmp_path, *, session=None, clock=None, governor=None):
    from data_sources.sec_transport import SecRequestGovernor, SecTransport

    clock = clock or _Clock()
    governor = governor or SecRequestGovernor(
        lock_dir=tmp_path / "locks",
        clock=clock.time,
        sleep=clock.sleep,
    )
    return SecTransport(
        user_agent="ArkScope ops@arkscope.test",
        session=session or _Session(),
        governor=governor,
        sleep=clock.sleep,
    )


def test_strict_sec_identity_rejects_missing_or_placeholder_before_session(
    tmp_path, monkeypatch
):
    from data_sources.sec_transport import SecTransport, SecTransportFailure

    for name in ("ARKSCOPE_SEC_USER_AGENT", "SEC_CONTACT_EMAIL", "SEC_USER_AGENT"):
        monkeypatch.delenv(name, raising=False)
    session = _Session()
    transport = SecTransport(session=session, lock_dir=tmp_path / "locks")

    with pytest.raises(SecTransportFailure) as exc:
        transport.get_json("https://www.sec.gov/files/company_tickers.json")

    assert exc.value.code == "sec_identity_unconfigured"
    assert session.calls == []


def test_two_client_instances_share_one_200ms_request_start_schedule(tmp_path):
    clock = _Clock()
    starts: list[float] = []
    first = _transport(
        tmp_path,
        session=_Session(on_get=lambda: starts.append(clock.time())),
        clock=clock,
    )
    second = _transport(
        tmp_path,
        session=_Session(on_get=lambda: starts.append(clock.time())),
        clock=clock,
    )

    first.get_json("https://data.sec.gov/submissions/CIK0000320193.json")
    second.get_json("https://www.sec.gov/files/company_tickers.json")

    assert starts[1] - starts[0] >= 0.2
    assert clock.sleeps == [pytest.approx(0.2)]


def test_governor_instances_coordinate_through_one_cross_process_state_file(tmp_path):
    from data_sources.sec_transport import SecRequestGovernor

    clock = _Clock()
    first = SecRequestGovernor(
        lock_dir=tmp_path / "locks",
        process_lock=threading.Lock(),
        clock=clock.time,
        sleep=clock.sleep,
    )
    second = SecRequestGovernor(
        lock_dir=tmp_path / "locks",
        process_lock=threading.Lock(),
        clock=clock.time,
        sleep=clock.sleep,
    )

    assert first.reserve_request_start() == 0
    clock.value += 0.05
    assert second.reserve_request_start() == pytest.approx(150)
    assert second.state_path == first.state_path
    assert second.state_path.read_text(encoding="ascii").endswith("Z\n")


def test_governor_fails_closed_when_fcntl_lock_dir_or_state_is_unavailable(
    tmp_path, monkeypatch
):
    from data_sources.sec_transport import SecRequestGovernor, SecTransportFailure

    clock = _Clock()
    real_import = builtins.__import__

    def without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ImportError("unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_fcntl)
    with pytest.raises(SecTransportFailure) as exc:
        SecRequestGovernor(
            lock_dir=tmp_path / "missing-fcntl",
            clock=clock.time,
            sleep=clock.sleep,
        ).reserve_request_start()
    assert exc.value.code == "sec_governor_unavailable"
    monkeypatch.setattr(builtins, "__import__", real_import)

    not_a_dir = tmp_path / "not-a-directory"
    not_a_dir.write_text("occupied", encoding="ascii")
    with pytest.raises(SecTransportFailure) as exc:
        SecRequestGovernor(
            lock_dir=not_a_dir,
            clock=clock.time,
            sleep=clock.sleep,
        ).reserve_request_start()
    assert exc.value.code == "sec_governor_unavailable"

    corrupt = tmp_path / "corrupt"
    corrupt.mkdir()
    (corrupt / "sec_request_governor.state").write_text("not-a-time\n", encoding="ascii")
    with pytest.raises(SecTransportFailure) as exc:
        SecRequestGovernor(
            lock_dir=corrupt,
            clock=clock.time,
            sleep=clock.sleep,
        ).reserve_request_start()
    assert exc.value.code == "sec_governor_unavailable"


def test_lifecycle_budget_enforces_attempt_document_and_byte_limits(tmp_path):
    from data_sources.sec_transport import SecRequestBudget, SecTransportFailure

    url = "https://www.sec.gov/Archives/edgar/data/1/a.htm"
    session = _Session([_Response(body=b"four"), _Response(body=b"more")])
    transport = _transport(tmp_path, session=session)
    budget = SecRequestBudget(
        max_attempts=2,
        max_documents=1,
        max_document_bytes=4,
        max_total_bytes=4,
    )

    assert transport.get_text(url, budget=budget, document=True) == "four"
    with pytest.raises(SecTransportFailure) as exc:
        transport.get_text(url, budget=budget, document=True)
    assert exc.value.code == "sec_request_budget_exhausted"
    assert len(session.calls) == 1
    assert budget.diagnostics() == {
        "attempt_count": 1,
        "document_count": 1,
        "body_bytes": 4,
    }


def test_one_429_retry_honors_only_bounded_retry_after(tmp_path):
    from data_sources.sec_transport import SecTransportFailure

    clock = _Clock()
    session = _Session(
        [
            _Response(429, headers={"Retry-After": "2"}),
            _Response(body=b'{"ok":true}'),
        ]
    )
    transport = _transport(tmp_path, session=session, clock=clock)
    assert transport.get_json("https://data.sec.gov/submissions/a.json") == {"ok": True}
    assert len(session.calls) == 2
    assert 2.0 in clock.sleeps

    session = _Session([_Response(429, headers={"Retry-After": "31"})])
    transport = _transport(tmp_path / "over", session=session, clock=_Clock())
    with pytest.raises(SecTransportFailure) as exc:
        transport.get_json("https://data.sec.gov/submissions/a.json")
    assert exc.value.code == "sec_rate_limited"
    assert len(session.calls) == 1

    session = _Session(
        [
            _Response(429, headers={"Retry-After": "0"}),
            _Response(429, headers={"Retry-After": "0"}),
        ]
    )
    transport = _transport(tmp_path / "twice", session=session, clock=_Clock())
    with pytest.raises(SecTransportFailure) as exc:
        transport.get_json("https://data.sec.gov/submissions/a.json")
    assert exc.value.code == "sec_rate_limited"
    assert len(session.calls) == 2


def test_json_and_document_reads_are_bounded_before_decode(tmp_path):
    from data_sources.sec_transport import SecTransportFailure

    responses = [
        _Response(chunks=[b'{"a":', b'"too long"}']),
        _Response(chunks=[b"abc", b"def"]),
    ]
    transport = _transport(tmp_path, session=_Session(responses))

    with pytest.raises(SecTransportFailure) as exc:
        transport.get_json(
            "https://data.sec.gov/submissions/a.json",
            max_bytes=5,
        )
    assert exc.value.code == "sec_response_too_large"

    with pytest.raises(SecTransportFailure) as exc:
        transport.get_text(
            "https://www.sec.gov/Archives/a.htm",
            max_bytes=5,
            document=True,
        )
    assert exc.value.code == "sec_response_too_large"


def test_governor_lock_is_released_before_network_io(tmp_path):
    from data_sources.sec_transport import SecRequestGovernor

    clock = _Clock()
    governor = SecRequestGovernor(
        lock_dir=tmp_path / "locks",
        clock=clock.time,
        sleep=clock.sleep,
    )

    def prove_unlocked():
        with governor.state_path.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    transport = _transport(
        tmp_path,
        governor=governor,
        session=_Session(on_get=prove_unlocked),
        clock=clock,
    )
    transport.get_json("https://www.sec.gov/files/company_tickers.json")


def test_diagnostics_are_bounded_integer_only_and_secret_safe(tmp_path):
    from data_sources.sec_transport import SecRequestBudget

    budget = SecRequestBudget.lifecycle()
    transport = _transport(tmp_path)
    transport.get_json(
        "https://data.sec.gov/submissions/CIK0000320193.json",
        budget=budget,
    )
    diagnostics = transport.diagnostics(budget)

    assert diagnostics.keys() == {
        "attempt_count",
        "document_count",
        "body_bytes",
        "governor_wait_ms",
        "rate_limit_retries",
    }
    assert all(type(value) is int and 0 <= value <= 12_582_912 for value in diagnostics.values())
    rendered = json.dumps(diagnostics, sort_keys=True)
    assert "sec.gov" not in rendered
    assert "arkscope.test" not in rendered
    assert len(rendered) < 180


def test_all_active_sec_http_callers_use_shared_transport_and_dormant_edgartools_is_unreachable():
    direct_owners = (
        Path("data_sources/sec_edgar_source.py"),
        Path("data_sources/sec_edgar_financials.py"),
        Path("data_sources/sec_earnings_releases.py"),
        Path("data_sources/sec_insider_trades.py"),
        Path("src/symbol_catalog.py"),
    )
    for path in direct_owners:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert "requests" not in imports, path
        assert "SecTransport" in path.read_text(encoding="utf-8"), path

    provider_source = Path("src/data_provider_config.py").read_text(encoding="utf-8")
    sec_branch = provider_source.split('if provider == "sec_edgar":', 1)[1].split(
        'if provider == "financial_datasets":', 1
    )[0]
    assert "SecTransport" in sec_branch
    assert "_http_probe" not in sec_branch

    for path in Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "data_sources.sec_filings", path
            elif isinstance(node, ast.Import):
                assert all(alias.name != "data_sources.sec_filings" for alias in node.names), path
