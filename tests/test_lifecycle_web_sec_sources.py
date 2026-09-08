import fcntl
import threading
import time

import pytest

from tests.test_lifecycle_public_sources import Response, _reader


def policy(tmp_path):
    from src.lifecycle_web_sec_sources import SecSourcePolicy
    from data_sources.sec_transport import SecRequestGovernor
    return SecSourcePolicy(user_agent="ArkScope review@arkscope.test", governor=SecRequestGovernor(lock_dir=tmp_path / "locks"))


def test_sec_sources_reuse_reviewed_identity_and_governor_on_every_redirect(tmp_path, monkeypatch):
    from src.lifecycle_web_sec_sources import SecSourcePolicy

    calls = []
    class Governor:
        def reserve_request_start(self, *, check):
            check()
            calls.append(True)
    reader, connections, _, _ = _reader(monkeypatch, [Response(status=302, headers={"Location": "/Archives/notice"}), Response()])
    reader.sec_policy = SecSourcePolicy(user_agent="ArkScope review@arkscope.test", governor=Governor())
    result = reader.read("https://www.sec.gov/Archives/start")
    assert len(calls) == 2 and result.url == "https://www.sec.gov/Archives/notice"
    assert all(connection.requests[0][2]["User-Agent"] == "ArkScope review@arkscope.test" for connection in connections)


def test_redirect_into_sec_cannot_bypass_identity_or_traffic_policy(monkeypatch):
    from src.lifecycle_public_sources import SourceReadError

    for name in ("ARKSCOPE_SEC_USER_AGENT", "SEC_CONTACT_EMAIL", "SEC_USER_AGENT"):
        monkeypatch.delenv(name, raising=False)
    reader, connections, resolutions, _ = _reader(monkeypatch, [Response(status=302, headers={"Location": "https://www.sec.gov/Archives/notice"})])
    with pytest.raises(SourceReadError, match="sec_identity_unconfigured"):
        reader.read("https://ir.example.com/start")
    assert len(connections) == 1 and len(resolutions) == 1


@pytest.mark.parametrize("value", ["ArkScope research@example.com", "missing-contact", "ArkScope test@example.test\r\nAuthorization: private"])
def test_invalid_sec_identity_never_dispatches_or_reserves_governor(tmp_path, value):
    from src.lifecycle_public_sources import SourceReadError
    from src.lifecycle_web_sec_sources import SecSourcePolicy

    calls = []
    class Governor:
        def reserve_request_start(self, **kwargs):
            calls.append(True)
    with pytest.raises(SourceReadError, match="sec_identity_unconfigured"):
        SecSourcePolicy(user_agent=value, governor=Governor()).prepare("https://www.sec.gov/Archives/notice", check=lambda: 5)
    assert calls == []


@pytest.mark.parametrize("lock_kind", ["process", "file"])
def test_waiting_for_sec_governor_remains_cancellable_and_never_dispatches(tmp_path, monkeypatch, lock_kind):
    from src.lifecycle_public_sources import SourceReadError
    from data_sources.sec_transport import SecRequestGovernor
    from src.lifecycle_web_sec_sources import SecSourcePolicy

    lock = threading.Lock()
    governor = SecRequestGovernor(lock_dir=tmp_path, process_lock=lock)
    held = None
    if lock_kind == "process":
        lock.acquire()
    else:
        held = governor.state_path.open("a+")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    reader, connections, _, _ = _reader(monkeypatch, timeout_seconds=0.12)
    reader.sec_policy = SecSourcePolicy(user_agent="ArkScope review@arkscope.test", governor=governor)
    errors = []
    def run():
        try:
            reader.read("https://www.sec.gov/Archives/notice")
        except Exception as exc:
            errors.append(exc)
    worker = threading.Thread(target=run)
    worker.start()
    try:
        worker.join(1)
        assert not worker.is_alive(), "SEC lock wait ignored the source deadline"
    finally:
        if held:
            held.close()
        else:
            lock.release()
        worker.join(2)
    assert len(errors) == 1 and isinstance(errors[0], SourceReadError) and str(errors[0]) == "source_read_timeout"
    assert connections == [] and reader.request_count == 0


def test_nonsec_sources_do_not_reserve_sec_budget_or_receive_contact_header(tmp_path, monkeypatch):
    reader, connections, _, _ = _reader(monkeypatch)
    reader.sec_policy = policy(tmp_path)
    reader.read("https://ir.example.com/notice")
    assert "review@" not in str(connections[0].requests)
    assert not (tmp_path / "locks").exists()
