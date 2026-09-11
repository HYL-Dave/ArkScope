"""Normalize declared inverse runs and retain exact failed testcase identities."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def failures(run):
    command = json.loads((WORK / run / 'command.json').read_text())
    assert command['exit_code'] == 1, run
    cases = list(ET.parse(WORK / run / 'results.xml').iter('testcase'))
    assert not any(case.find('error') is not None for case in cases), run
    values = sorted(case.get('classname') + '::' + case.get('name')
                    for case in cases if case.find('failure') is not None)
    assert values, run
    return values


def task1():
    source = json.loads((WORK / 'task-1/fix-r2-inverses.json').read_text())
    manifest = WORK / source['restoration_manifest']
    restored = {}
    for line in manifest.read_text().splitlines():
        digest, path = line.split(None, 1)
        path = path.strip().removeprefix('*')
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
        restored[path] = digest
    values = []
    for mutation in source['mutations']:
        actual = failures(mutation['run'])
        assert len(actual) == mutation['failed'], mutation['run']
        values.append({'run': mutation['run'], 'restored': restored,
                       'mutated': dict(restored, **{
                           source['mutated_file']: mutation['mutated_sha256']}),
                       'failed_testcases': actual,
                       'record': 'task-1/fix-r2-inverses.json',
                       'change': mutation['change']})
    return values


def task2():
    original = json.loads((WORK / 'task-2/inverse-hashes.json').read_text())
    final = json.loads((WORK / 'task-2/final-inverse-hashes.json').read_text())
    names = {
        'latest': 'task2-inverse-latest-final-01',
        'query': 'task2-inverse-query-binding-final-01',
        'primary': 'task2-inverse-primary-absence-01',
        'truncated': 'task2-inverse-truncated-complete-01',
    }
    values = []
    for document, key, admitted, record in (
            (original, 'inverses', {'primary', 'truncated'}, 'task-2/inverse-hashes.json'),
            (final, 'affected_inverses', {'latest', 'query'}, 'task-2/final-inverse-hashes.json')):
        baseline = {row['path']: row['sha256'] for row in document['baseline']}
        for mutation in document[key]:
            if mutation['name'] not in admitted:
                continue
            digest, path = mutation['mutated_hash'].split(None, 1)
            owner = 'tests/test_sec_research_' + Path(path).name
            restored = {name: baseline[name] for name in (path, owner)}
            assert mutation['all_eight_files_restored'], mutation['name']
            for name, sha in restored.items():
                assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
            run = names[mutation['name']]
            values.append({'run': run, 'restored': restored,
                           'mutated': dict(restored, **{path: digest}),
                           'failed_testcases': failures(run), 'record': record})
    assert len(values) == 4
    return values


def task2_fix1():
    record = 'task-2/fix-r1-inverse-hashes.json'
    source = json.loads((WORK / record).read_text())
    assert source['postcommit_snapshot_matches_baseline']
    restored = {row['path']: row['sha256'] for row in source['baseline']
                if not row['path'].startswith('.')}
    for path, digest in restored.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    values = []
    for mutation in source['inverses']:
        changed = mutation.get('mutated_snapshot') or [mutation['mutated_file']]
        mutated = dict(restored)
        mutated.update({row['path']: row['sha256'] for row in changed
                        if row['path'] in restored})
        assert mutation['all_nine_hashes_restored']
        run = mutation['evidence_directory']
        values.append({'run': run, 'restored': restored, 'mutated': mutated,
                       'failed_testcases': failures(run), 'record': record,
                       'change': mutation['mutation']})
    return values


def parent_queries():
    values = []
    for name in ('parent-inverse-pin-01', 'parent-inverse-filter-01'):
        source = json.loads((WORK / name / 'hashes.json').read_text())
        assert source['before'] == source['after'] and not source['disk_source_modified']
        for path, digest in source['after'].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
        values.append({'run': name, 'restored': source['after'],
                       'mutated': source['mutated'], 'failed_testcases': failures(name),
                       'record': name + '/hashes.json', 'kind': source['kind']})
    return values


def combine_current():
    names = ('task1-current-inverse-evidence.json',
             'task2-fix1-current-inverse-evidence.json',
             'parent-query-current-inverse-evidence.json',
             'task3-fix1-current-inverse-evidence.json')
    values = []
    seen = set()
    for name in names:
        for value in json.loads((WORK / name).read_text()):
            assert value['run'] not in seen, value['run']
            seen.add(value['run'])
            for path, digest in value['restored'].items():
                assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
            assert failures(value['run']) == sorted(value['failed_testcases']), value['run']
            assert any(value['mutated'].get(path) != digest
                       for path, digest in value['restored'].items()), value['run']
            values.append(value)
    return values


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--task', type=int, choices=(1, 2), default=1)
    parser.add_argument('--fix', action='store_true')
    parser.add_argument('--parent', action='store_true')
    parser.add_argument('--combine', action='store_true')
    args = parser.parse_args()
    assert not args.fix or args.task == 2
    values = (combine_current() if args.combine else parent_queries() if args.parent else task1() if args.task == 1
              else task2_fix1() if args.fix else task2())
    with args.output.open('x') as output:
        json.dump(values, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps({'runs': len(values), 'failed': sum(len(v['failed_testcases']) for v in values)}))
