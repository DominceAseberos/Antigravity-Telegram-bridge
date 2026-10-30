import os
import sys
import time
import io
import requests
import threading
from PIL import Image

from .config import (
    save_config,
    send_telegram_message,
    send_telegram_chunked,
    send_telegram_document
)
from .agy_engine import (
    execute_agy_turn,
    set_current_model,
    reset_conversation,
    get_current_model_name,
    get_current_model_alias,
    get_working_directory,
    set_working_directory,
    switch_workspace,
    transcribe_voice_ogg,
    run_git,
    run_shell,
    stop_active_agy_process,
    get_agy_status_summary,
    is_agy_busy,
    UPLOADS_DIR
)
from .keyboards import (
    send_telegram_menu,
    send_models_menu,
    send_projects_menu,
    send_approval_request,
    send_persistent_keyboard,
    remove_persistent_keyboard,
    setup_bot_commands
)
from .system_guard import capture_and_send_screenshot, get_system_health_report
from .agent_api import send_message_native, create_conversation_native, get_active_conversation_info
from .window_driver import (
    find_antigravity_window,
    is_antigravity_active,
    inject_prompt_to_antigravity,
    inject_photo_to_antigravity,
    create_new_conversation,
    emergency_stop_antigravity,
    send_approval_keystroke
)
from .models import (
    get_models_overview,
    switch_model_smart_vision,
    get_current_model_info
)
from .projects import (
    get_projects_summary,
    get_single_project_summary,
    get_session_info,
    get_latest_conversation_transcript
)

def handle_callback_query(token: str, query: dict, allowed_chat_id: int):
    """Handles 1-tap interactive inline keyboard button clicks."""
    cb_data = query.get("data", "")
    cb_chat_id = query.get("message", {}).get("chat", {}).get("id")

    if not cb_chat_id:
        return

    # Verify pairing
    if allowed_chat_id and cb_chat_id != allowed_chat_id:
        send_telegram_message(token, cb_chat_id, "⛔ Access denied. This Antigravity Bridge is paired to another user.")
        return

    # Acknowledge callback query
    cb_id = query.get("id")
    if cb_id:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5, verify=False)
        except Exception:
            pass

    if cb_data == "btn_screenshot":
        send_telegram_message(token, cb_chat_id, "📸 Capturing PC screen...")
        capture_and_send_screenshot(token, cb_chat_id)
    elif cb_data == "btn_new_chat":
        reset_conversation()
        m_name = get_current_model_name()
        send_telegram_message(token, cb_chat_id, f"✨ *Opened a new session!* Your next prompt will start a fresh chat using `{m_name}`.")
    elif cb_data == "btn_models":
        send_models_menu(token, cb_chat_id)
    elif cb_data.startswith("set_model_"):
        m_target = cb_data.replace("set_model_", "")
        success, detail = set_current_model(m_target)
        send_telegram_message(token, cb_chat_id, detail)
        send_models_menu(token, cb_chat_id)
    elif cb_data == "btn_projects":
        send_projects_menu(token, cb_chat_id)
    elif cb_data.startswith("set_proj_"):
        proj_key = cb_data.replace("set_proj_", "")
        success, detail = set_working_directory(proj_key)
        send_telegram_message(token, cb_chat_id, detail)
        send_projects_menu(token, cb_chat_id)
    elif cb_data in ["btn_chats", "btn_recent"]:
        recent = get_latest_conversation_transcript()
        if recent:
            send_telegram_chunked(token, cb_chat_id, f"📝 *Latest Output:*\n\n{recent}")
        else:
            chats_summary = get_session_info()
            send_telegram_chunked(token, cb_chat_id, chats_summary)
    elif cb_data == "btn_stop":
        ok, det = stop_active_agy_process()
        if not ok:
            ok2, det2 = emergency_stop_antigravity()
            send_telegram_message(token, cb_chat_id, det if not ok2 else det2)
        else:
            send_telegram_message(token, cb_chat_id, det)
    elif cb_data == "btn_approve":
        ok, det = send_approval_keystroke()
        send_telegram_message(token, cb_chat_id, "✅ *Action Approved!* Sent approval signal.")
    elif cb_data == "btn_toggle_kbd":
        send_persistent_keyboard(token, cb_chat_id, "⌨️ *Persistent bottom keyboard is now enabled on your screen!*")
    elif cb_data in ["btn_status", "btn_health"]:
        status_text = get_agy_status_summary()
        win = find_antigravity_window()
        is_active, _ = is_antigravity_active() if win else (False, "")
        model_name, _ = get_current_model_info()
        hw_report = get_system_health_report(model_name, win, is_active)
        full_report = f"{status_text}\n\n{hw_report}"
        send_telegram_chunked(token, cb_chat_id, full_report)
    elif cb_data == "btn_menu":
        send_telegram_menu(token, cb_chat_id)

def handle_incoming_message(token: str, msg: dict, cfg: dict, restart_func):
    """Processes an incoming text message, command, or photo."""
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    caption = msg.get("caption", "").strip()
    photo = msg.get("photo")
    document = msg.get("document")
    user_name = msg.get("from", {}).get("first_name", "User")
    allowed_chat_id = cfg.get("allowed_chat_id")

    # Pairing security check
    if not allowed_chat_id:
        cfg["allowed_chat_id"] = chat_id
        save_config(cfg)
        setup_bot_commands(token)
        send_persistent_keyboard(
            token,
            chat_id,
            f"🔒 *Bridge Successfully Paired!*\nWelcome, {user_name}! Your Telegram account has been bound to this PC's Antigravity desktop.\n\nUse the buttons below or send any prompt to begin:"
        )
        send_telegram_menu(token, chat_id)
        return
    elif chat_id != allowed_chat_id:
        print(f"⛔ Unauthorized message from Chat ID: {chat_id}", flush=True)
        send_telegram_message(
            token,
            chat_id,
            "⛔ *Access Denied.*\nThis Antigravity Remote Bridge is securely locked to its owner's Telegram account."
        )
        return

    # Handle Photo / Image Upload
    if photo or (document and document.get("mime_type", "").startswith("image/")):
        file_id = photo[-1]["file_id"] if photo else document["file_id"]
        send_telegram_message(token, chat_id, "📥 Downloading photo...")
        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=15, verify=False)
            file_path = r.json()["result"]["file_path"]
            img_bytes = requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=30, verify=False).content

            upload_filename = f"upload_{int(time.time())}.jpg"
            upload_full_path = os.path.join(UPLOADS_DIR, upload_filename)
            with open(upload_full_path, "wb") as f:
                f.write(img_bytes)

            user_prompt = caption or "Please analyze this image."
            full_prompt = f"The user uploaded an image saved at: {upload_full_path}\n\nInstructions: {user_prompt}"

            send_telegram_message(token, chat_id, "🚀 *Photo received!* Analyzing via agy...")
            threading.Thread(
                target=execute_agy_turn,
                args=(full_prompt, token, chat_id, False),
                daemon=True
            ).start()
        except Exception as e:
            send_telegram_message(token, chat_id, f"⚠️ Error processing photo: {e}")
        return

    # Handle Voice Note / Video Note / Audio Message
    voice = msg.get("voice") or msg.get("audio") or msg.get("video_note")
    if voice:
        file_id = voice["file_id"]
        is_video = "video_note" in msg
        send_telegram_message(token, chat_id, "🎥 Transcribing video note audio..." if is_video else "🎙️ Downloading & transcribing voice note...")
        try:
            r = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=15, verify=False)
            file_path = r.json()["result"]["file_path"]
            voice_bytes = requests.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=30, verify=False).content

            ext = ".mp4" if is_video else ".oga"
            voice_filename = f"voice_{int(time.time())}{ext}"
            voice_path = os.path.join(UPLOADS_DIR, voice_filename)
            with open(voice_path, "wb") as f:
                f.write(voice_bytes)

            success, transcribed_text = transcribe_voice_ogg(voice_path)
            if success and transcribed_text.strip():
                send_telegram_message(token, chat_id, f"🎙️ *Heard:* \"_{transcribed_text}_\"")
                threading.Thread(
                    target=execute_agy_turn,
                    args=(transcribed_text, token, chat_id, False),
                    daemon=True
                ).start()
            else:
                send_telegram_message(token, chat_id, f"⚠️ Voice transcription error: {transcribed_text or 'No speech detected'}")
        except Exception as e:
            send_telegram_message(token, chat_id, f"⚠️ Error processing audio: {e}")
        return

    if not text:
        return

    text_lower = text.lower()

    # 0. Keyboard Toggle Commands
    if text_lower in ["/keyboard", "keyboard", "show keyboard"]:
        send_persistent_keyboard(token, chat_id, "⌨️ Persistent keyboard attached!")
        return

    if text_lower in ["/hide_keyboard", "hide keyboard", "remove keyboard"]:
        remove_persistent_keyboard(token, chat_id)
        return

    # 1. New Chat Command (or persistent button "✨ New Session")
    if (
        text_lower in ["/new", "/newchat", "new chat", "new session", "✨ new session", "open new chat"]
        or text_lower.startswith("/new ")
        or text_lower.startswith("new chat on ")
        or text_lower.startswith("new session on ")
    ):
        prompt = ""
        if text_lower.startswith("/new "):
            prompt = text[5:].strip()
        elif text_lower.startswith("new chat on "):
            prompt = text[12:].strip()
        elif text_lower.startswith("new session on "):
            prompt = text[15:].strip()

        if prompt:
            send_telegram_message(token, chat_id, f"✨ *Starting fresh session on {get_current_model_name()}...*")
            threading.Thread(
                target=execute_agy_turn,
                args=(prompt, token, chat_id, True),
                daemon=True
            ).start()
            return
        else:
            reset_conversation()
            send_telegram_message(
                token,
                chat_id,
                f"✨ *Fresh session initialized!* Active model: `{get_current_model_name()}`.\nSend any prompt to begin."
            )
            return

    # 2. Models Command (or persistent button "🧠 Switch Model")
    if text_lower in ["/models", "models", "/model", "🧠 switch model", "switch model", "change model", "list models", "models list", "check model", "current model", "what model"]:
        send_models_menu(token, chat_id)
        return

    if text_lower.startswith("/model ") or text_lower.startswith("switch model ") or text_lower.startswith("change model "):
        target = ""
        if text_lower.startswith("/model "):
            target = text[7:].strip()
        elif text_lower.startswith("switch model "):
            target = text[13:].strip()
        elif text_lower.startswith("change model "):
            target = text[13:].strip()

        if not target:
            send_models_menu(token, chat_id)
        else:
            success, detail = set_current_model(target)
            send_telegram_message(token, chat_id, detail)
        return

    # 3. Help & Start Commands
    if text in ["/start", "/help", "help", "start"]:
        setup_bot_commands(token)
        send_persistent_keyboard(
            token,
            chat_id,
            f"👋 *Antigravity AGY Remote Bridge (Pro Edition)*\n\n"
            "✨ *Commands & Features:*\n"
            "• 💬 *Text Prompt:* Type anything to code, debug, or build\n"
            "• 🎙️ *Voice Note:* Send a voice message to prompt hands-free\n"
            "• 📸 *Image Upload:* Send photos for instant visual analysis\n"
            "• 🎨 *Image Gen:* Ask the agent to generate images/art\n"
            "• 📂 `/projects` or `/cd <name>`: Switch active project\n"
            "• 🧠 `/model <name>`: Switch AI model (`flash`, `argon`, `sonnet`, `opus`)\n"
            "• 🌿 `/git <args>`: Git shortcuts (e.g. `/git status`, `/git diff`)\n"
            "• 💻 `/run <cmd>`: Run terminal commands directly\n"
            "• 📦 `/file <name>`: Download any project file to your phone\n"
            "• 📊 `/status`: Check agent state, model & PC health\n"
            "• 🛑 `/stop`: Abort current running task\n"
            "• ⌨️ `/keyboard`: Toggle bottom quick-buttons\n\n"
            "_Tap a button below or send any prompt to begin!_"
        )
        send_telegram_menu(token, chat_id)
        return

    # 4. Interactive Menu
    if text_lower in ["/menu", "menu", "/buttons", "buttons"]:
        send_telegram_menu(token, chat_id)
        return

    # 5. Emergency Stop & Rejection (or persistent button "🛑 Stop Task")
    if text_lower in ["/stop", "stop", "/cancel", "cancel", "/abort", "abort", "/reject", "reject", "🛑 stop task", "stop task"]:
        ok, det = stop_active_agy_process()
        if not ok:
            ok2, det2 = emergency_stop_antigravity()
            send_telegram_message(token, chat_id, det if not ok2 else det2)
        else:
            send_telegram_message(token, chat_id, det)
        return

    # 5b. Approval & Confirmation
    if text_lower in ["/approve", "approve", "/proceed", "proceed", "/yes", "yes"]:
        ok, det = send_approval_keystroke()
        send_telegram_message(token, chat_id, "✅ *Action Approved!* Sent approval signal.")
        return

    # 6. Screenshot
    if (
        text_lower in ["/ss", "ss", "/screen", "screen", "capture", "/capture", "/shot", "shot", "📸 screenshot"]
        or any(k in text_lower for k in ["screenshot", "scresnshot", "screenshkt", "screensot", "screenshoot", "screnshot", "screeshot", "screensht"])
    ):
        send_telegram_message(token, chat_id, "📸 Capturing PC screen...")
        capture_and_send_screenshot(token, chat_id)
        return

    # 7. Projects Inspection & Switching (or persistent button "📁 Projects")
    if text_lower in ["📁 projects", "projects", "/projects", "/project", "project", "list projects"]:
        send_projects_menu(token, chat_id)
        return

    if (
        text_lower.startswith("/projects ")
        or text_lower.startswith("/project ")
        or text_lower.startswith("projects ")
        or text_lower.startswith("project ")
        or text_lower.startswith("open project ")
        or text_lower.startswith("view project ")
    ):
        target_p = ""
        if text_lower.startswith("/projects "):
            target_p = text[10:].strip()
        elif text_lower.startswith("/project "):
            target_p = text[9:].strip()
        elif text_lower.startswith("projects "):
            target_p = text[9:].strip()
        elif text_lower.startswith("project "):
            target_p = text[8:].strip()
        elif text_lower.startswith("open project "):
            target_p = text[13:].strip()
        elif text_lower.startswith("view project "):
            target_p = text[13:].strip()

        if target_p:
            ok, det = set_working_directory(target_p)
            send_telegram_message(token, chat_id, det)
        else:
            send_projects_menu(token, chat_id)
        return

    # 8. Chat Sessions & Recent Outputs (or persistent button "📜 Recent History")
    if (
        text_lower in ["📜 recent history", "recent history", "/recent", "recent", "/chats", "chats", "/sessions", "sessions"]
        or text_lower.startswith("/chat ")
        or text_lower.startswith("chat ")
        or text_lower.startswith("/session ")
        or text_lower.startswith("session ")
        or text_lower.startswith("/recent ")
        or text_lower.startswith("recent ")
    ):
        target_query = ""
        if text_lower.startswith("/chat "):
            target_query = text[6:].strip()
        elif text_lower.startswith("chat "):
            target_query = text[5:].strip()
        elif text_lower.startswith("/session "):
            target_query = text[9:].strip()
        elif text_lower.startswith("session "):
            target_query = text[8:].strip()
        elif text_lower.startswith("/recent "):
            target_query = text[8:].strip()
        elif text_lower.startswith("recent "):
            target_query = text[7:].strip()

        if not target_query:
            recent = get_latest_conversation_transcript()
            if recent:
                send_telegram_chunked(token, chat_id, f"📝 *Latest Output:*\n\n{recent}")
            else:
                chats_summary = get_session_info()
                send_telegram_chunked(token, chat_id, chats_summary)
            return

        session_summary = get_session_info(target_query)
        send_telegram_chunked(token, chat_id, session_summary)
        return

    # 9. Reload / Restart Bridge
    if text_lower in ["/restart", "/reload", "reload", "restart"]:
        send_telegram_message(token, chat_id, "🔄 *Restarting Antigravity Bridge on PC...* Back online in 2 seconds!")
        restart_func()
        return

    # 10. PC Health & AGY Status (or persistent button "📊 AGY Status")
    if text_lower in ["📊 agy status", "agy status", "/status", "status", "/health", "health", "/metrics", "metrics", "/system", "system", "check status"]:
        status_text = get_agy_status_summary()
        win = find_antigravity_window()
        is_active, _ = is_antigravity_active() if win else (False, "")
        model_name, _ = get_current_model_info()
        hw_report = get_system_health_report(model_name, win, is_active)
        full_report = f"{status_text}\n\n{hw_report}"
        send_telegram_chunked(token, chat_id, full_report)
        return

    # 11. Workspace Directory Switching (/cd <project>)
    if text_lower.startswith("/cd ") or text_lower.startswith("cd "):
        target = text[4:].strip() if text_lower.startswith("/cd ") else text[3:].strip()
        success, detail = switch_workspace(target)
        send_telegram_message(token, chat_id, detail)
        return

    # 12. Git & Version Control Shortcuts (/git <args>)
    if text_lower in ["/git", "git"] or text_lower.startswith("/git ") or text_lower.startswith("git "):
        if text_lower in ["/git", "git"]:
            git_args = ["status", "--short"]
        else:
            raw_args = text[5:].strip() if text_lower.startswith("/git ") else text[4:].strip()
            git_args = raw_args.split()
        send_telegram_message(token, chat_id, f"🌿 Running: `git {' '.join(git_args)}`...")
        output = run_git(git_args)
        send_telegram_chunked(token, chat_id, f"🌿 *Git ({' '.join(git_args)}):*\n```\n{output}\n```")
        return

    # 13. Terminal Shell Runner (/run <cmd> or /sh <cmd>)
    if (
        text_lower.startswith("/run ")
        or text_lower.startswith("run ")
        or text_lower.startswith("/sh ")
        or text_lower.startswith("sh ")
    ):
        if text_lower.startswith("/run "):
            cmd_str = text[5:].strip()
        elif text_lower.startswith("run "):
            cmd_str = text[4:].strip()
        elif text_lower.startswith("/sh "):
            cmd_str = text[4:].strip()
        else:
            cmd_str = text[3:].strip()
        send_telegram_message(token, chat_id, f"💻 Executing: `{cmd_str}`...")
        output = run_shell(cmd_str)
        send_telegram_chunked(token, chat_id, f"💻 *Shell Output:*\n```\n{output}\n```")
        return

    # 14. File Inspection & Download (/file <filename> or /get <filename>)
    if (
        text_lower.startswith("/file ")
        or text_lower.startswith("file ")
        or text_lower.startswith("/get ")
        or text_lower.startswith("get ")
        or text_lower.startswith("/cat ")
        or text_lower.startswith("cat ")
    ):
        fname = text.split(maxsplit=1)[1].strip()
        ws = get_working_directory()
        fpath = os.path.join(ws, fname) if not os.path.isabs(fname) else fname
        if os.path.exists(fpath):
            send_telegram_document(token, chat_id, fpath, caption=f"📄 *File:* `{os.path.basename(fpath)}`")
        else:
            send_telegram_message(token, chat_id, f"⚠️ File `{fname}` not found in `{ws}`.")
        return

    # 15. Text Prompt Delivery (agy Headless Real-Time Streaming)
    print(f"📥 Received prompt from phone: {text[:60]}...", flush=True)
    threading.Thread(
        target=execute_agy_turn,
        args=(text, token, chat_id, False),
        daemon=True
    ).start()
