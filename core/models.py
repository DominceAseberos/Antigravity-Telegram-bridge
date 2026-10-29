import os
import re
import time
import ctypes
from ctypes import wintypes
from PIL import ImageGrab

from .window_driver import (
    user32,
    ensure_attached_to_input_desktop,
    focus_antigravity_safe,
    press_key,
    VK_ESCAPE,
    VK_UP,
    VK_DOWN,
    VK_RETURN
)
from .config import send_telegram_photo

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
user32.mouse_event.restype = None

AVAILABLE_MODELS = {
    "flash": (
        "Gemini 3.8 Flash High",
        "MODEL_PLACEHOLDER_M318",
        "Default • Ultra-fast, highly intelligent coding & tool execution"
    ),
    "argon": (
        "Gemini 4 Argon (High)",
        "MODEL_PLACEHOLDER_M408",
        "Flagship tier • Deep reasoning, complex refactoring & system architecture"
    ),
    "pro": (
        "Gemini 2.5 Pro",
        "MODEL_GOOGLE_GEMINI_2_5_PRO",
        "Advanced multimodal reasoning & coding precision"
    ),
    "sonnet": (
        "Claude Sonnet 5.5",
        "claude-sonnet-5-5-high",
        "Anthropic advanced reasoning & architecture"
    ),
    "opus": (
        "Claude Opus 5.5",
        "claude-opus-5-5-high",
        "Anthropic flagship tier maximum reasoning"
    ),
}

def get_current_model_info() -> tuple[str, str]:
    """Reads the currently active model from Antigravity's state configuration."""
    state_file = os.path.expanduser(r"~/.gemini/antigravity/antigravity_state.pbtxt")
    raw_model = "MODEL_PLACEHOLDER_M318"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                content = f.read()
                m = re.search(r"last_selected_agent_model:\s*(\S+)", content)
                if m:
                    raw_model = m.group(1).strip()
        except Exception:
            pass

    friendly_map = {
        "MODEL_PLACEHOLDER_M318": "Gemini 3.8 Flash High",
        "MODEL_PLACEHOLDER_M124": "Gemini 3.8 Flash High",
        "MODEL_PLACEHOLDER_M408": "Gemini 4 Argon (High)",
        "MODEL_PLACEHOLDER_M400": "Gemini 4 Argon (Medium)",
        "MODEL_GOOGLE_GEMINI_2_5_PRO": "Gemini 2.5 Pro",
        "MODEL_GOOGLE_GEMINI_2_5_FLASH": "Gemini 2.5 Flash",
        "claude-sonnet-5-5-high": "Claude Sonnet 5.5",
        "claude-opus-5-5-high": "Claude Opus 5.5",
    }
    friendly_name = friendly_map.get(raw_model, raw_model)
    return friendly_name, raw_model

def get_models_overview() -> str:
    """Formats an overview of the active and available models for Telegram."""
    current_name, raw_id = get_current_model_info()
    msg = (
        "🤖 *Antigravity AI Models*\n\n"
        f"🎯 *Current Active Model:*\n"
        f"• *{current_name}*\n\n"
        "📋 *Available Models:*\n"
        "1. ⚡ *Gemini 3.8 Flash High* (`/model flash`)\n"
        "   _Default • Ultra-fast, highly intelligent coding model_\n\n"
        "2. 🧠 *Gemini 4 Argon (High)* (`/model argon`)\n"
        "   _Flagship • Deep reasoning, complex refactoring & architecture_\n\n"
        "3. 🎯 *Gemini Pro* (`/model pro`)\n"
        "   _Advanced multimodal reasoning & coding precision_\n\n"
        "4. 🌟 *Claude Sonnet 5.5* (`/model sonnet`)\n"
        "   _Anthropic advanced reasoning & architecture_\n\n"
        "5. 🏆 *Claude Opus 5.5* (`/model opus`)\n"
        "   _Anthropic flagship tier maximum reasoning_\n\n"
        "💡 *How to switch:*\n"
        "• Send `/model argon` or `/model flash` to update your model.\n"
        "• Then type `/new` to immediately start a fresh conversation with it!\n"
        "• In the PC app, you can also click the model pill at the bottom-left of the chat box (`+ Gemini 3.8 Flash High ^`)."
    )
    return msg

def locate_model_pill_vision(img):
    """
    Locates the model pill ('+ Gemini ... ^') inside Antigravity by analyzing text bands
    in the bottom region of the live window. Works dynamically on any resolution or layout.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    gray = img.convert('L')
    w, h = gray.size
    crop_h = int(h * 0.12)
    crop_top = h - crop_h
    arr = np.array(gray.crop((0, crop_top, w, h)))

    # Text pixels are brighter than background (background ~25-35, text > 65)
    mask = arr > 65

    # Look in the center-left band where the model pill sits: 15% to 60% of screen width
    band_x1 = int(w * 0.15)
    band_x2 = int(w * 0.60)
    band = mask[:, band_x1:band_x2]

    ys, xs = np.where(band)
    if len(xs) == 0:
        return None

    # Filter to the bottom action row (bottom 45% of the crop)
    row_filter = ys > int(crop_h * 0.40)
    ys_row = ys[row_filter]
    xs_row = xs[row_filter] + band_x1

    if len(xs_row) == 0:
        return None

    pill_left = int(xs_row.min())
    pill_right = int(xs_row.max())
    pill_top = int(ys_row.min()) + crop_top
    pill_bottom = int(ys_row.max()) + crop_top

    # Click in the middle of the pill
    click_x = (pill_left + pill_right) // 2
    click_y = (pill_top + pill_bottom) // 2

    return click_x, click_y, pill_left, pill_right, pill_top, pill_bottom

def click_at(x: int, y: int):
    """Sends a hardware mouse click event at exact screen coordinates."""
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004

    # Screen dimensions
    sm_cxscreen = user32.GetSystemMetrics(0)
    sm_cyscreen = user32.GetSystemMetrics(1)

    norm_x = int(x * 65535 / sm_cxscreen)
    norm_y = int(y * 65535 / sm_cyscreen)

    user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, norm_x, norm_y, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTDOWN, norm_x, norm_y, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_LEFTUP, norm_x, norm_y, 0, 0)

def switch_model_smart_vision(query: str, token: str, chat_id: int) -> tuple[bool, str]:
    """
    Smart Vision-Assisted Model Switcher:
    1. Updates global config (antigravity_state.pbtxt) for new sessions.
    2. Brings Antigravity to foreground safely.
    3. Locates the model pill dynamically via computer vision.
    4. Clicks the pill to open the menu and selects the requested model in the CURRENT chat!
    5. Sends a verification screenshot to Telegram.
    """
    q = query.lower().strip()

    matched_key = None
    if any(k in q for k in ["argon", "gemini 4", "gemini 4 argon", "m408"]):
        matched_key = "argon"
    elif any(k in q for k in ["flash", "gemini 3.8", "flash high", "m318"]):
        matched_key = "flash"
    elif any(k in q for k in ["pro", "gemini pro", "2.5 pro", "3.1 pro"]):
        matched_key = "pro"
    elif any(k in q for k in ["sonnet", "claude sonnet", "5.5 sonnet"]):
        matched_key = "sonnet"
    elif any(k in q for k in ["opus", "claude opus", "5.5 opus"]):
        matched_key = "opus"
    else:
        return False, f"⚠️ Unknown model '{query}'. Send `/models` to view all available models."

    friendly_name, model_id, desc = AVAILABLE_MODELS[matched_key]

    # 1. Update engine persistent state
    state_file = os.path.expanduser(r"~/.gemini/antigravity/antigravity_state.pbtxt")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                content = f.read()
            if "last_selected_agent_model:" in content:
                new_content = re.sub(
                    r"last_selected_agent_model:\s*\S+",
                    f"last_selected_agent_model: {model_id}",
                    content
                )
            else:
                new_content = content + f"\nlast_selected_agent_model: {model_id}\n"
            with open(state_file, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception:
            pass

    # 2. Focus Antigravity window
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return True, (
            f"🎯 *Model setting updated to {friendly_name}!*\n\n"
            f"ℹ️ {message}\n"
            f"💡 Type `/new` to open a fresh conversation with {friendly_name}."
        )

    # 3. Vision Detection of Model Pill
    time.sleep(0.18)
    pill_info = None
    try:
        ensure_attached_to_input_desktop()
        shot = ImageGrab.grab()
        pill_info = locate_model_pill_vision(shot)
    except Exception as e:
        print(f"Vision detection error: {e}", flush=True)

    if not pill_info:
        press_key(VK_ESCAPE)
        return True, (
            f"🎯 *Preferred model set to {friendly_name}!*\n\n"
            f"• Description: _{desc}_\n"
            f"💡 Type `/new` from your phone to start a fresh chat with {friendly_name}."
        )

    click_x, click_y, pill_left, pill_right, pill_top, pill_bottom = pill_info

    # 4. Click the model pill
    click_at(click_x, click_y)
    time.sleep(0.28)

    # 5. Navigate dropdown menu
    if matched_key == "argon":
        press_key(VK_DOWN)
        time.sleep(0.1)
        press_key(VK_RETURN)
    elif matched_key == "flash":
        press_key(VK_UP)
        time.sleep(0.1)
        press_key(VK_RETURN)
    elif matched_key == "pro":
        press_key(VK_DOWN)
        time.sleep(0.08)
        press_key(VK_DOWN)
        time.sleep(0.1)
        press_key(VK_RETURN)
    else:
        press_key(VK_DOWN)
        time.sleep(0.1)
        press_key(VK_RETURN)

    time.sleep(0.4)

    # 6. Capture verification crop of the updated pill and send to Telegram
    try:
        w_screen, h_screen = shot.size
        crop_box = (
            max(0, pill_left - 30),
            max(0, pill_top - 15),
            min(w_screen, pill_right + 50),
            min(h_screen, pill_bottom + 15)
        )
        verify_img = ImageGrab.grab(bbox=crop_box)
        send_telegram_photo(
            token,
            chat_id,
            verify_img,
            caption=f"🎯 *Switched to {friendly_name} in current chat!*"
        )
    except Exception as e:
        print(f"Verification screenshot error: {e}", flush=True)

    return True, (
        f"✅ *Successfully switched to {friendly_name}!* (`{model_id}`)\n\n"
        f"• *Status:* Active in current conversation and set as default for new chats."
    )
