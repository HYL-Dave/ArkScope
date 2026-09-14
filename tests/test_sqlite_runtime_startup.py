"""A selected but invalid engine must fail before application side effects."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def invalid_env(tmp_path):
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1",
            "ARKSCOPE_SQLITE_PACKAGE": str(tmp_path / "missing"),
            "ARKSCOPE_SQLITE_MANIFEST_SHA256": "a" * 64}


def test_src_rejects_selection_before_following_user_code(tmp_path):
    child = subprocess.run([sys.executable, "-B", "-c",
                            f"import sys; sys.path.insert(0, {str(ROOT)!r}); import src; print('unprotected')"],
                           cwd=tmp_path, env=invalid_env(tmp_path), capture_output=True, timeout=10)
    assert child.returncode != 0
    assert child.stdout == b""
    assert b"sqlite_runtime_" in child.stderr


def test_native_host_script_rejects_before_chdir_or_logging(tmp_path):
    script = f"""
import runpy, sys
def guard(event, args):
    if event in {{'os.chdir', 'os.mkdir'}}:
        raise RuntimeError('test blocked a premature native-host side effect')
sys.addaudithook(guard)
runpy.run_path({str(ROOT / 'src/sa_native_host.py')!r}, run_name='__main__')
"""
    child = subprocess.run([sys.executable, "-B", "-c", script], cwd=tmp_path,
                           env=invalid_env(tmp_path), capture_output=True, timeout=10)
    assert child.returncode != 0
    assert child.stdout == b""
    assert b"sqlite_runtime_" in child.stderr


@pytest.mark.parametrize("module", ["src.api.app", "src.api.__main__", "src.daily_update",
                                    "src.prices_runtime", "src.news_normalized.ibkr_cli",
                                    "src.lifecycle_investigation.__main__"])
def test_supported_module_imports_fail_before_dependency_import(module, tmp_path):
    script = f"""
import importlib, sys
sys.path.insert(0, {str(ROOT)!r})
def guard(event, args):
    if event == 'import' and args[0] in {{'fastapi', 'uvicorn', 'src.market_data_admin', 'src.env_keys'}}:
        raise RuntimeError('test blocked a premature application import')
sys.addaudithook(guard)
importlib.import_module({module!r})
"""
    child = subprocess.run([sys.executable, "-B", "-c", script], cwd=tmp_path,
                           env=invalid_env(tmp_path), capture_output=True, timeout=10)
    assert child.returncode != 0
    assert child.stdout == b""
    assert b"sqlite_runtime_" in child.stderr
