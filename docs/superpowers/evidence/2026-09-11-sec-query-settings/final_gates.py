"""Bind completed frontend/browser checks to the post-review source identity."""

import hashlib
import json
import re

from verification import WORK, identity, save


def main():
    final = json.loads((WORK / 'source-final.json').read_text())
    assert identity() == final, 'source changed during post-fix checks'
    runs = {}
    for name, expected in (
        ('frontend-post-fix', 0), ('typecheck-post-fix', 0), ('i18n-post-fix', 0),
        ('browser-post-fix', 0), ('census-post-fix', 2),
    ):
        record = json.loads((WORK / name / 'command.json').read_text())
        assert record['exit_code'] == expected, name
        runs[name] = {
            'exit_code': record['exit_code'], 'seconds': record['seconds'],
            'command_sha256': hashlib.sha256((WORK / name / 'command.json').read_bytes()).hexdigest(),
            'log_sha256': hashlib.sha256((WORK / name / 'output.log').read_bytes()).hexdigest(),
        }
    output = (WORK / 'frontend-post-fix/output.log').read_text()
    plain = re.sub(r'\x1b\[[0-9;]*m', '', output)
    assert re.search(r'Test Files\s+121 passed\s+\(121\)', plain)
    assert re.search(r'Tests\s+1738 passed\s+\(1738\)', plain)
    browser = json.loads((WORK / 'browser-post-fix/browser/results.json').read_text())
    assert {(item['locale'], tuple(item['viewport'])) for item in browser} == {
        (locale, size) for locale in ('en', 'zh-Hant') for size in ((1280, 960), (390, 844))}
    for item in browser:
        assert not item['errors']
        conflict = item['conflict_pagination']
        assert len(conflict['first_rows']) == 20 and len(conflict['next_rows']) == 1
        assert not conflict['duplicate_key_warnings']
        assert len(item['requests']) == 33 and len(item['state']['source_dispatches']) == 10
        assert all(rect['contained'] for rect in item['pagination_geometry'])
    census = json.loads((WORK / 'census-post-fix/reconciliation.json').read_text())
    assert census['comparison_counts']['review_required'] is True
    assert all(census['comparison_counts'][name] == 0 for name in (
        'coverage_reductions', 'dependency_metadata_changed', 'new_untracked_paths'))
    summary = {
        'source_patch_sha256': final['patch_sha256'],
        'source_paths_verified': len(final['paths']),
        'frontend': {'files': 121, 'passed': 1738, 'baseline_passed': 1692, 'added': 46},
        'browser_cases': len(browser), 'runs': runs,
        'backend_evidence': 'verification-summary.json',
        'backend_reuse_proof': 'post-fix-verification.json',
        'census': {'candidates': census['candidate_count'], 'uncertainties': census['uncertainty_count'],
                   'comparison': census['comparison_counts']},
    }
    save(WORK / 'final-gates.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
