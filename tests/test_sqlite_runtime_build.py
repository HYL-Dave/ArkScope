"""Offline preparation must never overwrite an existing generation."""

from pathlib import Path
import sys

import pytest


def test_missing_or_unverified_archive_never_creates_package(tmp_path):
    from src.sqlite_runtime.build import build_package
    from src.sqlite_runtime.contract import RuntimeAdmissionError
    archive = tmp_path / "source.tar.gz"
    archive.write_bytes(b"not the pinned archive")
    destination = tmp_path / "runtime"
    with pytest.raises(RuntimeAdmissionError, match="sqlite_runtime_source_mismatch"):
        build_package(archive, destination, Path(sys.executable))
    assert not destination.exists()


def test_existing_destination_is_never_reused(tmp_path):
    from src.sqlite_runtime.build import build_package
    destination = tmp_path / "runtime"
    destination.mkdir()
    marker = destination / "keep"
    marker.write_bytes(b"existing generation")
    with pytest.raises(FileExistsError):
        build_package(tmp_path / "missing", destination, Path(sys.executable))
    assert marker.read_bytes() == b"existing generation"


def test_build_recipe_retains_critical_baseline_limits():
    from src.sqlite_runtime.build import DEFINES
    assert {"SQLITE_MAX_VARIABLE_NUMBER=250000", "SQLITE_THREADSAFE=1",
            "SQLITE_SECURE_DELETE", "SQLITE_LIKE_DOESNT_MATCH_BLOBS",
            "SQLITE_ENABLE_FTS5", "SQLITE_ENABLE_RTREE", "SQLITE_ENABLE_SESSION",
            "SQLITE_ENABLE_PREUPDATE_HOOK", "SQLITE_USE_URI"} <= set(DEFINES)
