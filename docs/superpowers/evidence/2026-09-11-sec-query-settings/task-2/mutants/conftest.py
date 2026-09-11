"""Inverse verification in isolated module globals; no production file writes."""

import hashlib
import json
from pathlib import Path
import types

import pytest


ROOT = Path(__file__).resolve().parents[5]
OWNED = ["src/sec_research/queries.py", "src/sec_research/fact_queries.py",
         "tests/test_sec_research_fact_queries.py"]


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in OWNED}


def pytest_addoption(parser):
    parser.addoption("--fact-mutant", choices=["float", "as-of-end", "ids-latest"], required=True)


@pytest.fixture(autouse=True)
def mutate(request, monkeypatch):
    from src.sec_research import fact_queries

    before = hashes()
    source = (ROOT / "src/sec_research/fact_queries.py").read_text()
    mutant = request.config.getoption("--fact-mutant")
    old, new = {
        "float": ('rows = _periods(rows)', 'rows = _periods([{**row, "value": str(float(row["value"]))} for row in rows])'),
        "as-of-end": ('row["filed_date"] > filters["as_of"]', 'row["end"] > filters["as_of"]'),
        "ids-latest": ('rows = _periods(rows)', 'rows = _periods(_latest(rows) if "fact_ids" in filters else rows)'),
    }[mutant]
    assert source.count(old) == 1
    module = types.ModuleType("src.sec_research.fact_queries")
    exec(compile(source.replace(old, new), f"<task2-{mutant}>", "exec"), module.__dict__)
    monkeypatch.setattr(fact_queries, "query_facts", module.query_facts)
    yield
    monkeypatch.undo()
    after = hashes()
    assert before == after
    output = Path(request.config.option.xmlpath).parent / "hashes.json"
    output.write_text(json.dumps({"mutant": mutant, "before": before, "after": after,
                                  "unchanged": before == after}, indent=2) + "\n")
