"""Content-free secret-shape scan; never load production secrets for comparison."""

import hashlib
import json
from pathlib import Path
import re


PATTERNS = {
    "provider_key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
    "jwt": re.compile(rb"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer": re.compile(rb"\bBearer [A-Za-z0-9._~-]{30,}"),
}
SYNTHETIC_TEST_FIXTURES = {
    "04a58c720e50e840a22988f31fedecfce1ad5484b7504bd2443ab2a61e4d0344": ("provider_key", "_SK"),
    "de9a00917b5afe637a836d0b22c7325ef00bda850da03fa5844bfdd677fb92d5": ("provider_key", "_SK_ANT"),
    "670b9d6f09faf50459967219b09b3fd3692d9aa715afc89061d6bc3d59ca834a": ("jwt", "_JWT"),
}


def scan_files(files):
    findings = []
    for name, path in files.items():
        body = path.read_bytes()
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(body):
                digest = hashlib.sha256(match.group()).hexdigest()
                start, end = body.rfind(b"\n", 0, match.start()) + 1, body.find(b"\n", match.end())
                line = body[start:end if end >= 0 else len(body)]
                fixture = SYNTHETIC_TEST_FIXTURES.get(digest)
                allowed = (fixture is not None and kind == fixture[0]
                           and path.name in {"backend.xml", "backend-nodes.json"}
                           and b"test_redact_scrubs_token_shapes" in line)
                findings.append({"file": name, "kind": kind, "sha256": digest,
                                 "synthetic_named_test_fixture": allowed,
                                 "fixture_constant": fixture[1] if allowed else None})
    return {
        "scope": "pattern_scan_only_no_production_credential_read",
        "files_scanned": len(files), "findings": findings,
        "unexpected": sum(not row["synthetic_named_test_fixture"] for row in findings),
    }


if __name__ == "__main__":
    packet = Path(__file__).resolve().parent
    result = scan_files({str(path.relative_to(packet)): path for path in packet.rglob("*")
                         if path.is_file() and "__pycache__" not in path.parts})
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(bool(result["unexpected"]))
