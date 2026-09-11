"""Prove inverse mutations restore only Task 1's explicit source/test files."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FILES = ["src/sec_research/schema.py", "src/sec_research/store.py", "src/sec_research/service.py",
         "src/sec_research/queries.py", "tests/test_sec_research_store.py",
         "tests/test_sec_research_service.py", "tests/test_sec_research_queries.py"]
values = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
label = sys.argv[1]
if label != "before":
    assert values == json.loads((HERE / "hashes-before.json").read_text()), "mutation restoration differs"
(HERE / ("hashes-" + label + ".json")).write_text(json.dumps(values, indent=2) + "\n")
print(json.dumps({"label": label, "sha256": values}, indent=2))
