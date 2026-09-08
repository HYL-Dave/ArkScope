import hashlib
import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("instrument_record", Path(__file__).with_name("record_live.py"))
record = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(record)


def test_quote_projection_retains_original_and_never_republishes_nested_quotations():
    original = {"finding": {"citations": [{"quote": "Private exact quote", "url": "https://example.com/notice"}]}}
    projected = record.without_quotations(original)
    assert original["finding"]["citations"][0]["quote"] == "Private exact quote"
    assert projected["finding"]["citations"] == [{"url": "https://example.com/notice",
        "quote_utf8_bytes": 19, "quote_sha256": hashlib.sha256(b"Private exact quote").hexdigest()}]


def test_actual_frontend_reader_accepts_reopened_product_run(tmp_path):
    from src.lifecycle_web_projection import project_web_run
    from src.lifecycle_web_store import LifecycleWebStore
    from tests.test_lifecycle_web_review import context

    c = context(tmp_path, auth="claude_code_oauth")
    row = LifecycleWebStore(c["profile"], clock=lambda: c["now"][0]).read(c["run_id"])
    projection = project_web_run(row, at=c["now"][0])
    record.frontend_readback(projection)
    assert projection["finding"]["action"] == "terminal_delisting"
