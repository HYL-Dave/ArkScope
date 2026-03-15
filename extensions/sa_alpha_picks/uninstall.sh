#!/bin/bash
# Uninstall Native Messaging host for SA Alpha Picks.

HOST_NAME="com.mindfulrl.sa_alpha_picks"
MANIFEST_PATH="$HOME/.config/google-chrome/NativeMessagingHosts/$HOST_NAME.json"

if [ -f "$MANIFEST_PATH" ]; then
    rm "$MANIFEST_PATH"
    echo "Removed: $MANIFEST_PATH"
else
    echo "Not found: $MANIFEST_PATH (already uninstalled?)"
fi

echo ""
echo "To fully remove, also remove the extension from chrome://extensions."
