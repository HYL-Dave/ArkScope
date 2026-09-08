import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


SPEC = importlib.util.spec_from_file_location("original_analysis_diagnostic", Path(__file__).with_name("diagnose_original_analysis.py"))
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)
CAPTURE = Path("/tmp/lifecycle-instrument-live-r1")
DOCUMENT = Path("/tmp/lifecycle-instrument-document-r1")


def test_recorded_preparation_uses_real_product_prompt_without_network_or_credentials(monkeypatch):
    from src.lifecycle_public_sources import PublicSourceReader

    def deny(*args, **kwargs):
        raise AssertionError("offline_preparation_must_not_read_production_or_network")
    before = hashlib.sha256((CAPTURE / "profile.sqlite").read_bytes()).hexdigest()
    monkeypatch.setattr(PublicSourceReader, "read", deny)
    monkeypatch.setattr(diagnostic.original, "selected_metadata", deny)
    row, call = asyncio.run(diagnostic.prepared_call(CAPTURE, DOCUMENT))
    assert len(row["pages"]) == 5 and call.phase == "analysis" and call.timeout_seconds == 600
    assert call.selection.model == "claude-sonnet-5"
    assert 'tm2315684d1_8k.htm' in call.prompt and 'ceased to trade' in call.prompt
    assert hashlib.sha256((CAPTURE / "profile.sqlite").read_bytes()).hexdigest() == before


@pytest.mark.parametrize("change", ("source_text", "budget_receipt"))
def test_preparation_rejects_changed_capture_or_source_budget_before_a_model_call(tmp_path, change):
    shutil.copytree(DOCUMENT, tmp_path / "document")
    file = tmp_path / "document" / ("document-page.json" if change == "source_text" else "metrics.json")
    value = json.loads(file.read_text())
    if change == "source_text":
        value["text"] += "Changed content"
    else:
        value["source_http_campaign_used"] = 25
    file.write_text(json.dumps(value))
    with pytest.raises(AssertionError):
        asyncio.run(diagnostic.prepared_call(CAPTURE, tmp_path / "document"))


@pytest.mark.parametrize("value, valid", [(' {"value": 1}', True), ('```json\n{"value":1}\n```', False),
                                        ('{"value":"1"}', False), (None, False)])
def test_raw_final_diagnostic_never_repairs_or_changes_provider_output(value, valid):
    schema = {"type": "object", "properties": {"value": {"type": "integer"}},
              "required": ["value"], "additionalProperties": False}
    result = diagnostic.inspect_final(value, schema)
    assert result["host_schema_valid"] is valid
    if value is None:
        assert result["result_type"] == "NoneType"
    elif value.startswith('```'):
        assert result["json_error"]["line"] == 1
    elif not valid:
        assert result["schema_errors"][0]["keyword"] == "type"
