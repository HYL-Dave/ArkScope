"""Capture isolated check commands without importing product modules."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
PYTHON = '/home/hyl/.virtualenvs/llm_app/bin/python'
NODE = '/home/hyl/.nvm/versions/node/v22.14.0/bin'


def run(name, mode, args):
    run_root = WORK / name
    run_root.mkdir(exist_ok=False)
    env = {
        'PATH': f'/home/hyl/.virtualenvs/llm_app/bin:{NODE}:/usr/bin:/bin',
        'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'ARKSCOPE_OFFLINE_TEST_WORKSPACE': str(run_root),
        'HOME': str(run_root / 'home'), 'CI': '1', 'TZ': 'Asia/Taipei',
        'ARKSCOPE_TEST_SQLITE_ARCHIVE': str(WORK / 'sqlite-src-3530400.zip'),
    }
    Path(env['HOME']).mkdir()
    if mode in {'backend', 'backend-admitted', 'backend-sqlite', 'backend-c09-inverse', 'backend-task2-inverse'}:
        launcher = 'offline_pytest.py'
        if mode == 'backend-task2-inverse':
            launcher = 'task2_inverse.py'
        if mode == 'backend-c09-inverse':
            launcher = 'c09_inverse.py'
        if mode == 'backend-sqlite':
            env['LD_LIBRARY_PATH'] = str(WORK / 'sqlite-candidate/prefix/lib')
            launcher = 'sqlite_pytest.py'
        cmd = [PYTHON, '-B', str(WORK / launcher), *args,
               f'--junitxml={run_root / "results.xml"}']
        if mode == 'backend-admitted':
            cmd[0] = str(WORK / 'package/python')
        cwd = ROOT
    elif mode == 'source-check':
        cmd = [PYTHON, '-I', '-S', '-B', str(WORK / 'verify_cleanup.py'), *args]
        cwd = ROOT
    elif mode == 'collect':
        cmd = [PYTHON, '-B', str(WORK / 'offline_pytest.py'), '--collect-only', '-q', *args]
        cwd = ROOT
    elif mode == 'frontend':
        env['NODE_OPTIONS'] = f'--require={WORK / "offline_node.cjs"}'
        cmd = [str(Path(NODE) / 'npm'), *args]
        cwd = ROOT / 'apps/arkscope-web'
    elif mode == 'browser':
        env['PLAYWRIGHT_BROWSERS_PATH'] = '/home/hyl/.cache/ms-playwright'
        cmd = [PYTHON, '-B', str(WORK / 'browser_check.py'), '--base',
               'http://127.0.0.1:8457', '--output', str(run_root / 'browser'), *args]
        cwd = ROOT
    elif mode in {'census', 'census-base'}:
        cmd = [PYTHON, '-B', str(WORK / 'run_census.py'), '--root', '.',
               '--output', str(run_root / 'census.json.gz'), '--untracked-root',
               '/mnt/md0/PycharmProjects/ArkScope']
        if mode == 'census-base':
            cmd += ['--revision', '9dd2ab27', '--current-scanner-on-revision']
        else:
            cmd += ['--compare', str(WORK / 'census-current-scanner-base/census.json.gz')]
        cmd += args
        cwd = ROOT
    else:
        raise ValueError(mode)
    start = time.monotonic()
    with (run_root / 'output.log').open('x') as output:
        result = subprocess.run(cmd, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)
    record = {'name': name, 'command': cmd, 'cwd': str(cwd),
              'exit_code': result.returncode, 'seconds': round(time.monotonic() - start, 3),
              'environment': env, 'log': str(run_root / 'output.log')}
    (run_root / 'command.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    print('\n'.join((run_root / 'output.log').read_text().splitlines()[-15:]), flush=True)
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('mode', choices=('backend', 'backend-admitted', 'backend-sqlite', 'backend-c09-inverse', 'backend-task2-inverse', 'collect', 'frontend', 'browser', 'census', 'census-base', 'source-check'))
    parser.add_argument('args', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    raise SystemExit(run(options.name, options.mode, options.args))
