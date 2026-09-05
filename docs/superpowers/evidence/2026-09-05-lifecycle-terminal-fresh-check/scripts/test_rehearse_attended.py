import importlib.util
import os
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("rehearse_attended", Path(__file__).with_name("rehearse_attended.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("encoded", (False, True))
@pytest.mark.parametrize("kind", ("copy", "profile_readonly", "market_readonly", "sa_readonly"))
def test_rehearsal_sqlite_gate_accepts_native_path_encoding_without_widening_scope(tmp_path, encoded, kind):
    copy = tmp_path / "profile-rehearsal.db"
    values = {"copy": str(copy), "profile_readonly": f"{runner.base.PROFILE.as_uri()}?mode=ro",
              "market_readonly": f"{runner.MARKET.as_uri()}?mode=ro", "sa_readonly": f"file:{runner.base.SA}?mode=ro"}
    value = values[kind]
    runner.audit_for(copy)("sqlite3.connect", (os.fsencode(value) if encoded else value,))


@pytest.mark.parametrize("encoded", (False, True))
@pytest.mark.parametrize("kind", ("profile_path", "profile_write", "market_write", "sa_write", "other_file"))
def test_rehearsal_sqlite_gate_rejects_production_writes_and_other_stores(tmp_path, encoded, kind):
    copy = tmp_path / "profile-rehearsal.db"
    values = {"profile_path": str(runner.base.PROFILE), "profile_write": f"{runner.base.PROFILE.as_uri()}?mode=rw",
              "market_write": f"{runner.MARKET.as_uri()}?mode=rw", "sa_write": f"file:{runner.base.SA}?mode=rw",
              "other_file": str(tmp_path / "other.db")}
    value = values[kind]
    with pytest.raises(runner.base.CheckStopped, match="rehearsal_production_write_forbidden"):
        runner.audit_for(copy)("sqlite3.connect", (os.fsencode(value) if encoded else value,))


@pytest.mark.parametrize("event", ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"))
def test_rehearsal_never_connects_to_a_provider_or_starts_another_process(tmp_path, event):
    with pytest.raises(runner.base.CheckStopped, match="rehearsal_external_effect_forbidden"):
        runner.audit_for(tmp_path / "profile-rehearsal.db")(event, ())
