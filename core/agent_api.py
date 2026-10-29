"""
Antigravity Native Agent API Client
Direct IPC communication with Antigravity's internal language server.
Eliminates keyboard/mouse simulation, window stealing, and focus conflicts.
"""
import os
import json
import sqlite3
import subprocess

def find_language_server_exe() -> str:
    """Finds the path to Antigravity's language_server.exe executable."""
    # 1. Standard user local app data install
    local_app = os.environ.get("LOCALAPPDATA", "")
    p1 = os.path.join(local_app, "Programs", "antigravity", "resources", "bin", "language_server.exe")
    if os.path.exists(p1):
        return p1

    # 2. Program Files install
    p2 = r"C:\Program Files\Antigravity\resources\bin\language_server.exe"
    if os.path.exists(p2):
        return p2

    # 3. Agentapi bat wrapper in user profile
    home = os.path.expanduser("~")
    p3 = os.path.join(home, ".gemini", "antigravity", "bin", "agentapi.bat")
    if os.path.exists(p3):
        return p3

    return "language_server.exe"

def get_active_conversation_info() -> tuple[str, str]:
    """
    Queries conversation_summaries.db for the latest active conversation.
    Returns (conversation_id, title).
    """
    db_path = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")
    if not os.path.exists(db_path):
        return "", ""

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(
            """
            SELECT conversation_id, title
            FROM conversation_summaries
            WHERE status != 'killed'
            ORDER BY last_modified_time DESC
            LIMIT 1
            """
        )
        row = c.fetchone()
        conn.close()
        if row:
            return row[0], row[1] or "Untitled Conversation"
    except Exception as e:
        print(f"Error querying conversation_summaries.db: {e}", flush=True)

    return "", ""

def send_message_native(content: str, conversation_id: str = None) -> tuple[bool, str]:
    """
    Sends a message directly to Antigravity's active conversation via native IPC.
    No keyboard simulation, no mouse movement, no window focus required.
    """
    if not conversation_id:
        conversation_id, title = get_active_conversation_info()
    else:
        title = "Targeted Conversation"

    if not conversation_id:
        return False, "No active conversation found in Antigravity. Send `/new <prompt>` to start one!"

    server_exe = find_language_server_exe()

    try:
        if server_exe.endswith(".bat"):
            cmd = [server_exe, "send-message", conversation_id, content]
        else:
            cmd = [server_exe, "agentapi", "send-message", conversation_id, content]

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15
        )

        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                if "response" in data and "sendMessage" in data["response"]:
                    return True, f"Delivered to '{title}' (`{conversation_id[:8]}...`)"
            except Exception:
                pass
            return True, f"Delivered to conversation `{conversation_id[:8]}...`"
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return False, f"IPC Error: {err}"

    except subprocess.TimeoutExpired:
        return False, "Antigravity IPC timed out."
    except Exception as e:
        return False, f"Native API error: {e}"

def create_conversation_native(prompt: str, model: str = None, title: str = None) -> tuple[bool, str, str]:
    """
    Creates a new conversation in Antigravity natively via IPC.
    Returns (success, conversation_id, detail_message).
    """
    server_exe = find_language_server_exe()

    try:
        args = []
        if model:
            # Native model flag: --model=flash|pro|flash_lite
            m_lower = model.lower()
            if "pro" in m_lower:
                args.append("--model=pro")
            elif "flash" in m_lower:
                args.append("--model=flash")

        if title:
            args.append(f"--title={title}")

        if server_exe.endswith(".bat"):
            cmd = [server_exe, "new-conversation"] + args + [prompt]
        else:
            cmd = [server_exe, "agentapi", "new-conversation"] + args + [prompt]

        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20
        )

        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                conv_info = data.get("response", {}).get("newConversation", {})
                new_id = conv_info.get("conversationId", "")
                return True, new_id, "✨ New conversation started natively!"
            except Exception:
                pass
            return True, "", "✨ New conversation created in Antigravity!"
        else:
            err = res.stderr.strip() or res.stdout.strip()
            return False, "", f"Failed to create conversation: {err}"

    except Exception as e:
        return False, "", f"Native API error: {e}"
