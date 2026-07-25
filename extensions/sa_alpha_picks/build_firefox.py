#!/usr/bin/env python3
"""Build a dependency-complete Firefox extension tree atomically."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple


DEFAULT_MANIFEST = "manifest.firefox.json"
OUTPUT_MANIFEST = "manifest.json"
FIREFOX_COMPAT = "compat_firefox.js"
POPUP_SCRIPT = "popup.js"


class BuildError(RuntimeError):
    """The source tree cannot produce a complete, deterministic build."""


class DependencyReference(NamedTuple):
    source: str
    target: str
    kind: str
    line: int


class DependencyGraph(NamedTuple):
    files: tuple[str, ...]
    references: tuple[DependencyReference, ...]


class _Token(NamedTuple):
    kind: str
    value: str
    line: int


_IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$")
_IDENT_PART = _IDENT_START | frozenset("0123456789")
_REGEX_PREFIX_PUNCT = frozenset("([{,:;=!?&|+-*%^~<>")
_REGEX_PREFIX_IDENT = frozenset(
    {"case", "delete", "do", "else", "in", "instanceof", "new", "of", "return", "throw", "typeof", "void", "yield"}
)


def _tokenize_javascript(text: str, source: str) -> list[_Token]:
    tokens: list[_Token] = []
    i = 0
    line = 1

    def fail(message: str) -> BuildError:
        return BuildError(f"{source}:{line}: {message}")

    while i < len(text):
        char = text[i]
        if char.isspace():
            if char == "\n":
                line += 1
            i += 1
            continue

        if text.startswith("//", i):
            newline = text.find("\n", i + 2)
            if newline < 0:
                break
            i = newline
            continue

        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise fail("unterminated block comment")
            line += text.count("\n", i, end + 2)
            i = end + 2
            continue

        if char in ('"', "'"):
            quote = char
            token_line = line
            value: list[str] = []
            i += 1
            while i < len(text):
                char = text[i]
                if char == quote:
                    i += 1
                    break
                if char == "\\":
                    if i + 1 >= len(text):
                        raise fail("unterminated string escape")
                    escaped = text[i + 1]
                    if escaped == "\n":
                        line += 1
                    elif escaped in (quote, "\\", "/"):
                        value.append(escaped)
                    else:
                        # Preserve non-path JavaScript escapes. If this token is
                        # later used as an asset reference, _safe_basename()
                        # rejects the retained backslash.
                        value.extend(("\\", escaped))
                    i += 2
                    continue
                if char == "\n":
                    raise fail("unterminated string literal")
                value.append(char)
                i += 1
            else:
                raise fail("unterminated string literal")
            tokens.append(_Token("string", "".join(value), token_line))
            continue

        if char == "`":
            token_line = line
            i += 1
            while i < len(text):
                char = text[i]
                if char == "\\":
                    i += 2
                    continue
                if char == "`":
                    i += 1
                    break
                if char == "\n":
                    line += 1
                i += 1
            else:
                raise fail("unterminated template literal")
            tokens.append(_Token("template", "", token_line))
            continue

        if char in _IDENT_START:
            token_line = line
            start = i
            i += 1
            while i < len(text) and text[i] in _IDENT_PART:
                i += 1
            tokens.append(_Token("identifier", text[start:i], token_line))
            continue

        if char.isdigit():
            token_line = line
            start = i
            i += 1
            while i < len(text) and (text[i].isalnum() or text[i] in "._"):
                i += 1
            tokens.append(_Token("number", text[start:i], token_line))
            continue

        if char == "/" and _starts_regex(tokens):
            token_line = line
            i += 1
            in_class = False
            while i < len(text):
                char = text[i]
                if char == "\\":
                    i += 2
                    continue
                if char == "\n":
                    raise fail("unterminated regular expression")
                if char == "[":
                    in_class = True
                elif char == "]":
                    in_class = False
                elif char == "/" and not in_class:
                    i += 1
                    while i < len(text) and text[i].isalpha():
                        i += 1
                    break
                i += 1
            else:
                raise fail("unterminated regular expression")
            tokens.append(_Token("regex", "", token_line))
            continue

        tokens.append(_Token("punct", char, line))
        i += 1

    return tokens


def _starts_regex(tokens: list[_Token]) -> bool:
    if not tokens:
        return True
    previous = tokens[-1]
    if previous.kind == "identifier":
        return previous.value in _REGEX_PREFIX_IDENT
    return previous.kind == "punct" and previous.value in _REGEX_PREFIX_PUNCT


def _matching_token(tokens: list[_Token], opening: int, left: str, right: str, source: str) -> int:
    depth = 0
    for index in range(opening, len(tokens)):
        value = tokens[index].value
        if value == left:
            depth += 1
        elif value == right:
            depth -= 1
            if depth == 0:
                return index
    raise BuildError(f"{source}:{tokens[opening].line}: unbalanced {left}{right} expression")


def _literal_list(tokens: list[_Token], start: int, end: int, source: str, label: str) -> list[_Token]:
    values: list[_Token] = []
    index = start
    while index < end:
        token = tokens[index]
        if token.kind != "string":
            raise BuildError(f"{source}:{token.line}: {label} requires literal string basenames")
        values.append(token)
        index += 1
        if index >= end:
            break
        separator = tokens[index]
        if separator.value != ",":
            raise BuildError(
                f"{source}:{separator.line}: {label} requires comma-separated literals"
            )
        index += 1
        if index == end:
            break
    return values


def _javascript_references(text: str, source: str) -> list[DependencyReference]:
    tokens = _tokenize_javascript(text, source)
    references: list[DependencyReference] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "identifier" and token.value == "importScripts":
            if index + 1 >= len(tokens) or tokens[index + 1].value != "(":
                index += 1
                continue
            close = _matching_token(tokens, index + 1, "(", ")", source)
            for value in _literal_list(tokens, index + 2, close, source, "importScripts"):
                references.append(DependencyReference(source, value.value, "import_scripts", value.line))
            index = close + 1
            continue

        if token.kind == "identifier" and token.value == "executeScript":
            if index + 1 >= len(tokens) or tokens[index + 1].value != "(":
                index += 1
                continue
            call_close = _matching_token(tokens, index + 1, "(", ")", source)
            argument = index + 2
            if argument >= call_close or tokens[argument].value != "{":
                raise BuildError(
                    f"{source}:{token.line}: executeScript options must be a literal object"
                )
            object_close = _matching_token(tokens, argument, "{", "}", source)
            if object_close > call_close:
                raise BuildError(f"{source}:{token.line}: malformed executeScript options")
            references.extend(
                _execute_script_file_references(tokens, argument, object_close, source)
            )
            index = call_close + 1
            continue
        index += 1
    return references


def _execute_script_file_references(
    tokens: list[_Token], object_open: int, object_close: int, source: str
) -> list[DependencyReference]:
    stack = ["{"]
    files_property: int | None = None
    index = object_open + 1
    pairs = {"{": "}", "[": "]", "(": ")"}
    while index < object_close:
        token = tokens[index]
        if (
            len(stack) == 1
            and token.value == "["
            and (index == object_open + 1 or tokens[index - 1].value != ":")
        ):
            raise BuildError(
                f"{source}:{token.line}: executeScript requires literal property names"
            )
        if (
            len(stack) == 1
            and token.value == "."
            and index + 2 < object_close
            and tokens[index + 1].value == "."
            and tokens[index + 2].value == "."
        ):
            raise BuildError(
                f"{source}:{token.line}: executeScript options may not use nonliteral spreads"
            )
        if token.value in pairs:
            stack.append(token.value)
        elif token.value in pairs.values():
            if len(stack) > 1:
                stack.pop()
        elif (
            len(stack) == 1
            and token.value == "files"
            and token.kind in {"identifier", "string"}
        ):
            if files_property is not None:
                raise BuildError(f"{source}:{token.line}: duplicate executeScript files property")
            files_property = index
        index += 1

    if files_property is None:
        return []
    colon = files_property + 1
    if colon >= object_close or tokens[colon].value != ":":
        raise BuildError(
            f"{source}:{tokens[files_property].line}: executeScript files requires a literal array"
        )
    array_open = colon + 1
    if array_open >= object_close or tokens[array_open].value != "[":
        line = tokens[array_open].line if array_open < object_close else tokens[files_property].line
        raise BuildError(f"{source}:{line}: executeScript files requires a literal array")
    array_close = _matching_token(tokens, array_open, "[", "]", source)
    if array_close + 1 < object_close and tokens[array_close + 1].value not in {",", "}"}:
        token = tokens[array_close + 1]
        raise BuildError(
            f"{source}:{token.line}: executeScript files must be one literal array"
        )
    values = _literal_list(
        tokens, array_open + 1, array_close, source, "executeScript files"
    )
    return [
        DependencyReference(source, value.value, "execute_script", value.line)
        for value in values
    ]


class _HtmlAssets(HTMLParser):
    _ATTRS = {
        "audio": ("src",),
        "embed": ("src",),
        "iframe": ("src",),
        "img": ("src",),
        "input": ("src",),
        "link": ("href",),
        "object": ("data",),
        "script": ("src",),
        "source": ("src",),
        "video": ("src", "poster"),
    }

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.references: list[DependencyReference] = []
        self.scripts: list[tuple[str, int]] = []

    def handle_starttag(self, tag, attrs):
        self._collect(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._collect(tag, attrs)

    def _collect(self, tag, attrs):
        wanted = self._ATTRS.get(tag.lower(), ())
        values = dict(attrs)
        for name in wanted:
            target = values.get(name)
            if not target:
                continue
            line = self.getpos()[0]
            self.references.append(DependencyReference(self.source, target, "html", line))
            if tag.lower() == "script" and name == "src":
                self.scripts.append((target, line))


def _safe_basename(reference: DependencyReference) -> str:
    target = reference.target
    if (
        not target
        or target in {".", ".."}
        or Path(target).name != target
        or "/" in target
        or "\\" in target
        or "?" in target
        or "#" in target
        or ":" in target
    ):
        raise BuildError(
            f"{reference.source}:{reference.line}: unsafe runtime asset reference {target!r}"
        )
    return target


def _manifest_references(data: dict, source: str, text: str) -> list[DependencyReference]:
    targets: list[str] = []
    background = data.get("background") or {}
    if isinstance(background.get("service_worker"), str):
        targets.append(background["service_worker"])
    scripts = background.get("scripts") or []
    if not isinstance(scripts, list) or not all(isinstance(item, str) for item in scripts):
        raise BuildError(f"{source}: background.scripts must contain literal strings")
    targets.extend(scripts)

    action = data.get("action") or data.get("browser_action") or {}
    if isinstance(action.get("default_popup"), str):
        targets.append(action["default_popup"])
    for key in ("options_page", "devtools_page"):
        if isinstance(data.get(key), str):
            targets.append(data[key])
    options_ui = data.get("options_ui") or {}
    if isinstance(options_ui.get("page"), str):
        targets.append(options_ui["page"])
    side_panel = data.get("side_panel") or {}
    if isinstance(side_panel.get("default_path"), str):
        targets.append(side_panel["default_path"])

    icons = data.get("icons") or {}
    if not isinstance(icons, dict) or not all(isinstance(item, str) for item in icons.values()):
        raise BuildError(f"{source}: icons must map sizes to literal strings")
    targets.extend(icons.values())

    for content in data.get("content_scripts") or []:
        if not isinstance(content, dict):
            raise BuildError(f"{source}: content_scripts entries must be objects")
        for key in ("js", "css"):
            values = content.get(key) or []
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise BuildError(f"{source}: content_scripts.{key} must contain literal strings")
            targets.extend(values)

    for resource_group in data.get("web_accessible_resources") or []:
        if isinstance(resource_group, str):
            targets.append(resource_group)
            continue
        if not isinstance(resource_group, dict):
            raise BuildError(f"{source}: web_accessible_resources entries must be objects")
        resources = resource_group.get("resources") or []
        if not isinstance(resources, list) or not all(isinstance(item, str) for item in resources):
            raise BuildError(f"{source}: web_accessible_resources.resources must contain literal strings")
        targets.extend(resources)

    references = []
    for target in targets:
        marker = json.dumps(target)
        offset = text.find(marker)
        line = text.count("\n", 0, offset) + 1 if offset >= 0 else 1
        references.append(DependencyReference(source, target, "manifest", line))
    return references


def discover_dependency_graph(
    source: Path | str, manifest_name: str = DEFAULT_MANIFEST
) -> DependencyGraph:
    source_path = Path(source).resolve()
    manifest_ref = DependencyReference(manifest_name, manifest_name, "root", 1)
    manifest_name = _safe_basename(manifest_ref)
    manifest_path = source_path / manifest_name
    if not manifest_path.is_file():
        raise BuildError(f"{manifest_name}: required manifest does not exist")
    manifest_text = manifest_path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(manifest_text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BuildError(f"{manifest_name}: invalid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BuildError(f"{manifest_name}: manifest root must be an object")

    files = {manifest_name}
    references: list[DependencyReference] = []
    pending = _manifest_references(manifest, manifest_name, manifest_text)
    parsed: set[str] = set()
    while pending:
        reference = pending.pop(0)
        target = _safe_basename(reference)
        references.append(reference._replace(target=target))
        path = source_path / target
        if not path.is_file():
            raise BuildError(
                f"{reference.source}:{reference.line}: runtime dependency {target!r} does not exist"
            )
        files.add(target)
        if target in parsed:
            continue
        parsed.add(target)
        if path.suffix.lower() == ".html":
            parser = _HtmlAssets(target)
            try:
                parser.feed(path.read_text(encoding="utf-8"))
                parser.close()
            except (UnicodeDecodeError, ValueError) as exc:
                raise BuildError(f"{target}: invalid HTML: {exc}") from exc
            pending.extend(parser.references)
        elif path.suffix.lower() == ".js":
            pending.extend(_javascript_references(path.read_text(encoding="utf-8"), target))

    return DependencyGraph(tuple(sorted(files)), tuple(references))


def _popup_name(source: Path, manifest_name: str) -> str:
    data = json.loads((source / manifest_name).read_text(encoding="utf-8"))
    action = data.get("action") or data.get("browser_action") or {}
    popup = action.get("default_popup")
    if not isinstance(popup, str):
        raise BuildError(f"{manifest_name}: action.default_popup must be a literal string")
    return _safe_basename(DependencyReference(manifest_name, popup, "manifest", 1))


_POPUP_TAG = re.compile(
    r"<script\b[^>]*\bsrc\s*=\s*(['\"])popup\.js\1[^>]*>", re.IGNORECASE
)


def _firefox_popup(text: str, source: str) -> str:
    parser = _HtmlAssets(source)
    parser.feed(text)
    parser.close()
    scripts = [value for value, _line in parser.scripts]
    if scripts.count(POPUP_SCRIPT) != 1:
        raise BuildError(f"{source}: expected exactly one {POPUP_SCRIPT} script")
    compat_count = scripts.count(FIREFOX_COMPAT)
    if compat_count > 1:
        raise BuildError(f"{source}: {FIREFOX_COMPAT} must appear at most once")
    if compat_count == 1:
        if scripts.index(FIREFOX_COMPAT) > scripts.index(POPUP_SCRIPT):
            raise BuildError(f"{source}: {FIREFOX_COMPAT} must load before {POPUP_SCRIPT}")
        return text
    matches = list(_POPUP_TAG.finditer(text))
    if len(matches) != 1:
        raise BuildError(f"{source}: could not locate the unique {POPUP_SCRIPT} start tag")
    start = matches[0].start()
    line_start = text.rfind("\n", 0, start) + 1
    indent = text[line_start:start]
    injected = f'{indent}<script src="{FIREFOX_COMPAT}"></script>\n'
    return text[:start] + injected + text[start:]


def _generate_tree(source: Path, destination: Path, graph: DependencyGraph) -> tuple[str, ...]:
    if FIREFOX_COMPAT not in graph.files:
        raise BuildError(f"{DEFAULT_MANIFEST}: dependency graph must include {FIREFOX_COMPAT}")
    popup = _popup_name(source, DEFAULT_MANIFEST)
    for name in graph.files:
        if name == DEFAULT_MANIFEST:
            shutil.copy2(source / name, destination / OUTPUT_MANIFEST)
        elif name == popup:
            transformed = _firefox_popup((source / name).read_text(encoding="utf-8"), name)
            (destination / name).write_text(transformed, encoding="utf-8")
        else:
            shutil.copy2(source / name, destination / name)

    expected = set(graph.files)
    expected.remove(DEFAULT_MANIFEST)
    expected.add(OUTPUT_MANIFEST)
    actual = {
        item.relative_to(destination).as_posix()
        for item in destination.rglob("*")
        if item.is_file()
    }
    if actual != expected:
        raise BuildError(
            f"generated file set differs from dependency closure: missing={sorted(expected - actual)!r}, "
            f"extra={sorted(actual - expected)!r}"
        )
    generated = discover_dependency_graph(destination, manifest_name=OUTPUT_MANIFEST)
    if set(generated.files) != expected:
        raise BuildError("generated manifest/HTML dependency closure is incomplete")
    return tuple(sorted(actual))


def _replace_directory_atomically(staged: Path, output: Path) -> None:
    backup = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent)
    )
    backup.rmdir()
    moved_previous = False
    try:
        if output.exists():
            if not output.is_dir():
                raise BuildError(f"output path is not a directory: {output}")
            os.replace(output, backup)
            moved_previous = True
        try:
            os.replace(staged, output)
        except Exception:
            if moved_previous and not output.exists() and backup.exists():
                os.replace(backup, output)
                moved_previous = False
            raise
        if moved_previous and backup.exists():
            shutil.rmtree(backup)
            moved_previous = False
    finally:
        if staged.exists():
            shutil.rmtree(staged)
        if backup.exists() and not moved_previous:
            shutil.rmtree(backup)


def build_firefox(source: Path | str, output: Path | str) -> tuple[str, ...]:
    source_path = Path(source).resolve()
    output_path = Path(output).resolve()
    graph = discover_dependency_graph(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(
        tempfile.mkdtemp(prefix=f".{output_path.name}.tmp-", dir=output_path.parent)
    )
    try:
        built = _generate_tree(source_path, staged, graph)
        _replace_directory_atomically(staged, output_path)
        return built
    except Exception:
        if staged.exists():
            shutil.rmtree(staged)
        raise


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the dependency graph without writing an artifact",
    )
    args = parser.parse_args(argv)
    if not args.list and args.output is None:
        parser.error("--output is required unless --list is used")
    if args.list and args.output is not None:
        parser.error("--list and --output are mutually exclusive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.list:
            graph = discover_dependency_graph(args.source, manifest_name=args.manifest)
            for name in graph.files:
                print(name)
        else:
            for name in build_firefox(args.source, args.output):
                print(name)
    except (BuildError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
