#!/bin/bash
# Build and install the Firefox Native Messaging host for SA Alpha Picks.
#
# This does not modify the Chrome manifest or Chrome native-host registration.
# It creates an ignored Firefox load directory under build/firefox/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_NAME="com.mindfulrl.sa_alpha_picks"
ADDON_ID="${SA_ALPHA_PICKS_FIREFOX_ID:-sa-alpha-picks@mindfulrl.local}"
HOST_SCRIPT="$PROJECT_ROOT/scripts/sa_native_host.py"
LAUNCHER_SOURCE="$SCRIPT_DIR/native_host_launcher.sh"
LAUNCHER_DIR="${ARKSCOPE_NATIVE_HOST_DIR:-$HOME/.local/share/arkscope/native-hosts}"
LAUNCHER_PATH="$LAUNCHER_DIR/sa_alpha_picks_host.sh"
CONFIG_DIR="${ARKSCOPE_CONFIG_DIR:-$HOME/.config/arkscope}"
CONFIG_PATH="$CONFIG_DIR/sa_native_host.json"
BUILD_DIR="$SCRIPT_DIR/build/firefox"
MANIFEST_DIR="${MOZILLA_NATIVE_MESSAGING_DIR:-$HOME/.mozilla/native-messaging-hosts}"
NATIVE_MANIFEST_PATH="$MANIFEST_DIR/$HOST_NAME.json"

echo "SA Alpha Picks — Firefox Installer"
echo "=================================="
echo "Project root: $PROJECT_ROOT"
echo "Add-on ID:    $ADDON_ID"
echo "Launcher:     $LAUNCHER_PATH"
echo "Config:       $CONFIG_PATH"
echo ""

if [ ! -f "$HOST_SCRIPT" ]; then
    echo "ERROR: Native host script not found: $HOST_SCRIPT"
    exit 1
fi

if [ ! -f "$LAUNCHER_SOURCE" ]; then
    echo "ERROR: Native host launcher template not found: $LAUNCHER_SOURCE"
    exit 1
fi

PYTHON_PATH=""
if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python3" ]; then
    PYTHON_PATH="$VIRTUAL_ENV/bin/python3"
elif [ -x "$PROJECT_ROOT/.venv/bin/python3" ]; then
    PYTHON_PATH="$PROJECT_ROOT/.venv/bin/python3"
else
    PYTHON_PATH="$(command -v python3 || true)"
fi

if [ -n "$PYTHON_PATH" ] && "$PYTHON_PATH" -c "import psycopg2" 2>/dev/null; then
    echo "Python: $PYTHON_PATH (psycopg2 OK)"
else
    echo "WARNING: ${PYTHON_PATH:-python3} cannot import psycopg2."
    echo "Enter the full path to the virtualenv python3 used by this project:"
    read -r -p "Python path: " PYTHON_PATH
    if ! "$PYTHON_PATH" -c "import psycopg2" 2>/dev/null; then
        echo "ERROR: $PYTHON_PATH still cannot import psycopg2."
        exit 1
    fi
fi

mkdir -p "$LAUNCHER_DIR" "$CONFIG_DIR"
cp "$LAUNCHER_SOURCE" "$LAUNCHER_PATH"
chmod +x "$LAUNCHER_PATH"

"$PYTHON_PATH" - "$PROJECT_ROOT" "$PYTHON_PATH" "$HOST_SCRIPT" "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

project_root, python_path, host_script, config_path = sys.argv[1:]
Path(config_path).write_text(
    json.dumps(
        {
            "project_root": project_root,
            "python_path": python_path,
            "host_script": host_script,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cp "$SCRIPT_DIR/manifest.firefox.json" "$BUILD_DIR/manifest.json"
cp "$SCRIPT_DIR/background.js" "$BUILD_DIR/background.js"
cp "$SCRIPT_DIR/compat_firefox.js" "$BUILD_DIR/compat_firefox.js"
cp "$SCRIPT_DIR/popup.js" "$BUILD_DIR/popup.js"
cp "$SCRIPT_DIR/popup.html" "$BUILD_DIR/popup.html"
cp "$SCRIPT_DIR"/scrape*.js "$BUILD_DIR/"

sed -i 's#<script src="popup.js"></script>#<script src="compat_firefox.js"></script>\
  <script src="popup.js"></script>#' "$BUILD_DIR/popup.html"
if ! grep -q 'compat_firefox.js' "$BUILD_DIR/popup.html"; then
    echo "ERROR: Failed to inject compat_firefox.js into generated popup.html"
    exit 1
fi

mkdir -p "$MANIFEST_DIR"
cat > "$NATIVE_MANIFEST_PATH" << EOF
{
  "name": "$HOST_NAME",
  "description": "SA Alpha Picks data bridge for ArkScope",
  "path": "$LAUNCHER_PATH",
  "type": "stdio",
  "allowed_extensions": ["$ADDON_ID"]
}
EOF

echo ""
echo "Firefox build and native host registered."
echo "  Extension build: $BUILD_DIR"
echo "  Native manifest: $NATIVE_MANIFEST_PATH"
echo "  Launcher:        $LAUNCHER_PATH"
echo "  Config:          $CONFIG_PATH"
echo "  Native host:     $HOST_SCRIPT"
echo "  Python:          $PYTHON_PATH"
echo ""
echo "Load in Firefox:"
echo "  1. Open about:debugging#/runtime/this-firefox"
echo "  2. Click 'Load Temporary Add-on...'"
echo "  3. Select: $BUILD_DIR/manifest.json"
echo "     Do NOT select: $SCRIPT_DIR/manifest.json (Chrome build)"
echo ""
echo "After loading, sign in to Seeking Alpha in Firefox, then run Quick Refresh."
