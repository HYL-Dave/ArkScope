"""
Code Executor — restricted Python child-process execution for AI agents.

Provides execute_python_code() which:
1. Validates code via AST (blocked module check)
2. Runs in a child process with a closed environment and timeout
3. Supports data injection via stdin (data_json → `data` variable)

This is not an OS sandbox. The AST check and closed environment reduce accidental
capability and direct credential inheritance; filesystem, network, process, and
resource isolation require a separate platform sandbox.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import FrozenSet, Mapping, Optional

# ── Blocked modules ──────────────────────────────────────────
# These modules are denied at AST level (before code runs).
# Blocklist approach: everything not listed is allowed.
# Safe modules like numpy, pandas, scipy, json, math, etc. are permitted.

DEFAULT_BLOCKED_MODULES: FrozenSet[str] = frozenset({
    # filesystem / OS
    "os", "sys", "subprocess", "shutil", "pathlib",
    # network
    "socket", "http", "urllib", "requests", "httpx", "httpx2",
    "ftplib", "smtplib", "imaplib", "poplib", "telnetlib",
    # low-level / dynamic loading
    "ctypes", "importlib", "runpy", "code", "codeop",
    # serialization (unsafe deserialization)
    "shelve", "marshal",
    # concurrency / signals
    "multiprocessing", "threading", "signal",
    # misc
    "webbrowser", "antigravity",
})

# ── Preamble injected before user code ───────────────────────
# Uses underscore-prefixed aliases to avoid polluting user namespace.
# These imports are NOT subject to blocklist (only user code AST is checked).

_PREAMBLE = """\
import json as _json
import sys as _sys
_input = _sys.stdin.read()
data = _json.loads(_input) if _input.strip() else {}
del _json, _sys, _input
"""

_PYTHON_CHILD_ENV_ALLOWLIST = frozenset({
    "LANG",
    "LANGUAGE",
    "LC_ADDRESS",
    "LC_ALL",
    "LC_COLLATE",
    "LC_CTYPE",
    "LC_IDENTIFICATION",
    "LC_MEASUREMENT",
    "LC_MESSAGES",
    "LC_MONETARY",
    "LC_NAME",
    "LC_NUMERIC",
    "LC_PAPER",
    "LC_TELEPHONE",
    "LC_TIME",
    "TZ",
})
_PYTHON_CHILD_ENV_DEFAULTS = {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONNOUSERSITE": "1",
    "MPLBACKEND": "Agg",
}


def _python_child_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the non-secret environment allowed into analysis children."""
    parent = os.environ if source is None else source
    child = {
        name: value
        for name, value in parent.items()
        if name in _PYTHON_CHILD_ENV_ALLOWLIST
    }
    child.update(_PYTHON_CHILD_ENV_DEFAULTS)
    return child


# ── Result dataclass ─────────────────────────────────────────

@dataclass
class CodeExecutionResult:
    """Result of code execution."""
    success: bool
    output: str            # stdout
    error: str             # stderr or exception message
    execution_time: float  # seconds


# ── AST validation ───────────────────────────────────────────

def validate_code(
    code: str,
    blocked: FrozenSet[str] = DEFAULT_BLOCKED_MODULES,
) -> Optional[str]:
    """
    Validate Python code via AST analysis.

    Checks all Import and ImportFrom nodes against the blocked modules set.
    Uses top-level module name for matching (e.g., 'os.path' checks 'os').

    Args:
        code: Python source code string
        blocked: Set of blocked module names

    Returns:
        None if code passes validation, error message string if blocked.
    """
    if not code.strip():
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Check top-level module: "import os.path" → check "os"
                top_module = alias.name.split(".")[0]
                if top_module in blocked:
                    return f"Blocked import: {alias.name} (module '{top_module}' is not allowed)"

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_module = node.module.split(".")[0]
                if top_module in blocked:
                    return f"Blocked import: from {node.module} (module '{top_module}' is not allowed)"

    return None


# ── Code execution ───────────────────────────────────────────

def execute_python_code(
    code: str,
    data_json: str = "",
    timeout: int = 120,
    blocked_modules: FrozenSet[str] = DEFAULT_BLOCKED_MODULES,
) -> CodeExecutionResult:
    """
    Execute Python code in a restricted subprocess with a closed environment.

    The code has access to:
    - `data` variable (injected from data_json via stdin)
    - Standard library modules (except blocked ones)
    - numpy, pandas, scipy, and other installed packages

    Args:
        code: Python code to execute
        data_json: JSON string injected as `data` variable
        timeout: Max execution time in seconds (default: 120)
        blocked_modules: Set of module names to block

    Returns:
        CodeExecutionResult with output, error, and timing
    """
    # Validate code first (AST check)
    validation_error = validate_code(code, blocked_modules)
    if validation_error is not None:
        return CodeExecutionResult(
            success=False,
            output="",
            error=validation_error,
            execution_time=0.0,
        )

    # Build full code: preamble + user code
    full_code = _PREAMBLE + code

    # Ensure data_json is a string (could be empty)
    stdin_data = data_json if data_json else ""

    return _execute_foreground(full_code, stdin_data, timeout)


def _execute_foreground(
    full_code: str,
    stdin_data: str,
    timeout: int,
) -> CodeExecutionResult:
    """Run code in foreground subprocess with timeout."""
    start = time.monotonic()

    try:
        result = subprocess.run(
            [sys.executable, "-c", full_code],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_python_child_environment(),
        )
        elapsed = time.monotonic() - start

        return CodeExecutionResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            execution_time=round(elapsed, 3),
        )

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return CodeExecutionResult(
            success=False,
            output="",
            error=f"Execution timed out after {timeout} seconds",
            execution_time=round(elapsed, 3),
        )

    except Exception as e:
        elapsed = time.monotonic() - start
        return CodeExecutionResult(
            success=False,
            output="",
            error=f"Execution failed: {e}",
            execution_time=round(elapsed, 3),
        )
