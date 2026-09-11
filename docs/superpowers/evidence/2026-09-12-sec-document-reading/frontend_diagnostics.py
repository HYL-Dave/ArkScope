"""Compare emitted warning lines, not every occurrence of 'act' in stack traces."""

from collections import Counter
import gzip
import json
from pathlib import Path
import re
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
BASE = ROOT / 'docs/superpowers/evidence/2026-09-11-sec-query-settings/frontend-post-fix/output.log.gz'


def warnings(text):
    plain = re.sub(r'\x1b\[[0-9;]*m', '', text)
    return Counter(line for line in plain.splitlines() if line.startswith('Warning:'))


if __name__ == '__main__':
    current = WORK / sys.argv[1] / 'output.log'
    baseline = warnings(gzip.decompress(BASE.read_bytes()).decode())
    observed = warnings(current.read_text())
    result = {'baseline': str(BASE.relative_to(ROOT)), 'current': str(current.relative_to(WORK)),
              'baseline_warning_lines': sum(baseline.values()),
              'current_warning_lines': sum(observed.values()),
              'baseline_messages': baseline, 'current_messages': observed,
              'new_warning_lines': observed - baseline, 'removed_warning_lines': baseline - observed,
              'same_warning_multiset': baseline == observed}
    with (WORK / sys.argv[2]).open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps(result, indent=2))
