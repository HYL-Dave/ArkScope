"""
Tests for the Code Executor tool (Phase 5 of agent evolution).

Tests cover:
1. AST validation (blocked/allowed imports, syntax errors)
2. Foreground execution (stdout, stderr, timeout, data injection)
3. Background execution (Popen, output file, PID)
4. Result dataclass serialization
"""

import json
import os
import time

import pytest

from src.tools.code_executor import (
    CodeExecutionResult,
    DEFAULT_BLOCKED_MODULES,
    execute_python_code,
    validate_code,
)


# ============================================================
# AST Validation Tests
# ============================================================

class TestValidateCode:
    def test_valid_code_passes(self):
        """Simple print statement passes validation."""
        assert validate_code('print("hello")') is None

    def test_blocked_import_os(self):
        """import os is blocked."""
        result = validate_code("import os")
        assert result is not None
        assert "os" in result

    def test_blocked_from_import(self):
        """from subprocess import run is blocked."""
        result = validate_code("from subprocess import run")
        assert result is not None
        assert "subprocess" in result

    def test_blocked_os_path(self):
        """import os.path is blocked (top-level module 'os')."""
        result = validate_code("import os.path")
        assert result is not None
        assert "os" in result

    def test_allowed_numpy(self):
        """import numpy passes validation."""
        assert validate_code("import numpy") is None

    def test_allowed_pandas(self):
        """import pandas passes validation."""
        assert validate_code("import pandas") is None

    def test_allowed_json(self):
        """import json passes validation."""
        assert validate_code("import json") is None

    def test_allowed_math(self):
        """import math passes validation."""
        assert validate_code("import math") is None

    def test_syntax_error_caught(self):
        """Invalid syntax returns error."""
        result = validate_code("def f(:")
        assert result is not None
        assert "Syntax error" in result

    def test_nested_import_blocked(self):
        """Blocked import inside a function is still caught."""
        code = "def f():\n    import os\n    return os.getcwd()"
        result = validate_code(code)
        assert result is not None
        assert "os" in result

    def test_multiple_imports_one_blocked(self):
        """import json, os — blocked because os is in blocklist."""
        result = validate_code("import json, os")
        assert result is not None
        assert "os" in result

    def test_empty_code(self):
        """Empty code passes validation."""
        assert validate_code("") is None
        assert validate_code("   ") is None

    def test_http_submodule_blocked(self):
        """from http.client import HTTPConnection is blocked."""
        result = validate_code("from http.client import HTTPConnection")
        assert result is not None
        assert "http" in result

    def test_custom_blocklist(self):
        """Custom blocklist overrides default."""
        # Block only 'math'
        custom = frozenset({"math"})
        assert validate_code("import math", blocked=custom) is not None
        # os is now allowed with this custom list
        assert validate_code("import os", blocked=custom) is None


# ============================================================
# Foreground Execution Tests
# ============================================================

class TestExecutePythonCode:
    def test_simple_print(self):
        """print("hello") produces stdout output."""
        result = execute_python_code('print("hello")')
        assert result.success is True
        assert result.output.strip() == "hello"
        assert result.error == ""
        assert result.execution_time > 0

    def test_math_calculation(self):
        """Arithmetic result appears in stdout."""
        result = execute_python_code("print(2 + 3)")
        assert result.success is True
        assert result.output.strip() == "5"

    def test_data_injection(self):
        """data_json is accessible as `data` variable."""
        code = 'print(data["x"] + data["y"])'
        result = execute_python_code(code, data_json='{"x": 10, "y": 20}')
        assert result.success is True
        assert result.output.strip() == "30"

    def test_data_injection_list(self):
        """data_json can be a list."""
        code = "print(sum(data))"
        result = execute_python_code(code, data_json="[1, 2, 3, 4, 5]")
        assert result.success is True
        assert result.output.strip() == "15"

    def test_empty_data_json(self):
        """Empty data_json results in empty dict for `data`."""
        code = "print(type(data).__name__)"
        result = execute_python_code(code, data_json="")
        assert result.success is True
        assert result.output.strip() == "dict"

    def test_numpy_available(self):
        """numpy is available in the subprocess."""
        code = "import numpy as np; print(np.mean([1, 2, 3, 4, 5]))"
        result = execute_python_code(code)
        assert result.success is True
        assert "3.0" in result.output

    def test_pandas_available(self):
        """pandas is available in the subprocess."""
        code = "import pandas as pd; print(pd.Series([1,2,3]).sum())"
        result = execute_python_code(code)
        assert result.success is True
        assert "6" in result.output

    def test_timeout_kills_process(self):
        """Infinite loop is killed by timeout."""
        result = execute_python_code("while True: pass", timeout=2)
        assert result.success is False
        assert "timed out" in result.error

    def test_blocked_import_rejected(self):
        """Blocked import is caught at AST level (no execution)."""
        result = execute_python_code("import os; print(os.getcwd())")
        assert result.success is False
        assert "Blocked import" in result.error
        assert result.execution_time == 0.0  # Never executed

    def test_stderr_captured(self):
        """stderr output is captured in error field."""
        code = "import sys; print('error msg', file=sys.stderr)"
        # sys is blocked, so this should fail at AST level
        result = execute_python_code(code)
        assert result.success is False
        assert "Blocked import" in result.error

    def test_stderr_from_exception(self):
        """Exception traceback appears in stderr."""
        code = "raise ValueError('test error')"
        result = execute_python_code(code)
        assert result.success is False
        assert "ValueError" in result.error

    def test_empty_code_succeeds(self):
        """Empty code produces no output and succeeds."""
        result = execute_python_code("")
        assert result.success is True
        assert result.output == ""

    def test_exception_in_code(self):
        """Runtime exception is captured."""
        code = "x = 1 / 0"
        result = execute_python_code(code)
        assert result.success is False
        assert "ZeroDivisionError" in result.error

    def test_return_dataclass_fields(self):
        """Result has all expected fields."""
        result = execute_python_code('print("ok")')
        assert hasattr(result, "success")
        assert hasattr(result, "output")
        assert hasattr(result, "error")
        assert hasattr(result, "execution_time")
        assert hasattr(result, "output_file")
        assert hasattr(result, "pid")

    def test_multiline_code(self):
        """Multi-line code works correctly."""
        code = """
values = [10, 20, 30, 40, 50]
mean = sum(values) / len(values)
print(f"Mean: {mean}")
"""
        result = execute_python_code(code)
        assert result.success is True
        assert "Mean: 30.0" in result.output


# ============================================================
# Background Execution Tests
# ============================================================

class TestBackgroundExecution:
    def test_background_returns_immediately(self):
        """background=True returns quickly (no waiting for code)."""
        start = time.monotonic()
        result = execute_python_code(
            "import time; time.sleep(5); print('done')",
            background=True,
        )
        elapsed = time.monotonic() - start
        # Should return within 1 second (not wait for 5s sleep)
        assert elapsed < 2.0
        assert result.success is True
        assert result.execution_time == 0.0

    def test_background_has_output_file(self):
        """Background result includes a valid output file path."""
        result = execute_python_code('print("bg test")', background=True)
        assert result.output_file != ""
        assert result.output_file.startswith("/tmp/mindfulrl_exec_")
        assert result.output_file.endswith(".txt")

    def test_background_has_pid(self):
        """Background result includes a process PID."""
        result = execute_python_code('print("bg test")', background=True)
        assert result.pid > 0

    def test_background_writes_output(self):
        """Background process writes output to temp file."""
        result = execute_python_code('print("background output")', background=True)
        # Wait for subprocess to complete
        time.sleep(2)
        assert os.path.exists(result.output_file)
        content = open(result.output_file).read()
        assert "background output" in content
        # Cleanup
        os.unlink(result.output_file)

    def test_background_with_data_json(self):
        """Data injection works in background mode."""
        result = execute_python_code(
            'print(data["msg"])',
            data_json='{"msg": "hello from bg"}',
            background=True,
        )
        time.sleep(2)
        assert os.path.exists(result.output_file)
        content = open(result.output_file).read()
        assert "hello from bg" in content
        # Cleanup
        os.unlink(result.output_file)

    def test_background_blocked_import_still_rejected(self):
        """AST validation still applies in background mode."""
        result = execute_python_code("import os", background=True)
        assert result.success is False
        assert "Blocked import" in result.error


# ============================================================
# Serialization Tests
# ============================================================

class TestCodeExecutionResult:
    def test_serialization(self):
        """CodeExecutionResult can be serialized to dict/JSON."""
        from dataclasses import asdict
        result = CodeExecutionResult(
            success=True,
            output="hello",
            error="",
            execution_time=0.5,
        )
        d = asdict(result)
        assert d["success"] is True
        assert d["output"] == "hello"
        # JSON roundtrip
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["success"] is True