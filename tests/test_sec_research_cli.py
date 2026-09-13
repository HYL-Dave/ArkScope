"""Operator CLI admission before configured databases are opened."""

import json
import hashlib

import pytest

from src.sec_research.paths import SecResearchPaths
from tests.test_sec_research_maintenance import admin


def cli():
    from src.sec_research import __main__ as module
    assert hasattr(module, "open_profile_readonly"), "missing explicit maintenance CLI"
    return module


@pytest.mark.parametrize("operation", ["cleanup", "schema"])
def test_cli_explicit_preview_approval_and_receipt(admin, monkeypatch, capsys, operation):
    a = admin
    module = cli()
    a.captures.put(b"operator fixture")
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: a.paths))
    monkeypatch.setattr(module, "_profile_path", lambda: a.profile_path)
    path, receipt = a.tmp / "preview.json", a.tmp / "receipt.json"
    args = [operation + "-preview", "--preview", str(path)]
    if operation == "schema":
        args += ["--mode", "reset"]
    assert module.main(args) == 0
    p = json.loads(path.read_text())
    assert p["status"] == "ready" and p["version"] == 1
    assert not receipt.exists()
    args = [operation + "-apply", "--preview", str(path), "--approval-sha256", p["approval_sha256"],
            "--receipt", str(receipt)]
    if operation == "schema":
        args += ["--backup", str(a.tmp / "backup")]
    assert module.main(args) == 0
    result = json.loads(receipt.read_text())
    assert result["status"] == "ok" and result["phase"] == "complete"
    output = capsys.readouterr().out
    assert "operator fixture" not in output and str(a.profile_path) not in output


@pytest.mark.parametrize("args", [
    ["cleanup-apply", "--preview", "absent.json", "--approval-sha256", "bad", "--receipt", "receipt.json"],
    ["schema-apply", "--preview", "absent.json", "--approval-sha256", "0" * 64,
     "--receipt", "receipt.json", "--backup", "../bad"],
    ["cleanup-preview", "--preview", "../bad"],
])
def test_cli_invalid_requests_never_resolve_or_open_databases(monkeypatch, args):
    module = cli()
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: pytest.fail("resolved DB before validation")))
    monkeypatch.setattr(module, "_profile_path", lambda: pytest.fail("resolved profile before validation"))
    assert module.main(args) == 1


def test_cli_missing_profile_never_initializes(admin, monkeypatch):
    a = admin
    module = cli()
    path = a.tmp / "missing-profile.db"
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: a.paths))
    monkeypatch.setattr(module, "_profile_path", lambda: path)
    assert module.main(["cleanup-preview", "--preview", str(a.tmp / "preview.json")]) == 1
    assert not path.exists()


def test_cli_unknown_schema_requires_disclosed_digest_approval(admin, monkeypatch, capsys):
    a, module = admin, cli()
    with a.store.connect() as conn:
        conn.execute("CREATE TABLE sec_research_unknown(value TEXT)")
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: a.paths))
    monkeypatch.setattr(module, "_profile_path", lambda: a.profile_path)
    path, receipt, backup = a.tmp / "preview.json", a.tmp / "receipt.json", a.tmp / "backup"
    assert module.main(["schema-preview", "--mode", "uninstall", "--preview", str(path)]) == 1
    p = json.loads(path.read_text())
    summary = json.loads(capsys.readouterr().out)
    assert p.get("apply_effect") == summary.get("apply_effect") == "raw_backup_only"
    assert not backup.exists() and not receipt.exists()
    assert module.main(["schema-apply", "--preview", str(path), "--approval-sha256", p["approval_sha256"],
                        "--receipt", str(receipt), "--backup", str(backup)]) == 1
    result = json.loads(receipt.read_text())
    assert result["phase"] == "backed_up" and result["status"] == "blocked"
    assert result["recovery"] == "inspect_raw_backup"


@pytest.mark.parametrize("command", [None, "cleanup-preview", "cleanup-apply", "schema-preview", "schema-apply"])
def test_cli_help_does_not_resolve_stores(monkeypatch, capsys, command):
    module = cli()
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: pytest.fail("help resolved DB")))
    monkeypatch.setattr(module, "_profile_path", lambda: pytest.fail("help resolved profile"))
    with pytest.raises(SystemExit) as caught:
        module.main(([command] if command else []) + ["--help"])
    assert caught.value.code == 0
    output = capsys.readouterr().out
    assert "usage:" in output
    if command:
        assert "--preview" in output
    print(output)


@pytest.mark.parametrize("change", ["candidate", "reference_count", "object", "status"])
def test_cli_rejects_nonclosed_preview_before_resolving_database(admin, monkeypatch, change):
    from tests.test_sec_research_maintenance import preview

    a = admin
    module = cli()
    a.captures.put(b"fixture")
    p = preview(a)
    if change == "candidate":
        p["candidates"][0]["recursive"] = True
    elif change == "reference_count":
        p["references"]["unknown"] = 0
    elif change == "object":
        p["owned_objects"][0]["sql"] = "unknown SQL"
    else:
        p["status"] = "confirmed"
    p["approval_sha256"] = hashlib.sha256(json.dumps(
        {k: v for k, v in p.items() if k != "approval_sha256"},
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    path = a.tmp / "preview.json"
    path.write_text(json.dumps(p))
    monkeypatch.setattr(SecResearchPaths, "resolve", classmethod(lambda cls: pytest.fail("resolved nonclosed approval")))
    assert module.main(["cleanup-apply", "--preview", str(path), "--approval-sha256", p["approval_sha256"],
                        "--receipt", str(a.tmp / "receipt.json")]) == 1
