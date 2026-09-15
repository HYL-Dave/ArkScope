"""Source-free checks of the existing interpreter selection and launch paths.

These are not admission of a replacement production interpreter.
"""

import json
import os
from pathlib import Path
import select
import shutil
import signal
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "extensions/sa_alpha_picks/native_host_launcher.sh"


@pytest.fixture
def child_env(tmp_path):
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}


def test_self_build_runtime_is_removed():
    assert not list((ROOT / "src/sqlite_runtime").glob("*.py"))
    assert "sqlite_runtime" not in (ROOT / "src/__init__.py").read_text()
    assert "sqlite_runtime" not in (ROOT / "src/sa_native_host.py").read_text()


def test_src_import_is_inert(tmp_path, child_env):
    code = f"""
import sys, os, logging
sys.path.insert(0, {str(ROOT)!r})
start = os.getcwd()
def guard(event, args):
    if event in {{'os.chdir', 'os.mkdir', 'sqlite3.connect', 'subprocess.Popen'}}:
        raise AssertionError(event)
sys.addaudithook(guard)
import src
assert os.getcwd() == start
assert not logging.getLogger().handlers
"""
    child = subprocess.run([sys.executable, "-B", "-c", code], env=child_env,
                           cwd=tmp_path, capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout == b""
    assert child.stderr == b""


def native_config(tmp_path, code):
    project = tmp_path / "project with spaces"
    project.mkdir()
    host = project / "fixture host.py"
    host.write_text(code)
    config = tmp_path / "sa config.json"
    config.write_text(json.dumps({
        "project_root": str(project), "host_script": str(host), "python_path": sys.executable,
    }))
    return project, host, config


def test_browser_selector_preserves_io_cwd_exit_and_descendant_engine(tmp_path, child_env):
    code = """
import json, os, sqlite3, subprocess, sys
payload = sys.stdin.buffer.read()
sys.stdout.buffer.write(payload)
sys.stdout.buffer.flush()
print(json.dumps([os.getcwd(), sys.argv, sqlite3.sqlite_version, sys.executable]), flush=True)
subprocess.run([sys.executable, '-c', 'import sqlite3; print(sqlite3.sqlite_version)'], check=True)
sys.exit(19)
"""
    project, host, config = native_config(tmp_path, code)
    child = subprocess.run(["/bin/sh", str(LAUNCHER)], cwd=tmp_path,
                           env=dict(child_env, ARKSCOPE_SA_NATIVE_HOST_CONFIG=str(config)),
                           input=b"\x04\x00\x00\x00test\n", capture_output=True, timeout=30)
    assert child.returncode == 19, child.stderr.decode()
    lines = child.stdout.splitlines()
    assert lines[0] == b"\x04\x00\x00\x00test"
    assert json.loads(lines[1]) == [str(project), [str(host)], sqlite3.sqlite_version, sys.executable]
    assert lines[2].decode() == sqlite3.sqlite_version
    assert child.stderr == b""


def test_browser_selector_has_no_fallback_when_configured_python_is_missing(tmp_path, child_env):
    _, _, config = native_config(tmp_path, "print('must not run')\n")
    data = json.loads(config.read_text())
    data["python_path"] = str(tmp_path / "missing python")
    config.write_text(json.dumps(data))
    child = subprocess.run(["/bin/sh", str(LAUNCHER)],
                           env=dict(child_env, ARKSCOPE_SA_NATIVE_HOST_CONFIG=str(config)),
                           capture_output=True, timeout=30)
    assert child.returncode != 0
    assert child.stdout == b""
    assert b"Configured python is not executable" in child.stderr


def test_signals_reach_native_host_through_exec(tmp_path, child_env):
    _, _, config = native_config(tmp_path, "import signal; print('ready', flush=True); signal.pause()\n")
    child = subprocess.Popen(["/bin/sh", str(LAUNCHER)],
                             env=dict(child_env, ARKSCOPE_SA_NATIVE_HOST_CONFIG=str(config)),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert select.select([child.stdout], [], [], 30)[0]
        assert child.stdout.readline() == b"ready\n"
        child.send_signal(signal.SIGTERM)
        _, stderr = child.communicate(timeout=5)
        assert child.returncode == -signal.SIGTERM
        assert stderr == b""
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


@pytest.mark.parametrize("module", ["src.prices_runtime", "src.news_normalized.ibkr_cli",
                                    "src.lifecycle_investigation"])
def test_current_worker_help_with_selected_interpreter(module, tmp_path, child_env):
    code = f"""
import runpy, sys, sqlite3
sys.path.insert(0, {str(ROOT)!r})
from src import env_keys
env_keys._loaded = True
print('engine=' + sqlite3.sqlite_version, flush=True)
sys.argv = [{module!r}, '--help']
runpy.run_module({module!r}, run_name='__main__')
"""
    child = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path,
                           env=child_env, capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout.startswith(f"engine={sqlite3.sqlite_version}\n".encode())
    assert b"usage:" in child.stdout


def test_oauth_child_environments_keep_loader_injection_out(monkeypatch, tmp_path):
    from src.auth_drivers.claude_agent_sdk_runtime import build_claude_child_environment
    from src.auth_drivers.codex_app_server_runtime import isolated_codex_environment

    names = ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT")
    for name in names:
        monkeypatch.setenv(name, "/synthetic-untrusted-loader")
    claude = build_claude_child_environment(token="synthetic", config_dir=str(tmp_path))
    codex = isolated_codex_environment(tmp_path / "fixture", tmp_path / "fixture", tmp_path)
    assert all(not claude.get(name) and not codex.get(name) for name in names)


def test_desktop_real_child_uses_configured_interpreter(tmp_path, child_env):
    node = shutil.which("node")
    assert node, "Desktop acceptance requires the project's Node runtime"
    (tmp_path / "src").mkdir()
    (tmp_path / "src/__init__.py").write_text("")
    (tmp_path / "src/api.py").write_text("import sqlite3; print('engine=' + sqlite3.sqlite_version)\n")
    script = r"""
const vm = require('node:vm'), fs = require('node:fs'), path = require('node:path');
const cp = require('node:child_process');
const app = {disableHardwareAcceleration(){}, commandLine:{appendSwitch(){}},
  whenReady(){return {then(){}}}, on(){}};
let child;
const overrides = {
  electron: {app}, './navigation': {},
  './sidecarConfig': {nativeHostConfigPath(){return 'unused';}, stopSidecarCleanup(){}},
  'node:child_process': {spawn(...args){child=cp.spawn(...args); return child;}}
};
const context = {require(name){return overrides[name] || require(name)}, console, Buffer,
  __dirname:path.join(process.argv[2], 'apps', 'desktop'),
  process:{env:{...process.env,ARKSCOPE_PYTHON:process.argv[3],ARKSCOPE_SIDECAR_LOG:'1'},on(){}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8')+'\nstartSidecar(1234,"fixture");',context);
if(context.process.env.LD_LIBRARY_PATH) throw Error('Electron loader polluted');
child.on('exit', code=>{if(code) process.exitCode=code});
"""
    child = subprocess.run([node, "-e", script, str(ROOT / "apps/arkscope-desktop/main.js"),
                            str(tmp_path), sys.executable], env=child_env,
                           capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert f"engine={sqlite3.sqlite_version}".encode() in child.stdout


def test_native_data_dependencies_and_required_sql_features(tmp_path, child_env):
    code = """
import numpy as np, pandas as pd, sqlite3
assert np.array([1,2,3]).sum() == 6
assert pd.DataFrame({'x':[1,2]}).x.sum() == 3
c = sqlite3.connect(':memory:')
c.execute('CREATE VIRTUAL TABLE f USING fts5(v)')
c.execute("INSERT INTO f VALUES ('searchable')")
assert c.execute("SELECT v FROM f WHERE f MATCH 'searchable'").fetchone() == ('searchable',)
assert c.execute("SELECT value FROM json_each('[1,2]')").fetchall() == [(1,), (2,)]
assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
print(sqlite3.sqlite_version)
"""
    child = subprocess.run([sys.executable, "-B", "-c", code], cwd=tmp_path,
                           env=child_env, capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout == f"{sqlite3.sqlite_version}\n".encode()
