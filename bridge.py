"""
Antigravity Telegram Remote Bridge
Enterprise Modular Architecture v2.0
"""
import os
import sys
import time
import threading
import subprocess
import ctypes
import requests

from core.config import (
    BASE_DIR,
    CONFIG_FILE,
    load_config,
    save_config,
    send_telegram_message
)
from core.system_guard import inhibit_sleep
from core.transcript_watcher import start_transcript_watcher
from core.telegram_bot import handle_callback_query, handle_incoming_message

# Backwards compatibility & helper exports
from core.agent_api import (
    send_message_native,
    create_conversation_native,
    get_active_conversation_info
)
from core.window_driver import (
    find_antigravity_window,
    is_antigravity_active,
    focus_antigravity_safe,
    inject_prompt_to_antigravity,
    create_new_conversation,
    emergency_stop_antigravity
)
from core.models import AVAILABLE_MODELS, get_models_overview, switch_model_smart_vision
from core.projects import (
    get_projects_summary,
    get_single_project_summary,
    get_session_info,
    get_latest_conversation_transcript
)
from core.keyboards import (
    send_telegram_menu,
    send_models_menu,
    send_projects_menu,
    setup_bot_commands,
    send_persistent_keyboard
)
from core.system_guard import capture_and_send_screenshot

IS_WINDOWS = os.name == "nt"
SINGLE_INSTANCE_MUTEX = None
SINGLE_INSTANCE_FD = None

if IS_WINDOWS:
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.argtypes = []
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

def acquire_single_instance_lock():
    """Guarantees only one instance of Antigravity Telegram Bridge runs at any time."""
    global SINGLE_INSTANCE_MUTEX, SINGLE_INSTANCE_FD
    if IS_WINDOWS:
        ERROR_ALREADY_EXISTS = 183
        SINGLE_INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(
            None, False, "AntigravityTelegramBridgeSingleInstanceMutex"
        )
        last_err = ctypes.windll.kernel32.GetLastError()
        if last_err == ERROR_ALREADY_EXISTS:
            print("⚠️ Another instance of Antigravity Telegram Bridge is already running. Exiting.", flush=True)
            sys.exit(0)
    else:
        try:
            import fcntl
            lock_file = "/tmp/antigravity_bridge.lock"
            SINGLE_INSTANCE_FD = open(lock_file, "w")
            fcntl.flock(SINGLE_INSTANCE_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            print("⚠️ Another instance of Antigravity Telegram Bridge is already running. Exiting.", flush=True)
            sys.exit(0)
        except Exception:
            pass

def release_single_instance_lock():
    """Releases the single-instance lock."""
    global SINGLE_INSTANCE_MUTEX, SINGLE_INSTANCE_FD
    if IS_WINDOWS and SINGLE_INSTANCE_MUTEX:
        ctypes.windll.kernel32.CloseHandle(SINGLE_INSTANCE_MUTEX)
        SINGLE_INSTANCE_MUTEX = None
    elif SINGLE_INSTANCE_FD:
        try:
            import fcntl
            fcntl.flock(SINGLE_INSTANCE_FD, fcntl.LOCK_UN)
            SINGLE_INSTANCE_FD.close()
        except Exception:
            pass
        SINGLE_INSTANCE_FD = None

def restart_bridge():
    """Restarts the Python bridge process cleanly (relies on run_bridge.bat loop)."""
    print("🔄 Restarting Antigravity Bridge...", flush=True)
    inhibit_sleep(False)
    release_single_instance_lock()
    time.sleep(0.3)
    os._exit(0)

def get_watched_files_mtime() -> float:
    """Computes the maximum mtime across bridge.py, config.json, and all files in core/."""
    mtimes = []
    self_path = os.path.abspath(__file__)
    if os.path.exists(self_path):
        mtimes.append(os.path.getmtime(self_path))
    if os.path.exists(CONFIG_FILE):
        mtimes.append(os.path.getmtime(CONFIG_FILE))

    core_dir = os.path.join(BASE_DIR, "core")
    if os.path.exists(core_dir):
        for root, dirs, files in os.walk(core_dir):
            for f in files:
                if f.endswith(".py"):
                    p = os.path.join(root, f)
                    try:
                        mtimes.append(os.path.getmtime(p))
                    except Exception:
                        pass
    return max(mtimes) if mtimes else 0.0

def start_file_watcher(token, get_chat_id_func):
    """Watches bridge.py, core/*.py, and config.json for code edits and hot-reloads instantly."""
    last_mtime = get_watched_files_mtime()
    print("⚡ Auto-reload watcher active (monitoring core modules & config)!", flush=True)

    while True:
        time.sleep(1.5)
        try:
            current_mtime = get_watched_files_mtime()
            if current_mtime > last_mtime:
                # Debounce to ensure file writes are fully flushed to disk
                time.sleep(1.0)
                last_mtime = get_watched_files_mtime()
                print("🔄 Code change detected in core architecture! Auto-reloading bridge...", flush=True)
                # Restart bridge silently without spamming Telegram
                restart_bridge()
        except Exception:
            pass

def run_bot():
    # 0. Single instance lock
    acquire_single_instance_lock()

    # 1. Enable Windows sleep inhibitor to prevent computer sleeping during remote control
    inhibit_sleep(True)

    # 2. Load credentials
    cfg = load_config()
    token = cfg.get("bot_token", "").strip()
    allowed_chat_id = cfg.get("allowed_chat_id")

    if not token or token == "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("=" * 60)
        print("ERROR: Telegram Bot Token is not configured!")
        print(f"Please open:\n{CONFIG_FILE}")
        print("and paste your bot token obtained from @BotFather.")
        print("=" * 60)
        input("Press Enter to exit...")
        sys.exit(1)

    # 2b. Register native Telegram [/] Menu button commands
    setup_bot_commands(token)

    # 3. Start live transcript watcher
    watcher = threading.Thread(
        target=start_transcript_watcher,
        args=(token, lambda: cfg.get("allowed_chat_id")),
        daemon=True
    )
    watcher.start()

    # 4. Start hot-reload file watcher
    file_watcher = threading.Thread(
        target=start_file_watcher,
        args=(token, lambda: cfg.get("allowed_chat_id")),
        daemon=True
    )
    file_watcher.start()

    print("=" * 60)
    print("🚀 Antigravity Telegram Remote Bridge is RUNNING (Modular Architecture v2.0)!")
    print(f"Directory: {BASE_DIR}")
    print(f"Config: {CONFIG_FILE}")
    if allowed_chat_id:
        print(f"🔒 Bound to Chat ID: {allowed_chat_id}")
    else:
        print("🔓 Open mode: Send /start from your phone's Telegram to lock this bridge to your account.")
    print("=" * 60)

    last_update_id = 0
    poll_url = f"https://api.telegram.org/bot{token}/getUpdates"

    while True:
        try:
            params = {"offset": last_update_id + 1, "timeout": 20}
            resp = requests.get(poll_url, params=params, timeout=25)
            if resp.status_code != 200:
                time.sleep(2)
                continue

            data = resp.json()
            updates = data.get("result", [])

            for update in updates:
                last_update_id = update["update_id"]

                # A. Handle Callback Query (Inline Button Click)
                cb_query = update.get("callback_query")
                if cb_query:
                    handle_callback_query(token, cb_query, cfg.get("allowed_chat_id"))
                    continue

                # B. Handle Incoming Message (Text or Photo)
                msg = update.get("message")
                if msg:
                    handle_incoming_message(token, msg, cfg, restart_bridge)

        except requests.exceptions.RequestException:
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error in bot polling loop: {e}", flush=True)
            time.sleep(2)

if __name__ == "__main__":
    try:
        run_bot()
    finally:
        release_single_instance_lock()
        inhibit_sleep(False)
