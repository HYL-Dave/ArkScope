"""Firefox packaging must derive and atomically ship its runtime closure."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
EXT_DIR = REPO_ROOT / "extensions" / "sa_alpha_picks"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sa_extension" / "packaging"
BUILDER_PATH = EXT_DIR / "build_firefox.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("sa_firefox_builder", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def _copy_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    shutil.copytree(FIXTURE_DIR, source)
    return source


def _tree_bytes(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def test_dependency_graph_closes_manifest_html_imports_and_injected_scripts(tmp_path):
    builder = _load_builder()
    assert not (EXT_DIR / "__pycache__").exists()
    source = _copy_fixture(tmp_path)

    graph = builder.discover_dependency_graph(source)

    assert set(graph.files) == {
        "article_identity.js",
        "background.js",
        "compat_firefox.js",
        "content.css",
        "content.js",
        "icon.asset",
        "logo.asset",
        "manifest.firefox.json",
        "popup.html",
        "popup.js",
        "scrape_detail.js",
        "scrape_list.js",
        "shared.js",
        "style.css",
        "web.asset",
    }
    assert {ref.kind for ref in graph.references} >= {
        "manifest",
        "html",
        "import_scripts",
        "execute_script",
    }


def test_dependency_graph_includes_article_identity_for_both_injection_sites():
    builder = _load_builder()

    graph = builder.discover_dependency_graph(EXT_DIR)
    identity_refs = [
        ref
        for ref in graph.references
        if ref.target == "article_identity.js" and ref.kind == "execute_script"
    ]

    assert len(identity_refs) == 2
    assert {ref.source for ref in identity_refs} == {"background.js"}
    assert [ref.line for ref in identity_refs] == sorted(
        {ref.line for ref in identity_refs}
    )


def test_new_literal_runtime_dependency_is_included_without_builder_edits(tmp_path):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    background = source / "background.js"
    background.write_text(
        background.read_text(encoding="utf-8")
        + '\nchrome.scripting.executeScript({files: ["late_dependency.js"]});\n',
        encoding="utf-8",
    )
    (source / "late_dependency.js").write_text("globalThis.late = true;\n", encoding="utf-8")

    graph = builder.discover_dependency_graph(source)

    assert "late_dependency.js" in graph.files


def test_missing_runtime_dependency_fails_before_output_replacement(tmp_path):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    output = tmp_path / "firefox"
    output.mkdir()
    (output / "known-good.txt").write_text("keep\n", encoding="utf-8")
    before = _tree_bytes(output)
    (source / "scrape_detail.js").unlink()

    with pytest.raises(builder.BuildError, match=r"background\.js.*scrape_detail\.js"):
        builder.build_firefox(source, output)

    assert _tree_bytes(output) == before


def test_dynamic_execute_script_or_import_scripts_dependency_is_rejected(tmp_path):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    background = source / "background.js"

    for expression in (
        "const runtimeFile = 'late.js'; importScripts(runtimeFile);",
        "const runtimeFile = 'late.js'; chrome.scripting.executeScript({files: [runtimeFile]});",
        "const opts = {files: ['late.js']}; chrome.scripting.executeScript({...opts});",
        "chrome.scripting.executeScript({['files']: ['late.js']});",
        "chrome.scripting.executeScript({files: ['late.js'].concat(moreFiles)});",
    ):
        original = background.read_text(encoding="utf-8")
        background.write_text(original + "\n" + expression + "\n", encoding="utf-8")
        with pytest.raises(builder.BuildError, match=r"background\.js.*literal"):
            builder.discover_dependency_graph(source)
        background.write_text(original, encoding="utf-8")


def test_unsafe_remote_or_traversing_asset_reference_is_rejected(tmp_path):
    builder = _load_builder()

    for unsafe in ("../secret.js", "https://example.com/remote.js", "popup.js?q=secret"):
        source = _copy_fixture(tmp_path / unsafe.split("/")[-1].replace("?", "_"))
        manifest = source / "manifest.firefox.json"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace('"background.js"', f'"{unsafe}"'), encoding="utf-8")
        with pytest.raises(builder.BuildError, match=r"manifest\.firefox\.json.*unsafe"):
            builder.discover_dependency_graph(source)


def test_build_output_is_exact_and_drops_stale_files(tmp_path):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    output = tmp_path / "firefox"
    output.mkdir()
    (output / "stale.js").write_text("stale\n", encoding="utf-8")

    built = builder.build_firefox(source, output)

    expected = set(builder.discover_dependency_graph(source).files)
    expected.remove("manifest.firefox.json")
    expected.add("manifest.json")
    assert set(built) == expected
    assert set(_tree_bytes(output)) == expected
    assert "stale.js" not in _tree_bytes(output)


def test_generated_popup_loads_firefox_compat_exactly_once_before_popup(tmp_path):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    output = tmp_path / "firefox"

    builder.build_firefox(source, output)
    popup = (output / "popup.html").read_text(encoding="utf-8")

    assert popup.count('src="compat_firefox.js"') == 1
    assert popup.index('src="compat_firefox.js"') < popup.index('src="popup.js"')


def test_failed_build_preserves_the_previous_known_good_output(tmp_path, monkeypatch):
    builder = _load_builder()
    source = _copy_fixture(tmp_path)
    output = tmp_path / "firefox"
    builder.build_firefox(source, output)
    before = _tree_bytes(output)
    real_replace = os.replace

    def fail_new_tree_replace(src, dst):
        src_path = Path(src)
        dst_path = Path(dst)
        if dst_path == output and ".firefox.tmp-" in src_path.name:
            raise OSError("synthetic final replacement failure")
        return real_replace(src, dst)

    monkeypatch.setattr(builder.os, "replace", fail_new_tree_replace)

    with pytest.raises(OSError, match="synthetic final replacement failure"):
        builder.build_firefox(source, output)

    assert _tree_bytes(output) == before


def test_chrome_source_dependency_graph_is_complete():
    builder = _load_builder()

    graph = builder.discover_dependency_graph(EXT_DIR, manifest_name="manifest.json")

    assert "manifest.json" in graph.files
    assert "article_identity.js" in graph.files
    assert "popup.html" in graph.files
    assert "reconciliation_ui.js" in graph.files
    assert "popup.js" in graph.files
    assert all((EXT_DIR / name).is_file() for name in graph.files)
    assert all("/" not in name and "\\" not in name for name in graph.files)
