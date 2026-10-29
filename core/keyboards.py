import requests
from .agy_engine import get_available_projects, get_working_directory, get_current_model_alias

def setup_bot_commands(token: str) -> bool:
    """Registers bot commands with Telegram to display the native [/] Menu button."""
    url = f"https://api.telegram.org/bot{token}/setMyCommands"
    commands = [
        {"command": "menu", "description": "🎛️ Open Control Menu"},
        {"command": "new", "description": "✨ Start Fresh Chat Session"},
        {"command": "model", "description": "🧠 Switch AI Model"},
        {"command": "projects", "description": "📁 Select Project / Workspace"},
        {"command": "git", "description": "🌿 Git Status & Shortcuts"},
        {"command": "run", "description": "💻 Execute Shell Command"},
        {"command": "file", "description": "📦 Download Project File"},
        {"command": "status", "description": "📊 Check AGY Terminal Status"},
        {"command": "stop", "description": "🛑 Abort Running Task"},
        {"command": "recent", "description": "📜 View Latest Output"},
        {"command": "keyboard", "description": "⌨️ Toggle Bottom Keyboard"},
        {"command": "screenshot", "description": "📸 Instant PC Screenshot"},
        {"command": "help", "description": "❓ Help & Usage Guide"},
    ]
    try:
        r = requests.post(url, json={"commands": commands}, timeout=10, verify=False)
        return r.status_code == 200
    except Exception as e:
        print(f"Error setting bot commands: {e}", flush=True)
        return False

def send_persistent_keyboard(token: str, chat_id: int, text: str = "⌨️ *Persistent Keyboard Attached:*"):
    """Attaches quick 1-tap reply buttons pinned to the phone's bottom chat bar."""
    keyboard = {
        "keyboard": [
            [{"text": "✨ New Session"}, {"text": "🧠 Switch Model"}],
            [{"text": "📁 Projects"}, {"text": "📜 Recent History"}],
            [{"text": "📊 AGY Status"}, {"text": "🛑 Stop Task"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error sending persistent keyboard: {e}", flush=True)

def remove_persistent_keyboard(token: str, chat_id: int, text: str = "⌨️ Persistent keyboard removed. Type `/keyboard` to restore."):
    """Removes the persistent bottom reply keyboard."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"remove_keyboard": True}
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error removing keyboard: {e}", flush=True)

def send_telegram_menu(token: str, chat_id: int, text: str = "🎮 *AGY Terminal Remote Menu:*"):
    """Sends an interactive inline keyboard menu specifically designed for the AGY terminal."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✨ New Session", "callback_data": "btn_new_chat"},
                {"text": "🧠 Switch Model", "callback_data": "btn_models"}
            ],
            [
                {"text": "📁 Working Dir", "callback_data": "btn_projects"},
                {"text": "📜 Recent Output", "callback_data": "btn_recent"}
            ],
            [
                {"text": "📊 AGY Status", "callback_data": "btn_status"},
                {"text": "🛑 Stop Task", "callback_data": "btn_stop"}
            ],
            [
                {"text": "⌨️ Toggle Keyboard", "callback_data": "btn_toggle_kbd"},
                {"text": "📸 Screenshot", "callback_data": "btn_screenshot"}
            ]
        ]
    }
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error sending menu: {e}", flush=True)

def send_models_menu(token: str, chat_id: int):
    """Sends an interactive inline keyboard for choosing AI models."""
    cur_alias = get_current_model_alias()
    def tag(alias, label):
        return f"✅ {label}" if alias == cur_alias else label

    keyboard = {
        "inline_keyboard": [
            [
                {"text": tag("flash", "⚡ Flash (Fast)"), "callback_data": "set_model_flash"},
                {"text": tag("argon", "🧠 Argon (High)"), "callback_data": "set_model_argon"}
            ],
            [
                {"text": tag("sonnet", "🌟 Sonnet 5.5"), "callback_data": "set_model_sonnet"},
                {"text": tag("opus", "🏆 Opus 5.5"), "callback_data": "set_model_opus"}
            ],
            [
                {"text": "« Back to Main Menu", "callback_data": "btn_menu"}
            ]
        ]
    }
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "🤖 *Select AI Model for AGY Terminal:*\n_Flash is ultra-fast; Argon/Sonnet are recommended for deep coding._",
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error sending models menu: {e}", flush=True)

def send_projects_menu(token: str, chat_id: int):
    """Sends an interactive inline keyboard for choosing AGY working directory."""
    projs = get_available_projects()
    cur_cwd = get_working_directory()

    rows = []
    row = []
    for p in projs:
        name = p["name"]
        key = p["key"]
        btn_text = f"✅ {name}" if p.get("path") == cur_cwd else name
        row.append({"text": btn_text, "callback_data": f"set_proj_{key}"})
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([{"text": "« Back to Main Menu", "callback_data": "btn_menu"}])

    keyboard = {"inline_keyboard": rows}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"📁 *Select Active Project / Workspace:*\n_Current:_ `{cur_cwd}`",
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error sending projects menu: {e}", flush=True)

def send_approval_request(token: str, chat_id: int, message_text: str):
    """Sends an approval request dialog with 1-tap Approve or Reject buttons."""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Proceed", "callback_data": "btn_approve"},
                {"text": "🛑 Reject / Stop", "callback_data": "btn_stop"}
            ]
        ]
    }
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"❓ *Antigravity Action Approval Needed:*\n\n{message_text}",
        "parse_mode": "Markdown",
        "reply_markup": keyboard
    }
    try:
        requests.post(url, json=payload, timeout=10, verify=False)
    except Exception as e:
        print(f"Error sending approval prompt: {e}", flush=True)
