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
HOST_PATH="$PROJECT_ROOT/scripts/sa_native_host.py"
MANIFEST_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"

echo "SA Alpha Picks — Native Messaging Host Installer"
echo "================================================="
echo "Project root: $PROJECT_ROOT"
echo "Native host:  $HOST_PATH"
echo ""

# Check Python script exists
if [ ! -f "$HOST_PATH" ]; then
    echo "ERROR: Native host script not found: $HOST_PATH"
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

# Write shebang with the correct Python path
sed -i "1s|^#!.*|#!${PYTHON_PATH}|" "$HOST_PATH"
echo "Shebang set to: #!${PYTHON_PATH}"

# Make executable
chmod +x "$HOST_PATH"

# Get extension ID
echo ""
read -p "Enter your extension ID (from chrome://extensions): " EXT_ID

if [ -z "$EXT_ID" ]; then
    echo "ERROR: Extension ID cannot be empty."
    exit 1
fi

# Create manifest directory
mkdir -p "$MANIFEST_DIR"

# Write manifest
MANIFEST_PATH="$MANIFEST_DIR/$HOST_NAME.json"
cat > "$MANIFEST_PATH" << EOF
{
  "name": "$HOST_NAME",
  "description": "SA Alpha Picks data bridge for MindfulRL",
  "path": "$HOST_PATH",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF

echo ""
echo "Native messaging host registered!"
echo "  Manifest: $MANIFEST_PATH"
echo "  Host:     $HOST_PATH"
echo "  Python:   $PYTHON_PATH"
echo "  Extension ID: $EXT_ID"
echo ""
echo "You can now use the extension. Click the SA Alpha Picks icon in Chrome to refresh data."