import sqlite3

import pytest


def test_runtime_defaults_are_independent_and_reads_do_not_install(tmp_path):
    from src.lifecycle_investigation.runtime import InvestigationRuntime, RuntimeStore
    path = tmp_path / "profile.db"
    sqlite3.connect(path).close()
    before = path.read_bytes()
    assert RuntimeStore(path).read() == InvestigationRuntime()
    assert path.read_bytes() == before
    assert InvestigationRuntime().model_submissions == 24


@pytest.mark.parametrize("field,value", [("model_submissions", 0), ("model_submissions", True),
    ("deadline_seconds", float("nan")), ("http_requests", -1), ("unknown", 5)])
def test_runtime_rejects_invalid_or_unknown_values(field, value):
    from src.lifecycle_investigation.runtime import InvestigationRuntime
    with pytest.raises(ValueError):
        InvestigationRuntime.model_validate({field: value})


def test_runtime_save_reset_and_roundtrip_are_profile_scoped(tmp_path):
    from src.lifecycle_investigation.runtime import InvestigationRuntime, RuntimeStore
    store = RuntimeStore(tmp_path / "profile.db")
    configured = InvestigationRuntime(model_submissions=40, deadline_seconds=2400)
    store.save(configured)
    assert store.read() == configured
    assert RuntimeStore(tmp_path / "other.db").read() == InvestigationRuntime()
    store.reset()
    assert store.read() == InvestigationRuntime()


def test_runtime_existing_malformed_empty_table_is_not_a_default(tmp_path):
    from src.lifecycle_investigation.runtime import RuntimeStore
    path = tmp_path / "profile.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE lifecycle_investigation_runtime(singleton,version,config_json)")
    with pytest.raises(ValueError, match="investigation_runtime_schema_mismatch"):
        RuntimeStore(path).read()
