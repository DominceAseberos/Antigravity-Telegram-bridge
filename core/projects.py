import os
import glob
import json
import sqlite3

from .window_driver import find_antigravity_window

def get_projects_summary() -> str:
    """Retrieves all Antigravity projects and their recent conversations."""
    db_path = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")
    if not os.path.exists(db_path):
        return "❌ Antigravity database not found."

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                CASE 
                    WHEN project IS NOT NULL AND project != '' THEN project
                    WHEN workspace IS NOT NULL AND workspace != '' THEN workspace
                    ELSE 'CLI Project'
                END AS proj_name,
                title,
                last_modified_time
            FROM conversations_fts
            WHERE title IS NOT NULL AND title != ''
            ORDER BY last_modified_time DESC;
        """)

        projects_map = {}
        for proj, title, mtime in cur.fetchall():
            if not proj:
                proj = "CLI Project"
            if proj not in projects_map:
                projects_map[proj] = []
            if title not in projects_map[proj]:
                projects_map[proj].append(title)

        conn.close()

        if not projects_map:
            return "No projects found in Antigravity."

        known_order = ["Projects", "GridPulse", "CLI Project", "Projects_personal"]
        all_keys = list(projects_map.keys())
        sorted_keys = sorted(all_keys, key=lambda k: known_order.index(k) if k in known_order else 99)

        lines = ["📂 *Antigravity Projects:*\n"]
        for p in sorted_keys:
            convos = projects_map[p]
            lines.append(f"📁 *{p}* ({len(convos)} chats)")
            for c in convos[:5]:
                lines.append(f"  • {c}")
            if len(convos) > 5:
                lines.append(f"   _...and {len(convos) - 5} more_")
            lines.append("")

        lines.append("💡 *Tip:* Send `/chats` to view active sessions or `/chat <name>` to inspect any conversation.")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Error querying projects: {e}"

def get_single_project_summary(proj_query: str) -> str:
    """Retrieves detailed information, workspace folders, and recent chats for a specific project."""
    q = proj_query.strip().lower()

    known_projects = {
        "projects_personal": ("Projects_personal", r"C:\Users\user\OneDrive\Desktop\Projects_personal"),
        "personal": ("Projects_personal", r"C:\Users\user\OneDrive\Desktop\Projects_personal"),
        "gridpulse": ("GridPulse", r"C:\Users\user\OneDrive\Desktop\Projects\GridPulse"),
        "grid": ("GridPulse", r"C:\Users\user\OneDrive\Desktop\Projects\GridPulse"),
        "cli project": ("CLI Project", r"C:\Users\user\OneDrive\Desktop\applications_cli"),
        "cli": ("CLI Project", r"C:\Users\user\OneDrive\Desktop\applications_cli"),
        "projects": ("Projects", r"C:\Users\user\OneDrive\Desktop\Projects"),
    }

    canonical_name = None
    disk_path = None

    for k, (c_name, c_path) in known_projects.items():
        if q == k:
            canonical_name = c_name
            disk_path = c_path
            break

    if not canonical_name:
        if "personal" in q:
            canonical_name, disk_path = known_projects["projects_personal"]
        elif "pulse" in q or "grid" in q:
            canonical_name, disk_path = known_projects["gridpulse"]
        elif "cli" in q:
            canonical_name, disk_path = known_projects["cli project"]
        elif "project" in q:
            canonical_name, disk_path = known_projects["projects"]
        else:
            canonical_name = proj_query.strip()
            disk_path = os.path.join(r"C:\Users\user\OneDrive\Desktop", proj_query)
            if not os.path.exists(disk_path):
                disk_path = os.path.join(r"C:\Users\user\OneDrive\Desktop\Projects", proj_query)

    convos = []
    db_path = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT title, last_modified_time
                FROM conversations_fts
                WHERE (project LIKE ? OR workspace LIKE ?) AND title IS NOT NULL AND title != ''
                ORDER BY last_modified_time DESC;
            """, (f"%{canonical_name}%", f"%{canonical_name}%"))
            for title, mtime in cur.fetchall():
                if title not in convos:
                    convos.append(title)
            conn.close()
        except Exception:
            pass

    subfolders = []
    if disk_path and os.path.exists(disk_path):
        try:
            items = os.listdir(disk_path)
            for it in items:
                if it.startswith(".") or it == "__pycache__":
                    continue
                p_it = os.path.join(disk_path, it)
                if os.path.isdir(p_it):
                    subfolders.append(f"📁 `{it}/`")
                else:
                    subfolders.append(f"📄 `{it}`")
        except Exception:
            pass

    lines = [f"📂 *Project Workspace: {canonical_name}*"]
    if disk_path and os.path.exists(disk_path):
        lines.append(f"📍 Path: `{disk_path}`\n")
    else:
        lines.append("")

    if subfolders:
        lines.append("🗂️ *Workspace Files & Folders:*")
        for sf in subfolders[:12]:
            lines.append(f"• {sf}")
        if len(subfolders) > 12:
            lines.append(f"_...and {len(subfolders) - 12} more items_")
        lines.append("")

    if convos:
        lines.append(f"💬 *Recent Chats in this Project ({len(convos)}):*")
        for c in convos[:10]:
            lines.append(f"• {c}")
        if len(convos) > 10:
            lines.append(f"_...and {len(convos) - 10} more chats_")
    else:
        lines.append("💬 *No chat history recorded for this project yet.*")

    lines.append(f"\n💡 *Quick Action:* Type `/new {canonical_name}` to start a fresh chat in this workspace!")
    return "\n".join(lines)

def get_session_info(query: str = "") -> str:
    """
    Retrieves detailed information, history preview, and latest output for a specific chat session,
    or lists recent chat sessions if query is empty.
    """
    db_path = os.path.expanduser(r"~/.gemini/antigravity/conversation_summaries.db")
    if not os.path.exists(db_path):
        return "❌ Antigravity database not found."

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    q = query.strip()
    
    # 1. No query -> List top 10 recent sessions
    if not q:
        cur.execute("""
            SELECT conversation_id, title, step_count, last_modified_time
            FROM conversation_summaries
            WHERE title IS NOT NULL AND title != ''
            ORDER BY last_modified_time DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return "💬 No active chat sessions found."

        lines = ["💬 *Recent Antigravity Chat Sessions:*\n"]
        for cid, title, steps, mtime in rows:
            time_str = str(mtime)[:16]
            lines.append(f"• *{title}* ({steps} steps)")
            lines.append(f"  `{cid[:8]}` • _{time_str}_")
            lines.append(f"  👉 `/chat {title}`\n")
        lines.append("💡 *Tip:* Send `/chat <name>` or `/chat <id>` to inspect any session.")
        return "\n".join(lines)

    # 2. Search for matching conversation
    cur.execute("""
        SELECT conversation_id, title, step_count, last_modified_time, project_id, preview
        FROM conversation_summaries
        WHERE conversation_id LIKE ? OR title LIKE ?
        ORDER BY last_modified_time DESC
    """, (f"{q}%", f"%{q}%"))
    matches = cur.fetchall()
    conn.close()

    if not matches:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT conversation_id, title, max(last_modified_time)
                FROM conversations_fts
                WHERE conversations_fts MATCH ?
                GROUP BY conversation_id
                ORDER BY last_modified_time DESC
                LIMIT 5
            """, (f'"{q}"',))
            fts_matches = cur.fetchall()
            conn.close()
            if fts_matches:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                placeholders = ','.join('?' * len(fts_matches))
                cur.execute(f"""
                    SELECT conversation_id, title, step_count, last_modified_time, project_id, preview
                    FROM conversation_summaries
                    WHERE conversation_id IN ({placeholders})
                """, [m[0] for m in fts_matches])
                matches = cur.fetchall()
                conn.close()
        except Exception:
            pass

    if not matches:
        return (
            f"❌ No chat session found matching *\"{q}\"*.\n\n"
            "💡 Type `/chats` to see a list of recent active conversations."
        )

    best = None
    for m in matches:
        if m[1].lower() == q.lower() or m[0].lower().startswith(q.lower()):
            best = m
            break
    if not best:
        best = matches[0]

    cid, title, steps, mtime, project_id, preview = best

    base_brain = os.path.expanduser(r"~/.gemini/antigravity/brain")
    transcript_path = os.path.join(base_brain, cid, ".system_generated", "logs", "transcript.jsonl")

    first_user_prompt = ""
    last_user_prompt = ""
    last_agent_response = ""
    total_steps = steps

    if os.path.exists(transcript_path):
        try:
            with open(transcript_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        src = obj.get("source")
                        tp = obj.get("type")
                        content = obj.get("content")
                        if not content:
                            continue

                        clean_content = content
                        if "<USER_REQUEST>" in clean_content:
                            idx1 = clean_content.find("<USER_REQUEST>") + 14
                            idx2 = clean_content.find("</USER_REQUEST>")
                            if idx2 != -1:
                                clean_content = clean_content[idx1:idx2].strip()

                        if tp == "USER_INPUT" or src == "USER_EXPLICIT":
                            if not first_user_prompt:
                                first_user_prompt = clean_content
                            last_user_prompt = clean_content
                        elif tp == "PLANNER_RESPONSE" or src == "MODEL":
                            last_agent_response = content
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            last_agent_response = f"(Error reading transcript: {e})"

    if len(last_agent_response) > 1500:
        last_agent_response = last_agent_response[-1500:] + "\n_...(truncated)_"

    status_indicator = "⚪ *Status:* Stored Session"
    try:
        win = find_antigravity_window()
        if win and title and title.lower() in win[2].lower():
            status_indicator = "🟢 *Status:* Active in PC Foreground"
    except Exception:
        pass

    lines = [
        f"💬 *Chat Session:* `{title}`",
        f"🆔 `ID: {cid}`",
        f"📊 *Steps:* {total_steps}  •  🕒 *Updated:* {str(mtime)[:19]}",
        f"{status_indicator}\n"
    ]

    if len(matches) > 1:
        other_matches = [m for m in matches if m[0] != cid]
        if other_matches:
            lines.append(f"ℹ️ _Found {len(matches)} matching sessions. Showing newest (`{cid[:8]}`)._")
            lines.append(f"_Other session ID: `/chat {other_matches[0][0][:8]}`_\n")

    if first_user_prompt:
        lines.append(f"🎯 *Goal / First Prompt:*\n_{first_user_prompt[:250]}_\n")

    if last_user_prompt and last_user_prompt != first_user_prompt:
        lines.append(f"📩 *Latest User Request:*\n_{last_user_prompt[:250]}_\n")

    if last_agent_response:
        lines.append(f"🤖 *Latest Output:*\n{last_agent_response}")
    elif preview:
        lines.append(f"📝 *Preview:*\n{preview}")
    else:
        lines.append("ℹ️ _No output recorded yet for this session._")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💡 *To send a prompt:* Any message you send targets the active PC session.")
    lines.append(f"💡 *To open a fresh chat:* `/new`")

    return "\n".join(lines)

def get_latest_conversation_transcript():
    """Finds the most recently updated conversation transcript."""
    base_brain = os.path.expanduser(r"~/.gemini/antigravity/brain")
    if not os.path.exists(base_brain):
        return None

    pattern = os.path.join(base_brain, "*", ".system_generated", "logs", "transcript.jsonl")
    files = glob.glob(pattern)
    if not files:
        return None

    latest_file = max(files, key=os.path.getmtime)
    last_response = None
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "PLANNER_RESPONSE" and obj.get("content"):
                        last_response = obj.get("content")
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return last_response
