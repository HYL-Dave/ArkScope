from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import warnings

import anyio

from data_sources import ibkr_source
from src import portfolio_capture_ibkr


class _FakeEvent:
    def __iadd__(self, handler):
        return self


class _FakeIB:
    def __init__(self):
        self.errorEvent = _FakeEvent()
        self.loop = None
        self.disconnected = False

    def connect(self, *args, **kwargs):
        self.loop = asyncio.get_event_loop()

    def isConnected(self):
        return not self.disconnected

    def disconnect(self):
        self.disconnected = True


def test_connect_owns_event_loop_in_worker_thread_and_releases_it(monkeypatch):
    monkeypatch.setattr(ibkr_source, "IB", _FakeIB)

    def run():
        source = ibkr_source.IBKRDataSource(timeout=0.01)
        connected = source.connect()
        loop = source._ib.loop
        source.disconnect()
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            current_loop = None
        else:
            current_loop = asyncio.get_event_loop()
        return connected, loop.is_closed() if loop is not None else False, current_loop

    with ThreadPoolExecutor(max_workers=1) as executor:
        connected, loop_closed, current_loop = executor.submit(run).result()

    assert connected is True
    assert loop_closed is True
    assert current_loop is None


def test_disconnect_tolerates_instance_created_without_init():
    source = ibkr_source.IBKRDataSource.__new__(ibkr_source.IBKRDataSource)
    source._ib = None

    source.disconnect()


def test_capture_reader_runs_in_an_anyio_worker_thread_without_event_loop_warning(
    monkeypatch,
):
    class FakeCaptureSession:
        def managedAccounts(self):
            return []

        def accountSummary(self):
            return []

        def accountValues(self):
            return []

        def fills(self):
            return []

        def positions(self):
            return []

        def portfolio(self):
            return []

    class FakeCaptureSource:
        disconnect_calls = 0

        def __init__(self, *, client_id, readonly):
            self._ib = FakeCaptureSession()

        def connect(self):
            return True

        def disconnect(self):
            type(self).disconnect_calls += 1

    monkeypatch.setattr(
        portfolio_capture_ibkr,
        "_source_factory",
        FakeCaptureSource,
    )

    async def run_capture():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = await anyio.to_thread.run_sync(
                portfolio_capture_ibkr.read_ibkr_capture
            )
        return result, caught

    result, caught = anyio.run(run_capture)

    assert result.position_leg.state == "complete"
    assert not [warning for warning in caught if warning.category is RuntimeWarning]
    assert FakeCaptureSource.disconnect_calls == 1
