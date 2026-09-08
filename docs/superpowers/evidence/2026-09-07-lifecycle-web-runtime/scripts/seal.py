"""Create-only admission packet for four-channel Web execution and human review."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageStat

from verify import MUTATIONS, module


PACKET = Path(__file__).resolve().parent.parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-06-lifecycle-current-review"
parsers = module("previous_result_parsers", PRIOR / "scripts/seal.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_campaign(directory, kind):
    report = json.loads((directory / "report.json").read_text())
    assert report["complete"] and report["kind"] == kind
    assert [item["edit"] for item in report["mutations"]] == list(MUTATIONS[kind])
    source = directory.parent / "source"
    parse = parsers.backend_report if kind == "backend" else lambda path: parsers.frontend_report(path, source)
    extension = ".xml" if kind == "backend" else ".json"
    measured, nodes = {}, {}
    names = ("baseline", "restored", "integration", "backend") if kind == "backend" else ("baseline", "restored")
    for name in names:
        actual_name = report[name]["name"]
        assert actual_name == name or (kind == "frontend" and name == "restored"
                                      and actual_name.startswith("restored-recheck-")
                                      and actual_name.removeprefix("restored-recheck-").isdigit())
        measured[name], items = parse(directory / (actual_name + extension))
        assert report[name]["exit_code"] == 0 and report[name]["counts"] == measured[name]["counts"]
        assert not measured[name]["failed_nodes"] and not measured[name]["counts"]["errors"]
        nodes[name] = {"count": len(items), "nodes": items}
    assert nodes["baseline"] == nodes["restored"]
    for attempt in report.get("restored_attempts", []):
        assert kind == "frontend" and attempt["exit_code"] == 1
        value, items = parse(directory / (attempt["name"] + extension))
        assert value["counts"] == attempt["counts"] and value["failed_nodes"] == attempt["failed_nodes"]
        assert not value["counts"]["errors"] and items == nodes["baseline"]["nodes"]
    for item in report["mutations"]:
        value, items = parse(directory / (item["name"] + extension))
        assert item["exit_code"] == 1 and item["killed_by_owner"] and not item["counts"]["errors"]
        assert item["counts"] == value["counts"] and item["failed_nodes"] == value["failed_nodes"]
        assert items == nodes["baseline"]["nodes"]
        assert any(item["owner"] in node for node in item["failed_nodes"])
        assert item["restored_sha256"] == report["source_sha256"][item["edit"]["path"]]
    if kind == "backend":
        for item in [report["baseline"], *report["mutations"], report["restored"], report["integration"]]:
            expected_files = report["integration_files"] if item["name"] == "integration" else report["focus_files"]
            assert len(item["shards"]) == 4
            assert sorted(name for shard in item["shards"] for name in shard["files"]) == expected_files
            shard_nodes = []
            for shard in item["shards"]:
                value, items = parse(directory / (shard["name"] + ".xml"))
                assert value["counts"] == shard["counts"] and value["failed_nodes"] == shard["failed_nodes"]
                shard_nodes.extend(items)
            _, combined = parse(directory / (item["name"] + ".xml"))
            assert sorted(shard_nodes) == combined
    for name, expected in report["source_sha256"].items():
        assert digest(ROOT / name) == digest(source / name) == expected, name
    assert all(not (ROOT / name).exists() and not (source / name).exists() for name in report["deleted_files"])
    return report, measured, nodes


def historical_foundation(directory):
    report = json.loads((directory / "report.json").read_text())
    assert report["complete"] and report["scope"] == "offline_common_contract_and_source_reader_not_runtime_admission"
    results = {}
    for name, field in (("baseline", "baseline"), ("restored", "restored"), ("integration", "integration_result")):
        value, _ = parsers.backend_report(directory / (name + ".xml"))
        assert value["counts"] == report[field]["counts"] and report[field]["exit_code"] == 0
        results[name] = value
    for item in report["mutations"]:
        value, _ = parsers.backend_report(directory / (item["name"] + ".xml"))
        assert item["killed_by_owner"] and item["counts"] == value["counts"] and not item["counts"]["errors"]
        assert any(item["owner"] in node for node in value["failed_nodes"])
    assert all(digest(directory.parent / "source" / name) == expected for name, expected in report["source_sha256"].items())
    return {"scope": "historical_foundation_only_not_current_runtime_admission", "report": report, "measured": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--foundation", type=Path, required=True)
    parser.add_argument("--incremental", type=Path, action="append", default=[])
    parser.add_argument("--frontend-incremental", type=Path, action="append", default=[])
    parser.add_argument("--interrupted", type=Path, action="append", default=[])
    args = parser.parse_args()
    back, back_measured, back_nodes = validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"] and back["deleted_files"] == front["deleted_files"]
    changed = set()
    for command in (["git", "diff", "--name-only", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(name for name in subprocess.check_output(command, cwd=ROOT, text=True).split("\0")
                       if name and not name.startswith("docs/"))
    assert changed <= back["source_sha256"].keys() | set(back["deleted_files"])
    browser = json.loads((args.browser / "results.json").read_text())
    assert browser["complete"] and browser["provider_calls"] == 0 and not browser["production_app_started"]
    for name, expected in browser["source_sha256"].items():
        assert digest(ROOT / name) == expected, name
        if not name.startswith("docs/"):
            assert back["source_sha256"][name] == expected
    scenarios = (("start", "openai", "api_key"), ("start", "openai", "chatgpt_oauth"),
                 ("start", "anthropic", "api_key"), ("start", "anthropic", "claude_code_oauth"),
                 ("rename", "openai", "chatgpt_oauth"), ("blocked", "anthropic", "claude_code_oauth"),
                 ("cancel", "openai", "chatgpt_oauth"), ("changed", "openai", "api_key"),
                 ("unavailable", "anthropic", "claude_code_oauth"))
    expected_names = {f"{locale}-{width}-{scenario}-{provider}-{auth}" for locale in ("en", "zh-Hant")
                      for width in (1440, 390, 320) for scenario, provider, auth in scenarios}
    assert len(browser["scenarios"]) == len(expected_names) == 54
    assert {row["name"] for row in browser["scenarios"]} == expected_names
    screenshots = []
    for scenario in browser["scenarios"]:
        assert not scenario["unexpected_requests"] and not scenario["page_errors"]
        for phase, metrics in scenario["geometry"].items():
            assert not any(metrics.values())
            path = args.browser / f'{scenario["name"]}-{phase}.png'
            with Image.open(path) as picture:
                variance = max(ImageStat.Stat(picture).var)
            assert variance > 5 and variance == scenario["pixel_variance"][phase]
            screenshots.append(path)
    assert len(screenshots) == len(set(screenshots))
    assert set(screenshots) == set(args.browser.glob("*.png"))
    payloads = {name + "-nodes.json": value for name, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    changes = {}
    for kind in ("integration", "backend", "frontend"):
        old = set(json.loads((PRIOR / (kind + "-nodes.json")).read_text())["nodes"])
        new = set(payloads[kind + "-nodes.json"]["nodes"])
        assert not old - new, sorted(old - new)
        changes[kind] = {"added_count": len(new - old), "removed_count": 0, "added": sorted(new - old), "removed": []}
    prior_packets = {}
    for previous in (PRIOR, PACKET.parent / "2026-09-06-lifecycle-action-review", PACKET.parent / "2026-09-06-lifecycle-population-reconciliation"):
        manifest = json.loads((previous / "files.sha256.json").read_text())["files"]
        assert all(digest(previous / name) == expected for name, expected in manifest.items())
        prior_packets[previous.name] = {"seal_sha256": digest(previous / "files.sha256.json"), "files_verified": len(manifest)}
    old_sources = json.loads((PRIOR / "source-manifest.json").read_text())["files"]
    unchanged_schemas = {name: old_sources[name] for name in ("src/security_lifecycle_schema.py", "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")}
    assert all(digest(ROOT / name) == expected for name, expected in unchanged_schemas.items())
    payloads["historical-foundation.json"] = historical_foundation(args.foundation)
    incremental = {}
    initial_files = []
    for attempt in front.get("restored_attempts", []):
        path = args.frontend / (attempt["name"] + ".json")
        initial_files.append((path, "frontend-restored-failed-" + path.name))
    payloads["frontend-restored-history.json"] = {
        "scope": "same_source_full_suite_recheck_without_assertion_or_timeout_changes",
        "failed_attempts": front.get("restored_attempts", []), "final": front["restored"],
    }
    for index, directory in enumerate(args.incremental):
        for path in sorted(directory.glob("*.xml")):
            name = f"initial-{index}-{path.name}"
            value, _ = parsers.backend_report(path)
            incremental[name] = value
            initial_files.append((path, name))
    payloads["incremental-results.json"] = {
        "scope": "historical_incremental_red_green_not_final_source_admission", "files": incremental,
    }
    ui_initial = {}
    for path in args.frontend_incremental:
        name = "frontend-" + path.name
        value, _ = parsers.frontend_report(path, ROOT)
        ui_initial[name] = value
        initial_files.append((path, name))
    payloads["incremental-frontend-results.json"] = {
        "scope": "historical_incremental_red_green_not_final_source_admission", "files": ui_initial,
    }
    for index, directory in enumerate(args.interrupted):
        report = json.loads((directory / "report.json").read_text())
        assert report["complete"] is False
        assert all(digest(directory.parent / "source" / name) == expected
                   for name, expected in report["source_sha256"].items())
        payloads[f"interrupted-campaign-{index}.json"] = {
            "scope": "interrupted_not_final_admission", "report": report,
        }
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": result.returncode, "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    assert all(digest(ROOT / name) == expected for name, expected in back["source_sha256"].items())
    payloads.update({
        "backend-log.json": {"sha256": digest(args.backend / "backend.log"), "output": (args.backend / "backend.log").read_text()},
        "focus-files.json": {"files": back["focus_files"]}, "integration-files.json": {"files": back["integration_files"]},
        "mutation-results.json": {kind: {key: value[key] for key in ("baseline", "mutations", "restored")}
                                  for kind, value in (("backend", back), ("frontend", front))},
        "node-changes.json": changes, "browser-results.json": browser,
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "browser_scenarios": len(browser["scenarios"]), "browser_screenshots": len(screenshots),
            "source_files_verified": len(back["source_sha256"]), "prior_packets": prior_packets,
            "unchanged_existing_schemas": unchanged_schemas,
            "new_explicit_component_schema": "src/lifecycle_web_schema.py",
            "provider_calls": 0, "production_reads": False, "production_writes": False, "production_migration": False,
            "app_restart": False, "merge": False, "push": False,
            "complete_slice": "four_channel_web_investigation_and_attended_review_offline",
            "whole_workflow_complete": False, "remaining": ["authorized_web_journal_installation", "authorized_live_canaries", "existing_population_cutover", "merge_and_handtest"]},
    })
    sources = set(back["source_sha256"]) | {
        "docs/design/PROJECT_PRIORITY_MAP.md", "docs/design/ARKSCOPE_TOOL_CATALOG.md",
        "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-terminal-membership-completion.md",
    }
    sources.update(str(path.relative_to(ROOT)) for path in (PACKET / "scripts").iterdir() if path.is_file())
    payloads["source-manifest.json"] = {"base_commit": head, "files": {name: digest(ROOT / name) for name in sorted(sources)}, "deleted_files": back["deleted_files"]}
    assert not (PACKET / "files.sha256.json").exists() and not (PACKET / "screenshots").exists()
    assert not (PACKET / "incremental").exists()
    assert not any((PACKET / name).exists() for name in payloads)
    for name, value in payloads.items():
        with (PACKET / name).open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    (PACKET / "screenshots").mkdir()
    for path in screenshots:
        shutil.copy2(path, PACKET / "screenshots" / path.name)
    (PACKET / "incremental").mkdir()
    for path, name in initial_files:
        with path.open("rb") as source, (PACKET / "incremental" / name).open("xb") as target:
            shutil.copyfileobj(source, target)
    files = {str(path.relative_to(PACKET)): digest(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    with (PACKET / "files.sha256.json").open("x") as stream:
        json.dump({"algorithm": "sha256", "file_count": len(files), "files": files}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"backend": back_measured["backend"]["counts"], "frontend": front_measured["restored"]["counts"],
                      "browser_scenarios": len(browser["scenarios"]), "screenshots": len(screenshots),
                      "files": len(files), "seal_sha256": digest(PACKET / "files.sha256.json")}), flush=True)


if __name__ == "__main__":
    main()
