"""
Antigravity Telegram Remote Bridge - Command Line Interface (CLI)
Entrypoint for `antigravity-bridge` and `agy-bridge`.
Supports both subcommands (status, setup, doctor, start) and flags (--status, --setup, --version).
"""
import sys
import os
import argparse
import urllib.request
import json
import ssl

# Ensure base directory is in sys.path for direct script invocations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

VERSION = "2.1.0"

def cmd_status():
    from core.config import load_config, get_config_path
    from core.agy_engine import get_agy_status_summary, find_agy_executable
    cfg = load_config()
    token = cfg.get("bot_token", "")
    chat_id = cfg.get("allowed_chat_id")

    print("\n" + "=" * 60)
    print("  🚀 Antigravity Telegram Remote Bridge CLI")
    print(f"  Version: {VERSION}")
    print("=" * 60)
    print(f"📁 Config File:         {get_config_path()}")
    print(f"🤖 Telegram Bot Token:  {'Configured ✅' if token and token != 'PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE' else 'Missing ❌'}")
    print(f"🔒 Paired Chat ID:      {chat_id or 'Unpaired (Open Mode)'}")
    print(f"⚡ AGY Binary:          {find_agy_executable()}")
    print("-" * 60)
    print(get_agy_status_summary().replace("*", "").replace("`", ""))
    print("=" * 60 + "\n")

def cmd_setup():
    wizard_path = os.path.join(BASE_DIR, "wizard.py")
    if os.path.exists(wizard_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("wizard", wizard_path)
        wizard_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wizard_mod)
        wizard_mod.run_wizard()
    else:
        print("Setup wizard not found at:", wizard_path)

def cmd_doctor():
    from core.config import load_config, get_config_path
    from core.agy_engine import find_agy_executable, get_working_directory
    print("\n" + "=" * 60)
    print("  🩺 ANTIGRAVITY TELEGRAM BRIDGE - SYSTEM DOCTOR")
    print("=" * 60)

    # 1. Python Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    print(f"[{'✓' if py_ok else '✗'}] Python Version:        {py_ver} ({'Supported' if py_ok else 'Requires 3.10+'})")

    # 2. OS Check
    print(f"[✓] Platform:              {sys.platform} ({os.name})")

    # 3. AGY Binary Check
    agy_bin = find_agy_executable()
    if agy_bin and (os.path.isfile(agy_bin) or shutil.which(agy_bin)):
        print(f"[✓] AGY Executable:        Found ({agy_bin})")
    else:
        print(f"[✗] AGY Executable:        Not found in PATH or standard directories")

    # 4. Telegram Connection Check
    cfg = load_config()
    token = cfg.get("bot_token", "")
    if token and token != "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "AntigravityDoctor"})
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                if data.get("ok"):
                    bot_user = data.get("result", {}).get("username")
                    print(f"[✓] Telegram Bot API:      Connected (@{bot_user})")
                else:
                    print(f"[✗] Telegram Bot API:      Token rejected by Telegram")
        except Exception as e:
            print(f"[✗] Telegram Bot API:      Connection error ({e})")
    else:
        print(f"[✗] Telegram Bot Token:    Missing in {get_config_path()}")

    # 5. Workspace Directory
    cwd = get_working_directory()
    if os.path.isdir(cwd):
        print(f"[✓] Workspace Directory:   Accessible ({cwd})")
    else:
        print(f"[✗] Workspace Directory:   Not found ({cwd})")

    print("=" * 60 + "\n")

def main():
    # Normalize subcommands like `status`, `setup`, `doctor`, `start` into flag equivalents
    if len(sys.argv) > 1:
        first = sys.argv[1].lower().strip()
        if first == "status":
            cmd_status()
            return
        elif first in ["setup", "config"]:
            cmd_setup()
            return
        elif first == "doctor":
            cmd_doctor()
            return
        elif first == "start":
            sys.argv.pop(1)  # Remove "start" and proceed to run bot

    parser = argparse.ArgumentParser(
        prog="antigravity-bridge",
        description="Remote Telegram bridge for Google Antigravity & AGY Terminal Engine."
    )
    parser.add_argument(
        "--setup", "-s",
        action="store_true",
        help="Launch the interactive setup wizard to configure Telegram bot token."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display bridge configuration and AGY status."
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run diagnostic check on environment, bot token, and AGY CLI."
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {VERSION}"
    )

    args = parser.parse_args()

    if args.setup:
        cmd_setup()
        return

    if args.status:
        cmd_status()
        return

    if args.doctor:
        cmd_doctor()
        return

    # Default action: run the bridge
    bridge_path = os.path.join(BASE_DIR, "bridge.py")
    if os.path.exists(bridge_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bridge", bridge_path)
        bridge_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge_mod)
        bridge_mod.run_bot()
    else:
        print("Error: Could not locate bridge.py at:", bridge_path)

if __name__ == "__main__":
    main()
