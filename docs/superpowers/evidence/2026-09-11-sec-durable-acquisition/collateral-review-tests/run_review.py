"""Keep even tempfile-based conftest state inside this review's workspace."""
import os
from pathlib import Path
import runpy
import sys
import tempfile

scratch = Path(__file__).resolve().parent
tempdir = scratch / "tmp"
tempdir.mkdir(exist_ok=True)
tempfile.tempdir = str(tempdir)
os.environ["TMPDIR"] = str(tempdir)
runner = scratch.parent / sys.argv[1]
sys.argv = [str(runner), *sys.argv[2:]]
runpy.run_path(str(runner), run_name="__main__")
