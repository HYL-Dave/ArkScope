#!/bin/bash
# Install Native Messaging host for SA Alpha Picks Chrome extension.
#
# Usage:
#   1. Load extension in chrome://extensions (developer mode, load unpacked)
#   2. Copy the extension ID from chrome://extensions
#   3. Run: bash extensions/sa_alpha_picks/install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOST_NAME="com.mindfulrl.sa_alpha_picks"
HOST_PATH="$PROJECT_ROOT/src/sa_native_host.py"
LAUNCHER_SOURCE="$SCRIPT_DIR/native_host_launcher.sh"
LAUNCHER_DIR="${ARKSCOPE_NATIVE_HOST_DIR:-$HOME/.local/share/arkscope/native-hosts}"
LAUNCHER_PATH="$LAUNCHER_DIR/sa_alpha_picks_host.sh"
CONFIG_DIR="${ARKSCOPE_CONFIG_DIR:-$HOME/.config/arkscope}"
CONFIG_PATH="$CONFIG_DIR/sa_native_host.json"
MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
MANIFEST_PATH="$MANIFEST_DIR/$HOST_NAME.json"

echo "SA Alpha Picks — Native Messaging Host Installer"
echo "================================================="
echo "Project root: $PROJECT_ROOT"
echo "Native host:  $HOST_PATH"
echo "Launcher:     $LAUNCHER_PATH"
echo "Config:       $CONFIG_PATH"
echo ""

# Check Python script exists
if [ ! -f "$HOST_PATH" ]; then
    echo "ERROR: Native host script not found: $HOST_PATH"
    exit 1
fi

if [ ! -f "$LAUNCHER_SOURCE" ]; then
    echo "ERROR: Native host launcher template not found: $LAUNCHER_SOURCE"
    exit 1
fi

# Detect Python interpreter with required dependencies
# Priority: active virtualenv > VIRTUAL_ENV env var > project .venv > system python3
PYTHON_PATH=""
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_PATH="$VIRTUAL_ENV/bin/python3"
elif [ -f "$PROJECT_ROOT/.venv/bin/python3" ]; then
    PYTHON_PATH="$PROJECT_ROOT/.venv/bin/python3"
else
    PYTHON_PATH="$(which python3 2>/dev/null)"
fi

# Verify the interpreter can import psycopg2 (needed by DAL)
if [ -n "$PYTHON_PATH" ] && "$PYTHON_PATH" -c "import psycopg2" 2>/dev/null; then
    echo "Python: $PYTHON_PATH (psycopg2 OK)"
else
    echo "WARNING: $PYTHON_PATH cannot import psycopg2."
    echo "  Enter the full path to your virtualenv's python3:"
    read -p "  Python path: " PYTHON_PATH
    if ! "$PYTHON_PATH" -c "import psycopg2" 2>/dev/null; then
        echo "ERROR: $PYTHON_PATH still cannot import psycopg2."
        exit 1
    fi
fi

# Install stable launcher and repo-specific config.
mkdir -p "$LAUNCHER_DIR" "$CONFIG_DIR"
cp "$LAUNCHER_SOURCE" "$LAUNCHER_PATH"
chmod +x "$LAUNCHER_PATH"

"$PYTHON_PATH" - "$PROJECT_ROOT" "$PYTHON_PATH" "$HOST_PATH" "$CONFIG_PATH" <<'PY'
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

# Get extension ID
echo ""
DEFAULT_EXT_ID=""
if [ -f "$MANIFEST_PATH" ]; then
    DEFAULT_EXT_ID="$(python3 - "$MANIFEST_PATH" <<'PY' 2>/dev/null || true
import json
import re
import sys

try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    origins = data.get("allowed_origins") or []
    if origins:
        match = re.match(r"chrome-extension://([^/]+)/", origins[0])
        if match:
            print(match.group(1))
except Exception:
    pass
PY
)"
fi

if [ -n "$DEFAULT_EXT_ID" ]; then
    read -p "Enter your extension ID (from chrome://extensions) [$DEFAULT_EXT_ID]: " EXT_ID
    EXT_ID="${EXT_ID:-$DEFAULT_EXT_ID}"
else
    read -p "Enter your extension ID (from chrome://extensions): " EXT_ID
fi

if [ -z "$EXT_ID" ]; then
    echo "ERROR: Extension ID cannot be empty."
    exit 1
fi

# Create manifest directory
mkdir -p "$MANIFEST_DIR"

# Write manifest
cat > "$MANIFEST_PATH" << EOF
{
  "name": "$HOST_NAME",
  "description": "SA Alpha Picks data bridge for ArkScope",
  "path": "$LAUNCHER_PATH",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF

echo ""
echo "Native messaging host registered!"
echo "  Manifest: $MANIFEST_PATH"
echo "  Launcher: $LAUNCHER_PATH"
echo "  Config:   $CONFIG_PATH"
echo "  Host:     $HOST_PATH"
echo "  Python:   $PYTHON_PATH"
echo "  Extension ID: $EXT_ID"
echo ""
echo "You can now use the extension. Click the SA Alpha Picks icon in Chrome to refresh data."
