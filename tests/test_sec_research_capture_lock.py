"""The capture writer must never silently lose cross-process exclusion."""

import importlib.util

import pytest


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
