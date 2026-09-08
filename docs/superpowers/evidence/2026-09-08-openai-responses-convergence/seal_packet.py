"""Create-only, provider-free summaries and hashes for completed local reports."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[4]
PACKET = Path(__file__).resolve().parent
REPORTS = (
    "red", "green", "focused", "legacy-transport", "alias-receipt",
    "completion-gate", "text-items", "text-items-corrected",
    "probe-effort-fallback", "calibration-retry", "backend", "backend-corrected",
)
SOURCES = (
    "src/card_synthesis.py", "src/investor_profile_calibration_agent.py",
    "src/model_capabilities.py", "src/model_credentials.py",
    "src/openai_response_validation.py", "tests/offline_openai_mutation.py",
    "tests/test_card_synthesis.py", "tests/test_gpt6_admission.py",
    "tests/test_openai_fixed_output_compatibility.py",
    "tests/test_openai_responses_convergence.py", "docs/design/PROJECT_PRIORITY_MAP.md",
    "requirements.txt",
    "docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py",
)
SECRET = re.compile(
    rb"(?<![A-Za-z0-9])sk-(?:ant-api\d*-|ant-oat\d*-|proj-)?[A-Za-z0-9_-]{20,}"
    rb"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    rb"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
FIXTURE_DIGESTS = {
    "04a58c720e50e840a22988f31fedecfce1ad5484b7504bd2443ab2a61e4d0344",
    "de9a00917b5afe637a836d0b22c7325ef00bda850da03fa5844bfdd677fb92d5",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_report(data, tree):
    # Permit only exact preexisting redaction-fixture literals in their test IDs.
    allowed = Counter()
    fixture = (ROOT / "tests/test_probe_harness.py").read_bytes()
    for case in tree.iter("testcase"):
        name = case.get("name", "")
        if (case.get("classname") == "tests.test_probe_harness"
                and name.startswith("test_redact_scrubs_token_shapes[")):
            for match in SECRET.finditer(name.encode()):
                value = match.group()
                if digest(value) in FIXTURE_DIGESTS and value in fixture:
                    allowed[value] += 1
    if Counter(match.group() for match in SECRET.finditer(data)) != allowed:
        raise ValueError("unexpected secret-shaped report content")


def write_new(name, data):
    with (PACKET / name).open("xb") as output:
        output.write(data)


def main():
    reports = []
    for name in REPORTS:
        data = Path(f"/tmp/arkscope-responses-{name}.xml").read_bytes()
        tree = ET.fromstring(data)
        check_report(data, tree)
        counts = {key: sum(int(suite.get(key, 0)) for suite in tree.iter("testsuite"))
                  for key in ("tests", "failures", "errors", "skipped")}
        counts["passed"] = counts["tests"] - sum(counts[key] for key in ("failures", "errors", "skipped"))
        reports.append({
            "report": name, "sha256": digest(data), **counts,
            "failed_nodes": [case.get("classname", "") + "::" + case.get("name", "")
                             for case in tree.iter("testcase")
                             if any(child.tag in {"failure", "error"} for child in case)],
        })
        write_new(name + ".xml", data)
    write_new("results.json", (json.dumps(reports, indent=2) + "\n").encode())
    write_new("source-files.sha256", ("\n".join(
        digest((ROOT / name).read_bytes()) + "  " + name for name in SOURCES) + "\n").encode())
    rows = []
    for path in sorted(PACKET.iterdir()):
        if not path.is_file() or path.name == "artifact-files.sha256":
            continue
        data = path.read_bytes()
        if path.suffix != ".xml" and SECRET.search(data):
            raise ValueError("unexpected secret-shaped artifact content")
        rows.append(digest(data) + "  " + str(path.relative_to(ROOT)))
    write_new("artifact-files.sha256", ("\n".join(rows) + "\n").encode())
    print(json.dumps({"sealed_files": len(rows), "reports": len(reports)}))


if __name__ == "__main__":
    main()
