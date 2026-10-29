import os
import glob
import time
import json

from .config import (
    load_watcher_state,
    save_watcher_state,
    send_telegram_chunked,
    send_telegram_action
)
from .keyboards import send_approval_request

def get_file_highest_step(file_path: str) -> int:
    """Quickly scans a transcript.jsonl file to find the highest step_index."""
    max_step = -1
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    s = obj.get("step_index")
                    if s is not None and s > max_step:
                        max_step = s
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return max_step

def start_transcript_watcher(token: str, get_chat_id_func):
    """
    Continuously monitors Antigravity's transcript and forwards ONLY NEW live responses to Telegram.
    Includes active typing heartbeat when Antigravity is generating output.
    Guarantees that old conversation history is NEVER sent on startup, restart, or refresh.
    """
    watcher_state = load_watcher_state()
    active_convo_id = None
    last_typing_time = 0
    print("👀 Live response watcher thread started (Clean mode: zero historical spam)!", flush=True)

    while True:
        try:
            time.sleep(1.5)
            chat_id = get_chat_id_func()
            if not chat_id:
                continue

            base_brain = os.path.expanduser(r"~/.gemini/antigravity/brain")
            pattern = os.path.join(base_brain, "*", ".system_generated", "logs", "transcript.jsonl")
            files = glob.glob(pattern)
            if not files:
                continue

            latest_file = max(files, key=os.path.getmtime)

            norm_parts = os.path.normpath(latest_file).split(os.sep)
            convo_id = norm_parts[-4] if len(norm_parts) >= 4 else "default"

            # Cold boot initialization: record current state without emitting historical messages
            if convo_id not in watcher_state:
                current_max = get_file_highest_step(latest_file)
                current_size = os.path.getsize(latest_file)
                watcher_state[convo_id] = {
                    "last_step_index": current_max,
                    "last_byte_offset": current_size
                }
                save_watcher_state(watcher_state)
                active_convo_id = convo_id
                continue

            saved_info = watcher_state.get(convo_id)
            if isinstance(saved_info, int):
                last_step = saved_info
                last_offset = 0
            elif isinstance(saved_info, dict):
                last_step = saved_info.get("last_step_index", -1)
                last_offset = saved_info.get("last_byte_offset", 0)
            else:
                last_step = -1
                last_offset = 0

            cur_size = os.path.getsize(latest_file)
            if cur_size <= last_offset and last_offset > 0:
                continue

            # Read new bytes appended since last check
            new_lines = []
            with open(latest_file, "r", encoding="utf-8") as f:
                if last_offset > 0 and cur_size >= last_offset:
                    f.seek(last_offset)
                new_chunk = f.read()
                new_offset = f.tell()

            if not new_chunk.strip():
                continue

            for raw_line in new_chunk.splitlines():
                raw_line = raw_line.strip()
                if raw_line:
                    try:
                        new_lines.append(json.loads(raw_line))
                    except json.JSONDecodeError:
                        pass

            if not new_lines:
                watcher_state[convo_id]["last_byte_offset"] = new_offset
                save_watcher_state(watcher_state)
                continue

            highest_step_seen = last_step
            responses_to_send = []

            for obj in new_lines:
                s_idx = obj.get("step_index", -1)
                if s_idx > highest_step_seen:
                    highest_step_seen = s_idx

                # Check if Antigravity is currently generating (send typing heartbeat)
                status = obj.get("status")
                if status == "RUNNING" or obj.get("type") in ["GENERIC", "TOOL_CALL"]:
                    now = time.time()
                    if now - last_typing_time > 4.0:
                        send_telegram_action(token, chat_id, "typing")
                        last_typing_time = now

                # Check for approval / interactive question requests
                tool_calls = obj.get("tool_calls", [])
                if isinstance(tool_calls, list):
                    for tc in tool_calls:
                        if isinstance(tc, dict) and tc.get("name") == "ask_question":
                            args = tc.get("args", {})
                            questions = args.get("questions", [])
                            if questions and s_idx > last_step:
                                q_lines = []
                                for q_item in questions:
                                    q_lines.append(f"❓ *{q_item.get('question')}*")
                                    opts = q_item.get("options", [])
                                    for opt in opts[:4]:
                                        q_lines.append(f"  • {opt}")
                                send_approval_request(token, chat_id, "\n".join(q_lines))

                # Only forward final planner responses from the model
                if (
                    obj.get("source") == "MODEL"
                    and obj.get("type") == "PLANNER_RESPONSE"
                    and obj.get("status") == "DONE"
                ):
                    content = obj.get("content", "").strip()
                    if content and s_idx > last_step:
                        responses_to_send.append(content)

            # Update persisted watcher state
            watcher_state[convo_id] = {
                "last_step_index": highest_step_seen,
                "last_byte_offset": new_offset
            }
            save_watcher_state(watcher_state)

            # Send completed model responses to Telegram
            for resp in responses_to_send:
                print(f"🚀 Forwarding live Antigravity response to Telegram ({len(resp)} chars)...", flush=True)
                send_telegram_chunked(token, chat_id, resp)

        except Exception as e:
            print(f"Transcript watcher error: {e}", flush=True)
            time.sleep(2)
