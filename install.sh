#!/usr/bin/env bash
# Download Watcher - Quick Install
set -euo pipefail

INSTALL_DIR="${1:-$HOME/.local/share/download-watcher}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "⚡ Installing Download Watcher to $INSTALL_DIR"

mkdir -p "$INSTALL_DIR/watcher"
mkdir -p "$INSTALL_DIR/examples"

# Copy all files
cp -r "$SCRIPT_DIR/watcher/"* "$INSTALL_DIR/watcher/"
cp -r "$SCRIPT_DIR/examples/"* "$INSTALL_DIR/examples/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/desktop/"* "$INSTALL_DIR/desktop/" 2>/dev/null || true

# Chmod scripts
chmod +x "$INSTALL_DIR/watcher"/*.sh "$INSTALL_DIR/watcher"/*.py 2>/dev/null

# Install desktop entry
if [ -d "$HOME/.local/share/applications" ]; then
  sed "s|Exec=.*|Exec=$INSTALL_DIR/watcher/dl-launcher.sh|" \
    "$SCRIPT_DIR/desktop/download-watcher.desktop" > \
    "$HOME/.local/share/applications/download-watcher.desktop" 2>/dev/null || true
fi

# Setup config dir
mkdir -p "$HOME/.config/download-watcher"

# Symlink for PATH access
if [ -d "$HOME/.local/bin" ]; then
  ln -sf "$INSTALL_DIR/watcher/dl-launcher.sh" "$HOME/.local/bin/dl-watcher"
  ln -sf "$INSTALL_DIR/watcher/dl-setup.sh" "$HOME/.local/bin/dl-watcher-setup"
fi

echo ""
echo "✅ Download Watcher installed!"
echo ""
echo "Quick start:"
echo "  1. Run:  dl-watcher-setup"
echo "  2. Enter your download details"
echo "  3. Run:  dl-watcher"
echo ""
echo "Or search 'Download Watcher' in your app menu."
echo ""
echo "For help: cat $INSTALL_DIR/README.md"