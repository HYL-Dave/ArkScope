"""Create-only C11 source hashes and exact collected-node replacement ledger."""
import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASE = "eec66b9e129eb3383c1c6b136f6d10953a3568f8"
PRODUCT = [
    "src/news_providers.py", "src/news_normalized/routing.py", "src/api/routes/news.py",
    "src/news_sync_status.py", "src/service/provider_health.py", "src/news_direct.py",
    "apps/arkscope-web/src/api.ts", "apps/arkscope-web/src/marketDataDisplay.ts",
    "apps/arkscope-web/src/i18n/resources/en/settings.ts",
    "apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts",
]
TESTS = [
    "tests/test_news_settings_route.py", "tests/test_news_providers.py",
    "tests/test_news_normalized_routing.py", "tests/test_news_sync_status.py",
    "tests/test_provider_health.py", "tests/test_data_coverage_tools.py",
    "tests/test_stored_sec_projection.py", "tests/test_market_data_admin.py",
    "tests/test_data_scheduler.py", "tests/test_security_lifecycle_routes.py",
    "tests/test_news_routing_cleanup.py", "tests/test_api.py",
    "apps/arkscope-web/src/SettingsNewsStorage.test.ts",
    "apps/arkscope-web/src/SettingsLocalStorage.test.ts",
    "apps/arkscope-web/src/marketDataDisplay.test.ts",
    "apps/arkscope-web/src/i18n/resources.test.ts",
]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    with path.open("x") as out:
        json.dump(data, out, indent=2, sort_keys=True)
        out.write("\n")
    print(path.relative_to(ROOT))


def snapshot(name):
    product = {path: digest((ROOT / path).read_bytes()) for path in PRODUCT}
    data = {
        "base": BASE, "head": git("rev-parse", "HEAD").decode().strip(),
        "product": product,
        "product_collection_sha256": digest(json.dumps(product, sort_keys=True).encode()),
        "tests": {path: digest((ROOT / path).read_bytes()) for path in TESTS},
        "runners": {path: digest((WORK / path).read_bytes()) for path in
                    ("run_checks.py", "offline_pytest.py", "offline_node.cjs")},
    }
    with (WORK / f"{name}.diff").open("xb") as out:
        out.write(git("diff", "--no-ext-diff", BASE, "--", *PRODUCT))
    write_json(WORK / f"{name}.json", data)


def collected(name):
    return {line for line in (WORK / name / "output.log").read_text().splitlines()
            if line.startswith("tests/") and "::" in line}


def routes(source):
    rows = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router"):
                    rows.append((dec.func.attr.upper(), "/news" + ast.literal_eval(dec.args[0]), node.name))
    return sorted(rows)


def ledger():
    before = collected("task2-collect-before") | collected("task2-collect-api-before")
    after = collected("task2-collect-after")
    removed = sorted(before - after)
    added = sorted(after - before)
    renames = {
        "test_status_reports_explicit_and_env_rollback": "test_status_reports_current_normalized_environment_override",
        "test_status_and_http_409_after_completed_audit_marker": "test_status_selects_direct_writer_when_normalized_writes_are_disabled",
        "test_read_news_write_route_blocks_malformed_stored_exit_marker": "test_read_news_write_route_blocks_malformed_current_normalized_setting",
        "test_status_news_sync_follows_active_writer_only": "test_status_uses_current_news_sync_and_preserves_price_authority",
        "test_ticker_coverage_news_sync_follows_active_writer_only": "test_ticker_coverage_uses_current_news_sync_and_preserves_prices",
        "test_fundamentals_sync_is_null_while_price_and_news_remain_unchanged": "test_fundamentals_sync_is_null_with_price_and_current_news_telemetry",
        "test_run_source_news_direct_when_use_local_news_on": "test_run_source_news_direct_when_normalized_writes_unset",
        "test_direct_news_health_uses_provider_runs_and_current_ticker_errors": "test_direct_news_health_uses_provider_runs_and_current_ticker_errors[",
    }
    transferred = []
    for node in removed:
        leaf = node.split("::")[-1]
        if leaf.startswith("test_route_matrix["):
            required, normalized, _old, mode = leaf.removeprefix("test_route_matrix[").removesuffix("]").split("-")
            prefixes = [f"test_route_matrix[{required}-{normalized}-{mode}]"]
            reason = "Collapse only obsolete local-toggle dimension; persisted no-effect coverage is separate."
        elif leaf in renames:
            prefixes = [renames[leaf]]
            reason = "Transfer useful assertions to accurately named current authority/real telemetry owner."
        elif leaf == "test_put_settings_persists_explicit_rollback":
            prefixes = ["test_obsolete_put_is_unmounted_and_returns_405_without_writing",
                        "test_normalized_setter_denies_before_writing_and_preserves_old_key",
                        "test_normalized_setter_writes_only_current_key"]
            reason = "Retire obsolete write endpoint; retain current permission/write-only-key contract."
        elif leaf.startswith("test_use_local_news_") or leaf == "test_local_environment_value_overrides_profile_value":
            prefixes = ["test_current_writer_ignores_obsolete_profile_and_environment[",
                        "test_obsolete_helpers_and_resolver_parameters_are_physically_removed"]
            reason = "Retire rollback semantics; real stored/environment values are inert and helpers absent."
        else:
            raise ValueError(f"Unaccounted removed node: {node}")
        owners = sorted(n for n in after if any(n.split("::")[-1].startswith(p) for p in prefixes))
        if not owners:
            raise ValueError(f"Missing replacement for {node}")
        transferred.append({"removed": node, "replacement_owners": owners, "reason": reason})
    old_routes = routes(git("show", f"{BASE}:src/api/routes/news.py").decode())
    new_routes = routes((ROOT / "src/api/routes/news.py").read_text())
    data = {
        "before_count": len(before), "after_count": len(after),
        "unchanged_count": len(before & after), "removed_count": len(removed), "added_count": len(added),
        "removed": transferred, "added": added,
        "before_nodes": sorted(before), "after_nodes": sorted(after),
        "news_routes_before": old_routes, "news_routes_after": new_routes,
        "route_removals": sorted(set(old_routes) - set(new_routes)),
        "route_additions": sorted(set(new_routes) - set(old_routes)),
    }
    write_json(WORK / "task2-node-ledger.json", data)
    with (WORK / "task2-node-ledger.md").open("x") as out:
        out.write(f"# C11 Backend Node Ledger\n\n{len(before)} before, {len(after)} after; "
                  f"{len(before & after)} unchanged, {len(removed)} removed, {len(added)} added.\n\n")
        out.write("## Removed and Replacement Owners\n\n")
        for entry in transferred:
            out.write(f"### `{entry['removed']}`\n\n{entry['reason']}\n\n")
            for owner in entry["replacement_owners"]:
                out.write(f"- `{owner}`\n")
            out.write("\n")
        out.write("## Added Nodes\n\n")
        for node in added:
            out.write(f"- `{node}`\n")
    print(json.dumps({k: v for k, v in data.items() if k.endswith("_count")}))


def receipts():
    rows = []
    for folder in sorted(WORK.glob("task2-*")):
        if not folder.is_dir() or folder.is_symlink() or not (folder / "output.log").exists():
            continue
        command = json.loads((folder / "command.json").read_text())
        row = {"run": folder.name, "command": command}
        if (folder / "results.xml").exists():
            counts = Counter()
            for case in ET.parse(folder / "results.xml").findall(".//testcase"):
                state = next((tag for tag in ("failure", "error", "skipped") if case.find(tag) is not None), "passed")
                counts[state] += 1
            row["outcomes"] = dict(counts)
        rows.append(row)
    write_json(WORK / "task2-run-accounting.json", rows)


def audit():
    reviewed = json.loads((WORK / "task2-reviewed-before-inverse.json").read_text())
    scans = []
    pattern = ("USE_LOCAL_NEWS|use_local_news|local_value|local_env|LocalNewsToggle|"
               "set_local_news|setUseLocalNews|newsRoutingLabel|direct_active|"
               "directEnvOn|directEnvOff|localCompatibility|directExplicit|directDefault")
    commands = [
        ["rg", "-n", pattern, "src", "apps/arkscope-web/src", "-g", "*.py", "-g", "*.ts",
         "-g", "*.tsx", "-g", "!*.test.ts", "-g", "!*.test.tsx"],
        ["rg", "-n", "USE_LOCAL_NEWS|use_local_news|/news/settings|newsRoutingLabel|setUseLocalNews",
         "docs", "README.md", "-g", "*.md", "-g", "!**/superpowers/**", "-g", "!**/history/**",
         "-g", "!**/archive/**", "-g", "!ENGINEERING_ISSUE_REGISTER.md", "-g", "!PROJECT_PRIORITY_MAP.md"],
    ]
    for cmd in commands:
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        scans.append({"command": cmd, "exit_code": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == 1 and not result.stdout and not result.stderr
    restored = {}
    for name in ("task2-restored-validation-source", "task2-restored-telemetry-source"):
        restored[name] = json.loads((WORK / f"{name}.json").read_text()) == reviewed
    assert all(restored.values())
    for group in ("product", "tests"):
        assert all(digest((ROOT / path).read_bytes()) == expected for path, expected in reviewed[group].items())
    inverses = {}
    for name, expected in [
        ("task2-inverse-validation-source", {"src/news_normalized/routing.py"}),
        ("task2-inverse-telemetry-source", {"src/news_sync_status.py", "src/service/provider_health.py"}),
    ]:
        record = json.loads((WORK / f"{name}.json").read_text())
        changed = {path for path, value in record["product"].items() if reviewed["product"][path] != value}
        assert changed == expected
        assert record["tests"] == reviewed["tests"] and record["runners"] == reviewed["runners"]
        inverses[name] = sorted(changed)
    changed = set(git("diff", "--name-only", "--", "src", "tests", "apps").decode().splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard", "--", "src", "tests", "apps").decode().splitlines())
    assert changed == set(PRODUCT + TESTS)
    assert not git("diff", "--cached", "--name-only").strip()
    git("diff", "--check")
    processes = []
    output = subprocess.run(["ps", "-eo", "pid,ppid,comm,args"], capture_output=True, text=True, check=True).stdout
    for line in output.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) != 4 or int(parts[0]) == os.getpid():
            continue
        if not any(name in parts[2] for name in ("python", "node", "npm", "pytest", "vitest")):
            continue
        try:
            cwd = Path(f"/proc/{parts[0]}/cwd").resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if cwd == ROOT or ROOT in cwd.parents:
            processes.append({"pid": int(parts[0]), "command": parts[3], "cwd": str(cwd)})
    assert not processes, processes
    write_json(WORK / "task2-source-audit.json", {
        "source_scans": scans, "restored_hashes_equal": restored,
        "independent_mutation_files": inverses, "changed_product_test_paths": sorted(changed),
        "staged_files": [], "diff_check": "passed", "remaining_worktree_test_server_processes": processes,
        "product_collection_sha256": reviewed["product_collection_sha256"],
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("snapshot", "ledger", "receipts", "audit"))
    parser.add_argument("name", nargs="?")
    args = parser.parse_args()
    if args.mode == "snapshot":
        snapshot(args.name)
    elif args.mode == "ledger":
        ledger()
    elif args.mode == "receipts":
        receipts()
    else:
        audit()
