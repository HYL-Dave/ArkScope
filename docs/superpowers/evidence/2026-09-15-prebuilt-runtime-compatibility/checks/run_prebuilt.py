"""Reuse archived behavioral probes without the superseded loader identity check."""

import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import synthetic_probe as probe


def main():
    version, source_id = probe.sql_identity()
    assert version == '3.53.1'
    assert source_id == '2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9'
    print(json.dumps({'version': version, 'source_id': source_id,
                      'python': sys.executable}), flush=True)
    root = probe.ROOT / 'data'
    root.mkdir(exist_ok=False)
    results = []
    for case in (
        probe.json_decimal_text, probe.fts_external_content, probe.foreign_keys,
        probe.transactions, probe.wal_locking, probe.wal_concurrency,
        probe.backup_uncheckpointed_wal, probe.posix_process_lock,
    ):
        try:
            result = {'test': case.__name__, 'status': 'pass', 'details': case(root)}
        except Exception:
            result = {'test': case.__name__, 'status': 'fail', 'traceback': traceback.format_exc()}
        results.append(result)
        print(json.dumps(result), flush=True)
    assert all(row['status'] == 'pass' for row in results)


if __name__ == '__main__':
    main()
