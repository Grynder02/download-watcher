#!/usr/bin/env bash
# Download Watcher Launcher — click, pin to taskbar, run from terminal
CONFIG="$HOME/.config/download-watcher/config"
PIDFILE="/tmp/dl-dashboard.pid"
DASHBOARD_SCRIPT="$HOME/.openclaw/workspace/scripts/dl-dashboard.py"

mkdir -p "$HOME/.config/download-watcher"

# If already running, just open the page
if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
  xdg-open "http://localhost:18999" 2>/dev/null
  exit 0
fi

# No config? prompt to set up
if [ ! -f "$CONFIG" ]; then
  exec bash "$HOME/.openclaw/workspace/scripts/dl-setup.sh"
  exit 0
fi

source "$CONFIG"

pkill -f 'dl-dashboard\\.py' 2>/dev/null
sleep 0.5
nohup python3 "$DASHBOARD_SCRIPT" > /dev/null 2>&1 &
echo $! > "$PIDFILE"
sleep 1
xdg-open "http://localhost:18999" 2>/dev/null