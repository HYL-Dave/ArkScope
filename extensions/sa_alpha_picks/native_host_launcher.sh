#!/bin/sh
# Stable Native Messaging launcher for SA Alpha Picks.
#
# Browser manifests should point to a copy of this script outside the repo.
# Repo-specific paths live in ~/.config/arkscope/sa_native_host.json, so a
# project directory rename only requires updating config, not browser manifests.

set -eu

CONFIG_PATH="${ARKSCOPE_SA_NATIVE_HOST_CONFIG:-$HOME/.config/arkscope/sa_native_host.json}"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "SA native host config not found: $CONFIG_PATH" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required to read $CONFIG_PATH" >&2
    exit 1
fi

read_config() {
    key="$1"
    python3 -c 'import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
key = sys.argv[2]
if key == "host_script":
    value = cfg.get("host_script") or (cfg.get("project_root", "") + "/scripts/sa_native_host.py")
else:
    value = cfg.get(key)
if not value:
    raise SystemExit(f"missing required config key: {key}")
print(value)
' "$CONFIG_PATH" "$key"
}

PROJECT_ROOT="$(read_config project_root)"
PYTHON_PATH="$(read_config python_path)"
HOST_SCRIPT="$(read_config host_script)"

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Project root not found: $PROJECT_ROOT" >&2
    exit 1
fi

if [ ! -x "$PYTHON_PATH" ]; then
    echo "Configured python is not executable: $PYTHON_PATH" >&2
    exit 1
fi

if [ ! -f "$HOST_SCRIPT" ]; then
    echo "Native host script not found: $HOST_SCRIPT" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
exec "$PYTHON_PATH" "$HOST_SCRIPT"
