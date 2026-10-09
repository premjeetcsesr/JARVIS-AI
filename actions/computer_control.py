#computer_control.py
import io
import json
import platform
import re
import string
import subprocess
import sys

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}
import time
import random
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )

def _get_os() -> str:
    return _load_config().get("os_system", _platform_os()).lower()


def _get_api_key() -> str:
    return _load_config().get("gemini_api_key", "")

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if x is not None and y is not None:
        try:
            pyautogui.moveTo(x, y, duration=0.15)
        except Exception:
            pass
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"{'Double-c' if clicks == 2 else 'C'}licked ({x}, {y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"Clicked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    try:
        vertical   = direction in ("up", "down")
        clicks     = amount if direction in ("up", "right") else -amount
        pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
        return f"Scrolled {direction} x{amount}"
    except Exception as e:
        return f"Scroll failed: {e}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse -> ({x}, {y})"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return f"Dragged ({x1},{y1}) -> ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    select_key = "command" if _get_os() == "mac" else "ctrl"
    pyautogui.hotkey(select_key, "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5, **_WIN_HIDE,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"

def _grab_screenshot_gdi():
    """Ultra-reliable and fast Windows GDI screen capture using ctypes."""
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        if w <= 0 or h <= 0:
            return None

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

        ret = gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020 | 0x40000000)
        if not ret:
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
        img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)

        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        return img
    except Exception as e:
        return None

def _grab_screenshot():
    """
    Captures the screen with multiple fallback backends:
    1. Native Windows GDI (BitBlt) on Windows (fastest, never fails)
    2. mss (multi-monitor support)
    3. PIL ImageGrab
    4. pyautogui.screenshot()
    Returns a PIL.Image object, or None if all backends fail.
    """
    img = None
    if platform.system() == "Windows":
        img = _grab_screenshot_gdi()

    if img is None:
        try:
            import mss
            with mss.mss() as sct:
                monitors = sct.monitors
                target = monitors[1] if len(monitors) > 1 else monitors[0]
                shot = sct.grab(target)
                from PIL import Image
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        except Exception:
            pass

    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
        except Exception:
            pass

    if img is None:
        try:
            if _PYAUTOGUI:
                img = pyautogui.screenshot()
        except Exception:
            pass

    return img


def _screen_find(description: str) -> tuple[int, int] | None:
    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] [!] No API key for screen_find")
        return None

    try:
        from google import genai
        from google.genai import types as gtypes
        from PIL import Image

        _require_pyautogui()
        screen_w, screen_h = pyautogui.size()

        img = _grab_screenshot()
        if img is None:
            print("[ComputerControl] [!] Failed to capture screen using all available methods.")
            return None

        img_w, img_h = img.size

        # Optimize size for fast REST upload if very high-DPI (e.g. 4K)
        max_dim = 1600
        proc_img = img
        if max(img_w, img_h) > max_dim:
            ratio = max_dim / float(max(img_w, img_h))
            new_size = (int(img_w * ratio), int(img_h * ratio))
            proc_img = img.resize(new_size, Image.Resampling.BILINEAR)

        curr_w, curr_h = proc_img.size

        buf = io.BytesIO()
        proc_img.convert("RGB").save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        # Clean description for Hindi / Hinglish and generic button phrasing
        raw_desc = (description or "").strip()
        desc_lower = raw_desc.lower()

        clean_desc = re.sub(
            r'\s*(?:par|pe|ko|bhi|sa)?\s*(?:click|press|karo|kar do|dabao|chalao|khol do|trigger karo)\s*$',
            '',
            desc_lower,
            flags=re.IGNORECASE
        ).strip()
        clean_desc = re.sub(r'^(?:browser|brouser|chrome)\s*(?:me|in|par)?\s*', '', clean_desc).strip()

        generic_button_keywords = {
            "kisi button", "any button", "koi button", "button", "koi bhi button",
            "koi sa button", "a button", "some button", "kisi bhi button", "trigger", ""
        }
        is_generic = clean_desc in generic_button_keywords

        if is_generic:
            prompt = (
                f"This is a {curr_w}x{curr_h} screenshot of the computer screen. "
                f"Locate the most prominent or primary clickable action button or interactive control on the active window or webpage "
                f"(such as the primary CTA button, submit button, search button, play button, login button, or first interactive button). "
                f"Reply with ONLY its center coordinates in pixel format: x,y "
                f"Example: 640,360\n"
                f"If absolutely no button is visible, reply: NOT_FOUND"
            )
        else:
            prompt = (
                f"This is a {curr_w}x{curr_h} screenshot of the computer screen. "
                f"Locate the UI element or button described as: '{clean_desc}'. "
                f"Reply with ONLY its center coordinates in pixel format: x,y "
                f"Example: 640,360\n"
                f"If the element is not visible, reply: NOT_FOUND"
            )

        from core import gemini
        cl = gemini.client(timeout_ms=25_000, key=api_key)

        models_to_try = [
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash"
        ]
        text = ""
        for model_name in models_to_try:
            try:
                resp = cl.models.generate_content(
                    model=model_name,
                    contents=[
                        gtypes.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        prompt,
                    ],
                )
                if resp and resp.text:
                    candidate = resp.text.strip()
                    if candidate:
                        text = candidate
                        break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower():
                    continue
                print(f"[ComputerControl] Model {model_name} attempt: {e}")

        if not text or "NOT_FOUND" in text.upper():
            print(f"[ComputerControl] Element '{description}' not found on screen.")
            return None

        # Check for standard x,y format
        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            raw_x = int(match.group(1))
            raw_y = int(match.group(2))

            # If coords are normalized 0-1000 but image is larger:
            if raw_x <= 1000 and raw_y <= 1000 and curr_w > 1200 and "normalized" in text.lower():
                raw_x = int(raw_x / 1000.0 * curr_w)
                raw_y = int(raw_y / 1000.0 * curr_h)

            # Scale back to original screen dimensions (accounting for DPI scaling)
            scale_x = screen_w / float(curr_w)
            scale_y = screen_h / float(curr_h)
            target_x = int(raw_x * scale_x)
            target_y = int(raw_y * scale_y)

            # Clamp within screen bounds
            target_x = max(0, min(screen_w - 1, target_x))
            target_y = max(0, min(screen_h - 1, target_y))
            print(f"[ComputerControl] Found '{description}' -> screen coords ({target_x}, {target_y})")
            return target_x, target_y

    except Exception as e:
        print(f"[ComputerControl] screen_find failed: {e}")

    return None


def _fill_input(
    description: str = "",
    text: str = "",
    clear_first: bool = True,
    press_enter: bool = False,
    x: int = None,
    y: int = None,
) -> str:
    _require_pyautogui()
    coords = None
    if x is not None and y is not None:
        coords = (int(x), int(y))
    elif description:
        coords = _screen_find(description)

    if coords:
        time.sleep(0.15)
        _click(coords[0], coords[1])
        time.sleep(0.2)
    elif description:
        return f"Could not find input field on screen: '{description}'"

    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if _PYPERCLIP and text:
        _clipboard_paste(text)
    elif text:
        _type(text)

    if press_enter:
        time.sleep(0.15)
        _press("enter")

    return f"Filled '{description or 'field'}' with: '{text}'" + (" (pressed Enter)" if press_enter else "")

def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      button        : 'left' | 'right' (default: left)
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window
      description   : natural-language element description for screen_find/click
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — left click
      double_click  — double left click
      right_click   — right click
      move          — move mouse
      drag          — click-drag between two points
      hotkey        — key combination
      press         — single key
      scroll        — scroll the wheel
      copy          — read clipboard
      paste         — write + paste clipboard
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      screen_find   — AI element finder (returns x,y)
      screen_click  — AI element finder + click
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] > {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click"):
            desc = params.get("description", "")
            if desc and params.get("x") is None:
                coords = _screen_find(desc)
                if coords:
                    time.sleep(0.15)
                    _click(coords[0], coords[1])
                    return f"Clicked '{desc}' at {coords}"
                return f"Element not found on screen: '{desc}'"
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "move":
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action in ("fill_input", "fill_field", "screen_fill", "type_field"):
            return _fill_input(
                description=params.get("description", ""),
                text=params.get("text", ""),
                clear_first=params.get("clear_first", True),
                press_enter=params.get("press_enter", False),
                x=params.get("x"),
                y=params.get("y"),
            )

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] random {dt} -> {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] No '{field}' in memory, using random: {value}")
            return value

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] Error in {action}: {e}")
        return f"computer_control '{action}' failed: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "computer_control",
    "description": "Direct computer control: type, fill input fields, click, hotkeys, scroll, move mouse, screenshots, find elements on screen, web forms.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | fill_input | random_data | user_data"
            },
            "text": {
                "type": "STRING",
                "description": "Text to type or paste into inputs/fields"
            },
            "x": {
                "type": "INTEGER",
                "description": "X coordinate"
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate"
            },
            "keys": {
                "type": "STRING",
                "description": "Key combination e.g. 'ctrl+c'"
            },
            "key": {
                "type": "STRING",
                "description": "Single key e.g. 'enter'"
            },
            "direction": {
                "type": "STRING",
                "description": "up | down | left | right"
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount (default: 3)"
            },
            "seconds": {
                "type": "NUMBER",
                "description": "Seconds to wait"
            },
            "title": {
                "type": "STRING",
                "description": "Window title for focus_window"
            },
            "description": {
                "type": "STRING",
                "description": "Element description for screen_find/screen_click/fill_input (e.g. 'search bar', 'username input', 'submit button')"
            },
            "press_enter": {
                "type": "BOOLEAN",
                "description": "Press enter after filling input (default: false)"
            },
            "type": {
                "type": "STRING",
                "description": "Data type for random_data"
            },
            "field": {
                "type": "STRING",
                "description": "Field for user_data: name|email|city"
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear field before typing (default: true)"
            },
            "path": {
                "type": "STRING",
                "description": "Save path for screenshot"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": computer_control,
}
