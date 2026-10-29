#!/usr/bin/env bash
# Antigravity Telegram Remote Bridge - 1-Line Unix Installer (macOS & Linux)
# Usage: curl -fsSL https://raw.githubusercontent.com/DominceAseberos/Antigravity-Telegram-bridge/main/install.sh | bash

set -e

echo ""
echo "=========================================================="
echo "  🚀 Antigravity Telegram Remote Bridge - Installer"
echo "=========================================================="
echo ""

# 1. Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 could not be found."
    echo "Please install Python 3.10+ and rerun this command."
    exit 1
fi

# 2. Installation Directory
INSTALL_DIR="$HOME/.antigravity-telegram-bridge"
echo "📦 Installing to: $INSTALL_DIR"

if [ -d "$INSTALL_DIR" ]; then
    echo "🔄 Updating existing installation..."
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR" && git pull --quiet
    fi
else
    if command -v git &>/dev/null; then
        git clone --quiet https://github.com/DominceAseberos/Antigravity-Telegram-bridge.git "$INSTALL_DIR"
    else
        echo "⏳ Downloading repository archive..."
        TMP_ZIP="/tmp/antigravity-bridge.zip"
        curl -fsSL "https://github.com/DominceAseberos/Antigravity-Telegram-bridge/archive/refs/heads/main.zip" -o "$TMP_ZIP"
        unzip -q "$TMP_ZIP" -d /tmp
        mv /tmp/Antigravity-Telegram-bridge-main "$INSTALL_DIR"
        rm -f "$TMP_ZIP"
    fi
fi

# 3. Install Dependencies
echo "⏳ Installing required Python dependencies..."
python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --quiet

# 4. Create Global CLI Launcher
mkdir -p "$HOME/.local/bin"
LAUNCHER="$HOME/.local/bin/antigravity-bridge"
cat << 'EOF' > "$LAUNCHER"
#!/usr/bin/env bash
python3 "$HOME/.antigravity-telegram-bridge/bridge.py" "$@"
EOF
chmod +x "$LAUNCHER"

echo "✅ Installation complete!"
echo ""

# 5. Run Interactive Setup Wizard
cd "$INSTALL_DIR"
python3 setup.py
