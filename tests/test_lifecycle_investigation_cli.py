import json
import sqlite3

import pytest

from src.lifecycle_investigation.__main__ import main
from tests.test_security_lifecycle_population import stores, sec, persist


def test_explicit_install_and_36_row_two_stage_disposal_can_resume_without_touching_collectors(tmp_path, capsys):
    market, profile = stores(tmp_path)
    for index in range(36):
        persist(profile, sec(market, ticker=f"T{index}", ref=f"legacy-{index}"))
    install_manifest = tmp_path / "installation.json"
    before = profile.read_bytes()
    preview = main(["install-preview", "--profile", str(profile), "--output", str(install_manifest)])
    assert profile.read_bytes() == before
    assert json.loads(install_manifest.read_text()) == preview
    with pytest.raises(FileExistsError):
        main(["install-preview", "--profile", str(profile), "--output", str(install_manifest)])
    installed = main(["install", "--profile", str(profile), "--approval-sha256", preview["approval_sha256"],
        "--backup", str(tmp_path / "before-install.db"), "--app-stopped"])
    assert installed["changed"]
    disposal = tmp_path / "disposal.json"
    plan = main(["disposal-preview", "--profile", str(profile), "--market", str(market), "--output", str(disposal)])
    assert plan["counts"] == {"cases": 36, "observations": 36, "discard_cases": 36, "retained_cases": 0,
        "discard_observations": 36, "case_only": 0, "observation_only": 0}
    arguments = ["disposal-stage", "--profile", str(profile), "--market", str(market), "--manifest", str(disposal),
        "--approval-sha256", plan["approval_sha256"], "--app-stopped"]
    first = main([*arguments, "--stage", "profile", "--backup", str(tmp_path / "profile-backup.db")])
    assert first["counts"]["security_lifecycle_cases"] == 36
    # Unrelated collector activity between stages does not invalidate a selected-row receipt.
    with sqlite3.connect(market) as conn:
        conn.execute("CREATE TABLE unrelated_collector(value TEXT)")
        conn.execute("INSERT INTO unrelated_collector VALUES ('new public article')")
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_observations").fetchone()[0] == 36
    assert main([*arguments, "--stage", "profile", "--backup", str(tmp_path / "unused.db")])["status"] == "already_completed"
    final = main([*arguments, "--stage", "market", "--backup", str(tmp_path / "market-backup.db")])
    assert final["counts"]["observations"] == 36
    with sqlite3.connect(market) as conn:
        assert conn.execute("SELECT * FROM unrelated_collector").fetchall() == [("new public article",)]
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_observations").fetchone()[0] == 0
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    assert "approval_sha256" in capsys.readouterr().out


def test_operator_cli_never_guesses_database_paths_or_app_stop_permission():
    with pytest.raises(SystemExit):
        main(["install-preview", "--output", "unused"])
    with pytest.raises(SystemExit):
        main(["install", "--profile", "unused", "--backup", "unused-backup", "--approval-sha256", "a" * 64])


@pytest.mark.parametrize("command,aliased", (("install-preview", "profile"),
    ("disposal-preview", "profile"), ("disposal-preview", "market")))
def test_operator_preview_rejects_input_output_alias_before_creating_it(tmp_path, command, aliased):
    profile, market = tmp_path / "profile.db", tmp_path / "market.db"
    output = profile if aliased == "profile" else market
    args = [command, "--profile", str(profile), "--output", str(output)]
    if command == "disposal-preview":
        args += ["--market", str(market)]
    with pytest.raises(ValueError, match="installation_output_alias"):
        main(args)
    assert not profile.exists() and not market.exists()


@pytest.mark.parametrize("command", ("install-preview", "disposal-preview"))
def test_operator_failed_preview_leaves_no_artifact_and_preserves_prior_outputs(tmp_path, command):
    output = tmp_path / "preview.json"
    args = [command, "--profile", str(tmp_path / "absent-profile.db"), "--output", str(output)]
    if command == "disposal-preview":
        args += ["--market", str(tmp_path / "absent-market.db")]
    with pytest.raises((OSError, ValueError, sqlite3.Error, RuntimeError)):
        main(args)
    assert not output.exists()
    output.write_text("retained approval")
    with pytest.raises(FileExistsError):
        main(args)
    assert output.read_text() == "retained approval"
