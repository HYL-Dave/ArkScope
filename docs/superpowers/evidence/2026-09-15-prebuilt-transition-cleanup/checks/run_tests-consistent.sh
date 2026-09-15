#!/bin/sh
set -eu
BASE=/tmp/arkscope-prebuilt-compat.oCmRRHrQ
PYTHON=${PROBE_PYTHON:-$BASE/venv/bin/python}
EXPECTED=${PROBE_EXPECT_SQLITE:-3.53.1}
RUN=$1
shift
mkdir -p "$BASE/$RUN"
exec /usr/bin/bwrap --unshare-all --die-with-parent --new-session --clearenv \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 --dir /etc \
  --ro-bind /etc/ld.so.cache /etc/ld.so.cache --ro-bind /etc/hosts /etc/hosts \
  --dev /dev --proc /proc --tmpfs /tmp --bind "$BASE" "$BASE" \
  --ro-bind /home/hyl/.nvm/versions/node/v22.14.0 /node \
  --setenv PATH "${PYTHON%/*}:/node/bin:/usr/bin:/bin" \
  --setenv HOME /tmp --setenv PYTEST_DISABLE_PLUGIN_AUTOLOAD 1 \
  --setenv PYTHONHASHSEED 0 --setenv PYTHONDONTWRITEBYTECODE 1 \
  --setenv ARKSCOPE_DISABLE_SCHEDULER 1 --setenv ARKSCOPE_OFFLINE_TEST_WORKSPACE "$BASE/$RUN" \
  --setenv PROBE_EXPECT_SQLITE "$EXPECTED" \
  --setenv OPENAI_AGENTS_DISABLE_TRACING 1 --setenv LANG C.UTF-8 \
  --chdir "$BASE/source" \
  "$PYTHON" -I -B "$BASE/offline_pytest.py" "$@"
