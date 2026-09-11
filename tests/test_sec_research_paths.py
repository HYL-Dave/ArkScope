"""SEC capture-root authority and portable object-key contracts."""

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_sec_paths_owner_exists():
    assert (ROOT / "src" / "sec_research" / "paths.py").is_file()


def _paths_type():
    assert (ROOT / "src" / "sec_research" / "paths.py").is_file()
    from src.sec_research.paths import SecResearchPaths

    return SecResearchPaths


def test_capture_root_keeps_the_resolved_database_filename_without_creating_files(tmp_path):
    paths = _paths_type().from_market_db(tmp_path / "uncreated" / "market.snapshot.db")
    assert paths.market_db_path == tmp_path / "uncreated" / "market.snapshot.db"
    assert paths.capture_root == tmp_path / "uncreated" / "market.snapshot.db.sec-research"
    assert paths.object_path("objects/body.txt") == (
        tmp_path / "uncreated" / "market.snapshot.db.sec-research" / "objects" / "body.txt"
    )
    assert list(tmp_path.iterdir()) == []


def test_two_market_databases_in_one_directory_have_distinct_capture_roots(tmp_path):
    paths_type = _paths_type()
    first = paths_type.from_market_db(tmp_path / "first.db")
    second = paths_type.from_market_db(tmp_path / "second.db")
    assert first.object_path("body") == tmp_path / "first.db.sec-research" / "body"
    assert second.object_path("body") == tmp_path / "second.db.sec-research" / "body"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("factory", ["from_market_db", "constructor"])
def test_relative_market_binding_survives_cwd_changes(tmp_path, monkeypatch, factory):
    paths_type = _paths_type()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(tmp_path)
    if factory == "from_market_db":
        paths = paths_type.from_market_db("data/../data/market.db")
    else:
        paths = paths_type(market_db_path=Path("data/../data/market.db"))
    monkeypatch.chdir(elsewhere)
    assert paths.market_db_path == tmp_path / "data" / "market.db"
    assert paths.object_path("body") == tmp_path / "data" / "market.db.sec-research" / "body"
    assert not (tmp_path / "data").exists()


def test_market_binding_cannot_be_reassigned(tmp_path):
    from dataclasses import FrozenInstanceError

    paths = _paths_type().from_market_db(tmp_path / "market.db")
    with pytest.raises(FrozenInstanceError):
        paths.market_db_path = tmp_path / "other.db"
    assert paths.object_path("body") == tmp_path / "market.db.sec-research" / "body"


def test_resolve_uses_market_environment_authority(tmp_path, monkeypatch):
    paths_type = _paths_type()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", "custom/../custom/prices.sqlite")
    paths = paths_type.resolve()
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "other.db"))
    assert paths.market_db_path == tmp_path / "custom" / "prices.sqlite"
    assert paths.object_path("body") == tmp_path / "custom" / "prices.sqlite.sec-research" / "body"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("env_value", [None, ""], ids=["absent", "empty"])
def test_resolve_uses_existing_default_authority(tmp_path, monkeypatch, env_value):
    paths_type = _paths_type()
    from src import market_data_admin

    if env_value is None:
        monkeypatch.delenv("ARKSCOPE_MARKET_DB", raising=False)
    else:
        monkeypatch.setenv("ARKSCOPE_MARKET_DB", env_value)
    monkeypatch.setattr(market_data_admin, "_PROJECT_ROOT", tmp_path / "application")
    paths = paths_type.resolve()
    assert paths.market_db_path == tmp_path / "application" / "data" / "market_data.db"
    assert paths.capture_root == (
        tmp_path / "application" / "data" / "market_data.db.sec-research"
    )
    assert list(tmp_path.iterdir()) == []


def test_resolve_delegates_to_existing_market_path_resolver(tmp_path, monkeypatch):
    paths_type = _paths_type()
    from src import market_data_admin

    monkeypatch.setattr(
        market_data_admin, "resolve_market_db_path", lambda: str(tmp_path / "authority.db")
    )
    paths = paths_type.resolve()
    assert paths.object_path("body") == tmp_path / "authority.db.sec-research" / "body"
    assert list(tmp_path.iterdir()) == []


def test_market_database_symlink_binds_the_target_store(tmp_path):
    paths_type = _paths_type()
    target = tmp_path / "real" / "market.db"
    target.parent.mkdir()
    target.write_bytes(b"path-only fixture, never opened as SQLite")
    alias = tmp_path / "alias.db"
    alias.symlink_to(target)
    paths = paths_type.from_market_db(alias)
    assert paths.market_db_path == target
    assert paths.object_path("body") == tmp_path / "real" / "market.db.sec-research" / "body"
    assert not paths.capture_root.exists()


def test_relative_object_key_reopens_the_capture_after_relocation(tmp_path):
    paths_type = _paths_type()
    original = tmp_path / "original"
    original.mkdir()
    market = original / "market.db"
    market.write_bytes(b"path-only database fixture")
    root = original / "market.db.sec-research"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "abc.txt").write_bytes(b"retained capture")
    old_paths = paths_type.from_market_db(market)
    key = "objects/abc.txt"
    assert old_paths.object_path(key).read_bytes() == b"retained capture"

    moved = tmp_path / "relocated"
    original.rename(moved)
    new_paths = paths_type.from_market_db(moved / "market.db")
    assert new_paths.object_path(key) == moved / "market.db.sec-research" / "objects" / "abc.txt"
    assert new_paths.object_path(key).read_bytes() == b"retained capture"
    assert not old_paths.object_path(key).exists()


@pytest.mark.parametrize(
    "key",
    [
        "objects/sha256/ab/abcdef0123.html",
        "text/canonical-1_utf8.txt",
        "objects/a..b",
        "objects/%2e%2e.txt",
        "objects/\u6587\u672c.txt",
    ],
    ids=["nested-hash", "canonical-text", "embedded-dots", "literal-percent", "unicode-name"],
)
def test_safe_relative_object_keys_are_resolved_without_writes(tmp_path, key):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    assert paths.object_path(key) == tmp_path / "market.db.sec-research" / key
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("", id="empty"),
        pytest.param(".", id="dot"),
        pytest.param("..", id="parent"),
        pytest.param("../escape", id="parent-prefix"),
        pytest.param("objects/../../escape", id="nested-traversal"),
        pytest.param("objects/../body", id="contained-traversal"),
        pytest.param("./body", id="dot-prefix"),
        pytest.param("objects/./body", id="dot-component"),
        pytest.param("objects//body", id="empty-component"),
        pytest.param("objects/body/", id="trailing-separator"),
        pytest.param("/outside/body", id="posix-absolute"),
        pytest.param("//server/share/body", id="forward-unc"),
        pytest.param("C:/outside/body", id="windows-forward-drive"),
        pytest.param(r"C:\outside\body", id="windows-drive"),
        pytest.param("C:body", id="windows-drive-relative"),
        pytest.param("C:", id="windows-drive-only"),
        pytest.param(r"\outside", id="windows-rooted"),
        pytest.param(r"\\server\share\body", id="windows-unc"),
        pytest.param(r"\\?\C:\outside", id="windows-extended-drive"),
        pytest.param(r"\\?\UNC\server\share\body", id="windows-extended-unc"),
        pytest.param(r"\\.\device", id="windows-device-path"),
        pytest.param(r"objects\..\escape", id="windows-traversal"),
        pytest.param(r"objects\body", id="windows-separator"),
        pytest.param("objects/C:body", id="nested-drive-or-stream"),
        pytest.param("objects/body:stream", id="alternate-stream"),
        pytest.param("objects/body\x00", id="nul"),
        pytest.param("objects/body\n", id="newline"),
        pytest.param("objects/\x1fbody", id="control-character"),
        pytest.param("objects/body\x7f", id="delete-character"),
        pytest.param("objects/body.", id="trailing-dot"),
        pytest.param("objects/body ", id="trailing-space"),
        pytest.param("objects/CON", id="reserved-device"),
        pytest.param("objects/nul.txt", id="reserved-device-extension"),
        pytest.param("AUX/body", id="reserved-directory"),
        pytest.param("objects/COM1", id="reserved-port"),
        pytest.param("objects/a?b", id="question-mark"),
        pytest.param("objects/a*b", id="asterisk"),
        pytest.param("objects/a<b", id="left-angle"),
        pytest.param("objects/a>b", id="right-angle"),
        pytest.param('objects/a"b', id="double-quote"),
        pytest.param("objects/a|b", id="pipe"),
        pytest.param(None, id="null"),
        pytest.param(1, id="integer"),
        pytest.param(b"objects/body", id="bytes"),
        pytest.param(Path("objects/body"), id="path-object"),
    ],
)
def test_object_path_rejects_unsafe_or_malformed_keys(tmp_path, key):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    with pytest.raises(ValueError):
        paths.object_path(key)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "kind", ["directory", "file", "dangling", "chain", "prefix-sibling", "capture-root"]
)
def test_object_path_rejects_symlink_escape(tmp_path, kind):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    root = tmp_path / "market.db.sec-research"
    outside = tmp_path / ("market.db.sec-research-other" if kind == "prefix-sibling" else "outside")
    outside.mkdir()
    (outside / "body").write_bytes(b"outside sentinel")
    if kind == "capture-root":
        root.symlink_to(outside, target_is_directory=True)
        key = "body"
    else:
        root.mkdir()
        if kind == "file":
            (root / "link").symlink_to(outside / "body")
            key = "link"
        elif kind == "dangling":
            (root / "link").symlink_to(outside / "missing", target_is_directory=True)
            key = "link/body"
        elif kind == "chain":
            (root / "link").symlink_to(root / "second", target_is_directory=True)
            (root / "second").symlink_to(outside, target_is_directory=True)
            key = "link/body"
        else:
            (root / "link").symlink_to(outside, target_is_directory=True)
            key = "link/body"
    with pytest.raises(ValueError):
        paths.object_path(key)
    assert (outside / "body").read_bytes() == b"outside sentinel"
    assert not (outside / "missing").exists()


def test_object_path_rejects_preexisting_capture_root_symlink(tmp_path):
    paths_type = _paths_type()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "body").write_bytes(b"outside sentinel")
    root = tmp_path / "market.db.sec-research"
    root.symlink_to(outside, target_is_directory=True)
    paths = paths_type.from_market_db(tmp_path / "market.db")
    assert paths.capture_root == root
    with pytest.raises(ValueError):
        paths.object_path("body")
    assert (outside / "body").read_bytes() == b"outside sentinel"


def test_object_path_allows_symlinks_that_stay_beneath_the_capture_root(tmp_path):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    root = tmp_path / "market.db.sec-research"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "body").write_bytes(b"inside capture")
    (root / "alias").symlink_to("objects", target_is_directory=True)
    assert paths.object_path("alias/body") == root / "objects" / "body"
    assert paths.object_path("alias/body").read_bytes() == b"inside capture"


def test_object_path_does_not_accept_a_symlink_to_the_root_as_an_object(tmp_path):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    root = tmp_path / "market.db.sec-research"
    root.mkdir()
    (root / "alias").symlink_to(".", target_is_directory=True)
    with pytest.raises(ValueError):
        paths.object_path("alias")


def test_object_path_rejects_symlink_loops_as_invalid_keys(tmp_path):
    paths = _paths_type().from_market_db(tmp_path / "market.db")
    root = tmp_path / "market.db.sec-research"
    root.mkdir()
    (root / "first").symlink_to("second")
    (root / "second").symlink_to("first")
    with pytest.raises(ValueError):
        paths.object_path("first/body")
