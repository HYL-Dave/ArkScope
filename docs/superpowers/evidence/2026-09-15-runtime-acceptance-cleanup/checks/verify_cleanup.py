"""Reproduce the bounded removal/retained-owner checks without product imports."""

import ast
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = "b3385a31"
MODULES = (
    "security_lifecycle_migration",
    "security_lifecycle_automation_migration",
    "ticker_identity_migration",
)


def blob(path):
    return subprocess.run(["git", "show", f"{BASE}:{path}"], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode()


old = ast.parse(blob("tests/test_security_lifecycle_migration.py"))
new = ast.parse((ROOT / "tests/test_security_lifecycle_schema.py").read_text())
identical = {}
for name in ("_new_observation", "test_incomplete_receipt_blocks_all_lifecycle_writes"):
    before = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name)
    after = next(node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == name)
    identical[name] = ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)

removed = {str(Path(folder) / f"{prefix}{name}.py"):
           not (ROOT / folder / f"{prefix}{name}.py").exists()
           for name in MODULES for folder, prefix in (("src", ""), ("tests", "test_"))}
guard = (ROOT / "tests/test_abandoned_surface_cleanup.py").read_text()
absence_owners = all(f'"src/{name}.py"' in guard for name in MODULES)
scan = subprocess.run(["git", "grep", "-n", "-E", "|".join(MODULES), "--",
                       "src", "data_sources", "tests", "apps", "resources"],
                      cwd=ROOT, capture_output=True, text=True)
assert scan.returncode in (0, 1), scan.stderr
unexpected = [line for line in scan.stdout.splitlines()
              if not line.startswith("tests/test_abandoned_surface_cleanup.py:")
              and "security_lifecycle_migration_receipts" not in line
              and "security_lifecycle_migration_incomplete" not in line
              and "security_lifecycle_migration_keys" not in line]
protected = (
    "src/security_lifecycle_schema.py", "src/ticker_identity_schema.py",
    "src/ticker_identity_transition.py", "src/sqlite_backup.py",
    "src/lifecycle_investigation/migration.py", "src/lifecycle_investigation/disposal.py",
    "tests/test_security_lifecycle_manual_evidence.py",
    "tests/test_security_lifecycle_automation_schema.py",
    "tests/test_ticker_identity_transition.py",
)
unchanged = {path: (ROOT / path).read_text() == blob(path) for path in protected}
result = {"baseline": BASE, "removed_files": removed, "absence_owners": absence_owners,
          "retained_owner_ast_identical": identical, "protected_sources_unchanged": unchanged,
          "remaining_product_test_matches": scan.stdout.splitlines(),
          "unexpected_matches": unexpected, "production_data_accessed": False}
print(json.dumps(result, sort_keys=True, indent=2))
assert all(removed.values()) and absence_owners and all(identical.values())
assert all(unchanged.values()) and not unexpected
