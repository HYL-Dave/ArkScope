"""Disposable reproduction of interrupted publication versus stage-only recovery."""

import hashlib
import sqlite3

import pytest

from src.sec_research.capture_lock import CaptureDirectory
from tests.test_sec_research_maintenance import admin, preview


@pytest.mark.parametrize("crash", ["before_publish", "before_register"])
def test_interrupted_publication_can_reach_cleanup(admin, monkeypatch, crash):
    a = admin
    unrelated = a.captures.put(b"unrelated orphan")
    body = b"interrupted publication"
    sha = hashlib.sha256(body).hexdigest()

    def interrupted(*args):
        raise sqlite3.OperationalError("injected publication boundary failure")

    with monkeypatch.context() as patch:
        if crash == "before_publish":
            patch.setattr(CaptureDirectory, "publish", interrupted)
        else:
            patch.setattr(a.captures, "_register", interrupted)
        with pytest.raises(ValueError, match="^capture_store_write_failed$"):
            a.captures.put(body)

    target = a.paths.capture_root / "objects" / sha
    if crash == "before_register":
        assert target.stat().st_nlink == 2
    state = a.captures.recover()
    result = preview(a)
    assert state["charged_bytes"] == len(body) + len(b"unrelated orphan")
    assert result["status"] == "ready", result
    keys = {item["key"] for item in result["candidates"]}
    assert "objects/" + unrelated in keys
    if crash == "before_register":
        assert "objects/" + sha in keys
        assert target.stat().st_nlink == 1
