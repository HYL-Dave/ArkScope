"""Financial evidence crosses model boundaries whole or as an explicit page refusal."""

import json

import pytest

from src.agents.shared.compressor.reducers import get_reducer


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("budget", [800, 100000])
def test_compressed_financial_read_preserves_basis_or_returns_gap(wrapped, budget):
    value = {"status": "ok", "read_id": "a" * 64, "data_source": "seeking_alpha",
             "metric_basis": {"gross_margin": {"precision": "provider_display_rounded"}},
             "read_gaps": [], "income_statements": [{"data": {"revenue": "12345678901234567890.12"},
                 "value_metadata": {"revenue": {"raw": "9" * 20000}}}]}
    payload = json.dumps(value)
    prefix, suffix = '<tool_output tool="get_fundamentals_analysis">\n', '\n</tool_output>'
    if wrapped:
        payload = prefix + payload + suffix
    result, meta = get_reducer("tool_get_fundamentals_analysis")(payload, budget=budget)
    decoded = json.loads(result[len(prefix):-len(suffix)] if wrapped else result)
    if budget == 100000:
        assert decoded == value and meta == {}
    else:
        assert decoded == {"status": "unavailable", "error_code": "financial_read_page_too_large",
                           "read_id": value["read_id"], "required_action": "repeat_same_read_with_smaller_page"}
        assert len(result) <= budget


def test_malformed_financial_output_never_becomes_truncated_numbers():
    result, _ = get_reducer("get_fundamentals_analysis")('{"revenue":123456', budget=800)
    assert json.loads(result)["error_code"] == "financial_read_result_invalid"
