#!/bin/bash
# Uninstall Native Messaging host for SA Alpha Picks.

HOST_NAME="com.mindfulrl.sa_alpha_picks"
CHROME_MANIFEST_PATH="$HOME/.config/google-chrome/NativeMessagingHosts/$HOST_NAME.json"
FIREFOX_MANIFEST_PATH="$HOME/.mozilla/native-messaging-hosts/$HOST_NAME.json"
LAUNCHER_PATH="${ARKSCOPE_NATIVE_HOST_DIR:-$HOME/.local/share/arkscope/native-hosts}/sa_alpha_picks_host.sh"
CONFIG_PATH="${ARKSCOPE_CONFIG_DIR:-$HOME/.config/arkscope}/sa_native_host.json"

for path in "$CHROME_MANIFEST_PATH" "$FIREFOX_MANIFEST_PATH" "$LAUNCHER_PATH" "$CONFIG_PATH"; do
    if [ -f "$path" ]; then
        rm "$path"
        echo "Removed: $path"
    else
        echo "Not found: $path"
    fi
done

echo ""
echo "To fully remove, also remove the extension from chrome://extensions and about:debugging."
