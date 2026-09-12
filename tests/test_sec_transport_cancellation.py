"""Cancellation must reach the real SEC governor and body/retry boundaries."""

import pytest

from data_sources.sec_transport import SecTransportFailure
from tests.test_sec_transport import _Clock, _Response, _Session, _transport


@pytest.mark.parametrize("stage", ["before-governor", "pacing", "after-governor", "body", "retry"])
def test_sec_cancel_never_dispatches_next_request_and_closes_response(tmp_path, stage):
    clock, stopped = _Clock(), []

    def check():
        if stopped:
            raise ValueError("private stop detail")

    class Response(_Response):
        def iter_content(self, chunk_size):
            yield b"{"
            if stage == "body":
                stopped.append(True)
            yield b"}"

    response = Response(429 if stage == "retry" else 200, headers={"Retry-After": "3"})
    session = _Session([response, _Response()])
    transport = _transport(tmp_path, session=session, clock=clock)
    if stage == "before-governor":
        stopped.append(True)
    elif stage == "after-governor":
        reserve = transport._governor.reserve_request_start

        def reserve_then_stop(**kwargs):
            result = reserve(**kwargs)
            stopped.append(True)
            return result

        transport._governor.reserve_request_start = reserve_then_stop
    else:
        if stage == "pacing":
            transport._governor.reserve_request_start()

        def sleep_then_stop(seconds):
            clock.sleep(seconds)
            stopped.append(True)

        transport._governor._sleep = sleep_then_stop
        transport._sleep = sleep_then_stop

    with pytest.raises(SecTransportFailure, match="^sec_request_cancelled$"):
        transport.get("https://data.sec.gov/submissions/CIK0000320193.json", check=check)
    expected_calls = 1 if stage in {"body", "retry"} else 0
    assert len(session.calls) == expected_calls
    assert response.closed == bool(expected_calls)
    if stage == "before-governor":
        assert not transport._governor.state_path.exists()

