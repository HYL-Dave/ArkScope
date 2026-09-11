"""Create immutable task-diff inputs for a read-only reviewer."""

import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('base')
    parser.add_argument('head')
    options = parser.parse_args()
    assert options.name.replace('-', '').isalnum()
    base = git('rev-parse', '--verify', options.base + '^{commit}').strip()
    head = git('rev-parse', '--verify', options.head + '^{commit}').strip()
    span = base + '..' + head
    parts = [f'Base: {base}\nHead: {head}\n', git('log', '--oneline', span),
             git('diff', '--stat', span), git('diff', '--unified=30', span)]
    target = WORK / (options.name + '-diff.txt')
    with target.open('x') as output:
        output.write('\n'.join(parts))
    print(target)
