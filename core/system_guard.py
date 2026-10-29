import os
import io
import time
import requests
from PIL import ImageGrab

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    # Thread Execution State Flags (Windows Power Management)
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_AWAYMODE_REQUIRED = 0x00000040

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD)
        ]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("sullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", wintypes.BYTE),
            ("BatteryFlag", wintypes.BYTE),
            ("BatteryLifePercent", wintypes.BYTE),
            ("SystemStatusFlag", wintypes.BYTE),
            ("BatteryLifeTime", wintypes.DWORD),
            ("BatteryFullLifeTime", wintypes.DWORD),
        ]

    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    user32.GetLastInputInfo.restype = wintypes.BOOL
    kernel32.GetTickCount.argtypes = []
    kernel32.GetTickCount.restype = wintypes.DWORD
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    kernel32.GetSystemPowerStatus.argtypes = [ctypes.POINTER(SYSTEM_POWER_STATUS)]
    kernel32.GetSystemPowerStatus.restype = wintypes.BOOL
    kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    kernel32.SetThreadExecutionState.restype = wintypes.DWORD

def get_system_health_report(model_name: str = "", win_info: tuple = None, is_active: bool = False) -> str:
    """Generates a complete system health, resource utilization, and status report for Telegram."""
    total_ram = 0.0
    used_ram = 0.0
    mem_load = 0
    power_str = "🔌 AC Power"

    try:
        import psutil
        vmem = psutil.virtual_memory()
        total_ram = vmem.total / (1024**3)
        used_ram = vmem.used / (1024**3)
        mem_load = int(vmem.percent)
        battery = psutil.sensors_battery()
        if battery:
            ac_state = "Charging" if battery.power_plugged else "Discharging"
            power_str = f"🔋 Battery: {battery.percent}% ({ac_state})"
    except Exception:
        if IS_WINDOWS:
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_ram = mem.ullTotalPhys / (1024**3)
            used_ram = (mem.ullTotalPhys - mem.ullAvailPhys) / (1024**3)
            mem_load = mem.dwMemoryLoad
            sps = SYSTEM_POWER_STATUS()
            if kernel32.GetSystemPowerStatus(ctypes.byref(sps)) and sps.BatteryLifePercent != 255:
                ac_state = "Charging" if sps.ACLineStatus == 1 else "Discharging"
                power_str = f"🔋 Battery: {sps.BatteryLifePercent}% ({ac_state})"

    idle_sec = get_user_idle_seconds()
    if idle_sec < 60:
        idle_str = f"{int(idle_sec)}s ago (Active)"
    elif idle_sec < 3600:
        idle_str = f"{int(idle_sec // 60)}m ago (Away)"
    else:
        idle_str = f"{int(idle_sec // 3600)}h ago (Idle)"

    ag_status = "❌ Not Running"
    pid_str = "N/A"
    win_title = "N/A"
    if win_info:
        hwnd, pid, title = win_info
        pid_str = str(pid)
        win_title = title
        ag_status = "🟢 Online (Foreground)" if is_active else "🟡 Online (Background / Minimized)"

    lines = [
        "🖥️ *System Health & Resource Monitor*",
        "",
        "📊 *System Resources:*",
        f"• *RAM:* `{used_ram:.1f} GB` / `{total_ram:.1f} GB` ({mem_load}% load)",
        f"• *Power:* {power_str}",
        f"• *Input Activity:* Last seen {idle_str}",
        "",
        "🤖 *Antigravity Desktop State:*",
        f"• *Process Status:* {ag_status}",
        f"• *Process PID:* `{pid_str}`",
        f"• *Active Window:* `{win_title}`",
        f"• *Engine Model:* {model_name or 'Default'}",
    ]
    return "\n".join(lines)

def inhibit_sleep(enable: bool = True):
    """Prevents system sleep during long remote tasks."""
    if not IS_WINDOWS:
        return
    try:
        if enable:
            flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            kernel32.SetThreadExecutionState(flags)
        else:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception as e:
        print(f"Error adjusting sleep state: {e}", flush=True)

def get_user_idle_seconds() -> float:
    """Returns seconds since the user last physically interacted with the PC."""
    if not IS_WINDOWS:
        return 0.0
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = kernel32.GetTickCount() - lii.dwTime
            return max(0.0, millis / 1000.0)
    except Exception:
        pass
    return 0.0

def is_user_actively_typing(threshold_seconds: float = 3.0) -> bool:
    """Returns True if the user physically touched their keyboard or mouse within threshold_seconds."""
    return get_user_idle_seconds() < threshold_seconds

def capture_and_send_screenshot(token: str, chat_id: int):
    """Captures the current screen and sends it as a photo to Telegram."""
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        buf.seek(0)
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        data = {
            "chat_id": chat_id,
            "caption": f"📸 *PC Screen Capture*\n`{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            "parse_mode": "Markdown"
        }
        files = {"photo": ("screenshot.jpg", buf, "image/jpeg")}
        requests.post(url, data=data, files=files, timeout=25, verify=False)
    except Exception as e:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": f"⚠️ Could not capture screenshot: {e}"}
        requests.post(url, json=payload, timeout=10, verify=False)
