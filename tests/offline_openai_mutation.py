"""Explicit opt-in pytest plugin for no-egress contract mutation checks."""

from dataclasses import replace
import inspect


def pytest_addoption(parser):
    parser.addoption("--openai-mutant", choices=("legacy-transport", "alias-receipt"), required=True)


def pytest_configure(config):
    from src import card_synthesis as cs

    if config.getoption("--openai-mutant") == "legacy-transport":
        original = cs.capability_for

        def legacy(model):
            cap = original(model)
            return replace(cap, uses_responses_for_tools=False) if cap and cap.id.startswith("gpt-5.6-") else cap

        cs.capability_for = legacy
    else:
        original = cs._openai_responses_output
        source = inspect.getsource(original)
        assert source.count("if not model_matches:") == 1
        # Real module globals preserve pytest's dependency patches.
        exec(compile(source.replace("if not model_matches:", "if False:"),
                     "<receipt-mutation>", "exec"), original.__globals__)
