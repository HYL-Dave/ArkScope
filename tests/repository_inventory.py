"""Repeatable source-only maintenance inventory; findings are review candidates.

Run with ``python -m tests.repository_inventory --root . --output report.json``.
No application modules, private configuration, untracked contents or real DBs
are loaded. Installed distribution metadata is observed, not imported code.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from tests.repository_sql_inventory import sql_inventory


def classify_path(path):
    parts = PurePosixPath(path).parts
    if not parts or any(part == ".." for part in parts) or path.startswith("/"):
        return "excluded_path"
    if parts[0] in {"data", "config"} or any(
        part == ".env" or part.startswith(".env.")
        or part.endswith((".local.yaml", ".local.yml", ".local.json", ".local.toml")) for part in parts
    ):
        return "excluded_private"
    if any(part in {"node_modules", ".git", "__pycache__", "dist", "target"} for part in parts):
        return "excluded_dependency"
    if parts[0] == "docs":
        return "excluded_evidence" if "evidence" in parts else "documentation"
    if path.endswith(".py"):
        return "python"
    if path.endswith((".ts", ".tsx", ".js", ".mjs", ".cjs", ".css")) or parts[-1] in {"package.json", "tsconfig.json"}:
        return "frontend"
    if path == "requirements.txt":
        return "requirements"
    if path.endswith((".md", ".json", ".toml", ".yaml", ".yml", ".html", ".rs", ".sql", ".sh", ".ps1", ".bat")):
        return "entrypoint_or_data_definition"
    return "excluded_non_source"


def read_sources(root, paths):
    root = Path(root).resolve()
    files, manifest = {}, []
    for name in sorted(set(paths)):
        kind = classify_path(name)
        row = {"path": name, "kind": kind, "status": kind}
        if kind.startswith("excluded") or kind == "documentation":
            manifest.append(row)
            continue
        path = root / name
        if any(part.is_symlink() for part in [path, *path.parents] if part != root):
            row["status"] = "symlink_not_read"
        elif not path.is_file():
            row["status"] = "tracked_file_missing"
        else:
            raw = path.read_bytes()
            row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            try:
                files[name] = raw.decode("utf-8")
                row["status"] = "read"
            except UnicodeDecodeError:
                row["status"] = "decode_failed"
        manifest.append(row)
    return files, manifest


def module_name(path):
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def literal(node, constants):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [literal(item, constants) for item in node.elts]
    if isinstance(node, ast.Dict):
        if any(key is None or not isinstance(literal(key, constants), (str, int)) for key in node.keys):
            return None
        return {literal(key, constants): literal(value, constants)
                for key, value in zip(node.keys, node.values) if key is not None
                and isinstance(literal(key, constants), (str, int))}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = literal(node.left, constants), literal(node.right, constants)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    return None


def sql_literal(node, constants, helpers):
    """Resolve closed string expressions, never execute a source expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and isinstance(constants.get(node.id), str):
        return constants[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = sql_literal(node.left, constants, helpers)
        right = sql_literal(node.right, constants, helpers)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                if part.conversion != -1 or part.format_spec is not None:
                    return None
                part = part.value
            value = sql_literal(part, constants, helpers)
            if value is None:
                return None
            parts.append(value)
        return "".join(parts)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in helpers and len(node.args) == 1 and not node.keywords
            and isinstance(node.args[0], ast.Name)):
        values = constants.get(node.args[0].id)
        if isinstance(values, frozenset) and all(isinstance(value, str) for value in values):
            return ", ".join("'" + value + "'" for value in sorted(values))
    return None


def sql_literal_contexts(tree):
    # This deliberately recognizes one exact pure helper idiom, not arbitrary
    # Python functions. Rebinding or shadowing falls back to dynamic SQL.
    expected = ast.dump(ast.parse('''
def quoted(values):
    return ", ".join(f"'{value}'" for value in sorted(values))
''').body[0].body[0])
    constants, helpers, bound, contexts = {}, set(), set(), {}
    for node in tree.body:
        # Module assignments evaluate eagerly. Keep the context at that point,
        # not the last version of a schema enum rebound later in the module.
        contexts[node] = (dict(constants), set(helpers))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = {node.name}
        else:
            names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name)
                     and isinstance(item.ctx, (ast.Store, ast.Del))}
            for item in ast.walk(node):
                if isinstance(item, (ast.Import, ast.ImportFrom)):
                    names.update(alias.asname or alias.name.split(".")[0] for alias in item.names)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(item.name)
                elif isinstance(item, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)) and item.name:
                    names.add(item.name)
                elif isinstance(item, ast.MatchMapping) and item.rest:
                    names.add(item.rest)
        if "*" in names:
            constants.clear()
            helpers.clear()
            bound.update({"sorted", "frozenset"})
        previous = dict(constants)
        for name in names:
            constants.pop(name, None)
            helpers.discard(name)
        if "sorted" in names:
            helpers.clear()
        bound.update(names)
        if isinstance(node, ast.FunctionDef) and "sorted" not in bound:
            args = node.args
            if (not node.decorator_list and len(args.args) == 1 and args.args[0].arg == "values"
                    and not (args.posonlyargs or args.kwonlyargs or args.defaults
                             or args.kw_defaults or args.vararg or args.kwarg)
                    and len(node.body) == 1 and ast.dump(node.body[0]) == expected):
                helpers.add(node.name)
        if (not isinstance(node, ast.Assign) or len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)):
            continue
        target, value = node.targets[0], node.value
        if ("frozenset" not in bound and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name) and value.func.id == "frozenset"
                and len(value.args) == 1 and not value.keywords
                and isinstance(value.args[0], (ast.Set, ast.Tuple, ast.List))
                and all(isinstance(item, ast.Constant) and isinstance(item.value, str)
                        for item in value.args[0].elts)):
            constants[target.id] = frozenset(item.value for item in value.args[0].elts)
        else:
            resolved = sql_literal(value, previous, contexts[node][1])
            if resolved is not None:
                constants[target.id] = resolved
    return contexts


def python_inventory(files):
    sources = {name: text for name, text in sorted(files.items()) if name.endswith(".py")}
    paths = {module_name(name): name for name in sources}
    inbound, strings = defaultdict(set), defaultdict(set)
    unresolved, errors, external, sql_sites, routes = [], [], [], [], []
    settings = defaultdict(lambda: {"reads": [], "writes": []})
    dynamic_settings, entrypoints, edges = [], {}, set()
    parsed = 0
    sql_sink_counts = Counter()
    top_modules = {name.split(".")[0] for name in paths}

    def edge(source, target):
        if target in paths and source != target:
            inbound[target].add(source)
            edges.add((source, target))
        parts = target.split(".")
        for size in range(1, len(parts)):
            parent = ".".join(parts[:size])
            if parent in paths and parent != source:
                inbound[parent].add(source)
                edges.add((source, parent))

    for path, source in sources.items():
        module = module_name(path)
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            errors.append({"path": path, "line": exc.lineno, "kind": "python_parse_failed"})
            continue
        parsed += 1
        constants, router_prefix = {}, {}
        sql_contexts = sql_literal_contexts(tree)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        scope_types = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

        def enclosing_scope(node):
            cursor = parents.get(node)
            while cursor is not None and not isinstance(cursor, scope_types):
                cursor = parents.get(cursor)
            return cursor

        aliases_by_scope = defaultdict(dict)
        locals_by_scope = {}
        for scope in ast.walk(tree):
            if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                locals_by_scope[scope] = {item.id for item in ast.walk(scope) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)} | {
                    item.arg for item in ast.walk(scope.args) if isinstance(item, ast.arg)}

        def scoped_literal(node):
            scoped = dict(constants)
            cursor = node
            while cursor in parents:
                cursor = parents[cursor]
                for name in locals_by_scope.get(cursor, ()):
                    scoped.pop(name, None)
            return literal(node, scoped)

        def scoped_sql_literal(node):
            cursor = node
            while cursor in parents and parents[cursor] is not tree:
                if isinstance(cursor, (ast.Lambda, ast.GeneratorExp, ast.ListComp,
                                       ast.SetComp, ast.DictComp)):
                    return None
                cursor = parents[cursor]
            if not isinstance(cursor, ast.Assign):
                return None
            if any(isinstance(item, ast.NamedExpr) for item in ast.walk(cursor.value)):
                return None
            sql_constants, sql_helpers = sql_contexts[cursor]
            return sql_literal(node, sql_constants, sql_helpers)

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        value = literal(node.value, constants)
                        if value is not None:
                            constants[target.id] = value
                        if isinstance(node.value, ast.Call) and ast.unparse(node.value.func).endswith(("APIRouter", "FastAPI")):
                            router_prefix[target.id] = next((literal(k.value, constants) for k in node.value.keywords if k.arg == "prefix"), "")
        bindings = Counter(node.id for node in ast.walk(tree)
                           if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                           and enclosing_scope(node) is tree)
        for name, count in bindings.items():
            if count > 1:
                constants.pop(name, None)
        for node in ast.walk(tree):
            aliases = aliases_by_scope[enclosing_scope(node)]
            if isinstance(node, ast.Import):
                for item in node.names:
                    aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
            if isinstance(node, ast.ImportFrom) and not node.level:
                for item in node.names:
                    aliases[item.asname or item.name] = f"{node.module}.{item.name}"

        def resolved_call(node, first, tail):
            scope = enclosing_scope(node)
            while scope is not None:
                if first in locals_by_scope.get(scope, ()):
                    return ".".join(["<unresolved>", *tail])
                if first in aliases_by_scope[scope]:
                    return ".".join([aliases_by_scope[scope][first], *tail])
                scope = enclosing_scope(scope)
            return ".".join([first, *tail])

        if path.endswith("/__main__.py"):
            entrypoints[module] = "module_main"
        elif any(isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)
                 and "__main__" in ast.unparse(n.test) for n in tree.body):
            entrypoints[module] = "main_guard"

        for node in ast.walk(tree):
            where = {"path": path, "line": getattr(node, "lineno", 1)}
            if isinstance(node, ast.Import):
                for item in node.names:
                    edge(module, item.name)
                    if item.name.split(".")[0] not in top_modules:
                        external.append({**where, "name": item.name.split(".")[0]})
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    package = module.split(".") if path.endswith("/__init__.py") else module.split(".")[:-1]
                    if node.level > len(package):
                        unresolved.append({**where, "kind": "relative_import_outside_known_package"})
                        continue
                    base = ".".join(package[:len(package) - node.level + 1] + ([base] if base else []))
                edge(module, base)
                for item in node.names:
                    edge(module, f"{base}.{item.name}")
                    if item.name == "*":
                        unresolved.append({**where, "kind": "star_import"})
                if not node.level and base.split(".")[0] not in top_modules:
                    external.append({**where, "name": base.split(".")[0]})
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in paths and module != node.value:
                    strings[node.value].add(module)
                if not path.startswith("tests/") and not isinstance(parents.get(node), ast.JoinedStr) and re.match(r"\s*(?:CREATE|SELECT|WITH|INSERT|REPLACE|UPDATE|DELETE|ALTER|DROP)\s", node.value, re.I):
                    sql_sites.append({**where, "text": node.value, "dynamic": False})
            elif isinstance(node, ast.JoinedStr) and not path.startswith("tests/"):
                prefix = "".join(n.value for n in node.values if isinstance(n, ast.Constant) and isinstance(n.value, str))
                if re.match(r"\s*(?:CREATE|SELECT|WITH|INSERT|REPLACE|UPDATE|DELETE|ALTER|DROP)\s", prefix, re.I):
                    resolved = scoped_sql_literal(node)
                    sql_sites.append({**where, "text": prefix if resolved is None else resolved,
                                      "dynamic": resolved is None, "origin": "sql_expression"})
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                first, *tail = name.split(".")
                resolved = resolved_call(node, first, tail)
                if resolved in {"importlib.import_module", "__import__"}:
                    target = scoped_literal(node.args[0]) if node.args else None
                    if isinstance(target, str) and not target.startswith("."):
                        edge(module, target)
                        if target.split(".")[0] not in top_modules:
                            external.append({**where, "name": target.split(".")[0]})
                    else:
                        unresolved.append({**where, "kind": "dynamic_import"})
                elif name.endswith("import_module"):
                    unresolved.append({**where, "kind": "unresolved_dynamic_import_receiver"})
                elif name.endswith(("spec_from_file_location", "entry_points")):
                    unresolved.append({**where, "kind": "dynamic_loader"})
                method = name.split(".")[-1]
                if method in {"execute", "executemany", "executescript"} and not path.startswith("tests/"):
                    sql_sink_counts["calls"] += 1
                    value = scoped_literal(node.args[0]) if node.args else None
                    dynamic = not isinstance(value, str)
                    sql_sink_counts["dynamic" if dynamic else "literal"] += 1
                    sql_sites.append({**where, "text": value if isinstance(value, str) else "",
                                      "dynamic": dynamic, "origin": "sql_call"})
                if method in {"get_setting", "get_settings_snapshot", "set_setting", "update_settings"} and not path.startswith("tests/"):
                    value = scoped_literal(node.args[0]) if node.args else None
                    keys = list(value) if isinstance(value, (list, dict)) else [value]
                    operation = "writes" if method in {"set_setting", "update_settings"} else "reads"
                    for key in keys:
                        if isinstance(key, str):
                            settings[key][operation].append({**where, "accessor": name})
                        else:
                            dynamic_settings.append({**where, "accessor": name, "operation": operation})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                        continue
                    method = decorator.func.attr.upper()
                    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "WEBSOCKET", "API_ROUTE"}:
                        continue
                    router = ast.unparse(decorator.func.value)
                    value = literal(decorator.args[0], constants) if decorator.args else None
                    prefix = router_prefix.get(router, "")
                    if isinstance(value, str) and isinstance(prefix, str):
                        routes.append({**where, "method": method, "path_template": prefix + value,
                                       "handler": node.name, "mount_resolution": "router_local"})
                    else:
                        unresolved.append({**where, "kind": "dynamic_http_route"})

    launch = defaultdict(list)
    for path, source in sorted(files.items()):
        if path.startswith("tests/") or path.endswith(".md"):
            continue
        # Positive lexical witnesses only; this does not prove a launcher executes.
        for match in re.finditer(r'''["']([A-Za-z_][\w.]*)(?::[A-Za-z_][\w.]*)?["']''', source):
            for target in (match.group(1), match.group(1) + ".__main__"):
                if target in paths and paths[target] != path:
                    launch[target].append({"path": path, "line": source.count("\n", 0, match.start()) + 1,
                                           "kind": "literal_module_witness_not_execution_proof"})
    rows = []
    for module, path in sorted(paths.items()):
        runtime = sorted(n for n in inbound[module] if not paths[n].startswith("tests/"))
        tests = sorted(n for n in inbound[module] if paths[n].startswith("tests/"))
        runtime_strings = [name for name in strings[module] if not paths[name].startswith("tests/")]
        state = "runtime_imported" if runtime else "string_reference" if runtime_strings else "test_only" if tests or strings[module] else "no_inbound_reference"
        rows.append({"module": module, "path": path, "runtime_importers": runtime, "test_importers": tests,
                     "string_referrers": sorted(strings[module]), "reference_state": state,
                     "entrypoint_kind": entrypoints.get(module), "launch_witnesses": launch[module],
                     "deletion_authorized": False})
    return {"modules": rows, "edges": [list(edge) for edge in sorted(edges)],
            "external_imports": external, "parse_errors": errors, "unresolved": unresolved,
            "sql_sites": sql_sites, "sql_sink_coverage": dict(sql_sink_counts), "routes": routes,
            "settings": {"keys": [{"key": key, **value,
                "state": "reader_observed" if value["reads"] else "no_literal_reader_observed",
                "deletion_authorized": False} for key, value in sorted(settings.items())],
                "dynamic_accesses": dynamic_settings},
            "coverage": {"python_files": len(sources), "parsed_python_files": parsed},
            "limitations": ["module edges are not whole-program call reachability",
                            "dynamic dispatch and external operator use require review",
                            "settings accessor names do not establish database/receiver identity"]}


def dependency_inventory(requirements_text, imports, observed):
    requirements, invalid = [], []
    for number, line in enumerate(requirements_text.splitlines(), 1):
        line = line.partition("#")[0].strip()
        if not line:
            continue
        try:
            requirements.append(Requirement(line))
        except Exception:
            invalid.append({"line": number, "kind": "unparsed_requirement"})
    distributions = {canonicalize_name(name): value for name, value in observed["distributions"].items()}
    direct = defaultdict(list)
    for item in imports:
        for name in observed["packages"].get(item["name"], []):
            direct[canonicalize_name(name)].append(item)
    required_by = defaultdict(set)
    dependency_edges = {}
    for name, row in distributions.items():
        dependency_edges[name] = []
        for raw in row.get("requires", []):
            try:
                req = Requirement(raw)
                target = canonicalize_name(req.name)
                dependency_edges[name].append(target)
                required_by[target].add(name)
            except Exception:
                invalid.append({"name": name, "kind": "unparsed_dependency_metadata"})
    reachable = set(direct)
    pending = list(reachable)
    while pending:
        for child in dependency_edges.get(pending.pop(), []):
            if child not in reachable:
                reachable.add(child)
                pending.append(child)
    rows = []
    for req in requirements:
        name = canonicalize_name(req.name)
        if name not in distributions:
            invalid.append({"name": name, "kind": "dependency_metadata_unavailable"})
        state = "direct_import" if direct[name] else "transitive_requirement" if name in reachable else "metadata_unavailable" if name not in distributions else "no_observed_import_or_dependency"
        rows.append({"name": name, "declaration": str(req), "state": state,
                     "imports": direct[name], "required_by": sorted(required_by[name] & reachable),
                     "installed": distributions.get(name), "deletion_authorized": False})
    return {"requirements": rows, "unresolved": invalid,
            "limitations": ["installed metadata is environment-specific", "conditional extras retained conservatively",
                            "CLI/data/tooling usage must also be checked before deleting a declaration"]}


def package_roots(record_paths):
    roots = set()
    for raw in record_paths:
        path = PurePosixPath(str(raw))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            continue
        if path.suffix not in {".py", ".pyi", ".so", ".pyd"}:
            continue
        name = path.parts[0] if len(path.parts) > 1 else path.name.split(".")[0]
        if name.isidentifier():
            roots.add(name)
    return roots


def installed_metadata():
    distributions = {}
    packages = defaultdict(set, {name: set(values) for name, values in metadata.packages_distributions().items()})
    for item in metadata.distributions():
        name = item.metadata.get("Name")
        if name:
            distributions[canonicalize_name(name)] = {"version": item.version, "requires": item.requires or []}
            # Some wheels omit top_level.txt; RECORD still identifies their packages.
            for package in package_roots(item.files or []):
                packages[package].add(name)
    return {"packages": {key: sorted(values) for key, values in sorted(packages.items())},
            "distributions": distributions}


def compare_reports(before, after):
    def difference(key):
        return sorted({row["id"] for row in after.get(key, [])} - {row["id"] for row in before.get(key, [])})
    candidates, uncertainties = difference("candidates"), difference("uncertainties")
    observed = {row["path"] for row in after.get("source_manifest", []) if row["status"] == "read"}
    reductions = sorted(row["path"] for row in before.get("source_manifest", [])
                        if row["status"] == "read" and row["path"] not in observed)
    new_untracked = sorted(set(after.get("untracked", {}).get("paths", []))
                           - set(before.get("untracked", {}).get("paths", [])))
    def dependency_state(report):
        return {row["name"]: row.get("installed")
                for row in report.get("python_dependencies", {}).get("requirements", [])}
    old_deps, new_deps = dependency_state(before), dependency_state(after)
    changed_deps = sorted(name for name in old_deps.keys() | new_deps.keys()
                          if old_deps.get(name) != new_deps.get(name))
    return {"new_candidates": candidates, "new_uncertainties": uncertainties,
            "coverage_reductions": reductions,
            "new_untracked_paths": new_untracked, "dependency_metadata_changed": changed_deps,
            "review_required": bool(candidates or uncertainties or reductions or new_untracked or changed_deps)}


def write_report(path, payload):
    raw = (json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()
    if path.suffix == ".gz":
        raw = gzip.compress(raw, mtime=0)
    with path.open("xb") as stream:
        stream.write(raw)


def read_report(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def git_names(root, *arguments):
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", *arguments],
                            check=True, capture_output=True)
    return sorted(set(result.stdout.decode().split("\0")) - {""})


def candidate_rows(python, dependencies, sql):
    rows = []
    for row in python["modules"]:
        if row["path"].startswith("tests/") or row["path"].endswith("/__init__.py"):
            continue
        if row["reference_state"] in {"test_only", "no_inbound_reference", "string_reference"}:
            rows.append({"id": f"python:{row['module']}", "kind": row["reference_state"],
                         "path": row["path"], "entrypoint_kind": row["entrypoint_kind"]})
    for row in dependencies["requirements"]:
        if row["state"] == "no_observed_import_or_dependency":
            rows.append({"id": f"dependency:{row['name']}", "kind": row["state"]})
    for row in python["settings"]["keys"]:
        if not row["reads"]:
            rows.append({"id": f"setting:{row['key']}", "kind": row["state"]})
    for row in sql["tables"]:
        if row.get("sqlite_table_kind") == "shadow":
            continue
        if not row["reads"]:
            rows.append({"id": f"table:{row['table']}", "kind": row["state"]})
        for column in row["columns_without_observed_read"]:
            rows.append({"id": f"column:{row['table']}.{column}", "kind": "no_static_column_read"})
    return sorted(rows, key=lambda row: row["id"])


def frontend_candidates(frontend):
    rows = []
    for axis, group, key, identity_keys in (
        ("npm", "dependencies", "candidates", ("file", "package", "section")),
        ("i18n", "i18n", "keys", ("file", "locale", "namespace", "key")),
        ("css", "css", "selectors", ("file", "selector")),
    ):
        for row in frontend.get(group, {}).get(key, []):
            if row["status"] not in {"unresolved", "no-static-reference"}:
                continue
            identity = ":".join(str(row.get(field, "")) for field in identity_keys)
            rows.append({"id": f"{axis}:{identity}", "kind": row["status"],
                         "path": row["file"], "line": row["line"], "deletion_authorized": False})
    return rows


def http_inventory(routes, references):
    def shape(path):
        if not isinstance(path, str) or not path.startswith("/"):
            return None
        return re.sub(r"\{[^{}]*\}", "{}", re.sub(r"\$\{[^{}]*\}", "{}", path)).split("?", 1)[0]

    rows = []
    for route in routes:
        matches = [row for row in references if row.get("method") == route["method"]
                   and shape(row.get("url")) == shape(route["path_template"])]
        rows.append({**route, "frontend_references": matches,
                     "state": "syntactic_frontend_match" if matches else "no_frontend_match_observed",
                     "deletion_authorized": False})
    return {"routes": rows, "limitations": [
        "router-local shapes only; mounts, dynamic clients and external/API consumers need review",
        "a frontend match is not proof that a route is live; its absence does not authorize removal"]}


def scan_uncertainties(python, sql, dependencies, frontend, manifest):
    rows = []
    axes = [
        ("python", python.get("unresolved", []) + python.get("parse_errors", [])),
        ("settings", python.get("settings", {}).get("dynamic_accesses", [])),
        ("sql", sql.get("unresolved", [])), ("dependencies", dependencies.get("unresolved", [])),
        ("frontend", frontend.get("unresolved", []) + frontend.get("coverage", {}).get("parseErrors", [])),
        ("source", [row for row in manifest if row["status"] in {
            "decode_failed", "tracked_file_missing", "symlink_not_read"}]),
    ]
    if frontend.get("status") == "not_run":
        axes.append(("frontend", [{"kind": "frontend_not_run"}]))
    for axis, items in axes:
        for item in items:
            identity = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]
            rows.append({"id": f"{axis}:{identity}", "axis": axis, **item})
    return sorted({row["id"]: row for row in rows}.values(), key=lambda row: row["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--untracked-root", type=Path)
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    files, manifest = read_sources(root, git_names(root))
    python = python_inventory(files)
    sql = sql_inventory(python.pop("sql_sites"))
    dependencies = dependency_inventory(files.get("requirements.txt", ""), python["external_imports"], installed_metadata())
    frontend = {"status": "not_run", "reason": "explicit_skip"}
    if not args.skip_frontend:
        tool = root / "apps/arkscope-web/scripts/maintenance/frontend-inventory.mjs"
        process = subprocess.run(["node", str(tool)], input=json.dumps(files), text=True,
                                 capture_output=True, check=True, timeout=120)
        frontend = json.loads(process.stdout)
    candidates = candidate_rows(python, dependencies, sql)
    http = http_inventory(python["routes"], frontend.get("http", {}).get("references", []))
    candidates += frontend_candidates(frontend)
    candidates += [{"id": f"http:{row['method']}:{row['path_template']}:{row['path']}",
                    "kind": row["state"], "path": row["path"], "line": row["line"]}
                   for row in http["routes"] if not row["frontend_references"]]
    candidates.sort(key=lambda row: row["id"])
    uncertainties = scan_uncertainties(python, sql, dependencies, frontend, manifest)
    excluded = Counter(row["status"] for row in manifest)
    payload = {"format": 1, "status": "review_required_not_a_deletion_list",
               "source_manifest": manifest,
               "source_digest": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
               "coverage": dict(sorted(excluded.items())), "python": python, "sql": sql,
               "python_dependencies": dependencies, "frontend": frontend, "http": http,
               "candidates": candidates, "uncertainties": uncertainties,
               "untracked": {"paths": git_names(args.untracked_root or root, "--others", "--exclude-standard"),
                             "contents_read": False, "ignored_private_files": "not_enumerated"}}
    if args.compare:
        payload["comparison"] = compare_reports(read_report(args.compare), payload)
    # Reports are generated artifacts; never overwrite a previous observation.
    write_report(args.output, payload)
    print(json.dumps({"output": str(args.output), "coverage": payload["coverage"],
                      "candidates": len(candidates), "uncertainties": len(uncertainties)}, sort_keys=True))
    return 2 if payload.get("comparison", {}).get("review_required") else 0


if __name__ == "__main__":
    raise SystemExit(main())
