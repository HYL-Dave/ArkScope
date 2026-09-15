"""Replay the user-downloaded SEC bytes without DB access or acquisition."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types


REPO = Path(__file__).resolve().parents[4]
BASE = "f36a7b336aad35d49c043547815e0f28dee463ff"
ORIGINAL_SHA = "548ae59778cf08ee0f2ee088e7ece20d947076c3c01f74d2d65db4c2777e436a"
TEXT_SHA = "6c6372dc63236ef8831c6cfb3ff8d3180f5ecd0a47b52282ff365b0bd81f758a"


def observe(owner, body):
    structures = []
    text, mime = owner.extract_document_text(
        body, "text/html", check=lambda: None, structure_observer=structures.append)
    sections, gaps = owner.index_sections(
        text, "10-K", check=lambda: None, toc_ranges=structures[0]["toc_ranges"])
    return {
        "extraction_version": owner.EXTRACTION_VERSION,
        "mime": mime,
        "text_bytes": len(text.encode()),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        **structures[0],
        "sections": sections,
        "section_gaps": gaps,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    body = args.original.read_bytes()
    assert len(body) == 1_520_208
    assert hashlib.sha256(body).hexdigest() == ORIGINAL_SHA
    sys.path.insert(0, str(REPO))
    from src.sec_research import document_text

    baseline = types.ModuleType("sec_settings_replay_baseline")
    sys.modules[baseline.__name__] = baseline
    code = subprocess.check_output(
        ["git", "show", BASE + ":src/sec_research/document_text.py"], cwd=REPO)
    exec(compile(code, "baseline/document_text.py", "exec"), baseline.__dict__)
    before, after = observe(baseline, body), observe(document_text, body)
    assert before["extraction_version"] == "sec-document-text-v4"
    assert after["extraction_version"] == "sec-document-text-v5"
    assert before["text_sha256"] == after["text_sha256"] == TEXT_SHA
    assert before["text_bytes"] == after["text_bytes"] == 207_845
    assert before["sections"] == [] and len(before["section_gaps"]) == 27
    assert len(after["sections"]) == 27 and after["section_gaps"] == []
    assert after["structure_gaps"] == []
    assert after["toc_ranges"] == [{"start_byte": 5288, "end_byte": 6576}]
    result = {
        "base": BASE, "original_sha256": ORIGINAL_SHA,
        "original_bytes": len(body), "before": before, "after": after,
        "database_access": False, "provider_calls": False,
        "retained_capture_rewritten": False,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
