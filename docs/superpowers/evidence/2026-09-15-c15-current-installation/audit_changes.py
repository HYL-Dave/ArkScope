"""Read-only, stdlib-only source and sealed-evidence preservation audit."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[4]
BASELINE = "9bb80725238947c351e0257765c9b53280e67569"
LISTING = "src/security_lifecycle_listing_migration.py"
PROVIDER = "src/security_lifecycle_provider_migration.py"
HELPERS = "src/lifecycle_investigation/sqlite_helpers.py"
INSTALLATION = "src/sa_tracking_installation.py"
RENAMES = {
    "preflight_provider_upgrade": "inspect_installation",
    "upgrade_provider_authority": "_install_memberships",
    "_cutover_preview": "_installation_preview",
    "preview_provider_cutover": "preview_installation",
    "apply_provider_cutover": "apply_installation",
}
PRESERVED = (
    "src/security_lifecycle_schema.py",
    "src/ticker_identity_schema.py",
    "src/sa_tracking_memberships.py",
    "src/lifecycle_investigation/__main__.py",
    "tests/test_lifecycle_investigation_migration.py",
    "tests/test_lifecycle_investigation_retirement.py",
    "tests/test_lifecycle_investigation_cli.py",
    "tests/test_sqlite_backup.py",
)
SEALED = (
    "docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/run_mutations.py",
    "docs/superpowers/evidence/2026-08-28-lifecycle-listing-authority/capture_offline_authority.py",
    "docs/superpowers/evidence/2026-09-05-lifecycle-terminal-cutover/scripts/fresh_check_v2.py",
    "docs/superpowers/evidence/2026-09-05-lifecycle-terminal-cutover/scripts/fresh_check_v1.py",
    "docs/superpowers/evidence/2026-09-05-lifecycle-terminal-cutover/scripts/install.py",
    "docs/superpowers/evidence/2026-09-08-lifecycle-investigation/completion-r1/source/src/lifecycle_investigation/migration.py",
    "docs/superpowers/evidence/2026-09-08-lifecycle-investigation/completion-r1/source/src/lifecycle_investigation/disposal.py",
)


def historical(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)


class NormalizeOwnership(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        if node.module == "src.security_lifecycle_listing_migration":
            node.module = "src.lifecycle_investigation.sqlite_helpers"
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name = RENAMES.get(node.name, node.name)
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            node.body.pop(0)
        return node

    def visit_Name(self, node):
        node.id = RENAMES.get(node.id, node.id)
        return node


def normalized(source, function=None):
    node = ast.parse(source)
    if function:
        node = next(item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == function)
    return ast.dump(NormalizeOwnership().visit(node), include_attributes=False)


def main():
    equivalent = []
    for old_path, new_path, old_name in (
        (LISTING, HELPERS, "_sha_file"),
        (LISTING, HELPERS, "_quote_identifier"),
        (LISTING, HELPERS, "_encode_cell"),
        (PROVIDER, INSTALLATION, "_automation_settings"),
        (PROVIDER, INSTALLATION, "_digest"),
        (PROVIDER, INSTALLATION, "_cutover_preview"),
        (PROVIDER, INSTALLATION, "preview_provider_cutover"),
        (PROVIDER, INSTALLATION, "apply_provider_cutover"),
    ):
        new_name = RENAMES.get(old_name, old_name)
        assert normalized(historical(old_path), old_name) == normalized((ROOT / new_path).read_bytes(), new_name)
        equivalent.append(f"{old_path}:{old_name} -> {new_path}:{new_name}")
    for path in ("src/lifecycle_investigation/migration.py", "src/lifecycle_investigation/disposal.py"):
        assert normalized(historical(path)) == normalized((ROOT / path).read_bytes())
        equivalent.append(f"{path}: whole module, helper import change only")
    hashes = {}
    for path in (*PRESERVED, *SEALED):
        current = (ROOT / path).read_bytes()
        assert current == historical(path), path
        hashes[path] = hashlib.sha256(current).hexdigest()
    for path in (LISTING, PROVIDER):
        assert not (ROOT / path).exists()
    retired = {LISTING.removesuffix(".py").replace("/", "."), PROVIDER.removesuffix(".py").replace("/", ".")}
    imports = []
    installers = []
    for folder in ("src", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_bytes())):
                if isinstance(node, ast.Import):
                    imports.extend(str(path.relative_to(ROOT)) for item in node.names if item.name in retired)
                elif isinstance(node, ast.ImportFrom):
                    targets = {node.module, *(f"{node.module}.{item.name}" for item in node.names)}
                    if targets & retired:
                        imports.append(str(path.relative_to(ROOT)))
                elif (folder == "src" and isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == "install"
                      and isinstance(node.func.value, ast.Name) and node.func.value.id == "SaTrackingMembershipStore"):
                    installers.append(str(path.relative_to(ROOT)))
    assert imports == []
    assert installers == [INSTALLATION]
    current = ast.parse((ROOT / INSTALLATION).read_bytes())
    entry = current.body[-1]
    assert isinstance(entry, ast.If)
    assert ast.unparse(entry.test) == "__name__ == '__main__'"
    assert ast.unparse(entry.body[0]) == "main()"
    print(json.dumps({
        "baseline": BASELINE,
        "ast_equivalent_after_owner_renames_and_docstrings": equivalent,
        "byte_identical_sha256": hashes,
        "sealed_scripts_replay_revision": BASELINE,
        "historical_scripts_executed": False,
        "current_retired_imports": imports,
        "non_test_membership_install_callers": installers,
        "current_operator_entrypoint": "python -m src.sa_tracking_installation",
        "current_operator_commands": ["inspect", "install-preview", "install"],
        "retired_runtime_modules": [LISTING, PROVIDER],
        "retired_converter_test_consumers": [
            "tests/test_security_lifecycle_listing_migration.py",
            "tests/test_security_lifecycle_provider_migration.py",
        ],
        "retained_current_consumer_paths": [
            "src/lifecycle_investigation/migration.py",
            "src/lifecycle_investigation/disposal.py",
            "src/lifecycle_investigation/__main__.py",
            "src/sa_tracking_installation.py",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
