"""The capture writer must never silently lose cross-process exclusion."""

import importlib.util
import os
from contextlib import contextmanager

import pytest

from tests.test_sec_research_captures import captures, interrupted_publication


def test_capture_writer_implementation_exists():
    assert importlib.util.find_spec("src.sec_research.capture_lock") is not None


def writer():
    from src.sec_research.capture_lock import capture_writer
    return capture_writer


def test_capture_writer_excludes_a_second_owner(tmp_path):
    with writer()(tmp_path / "root"):
        with pytest.raises(ValueError, match="capture_store_busy"):
            with writer()(tmp_path / "root"):
                pytest.fail("a second owner entered")
    with writer()(tmp_path / "root"):
        pass


@pytest.mark.parametrize("leaf", ["root", "objects", "staging"])
def test_capture_writer_rejects_symlinks(tmp_path, leaf):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    outside.mkdir()
    if leaf == "root":
        root.symlink_to(outside, target_is_directory=True)
    else:
        root.mkdir()
        (root / leaf).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="capture_path_unsafe"):
        with writer()(root):
            pytest.fail("symlink admitted")
    assert list(outside.iterdir()) == []


def test_trusted_lock_namespace_rejects_symlink(tmp_path, monkeypatch):
    import src.sec_research.capture_lock as module
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "locks"
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(module, "lock_dir", lambda: link)
    with pytest.raises(ValueError, match="capture_path_unsafe"):
        with writer()(tmp_path / "root"):
            pytest.fail("symlink lock namespace admitted")
    assert list(outside.iterdir()) == []


def test_lease_creation_enospc_retains_capacity_code(tmp_path, monkeypatch):
    import errno
    import src.sec_research.capture_lock as module
    original = module.os.open
    def open_file(name, *args, **kwargs):
        if str(name).startswith("sec-research-"):
            raise OSError(errno.ENOSPC, "private detail")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(module.os, "open", open_file)
    monkeypatch.setattr(module, "_supported", lambda: True)
    with pytest.raises(ValueError, match="^storage_space_insufficient$"):
        with writer()(tmp_path / "root"):
            pytest.fail("disk-full lock created")


def test_unsupported_platform_never_runs_unlocked(tmp_path, monkeypatch):
    import src.sec_research.capture_lock as module
    monkeypatch.setattr(module, "_supported", lambda: False)
    with pytest.raises(ValueError, match="capture_platform_unsupported"):
        with writer()(tmp_path / "root"):
            pytest.fail("unlocked fallback")
    assert not (tmp_path / "root").exists()


def test_descriptor_writes_do_not_follow_replaced_root(tmp_path):
    root = tmp_path / "root"
    with writer()(root) as directory:
        root.rename(tmp_path / "detached")
        root.symlink_to(tmp_path / "elsewhere", target_is_directory=True)
        with pytest.raises(ValueError, match="capture_path_unsafe"):
            directory.assert_current()
    assert not (tmp_path / "elsewhere").exists()


def test_issuer_refresh_exclusion_does_not_hold_capture_writer(tmp_path):
    from src.sec_research.capture_lock import issuer_refresh
    root = tmp_path / "root"
    with issuer_refresh(root, "0000320193"):
        with pytest.raises(ValueError, match="sec_research_refresh_busy"):
            with issuer_refresh(root, "0000320193"):
                pytest.fail("same issuer entered")
        with issuer_refresh(root, "0000789019"):
            with writer()(root):
                pass


def test_capture_root_lock_replacement_cannot_admit_another_owner(tmp_path):
    from src.sec_research.capture_lock import issuer_refresh
    root = tmp_path / "root"
    with writer()(root):
        legacy = root / ".writer.lock"
        legacy.unlink(missing_ok=True)
        legacy.write_bytes(b"replaced")
        with pytest.raises(ValueError, match="capture_store_busy"):
            with writer()(root):
                pytest.fail("replacement bypassed writer")
    with issuer_refresh(root, "320193"):
        legacy = root / ".refresh-0000320193.lock"
        legacy.unlink(missing_ok=True)
        legacy.write_bytes(b"replaced")
        with pytest.raises(ValueError, match="sec_research_refresh_busy"):
            with issuer_refresh(root, "320193"):
                pytest.fail("replacement bypassed refresh")


@pytest.mark.parametrize("damage", ["foreign_link", "extra_stage", "extra_object",
    "malformed_stage", "malformed_object", "mismatched_body"])
def test_publication_recovery_rejects_unproven_alias_without_unlink(captures, monkeypatch, tmp_path, damage):
    _, target, stage = interrupted_publication(captures, monkeypatch)
    if damage == "foreign_link":
        os.link(target, tmp_path / "foreign")
    elif damage == "extra_stage":
        os.link(target, stage.parent / ("f" * 32))
    elif damage == "extra_object":
        os.link(target, target.parent / ("f" * 64))
    elif damage == "malformed_stage":
        stage = stage.rename(stage.with_name("a"))
    elif damage == "malformed_object":
        target = target.rename(target.with_name("b"))
    else:
        target.write_bytes(b"substituted")
    before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_nlink)
        for parent in (target.parent, stage.parent) for p in parent.iterdir()}
    with pytest.raises(ValueError, match="^capture_(path_unsafe|integrity_failed)$"):
        captures.recover()
    assert {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_nlink) for p in before} == before
    assert captures.status()["charged_bytes"] == 11
    with writer()(captures.store.paths.capture_root) as directory:
        with pytest.raises(ValueError, match="^capture_path_unsafe$"):
            directory.inventory()
    if damage == "foreign_link":
        assert (tmp_path / "foreign").read_bytes() == b"publication"


def test_publication_recovery_does_not_prune_separate_identical_stage(captures, monkeypatch):
    _, target, stage = interrupted_publication(captures, monkeypatch)
    stage.unlink()
    stage.write_bytes(b"publication")
    assert stage.stat().st_ino != target.stat().st_ino
    state = captures.recover()
    assert stage.read_bytes() == target.read_bytes() == b"publication"
    assert state["charged_bytes"] == state["orphan_bytes"] == 22


def test_publication_recovery_does_not_refresh_identity_to_accept_new_foreign_link(captures, monkeypatch, tmp_path):
    _, target, stage = interrupted_publication(captures, monkeypatch)
    open_file, fstat = os.open, os.fstat
    stage_fds, changed = set(), []
    foreign = tmp_path / "foreign"

    def open_stage(name, *args, **kwargs):
        fd = open_file(name, *args, **kwargs)
        if name == stage.name:
            stage_fds.add(fd)
        return fd

    def add_link_after_stat(fd):
        info = fstat(fd)
        if fd in stage_fds and not changed:
            os.link(target, foreign)
            changed.append(True)
        return info

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", open_stage)
        patch.setattr(os, "supports_dir_fd", os.supports_dir_fd | {open_stage})
        patch.setattr(os, "fstat", add_link_after_stat)
        with pytest.raises(ValueError, match="^capture_path_unsafe$"):
            captures.recover()
    assert changed == [True]
    assert stage.read_bytes() == target.read_bytes() == foreign.read_bytes() == b"publication"
    assert stage.stat().st_nlink == target.stat().st_nlink == foreign.stat().st_nlink == 3
    assert captures.status()["charged_bytes"] == 11


@pytest.mark.parametrize("replacement", ["regular", "symlink", "fifo"])
def test_publication_recovery_binds_unlink_to_accounted_entry(captures, monkeypatch, tmp_path, replacement):
    from src.sec_research.capture_lock import CaptureDirectory

    _, target, stage = interrupted_publication(captures, monkeypatch)
    files = CaptureDirectory.files
    retained = tmp_path / "retained-stage"

    def replace_after_scan(directory):
        result = files(directory)
        stage.rename(retained)
        if replacement == "regular":
            stage.write_bytes(b"unproven")
        elif replacement == "symlink":
            stage.symlink_to(retained)
        else:
            os.mkfifo(stage)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(CaptureDirectory, "files", replace_after_scan)
        with pytest.raises(ValueError, match="^capture_(path_unsafe|store_write_failed)$"):
            captures.recover()
    assert stage.lstat()
    assert retained.read_bytes() == target.read_bytes() == b"publication"
    assert captures.status()["charged_bytes"] == 11


@pytest.mark.parametrize("replacement", ["stage", "object", "root", "extra_link", "body"])
def test_publication_recovery_rechecks_identity_after_hash_before_unlink(captures, monkeypatch, tmp_path, replacement):
    _, target, stage = interrupted_publication(captures, monkeypatch)
    original_inode, fdopen = target.stat().st_ino, os.fdopen
    moved = tmp_path / "detached"
    changed = []

    @contextmanager
    def replace_after_read(fd, *args, **kwargs):
        is_object = os.fstat(fd).st_ino == original_inode
        with fdopen(fd, *args, **kwargs) as handle:
            yield handle
            if is_object and not changed:
                changed.append(replacement)
                if replacement in {"stage", "object"}:
                    path = stage if replacement == "stage" else target
                    path.rename(moved)
                    path.write_bytes(b"unproven replacement")
                elif replacement == "root":
                    root = captures.store.paths.capture_root
                    root.rename(moved)
                    root.mkdir()
                    (root / "objects").mkdir()
                    (root / "staging").mkdir()
                elif replacement == "extra_link":
                    os.link(target, moved)
                else:
                    target.write_bytes(b"substituted")

    with monkeypatch.context() as patch:
        patch.setattr(os, "fdopen", replace_after_read)
        with pytest.raises(ValueError, match="^capture_path_unsafe$"):
            captures.recover()
    assert changed == [replacement]
    if replacement == "root":
        assert (moved / "staging" / stage.name).read_bytes() == b"publication"
        assert (moved / "objects" / target.name).read_bytes() == b"publication"
    elif replacement == "stage":
        assert stage.read_bytes() == b"unproven replacement"
        assert target.read_bytes() == moved.read_bytes() == b"publication"
    elif replacement == "object":
        assert target.read_bytes() == b"unproven replacement"
        assert stage.read_bytes() == moved.read_bytes() == b"publication"
    else:
        assert stage.read_bytes() == target.read_bytes() == (
            b"substituted" if replacement == "body" else b"publication")
    assert captures.status()["charged_bytes"] == 11
