"""Verify R1 restoration without inspecting other workers' changing files."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FILES = ["src/sec_research/store.py", "tests/test_sec_research_store.py",
         "tests/test_sec_research_queries.py"]
hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
label = sys.argv[1]
if label != "before":
    assert hashes == json.loads((HERE / "r1-hashes-before.json").read_text())
(HERE / ("r1-hashes-" + label + ".json")).write_text(json.dumps(hashes, indent=2) + "\n")
print(json.dumps({"label": label, "sha256": hashes}, indent=2))
