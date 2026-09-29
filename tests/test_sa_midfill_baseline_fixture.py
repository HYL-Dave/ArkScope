"""Frozen upgrade inputs must survive shallow clones and history replacement."""

import hashlib
import json
from types import SimpleNamespace
import warnings
import zipfile

import pytest

from tests import sa_midfill_fixture as fixture
from tests.sa_midfill_browser_fixture import package


ORIGIN = "b24a2c1dfac740fde8e4b491684b7ff9b58a6b7e"
COLLECTOR = "src/sa/company_collector.py"
SOURCE = b"class CompanyCollector:\n    pass\n"


def refuse_historical_reads(monkeypatch):
    original = fixture.subprocess.check_output

    def checked(command, *args, **kwargs):
        if command[0] == "git" and any(x in command for x in ("show", "ls-tree")):
            raise AssertionError("Historical Git objects are unavailable")
        return original(command, *args, **kwargs)

    monkeypatch.setattr(fixture.subprocess, "check_output", checked)


def make_bundle(tmp_path, monkeypatch, *, content=SOURCE, entries=None, metadata=None):
    record = {
        "path": COLLECTOR,
        "bytes": len(SOURCE),
        "sha256": hashlib.sha256(SOURCE).hexdigest(),
        "blob_id": hashlib.sha1(b"blob " + str(len(SOURCE)).encode() + b"\0" + SOURCE).hexdigest(),
    }
    record.update(metadata or {})
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "origin_commit": ORIGIN, "files": [record],
    }))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(tmp_path / "baseline.zip", "w") as archive:
            for path, data in entries if entries is not None else [(COLLECTOR, content)]:
                archive.writestr(path, data)
    monkeypatch.setattr(fixture, "_BASELINE_DIR", tmp_path, raising=False)
    refuse_historical_reads(monkeypatch)


def test_baseline_collector_is_executable_without_historical_git(monkeypatch):
    refuse_historical_reads(monkeypatch)
    namespace = {"__name__": "tests._frozen_collector", "__file__": str(fixture.ROOT / COLLECTOR)}
    exec(compile(fixture.baseline_source(COLLECTOR), COLLECTOR, "exec"), namespace)
    assert callable(namespace["CompanyCollector"])


@pytest.mark.parametrize("browser", ["chrome", "firefox"])
def test_installed_baseline_package_does_not_enumerate_old_tree(tmp_path, monkeypatch, browser):
    refuse_historical_reads(monkeypatch)
    rig = SimpleNamespace(root=tmp_path, url="http://127.0.0.1:9", client={}, now=0)
    folder = package(rig, browser, "baseline")
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
    assert "nativeMessaging" not in manifest["permissions"]
    assert (folder / "company_refresh.js").read_text() == fixture.baseline_source(
        "extensions/sa_alpha_picks/company_refresh.js"
    )


def test_bundle_returns_verified_bytes(tmp_path, monkeypatch):
    make_bundle(tmp_path, monkeypatch)
    assert fixture.baseline_source(COLLECTOR) == SOURCE.decode()


@pytest.mark.parametrize("path", ["config/.env", "../src/sa/company_collector.py", "/etc/passwd"])
def test_unknown_paths_are_not_read(tmp_path, monkeypatch, path):
    make_bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="baseline"):
        fixture.baseline_source(path)


@pytest.mark.parametrize("change", ["bytes", "sha256", "blob_id"])
def test_incorrect_manifest_metadata_is_rejected(tmp_path, monkeypatch, change):
    value = 1 if change == "bytes" else "0" * (40 if change == "blob_id" else 64)
    make_bundle(tmp_path, monkeypatch, metadata={change: value})
    with pytest.raises(ValueError, match="baseline"):
        fixture.baseline_source(COLLECTOR)


@pytest.mark.parametrize("entries", [[], [(COLLECTOR, SOURCE), (COLLECTOR, SOURCE)],
    [(COLLECTOR, SOURCE), ("../escape.py", SOURCE)]])
def test_missing_duplicate_or_extra_archive_entries_are_rejected(tmp_path, monkeypatch, entries):
    make_bundle(tmp_path, monkeypatch, entries=entries)
    with pytest.raises(ValueError, match="baseline"):
        fixture.baseline_source(COLLECTOR)


def test_changed_archive_content_is_rejected(tmp_path, monkeypatch):
    make_bundle(tmp_path, monkeypatch, content=SOURCE.replace(b"pass", b"None"))
    with pytest.raises(ValueError, match="baseline"):
        fixture.baseline_source(COLLECTOR)
