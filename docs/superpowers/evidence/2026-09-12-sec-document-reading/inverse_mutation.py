"""Opt-in process-local source inverses; never edit another worker's files."""

import hashlib
import importlib
import json
import os
from pathlib import Path


def pytest_addoption(parser):
    parser.addoption('--sec-inverse', choices=('pin', 'filter'))


def pytest_configure(config):
    choice = config.getoption('--sec-inverse')
    if not choice:
        return
    module = importlib.import_module('src.sec_research.document_queries')
    root = Path(module.__file__).resolve().parents[2]
    source_path = 'src/sec_research/document_queries.py'
    owner_path = 'tests/test_sec_research_document_queries.py'
    before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
              for path in (source_path, owner_path)}
    source = (root / source_path).read_text()
    old, new = (
        ('        if capture_id is None:\n', '        if True:\n')
        if choice == 'pin' else
        ('or token["filters_hash"] != _filters(section_id, query, max_chars)', 'or False'))
    assert source.count(old) == 1, 'mutation target drifted'
    mutated = source.replace(old, new, 1)
    run = Path(os.environ['ARKSCOPE_OFFLINE_TEST_WORKSPACE'])
    (run / 'mutation.py').write_text(mutated)
    snapshot = dict(module.__dict__)
    exec(compile(mutated, str(run / 'mutation.py'), 'exec'), module.__dict__)
    config._sec_inverse = module, snapshot, root, run, {
        'kind': 'process_local_compiled_source', 'choice': choice,
        'before': before, 'mutated': dict(before, **{
            source_path: hashlib.sha256(mutated.encode()).hexdigest()}),
        'disk_source_modified': False,
    }


def pytest_sessionfinish(session):
    state = getattr(session.config, '_sec_inverse', None)
    if state is None:
        return
    module, snapshot, root, run, evidence = state
    module.__dict__.clear()
    module.__dict__.update(snapshot)
    evidence['after'] = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                         for path in evidence['before']}
    assert evidence['after'] == evidence['before'], 'disk source changed during inverse'
    (run / 'hashes.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
