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

# Make executable
chmod +x "$HOST_PATH"

# Get extension ID
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
echo "  Extension ID: $EXT_ID"
echo ""
echo "You can now use the extension. Click the SA Alpha Picks icon in Chrome to refresh data."
