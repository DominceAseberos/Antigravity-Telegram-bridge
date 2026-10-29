import os
import io
import time
import ctypes
from ctypes import wintypes
from PIL import Image

from .system_guard import is_user_actively_typing

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Virtual Key Codes
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key
VK_L = 0x4C
VK_V = 0x56
VK_N = 0x4E
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_UP = 0x26
VK_DOWN = 0x28

SW_RESTORE = 9

KEYEVENTF_KEYUP = 0x0002
GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13
CF_DIB = 8

# Explicit 64-bit Win32 Function Signatures (prevents truncation & access violations)
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID

kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL

kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL

user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL

user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL

user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.SetActiveWindow.argtypes = [wintypes.HWND]
user32.SetActiveWindow.restype = wintypes.HWND

user32.SetFocus.argtypes = [wintypes.HWND]
user32.SetFocus.restype = wintypes.HWND

user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL

user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HANDLE

user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
user32.SetThreadDesktop.restype = wintypes.BOOL

EXCLUDED_WINDOW_TITLES = [
    "antigravity telegram remote bridge",
    "chatgpt",
    "google chrome",
    "microsoft edge",
    "brave",
    "discord",
    "spotify",
    "visual studio code",
    "obs "
]

def press_key(vk_code):
    """Sends a hardware keypress and release via Windows API."""
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

def press_hotkey(modifier_vk, key_vk):
    """Sends a hotkey combination (e.g. Ctrl+L, Ctrl+V, Ctrl+N)."""
    user32.keybd_event(modifier_vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.03)
    user32.keybd_event(modifier_vk, 0, KEYEVENTF_KEYUP, 0)

def set_clipboard(text: str) -> bool:
    """Sets Unicode text onto the Windows system clipboard safely."""
    if not user32.OpenClipboard(None):
        time.sleep(0.05)
        if not user32.OpenClipboard(None):
            return False
    try:
        user32.EmptyClipboard()
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            return False
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            return False
        ctypes.memmove(p_mem, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        return True
    finally:
        user32.CloseClipboard()

def copy_image_to_clipboard(pil_img) -> bool:
    """Copies a PIL Image to the Windows clipboard in CF_DIB format."""
    output = io.BytesIO()
    pil_img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # Strip 14-byte BMP header for DIB
    output.close()

    if not user32.OpenClipboard(None):
        time.sleep(0.05)
        if not user32.OpenClipboard(None):
            return False
    try:
        user32.EmptyClipboard()
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            return False
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            return False
        ctypes.memmove(p_mem, data, len(data))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(CF_DIB, h_mem)
        return True
    finally:
        user32.CloseClipboard()

def is_antigravity_hwnd(hwnd) -> tuple[bool, str]:
    """Determines if a window handle belongs to the Antigravity desktop application."""
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return False, ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return False, ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buff, length + 1)
    title = buff.value
    t_lower = title.lower()

    cls_buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls_buff, 256)
    cls_name = cls_buff.value

    # Antigravity desktop is an Electron application (window class Chrome_WidgetWin_1)
    if cls_name != "Chrome_WidgetWin_1":
        return False, title

    for ex in EXCLUDED_WINDOW_TITLES:
        if ex in t_lower:
            return False, title

    return True, title

def ensure_attached_to_input_desktop():
    """Attaches the calling thread to the current interactive input desktop."""
    try:
        h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
            return h_desk
    except Exception:
        pass
    return None

def find_antigravity_window():
    """Finds the handle of the running Antigravity graphical desktop window."""
    ensure_attached_to_input_desktop()
    found_windows = []

    def enum_cb(hwnd, lparam):
        ok, title = is_antigravity_hwnd(hwnd)
        if ok:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found_windows.append((hwnd, pid.value, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
    user32.EnumDesktopWindows(h_desk, WNDENUMPROC(enum_cb), 0)

    if found_windows:
        for w in found_windows:
            if not any(ex in w[2].lower() for ex in EXCLUDED_WINDOW_TITLES):
                return w
        return found_windows[0]
    return None

def focus_window(hwnd):
    """Forces the target window into the foreground reliably."""
    ensure_attached_to_input_desktop()
    user32.ShowWindow(hwnd, SW_RESTORE)

    cur_thread = kernel32.GetCurrentThreadId()
    fore_hwnd = user32.GetForegroundWindow()
    fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None) if fore_hwnd else 0
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    if fore_thread and fore_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, fore_thread, True)
    if target_thread and target_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, target_thread, True)

    # Bypass Windows foreground lock via Alt key pulse
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetFocus(hwnd)

    if fore_thread and fore_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, fore_thread, False)
    if target_thread and target_thread != cur_thread:
        user32.AttachThreadInput(cur_thread, target_thread, False)

def get_active_window_title() -> str:
    """Returns the title of the current foreground window."""
    ensure_attached_to_input_desktop()
    fore_hwnd = user32.GetForegroundWindow()
    if not fore_hwnd:
        return ""
    length = user32.GetWindowTextLengthW(fore_hwnd)
    if length == 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(fore_hwnd, buff, length + 1)
    return buff.value

def is_antigravity_active() -> tuple[bool, str]:
    """Checks if the active foreground window belongs to Antigravity."""
    ensure_attached_to_input_desktop()
    fore_hwnd = user32.GetForegroundWindow()
    if not fore_hwnd:
        return False, ""

    # Check by process ID
    target = find_antigravity_window()
    if target:
        _, target_pid, target_title = target
        f_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fore_hwnd, ctypes.byref(f_pid))
        if f_pid.value == target_pid:
            return True, target_title

    return is_antigravity_hwnd(fore_hwnd)

def focus_antigravity_safe() -> tuple[bool, str, int]:
    """
    Finds Antigravity, unminimizes it, brings it to foreground, and verifies it is active.
    """
    ensure_attached_to_input_desktop()
    target = find_antigravity_window()
    if not target:
        return False, "Could not find any open Antigravity desktop window on your PC.", 0

    hwnd, pid, title = target

    # Guard: If user is actively typing on PC in another window, wait briefly
    if is_user_actively_typing(idle_threshold_seconds=2.0):
        fore_ok, _ = is_antigravity_active()
        if not fore_ok:
            time.sleep(1.0)

    # Force foreground focus
    focus_window(hwnd)
    time.sleep(0.18)

    # Verification Guard
    is_active, active_title = is_antigravity_active()
    if not is_active:
        # Retry once
        focus_window(hwnd)
        time.sleep(0.15)
        is_active, active_title = is_antigravity_active()

    if not is_active:
        # Check foreground PID directly
        fore_hwnd = user32.GetForegroundWindow()
        f_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(fore_hwnd, ctypes.byref(f_pid))
        if f_pid.value == pid:
            is_active = True

    if not is_active:
        return (
            False,
            f"Antigravity is not active on screen (current foreground: '{active_title}'). Message was safely cancelled to avoid typing into another app.",
            hwnd
        )

    return True, title, hwnd

def focus_prompt_box_keyboard():
    """Focuses prompt textarea via vision-assisted click, falling back to Ctrl+L."""
    ensure_attached_to_input_desktop()
    # 1. Vision click right above model pill
    try:
        from PIL import ImageGrab
        from .models import locate_model_pill_vision, click_at
        shot = ImageGrab.grab()
        pill = locate_model_pill_vision(shot)
        if pill:
            click_x, click_y, pill_left, pill_right, pill_top, pill_bottom = pill
            input_y = pill_top - 35
            click_at(click_x, input_y)
            time.sleep(0.08)
            return
    except Exception:
        pass

    # 2. Keyboard shortcut fallback: Ctrl+L
    press_hotkey(VK_CONTROL, VK_L)
    time.sleep(0.08)

def inject_prompt_to_antigravity(prompt: str) -> tuple[bool, str]:
    """Focuses Antigravity safely, focuses prompt via Ctrl+L, and pastes prompt."""
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return False, message

    if not set_clipboard(prompt):
        return False, "Failed to copy prompt to Windows clipboard."

    focus_prompt_box_keyboard()
    time.sleep(0.1)

    # Paste via Ctrl+V
    press_hotkey(VK_CONTROL, VK_V)
    time.sleep(0.25)

    # Submit via Enter
    press_key(VK_RETURN)

    return True, f"Targeted: {message}"

def inject_photo_to_antigravity(pil_img, caption: str = "") -> tuple[bool, str]:
    """Copies an image to clipboard and pastes it into Antigravity."""
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return False, message

    if not copy_image_to_clipboard(pil_img):
        return False, "Failed to copy image to Windows clipboard."

    focus_prompt_box_keyboard()
    time.sleep(0.1)

    # Paste image via Ctrl+V
    press_hotkey(VK_CONTROL, VK_V)
    time.sleep(0.8)

    # If caption is provided, paste and submit
    if caption:
        if set_clipboard(caption):
            press_hotkey(VK_CONTROL, VK_V)
            time.sleep(0.2)

    press_key(VK_RETURN)
    return True, f"Image attached & submitted to: {message}"

def create_new_conversation(project_name: str = None) -> tuple[bool, str]:
    """Opens a new chat session in Antigravity via keyboard shortcut (Ctrl+N)."""
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return False, message

    # Keyboard shortcut for New Chat in Antigravity: Ctrl+N
    press_hotkey(VK_CONTROL, VK_N)
    time.sleep(0.35)

    focus_prompt_box_keyboard()
    return True, f"New conversation started (Project: {project_name or 'Default'})"

def emergency_stop_antigravity() -> tuple[bool, str]:
    """Sends an Escape key event to halt / cancel current generation in Antigravity."""
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return False, message

    press_key(VK_ESCAPE)
    time.sleep(0.05)
    press_key(VK_ESCAPE)
    return True, "Sent STOP (Escape) signal to Antigravity."

def send_approval_keystroke() -> tuple[bool, str]:
    """Sends an Enter keypress to Antigravity to confirm / approve a pending action."""
    success, message, hwnd = focus_antigravity_safe()
    if not success:
        return False, message

    press_key(VK_RETURN)
    return True, "Sent APPROVE (Enter) signal to Antigravity."
