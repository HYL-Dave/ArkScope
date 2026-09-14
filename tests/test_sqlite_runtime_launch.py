"""Real launcher acceptance against an explicitly supplied offline source archive."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    from src.sqlite_runtime.build import build_package
    archive = os.environ.get("ARKSCOPE_TEST_SQLITE_ARCHIVE")
    if not archive:
        from src.sqlite_runtime.contract import require_selected_runtime
        if require_selected_runtime() is not None:
            pytest.fail(
                "selected-runtime acceptance requires the offline SQLite source archive",
                pytrace=False,
            )
        pytest.skip("final-artifact acceptance needs explicit offline SQLite source archive")
    root = tmp_path_factory.mktemp("sqlite-package") / "generation"
    build_package(Path(archive), root, Path(sys.executable))
    return root


@pytest.fixture
def child_env(tmp_path):
    return {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}


def run(root, env, *args, cwd=None, input=None):
    return subprocess.run([str(root / "python"), *args], env=env, cwd=cwd,
                          input=input, capture_output=True, timeout=30)


def test_real_python_and_descendant_use_same_engine(prepared, child_env):
    code = "import sqlite3,sys,json; print(json.dumps([sqlite3.sqlite_version,sys.executable]))"
    parent = "import subprocess,sys; " + code + f"; subprocess.run([sys.executable,'-c',{code!r}], check=True)"
    result = run(prepared, child_env, "-u", "-c", parent)
    assert result.returncode == 0, result.stderr.decode()
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows == [["3.53.4", sys.executable]] * 2
    assert "LD_LIBRARY_PATH" not in child_env


@pytest.mark.parametrize("selected", [True, False], ids=["selected-required", "unmanaged-skip"])
def test_missing_archive_is_not_selected_runtime_acceptance(prepared, child_env, tmp_path, selected):
    repo = Path(__file__).resolve().parents[1]
    node = "tests/test_sqlite_runtime_launch.py::test_real_python_and_descendant_use_same_engine"
    script = (
        "from src import env_keys; env_keys._loaded = True; import pytest; "
        f"raise SystemExit(pytest.main(['-p', 'no:cacheprovider', '-q', '-rs', '--tb=short', {node!r}]))"
    )
    executable = str(prepared / "python") if selected else sys.executable
    env = dict(child_env, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", TMPDIR=str(tmp_path))
    child = subprocess.run([executable, "-B", "-c", script], cwd=repo, env=env,
                           capture_output=True, timeout=30)
    if selected:
        assert child.returncode == 1, child.stdout.decode() + child.stderr.decode()
        assert b"selected-runtime acceptance requires the offline SQLite source archive" in child.stdout
        assert b"1 skipped" not in child.stdout
    else:
        assert child.returncode == 0, child.stdout.decode() + child.stderr.decode()
        assert b"1 skipped" in child.stdout
        assert b"final-artifact acceptance needs explicit offline SQLite source archive" in child.stdout


@pytest.mark.parametrize("args,stdin,code,stdout", [
    (["-c", "import sys; print(repr(sys.argv[1:])); sys.exit(19)", "a b", "--flag"], None, 19, b"['a b', '--flag']\n"),
    (["-I", "-S", "-"], b"print('from stdin')\n", 0, b"from stdin\n"),
    (["-m", "json.tool"], b'{"x":1}', 0, b'{\n    "x": 1\n}\n'),
])
def test_python_cli_semantics(prepared, child_env, args, stdin, code, stdout):
    result = run(prepared, child_env, *args, input=stdin)
    assert result.returncode == code, result.stderr.decode()
    assert result.stdout == stdout
    assert result.stderr == b""


def test_relocation_cwd_and_external_selector_symlink(prepared, tmp_path, child_env):
    moved = tmp_path / "relocated generation"
    shutil.copytree(prepared, moved, symlinks=True)
    alias = tmp_path / "selector"
    alias.symlink_to(moved / "python")
    result = subprocess.run([str(alias), "-c", "import sqlite3,os; print(sqlite3.sqlite_version); print(os.getcwd())"],
                            cwd=tmp_path, env=child_env, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout.decode().splitlines() == ["3.53.4", str(tmp_path)]


def test_signals_reach_execed_python(prepared, child_env):
    child = subprocess.Popen([str(prepared / "python"), "-u", "-c",
                              "import signal; print('ready'); signal.pause()"],
                             env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        import select
        assert select.select([child.stdout], [], [], 30)[0]
        assert child.stdout.readline() == b"ready\n"
        child.send_signal(signal.SIGTERM)
        child.communicate(timeout=5)
        assert child.returncode == -signal.SIGTERM
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


@pytest.mark.parametrize("fault", ["library", "manifest", "extra_library", "extension_hash", "source_id"])
def test_drift_stops_before_user_code(prepared, tmp_path, child_env, fault):
    from src.sqlite_runtime.contract import selector_text
    root = tmp_path / "broken"
    shutil.copytree(prepared, root, symlinks=True)
    root.chmod(0o700)
    (root / "lib").chmod(0o700)
    if fault == "library":
        path = root / "lib/libsqlite3.so.3.53.4"
        path.chmod(0o600)
        with path.open("ab") as stream:
            stream.write(b"drift")
    elif fault == "extra_library":
        (root / "lib/libc.so.6").write_bytes(b"unowned")
    else:
        path = root / "manifest.json"
        path.chmod(0o600)
        data = json.loads(path.read_text())
        if fault == "manifest":
            data["format"] = 2
        elif fault == "extension_hash":
            data["python"]["extension_sha256"] = "f" * 64
        else:
            data["engine"]["source_id"] = "2026-07-24 19:02:57 " + "a" * 64
        body = json.dumps(data, sort_keys=True).encode()
        path.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        (root / "python").chmod(0o700)
        (root / "python").write_text(selector_text(data["python"]["path"], digest, data["files"]))
    result = run(root, child_env, "-c", "print('must not run')")
    assert result.returncode == 78
    assert result.stdout == b""
    assert b"sqlite_runtime_" in result.stderr


def test_native_imports_and_important_sql_features(prepared, child_env):
    script = """
import numpy as np, pandas as pd, sqlite3
assert np.array([1,2,3]).sum() == 6
assert pd.DataFrame({'x':[1,2]}).x.sum() == 3
c = sqlite3.connect(':memory:')
assert c.execute('PRAGMA secure_delete').fetchone() == (1,)
assert c.execute("SELECT x'61' LIKE 'a'").fetchone() == (0,)
c.execute('CREATE VIRTUAL TABLE r USING rtree(id, x, y)')
c.execute('CREATE VIRTUAL TABLE f USING fts5(v)')
c.execute('SELECT ?250000', (None,) * 250000)
assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
print(sqlite3.sqlite_version)
"""
    result = run(prepared, child_env, "-c", script)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == b"3.53.4\n"


def test_preload_is_not_a_second_loader_authority(prepared, child_env):
    result = run(prepared, dict(child_env, LD_PRELOAD="/nonexistent-fixture"), "-c", "print('must not run')")
    assert result.returncode == 78
    assert result.stdout == b""
    assert b"sqlite_runtime_loader_conflict" in result.stderr


def test_limit_grammar_is_real_not_just_a_compile_option(prepared, child_env):
    result = run(prepared, child_env, "-c", """
import sqlite3
c = sqlite3.connect(':memory:')
c.execute('CREATE TABLE x(a)')
c.execute('INSERT INTO x VALUES (1), (2)')
c.execute('UPDATE x SET a=3 ORDER BY a LIMIT 1')
assert c.execute('SELECT a FROM x ORDER BY a').fetchall() == [(2,), (3,)]
c.execute('DELETE FROM x ORDER BY a LIMIT 1')
assert c.execute('SELECT a FROM x').fetchall() == [(3,)]
""")
    assert result.returncode == 0, result.stderr.decode()


def test_same_version_copy_is_not_the_loaded_artifact(prepared, tmp_path, child_env):
    root = tmp_path / "different-generation"
    shutil.copytree(prepared, root, symlinks=True)
    digest = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()
    env = dict(child_env, LD_LIBRARY_PATH=str(prepared / "lib"))
    child = subprocess.run([sys.executable, "-I", "-S", "-B", str(root / "contract.py"),
                            "--probe", str(root), digest], env=env, capture_output=True, timeout=30)
    assert child.returncode == 78
    assert child.stdout == b""
    assert b"sqlite_runtime_engine_mismatch" in child.stderr


def test_existing_sa_selector_launches_selected_python(prepared, tmp_path, child_env):
    repo = Path(__file__).resolve().parents[1]
    host = tmp_path / "fixture_host.py"
    host.write_text("import sqlite3,sys; sys.stdout.buffer.write(sys.stdin.buffer.read()); "
                    "print(sqlite3.sqlite_version)\n")
    config = tmp_path / "sa.json"
    config.write_text(json.dumps({"project_root": str(tmp_path), "python_path": str(prepared / "python"),
                                 "host_script": str(host)}))
    child = subprocess.run(["/bin/sh", str(repo / "extensions/sa_alpha_picks/native_host_launcher.sh")],
                           env=dict(child_env, ARKSCOPE_SA_NATIVE_HOST_CONFIG=str(config)),
                           input=b"native-input\n", capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout == b"native-input\n3.53.4\n"


@pytest.mark.parametrize("module", ["src.prices_runtime", "src.news_normalized.ibkr_cli",
                                    "src.lifecycle_investigation"])
def test_real_worker_help_paths_are_admitted_before_dispatch(prepared, child_env, module):
    repo = Path(__file__).resolve().parents[1]
    child = run(prepared, child_env, "-m", module, "--help", cwd=repo)
    assert child.returncode == 0, child.stderr.decode()
    assert b"usage:" in child.stdout


def test_oauth_child_environments_do_not_inherit_loader(prepared, child_env, tmp_path):
    repo = Path(__file__).resolve().parents[1]
    script = f"""
import os, pathlib
from src.auth_drivers.claude_agent_sdk_runtime import build_claude_child_environment
from src.auth_drivers.codex_app_server_runtime import isolated_codex_environment
names = ('LD_LIBRARY_PATH', 'ARKSCOPE_SQLITE_PACKAGE', 'ARKSCOPE_SQLITE_MANIFEST_SHA256')
assert all(os.environ.get(name) for name in names)
claude = build_claude_child_environment(token='synthetic', config_dir={str(tmp_path)!r})
assert all(not claude.get(name) for name in names)
root = pathlib.Path({str(tmp_path)!r})
codex = isolated_codex_environment(root/'fixture', root/'fixture', root)
assert all(not codex.get(name) for name in names)
print('closed')
"""
    child = run(prepared, child_env, "-c", script, cwd=repo)
    assert child.returncode == 0, child.stderr.decode()
    assert child.stdout == b"closed\n"


def test_desktop_spawn_keeps_loader_out_of_electron(prepared, child_env, tmp_path):
    repo = Path(__file__).resolve().parents[1]
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
    child = subprocess.run([node, "-e", script, str(repo / "apps/arkscope-desktop/main.js"),
                            str(tmp_path), str(prepared / "python")], env=child_env,
                           capture_output=True, timeout=30)
    assert child.returncode == 0, child.stderr.decode()
    assert b"engine=3.53.4" in child.stdout


@pytest.mark.parametrize("name", ["contract.py", "launch.py"])
def test_changed_bootstrap_is_rejected_before_execution(prepared, tmp_path, child_env, name):
    root = tmp_path / "changed-bootstrap"
    shutil.copytree(prepared, root, symlinks=True)
    target = root / name
    target.chmod(0o600)
    target.write_text("print('unverified bootstrap executed', flush=True)\nraise SystemExit(0)\n")
    result = run(root, child_env, "-c", "print('user code')")
    assert result.returncode == 78
    assert result.stdout == b""


def test_extra_module_has_no_bootstrap_import_authority(prepared, tmp_path, child_env):
    root = tmp_path / "extra-module"
    shutil.copytree(prepared, root, symlinks=True)
    root.chmod(0o700)
    (root / "platform.py").write_text("print('unverified module executed', flush=True)\n")
    result = run(root, child_env, "-c", "print('user code')")
    assert result.returncode == 78
    assert result.stdout == b""


@pytest.mark.parametrize("name", ["LD_PRELOAD", "LD_AUDIT"])
def test_direct_python_child_rechecks_loader_authority(prepared, tmp_path, child_env, name):
    repo = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256((prepared / "manifest.json").read_bytes()).hexdigest()
    env = dict(child_env, LD_LIBRARY_PATH=str(prepared / "lib"),
               ARKSCOPE_SQLITE_PACKAGE=str(prepared), ARKSCOPE_SQLITE_MANIFEST_SHA256=digest)
    env[name] = "/nonexistent-fixture"
    child = subprocess.run([sys.executable, "-B", "-c", "import src; print('unprotected')"],
                           env=env, cwd=repo, capture_output=True, timeout=30)
    assert child.returncode != 0
    assert child.stdout == b""
    assert b"sqlite_runtime_loader_conflict" in child.stderr


@pytest.mark.parametrize("name", ["manifest.json", "contract.py", "launch.py"])
def test_bootstrap_fifo_is_rejected_without_blocking(prepared, tmp_path, child_env, name):
    root = tmp_path / "fifo-package"
    shutil.copytree(prepared, root, symlinks=True)
    root.chmod(0o700)
    (root / name).unlink()
    os.mkfifo(root / name, mode=0o600)
    child = subprocess.Popen([str(root / "python"), "-c", "print('user code')"],
                             env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
    try:
        stdout, stderr = child.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        pytest.fail("bootstrap blocked on a FIFO before file-shape admission")
    assert child.returncode == 78, stderr.decode()
    assert stdout == b""
