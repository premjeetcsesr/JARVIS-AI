# actions/mobile_control.py
"""
Mobile Control Action for JARVIS.

Enables JARVIS to control an Android smartphone wirelessly via ADB (Android Debug Bridge):
1. Connection: Connect to phone over Wi-Fi (IP/Port), check status, battery info.
2. App Management: Open/close any mobile app (WhatsApp, YouTube, Camera, Instagram, etc.).
3. Calls & Communication: Make phone calls, send WhatsApp/SMS messages, end calls.
4. Navigation & Hardware: Home, Back, Recent apps, Lock/Unlock screen, Volume, Media playback.
5. Touch & Gestures: Scroll up/down, Swipe, Tap, Type text into active fields.
6. Utilities: Take mobile screenshots, check battery percentage.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

# Common Android application package names
_APP_PACKAGES = {
    "whatsapp": "com.whatsapp",
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "google": "com.google.android.googlequicksearchbox",
    "camera": "com.android.camera",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "spotify": "com.spotify.music",
    "settings": "com.android.settings",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "gmail": "com.google.android.gm",
    "gallery": "com.google.android.apps.photos",
    "photos": "com.google.android.apps.photos",
    "playstore": "com.android.vending",
    "play store": "com.android.vending",
    "telegram": "org.telegram.messenger",
    "twitter": "com.twitter.android",
    "x": "com.twitter.android",
    "calculator": "com.google.android.calculator",
    "clock": "com.google.android.deskclock",
    "contacts": "com.google.android.contacts",
    "dialer": "com.google.android.dialer",
    "phone": "com.google.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "files": "com.google.android.documentsui",
    "file manager": "com.google.android.documentsui",
    "snapchat": "com.snapchat.android",
}

# Key event codes for Android ADB
_KEY_EVENTS = {
    "home": 3,
    "back": 4,
    "call": 5,
    "endcall": 6,
    "volume_up": 24,
    "volume_down": 25,
    "power": 26,
    "camera": 27,
    "menu": 82,
    "media_play_pause": 85,
    "media_stop": 86,
    "media_next": 87,
    "media_prev": 88,
    "mute": 164,
    "recent_apps": 187,
    "wakeup": 224,
    "sleep": 223,
}

_CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "last_mobile_ip.txt"


def _get_adb_path() -> str:
    """Finds adb binary path on the system."""
    found = shutil.which("adb")
    if found:
        return found

    candidates = [
        os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
        r"C:\Program Files\platform-tools\adb.exe",
        r"C:\Android\platform-tools\adb.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"


def _run_adb(args: list[str], timeout: int = 10) -> tuple[int, str]:
    """Runs an ADB command and returns (returncode, stdout)."""
    adb_bin = _get_adb_path()
    try:
        proc = subprocess.run(
            [adb_bin] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, "ADB command timed out."
    except Exception as e:
        return -1, str(e)


def _get_connected_devices() -> list[str]:
    """Returns list of active connected devices."""
    code, out = _run_adb(["devices"])
    devices = []
    if code == 0:
        lines = out.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
    return devices


def _ensure_connected(target_ip: Optional[str] = None) -> tuple[bool, str]:
    """Ensures that at least one device is connected, reconnecting if needed."""
    devices = _get_connected_devices()
    if devices:
        return True, devices[0]

    # Try connecting to given IP or cached last IP
    ip_to_try = target_ip
    if not ip_to_try and _CACHE_FILE.exists():
        try:
            ip_to_try = _CACHE_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    if ip_to_try:
        if ":" not in ip_to_try:
            ip_to_try = f"{ip_to_try}:5555"
        code, out = _run_adb(["connect", ip_to_try], timeout=8)
        if "connected to" in out.lower() and "cannot" not in out.lower():
            # Save successful IP
            try:
                _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                _CACHE_FILE.write_text(ip_to_try, encoding="utf-8")
            except Exception:
                pass
            return True, ip_to_try

    return False, "Phone is not connected to ADB."


def connect_phone(ip: str) -> str:
    """Connects to Android phone over Wi-Fi."""
    ip = ip.strip()
    if not ip:
        return "Boss, kripya phone ka IP address batayein (jaise: 10.190.62.50:5555)."

    if ":" not in ip:
        ip = f"{ip}:5555"

    code, out = _run_adb(["connect", ip], timeout=10)
    if "connected to" in out.lower() and "cannot" not in out.lower():
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(ip, encoding="utf-8")
        except Exception:
            pass
        return f"Phone safaltapoorvak connect ho gaya hai: {ip}"
    return f"Phone connect nahi ho paya: {out}"


def get_phone_status() -> str:
    """Gets connection status and battery details."""
    connected, dev = _ensure_connected()
    if not connected:
        return "Mobile abhi connected nahi hai. Kripya phone ko 'adb connect <IP>:5555' se connect karein."

    # Battery
    _, out = _run_adb(["shell", "dumpsys", "battery"])
    level = "Unknown"
    status = "Normal"
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("level:"):
            level = line.split(":", 1)[1].strip()
        elif line.startswith("status:"):
            s_val = line.split(":", 1)[1].strip()
            status = "Charging" if s_val in ("2", "charging") else "Discharging"

    # Model
    _, model = _run_adb(["shell", "getprop", "ro.product.model"])
    model_name = model.strip() if model else "Android Device"

    return f"Phone connected hai: {model_name}. Battery level {level}% hai aur status {status} hai."


def open_mobile_app(app_name: str) -> str:
    """Launches an application on the mobile phone."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai. Kripya pehle phone connect karein."

    clean_name = app_name.lower().strip()
    pkg = _APP_PACKAGES.get(clean_name)

    if not pkg:
        for k, v in _APP_PACKAGES.items():
            if k in clean_name or clean_name in k:
                pkg = v
                break

    if pkg:
        # Launch by package monkey command
        cmd = ["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]
        _run_adb(cmd)
        return f"Phone me {app_name.title()} khol diya hai, Sir."

    # Special intents
    if "camera" in clean_name:
        _run_adb(["shell", "am", "start", "-a", "android.media.action.STILL_IMAGE_CAMERA"])
        return "Phone ka camera open kar diya hai, Sir."

    # Try generic monkey launch with provided name
    _run_adb(["shell", "monkey", "-p", clean_name, "1"])
    return f"Phone me {app_name} open karne ki koshish ki hai."


def close_mobile_app(app_name: str) -> str:
    """Closes an application on the mobile phone."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    clean_name = app_name.lower().strip()
    pkg = _APP_PACKAGES.get(clean_name, clean_name)
    _run_adb(["shell", "am", "force-stop", pkg])
    return f"Phone me {app_name.title()} close kar diya hai, Sir."


def make_phone_call(number: str) -> str:
    """Dials or places a phone call on mobile."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    clean_num = re.sub(r"[^\d+]", "", number)
    if not clean_num:
        return "Kripya valid phone number batayein."

    # Place call via ACTION_CALL, fallback to ACTION_DIAL
    code, _ = _run_adb(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{clean_num}"])
    if code != 0:
        _run_adb(["shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", f"tel:{clean_num}"])

    return f"Phone par {clean_num} ko call laga diya hai, Sir."


def end_phone_call() -> str:
    """Ends the active phone call."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    _run_adb(["shell", "input", "keyevent", "6"])
    return "Call end kar diya gaya hai, Sir."


def lock_unlock_screen(action: str) -> str:
    """Locks or unlocks the phone screen."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    if action in ("lock", "band", "off", "sleep"):
        _run_adb(["shell", "input", "keyevent", "26"])
        return "Phone screen lock kar diya gaya hai, Sir."
    else:
        # Wakeup + swipe up to unlock
        _run_adb(["shell", "input", "keyevent", "224"])
        time.sleep(0.3)
        _run_adb(["shell", "input", "keyevent", "82"])
        time.sleep(0.3)
        _run_adb(["shell", "input", "swipe", "500", "1500", "500", "400", "200"])
        return "Phone screen unlock kar diya gaya hai, Sir."


def adjust_volume(direction: str) -> str:
    """Adjusts media volume up, down, or mute."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    if direction == "up":
        for _ in range(3):
            _run_adb(["shell", "input", "keyevent", "24"])
        return "Phone ka volume badha diya gaya hai."
    elif direction == "down":
        for _ in range(3):
            _run_adb(["shell", "input", "keyevent", "25"])
        return "Phone ka volume kam kar diya gaya hai."
    elif direction == "mute":
        _run_adb(["shell", "input", "keyevent", "164"])
        return "Phone ko mute kar diya gaya hai."
    return "Volume command samajh nahi aayi."


def navigation_key(key: str) -> str:
    """Presses navigation button (home, back, recent_apps)."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    keycode = _KEY_EVENTS.get(key)
    if keycode:
        _run_adb(["shell", "input", "keyevent", str(keycode)])
        return f"Phone par {key} press kar diya hai."
    return f"Unknown navigation key: {key}"


def scroll_screen(direction: str) -> str:
    """Scrolls or swipes the phone screen."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    if direction in ("down", "neeche", "reels"):
        # Swipe up to scroll down
        _run_adb(["shell", "input", "swipe", "500", "1400", "500", "400", "300"])
        return "Screen neeche scroll kar diya hai."
    elif direction in ("up", "upar"):
        # Swipe down to scroll up
        _run_adb(["shell", "input", "swipe", "500", "400", "500", "1400", "300"])
        return "Screen upar scroll kar diya hai."
    return "Scroll direction clear nahi hai."


def take_mobile_screenshot() -> str:
    """Takes a screenshot of the phone screen and pulls to PC."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    save_dir = Path(__file__).resolve().parent.parent / "data"
    save_dir.mkdir(parents=True, exist_ok=True)
    local_path = save_dir / "mobile_screenshot.png"

    _run_adb(["shell", "screencap", "-p", "/sdcard/jarvis_screen.png"])
    code, _ = _run_adb(["pull", "/sdcard/jarvis_screen.png", str(local_path)])
    if code == 0 and local_path.exists():
        return f"Mobile screenshot lekar save kar liya gaya hai: {local_path.name}"
    return "Screenshot lene me dikkat aayi."


def send_whatsapp_message(phone_number: str, message: str) -> str:
    """Opens WhatsApp chat with the specified number and message, then taps send."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    clean_num = re.sub(r"[^\d]", "", phone_number)
    if len(clean_num) == 10:
        clean_num = "91" + clean_num  # default to India country code if 10 digits

    encoded_msg = subprocess.list2cmdline([message]).strip('"')
    url = f"https://api.whatsapp.com/send?phone={clean_num}&text={encoded_msg}"
    _run_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])
    time.sleep(2.0)
    # Tap the send button (standard WhatsApp send button coordinates around right-bottom)
    # Also press enter key
    _run_adb(["shell", "input", "keyevent", "66"])
    return f"WhatsApp par {clean_num} ko message bhej diya gaya hai, Sir."


def type_on_phone(text: str) -> str:
    """Types text on the phone active input field."""
    connected, _ = _ensure_connected()
    if not connected:
        return "Phone connected nahi hai."

    # ADB input text replaces spaces with %s
    formatted = text.replace(" ", "%s")
    _run_adb(["shell", "input", "text", formatted])
    return f"Phone par type kar diya: {text}"


def mobile_control(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Main entry point for mobile_control tool dispatched by JARVIS.
    """
    params = parameters or {}
    action = str(params.get("action", "status")).lower().strip()
    target = str(params.get("target", "")).strip()
    message = str(params.get("message", "")).strip()
    ip = str(params.get("ip", "")).strip()

    # Route action
    if action in ("enable_mode", "turn_on_mobile", "mobile_on", "start_mobile"):
        try:
            from memory.config_manager import save_mobile_mode_enabled
            save_mobile_mode_enabled(True)
        except Exception:
            pass
        connected, dev = _ensure_connected()
        status_extra = f" Phone ({dev}) se connected hai." if connected else " Phone Wi-Fi se connect ho raha hai."
        res = f"Boss, Mobile System ON kar diya gaya hai.{status_extra} Ab aap jo bhi bolenge wo mobile phone par hoga."
    elif action in ("disable_mode", "turn_off_mobile", "mobile_off", "stop_mobile"):
        try:
            from memory.config_manager import save_mobile_mode_enabled
            save_mobile_mode_enabled(False)
        except Exception:
            pass
        res = "Boss, Mobile System OFF kar diya gaya hai. Ab aapke voice commands PC ko control karenge."
    elif action in ("toggle_mode",):
        try:
            from memory.config_manager import get_mobile_mode_enabled, save_mobile_mode_enabled
            curr = get_mobile_mode_enabled()
            save_mobile_mode_enabled(not curr)
            state = "ON" if not curr else "OFF"
            res = f"Boss, Mobile System ab {state} hai."
        except Exception:
            res = "Mobile mode toggle kar diya gaya hai."
    elif action == "connect":
        res = connect_phone(ip=ip or target)
    elif action in ("status", "battery", "info", "battery_status"):
        res = get_phone_status()
    elif action in ("open_app", "launch", "open"):
        res = open_mobile_app(target or "whatsapp")
    elif action in ("close_app", "exit_app", "stop"):
        res = close_mobile_app(target or "whatsapp")
    elif action in ("call", "phone_call", "dial"):
        res = make_phone_call(target)
    elif action in ("end_call", "cut_call", "hangup"):
        res = end_phone_call()
    elif action in ("lock", "unlock"):
        res = lock_unlock_screen(action)
    elif action in ("volume_up", "volume_down", "mute"):
        res = adjust_volume(action.replace("volume_", ""))
    elif action in ("home", "back", "recent_apps"):
        res = navigation_key(action)
    elif action in ("scroll_down", "scroll_up", "next_reel"):
        direction = "down" if action in ("scroll_down", "next_reel") else "up"
        res = scroll_screen(direction)
    elif action in ("screenshot", "screen_capture"):
        res = take_mobile_screenshot()
    elif action in ("whatsapp_message", "send_whatsapp"):
        res = send_whatsapp_message(target, message)
    elif action in ("type", "type_text"):
        res = type_on_phone(target or message)
    else:
        # Fallback heuristic
        if "lock" in action:
            res = lock_unlock_screen("lock")
        elif "unlock" in action:
            res = lock_unlock_screen("unlock")
        elif "app" in action and target:
            res = open_mobile_app(target)
        else:
            res = get_phone_status()

    if player:
        try:
            player.write_log(f"[mobile_control] {res[:60]}")
        except Exception:
            pass

    return res


TOOL = {
    "name": "mobile_control",
    "description": (
        "Controls user's Android smartphone wirelessly via ADB. "
        "Use this tool whenever the user asks to control mobile or turn on/off mobile system: "
        "turn on/off mobile mode ('mobile system on/off karo', 'mobile mode chalu karo'), "
        "connect phone ('phone connect karo', 'mobile connect karo'), "
        "check phone battery or status ('mobile battery kitni hai', 'phone status'), "
        "open mobile apps ('WhatsApp kholo', 'YouTube chalao', 'Instagram kholo', 'Camera on karo'), "
        "close mobile apps ('phone me app band karo'), "
        "make phone calls ('mobile se call lagao', 'call 9876543210'), "
        "end calls ('phone call kaat do'), "
        "lock/unlock phone screen ('phone lock kardo', 'mobile unlock karo'), "
        "control mobile volume ('phone volume badhao/kam karo'), "
        "navigate phone ('phone home/back karo'), "
        "scroll mobile screen ('phone screen scroll karo', 'next reel karo'), "
        "take phone screenshot ('mobile ka screenshot lo'), "
        "send WhatsApp message on phone ('phone se WhatsApp message bhejo'), "
        "or type text on phone. When mobile system is ON, user commands for apps/calls/reels/screen target the mobile phone."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform on mobile: enable_mode | disable_mode | connect | status | open_app | close_app | "
                    "call | end_call | lock | unlock | volume_up | volume_down | mute | "
                    "home | back | recent_apps | scroll_down | scroll_up | screenshot | "
                    "whatsapp_message | type_text"
                ),
            },
            "target": {
                "type": "STRING",
                "description": "App name (e.g. 'whatsapp', 'youtube'), phone number, contact name, or text to type",
            },
            "message": {
                "type": "STRING",
                "description": "Message content for WhatsApp or SMS",
            },
            "ip": {
                "type": "STRING",
                "description": "Phone IP and port for connection (e.g. '10.190.62.50:5555')",
            },
        },
        "required": ["action"],
    },
    "handler": mobile_control,
}
