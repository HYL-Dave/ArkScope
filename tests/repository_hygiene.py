"""Reject repository-local artifacts in staged changes or the entire index.

Run from anywhere in the repository. Exit codes: 0 clean, 1 forbidden paths,
2 unable to inspect Git. Only the Python standard library and Git are required.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


FORBIDDEN_ROOTS = (b".superpowers", b"docs/superpowers/evidence", b"data/verification")


def git_output(*args: str, cwd: str | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
    ).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-tracked",
        action="store_true",
        help="check every currently tracked path, not just staged changes",
    )
    options = parser.parse_args(argv)

    try:
        root = os.fsdecode(git_output("rev-parse", "--show-toplevel").removesuffix(b"\n"))
        if options.all_tracked:
            paths = git_output("ls-files", "--cached", "--full-name", "-z", cwd=root)
        else:
            # An unborn branch has no revision. An explicit HEAD otherwise keeps
            # Git from silently treating a dangling HEAD object as an empty tree.
            base = ["HEAD"] if git_output("rev-parse", "--revs-only", "HEAD", cwd=root) else []
            # Check rename/copy destinations as additions, never deleted sources.
            paths = git_output(
                "diff", "--cached", "--name-only", "--diff-filter=ACMRT",
                "--no-renames", "--no-ext-diff", "--no-relative", "-z", *base, "--",
                cwd=root,
            )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="backslashreplace").strip()
        print(
            f"Repository hygiene: git command failed (exit {exc.returncode}): {detail}",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"Repository hygiene: unable to run git: {exc}", file=sys.stderr)
        return 2

    forbidden = sorted({
        path for path in paths.split(b"\0")
        if any(path == root or path.startswith(root + b"/") for root in FORBIDDEN_ROOTS)
    })
    if not forbidden:
        return 0

    scope = "tracked files" if options.all_tracked else "staged changes"
    print(f"Repository hygiene: forbidden artifacts in {scope}:", file=sys.stderr)
    for path in forbidden:
        # Escape control characters and undecodable bytes in diagnostic filenames.
        print(f"  {os.fsdecode(path)!a}", file=sys.stderr)
    print(
        "Keep these artifacts local and untracked; remove them from the index before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
