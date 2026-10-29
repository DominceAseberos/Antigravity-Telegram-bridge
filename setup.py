"""
Antigravity Telegram Remote Bridge - Interactive Setup Wizard
Guides users through Telegram bot creation, token verification,
pairing, and desktop shortcut generation.
"""
import os
import sys
import json
import time
import shutil
import urllib.request
import webbrowser
from typing import List, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICON_ICO = os.path.join(ASSETS_DIR, "icon.ico")
ICON_PNG = os.path.join(ASSETS_DIR, "icon.png")

# --- Interactive Terminal Arrow Selector ---

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def get_key():
    """Reads a single keypress across Windows and Unix platforms."""
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ch2 = msvcrt.getch()
            if ch2 == b"H":
                return "UP"
            elif ch2 == b"P":
                return "DOWN"
        elif ch in (b"\r", b"\n"):
            return "ENTER"
        elif ch == b"\x03":
            raise KeyboardInterrupt
        return ch.decode("latin1", errors="ignore")
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                ch3 = sys.stdin.read(1)
                if ch3 == "A":
                    return "UP"
                elif ch3 == "B":
                    return "DOWN"
            elif ch in ("\r", "\n"):
                return "ENTER"
            elif ch == "\x03":
                raise KeyboardInterrupt
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def prompt_choice(question: str, options: List[str], default_idx: int = 0) -> int:
    """Renders an interactive menu navigated via Up/Down arrow keys or numbers."""
    selected = default_idx
    num_opts = len(options)

    # Check if stdin is interactive terminal
    if not sys.stdin.isatty():
        print(f"\n{question}")
        for i, opt in enumerate(options):
            print(f"  [{i + 1}] {opt}")
        choice = input(f"Select option (1-{num_opts}) [1]: ").strip()
        return (int(choice) - 1) if choice.isdigit() and 1 <= int(choice) <= num_opts else 0

    print("\n" + question)
    print("  \033[90m(Use ↑/↓ arrow keys to navigate, Enter to select)\033[0m")

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            for i, opt in enumerate(options):
                if i == selected:
                    sys.stdout.write(f"\r  \033[1;36m❯ [ {opt} ]\033[0m    \n")
                else:
                    sys.stdout.write(f"\r    {opt}        \n")

            # Move cursor back up
            sys.stdout.write(f"\033[{num_opts}A")
            sys.stdout.flush()

            key = get_key()
            if key == "UP":
                selected = (selected - 1) % num_opts
            elif key == "DOWN":
                selected = (selected + 1) % num_opts
            elif key == "ENTER":
                # Move cursor past options
                sys.stdout.write(f"\033[{num_opts}B\n")
                sys.stdout.flush()
                return selected
            elif key in [str(i + 1) for i in range(num_opts)]:
                sys.stdout.write(f"\033[{num_opts}B\n")
                sys.stdout.flush()
                return int(key) - 1
    finally:
        # Restore cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

# --- Telegram API Verification ---

def verify_bot_token(token: str) -> Tuple[bool, dict]:
    """Tests a Telegram Bot Token against Telegram API."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AntigravitySetupWizard"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return True, data.get("result", {})
    except Exception:
        pass
    return False, {}

# --- Desktop Shortcut Creators ---

def get_desktop_path() -> str:
    """Returns the user's Desktop directory path."""
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), "Desktop")
    return os.path.join(os.path.expanduser("~"), "Desktop")

def create_windows_shortcut(target_bat: str, shortcut_name: str = "Antigravity Telegram Bridge.lnk") -> bool:
    """Creates a Windows .lnk desktop shortcut with icon."""
    try:
        import subprocess
        desktop = get_desktop_path()
        shortcut_path = os.path.join(desktop, shortcut_name)
        vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_bat}"
oLink.WorkingDirectory = "{BASE_DIR}"
oLink.Description = "Antigravity Telegram Remote Bridge"
If "{os.path.exists(ICON_ICO)}" = "True" Then
    oLink.IconLocation = "{ICON_ICO},0"
End If
oLink.Save
"""
        vbs_file = os.path.join(BASE_DIR, "_temp_shortcut.vbs")
        with open(vbs_file, "w", encoding="utf-8") as f:
            f.write(vbs_script)
        subprocess.run(["cscript", "//nologo", vbs_file], check=True, capture_output=True)
        if os.path.exists(vbs_file):
            os.remove(vbs_file)
        return os.path.exists(shortcut_path)
    except Exception as e:
        print(f"Error creating Windows shortcut: {e}")
        return False

def create_unix_desktop_file() -> bool:
    """Creates a Linux/macOS desktop launcher."""
    desktop = get_desktop_path()
    if sys.platform == "darwin":
        # macOS command launcher
        cmd_path = os.path.join(desktop, "Antigravity Bridge.command")
        try:
            with open(cmd_path, "w", encoding="utf-8") as f:
                f.write(f"#!/bin/bash\ncd \"{BASE_DIR}\"\npython3 bridge.py\n")
            os.chmod(cmd_path, 0o755)
            return True
        except Exception:
            return False
    else:
        # Linux .desktop file
        desktop_file = os.path.join(desktop, "antigravity-bridge.desktop")
        try:
            with open(desktop_file, "w", encoding="utf-8") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=Antigravity Telegram Bridge
Exec=python3 "{os.path.join(BASE_DIR, 'bridge.py')}"
Path={BASE_DIR}
Icon={ICON_PNG}
Terminal=true
Categories=Development;
""")
            os.chmod(desktop_file, 0o755)
            return True
        except Exception:
            return False

# --- Main Setup Flow ---

def run_wizard():
    print("=" * 65)
    print("  🚀  ANTIGRAVITY TELEGRAM REMOTE BRIDGE SETUP WIZARD")
    print("  Control your AI development environment headlessly via Telegram")
    print("=" * 65)

    # 1. Check existing config
    token = ""
    allowed_chat_id = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                existing_cfg = json.load(f)
                token = existing_cfg.get("bot_token", "").strip()
                allowed_chat_id = existing_cfg.get("allowed_chat_id")
        except Exception:
            pass

    has_valid_token = False
    bot_info = {}
    if token and token != "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        valid, info = verify_bot_token(token)
        if valid:
            has_valid_token = True
            bot_info = info
            print(f"\n✅ Existing bot token verified: @{bot_info.get('username')}")

    # Step 1: Telegram Bot Token Setup
    if not has_valid_token:
        print("\n\033[1mSTEP 1: Telegram Bot Token\033[0m")
        print("To control Antigravity from Telegram, you need a free Telegram Bot.")

        opt = prompt_choice(
            "Do you already have a Telegram Bot Token?",
            [
                "No, open @BotFather in my browser to create one (Recommended)",
                "Yes, I already have my bot token ready"
            ]
        )

        if opt == 0:
            print("\n🌐 Opening https://t.me/BotFather in your default browser...")
            webbrowser.open("https://t.me/BotFather")
            time.sleep(1)
            print("\n📋 \033[1mQuick 3-Step Bot Creation in Telegram:\033[0m")
            print("  1. In the chat with @BotFather, send: \033[1;36m/newbot\033[0m")
            print("  2. Enter a display name (e.g. \033[33mMy Antigravity\033[0m)")
            print("  3. Choose a username ending in 'bot' (e.g. \033[33mmy_antigravity_bot\033[0m)")
            print("  4. Copy the HTTP API token BotFather replies with.")

        while True:
            raw_token = input("\n🔑 Paste your Telegram Bot Token here: ").strip()
            if not raw_token:
                continue

            print("⏳ Verifying bot token with Telegram API...", end="", flush=True)
            valid, info = verify_bot_token(raw_token)
            if valid:
                print(f"\r✅ Verified successfully! Connected to: \033[1;32m@{info.get('username')}\033[0m ({info.get('first_name')})")
                token = raw_token
                bot_info = info
                break
            else:
                print("\r❌ Invalid Bot Token. Please ensure you copied the entire token string from @BotFather.")

    # Save Config
    cfg_data = {
        "bot_token": token,
        "allowed_chat_id": allowed_chat_id
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, indent=2)
    print(f"💾 Saved configuration to `{CONFIG_FILE}`.")

    # Offer to open bot in Telegram
    bot_username = bot_info.get("username")
    if bot_username:
        open_bot = prompt_choice(
            f"Would you like to open @{bot_username} in Telegram now to prepare pairing?",
            [
                f"Yes, open https://t.me/{bot_username} (Web / App)",
                "No, I will open it manually later"
            ]
        )
        if open_bot == 0:
            webbrowser.open(f"https://t.me/{bot_username}")
            print(f"👉 Opened @{bot_username}. When the bridge starts, send \033[1;36m/start\033[0m to pair your phone!")

    # Step 2: Desktop Shortcut & Icon
    print("\n\033[1mSTEP 2: Desktop App Shortcut\033[0m")
    add_shortcut = prompt_choice(
        "Would you like to create a Desktop App Shortcut with the custom icon?",
        [
            "Yes, add shortcut to my Desktop (Recommended)",
            "No, I will only run it via terminal"
        ]
    )

    if add_shortcut == 0:
        bat_path = os.path.join(BASE_DIR, "run_bridge.bat")
        if os.name == "nt":
            if create_windows_shortcut(bat_path):
                print("✨ \033[1;32mDesktop Shortcut created successfully!\033[0m Look for 'Antigravity Telegram Bridge' on your Desktop.")
            else:
                print("⚠️ Could not create desktop shortcut automatically. You can use run_bridge.bat.")
        else:
            if create_unix_desktop_file():
                print("✨ \033[1;32mDesktop launcher created successfully!\033[0m")
            else:
                print("⚠️ Could not create desktop launcher automatically.")

    # Step 3: Launch Option
    print("\n\033[1mSTEP 3: Launch Bridge\033[0m")
    launch_now = prompt_choice(
        "Setup is complete! Would you like to launch the bridge right now?",
        [
            "🚀 Yes, start the bridge now!",
            "Exit setup (I will launch it later)"
        ]
    )

    if launch_now == 0:
        print("\n🚀 Starting Antigravity Telegram Remote Bridge...\n")
        time.sleep(1)
        import subprocess
        if os.name == "nt":
            os.system(f'cmd /c "{os.path.join(BASE_DIR, "run_bridge.bat")}"')
        else:
            os.system(f'python3 "{os.path.join(BASE_DIR, "bridge.py")}"')
    else:
        print("\n🎉 Setup complete! Whenever you want to run the bridge, run:")
        print("   \033[1;36mrun_bridge.bat\033[0m (Windows) or \033[1;36mpython bridge.py\033[0m (Mac/Linux)")
        print("   or double-click the Desktop App icon.")

if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
