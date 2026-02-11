"""
Code Executor — sandboxed Python code execution for AI agents.

Provides execute_python_code() which:
1. Validates code via AST (blocked module check)
2. Runs in isolated subprocess with timeout
3. Supports data injection via stdin (data_json → `data` variable)
4. Background mode for long-running tasks (Popen + temp file)

Security: Dual-layer defense
- Layer 1: AST static analysis blocks dangerous imports before execution
- Layer 2: Subprocess isolation with timeout prevents runaway processes
"""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import FrozenSet, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ── Blocked modules ──────────────────────────────────────────
# These modules are denied at AST level (before code runs).
# Blocklist approach: everything not listed is allowed.
# Safe modules like numpy, pandas, scipy, json, math, etc. are permitted.

DEFAULT_BLOCKED_MODULES: FrozenSet[str] = frozenset({
    # filesystem / OS
    "os", "sys", "subprocess", "shutil", "pathlib",
    # network
    "socket", "http", "urllib", "requests", "httpx",
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


# ── Result dataclass ─────────────────────────────────────────

@dataclass
class CodeExecutionResult:
    """Result of code execution."""
    success: bool
    output: str            # stdout (or "Background started..." message)
    error: str             # stderr or exception message
    execution_time: float  # seconds (0.0 for background mode)
    output_file: str = ""  # background mode: temp file path
    pid: int = 0           # background mode: process PID
    generated_code: str = ""  # code gen mode: the generated code


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
    code: str = "",
    task: str = "",
    data_json: str = "",
    timeout: int = 120,
    background: bool = False,
    blocked_modules: FrozenSet[str] = DEFAULT_BLOCKED_MODULES,
) -> CodeExecutionResult:
    """
    Execute Python code in an isolated subprocess.

    Two modes:
    - Direct: provide `code` to execute directly
    - Code gen: provide `task` to auto-generate code using a coding model

    The code has access to:
    - `data` variable (injected from data_json via stdin)
    - Standard library modules (except blocked ones)
    - numpy, pandas, scipy, and other installed packages

    Args:
        code: Python code to execute (direct mode)
        task: Task description for auto code generation (code gen mode)
        data_json: JSON string injected as `data` variable
        timeout: Max execution time in seconds (default: 120)
        background: If True, run non-blocking with output to temp file
        blocked_modules: Set of module names to block

    Returns:
        CodeExecutionResult with output, error, timing, and background info
    """
    # Task mode: delegate to code_generator
    if task and not code:
        from .code_generator import generate_and_execute
        return generate_and_execute(
            task=task, data_json=data_json,
            timeout=timeout, background=background,
        )

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

    if background:
        return _execute_background(full_code, stdin_data)
    else:
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


def _execute_background(
    full_code: str,
    stdin_data: str,
) -> CodeExecutionResult:
    """Run code in background subprocess, output to temp file."""
    output_path = f"/tmp/mindfulrl_exec_{uuid4().hex[:12]}.txt"

    try:
        # Open output file for subprocess stdout/stderr
        out_file = open(output_path, "w")

        proc = subprocess.Popen(
            [sys.executable, "-c", full_code],
            stdin=subprocess.PIPE,
            stdout=out_file,
            stderr=subprocess.STDOUT,
        )

        # Write stdin data and close
        if stdin_data:
            proc.stdin.write(stdin_data.encode())
        proc.stdin.close()

        # Close parent's copy of file descriptor (child has its own)
        out_file.close()

        logger.info(f"Background execution started: pid={proc.pid} output={output_path}")

        return CodeExecutionResult(
            success=True,
            output=f"Background execution started. Output file: {output_path}",
            error="",
            execution_time=0.0,
            output_file=output_path,
            pid=proc.pid,
        )

    except Exception as e:
        return CodeExecutionResult(
            success=False,
            output="",
            error=f"Failed to start background execution: {e}",
            execution_time=0.0,
        )