"""Process-local fault injection; never mutate source files under another check."""

from pathlib import Path
import runpy
import sys

import pytest

mode = sys.argv.pop(1)
assert mode in {"obsolete-export", "retained-export", "key-precedence"}


class Fault:
    undo = None

    def pytest_runtest_setup(self, item):
        import data_sources

        if mode == "key-precedence":
            from data_sources.polygon_source import PolygonDataSource
            import os

            original = PolygonDataSource.__init__

            def wrong_precedence(instance, *args, **kwargs):
                original(instance, *args, **kwargs)
                instance.api_key = os.environ["POLYGON_API_KEY"]

            PolygonDataSource.__init__ = wrong_precedence
            self.undo = lambda: setattr(PolygonDataSource, "__init__", original)
        else:
            original = data_sources.__all__
            data_sources.__all__ = (original + ["get_data_source"]
                if mode == "obsolete-export" else [n for n in original if n != "PolygonDataSource"])
            self.undo = lambda: setattr(data_sources, "__all__", original)

    def pytest_runtest_teardown(self, item):
        if self.undo is not None:
            self.undo()
            self.undo = None


main = pytest.main
pytest.main = lambda args: main(args, plugins=[Fault()])
launcher = Path(__file__).with_name("offline_pytest.py")
sys.argv[0] = str(launcher)
runpy.run_path(str(launcher), run_name="__main__")
