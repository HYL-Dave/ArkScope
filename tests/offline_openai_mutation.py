"""Explicit opt-in pytest plugin for no-egress contract mutation checks."""

import inspect


def pytest_addoption(parser):
    parser.addoption("--openai-mutant", choices=(
        "legacy-transport", "alias-receipt", "completion-gate", "text-items",
        "probe-effort-fallback", "calibration-retry",
    ), required=True)


def pytest_configure(config):
    from src import card_synthesis as cs
    from src import openai_response_validation as validation
    from src import model_credentials
    from src import investor_profile_calibration_agent as calibration

    changes = {
        "legacy-transport": (cs._openai_responses_output, "client.responses.create(", "client.chat.completions.create("),
        "alias-receipt": (validation.require_response_model, "if not model_matches:", "if False:"),
        "completion-gate": (validation.require_completed_response,
                            'if response.status != "completed" or response.error is not None:', "if False:"),
        "text-items": (validation.completed_response_text,
                       'raise RuntimeError("OpenAI response returned an unexpected output item")', "continue"),
        "probe-effort-fallback": (model_credentials.test_model,
                                  'if provider == "anthropic" and effort', "if effort"),
        "calibration-retry": (calibration._call_calibration_llm,
                              "live_openai_client().with_options(max_retries=0)", "live_openai_client()"),
    }
    original, old, new = changes[config.getoption("--openai-mutant")]
    source = inspect.getsource(original)
    assert source.count(old) == 1
    # Keep real module globals so dependency isolation applies to the mutant too.
    exec(compile(source.replace(old, new), "<openai-mutation>", "exec"), original.__globals__)
    if config.getoption("--openai-mutant") == "text-items":
        calibration.completed_response_text = validation.completed_response_text
