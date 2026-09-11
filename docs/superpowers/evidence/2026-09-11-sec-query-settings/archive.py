"""Publish only named verification artifacts, excluding all disposable stores."""

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
DEST = ROOT / 'docs/superpowers/evidence/2026-09-11-sec-query-settings'


def selected():
    for path in WORK.iterdir():
        if path.is_file() and path.suffix in {'.md', '.py', '.cjs', '.mjs', '.json', '.gz', '.txt'}:
            yield path
    for folder in WORK.iterdir():
        if not folder.is_dir() or folder.name.startswith('vite-'):
            continue
        for name in ('output.log', 'results.xml', 'command.json', 'responses.json', 'hashes.json', 'census.json.gz', 'reconciliation.json'):
            if (folder / name).is_file():
                yield folder / name
        if folder.name in {'task-1', 'task-2', 'task-4', 'task-1-review-probe', 'task-3-review-probe', 'task-3-examples'}:
            for path in folder.iterdir():
                if path.is_file() and path.suffix in {'.py', '.log', '.xml', '.json', '.md'}:
                    yield path
                if path.is_dir():
                    for name in ('output.log', 'results.xml', 'command.json', 'hashes.json'):
                        if (path / name).is_file():
                            yield path / name
                    if path.name == 'mutants':
                        yield from path.glob('*.py')
        if (folder / 'browser').is_dir():
            for path in (folder / 'browser').iterdir():
                if path.is_file() and path.suffix in {'.png', '.json'}:
                    yield path
        elif folder.name.startswith('browser-'):
            for path in folder.iterdir():
                if path.is_file() and path.suffix in {'.png', '.json'}:
                    yield path


def main():
    DEST.mkdir(exist_ok=False)
    manifest = {}
    for path in sorted(set(selected())):
        relative = path.relative_to(WORK)
        body = path.read_bytes()
        compress = path.suffix in {'.log', '.xml', '.txt'} or (
            path.suffix == '.json' and len(body) > 100000)
        target = DEST / (str(relative) + '.gz' if compress else relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(body, mtime=0) if compress else body)
        manifest[str(target.relative_to(DEST))] = {
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'source_sha256': hashlib.sha256(body).hexdigest(), 'source_bytes': len(body),
        }
    nodes = WORK / 'final-collect/output.log'
    target = DEST / 'final-nodes.txt.gz'
    body = nodes.read_bytes()
    target.write_bytes(gzip.compress(body, mtime=0))
    manifest[target.name] = {'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                             'source_sha256': hashlib.sha256(body).hexdigest(), 'source_bytes': len(body)}
    (DEST / 'artifact-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'destination': str(DEST), 'artifacts': len(manifest)}))


if __name__ == '__main__':
    main()
