"""In-memory negative controls; production source files remain untouched."""

import inspect
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
FOCUS = sorted({str(path.relative_to(ROOT)) for path in (ROOT / "tests").glob("test_model_*.py")} | {
    "tests/test_gpt6_admission.py", "tests/test_card_synthesis.py",
    "tests/test_analysis_cards_api.py", "tests/test_content_translation_failures.py",
    "tests/test_security_lifecycle_translation.py", "tests/test_openai_transport.py",
    "tests/test_subscription_structured_output.py", "tests/test_security_lifecycle_automation_config.py",
    "tests/test_security_lifecycle_routes.py", "tests/test_data_scheduler.py",
    "tests/test_security_lifecycle_automation_scheduler.py", "tests/test_ticker_identity_scheduler.py",
    "tests/test_security_lifecycle_automation_worker.py", "tests/test_security_lifecycle_decision_policy.py",
})


def focused_tests():
    return pytest.main(["-q", *FOCUS, "--tb=short"])


def run(mutation):
    from src import card_synthesis as cs
    from src.service.security_lifecycle_automation_config import SecurityLifecycleAutomationConfigState

    if mutation == "baseline":
        return focused_tests()
    if mutation == "output_classification":
        from src import content_translation_failures as failures
        original = failures.ModelStructuredOutputInvalid
        failures.ModelStructuredOutputInvalid = type("UnmatchedOutputError", (ValueError,), {})
        try:
            return focused_tests()
        finally:
            failures.ModelStructuredOutputInvalid = original
    if mutation == "disabled_mutation":
        original = SecurityLifecycleAutomationConfigState.effective_apply_profile_transitions
        SecurityLifecycleAutomationConfigState.effective_apply_profile_transitions = property(
            lambda self: bool(self.valid and self.config and self.config.apply_profile_transitions))
        try:
            return focused_tests()
        finally:
            SecurityLifecycleAutomationConfigState.effective_apply_profile_transitions = original
    changes = {
        "completion_gate": ("_openai_responses_output", 'if response.status != "completed" or response.error is not None:', "if False:"),
        "model_receipt": ("_openai_responses_output", "if not model_matches:", "if False:"),
        "translation_shape": ("translate_card", "Draft202012Validator(schema).validate(translated)", "pass"),
    }
    name, old, new = changes[mutation]
    original = getattr(cs, name)
    source = inspect.getsource(original)
    assert source.count(old) == 1
    # Keep normal module globals so pytest's dependency patches still apply.
    namespace = original.__globals__
    exec(compile(source.replace(old, new), "<in-memory-mutation>", "exec"), namespace)
    setattr(cs, name, namespace[name])
    try:
        return focused_tests()
    finally:
        setattr(cs, name, original)


if __name__ == "__main__":
    # A failing test is the required result, not a swallowed mutation escape.
    result = run(sys.argv[1])
    expected = pytest.ExitCode.OK if sys.argv[1] == "baseline" else pytest.ExitCode.TESTS_FAILED
    raise SystemExit(0 if result == expected else 1)
