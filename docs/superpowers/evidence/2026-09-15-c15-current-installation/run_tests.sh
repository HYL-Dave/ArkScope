#!/bin/bash
set -euo pipefail

SOURCE=${C15_WORKTREE:-/tmp/arkscope-c15-current-installation-cleanup}
WORK=${C15_WORKSPACE:-/tmp/arkscope-c15-evaluation.G7sxyGBc}
BASE=/tmp/arkscope-prebuilt-compat.oCmRRHrQ
EVIDENCE=docs/superpowers/evidence/2026-09-15-c15-current-installation
CENSUS=docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/run_census.py
RUN=$1
shift
case "$RUN" in
  *[!a-zA-Z0-9_-]*|'') exit 2 ;;
esac
case "${C15_INTERPRETER:-prebuilt}" in
  prebuilt) PYTHON=$BASE/venv/bin/python; EXPECTED=3.53.1 ;;
  control) PYTHON=$BASE/control-venv/bin/python; EXPECTED=3.37.2 ;;
  *) exit 2 ;;
esac
mkdir -p "$WORK/$RUN" "$WORK/source"
MODULE_MOUNTS=()
while IFS= read -r module; do
  MODULE_MOUNTS+=(--ro-bind "$module" "$WORK/source/${module#"$SOURCE/"}")
done < <(rg --files "$SOURCE/data_sources" -g '*.py')
/usr/bin/bwrap --unshare-all --die-with-parent --new-session --clearenv \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 --dir /etc \
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache --ro-bind /etc/hosts /etc/hosts \
  --dev /dev --proc /proc --tmpfs /tmp \
  --ro-bind "$BASE/python" "$BASE/python" \
  --ro-bind "$BASE/venv" "$BASE/venv" \
  --ro-bind "$BASE/control-venv" "$BASE/control-venv" \
  --bind "$WORK" "$WORK" \
  --ro-bind "$SOURCE/src" "$WORK/source/src" \
  --ro-bind "$SOURCE/tests" "$WORK/source/tests" \
  --ro-bind "$SOURCE/resources/skills" "$WORK/source/resources/skills" \
  --ro-bind "$SOURCE/$CENSUS" "$WORK/source/$CENSUS" \
  "${MODULE_MOUNTS[@]}" \
  --ro-bind "$SOURCE/$EVIDENCE/offline_pytest.py" "$WORK/offline_pytest.py" \
  --setenv PATH /usr/bin:/bin --setenv HOME /tmp \
  --setenv PYTEST_DISABLE_PLUGIN_AUTOLOAD 1 \
  --setenv PYTHONHASHSEED 0 --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv ARKSCOPE_DISABLE_SCHEDULER 1 \
  --setenv ARKSCOPE_OFFLINE_TEST_WORKSPACE "$WORK/$RUN" \
  --setenv C15_SOURCE_ROOT "$WORK/source" \
  --setenv PROBE_EXPECT_SQLITE "$EXPECTED" \
  --setenv OPENAI_AGENTS_DISABLE_TRACING 1 --setenv LANG C.UTF-8 \
  --chdir "$WORK/source" \
  "$PYTHON" -I -B "$WORK/offline_pytest.py" "$@" 2>&1 | tee "$WORK/$RUN/pytest.log"
