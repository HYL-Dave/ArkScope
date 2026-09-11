"""Freeze source identities and reconcile exact executed/collected test nodes."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASE = '483e8f3e'
PREVIOUS = ROOT / 'docs/superpowers/evidence/2026-09-11-sec-durable-acquisition'


def save(path, value):
    with path.open('x') as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write('\n')


def identity():
    roots = ['src', 'tests', 'data_sources', 'apps/arkscope-web']
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--', *roots], cwd=ROOT).decode().rstrip('\0').split('\0')
    values = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
              if (ROOT / path).is_file() else None for path in paths}
    patch = subprocess.check_output(['git', 'diff', BASE, '--', *roots], cwd=ROOT)
    return {'paths': values, 'patch_sha256': hashlib.sha256(patch).hexdigest()}


def nodes(text):
    values = [line for line in text.splitlines() if line.startswith('tests/') and '::' in line]
    assert len(values) == len(set(values)), 'duplicate collected nodes'
    return set(values)


def reconcile(run):
    old = nodes(gzip.decompress((PREVIOUS / 'final-nodes.txt.gz').read_bytes()).decode())
    new = nodes((WORK / 'final-collect/output.log').read_text())
    assert len(old) == 8446
    modules = {path[:-3].replace('/', '.'): path for path in {node.split('::', 1)[0] for node in new}}
    result = {}
    for case in ET.parse(WORK / run / 'results.xml').iter('testcase'):
        classname = case.get('classname', '')
        matches = [module for module in modules if classname == module or classname.startswith(module + '.')]
        assert matches, ('unmapped testcase', classname, case.get('name'))
        module = max(matches, key=len)
        classes = classname[len(module):].lstrip('.').replace('.', '::')
        node = modules[module] + ('::' + classes if classes else '') + '::' + case.get('name')
        assert node not in result, ('duplicate executed node', node)
        result[node] = next((kind for kind in ('error', 'failure', 'skipped') if case.find(kind) is not None), 'passed')
    assert set(result) == new, {'missing': sorted(new - result.keys()), 'extra': sorted(result.keys() - new)}
    counts = Counter(result.values())
    assert not counts['error'] and not counts['failure'], counts
    skips = sorted(node for node, status in result.items() if status == 'skipped')
    assert skips == json.loads((PREVIOUS / 'verification-summary.json').read_text())['skipped']
    before = json.loads((WORK / 'source-before.json').read_text())
    after = identity()
    assert before == after, 'source/test changed during final verification'
    inverse_runs = ('parent-inverse-float', 'parent-inverse-as-of', 'parent-inverse-fact-ids')
    for name in inverse_runs:
        value = json.loads((WORK / name / 'hashes.json').read_text())
        expected = {path: before['paths'][path] for path in value['before']}
        assert value['before'] == value['after'] == expected, name
        cases = list(ET.parse(WORK / name / 'results.xml').iter('testcase'))
        assert len(cases) == 1 and cases[0].find('failure') is not None and cases[0].find('error') is None, name
    summary = {'base': BASE, 'baseline_collected': len(old), 'final_collected': len(new),
               'executed': len(result), 'counts': dict(counts), 'added': sorted(new - old),
               'removed': sorted(old - new), 'skipped': skips, 'skip_identities_unchanged': True,
               'source_paths_verified': len(after['paths']), 'source_patch_sha256': after['patch_sha256'],
               'production_access': False,
               'current_source_inverse_runs': list(inverse_runs),
               'runner_sha256': hashlib.sha256((WORK / 'offline_pytest.py').read_bytes()).hexdigest()}
    save(WORK / 'verification-summary.json', summary)
    print(json.dumps({key: len(value) if isinstance(value, list) else value for key, value in summary.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'reconcile'))
    parser.add_argument('--run', default='backend-full')
    options = parser.parse_args()
    if options.mode == 'freeze':
        value = identity()
        save(WORK / 'source-before.json', value)
        print(json.dumps({'paths': len(value['paths']), 'patch_sha256': value['patch_sha256']}))
    else:
        reconcile(options.run)
