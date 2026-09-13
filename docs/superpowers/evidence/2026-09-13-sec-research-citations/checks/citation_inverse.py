"""Run one exact in-memory source inverse under the unchanged offline guard."""

import __future__
import difflib
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import runpy
import sys
import textwrap

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK))
import offline_pytest  # noqa: E402,F401
import pytest  # noqa: E402


class Inverse:
    def __init__(self, recipe):
        self.recipe = recipe
        self.owner = self.original = None

    def pytest_sessionstart(self, session):
        recipe = self.recipe
        module = importlib.import_module(recipe["module"])
        owner = module
        parts = recipe["qualname"].split(".")
        for part in parts[:-1]:
            owner = getattr(owner, part)
        self.name = parts[-1]
        original = getattr(owner, self.name)
        before = textwrap.dedent(inspect.getsource(original))
        after = before
        for replacement in recipe["replacements"]:
            if after.count(replacement["old"]) != replacement.get("count", 1):
                raise AssertionError("inverse anchor count mismatch: " + recipe["name"])
            after = after.replace(replacement["old"], replacement["new"])
        if before == after:
            raise AssertionError("inverse made no change")
        namespace = {}
        exec(compile(after, original.__code__.co_filename, "exec",
                     flags=__future__.annotations.compiler_flag), original.__globals__, namespace)
        mutated = namespace[self.name]
        if mutated.__code__.co_freevars != original.__code__.co_freevars:
            raise AssertionError("inverse changed function closure")
        self.owner, self.original = owner, original
        self.original_code = original.__code__
        # Preserve existing imported aliases, not only the module attribute.
        original.__code__ = mutated.__code__
        self.record = {"name": recipe["name"], "module": recipe["module"],
                       "qualname": recipe["qualname"], "recipe": recipe,
                       "source_sha256": hashlib.sha256(before.encode()).hexdigest(),
                       "inverse_sha256": hashlib.sha256(after.encode()).hexdigest(),
                       "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                          fromfile="admitted", tofile="inverse")),
                       "tracked_source_edited": False}

    def pytest_sessionfinish(self, session, exitstatus):
        if self.owner is None:
            return
        self.original.__code__ = self.original_code
        self.record.update(exit_code=int(exitstatus), original_restored=(
            getattr(self.owner, self.name) is self.original and self.original.__code__ is self.original_code))
        destination = offline_pytest.WORK / "citation-inverse.json"
        with destination.open("x") as output:
            json.dump(self.record, output, indent=2, sort_keys=True)
            output.write("\n")


if __name__ == "__main__":
    recipe_path = (WORK / sys.argv.pop(1)).resolve()
    if recipe_path.parent != WORK or recipe_path.suffix != ".json":
        raise ValueError("inverse recipe must be a plan-owned JSON file")
    plugin = Inverse(json.loads(recipe_path.read_text()))
    original_main = pytest.main

    def guarded_main(args):
        return original_main(args, plugins=[plugin])

    pytest.main = guarded_main
    runpy.run_path(str(WORK / "offline_pytest.py"), run_name="__main__")
