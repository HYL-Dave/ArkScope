"""Task 2 process-local inverses; launch only through admitted run_checks.py."""

import __future__
import ast
import inspect
import json
import os
from pathlib import Path
import runpy
import sys
import textwrap
from types import CodeType

import pytest


MODES = {
    "omit-openai", "omit-anthropic", "omit-chatgpt", "omit-claude",
    "generic-truncation", "omit-worker-join", "omit-subagent-guard",
    "omit-subagent-required-tool",
}
mode = sys.argv.pop(1)
if mode not in MODES:
    raise SystemExit(f"Unknown Task 2 inverse: {mode}")


def same_expression(node, source):
    expected = ast.parse(source, mode="eval").body
    return ast.dump(node) == ast.dump(expected)


class Fault:
    def __init__(self):
        self.patches = []
        self.pools = []
        self.items = []
        self.collected = []
        self.reports = []
        self.exit_code = None

    def replace(self, owner, name, value):
        self.patches.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def rewrite(self, function):
        lines, start = inspect.getsourcelines(function)
        tree = ast.parse(textwrap.dedent("".join(lines)))
        changes = 0
        for node in ast.walk(tree):
            if mode == "omit-openai" and isinstance(node, ast.List):
                kept = [element for element in node.elts if not
                        same_expression(element, "sec_function_tool(list_sec_filings)")]
                changes += len(node.elts) - len(kept)
                node.elts = kept
            elif mode == "omit-anthropic" and isinstance(node, ast.Call):
                if same_expression(node, "tools.extend(sec.to_anthropic_schema())"):
                    node.args[0] = ast.copy_location(ast.parse(
                        '[schema for schema in sec.to_anthropic_schema() '
                        'if schema["name"] != "list_sec_filings"]', mode="eval").body,
                        node.args[0])
                    changes += 1
            elif mode == "generic-truncation" and isinstance(node, ast.Return):
                if node.value is not None and same_expression(node.value, "sec_result_reducer"):
                    node.value = ast.copy_location(ast.Name(id="truncate_with_marker", ctx=ast.Load()),
                                                   node.value)
                    changes += 1
            elif mode == "omit-worker-join" and isinstance(node, ast.ExceptHandler):
                for index, statement in enumerate(node.body[:-1]):
                    following = node.body[index + 1]
                    if (isinstance(statement, ast.While)
                            and same_expression(statement.test, "not future.done()")
                            and isinstance(following, ast.Expr)
                            and same_expression(following.value, "future.result()")):
                        del node.body[index:index + 2]
                        changes += 1
                        break
            elif mode == "omit-subagent-guard" and isinstance(node, ast.FunctionDef):
                kept = [statement for statement in node.body if not (
                    isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == "require_sec_inventory")]
                changes += len(node.body) - len(kept)
                node.body = kept
        if changes != 1:
            raise RuntimeError(f"Injection shape drift: {mode} matched {changes} boundaries")
        ast.fix_missing_locations(tree)
        ast.increment_lineno(tree, start - 1)
        # Extract only the compiled function code. Never execute a source module,
        # replace fixtures, re-evaluate defaults, or modify imported aliases.
        flags = function.__code__.co_flags & __future__.annotations.compiler_flag
        compiled = compile(tree, function.__code__.co_filename, "exec", flags=flags, dont_inherit=True)
        candidates = [value for value in compiled.co_consts
                      if isinstance(value, CodeType) and value.co_name == function.__name__]
        if len(candidates) != 1 or candidates[0].co_freevars != function.__code__.co_freevars:
            raise RuntimeError("Injection changed the function closure contract")
        self.replace(function, "__code__", candidates[0])

    def inject(self):
        # All product imports are inside pytest's call hook, after the unchanged
        # offline_pytest launcher has installed its audit hook and closed env.
        if mode == "omit-openai":
            from src.agents.openai_agent.tools import create_openai_tools
            self.rewrite(create_openai_tools)
        elif mode == "omit-anthropic":
            from src.agents.anthropic_agent.tools import get_anthropic_tools
            self.rewrite(get_anthropic_tools)
        elif mode in {"omit-chatgpt", "omit-claude"}:
            if mode == "omit-chatgpt":
                from src.auth_drivers import chatgpt_oauth_driver as module
            else:
                from src.auth_drivers import claude_code_sdk_driver as module
            original = module._RESEARCH_READONLY_TOOLS
            if "list_sec_filings" not in original:
                raise RuntimeError("Injection target is already missing from the allowlist")
            self.replace(module, "_RESEARCH_READONLY_TOOLS", original - {"list_sec_filings"})
        elif mode == "generic-truncation":
            from src.agents.shared.compressor.reducers import get_reducer
            self.rewrite(get_reducer)
        elif mode == "omit-subagent-guard":
            from src.agents.shared.subagent import _filter_openai_tools
            self.rewrite(_filter_openai_tools)
        elif mode == "omit-subagent-required-tool":
            from src.agents.shared.subagent import SUBAGENT_REGISTRY
            spec = SUBAGENT_REGISTRY["deep_researcher"]
            original = spec.tool_names
            if not isinstance(original, list) or original.count("list_sec_filings") != 1:
                raise RuntimeError("Injection target must occur once in the subagent tool list")
            self.replace(spec, "tool_names", [name for name in original if name != "list_sec_filings"])
        else:
            from src.sec_research import tool_execution
            self.rewrite(tool_execution.invoke_sec_tool)
            original_pool = tool_execution.ThreadPoolExecutor

            def tracked_pool(*args, **kwargs):
                pool = original_pool(*args, **kwargs)
                self.pools.append(pool)
                return pool

            self.replace(tool_execution, "ThreadPoolExecutor", tracked_pool)

    def restore(self, record):
        try:
            # Reap only this item's actual SEC pools, after its behavioral
            # assertion ran and before monkeypatch/storage fixtures tear down.
            threads = set()
            for pool in self.pools:
                pool.shutdown(wait=True, cancel_futures=True)
                threads.update(pool._threads)
            record["owned_pools_reaped"] = len(self.pools)
            record["owned_threads_reaped"] = len(threads)
            record["owned_threads_alive"] = sum(thread.is_alive() for thread in threads)
        finally:
            patches = self.patches[:]
            for owner, name, original in reversed(patches):
                setattr(owner, name, original)
            record["restored_attributes"] = len(patches)
            record["restored"] = all(getattr(owner, name) is original
                                     for owner, name, original in patches)
            self.patches.clear()
            self.pools.clear()

    def pytest_collection_modifyitems(self, items):
        self.collected = [item.nodeid for item in items]

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_call(self, item):
        record = {"nodeid": item.nodeid, "mode": mode}
        self.items.append(record)
        try:
            self.inject()
            record["injected"] = True
            yield
        finally:
            self.restore(record)

    def pytest_runtest_logreport(self, report):
        entry = {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome}
        if report.failed or report.skipped:
            entry["longrepr"] = report.longreprtext
        self.reports.append(entry)

    def pytest_sessionfinish(self, exitstatus):
        self.exit_code = int(exitstatus)

    def finish(self, original_main):
        data = {
            "mode": mode, "exit_code": self.exit_code,
            "collected": self.collected, "items": self.items, "reports": self.reports,
            "pytest_main_restored": pytest.main is original_main,
            "all_items_restored": bool(self.items) and all(item.get("restored") for item in self.items),
            "all_collected_called": self.collected == [item["nodeid"] for item in self.items],
            "remaining_patches": len(self.patches), "remaining_pools": len(self.pools),
            "call_failures": sum(report["when"] == "call" and report["outcome"] == "failed"
                                 for report in self.reports),
            "skipped_reports": sum(report["outcome"] == "skipped" for report in self.reports),
        }
        path = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"]) / "task2-inverse.json"
        with path.open("x") as output:
            json.dump(data, output, indent=2)
            output.write("\n")
        print("TASK2_INVERSE " + json.dumps({key: value for key, value in data.items()
                                            if key not in {"items", "reports", "collected"}}), flush=True)


fault = Fault()
original_main = pytest.main
pytest.main = lambda args: original_main(args, plugins=[fault])
launcher = Path(__file__).with_name("offline_pytest.py")
sys.argv[0] = str(launcher)
try:
    runpy.run_path(str(launcher), run_name="__main__")
finally:
    pytest.main = original_main
    fault.finish(original_main)
