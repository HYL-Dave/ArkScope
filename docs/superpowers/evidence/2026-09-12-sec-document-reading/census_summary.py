"""Reconcile scanner observations without treating candidates as deletions."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def semantic(row):
    return json.dumps({key: value for key, value in row.items()
                       if key not in {'id', 'line', 'column'}}, sort_keys=True)


def main(name):
    previous = read(ROOT / 'docs/superpowers/evidence/2026-09-11-sec-query-settings/census-post-fix/census.json.gz')
    current = read(WORK / name / 'census.json.gz')
    comparison = current['comparison']
    old_candidates = {item['id'] for item in previous['candidates']}
    new_candidates = {item['id'] for item in current['candidates']}
    ids = set(comparison['new_uncertainties'])
    added = [item for item in current['uncertainties'] if item['id'] in ids]
    old_semantics = Counter(semantic(item) for item in previous['uncertainties'])
    added_semantics = Counter(semantic(item) for item in added)
    matching = sum((old_semantics & added_semantics).values())
    result = {
        'status': current['status'],
        'coverage': current['coverage'],
        'candidate_count': len(current['candidates']),
        'uncertainty_count': len(current['uncertainties']),
        'comparison_counts': {key: len(value) if isinstance(value, list) else value
                              for key, value in comparison.items()},
        'new_candidate_kinds': dict(Counter(item.split(':')[0] for item in comparison['new_candidates'])),
        'new_uncertainty_kinds': dict(Counter(item['id'].split(':')[0] for item in added)),
        'new_uncertainty_ids_with_matching_previous_location_independent_metadata': matching,
        'removed_candidates': sorted(old_candidates - new_candidates),
        'sec_routes': [{key: row[key] for key in ('method', 'path_template', 'state')}
                       for row in current['http']['routes'] if row['path'] == 'src/api/routes/sec_research.py'],
        'interpretation': 'Raw scanner candidates retained; runtime consumers require independent evidence.',
    }
    with (WORK / name / 'reconciliation.json').open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(sys.argv[1])
