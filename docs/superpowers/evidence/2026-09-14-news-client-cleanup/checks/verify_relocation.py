"""Compare retained client definitions against the pre-C12 immutable source."""

import ast
import copy
import json
from pathlib import Path
import subprocess

BASE = "8c64f884"


def definitions(text):
    return {node.name: node for node in ast.parse(text).body if hasattr(node, "name")}


class StripDocstrings(ast.NodeTransformer):
    def generic_visit(self, node):
        super().generic_visit(node)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr):
                value = node.body[0].value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    node.body = node.body[1:]
        return node


def normalized(node):
    return ast.dump(StripDocstrings().visit(copy.deepcopy(node)), include_attributes=False)


def main():
    comparisons = []
    for source, config, limiter, client, fetch in (
        ("polygon", "CollectionConfig", "RateLimiter", "PolygonNewsCollector", "fetch_news_range"),
        ("finnhub", "FinnhubConfig", "FinnhubRateLimiter", "FinnhubNewsCollector", "fetch_news"),
    ):
        old = definitions(subprocess.check_output([
            "git", "show", f"{BASE}:src/collectors/{source}_news.py",
        ], text=True))
        new = definitions(Path(f"src/news_clients/{source}.py").read_text())
        for name in ("NewsArticle", limiter, "load_env"):
            comparisons.append({"source": source, "definition": name,
                                "same": normalized(old[name]) == normalized(new[name])})
        old_config = copy.deepcopy(old[config])
        old_config.body = [node for node in old_config.body if not (
            isinstance(node, ast.AnnAssign) and node.target.id in {
                "data_dir", "checkpoint_dir", "default_start",
            }
        )]
        comparisons.append({"source": source, "definition": config,
                            "same": normalized(old_config) == normalized(new[config])})
        for name in ("__init__", fetch, "parse_article"):
            before = next(n for n in old[client].body if getattr(n, "name", None) == name)
            after = next(n for n in new[client].body if getattr(n, "name", None) == name)
            comparisons.append({"source": source, "definition": f"{client}.{name}",
                                "same": normalized(before) == normalized(after)})
        before = next(n for n in old[client].body if isinstance(n, ast.Assign))
        after = next(n for n in new[client].body if isinstance(n, ast.Assign))
        comparisons.append({"source": source, "definition": f"{client}.BASE_URL",
                            "same": normalized(before) == normalized(after)})
    old_cli = subprocess.check_output(["git", "show", f"{BASE}:src/daily_update.py"], text=True)
    new_cli = Path("src/daily_update.py").read_text()
    for name in ("main", "get_ibkr_prices_status"):
        before = ast.get_source_segment(old_cli, definitions(old_cli)[name])
        after = ast.get_source_segment(new_cli, definitions(new_cli)[name])
        comparisons.append({"source": "daily_update", "definition": name,
                            "same": before == after, "comparison": "exact_source"})
    print(json.dumps({"base": BASE, "comparisons": comparisons}, indent=2))
    return 0 if all(row["same"] for row in comparisons) else 1


if __name__ == "__main__":
    raise SystemExit(main())
