"""Exclusive preview artifacts for attended database maintenance commands."""

import json
import os
from pathlib import Path
from typing import Callable, Sequence


def write_operator_preview(path: Path, *, inputs: Sequence[Path], build: Callable[[], dict]) -> dict:
    if path.resolve() in {source.resolve() for source in inputs}:
        raise ValueError("installation_output_alias")
    # Preserve prior approvals before reading stores; exclusive create rechecks races.
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    value = build()
    payload = json.dumps(value, ensure_ascii=True, indent=2) + "\n"
    created = None
    try:
        with path.open("x", encoding="utf-8") as output:
            info = os.fstat(output.fileno())
            created = (info.st_dev, info.st_ino)
            output.write(payload)
    except BaseException:
        if created is not None:
            try:
                current = path.lstat()
                if (current.st_dev, current.st_ino) == created:
                    path.unlink()
            except FileNotFoundError:
                pass
        raise
    return value
