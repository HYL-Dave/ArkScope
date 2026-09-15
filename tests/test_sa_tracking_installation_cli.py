"""Exercise the current operator entrypoint, not a test-only installation caller."""

import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tests.current_installation_fixtures import seeded_current_profile
from tests.test_sa_tracking_installation import capture, retained_state


ROOT = Path(__file__).resolve().parents[1]


def invoke(*args):
    return subprocess.run(
        [sys.executable, "-B", "-m", "src.sa_tracking_installation", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


def receipt(*args):
    result = invoke(*args)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "current membership CLI did not return a receipt"
    return json.loads(result.stdout)


def test_current_module_cli_inspects_previews_installs_and_noops_populated_v4(tmp_path):
    profile, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    retained = retained_state(profile)
    original = profile.read_bytes()
    inspection_path = tmp_path / "inspection.json"
    inspected = receipt("inspect", "--profile", profile, "--output", inspection_path)
    assert inspected["schema_version"] == "v4" and not inspected["membership_installed"]
    assert json.loads(inspection_path.read_text()) == inspected
    preview_path = tmp_path / "preview.json"
    preview = receipt("install-preview", "--profile", profile, "--sa", sa, "--output", preview_path)
    assert json.loads(preview_path.read_text()) == preview
    assert preview["profile"] == inspected
    assert preview["lineage_count"] == 3 and preview["dual_source_count"] == 1
    assert profile.read_bytes() == original
    installed = receipt("install", "--profile", profile, "--sa", sa, "--backup", tmp_path / "backup.db",
        "--cutover-sha256", preview["cutover_sha256"], "--app-stopped")
    assert installed["changed"] and installed["membership_installed"]
    assert installed["actor"] == "attended_user" and len(installed["memberships"]) == 4
    assert retained_state(profile) == retained == retained_state(tmp_path / "backup.db")
    current = receipt("install-preview", "--profile", profile, "--sa", sa, "--output", tmp_path / "current.json")
    no_op = receipt("install", "--profile", profile, "--sa", sa, "--backup", tmp_path / "unused.db",
        "--cutover-sha256", current["cutover_sha256"], "--app-stopped")
    assert no_op["changed"] is False and no_op["memberships"] == installed["memberships"]
    assert not (tmp_path / "unused.db").exists()


@pytest.mark.parametrize("args", (
    (),
    ("inspect",),
    ("install-preview", "--profile", "absent", "--output", "manifest"),
    ("install", "--profile", "absent", "--sa", "absent-sa", "--backup", "backup", "--cutover-sha256", "a" * 64),
    ("install", "--profile", "absent", "--sa", "absent-sa", "--app-stopped"),
))
def test_current_module_cli_requires_paths_digest_backup_and_stopped_app(args):
    result = invoke(*args)
    assert result.returncode == 2
    assert "required" in result.stderr


def test_current_module_cli_refuses_overwriting_preview_before_reading_stores(tmp_path):
    output = tmp_path / "preview.json"
    output.write_text("retained-approval")
    result = invoke("install-preview", "--profile", tmp_path / "absent.db",
        "--sa", tmp_path / "absent-sa.db", "--output", output)
    assert result.returncode != 0 and "FileExistsError" in result.stderr
    assert output.read_text() == "retained-approval"
    assert list(tmp_path.iterdir()) == [output]


def test_current_module_cli_rejects_observation_drift_before_backup(tmp_path):
    profile, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    preview = receipt("install-preview", "--profile", profile, "--sa", sa, "--output", tmp_path / "preview.json")
    with sqlite3.connect(sa) as conn:
        conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-05T02:00:00Z'")
    original = profile.read_bytes()
    result = invoke("install", "--profile", profile, "--sa", sa, "--backup", tmp_path / "backup.db",
        "--cutover-sha256", preview["cutover_sha256"], "--app-stopped")
    assert result.returncode != 0 and "provider_cutover_preview_changed" in result.stderr
    assert not (tmp_path / "backup.db").exists()
    assert profile.read_bytes() == original


def test_current_module_cli_does_not_overwrite_a_backup(tmp_path):
    profile, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    preview = receipt("install-preview", "--profile", profile, "--sa", sa, "--output", tmp_path / "preview.json")
    backup = tmp_path / "backup.db"
    backup.write_bytes(b"retained-backup")
    original = profile.read_bytes()
    result = invoke("install", "--profile", profile, "--sa", sa, "--backup", backup,
        "--cutover-sha256", preview["cutover_sha256"], "--app-stopped")
    assert result.returncode != 0 and "FileExistsError" in result.stderr
    assert backup.read_bytes() == b"retained-backup"
    assert profile.read_bytes() == original


def test_current_module_cli_has_discoverable_install_options():
    result = invoke("install", "--help")
    assert result.returncode == 0
    for flag in ("--profile", "--sa", "--backup", "--cutover-sha256", "--app-stopped"):
        assert flag in result.stdout


@pytest.mark.parametrize("command", ("inspect", "install-preview"))
@pytest.mark.parametrize("malformed", (False, True))
def test_failed_profile_preview_leaves_no_artifact_and_can_retry(tmp_path, command, malformed):
    profile = tmp_path / "profile.db"
    output = tmp_path / "preview.json"
    sa = capture(tmp_path)
    if malformed:
        profile.write_bytes(b"not a database")
    args = [command, "--profile", profile, "--output", output]
    if command == "install-preview":
        args += ["--sa", sa]
    result = invoke(*args)
    assert result.returncode != 0
    assert not output.exists()
    assert profile.exists() is malformed
    if malformed:
        assert profile.read_bytes() == b"not a database"
        profile.unlink()
    seeded_current_profile(tmp_path)
    value = receipt(*args)
    assert json.loads(output.read_text()) == value


@pytest.mark.parametrize("malformed", (False, True))
def test_failed_sa_preview_leaves_no_artifact_and_can_retry(tmp_path, malformed):
    profile = seeded_current_profile(tmp_path)
    sa, output = tmp_path / "sa.db", tmp_path / "preview.json"
    if malformed:
        sa.write_bytes(b"not a capture database")
    args = ["install-preview", "--profile", profile, "--sa", sa, "--output", output]
    result = invoke(*args)
    assert result.returncode != 0
    assert not output.exists()
    assert sa.exists() is malformed
    if malformed:
        assert sa.read_bytes() == b"not a capture database"
        sa.unlink()
    capture(tmp_path)
    assert receipt(*args)["lineage_count"] == 3


@pytest.mark.parametrize("command,aliased", (("inspect", "profile"),
    ("install-preview", "profile"), ("install-preview", "sa")))
@pytest.mark.parametrize("symlink", (False, True))
def test_preview_refuses_input_output_alias_without_creating_input(tmp_path, command, aliased, symlink):
    paths = {name: tmp_path / f"{name}.db" for name in ("profile", "sa")}
    output = paths[aliased]
    if symlink:
        output = tmp_path / "output.json"
        output.symlink_to(paths[aliased])
    args = [command, "--profile", paths["profile"], "--output", output]
    if command == "install-preview":
        args += ["--sa", paths["sa"]]
    result = invoke(*args)
    assert result.returncode != 0 and "installation_output_alias" in result.stderr
    assert not paths["profile"].exists() and not paths["sa"].exists()
    if symlink:
        assert output.is_symlink()


@pytest.mark.parametrize("replaced", (False, True))
def test_preview_write_failure_removes_only_its_own_partial_file(tmp_path, monkeypatch, replaced):
    from src import sa_tracking_installation as installation

    profile = seeded_current_profile(tmp_path)
    output = tmp_path / "preview.json"
    original_open = Path.open

    @contextmanager
    def failing_output(path, *args, **kwargs):
        with original_open(path, *args, **kwargs) as handle:
            if path != output or args != ("x",):
                yield handle
                return

            class InterruptedWrite:
                def fileno(self):
                    return handle.fileno()

                def write(self, value):
                    handle.write(value[:5])
                    if replaced:
                        output.unlink()
                        with original_open(output, "x") as replacement:
                            replacement.write("unrelated replacement")
                    raise OSError("interrupted preview write")

            yield InterruptedWrite()

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_output)
        with pytest.raises(OSError, match="interrupted preview write"):
            installation.main(["inspect", "--profile", str(profile), "--output", str(output)])
    if replaced:
        assert output.read_text() == "unrelated replacement"
    else:
        assert not output.exists()
        assert receipt("inspect", "--profile", profile, "--output", output)["schema_version"] == "v4"
