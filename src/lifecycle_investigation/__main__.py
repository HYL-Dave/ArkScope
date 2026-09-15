"""Explicit operator commands. No default database path, provider IO, or app restart."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from src.operator_preview import write_operator_preview
from src.lifecycle_investigation.disposal import preview_disposal, apply_disposal_stage
from src.lifecycle_investigation.migration import preview_installation, apply_installation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("install-preview", "install", "disposal-preview", "disposal-stage"):
        item = commands.add_parser(name)
        item.add_argument("--profile", required=True, type=Path)
        if name.startswith("disposal"):
            item.add_argument("--market", required=True, type=Path)
        if name.endswith("preview"):
            item.add_argument("--output", required=True, type=Path)
        else:
            item.add_argument("--approval-sha256", required=True)
            item.add_argument("--backup", required=True, type=Path)
            item.add_argument("--app-stopped", action="store_true", required=True)
        if name == "disposal-stage":
            item.add_argument("--manifest", required=True, type=Path)
            item.add_argument("--stage", choices=("profile", "market"), required=True)
    args = parser.parse_args(argv)
    if args.command.endswith("preview"):
        inputs = [args.profile] if args.command == "install-preview" else [args.profile, args.market]
        value = write_operator_preview(args.output, inputs=inputs,
            build=lambda: preview_installation(args.profile) if args.command == "install-preview" else preview_disposal(args.market, args.profile))
    elif args.command == "install":
        value = apply_installation(args.profile, backup_path=args.backup, approval_sha256=args.approval_sha256,
            at=datetime.now(timezone.utc).isoformat(), app_stopped=args.app_stopped)
    else:
        plan = json.loads(args.manifest.read_text(encoding="utf-8"))
        value = apply_disposal_stage(args.profile if args.stage == "profile" else args.market, plan,
            stage=args.stage, approval_sha256=args.approval_sha256, backup_path=args.backup, app_stopped=args.app_stopped, profile_path=args.profile)
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))
    return value


if __name__ == "__main__":
    main()
