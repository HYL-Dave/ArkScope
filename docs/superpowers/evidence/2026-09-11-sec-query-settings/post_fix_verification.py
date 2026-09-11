"""Certify an explicit frontend-only delta after the completed backend freeze."""

import hashlib
import json
from pathlib import Path

from verification import WORK, identity, save

ALLOWED = {
    'apps/arkscope-web/src/settings/SecResearchPanel.tsx',
    'apps/arkscope-web/src/settings/SecResearchPanel.test.tsx',
}


def main():
    before = json.loads((WORK / 'source-before.json').read_text())
    current = identity()
    assert before['paths'].keys() == current['paths'].keys(), 'source file set changed'
    changed = {path for path in before['paths'] if before['paths'][path] != current['paths'][path]}
    assert changed == ALLOWED, changed
    backend = [path for path in before['paths'] if not path.startswith('apps/arkscope-web/')]
    assert all(before['paths'][path] == current['paths'][path] for path in backend)
    backend_result = json.loads((WORK / 'verification-summary.json').read_text())
    assert backend_result['counts'] == {'passed': 8811, 'skipped': 12}
    assert backend_result['source_patch_sha256'] == before['patch_sha256']
    summary = {
        'backend_checkpoint': 'verification-summary.json',
        'backend_checkpoint_sha256': hashlib.sha256((WORK / 'verification-summary.json').read_bytes()).hexdigest(),
        'backend_counts': backend_result['counts'],
        'backend_paths_unchanged': len(backend),
        'full_source_paths': len(current['paths']),
        'changed_paths': sorted(changed),
        'before_patch_sha256': before['patch_sha256'],
        'final_patch_sha256': current['patch_sha256'],
        'changes': {path: {'before': before['paths'][path], 'after': current['paths'][path]} for path in sorted(changed)},
        'backend_rerun_after_frontend_only_fix': False,
    }
    save(WORK / 'source-final.json', current)
    save(WORK / 'post-fix-verification.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
