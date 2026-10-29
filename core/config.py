import os
import io
import json
import time
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_CONFIG_DIR = os.path.expanduser("~/.antigravity-telegram-bridge")

def get_config_path() -> str:
    """Returns the config file path, prioritizing local directory then user profile."""
    local_cfg = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(local_cfg):
        return local_cfg
    env_cfg = os.environ.get("ANTIGRAVITY_CONFIG")
    if env_cfg and os.path.exists(env_cfg):
        return env_cfg
    os.makedirs(USER_CONFIG_DIR, exist_ok=True)
    return os.path.join(USER_CONFIG_DIR, "config.json")

def get_watcher_state_path() -> str:
    local_state = os.path.join(BASE_DIR, "watcher_state.json")
    if os.path.exists(local_state):
        return local_state
    os.makedirs(USER_CONFIG_DIR, exist_ok=True)
    return os.path.join(USER_CONFIG_DIR, "watcher_state.json")

CONFIG_FILE = get_config_path()
WATCHER_STATE_FILE = get_watcher_state_path()

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}", flush=True)
    return {}

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Error saving config.json: {e}", flush=True)

def load_watcher_state() -> dict:
    if os.path.exists(WATCHER_STATE_FILE):
        try:
            with open(WATCHER_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_watcher_state(state: dict):
    try:
        with open(WATCHER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

def send_telegram_message(token: str, chat_id: int, text: str, parse_mode: str = "Markdown"):
    """Sends a text message to Telegram with markdown fallback. Returns message_id if successful."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code != 200 and parse_mode:
            # Fallback to plain text if Markdown parsing fails
            payload.pop("parse_mode", None)
            r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            return r.json().get("result", {}).get("message_id")
        return None
    except Exception as e:
        print(f"Error sending message to Telegram: {e}", flush=True)
        return None

def edit_telegram_message(token: str, chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown") -> bool:
    """Edits an existing Telegram message in place for real-time streaming."""
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    try:
        r = requests.post(url, json=payload, timeout=8)
        if r.status_code != 200 and parse_mode:
            payload.pop("parse_mode", None)
            r = requests.post(url, json=payload, timeout=8)
        return r.status_code == 200
    except Exception:
        return False

def send_telegram_document(token: str, chat_id: int, file_path: str, caption: str = "") -> bool:
    """Sends any local file to Telegram as a downloadable document."""
    if not os.path.exists(file_path):
        return False
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
                data["parse_mode"] = "Markdown"
            files = {"document": (os.path.basename(file_path), f)}
            r = requests.post(url, data=data, files=files, timeout=45)
            if r.status_code != 200 and caption:
                f.seek(0)
                data.pop("parse_mode", None)
                r = requests.post(url, data=data, files=files, timeout=45)
            return r.status_code == 200
    except Exception as e:
        print(f"Error sending document {file_path}: {e}", flush=True)
        return False

def send_telegram_chunked(token: str, chat_id: int, text: str, max_chars: int = 3800):
    """Splits long text messages to stay safely within Telegram's 4096-character limit."""
    if len(text) <= max_chars:
        send_telegram_message(token, chat_id, text)
        return

    paragraphs = text.split("\n\n")
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) + 2 > max_chars:
            chunk_str = "\n\n".join(current_chunk)
            if chunk_str.strip():
                send_telegram_message(token, chat_id, chunk_str)
                time.sleep(0.3)
            current_chunk = [para]
            current_len = len(para)
        else:
            current_chunk.append(para)
            current_len += len(para) + 2

    if current_chunk:
        chunk_str = "\n\n".join(current_chunk)
        if chunk_str.strip():
            send_telegram_message(token, chat_id, chunk_str)

def send_telegram_photo(token: str, chat_id: int, pil_img, caption: str = ""):
    """Sends a PIL image to Telegram chat with optional caption."""
    try:
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "Markdown"
        r = requests.post(
            url,
            data=data,
            files={"photo": ("verification.jpg", buf, "image/jpeg")},
            timeout=25
        )
        if r.status_code != 200 and caption:
            buf.seek(0)
            data.pop("parse_mode", None)
            requests.post(url, data=data, files={"photo": ("verification.jpg", buf, "image/jpeg")}, timeout=25)
    except Exception as e:
        print(f"Error sending photo to Telegram: {e}", flush=True)

def send_telegram_action(token: str, chat_id: int, action: str = "typing"):
    """Sends a chat action (e.g. typing, upload_photo) to indicate agent activity."""
    url = f"https://api.telegram.org/bot{token}/sendChatAction"
    try:
        requests.post(url, json={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass
