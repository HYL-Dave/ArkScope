"""Archive isolated Task 1 verification subprocesses, without ambient config."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
label, *tests = sys.argv[1:]
env = {
    "PATH": "/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "ARKSCOPE_OFFLINE_TEST_WORKSPACE": str(HERE / label),
}
command = ["/home/hyl/.virtualenvs/llm_app/bin/python", "-B",
           str(HERE.parent / "offline_pytest.py"), *tests, "-q",
           "--junitxml=" + str(HERE / (label + ".xml"))]
result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True)
(HERE / (label + ".log")).write_text(result.stdout)
print(result.stdout)
raise SystemExit(result.returncode)
