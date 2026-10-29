#!/usr/bin/env bash
# Antigravity Telegram Remote Bridge - Unix Daemon Loop (macOS & Linux)
cd "$(dirname "$0")" || exit 1

echo "=========================================================="
echo " 🚀 Starting Antigravity Telegram Remote Bridge (AGY Engine)"
echo "=========================================================="

while true; do
    python3 -u bridge.py
    EXIT_CODE=$?
    echo "⚠️ Bridge stopped with exit code $EXIT_CODE. Restarting in 2 seconds..."
    sleep 2
done
