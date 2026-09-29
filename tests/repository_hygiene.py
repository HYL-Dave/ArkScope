"""Reject repository-local artifacts in the index or proposed Git history.

Run from anywhere in the repository. Exit codes: 0 clean, 1 forbidden paths,
2 unable to inspect Git. Only the Python standard library and Git are required.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys


FORBIDDEN_ROOTS = (b".superpowers", b"docs/superpowers/evidence", b"data/verification")


def git_output(*args: str, cwd: str | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
    ).stdout


def pre_push_tips(lines: list[str]) -> list[str]:
    tips = []
    for line in lines:
        fields = line.split()
        if len(fields) != 4 or any(
            re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is None
            for value in (fields[1], fields[3])
        ):
            raise ValueError("invalid pre-push input")
        if set(fields[1]) != {"0"}:
            tips.append(fields[1])
    return tips


def check_history(root: str, refs: list[str]) -> int:
    if not refs:
        return 0
    if git_output("rev-parse", "--is-shallow-repository", cwd=root).strip() != b"false":
        raise ValueError("cannot verify shallow history; fetch complete history first")
    # Replacement objects must not hide the ancestry that a push would publish.
    tips = sorted({
        git_output("--no-replace-objects", "rev-parse", "--verify", "--end-of-options",
                   ref + "^{commit}", cwd=root).strip().decode("ascii")
        for ref in refs
    })
    paths = [":(top,literal)" + path.decode("ascii") for path in FORBIDDEN_ROOTS]
    found = git_output(
        "--no-replace-objects", "log", "--full-history", "--format=%H", "--max-count=1",
        *tips, "--", *paths, cwd=root,
    ).strip()
    if not found:
        return 0
    print(
        "Repository hygiene: forbidden artifacts in proposed history at "
        + found.decode("ascii") + ".", file=sys.stderr,
    )
    print("Use the cleaned history; deleting files only at the tip does not remove ancestors.",
          file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--all-tracked",
        action="store_true",
        help="check every currently tracked path, not just staged changes",
    )
    modes.add_argument("--history-ref", action="append", metavar="REF",
                       help="verify full ancestry of each specified commit or commit tag")
    modes.add_argument("--pre-push", action="store_true",
                       help="check every nondeleted tip from Git pre-push standard input")
    options = parser.parse_args(argv)

    try:
        root = os.fsdecode(git_output("rev-parse", "--show-toplevel").removesuffix(b"\n"))
        if options.history_ref is not None or options.pre_push:
            refs = pre_push_tips(sys.stdin.read().splitlines()) if options.pre_push else options.history_ref
            return check_history(root, refs)
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
    except ValueError as exc:
        print(f"Repository hygiene: {exc}", file=sys.stderr)
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
