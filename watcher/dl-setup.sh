#!/usr/bin/env bash
# Download Watcher Setup — run this to configure for a new download
set -euo pipefail

CONFIG_DIR="$HOME/.config/download-watcher"
mkdir -p "$CONFIG_DIR"

DIR=$(zenity --title="Download Watcher" --text="Download directory path:" --entry 2>/dev/null)
[ -z "$DIR" ] && exit 1

TOTAL=$(zenity --title="Download Watcher" --text="Total expected files/shards:" --entry 2>/dev/null)
[ -z "$TOTAL" ] && exit 1

SERVICE=$(zenity --title="Download Watcher" --text="systemd service name (or leave blank):" --entry 2>/dev/null)

cat > "$CONFIG_DIR/config" << EOF
DIR="$DIR"
TOTAL_FILES="$TOTAL"
SERVICE="$SERVICE"
DASHBOARD_SCRIPT="\$HOME/.openclaw/workspace/scripts/dl-dashboard.py"
MONITOR_SCRIPT="\$HOME/.openclaw/workspace/scripts/dl-monitor.sh"
ALARM_WAV="\$HOME/.openclaw/workspace/scripts/dl-alarm.wav"
HEARTBEAT_WAV="\$HOME/.openclaw/workspace/scripts/dl-heartbeat.wav"
PORT=18999
STALL_SECONDS=300
EOF

echo "Config saved to $CONFIG_DIR/config"
echo ""
echo "Now run: dl-launcher"