"""
Antigravity CLI (agy) Advanced Headless Engine
- Real-time stream-json token streaming & tool progress
- Multi-project workspace switching (/cd, /projects)
- Voice note transcription (Telegram voice -> SpeechRecognition)
- Automatic image & document artifact delivery
- Git & DevOps command runner
"""
import os
import re
import json
import time
import subprocess
import threading
from typing import Optional

from .config import (
    BASE_DIR,
    send_telegram_message,
    edit_telegram_message,
    send_telegram_chunked,
    send_telegram_photo,
    send_telegram_document,
    send_telegram_action
)

AGY_STATE_FILE = os.path.join(BASE_DIR, "agy_state.json")
PROJECTS_ROOT = os.path.dirname(BASE_DIR)  # C:\Users\user\OneDrive\Desktop\Projects
UPLOADS_DIR = os.path.join(PROJECTS_ROOT, "telegram_uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

AGY_EXE_PATH = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")

MODEL_MAP = {
    "flash": "gemini-3.8-flash-high",
    "argon": "gemini-4-argon-high",
    "pro": "gemini-4-argon-high",
    "sonnet": "claude-sonnet-5-5-high",
    "opus": "claude-opus-5-5-high",
}

# --- State Management ---

def load_agy_state() -> dict:
    if os.path.exists(AGY_STATE_FILE):
        try:
            with open(AGY_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "active_conversation_id": None,
        "selected_model": "gemini-3.8-flash-high",
        "model_alias": "flash",
        "current_workspace": PROJECTS_ROOT
    }

def save_agy_state(state: dict):
    try:
        with open(AGY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving agy state: {e}", flush=True)

def get_current_model_name() -> str:
    state = load_agy_state()
    return state.get("selected_model", "gemini-3.8-flash-high")

def get_current_model_alias() -> str:
    state = load_agy_state()
    return state.get("model_alias", "flash")

def set_current_model(model_key: str) -> tuple[bool, str]:
    k = model_key.lower().strip()
    matched = None
    for alias, full_name in MODEL_MAP.items():
        if alias in k or full_name in k:
            matched = (alias, full_name)
            break
    if not matched:
        return False, f"Unknown model '{model_key}'. Available: flash, argon, sonnet, opus"

    alias, full_name = matched
    state = load_agy_state()
    state["selected_model"] = full_name
    state["model_alias"] = alias
    save_agy_state(state)
    return True, f"🎯 Switched active model to *{full_name}* (`{alias}`). Next prompt will use this model."

def reset_conversation():
    state = load_agy_state()
    state["active_conversation_id"] = None
    save_agy_state(state)

# --- Workspace Management ---

ACTIVE_PROC = None

def set_working_directory(proj_key: str) -> tuple[bool, str]:
    """Alias for switch_workspace to match keyboards.py import."""
    return switch_workspace(proj_key)

def is_agy_busy() -> bool:
    """Returns True if an agy turn is actively executing."""
    global ACTIVE_PROC
    return ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None

def stop_active_agy_process() -> tuple[bool, str]:
    """Terminates any actively executing agy subprocess."""
    global ACTIVE_PROC
    if ACTIVE_PROC and ACTIVE_PROC.poll() is None:
        try:
            ACTIVE_PROC.terminate()
            time.sleep(0.4)
            if ACTIVE_PROC.poll() is None:
                ACTIVE_PROC.kill()
            ACTIVE_PROC = None
            return True, "🛑 *Active AGY task was terminated!*"
        except Exception as e:
            return False, f"Failed to stop task: {e}"
    return False, "No active AGY task is currently running."

def get_agy_status_summary() -> str:
    """Returns a formatted status overview of the AGY headless engine."""
    state = load_agy_state()
    model = state.get("selected_model", "gemini-3.8-flash-high")
    alias = state.get("model_alias", "flash")
    cwd = get_working_directory()
    proj = os.path.basename(cwd)
    conv = state.get("active_conversation_id")
    
    is_running = ACTIVE_PROC is not None and ACTIVE_PROC.poll() is None
    state_str = "🟢 *Active* (Running task)" if is_running else "💤 *Idle* (Ready for prompt)"
    
    return (
        f"⚡ *AGY Terminal Engine Status:*\n"
        f"• *Status:* {state_str}\n"
        f"• *Model:* `{model}` (`{alias}`)\n"
        f"• *Workspace:* `{proj}` (`{cwd}`)\n"
        f"• *Session ID:* `{conv[:12] + '...' if conv else 'None (New Session)'}`"
    )

def get_working_directory() -> str:
    state = load_agy_state()
    ws = state.get("current_workspace")
    if ws and os.path.exists(ws):
        return ws
    return PROJECTS_ROOT

def get_available_projects() -> list[dict]:
    """Scans and returns available sub-projects in Projects/."""
    results = [{"name": "Root (Projects)", "key": "root", "path": PROJECTS_ROOT}]
    if os.path.exists(PROJECTS_ROOT):
        for entry in os.scandir(PROJECTS_ROOT):
            if entry.is_dir() and not entry.name.startswith((".", "$")):
                if entry.name not in ["antigravity-telegram-bridge", "telegram_uploads", "node_modules"]:
                    safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", entry.name).lower()[:24]
                    results.append({
                        "name": entry.name,
                        "key": safe_key,
                        "path": entry.path
                    })
    return results

def switch_workspace(target_name: str) -> tuple[bool, str]:
    """Switches active workspace directory to a chosen project folder."""
    target_clean = target_name.strip().strip("\"'").lower()
    if target_clean in ["root", "projects", "home", "default", "/"]:
        state = load_agy_state()
        state["current_workspace"] = PROJECTS_ROOT
        state["active_conversation_id"] = None
        save_agy_state(state)
        return True, f"📂 Workspace set to Root Projects folder:\n`{PROJECTS_ROOT}`"

    matched = None
    if os.path.exists(PROJECTS_ROOT):
        for entry in os.scandir(PROJECTS_ROOT):
            if entry.is_dir() and not entry.name.startswith((".", "$")):
                safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", entry.name).lower()
                if entry.name.lower() == target_clean or safe_key == target_clean:
                    matched = entry.path
                    break
                elif target_clean in entry.name.lower():
                    matched = entry.path

    if matched:
        state = load_agy_state()
        state["current_workspace"] = matched
        state["active_conversation_id"] = None
        save_agy_state(state)
        return True, f"📂 Switched active workspace to: *{os.path.basename(matched)}*\n`{matched}`"
    else:
        return False, f"⚠️ Project '{target_name}' not found. Send `/projects` to view available projects."

# --- Voice Note Audio Transcription ---

def transcribe_voice_ogg(ogg_path: str) -> tuple[bool, str]:
    """Converts Telegram voice OGG/OGA to WAV using imageio-ffmpeg and transcribes via Google Speech."""
    try:
        import imageio_ffmpeg
        import speech_recognition as sr

        wav_path = ogg_path.rsplit(".", 1)[0] + ".wav"
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-y", "-i", ogg_path, "-vn", "-ar", "16000", "-ac", "1", wav_path]
        res = subprocess.run(cmd, capture_output=True, timeout=20)
        if res.returncode != 0 or not os.path.exists(wav_path):
            return False, "Failed to decode voice note audio."

        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = r.record(source)
            text = r.recognize_google(audio)

        try:
            os.remove(wav_path)
        except Exception:
            pass

        return True, text
    except Exception as e:
        return False, f"Transcription error: {e}"

# --- Artifact & Image Discovery ---

def find_created_images(text: str) -> list[str]:
    """Scans response text for referenced image files that exist on disk."""
    ws = get_working_directory()
    patterns = [
        r"\[.*?\]\((file:///[a-zA-Z]:[^\)]+?\.(?:png|jpg|jpeg|webp))\)",
        r"file:///([a-zA-Z]:/[^\s\)\"']+?\.(?:png|jpg|jpeg|webp))",
        r"([a-zA-Z]:\\[^\s\)\"']+?\.(?:png|jpg|jpeg|webp))",
        r"[`'\"]([\w\-\./\\]+\.(?:png|jpg|jpeg|webp))[`'\"]",
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw_path = m.group(1).replace("file:///", "").replace("/", "\\")
            if not os.path.isabs(raw_path):
                raw_path = os.path.join(ws, raw_path)
            if os.path.exists(raw_path) and raw_path not in found:
                found.append(raw_path)
    return found

def find_created_artifacts(text: str) -> list[str]:
    """Finds newly created non-image code/data files to send as documents."""
    ws = get_working_directory()
    patterns = [
        r"\[.*?\]\((file:///[a-zA-Z]:[^\)]+?)\)",
        r"file:///([a-zA-Z]:/[^\s\)\"']+)",
        r"created.*?file.*?[`'\"]([\w\-\./\\]+\.[a-zA-Z0-9]+)[`'\"]",
        r"saved.*?to.*?[`'\"]([\w\-\./\\]+\.[a-zA-Z0-9]+)[`'\"]",
        r"wrote.*?to.*?[`'\"]([\w\-\./\\]+\.[a-zA-Z0-9]+)[`'\"]",
    ]
    found = []
    skip_ext = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".lock"]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw = m.group(1).replace("file:///", "").replace("/", "\\")
            if not os.path.isabs(raw):
                raw = os.path.join(ws, raw)
            ext = os.path.splitext(raw)[1].lower()
            if ext and ext not in skip_ext and os.path.exists(raw) and raw not in found:
                # Deliver if smaller than 30MB
                if os.path.getsize(raw) < 30 * 1024 * 1024:
                    found.append(raw)
    return found

# --- Git & DevOps Helpers ---

def run_git(args: list[str]) -> str:
    """Runs a git command in the active workspace."""
    ws = get_working_directory()
    cmd = ["git"] + args
    try:
        res = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=25)
        out = res.stdout.strip()
        err = res.stderr.strip()
        combined = f"{out}\n{err}".strip()
        return combined if combined else "(Clean / no output)"
    except Exception as e:
        return f"Git error: {e}"

def run_shell(cmd_str: str) -> str:
    """Runs an arbitrary terminal shell command in the active workspace."""
    ws = get_working_directory()
    try:
        res = subprocess.run(cmd_str, shell=True, cwd=ws, capture_output=True, text=True, timeout=60)
        out = res.stdout.strip()
        err = res.stderr.strip()
        combined = f"{out}\n{err}".strip()
        return combined if combined else "(Command completed with exit code 0)"
    except subprocess.TimeoutExpired:
        return "⚠️ Command timed out after 60 seconds."
    except Exception as e:
        return f"Shell error: {e}"

# --- Real-Time Streaming Turn Execution ---

def execute_agy_turn(
    prompt: str,
    token: str,
    chat_id: int,
    is_new_chat: bool = False
):
    """
    Executes a prompt via agy in stream-json mode.
    Streams token deltas & tool updates to Telegram in real-time.
    Delivers final response, generated images, and created file attachments.
    """
    state = load_agy_state()
    conv_id = state.get("active_conversation_id")
    model = state.get("selected_model", "gemini-3.8-flash-high")
    alias = state.get("model_alias", "flash")
    cwd = get_working_directory()
    proj_name = os.path.basename(cwd)

    if is_new_chat:
        conv_id = None
        reset_conversation()

    cmd = [
        AGY_EXE_PATH,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--model", model,
    ]

    if conv_id and not is_new_chat:
        cmd.extend(["--conversation", conv_id])

    cmd.extend(["-p", prompt])

    # 1. Send initial status message
    initial_text = f"⚡ *[{alias.upper()} | {proj_name}]* _Thinking..._"
    status_msg_id = send_telegram_message(token, chat_id, initial_text)

    # 2. Start typing action heartbeat
    stop_event = threading.Event()
    def typing_loop():
        while not stop_event.is_set():
            send_telegram_action(token, chat_id, "typing")
            time.sleep(3.5)

    th = threading.Thread(target=typing_loop, daemon=True)
    th.start()

    accumulated_text = ""
    current_status = ""
    final_response = ""
    new_conv_id = None

    last_edit_time = time.time()
    last_edited_text = initial_text

    global ACTIVE_PROC
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            bufsize=1
        )
        ACTIVE_PROC = proc

        for line in iter(proc.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue

            try:
                evt = json.loads(line)
                event_type = evt.get("event")

                if event_type == "step_update":
                    su = evt.get("step_update", {})
                    step_type = su.get("step_type", "")
                    state_val = su.get("state", "")
                    delta = su.get("text_delta", "")

                    if delta:
                        accumulated_text += delta

                    if "tool" in step_type:
                        tool_name = su.get("tool_name", "tool")
                        current_status = f"⚙️ Tool: `{tool_name}`"

                elif event_type == "result":
                    res_data = evt.get("result", {})
                    final_response = res_data.get("response", "").strip()
                    new_conv_id = res_data.get("conversation_id")
                    break

            except Exception:
                pass

            # Debounced edit every 1.8 seconds if text changed
            now = time.time()
            if now - last_edit_time >= 1.8 and accumulated_text and status_msg_id:
                display_chunk = accumulated_text[-2800:]  # Stay well within edit length limit
                edit_text = f"⚡ *[{alias.upper()} | {proj_name}]*\n\n{display_chunk}"
                if current_status:
                    edit_text += f"\n\n_{current_status}_"

                if edit_text != last_edited_text:
                    edit_telegram_message(token, chat_id, status_msg_id, edit_text)
                    last_edited_text = edit_text
                    last_edit_time = now

        proc.stdout.close()
        proc.wait(timeout=10)

    except Exception as e:
        final_response = f"⚠️ Execution error: {e}"
    finally:
        ACTIVE_PROC = None
        stop_event.set()

    # 3. Finalize conversation state
    if new_conv_id:
        state["active_conversation_id"] = new_conv_id
        save_agy_state(state)

    result_text = final_response or accumulated_text.strip() or "*(Completed with no textual output)*"

    # 4. Final message edit / delivery
    header = f"🚀 *[{alias.upper()} | {proj_name}]*\n\n"
    if status_msg_id and len(header + result_text) <= 3800:
        edit_telegram_message(token, chat_id, status_msg_id, header + result_text)
    else:
        if status_msg_id:
            edit_telegram_message(token, chat_id, status_msg_id, f"✅ *[{alias.upper()} | {proj_name}]* Task completed. Delivering output below:")
        send_telegram_chunked(token, chat_id, result_text)

    # 5. Discover & send generated images
    created_images = find_created_images(result_text)
    for img_path in created_images:
        try:
            from PIL import Image
            pil_img = Image.open(img_path)
            send_telegram_photo(token, chat_id, pil_img, caption=f"🎨 *Generated:* `{os.path.basename(img_path)}`")
        except Exception as e:
            print(f"Error sending image {img_path}: {e}", flush=True)

    # 6. Discover & send created code / data artifacts
    created_files = find_created_artifacts(result_text)
    for f_path in created_files:
        try:
            send_telegram_document(token, chat_id, f_path, caption=f"📦 *Artifact:* `{os.path.basename(f_path)}`")
        except Exception as e:
            print(f"Error sending artifact {f_path}: {e}", flush=True)
