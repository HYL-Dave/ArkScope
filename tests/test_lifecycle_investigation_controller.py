from threading import Event

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential
from src.lifecycle_investigation.controller import InvestigationController
from src.lifecycle_investigation.news import LocalNews
from tests.test_lifecycle_investigation_store import running


@pytest.mark.parametrize("changed", ("cancel", "credential", "permission"))
def test_pre_dispatch_rereads_stop_identity_and_permission_after_credential_load(tmp_path, changed):
    _, store, initial, binding = running(tmp_path)
    store.finish(initial, owner="worker", status="failed")
    loading, release, invoked = Event(), Event(), []
    permit = [True]

    def before_dispatch():
        if not permit[0]:
            raise ValueError("writes_disabled")

    def load(selection):
        loading.set()
        assert release.wait(5)
        return WebCredential(selection, generation="changed" if changed == "credential" else "generation-1")

    async def runner(*args, **kwargs):
        invoked.append(True)
        raise AssertionError("Must stop before the agent or provider is invoked")

    controller = InvestigationController(store, credential_loader=load, news_factory=lambda: LocalNews(None, None),
        before_dispatch=before_dispatch, runner=runner, heartbeat_seconds=.02)
    job = controller.start(binding=binding, request_key="second-click")
    assert loading.wait(5)
    if changed == "cancel":
        controller.cancel(job["run_id"])
    if changed == "permission":
        permit[0] = False
    with controller._lock:
        thread = controller._workers[job["run_id"]].thread
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    row = store.read(job["run_id"])
    assert invoked == []
    assert row["status"] == ("cancelled" if changed == "cancel" else "failed")
    assert row["calls"] == []
    controller.close()
