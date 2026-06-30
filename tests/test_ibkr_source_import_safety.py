import os
import subprocess
import sys
from pathlib import Path


def test_ibkr_source_imports_without_ib_insync_and_constructor_explains_dependency():
    repo = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": f"{repo}:/tmp/arkscope_pydeps",
    }
    code = (
        "import src.news_normalized.ibkr_adapter\n"
        "from data_sources.ibkr_source import IBKRDataSource\n"
        "try:\n"
        "    IBKRDataSource()\n"
        "except ImportError as exc:\n"
        "    assert 'ib_insync is required for IBKR data source' in str(exc)\n"
        "else:\n"
        "    raise AssertionError('IBKRDataSource construction should require ib_insync')\n"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
