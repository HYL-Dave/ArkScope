"""Create a content manifest for this completed, non-secret verification packet."""

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
PACKET = Path(__file__).resolve().parent
SECRET = re.compile(
    rb"(?<![A-Za-z0-9])sk-(?:ant-api\d*-|ant-oat\d*-|proj-)?[A-Za-z0-9_-]{20,}"
    rb"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    rb"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
FIXTURE_DIGESTS = {
    "04a58c720e50e840a22988f31fedecfce1ad5484b7504bd2443ab2a61e4d0344",
    "de9a00917b5afe637a836d0b22c7325ef00bda850da03fa5844bfdd677fb92d5",
}


if __name__ == "__main__":
    files = sorted(path for path in PACKET.rglob("*")
                   if path.is_file() and "__pycache__" not in path.parts
                   and path.name != "artifact-files.sha256")
    rows = []
    fixture_matches = 0
    for path in files:
        data = path.read_bytes()
        for match in SECRET.finditer(data):
            node = data[:match.start()].rsplit(b"\n", 1)[-1].split(b"[", 1)[0]
            if (path.name == "collection.txt"
                    and node == b"tests/test_probe_harness.py::test_redact_scrubs_token_shapes"
                    and hashlib.sha256(match.group()).hexdigest() in FIXTURE_DIGESTS
                    and match.group() in (ROOT / "tests/test_probe_harness.py").read_bytes()):
                fixture_matches += 1
            else:
                raise ValueError("secret-shaped content in " + str(path.relative_to(PACKET)))
        rows.append(hashlib.sha256(data).hexdigest() + "  " + str(path.relative_to(ROOT)))
    with (PACKET / "artifact-files.sha256").open("x", encoding="utf-8") as output:
        output.write("\n".join(rows) + "\n")
    print(f"Sealed {len(rows)} files; {fixture_matches} existing redaction-test fixtures, no unexpected secret shapes.")
