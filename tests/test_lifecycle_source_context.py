from copy import deepcopy
from dataclasses import replace
import json

import pytest

from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page


def long_source():
    # Distinct paragraphs avoid manufacturing ambiguous repeated citation text.
    filler = "\n".join(f"Unrelated navigation entry {index}: decorative layout information." for index in range(3000))
    return "Public announcement\n" + filler + "\n" + NOTICE + "\n" + filler + "\nHowever, the ordinary shares remain actively traded OTC."


def test_context_keeps_tail_negation_and_dates_without_sending_whole_page():
    from src.lifecycle_source_context import select_source_context

    page = source_page(long_source())
    context = select_source_context(public_input(), page)
    material = context.prompt_material(page)
    sent = "\n".join(part["text"] for part in material["passages"])
    assert NOTICE in sent
    assert "However, the ordinary shares remain actively traded OTC." in sent
    assert material["coverage"] == "selected_passages"
    assert len(sent) < len(page.text) / 10
    assert page.text == long_source()
    encoded = page.text.encode()
    for part in material["passages"]:
        assert encoded[part["start_byte"]:part["end_byte"]].decode() == part["text"]
    assert context.to_material()["source_text_sha256"] == page.text_sha256


def test_no_relevance_match_and_dense_relevance_both_keep_whole_text():
    from src.lifecycle_source_context import select_source_context

    for text in ("\n".join("\u6587\u5b57\u8cc7\u6599" * 100 for _ in range(300)),
                 "\n".join(f"Trading remains active for issuer {index}." for index in range(20000))):
        page = source_page(text)
        material = select_source_context(public_input(), page).prompt_material(page)
        assert material["coverage"] == "full_text"
        assert material["passages"] == [{"start_byte": 0, "end_byte": len(text.encode()), "text": text}]


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(version=999),
    lambda value: value.update(source_text_sha256="0" * 64),
    lambda value: value.update(ranges=[]),
    lambda value: value.update(ranges=[[0, True]]),
    lambda value: value.update(ranges=[[1, 3]]),
    lambda value: value.update(ranges=[[0, 10], [5, 15]]),
    lambda value: value.update(ranges=[[0, 99999999]]),
])
def test_context_manifest_rejects_malformed_ranges_or_changed_source(mutation):
    from src.lifecycle_source_context import SourceContext, select_source_context

    page = source_page("\u66f4\u540d\u6587\u4ef6\n" + NOTICE)
    value = deepcopy(select_source_context(public_input(), page).to_material())
    mutation(value)
    with pytest.raises(ValueError, match="^source_context_invalid$"):
        SourceContext.from_material(value, page)


def test_citation_must_have_been_in_model_context_not_merely_stored_page():
    from src.lifecycle_source_context import SourceContext
    from src.security_lifecycle_web_finding import validate_finding

    text = "Only this unrelated header was supplied.\n" + NOTICE
    page = source_page(text)
    context = SourceContext.from_material({
        "version": 1, "source_text_sha256": page.text_sha256,
        "source_bytes": len(text.encode()), "ranges": [[0, text.index("\n")]],
    }, page)
    checked = validate_finding(public_input(), finding_payload(), {"source-1": page},
                               source_context={"source-1": context.to_material()})
    assert checked.action is None
    assert "source_citation_not_supplied" in checked.block_reasons
    assert checked.passages == ()
    # Original full-source journal entries remain readable and actionable.
    assert validate_finding(public_input(), finding_payload(), {"source-1": page}).action == "terminal_delisting"


def test_json_metadata_cannot_stand_in_for_a_listing_notice():
    from src.security_lifecycle_web_finding import validate_finding
    from src.lifecycle_public_sources import _capture_digest

    page = replace(source_page(NOTICE), mime_type="application/json")
    page = replace(page, capture_sha256=_capture_digest(page))
    finding = validate_finding(public_input(), finding_payload(), {"source-1": page})
    assert finding.action is None and "source_metadata_not_notice" in finding.block_reasons


def test_web_journal_retains_context_ranges_and_full_source_after_reopen(tmp_path, monkeypatch):
    from src.lifecycle_source_context import select_source_context
    from tests.test_lifecycle_web_store import setup_store, completed

    path, store = setup_store(tmp_path)
    original = store.complete
    material = {"source-1": select_source_context(public_input(), source_page(NOTICE)).to_material()}
    monkeypatch.setattr(store, "complete", lambda *args, **kwargs: original(*args, **kwargs, source_context=material))
    identity = completed(store)
    from src.lifecycle_web_store import LifecycleWebStore
    row = LifecycleWebStore(path).read(identity)
    assert row["source_context"] == material
    assert row["pages"]["source-1"].text == NOTICE
    assert row["finding"].action == "terminal_delisting"
    from src.lifecycle_web_projection import project_web_run
    projected = project_web_run(row, at="2026-09-07T00:00:00Z")
    assert projected["source_reading"] == {"sources": 1, "selected_sources": 0,
                                            "retained_text_bytes": len(NOTICE.encode()), "model_text_bytes": len(NOTICE.encode())}
    assert page_private_data_absent(projected)


def page_private_data_absent(projected):
    encoded = json.dumps(projected)
    return not any(value in encoded for value in ("source_text_sha256", "ranges", "page_json", "worker-1", "local:7"))


@pytest.mark.parametrize("value", [None, [], {"source-1": None}, {}])
def test_present_but_malformed_journal_context_is_not_treated_as_legacy_full_text(tmp_path, value):
    from tests.test_lifecycle_web_store import setup_store, completed
    from src.lifecycle_web_store import _json, _sha

    _, store = setup_store(tmp_path)
    identity = completed(store)
    with store.connection(write=True) as conn:
        row = conn.execute("SELECT payload_json FROM lifecycle_web_results WHERE run_id=?", (identity,)).fetchone()
        material = json.loads(row[0])
        material["source_context"] = value
        from src.lifecycle_web_schema import TRIGGERS
        trigger = "lifecycle_web_results_update_immutable"
        conn.execute("DROP TRIGGER " + trigger)
        conn.execute("UPDATE lifecycle_web_results SET payload_json=?,result_sha256=? WHERE run_id=?",
                     (_json(material), _sha(material), identity))
        conn.execute(TRIGGERS[trigger])
    with pytest.raises(ValueError, match="^source_context_invalid$"):
        store.read(identity)
