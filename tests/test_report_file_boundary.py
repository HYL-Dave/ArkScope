"""Untrusted tool arguments and stored paths cannot read outside reports."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.tools import report_tools as reports


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    directory = root / "data" / "reports"
    directory.mkdir(parents=True)
    outside = tmp_path / "private.md"
    outside.write_text("SYNTHETIC_PRIVATE_CANARY", encoding="utf-8")
    metadata = {}
    store = SimpleNamespace(get_report_metadata=lambda _: metadata)
    monkeypatch.setattr(reports, "get_app_records_store", lambda _: store)
    return SimpleNamespace(root=root, directory=directory, outside=outside,
                           dal=SimpleNamespace(_base=root), metadata=metadata)


@pytest.mark.parametrize("path", [
    "../private.md", "../../private.md", "data/reports/../../../private.md",
    "data/reports/../private.md", "config/.env", "data/reports/private.env",
    "data/reports/subdir/report.md", "data/reports/./report.md",
    "data//reports/report.md", "data/reports\\private.md", "data/reports/a\x00.md",
])
def test_rejects_noncanonical_report_paths(world, path):
    result = reports.get_report(world.dal, file_path=path)
    assert result.get("code") == "report_path_invalid"
    assert "content" not in result
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(result)


@pytest.mark.parametrize("via_metadata", [False, True])
def test_absolute_paths_are_not_report_authority(world, via_metadata):
    path = str(world.outside)
    world.metadata.update(file_path=path)
    result = reports.get_report(world.dal, **({"report_id": 1} if via_metadata else {"file_path": path}))
    assert result.get("code") == "report_path_invalid"
    assert str(world.outside) not in str(result)
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(result)


@pytest.mark.parametrize("link", ["symlink", "hardlink"])
def test_links_cannot_leak_through_detail_or_listing(world, link):
    name = "2026-09-19_TEST_link.md"
    if link == "symlink":
        (world.directory / name).symlink_to(world.outside)
    else:
        os.link(world.outside, world.directory / name)
    result = reports.get_report(world.dal, file_path=f"data/reports/{name}")
    assert result.get("code") == "report_path_unsafe"
    assert "content" not in result
    assert reports.list_reports(world.dal) == []


@pytest.mark.parametrize("component", ["data", "reports"])
def test_directory_links_are_rejected_for_reads_and_writes(world, component):
    outside_dir = world.outside.parent / "outside"
    outside_dir.mkdir()
    (outside_dir / "2026-09-19_TEST_file.md").write_text("SYNTHETIC_PRIVATE_CANARY")
    world.directory.rmdir()
    target = world.root / "data"
    if component == "data":
        target.rmdir()
        target.symlink_to(outside_dir, target_is_directory=True)
        (outside_dir / "reports").mkdir()
        (outside_dir / "reports" / "2026-09-19_TEST_file.md").write_text("SYNTHETIC_PRIVATE_CANARY")
    else:
        world.directory.symlink_to(outside_dir, target_is_directory=True)
    before = sorted(str(p.relative_to(outside_dir)) for p in outside_dir.rglob("*"))
    result = reports.get_report(world.dal, file_path="data/reports/2026-09-19_TEST_file.md")
    assert result.get("code") == "report_path_unsafe"
    assert reports.list_reports(world.dal) == []
    result = reports.save_report(world.dal, title="Test", tickers=["TEST"], report_type="test", summary="Summary", content="Report")
    assert result.get("code") == "report_path_unsafe"
    assert sorted(str(p.relative_to(outside_dir)) for p in outside_dir.rglob("*")) == before


def test_reads_do_not_create_missing_directories(world):
    world.directory.rmdir()
    (world.root / "data").rmdir()
    assert reports.get_report(world.dal, file_path="data/reports/missing.md").get("code") == "report_not_found"
    assert reports.list_reports(world.dal) == []
    assert not (world.root / "data").exists()


def test_original_markdown_roundtrip_and_database_path(world):
    saved = reports.save_report(world.dal, title="Original", tickers=["BRK.B"], report_type="test", summary="Summary", content="Original analysis")
    assert saved["file_path"].startswith("data/reports/")
    world.metadata.update(id=7, title="Original", file_path=saved["file_path"])
    result = reports.get_report(world.dal, report_id=7)
    assert result["id"] == 7
    assert "Original analysis" in result["content"]
    assert reports.get_report(world.dal, file_path=saved["file_path"])["content"] == result["content"]
    assert len(reports.list_reports(world.dal)) == 1


def test_generated_filename_never_inherits_path_syntax(world):
    saved = reports.save_report(world.dal, title="Original", tickers=["../../ESCAPE", "/ABS", "A\\B"],
                                report_type="test", summary="Summary", content="Original analysis")
    assert "error" not in saved
    assert len(Path(saved["file_path"]).parts) == 3
    assert "\\" not in saved["file_path"]
    assert len(list(world.directory.glob("*.md"))) == 1


def test_save_never_overwrites_existing_file_or_link(world, monkeypatch):
    leaf = world.directory / "existing.md"
    leaf.symlink_to(world.outside)
    monkeypatch.setattr(reports, "_generate_filename", lambda *_: leaf.name)
    result = reports.save_report(world.dal, title="Overwrite", tickers=["TEST"], report_type="test", summary="Summary", content="Modified")
    assert result.get("code") == "report_write_failed"
    assert world.outside.read_text() == "SYNTHETIC_PRIVATE_CANARY"


def test_opened_descriptor_prevents_leaf_swap_leak(world, monkeypatch):
    leaf = world.directory / "2026-09-19_TEST_race.md"
    leaf.write_text("Original report", encoding="utf-8")
    original_open = os.open

    def swapping_open(path, flags, *args, **kwargs):
        fd = original_open(path, flags, *args, **kwargs)
        if path == leaf.name:
            leaf.unlink()
            leaf.symlink_to(world.outside)
        return fd

    monkeypatch.setattr(reports.os, "open", swapping_open)
    result = reports.get_report(world.dal, file_path=f"data/reports/{leaf.name}")
    assert "SYNTHETIC_PRIVATE_CANARY" not in str(result)
    assert result.get("content") == "Original report" or result.get("code") == "report_path_unsafe"


def test_no_follow_directory_support_is_required(world, monkeypatch):
    monkeypatch.delattr(reports.os, "O_NOFOLLOW")
    result = reports.get_report(world.dal, file_path="data/reports/test.md")
    assert result.get("code") == "report_secure_io_unavailable"


def test_nonregular_file_rejection_does_not_wait_for_a_writer(world):
    import subprocess
    import sys

    leaf = world.directory / "2026-09-19_TEST_pipe.md"
    os.mkfifo(leaf)
    code = """
from types import SimpleNamespace
from pathlib import Path
from src.tools import report_tools as r
import sys
r.get_app_records_store = lambda _: object()
result = r.get_report(SimpleNamespace(_base=Path(sys.argv[1])), file_path='data/reports/2026-09-19_TEST_pipe.md')
assert result.get('code') == 'report_path_unsafe', result
"""
    result = subprocess.run([sys.executable, "-c", code, str(world.root)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
