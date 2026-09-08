"""In-memory negative controls; never edit the worktree or call a provider."""
import inspect
from pathlib import Path
import sys
import textwrap
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path.cwd()))

if sys.argv[1] == "request-errors":
    from data_sources import ibkr_source

    original = ibkr_source.IBKRDataSource._price_request
    source = textwrap.dedent(inspect.getsource(original))
    assert source.count("ib.RaiseRequestErrors = True") == 1
    scope = {}
    exec(source.replace("ib.RaiseRequestErrors = True", "ib.RaiseRequestErrors = False"), vars(ibkr_source), scope)
    with patch.object(ibkr_source.IBKRDataSource, "_price_request", scope["_price_request"]):
        code = pytest.main(["-q", "tests/test_ibkr_price_request_diagnostics.py::test_qualification_request_error_is_not_an_unknown_contract"])
elif sys.argv[1] == "atomic-routes":
    from src.model_route_store import ModelRouteStore

    original = ModelRouteStore.set_many

    def non_atomic(self, routes):
        return [original(self, [row])[0] for row in routes]

    with patch.object(ModelRouteStore, "set_many", non_atomic):
        code = pytest.main(["-q", "tests/test_model_route_store.py::test_batch_save_rolls_back_every_route_when_a_later_write_fails",
                            "tests/test_lifecycle_investigation_routing.py::test_multi_task_route_save_api_rolls_back_on_late_sql_failure"])
else:
    raise SystemExit("unknown mutation")

raise SystemExit(int(code))
