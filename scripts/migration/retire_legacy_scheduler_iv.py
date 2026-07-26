#!/usr/bin/env python3
"""Audited retirement of legacy scheduler identities and the old IV store."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


PRE_RETIREMENT_COMMIT = "7bb7cc29f70ca899a5b598f2322ce181daa17ebe"


@dataclass(frozen=True)
class RetirementPaths:
    profile_db: Path
    market_db: Path
    iv_parquet_dir: Path
    backup_root: Path


@dataclass(frozen=True)
class PreviewReport:
    preview_sha256: str
    pre_retirement_commit: str
    profile_targets: Mapping[str, object]
    market_targets: Mapping[str, object]
    parquet_targets: tuple[Mapping[str, object], ...]
    preserved_job_runs_sha256: str
    non_target_digests: Mapping[str, str]


class MigrationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def preview_retirement(
    paths: RetirementPaths,
    *,
    pre_retirement_commit: str = PRE_RETIREMENT_COMMIT,
) -> PreviewReport:
    del paths, pre_retirement_commit
    raise NotImplementedError("preview")


def create_archive(paths: RetirementPaths, preview: PreviewReport) -> Path:
    del paths, preview
    raise NotImplementedError("archive")


def verify_archive(archive_dir: Path) -> Mapping[str, object]:
    del archive_dir
    raise NotImplementedError("archive_verification")


def _after_phase_checkpoint(phase: str) -> None:
    del phase


def _git_head(repo_root: Path) -> str:
    del repo_root
    raise NotImplementedError("git_head")


def apply_retirement(
    paths: RetirementPaths,
    *,
    expected_preview_sha256: str,
    expected_pre_retirement_commit: str,
) -> Mapping[str, object]:
    del paths, expected_preview_sha256, expected_pre_retirement_commit
    raise NotImplementedError("apply")


def restore_retirement(
    archive_dir: Path,
    paths: RetirementPaths,
    *,
    repo_root: Path,
    expected_current_commit: str,
) -> Mapping[str, object]:
    del archive_dir, paths, repo_root, expected_current_commit
    raise NotImplementedError("restore")


def _paths_from_args(args: argparse.Namespace) -> RetirementPaths:
    return RetirementPaths(
        profile_db=Path(args.profile_db),
        market_db=Path(args.market_db),
        iv_parquet_dir=Path(args.iv_parquet_dir),
        backup_root=Path(getattr(args, "backup_root", ".")),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    for mode in ("preview", "apply"):
        command = subparsers.add_parser(mode)
        command.add_argument("--profile-db", required=True)
        command.add_argument("--market-db", required=True)
        command.add_argument("--iv-parquet-dir", required=True)
        command.add_argument("--backup-root", required=True)
        command.add_argument("--output", required=True)
        if mode == "apply":
            command.add_argument("--expected-preview-sha256", required=True)
            command.add_argument("--expected-pre-retirement-commit", required=True)

    restore = subparsers.add_parser("restore")
    restore.add_argument("--archive-dir", required=True)
    restore.add_argument("--profile-db", required=True)
    restore.add_argument("--market-db", required=True)
    restore.add_argument("--iv-parquet-dir", required=True)
    restore.add_argument("--repo-root", required=True)
    restore.add_argument("--expected-current-commit", required=True)
    restore.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode == "preview":
        preview_retirement(_paths_from_args(args))
    elif args.mode == "apply":
        apply_retirement(
            _paths_from_args(args),
            expected_preview_sha256=args.expected_preview_sha256,
            expected_pre_retirement_commit=args.expected_pre_retirement_commit,
        )
    else:
        restore_retirement(
            Path(args.archive_dir),
            RetirementPaths(
                profile_db=Path(args.profile_db),
                market_db=Path(args.market_db),
                iv_parquet_dir=Path(args.iv_parquet_dir),
                backup_root=Path(args.archive_dir).parent,
            ),
            repo_root=Path(args.repo_root),
            expected_current_commit=args.expected_current_commit,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
