"""Source-only return-policy inventory. Does not import or execute product code."""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
registry = ROOT / "src/tools/registry.py"
tree = ast.parse(registry.read_text())
rows = []
for method in ast.walk(tree):
    if not isinstance(method, ast.FunctionDef) or not method.name.startswith("_register_"):
        continue
    imports = {}
    for node in ast.walk(method):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            module = f"src.tools.{module}" if node.level == 1 else module
            for alias in node.names:
                imports[alias.asname or alias.name] = (module, alias.name)
    for node in ast.walk(method):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "ToolDefinition"):
            continue
        fields = {field.arg: field.value for field in node.keywords}
        name = ast.literal_eval(fields["name"])
        symbol = ast.unparse(fields["function"])
        source = imports.get(symbol)
        row = {"name": name, "symbol": symbol, "registry_line": node.lineno}
        if source:
            path = Path(*source[0].split(".")).with_suffix(".py")
            row["source"] = path.as_posix()
            if (ROOT / path).is_file():
                source_tree = ast.parse((ROOT / path).read_text())
                functions = [f for f in source_tree.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == source[1]]
                if functions:
                    function = functions[0]
                    row["source_line"] = function.lineno
                    row["annotation"] = ast.unparse(function.returns) if function.returns else None
                    row["return_shapes"] = sorted({type(r.value).__name__ for r in ast.walk(function) if isinstance(r, ast.Return)})
        rows.append(row)

result = json.dumps({"registered": len(rows), "tools": sorted(rows, key=lambda r: r["name"])}, indent=2) + "\n"
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path)
options = parser.parse_args()
if options.output:
    with options.output.open("x") as stream:
        stream.write(result)
else:
    print(result, end="")
