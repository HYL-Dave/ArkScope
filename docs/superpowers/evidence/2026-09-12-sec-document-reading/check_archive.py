"""Verify published evidence bytes and their exact Git-index counterparts."""

import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from archive import DEST, ROOT


def main():
    manifest = json.loads((DEST / 'artifact-manifest.json').read_text())
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z', '--', str(DEST.relative_to(ROOT))], cwd=ROOT
    ).decode().rstrip('\0').split('\0'))
    for name, expected in manifest.items():
        path = DEST / name
        body = path.read_bytes()
        assert hashlib.sha256(body).hexdigest() == expected['sha256'], name
        decoded = body
        if hashlib.sha256(decoded).hexdigest() != expected['source_sha256']:
            decoded = gzip.decompress(body)
        assert hashlib.sha256(decoded).hexdigest() == expected['source_sha256'], name
        assert len(decoded) == expected['source_bytes'], name
        relative = str(path.relative_to(ROOT))
        assert relative in tracked, ('not tracked', relative)
        staged = subprocess.check_output(['git', 'show', ':' + relative], cwd=ROOT)
        assert body == staged, ('index differs', relative)
    actual = {str(path.relative_to(DEST)) for path in DEST.rglob('*') if path.is_file()}
    assert actual == set(manifest) | {'artifact-manifest.json'}, 'unmanifested evidence'
    print(json.dumps({'verified_artifacts': len(manifest),
                      'all_evidence_bytes_tracked': True, 'unmanifested_files': 0}))


if __name__ == '__main__':
    main()
